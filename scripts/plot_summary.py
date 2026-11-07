"""Render a compact measured win-rate chart from a completed summary JSON."""
import argparse
import json
from html import escape
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('summary', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--note', default='')
    args = parser.parse_args()
    data = json.loads(args.summary.read_text())
    rows = list(data['results'].items())
    width, height = 940, 76 + 30 * len(rows) + (24 if args.note else 0)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           f'<rect width="{width}" height="{height}" fill="#101719"/>',
           f'<text x="22" y="34" fill="#e8e3d7" font-family="monospace" font-size="16">{escape(data["run_id"])} · {data["completed_matches"]} matches</text>']
    for index, (label, result) in enumerate(rows):
        y = 64 + 30 * index
        rate = result['win_rate']
        low, high = result['wilson95']
        svg += [f'<text x="22" y="{y}" fill="#bdc7c2" font-family="monospace" font-size="10">{escape(label)}</text>',
                f'<rect x="500" y="{y-10}" width="320" height="11" fill="#2b3836"/>',
                f'<rect x="500" y="{y-10}" width="{round(320*rate)}" height="11" fill="#e7a15f"/>',
                f'<text x="830" y="{y}" fill="#e8e3d7" font-family="monospace" font-size="10">{rate*100:.1f}%</text>',
                f'<title>{escape(label)}: {result["wins"]}/{result["matches"]}; 95% Wilson [{low*100:.1f}%, {high*100:.1f}%]</title>']
    if args.note:
        svg.append(f'<text x="22" y="{height-17}" fill="#e7a15f" font-family="monospace" font-size="10">{escape(args.note)}</text>')
    svg.append('</svg>')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text('\n'.join(svg))


if __name__ == '__main__':
    main()
