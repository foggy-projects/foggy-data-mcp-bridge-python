#!/usr/bin/env python3
"""
check-model-drift.py — Verify Odoo model directory matches models.lock.json.

Usage:
  python scripts/check-model-drift.py [--model-dir <dir>] [--lock-file <path>]

Exit codes:
  0  models match lock file
  1  mismatch (drift detected) or missing lock/model files

Algorithm:
  Computes a content-level checksum (sorted relative POSIX paths + per-file
  sha256, then sha256 of the combined output) and compares with
  content_checksum in models.lock.json.

  This is identical to the algorithm in pull-odoo-models.py and aligned with
  the Java side's check-model-drift.sh.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_MODEL_DIR = PROJECT_ROOT / "src" / "foggy" / "demo" / "models" / "odoo"


def compute_content_checksum(model_dir: Path) -> str:
    """
    Deterministic content-level checksum — must match pull-odoo-models.py.

    1. List all files (excluding GENERATED.md and models.lock.json)
    2. Sort by relative POSIX path
    3. Per-file sha256
    4. Hash the combined output
    """
    rel_hashes: list[str] = []
    for fpath in sorted(model_dir.rglob("*")):
        if not fpath.is_file():
            continue
        if fpath.name in ("GENERATED.md", "models.lock.json"):
            continue
        rel = fpath.relative_to(model_dir).as_posix()
        digest = hashlib.sha256(fpath.read_bytes()).hexdigest()
        rel_hashes.append(f"{digest}  ./{rel}")

    combined = "\n".join(rel_hashes) + "\n" if rel_hashes else ""
    overall = hashlib.sha256(combined.encode()).hexdigest()
    return f"sha256:{overall}"


def main():
    parser = argparse.ArgumentParser(
        description="Verify Odoo model directory matches models.lock.json",
    )
    parser.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR),
                        help=f"Model directory (default: {DEFAULT_MODEL_DIR})")
    parser.add_argument("--lock-file", default=None,
                        help="Lock file path (default: <model-dir>/models.lock.json)")
    args = parser.parse_args()

    model_dir = Path(args.model_dir).resolve()
    lock_file = Path(args.lock_file) if args.lock_file else model_dir / "models.lock.json"

    # Pre-flight
    if not lock_file.is_file():
        print(f"FAIL: Lock file not found: {lock_file}", file=sys.stderr)
        print("  Run scripts/pull-odoo-models.py first.", file=sys.stderr)
        sys.exit(1)

    if not model_dir.is_dir():
        print(f"FAIL: Model directory not found: {model_dir}", file=sys.stderr)
        sys.exit(1)

    # Read lock
    lock = json.loads(lock_file.read_text(encoding="utf-8"))
    pkg = lock.get("package", "?")
    ver = lock.get("version", "?")
    lock_cc = lock.get("content_checksum", "")

    if not lock_cc:
        print("FAIL: Lock file has no content_checksum field.", file=sys.stderr)
        print("  Re-run scripts/pull-odoo-models.py to regenerate.", file=sys.stderr)
        sys.exit(1)

    print(f"Package:               {pkg}@{ver}")
    print(f"Lock content_checksum: {lock_cc}")

    # Compute actual
    actual_cc = compute_content_checksum(model_dir)
    print(f"Dir  content_checksum: {actual_cc}")

    # Compare
    if lock_cc == actual_cc:
        print()
        print("OK: Model directory matches lock file.")
        sys.exit(0)
    else:
        print(file=sys.stderr)
        print("FAIL: Model drift detected!", file=sys.stderr)
        print(f"  Lock expects: {lock_cc}", file=sys.stderr)
        print(f"  Directory is: {actual_cc}", file=sys.stderr)
        print(file=sys.stderr)
        print("  Either the model files were manually modified, or the lock file is stale.", file=sys.stderr)
        print("  Run scripts/pull-odoo-models.py to re-sync from registry.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
