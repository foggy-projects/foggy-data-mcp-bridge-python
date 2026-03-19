"""Core module for Foggy Framework."""

from foggy.core.common import MapBuilder, State, TreeNode, TreeUtils
from foggy.core.exceptions import (
    A_COMMON,
    B_COMMON,
    C_COMMON,
    DEFAULT_SUCCESS,
    STATE_COMMON,
    OPER_ERROR,
    SYSTEM_ERROR,
    NOT_NULL_ERROR,
    OBJ_REQUEST_ERROR,
    OUT_OF_LENGTH_ERROR,
    NOT_EXISTS_ERROR,
    RESOURCE_NOT_FOUND,
    REPEAT_ERROR,
    PERMISSION_ERROR,
    ExDefined,
    ExDefinedSupport,
    ExRuntimeException,
    ErrorLevel,
    RX,
    RXBuilder,
)
from foggy.core.utils import DateUtils, FileUtils, JsonUtils, StringUtils, UuidUtils
from foggy.core.tuple import Tuple2, Tuple3, Tuple4, Tuple5, Tuple6, Tuple7, Tuple8, Tuples

__all__ = [
    # Common
    "MapBuilder",
    "State",
    "TreeNode",
    "TreeUtils",
    # Exceptions
    "RX",
    "RXBuilder",
    "DEFAULT_SUCCESS",
    "ExDefined",
    "ExDefinedSupport",
    "ExRuntimeException",
    "ErrorLevel",
    # Error codes
    "A_COMMON",
    "B_COMMON",
    "C_COMMON",
    "STATE_COMMON",
    "OPER_ERROR",
    "SYSTEM_ERROR",
    "NOT_NULL_ERROR",
    "OBJ_REQUEST_ERROR",
    "OUT_OF_LENGTH_ERROR",
    "NOT_EXISTS_ERROR",
    "RESOURCE_NOT_FOUND",
    "REPEAT_ERROR",
    "PERMISSION_ERROR",
    # Utils
    "DateUtils",
    "FileUtils",
    "JsonUtils",
    "StringUtils",
    "UuidUtils",
    # Tuples
    "Tuple2",
    "Tuple3",
    "Tuple4",
    "Tuple5",
    "Tuple6",
    "Tuple7",
    "Tuple8",
    "Tuples",
]