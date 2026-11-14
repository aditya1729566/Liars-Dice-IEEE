"""Seat-balanced, fully logged evaluation of the compiled agents."""
import argparse
import hashlib
import itertools
import json
import math
import os
import platform
import resource
import secrets
import select
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BIN=ROOT/'build'/'bluff_engine'
STREAM=None

def engine(command):
    if STREAM is None:
        result=subprocess.run([str(BIN)],input=json.dumps(command,separators=(',',':')),text=True,capture_output=True,timeout=8)
        data=json.loads(result.stdout)
        if result.returncode or 'error' in data: raise RuntimeError(data.get('error',result.stderr))
        return data
    STREAM.stdin.write(json.dumps(command,separators=(',',':'))+'\n')
    STREAM.stdin.flush()
    if not select.select([STREAM.stdout],[],[],8)[0]:raise RuntimeError('stream engine timed out')
    response=STREAM.stdout.readline()
    if not response:raise RuntimeError('stream engine exited')
    data=json.loads(response)
    if 'error' in data:raise RuntimeError(data['error'])
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
    ap.add_argument('--stream-engine',action='store_true',help='reuse one engine process for faster evaluation; latency excludes startup')
    ap.add_argument('--rebel-iters',type=int,default=4)
    ap.add_argument('--rebel-depth',type=int,default=1)
    ap.add_argument('--rebel-v2-iters',type=int,default=32)
    ap.add_argument('--rebel-v2-depth',type=int,default=1)
    ap.add_argument('--min-free-mib',type=int,default=2048,help='free-disk guard; default 2 GiB')
    ap.add_argument('--policy-seed-file',help='reuse recorded independent ReBeL search seeds for exact reruns')
    args=ap.parse_args()
    if args.n != 5 or not 1<=args.per_seat<=10000:raise SystemExit('this ruleset requires N=5 and per-seat 1..10000')
    if not 512<=args.min_free_mib<=16384:raise SystemExit('min-free-mib must be 512..16384')
    policy_paths={
        'cfr':ROOT/'policies'/'fixed5_cfr.json',
        'adaptive':ROOT/'policies'/'fixed5_cfr.json',
        'cfr2':ROOT/'policies'/'fixed5_cfr_v2.json',
        'mccfr_external_v1':ROOT/'policies'/'mccfr_external_v1.bin',
        'mccfr_external_v2':ROOT/'policies'/'mccfr_external_v2.bin',
        'rebel_transfer_v1':ROOT/'.cache'/'rebel-source'/'checkpoints'/'rebel_5x6f_epoch_6.pt',
        'rebel_bluff_v2':ROOT/'.cache'/'rebel-source-v2'/'checkpoints'/'bluff_exe_v1'/'rebel_bluff_epoch_5.pt',
    }
    used_policy_paths=sorted({policy_paths[a] for a in args.agents if a in policy_paths})
    rebel_policy=None
    if 'rebel_transfer_v1' in args.agents:
        from rebel_bridge import RebelPolicy, SOURCE, SOURCE_COMMIT
        if subprocess.check_output(['git','-C',str(SOURCE),'rev-parse','HEAD'],text=True).strip()!=SOURCE_COMMIT:
            raise SystemExit('ReBeL source commit differs from pinned version')
        rebel_policy=RebelPolicy(seed=args.seed_offset,search_iters=args.rebel_iters,search_depth=args.rebel_depth)
    rebel_v2_source=None
    if 'rebel_bluff_v2' in args.agents:
        from rebel_v2_bridge import SOURCE as rebel_v2_source, SOURCE_COMMIT as rebel_v2_commit, CHECKPOINT_SHA256 as rebel_v2_sha
        if subprocess.check_output(['git','-C',str(rebel_v2_source),'rev-parse','HEAD'],text=True).strip()!=rebel_v2_commit:
            raise SystemExit('updated ReBeL source commit differs from pinned version')
    for path in used_policy_paths:
        if not path.exists():raise SystemExit(f'trained agent requires {path.relative_to(ROOT)}')
        if path.suffix == '.pt':
            continue
        if path.suffix == '.bin':
            import struct
            raw=path.read_bytes()
            if path.name=='mccfr_external_v2.bin':
                magic=raw[:8]
                record_bytes={b'MCCFR2\0\0':137,b'MCCFR2Q\0':89}.get(magic,0)
            else:
                magic=b'MCCFR1\0\0'
                record_bytes=68
            if len(raw)<16 or raw[:8]!=magic or len(raw)!=16+record_bytes*struct.unpack('<Q',raw[8:16])[0]:
                raise SystemExit(f'trained policy missing or incompatible: {path.relative_to(ROOT)}')
        else:
            policy=json.loads(path.read_text())
            if policy.get('ruleset')!='fixed5_score5_quantity_only_v1' or not policy.get('policy'):
                raise SystemExit(f'trained policy missing or incompatible: {path.relative_to(ROOT)}')
    folder=ROOT/'experiments'/'runs'/args.run_id
    folder.mkdir(parents=True,exist_ok=False)
    run_started=time.perf_counter()
    plan=list(itertools.combinations(args.agents,2))
    if args.focus:
        plan=[pair for pair in plan if args.focus in pair]
        if not plan:raise SystemExit('focus agent has no pairings')
    if args.policy_seed_file and not (rebel_policy or rebel_v2_source):
        raise SystemExit('--policy-seed-file requires a ReBeL agent')
    if args.policy_seed_file:
        seed_text=Path(args.policy_seed_file).read_text()
        policy_seeds=json.loads(seed_text)
    else:
        policy_seeds=[[{'rebel_transfer_v1':secrets.randbits(64),
                        'rebel_bluff_v2':secrets.randbits(64)} for _ in range(args.per_seat)]
                      for _ in plan] if rebel_policy or rebel_v2_source else []
        seed_text=json.dumps(policy_seeds,separators=(',',':'))
    if policy_seeds and (len(policy_seeds)!=len(plan) or any(
            len(group)!=args.per_seat or any(
                not isinstance(block,dict) or any(
                    not isinstance(block.get(agent),int) or not 0<=block[agent]<2**64
                    for agent in ('rebel_transfer_v1','rebel_bluff_v2'))
                for block in group) for group in policy_seeds)):
        raise SystemExit('policy seed file does not match this tournament plan')
    if policy_seeds:
        (folder/'policy_seeds.json').write_text(seed_text)
    policy_hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in used_policy_paths}
    policy_hash=next(iter(policy_hashes.values())) if len(policy_hashes)==1 else None
    manifest={'run_id':args.run_id,'status':'started','ruleset':'fixed5_score5_quantity_only_v1','n':args.n,'per_seat':args.per_seat,'pairings':plan,'focus':args.focus,'seed_offset':args.seed_offset,'paired_seeds':args.paired_seeds,'command':' '.join(os.sys.argv),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'hardware':platform.platform(),'python':platform.python_version(),'engine_sha256':hashlib.sha256(BIN.read_bytes()).hexdigest(),'policy_sha256':policy_hash,'policy_sha256_by_file':policy_hashes,'inference_mode':'persistent_process' if args.stream_engine else 'fresh_process','observation_log':'player,hand,scores,bid,round; legal actions reconstructible from ruleset','policy_integrity':'mtime and size every match; SHA-256 every 100 matches and at completion'}
    manifest['min_free_mib']=args.min_free_mib
    if policy_seeds:
        manifest['policy_seed_file']='policy_seeds.json'
        manifest['policy_seed_sha256']=hashlib.sha256((folder/'policy_seeds.json').read_bytes()).hexdigest()
        manifest['policy_seed_source']=args.policy_seed_file or 'OS random'
    if rebel_policy:
        manifest['rebel']={'source_commit':SOURCE_COMMIT,'checkpoint_sha256':rebel_policy.checkpoint_sha256,'search_depth':rebel_policy.search_depth,'search_iters':rebel_policy.search_iters,'algorithm':'linear_fp','transfer_warning':'checkpoint trained with wild highest and face-ordered bids; inference uses no wilds and quantity-only bids','policy_rng_seed':'independent OS-random seed in policy_seeds.json; shared by paired seats'}
    if rebel_v2_source:
        manifest['rebel_v2']={'source_commit':rebel_v2_commit,'checkpoint_sha256':rebel_v2_sha,
                              'search_depth':args.rebel_v2_depth,'search_iters':args.rebel_v2_iters,
                              'algorithm':'linear_fp','rules_note':'no wilds and quantity-only bids; source alternates next opener, local referee uses round loser',
                              'policy_rng_seed':'independent OS-random seed in policy_seeds.json; shared by paired seats'}
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
    db=sqlite3.connect(folder/'evaluation.sqlite3')
    db.executescript('CREATE TABLE matches(id INTEGER PRIMARY KEY, agent_a TEXT, agent_b TEXT, seed INTEGER, winner TEXT, rounds INTEGER, actions INTEGER, duration_ms REAL);CREATE TABLE decisions(match_id INTEGER, action_index INTEGER, round_index INTEGER, player TEXT, agent TEXT, observation_json TEXT, action_json TEXT, latency_ms REAL, policy_hit INTEGER, policy_source TEXT);CREATE TABLE rounds(match_id INTEGER, round_index INTEGER, reveal_json TEXT);CREATE TABLE errors(match_id INTEGER,error TEXT);')
    results={}
    total_planned=len(plan)*2*args.per_seat
    completed=0
    binary_mtime=BIN.stat().st_mtime_ns
    policy_stats={path:(path.stat().st_mtime_ns,path.stat().st_size) for path in used_policy_paths}
    global STREAM
    if args.stream_engine:
        STREAM=subprocess.Popen([str(BIN),'--stream'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,text=True,cwd=ROOT,bufsize=1)
    rebel_v2_worker=None
    if rebel_v2_source:
        python=ROOT/'.cache'/'rebel-venv'/'bin'/'python'
        if not python.is_file():raise SystemExit('updated ReBeL requires make setup-rebel-v2')
        rebel_v2_worker=subprocess.Popen([str(python),str(ROOT/'server'/'rebel_worker_v2.py')],
                                          stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                          text=True,cwd=ROOT,bufsize=1)
    def rebel_v2_command(command):
        rebel_v2_worker.stdin.write(json.dumps(command,separators=(',',':'))+'\n')
        rebel_v2_worker.stdin.flush()
        if not select.select([rebel_v2_worker.stdout],[],[],30)[0]:raise RuntimeError('updated ReBeL worker timed out')
        response=rebel_v2_worker.stdout.readline()
        if not response:raise RuntimeError('updated ReBeL worker exited')
        data=json.loads(response)
        if 'error' in data:raise RuntimeError(data['error'])
        return data
    try:
        for pair_index,(left,right) in enumerate(plan):
            for seat in (0,1):
                agent_a,agent_b=(left,right) if seat==0 else (right,left)
                wins=0
                for index in range(args.per_seat):
                    if BIN.stat().st_mtime_ns!=binary_mtime:raise RuntimeError('engine binary changed during run')
                    for path in used_policy_paths:
                        if (path.stat().st_mtime_ns,path.stat().st_size)!=policy_stats[path]:raise RuntimeError('policy metadata changed during run')
                        if completed%100==0 and hashlib.sha256(path.read_bytes()).hexdigest()!=policy_hashes[str(path.relative_to(ROOT))]:raise RuntimeError('policy changed during run')
                    if os.statvfs(folder).f_bavail*os.statvfs(folder).f_frsize<args.min_free_mib*1024**2:raise RuntimeError('free disk guard reached')
                    if (folder/'evaluation.sqlite3').stat().st_size>int(1.5*1024**3):raise RuntimeError('artifact cap reached')
                    seed=args.seed_offset+index if args.paired_seeds else args.seed_offset+pair_index*args.per_seat+index
                    started=time.perf_counter()
                    state=engine({'op':'new','n':5,'agent_human':agent_a,'agent':agent_b,'seed':seed,'auto_ai':False})['state']
                    if rebel_policy:
                        rebel_policy.reset_match(policy_seeds[pair_index][index]['rebel_transfer_v1'])
                    match_id=completed+1
                    decisions=[]
                    for turn in range(500):
                        if state['status']=='COMPLETED':break
                        if state['phase']=='ROUND_OVER':
                            state=engine({'op':'next_round','state':state,'auto_ai':False})['state']
                            continue
                        player=state['turn'];t=time.perf_counter()
                        agent=agent_a if player==0 else agent_b
                        if agent=='rebel_transfer_v1':
                            from rebel_bridge import private_observation
                            observation={'player':'HUMAN' if player==0 else 'AI','hand':state['hands'][player],
                                         'scores':state['scores'],'bid':state['bid'],'round':state['round']}
                            action=rebel_policy.act(private_observation(state))
                            result={'state':engine({'op':'step','state':state,'action':action})['state'],
                                    'observation':observation,'action':action,'policy_hit':True,
                                    'policy_source':f'rebel_transfer_depth{rebel_policy.search_depth}_fp{rebel_policy.search_iters}'}
                        elif agent=='rebel_bluff_v2':
                            from rebel_v2_bridge import private_observation
                            observation={'player':'HUMAN' if player==0 else 'AI','hand':state['hands'][player],
                                         'scores':state['scores'],'bid':state['bid'],'round':state['round']}
                            choice=rebel_v2_command({'match_id':str(match_id),
                                                     'seed':policy_seeds[pair_index][index]['rebel_bluff_v2'],
                                                     'search_iters':args.rebel_v2_iters,'search_depth':args.rebel_v2_depth,
                                                     'observation':private_observation(state)})
                            action=choice['action']
                            result={'state':engine({'op':'step','state':state,'action':action})['state'],
                                    'observation':observation,'action':action,'policy_hit':True,
                                    'policy_source':f'rebel_bluff_depth{args.rebel_v2_depth}_fp{args.rebel_v2_iters}'}
                        else:
                            result=engine({'op':'bot_step','state':state})
                        latency=(time.perf_counter()-t)*1000
                        observation=result['observation']
                        compact={key:observation[key] for key in ('player','hand','scores','bid','round')}
                        decisions.append((match_id,turn,state['round'],'HUMAN' if player==0 else 'AI',agent_a if player==0 else agent_b,json.dumps(compact,separators=(',',':')),json.dumps(result['action'],separators=(',',':')),latency,int(result.get('policy_hit',False)),result.get('policy_source')))
                        state=result['state']
                    if state['status']!='COMPLETED':raise RuntimeError(f'match {match_id} exceeded 500 actions')
                    wins+=state['winner']==('HUMAN' if seat==0 else 'AI')
                    db.execute('INSERT INTO matches VALUES (?,?,?,?,?,?,?,?)',(match_id,agent_a,agent_b,seed,state['winner'],state['round'],len(decisions),(time.perf_counter()-started)*1000))
                    db.executemany('INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?)',decisions)
                    db.executemany('INSERT INTO rounds VALUES (?,?,?)',[(match_id,e['round'],json.dumps(e,separators=(',',':'))) for e in state['events'] if e['type']=='reveal'])
                    db.commit()
                    if rebel_v2_worker:rebel_v2_command({'op':'drop','match_id':str(match_id)})
                    completed+=1
                    if completed%100==0:print(json.dumps({'completed':completed,'planned':total_planned}),flush=True)
                results[f'{left}_vs_{right}_seat_{seat}']={'wins':wins,'matches':args.per_seat,'win_rate':wins/args.per_seat,'wilson95':wilson(wins,args.per_seat)}
        for path in used_policy_paths:
            if hashlib.sha256(path.read_bytes()).hexdigest()!=policy_hashes[str(path.relative_to(ROOT))]:raise RuntimeError('policy changed before completion')
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
    finally:
        db.close()
        if STREAM is not None:
            STREAM.stdin.close()
            STREAM.wait(timeout=5)
            STREAM=None
        if rebel_v2_worker is not None:
            rebel_v2_worker.stdin.close()
            rebel_v2_worker.wait(timeout=5)
        details=json.loads((folder/'manifest.json').read_text())
        details['elapsed_seconds']=time.perf_counter()-run_started
        details['database_bytes']=(folder/'evaluation.sqlite3').stat().st_size
        unit=1 if platform.system()=='Darwin' else 1024
        details['python_peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*unit
        details['engine_peak_rss_bytes']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*unit
        (folder/'manifest.json').write_text(json.dumps(details,indent=2))
if __name__=='__main__':main()
