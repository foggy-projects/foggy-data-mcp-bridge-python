#!/usr/bin/env python3
"""Summarize Java compose snapshot dialect and SQL-shape coverage."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "java_compose_snapshot_parity.json"
TARGET_DIALECTS = ("mysql", "mysql8", "postgres", "sqlserver", "sqlite")
TARGET_PLAN_TYPES = ("base", "derived", "union", "join")


def summarize_fixture(path: Path) -> dict[str, Any]:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    cases = snapshot.get("cases", [])
    success_cases = [
        case for case in cases if not case.get("expected", {}).get("errorCode")
    ]
    error_cases = [
        case for case in cases if case.get("expected", {}).get("errorCode")
    ]
    strict_success_cases = [
        case
        for case in success_cases
        if case.get("expected", {}).get("strictSqlShape") is True
    ]

    cells: Counter[tuple[str, str, str]] = Counter()
    strict_cells: Counter[tuple[str, str, str]] = Counter()
    for case in cases:
        dialect = case.get("dialect", "mysql8")
        plan_type = case.get("plan", {}).get("type", "unknown")
        status = "error" if case.get("expected", {}).get("errorCode") else "success"
        key = (dialect, plan_type, status)
        cells[key] += 1
        if case.get("expected", {}).get("strictSqlShape") is True:
            strict_cells[key] += 1

    matrix = [
        {
            "dialect": dialect,
            "planType": plan_type,
            "status": status,
            "caseCount": count,
            "strictSqlShapeCount": strict_cells[(dialect, plan_type, status)],
        }
        for (dialect, plan_type, status), count in sorted(cells.items())
    ]
    missing_success_cells = [
        {"dialect": dialect, "planType": plan_type}
        for dialect in TARGET_DIALECTS
        for plan_type in TARGET_PLAN_TYPES
        if cells[(dialect, plan_type, "success")] == 0
    ]

    return {
        "fixture": str(path),
        "schemaVersion": snapshot.get("schemaVersion"),
        "feature": snapshot.get("feature"),
        "source": snapshot.get("source"),
        "caseCount": len(cases),
        "successCaseCount": len(success_cases),
        "strictSuccessCaseCount": len(strict_success_cases),
        "successStrictCoverage": (
            f"{len(strict_success_cases)}/{len(success_cases)}"
        ),
        "errorCaseCount": len(error_cases),
        "dialects": sorted({case.get("dialect", "mysql8") for case in cases}),
        "planTypes": sorted(
            {case.get("plan", {}).get("type", "unknown") for case in cases}
        ),
        "matrix": matrix,
        "missingSuccessCells": missing_success_cells,
    }


def validate_summary(summary: dict[str, Any]) -> None:
    if summary["schemaVersion"] != 1:
        raise ValueError(f"unsupported schemaVersion: {summary['schemaVersion']!r}")
    if summary["feature"] != "composeQuery":
        raise ValueError(f"unexpected feature: {summary['feature']!r}")
    if summary["caseCount"] <= 0:
        raise ValueError("compose snapshot fixture has no cases")
    if summary["strictSuccessCaseCount"] != summary["successCaseCount"]:
        raise ValueError(
            "not every successful compose snapshot has strict SQL-shape replay: "
            f"{summary['successStrictCoverage']}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize Java compose snapshot dialect/plan coverage.",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help=f"Fixture path (default: {DEFAULT_FIXTURE})",
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
        print(f"invalid compose snapshot fixture: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
