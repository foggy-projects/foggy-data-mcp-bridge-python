#!/usr/bin/env python3
"""
pull-odoo-models.py — Pull Odoo TM/QM models from foggy-model-registry.

Usage:
  python scripts/pull-odoo-models.py [OPTIONS]

Options:
  --registry <path|url>   Registry data path or HTTP URL (default: ../foggy-model-registry/data)
  --channel  <name>       Channel: stable | beta (default: stable)
  --edition  <name>       Edition: community | pro (default: community)
  --package  <name>       Package name (default: foggy.odoo.<edition>)
  --key      <value>      Bearer key (required for pro edition)
  --output   <dir>        Output directory (default: src/foggy/demo/models/odoo/)
  --dry-run               Show what would change without writing files

Requires: Python 3.10+
"""

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "src" / "foggy" / "demo" / "models" / "odoo"
DEFAULT_REGISTRY = str(PROJECT_ROOT.parent / "foggy-model-registry" / "data")

GENERATED_MARKER = """\
本目录由 foggy-model-registry 同步生成，禁止手工修改。
使用 scripts/pull-odoo-models.py 更新。
"""


# ---------------------------------------------------------------------------
# Network / file helpers
# ---------------------------------------------------------------------------

def is_http(registry: str) -> bool:
    return registry.startswith("http://") or registry.startswith("https://")


def read_local(path: Path) -> bytes:
    if not path.is_file():
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path.read_bytes()


def read_http(url: str, key: str | None = None) -> bytes:
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = Request(url, headers=headers)
    try:
        with urlopen(req) as resp:
            return resp.read()
    except HTTPError as e:
        if e.code == 401:
            print("ERROR: Unauthorized (401). A valid key is required.", file=sys.stderr)
        elif e.code == 403:
            print("ERROR: Forbidden (403). The provided key is not valid.", file=sys.stderr)
        else:
            print(f"ERROR: HTTP {e.code} fetching {url}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"ERROR: Cannot connect to {url}: {e.reason}", file=sys.stderr)
        sys.exit(1)


def fetch(registry: str, *parts: str, key: str | None = None) -> bytes:
    """Fetch a resource from the registry (local or HTTP)."""
    if is_http(registry):
        url = "/".join([registry.rstrip("/")] + list(parts))
        return read_http(url, key)
    else:
        path = Path(registry)
        for p in parts:
            path = path / p
        return read_local(path)


# ---------------------------------------------------------------------------
# Registry protocol
# ---------------------------------------------------------------------------

def resolve_channel(registry: str, edition: str, package: str, channel: str,
                    key: str | None = None) -> str:
    data = fetch(registry, edition, package, f"{channel}.json", key=key)
    info = json.loads(data)
    version = info.get("version")
    if not version:
        print(f"ERROR: Channel '{channel}' has no version field", file=sys.stderr)
        sys.exit(1)
    return version


def read_manifest(registry: str, edition: str, package: str, version: str,
                  key: str | None = None) -> dict:
    data = fetch(registry, edition, package, version, "manifest.json", key=key)
    return json.loads(data)


def download_bundle(registry: str, edition: str, package: str, version: str,
                    key: str | None = None) -> bytes:
    return fetch(registry, edition, package, version, "bundle.tar.gz", key=key)


def verify_checksum(data: bytes, expected: str) -> bool:
    if not expected.startswith("sha256:"):
        print(f"ERROR: Unsupported checksum format: {expected}", file=sys.stderr)
        return False
    return hashlib.sha256(data).hexdigest() == expected[len("sha256:"):]


def extract_bundle(bundle_data: bytes, output_dir: Path):
    buf = io.BytesIO(bundle_data)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        tar.extractall(path=output_dir)


# ---------------------------------------------------------------------------
# Content checksum — must match Java's check-model-drift.sh algorithm
# ---------------------------------------------------------------------------

def compute_content_checksum(model_dir: Path) -> str:
    """
    Deterministic content-level checksum:
      1. List all files (excluding GENERATED.md and models.lock.json)
      2. Sort by relative POSIX path (LC_ALL=C order)
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
        # Reproduce `sha256sum` output format: "<hash>  ./<relpath>"
        rel_hashes.append(f"{digest}  ./{rel}")

    combined = "\n".join(rel_hashes) + "\n" if rel_hashes else ""
    overall = hashlib.sha256(combined.encode()).hexdigest()
    return f"sha256:{overall}"


# ---------------------------------------------------------------------------
# Lock file
# ---------------------------------------------------------------------------

def write_lock(lock_path: Path, registry: str, package: str, version: str,
               checksum: str, content_checksum: str):
    lock = {
        "registry": registry,
        "package": package,
        "version": version,
        "checksum": checksum,
        "content_checksum": content_checksum,
    }
    lock_path.write_text(
        json.dumps(lock, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return lock


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Pull Odoo TM/QM models from foggy-model-registry",
    )
    parser.add_argument("--registry", default=DEFAULT_REGISTRY,
                        help=f"Registry data path or HTTP URL (default: {DEFAULT_REGISTRY})")
    parser.add_argument("--channel", default="stable",
                        help="Channel: stable | beta (default: stable)")
    parser.add_argument("--edition", default="community", choices=["community", "pro"],
                        help="Edition: community | pro (default: community)")
    parser.add_argument("--package", default=None,
                        help="Package name (default: foggy.odoo.<edition>)")
    parser.add_argument("--key", default=None,
                        help="Bearer key (required for pro edition)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                        help=f"Output directory (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing files")
    args = parser.parse_args()

    package = args.package or f"foggy.odoo.{args.edition}"
    output_dir = Path(args.output).resolve()
    lock_path = output_dir / "models.lock.json"

    print("=== pull-odoo-models (Python) ===")
    print(f"  registry : {args.registry}")
    print(f"  package  : {package}")
    print(f"  channel  : {args.channel}")
    print(f"  edition  : {args.edition}")
    print(f"  output   : {output_dir}")
    print()

    # Pre-flight: pro requires key
    if args.edition == "pro" and not args.key:
        print("ERROR: Pro edition requires --key", file=sys.stderr)
        sys.exit(1)

    # 1. Resolve channel → version
    print(f"Resolving channel '{args.channel}'...")
    version = resolve_channel(args.registry, args.edition, package, args.channel,
                              key=args.key)
    print(f"  Resolved to version: {version}")

    # 2. Read manifest
    print(f"Reading manifest for {package}@{version}...")
    manifest = read_manifest(args.registry, args.edition, package, version,
                             key=args.key)
    checksum = manifest["checksum"]
    model_count = len(manifest.get("models", []))
    print(f"  Found {model_count} models, checksum: {checksum}")

    # 3. Download bundle
    print("Downloading bundle...")
    bundle_data = download_bundle(args.registry, args.edition, package, version,
                                  key=args.key)
    print(f"  Bundle size: {len(bundle_data)} bytes")

    # 4. Verify checksum
    print("Verifying checksum...")
    if not verify_checksum(bundle_data, checksum):
        actual = hashlib.sha256(bundle_data).hexdigest()
        print(f"ERROR: Checksum mismatch!", file=sys.stderr)
        print(f"  Expected: {checksum}", file=sys.stderr)
        print(f"  Actual:   sha256:{actual}", file=sys.stderr)
        sys.exit(1)
    print("  Checksum verified.")

    # 5. Extract to staging
    staging = Path(tempfile.mkdtemp(prefix="foggy-pull-"))
    try:
        print(f"Extracting to staging ({staging})...")
        extract_bundle(bundle_data, staging)

        if args.dry_run:
            print()
            print("[dry-run] Would sync model files to:", output_dir)
            print("[dry-run] Would write lock file to:", lock_path)
            cc = compute_content_checksum(staging)
            print("[dry-run] Content checksum:", cc)
            return

        # 6. Sync to output directory
        print(f"Syncing model directory: {output_dir}")

        # Preserve models.lock.json and GENERATED.md during clear
        for item in output_dir.iterdir():
            if item.name in ("models.lock.json", "GENERATED.md"):
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        # Copy from staging (everything except models.lock.json)
        for item in staging.iterdir():
            if item.name == "models.lock.json":
                continue
            dest = output_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        # 7. Compute content checksum
        content_checksum = compute_content_checksum(output_dir)

        # 8. Write lock file
        lock = write_lock(lock_path, args.registry, package, version,
                          checksum, content_checksum)

        # 9. Write GENERATED.md marker
        (output_dir / "GENERATED.md").write_text(GENERATED_MARKER, encoding="utf-8")

        print()
        print("Pull complete.")
        print(f"  Models : {output_dir}")
        print(f"  Lock   : {lock_path}")
        print()
        print(json.dumps(lock, indent=2, ensure_ascii=False))

    finally:
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    main()
