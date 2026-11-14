"""Fetch the updated BLUFF.EXE-specific ReBeL source and checkpoint."""
import hashlib
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".cache" / "rebel-source-v2"
VENV = ROOT / ".cache" / "rebel-venv"
REMOTE = "https://github.com/shivangijod-creator/ReBeL-Liars-Dice.git"
COMMIT = "05607c7a208189ac6b0149337f45d46ad3828894"
CHECKPOINT_SHA256 = "6c629db416e337bbce06e07375238b62fa3e414b8d36ae01b90635175fdbbc77"


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
        raise SystemExit(f"updated ReBeL source commit mismatch: expected {COMMIT}, got {actual}")
    checkpoint = SOURCE / "checkpoints" / "bluff_exe_v1" / "rebel_bluff_epoch_5.pt"
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != CHECKPOINT_SHA256:
        raise SystemExit("updated ReBeL checkpoint checksum mismatch")
    if not VENV.exists():
        venv.create(VENV, with_pip=True)
        run(str(VENV / "bin" / "python"), "-m", "pip", "install", "--no-cache-dir", "numpy==2.5.4", "torch==2.15.0")
    run(str(VENV / "bin" / "python"), "-m", "unittest", "discover", "-s", str(ROOT / "scripts"),
        "-p", "test_rebel_v2_bridge.py", "-v")


if __name__ == "__main__":
    main()
