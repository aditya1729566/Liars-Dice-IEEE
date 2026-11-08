import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from server import app

class HttpTests(unittest.TestCase):
    def test_create_action_replay_and_duplicate(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app,'DB',Path(folder)/'test.sqlite3'):
            server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{server.server_port}'
            def send(path,data=None,method=None):
                body=None if data is None else json.dumps(data).encode()
                req=urllib.request.Request(base+path,data=body,headers={'Content-Type':'application/json'},method=method)
                with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)
            try:
                self.assertTrue(send('/api/health')['policy_ok'])
                listed=send('/api/agents')['agents']
                self.assertEqual({x['id'] for x in listed},{'random','probability','aggressive','cfr2','adaptive'})
                self.assertTrue(all(x['available'] for x in listed))
                self.assertFalse(next(x for x in listed if x['id']=='adaptive')['trained'])
                self.assertTrue(next(x for x in listed if x['id']=='adaptive')['uses_trained_base'])
                denied=urllib.request.Request(base+'/api/matches',method='OPTIONS',headers={'Origin':'https://untrusted.example'})
                with self.assertRaises(urllib.error.HTTPError) as cors:
                    urllib.request.urlopen(denied,timeout=5)
                self.assertEqual(cors.exception.code,403)
                with patch.object(app,'trained_policy_ok',return_value=False):
                    with self.assertRaises(urllib.error.HTTPError) as mismatched:
                        send('/api/matches',{'n':5,'agent':'cfr2'})
                    self.assertEqual(mismatched.exception.code,400)
                trained=send('/api/matches',{'n':5,'agent':'cfr2'})
                self.assertEqual(trained['agent'],'cfr2')
                self.assertIsNone(trained['ai_hand'])
                self.assertNotIn('ai_decisions',trained)
                with self.assertRaises(urllib.error.HTTPError) as private_report:
                    send(f"/api/matches/{trained['id']}/research")
                self.assertEqual(private_report.exception.code,409)
                for action_index in range(30):
                    if trained['status']=='COMPLETED':break
                    if trained['phase']=='ROUND_OVER':
                        trained=send(f"/api/matches/{trained['id']}/next-round",{'expected_version':trained['version'],'idempotency_key':f'research-next-{action_index:03d}'})
                    else:
                        action={'type':'call'} if any(a['type']=='call' for a in trained['legal_actions']) else {'type':'bid','q':10,'f':1}
                        trained=send(f"/api/matches/{trained['id']}/actions",{'action':action,'expected_version':trained['version'],'idempotency_key':f'research-act-{action_index:03d}'})
                self.assertEqual(trained['status'],'COMPLETED')
                report=send(f"/api/matches/{trained['id']}/research")
                self.assertEqual(report['scores'],trained['scores'])
                self.assertTrue(report['decisions'])
                self.assertEqual(len(report['replay']),len(trained['events'])+trained['round'])
                self.assertEqual(sum(frame['kind']=='call' for frame in report['replay']),trained['round'])
                self.assertEqual(sum(frame['kind']=='reveal' for frame in report['replay']),trained['round'])
                revealed={event['round']:event['hands'] for event in report['reveals']}
                self.assertTrue(all(frame['hands']==revealed[frame['round']] for frame in report['replay']))
                self.assertTrue(all(0<=d['current_bid_truth_prior']<=1 for d in report['decisions'] if d['current_bid_truth_prior'] is not None))
                self.assertTrue(all(0<=d['action_truth_prior']<=1 for d in report['decisions'] if d['action_truth_prior'] is not None))
                self.assertEqual(len(report['reveals']),trained['round'])
                self.assertTrue(send(f"/api/matches/{trained['id']}",method='DELETE')['deleted'])
                with self.assertRaises(urllib.error.HTTPError) as deleted_report:
                    send(f"/api/matches/{trained['id']}/research")
                self.assertEqual(deleted_report.exception.code,404)
                created=send('/api/matches',{'n':5,'agent':'probability'})
                self.assertNotIn('rng',created)
                self.assertNotIn('hands',created)
                self.assertFalse(any('hands' in event for event in created['events']))
                id=created['id'];payload={'action':next(a for a in created['legal_actions'] if a['type']=='bid'),'expected_version':created['version'],'idempotency_key':'test-unique-001'}
                first=send(f'/api/matches/{id}/actions',payload)
                again=send(f'/api/matches/{id}/actions',payload)
                self.assertEqual(first,again)
                self.assertEqual(send(f'/api/matches/{id}')['version'],first['version'])
                with self.assertRaises(urllib.error.HTTPError) as bad:
                    send(f'/api/matches/{id}/actions',{**payload,'idempotency_key':'test-unique-002'})
                self.assertEqual(bad.exception.code,409)
                force=send('/api/matches',{'n':5,'agent':'probability'})
                illegal={'type':'bid','q':force['bid']['q'],'f':6} if force['bid'] else {'type':'bid','q':0,'f':6}
                with self.assertRaises(urllib.error.HTTPError) as invalid:
                    send(f"/api/matches/{force['id']}/actions",{'action':illegal,'expected_version':force['version'],'idempotency_key':'invalid-quantity'})
                self.assertEqual(invalid.exception.code,400)
                malformed=urllib.request.Request(base+f"/api/matches/{force['id']}/actions",data=b'{',headers={'Content-Type':'application/json'})
                with self.assertRaises(urllib.error.HTTPError) as broken:
                    urllib.request.urlopen(malformed,timeout=5)
                self.assertEqual(broken.exception.code,400)
                self.assertEqual(send(f"/api/matches/{force['id']}")['version'],force['version'])
                with app.connection() as con:
                    self.assertEqual(con.execute('SELECT COUNT(*) FROM invalid_actions WHERE match_id=?',(force['id'],)).fetchone()[0],2)
                forced_action={'type':'call'} if any(a['type']=='call' for a in force['legal_actions']) else {'type':'bid','q':10,'f':1}
                ended=send(f"/api/matches/{force['id']}/actions",{'action':forced_action,'expected_version':force['version'],'idempotency_key':'force-round-end'})
                self.assertEqual(ended['phase'],'ROUND_OVER')
                self.assertEqual(sum(ended['scores']),1)
                self.assertEqual(ended['counts'],[5,5])
                self.assertEqual(len(ended['ai_hand']),5)
                nxt={'expected_version':ended['version'],'idempotency_key':'next-round-once'}
                advanced=send(f"/api/matches/{force['id']}/next-round",nxt)
                self.assertEqual(advanced['round'],2)
                self.assertEqual(advanced['phase'],'BIDDING')
                self.assertEqual(advanced['scores'],ended['scores'])
                self.assertIsNone(advanced['ai_hand'])
                self.assertEqual(advanced,send(f"/api/matches/{force['id']}/next-round",nxt))
                self.assertTrue(send(f'/api/matches/{id}',method='DELETE')['deleted'])
                with self.assertRaises(urllib.error.HTTPError) as missing:
                    send(f'/api/matches/{id}')
                self.assertEqual(missing.exception.code,404)
                self.assertTrue(send(f"/api/matches/{force['id']}",method='DELETE')['deleted'])
                with app.connection() as con:
                    self.assertEqual(con.execute('SELECT COUNT(*) FROM invalid_actions WHERE match_id=?',(force['id'],)).fetchone()[0],0)
            finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main()
