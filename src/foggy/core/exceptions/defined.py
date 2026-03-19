"""
Error code definitions based on Alibaba coding guidelines.
https://sdsh.yuque.com/lgg1k8/lieoog/arofnh
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Optional


class ExDefined(ABC):
    """Error definition interface.

    Error codes reference Alibaba coding guidelines.

    Error source types:
    - A: User-side errors (parameter errors, version issues, payment timeout, etc.)
    - B: Current system errors (business logic errors, robustness issues)
    - C: Third-party service errors (CDN errors, message delivery timeout, etc.)
    """

    # Error source types
    SRC_TYPE_USER = "A"
    SRC_TYPE_BUSINESS = "B"
    SRC_TYPE_THIRD = "C"

    # System error codes
    INNER_ERROR_CODE = 500
    COMMON_ERROR_CODE = 600
    STATE_ERROR_CODE = 601

    @abstractmethod
    def get_code(self) -> int:
        """Return the numeric error code.

        Note: Codes below 10000 are reserved for system use.
        Business modules should use assigned error codes.
        """
        ...

    @abstractmethod
    def get_ex_code(self) -> str:
        """Return the error code with source prefix.

        Format: A/B/C prefix + numeric code
        - A prefix: User-side errors
        - B prefix: Current system errors
        - C prefix: Third-party service errors
        """
        ...

    @abstractmethod
    def get_err_msg(self) -> Optional[str]:
        """Return the error message."""
        ...

    @abstractmethod
    def set_err_msg(self, msg: str) -> None:
        """Set the error message."""
        ...

    @abstractmethod
    def get_user_tip(self) -> Optional[str]:
        """Return the user-facing error message."""
        ...

    @abstractmethod
    def set_user_tip(self, tip: str) -> None:
        """Set the user-facing error message."""
        ...

    def get_message(self) -> Optional[str]:
        """Return user tip if available, otherwise error message."""
        tip = self.get_user_tip()
        return tip if tip is not None else self.get_err_msg()

    # Property aliases for convenience
    @property
    def code(self) -> int:
        """Error code property."""
        return self.get_code()

    @property
    def msg(self) -> Optional[str]:
        """Error message property."""
        return self.get_err_msg()

    @property
    def ex_code(self) -> str:
        """Extended error code property."""
        return self.get_ex_code()


@dataclass
class ExDefinedSupport(ExDefined):
    """Default implementation of ExDefined."""

    code: int
    ex_code: str
    err_msg: Optional[str] = None
    user_tip: Optional[str] = None

    def get_code(self) -> int:
        return self.code

    def get_ex_code(self) -> str:
        return self.ex_code

    def get_err_msg(self) -> Optional[str]:
        return self.err_msg

    def set_err_msg(self, msg: str) -> None:
        self.err_msg = msg

    def get_user_tip(self) -> Optional[str]:
        return self.user_tip

    def set_user_tip(self, tip: str) -> None:
        self.user_tip = tip


# Common error definitions
OPER_ERROR: ClassVar[ExDefined] = ExDefinedSupport(1100, "A1100", "操作失败")
SYSTEM_ERROR: ClassVar[ExDefined] = ExDefinedSupport(1101, "B1101", "服务器错误,请联系管理员")
NOT_NULL_ERROR: ClassVar[ExDefined] = ExDefinedSupport(1102, "B1102", "{0}不能为空")
OBJ_REQUEST_ERROR: ClassVar[ExDefined] = ExDefinedSupport(1103, "B1103", "{0}未填写")
OUT_OF_LENGTH_ERROR: ClassVar[ExDefined] = ExDefinedSupport(1104, "B1104", "{0}超出长度")
NOT_EXISTS_ERROR: ClassVar[ExDefined] = ExDefinedSupport(1105, "B1105", "{0}查询的数据不存在")
RESOURCE_NOT_FOUND: ClassVar[ExDefined] = ExDefinedSupport(1106, "B1106", "资源{0}不存在")
REPEAT_ERROR: ClassVar[ExDefined] = ExDefinedSupport(201, "B201", "重复的操作")
PERMISSION_ERROR: ClassVar[ExDefined] = ExDefinedSupport(1999, "A1999", "权限错误{0}")

# Aliases for backward compatibility
A_COMMON = "A"
B_COMMON = "B"
C_COMMON = "C"