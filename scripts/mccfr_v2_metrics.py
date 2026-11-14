"""Derive v2 match, move, latency, coverage, and conservative paired intervals."""
import argparse
import json
import math
import sqlite3
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = 'mccfr_external_v2'


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)] if ordered else None


def wilson(proportion, blocks):
    z = 1.96
    denominator = 1 + z * z / blocks
    center = (proportion + z * z / (2 * blocks)) / denominator
    radius = z * math.sqrt(proportion * (1 - proportion) / blocks + z * z / (4 * blocks * blocks)) / denominator
    return [center - radius, center + radius]


def analyze(folder, agent=AGENT):
    manifest = json.loads((folder / 'manifest.json').read_text())
    if manifest['status'] != 'completed':
        raise ValueError('evaluation has not completed')
    connection = sqlite3.connect(folder / 'evaluation.sqlite3')
    reveals = defaultdict(dict)
    for match_id, round_index, raw in connection.execute('SELECT match_id,round_index,reveal_json FROM rounds'):
        reveals[match_id][round_index] = json.loads(raw)
    decisions = defaultdict(list)
    for row in connection.execute('SELECT match_id,round_index,player,agent,action_json,latency_ms,policy_source FROM decisions'):
        match_id, round_index, player, decision_agent, action, latency, source = row
        decisions[match_id].append((round_index, player, decision_agent, json.loads(action), latency, source))
    groups = defaultdict(lambda: {'matches': 0, 'wins': 0, 'rounds': [], 'actions': [],
                                  'seeds': defaultdict(list), 'sources': Counter(),
                                  'bids': 0, 'false_bids': 0, 'calls': 0, 'correct_calls': 0,
                                  'decisions': 0, 'latencies': []})
    for match_id, agent_a, agent_b, seed, winner, rounds, actions in connection.execute(
        'SELECT id,agent_a,agent_b,seed,winner,rounds,actions FROM matches'
    ):
        if agent not in (agent_a, agent_b):
            continue
        opponent = agent_b if agent_a == agent else agent_a
        group = groups[opponent]
        won = (agent_a if winner == 'HUMAN' else agent_b) == agent
        group['matches'] += 1
        group['wins'] += won
        group['seeds'][seed].append(int(won))
        group['rounds'].append(rounds)
        group['actions'].append(actions)
        for round_index, player, decision_agent, action, latency, source in decisions[match_id]:
            if decision_agent != agent:
                continue
            group['decisions'] += 1
            group['latencies'].append(latency)
            group['sources'][source or 'heuristic'] += 1
            reveal = reveals[match_id][round_index]
            if action['type'] == 'bid':
                group['bids'] += 1
                actual = sum(die == action['f'] for hand in reveal['hands'] for die in hand)
                group['false_bids'] += actual < action['q']
            else:
                group['calls'] += 1
                group['correct_calls'] += reveal['winner'] == player
    output = {'run_id': folder.name, 'agent': agent,
              'source': str((folder / 'evaluation.sqlite3').relative_to(ROOT)),
              'completed_matches': connection.execute('SELECT COUNT(*) FROM matches').fetchone()[0],
              'errors': connection.execute('SELECT COUNT(*) FROM errors').fetchone()[0], 'opponents': {}}
    for name, group in sorted(groups.items()):
        n = group['matches']
        result = {'matches': n, 'wins': group['wins'], 'losses': n - group['wins'],
                  'win_rate': group['wins'] / n, 'average_match_rounds': statistics.mean(group['rounds']),
                  'average_match_actions': statistics.mean(group['actions']),
                  'decisions': group['decisions'], 'sources': dict(group['sources']),
                  'policy_coverage': ((group['sources']['exact'] + group['sources']['backoff']) if agent == AGENT else
                                      sum(value for key, value in group['sources'].items() if key not in ('heuristic', 'probability_heuristic'))) / group['decisions'],
                  'exact_coverage': group['sources']['exact'] / group['decisions'],
                  'bluff_frequency': group['false_bids'] / group['bids'] if group['bids'] else None,
                  'challenge_frequency': group['calls'] / group['decisions'],
                  'challenge_accuracy': group['correct_calls'] / group['calls'] if group['calls'] else None,
                  'latency_p50_ms': percentile(group['latencies'], 0.5),
                  'latency_p95_ms': percentile(group['latencies'], 0.95)}
        if agent == 'rebel_bluff_v2':
            result['worker_response_coverage'] = result['policy_coverage']
            result['learned_information_set_coverage'] = None
            result['coverage_note'] = 'Worker response coverage only; no learned information-set coverage is measured.'
        if len(group['seeds']) > 1 and all(len(outcomes) == 2 for outcomes in group['seeds'].values()):
            paired = [sum(outcomes) / 2 for outcomes in group['seeds'].values()]
            standard_error = math.sqrt(statistics.variance(paired) / len(paired))
            normal = [max(0, result['win_rate'] - 1.96 * standard_error),
                      min(1, result['win_rate'] + 1.96 * standard_error)]
            # The seed-count Wilson bound prevents degenerate intervals when every
            # observed seed block wins (or loses) both seats.
            floor = wilson(result['win_rate'], len(paired))
            result['paired_seed_cluster95'] = [min(normal[0], floor[0]), max(normal[1], floor[1])]
        output['opponents'][name] = result
    connection.close()
    filename = 'mccfr_v2_metrics.json' if agent == AGENT else f'{agent}_metrics.json'
    (folder / filename).write_text(json.dumps(output, indent=2))
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    parser.add_argument('--agent', default=AGENT)
    args = parser.parse_args()
    print(json.dumps(analyze(ROOT / 'experiments/runs' / args.run_id, args.agent), indent=2))
