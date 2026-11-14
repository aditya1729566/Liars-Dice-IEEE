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
    def test_rebel_workers_receive_independent_search_seeds(self):
        state = app.engine({"op": "new", "n": 5, "agent": "rebel_bluff_v2",
                            "seed": 42, "auto_ai": False})["state"]
        for runtime in (app.rebel_runtime, app.rebel_v2_runtime):
            with self.subTest(runtime=runtime.__name__), \
                 patch.object(runtime, "command", return_value={"action": {"type": "bid", "q": 1, "f": 1}}) as command, \
                 patch.object(runtime.secrets, "randbits", return_value=123):
                runtime.SEEDS.clear()
                runtime.choose("seed-isolation-probe", state)
                request = command.call_args.args[0]
                self.assertEqual(request["seed"], 123)
                self.assertNotEqual(request["seed"], state["initial_seed"])
                self.assertNotIn("initial_seed", request["observation"])
                runtime.SEEDS.clear()

    def test_client_cannot_act_for_rebel_seat(self):
        for agent_id in ("rebel_transfer_v1", "rebel_bluff_v2"):
            with self.subTest(agent=agent_id), tempfile.TemporaryDirectory() as folder, patch.object(app, "DB", Path(folder) / "test.sqlite3"):
                state = None
                for seed in range(100):
                    candidate = app.engine({"op": "new", "n": 5, "agent": agent_id,
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
    @unittest.skipUnless(app.rebel_v2_runtime.available(), "updated ReBeL local runtime unavailable")
    def test_updated_rebel_full_http_match_and_replay(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, "DB", Path(folder) / "test.sqlite3"):
            server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            def send(path, payload=None):
                request = urllib.request.Request(base + path,
                    data=json.dumps(payload).encode() if payload is not None else None,
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.load(response)
            try:
                game = send("/api/matches", {"n": 5, "agent": "rebel_bluff_v2"})
                self.assertIsNone(game["ai_hand"])
                self.assertNotIn("ai_decisions", game)
                for step in range(100):
                    if game["status"] == "COMPLETED":
                        break
                    endpoint = "next-round" if game["phase"] == "ROUND_OVER" else "actions"
                    body = {"expected_version": game["version"], "idempotency_key": f"rebel-v2-step-{step:03d}"}
                    if endpoint == "actions":
                        legal = game["legal_actions"]
                        body["action"] = next((a for a in legal if a["type"] == "call"), legal[0])
                    game = send(f"/api/matches/{game['id']}/{endpoint}", body)
                self.assertEqual(game["status"], "COMPLETED")
                report = send(f"/api/matches/{game['id']}/research")
                self.assertEqual(report["agent"], "rebel_bluff_v2")
                self.assertTrue(report["decisions"])
                self.assertTrue(all(d["source"] == "rebel_bluff_depth1_fp32" for d in report["decisions"]))
                self.assertTrue(report["replay"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()
