#pragma once
#include <array>
#include <algorithm>
#include <string>
#include <vector>

namespace mccfr {
struct Bid { int q, f; };
using Hand = std::array<int, 5>;
inline int modal(const Hand& hand) {
  int best=1, count=-1;
  for(int f=1;f<=6;++f){int n=int(std::count(hand.begin(),hand.end(),f));if(n>count){best=f;count=n;}}
  return best;
}
inline std::string histogram(const Hand& hand) {
  std::string out;
  for(int f=1;f<=6;++f)out+=char('0'+std::count(hand.begin(),hand.end(),f));
  return out;
}
inline std::vector<std::string> actions(const Hand& hand,const std::vector<Bid>& history) {
  std::vector<std::string> out;
  const int m=modal(hand);
  if(history.empty()){
    for(int f=1;f<=6;++f)out.push_back("1-"+std::to_string(f));
    out.push_back("2-"+std::to_string(m));
    return out;
  }
  const auto [q,f]=history.back();
  out.push_back("C");
  for(int nq:{q+1,q+2})if(nq<=10){
    out.push_back(std::to_string(nq)+"-"+std::to_string(f));
    if(m!=f)out.push_back(std::to_string(nq)+"-"+std::to_string(m));
  }
  return out;
}
inline std::string key(int starter,int player,const Hand& hand,const std::vector<Bid>& history) {
  int pq=0,pf=0,q=0,f=0;
  if(!history.empty()){q=history.back().q;f=history.back().f;}
  if(history.size()>1){pq=history[history.size()-2].q;pf=history[history.size()-2].f;}
  return std::to_string(starter)+"|"+std::to_string(player)+"|"+histogram(hand)+"|"+
    std::to_string(pq)+"|"+std::to_string(pf)+"|"+std::to_string(q)+"|"+std::to_string(f);
}
inline std::string backoff_key(int starter,int player,const Hand& hand,const std::vector<Bid>& history) {
  int q=0,f=0;if(!history.empty()){q=history.back().q;f=history.back().f;}
  return std::to_string(starter)+"|"+std::to_string(player)+"|"+histogram(hand)+"|"+
    std::to_string(q)+"|"+std::to_string(f);
}
inline Bid parse_bid(const std::string& action) {
  auto sep=action.find('-');return {std::stoi(action.substr(0,sep)),std::stoi(action.substr(sep+1))};
}
}
