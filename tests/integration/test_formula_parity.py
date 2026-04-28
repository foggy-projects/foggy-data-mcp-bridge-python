"""Formula parity (M5 Step 5.1) — Python side.

Reads the shared parity catalog (maintained at
``foggy-data-mcp-bridge/foggy-dataset-model/src/test/resources/parity/formula-parity-expressions.json``)
and asserts that the Python ``FormulaCompiler`` output reduces to the catalog's
``expected_sql`` / ``expected_params`` through the shared
:mod:`tests.integration._sql_normalizer`.

Java side owns an equivalent ``FormulaParitySnapshotTest`` (see M5 Step 5.1 in
``docs/v1.4/REQ-FORMULA-EXTEND-M5-parity-execution-prompt.md``): the Java test
produces a snapshot JSON at ``tests/integration/_parity_snapshot.json``; the
``test_parity_matches_java_snapshot`` test below picks it up opportunistically
when present, so the two sides stay honest.

When the Java snapshot is absent (fresh clone or CI lane without the Java
build), the snapshot test is skipped; the catalog-driven tests still run and
guard Python-side parity on their own.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest

from foggy.dataset_model.semantic.formula_compiler import (
    CompiledFormula,
    FormulaCompiler,
)
from foggy.dataset_model.semantic.formula_dialect import SqlDialect

from tests.integration._sql_normalizer import (
    canonicalize_params,
    to_canonical,
)

# --------------------------------------------------------------------------- #
# Catalog loader
# --------------------------------------------------------------------------- #

# Java side is the source of truth for the catalog file so both ends read the
# same bytes.  We locate it via repo-root relative path.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CATALOG_PATH = (
    _REPO_ROOT
    / "foggy-data-mcp-bridge"
    / "foggy-dataset-model"
    / "src"
    / "test"
    / "resources"
    / "parity"
    / "formula-parity-expressions.json"
)


def _load_catalog() -> List[dict]:
    if not _CATALOG_PATH.exists():
        pytest.skip(
            f"parity catalog missing: {_CATALOG_PATH} "
            "(run mvn or check out the Java repo)"
        )
    data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    entries = [e for e in data["expressions"] if e.get("kind") == "positive"]
    assert len(entries) >= 30, (
        f"parity catalog has only {len(entries)} positive entries "
        "(expected >= 30 per M5 Step 5.1)"
    )
    return entries


# Eager load at collection time so pytest's parametrize decorator can see ids.
_CATALOG: List[dict] = _load_catalog() if _CATALOG_PATH.exists() else []


# --------------------------------------------------------------------------- #
# Per-entry tests (Python compile → normalize → compare against catalog)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "entry",
    _CATALOG,
    ids=[e["id"] for e in _CATALOG],
)
def test_python_matches_catalog(entry: dict) -> None:
    expr: str = entry["expression"]
    dialect_name: str = entry["dialect"]
    expected_sql: str = entry["expected_sql"]
    expected_params: List[object] = list(entry["expected_params"])

    compiler = FormulaCompiler(SqlDialect.of(dialect_name))
    result: CompiledFormula = compiler.compile(expr, lambda name: name)

    # Canonicalize both sides through the same rules.
    actual_sql, actual_params = to_canonical(
        result.sql_fragment, list(result.bind_params)
    )
    norm_expected_sql, norm_expected_params = to_canonical(
        expected_sql, expected_params
    )

    assert actual_sql == norm_expected_sql, (
        f"[{entry['id']}] SQL parity mismatch\n"
        f"  expression : {expr!r}\n"
        f"  dialect    : {dialect_name}\n"
        f"  expected   : {norm_expected_sql}\n"
        f"  actual     : {actual_sql}\n"
        f"  raw Python : {result.sql_fragment}\n"
    )
    assert canonicalize_params(actual_params) == canonicalize_params(
        norm_expected_params
    ), (
        f"[{entry['id']}] param parity mismatch\n"
        f"  expected   : {norm_expected_params}\n"
        f"  actual     : {actual_params}\n"
    )


def test_catalog_has_coverage_targets() -> None:
    """Guard: catalog must cover Step 5.1 category quotas from the execution prompt."""
    ids = [e["id"] for e in _CATALOG]
    # 算术 ≥5, 比较/逻辑 ≥5, IN ≥3, 函数 ≥5, 聚合 ≥5, 日期 ≥3
    assert sum(i.startswith("ari-") for i in ids) >= 5
    assert sum(i.startswith("cmp-") or i.startswith("bool-") for i in ids) >= 5
    assert sum(i.startswith("in-") for i in ids) >= 3
    assert (
        sum(
            i.startswith(pfx)
            for pfx in ("null-", "num-", "bt-")
            for i in ids
        )
        >= 5
    )
    assert sum(i.startswith("agg-") for i in ids) >= 5
    assert sum(i.startswith("dt-") for i in ids) >= 3


def test_normalizer_collapses_java_python_equivalent_shapes() -> None:
    examples = [
        ("(- a)", None, "(-a)", ()),
        ("(NOT (a = 0))", None, "NOT (a = ?)", (0,)),
        ("CASE WHEN (overdue) THEN amount ELSE NULL END", [], "CASE WHEN overdue THEN amount ELSE NULL END", ()),
        ("(deletedAt IS NULL)", None, "deletedAt IS NULL", ()),
        ("CEIL(a / b)", [], "CEILING(a / b)", ()),
        ("CAST((julianday(datetime('now')) - julianday(dateMaturity)) AS INTEGER)", None,
         "CAST((julianday(datetime('NOW')) - julianday(dateMaturity)) AS INTEGER)", ()),
    ]
    for raw_sql, raw_params, expected_sql, expected_params in examples:
        assert to_canonical(raw_sql, raw_params) == (expected_sql, expected_params)


# --------------------------------------------------------------------------- #
# Java snapshot compare (enabled when Java side has produced it)
# --------------------------------------------------------------------------- #

# Stage 2 (P2-post-v1.5): snapshot CI solidification.
#
# Artifact contract:
#   - Java produces the snapshot by running:
#       mvn test -pl foggy-dataset-model -Dtest=FormulaParitySnapshotTest
#     This writes to:
#       1. ../foggy-data-mcp-bridge-python/tests/integration/_parity_snapshot.json
#          (cross-repo direct write — works when both repos live under the same
#          foggy-data-mcp workspace)
#       2. target/parity/_parity_snapshot.json (local copy for CI artifact upload)
#
#   - Python consumes the committed snapshot at the path below.
#
#   - In CI, either:
#     (a) Both repos are checked out under the same workspace and the Java job
#         runs first, writing the snapshot directly, OR
#     (b) The Java job uploads target/parity/_parity_snapshot.json as an artifact
#         and the Python job downloads it to tests/integration/ before running.
#
#   - The committed snapshot in git serves as a fallback and drift-detection
#     baseline. When the catalog changes, the Java test must be re-run to
#     regenerate; the drift check below catches staleness.
#
# Regeneration command (run from the Java worktree root):
#   mvn test -pl foggy-dataset-model -Dtest=FormulaParitySnapshotTest

_SNAPSHOT_PATH = Path(__file__).with_name("_parity_snapshot.json")

_REGEN_HINT = (
    "_parity_snapshot.json not present — regenerate by running:\n"
    "  cd <java-worktree>\n"
    "  mvn test -pl foggy-dataset-model -Dtest=FormulaParitySnapshotTest\n"
    "See docs/v1.5/S2-formula-parity-snapshot-ci-progress.md for details."
)


def _load_snapshot() -> dict:
    if not _SNAPSHOT_PATH.exists():
        pytest.skip(_REGEN_HINT)
    return json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_snapshot_schema_integrity() -> None:
    """Stage 2: committed snapshot has valid schema and expected source."""
    snapshot = _load_snapshot()
    assert snapshot.get("schema_version") == "1", (
        "snapshot schema_version must be '1'; got "
        f"{snapshot.get('schema_version')!r}"
    )
    assert snapshot.get("source") == "FormulaParitySnapshotTest", (
        "snapshot source must be 'FormulaParitySnapshotTest'; got "
        f"{snapshot.get('source')!r}"
    )
    snapshots = snapshot.get("snapshots", [])
    assert len(snapshots) >= 30, (
        f"snapshot has {len(snapshots)} entries, expected >= 30 "
        "(per M5 Step 5.1 quota)"
    )


def test_snapshot_covers_full_catalog() -> None:
    """Stage 2: every non-java_skip catalog entry appears in the snapshot.

    Detects staleness: when new expressions are added to the catalog but
    the Java snapshot has not been regenerated, this test fails with a
    clear list of missing ids.
    """
    snapshot = _load_snapshot()
    snapshot_ids = {row["id"] for row in snapshot.get("snapshots", [])}

    catalog_ids = {
        e["id"] for e in _CATALOG
        if not e.get("java_skip", False)
    }
    missing = sorted(catalog_ids - snapshot_ids)
    assert not missing, (
        f"committed snapshot is stale — missing {len(missing)} catalog entries: "
        f"{missing}. Regenerate by running:\n"
        "  mvn test -pl foggy-dataset-model -Dtest=FormulaParitySnapshotTest"
    )


def test_committed_snapshot_not_hand_edited() -> None:
    """Stage 2: every snapshot entry has exactly the expected fields and
    corresponds to a catalog entry — hand-edits would add unknown fields or
    orphan ids.
    """
    snapshot = _load_snapshot()
    catalog_ids = {e["id"] for e in _CATALOG}
    expected_fields = {"id", "expression", "dialect", "sql_normalized"}

    orphans = []
    bad_fields = []
    for row in snapshot.get("snapshots", []):
        rid = row.get("id", "<missing-id>")
        if rid not in catalog_ids:
            orphans.append(rid)
        actual_fields = set(row.keys())
        # bind_params is optional (Java currently doesn't emit it)
        extra = actual_fields - expected_fields - {"bind_params"}
        if extra:
            bad_fields.append(f"[{rid}] unexpected fields: {extra}")

    issues = []
    if orphans:
        issues.append(f"orphan snapshot entries not in catalog: {orphans}")
    if bad_fields:
        issues.append("hand-edited fields:\n  " + "\n  ".join(bad_fields))
    assert not issues, (
        "snapshot integrity check failed:\n  " + "\n  ".join(issues)
    )


def test_parity_matches_java_snapshot() -> None:
    """Strict Java↔Python compare, when the Java snapshot is available.

    Stage 3: migrated to :mod:`tests.integration._golden_sql_diff` helper
    for structured mismatch output.
    """
    from tests.integration._golden_sql_diff import GoldenCase, assert_golden_cases

    snapshot = _load_snapshot()
    java_by_id: dict = {row["id"]: row for row in snapshot.get("snapshots", [])}
    cases: list[GoldenCase] = []

    for entry in _CATALOG:
        java_row = java_by_id.get(entry["id"])
        if java_row is None:
            continue  # Java side may intentionally omit some cases
        expr = entry["expression"]
        dialect_name = entry["dialect"]

        compiler = FormulaCompiler(SqlDialect.of(dialect_name))
        py_result = compiler.compile(expr, lambda name: name)

        java_raw_sql: str = java_row["sql_normalized"]
        java_raw_params = java_row.get("bind_params", None)

        cases.append(
            GoldenCase(
                feature="formula",
                case_id=entry["id"],
                dialect=dialect_name,
                expected_sql=java_raw_sql,
                actual_sql=py_result.sql_fragment,
                expected_params=(
                    list(java_raw_params) if java_raw_params is not None else None
                ),
                actual_params=list(py_result.bind_params),
                source_hint="_parity_snapshot.json",
            )
        )

    assert len(cases) >= 30, (
        f"expected >= 30 Java↔Python compare cases, got {len(cases)}"
    )
    assert_golden_cases(cases)
