"""Fetch the separately hosted ReBeL source and install its local runtime."""
import hashlib
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".cache" / "rebel-source"
VENV = ROOT / ".cache" / "rebel-venv"
REMOTE = "https://github.com/shivangijod-creator/ReBeL-Liars-Dice.git"
COMMIT = "1d915cc2dcecf9670aaec652ab78bf528241ce21"
CHECKPOINT_SHA256 = "028b9708fe60848cd409fde581bee1e92e20aa67b7cbd65c475e7bf0149f2f3a"


def run(*args):
    subprocess.run(args, check=True)


def main():
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    if not SOURCE.exists():
        run("git", "clone", "--filter=blob:none", "--no-checkout", REMOTE, str(SOURCE))
        run("git", "-C", str(SOURCE), "fetch", "--depth", "1", "origin", COMMIT)
        run("git", "-C", str(SOURCE), "checkout", "--detach", COMMIT)
    actual = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip()
    if actual != COMMIT:
        raise SystemExit(f"ReBeL source commit mismatch: expected {COMMIT}, got {actual}")
    checkpoint = SOURCE / "checkpoints" / "rebel_5x6f_epoch_6.pt"
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != CHECKPOINT_SHA256:
        raise SystemExit("ReBeL checkpoint checksum mismatch")
    if not VENV.exists():
        venv.create(VENV, with_pip=True)
    python = VENV / "bin" / "python"
    run(str(python), "-m", "pip", "install", "--no-cache-dir", "numpy==2.5.4", "torch==2.15.0")
    run(str(python), "-c", "import torch,numpy; print('ReBeL runtime ready:',torch.__version__,numpy.__version__)")


if __name__ == "__main__":
    main()
