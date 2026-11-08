#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
#include "../vendor/json.hpp"
using json=nlohmann::json;
using namespace std;
static constexpr const char* RULESET="fixed5_score5_quantity_only_v1";
static uint64_t next64(json& s,const string& key="rng"){
  uint64_t x=s.value(key,uint64_t(1));x+=0x9e3779b97f4a7c15ULL;s[key]=x;
  uint64_t z=x;z=(z^(z>>30))*0xbf58476d1ce4e5b9ULL;z=(z^(z>>27))*0x94d049bb133111ebULL;return z^(z>>31);
}
static int die(json& s){uint64_t v;do{v=next64(s);}while(v>=UINT64_MAX-(UINT64_MAX%6));return int(v%6)+1;}
static int other(int p){return 1-p;}
static string name(int p){return p==0?"HUMAN":"AI";}
static bool higher(int q,const json& bid){return bid.is_null()||q>bid.at("q").get<int>();}
static json legal(const json& s){
  json out=json::array();if(s.value("phase",string(""))!="BIDDING")return out;
  for(int q=1;q<=10;q++)for(int f=1;f<=6;f++)if(higher(q,s["bid"]))out.push_back({{"type","bid"},{"q",q},{"f",f}});
  if(!s["bid"].is_null())out.push_back({{"type","call"}});
  return out;
}
static double truth_prior(int q,int f,const json& hand,int unknown){
  int k=0;for(const auto& d:hand)if(d.get<int>()==f)k++;
  int needed=q-k;if(needed<=0)return 1;if(needed>unknown)return 0;
  double p=0;for(int i=needed;i<=unknown;i++){double comb=1;for(int j=1;j<=i;j++)comb*=double(unknown-j+1)/j;p+=comb*pow(1.0/6,i)*pow(5.0/6,unknown-i);}return min(1.0,p);
}
static void roll(json& s){
  s["hands"]=json::array({json::array(),json::array()});
  for(int p=0;p<2;p++)for(int i=0;i<5;i++)s["hands"][p].push_back(die(s));
  s["bid"]=nullptr;s["bidder"]=-1;s["turn"]=s["starter"];s["phase"]="BIDDING";
  s["events"].push_back({{"type","round_start"},{"round",s["round"]},{"starter",name(s["starter"])},{"scores",s["scores"]}});
}
static json new_game(const json& c){
  if(c.contains("n")&&c["n"]!=5)throw runtime_error("this ruleset requires exactly five dice per player");
  uint64_t seed=c.contains("seed")?c["seed"].get<uint64_t>():((uint64_t(random_device{}())<<32)^random_device{}());
  json s={{"ruleset",RULESET},{"counts",json::array({5,5})},{"scores",json::array({0,0})},{"round",1},{"starter",0},{"turn",0},{"bid",nullptr},{"bidder",-1},{"phase","BIDDING"},{"status","ACTIVE"},{"winner",nullptr},{"version",0},{"events",json::array()},{"ai_decisions",json::array()},{"initial_seed",seed},{"rng",seed},{"policy_rng",seed^0xa5a5a5a55a5a5a5aULL},{"agent",c.value("agent",string("probability"))},{"agent_human",c.value("agent_human",string("random"))}};
  s["starter"]=int(next64(s)%2);roll(s);return s;
}
static void apply_action(json& s,const json& a){
  if(s.value("status",string(""))!="ACTIVE"||s.value("phase",string(""))!="BIDDING")throw runtime_error("round is not accepting bids");
  int p=s["turn"].get<int>();if(p!=0&&p!=1)throw runtime_error("invalid turn");
  string type=a.value("type",string(""));
  if(type=="bid"){
    if(!a.contains("q")||!a["q"].is_number_integer()||!a.contains("f")||!a["f"].is_number_integer())throw runtime_error("bid quantity and face must be integers");
    int q=a["q"],f=a["f"];
    if(q<1||q>10||f<1||f>6||!higher(q,s["bid"]))throw runtime_error("illegal bid: quantity must increase and face must be 1..6");
    s["bid"]={{"q",q},{"f",f}};s["bidder"]=p;s["turn"]=other(p);
    s["events"].push_back({{"type","bid"},{"round",s["round"]},{"sequence",s["version"].get<int>()+1},{"player",name(p)},{"q",q},{"f",f}});
  }else if(type=="call"){
    if(s["bid"].is_null()||s["bidder"].get<int>()==p)throw runtime_error("challenge unavailable");
    s["phase"]="REVEAL";
    int q=s["bid"]["q"],f=s["bid"]["f"],count=0;
    for(int side=0;side<2;side++)for(const auto& d:s["hands"][side])if(d.get<int>()==f)count++;
    int bidder=s["bidder"].get<int>(),winner=count>=q?bidder:p,loser=other(winner);
    s["scores"][winner]=s["scores"][winner].get<int>()+1;
    s["events"].push_back({{"type","reveal"},{"round",s["round"]},{"caller",name(p)},{"bidder",name(bidder)},{"bid",s["bid"]},{"actual",count},{"true",count>=q},{"winner",name(winner)},{"loser",name(loser)},{"hands",s["hands"]},{"scores",s["scores"]}});
    s["turn"]=-1;s["next_starter"]=loser;
    if(s["scores"][winner].get<int>()>=5){s["status"]="COMPLETED";s["phase"]="MATCH_OVER";s["winner"]=name(winner);s["events"].push_back({{"type","match_end"},{"winner",s["winner"]},{"scores",s["scores"]}});}
    else s["phase"]="ROUND_OVER";
  }else throw runtime_error("unknown action");
  s["version"]=s["version"].get<int>()+1;
}
static json choose(json& s,int player){
  json acts=legal(s);if(acts.empty())throw runtime_error("no actions");
  string agent=player==1?s.value("agent",string("random")):s.value("agent_human",string("random"));
  s["last_policy_hit"]=false;
  s["last_policy_options"]=json::array();
  if(agent=="switcher")agent=s["round"].get<int>()<=3?"aggressive":"conservative";
  json hand=s["hands"][player];double callP=s["bid"].is_null()?1:truth_prior(s["bid"]["q"],s["bid"]["f"],hand,5);
  auto finish=[&](const json& action,const string& source,const json& policyProbability,const string& policyKey)->json{
    if(player==1){
      json trace={{"round",s["round"]},{"sequence",s["version"].get<int>()+1},{"scores",s["scores"]},{"hand",hand},{"current_bid",s["bid"]},{"current_bid_truth_prior",s["bid"].is_null()?json(nullptr):json(callP)},{"action",action},{"action_truth_prior",action["type"]=="bid"?json(truth_prior(action["q"],action["f"],hand,5)):json(nullptr)},{"source",source},{"policy_probability",policyProbability},{"policy_options",s["last_policy_options"]},{"policy_key",policyKey.empty()?json(nullptr):json(policyKey)},{"policy_id",agent=="cfr2"?"fixed5_cfr_v2_100k":(agent=="cfr"||agent=="adaptive"?"fixed5_cfr_100k":"fixed5_heuristic_v1")}};
      if(!s.contains("ai_decisions"))s["ai_decisions"]=json::array();
      s["ai_decisions"].push_back(trace);
    }
    return action;
  };
  if(agent=="random")return finish(acts[size_t(next64(s,"policy_rng")%acts.size())],"uniform_random",nullptr,"");
  if(agent=="always_call"&&!s["bid"].is_null())return finish({{"type","call"}},"always_call",nullptr,"");
  int modal=1,modalCount=0;
  for(int face=1;face<=6;face++){int count=0;for(const auto& d:hand)if(d.get<int>()==face)count++;if(count>modalCount){modal=face;modalCount=count;}}
  if(agent=="truthful"){
    int current=s["bid"].is_null()?0:s["bid"]["q"].get<int>();
    for(int target=min(5,modalCount);target>current;target--)
      for(int candidateFace=1;candidateFace<=6;candidateFace++){
        int count=0;for(const auto& d:hand)if(d.get<int>()==candidateFace)count++;
        if(count>=target)return finish({{"type","bid"},{"q",target},{"f",candidateFace}},"truthful_probe",nullptr,"");
      }
  }
  if(agent=="cfr"||agent=="adaptive"||agent=="cfr2"){
    int q=s["bid"].is_null()?0:s["bid"]["q"].get<int>();
    int f=s["bid"].is_null()?0:s["bid"]["f"].get<int>();
    int k=0;for(const auto& d:hand)if(d.get<int>()==f)k++;
    string key=to_string(s["starter"].get<int>())+"|"+to_string(player)+"|"+to_string(modal)+"|"+to_string(modalCount)+"|"+to_string(q)+"|"+to_string(f)+"|"+to_string(k);
    if(agent=="cfr2"){
      int previousQ=0,previousF=0,seenBids=0;
      for(auto it=s["events"].rbegin();it!=s["events"].rend();++it){
        if(it->value("round",0)!=s["round"].get<int>())continue;
        if(it->value("type",string(""))=="bid"&&++seenBids==2){previousQ=it->at("q");previousF=it->at("f");break;}
      }
      key=to_string(s["starter"].get<int>())+"|"+to_string(player)+"|"+to_string(modal)+"|"+to_string(modalCount)+"|"+to_string(previousQ)+"|"+to_string(previousF)+"|"+to_string(q)+"|"+to_string(f)+"|"+to_string(k);
    }
    std::ifstream file(agent=="cfr2"?"policies/fixed5_cfr_v2.json":"policies/fixed5_cfr.json");
    if(file){try{
      json saved=json::parse(file);if(saved.value("ruleset",string(""))!=RULESET)throw runtime_error("policy ruleset mismatch");
      const json& table=saved.at("policy");
      if(table.contains(key)){
        vector<pair<json,double>> candidates;double total=0;
        for(const auto& a:acts){string akey=a["type"]=="call"?"C":to_string(a["q"].get<int>())+"-"+to_string(a["f"].get<int>());
          double w=table[key].value(akey,0.0);if(w>0){candidates.push_back({a,w});total+=w;}}
        if(total>0){s["last_policy_hit"]=true;
          vector<pair<string,double>> options;
          for(const auto& item:candidates){string akey=item.first["type"]=="call"?"C":to_string(item.first["q"].get<int>())+"-"+to_string(item.first["f"].get<int>());options.push_back({akey,item.second/total});}
          sort(options.begin(),options.end(),[](const auto& a,const auto& b){return a.second>b.second;});
          for(size_t i=0;i<min(size_t(3),options.size());i++)s["last_policy_options"].push_back({{"action",options[i].first},{"weight",options[i].second}});
          bool exploit=false;
          if(agent=="adaptive"){
            int seen=0;for(const auto& e:s["events"])if(e.value("type",string(""))=="reveal"&&e.value("bidder",string(""))==name(other(player)))seen++;
            exploit=seen>=3&&next64(s,"policy_rng")%100<25;
          }
          if(!exploit){double draw=double(next64(s,"policy_rng")%1000000)/1000000*total;
            for(const auto& item:candidates){draw-=item.second;if(draw<=0)return finish(item.first,"sampled_cfr",item.second/total,key);}return finish(candidates.back().first,"sampled_cfr",candidates.back().second/total,key);}
          s["last_policy_hit"]=false;s["last_policy_options"]=json::array();
        }
      }
    }catch(const exception&){}
    }
  }
  int seen=0,bluffs=0;
  if(agent=="adaptive")for(const auto& e:s["events"])if(e.value("type",string(""))=="reveal"&&e.value("bidder",string(""))==name(other(player))){seen++;if(!e.value("true",true))bluffs++;}
  double adaptiveRate=double(bluffs+1)/double(seen+2);
  double threshold=agent=="aggressive"?0.18:(agent=="conservative"?0.25:(agent=="high_call"?0.60:0.44));
  double adjustedCallP=agent=="adaptive"&&seen>=3?std::clamp(callP-(adaptiveRate-0.5)*0.6,0.0,1.0):callP;
  if(!s["bid"].is_null()&&adjustedCallP<threshold)return finish({{"type","call"}},agent=="adaptive"?"adaptive_public_outcomes":"probability_heuristic",nullptr,"");
  double best=-1e9;json selected=acts.back();
  for(const auto& a:acts){if(a["type"]!="bid")continue;int q=a["q"],f=a["f"];
    double p=truth_prior(q,f,hand,5);double score=p-0.022*q;
    if(agent=="aggressive")score+=0.16*q+0.02*double(next64(s,"policy_rng")%100)/100;
    if(score>best){best=score;selected=a;}}
  if(selected["type"]=="call")return finish(selected,"probability_heuristic",nullptr,"");
  if(best<0.28&&!s["bid"].is_null())return finish({{"type","call"}},agent=="adaptive"?"adaptive_public_outcomes":"probability_heuristic",nullptr,"");
  return finish(selected,agent=="adaptive"?"adaptive_public_outcomes":"probability_heuristic",nullptr,"");
}
static void auto_ai(json& s){
  if(s["phase"]=="BIDDING"&&s["turn"]==1){json a=choose(s,1);apply_action(s,a);}
}
static void next_round(json& s,bool auto_open=true){
  if(s["status"]!="ACTIVE"||s["phase"]!="ROUND_OVER")throw runtime_error("next round unavailable");
  s["events"].push_back({{"type","next_round"},{"from_round",s["round"]},{"requested_after_version",s["version"]}});
  s["starter"]=s["next_starter"];s["round"]=s["round"].get<int>()+1;roll(s);s["version"]=s["version"].get<int>()+1;if(auto_open)auto_ai(s);
}
static json view(const json& s){
  bool reveal=s["phase"]!="BIDDING";
  json v={{"ruleset",s["ruleset"]},{"counts",s["counts"]},{"scores",s["scores"]},{"target_score",5},{"round",s["round"]},{"phase",s["phase"]},{"status",s["status"]},{"turn",s["turn"].get<int>()<0?"NONE":name(s["turn"])},{"bid",s["bid"]},{"winner",s["winner"]},{"version",s["version"]},{"agent",s["agent"]},{"events",s["events"]},{"legal_actions",json::array()},{"hand",s["hands"][0]},{"ai_hand",reveal?s["hands"][1]:json(nullptr)}};
  if(s["phase"]=="BIDDING"&&s["turn"]==0)v["legal_actions"]=legal(s);
  return v;
}
static json run(const json& c){
  string op=c.value("op",string(""));
  if(op=="new"){json s=new_game(c);if(c.value("auto_ai",true))auto_ai(s);return {{"state",s},{"view",view(s)}};}
  if(op=="prior")return {{"probability",truth_prior(c.at("q"),c.at("f"),c.at("hand"),c.at("unknown"))}};
  json s=c.at("state");if(s.value("ruleset",string(""))!=RULESET)throw runtime_error("ruleset version mismatch");
  if(op=="view")return {{"view",view(s)}};
  if(op=="legal")return {{"actions",legal(s)}};
  if(op=="act"){
    if(s["turn"]!=0)throw runtime_error("not human turn");apply_action(s,c.at("action"));auto_ai(s);return {{"state",s},{"view",view(s)}};
  }
  if(op=="step"){apply_action(s,c.at("action"));return {{"state",s},{"view",view(s)}};}
  if(op=="next_round"){next_round(s,c.value("auto_ai",true));return {{"state",s},{"view",view(s)}};}
  if(op=="bot_step"){
    if(s["phase"]!="BIDDING")throw runtime_error("round is over");
    int p=s["turn"].get<int>();json observation={{"player",name(p)},{"hand",s["hands"][p]},{"scores",s["scores"]},{"bid",s["bid"]},{"round",s["round"]},{"legal_actions",legal(s)}};
    json a=choose(s,p);bool policyHit=s.value("last_policy_hit",false);apply_action(s,a);return {{"state",s},{"action",a},{"observation",observation},{"policy_hit",policyHit}};
  }
  if(op=="replay"){
    json rebuilt=new_game({{"seed",s["initial_seed"]},{"agent",s["agent"]},{"agent_human",s.value("agent_human",string("random"))}});
    for(const auto& e:s["events"]){string type=e.value("type",string(""));
      if(type=="next_round")next_round(rebuilt,false);
      else if(type=="bid")apply_action(rebuilt,{{"type","bid"},{"q",e["q"]},{"f",e["f"]}});
      else if(type=="reveal")apply_action(rebuilt,{{"type","call"}});
    }
    bool valid=rebuilt["events"]==s["events"]&&rebuilt["scores"]==s["scores"]&&rebuilt["phase"]==s["phase"]&&rebuilt["rng"]==s["rng"];
    return {{"valid",valid},{"event_count",s["events"].size()}};
  }
  throw runtime_error("unknown operation");
}
int main(){try{json c;cin>>c;cout<<run(c).dump()<<endl;return 0;}catch(const exception& e){cout<<json({{"error",e.what()}}).dump()<<endl;return 1;}}
