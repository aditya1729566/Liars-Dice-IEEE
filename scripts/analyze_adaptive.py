"""Measure public-outcome observation opportunities in an adaptive evaluation."""
import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    folder = ROOT / 'experiments' / 'runs' / args.run_id
    manifest = json.loads((folder / 'manifest.json').read_text())
    if manifest.get('status') != 'completed':
        raise SystemExit('requires a completed run')
    with sqlite3.connect(folder / 'evaluation.sqlite3') as con:
        matches = con.execute("SELECT id,agent_a,agent_b FROM matches WHERE agent_a='adaptive' OR agent_b='adaptive'").fetchall()
        reveal_rows = con.execute('SELECT match_id,round_index,reveal_json FROM rounds ORDER BY match_id,round_index').fetchall()
        decision_rows = con.execute("SELECT match_id,round_index,policy_hit FROM decisions WHERE agent='adaptive'").fetchall()
    reveals = {}
    for match_id, round_index, payload in reveal_rows:
        reveals.setdefault(match_id, []).append((round_index, json.loads(payload)['bidder']))
    seats = {match_id: ('AI' if agent_b == 'adaptive' else 'HUMAN') for match_id, agent_a, agent_b in matches}
    eligible_decisions = total_decisions = policy_hits = 0
    eligible_match_ids = set()
    first_eligible_rounds = []
    for match_id, round_index, hit in decision_rows:
        total_decisions += 1
        policy_hits += hit
        opponent = 'HUMAN' if seats[match_id] == 'AI' else 'AI'
        count = sum(r < round_index and bidder == opponent for r, bidder in reveals.get(match_id, []))
        if count >= 3:
            eligible_decisions += 1
            if match_id not in eligible_match_ids:
                eligible_match_ids.add(match_id)
                first_eligible_rounds.append(round_index)
    result = {'run_id': args.run_id, 'adaptive_matches': len(matches), 'adaptive_decisions': total_decisions, 'policy_hits': policy_hits, 'decisions_with_at_least_three_confirmed_opponent_bidder_reveals': eligible_decisions, 'matches_reaching_three_observations': len(eligible_match_ids), 'first_eligible_round_mean': sum(first_eligible_rounds)/len(first_eligible_rounds) if first_eligible_rounds else None, 'note': 'Eligibility is reconstructed from public revealed rounds; this does not prove the adaptive branch was sampled on every eligible decision.'}
    (folder / 'adaptive_observations.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
