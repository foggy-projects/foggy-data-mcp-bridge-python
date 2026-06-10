from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "summarize-compose-snapshot-coverage.py"


def test_compose_snapshot_coverage_script_summary() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads(completed.stdout)

    assert summary["feature"] == "composeQuery"
    assert summary["caseCount"] >= 31
    assert summary["successCaseCount"] >= 27
    assert summary["strictSuccessCaseCount"] == summary["successCaseCount"]
    assert summary["successStrictCoverage"] == (
        f"{summary['successCaseCount']}/{summary['successCaseCount']}"
    )
    assert {"mysql", "mysql8", "postgres", "sqlite", "sqlserver"}.issubset(
        set(summary["dialects"])
    )
    assert {"base", "derived", "union", "join"}.issubset(
        set(summary["planTypes"])
    )
    missing_success_cells = summary["missingSuccessCells"]
    assert {
        "dialect": "sqlite",
        "planType": "base",
    } not in missing_success_cells
    assert {
        "dialect": "sqlite",
        "planType": "derived",
    } not in missing_success_cells
    assert {
        "dialect": "sqlite",
        "planType": "union",
    } not in missing_success_cells
    assert {
        "dialect": "sqlite",
        "planType": "join",
    } not in missing_success_cells
    assert {
        "dialect": "mysql",
        "planType": "derived",
    } not in missing_success_cells
    assert {
        "dialect": "mysql",
        "planType": "union",
    } not in missing_success_cells
    assert {
        "dialect": "mysql",
        "planType": "join",
    } not in missing_success_cells
    assert {
        "dialect": "mysql8",
        "planType": "join",
    } not in missing_success_cells
    assert {
        "dialect": "postgres",
        "planType": "join",
    } not in missing_success_cells
    assert {
        "dialect": "postgres",
        "planType": "union",
    } not in missing_success_cells
    assert {
        "dialect": "sqlserver",
        "planType": "union",
    } not in missing_success_cells
