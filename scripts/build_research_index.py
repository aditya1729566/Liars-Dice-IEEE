"""Publish completed fixed-five evaluation summaries for a fresh local checkout."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULESET = 'fixed5_score5_quantity_only_v1'
HISTORICAL_ADAPTIVE = {'fixed5_five_agent_holdout_200', 'fixed5_hard_holdout_200'}
REBEL_SCREENS = {'rebel_adapter_smoke_20261112': 'Two-match integration smoke check; not a strength estimate.',
                 'rebel_transfer_league_20261112': 'Development screen before per-match ReBeL sampler reseeding; use the final tournament for strength estimates.',
                 'rebel_fp16_dev_20261112': 'Small 16-iteration search development screen; not the selected ReBeL configuration.',
                 'rebel_bluff_v2_smoke_20261114': 'Six-match updated ReBeL integration smoke check; not a strength estimate.',
                 'rebel_v2_seed_replay_a_20261115': 'Two-match exact seed-replay check; not a strength estimate.',
                 'rebel_v2_seed_replay_b_20261115': 'Repeat of the exact seed-replay check; not independent strength evidence.'}


def main():
    runs = []
    for path in sorted((ROOT / 'experiments' / 'runs').glob('*/summary.json')):
        manifest_path = path.parent / 'manifest.json'
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        if manifest.get('status') != 'completed' or manifest.get('ruleset') != RULESET:
            continue
        item = json.loads(path.read_text())
        if 'results' not in item:
            continue
        metrics_path = path.parent / 'mccfr_metrics.json'
        if metrics_path.exists():
            item['mccfr_metrics'] = {'opponents': {
                opponent: {'paired_seed_cluster95': values['paired_seed_cluster95']}
                for opponent, values in json.loads(metrics_path.read_text())['opponents'].items()
                if 'paired_seed_cluster95' in values
            }}
        v2_metrics_path = path.parent / 'mccfr_v2_metrics.json'
        if v2_metrics_path.exists():
            item['mccfr_v2_metrics'] = {'opponents': {
                opponent: {'paired_seed_cluster95': values['paired_seed_cluster95'],
                           'policy_coverage': values['policy_coverage']}
                for opponent, values in json.loads(v2_metrics_path.read_text())['opponents'].items()
                if 'paired_seed_cluster95' in values
            }}
        rebel_metrics_path = path.parent / 'rebel_transfer_v1_metrics.json'
        if rebel_metrics_path.exists():
            item['rebel_metrics'] = {'opponents': {
                opponent: {'paired_seed_cluster95': values['paired_seed_cluster95'],
                           'policy_coverage': values['policy_coverage']}
                for opponent, values in json.loads(rebel_metrics_path.read_text())['opponents'].items()
                if 'paired_seed_cluster95' in values
            }}
        rebel_v2_metrics_path = path.parent / 'rebel_bluff_v2_metrics.json'
        if rebel_v2_metrics_path.exists():
            item['rebel_v2_metrics'] = {'opponents': {
                opponent: {'paired_seed_cluster95': values['paired_seed_cluster95'],
                           'policy_coverage': values['policy_coverage']}
                for opponent, values in json.loads(rebel_v2_metrics_path.read_text())['opponents'].items()
                if 'paired_seed_cluster95' in values
            }}
        item['provenance'] = {key: manifest.get(key) for key in ('seed_offset', 'engine_sha256', 'policy_sha256', 'policy_sha256_by_file')}
        if item['run_id'] in HISTORICAL_ADAPTIVE:
            item['warning'] = 'Historical adaptive rows are excluded from promotion after a seat-symmetry bug; CFR pairings remain valid.'
        if item['run_id'] in REBEL_SCREENS:
            item['warning'] = REBEL_SCREENS[item['run_id']]
        runs.append(item)
    output = ROOT / 'docs' / 'research_runs.json'
    output.write_text(json.dumps(runs, indent=2))
    print(f'{len(runs)} completed runs written to {output.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
