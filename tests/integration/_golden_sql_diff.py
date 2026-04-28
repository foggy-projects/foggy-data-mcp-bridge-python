"""Reusable golden SQL diff helper for cross-engine parity (Stage 3).

Provides a feature-lane-agnostic comparison framework that normalizes
both Java and Python SQL output through the shared
:mod:`tests.integration._sql_normalizer` and produces high-signal
structured mismatch reports.

Usage::

    from tests.integration._golden_sql_diff import GoldenCase, assert_golden_cases

    cases = [
        GoldenCase(
            feature="formula",
            case_id="ari-001",
            dialect="mysql",
            expected_sql="CASE WHEN (a > ?) THEN ? ELSE ? END",
            actual_sql="CASE WHEN (a > ?) THEN ? ELSE ? END",
            expected_params=(0, 1, 0),
            actual_params=(0, 1, 0),
            source_hint="formula-parity-expressions.json",
        ),
    ]
    assert_golden_cases(cases)

Cross-repo invariant: the normalization rules are shared with
``foggy-data-mcp-bridge-wt-dev-compose/.../parity/SqlNormalizer.java``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from tests.integration._sql_normalizer import canonicalize_params, to_canonical


@dataclass(frozen=True)
class GoldenCase:
    """One golden SQL comparison case.

    Attributes:
        feature:         Feature lane (e.g. ``"formula"``, ``"timeWindow"``).
        case_id:         Unique case identifier within the feature lane.
        dialect:         SQL dialect (e.g. ``"mysql"``, ``"postgres"``).
        expected_sql:    Java-side (or catalog) SQL — may contain inline
                         literals or ``?`` placeholders.
        actual_sql:      Python-side SQL — typically ``?`` placeholders.
        expected_params: Parameters for ``expected_sql``.  ``None`` triggers
                         inline-literal extraction.
        actual_params:   Parameters for ``actual_sql``.  ``None`` triggers
                         inline-literal extraction.
        source_hint:     Optional provenance info (fixture path, snapshot id).
    """

    feature: str
    case_id: str
    dialect: str
    expected_sql: str
    actual_sql: str
    expected_params: Optional[Sequence[object]] = None
    actual_params: Optional[Sequence[object]] = None
    source_hint: str = ""


@dataclass
class GoldenMismatch:
    """Structured mismatch detail for a single case."""

    feature: str
    case_id: str
    dialect: str
    expected_canonical_sql: str
    actual_canonical_sql: str
    expected_params: Tuple[object, ...]
    actual_params: Tuple[object, ...]
    sql_match: bool
    params_match: bool
    source_hint: str = ""

    def summary(self) -> str:
        lines = [
            f"[{self.feature}/{self.case_id}] dialect={self.dialect}",
        ]
        if not self.sql_match:
            lines.append(f"  expected SQL : {self.expected_canonical_sql}")
            lines.append(f"  actual SQL   : {self.actual_canonical_sql}")
        if not self.params_match:
            lines.append(f"  expected params : {self.expected_params}")
            lines.append(f"  actual params   : {self.actual_params}")
        if self.source_hint:
            lines.append(f"  source : {self.source_hint}")
        return "\n".join(lines)


@dataclass
class GoldenDiffResult:
    """Aggregated result from :func:`compare_golden_cases`."""

    total: int = 0
    passed: int = 0
    mismatches: List[GoldenMismatch] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.mismatches) == 0

    def failure_message(self) -> str:
        header = (
            f"Golden SQL diff: {len(self.mismatches)} mismatch(es) "
            f"out of {self.total} cases"
        )
        details = "\n\n".join(m.summary() for m in self.mismatches)
        return f"{header}\n\n{details}"


def compare_golden_cases(cases: Sequence[GoldenCase]) -> GoldenDiffResult:
    """Compare a batch of golden cases and return structured results.

    Each case's expected and actual SQL are normalized through
    :func:`~tests.integration._sql_normalizer.to_canonical` before
    comparison.  Parameters are canonicalized via
    :func:`~tests.integration._sql_normalizer.canonicalize_params`.
    """
    result = GoldenDiffResult(total=len(cases))

    for case in cases:
        exp_sql, exp_params = to_canonical(
            case.expected_sql,
            list(case.expected_params) if case.expected_params is not None else None,
        )
        act_sql, act_params = to_canonical(
            case.actual_sql,
            list(case.actual_params) if case.actual_params is not None else None,
        )

        canon_exp_params = canonicalize_params(exp_params)
        canon_act_params = canonicalize_params(act_params)

        sql_match = exp_sql == act_sql
        params_match = canon_exp_params == canon_act_params

        if sql_match and params_match:
            result.passed += 1
        else:
            result.mismatches.append(
                GoldenMismatch(
                    feature=case.feature,
                    case_id=case.case_id,
                    dialect=case.dialect,
                    expected_canonical_sql=exp_sql,
                    actual_canonical_sql=act_sql,
                    expected_params=canon_exp_params,
                    actual_params=canon_act_params,
                    sql_match=sql_match,
                    params_match=params_match,
                    source_hint=case.source_hint,
                )
            )

    return result


def assert_golden_cases(cases: Sequence[GoldenCase]) -> None:
    """Assert all golden cases match.  Raises ``AssertionError`` with
    structured mismatch detail on failure."""
    result = compare_golden_cases(cases)
    assert result.ok, result.failure_message()
