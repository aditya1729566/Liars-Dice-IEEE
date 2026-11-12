"""Local PyTorch ReBeL process used only when its pinned dependency is installed."""
import hashlib
import json
import os
import select
import subprocess
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".cache" / "rebel-venv" / "bin" / "python"
SOURCE = ROOT / ".cache" / "rebel-source"
CHECKPOINT = SOURCE / "checkpoints" / "rebel_5x6f_epoch_6.pt"
CHECKPOINT_SHA256 = "028b9708fe60848cd409fde581bee1e92e20aa67b7cbd65c475e7bf0149f2f3a"
SOURCE_COMMIT = "1d915cc2dcecf9670aaec652ab78bf528241ce21"
LOCK = threading.RLock()
WORKER = None


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
            raise RuntimeError("ReBeL runtime unavailable; run make setup-rebel")
        if WORKER is None or WORKER.poll() is not None:
            env = dict(os.environ, BLUFF_REBEL_SOURCE=str(SOURCE))
            WORKER = subprocess.Popen([str(PYTHON), str(ROOT / "server" / "rebel_worker.py")],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, text=True, bufsize=1, env=env)
        WORKER.stdin.write(json.dumps(value, separators=(",", ":")) + "\n")
        WORKER.stdin.flush()
        if not select.select([WORKER.stdout], [], [], 15)[0]:
            raise RuntimeError("ReBeL inference timed out")
        line = WORKER.stdout.readline()
        if not line:
            raise RuntimeError("ReBeL worker exited")
        result = json.loads(line)
        if "error" in result:
            raise RuntimeError(result["error"])
        return result


def choose(match_id, state):
    from sys import path
    scripts = str(ROOT / "scripts")
    if scripts not in path:
        path.insert(0, scripts)
    from rebel_bridge import private_observation
    return command({"match_id": match_id, "seed": int(state["initial_seed"]),
                    "observation": private_observation(state)})


def drop(match_id):
    if WORKER is not None and WORKER.poll() is None:
        command({"op": "drop", "match_id": match_id})
