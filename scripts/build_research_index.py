"""Publish completed fixed-five evaluation summaries for a fresh local checkout."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULESET = 'fixed5_score5_quantity_only_v1'
HISTORICAL_ADAPTIVE = {'fixed5_five_agent_holdout_200', 'fixed5_hard_holdout_200'}


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
        item['provenance'] = {key: manifest.get(key) for key in ('seed_offset', 'engine_sha256', 'policy_sha256', 'policy_sha256_by_file')}
        if item['run_id'] in HISTORICAL_ADAPTIVE:
            item['warning'] = 'Historical adaptive rows are excluded from promotion after a seat-symmetry bug; CFR pairings remain valid.'
        runs.append(item)
    output = ROOT / 'docs' / 'research_runs.json'
    output.write_text(json.dumps(runs, indent=2))
    print(f'{len(runs)} completed runs written to {output.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
