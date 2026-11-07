"""Bounded external-sampling MCCFR for a fixed-five, quantity-only one-round abstraction.

The abstraction permits quantity +1 only and two face choices after a bid.
Information sets summarize public history and private hand, so perfect recall is
not claimed. This is a candidate policy, not an exact Nash solution.
"""
import argparse
import hashlib
import json
import os
import pickle
import random
import shutil
import subprocess
import time
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RULESET='fixed5_score5_quantity_only_v1'
ARTIFACT_CAP=int(1.5*1024**3)
FREE_DISK_GUARD=2*1024**3

def resource_guard(folder):
    if shutil.disk_usage(folder).free<FREE_DISK_GUARD:raise RuntimeError('2 GiB free-disk guard reached')
    if sum(p.stat().st_size for p in folder.iterdir() if p.is_file())>ARTIFACT_CAP:raise RuntimeError('1.5 GiB experiment-artifact cap reached')

def modal(hand):
    counts=[hand.count(f) for f in range(1,7)]
    maximum=max(counts)
    return counts.index(maximum)+1,maximum

def actions(hand,history):
    if not history:return [f'1-{f}' for f in range(1,7)]
    q,f=history[-1]
    if q==10:return ['C']
    m,_=modal(hand)
    out=['C',f'{q+1}-{f}']
    if m!=f:out.append(f'{q+1}-{m}')
    return out

def info_key(starter,player,hand,history):
    m,mc=modal(hand)
    if not history:return f'{starter}|{player}|{m}|{mc}|0|0|0'
    q,f=history[-1]
    k=hand.count(f)
    return f'{starter}|{player}|{m}|{mc}|{q}|{f}|{k}'

def strategy(regrets,key,acts):
    weights=[max(0.0,regrets[key].get(a,0.0)) for a in acts]
    total=sum(weights)
    return [w/total for w in weights] if total else [1/len(acts)]*len(acts)

def sample(rng,acts,probs):
    draw=rng.random()
    for a,p in zip(acts,probs):
        draw-=p
        if draw<=0:return a
    return acts[-1]

def payoff(hands,caller,history):
    q,f=history[-1]
    truth=sum(d==f for h in hands for d in h)>=q
    winner=1-caller if truth else caller
    return 1.0 if winner==0 else -1.0

def traverse(hands,history,starter,turn,traverser,reach,regrets,sums,rng):
    hand=hands[turn];acts=actions(hand,history);key=info_key(starter,turn,hand,history)
    probs=strategy(regrets,key,acts)
    if turn!=traverser:
        a=sample(rng,acts,probs)
        return payoff(hands,turn,history) if a=='C' else traverse(hands,history+((int(a.split('-')[0]),int(a.split('-')[1])),),starter,1-turn,traverser,reach,regrets,sums,rng)
    values=[]
    for a,p in zip(acts,probs):
        if a=='C':value=payoff(hands,turn,history)
        else:
            q,f=map(int,a.split('-'))
            value=traverse(hands,history+((q,f),),starter,1-turn,traverser,reach*p,regrets,sums,rng)
        values.append(value)
    node=sum(p*v for p,v in zip(probs,values))
    sign=1 if traverser==0 else -1
    for a,p,v in zip(acts,probs,values):
        regrets[key][a]+=sign*(v-node)
        sums[key][a]+=reach*p
    return node

def write_json(path,value):path.write_text(json.dumps(value,indent=2))
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--n',type=int,default=5)
    ap.add_argument('--iterations',type=int,default=20000)
    ap.add_argument('--seed',type=int,default=1729)
    ap.add_argument('--run-id',required=True)
    ap.add_argument('--resume',action='store_true')
    args=ap.parse_args()
    if args.n!=5 or not 1<=args.iterations<=200000:raise SystemExit('requires N=5 and 1..200000 iterations')
    folder=ROOT/'experiments'/'runs'/args.run_id
    checkpoint=folder/'checkpoint.pkl'
    if args.resume:
        saved=pickle.loads(checkpoint.read_bytes());start,regrets,sums,rng=saved['iteration'],saved['regrets'],saved['sums'],saved['rng']
        if args.seed!=saved['seed']:raise SystemExit('seed mismatch')
    else:
        folder.mkdir(parents=True,exist_ok=False);start=0;regrets=defaultdict(lambda:defaultdict(float));sums=defaultdict(lambda:defaultdict(float));rng=random.Random(args.seed)
    # Convert nested lambdas to plain dictionaries when checkpointing; restore with factories.
    if args.resume:
        regrets=defaultdict(lambda:defaultdict(float),{k:defaultdict(float,v) for k,v in regrets.items()})
        sums=defaultdict(lambda:defaultdict(float),{k:defaultdict(float,v) for k,v in sums.items()})
    resource_guard(folder)
    manifest={'run_id':args.run_id,'status':'started','ruleset':RULESET,'algorithm':'external-sampling MCCFR with imperfect-recall abstraction','objective':'one-round +1/-1 point utility, fixed five dice','iterations_planned':args.iterations,'iterations_resumed_from':start,'seed':args.seed,'action_abstraction':'opening quantity 1, then quantity +1; current face or private modal face','command':' '.join(os.sys.argv),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'engine_sha256':hashlib.sha256((ROOT/'build'/'bluff_engine').read_bytes()).hexdigest()}
    write_json(folder/'manifest.json',manifest)
    started=time.time()
    try:
        for i in range(start,args.iterations):
            hands=tuple(tuple(rng.randint(1,6) for _ in range(5)) for _ in range(2))
            starter=rng.randrange(2)
            for traverser in (0,1):traverse(hands,(),starter,starter,traverser,1.0,regrets,sums,rng)
            if (i+1)%1000==0 or i+1==args.iterations:
                resource_guard(folder)
                pending=folder/'checkpoint.pending'
                payload={'iteration':i+1,'seed':args.seed,'regrets':{k:dict(v) for k,v in regrets.items()},'sums':{k:dict(v) for k,v in sums.items()},'rng':rng}
                pending.write_bytes(pickle.dumps(payload,protocol=5));pending.replace(checkpoint)
                print(json.dumps({'iteration':i+1,'infosets':len(regrets),'elapsed_seconds':round(time.time()-started,2)}),flush=True)
        policy={}
        for key,weights in sums.items():
            total=sum(weights.values())
            if total>0:policy[key]={a:w/total for a,w in weights.items()}
        output={'ruleset':RULESET,'policy_id':args.run_id,'algorithm':'sampled CFR, abstract imperfect-recall one-round game','objective':'one-round point utility','iterations':args.iterations,'policy':policy}
        policy_path=folder/'policy.json';policy_path.write_text(json.dumps(output,separators=(',',':')))
        summary={'run_id':args.run_id,'ruleset':RULESET,'iterations':args.iterations,'infosets':len(policy),'elapsed_seconds':round(time.time()-started,2),'policy_sha256':hashlib.sha256(policy_path.read_bytes()).hexdigest(),'limitations':['not full match-aware','quantity jumps abstracted away','imperfect recall; no equilibrium guarantee','no exploitability estimate']}
        write_json(folder/'summary.json',summary)
        manifest.update(status='completed',iterations_completed=args.iterations,ended_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
        write_json(folder/'manifest.json',manifest)
        print(json.dumps(summary),flush=True)
    except BaseException as exc:
        manifest.update(status='failed',error=repr(exc),iterations_completed=i if 'i' in locals() else start)
        write_json(folder/'manifest.json',manifest)
        raise
if __name__=='__main__':main()
