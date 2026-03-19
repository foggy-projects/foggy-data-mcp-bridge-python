"""Core exceptions module for Foggy Framework."""

from foggy.core.exceptions.defined import (
    ExDefined,
    ExDefinedSupport,
    NOT_EXISTS_ERROR,
    NOT_NULL_ERROR,
    OBJ_REQUEST_ERROR,
    OPER_ERROR,
    OUT_OF_LENGTH_ERROR,
    PERMISSION_ERROR,
    REPEAT_ERROR,
    RESOURCE_NOT_FOUND,
    SYSTEM_ERROR,
    A_COMMON,
    B_COMMON,
    C_COMMON,
)
from foggy.core.exceptions.rx import RX, RXBuilder
from foggy.core.exceptions.runtime import ErrorLevel, ExRuntimeException

# State error type
STATE_COMMON = "S"  # State error

# Default success response
DEFAULT_SUCCESS = RX(code=200, msg="success", data=None)

__all__ = [
    "RX",
    "RXBuilder",
    "DEFAULT_SUCCESS",
    "ExDefined",
    "ExDefinedSupport",
    "ExRuntimeException",
    "ErrorLevel",
    # Common error source types
    "A_COMMON",
    "B_COMMON",
    "C_COMMON",
    "STATE_COMMON",
    # Common error codes
    "OPER_ERROR",
    "SYSTEM_ERROR",
    "NOT_NULL_ERROR",
    "OBJ_REQUEST_ERROR",
    "OUT_OF_LENGTH_ERROR",
    "NOT_EXISTS_ERROR",
    "RESOURCE_NOT_FOUND",
    "REPEAT_ERROR",
    "PERMISSION_ERROR",
]