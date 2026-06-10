#!/usr/bin/env python3
"""Run the neutral domain/question Java snapshot replay.

This is an ergonomic wrapper around the existing pytest replay lane. It keeps
the contract LLM-free and Odoo-free while making the fixture runnable from
``scripts/`` like the Java-side direct-runner tooling.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = (
    REPO_ROOT / "tests" / "fixtures" / "java_domain_question_neutral_runner_parity.json"
)
DOMAIN_REPLAY_TEST = REPO_ROOT / "tests" / "integration" / "test_java_domain_fixture_runner.py"
MANIFEST_TEST = REPO_ROOT / "tests" / "integration" / "test_java_snapshot_parity_manifest.py"
FIXTURE_ENV = "FOGGY_DOMAIN_QUESTION_NEUTRAL_FIXTURE"


def summarize_fixture(path: Path) -> dict[str, Any]:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    cases = snapshot.get("cases", [])
    unsupported_cases = [
        case
        for case in cases
        if case.get("expected", {}).get("unsupportedConstructs")
    ]
    error_cases = [
        case
        for case in cases
        if case.get("expected", {}).get("errorCode")
    ]
    return {
        "fixture": str(path),
        "schemaVersion": snapshot.get("schemaVersion"),
        "feature": snapshot.get("feature"),
        "contract": snapshot.get("contract"),
        "caseCount": len(cases),
        "errorCaseCount": len(error_cases),
        "unsupportedCaseCount": len(unsupported_cases),
        "unsupportedCaseIds": [case.get("id") for case in unsupported_cases],
    }


def validate_summary(summary: dict[str, Any]) -> None:
    if summary["schemaVersion"] != 1:
        raise ValueError(f"unsupported schemaVersion: {summary['schemaVersion']!r}")
    if summary["feature"] != "domainQuestionNeutralRunner":
        raise ValueError(f"unexpected feature: {summary['feature']!r}")
    if summary["contract"] != "normalized-tool-arguments-v1":
        raise ValueError(f"unexpected contract: {summary['contract']!r}")
    if summary["caseCount"] <= 0:
        raise ValueError("neutral runner fixture has no cases")


def build_pytest_command(*, include_manifest: bool) -> list[str]:
    command = [sys.executable, "-m", "pytest", str(DOMAIN_REPLAY_TEST)]
    if include_manifest:
        command.append(str(MANIFEST_TEST))
    command.append("-q")
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the neutral domain/question Java snapshot replay.",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help=f"Fixture path (default: {DEFAULT_FIXTURE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate and print fixture summary; do not invoke pytest.",
    )
    parser.add_argument(
        "--no-manifest",
        action="store_true",
        help="Run only the domain/question replay test, skipping the manifest gate.",
    )
    args = parser.parse_args(argv)

    fixture = args.fixture.resolve()
    if not fixture.is_file():
        print(f"fixture not found: {fixture}", file=sys.stderr)
        return 2

    try:
        summary = summarize_fixture(fixture)
        validate_summary(summary)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid neutral runner fixture: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.dry_run:
        return 0

    env = os.environ.copy()
    env[FIXTURE_ENV] = str(fixture)
    command = build_pytest_command(include_manifest=not args.no_manifest)
    print("Running: " + " ".join(command), file=sys.stderr)
    completed = subprocess.run(command, cwd=REPO_ROOT, env=env, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
