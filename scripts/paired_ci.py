"""Paired bootstrap of CFR's balanced-league improvement over probability."""
import argparse
import json
import random
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--resamples', type=int, default=20000)
    args = parser.parse_args()
    folder = ROOT / 'experiments' / 'runs' / args.run_id
    manifest = json.loads((folder / 'manifest.json').read_text())
    if manifest['status'] != 'completed' or not manifest.get('paired_seeds'):
        raise SystemExit('requires a completed paired-seed run')
    with sqlite3.connect(folder / 'evaluation.sqlite3') as con:
        rows = con.execute('SELECT agent_a,agent_b,seed,winner FROM matches').fetchall()
    wins = {(a, b, seed): int(winner == 'HUMAN') for a, b, seed, winner in rows}
    # Each block keeps the same seed, both seats, and both opponent archetypes together.
    blocks = []
    for seed in range(manifest['seed_offset'], manifest['seed_offset'] + manifest['per_seat']):
        differences = []
        for seat in ('human', 'ai'):
            for opponent in ('conservative', 'high_call'):
                if seat == 'human':
                    cfr_win = wins[('cfr', opponent, seed)]
                    prob_win = wins[('probability', opponent, seed)]
                else:
                    cfr_win = 1 - wins[(opponent, 'cfr', seed)]
                    prob_win = 1 - wins[(opponent, 'probability', seed)]
                differences.append(cfr_win - prob_win)
        blocks.append(sum(differences) / len(differences))
    n = len(blocks)
    observed = sum(blocks) / n
    rng = random.Random(1729)
    samples = sorted(sum(blocks[rng.randrange(n)] for _ in range(n)) / n for _ in range(args.resamples))
    result = {'run_id': args.run_id, 'metric': 'CFR minus probability match win rate vs conservative and high_call, equally weighted by opponent and seat', 'blocks': n, 'block_definition': 'same seed, average difference across both seats and both opponents', 'improvement': observed, 'paired_bootstrap_95': [samples[int(.025 * args.resamples)], samples[int(.975 * args.resamples) - 1]], 'resamples': args.resamples, 'bootstrap_seed': 1729}
    (folder / 'paired_ci.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
