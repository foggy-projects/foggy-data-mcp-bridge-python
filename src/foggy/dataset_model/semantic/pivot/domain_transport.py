"""Pivot Stage 5A Domain Transport — renderer and data structures.

Provides ``DomainTransportPlan``, ``DomainRelationFragment``, and
dialect-specific renderers that generate SQL fragments for domain tuple
transport.  These fragments are injected into the query builder *before*
aggregation so that non-additive metrics (``COUNT_DISTINCT``, ``AVG``)
compute correctly on the domain-filtered detail rows.

Design contract:
  - ``DomainRelationRenderer.render()`` only generates the domain relation
    CTE/derived-table SQL and its params.  It does NOT generate the JOIN
    predicate left side, because the renderer does not know the physical SQL
    expression for each QM column in the base query.
  - The JOIN predicate is built by ``build_join_predicate()`` using a
    ``field_sql_map`` supplied by the caller (query builder or assembler),
    which maps QM column name → SQL expression in the base query
    (e.g. ``{"category_name": 'p."category_name"'}``).
  - ``assemble_domain_transport_sql()`` requires ``field_sql_map`` so it can
    produce executable SQL without hardcoded alias references.

Production code.  Introduced in P3-B.  No public DSL change.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# ── Stable error codes ─────────────────────────────────────────────────

PIVOT_DOMAIN_TRANSPORT_REFUSED = "PIVOT_DOMAIN_TRANSPORT_REFUSED"

# ── Default limits ─────────────────────────────────────────────────────

DEFAULT_DOMAIN_THRESHOLD = 500
# SQLite SQLITE_LIMIT_VARIABLE_NUMBER default is 999
SQLITE_MAX_BIND_PARAMS = 999
MYSQL57_MAX_TUPLES = 2000
MYSQL57_MAX_BIND_PARAMS = 10000


# ── Data structures ───────────────────────────────────────────────────

@dataclass(frozen=True)
class DomainTransportPlan:
    """Internal carrier for surviving domain tuples.

    Not part of public DSL.  Passed internally between pivot stages.

    Attributes:
        columns:   Domain column names (QM field names, not physical).
        tuples:    Each tuple is one surviving domain row.  May contain
                   ``None`` for NULL members.
        threshold: Domain size at or below which OR-of-AND slicing is
                   used instead of transport.  Default 500.
    """

    columns: Tuple[str, ...]
    tuples: Tuple[Tuple[Any, ...], ...]
    threshold: int = DEFAULT_DOMAIN_THRESHOLD


@dataclass(frozen=True)
class DomainRelationFragment:
    """Result of rendering a DomainTransportPlan into SQL fragments.

    The renderer only populates ``cte_sql`` and ``domain_params``.  The
    JOIN clause is NOT included here — it is built separately by
    ``build_join_predicate()`` once the caller provides ``field_sql_map``.

    Attributes:
        cte_sql:        The ``WITH _pivot_domain_transport(...) AS (...)``
                        SQL block.  Empty string for Derived Table strategy
                        (the relation SQL is inline in the join).
        relation_alias: SQL alias for the domain relation table (e.g. ``_d``).
        columns:        QM column names in the domain relation (same order as
                        the CTE column definitions and VALUES rows).
        domain_params:  Bind params for the domain relation VALUES, in order.
        placement:      ``"CTE"`` or ``"DERIVED_TABLE"`` — determines how
                        ``domain_params`` are merged with base query params.
    """

    cte_sql: str
    relation_alias: str
    columns: Tuple[str, ...]
    domain_params: Tuple[Any, ...]
    placement: str  # "CTE" | "DERIVED_TABLE"


# ── Abstract renderer ────────────────────────────────────────────────

class DomainRelationRenderer(ABC):
    """Renders a ``DomainTransportPlan`` into dialect-specific SQL.

    The renderer's responsibility is limited to generating the domain
    relation (CTE definition or derived table SQL) and its bind params.
    JOIN predicate construction is delegated to the assembly layer, which
    has access to the physical SQL expressions of the base query.
    """

    @abstractmethod
    def render(self, plan: DomainTransportPlan) -> DomainRelationFragment:
        """Generate SQL fragments for the domain relation.

        Raises:
            NotImplementedError: If this renderer cannot handle the plan.
        """
        ...

    @abstractmethod
    def can_render(self, plan: DomainTransportPlan) -> Tuple[bool, Optional[str]]:
        """Check whether this renderer can handle the plan.

        Returns:
            ``(True, None)`` if OK, ``(False, reason_string)`` otherwise.
        """
        ...

    @abstractmethod
    def build_null_safe_predicate(self, left_expr: str, right_expr: str) -> str:
        """Build a dialect-appropriate NULL-safe equality predicate.

        Args:
            left_expr:  SQL expression from the base query side.
            right_expr: SQL expression from the domain relation side.

        Returns:
            e.g. ``'p."cat" IS _d."cat"'`` (SQLite)
        """
        ...

    def quote_domain_column(self, column: str) -> str:
        """Quote a domain CTE column name for this dialect."""
        escaped = column.replace('"', '""')
        return f'"{escaped}"'


# ── SQLite CTE renderer ─────────────────────────────────────────────

class SqliteCteDomainRenderer(DomainRelationRenderer):
    """Render domain relation as a CTE using SQLite ``VALUES`` syntax.

    NULL-safe matching uses the ``IS`` operator, which treats
    ``NULL IS NULL`` as ``TRUE`` in SQLite.
    """

    _CTE_NAME = "_pivot_domain_transport"
    _JOIN_ALIAS = "_d"

    def can_render(self, plan: DomainTransportPlan) -> Tuple[bool, Optional[str]]:
        if not plan.tuples:
            # Empty domain: no transport needed; caller should skip.
            return False, None
        if not plan.columns:
            return False, f"{PIVOT_DOMAIN_TRANSPORT_REFUSED}: empty columns"
        total_params = len(plan.tuples) * len(plan.columns)
        if total_params > SQLITE_MAX_BIND_PARAMS:
            return False, (
                f"{PIVOT_DOMAIN_TRANSPORT_REFUSED}: SQLite bind param limit "
                f"exceeded ({total_params} > {SQLITE_MAX_BIND_PARAMS}). "
                f"Reduce domain size or use a different dialect."
            )
        return True, None

    def render(self, plan: DomainTransportPlan) -> DomainRelationFragment:
        ok, reason = self.can_render(plan)
        if not ok:
            raise NotImplementedError(
                reason or f"{PIVOT_DOMAIN_TRANSPORT_REFUSED}: cannot render plan"
            )

        n_cols = len(plan.columns)

        # ── CTE definition ──────────────────────────────────────────
        # Column names in the CTE are the QM field names, double-quoted.
        col_defs = ", ".join(self.quote_domain_column(c) for c in plan.columns)
        row_ph = ", ".join("?" for _ in range(n_cols))
        values_rows = ", ".join(f"({row_ph})" for _ in plan.tuples)
        cte_sql = (
            f"WITH {self._CTE_NAME}({col_defs}) AS (\n"
            f"    VALUES {values_rows}\n"
            f")"
        )

        # ── Flatten params (row-major) ──────────────────────────────
        domain_params: List[Any] = []
        for t in plan.tuples:
            domain_params.extend(t)

        logger.info(
            "PIVOT_DOMAIN_TRANSPORT: dialect=sqlite, strategy=CTE, "
            "domain_size=%d, columns=%s",
            len(plan.tuples), plan.columns,
        )

        return DomainRelationFragment(
            cte_sql=cte_sql,
            relation_alias=self._JOIN_ALIAS,
            columns=plan.columns,
            domain_params=tuple(domain_params),
            placement="CTE",
        )

    def build_null_safe_predicate(self, left_expr: str, right_expr: str) -> str:
        """SQLite NULL-safe equality: ``left IS right``."""
        return f"{left_expr} IS {right_expr}"


# ── PostgreSQL CTE renderer ─────────────────────────────────────────

class PostgresCteDomainRenderer(DomainRelationRenderer):
    """Render domain relation as a CTE using PostgreSQL ``VALUES`` syntax.

    NULL-safe matching uses the ``IS NOT DISTINCT FROM`` operator.
    """

    _CTE_NAME = "_pivot_domain_transport"
    _JOIN_ALIAS = "_d"

    def can_render(self, plan: DomainTransportPlan) -> Tuple[bool, Optional[str]]:
        if not plan.tuples:
            return False, None
        if not plan.columns:
            return False, f"{PIVOT_DOMAIN_TRANSPORT_REFUSED}: empty columns"
        # PostgreSQL max params is 32767, but we use 10000 to be safe
        total_params = len(plan.tuples) * len(plan.columns)
        if total_params > 10000:
            return False, (
                f"{PIVOT_DOMAIN_TRANSPORT_REFUSED}: PostgreSQL bind param limit "
                f"exceeded ({total_params} > 10000). "
                f"Reduce domain size or use a different dialect."
            )
        return True, None

    def render(self, plan: DomainTransportPlan) -> DomainRelationFragment:
        ok, reason = self.can_render(plan)
        if not ok:
            raise NotImplementedError(
                reason or f"{PIVOT_DOMAIN_TRANSPORT_REFUSED}: cannot render plan"
            )

        n_cols = len(plan.columns)

        # ── CTE definition ──────────────────────────────────────────
        col_defs = ", ".join(f'"{c}"' for c in plan.columns)
        row_ph = ", ".join("?" for _ in range(n_cols))
        values_rows = ", ".join(f"({row_ph})" for _ in plan.tuples)
        cte_sql = (
            f"WITH {self._CTE_NAME}({col_defs}) AS (\n"
            f"    VALUES {values_rows}\n"
            f")"
        )

        domain_params: List[Any] = []
        for t in plan.tuples:
            domain_params.extend(t)

        logger.info(
            "PIVOT_DOMAIN_TRANSPORT: dialect=postgres, strategy=CTE, "
            "domain_size=%d, columns=%s",
            len(plan.tuples), plan.columns,
        )

        return DomainRelationFragment(
            cte_sql=cte_sql,
            relation_alias=self._JOIN_ALIAS,
            columns=plan.columns,
            domain_params=tuple(domain_params),
            placement="CTE",
        )

    def build_null_safe_predicate(self, left_expr: str, right_expr: str) -> str:
        """PostgreSQL NULL-safe equality: ``left IS NOT DISTINCT FROM right``."""
        return f"{left_expr} IS NOT DISTINCT FROM {right_expr}"


# ── MySQL 8 CTE renderer ────────────────────────────────────────────

class Mysql8DomainRenderer(DomainRelationRenderer):
    """Render domain relation as a CTE using MySQL ``UNION ALL SELECT``.

    Avoids ``VALUES ROW(?)`` due to stability issues in older/mixed MySQL 8.x versions.
    NULL-safe matching uses the ``<=>`` operator.
    """

    _CTE_NAME = "_pivot_domain_transport"
    _JOIN_ALIAS = "_d"

    def can_render(self, plan: DomainTransportPlan) -> Tuple[bool, Optional[str]]:
        if not plan.tuples:
            return False, None
        if not plan.columns:
            return False, f"{PIVOT_DOMAIN_TRANSPORT_REFUSED}: empty columns"
        total_params = len(plan.tuples) * len(plan.columns)
        if total_params > MYSQL57_MAX_BIND_PARAMS:
            return False, (
                f"{PIVOT_DOMAIN_TRANSPORT_REFUSED}: MySQL bind param limit "
                f"exceeded ({total_params} > {MYSQL57_MAX_BIND_PARAMS}). "
            )
        return True, None

    def render(self, plan: DomainTransportPlan) -> DomainRelationFragment:
        ok, reason = self.can_render(plan)
        if not ok:
            raise NotImplementedError(
                reason or f"{PIVOT_DOMAIN_TRANSPORT_REFUSED}: cannot render plan"
            )

        # ── CTE definition using UNION ALL SELECT ───────────────────
        col_defs = ", ".join(self.quote_domain_column(c) for c in plan.columns)

        selects = []
        for i, t in enumerate(plan.tuples):
            # First row must provide aliases for some strict SQL engines,
            # though CTE columns already define names. We use standard ? params.
            row_cols = ", ".join("?" for _ in plan.columns)
            selects.append(f"SELECT {row_cols}")

        union_all_sql = "\n    UNION ALL ".join(selects)

        cte_sql = (
            f"WITH {self._CTE_NAME}({col_defs}) AS (\n"
            f"    {union_all_sql}\n"
            f")"
        )

        domain_params: List[Any] = []
        for t in plan.tuples:
            domain_params.extend(t)

        logger.info(
            "PIVOT_DOMAIN_TRANSPORT: dialect=mysql8, strategy=CTE_UNION_ALL, "
            "domain_size=%d, columns=%s",
            len(plan.tuples), plan.columns,
        )

        return DomainRelationFragment(
            cte_sql=cte_sql,
            relation_alias=self._JOIN_ALIAS,
            columns=plan.columns,
            domain_params=tuple(domain_params),
            placement="CTE",
        )

    def build_null_safe_predicate(self, left_expr: str, right_expr: str) -> str:
        """MySQL NULL-safe equality: ``left <=> right``."""
        return f"{left_expr} <=> {right_expr}"

    def quote_domain_column(self, column: str) -> str:
        """MySQL identifier quoting for domain CTE columns."""
        escaped = column.replace("`", "``")
        return f"`{escaped}`"


# ── JOIN predicate builder ─────────────────────────────────────────

def build_join_predicate(
    fragment: DomainRelationFragment,
    field_sql_map: Dict[str, str],
    renderer: DomainRelationRenderer,
) -> str:
    """Build the ``INNER JOIN ... ON ...`` clause for the domain relation.

    Args:
        fragment:       The rendered domain relation fragment.
        field_sql_map:  Mapping from QM column name to the SQL expression
                        used in the base query.  E.g.::

                            {"category_name": 'p."category_name"'}

                        All columns in ``fragment.columns`` must be present.
        renderer:       Renderer used to build dialect-correct NULL-safe
                        equality predicates.

    Returns:
        Complete ``INNER JOIN ... ON ...`` SQL string.

    Raises:
        ValueError: If any required column is missing from ``field_sql_map``.
    """
    missing = [c for c in fragment.columns if c not in field_sql_map]
    if missing:
        raise ValueError(
            f"{PIVOT_DOMAIN_TRANSPORT_REFUSED}: field_sql_map is missing "
            f"expressions for columns: {missing}"
        )

    predicates = []
    for col in fragment.columns:
        left_expr = field_sql_map[col]
        right_expr = f"{fragment.relation_alias}.{renderer.quote_domain_column(col)}"
        predicates.append(renderer.build_null_safe_predicate(left_expr, right_expr))

    join_predicate = " AND ".join(predicates)
    cte_name = _extract_cte_name(fragment)
    return f"INNER JOIN {cte_name} AS {fragment.relation_alias} ON {join_predicate}"


def _extract_cte_name(fragment: DomainRelationFragment) -> str:
    """Extract the domain relation name from the CTE SQL (for CTE placement)
    or derive it from the alias for derived table placement."""
    if fragment.placement == "CTE" and fragment.cte_sql:
        # First word after "WITH " is the CTE name (before the open paren)
        # e.g. "WITH _pivot_domain_transport(...) AS (...)"
        after_with = fragment.cte_sql[fragment.cte_sql.upper().find("WITH ") + 5:]
        name = after_with.split("(")[0].strip()
        return name
    # Derived table: the join clause is the full derived subquery
    return ""


# ── Renderer resolution ─────────────────────────────────────────────

def resolve_renderer(dialect) -> DomainRelationRenderer:
    """Return the appropriate renderer for the given dialect.

    Raises:
        NotImplementedError: For unsupported or missing dialects.
    """
    if dialect is None:
        raise NotImplementedError(
            f"{PIVOT_DOMAIN_TRANSPORT_REFUSED}: no dialect configured"
        )

    dialect_name = _get_dialect_name(dialect)

    if dialect_name == "sqlite":
        return SqliteCteDomainRenderer()
    if dialect_name in ("postgres", "postgresql"):
        return PostgresCteDomainRenderer()
    if dialect_name in ("mysql", "mysql8"):
        return Mysql8DomainRenderer()

    if dialect_name == "mysql5.7" or dialect_name.startswith("mysql5"):
        raise NotImplementedError(
            f"{PIVOT_DOMAIN_TRANSPORT_REFUSED}: dialect '{dialect_name}' "
            f"domain transport not supported. MySQL 5.7 lacks robust CTE support."
        )

    raise NotImplementedError(
        f"{PIVOT_DOMAIN_TRANSPORT_REFUSED}: dialect '{dialect_name}' "
        f"domain transport not yet implemented"
    )


def _get_dialect_name(dialect) -> str:
    """Extract dialect name string from an FDialect instance."""
    if hasattr(dialect, "name"):
        name_attr = getattr(dialect, "name")
        value = name_attr() if callable(name_attr) else name_attr
        return str(value).lower() if value else ""
    return ""


# ── SQL assembly helper ──────────────────────────────────────────────

def assemble_domain_transport_sql(
    base_sql: str,
    base_params: Sequence[Any],
    fragment: DomainRelationFragment,
    field_sql_map: Dict[str, str],
    renderer: DomainRelationRenderer,
) -> Tuple[str, List[Any]]:
    """Assemble final SQL by injecting the domain CTE and JOIN into base SQL.

    The JOIN clause is built here using ``field_sql_map`` so that the
    left-side SQL expressions match exactly what the base query uses,
    producing directly executable SQL.

    For CTE placement:
      1. Prepend ``fragment.cte_sql`` before the base SQL.
      2. Find the injection point (after existing JOINs, before WHERE/GROUP BY).
      3. Insert the ``INNER JOIN`` clause at the injection point.
      4. Params: ``domain_params`` before ``base_params`` (CTE appears first
         in SQL text, so its ``?`` placeholders come first).

    For DERIVED_TABLE placement:
      1. Build a derived subquery inline at the JOIN injection point.
      2. Params: ``base_params`` split around the injection point, with
         ``domain_params`` inserted at the join position.

    Args:
        base_sql:       SQL from ``QueryBuildResult.sql``.
        base_params:    Params from ``QueryBuildResult.params``.
        fragment:       Rendered domain relation fragment.
        field_sql_map:  QM column name → SQL expression in the base query.
                        Used to build the JOIN predicate left side.
        renderer:       The renderer that produced ``fragment``; used for
                        dialect-correct NULL-safe predicate generation.

    Returns:
        ``(assembled_sql, assembled_params)`` — directly executable.

    Raises:
        ValueError: If ``field_sql_map`` is missing required columns.
        ValueError: If ``fragment.placement`` is unrecognized.
    """
    join_clause = build_join_predicate(fragment, field_sql_map, renderer)
    injection_point = _find_join_injection_point(base_sql)

    if fragment.placement == "CTE":
        assembled_sql = (
            fragment.cte_sql + "\n"
            + base_sql[:injection_point]
            + "\n" + join_clause + "\n"
            + base_sql[injection_point:]
        )
        # CTE VALUES appear first in text → domain params precede base params
        assembled_params = list(fragment.domain_params) + list(base_params)

    elif fragment.placement == "DERIVED_TABLE":
        assembled_sql = (
            base_sql[:injection_point]
            + "\n" + join_clause + "\n"
            + base_sql[injection_point:]
        )
        # Derived table join appears after the FROM clause in text.
        # base_params that belong to FROM subqueries precede domain params.
        # For P3-B (SQLite only), all base_params are in WHERE/GROUP BY which
        # come after the injection point → safe to concat as base + domain.
        assembled_params = list(base_params) + list(fragment.domain_params)

    else:
        raise ValueError(
            f"Unknown fragment placement: {fragment.placement!r}. "
            f"Expected 'CTE' or 'DERIVED_TABLE'."
        )

    return assembled_sql, assembled_params


def _find_join_injection_point(sql: str) -> int:
    """Find the character position where a new JOIN clause should be inserted.

    The JOIN must go after the FROM clause and any existing JOINs, but
    before WHERE / GROUP BY / HAVING / ORDER BY / LIMIT.

    Returns the index of the first terminating keyword found (scanning the
    SQL as uppercase), or ``len(sql)`` if none are found.
    """
    sql_upper = sql.upper()

    # Newline-prefixed keywords to avoid false matches inside string literals
    terminators = [
        "\nWHERE ", "\nGROUP BY ", "\nHAVING ",
        "\nORDER BY ", "\nLIMIT ",
    ]

    earliest = len(sql)
    for term in terminators:
        pos = sql_upper.find(term)
        if pos != -1 and pos < earliest:
            earliest = pos

    return earliest
