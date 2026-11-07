import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from server import app
class ApiTests(unittest.TestCase):
    def test_store_redacted_current_match(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(app,'DB',Path(folder)/'test.sqlite3'):
            created=app.engine({'op':'new','n':5,'agent':'random','seed':123})
            with app.connection() as con:
                con.execute('INSERT INTO matches VALUES (?,?,?)',('m',json.dumps(created['state']),0))
                state=app.read_match(con,'m')
                self.assertEqual(state['ruleset'],app.RULESET)
                self.assertEqual(state['counts'],[5,5])
                self.assertNotIn('rng',created['view'])
                self.assertIsNone(created['view']['ai_hand'])
if __name__=='__main__':unittest.main()
