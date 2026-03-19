"""Runtime exception for Foggy Framework."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from foggy.core.exceptions.defined import ExDefined, SYSTEM_ERROR


class ErrorLevel(Enum):
    """Error severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


@dataclass
class ExRuntimeException(Exception):
    """Foggy runtime exception.

    Usage:
        raise ExRuntimeException("Something went wrong")
        raise ExRuntimeException.from_defined(SYSTEM_ERROR)
        raise ExRuntimeException.from_defined(OPER_ERROR, item={"key": "value"})
    """

    msg: str = "系统异常"
    code: int = 1
    ex_code: str = "B001"
    item: Optional[dict[str, Any]] = None
    level: ErrorLevel = ErrorLevel.ERROR
    user_tip: Optional[str] = None
    cause: Optional[Exception] = None

    def __init__(
        self,
        msg: str = "系统异常",
        code: int = 1,
        ex_code: str = "B001",
        item: Optional[dict[str, Any]] = None,
        level: ErrorLevel = ErrorLevel.ERROR,
        user_tip: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(msg)
        self.msg = msg
        self.code = code
        self.ex_code = ex_code
        self.item = item
        self.level = level
        self.user_tip = user_tip
        self.cause = cause

    @classmethod
    def from_defined(
        cls,
        ex: ExDefined,
        item: Optional[dict[str, Any]] = None,
        level: ErrorLevel = ErrorLevel.ERROR,
        user_tip: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> "ExRuntimeException":
        """Create exception from ExDefined."""
        return cls(
            msg=ex.msg,
            code=ex.code,
            ex_code=ex.ex_code,
            item=item,
            level=level,
            user_tip=user_tip,
            cause=cause,
        )

    @property
    def message(self) -> str:
        """Get error message."""
        return self.msg

    def __str__(self) -> str:
        result = f"[{self.ex_code}] {self.msg}"
        if self.item:
            result += f" | item={self.item}"
        return result

    def __repr__(self) -> str:
        return (
            f"ExRuntimeException(msg={self.msg!r}, code={self.code}, "
            f"ex_code={self.ex_code!r}, level={self.level.value})"
        )