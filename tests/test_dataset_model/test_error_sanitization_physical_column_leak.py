"""Regression tests for BUG-007-v1.3: physical column leak in error messages.

Background
----------
When a query reaches the database with an unresolved column reference
(validation bypassed, calculated-field edge case, future query shape,
or gateway-engine drift), the executor returns a raw DB error such as::

    column t.move$date does not exist
    HINT:  Perhaps you meant to reference the column "t.move_name".

This leaks:

  1. The physical table alias (``t``) and schema-qualified physical column
     names (``t.move_name``) to the upstream caller / AI / end user.
  2. A PostgreSQL-specific ``HINT:`` referring to physical columns, which
     is confusing for consumers that only know the QM surface.

Expected governance
-------------------
Even when validation is bypassed, the engine's error-reporting surface
must not expose physical column identifiers.  The error propagated back
through ``SemanticQueryResponse.error`` should:

  * Not contain physical column names like ``t.move_name`` or ``move_name``
  * Not contain a raw ``HINT: Perhaps you meant to reference the column ...``
    clause that cites physical columns
  * Prefer QM-field vocabulary (e.g. ``move$date``) and, when possible,
    a QM-level did-you-mean suggestion

These tests pin the current exposure so the fix has a clear target, and
lock in the desired shape after the fix lands.

Ref: docs/v1.3/BUG-007-engine-error-exposes-physical-column.md
"""

from __future__ import annotations

from pathlib import Path

import pytest

from foggy.dataset_model.impl.loader import load_models_from_directory
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.mcp_spi import SemanticQueryRequest


ODOO_MODELS_DIR = (
    Path(__file__).resolve().parents[2].parent
    / "foggy-odoo-bridge-pro"
    / "foggy_mcp_pro"
    / "setup"
    / "foggy-models"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def odoo_service() -> SemanticQueryService:
    """Load the real Odoo TM/QM set and return a configured service."""
    if not ODOO_MODELS_DIR.exists():
        pytest.skip(f"Odoo models directory not found: {ODOO_MODELS_DIR}")

    svc = SemanticQueryService()
    for m in load_models_from_directory(str(ODOO_MODELS_DIR), namespace=None):
        svc.register_model(m)
    return svc


class _PhysicalColumnErrorExecutor:
    """Executor that simulates a PostgreSQL undefined-column error.

    The error text mirrors what psycopg2 / asyncpg surface in real
    deployments, including the ``HINT:`` line citing a physical column.
    """

    def __init__(self, reported_column: str = "move$date",
                 hint_column: str = "t.move_name") -> None:
        self.sql = None
        self._reported_column = reported_column
        self._hint_column = hint_column

    async def execute(self, sql, params=None):
        self.sql = sql
        err = (
            f"column t.{self._reported_column} does not exist\n"
            f"HINT:  Perhaps you meant to reference the column \"{self._hint_column}\"."
        )
        return type("Result", (), {
            "error": err,
            "rows": [],
            "total": 0,
            "sql": sql,
        })()


# ---------------------------------------------------------------------------
# Pre-SQL governance: validation DOES catch the common cases.
# These tests lock in the clean-path behavior so a future refactor of
# error sanitization cannot silently regress user-facing validation.
# ---------------------------------------------------------------------------


class TestSchemaValidationStillCatchesInvalidField:
    """Sanity baseline — the schema-aware validator already rejects
    ``move$date`` on ``OdooAccountMoveLineQueryModel`` before any SQL
    is generated.  This protects the common case."""

    def test_slice_invalid_field_rejected_with_qm_message(self, odoo_service):
        request = SemanticQueryRequest(
            columns=["company$caption", "balance"],
            slice=[{"field": "move$date", "op": ">=", "value": "2026-04-01"}],
        )
        resp = odoo_service.query_model(
            "OdooAccountMoveLineQueryModel", request, mode="validate",
        )

        assert resp.error is not None
        assert "move$date" in resp.error
        # Must use QM vocabulary — no physical alias or DB column leak here
        assert "t.move_name" not in resp.error
        assert "HINT:" not in resp.error
        assert "does not exist" not in resp.error  # DB-style wording forbidden
        assert resp.error_detail is not None
        assert resp.error_detail["errorCode"] == "INVALID_QUERY_FIELD"
        assert resp.error_detail["invalidField"] == "move$date"
        # Did-you-mean should point at a QM field, not a physical column
        suggestions = resp.error_detail["suggestions"]
        assert suggestions, "expected a QM did-you-mean suggestion"
        assert "date" in suggestions
        for s in suggestions:
            assert "_" not in s, f"suggestion leaks physical column: {s!r}"


# ---------------------------------------------------------------------------
# Execution-path defense-in-depth: the bug.
# When something slips through validation and the DB rejects the SQL, the
# current engine pipes the raw DB error through to the user verbatim.
# This exposes physical column names.
# ---------------------------------------------------------------------------


class TestExecutionErrorMustNotLeakPhysicalColumns:
    """Even when validation is bypassed, the engine's error channel must
    not surface physical column identifiers."""

    def _run_with_failing_executor(self, odoo_service):
        # Register a failing executor that mimics PostgreSQL's verbatim
        # 42703 undefined_column error with a HINT citing a physical column.
        executor = _PhysicalColumnErrorExecutor(
            reported_column="move$date",
            hint_column="t.move_name",
        )
        odoo_service.set_executor(executor)
        try:
            # Use a query that passes schema validation (all fields valid)
            # — the point is to force the engine past validation and let
            # the executor produce a DB-style error.
            request = SemanticQueryRequest(
                columns=["company$caption", "balance"],
            )
            resp = odoo_service.query_model(
                "OdooAccountMoveLineQueryModel", request, mode="execute",
            )
            return resp
        finally:
            odoo_service.set_executor(None)

    def test_error_does_not_expose_physical_column_hint(self, odoo_service):
        """The ``HINT: Perhaps you meant to reference the column "t.move_name"``
        phrasing must not escape the engine boundary."""
        resp = self._run_with_failing_executor(odoo_service)
        assert resp.error is not None, "executor error should surface as error"

        # --- Primary governance assertions (currently FAILING) ---
        assert "t.move_name" not in resp.error, (
            "engine leaked physical column name in error:\n" + resp.error
        )
        assert "move_name" not in resp.error, (
            "engine leaked physical column name in error:\n" + resp.error
        )
        assert "HINT:" not in resp.error, (
            "engine forwarded raw DB HINT clause:\n" + resp.error
        )
        assert "Perhaps you meant to reference the column" not in resp.error, (
            "engine forwarded DB-vocabulary did-you-mean:\n" + resp.error
        )

    def test_error_keeps_qm_vocabulary(self, odoo_service):
        """After sanitization the error should still identify the offending
        field in QM vocabulary (``move$date``) so the caller / LLM has
        enough signal to self-correct."""
        resp = self._run_with_failing_executor(odoo_service)
        assert resp.error is not None
        # We are OK with the QM-level name being preserved
        assert "move$date" in resp.error or "field" in resp.error.lower(), (
            "sanitized error must still identify the failing reference, got:\n"
            + resp.error
        )
