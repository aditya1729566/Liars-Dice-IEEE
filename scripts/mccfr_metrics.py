"""Calculate auditable match and move metrics from tournament SQLite evidence."""
import argparse
import json
import math
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def wilson(wins, total):
    if not total:
        return [0, 1]
    z = 1.96
    p = wins / total
    divisor = 1 + z * z / total
    center = (p + z * z / (2 * total)) / divisor
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / divisor
    return [center - half, center + half]


def percentile(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, math.ceil(p * len(values)) - 1)] if values else None


def analyze(folder):
    connection = sqlite3.connect(folder / 'evaluation.sqlite3')
    matches = connection.execute('SELECT id,agent_a,agent_b,seed,winner,rounds,actions FROM matches').fetchall()
    rounds = defaultdict(dict)
    for match_id, round_index, raw in connection.execute('SELECT match_id,round_index,reveal_json FROM rounds'):
        rounds[match_id][round_index] = json.loads(raw)
    decisions = defaultdict(list)
    for match_id, round_index, player, agent, action, latency, hit in connection.execute(
        'SELECT match_id,round_index,player,agent,action_json,latency_ms,policy_hit FROM decisions'
    ):
        decisions[match_id].append((round_index, player, agent, json.loads(action), latency, hit))
    by_pair = defaultdict(lambda: {'matches': 0, 'wins': 0, 'rounds': [], 'actions': [],
                                   'mccfr': {'bids': 0, 'false_bids': 0, 'calls': 0, 'correct_calls': 0, 'decisions': 0, 'policy_hits': 0, 'latency_ms': []},
                                   'opponent': {'bids': 0, 'false_bids': 0, 'calls': 0, 'correct_calls': 0, 'decisions': 0, 'policy_hits': 0, 'latency_ms': []}})
    for match_id, agent_a, agent_b, seed, winner, count_rounds, actions in matches:
        if 'mccfr_external_v1' not in (agent_a, agent_b):
            continue
        opponent = agent_b if agent_a == 'mccfr_external_v1' else agent_a
        row = by_pair[opponent]
        row['matches'] += 1
        won = (agent_a if winner == 'HUMAN' else agent_b) == 'mccfr_external_v1'
        row['wins'] += won
        row.setdefault('seed_outcomes', defaultdict(list))[seed].append(int(won))
        row['rounds'].append(count_rounds)
        row['actions'].append(actions)
        for round_index, player, agent, action, latency, hit in decisions[match_id]:
            side = row['mccfr' if agent == 'mccfr_external_v1' else 'opponent']
            side['decisions'] += 1
            side['policy_hits'] += hit
            side['latency_ms'].append(latency)
            reveal = rounds[match_id][round_index]
            if action['type'] == 'bid':
                side['bids'] += 1
                actual = sum(die == action['f'] for hand in reveal['hands'] for die in hand)
                side['false_bids'] += actual < action['q']
            elif action['type'] == 'call':
                side['calls'] += 1
                side['correct_calls'] += reveal['winner'] == player
    output = {'source': str((folder / 'evaluation.sqlite3').relative_to(ROOT)), 'completed_matches': len(matches), 'opponents': {}}
    for opponent, row in sorted(by_pair.items()):
        result = {'matches': row['matches'], 'wins': row['wins'], 'losses': row['matches'] - row['wins'],
                  'win_rate': row['wins'] / row['matches'], 'wilson95': wilson(row['wins'], row['matches']),
                  'average_match_rounds': statistics.mean(row['rounds']),
                  'average_match_actions': statistics.mean(row['actions'])}
        seed_outcomes = row['seed_outcomes']
        if len(seed_outcomes) > 1 and all(len(outcomes) == 2 for outcomes in seed_outcomes.values()):
            paired_rates = [sum(outcomes) / 2 for outcomes in seed_outcomes.values()]
            standard_error = math.sqrt(statistics.variance(paired_rates) / len(paired_rates))
            result['paired_seed_cluster95'] = [max(0, result['win_rate'] - 1.96 * standard_error),
                                               min(1, result['win_rate'] + 1.96 * standard_error)]
        for side_name in ('mccfr', 'opponent'):
            side = row[side_name]
            result[side_name] = {key: side[key] for key in ('decisions', 'policy_hits', 'bids', 'false_bids', 'calls', 'correct_calls')}
            result[side_name].update(bluff_frequency=side['false_bids'] / side['bids'] if side['bids'] else None,
                                     challenge_frequency=side['calls'] / side['decisions'] if side['decisions'] else None,
                                     challenge_accuracy=side['correct_calls'] / side['calls'] if side['calls'] else None,
                                     latency_p50_ms=percentile(side['latency_ms'], .5),
                                     latency_p95_ms=percentile(side['latency_ms'], .95))
        output['opponents'][opponent] = result
    (folder / 'mccfr_metrics.json').write_text(json.dumps(output, indent=2))
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    args = parser.parse_args()
    print(json.dumps(analyze(ROOT / 'experiments/runs' / args.run_id), indent=2))
