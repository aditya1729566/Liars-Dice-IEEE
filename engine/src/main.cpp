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
  json s={{"ruleset",RULESET},{"counts",json::array({5,5})},{"scores",json::array({0,0})},{"round",1},{"starter",0},{"turn",0},{"bid",nullptr},{"bidder",-1},{"phase","BIDDING"},{"status","ACTIVE"},{"winner",nullptr},{"version",0},{"events",json::array()},{"initial_seed",seed},{"rng",seed},{"policy_rng",seed^0xa5a5a5a55a5a5a5aULL},{"agent",c.value("agent",string("probability"))},{"agent_human",c.value("agent_human",string("random"))}};
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
  if(agent=="random")return acts[size_t(next64(s,"policy_rng")%acts.size())];
  if(agent=="always_call"&&!s["bid"].is_null())return {{"type","call"}};
  json hand=s["hands"][player];double callP=s["bid"].is_null()?1:truth_prior(s["bid"]["q"],s["bid"]["f"],hand,5);
  double threshold=agent=="aggressive"?0.18:(agent=="conservative"?0.25:(agent=="high_call"?0.60:0.44));
  if(!s["bid"].is_null()&&callP<threshold)return {{"type","call"}};
  double best=-1e9;json selected=acts.back();
  for(const auto& a:acts){if(a["type"]!="bid")continue;int q=a["q"],f=a["f"];
    double p=truth_prior(q,f,hand,5);double score=p-0.022*q;
    if(agent=="aggressive")score+=0.16*q+0.02*double(next64(s,"policy_rng")%100)/100;
    if(score>best){best=score;selected=a;}}
  if(selected["type"]=="call")return selected;
  if(best<0.28&&!s["bid"].is_null())return {{"type","call"}};
  return selected;
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
    json a=choose(s,p);apply_action(s,a);return {{"state",s},{"action",a},{"observation",observation}};
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
