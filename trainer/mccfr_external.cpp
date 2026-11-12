#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>
#include <sys/resource.h>
#include "../engine/src/mccfr_policy.hpp"
#include "../engine/vendor/json.hpp"
using json=nlohmann::json;
namespace fs=std::filesystem;
using namespace std;
static constexpr const char* RULESET="fixed5_score5_quantity_only_v1";
struct Node {vector<string> actions;vector<double> regret,average;};
struct State {mccfr::Hand hand[2];vector<mccfr::Bid> history;int starter=0,turn=0;};
struct Trainer {
  mt19937_64 rng;uint64_t seed,terminals=0;bool toy=false;
  unordered_map<string,Node> table;
  explicit Trainer(uint64_t s,bool t):rng(s),seed(s),toy(t){}
  static vector<double> strategy(const vector<double>& regrets){
    vector<double> p(regrets.size());double total=0;
    for(size_t i=0;i<p.size();++i){if(!isfinite(regrets[i]))throw runtime_error("nonfinite regret");p[i]=max(0.0,regrets[i]);total+=p[i];}
    if(!isfinite(total))throw runtime_error("nonfinite regret sum");
    if(total>0)for(double& x:p)x/=total;
    else for(double& x:p)x=1.0/double(p.size());
    return p;
  }
  int die(){return int(uniform_int_distribution<int>(1,6)(rng));}
  double unit(){return generate_canonical<double,53>(rng);}
  int sample(const vector<double>& p){double r=unit();for(size_t i=0;i<p.size();++i){r-=p[i];if(r<=0)return int(i);}return int(p.size()-1);}
  vector<string> actions(const State& s)const{
    if(!toy)return mccfr::actions(s.hand[s.turn],s.history);
    vector<string> a;
    if(s.history.empty()){for(int q=1;q<=2;++q)for(int f=1;f<=6;++f)a.push_back(to_string(q)+"-"+to_string(f));}
    else if(s.history.back().q==1){for(int f=1;f<=6;++f)a.push_back("2-"+to_string(f));a.push_back("C");}
    else a.push_back("C");
    return a;
  }
  string key(const State& s)const{
    if(!toy)return mccfr::key(s.starter,s.turn,s.hand[s.turn],s.history);
    string k=to_string(s.turn)+"|"+to_string(s.hand[s.turn][0])+"|";
    for(size_t i=0;i<s.history.size();++i){if(i)k+=",";k+=to_string((s.history[i].q-1)*6+s.history[i].f-1);}return k;
  }
  double call_value(const State& s,int traverser) {
    ++terminals;const auto bid=s.history.back();int n=0;
    for(int p=0;p<2;++p)for(int i=0;i<(toy?1:5);++i)n+=s.hand[p][i]==bid.f;
    const int winner=n>=bid.q?1-s.turn:s.turn;
    return winner==traverser?1.0:-1.0;
  }
  double traverse(State& s,int traverser){
    auto acts=actions(s);auto k=key(s);
    auto [it,inserted]=table.try_emplace(k);
    if(inserted){it->second.actions=acts;it->second.regret.assign(acts.size(),0);it->second.average.assign(acts.size(),0);}
    else if(it->second.actions!=acts)throw runtime_error("information set has inconsistent actions: "+k);
    auto p=strategy(it->second.regret);
    auto advance=[&](const string& action)->double{
      if(action=="C")return call_value(s,traverser);
      s.history.push_back(mccfr::parse_bid(action));s.turn=1-s.turn;
      double v=traverse(s,traverser);
      s.turn=1-s.turn;s.history.pop_back();return v;
    };
    if(s.turn!=traverser){
      // Opponent-node average: prior sampled actions of this player already
      // weight visitation by its own reach probability (OpenSpiel simple average).
      auto& avg=table.at(k).average;
      for(size_t i=0;i<p.size();++i){avg[i]+=p[i];if(!isfinite(avg[i]))throw runtime_error("nonfinite average sum");}
      return advance(acts[size_t(sample(p))]);
    }
    vector<double> values;values.reserve(acts.size());double node=0;
    for(size_t i=0;i<acts.size();++i){double v=advance(acts[i]);values.push_back(v);node+=p[i]*v;}
    auto& regret=table.at(k).regret;
    for(size_t i=0;i<acts.size();++i){regret[i]+=values[i]-node;if(!isfinite(regret[i]))throw runtime_error("nonfinite regret");}
    return node;
  }
  void iteration(){
    for(int traverser=0;traverser<2;++traverser){
      State s;s.starter=toy?0:int(uniform_int_distribution<int>(0,1)(rng));s.turn=s.starter;
      for(int p=0;p<2;++p)for(int i=0;i<(toy?1:5);++i)s.hand[p][i]=die();
      traverse(s,traverser);
    }
  }
  json policy(uint64_t iterations)const{
    json out={{"format_version",1},{"ruleset",toy?"quantity_only_n1_toy":RULESET},{"policy_id",toy?"mccfr_external_toy":"mccfr_external_v1"},{"algorithm","external-sampling MCCFR; opponent-node sampled averaging"},{"objective","one-round +1/-1 point utility"},{"iterations",iterations},{"traversals",iterations*2},{"information_abstraction",toy?"full public history and private die":"private histogram, starter, player, last two public bids; imperfect recall"},{"action_abstraction",toy?"all one-die legal bids":"opening 1 any face or 2 modal; raise +1/+2 current or modal face; call"},{"policy",json::object()}};
    map<string,const Node*> ordered;for(const auto& [k,n]:table)ordered[k]=&n;
    for(const auto& [k,n]:ordered){double total=0;for(double x:n->average)total+=x;
      if(total<=0)continue;
      json weights=json::object();for(size_t i=0;i<n->actions.size();++i)weights[n->actions[i]]=n->average[i]/total;
      out["policy"][k]=weights;
    }
    return out;
  }
  json checkpoint(uint64_t iterations)const{
    ostringstream stream;stream<<rng;
    json out={{"format_version",1},{"mode",toy?"toy":"fixed5"},{"seed",seed},{"iterations",iterations},{"terminals",terminals},{"rng",stream.str()},{"table",json::object()}};
    map<string,const Node*> ordered;for(const auto& [k,n]:table)ordered[k]=&n;
    for(const auto& [k,n]:ordered)out["table"][k]={{"actions",n->actions},{"regret",n->regret},{"average",n->average}};
    return out;
  }
  void restore(const json& saved){
    if(saved.at("format_version")!=1||saved.at("mode")!=(toy?"toy":"fixed5")||saved.at("seed")!=seed)throw runtime_error("incompatible checkpoint");
    istringstream stream(saved.at("rng").get<string>());stream>>rng;if(!stream)throw runtime_error("corrupt RNG state");
    terminals=saved.at("terminals");
    for(auto it=saved.at("table").begin();it!=saved.at("table").end();++it){
      Node n{it.value().at("actions").get<vector<string>>(),it.value().at("regret").get<vector<double>>(),it.value().at("average").get<vector<double>>()};
      if(n.actions.empty()||n.actions.size()!=n.regret.size()||n.actions.size()!=n.average.size()||
         !all_of(n.regret.begin(),n.regret.end(),[](double x){return isfinite(x);})||
         !all_of(n.average.begin(),n.average.end(),[](double x){return isfinite(x)&&x>=0;}))throw runtime_error("corrupt checkpoint table");
      table.emplace(it.key(),std::move(n));
    }
  }
};
static void atomic_json(const fs::path& path,const json& value){
  auto pending=path;pending+=".pending";{ofstream f(pending);if(!f)throw runtime_error("cannot open "+pending.string());f<<value.dump();if(!f)throw runtime_error("write failed");}fs::rename(pending,path);
}
static void guard(const fs::path& folder){
  if(fs::space(folder).available<2ULL*1024*1024*1024)throw runtime_error("2 GiB free-disk guard reached");
  uintmax_t bytes=0;for(const auto& e:fs::directory_iterator(folder))if(e.is_regular_file())bytes+=e.file_size();
  if(bytes>uintmax_t(1.5*1024*1024*1024))throw runtime_error("1.5 GiB experiment-artifact cap reached");
}
static uint64_t peak_memory_bytes(){
  rusage usage{};if(getrusage(RUSAGE_SELF,&usage)!=0)return 0;
#ifdef __APPLE__
  return uint64_t(usage.ru_maxrss);
#else
  return uint64_t(usage.ru_maxrss)*1024;
#endif
}
static void self_test(){
  auto require=[](bool ok,const string& message){if(!ok)throw runtime_error("self-test failed: "+message);};
  auto p=Trainer::strategy({-3,2,4});
  require(p.size()==3&&p[0]==0&&abs(p[1]-1.0/3)<1e-12&&abs(p[2]-2.0/3)<1e-12,"regret matching");
  p=Trainer::strategy({-2,0,0});require(abs(p[0]-1.0/3)<1e-12,"uniform zero-positive regrets");
  Trainer t(42,false);int counts[3]{};
  for(int i=0;i<100000;++i)++counts[t.sample({0.2,0.3,0.5})];
  require(abs(counts[0]-20000)<500&&abs(counts[1]-30000)<500&&abs(counts[2]-50000)<500,"sample distribution");
  mccfr::Hand a{1,1,2,3,4},b{6,6,6,6,6};
  State s;s.hand[0]=a;s.hand[1]=b;s.turn=0;
  auto k=t.key(s);s.hand[1]=a;require(t.key(s)==k,"private information leak");
  s.hand[1]=b;s.history.push_back({3,1});
  require(t.actions(s)==vector<string>({"C","4-1","5-1"}),"legal abstract actions");
  require(t.call_value(s,0)==1.0,"false bid caller wins");
  s.hand[1]=a;require(t.call_value(s,0)==-1.0,"true bid bidder wins");
  int dice[6]{};for(int i=0;i<60000;++i)++dice[t.die()-1];
  for(int n:dice)require(abs(n-10000)<350,"fair die distribution");
  cout<<"{\"self_test\":\"passed\"}"<<endl;
}
int main(int argc,char** argv)try{
  string run,git_commit;uint64_t seed=1729,target=0,every=10000;bool resume=false,toy=false,verify=false,export_only=false;vector<uint64_t> milestones;
  for(int i=1;i<argc;++i){string a=argv[i];
    if(a=="--run-id"&&i+1<argc)run=argv[++i];else if(a=="--seed"&&i+1<argc)seed=stoull(argv[++i]);
    else if(a=="--iterations"&&i+1<argc)target=stoull(argv[++i]);else if(a=="--checkpoint-every"&&i+1<argc)every=stoull(argv[++i]);
    else if(a=="--milestones"&&i+1<argc){istringstream stream(argv[++i]);string part;while(getline(stream,part,','))milestones.push_back(stoull(part));}
    else if(a=="--git-commit"&&i+1<argc)git_commit=argv[++i];
    else if(a=="--resume")resume=true;else if(a=="--toy")toy=true;else if(a=="--self-test")verify=true;else if(a=="--export-only")export_only=true;else throw runtime_error("unknown or incomplete argument: "+a);
  }
  if(verify){self_test();return 0;}
  if(run.empty()||run.find('/')!=string::npos||run.find("..")!=string::npos||(!export_only&&target==0)||every==0||target>1000000)throw runtime_error("invalid run ID or training budget");
  if(!git_commit.empty()&&(git_commit.size()!=40||!all_of(git_commit.begin(),git_commit.end(),[](char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');})))throw runtime_error("invalid git commit");
  for(auto milestone:milestones)if(milestone==0||milestone>target)throw runtime_error("invalid milestone");
  fs::path folder=fs::path("experiments/runs")/run;uint64_t start=0;
  if(resume||export_only){if(!fs::exists(folder/"checkpoint.json"))throw runtime_error("checkpoint missing");}
  else if(!fs::create_directories(folder))throw runtime_error("run directory already exists");
  guard(folder);Trainer trainer(seed,toy);
  if(resume||export_only){json saved;ifstream f(folder/"checkpoint.json");f>>saved;trainer.restore(saved);start=saved.at("iterations");if(resume&&!export_only&&start>=target)throw runtime_error("target must exceed checkpoint");}
  if(export_only){atomic_json(folder/("policy_"+to_string(start)+".json"),trainer.policy(start));cout<<json({{"iterations",start},{"information_sets",trainer.table.size()},{"exported",true}}).dump()<<endl;return 0;}
  auto clock_start=chrono::steady_clock::now();
  json manifest={{"run_id",run},{"status","started"},{"mode",toy?"toy":"fixed5"},{"ruleset",toy?"quantity_only_n1_toy":RULESET},{"algorithm","external-sampling MCCFR"},{"seed",seed},{"git_commit",git_commit.empty()?json(nullptr):json(git_commit)},{"iterations_planned",target},{"iterations_resumed_from",start},{"checkpoint_every",every},{"milestones",milestones},{"workers",1},{"command",json::array()}};
  for(int i=0;i<argc;++i)manifest["command"].push_back(argv[i]);atomic_json(folder/"manifest.json",manifest);
  try{
    for(uint64_t n=start+1;n<=target;++n){trainer.iteration();
      if((milestones.empty()&&n%every==0)||std::find(milestones.begin(),milestones.end(),n)!=milestones.end()||n==target){guard(folder);
        atomic_json(folder/"checkpoint.json",trainer.checkpoint(n));
        atomic_json(folder/("policy_"+to_string(n)+".json"),trainer.policy(n));
        const double elapsed=chrono::duration<double>(chrono::steady_clock::now()-clock_start).count();
        cout<<json({{"iterations",n},{"traversals",n*2},{"terminals",trainer.terminals},{"information_sets",trainer.table.size()},{"elapsed_seconds",elapsed},{"peak_memory_bytes",peak_memory_bytes()}}).dump()<<endl;
      }
    }
    manifest["status"]="completed";manifest["iterations_completed"]=target;
    manifest["elapsed_seconds"]=chrono::duration<double>(chrono::steady_clock::now()-clock_start).count();
    manifest["terminals"]=trainer.terminals;manifest["information_sets"]=trainer.table.size();manifest["peak_memory_bytes"]=peak_memory_bytes();atomic_json(folder/"manifest.json",manifest);
  }catch(const exception& e){manifest["status"]="failed";manifest["error"]=e.what();atomic_json(folder/"manifest.json",manifest);throw;}
  return 0;
}catch(const exception& e){cerr<<e.what()<<endl;return 1;}
