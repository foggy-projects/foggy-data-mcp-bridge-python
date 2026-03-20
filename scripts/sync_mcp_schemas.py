#!/usr/bin/env python3
"""Sync MCP tool schemas and descriptions from Java source project.

Usage:
    python scripts/sync_mcp_schemas.py
    python scripts/sync_mcp_schemas.py --java-root /path/to/foggy-data-mcp-bridge
    python scripts/sync_mcp_schemas.py --dry-run
    python scripts/sync_mcp_schemas.py --diff

This script copies tool description (.md) and schema (.json) files from the
Java project to the Python project, ensuring both sides use identical tool
definitions for MCP protocol compatibility.

Source: {java-root}/foggy-dataset-mcp/src/main/resources/schemas/
Target: {python-root}/src/foggy/mcp/schemas/
"""

import argparse
import os
import shutil
import sys
import filecmp
from pathlib import Path
from datetime import datetime


# Default paths (relative to this script's location)
SCRIPT_DIR = Path(__file__).parent.resolve()
PYTHON_ROOT = SCRIPT_DIR.parent
JAVA_ROOT_DEFAULT = PYTHON_ROOT.parent.parent / "foggy-data-mcp-bridge"

# Source and target directories
JAVA_SCHEMAS_REL = "foggy-dataset-mcp/src/main/resources/schemas"
PYTHON_SCHEMAS_REL = "src/foggy/mcp/schemas"

# Addon schemas (optional)
ADDON_SCHEMAS = {
    "foggy-data-viewer": "addons/foggy-data-viewer/src/main/resources/schemas",
}

# Files to sync
SCHEMA_FILES = [
    "get_metadata_schema.json",
    "describe_model_internal_schema.json",
    "query_model_v3_schema.json",
    "compose_query_schema.json",
    "dataset_nl_query_schema.json",
    "export_with_chart_schema.json",
    "generate_chart_schema.json",
    "inspect_table_schema.json",
]

DESCRIPTION_FILES = [
    "descriptions/get_metadata.md",
    "descriptions/describe_model_internal.md",
    "descriptions/query_model_v3.md",
    "descriptions/query_model_v3_basic.md",
    "descriptions/query_model_v3_no_vector.md",
    "descriptions/compose_query.md",
    "descriptions/dataset_nl_query.md",
    "descriptions/export_with_chart.md",
    "descriptions/generate_chart.md",
    "descriptions/inspect_table.md",
]


def sync_file(src: Path, dst: Path, dry_run: bool = False) -> str:
    """Sync a single file. Returns status string."""
    if not src.exists():
        return f"  SKIP (not found): {src.name}"

    if dst.exists() and filecmp.cmp(src, dst, shallow=False):
        return f"  OK   (identical):  {src.name}"

    action = "NEW " if not dst.exists() else "SYNC"
    if dry_run:
        return f"  {action} (dry-run):  {src.name}"

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return f"  {action} (copied):   {src.name}"


def diff_file(src: Path, dst: Path) -> str:
    """Show diff between source and target."""
    if not src.exists():
        return f"--- {src.name}: not found in Java project"
    if not dst.exists():
        return f"+++ {src.name}: missing in Python project (needs sync)"
    if filecmp.cmp(src, dst, shallow=False):
        return f"=== {src.name}: identical"

    # Show basic diff info
    src_lines = src.read_text(encoding="utf-8").splitlines()
    dst_lines = dst.read_text(encoding="utf-8").splitlines()
    return (
        f"!!! {src.name}: DIFFERS\n"
        f"    Java:   {len(src_lines)} lines, {src.stat().st_size} bytes, "
        f"modified {datetime.fromtimestamp(src.stat().st_mtime).strftime('%Y-%m-%d %H:%M')}\n"
        f"    Python: {len(dst_lines)} lines, {dst.stat().st_size} bytes, "
        f"modified {datetime.fromtimestamp(dst.stat().st_mtime).strftime('%Y-%m-%d %H:%M')}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Sync MCP tool schemas from Java to Python project"
    )
    parser.add_argument(
        "--java-root",
        type=Path,
        default=JAVA_ROOT_DEFAULT,
        help=f"Java project root (default: {JAVA_ROOT_DEFAULT})",
    )
    parser.add_argument(
        "--python-root",
        type=Path,
        default=PYTHON_ROOT,
        help=f"Python project root (default: {PYTHON_ROOT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without copying",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Show differences between Java and Python files",
    )
    parser.add_argument(
        "--include-addons",
        action="store_true",
        help="Also sync addon schemas (foggy-data-viewer, etc.)",
    )
    args = parser.parse_args()

    java_root = args.java_root.resolve()
    python_root = args.python_root.resolve()

    java_schemas = java_root / JAVA_SCHEMAS_REL
    python_schemas = python_root / PYTHON_SCHEMAS_REL

    print(f"Java source:  {java_schemas}")
    print(f"Python target: {python_schemas}")
    print()

    if not java_schemas.exists():
        print(f"ERROR: Java schemas directory not found: {java_schemas}")
        print("       Use --java-root to specify the Java project location")
        sys.exit(1)

    all_files = SCHEMA_FILES + DESCRIPTION_FILES

    if args.diff:
        print("=== Diff Report ===")
        for f in all_files:
            result = diff_file(java_schemas / f, python_schemas / f)
            print(result)
        return

    # Sync
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Syncing {len(all_files)} files...")
    print()

    synced = 0
    skipped = 0
    for f in all_files:
        result = sync_file(java_schemas / f, python_schemas / f, args.dry_run)
        print(result)
        if "copied" in result or "NEW" in result:
            synced += 1
        elif "SKIP" in result:
            skipped += 1

    # Addon schemas
    if args.include_addons:
        print()
        print("=== Addon Schemas ===")
        for addon_name, addon_rel in ADDON_SCHEMAS.items():
            addon_dir = java_root / addon_rel
            if addon_dir.exists():
                for f in addon_dir.glob("**/*.json"):
                    rel = f.relative_to(addon_dir)
                    result = sync_file(f, python_schemas / rel, args.dry_run)
                    print(f"  [{addon_name}] {result.strip()}")
                for f in addon_dir.glob("**/*.md"):
                    rel = f.relative_to(addon_dir)
                    result = sync_file(f, python_schemas / rel, args.dry_run)
                    print(f"  [{addon_name}] {result.strip()}")

    print()
    print(f"Done. Synced: {synced}, Skipped: {skipped}, Total: {len(all_files)}")
    if args.dry_run:
        print("(No files were actually copied — remove --dry-run to sync)")


if __name__ == "__main__":
    main()
