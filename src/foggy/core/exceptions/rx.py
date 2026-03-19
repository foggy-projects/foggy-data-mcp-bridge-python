"""RX - Unified REST API Response Object.

This module provides a standardized response wrapper for all REST APIs.
All endpoints should return RX objects instead of ResponseEntity.
"""

from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

from foggy.core.exceptions.defined import ExDefined, OPER_ERROR, SYSTEM_ERROR

T = TypeVar("T")


class RXBuilder(Generic[T]):
    """Builder for creating RX responses."""

    def __init__(self) -> None:
        self._code: int = 200
        self._msg: str = "success"
        self._data: Optional[T] = None
        self._ex_code: Optional[str] = None

    def code(self, code: int) -> "RXBuilder[T]":
        """Set response code."""
        self._code = code
        return self

    def msg(self, msg: str) -> "RXBuilder[T]":
        """Set response message."""
        self._msg = msg
        return self

    def data(self, data: T) -> "RXBuilder[T]":
        """Set response data."""
        self._data = data
        return self

    def ex_code(self, ex_code: str) -> "RXBuilder[T]":
        """Set extended error code."""
        self._ex_code = ex_code
        return self

    def build(self) -> "RX[T]":
        """Build the RX response."""
        return RX[T](
            code=self._code,
            msg=self._msg,
            data=self._data,
            ex_code=self._ex_code,
        )


class RX(BaseModel, Generic[T]):
    """Unified REST API Response Object.

    Usage:
        # Success response
        return RX.ok(data)

        # Error response
        return RX.fail("Error message")
        return RX.fail_ex(OPER_ERROR)

        # Builder pattern
        return RX.builder().code(200).msg("success").data(data).build()
    """

    # Model fields
    code: int = Field(default=200, description="Response code, 200 means success")
    msg: str = Field(default="success", description="Response message")
    data: Optional[T] = Field(default=None, description="Response data")
    ex_code: Optional[str] = Field(default=None, description="Extended error code")

    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
    }

    # Class constants as properties
    @classmethod
    @property
    def SYSTEM_ERROR_MSG(cls) -> str:
        return "服务器发生异常，请联系管理员"

    @classmethod
    @property
    def SUCCESS(cls) -> int:
        return 200

    @classmethod
    @property
    def REPEAT(cls) -> int:
        return 201

    @classmethod
    @property
    def FAIL(cls) -> int:
        return 500

    @classmethod
    @property
    def A_COMMON(cls) -> str:
        return "A"

    @classmethod
    @property
    def B_COMMON(cls) -> str:
        return "B"

    @classmethod
    @property
    def C_COMMON(cls) -> str:
        return "C"

    @classmethod
    @property
    def STATE_COMMON(cls) -> str:
        return "S"

    @classmethod
    @property
    def DEFAULT_SUCCESS(cls) -> "RX[Any]":
        return RX(code=200, msg="success", data=None)

    @classmethod
    def ok(cls, data: Optional[T] = None, msg: str = "success") -> "RX[T]":
        """Create a success response."""
        return cls(code=200, msg=msg, data=data)

    @classmethod
    def fail(cls, msg: str, data: Optional[T] = None) -> "RX[T]":
        """Create a failure response with message."""
        return cls(code=500, msg=msg, data=data)

    @classmethod
    def fail_b(cls, msg: str, data: Optional[T] = None) -> "RX[T]":
        """Create a failure response (alias for fail)."""
        return cls.fail(msg, data)

    @classmethod
    def fail_ex(cls, ex: ExDefined, data: Optional[T] = None) -> "RX[T]":
        """Create a failure response from ExDefined."""
        return cls(
            code=500,
            msg=ex.msg,
            data=data,
            ex_code=ex.ex_code,
        )

    @classmethod
    def not_found(cls, msg: str = "Resource not found") -> "RXBuilder[T]":
        """Create a not found response builder."""
        return RXBuilder[T]().code(404).msg(msg)

    @classmethod
    def bad_request(cls, msg: str = "Bad request") -> "RXBuilder[T]":
        """Create a bad request response builder."""
        return RXBuilder[T]().code(400).msg(msg)

    @classmethod
    def unauthorized(cls, msg: str = "Unauthorized") -> "RXBuilder[T]":
        """Create an unauthorized response builder."""
        return RXBuilder[T]().code(401).msg(msg)

    @classmethod
    def forbidden(cls, msg: str = "Forbidden") -> "RXBuilder[T]":
        """Create a forbidden response builder."""
        return RXBuilder[T]().code(403).msg(msg)

    @classmethod
    def builder(cls) -> RXBuilder[T]:
        """Create a response builder."""
        return RXBuilder[T]()

    @classmethod
    def error(cls, ex: ExDefined, data: Optional[T] = None) -> "RX[T]":
        """Create an error response from ExDefined (alias for fail_ex)."""
        return cls.fail_ex(ex, data)

    def is_success(self) -> bool:
        """Check if response is successful."""
        return self.code == 200

    def is_fail(self) -> bool:
        """Check if response is a failure."""
        return self.code != 200

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "msg": self.msg,
            "data": self.data,
            "exCode": self.ex_code,
        }