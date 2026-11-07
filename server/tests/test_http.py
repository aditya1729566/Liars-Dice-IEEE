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
                denied=urllib.request.Request(base+'/api/matches',method='OPTIONS',headers={'Origin':'https://untrusted.example'})
                with self.assertRaises(urllib.error.HTTPError) as cors:
                    urllib.request.urlopen(denied,timeout=5)
                self.assertEqual(cors.exception.code,403)
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
                self.assertEqual(send(f"/api/matches/{force['id']}")['version'],force['version'])
                with app.connection() as con:
                    self.assertEqual(con.execute('SELECT COUNT(*) FROM invalid_actions WHERE match_id=?',(force['id'],)).fetchone()[0],1)
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
            finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main()
