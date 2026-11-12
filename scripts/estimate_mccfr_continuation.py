"""Measure v1 self-play round win probability for v2's frozen match continuation."""
import argparse
import hashlib
import json
import math
import os
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'build/bluff_engine'
POLICY = ROOT / 'policies/mccfr_external_v1.bin'
RULESET = 'fixed5_score5_quantity_only_v1'


def step(command):
    result = subprocess.run([str(ENGINE)], input=json.dumps(command), text=True,
                            capture_output=True, cwd=ROOT, check=True, timeout=8)
    parsed = json.loads(result.stdout)
    if 'error' in parsed:
        raise RuntimeError(parsed['error'])
    return parsed['state']


def wilson(wins, total):
    z = 1.96
    p = wins / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [center - radius, center + radius]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--rounds', type=int, default=2000)
    parser.add_argument('--seed-offset', type=int, default=8600000)
    args = parser.parse_args()
    if not (1000 <= args.rounds <= 100000) or '/' in args.run_id or '..' in args.run_id:
        raise ValueError('invalid run configuration')
    folder = ROOT / 'experiments/runs' / args.run_id
    folder.mkdir(parents=True, exist_ok=False)
    manifest = {'run_id': args.run_id, 'status': 'started', 'ruleset': RULESET,
                'agent': 'mccfr_external_v1', 'rounds_planned': args.rounds,
                'seed_offset': args.seed_offset, 'command': ' '.join(os.sys.argv),
                'engine_sha256': hashlib.sha256(ENGINE.read_bytes()).hexdigest(),
                'policy_sha256': hashlib.sha256(POLICY.read_bytes()).hexdigest(),
                'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    database = sqlite3.connect(folder / 'rounds.sqlite3')
    database.execute('CREATE TABLE rounds(seed INTEGER PRIMARY KEY,starter INTEGER,winner INTEGER,actions INTEGER)')
    wins = 0
    started = time.perf_counter()
    try:
        for index in range(args.rounds):
            if os.statvfs(folder).f_bavail * os.statvfs(folder).f_frsize < 2 * 1024**3:
                raise RuntimeError('2 GiB free-disk guard reached')
            seed = args.seed_offset + index
            state = step({'op': 'new', 'n': 5, 'seed': seed, 'agent': 'mccfr_external_v1',
                          'agent_human': 'mccfr_external_v1', 'auto_ai': False})
            starter = state['starter']
            actions = 0
            while state['phase'] == 'BIDDING':
                state = step({'op': 'bot_step', 'state': state})
                actions += 1
                if actions > 50:
                    raise RuntimeError('round exceeded 50 actions')
            reveal = next(event for event in reversed(state['events']) if event['type'] == 'reveal')
            winner = 0 if reveal['winner'] == 'HUMAN' else 1
            wins += winner == starter
            database.execute('INSERT INTO rounds VALUES (?,?,?,?)', (seed, starter, winner, actions))
            if index % 100 == 99:
                database.commit()
                print(json.dumps({'completed_rounds': index + 1, 'planned': args.rounds}), flush=True)
        database.commit()
        summary = {'ruleset': RULESET, 'agent': 'mccfr_external_v1', 'completed_rounds': args.rounds,
                   'starter_wins': wins, 'starter_win_rate': wins / args.rounds,
                   'wilson95': wilson(wins, args.rounds), 'elapsed_seconds': time.perf_counter() - started,
                   'seed_offset': args.seed_offset}
        (folder / 'continuation.json').write_text(json.dumps(summary, indent=2))
        manifest.update(status='completed', completed_rounds=args.rounds,
                        ended_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        print(json.dumps(summary), flush=True)
    except BaseException as error:
        database.commit()
        manifest.update(status='failed', completed_rounds=database.execute('SELECT COUNT(*) FROM rounds').fetchone()[0],
                        error=repr(error), ended_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        raise
    finally:
        database.close()


if __name__ == '__main__':
    main()
