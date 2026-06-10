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
    assert summary["caseCount"] >= 20
    assert summary["successCaseCount"] >= 16
    assert summary["strictSuccessCaseCount"] == summary["successCaseCount"]
    assert summary["successStrictCoverage"] == (
        f"{summary['successCaseCount']}/{summary['successCaseCount']}"
    )
    assert {"mysql", "mysql8", "postgres", "sqlserver"}.issubset(
        set(summary["dialects"])
    )
    assert {"base", "derived", "union", "join"}.issubset(
        set(summary["planTypes"])
    )
    assert {
        "dialect": "sqlite",
        "planType": "base",
    } in summary["missingSuccessCells"]
    assert {
        "dialect": "mysql8",
        "planType": "join",
    } in summary["missingSuccessCells"]
