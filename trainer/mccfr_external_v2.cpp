#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <ctime>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>
#include <sys/resource.h>
#include <zlib.h>
#include "../engine/src/mccfr_v2_policy.hpp"
#include "../engine/vendor/json.hpp"

using json=nlohmann::json;
namespace fs=std::filesystem;
using namespace std;
static constexpr const char* RULESET="fixed5_score5_quantity_only_v1";
static constexpr size_t MAX_FINE_SETS=1800000;

struct Node {
  uint8_t n=0;
  array<uint8_t,mccfr_v2::MAX_ACTIONS> ids{};
  array<double,mccfr_v2::MAX_ACTIONS> regret{},average{};
};
struct Coarse {
  uint8_t n=0;
  array<uint8_t,mccfr_v2::MAX_ACTIONS> ids{};
  array<double,mccfr_v2::MAX_ACTIONS> average{};
};
struct State {
  mccfr_v2::Hand hand[2]{};
  vector<mccfr_v2::Bid> history;
  int starter=0,turn=0,score[2]{0,0};
};

struct Trainer {
  mt19937_64 rng;
  uint64_t seed,terminals=0;
  double starter_win_probability;
  bool toy=false,enumerate_starters=false;
  unordered_map<string,Node> table;
  unordered_map<string,Coarse> backoff;
  double continuation[6][6][2]{};

  Trainer(uint64_t s,double p,bool t,bool enumerate):rng(s),seed(s),starter_win_probability(p),toy(t),enumerate_starters(enumerate){
    if(!isfinite(p)||p<=0||p>=1)throw runtime_error("invalid continuation probability");
    for(int total=9;total>=0;--total)for(int score0=0;score0<=5;++score0)for(int score1=0;score1<=5;++score1){
      if(score0+score1!=total&&score0<5&&score1<5)continue;
      for(int starter=0;starter<2;++starter){
        if(score0==5)continuation[score0][score1][starter]=1;
        else if(score1==5)continuation[score0][score1][starter]=0;
        else {
          double p0=starter==0?p:1-p;
          continuation[score0][score1][starter]=p0*continuation[score0+1][score1][1]+(1-p0)*continuation[score0][score1+1][0];
        }
      }
    }
  }
  static vector<double> strategy(const Node& node){
    vector<double> probabilities(node.n);double total=0;
    for(int i=0;i<node.n;++i){
      if(!isfinite(node.regret[i]))throw runtime_error("nonfinite regret");
      probabilities[i]=max(0.0,node.regret[i]);total+=probabilities[i];
    }
    if(!isfinite(total))throw runtime_error("nonfinite strategy sum");
    if(total>0)for(double& value:probabilities)value/=total;
    else for(double& value:probabilities)value=1.0/node.n;
    return probabilities;
  }
  int die(){return int(uniform_int_distribution<int>(1,6)(rng));}
  int sample(const vector<double>& probabilities){
    double draw=generate_canonical<double,53>(rng);
    for(size_t i=0;i<probabilities.size();++i){draw-=probabilities[i];if(draw<=0)return int(i);}
    return int(probabilities.size()-1);
  }
  vector<uint8_t> actions(const State& state)const{
    if(!toy)return mccfr_v2::actions(state.hand[state.turn],state.history);
    vector<uint8_t> out;
    if(state.history.empty())for(int q=1;q<=2;++q)for(int f=1;f<=6;++f)out.push_back(mccfr_v2::action_id(q,f));
    else {out.push_back(0);if(state.history.back().q==1)for(int f=1;f<=6;++f)out.push_back(mccfr_v2::action_id(2,f));}
    return out;
  }
  string key(const State& state)const{
    if(!toy)return mccfr_v2::fine_key(state.starter,state.turn,state.hand[state.turn],state.history);
    string key=to_string(state.turn)+"|"+to_string(state.hand[state.turn][0])+"|";
    for(size_t i=0;i<state.history.size();++i){if(i)key+=',';key+=to_string((state.history[i].q-1)*6+state.history[i].f-1);}
    return key;
  }
  double terminal(const State& state,int traverser){
    ++terminals;
    const auto bid=state.history.back();int matching=0;
    for(int player=0;player<2;++player)for(int die_index=0;die_index<(toy?1:5);++die_index)
      matching+=state.hand[player][die_index]==bid.f;
    int winner=matching>=bid.q?1-state.turn:state.turn;
    if(toy)return winner==traverser?1:-1;
    int score0=state.score[0]+(winner==0),score1=state.score[1]+(winner==1);
    double match_win=continuation[score0][score1][1-winner];
    return traverser==0?2*match_win-1:1-2*match_win;
  }
  double traverse(State& state,int traverser){
    auto available=actions(state);
    auto information=key(state);
    auto [it,inserted]=table.try_emplace(information);
    if(inserted){
      if(table.size()>MAX_FINE_SETS)throw runtime_error("fine information-set cap reached");
      it->second.n=uint8_t(available.size());
      copy(available.begin(),available.end(),it->second.ids.begin());
    }else if(it->second.n!=available.size()||!equal(available.begin(),available.end(),it->second.ids.begin()))
      throw runtime_error("inconsistent information-set actions");
    auto probabilities=strategy(it->second);
    auto advance=[&](uint8_t action)->double{
      if(action==0)return terminal(state,traverser);
      state.history.push_back(mccfr_v2::bid_for(action));state.turn=1-state.turn;
      double value=traverse(state,traverser);
      state.turn=1-state.turn;state.history.pop_back();return value;
    };
    if(state.turn!=traverser){
      auto& node=table.at(information);
      for(size_t i=0;i<available.size();++i){
        node.average[i]+=probabilities[i];
        if(!isfinite(node.average[i]))throw runtime_error("nonfinite average");
      }
      if(!toy){
        auto coarse_key=mccfr_v2::backoff_key(state.starter,state.turn,state.hand[state.turn],state.history);
        auto& coarse=backoff[coarse_key];
        if(coarse.n==0){coarse.n=uint8_t(available.size());copy(available.begin(),available.end(),coarse.ids.begin());}
        else if(coarse.n!=available.size()||!equal(available.begin(),available.end(),coarse.ids.begin()))throw runtime_error("inconsistent backoff actions");
        for(size_t i=0;i<available.size();++i){coarse.average[i]+=probabilities[i];if(!isfinite(coarse.average[i]))throw runtime_error("nonfinite backoff average");}
      }
      return advance(available[size_t(sample(probabilities))]);
    }
    vector<double> values;values.reserve(available.size());double expected=0;
    for(size_t i=0;i<available.size();++i){
      double value=advance(available[i]);values.push_back(value);expected+=probabilities[i]*value;
    }
    auto& node=table.at(information);
    for(size_t i=0;i<available.size();++i){node.regret[i]+=values[i]-expected;if(!isfinite(node.regret[i]))throw runtime_error("nonfinite cumulative regret");}
    return expected;
  }
  void iteration(){
    State state;
    state.score[0]=toy?0:int(uniform_int_distribution<int>(0,4)(rng));
    state.score[1]=toy?0:int(uniform_int_distribution<int>(0,4)(rng));
    for(int player=0;player<2;++player)for(int die_index=0;die_index<(toy?1:5);++die_index)state.hand[player][die_index]=die();
    int sampled_starter=toy?0:int(uniform_int_distribution<int>(0,1)(rng));
    for(int starter=0;starter<(enumerate_starters&&!toy?2:1);++starter){
      state.starter=enumerate_starters&&!toy?starter:sampled_starter;state.turn=state.starter;
      for(int traverser=0;traverser<2;++traverser)traverse(state,traverser);
    }
  }
};

static void gz_write(gzFile file,const void* data,size_t bytes){
  if(bytes>INT32_MAX||gzwrite(file,data,unsigned(bytes))!=int(bytes))throw runtime_error("checkpoint write failed");
}
static void gz_read(gzFile file,void* data,size_t bytes){
  if(bytes>INT32_MAX||gzread(file,data,unsigned(bytes))!=int(bytes))throw runtime_error("checkpoint truncated or corrupt");
}
static void write_node(gzFile file,const string& key,const Node& node){
  if(key.size()>UINT16_MAX)throw runtime_error("key too long");
  uint16_t length=uint16_t(key.size());gz_write(file,&length,sizeof(length));gz_write(file,key.data(),key.size());
  gz_write(file,&node.n,1);gz_write(file,node.ids.data(),node.ids.size());
  gz_write(file,node.regret.data(),node.regret.size()*sizeof(double));
  gz_write(file,node.average.data(),node.average.size()*sizeof(double));
}
static void write_coarse(gzFile file,const string& key,const Coarse& node){
  if(key.size()>UINT16_MAX)throw runtime_error("key too long");
  uint16_t length=uint16_t(key.size());gz_write(file,&length,sizeof(length));gz_write(file,key.data(),key.size());
  gz_write(file,&node.n,1);gz_write(file,node.ids.data(),node.ids.size());
  gz_write(file,node.average.data(),node.average.size()*sizeof(double));
}
static string read_key(gzFile file){
  uint16_t length=0;gz_read(file,&length,sizeof(length));
  if(length==0||length>512)throw runtime_error("invalid checkpoint key length");
  string key(length,'\0');gz_read(file,key.data(),length);return key;
}
static void save_checkpoint(const fs::path& path,const Trainer& trainer,uint64_t iterations){
  auto pending=path;pending+=".pending";
  gzFile file=gzopen(pending.string().c_str(),"wb6");if(!file)throw runtime_error("cannot open checkpoint");
  try{
    ostringstream rng_state;rng_state<<trainer.rng;
    json metadata={{"format_version",2},{"seed",trainer.seed},{"iterations",iterations},{"terminals",trainer.terminals},
      {"starter_win_probability",trainer.starter_win_probability},{"toy",trainer.toy},
      {"enumerate_starters",trainer.enumerate_starters},{"rng",rng_state.str()},
      {"fine_count",trainer.table.size()},{"backoff_count",trainer.backoff.size()}};
    string header=metadata.dump();uint64_t length=header.size();gz_write(file,&length,sizeof(length));gz_write(file,header.data(),header.size());
    map<string,const Node*> ordered;for(const auto& [key,node]:trainer.table)ordered[key]=&node;
    for(const auto& [key,node]:ordered)write_node(file,key,*node);
    map<string,const Coarse*> coarse;for(const auto& [key,node]:trainer.backoff)coarse[key]=&node;
    for(const auto& [key,node]:coarse)write_coarse(file,key,*node);
    int closed=gzclose(file);file=nullptr;if(closed!=Z_OK)throw runtime_error("checkpoint close failed");
    fs::rename(pending,path);
  }catch(...){if(file)gzclose(file);throw;}
}
static uint64_t load_checkpoint(const fs::path& path,Trainer& trainer){
  gzFile file=gzopen(path.string().c_str(),"rb");if(!file)throw runtime_error("cannot open checkpoint");
  try{
    uint64_t length=0;gz_read(file,&length,sizeof(length));if(length==0||length>1000000)throw runtime_error("invalid checkpoint header");
    string raw(length,'\0');gz_read(file,raw.data(),raw.size());json metadata=json::parse(raw);
    if(metadata.at("format_version")!=2||metadata.at("seed")!=trainer.seed||metadata.at("toy")!=trainer.toy||
       metadata.at("enumerate_starters")!=trainer.enumerate_starters||
       abs(metadata.at("starter_win_probability").get<double>()-trainer.starter_win_probability)>1e-12)
      throw runtime_error("incompatible checkpoint");
    istringstream rng_state(metadata.at("rng").get<string>());rng_state>>trainer.rng;
    if(!rng_state)throw runtime_error("invalid checkpoint RNG");
    trainer.terminals=metadata.at("terminals");
    size_t fine_count=metadata.at("fine_count"),coarse_count=metadata.at("backoff_count");
    if(fine_count>MAX_FINE_SETS||coarse_count>1000000)throw runtime_error("invalid checkpoint counts");
    trainer.table.clear();trainer.backoff.clear();trainer.table.reserve(fine_count);
    for(size_t index=0;index<fine_count;++index){
      string key=read_key(file);Node node;gz_read(file,&node.n,1);gz_read(file,node.ids.data(),node.ids.size());
      gz_read(file,node.regret.data(),node.regret.size()*sizeof(double));gz_read(file,node.average.data(),node.average.size()*sizeof(double));
      if(node.n==0||node.n>mccfr_v2::MAX_ACTIONS||
         !all_of(node.regret.begin(),node.regret.end(),[](double value){return isfinite(value);})||
         !all_of(node.average.begin(),node.average.end(),[](double value){return isfinite(value)&&value>=0;}))throw runtime_error("invalid checkpoint node");
      if(!trainer.table.emplace(std::move(key),node).second)throw runtime_error("duplicate checkpoint node");
    }
    trainer.backoff.reserve(coarse_count);
    for(size_t index=0;index<coarse_count;++index){
      string key=read_key(file);Coarse node;gz_read(file,&node.n,1);gz_read(file,node.ids.data(),node.ids.size());
      gz_read(file,node.average.data(),node.average.size()*sizeof(double));
      if(node.n==0||node.n>mccfr_v2::MAX_ACTIONS||
         !all_of(node.average.begin(),node.average.end(),[](double value){return isfinite(value)&&value>=0;}))throw runtime_error("invalid checkpoint backoff");
      if(!trainer.backoff.emplace(std::move(key),node).second)throw runtime_error("duplicate checkpoint backoff");
    }
    char trailing;if(gzread(file,&trailing,1)!=0)throw runtime_error("trailing checkpoint data");
    int closed=gzclose(file);file=nullptr;if(closed!=Z_OK)throw runtime_error("checkpoint CRC failed");
    return metadata.at("iterations");
  }catch(...){if(file)gzclose(file);throw;}
}

struct PolicyRecord {
  array<uint8_t,16> digest{};
  uint8_t n=0;
  array<uint8_t,mccfr_v2::MAX_ACTIONS> ids{};
  array<float,mccfr_v2::MAX_ACTIONS> weights{};
};
static PolicyRecord policy_record(const string& key,uint8_t n,const array<uint8_t,mccfr_v2::MAX_ACTIONS>& ids,
                                  const array<double,mccfr_v2::MAX_ACTIONS>& average){
  PolicyRecord record;record.digest=mccfr_v2::digest(key);record.n=n;record.ids=ids;
  double total=0;for(int i=0;i<n;++i)total+=average[i];
  if(!isfinite(total)||total<=0)throw runtime_error("invalid policy average");
  for(int i=0;i<n;++i)record.weights[i]=float(average[i]/total);
  return record;
}
static pair<size_t,size_t> save_policy(const fs::path& path,const Trainer& trainer){
  vector<PolicyRecord> records;records.reserve(trainer.table.size()+trainer.backoff.size());
  size_t fine_count=0,coarse_count=0;
  for(const auto& [key,node]:trainer.table){
    if(accumulate(node.average.begin(),node.average.begin()+node.n,0.0)>0){records.push_back(policy_record(key,node.n,node.ids,node.average));++fine_count;}
  }
  for(const auto& [key,node]:trainer.backoff){
    if(accumulate(node.average.begin(),node.average.begin()+node.n,0.0)>0){records.push_back(policy_record(key,node.n,node.ids,node.average));++coarse_count;}
  }
  sort(records.begin(),records.end(),[](const auto& a,const auto& b){return a.digest<b.digest;});
  for(size_t i=1;i<records.size();++i)if(records[i-1].digest==records[i].digest)throw runtime_error("policy key digest collision");
  auto pending=path;pending+=".pending";ofstream out(pending,ios::binary);if(!out)throw runtime_error("cannot write policy");
  const char magic[8]={'M','C','C','F','R','2','\0','\0'};uint64_t count=records.size();
  out.write(magic,8);out.write(reinterpret_cast<const char*>(&count),8);
  for(const auto& record:records){
    out.write(reinterpret_cast<const char*>(record.digest.data()),16);
    out.write(reinterpret_cast<const char*>(&record.n),1);
    out.write(reinterpret_cast<const char*>(record.ids.data()),record.ids.size());
    out.write(reinterpret_cast<const char*>(record.weights.data()),record.weights.size()*sizeof(float));
  }
  out.close();if(!out)throw runtime_error("policy write failed");fs::rename(pending,path);
  return {fine_count,coarse_count};
}
static void save_toy_policy(const fs::path& path,const Trainer& trainer,uint64_t iterations){
  json result={{"format_version",2},{"ruleset","quantity_only_n1_toy"},{"policy_id","mccfr_external_v2_toy"},
    {"iterations",iterations},{"policy",json::object()}};
  for(const auto& [key,node]:trainer.table){
    double total=accumulate(node.average.begin(),node.average.begin()+node.n,0.0);if(total<=0)continue;
    json distribution=json::object();
    for(int i=0;i<node.n;++i){
      int id=node.ids[i];auto bid=id?mccfr_v2::bid_for(uint8_t(id)):mccfr_v2::Bid{};
      string action=id?to_string(bid.q)+"-"+to_string(bid.f):"C";
      distribution[action]=node.average[i]/total;
    }
    result["policy"][key]=distribution;
  }
  auto pending=path;pending+=".pending";ofstream out(pending);out<<result.dump();out.close();if(!out)throw runtime_error("toy policy write failed");fs::rename(pending,path);
}

static uint64_t peak_memory_bytes(){
  rusage usage{};if(getrusage(RUSAGE_SELF,&usage)!=0)return 0;
#ifdef __APPLE__
  return uint64_t(usage.ru_maxrss);
#else
  return uint64_t(usage.ru_maxrss)*1024;
#endif
}
static void guard(const fs::path& folder){
  if(fs::space(folder).available<2ULL*1024*1024*1024)throw runtime_error("2 GiB free-disk guard reached");
  uintmax_t bytes=0;
  for(const auto& entry:fs::directory_iterator(folder))if(entry.is_regular_file())bytes+=entry.file_size();
  if(bytes>uintmax_t(1.5*1024*1024*1024))throw runtime_error("1.5 GiB experiment-artifact cap reached");
}
static void atomic_json(const fs::path& path,const json& value){
  auto pending=path;pending+=".pending";
  ofstream out(pending);if(!out)throw runtime_error("cannot write manifest");out<<value.dump(2);out.close();
  if(!out)throw runtime_error("manifest write failed");fs::rename(pending,path);
}
static string utc_now(){
  time_t value=time(nullptr);tm clock{};gmtime_r(&value,&clock);char result[32]{};
  strftime(result,sizeof(result),"%Y-%m-%dT%H:%M:%SZ",&clock);return result;
}
static void self_test(){
  auto check=[](bool ok,const string& message){if(!ok)throw runtime_error("self-test failed: "+message);};
  Trainer trainer(42,0.57,false,false);
  Node node;node.n=3;node.regret[0]=-3;node.regret[1]=2;node.regret[2]=4;
  auto probabilities=Trainer::strategy(node);
  check(probabilities[0]==0&&abs(probabilities[1]-1.0/3)<1e-12&&abs(probabilities[2]-2.0/3)<1e-12,"regret matching");
  int counts[3]{};for(int i=0;i<100000;++i)++counts[trainer.sample({0.2,0.3,0.5})];
  check(abs(counts[0]-20000)<500&&abs(counts[1]-30000)<500&&abs(counts[2]-50000)<500,"opponent sampling");
  State state;state.hand[0]={1,1,2,3,4};state.hand[1]={6,6,6,6,6};state.turn=0;state.starter=0;
  auto key=trainer.key(state);state.hand[1]={1,1,1,1,1};check(trainer.key(state)==key,"hidden hand in key");
  check(trainer.actions(state).size()==18,"expanded openings");
  state.history={{1,1},{2,2},{3,1}};key=trainer.key(state);
  state.history[0]={1,3};check(trainer.key(state)!=key,"third most recent public bid discarded");
  state.history.push_back({4,2});key=trainer.key(state);
  state.history[0]={1,6};check(trainer.key(state)==key,"older public bid not abstracted");
  state.history={{9,1}};check(trainer.actions(state).size()==3,"quantity-ten response menu");
  state.history={{3,1}};state.score[0]=4;state.score[1]=4;state.hand[1]={6,6,6,6,6};
  check(trainer.terminal(state,0)==1,"match win after false bid");
  state.hand[1]={1,1,1,1,1};check(trainer.terminal(state,0)==-1,"match loss after true bid");
  int dice[6]{};for(int i=0;i<60000;++i)++dice[trainer.die()-1];
  for(int count:dice)check(abs(count-10000)<350,"fair dice");
  check(trainer.continuation[0][0][0]>0&&trainer.continuation[0][0][0]<1,"finite match continuation");
  cout<<"{\"self_test\":\"passed\"}"<<endl;
}
int main(int argc,char** argv)try{
  string run,git_commit,continuation_path;
  uint64_t seed=1729,target=0,every=100000;bool resume=false,toy=false,verify=false,export_only=false,enumerate_starters=false;
  vector<uint64_t> milestones;
  for(int i=1;i<argc;++i){string argument=argv[i];
    if(argument=="--run-id"&&i+1<argc)run=argv[++i];
    else if(argument=="--seed"&&i+1<argc)seed=stoull(argv[++i]);
    else if(argument=="--iterations"&&i+1<argc)target=stoull(argv[++i]);
    else if(argument=="--checkpoint-every"&&i+1<argc)every=stoull(argv[++i]);
    else if(argument=="--milestones"&&i+1<argc){istringstream in(argv[++i]);string part;while(getline(in,part,','))milestones.push_back(stoull(part));}
    else if(argument=="--continuation"&&i+1<argc)continuation_path=argv[++i];
    else if(argument=="--git-commit"&&i+1<argc)git_commit=argv[++i];
    else if(argument=="--resume")resume=true;
    else if(argument=="--toy")toy=true;
    else if(argument=="--self-test")verify=true;
    else if(argument=="--export-only")export_only=true;
    else if(argument=="--enumerate-starters")enumerate_starters=true;
    else throw runtime_error("unknown or incomplete argument: "+argument);
  }
  if(verify){self_test();return 0;}
  if(run.empty()||run.find('/')!=string::npos||run.find("..")!=string::npos||(!export_only&&target==0)||target>10000000||every==0)
    throw runtime_error("invalid run ID or training budget");
  if(!git_commit.empty()&&(git_commit.size()!=40||!all_of(git_commit.begin(),git_commit.end(),[](char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');})))
    throw runtime_error("invalid git commit");
  if(!toy&&continuation_path.empty())throw runtime_error("fixed-five training needs a measured continuation file");
  for(auto milestone:milestones)if(milestone==0||milestone>target)throw runtime_error("invalid checkpoint milestone");
  double p=0.5;
  if(!toy){ifstream in(continuation_path);if(!in)throw runtime_error("continuation file missing");json data=json::parse(in);p=data.at("starter_win_rate").get<double>();
    if(data.at("ruleset")!=RULESET||data.at("agent")!="mccfr_external_v1"||data.at("completed_rounds").get<int>()<1000)
      throw runtime_error("incompatible continuation estimate");}
  fs::path folder=fs::path("experiments/runs")/run;
  if(!resume&&!export_only){if(!fs::create_directories(folder))throw runtime_error("run directory already exists");}
  else if(!fs::exists(folder))throw runtime_error("run directory missing");
  guard(folder);Trainer trainer(seed,p,toy,enumerate_starters);
  uint64_t start=0;
  if(resume||export_only){
    fs::path latest;uint64_t latest_iteration=0;
    for(const auto& item:fs::directory_iterator(folder)){
      string name=item.path().filename().string();
      if(name.rfind("checkpoint_",0)==0&&name.ends_with(".bin.gz")){
        string number=name.substr(11,name.size()-18);
        if(!number.empty()&&all_of(number.begin(),number.end(),::isdigit)){
          uint64_t value=stoull(number);if(value>latest_iteration){latest_iteration=value;latest=item.path();}
        }
      }
    }
    if(latest.empty())throw runtime_error("checkpoint missing");
    start=load_checkpoint(latest,trainer);
    if(start!=latest_iteration)throw runtime_error("checkpoint filename does not match contents");
    if(resume&&!export_only&&start>=target)throw runtime_error("training target must exceed checkpoint");
  }
  if(export_only){
    auto result=toy?pair<size_t,size_t>{0,0}:save_policy(folder/("policy_"+to_string(start)+".bin"),trainer);
    if(toy)save_toy_policy(folder/("policy_"+to_string(start)+".json"),trainer,start);
    cout<<json({{"exported",true},{"iterations",start},{"fine_information_sets",trainer.table.size()},
      {"exact_policy_records",result.first},{"backoff_policy_records",result.second}}).dump()<<endl;return 0;
  }
  json manifest;
  if(resume){ifstream in(folder/"manifest.json");manifest=json::parse(in);}
  else manifest={{"run_id",run},{"format_version",2},{"ruleset",toy?"quantity_only_n1_toy":RULESET},
    {"policy_id",toy?"mccfr_external_v2_toy":"mccfr_external_v2"},{"algorithm","external-sampling MCCFR"},
    {"objective",toy?"one-round toy utility":"expected first-to-five match win with frozen v1 continuation"},
    {"seed",seed},{"continuation_file",continuation_path.empty()?json(nullptr):json(continuation_path)},
    {"starter_win_probability",p},{"enumerate_starters",enumerate_starters},
    {"git_commit",git_commit.empty()?json(nullptr):json(git_commit)},
    {"workers",1},{"segments",json::array()},{"started_utc",utc_now()}};
  manifest["status"]="started";manifest["iterations_planned"]=target;manifest["iterations_resumed_from"]=start;
  manifest["command"]=json::array();for(int i=0;i<argc;++i)manifest["command"].push_back(argv[i]);
  atomic_json(folder/"manifest.json",manifest);
  auto clock_start=chrono::steady_clock::now();
  try{
    for(uint64_t n=start+1;n<=target;++n){
      trainer.iteration();
      if((milestones.empty()&&n%every==0)||find(milestones.begin(),milestones.end(),n)!=milestones.end()||n==target){
        guard(folder);
        save_checkpoint(folder/("checkpoint_"+to_string(n)+".bin.gz"),trainer,n);
        auto records=toy?pair<size_t,size_t>{0,0}:save_policy(folder/("policy_"+to_string(n)+".bin"),trainer);
        if(toy)save_toy_policy(folder/("policy_"+to_string(n)+".json"),trainer,n);
        guard(folder);
        double elapsed=chrono::duration<double>(chrono::steady_clock::now()-clock_start).count();
        cout<<json({{"iterations",n},{"traversals",n*(enumerate_starters&&!toy?4:2)},
          {"sampled_terminal_histories",trainer.terminals},{"fine_information_sets",trainer.table.size()},
          {"backoff_information_sets",trainer.backoff.size()},{"exact_policy_records",records.first},
          {"backoff_policy_records",records.second},{"segment_elapsed_seconds",elapsed},
          {"peak_memory_bytes",peak_memory_bytes()}}).dump()<<endl;
      }
    }
    double elapsed=chrono::duration<double>(chrono::steady_clock::now()-clock_start).count();
    manifest["segments"].push_back({{"from",start},{"to",target},{"elapsed_seconds",elapsed},
      {"peak_memory_bytes",peak_memory_bytes()},{"sampled_terminal_histories",trainer.terminals},
      {"fine_information_sets",trainer.table.size()},{"backoff_information_sets",trainer.backoff.size()}});
    manifest["status"]="completed";manifest["iterations_completed"]=target;manifest["ended_utc"]=utc_now();
    atomic_json(folder/"manifest.json",manifest);
  }catch(const exception& error){manifest["status"]="failed";manifest["error"]=error.what();manifest["ended_utc"]=utc_now();atomic_json(folder/"manifest.json",manifest);throw;}
  return 0;
}catch(const exception& error){cerr<<error.what()<<endl;return 1;}
