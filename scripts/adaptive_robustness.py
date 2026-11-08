"""Paired fresh-seed adaptive robustness comparisons against control runs."""
import argparse
import json
import random
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVES = {
    'fixed5_adaptive_corrected_400': 'fixed5-adaptive-corrected.zip',
    'fixed5_probability_controls_400': 'fixed5-probability-controls.zip',
    'fixed5_switcher_controls_400': 'fixed5-switcher-controls.zip',
}


def outcomes(run_id):
    path = ROOT / 'experiments' / 'runs' / run_id / 'evaluation.sqlite3'
    if path.exists():
        with sqlite3.connect(path) as con:
            return {(a, b, seed): winner for a, b, seed, winner in con.execute('SELECT agent_a,agent_b,seed,winner FROM matches')}
    archive = ROOT / 'outputs' / ARCHIVES[run_id]
    with tempfile.TemporaryDirectory(prefix='bluff-eval-') as directory, zipfile.ZipFile(archive) as zipped:
        name = f'{run_id}/evaluation.sqlite3'
        if zipped.getinfo(name).file_size > 1_500_000_000:
            raise SystemExit(f'archived evaluation exceeds artifact cap: {run_id}')
        temporary_db = Path(directory) / 'evaluation.sqlite3'
        with zipped.open(name) as source, temporary_db.open('wb') as destination:
            shutil.copyfileobj(source, destination)
        with sqlite3.connect(temporary_db) as con:
            return {(a, b, seed): winner for a, b, seed, winner in con.execute('SELECT agent_a,agent_b,seed,winner FROM matches')}


def win(rows, agent, opponent, seed, seat):
    if seat == 'HUMAN':
        return int(rows[(agent, opponent, seed)] == 'HUMAN')
    return int(rows[(opponent, agent, seed)] == 'AI')


def interval(blocks, rng, resamples):
    n = len(blocks)
    samples = sorted(sum(blocks[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples))
    return [samples[int(.025 * resamples)], samples[int(.975 * resamples) - 1]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adaptive-run', default='fixed5_adaptive_corrected_400')
    parser.add_argument('--static-controls', default='fixed5_probability_controls_400')
    parser.add_argument('--switcher-controls', default='fixed5_switcher_controls_400')
    args = parser.parse_args()
    runs = [args.adaptive_run, args.static_controls, args.switcher_controls]
    for run_id in runs:
        manifest = json.loads((ROOT / 'experiments' / 'runs' / run_id / 'manifest.json').read_text())
        if manifest.get('status') != 'completed' or not manifest.get('paired_seeds') or manifest.get('seed_offset') != 8000000 or manifest.get('per_seat') != 400:
            raise SystemExit(f'incompatible or incomplete control: {run_id}')
    adaptive, static, switcher = map(outcomes, runs)
    rng = random.Random(1729)
    results = {}
    for label, opponents, comparator, control in (
        ('adaptive_minus_probability_static', ('conservative', 'high_call'), 'probability', static),
        ('adaptive_minus_probability_switcher', ('switcher',), 'probability', switcher),
        ('adaptive_minus_cfr_switcher', ('switcher',), 'cfr', switcher),
    ):
        blocks = []
        for seed in range(8000000, 8000400):
            diffs = [win(adaptive, 'adaptive', opp, seed, seat) - win(control, comparator, opp, seed, seat)
                     for seat in ('HUMAN', 'AI') for opp in opponents]
            blocks.append(sum(diffs) / len(diffs))
        results[label] = {'improvement': sum(blocks) / len(blocks), 'paired_bootstrap_95': interval(blocks, rng, 10000), 'seed_blocks': len(blocks)}
    output = {'runs': runs, 'block_definition': 'same seed, both seats and all opponents in the named comparison', 'bootstrap_seed': 1729, 'resamples': 10000, 'results': results}
    folder = ROOT / 'experiments' / 'runs' / args.adaptive_run
    (folder / 'robustness.json').write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
