"""Memory Grid contract helpers aligned with the Java P0.9 resolver cut."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, DivisionByZero, InvalidOperation
from hashlib import sha256
from typing import Any

from foggy.mcp_spi import SemanticRequestContext

UNBOUNDED_INPUT = "MEMORY_GRID_UNBOUNDED_INPUT"
UNGOVERNED_SOURCE = "MEMORY_GRID_UNGOVERNED_SOURCE"
GRAIN_MISMATCH = "MEMORY_GRID_GRAIN_MISMATCH"
LIMIT_EXCEEDED = "MEMORY_GRID_LIMIT_EXCEEDED"
RESULT_HANDLE_NOT_FOUND = "MEMORY_GRID_RESULT_HANDLE_NOT_FOUND"
RESULT_HANDLE_EXPIRED = "MEMORY_GRID_RESULT_HANDLE_EXPIRED"
NAMESPACE_MISMATCH = "MEMORY_GRID_RESULT_NAMESPACE_MISMATCH"
SOURCE_ROUTE_MISMATCH = "MEMORY_GRID_RESULT_SOURCE_ROUTE_MISMATCH"
SCHEMA_MISMATCH = "MEMORY_GRID_RESULT_SCHEMA_MISMATCH"
GOVERNANCE_MISMATCH = "MEMORY_GRID_RESULT_GOVERNANCE_MISMATCH"
STORAGE_UNAVAILABLE = "MEMORY_GRID_RESULT_STORAGE_UNAVAILABLE"

STATUS_READY = "BRIDGE_READY"
STATUS_DEFERRED = "BRIDGE_DEFERRED"

_GOVERNED_SOURCE_ROUTES = {"DSL", "DSL_CTE", "SEMANTIC_SQL"}
_MAX_INPUT_ROW_LIMIT = 500
_MAX_INPUT_COUNT = 3
_MAX_OUTPUT_LIMIT = 1000
_MAX_CELL_COUNT = 50_000
_BINARY_EXPR = re.compile(r"^\s*([A-Za-z_][\w.$]*)\s*([+\-*/])\s*([A-Za-z_][\w.$]*)\s*$")


class MemoryGridError(ValueError):
    """Fail-closed Memory Grid validation or resolver error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class MemoryGridColumn:
    name: str
    type: str = "string"
    join_allowed: bool = False
    derived_allowed: bool = False
    output_allowed: bool = False
    sensitive: bool = False


@dataclass(frozen=True)
class ResultHandleMetadata:
    handle_id: str
    namespace: str | None = None
    owner_context_hash: str | None = None
    source_route: str | None = None
    source_model_refs: list[str] = field(default_factory=list)
    query_hash: str | None = None
    created_at: Any | None = None
    expires_at: Any | None = None
    invalidated_at: Any | None = None
    row_count: int = -1
    row_limit: int = -1
    cell_count: int = -1
    byte_size: int = -1
    lineage: dict[str, Any] = field(default_factory=dict)
    storage_ref: str | None = None
    read_count: int = 0
    max_read_count: int = -1


@dataclass(frozen=True)
class ResolvedMemoryGridResult:
    result_handle: str
    source_route: str
    namespace: str | None
    grain: list[str]
    schema: dict[str, Any]
    rows: list[dict[str, Any]]
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: Any | None = None


class MemoryGridRegistryResultResolver:
    """Small in-memory resolver for tests and local parity fixtures."""

    def __init__(self) -> None:
        self._results: dict[str, ResolvedMemoryGridResult] = {}

    def register(self, result: ResolvedMemoryGridResult) -> MemoryGridRegistryResultResolver:
        self._results[result.result_handle] = result
        return self

    def resolve(
        self,
        result_handle: str,
        context: SemanticRequestContext | None = None,
    ) -> ResolvedMemoryGridResult | None:
        return self._results.get(result_handle)


@dataclass(frozen=True)
class ResultHandleRecord:
    result: ResolvedMemoryGridResult


class ResultHandleStore:
    """Result handle metadata store contract for Memory Grid."""

    def save(self, record: ResultHandleRecord) -> None:
        raise NotImplementedError

    def find(self, handle_id: str) -> ResultHandleRecord | None:
        raise NotImplementedError

    def increment_read_count(self, handle_id: str) -> None:
        raise NotImplementedError

    def invalidate(self, handle_id: str) -> None:
        raise NotImplementedError


class ResultStorageAdapter:
    """Bounded row storage contract for Memory Grid result handles."""

    def write(self, storage_ref: str, rows: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    def read(self, storage_ref: str) -> list[dict[str, Any]]:
        raise NotImplementedError


class InMemoryResultHandleStore(ResultHandleStore):
    """Scoped in-memory result handle store for tests and local parity fixtures."""

    def __init__(self) -> None:
        self._records: dict[str, ResultHandleRecord] = {}

    def save(self, record: ResultHandleRecord) -> None:
        self._records[record.result.metadata.handle_id] = record

    def find(self, handle_id: str) -> ResultHandleRecord | None:
        return self._records.get(handle_id)

    def increment_read_count(self, handle_id: str) -> None:
        record = self._records.get(handle_id)
        if record is None:
            return
        metadata = record.result.metadata
        refreshed = replace(record.result, metadata=replace(metadata, read_count=metadata.read_count + 1))
        self._records[handle_id] = ResultHandleRecord(refreshed)

    def invalidate(self, handle_id: str) -> None:
        record = self._records.get(handle_id)
        if record is None:
            return
        metadata = record.result.metadata
        refreshed = replace(record.result, metadata=replace(metadata, invalidated_at=datetime.now(UTC)))
        self._records[handle_id] = ResultHandleRecord(refreshed)


class InMemoryResultStorageAdapter(ResultStorageAdapter):
    """Scoped in-memory row storage for tests and local parity fixtures."""

    def __init__(self) -> None:
        self._rows_by_storage_ref: dict[str, list[dict[str, Any]]] = {}

    def write(self, storage_ref: str, rows: list[dict[str, Any]]) -> None:
        if not _string(storage_ref):
            raise MemoryGridError(STORAGE_UNAVAILABLE, "storage_ref is required.")
        self._rows_by_storage_ref[storage_ref] = _copy_rows(rows)

    def read(self, storage_ref: str) -> list[dict[str, Any]]:
        if not _string(storage_ref):
            raise MemoryGridError(STORAGE_UNAVAILABLE, "storage_ref is missing.")
        rows = self._rows_by_storage_ref.get(storage_ref)
        if rows is None:
            raise MemoryGridError(STORAGE_UNAVAILABLE, storage_ref)
        return _copy_rows(rows)


@dataclass(frozen=True)
class ResultHandleWriteRequest:
    source_route: str
    source_model_refs: list[str]
    query_hash: str | None
    grain: list[str]
    schema: dict[str, Any]
    rows: list[dict[str, Any]]
    lineage: dict[str, Any] = field(default_factory=dict)
    row_limit: int = -1
    cell_limit: int = -1
    ttl: timedelta = timedelta(minutes=30)
    max_read_count: int = -1


class ResultHandleWriter:
    """Writes governed bounded results and returns an opaque system-generated handle."""

    def __init__(
        self,
        store: ResultHandleStore,
        storage_adapter: ResultStorageAdapter,
        *,
        handle_supplier: Any | None = None,
        now: Any | None = None,
    ) -> None:
        self._store = store
        self._storage_adapter = storage_adapter
        self._handle_supplier = handle_supplier or (lambda: f"mgr_{uuid.uuid4().hex}")
        self._now = now or (lambda: datetime.now(UTC))

    def write(self, request: ResultHandleWriteRequest, context: SemanticRequestContext | None = None) -> str:
        if request is None:
            raise MemoryGridError(GOVERNANCE_MISMATCH, "result handle write request is required.")
        if not _normalize_route(request.source_route):
            raise MemoryGridError(GOVERNANCE_MISMATCH, "source_route is required.")
        if not request.schema:
            raise MemoryGridError(SCHEMA_MISMATCH, "schema is required.")
        if request.rows is None:
            raise MemoryGridError(GOVERNANCE_MISMATCH, "rows are required.")
        if request.row_limit <= 0 or len(request.rows) > request.row_limit:
            raise MemoryGridError(GOVERNANCE_MISMATCH, "rows exceed row_limit.")
        cell_count = _cell_count(request.rows)
        if request.cell_limit > 0 and cell_count > request.cell_limit:
            raise MemoryGridError(GOVERNANCE_MISMATCH, "rows exceed cell_limit.")
        if request.ttl.total_seconds() <= 0:
            raise MemoryGridError(GOVERNANCE_MISMATCH, "positive ttl is required.")

        handle = _string(self._handle_supplier())
        if not handle:
            raise MemoryGridError(GOVERNANCE_MISMATCH, "generated result_handle is blank.")
        created_at = self._now()
        storage_ref = f"memory-grid://result/{handle}"
        self._storage_adapter.write(storage_ref, request.rows)
        metadata = ResultHandleMetadata(
            handle_id=handle,
            namespace=getattr(context, "namespace", None),
            owner_context_hash=_owner_context_hash(context),
            source_route=_normalize_route(request.source_route),
            source_model_refs=list(request.source_model_refs or []),
            query_hash=request.query_hash,
            created_at=created_at,
            expires_at=created_at + request.ttl,
            row_count=len(request.rows),
            row_limit=request.row_limit,
            cell_count=cell_count,
            byte_size=len(str(request.rows).encode("utf-8")),
            lineage=dict(request.lineage or {}),
            storage_ref=storage_ref,
            read_count=0,
            max_read_count=request.max_read_count,
        )
        result = ResolvedMemoryGridResult(
            result_handle=handle,
            source_route=_normalize_route(request.source_route) or request.source_route,
            namespace=getattr(context, "namespace", None),
            grain=list(request.grain or []),
            schema=dict(request.schema),
            rows=[],
            lineage=dict(request.lineage or {}),
            metadata=metadata,
        )
        self._store.save(ResultHandleRecord(result))
        return handle


class MemoryGridStoreBackedResultResolver:
    """Store-backed resolver for production Memory Grid handles."""

    def __init__(self, store: ResultHandleStore, storage_adapter: ResultStorageAdapter) -> None:
        self._store = store
        self._storage_adapter = storage_adapter

    def resolve(
        self,
        result_handle: str,
        context: SemanticRequestContext | None = None,
    ) -> ResolvedMemoryGridResult | None:
        handle = _string(result_handle)
        if not handle:
            raise MemoryGridError(RESULT_HANDLE_NOT_FOUND, "result_handle is missing.")
        record = self._store.find(handle)
        if record is None:
            raise MemoryGridError(RESULT_HANDLE_NOT_FOUND, handle)
        metadata = record.result.metadata
        if _parse_datetime(metadata.invalidated_at) is not None:
            raise MemoryGridError(RESULT_HANDLE_EXPIRED, f"{handle} is invalidated.")
        expires_at = _parse_datetime(metadata.expires_at)
        if expires_at is not None and expires_at < datetime.now(UTC):
            raise MemoryGridError(RESULT_HANDLE_EXPIRED, handle)
        if metadata.max_read_count >= 0 and metadata.read_count >= metadata.max_read_count:
            raise MemoryGridError(GOVERNANCE_MISMATCH, f"resolver read_count exceeds max_read_count for {handle}.")
        rows = self._storage_adapter.read(metadata.storage_ref)
        self._store.increment_read_count(handle)
        refreshed = self._store.find(handle) or record
        return replace(refreshed.result, rows=rows)


@dataclass(frozen=True)
class DerivedFormula:
    name: str
    left: str
    operator: str
    right: str


@dataclass(frozen=True)
class BridgePlan:
    status: str
    unsupported: list[str]
    join_keys: list[str]
    derived: list[DerivedFormula]
    output_limit: int
    output_columns: list[str]

    @property
    def ready(self) -> bool:
        return self.status == STATUS_READY


def validate_memory_grid_plan(
    plan: dict[str, Any] | None,
    context: SemanticRequestContext | None = None,
) -> dict[str, Any]:
    if not plan:
        raise MemoryGridError(UNBOUNDED_INPUT, "memory_grid_plan must be provided.")

    inputs = _input_plans(plan.get("inputs"))
    if not inputs:
        raise MemoryGridError(UNBOUNDED_INPUT, "memory_grid_plan.inputs must be non-empty.")
    if len(inputs) > _MAX_INPUT_COUNT:
        raise MemoryGridError(LIMIT_EXCEEDED, "memory grid input count exceeds phase-1 limit.")

    estimated_cells = 0
    input_evidence: list[dict[str, Any]] = []
    governed_routes: list[str] = []
    grains: list[str] = []
    for idx, input_plan in enumerate(inputs, start=1):
        source_route = _normalize_route(input_plan.get("source_route"))
        if source_route not in _GOVERNED_SOURCE_ROUTES or input_plan.get("governed") is not True:
            raise MemoryGridError(
                UNGOVERNED_SOURCE,
                f"input {idx} must come from governed DSL/DSL_CTE/Semantic SQL result.",
            )
        if not _string(input_plan.get("result_handle")):
            raise MemoryGridError(UNGOVERNED_SOURCE, f"input {idx} must declare governed result_handle.")

        row_limit = _int(input_plan.get("row_limit"))
        if row_limit is None or row_limit <= 0:
            raise MemoryGridError(UNBOUNDED_INPUT, f"input {idx} must declare positive row_limit.")
        if row_limit > _MAX_INPUT_ROW_LIMIT:
            raise MemoryGridError(LIMIT_EXCEEDED, f"input {idx} row_limit exceeds phase-1 limit.")

        grain = _string_list(input_plan.get("grain"))
        if not grain:
            raise MemoryGridError(GRAIN_MISMATCH, f"input {idx} grain must be declared.")
        _ensure_fields_allowed(grain, context)

        metrics = _list(input_plan.get("metrics"))
        estimated_cells += row_limit * (len(grain) + len(metrics))
        input_evidence.append({
            "name": _string(input_plan.get("name")) or f"input_{idx}",
            "source_route": source_route,
            "row_limit": row_limit,
            "grain": grain,
            "governed": True,
        })
        if source_route not in governed_routes:
            governed_routes.append(source_route)
        for grain_field in grain:
            if grain_field not in grains:
                grains.append(grain_field)

    if estimated_cells > _MAX_CELL_COUNT:
        raise MemoryGridError(LIMIT_EXCEEDED, "estimated input cells exceed phase-1 limit.")

    output_limit = _int(plan.get("output_limit"))
    if output_limit is None or output_limit <= 0:
        raise MemoryGridError(UNBOUNDED_INPUT, "output_limit must be declared.")
    if output_limit > _MAX_OUTPUT_LIMIT:
        raise MemoryGridError(LIMIT_EXCEEDED, "output_limit exceeds phase-1 limit.")

    join = _dict(plan.get("join"))
    join_keys = _string_list(join.get("keys") if join else None)
    if not join_keys:
        raise MemoryGridError(GRAIN_MISMATCH, "memory grid join keys must be declared.")
    _ensure_fields_allowed(join_keys, context)
    for idx, input_plan in enumerate(inputs, start=1):
        if not set(join_keys).issubset(set(_string_list(input_plan.get("grain")))):
            raise MemoryGridError(GRAIN_MISMATCH, f"input {idx} grain must contain every memory grid join key.")

    if not _list(plan.get("derived")):
        raise MemoryGridError(GRAIN_MISMATCH, "memory grid derived formula must be declared.")

    return {
        "inputs": input_evidence,
        "governed_source_routes": governed_routes,
        "grain": grains,
        "join_keys": join_keys,
        "output_limit": output_limit,
        "estimated_input_cells": estimated_cells,
        "limits": {
            "max_input_row_limit": _MAX_INPUT_ROW_LIMIT,
            "max_input_count": _MAX_INPUT_COUNT,
            "max_output_limit": _MAX_OUTPUT_LIMIT,
            "max_cell_count": _MAX_CELL_COUNT,
        },
        "denied": [],
    }


def plan_memory_grid_bridge(plan: dict[str, Any] | None) -> BridgePlan:
    unsupported: list[str] = []
    if not plan:
        return BridgePlan(STATUS_DEFERRED, ["memory_grid_plan must be provided"], [], [], 0, [])
    if "rows" in plan:
        unsupported.append("memory grid execution does not accept request-provided rows")

    inputs = [_dict(item) for item in _list(plan.get("inputs")) if _dict(item) is not None]
    if len(inputs) != 2:
        unsupported.append("Memory Grid bridge v1 requires exactly two inputs")
    for input_plan in inputs:
        if "rows" in input_plan:
            unsupported.append(f"memory grid input rows must come from result resolver: {_input_name(input_plan)}")

    join = _dict(plan.get("join"))
    join_type = (_string(join.get("type")) if join else None)
    if (join_type or "").lower() != "inner":
        unsupported.append("Memory Grid bridge v1 supports inner join only")
    join_keys = _string_list(join.get("keys") if join else None)
    if len(join_keys) != 1:
        unsupported.append("Memory Grid bridge v1 requires a single join key")

    derived = _derived_formulas(plan.get("derived"), unsupported)
    if not derived:
        unsupported.append("Memory Grid bridge v1 requires at least one binary numeric derived formula")

    output_limit = _int(plan.get("output_limit"))
    if output_limit is None or output_limit <= 0:
        unsupported.append("Memory Grid bridge v1 requires positive output_limit")

    output_columns = _output_columns(plan.get("output"), inputs, join_keys, derived)
    if not output_columns:
        unsupported.append("Memory Grid bridge v1 requires output columns")

    if unsupported:
        return BridgePlan(STATUS_DEFERRED, unsupported, [], [], 0, [])
    return BridgePlan(STATUS_READY, [], join_keys, derived, output_limit or 0, output_columns)


def append_memory_grid_bridge_evidence(validation: dict[str, Any], bridge_plan: BridgePlan) -> None:
    validation["memory_grid_bridge_status"] = bridge_plan.status
    if bridge_plan.ready:
        validation["memory_grid_bridge_output"] = list(bridge_plan.output_columns)
        validation["memory_grid_bridge_derived"] = [formula.name for formula in bridge_plan.derived]
    else:
        validation["memory_grid_bridge_unsupported"] = list(bridge_plan.unsupported)


def execute_memory_grid(
    plan: dict[str, Any],
    bridge_plan: BridgePlan,
    resolver: Any,
    context: SemanticRequestContext | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if resolver is None:
        raise MemoryGridError(RESULT_HANDLE_NOT_FOUND, "no MemoryGridResultResolver is configured.")
    inputs = [_dict(item) for item in _list(plan.get("inputs")) if _dict(item) is not None]
    left = _resolve(inputs[0], resolver, context)
    right = _resolve(inputs[1], resolver, context)
    join_key = bridge_plan.join_keys[0]
    _validate_resolved_input(inputs[0], left, join_key, context)
    _validate_resolved_input(inputs[1], right, join_key, context)
    _validate_global_columns(left, right, bridge_plan)

    right_rows_by_key: dict[Any, list[dict[str, Any]]] = {}
    for row in right.rows:
        right_rows_by_key.setdefault(row.get(join_key), []).append(row)

    output: list[dict[str, Any]] = []
    for left_row in left.rows:
        for right_row in right_rows_by_key.get(left_row.get(join_key), []):
            combined = dict(left_row)
            for key, value in right_row.items():
                combined.setdefault(key, value)
            for formula in bridge_plan.derived:
                combined[formula.name] = _evaluate(formula, combined)
            output.append({column: combined.get(column) for column in bridge_plan.output_columns})
            if len(output) >= bridge_plan.output_limit:
                return output, _summary(plan, bridge_plan, left, right, len(output), True)
    return output, _summary(plan, bridge_plan, left, right, len(output), False)


def _resolve(input_plan: dict[str, Any], resolver: Any, context: SemanticRequestContext | None) -> ResolvedMemoryGridResult:
    handle = _string(input_plan.get("result_handle"))
    if not handle:
        raise MemoryGridError(RESULT_HANDLE_NOT_FOUND, "memory grid input result_handle is missing.")
    if hasattr(resolver, "resolve"):
        result = resolver.resolve(handle, context)
    elif callable(resolver):
        result = resolver(handle, context)
    else:
        result = None
    if result is None:
        raise MemoryGridError(RESULT_HANDLE_NOT_FOUND, handle)
    result = _coerce_result(result)
    if not result.schema:
        raise MemoryGridError(SCHEMA_MISMATCH, f"resolver schema is missing for {handle}.")
    if result.rows is None:
        raise MemoryGridError(GOVERNANCE_MISMATCH, f"resolver rows are missing for {handle}.")
    return result


def _validate_resolved_input(
    input_plan: dict[str, Any],
    result: ResolvedMemoryGridResult,
    join_key: str,
    context: SemanticRequestContext | None,
) -> None:
    handle = _string(input_plan.get("result_handle"))
    if handle != result.result_handle:
        raise MemoryGridError(GOVERNANCE_MISMATCH, "resolver returned mismatched result_handle.")
    _validate_metadata(input_plan, result, context)
    expected_route = _normalize_route(input_plan.get("source_route"))
    actual_route = _normalize_route(result.source_route)
    if not expected_route:
        raise MemoryGridError(GOVERNANCE_MISMATCH, f"input source_route is missing for {handle}.")
    if actual_route and expected_route != actual_route:
        raise MemoryGridError(SOURCE_ROUTE_MISMATCH, f"resolver returned mismatched source_route for {handle}.")
    row_limit = _int(input_plan.get("row_limit"))
    if row_limit is not None and len(result.rows) > row_limit:
        raise MemoryGridError(GOVERNANCE_MISMATCH, f"resolver row count exceeds declared row_limit for {handle}.")
    _require_column(result, join_key, join=True, derived=False, output=True)
    for metric in _metric_names(input_plan):
        _require_column(result, metric, join=False, derived=True, output=True)


def _validate_metadata(
    input_plan: dict[str, Any],
    result: ResolvedMemoryGridResult,
    context: SemanticRequestContext | None,
) -> None:
    metadata = _metadata_dict(result.metadata)
    if not metadata:
        return
    handle = _string(input_plan.get("result_handle"))
    metadata_handle = _first_non_blank(_get(metadata, "handle_id", "handleId"), _get(metadata, "result_handle", "resultHandle"))
    if metadata_handle and metadata_handle != result.result_handle:
        raise MemoryGridError(GOVERNANCE_MISMATCH, f"resolver metadata handle_id mismatch for {handle}.")

    expires_at = _parse_datetime(_get(metadata, "expires_at", "expiresAt"))
    if expires_at is not None and expires_at < datetime.now(UTC):
        raise MemoryGridError(RESULT_HANDLE_EXPIRED, str(handle))
    invalidated_at = _parse_datetime(_get(metadata, "invalidated_at", "invalidatedAt"))
    if invalidated_at is not None:
        raise MemoryGridError(RESULT_HANDLE_EXPIRED, f"{handle} is invalidated.")

    request_namespace = _normalize_namespace(getattr(context, "namespace", None))
    result_namespace = _normalize_namespace(_first_non_blank(_get(metadata, "namespace"), result.namespace))
    if result_namespace != request_namespace:
        raise MemoryGridError(NAMESPACE_MISMATCH, f"resolver namespace does not match request namespace for {handle}.")

    expected_route = _normalize_route(input_plan.get("source_route"))
    metadata_route = _normalize_route(_first_non_blank(_get(metadata, "source_route", "sourceRoute"), result.source_route))
    if expected_route and metadata_route and expected_route != metadata_route:
        raise MemoryGridError(SOURCE_ROUTE_MISMATCH, f"resolver metadata source_route mismatch for {handle}.")

    row_count = _int(_get(metadata, "row_count", "rowCount"))
    if row_count is not None and row_count >= 0 and row_count != len(result.rows):
        raise MemoryGridError(GOVERNANCE_MISMATCH, f"resolver metadata row_count mismatch for {handle}.")
    row_limit = _int(_get(metadata, "row_limit", "rowLimit"))
    if row_limit is not None and row_limit >= 0 and len(result.rows) > row_limit:
        raise MemoryGridError(GOVERNANCE_MISMATCH, f"resolver rows exceed metadata row_limit for {handle}.")
    cell_count = _int(_get(metadata, "cell_count", "cellCount"))
    if cell_count is not None and cell_count >= 0 and cell_count != _cell_count(result.rows):
        raise MemoryGridError(GOVERNANCE_MISMATCH, f"resolver metadata cell_count mismatch for {handle}.")
    read_count = _int(_get(metadata, "read_count", "readCount"))
    max_read_count = _int(_get(metadata, "max_read_count", "maxReadCount"))
    if read_count is not None and max_read_count is not None and max_read_count >= 0 and read_count > max_read_count:
        raise MemoryGridError(GOVERNANCE_MISMATCH, f"resolver read_count exceeds max_read_count for {handle}.")
    storage_ref = _string(_get(metadata, "storage_ref", "storageRef"))
    if not storage_ref:
        raise MemoryGridError(STORAGE_UNAVAILABLE, f"resolver metadata storage_ref is missing for {handle}.")


def _validate_global_columns(
    left: ResolvedMemoryGridResult,
    right: ResolvedMemoryGridResult,
    bridge_plan: BridgePlan,
) -> None:
    for formula in bridge_plan.derived:
        if not (_contains_derived(left, formula.left) or _contains_derived(right, formula.left)):
            raise MemoryGridError(SCHEMA_MISMATCH, f"derived operand is not available: {formula.left}")
        if not (_contains_derived(left, formula.right) or _contains_derived(right, formula.right)):
            raise MemoryGridError(SCHEMA_MISMATCH, f"derived operand is not available: {formula.right}")
    derived_names = {formula.name for formula in bridge_plan.derived}
    for output in bridge_plan.output_columns:
        if output in derived_names:
            continue
        if not (_contains_output(left, output) or _contains_output(right, output)):
            raise MemoryGridError(SCHEMA_MISMATCH, f"output column is not available: {output}")


def _require_column(
    result: ResolvedMemoryGridResult,
    name: str,
    *,
    join: bool,
    derived: bool,
    output: bool,
) -> None:
    column = _column_dict(result.schema.get(name))
    if not column:
        raise MemoryGridError(SCHEMA_MISMATCH, f"column is not available: {name}")
    if join and not bool(_get(column, "join_allowed", "joinAllowed")):
        raise MemoryGridError(GOVERNANCE_MISMATCH, f"column is not join-allowed: {name}")
    if bool(_get(column, "sensitive")) and (derived or output):
        raise MemoryGridError(GOVERNANCE_MISMATCH, f"sensitive column cannot be used in Memory Grid output or derived expression: {name}")
    if derived and not bool(_get(column, "derived_allowed", "derivedAllowed")):
        raise MemoryGridError(GOVERNANCE_MISMATCH, f"column is not derived-allowed: {name}")
    if output and not bool(_get(column, "output_allowed", "outputAllowed")):
        raise MemoryGridError(GOVERNANCE_MISMATCH, f"column is not output-allowed: {name}")


def _contains_derived(result: ResolvedMemoryGridResult, name: str) -> bool:
    column = _column_dict(result.schema.get(name))
    return bool(column and _get(column, "derived_allowed", "derivedAllowed") and not _get(column, "sensitive"))


def _contains_output(result: ResolvedMemoryGridResult, name: str) -> bool:
    column = _column_dict(result.schema.get(name))
    return bool(column and _get(column, "output_allowed", "outputAllowed") and not _get(column, "sensitive"))


def _summary(
    plan: dict[str, Any],
    bridge_plan: BridgePlan,
    left: ResolvedMemoryGridResult,
    right: ResolvedMemoryGridResult,
    output_rows: int,
    output_limited: bool,
) -> dict[str, Any]:
    return {
        "memory_grid_bridge_status": bridge_plan.status,
        "result_handles": [left.result_handle, right.result_handle],
        "input_row_counts": [len(left.rows), len(right.rows)],
        "join_type": (_dict(plan.get("join")) or {}).get("type"),
        "join_keys": list(bridge_plan.join_keys),
        "derived": [formula.name for formula in bridge_plan.derived],
        "output_rows": output_rows,
        "output_limited": output_limited,
        "resolver_audit": [_audit(left), _audit(right)],
    }


def _audit(result: ResolvedMemoryGridResult) -> dict[str, Any]:
    metadata = _metadata_dict(result.metadata)
    audit = {
        "result_handle": result.result_handle,
        "row_count": len(result.rows),
    }
    if metadata:
        audit.update({
            "source_route": _first_non_blank(_get(metadata, "source_route", "sourceRoute"), result.source_route),
            "namespace": _first_non_blank(_get(metadata, "namespace"), result.namespace),
            "query_hash": _get(metadata, "query_hash", "queryHash"),
            "storage_ref": _get(metadata, "storage_ref", "storageRef"),
            "expires_at": _string(_get(metadata, "expires_at", "expiresAt")),
            "source_model_refs": _get(metadata, "source_model_refs", "sourceModelRefs") or [],
            "read_count": _get(metadata, "read_count", "readCount"),
            "cell_count": _get(metadata, "cell_count", "cellCount"),
        })
    else:
        audit.update({"source_route": result.source_route, "namespace": result.namespace})
    return audit


def _evaluate(formula: DerivedFormula, row: dict[str, Any]) -> float | None:
    try:
        left = Decimal(str(row.get(formula.left)))
        right = Decimal(str(row.get(formula.right)))
    except (InvalidOperation, TypeError):
        return None
    try:
        if formula.operator == "+":
            value = left + right
        elif formula.operator == "-":
            value = left - right
        elif formula.operator == "*":
            value = left * right
        elif formula.operator == "/":
            value = None if right == 0 else left / right
        else:
            value = None
    except (DivisionByZero, InvalidOperation):
        value = None
    return None if value is None else float(value)


def _derived_formulas(raw: Any, unsupported: list[str]) -> list[DerivedFormula]:
    result: list[DerivedFormula] = []
    for item in _list(raw):
        derived = _dict(item)
        if not derived:
            unsupported.append(f"derived entries must be objects: {item}")
            continue
        name = _string(derived.get("name"))
        expr = _string(derived.get("expr"))
        match = _BINARY_EXPR.match(expr or "")
        if not name or match is None:
            unsupported.append(f"derived formula is not executable through Memory Grid bridge v1: {derived}")
            continue
        result.append(DerivedFormula(name, match.group(1), match.group(2), match.group(3)))
    return result


def _output_columns(
    raw_output: Any,
    inputs: list[dict[str, Any]],
    join_keys: list[str],
    derived: list[DerivedFormula],
) -> list[str]:
    declared = _string_list(raw_output)
    if declared:
        return declared
    columns: list[str] = []
    for field_name in join_keys:
        if field_name not in columns:
            columns.append(field_name)
    for input_plan in inputs:
        for metric in _list(input_plan.get("metrics")):
            metric_map = _dict(metric)
            name = _string(metric_map.get("name")) if metric_map else None
            if name and name not in columns:
                columns.append(name)
    for formula in derived:
        if formula.name not in columns:
            columns.append(formula.name)
    return columns


def _coerce_result(value: Any) -> ResolvedMemoryGridResult:
    if isinstance(value, ResolvedMemoryGridResult):
        return value
    if isinstance(value, dict):
        return ResolvedMemoryGridResult(
            result_handle=_string(_get(value, "result_handle", "resultHandle")) or "",
            source_route=_string(_get(value, "source_route", "sourceRoute")) or "",
            namespace=_string(_get(value, "namespace")),
            grain=_string_list(_get(value, "grain")),
            schema=_get(value, "schema") or {},
            rows=_get(value, "rows") or [],
            lineage=_get(value, "lineage") or {},
            metadata=_get(value, "metadata"),
        )
    return value


def _metadata_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, ResultHandleMetadata):
        return {
            "handle_id": value.handle_id,
            "namespace": value.namespace,
            "owner_context_hash": value.owner_context_hash,
            "source_route": value.source_route,
            "source_model_refs": value.source_model_refs,
            "query_hash": value.query_hash,
            "created_at": value.created_at,
            "expires_at": value.expires_at,
            "invalidated_at": value.invalidated_at,
            "row_count": value.row_count,
            "row_limit": value.row_limit,
            "cell_count": value.cell_count,
            "byte_size": value.byte_size,
            "lineage": value.lineage,
            "storage_ref": value.storage_ref,
            "read_count": value.read_count,
            "max_read_count": value.max_read_count,
        }
    if isinstance(value, dict):
        return value
    return getattr(value, "__dict__", {}) or {}


def _column_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, MemoryGridColumn):
        return {
            "name": value.name,
            "type": value.type,
            "join_allowed": value.join_allowed,
            "derived_allowed": value.derived_allowed,
            "output_allowed": value.output_allowed,
            "sensitive": value.sensitive,
        }
    if isinstance(value, dict):
        return value
    return getattr(value, "__dict__", {}) or {}


def _ensure_fields_allowed(fields: list[str], context: SemanticRequestContext | None) -> None:
    field_access = getattr(context, "field_access", None)
    visible = getattr(field_access, "visible", None) if field_access is not None else None
    if not visible:
        return
    allowed = set(visible)
    for field_name in fields:
        if field_name not in allowed:
            raise MemoryGridError(UNGOVERNED_SOURCE, f"field '{field_name}' is denied by semantic field access policy.")


def _input_plans(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _list(value):
        item_dict = _dict(item)
        if item_dict is None:
            raise MemoryGridError(UNBOUNDED_INPUT, "memory grid inputs must be objects.")
        result.append(item_dict)
    return result


def _metric_names(input_plan: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for metric in _list(input_plan.get("metrics")):
        metric_map = _dict(metric)
        name = _string(metric_map.get("name")) if metric_map else None
        if name:
            names.append(name)
    return names


def _input_name(input_plan: dict[str, Any]) -> str:
    return _string(input_plan.get("name")) or "input"


def _dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in _list(value) if str(item).strip()]


def _copy_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if rows is None:
        return []
    return [dict(row or {}) for row in rows]


def _cell_count(rows: list[dict[str, Any]] | None) -> int:
    return sum(len(row or {}) for row in rows or [])


def _owner_context_hash(context: SemanticRequestContext | None) -> str:
    seed = ""
    if context is not None:
        seed = "|".join(
            [
                str(getattr(context, "namespace", None)),
                str(getattr(context, "authorization", None)),
                str(getattr(context, "field_access", None)),
            ]
        )
    return "sha256:" + sha256(seed.encode("utf-8")).hexdigest()


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = _string(value)
    if text:
        try:
            return int(text)
        except ValueError:
            return None
    return None


def _normalize_route(value: Any) -> str | None:
    text = _string(value)
    return text.upper() if text else None


def _normalize_namespace(value: Any) -> str | None:
    return _string(value)


def _first_non_blank(*values: Any) -> str | None:
    for value in values:
        text = _string(value)
        if text:
            return text
    return None


def _get(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = _string(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


__all__ = [
    "BridgePlan",
    "DerivedFormula",
    "GOVERNANCE_MISMATCH",
    "GRAIN_MISMATCH",
    "InMemoryResultHandleStore",
    "InMemoryResultStorageAdapter",
    "LIMIT_EXCEEDED",
    "MemoryGridColumn",
    "MemoryGridError",
    "MemoryGridRegistryResultResolver",
    "MemoryGridStoreBackedResultResolver",
    "NAMESPACE_MISMATCH",
    "ResolvedMemoryGridResult",
    "ResultHandleRecord",
    "ResultHandleStore",
    "ResultHandleWriteRequest",
    "ResultHandleMetadata",
    "ResultHandleWriter",
    "ResultStorageAdapter",
    "RESULT_HANDLE_EXPIRED",
    "RESULT_HANDLE_NOT_FOUND",
    "SCHEMA_MISMATCH",
    "SOURCE_ROUTE_MISMATCH",
    "STATUS_DEFERRED",
    "STATUS_READY",
    "STORAGE_UNAVAILABLE",
    "UNBOUNDED_INPUT",
    "UNGOVERNED_SOURCE",
    "append_memory_grid_bridge_evidence",
    "execute_memory_grid",
    "plan_memory_grid_bridge",
    "validate_memory_grid_plan",
]
