"""Formula compiler exceptions.

实现 Spec v1 (grammar.md §2.4 + security.md §2.5) 的标准错误消息模板。

所有异常继承 FormulaError 基类，方便上游批量捕获。

Spec 对错误消息的要求（security.md §2.4）：
- 分类（reject_reason）必须精确，便于上游按类型处理
- 消息必须含违规节点 / 函数名 / 表达式片段 / 位置
- 不泄漏内部实现细节（栈帧、物理列名）
"""

from __future__ import annotations

import hashlib
from typing import Optional


def _expression_hash(expression: str) -> str:
    """Compute SHA-256 first 8 bytes of expression for logging.

    按 security.md §2.5 规定：日志里不记录完整表达式内容（可能包含业务敏感字符串字面量），
    只记录 hash 用于事件关联。
    """
    return hashlib.sha256(expression.encode("utf-8")).hexdigest()[:16]


class FormulaError(Exception):
    """所有 formula 编译错误的基类。"""

    # 子类覆盖：reject_reason 分类（见 examples.md 头部取值）
    reject_reason: str = "error"

    def __init__(self, message: str, expression: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.expression = expression

    @property
    def expression_hash(self) -> Optional[str]:
        """表达式哈希（用于日志关联，不泄漏内容）。"""
        return _expression_hash(self.expression) if self.expression else None


class FormulaSyntaxError(FormulaError):
    """语法错误：表达式不符合 Spec v1 grammar。

    对应 reject_reason: `syntax`。
    典型场景：参数数错 / 类型错 / 空 IN / 双引号 / 分号 / null 直接比较。
    """

    reject_reason = "syntax"


class FormulaSecurityError(FormulaError):
    """安全错误：表达式含禁用构造。

    对应 reject_reason: `security` / `function_not_allowed` / `node_not_allowed`。
    触发的是黑名单或白名单拒绝。
    """

    reject_reason = "security"


class FormulaNodeNotAllowedError(FormulaSecurityError):
    """AST 节点不在白名单。

    对应 reject_reason: `node_not_allowed`。
    """

    reject_reason = "node_not_allowed"


class FormulaFunctionNotAllowedError(FormulaSecurityError):
    """函数名不在白名单。

    对应 reject_reason: `function_not_allowed`。
    """

    reject_reason = "function_not_allowed"


class FormulaDepthError(FormulaError):
    """AST 深度超限。

    对应 reject_reason: `depth`。
    """

    reject_reason = "depth"


class FormulaInListSizeError(FormulaError):
    """IN 列表成员数超限（Spec §3.2：硬上限 1024）。

    对应 reject_reason: `in_list_size`。
    """

    reject_reason = "in_list_size"


class FormulaNullComparisonError(FormulaSyntaxError):
    """`x == null` / `x != null` 被拒（Spec §2.2）。

    必须使用 `is_null(x)` / `is_not_null(x)`。
    对应 reject_reason: `null_comparison`。
    """

    reject_reason = "null_comparison"


class FormulaAggNotOutermostError(FormulaSyntaxError):
    """聚合函数出现在非最外层位置（Spec §4）。

    对应 reject_reason: `agg_not_outermost`。
    典型场景：`sum(sum(x))`、`if(cond, sum(x), 0)`、`avg(distinct(x))`。
    """

    reject_reason = "agg_not_outermost"


# 标准错误消息模板（Spec v1 security.md §2.5）
# 所有 compiler 错误都应该走这些模板，确保两端一致性。
class ErrorMessages:
    """标准错误消息模板。"""

    @staticmethod
    def function_not_allowed(fn_name: str, allowed: list[str]) -> str:
        """Function '{name}' is not allowed in formula expression. Allowed: {list}"""
        preview = ", ".join(sorted(allowed)[:8])
        suffix = ", ..." if len(allowed) > 8 else ""
        return (
            f"Function '{fn_name}' is not allowed in formula expression. "
            f"Allowed: {preview}{suffix}"
        )

    @staticmethod
    def invalid_arg_count(fn_name: str, expected: int, actual: int, snippet: str) -> str:
        """Invalid argument count for '{fn}': expected {expected}, got {actual}."""
        return (
            f"Invalid argument count for '{fn_name}': expected {expected}, "
            f"got {actual}. Expression: {snippet}"
        )

    @staticmethod
    def invalid_arg_type(fn_name: str, idx: int, expected: str, actual: str) -> str:
        """Invalid argument type for '{fn}({idx})': expected {expected}, got {actual}."""
        return (
            f"Invalid argument type for '{fn_name}(arg {idx})': "
            f"expected {expected}, got {actual}"
        )

    @staticmethod
    def null_comparison() -> str:
        return (
            "Null comparison forbidden. Use 'is_null(x)' or 'is_not_null(x)' instead."
        )

    @staticmethod
    def double_quoted_string() -> str:
        return (
            "Double-quoted string forbidden. Use single quotes for string literals."
        )

    @staticmethod
    def reserved_name_as_field(name: str) -> str:
        """Reserved name '{name}' cannot be used as field identifier."""
        return f"Reserved name '{name}' cannot be used as field identifier"

    @staticmethod
    def ast_depth_exceeded(actual: int, maximum: int, expr_hash: str) -> str:
        """AST depth {actual} exceeds maximum {max}. Expression hash: {hash}"""
        return (
            f"AST depth {actual} exceeds maximum {maximum}. "
            f"Expression hash: {expr_hash}"
        )

    @staticmethod
    def in_list_size_exceeded(actual: int, maximum: int) -> str:
        """IN list size {actual} exceeds maximum {max}"""
        return f"IN list size {actual} exceeds maximum {maximum}"

    @staticmethod
    def function_call_count_exceeded(actual: int, maximum: int) -> str:
        """Function call count {actual} exceeds maximum {max}"""
        return f"Function call count {actual} exceeds maximum {maximum}"

    @staticmethod
    def node_type_not_allowed(ast_type: str) -> str:
        """Node type {ast_type} is not allowed in formula"""
        return f"Node type {ast_type} is not allowed in formula"

    @staticmethod
    def distinct_outside_count() -> str:
        return "'distinct()' can only appear inside count() aggregation wrapper"

    @staticmethod
    def agg_not_outermost(fn_name: str) -> str:
        """Aggregation not allowed at non-outermost position: {fn}"""
        return f"Aggregation not allowed at non-outermost position: {fn_name}"
