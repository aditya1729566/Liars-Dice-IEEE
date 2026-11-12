"""Pack a measured MCCFR checkpoint into a fixed-record, seekable policy.

The source JSON remains in experiments/runs; this compact binary is used only
for low-latency inference in the one-process-per-action game engine.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = struct.Struct('<32sB7B7f')
HEADER = struct.Struct('<8sQ')


def action_id(action):
    if action == 'C':
        return 0
    quantity, face = map(int, action.split('-'))
    if not (1 <= quantity <= 10 and 1 <= face <= 6):
        raise ValueError(f'invalid action {action}')
    return (quantity - 1) * 6 + face


def pack(source, destination):
    data = json.loads(source.read_text())
    if data.get('ruleset') != 'fixed5_score5_quantity_only_v1' or data.get('policy_id') != 'mccfr_external_v1':
        raise ValueError('wrong policy identity or ruleset')
    table = data['policy']
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending = destination.with_suffix(destination.suffix + '.pending')
    with pending.open('wb') as out:
        out.write(HEADER.pack(b'MCCFR1\0', len(table)))
        for key, weights in sorted(table.items()):
            encoded = key.encode('ascii')
            if len(encoded) > 31 or not weights or len(weights) > 7:
                raise ValueError(f'invalid policy row {key}')
            ids = [action_id(action) for action in weights]
            values = list(weights.values())
            if len(ids) != len(set(ids)) or abs(sum(values) - 1) > 1e-5 or any(v < 0 or v > 1 for v in values):
                raise ValueError(f'invalid distribution {key}')
            out.write(RECORD.pack(encoded, len(ids), *(ids + [0] * (7 - len(ids))), *(values + [0.0] * (7 - len(values)))))
    pending.replace(destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    print(json.dumps({'source': str(source), 'path': str(destination), 'rows': len(table), 'bytes': destination.stat().st_size, 'sha256': digest}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    pack(args.source, args.destination)
