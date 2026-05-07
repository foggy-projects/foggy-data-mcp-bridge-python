"""Physical column mapping cache — bidirectional QM field <-> physical column.

Aligned with Java ``PhysicalColumnMappingBuilder`` / ``PhysicalColumnMappingImpl``.

This module builds a mapping between semantic (QM) field names and their
underlying physical database table.column references.  The mapping enables:

1. **Forward** (QM -> physical): determine which physical columns a QM field
   depends on — used for metadata ``physicalTables`` output.
2. **Reverse** (physical -> QM): convert a list of denied physical columns into
   a set of denied QM field names — used for ``denied_columns`` governance.

Design rules:
- Non-stored ``compute`` / non-stored ``related`` fields are NOT included.
- The mapping is built once per model load and cached alongside the model.
- ``schema`` in ``DeniedColumn`` is currently ignored (matches any schema),
  aligned with Java ``PhysicalColumnMappingImpl.toDeniedQmFields()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Set

from foggy.dataset_model.definitions.base import ColumnType

if TYPE_CHECKING:
    from foggy.dataset_model.impl.model import DbTableModelImpl
    from foggy.mcp_spi.semantic import DeniedColumn


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PhysicalColumnRef:
    """Reference to a single physical database column."""

    table: str
    column: str

    @property
    def key(self) -> str:
        """Canonical lookup key: ``table.column``."""
        return f"{self.table}.{self.column}"


@dataclass
class PhysicalColumnMapping:
    """Immutable bidirectional mapping between QM fields and physical columns.

    After construction via :func:`build_physical_column_mapping`, both the
    forward and reverse maps are frozen and safe to share across threads.
    """

    qm_to_physical: Dict[str, List[PhysicalColumnRef]] = field(default_factory=dict)
    physical_to_qm: Dict[str, List[str]] = field(default_factory=dict)
    physical_tables: List[Dict[str, str]] = field(default_factory=list)
    all_qm_fields: Set[str] = field(default_factory=set)

    def get_physical_columns(self, qm_field: str) -> List[PhysicalColumnRef]:
        """Return physical columns a QM field depends on."""
        return list(self.qm_to_physical.get(qm_field, []))

    def get_qm_fields(self, table: str, column: str) -> List[str]:
        """Return QM fields that map to a given physical column."""
        return list(self.physical_to_qm.get(f"{table}.{column}", []))

    def get_all_qm_field_names(self) -> Set[str]:
        """Return all QM field names known to this mapping."""
        return set(self.all_qm_fields)

    def get_physical_tables(self) -> List[Dict[str, str]]:
        """Return deduplicated list of ``{"table": ..., "role": ...}``."""
        return list(self.physical_tables)

    def to_denied_qm_fields(self, denied_columns: List[DeniedColumn]) -> Set[str]:
        """Convert physical denied columns to a set of denied QM field names.

        Schema is ignored (matches any), aligned with Java.
        Entries with ``None``/empty table or column are skipped.
        """
        denied: Set[str] = set()
        for dc in denied_columns:
            if not dc.table or not dc.column:
                continue
            key = f"{dc.table}.{dc.column}"
            qm_fields = self.physical_to_qm.get(key, [])
            denied.update(qm_fields)
        return denied


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_physical_column_mapping(model: DbTableModelImpl) -> PhysicalColumnMapping:
    """Build a bidirectional mapping from a loaded ``DbTableModelImpl``.

    Covers:
    - Measures -> fact table columns
    - Simple dimensions (on fact table, no JOIN) -> fact table columns
    - Dimension ``$id`` -> fact table FK **and** dimension table PK
    - Dimension ``$caption`` -> dimension table caption column
    - Dimension ``$property`` -> dimension table property column
    - Fact table properties (``model.columns`` dict)

    Calculated fields are **not** expanded here; their dependencies are
    resolved at validation time via the expression parser (same approach
    as field_validator.py).
    """
    qm_to_physical: Dict[str, List[PhysicalColumnRef]] = {}
    physical_to_qm: Dict[str, List[str]] = {}
    tables_seen: Set[str] = set()
    physical_tables: List[Dict[str, str]] = []
    all_qm_fields: Set[str] = set()

    fact_table = model.source_table

    def _add_table(table: str, role: str) -> None:
        if table and table not in tables_seen:
            tables_seen.add(table)
            physical_tables.append({"table": table, "role": role})

    def _add_mapping(qm_field: str, table: str, column: str) -> None:
        ref = PhysicalColumnRef(table=table, column=column)

        qm_to_physical.setdefault(qm_field, []).append(ref)

        key = ref.key
        entries = physical_to_qm.setdefault(key, [])
        if qm_field not in entries:
            entries.append(qm_field)

        all_qm_fields.add(qm_field)

    # 0. Fact table itself
    _add_table(fact_table, "fact")

    # 1. Measures -> fact table columns
    for m_name, measure in model.measures.items():
        col = measure.column or measure.name
        _add_mapping(m_name, fact_table, col)

    # 2. Simple dimensions (on fact table, not JOIN dimensions)
    join_dim_names = {jd.name for jd in model.dimension_joins}
    for dim_name, dim in model.dimensions.items():
        if dim_name in join_dim_names:
            continue  # handled below via JOIN
        _add_mapping(dim_name, fact_table, dim.column)

    # 3. Dimension JOINs (star schema)
    for jd in model.dimension_joins:
        dim_table = jd.table_name
        dim_obj = model.dimensions.get(jd.name)
        if dim_table:
            _add_table(dim_table, "dimension")

        # dim$id -> FK on fact table + PK on dimension table
        id_field = f"{jd.name}$id"
        if jd.foreign_key:
            _add_mapping(id_field, fact_table, jd.foreign_key)
        if jd.primary_key and dim_table:
            _add_mapping(id_field, dim_table, jd.primary_key)

        # dim$caption -> caption column on dimension table, or fact table for tableless/self dimensions.
        caption_table = dim_table or fact_table
        if jd.caption_column:
            cap_field = f"{jd.name}$caption"
            _add_mapping(cap_field, caption_table, jd.caption_column)
            if (
                dim_obj
                and dim_obj.data_type in {ColumnType.DATE, ColumnType.DATETIME, ColumnType.TIMESTAMP}
            ):
                _add_mapping(jd.name, caption_table, jd.caption_column)

        # dim$property -> property column on dimension table
        for prop in jd.properties:
            prop_name = prop.get_name()
            prop_field = f"{jd.name}${prop_name}"
            _add_mapping(prop_field, dim_table or fact_table, prop.column)

    # 4. Fact table properties (model.columns dict)
    for col_name, col_def in model.columns.items():
        if col_name not in all_qm_fields:
            _add_mapping(col_name, fact_table, col_def.name)

    return PhysicalColumnMapping(
        qm_to_physical=qm_to_physical,
        physical_to_qm=physical_to_qm,
        physical_tables=physical_tables,
        all_qm_fields=all_qm_fields,
    )
