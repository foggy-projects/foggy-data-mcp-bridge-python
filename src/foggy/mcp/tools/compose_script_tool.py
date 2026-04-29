"""``ComposeScriptTool`` — MCP entry point for Compose Query scripts.

Single tool, single parameter: ``script``. Everything else (principal,
namespace, resolver) is derived from :class:`ToolExecutionContext` —
either embedded-mode state or HTTP headers (see
:func:`foggy.dataset_model.engine.compose.runtime.to_compose_context`).

Error routing
-------------
M7 does NOT introduce new error-code namespaces. Upstream structured
exceptions are unwrapped into the :class:`ToolResult`'s ``data``
payload with a 4-field shape::

    {
        "error_code": "<code>",
        "phase":      "<permission-resolve | schema-derive | compile | execute | internal>",
        "message":    "<human-readable>",
        "model":      "<optional QM name>",
    }

``error_code`` is either a ``compose-*-error/*`` / ``compose-sandbox-violation/*``
/ ``authority-resolution-error/*`` code (real namespace entries), or an
M7-only tag (``host-misconfig`` / ``internal-error``). The caller can
distinguish by checking ``"/"`` in the string.
"""

from __future__ import annotations

from typing import Any, Callable, ClassVar, Dict, List, Optional

from foggy.dataset_model.engine.compose.authority.resolver import (
    AuthorityResolutionError,
)
from foggy.dataset_model.engine.compose.compilation.errors import (
    ComposeCompileError,
)
from foggy.dataset_model.engine.compose.runtime import (
    run_script,
    to_compose_context,
)
from foggy.dataset_model.engine.compose.sandbox.exceptions import (
    ComposeSandboxViolationError,
)
from foggy.dataset_model.engine.compose.schema.errors import ComposeSchemaError
from foggy.dataset_model.engine.compose.security.authority_resolver import (
    AuthorityResolver,
)
from foggy.mcp.tools.base import BaseMcpTool
from foggy.mcp_spi.context import ToolExecutionContext
from foggy.mcp_spi.tool import ToolCategory, ToolResult


class ComposeScriptTool(BaseMcpTool):
    """MCP tool exposing the Compose Query script entry point.

    Contract (spec §4 input protocol):
      * ``arguments["script"]`` is the only parameter — a string.
      * Principal / namespace / trace are lifted from
        :class:`ToolExecutionContext` via :func:`to_compose_context`.
      * Host MUST have configured ``authority_resolver_factory`` (for
        embedded mode) — M7 does not implement remote-mode
        ``HttpAuthorityResolver``.

    Construction
    ------------
    ``authority_resolver_factory(tool_ctx) -> AuthorityResolver``:
        Per-call resolver factory. Enables the host to vary resolver
        implementation by tenant / session if needed.
    ``semantic_service``:
        Must expose ``execute_sql(sql, params, *, route_model)``
        (Step 0 public method).
    ``default_dialect``:
        Forwarded to :func:`run_script`. Default ``"mysql"``.
    """

    tool_name: ClassVar[str] = "dataset.compose_script"
    tool_description: ClassVar[str] = (
        "Run a secure FSScript SemanticDSL script for multi-model queries, "
        "derived queries, joins, unions, and time-window analysis. Use only "
        "dsl({...}), .join(...), and .union(...). Return query plans as an "
        "envelope such as return { plans: plan }; do not call .execute() "
        "directly unless specifically instructed. Do not generate raw SQL, "
        "raw WITH blocks, file I/O, network calls, dynamic imports, eval, "
        "or host-controlled security and datasource routing parameters."
    )
    tool_category: ClassVar[ToolCategory] = ToolCategory.ANALYSIS
    tool_tags: ClassVar[List[str]] = ["compose", "query", "script"]

    def __init__(
        self,
        authority_resolver_factory: Callable[[ToolExecutionContext], AuthorityResolver],
        semantic_service: Any,
        default_dialect: str = "mysql",
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(config)
        if authority_resolver_factory is None:
            raise ValueError(
                "ComposeScriptTool: authority_resolver_factory is required"
            )
        if semantic_service is None:
            raise ValueError(
                "ComposeScriptTool: semantic_service is required"
            )
        self._resolver_factory = authority_resolver_factory
        self._semantic_service = semantic_service
        self._default_dialect = default_dialect

    # ------------------------------------------------------------------
    # MCP metadata surface
    # ------------------------------------------------------------------

    def get_parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "script",
                "type": "string",
                "required": True,
                "description": (
                    "FSScript SemanticDSL script. Build base plans with "
                    "`dsl({...})`, combine with `.join(other, type, on)` or "
                    "`.union(other, options)`, and return an envelope such as "
                    "`return { plans: plan };`. Do not call `.execute()` "
                    "directly unless specifically instructed, and do not pass "
                    "host-controlled identity, permission, namespace, or "
                    "datasource routing parameters."
                ),
            },
        ]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None,
    ) -> ToolResult:
        script = arguments.get("script") if arguments else None
        if not isinstance(script, str) or not script:
            return self._error_payload(
                error_code="host-misconfig",
                phase="internal",
                message="Parameter 'script' is required and must be a non-empty string",
            )
        if context is None:
            return self._error_payload(
                error_code="host-misconfig",
                phase="internal",
                message="ToolExecutionContext is required for dataset.compose_script",
            )

        # 1. Build AuthorityResolver via factory
        try:
            resolver = self._resolver_factory(context)
        except Exception as exc:
            return self._error_payload(
                error_code="host-misconfig",
                phase="internal",
                message=f"authority_resolver_factory raised: {exc}",
            )
        if resolver is None:
            return self._error_payload(
                error_code="host-misconfig",
                phase="internal",
                message="authority_resolver_factory returned None",
            )

        # 2. Build ComposeQueryContext
        try:
            compose_ctx = to_compose_context(
                context, authority_resolver=resolver,
            )
        except (ValueError, TypeError) as exc:
            return self._error_payload(
                error_code="host-misconfig",
                phase="internal",
                message=str(exc),
            )

        # 3. Execute the script — route known exception families to
        # structured error payloads; unknown exceptions become
        # internal-error.
        try:
            result = run_script(
                script,
                compose_ctx,
                semantic_service=self._semantic_service,
                dialect=self._default_dialect,
            )
        except AuthorityResolutionError as exc:
            return self._error_payload(
                error_code=exc.code,
                phase="permission-resolve",
                message=str(exc),
                model=getattr(exc, "model_involved", None),
            )
        except ComposeSchemaError as exc:
            return self._error_payload(
                error_code=exc.code,
                phase="schema-derive",
                message=str(exc),
                model=getattr(exc, "offending_field", None),
            )
        except ComposeCompileError as exc:
            return self._error_payload(
                error_code=exc.code,
                phase="compile",
                message=str(exc),
                model=getattr(exc, "model", None),
            )
        except ComposeSandboxViolationError as exc:
            return self._error_payload(
                error_code=exc.code,
                phase="compile",
                message=str(exc),
            )
        except RuntimeError as exc:
            msg = str(exc)
            if msg.startswith("Plan execution failed at execute phase"):
                return self._error_payload(
                    error_code="execute-phase-error",
                    phase="execute",
                    message=msg,
                )
            if "ComposeRuntimeBundle" in msg or "semantic_service unbound" in msg:
                return self._error_payload(
                    error_code="host-misconfig",
                    phase="internal",
                    message=msg,
                )
            return self._error_payload(
                error_code="internal-error",
                phase="internal",
                message=msg,
            )
        except ValueError as exc:
            return self._error_payload(
                error_code="internal-error",
                phase="internal",
                message=str(exc),
            )
        except Exception as exc:
            return self._error_payload(
                error_code="internal-error",
                phase="internal",
                message=f"{type(exc).__name__}: {exc}",
            )

        # 4. Success — shape the result for MCP callers.
        data: Dict[str, Any] = {"value": result.value}
        if result.sql is not None:
            data["sql"] = result.sql
            data["params"] = list(result.params or [])
        if result.warnings:
            data["warnings"] = list(result.warnings)
        return self._success_result(
            data=data, message="Compose script executed",
        )

    # ------------------------------------------------------------------
    # Error payload helper
    # ------------------------------------------------------------------

    def _error_payload(
        self,
        *,
        error_code: str,
        phase: str,
        message: str,
        model: Optional[str] = None,
    ) -> ToolResult:
        data: Dict[str, Any] = {
            "error_code": error_code,
            "phase": phase,
            "message": message,
        }
        if model is not None:
            data["model"] = model
        # We intentionally use the explicit success=False construct so
        # the ``data`` field carries the 4-field shape MCP callers parse.
        return ToolResult(
            success=False,
            tool_name=self.tool_name,
            data=data,
            error=message,
            error_code=error_code,
        )
