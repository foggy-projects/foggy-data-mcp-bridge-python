"""Compose Query three-layer sandbox (8.2.0.beta M3 foundation).

This subpackage establishes the error taxonomy that the M9 sandbox tests
(see ``M9-三层沙箱防护测试脚手架.md``) assert against. The concrete
enforcement — static AST validator for Layer A, AllowedFunctions guard
for Layer B, and method-whitelist reflection for Layer C — lands in M9.
M3 delivers the hooks so M7 (``script`` MCP tool) can wire the
``ComposeQueryContext`` through a runnable sandbox harness without the
harness itself needing to block on M9.

Public API
----------
* :class:`ComposeSandboxViolationError` — structured error raised by any
  enforcement layer; validates ``code`` / ``phase`` on construction.
* ``error_codes`` — frozen constants for the 14 violation codes across
  Layers A/B/C.

Cross-language parity
---------------------
Error code strings mirror the Java ``ComposeSandboxErrorCodes.java`` class
byte-for-byte (Java side delivered in M3 Java handoff).
"""

from __future__ import annotations

from . import error_codes
from .exceptions import ComposeSandboxViolationError
from .expression_whitelist_validator import (
    validate_columns,
    validate_derived_columns,
    validate_slice,
)
from .script_source_scanner import scan_script_source
from .security_param_guard import validate as validate_security_param

__all__ = [
    "error_codes",
    "ComposeSandboxViolationError",
    "scan_script_source",
    "validate_columns",
    "validate_derived_columns",
    "validate_slice",
    "validate_security_param",
]
