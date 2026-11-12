#pragma once
#include <array>
#include <algorithm>
#include <cstdint>
#include <string>
#include <vector>
#include "mccfr_policy.hpp"

namespace mccfr_v2 {
using Hand=mccfr::Hand;
using Bid=mccfr::Bid;
constexpr int MAX_ACTIONS=24;
constexpr int RECORD_BYTES=16+1+MAX_ACTIONS+4*MAX_ACTIONS;
constexpr int PACKED_RECORD_BYTES=16+1+MAX_ACTIONS+2*MAX_ACTIONS;
inline uint8_t action_id(int q,int f){return uint8_t((q-1)*6+f);}
inline Bid bid_for(uint8_t id){return {int((id-1)/6+1),int((id-1)%6+1)};}
inline int second_modal(const Hand& hand,int primary){
  int best=primary==1?2:1,count=-1;
  for(int f=1;f<=6;++f)if(f!=primary){
    int n=int(std::count(hand.begin(),hand.end(),f));
    if(n>count){best=f;count=n;}
  }
  return best;
}
inline std::vector<uint8_t> actions(const Hand& hand,const std::vector<Bid>& history){
  std::vector<uint8_t> out;
  if(history.empty()){
    for(int q:{1,2,10})for(int f=1;f<=6;++f)out.push_back(action_id(q,f));
  }else{
    out.push_back(0);
    int current=history.back().q;
    int modal=mccfr::modal(hand),second=second_modal(hand,modal);
    for(int q=current+1;q<=std::min(10,current+2);++q)
      for(int f:{history.back().f,modal,second})
        if(std::find(out.begin(),out.end(),action_id(q,f))==out.end())out.push_back(action_id(q,f));
  }
  return out;
}
inline std::string fine_key(int starter,int player,const Hand& hand,const std::vector<Bid>& history){
  int previous_q=0,previous_f=0,current_q=0,current_f=0;
  if(!history.empty()){current_q=history.back().q;current_f=history.back().f;}
  if(history.size()>1){previous_q=history[history.size()-2].q;previous_f=history[history.size()-2].f;}
  bool older_same_face=false;
  if(history.size()>2)for(size_t i=0;i+2<history.size();++i)older_same_face|=history[i].f==current_f;
  return "F|"+std::to_string(starter)+"|"+std::to_string(player)+"|"+mccfr::histogram(hand)+"|"+
    std::to_string(previous_q)+"|"+std::to_string(previous_f)+"|"+
    std::to_string(current_q)+"|"+std::to_string(current_f)+"|"+
    std::to_string(history.size()>2)+"|"+std::to_string(older_same_face);
}
inline std::string backoff_key(int starter,int player,const Hand& hand,const std::vector<Bid>& history){
  int q=0,f=0;if(!history.empty()){q=history.back().q;f=history.back().f;}
  return "B|"+std::to_string(starter)+"|"+std::to_string(player)+"|"+mccfr::histogram(hand)+"|"+
    std::to_string(q)+"|"+std::to_string(f);
}
inline std::array<uint8_t,16> digest(const std::string& key){
  uint64_t a=14695981039346656037ULL,b=7809847782465536322ULL;
  for(unsigned char c:key){a=(a^c)*1099511628211ULL;b=(b^uint64_t(c+157))*1099511628211ULL;}
  std::array<uint8_t,16> out{};
  for(int i=0;i<8;++i){out[i]=uint8_t(a>>(8*i));out[i+8]=uint8_t(b>>(8*i));}
  return out;
}
}
