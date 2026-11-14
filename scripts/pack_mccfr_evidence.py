"""Archive completed MCCFR runs without modifying their original evidence."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def package(output, run_ids, include_policies=False):
    output = output if output.is_absolute() else ROOT / output
    files = []
    for run_id in run_ids:
        folder = ROOT / 'experiments/runs' / run_id
        manifest = folder / 'manifest.json'
        if not manifest.exists() or json.loads(manifest.read_text()).get('status') != 'completed':
            raise ValueError(f'run is not completed: {run_id}')
        files.extend(path for path in (manifest, folder / 'summary.json', folder / 'mccfr_metrics.json',
                                       folder / 'mccfr_v2_metrics.json', folder / 'rebel_transfer_v1_metrics.json',
                                       folder / 'rebel_bluff_v2_metrics.json', folder / 'continuation.json',
                                       folder / 'policy_seeds.json', folder / 'rounds.sqlite3', folder / 'evaluation.sqlite3') if path.exists())
        if include_policies:
            files.extend(sorted(folder.glob('policy_*.json')))
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_suffix(output.suffix + '.pending')
    with ZipFile(pending, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT))
    pending.replace(output)
    print(json.dumps({'archive': str(output.relative_to(ROOT)), 'files': len(files),
                      'bytes': output.stat().st_size,
                      'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('run_ids', nargs='+')
    parser.add_argument('--include-policies', action='store_true')
    args = parser.parse_args()
    package(args.output, args.run_ids, args.include_policies)
