"""Reproduce paired v2-versus-legacy results from completed fixed-five runs."""
import json
import random
import sqlite3
from pathlib import Path

from tournament import wilson

ROOT = Path(__file__).resolve().parents[1]
CONFIRM = 'fixed5_cfr_v2_confirm_400'
TRUTHFUL = 'fixed5_truthful_probe_200'


def run_data(run_id):
    folder = ROOT / 'experiments' / 'runs' / run_id
    manifest = json.loads((folder / 'manifest.json').read_text())
    if manifest.get('status') != 'completed' or not manifest.get('paired_seeds'):
        raise SystemExit(f'run is not complete and paired: {run_id}')
    with sqlite3.connect(folder / 'evaluation.sqlite3') as con:
        rows = con.execute('SELECT agent_a,agent_b,seed,winner FROM matches').fetchall()
        latencies = sorted(value for (value,) in con.execute("SELECT latency_ms FROM decisions WHERE agent='cfr2'"))
        errors = con.execute('SELECT COUNT(*) FROM errors').fetchone()[0]
        policy_hits = con.execute("SELECT COALESCE(SUM(policy_hit),0) FROM decisions WHERE agent='cfr2'").fetchone()[0]
    return manifest, {(a, b, seed): winner for a, b, seed, winner in rows}, latencies, errors, policy_hits


def win(rows, agent, opponent, seed, seat):
    if seat == 'HUMAN':
        return int(rows[(agent, opponent, seed)] == 'HUMAN')
    return int(rows[(opponent, agent, seed)] == 'AI')


def bootstrap(blocks, seed=1729, resamples=20000):
    rng = random.Random(seed)
    n = len(blocks)
    samples = sorted(sum(blocks[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples))
    return [samples[int(.025 * resamples)], samples[int(.975 * resamples) - 1]]


def comparison(manifest, rows, opponent):
    seeds = range(manifest['seed_offset'], manifest['seed_offset'] + manifest['per_seat'])
    blocks = [(sum(win(rows, 'cfr2', opponent, seed, seat) - win(rows, 'cfr', opponent, seed, seat) for seat in ('HUMAN', 'AI')) / 2) for seed in seeds]
    return {'v2_minus_legacy': sum(blocks) / len(blocks), 'paired_bootstrap_95': bootstrap(blocks), 'seed_blocks': len(blocks)}


def main():
    confirm, confirm_rows, latencies, errors, hits = run_data(CONFIRM)
    truthful, truthful_rows, _, truthful_errors, _ = run_data(TRUTHFUL)
    if errors or truthful_errors:
        raise SystemExit('evaluation contains run errors')
    direct = [win(confirm_rows, 'cfr2', 'cfr', seed, seat) for seed in range(confirm['seed_offset'], confirm['seed_offset'] + confirm['per_seat']) for seat in ('HUMAN', 'AI')]
    probability = {agent: [win(confirm_rows, agent, 'probability', seed, seat) for seed in range(confirm['seed_offset'], confirm['seed_offset'] + confirm['per_seat']) for seat in ('HUMAN', 'AI')] for agent in ('cfr2', 'cfr')}
    result = {
        'runs': [CONFIRM, TRUTHFUL],
        'direct_v2_vs_legacy': {'wins': sum(direct), 'matches': len(direct), 'win_rate': sum(direct) / len(direct), 'wilson95': wilson(sum(direct), len(direct))},
        'versus_probability': {agent: {'wins': sum(wins), 'matches': len(wins), 'win_rate': sum(wins) / len(wins), 'wilson95': wilson(sum(wins), len(wins))} for agent, wins in probability.items()},
        'paired_v2_minus_legacy_vs_probability': comparison(confirm, confirm_rows, 'probability'),
        'paired_v2_minus_legacy_vs_truthful': comparison(truthful, truthful_rows, 'truthful'),
        'v2_decision_latency_ms': {'count': len(latencies), 'p95': latencies[int(.95 * len(latencies)) - 1], 'maximum': latencies[-1], 'policy_hits': hits},
        'errors': errors + truthful_errors,
        'bootstrap_seed': 1729,
        'bootstrap_resamples': 20000,
        'block_definition': 'same seed and both seats, one opponent per comparison',
    }
    path = ROOT / 'experiments' / 'runs' / CONFIRM / 'comparison.json'
    path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
