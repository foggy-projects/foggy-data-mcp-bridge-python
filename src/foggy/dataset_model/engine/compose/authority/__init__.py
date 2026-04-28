"""Compose Query authority-binding pipeline (8.2.0.beta M5).

This subpackage threads the M1 ``AuthorityResolver`` SPI into the
``QueryPlan`` execution chain: collect unique ``BaseModelPlan`` nodes,
batch-call the host's resolver once, and surface the per-model
``ModelBinding`` back to downstream consumers (schema derivation,
SQL compilation, execute).

Public API
----------
* :class:`ModelInfoProvider` — host-supplied lookup for QM → physical tables
  and datasource identity. Falls back to empty ``[]`` / ``None`` when not
  provided.
* :func:`collect_base_models` — walk a plan tree, return unique
  ``BaseModelPlan`` nodes by model name (first occurrence wins).
* :func:`resolve_authority_for_plan` — top-level entry: collect → build
  ``AuthorityRequest`` → call resolver → validate response → return
  ``Dict[str, ModelBinding]`` keyed by QM model name.
* :func:`collect_datasource_ids` — walk a plan tree, return
  ``Dict[str, Optional[str]]`` of datasource identities per model (F-7).
* :func:`apply_field_access_to_schema` — convenience: filter an
  ``OutputSchema`` by a ``ModelBinding.field_access`` whitelist. Does NOT
  touch ``denied_columns`` — that filter needs v1.3 ``PhysicalColumnMapping``
  and is M6 SQL-compile scope.

Scope boundaries
----------------
* **In M5 (this subpackage)**
    - Batch resolver invocation
    - Request-level dedup (same (principal, namespace, model) ⇒ one call)
    - Fail-closed validation of resolver response
    - ``field_access`` whitelist applied to declared schema
    - Datasource identity collection (F-7)
* **Deferred to M6**
    - ``denied_columns`` physical-column filtering (needs QM mapping)
    - ``system_slice`` merge into SQL WHERE clause
"""

from __future__ import annotations

from .apply import apply_field_access_to_schema
from .collector import collect_base_models
from .datasource_ids import collect_datasource_ids
from .model_info import ModelInfoProvider, NullModelInfoProvider
from .resolver import resolve_authority_for_plan

__all__ = [
    "ModelInfoProvider",
    "NullModelInfoProvider",
    "collect_base_models",
    "collect_datasource_ids",
    "resolve_authority_for_plan",
    "apply_field_access_to_schema",
]
