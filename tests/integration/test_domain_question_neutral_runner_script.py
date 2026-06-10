from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run-domain-question-neutral-runner.py"


def test_domain_question_neutral_runner_script_dry_run_summary() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dry-run"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["feature"] == "domainQuestionNeutralRunner"
    assert summary["contract"] == "normalized-tool-arguments-v1"
    assert summary["caseCount"] >= 6
    assert summary["collectorRecordCount"] == summary["caseCount"]
    assert summary["unsupportedCaseCount"] >= 3
    assert "pivot-time-window-mutual-exclusion-unsupported" in summary[
        "unsupportedCaseIds"
    ]
