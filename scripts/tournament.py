"""Seat-balanced, fully logged evaluation of the compiled agents."""
import argparse
import hashlib
import itertools
import json
import math
import os
import platform
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BIN=ROOT/'build'/'bluff_engine'

def engine(command):
    result=subprocess.run([str(BIN)],input=json.dumps(command,separators=(',',':')),text=True,capture_output=True,timeout=8)
    data=json.loads(result.stdout)
    if result.returncode or 'error' in data: raise RuntimeError(data.get('error',result.stderr))
    return data

def wilson(wins,total):
    if not total:return [0,1]
    z=1.96;p=wins/total;d=1+z*z/total
    center=(p+z*z/(2*total))/d
    half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return [center-half,center+half]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--run-id',required=True)
    ap.add_argument('--per-seat',type=int,default=1000)
    ap.add_argument('--n',type=int,default=5)
    ap.add_argument('--agents',nargs='+',default=['random','probability','aggressive'])
    ap.add_argument('--seed-offset',type=int,default=1000000)
    ap.add_argument('--paired-seeds',action='store_true',help='reuse each seed and seat across pairings for paired league comparisons')
    ap.add_argument('--focus',help='evaluate only pairings containing this agent')
    args=ap.parse_args()
    if args.n != 5 or not 1<=args.per_seat<=10000:raise SystemExit('this ruleset requires N=5 and per-seat 1..10000')
    policy_paths={
        'cfr':ROOT/'policies'/'fixed5_cfr.json',
        'adaptive':ROOT/'policies'/'fixed5_cfr.json',
        'cfr2':ROOT/'policies'/'fixed5_cfr_v2.json',
        'mccfr_external_v1':ROOT/'policies'/'mccfr_external_v1.bin',
    }
    used_policy_paths=sorted({policy_paths[a] for a in args.agents if a in policy_paths})
    for path in used_policy_paths:
        if not path.exists():raise SystemExit(f'trained agent requires {path.relative_to(ROOT)}')
        if path.suffix == '.bin':
            import struct
            raw=path.read_bytes()
            if len(raw)<16 or raw[:8]!=b'MCCFR1\0\0' or len(raw)!=16+68*struct.unpack('<Q',raw[8:16])[0]:
                raise SystemExit(f'trained policy missing or incompatible: {path.relative_to(ROOT)}')
        else:
            policy=json.loads(path.read_text())
            if policy.get('ruleset')!='fixed5_score5_quantity_only_v1' or not policy.get('policy'):
                raise SystemExit(f'trained policy missing or incompatible: {path.relative_to(ROOT)}')
    folder=ROOT/'experiments'/'runs'/args.run_id
    folder.mkdir(parents=True,exist_ok=False)
    plan=list(itertools.combinations(args.agents,2))
    if args.focus:
        plan=[pair for pair in plan if args.focus in pair]
        if not plan:raise SystemExit('focus agent has no pairings')
    policy_hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in used_policy_paths}
    policy_hash=next(iter(policy_hashes.values())) if len(policy_hashes)==1 else None
    manifest={'run_id':args.run_id,'status':'started','ruleset':'fixed5_score5_quantity_only_v1','n':args.n,'per_seat':args.per_seat,'pairings':plan,'focus':args.focus,'seed_offset':args.seed_offset,'paired_seeds':args.paired_seeds,'command':' '.join(os.sys.argv),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'hardware':platform.platform(),'python':platform.python_version(),'engine_sha256':hashlib.sha256(BIN.read_bytes()).hexdigest(),'policy_sha256':policy_hash,'policy_sha256_by_file':policy_hashes}
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
    db=sqlite3.connect(folder/'evaluation.sqlite3')
    db.executescript('CREATE TABLE matches(id INTEGER PRIMARY KEY, agent_a TEXT, agent_b TEXT, seed INTEGER, winner TEXT, rounds INTEGER, actions INTEGER, duration_ms REAL);CREATE TABLE decisions(match_id INTEGER, action_index INTEGER, round_index INTEGER, player TEXT, agent TEXT, observation_json TEXT, action_json TEXT, latency_ms REAL, policy_hit INTEGER);CREATE TABLE rounds(match_id INTEGER, round_index INTEGER, reveal_json TEXT);CREATE TABLE errors(match_id INTEGER,error TEXT);')
    results={}
    total_planned=len(plan)*2*args.per_seat
    completed=0
    binary_mtime=BIN.stat().st_mtime_ns
    try:
        for pair_index,(left,right) in enumerate(plan):
            for seat in (0,1):
                agent_a,agent_b=(left,right) if seat==0 else (right,left)
                wins=0
                for index in range(args.per_seat):
                    if BIN.stat().st_mtime_ns!=binary_mtime:raise RuntimeError('engine binary changed during run')
                    for path in used_policy_paths:
                        if hashlib.sha256(path.read_bytes()).hexdigest()!=policy_hashes[str(path.relative_to(ROOT))]:raise RuntimeError('policy changed during run')
                    if os.statvfs(folder).f_bavail*os.statvfs(folder).f_frsize<2*1024**3:raise RuntimeError('free disk guard reached')
                    if (folder/'evaluation.sqlite3').stat().st_size>int(1.5*1024**3):raise RuntimeError('artifact cap reached')
                    seed=args.seed_offset+index if args.paired_seeds else args.seed_offset+pair_index*args.per_seat+index
                    started=time.perf_counter()
                    state=engine({'op':'new','n':5,'agent_human':agent_a,'agent':agent_b,'seed':seed,'auto_ai':False})['state']
                    match_id=completed+1
                    decisions=[]
                    for turn in range(500):
                        if state['status']=='COMPLETED':break
                        if state['phase']=='ROUND_OVER':
                            state=engine({'op':'next_round','state':state,'auto_ai':False})['state']
                            continue
                        player=state['turn'];t=time.perf_counter()
                        result=engine({'op':'bot_step','state':state})
                        latency=(time.perf_counter()-t)*1000
                        decisions.append((match_id,turn,state['round'],'HUMAN' if player==0 else 'AI',agent_a if player==0 else agent_b,json.dumps(result['observation'],separators=(',',':')),json.dumps(result['action'],separators=(',',':')),latency,int(result.get('policy_hit',False))))
                        state=result['state']
                    if state['status']!='COMPLETED':raise RuntimeError(f'match {match_id} exceeded 500 actions')
                    wins+=state['winner']==('HUMAN' if seat==0 else 'AI')
                    db.execute('INSERT INTO matches VALUES (?,?,?,?,?,?,?,?)',(match_id,agent_a,agent_b,seed,state['winner'],state['round'],len(decisions),(time.perf_counter()-started)*1000))
                    db.executemany('INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?)',decisions)
                    db.executemany('INSERT INTO rounds VALUES (?,?,?)',[(match_id,e['round'],json.dumps(e,separators=(',',':'))) for e in state['events'] if e['type']=='reveal'])
                    db.commit()
                    completed+=1
                    if completed%100==0:print(json.dumps({'completed':completed,'planned':total_planned}),flush=True)
                results[f'{left}_vs_{right}_seat_{seat}']={'wins':wins,'matches':args.per_seat,'win_rate':wins/args.per_seat,'wilson95':wilson(wins,args.per_seat)}
        summary={'status':'completed','run_id':args.run_id,'n':args.n,'completed_matches':completed,'results':results,'decision_count':db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],'policy_hits':dict(db.execute('SELECT agent,SUM(policy_hit) FROM decisions GROUP BY agent').fetchall())}
        (folder/'summary.json').write_text(json.dumps(summary,indent=2))
        manifest.update(status='completed',completed=completed,ended_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
        (ROOT/'experiments'/'summary.json').write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary),flush=True)
    except BaseException as exc:
        db.execute('INSERT INTO errors VALUES (?,?)',(completed+1,repr(exc)));db.commit()
        manifest.update(status='failed',completed=completed,error=repr(exc))
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
        raise
    finally:db.close()
if __name__=='__main__':main()
