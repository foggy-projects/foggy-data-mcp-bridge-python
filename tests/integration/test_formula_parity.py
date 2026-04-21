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
from typing import List, Tuple

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


# --------------------------------------------------------------------------- #
# Java snapshot compare (optional — enabled when Java side has produced it)
# --------------------------------------------------------------------------- #


_SNAPSHOT_PATH = Path(__file__).with_name("_parity_snapshot.json")


def _load_snapshot() -> dict:
    if not _SNAPSHOT_PATH.exists():
        pytest.skip(
            "_parity_snapshot.json not present — regenerate by running "
            "`mvn test -pl foggy-dataset-model "
            "-Dtest=FormulaParitySnapshotTest` on the Java side"
        )
    return json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_parity_matches_java_snapshot() -> None:
    """Strict Java↔Python compare, when the Java snapshot is available."""
    snapshot = _load_snapshot()
    java_by_id: dict = {row["id"]: row for row in snapshot.get("snapshots", [])}
    mismatches: List[Tuple[str, str]] = []

    for entry in _CATALOG:
        java_row = java_by_id.get(entry["id"])
        if java_row is None:
            continue  # Java side may intentionally omit some cases
        expr = entry["expression"]
        dialect_name = entry["dialect"]

        compiler = FormulaCompiler(SqlDialect.of(dialect_name))
        py_result = compiler.compile(expr, lambda name: name)
        py_sql, py_params = to_canonical(
            py_result.sql_fragment, list(py_result.bind_params)
        )

        java_raw_sql: str = java_row["sql_normalized"]
        java_raw_params = java_row.get("bind_params", None)
        java_sql, java_params = to_canonical(
            java_raw_sql,
            list(java_raw_params) if java_raw_params is not None else None,
        )

        if py_sql != java_sql or canonicalize_params(
            py_params
        ) != canonicalize_params(java_params):
            mismatches.append(
                (
                    entry["id"],
                    f"py={py_sql!r} params={py_params} | "
                    f"java={java_sql!r} params={java_params}",
                )
            )

    assert not mismatches, (
        "parity drift between Java snapshot and Python compiler:\n"
        + "\n".join(f"  [{mid}] {detail}" for mid, detail in mismatches)
    )
