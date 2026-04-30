"""Request-scoped resolver for host-pushed remote compose authority bindings.

The envelope is produced by foggy-odoo-bridge-pro and injected as a
host-private MCP argument. This resolver validates the envelope and converts
each per-model binding into the native compose :class:`ModelBinding`
contract. Any malformed or divergent authority input fails closed.

Constructor-time validation
---------------------------
Version, issuer, namespace, principal shape, and bindings shape are
validated eagerly in ``__init__``. If the envelope is structurally invalid,
the resolver object is never created — call sites that construct the
resolver in a try/except will surface the error immediately.

This mirrors the Java ``AuthorityBindingResolver`` constructor which calls
``validateTopLevelEnvelope()`` during construction.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from foggy.dataset_model.engine.compose.security import (
    AuthorityResolver,
    AuthorityRequest,
    AuthorityResolution,
    ModelBinding,
    AuthorityResolutionError,
    error_codes,
)
from foggy.mcp_spi.semantic import DeniedColumn


# Frozen protocol constants — must match Java AuthorityBindingResolver
VERSION = "foggy.compose.authority-binding.v1"
ISSUER_ODOO_BRIDGE = "foggy-odoo-bridge-pro"
ISSUER_TEST_FIXTURE = "test-fixture-issuer"
_ALLOWED_ISSUERS = frozenset({ISSUER_ODOO_BRIDGE, ISSUER_TEST_FIXTURE})


class AuthorityBindingResolver(AuthorityResolver):
    """A request-scoped static authority resolver that consumes a pre-computed
    Authority Binding Push envelope from the Odoo gateway.

    Envelope validation happens at construction time — if the envelope is
    structurally invalid (wrong version, unknown issuer, namespace mismatch,
    missing principal/bindings), the constructor raises
    :class:`AuthorityResolutionError` and no resolver instance is created.
    """

    def __init__(self, envelope: Any, expected_namespace: str) -> None:
        if not isinstance(envelope, dict):
            raise _invalid("authority binding envelope must be a dictionary", None)

        self._expected_namespace = _normalize_optional(expected_namespace)
        self._envelope: Dict[str, Any] = envelope

        # Validate top-level envelope structure eagerly (mirrors Java ctor)
        self._validate_top_level_envelope()

        # Extract and validate principal and bindings shapes
        principal = envelope.get("principal")
        if not isinstance(principal, dict):
            raise _invalid(
                "authority binding envelope is missing a valid principal dictionary",
                None,
            )
        self._principal: Dict[str, Any] = principal

        bindings = envelope.get("bindings")
        if not isinstance(bindings, dict):
            raise _invalid("envelope bindings must be a dictionary", None)
        self._bindings: Dict[str, Any] = bindings

    # ------------------------------------------------------------------
    # AuthorityResolver protocol
    # ------------------------------------------------------------------

    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        if request is None:
            raise _invalid("authority request is required", None)

        self._validate_request_identity(request)

        result_bindings: Dict[str, ModelBinding] = {}
        for mq in request.models:
            if mq.model not in self._bindings:
                raise AuthorityResolutionError(
                    code=error_codes.MODEL_BINDING_MISSING,
                    message=f"authority binding missing for requested model",
                    model_involved=mq.model,
                    phase=error_codes.PHASE_AUTHORITY_RESOLVE,
                )
            raw_binding = self._bindings[mq.model]
            if not isinstance(raw_binding, dict):
                raise _invalid(
                    f"binding for {mq.model} must be a dictionary", mq.model
                )
            result_bindings[mq.model] = self._parse_model_binding(
                mq.model, raw_binding
            )

        return AuthorityResolution(bindings=result_bindings)

    # ------------------------------------------------------------------
    # Top-level envelope validation (called from __init__)
    # ------------------------------------------------------------------

    def _validate_top_level_envelope(self) -> None:
        version = _require_non_blank_string(
            self._envelope.get("version"), "version", None
        )
        if version != VERSION:
            raise _invalid("unsupported authority binding version", None)

        issuer = _require_non_blank_string(
            self._envelope.get("issuer"), "issuer", None
        )
        if issuer not in _ALLOWED_ISSUERS:
            raise _invalid(
                f"unsupported authority binding issuer: {issuer}", None
            )

        namespace = _require_non_blank_string(
            self._envelope.get("namespace"), "namespace", None
        )
        if (
            self._expected_namespace is not None
            and self._expected_namespace != namespace
        ):
            raise _invalid("authority binding namespace mismatch", None)

    # ------------------------------------------------------------------
    # Request identity validation (mirrors Java validateRequestIdentity)
    # ------------------------------------------------------------------

    def _validate_request_identity(self, request: AuthorityRequest) -> None:
        # Namespace must match
        envelope_namespace = _require_non_blank_string(
            self._envelope.get("namespace"), "namespace", None
        )
        req_namespace = _normalize_optional(request.namespace)
        if envelope_namespace != req_namespace:
            raise _invalid(
                "request namespace differs from authority binding", None
            )

        # Principal userId must match
        binding_user_id = _require_non_blank_string(
            _read_either(self._principal, "userId", "user_id"),
            "principal.userId",
            None,
        )
        req_user_id = (
            request.principal.user_id if request.principal else None
        )
        if binding_user_id != str(req_user_id) if req_user_id is not None else True:
            # More precise check: compare normalised strings
            if str(binding_user_id) != str(req_user_id):
                raise _principal_mismatch(
                    "authority binding principal differs from request principal"
                )

        # Tenant: dual-source diverge detection (mirrors Java L107-115)
        principal_tenant = _normalize_optional(
            _read_either(self._principal, "tenantId", "tenant_id")
        )
        envelope_tenant = _normalize_optional(
            _read_either(self._envelope, "tenantId", "tenant_id")
        )

        # If both sources provide tenant and they disagree → diverge error
        if (
            principal_tenant is not None
            and envelope_tenant is not None
            and principal_tenant != envelope_tenant
        ):
            raise _principal_mismatch(
                "authority binding tenant fields diverge"
            )

        # Merge: prefer principal-level, fall back to envelope-level
        binding_tenant = (
            principal_tenant if principal_tenant is not None else envelope_tenant
        )
        req_tenant_id = _normalize_optional(
            request.principal.tenant_id if request.principal else None
        )

        if binding_tenant is not None and binding_tenant != req_tenant_id:
            raise _principal_mismatch(
                "authority binding tenant differs from request principal"
            )

    # ------------------------------------------------------------------
    # Per-model binding parsing
    # ------------------------------------------------------------------

    def _parse_model_binding(
        self, model_name: str, binding_data: Dict[str, Any]
    ) -> ModelBinding:
        return ModelBinding(
            field_access=self._parse_field_access(
                binding_data.get("fieldAccess"), model_name
            ),
            denied_columns=self._parse_denied_columns(
                binding_data.get("deniedColumns"), model_name
            ),
            system_slice=self._parse_system_slice(
                binding_data.get("systemSlice"), model_name
            ),
        )

    def _parse_field_access(
        self, raw: Any, model_name: str
    ) -> Optional[List[str]]:
        if raw is None:
            return None
        if not isinstance(raw, list):
            raise _invalid(
                f"fieldAccess must be a list or null", model_name
            )
        result: List[str] = []
        for item in raw:
            if not isinstance(item, str):
                raise _invalid(
                    "fieldAccess item must be a string", model_name
                )
            field = _require_non_blank_string(item, "fieldAccess item", model_name)
            result.append(field)
        return result

    def _parse_denied_columns(
        self, raw: Any, model_name: str
    ) -> List[DeniedColumn]:
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise _invalid(
                f"deniedColumns must be a list", model_name
            )
        result: List[DeniedColumn] = []
        for dc in raw:
            if not isinstance(dc, dict) or "table" not in dc or "column" not in dc:
                raise _invalid(
                    f"deniedColumns entry must be a dict with 'table' and 'column'",
                    model_name,
                )
            table_val = _require_non_blank_string(
                dc["table"], "deniedColumns.table", model_name
            )
            column_val = _require_non_blank_string(
                dc["column"], "deniedColumns.column", model_name
            )
            schema_val = dc.get("schema") or dc.get("schema_name")
            schema_val = (
                str(schema_val).strip() if schema_val is not None else None
            )
            # Normalise whitespace-only schema to None
            if schema_val is not None and not schema_val:
                schema_val = None
            result.append(
                DeniedColumn(
                    table=table_val, column=column_val, schema_name=schema_val
                )
            )
        return result

    def _parse_system_slice(
        self, raw: Any, model_name: str
    ) -> List[Any]:
        """Parse and validate systemSlice entries.

        Each entry must be a dict. Leaf conditions require ``field`` + ``op``
        (or ``type``). Logical groups (``$or`` / ``$and``) must contain a list.
        ``$expr`` must be a non-blank string. This mirrors Java's
        ``parseCondition()`` / ``parseConditionList()`` structure.

        The output is still ``List[Any]`` (plain dicts) — we validate
        structure here but do not convert to a dedicated dataclass. This
        keeps the ``ModelBinding.system_slice`` type signature unchanged
        and avoids impacting downstream SQL compilation code.
        """
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise _invalid(
                f"systemSlice must be a list", model_name
            )
        result: List[Any] = []
        for item in raw:
            self._validate_condition(item, model_name)
            result.append(item)
        return result

    def _validate_condition(self, raw: Any, model_name: str) -> None:
        """Recursively validate a single systemSlice condition entry."""
        if not isinstance(raw, dict):
            raise _invalid("systemSlice item must be a dictionary", model_name)

        # Logical groups: $or / $and
        if "$or" in raw:
            or_val = raw["$or"]
            if not isinstance(or_val, list):
                raise _invalid(
                    "systemSlice.$or must be a list", model_name
                )
            for child in or_val:
                self._validate_condition(child, model_name)
            return

        if "$and" in raw:
            and_val = raw["$and"]
            if not isinstance(and_val, list):
                raise _invalid(
                    "systemSlice.$and must be a list", model_name
                )
            for child in and_val:
                self._validate_condition(child, model_name)
            return

        # Expression shorthand
        if "$expr" in raw:
            _require_non_blank_string(
                raw["$expr"], "systemSlice.$expr", model_name
            )
            return

        # Leaf condition: field + op required
        _require_non_blank_string(raw.get("field"), "systemSlice.field", model_name)
        _require_non_blank_string(
            _read_either(raw, "op", "type"), "systemSlice.op", model_name
        )
        # value is optional (some ops like IS NULL don't need it)
        # maxDepth is optional but must be numeric if present
        max_depth = raw.get("maxDepth")
        if max_depth is not None and not isinstance(max_depth, (int, float)):
            raise _invalid("systemSlice.maxDepth must be numeric", model_name)


# ---------------------------------------------------------------------------
# Module-level helpers (mirrors Java's static utility methods)
# ---------------------------------------------------------------------------


def _normalize_optional(raw: Any) -> Optional[str]:
    """Normalise a value to a stripped string or None."""
    if raw is None:
        return None
    value = str(raw).strip()
    return value if value else None


def _require_non_blank_string(
    raw: Any, field: str, model_name: Optional[str]
) -> str:
    value = _normalize_optional(raw)
    if value is None:
        raise _invalid(f"{field} must be a non-empty string", model_name)
    return value


def _read_either(
    mapping: Dict[str, Any], first: str, second: str
) -> Any:
    """Read a value using the first key, falling back to the second."""
    if first in mapping:
        return mapping[first]
    return mapping.get(second)


def _invalid(
    message: str, model_name: Optional[str]
) -> AuthorityResolutionError:
    return AuthorityResolutionError(
        code=error_codes.INVALID_RESPONSE,
        message=message,
        model_involved=model_name,
        phase=error_codes.PHASE_AUTHORITY_RESOLVE,
    )


def _principal_mismatch(message: str) -> AuthorityResolutionError:
    return AuthorityResolutionError(
        code=error_codes.PRINCIPAL_MISMATCH,
        message=message,
        phase=error_codes.PHASE_AUTHORITY_RESOLVE,
    )
