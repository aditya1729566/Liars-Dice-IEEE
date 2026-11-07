"""Local HTTP adapter. Rules and AI choices are delegated to the C++ engine."""
import json
import os
import secrets
import sqlite3
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "build" / "bluff_engine"
DB = ROOT / "data" / "matches.sqlite3"
LOCK = threading.RLock()
RULESET = "fixed5_score5_quantity_only_v1"
AGENTS = {"random", "probability", "aggressive"}
ALLOWED_ORIGINS = {"http://localhost:3000", "http://127.0.0.1:3000"}


def engine(command):
    result = subprocess.run([str(ENGINE)], input=json.dumps(command), text=True,
                            capture_output=True, timeout=5, check=False)
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(result.stderr or "engine returned invalid JSON") from exc
    if result.returncode or "error" in value:
        raise ValueError(value.get("error", result.stderr or "engine failed"))
    return value


def connection():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS matches (id TEXT PRIMARY KEY, state TEXT NOT NULL, created REAL NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS requests (match_id TEXT NOT NULL, key TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(match_id,key))")
    con.execute("CREATE TABLE IF NOT EXISTS invalid_actions (match_id TEXT, key TEXT, submitted_json TEXT, reason TEXT, created REAL)")
    con.commit()
    return con


def read_match(con, match_id):
    row = con.execute("SELECT state FROM matches WHERE id=?", (match_id,)).fetchone()
    if not row:
        raise LookupError("match not found")
    state = json.loads(row["state"])
    if state.get("ruleset") != RULESET:
        raise LookupError("legacy match uses an obsolete ruleset")
    return state


def match_response(con, match_id, view):
    row = con.execute("SELECT created FROM matches WHERE id=?", (match_id,)).fetchone()
    return {"id": match_id, "duration_seconds": max(0, int(time.time() - row["created"])), **view}


class Handler(BaseHTTPRequestHandler):
    server_version = "BLUFF.EXE/0.1"

    def send_json(self, code, value):
        body = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        if self.headers.get("Origin", "") not in ALLOWED_ORIGINS:
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.end_headers()

    def body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 16384:
            raise ValueError("request too large")
        raw = self.rfile.read(length) or b"{}"
        self._request_payload = raw.decode("utf-8", errors="replace")
        return json.loads(raw)

    def audit_invalid(self, reason):
        bits = [b for b in urlsplit(self.path).path.split("/") if b]
        if len(bits) == 4 and bits[:2] == ["api", "matches"] and bits[3] in {"actions", "next-round"}:
            try:
                payload = getattr(self, "_request_payload", "")
                try:
                    key = str(json.loads(payload).get("idempotency_key", ""))
                except (ValueError, AttributeError):
                    key = ""
                with connection() as con:
                    con.execute("INSERT INTO invalid_actions VALUES (?,?,?,?,?)", (bits[2], key, payload, str(reason), time.time()))
            except Exception:
                pass

    def dispatch(self, method):
        path = urlsplit(self.path).path
        bits = [b for b in path.split("/") if b]
        if bits[:1] != ["api"]:
            raise LookupError("endpoint not found")
        if method == "GET" and bits == ["api", "health"]:
            return {"ok": ENGINE.exists(), "engine": str(ENGINE.name), "ruleset": RULESET}
        if method == "GET" and bits == ["api", "rules"]:
            return {"version": RULESET, "faces": 6, "wild": False, "dice_per_player": 5, "target_score": 5, "bid_order": "quantity only", "next_starter": "round loser"}
        if method == "GET" and bits == ["api", "agents"]:
            return {"agents": [{"id": a, "policy_version": "fixed5_heuristic_v1", "trained": False} for a in sorted(AGENTS)]}
        if method == "POST" and bits == ["api", "matches"]:
            request = self.body()
            n, agent = request.get("n", 5), request.get("agent", "probability")
            if n != 5 or agent not in AGENTS:
                raise ValueError("this game requires five dice and a supported agent")
            result = engine({"op": "new", "n": 5, "agent": agent})
            match_id = secrets.token_urlsafe(18)
            with LOCK, connection() as con:
                con.execute("INSERT INTO matches VALUES (?,?,?)", (match_id, json.dumps(result["state"]), time.time()))
            return {"id": match_id, "duration_seconds": 0, **result["view"]}
        if method == "GET" and bits == ["api", "leaderboard"]:
            with connection() as con:
                states = [json.loads(x[0]) for x in con.execute("SELECT state FROM matches")]
            completed = [s for s in states if s.get("ruleset") == RULESET and s.get("status") == "COMPLETED"]
            return {"completed_matches": len(completed), "human_wins": sum(s.get("winner") == "HUMAN" for s in completed), "ai_wins": sum(s.get("winner") == "AI" for s in completed)}
        if method == "GET" and bits == ["api", "research", "summary"]:
            runs = []
            for path in sorted((ROOT / "experiments" / "runs").glob("*/summary.json")):
                manifest = path.parent / "manifest.json"
                if manifest.exists() and json.loads(manifest.read_text()).get("status") == "completed" and json.loads(manifest.read_text()).get("ruleset") == RULESET:
                    item = json.loads(path.read_text())
                    if "results" in item:
                        runs.append(item)
            return {"status": "completed" if runs else "no completed evaluation", "runs": runs}
        if len(bits) >= 3 and bits[:2] == ["api", "matches"]:
            match_id = bits[2]
            if method == "DELETE" and len(bits) == 3:
                with LOCK, connection() as con:
                    read_match(con, match_id)
                    con.execute("DELETE FROM requests WHERE match_id=?", (match_id,))
                    con.execute("DELETE FROM matches WHERE id=?", (match_id,))
                return {"deleted": True}
            if method == "GET":
                with connection() as con:
                    s = read_match(con, match_id)
                v = engine({"op": "view", "state": s})["view"]
                if len(bits) == 3:
                    with connection() as con:
                        return match_response(con, match_id, v)
                if bits[3:] == ["events"]:
                    return {"events": v["events"]}
                if len(bits) == 5 and bits[3] == "analysis":
                    round_index = int(bits[4])
                    reveals = [e for e in v["events"] if e["type"] == "reveal" and e["round"] == round_index]
                    if not reveals:
                        raise LookupError("round not revealed")
                    r = reveals[-1]
                    prior = engine({"op": "prior", "q": r["bid"]["q"], "f": r["bid"]["f"], "hand": r["hands"][1], "unknown": len(r["hands"][0])})["probability"]
                    return {"round": round_index, "bid": r["bid"], "actual": r["actual"], "true": r["true"], "loser": r["loser"], "naive_prior_from_ai_hand": prior, "policy": s["agent"], "note": "Prior before strategic bid evidence; no posterior or action propensity is claimed."}
            if method == "POST" and bits[3:] in (["actions"], ["next-round"]):
                body = self.body()
                key = str(body.get("idempotency_key", ""))
                with LOCK, connection() as con:
                    cached = con.execute("SELECT response FROM requests WHERE match_id=? AND key=?", (match_id, key)).fetchone()
                    if cached:
                        return json.loads(cached["response"])
                    if not 8 <= len(key) <= 128:
                        raise ValueError("idempotency_key must be 8–128 characters")
                    s = read_match(con, match_id)
                    if body.get("expected_version") != s["version"]:
                        raise RuntimeError("stale match version")
                    command = {"op": "act", "state": s, "action": body.get("action", {})} if bits[3:] == ["actions"] else {"op": "next_round", "state": s}
                    result = engine(command)
                    response = match_response(con, match_id, result["view"])
                    con.execute("UPDATE matches SET state=? WHERE id=?", (json.dumps(result["state"]), match_id))
                    con.execute("INSERT INTO requests VALUES (?,?,?)", (match_id, key, json.dumps(response)))
                    return response
        raise LookupError("endpoint not found")

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def do_DELETE(self):
        self.handle_request("DELETE")

    def handle_request(self, method):
        try:
            origin = self.headers.get("Origin")
            if origin and origin not in ALLOWED_ORIGINS:
                self.send_json(403, {"error": "origin not allowed"})
                return
            self.send_json(200 if method in {"GET", "DELETE"} else 201, self.dispatch(method))
        except LookupError as exc:
            self.audit_invalid(exc)
            self.send_json(404, {"error": str(exc)})
        except RuntimeError as exc:
            self.audit_invalid(exc)
            self.send_json(409, {"error": str(exc)})
        except (ValueError, KeyError, TypeError) as exc:
            self.audit_invalid(exc)
            self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})


if __name__ == "__main__":
    if not ENGINE.exists():
        raise SystemExit("Build engine first: make build-engine")
    server = ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("BLUFF_PORT", "8787"))), Handler)
    print("BLUFF.EXE API on http://127.0.0.1:8787", flush=True)
    server.serve_forever()
