"""Export only completed immutable evaluation runs from their SQLite records."""
import csv
import json
import sqlite3
from html import escape
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for db in (ROOT/'experiments'/'runs').glob('*/evaluation.sqlite3'):
    folder=db.parent
    manifest=folder/'manifest.json'
    if not manifest.exists() or json.loads(manifest.read_text()).get('status')!='completed' or json.loads(manifest.read_text()).get('ruleset')!='fixed5_score5_quantity_only_v1':
        continue
    with sqlite3.connect(db) as con:
        for table in ('matches','rounds'):
            out=folder/f'{table}.csv'
            with out.open('w',newline='') as f:
                cur=con.execute(f'SELECT * FROM {table}')
                writer=csv.writer(f);writer.writerow([x[0] for x in cur.description]);writer.writerows(cur)
        with (folder/'decisions.jsonl').open('w') as f:
            cur=con.execute('SELECT match_id,action_index,round_index,player,agent,observation_json,action_json,latency_ms FROM decisions')
            for match_id,index,round_index,player,agent,obs,action,latency in cur:
                f.write(json.dumps({'match_id':match_id,'action_index':index,'round':round_index,'player':player,'agent':agent,'observation':json.loads(obs),'action':json.loads(action),'latency_ms':latency},separators=(',',':'))+'\n')
    summary=json.loads((folder/'summary.json').read_text())
    rows=list(summary['results'].items())
    width,height=900,80+34*len(rows)
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',f'<rect width="{width}" height="{height}" fill="#101719"/>',f'<text x="24" y="34" fill="#e8e3d7" font-family="monospace" font-size="17">{escape(summary["run_id"])} · {summary["n"]} dice · {summary["completed_matches"]} matches</text>']
    for i,(name,result) in enumerate(rows):
        y=70+34*i;rate=result['win_rate'];bar=round(350*rate)
        parts.extend([f'<text x="24" y="{y}" fill="#bdc7c2" font-family="monospace" font-size="10">{escape(name)}</text>',f'<rect x="470" y="{y-11}" width="350" height="12" fill="#2b3836"/>',f'<rect x="470" y="{y-11}" width="{bar}" height="12" fill="#e7a15f"/>',f'<text x="833" y="{y}" fill="#e8e3d7" font-family="monospace" font-size="11">{rate*100:.1f}%</text>'])
    parts.append('</svg>')
    (folder/'win_rates.svg').write_text('\n'.join(parts))
    print(folder)
