"""Pack v2 float policy records as bounded, fixed-width 16-bit probabilities."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = struct.Struct('<8sQ')
FLOAT_RECORD = struct.Struct('<16sB24B24f')
PACKED_RECORD = struct.Struct('<16sB24B24H')
TOTAL = 65535


def quantize(weights):
    if not weights or any(not math.isfinite(value) or value < 0 for value in weights):
        raise ValueError('invalid policy weights')
    total = sum(weights)
    if not 0.999 <= total <= 1.001:
        raise ValueError('policy weights are not normalized')
    scaled = [value / total * TOTAL for value in weights]
    units = [math.floor(value) for value in scaled]
    remainder = TOTAL - sum(units)
    for index in sorted(range(len(units)), key=lambda i: (scaled[i] - units[i], -i), reverse=True)[:remainder]:
        units[index] += 1
    if sum(units) != TOTAL:
        raise AssertionError('quantization total changed')
    return units


def pack(source, destination):
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending = destination.with_suffix(destination.suffix + '.pending')
    with source.open('rb') as inp, pending.open('wb') as out:
        raw_header = inp.read(HEADER.size)
        if len(raw_header) != HEADER.size:
            raise ValueError('short policy header')
        magic, count = HEADER.unpack(raw_header)
        if magic != b'MCCFR2\0\0' or source.stat().st_size != HEADER.size + count * FLOAT_RECORD.size:
            raise ValueError('invalid source policy')
        out.write(HEADER.pack(b'MCCFR2Q\0', count))
        previous = None
        for _ in range(count):
            row = inp.read(FLOAT_RECORD.size)
            if len(row) != FLOAT_RECORD.size:
                raise ValueError('truncated policy record')
            unpacked = FLOAT_RECORD.unpack(row)
            digest, n = unpacked[:2]
            ids = unpacked[2:26]
            weights = unpacked[26:]
            if not 1 <= n <= 24 or previous is not None and digest <= previous:
                raise ValueError('unsorted or malformed policy')
            previous = digest
            quantized = quantize(weights[:n])
            out.write(PACKED_RECORD.pack(digest, n, *ids, *(quantized + [0] * (24 - n))))
        if inp.read(1):
            raise ValueError('trailing source bytes')
    pending.replace(destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    print(json.dumps({'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                      'policy': str(destination), 'records': count,
                      'bytes': destination.stat().st_size, 'sha256': digest}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    pack(args.source, args.destination)
