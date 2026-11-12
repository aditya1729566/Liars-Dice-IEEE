import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from server import app


class RebelApiTests(unittest.TestCase):
    def test_client_cannot_act_for_rebel_seat(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, "DB", Path(folder) / "test.sqlite3"):
            state = None
            for seed in range(100):
                candidate = app.engine({"op": "new", "n": 5, "agent": "rebel_transfer_v1",
                                        "seed": seed, "auto_ai": False})["state"]
                if candidate["turn"] == 1:
                    state = candidate
                    break
            self.assertIsNotNone(state)
            with app.connection() as con:
                con.execute("INSERT INTO matches VALUES (?,?,?)",
                            ("rebel-test", json.dumps(state), time.time()))
            server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                payload = {"expected_version": state["version"],
                           "idempotency_key": "cannot-play-for-rebel",
                           "action": {"type": "bid", "q": 1, "f": 1}}
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/api/matches/rebel-test/actions",
                    data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(request, timeout=5)
                self.assertEqual(denied.exception.code, 400)
                with app.connection() as con:
                    self.assertEqual(app.read_match(con, "rebel-test")["version"], state["version"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()
