"""Local worker for the updated, BLUFF.EXE-specific ReBeL checkpoint."""
import hashlib
import json
import os
import secrets
import select
import subprocess
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".cache" / "rebel-venv" / "bin" / "python"
SOURCE = ROOT / ".cache" / "rebel-source-v2"
CHECKPOINT = SOURCE / "checkpoints" / "bluff_exe_v1" / "rebel_bluff_epoch_5.pt"
CHECKPOINT_SHA256 = "6c629db416e337bbce06e07375238b62fa3e414b8d36ae01b90635175fdbbc77"
SOURCE_COMMIT = "05607c7a208189ac6b0149337f45d46ad3828894"
LOCK = threading.RLock()
WORKER = None
SEEDS = {}


def available():
    try:
        return (PYTHON.is_file() and CHECKPOINT.is_file() and
                hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest() == CHECKPOINT_SHA256 and
                subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"],
                                        text=True, stderr=subprocess.DEVNULL).strip() == SOURCE_COMMIT)
    except (OSError, subprocess.SubprocessError):
        return False


def command(value):
    global WORKER
    with LOCK:
        if not available():
            raise RuntimeError("updated ReBeL runtime unavailable; run make setup-rebel-v2")
        if WORKER is None or WORKER.poll() is not None:
            env = dict(os.environ, BLUFF_REBEL_SOURCE_V2=str(SOURCE))
            WORKER = subprocess.Popen([str(PYTHON), str(ROOT / "server" / "rebel_worker_v2.py")],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, text=True, bufsize=1, env=env)
        WORKER.stdin.write(json.dumps(value, separators=(",", ":")) + "\n")
        WORKER.stdin.flush()
        if not select.select([WORKER.stdout], [], [], 30)[0]:
            raise RuntimeError("updated ReBeL inference timed out")
        line = WORKER.stdout.readline()
        if not line:
            raise RuntimeError("updated ReBeL worker exited")
        result = json.loads(line)
        if "error" in result:
            raise RuntimeError(result["error"])
        return result


def choose(match_id, state):
    from sys import path
    scripts = str(ROOT / "scripts")
    if scripts not in path:
        path.insert(0, scripts)
    from rebel_v2_bridge import private_observation
    with LOCK:
        seed = SEEDS.setdefault(match_id, secrets.randbits(64))
        return command({"match_id": match_id, "seed": seed,
                        "observation": private_observation(state)})


def drop(match_id):
    with LOCK:
        SEEDS.pop(match_id, None)
        if WORKER is not None and WORKER.poll() is None:
            command({"op": "drop", "match_id": match_id})
