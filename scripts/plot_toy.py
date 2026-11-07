"""Plot measured one-die toy NashConv against exact CFR iteration count."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POINTS = (10, 50, 100, 200, 500, 1000, 2000)


def main():
    rows = []
    for n in POINTS:
        run = f'quantity_n1_curve_{n}' if n != 2000 else 'quantity_n1_exact_2000_v3'
        summary = json.loads((ROOT / 'experiments' / 'runs' / run / 'summary.json').read_text())
        rows.append({'iterations': n, 'nashconv': summary['nashconv'], 'run_id': run})
    (ROOT / 'docs' / 'quantity-n1-curve.json').write_text(json.dumps(rows, indent=2))
    width, height = 760, 400
    xmin, xmax = math.log10(10), math.log10(2000)
    ymin, ymax = math.log10(.001), math.log10(.5)
    xy = [(70 + 630 * (math.log10(row['iterations']) - xmin) / (xmax - xmin),
           335 - 270 * (math.log10(row['nashconv']) - ymin) / (ymax - ymin)) for row in rows]
    polyline = ' '.join(f'{x:.1f},{y:.1f}' for x, y in xy)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="#101719"/>',
             '<text x="34" y="32" fill="#e8e3d7" font-family="monospace" font-size="17">Quantity-only one-die toy · exact NashConv</text>',
             '<text x="34" y="53" fill="#9ba7a6" font-family="monospace" font-size="11">36 deals · full-history CFR · exact information-respecting best response</text>',
             '<line x1="70" y1="65" x2="70" y2="335" stroke="#71847e"/>',
             '<line x1="70" y1="335" x2="700" y2="335" stroke="#71847e"/>',
             f'<polyline fill="none" stroke="#e7a15f" stroke-width="3" points="{polyline}"/>']
    for row, (x, y) in zip(rows, xy):
        parts += [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#e7a15f"/>',
                  f'<text x="{x:.1f}" y="{y-11:.1f}" text-anchor="middle" fill="#e8e3d7" font-family="monospace" font-size="10">{row["nashconv"]:.4f}</text>',
                  f'<text x="{x:.1f}" y="354" text-anchor="middle" fill="#9ba7a6" font-family="monospace" font-size="10">{row["iterations"]}</text>']
    parts.append('<text x="530" y="382" fill="#9ba7a6" font-family="monospace" font-size="10">CFR iterations (log scale)</text>')
    parts.append('</svg>')
    (ROOT / 'docs' / 'plots' / 'quantity-n1-convergence.svg').write_text('\n'.join(parts))


if __name__ == '__main__':
    main()
