"""Formula compiler: FSScript AST → SQL fragment.

实现 Formula Spec v1（`docs/v1.4/formula-spec-v1/`）定义的 formula 表达式编译器。
从 FSScript AST（`foggy.fsscript`）转换为 SQL 片段 + bind_params 元组。

依赖契约：
- 解析器：`foggy.fsscript.parser.FsscriptParser`（与 Java JavaCC FSScript 规格对齐：
  原生支持 `&&/||/!`、`v in (...)`、`null/true/false` 关键字字面量）
- 方言：`SQL_EXPRESSION_DIALECT`，让词法层把 `if` 视作 IDENTIFIER 以支持 `if(c, a, b)`
  函数调用语法；其他控制流关键字仍保持保留字身份

Spec 治理范围（grammar.md §2.0）：
- 本模块仅负责 FormulaCompiler 的 SQL 生成路径
- `DbFormulaDef.evaluate()` 的内存计算路径独立，不在本 Spec 治理范围

核心入口：
- FormulaCompiler(dialect).compile(expression, field_resolver) -> CompiledFormula
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Set

from foggy.dataset_model.semantic.formula_dialect import SqlDialect
from foggy.dataset_model.semantic.formula_errors import (
    ErrorMessages,
    FormulaAggNotOutermostError,
    FormulaDepthError,
    FormulaFunctionNotAllowedError,
    FormulaInListSizeError,
    FormulaNodeNotAllowedError,
    FormulaNullComparisonError,
    FormulaSecurityError,
    FormulaSyntaxError,
)

# FSScript AST 节点
from foggy.fsscript.expressions.base import Expression
from foggy.fsscript.expressions.literals import (
    ArrayExpression,
    BooleanExpression,
    LiteralExpression,
    NullExpression,
    NumberExpression,
    StringExpression,
)
from foggy.fsscript.expressions.operators import (
    BinaryExpression,
    BinaryOperator,
    UnaryExpression,
    UnaryOperator,
)
from foggy.fsscript.expressions.variables import VariableExpression
from foggy.fsscript.expressions.functions import FunctionCallExpression
from foggy.fsscript.parser import SQL_EXPRESSION_DIALECT, FsscriptParser

# ---------------------------------------------------------------------------
# 白名单常量（Spec v1-r4 grammar.md §5.1）
# ---------------------------------------------------------------------------

# 允许的 Binary 运算符（FSScript BinaryOperator 子集）
ALLOWED_BINARY_OPERATORS: frozenset[BinaryOperator] = frozenset({
    # 算术（Spec §2.1）
    BinaryOperator.ADD,
    BinaryOperator.SUBTRACT,
    BinaryOperator.MULTIPLY,
    BinaryOperator.DIVIDE,
    BinaryOperator.MODULO,
    # 比较（Spec §2.2）
    BinaryOperator.EQUAL,
    BinaryOperator.NOT_EQUAL,
    BinaryOperator.LESS,
    BinaryOperator.LESS_EQUAL,
    BinaryOperator.GREATER,
    BinaryOperator.GREATER_EQUAL,
    # 逻辑（Spec §2.3）
    BinaryOperator.AND,
    BinaryOperator.OR,
    # 成员（Spec §3.2，r4 保持运算符形式）
    BinaryOperator.IN,
    BinaryOperator.NOT_IN,
})

# 允许的 Unary 运算符（FSScript UnaryOperator 子集）
ALLOWED_UNARY_OPERATORS: frozenset[UnaryOperator] = frozenset({
    UnaryOperator.NEGATE,  # -x
    UnaryOperator.NOT,     # !x
})

# 函数白名单（Spec v1 grammar.md §3）
ALLOWED_FUNCTIONS: frozenset[str] = frozenset({
    # MUST
    "if",
    "coalesce",
    "is_null",
    "is_not_null",
    "abs",
    "round",
    "ceil",
    "floor",
    # SHOULD
    "between",
    "date_diff",
    "date_add",
    "now",
})

# 聚合函数白名单（只允许在 §4 聚合包裹模式的最外层使用）
ALLOWED_AGG_FUNCTIONS: frozenset[str] = frozenset({
    "sum", "count", "avg", "max", "min",
})

# pseudo-function（Spec v1 §4.2）：仅合法在 count(distinct(...)) 的 count 直接子节点
ALLOWED_PSEUDO_FUNCTIONS: frozenset[str] = frozenset({"distinct"})

# 硬上限（Spec v1 §7 / security.md §3）
DEFAULT_MAX_DEPTH: int = 32
DEFAULT_MAX_CALLS: int = 64
DEFAULT_MAX_EXPR_LEN: int = 4096
IN_LIST_HARD_MAX: int = 1024  # 不可配置
ROUND_N_MIN: int = 0
ROUND_N_MAX: int = 10
COALESCE_ARG_MIN: int = 2
COALESCE_ARG_MAX: int = 16

# date_add 合法单位（Spec §3.6）
DATE_ADD_UNITS: frozenset[str] = frozenset({"day", "month", "year"})


# 二元运算符 → SQL 映射（grammar.md §2.1-2.3）
_BINOP_SYMBOL: dict[BinaryOperator, str] = {
    BinaryOperator.ADD: "+",
    BinaryOperator.SUBTRACT: "-",
    BinaryOperator.MULTIPLY: "*",
    BinaryOperator.DIVIDE: "/",
    BinaryOperator.MODULO: "%",
    BinaryOperator.EQUAL: "=",
    BinaryOperator.NOT_EQUAL: "<>",
    BinaryOperator.LESS: "<",
    BinaryOperator.LESS_EQUAL: "<=",
    BinaryOperator.GREATER: ">",
    BinaryOperator.GREATER_EQUAL: ">=",
    BinaryOperator.AND: "AND",
    BinaryOperator.OR: "OR",
}


# Type alias：语义字段名 → 物理列 SQL 片段
FieldResolver = Callable[[str], str]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompiledFormula:
    """Formula compile 结果。

    Attributes:
        sql_fragment: 生成的 SQL 片段（含 `?` 参数占位符，所有字面量都走参数绑定）
        bind_params: 参数值元组，按前序 DFS 遍历顺序（parity.md §2.4）
        referenced_fields: 表达式引用的**语义字段名**集合（未经 field_resolver 映射的原始名）
        used_functions: 使用到的公开函数名集合
    """

    sql_fragment: str
    bind_params: tuple
    referenced_fields: frozenset[str] = field(default_factory=frozenset)
    used_functions: frozenset[str] = field(default_factory=frozenset)


@dataclass
class FormulaCompilerConfig:
    """FormulaCompiler 可配置项（Spec v1 §7 + security.md §3）。

    硬上限（IN 列表、round n 范围、coalesce 参数数）不可配置。
    """

    max_depth: int = DEFAULT_MAX_DEPTH
    max_calls: int = DEFAULT_MAX_CALLS
    max_expr_len: int = DEFAULT_MAX_EXPR_LEN


class FormulaCompiler:
    """Formula 编译器主类。

    使用方式：
        compiler = FormulaCompiler(SqlDialect.of("mysql"))
        result = compiler.compile("if(a > 0, a, 0)", field_resolver=lambda name: f"t.{name}")
        print(result.sql_fragment)  # "CASE WHEN (t.a > ?) THEN t.a ELSE ? END"
        print(result.bind_params)   # (0, 0)

    Thread safety: 实例只读，可在多线程共享。
    """

    def __init__(
        self,
        dialect: SqlDialect,
        config: Optional[FormulaCompilerConfig] = None,
    ) -> None:
        self._dialect = dialect
        self._config = config or FormulaCompilerConfig()

    @property
    def dialect(self) -> SqlDialect:
        return self._dialect

    @property
    def config(self) -> FormulaCompilerConfig:
        return self._config

    def compile(
        self,
        expression: str,
        field_resolver: FieldResolver,
    ) -> CompiledFormula:
        """编译 formula 表达式为 SQL 片段 + bind_params。

        Args:
            expression: formula 表达式字符串（遵循 Spec v1 grammar）
            field_resolver: 语义字段名 → 物理列 SQL 片段的映射函数

        Returns:
            CompiledFormula 含 sql_fragment / bind_params / referenced_fields

        Raises:
            FormulaSyntaxError: 表达式语法不合法
            FormulaSecurityError / FormulaNodeNotAllowedError / FormulaFunctionNotAllowedError:
                表达式含禁用构造
            FormulaDepthError: AST 深度超限
            FormulaInListSizeError: IN 成员数超限
            FormulaAggNotOutermostError: 聚合函数位置错
        """
        # 1. 类型 / 长度检查
        if not isinstance(expression, str):
            raise FormulaSyntaxError(
                f"Expression must be str, got {type(expression).__name__}"
            )
        if len(expression) > self._config.max_expr_len:
            raise FormulaSecurityError(
                f"Expression length {len(expression)} exceeds maximum "
                f"{self._config.max_expr_len}",
                expression=expression,
            )
        if not expression.strip():
            raise FormulaSyntaxError("Expression cannot be empty")

        # 2. FSScript 解析。SQL_EXPRESSION_DIALECT 在词法层把 `if` 当 IDENTIFIER
        # 而非控制流保留字，使得 `if(c, a, b)` 解析成普通 FunctionCallExpression。
        # 字符串字面量内部的 `if(` 自然由 STRING token 路径承担，无需源码预处理。
        try:
            parser = FsscriptParser(expression, dialect=SQL_EXPRESSION_DIALECT)
            tree = parser.parse_expression()
        except Exception as exc:
            # FSScript parser 失败，统一归类为语法错误
            raise FormulaSyntaxError(
                f"Invalid formula syntax: {exc}",
                expression=expression,
            ) from exc

        if tree is None:
            raise FormulaSyntaxError("Expression did not produce any AST node")

        # 3. 白名单 + 位置约束校验（Step 2.2）
        validator = _Validator(self._config, expression)
        validator.validate(tree)

        # 4. SQL 生成（Step 2.3，带方言分派 Step 2.4）
        generator = _SqlGenerator(self._dialect, field_resolver)
        return generator.generate(tree)


# ---------------------------------------------------------------------------
# Step 2.2：Validator —— FSScript AST 白名单 + 位置约束校验
# ---------------------------------------------------------------------------


@dataclass
class _ValidationContext:
    """追踪位置上下文（用于聚合 / distinct 位置约束）。

    top_level: 当前节点是否在表达式最外层（聚合函数只能在此位置）
    inside_count: 当前节点是否是 `count(...)` 的直接子节点（distinct 只能在此位置）
    """

    top_level: bool = False
    inside_count: bool = False


class _Validator:
    """Step 2.2：FSScript AST 白名单 + 位置约束校验。"""

    def __init__(self, config: FormulaCompilerConfig, expression: str) -> None:
        self._config = config
        self._expression = expression

    def validate(self, tree: Expression) -> None:
        """顶层校验入口。校验通过时返回 None，违规时抛异常。"""
        # 1. AST 深度
        depth = _fs_depth(tree)
        if depth > self._config.max_depth:
            expr_hash = hashlib.sha256(self._expression.encode("utf-8")).hexdigest()[:16]
            raise FormulaDepthError(
                ErrorMessages.ast_depth_exceeded(depth, self._config.max_depth, expr_hash),
                expression=self._expression,
            )

        # 2. 函数调用总数
        call_count = _count_calls(tree)
        if call_count > self._config.max_calls:
            raise FormulaSecurityError(
                ErrorMessages.function_call_count_exceeded(call_count, self._config.max_calls),
                expression=self._expression,
            )

        # 3. 递归校验节点
        self._validate_node(tree, _ValidationContext(top_level=True))

    def _validate_node(self, node: Expression, ctx: _ValidationContext) -> None:
        # 白名单分派：只接受以下 7 类 Expression
        # r4: 从 Python stdlib AST 改为 FSScript Expression
        if isinstance(node, LiteralExpression):
            self._validate_literal(node)
            return
        if isinstance(node, VariableExpression):
            self._validate_variable(node)
            return
        if isinstance(node, BinaryExpression):
            self._validate_binary(node, ctx)
            return
        if isinstance(node, UnaryExpression):
            self._validate_unary(node, ctx)
            return
        if isinstance(node, FunctionCallExpression):
            self._validate_function_call(node, ctx)
            return
        if isinstance(node, ArrayExpression):
            # ArrayExpression 只合法在 BinaryExpression(IN/NOT_IN).right 位置
            # 其他位置（如作为函数参数、算术操作数）一律拒绝
            raise FormulaNodeNotAllowedError(
                ErrorMessages.node_type_not_allowed("ArrayExpression"),
                expression=self._expression,
            )

        # 其他 FSScript 节点：TernaryExpression / ObjectExpression / BlockExpression /
        # IfExpression / ForExpression / WhileExpression / SwitchExpression /
        # TryCatchExpression / MemberAccessExpression / IndexAccessExpression /
        # UpdateExpression / TemplateLiteralExpression / SpreadExpression /
        # ImportExpression / ExportExpression / AssignmentExpression / ThrowExpression
        raise FormulaNodeNotAllowedError(
            ErrorMessages.node_type_not_allowed(type(node).__name__),
            expression=self._expression,
        )

    def _validate_literal(self, node: LiteralExpression) -> None:
        """校验字面量节点。

        FSScript 已把 `null` / `true` / `false` / 数字 / 字符串都解析为
        LiteralExpression 子类（NullExpression / BooleanExpression / NumberExpression /
        StringExpression），无需 Python stdlib AST 的保留名硬映射。
        """
        if isinstance(node, NullExpression):
            return
        if isinstance(node, BooleanExpression):
            return
        if isinstance(node, NumberExpression):
            value = node.value
            if isinstance(value, int) and abs(value) > (2**63 - 1):
                raise FormulaSyntaxError(
                    f"Integer literal out of range: {value}",
                    expression=self._expression,
                )
            return
        if isinstance(node, StringExpression):
            return
        # 其他 LiteralExpression 子类（如果有）拒绝
        raise FormulaSyntaxError(
            f"Unsupported literal type: {type(node).__name__}",
            expression=self._expression,
        )

    def _validate_variable(self, node: VariableExpression) -> None:
        name = node.name
        if name.startswith("__"):
            raise FormulaSecurityError(
                f"Identifier starting with '__' is forbidden: {name}",
                expression=self._expression,
            )

    def _validate_binary(self, node: BinaryExpression, ctx: _ValidationContext) -> None:
        op = node.operator
        if op not in ALLOWED_BINARY_OPERATORS:
            raise FormulaNodeNotAllowedError(
                f"Binary operator '{op.value}' is not allowed in formula",
                expression=self._expression,
            )

        # null 比较禁止（Spec §2.2）
        if op in (BinaryOperator.EQUAL, BinaryOperator.NOT_EQUAL):
            if _is_null_literal(node.left) or _is_null_literal(node.right):
                raise FormulaNullComparisonError(
                    ErrorMessages.null_comparison(),
                    expression=self._expression,
                )

        # in / not in 特殊处理：右侧必须是 ArrayExpression 且成员是字面量
        if op in (BinaryOperator.IN, BinaryOperator.NOT_IN):
            self._validate_in_expression(node)
            return

        # 普通二元：递归校验左右
        child_ctx = _ValidationContext(top_level=False, inside_count=False)
        self._validate_node(node.left, child_ctx)
        self._validate_node(node.right, child_ctx)

    def _validate_in_expression(self, node: BinaryExpression) -> None:
        """校验 `v in (a, b, c)` / `v not in (a, b, c)`（Spec §3.2）。

        FSScript 对单元素 `(x)` 会退化为普通括号表达式（LiteralExpression 或其他）；
        只有 `(x, y)` 或 `(x,)` 带逗号才是 ArrayExpression。
        为兼容 LLM / QM 作者写 `v in ('draft')` 不加尾逗号的直觉，compiler 接受
        LiteralExpression 右侧作为单元素 IN list。
        """
        child_ctx = _ValidationContext(top_level=False, inside_count=False)
        self._validate_node(node.left, child_ctx)

        right = node.right

        # 单元素退化：接受 LiteralExpression 右侧，视为 1-元素 IN list
        if isinstance(right, LiteralExpression):
            if isinstance(right, NullExpression):
                raise FormulaSyntaxError(
                    "'in' / 'not in' member cannot be null",
                    expression=self._expression,
                )
            self._validate_literal(right)
            return

        if not isinstance(right, ArrayExpression):
            raise FormulaSyntaxError(
                "Right-hand side of 'in' / 'not in' must be a literal or "
                "a parenthesized list like (a, b, c)",
                expression=self._expression,
            )

        members = right.elements
        if len(members) == 0:
            raise FormulaSyntaxError(
                "'in' / 'not in' list cannot be empty",
                expression=self._expression,
            )
        if len(members) > IN_LIST_HARD_MAX:
            raise FormulaInListSizeError(
                ErrorMessages.in_list_size_exceeded(len(members), IN_LIST_HARD_MAX),
                expression=self._expression,
            )
        for idx, member in enumerate(members):
            # 成员必须是字面量（grammar §3.2：不支持子查询 / 列引用 / 表达式）
            if not isinstance(member, LiteralExpression):
                raise FormulaSyntaxError(
                    f"'in' / 'not in' member at position {idx} must be a literal; "
                    f"got {type(member).__name__}",
                    expression=self._expression,
                )
            # 成员不能是 null（`in (null, 1)` 语义混乱，拒绝）
            if isinstance(member, NullExpression):
                raise FormulaSyntaxError(
                    f"'in' / 'not in' member at position {idx} cannot be null; "
                    "use 'is_null(x)' separately",
                    expression=self._expression,
                )
            # 复用字面量校验（整数范围等）
            self._validate_literal(member)

    def _validate_unary(self, node: UnaryExpression, ctx: _ValidationContext) -> None:
        op = node.operator
        if op not in ALLOWED_UNARY_OPERATORS:
            raise FormulaNodeNotAllowedError(
                f"Unary operator '{op.value}' is not allowed in formula",
                expression=self._expression,
            )
        child_ctx = _ValidationContext(top_level=False, inside_count=False)
        self._validate_node(node.operand, child_ctx)

    def _validate_function_call(
        self,
        node: FunctionCallExpression,
        ctx: _ValidationContext,
    ) -> None:
        fn_name = self._extract_function_name(node)

        if fn_name in ALLOWED_AGG_FUNCTIONS:
            self._validate_aggregate_call(fn_name, node, ctx)
            return

        if fn_name in ALLOWED_PSEUDO_FUNCTIONS:
            self._validate_pseudo_call(fn_name, node, ctx)
            return

        if fn_name not in ALLOWED_FUNCTIONS:
            raise FormulaFunctionNotAllowedError(
                ErrorMessages.function_not_allowed(
                    fn_name,
                    list(ALLOWED_FUNCTIONS | ALLOWED_AGG_FUNCTIONS),
                ),
                expression=self._expression,
            )

        # 普通函数：参数个数 / 类型校验
        self._validate_normal_function_args(fn_name, node)

        # 递归校验参数
        child_ctx = _ValidationContext(top_level=False, inside_count=False)
        for arg in node.arguments:
            self._validate_node(arg, child_ctx)

    def _validate_aggregate_call(
        self,
        fn_name: str,
        node: FunctionCallExpression,
        ctx: _ValidationContext,
    ) -> None:
        """聚合函数位置约束（Spec §4.1）：只能在 top_level。"""
        if not ctx.top_level:
            raise FormulaAggNotOutermostError(
                ErrorMessages.agg_not_outermost(fn_name),
                expression=self._expression,
            )

        args = node.arguments
        if len(args) != 1:
            raise FormulaSyntaxError(
                f"Aggregate '{fn_name}' must have exactly 1 argument; got {len(args)}",
                expression=self._expression,
            )

        # count(distinct(...)) 允许：count 的直接子节点可以是 distinct
        # 其他聚合：distinct 不允许嵌套
        if fn_name == "count":
            child_ctx = _ValidationContext(top_level=False, inside_count=True)
        else:
            child_ctx = _ValidationContext(top_level=False, inside_count=False)

        self._validate_node(args[0], child_ctx)

    def _validate_pseudo_call(
        self,
        fn_name: str,
        node: FunctionCallExpression,
        ctx: _ValidationContext,
    ) -> None:
        """pseudo-function 位置约束（Spec §4.2）：distinct(x) 只能在 count 直接子节点。"""
        if fn_name == "distinct":
            if not ctx.inside_count:
                raise FormulaAggNotOutermostError(
                    ErrorMessages.distinct_outside_count(),
                    expression=self._expression,
                )
            if len(node.arguments) != 1:
                raise FormulaSyntaxError(
                    f"'distinct' must have exactly 1 argument; got {len(node.arguments)}",
                    expression=self._expression,
                )
            child_ctx = _ValidationContext(top_level=False, inside_count=False)
            self._validate_node(node.arguments[0], child_ctx)
            return

        raise FormulaFunctionNotAllowedError(
            ErrorMessages.function_not_allowed(fn_name, list(ALLOWED_FUNCTIONS)),
            expression=self._expression,
        )

    def _validate_normal_function_args(
        self,
        fn_name: str,
        node: FunctionCallExpression,
    ) -> None:
        """普通函数的参数个数 / 类型检查（按函数各自规则）。"""
        args = node.arguments
        snippet = _expr_snippet(node)

        if fn_name == "if":
            if len(args) != 3:
                raise FormulaSyntaxError(
                    ErrorMessages.invalid_arg_count("if", 3, len(args), snippet),
                    expression=self._expression,
                )
        elif fn_name in ("is_null", "is_not_null"):
            if len(args) != 1:
                raise FormulaSyntaxError(
                    ErrorMessages.invalid_arg_count(fn_name, 1, len(args), snippet),
                    expression=self._expression,
                )
        elif fn_name == "abs":
            if len(args) != 1:
                raise FormulaSyntaxError(
                    ErrorMessages.invalid_arg_count("abs", 1, len(args), snippet),
                    expression=self._expression,
                )
        elif fn_name in ("ceil", "floor"):
            if len(args) != 1:
                raise FormulaSyntaxError(
                    ErrorMessages.invalid_arg_count(fn_name, 1, len(args), snippet),
                    expression=self._expression,
                )
        elif fn_name == "round":
            if len(args) != 2:
                raise FormulaSyntaxError(
                    ErrorMessages.invalid_arg_count("round", 2, len(args), snippet),
                    expression=self._expression,
                )
            n = args[1]
            if not isinstance(n, NumberExpression) or not isinstance(n.value, int):
                raise FormulaSyntaxError(
                    ErrorMessages.invalid_arg_type(
                        "round", 1, "int literal", type(n).__name__
                    ),
                    expression=self._expression,
                )
            if not (ROUND_N_MIN <= n.value <= ROUND_N_MAX):
                raise FormulaSyntaxError(
                    f"'round' second argument must be in [{ROUND_N_MIN}, {ROUND_N_MAX}], "
                    f"got {n.value}",
                    expression=self._expression,
                )
        elif fn_name == "coalesce":
            if not (COALESCE_ARG_MIN <= len(args) <= COALESCE_ARG_MAX):
                raise FormulaSyntaxError(
                    f"'coalesce' requires {COALESCE_ARG_MIN}..{COALESCE_ARG_MAX} "
                    f"arguments; got {len(args)}",
                    expression=self._expression,
                )
        elif fn_name == "between":
            if len(args) != 3:
                raise FormulaSyntaxError(
                    ErrorMessages.invalid_arg_count("between", 3, len(args), snippet),
                    expression=self._expression,
                )
        elif fn_name == "date_diff":
            if len(args) != 2:
                raise FormulaSyntaxError(
                    ErrorMessages.invalid_arg_count("date_diff", 2, len(args), snippet),
                    expression=self._expression,
                )
        elif fn_name == "date_add":
            if len(args) != 3:
                raise FormulaSyntaxError(
                    ErrorMessages.invalid_arg_count("date_add", 3, len(args), snippet),
                    expression=self._expression,
                )
            unit = args[2]
            if not isinstance(unit, StringExpression):
                raise FormulaSyntaxError(
                    ErrorMessages.invalid_arg_type(
                        "date_add", 2, "string literal", type(unit).__name__
                    ),
                    expression=self._expression,
                )
            if unit.value not in DATE_ADD_UNITS:
                raise FormulaSyntaxError(
                    f"'date_add' unit must be one of {sorted(DATE_ADD_UNITS)}; "
                    f"got '{unit.value}'",
                    expression=self._expression,
                )
        elif fn_name == "now":
            if len(args) != 0:
                raise FormulaSyntaxError(
                    ErrorMessages.invalid_arg_count("now", 0, len(args), snippet),
                    expression=self._expression,
                )
        # 其他白名单函数无额外约束

    def _extract_function_name(self, node: FunctionCallExpression) -> str:
        """从 FunctionCallExpression.function 提取函数名。

        FSScript 的 function 字段是 Expression，通常是 VariableExpression（简单调用）。
        方法调用（MemberAccessExpression）会拒绝。
        """
        func = node.function
        if isinstance(func, VariableExpression):
            return func.name
        raise FormulaNodeNotAllowedError(
            f"Function call must be a simple name; got {type(func).__name__}",
            expression=self._expression,
        )


# ---------------------------------------------------------------------------
# Step 2.3：SqlGenerator —— FSScript AST → SQL 片段 + bind_params
# ---------------------------------------------------------------------------


class _GenContext:
    """SQL 生成上下文。累积 bind_params / referenced_fields / used_functions。"""

    def __init__(self) -> None:
        self.params: list[Any] = []
        self.referenced_fields: set[str] = set()
        self.used_functions: set[str] = set()

    def add_param(self, value: Any) -> str:
        self.params.append(value)
        return "?"


class _SqlGenerator:
    """Step 2.3：FSScript AST → SQL 生成器。"""

    def __init__(self, dialect: SqlDialect, field_resolver: FieldResolver) -> None:
        self._dialect = dialect
        self._field_resolver = field_resolver
        self._ctx = _GenContext()

    def generate(self, tree: Expression) -> CompiledFormula:
        sql = self._gen_node(tree)
        return CompiledFormula(
            sql_fragment=sql,
            bind_params=tuple(self._ctx.params),
            referenced_fields=frozenset(self._ctx.referenced_fields),
            used_functions=frozenset(self._ctx.used_functions),
        )

    def _gen_node(self, node: Expression) -> str:
        if isinstance(node, LiteralExpression):
            return self._gen_literal(node)
        if isinstance(node, VariableExpression):
            return self._gen_variable(node)
        if isinstance(node, BinaryExpression):
            return self._gen_binary(node)
        if isinstance(node, UnaryExpression):
            return self._gen_unary(node)
        if isinstance(node, FunctionCallExpression):
            return self._gen_function_call(node)
        # ArrayExpression 已由 _gen_binary(in/not_in) 消费；其他位置不应到这里
        raise FormulaNodeNotAllowedError(
            ErrorMessages.node_type_not_allowed(type(node).__name__),
        )

    def _gen_literal(self, node: LiteralExpression) -> str:
        if isinstance(node, NullExpression):
            return "NULL"
        # 其他字面量（数字 / 字符串 / 布尔）走参数绑定
        return self._ctx.add_param(node.value)

    def _gen_variable(self, node: VariableExpression) -> str:
        name = node.name
        # r4: FSScript 已原生支持 null/true/false 作为字面量关键字 → NullExpression/BooleanExpression；
        # 不会以 VariableExpression 形式到达这里。
        physical = self._field_resolver(name)
        self._ctx.referenced_fields.add(name)
        return physical

    def _gen_binary(self, node: BinaryExpression) -> str:
        op = node.operator

        # in / not in 特殊处理（消费 ArrayExpression）
        if op in (BinaryOperator.IN, BinaryOperator.NOT_IN):
            return self._gen_in(node)

        # 统一 R-2：BinaryExpression 外包一层；operand 的括号由其自身递归负责
        # （避免 `a && b && c` 产生 `((((a)) AND ((b)))) AND ((c))` 这种过度嵌套）
        left = self._gen_node(node.left)
        right = self._gen_node(node.right)
        sym = _BINOP_SYMBOL[op]
        return f"({left} {sym} {right})"

    def _gen_in(self, node: BinaryExpression) -> str:
        """生成 `(v IN (?, ?, ...))` / `(v NOT IN (?, ?, ...))`。"""
        left_sql = self._gen_node(node.left)
        right = node.right

        # 单元素退化：右侧是 LiteralExpression 时视为 1-元素 IN list
        if isinstance(right, LiteralExpression):
            member_sql = self._gen_literal(right)
            kw = "IN" if node.operator == BinaryOperator.IN else "NOT IN"
            return f"({left_sql} {kw} ({member_sql}))"

        assert isinstance(right, ArrayExpression), (
            "validator should have ensured right-hand side is Array or Literal"
        )
        member_sqls: list[str] = []
        for member in right.elements:
            assert isinstance(member, LiteralExpression)
            member_sqls.append(self._gen_literal(member))
        members_joined = ", ".join(member_sqls)
        kw = "IN" if node.operator == BinaryOperator.IN else "NOT IN"
        # R-2：整个 in 比较外包一层
        return f"({left_sql} {kw} ({members_joined}))"

    def _gen_unary(self, node: UnaryExpression) -> str:
        operand = self._gen_node(node.operand)
        if node.operator == UnaryOperator.NEGATE:
            return f"(-{operand})"
        if node.operator == UnaryOperator.NOT:
            return f"NOT ({operand})"
        # validator 已经拒绝，这里是防御
        raise FormulaNodeNotAllowedError(
            f"Unary operator '{node.operator.value}' is not allowed in formula",
        )

    def _gen_function_call(self, node: FunctionCallExpression) -> str:
        # validator 保证 function 是 VariableExpression
        assert isinstance(node.function, VariableExpression)
        fn_name = node.function.name
        self._ctx.used_functions.add(fn_name)

        if fn_name in ALLOWED_AGG_FUNCTIONS:
            return self._gen_aggregate(fn_name, node)

        if fn_name == "distinct":
            # 仅合法在 count(distinct(...))，此处由 _gen_aggregate('count', ...) 调用
            # 直接生成内层 formula 的 SQL
            assert len(node.arguments) == 1
            return self._gen_node(node.arguments[0])

        if fn_name == "if":
            cond = self._gen_node(node.arguments[0])
            a = self._gen_node(node.arguments[1])
            b = self._gen_node(node.arguments[2])
            return f"CASE WHEN ({cond}) THEN {a} ELSE {b} END"

        if fn_name == "is_null":
            x = self._gen_node(node.arguments[0])
            return f"{x} IS NULL"

        if fn_name == "is_not_null":
            x = self._gen_node(node.arguments[0])
            return f"{x} IS NOT NULL"

        if fn_name == "coalesce":
            parts = [self._gen_node(a) for a in node.arguments]
            return "COALESCE(" + ", ".join(parts) + ")"

        if fn_name == "abs":
            x = self._gen_node(node.arguments[0])
            return f"ABS({x})"

        if fn_name == "round":
            x = self._gen_node(node.arguments[0])
            n_node = node.arguments[1]
            # n 走参数绑定（grammar.md §6.1：`ROUND(x, ?)` params `[n]`）
            assert isinstance(n_node, NumberExpression)
            n_placeholder = self._ctx.add_param(n_node.value)
            return f"ROUND({x}, {n_placeholder})"

        if fn_name == "ceil":
            x = self._gen_node(node.arguments[0])
            return f"CEILING({x})"

        if fn_name == "floor":
            x = self._gen_node(node.arguments[0])
            return f"FLOOR({x})"

        if fn_name == "between":
            v = self._gen_node(node.arguments[0])
            lo = self._gen_node(node.arguments[1])
            hi = self._gen_node(node.arguments[2])
            return f"({v} BETWEEN {lo} AND {hi})"

        if fn_name == "date_diff":
            a = self._gen_node(node.arguments[0])
            b = self._gen_node(node.arguments[1])
            return self._dialect.date_diff_expr(a, b)

        if fn_name == "date_add":
            d = self._gen_node(node.arguments[0])
            n_node = node.arguments[1]
            unit_node = node.arguments[2]
            n_placeholder = self._gen_node(n_node)
            assert isinstance(unit_node, StringExpression)
            return self._dialect.date_add_expr(d, n_placeholder, unit_node.value)  # type: ignore[arg-type]

        if fn_name == "now":
            return self._dialect.now_expr()

        # validator 应该已经拒绝未知函数；防御兜底
        raise FormulaFunctionNotAllowedError(
            ErrorMessages.function_not_allowed(fn_name, list(ALLOWED_FUNCTIONS)),
        )

    def _gen_aggregate(self, fn_name: str, node: FunctionCallExpression) -> str:
        """生成聚合函数 SQL。支持 `count(distinct(x))` 特殊形态（Spec §4.2）。"""
        inner = node.arguments[0]

        # count(distinct(x)) 形态
        if (
            fn_name == "count"
            and isinstance(inner, FunctionCallExpression)
            and isinstance(inner.function, VariableExpression)
            and inner.function.name == "distinct"
        ):
            # distinct 的唯一参数
            distinct_inner = inner.arguments[0]
            inner_sql = self._gen_node(distinct_inner)
            self._ctx.used_functions.add("distinct")
            # parity.md §7：count(distinct(if(c, col, null))) → COUNT(DISTINCT CASE WHEN c THEN col END)
            inner_sql = _maybe_drop_else_null_for_count_distinct(inner_sql)
            return f"COUNT(DISTINCT {inner_sql})"

        # 普通聚合 sum/avg/max/min/count
        inner_sql = self._gen_node(inner)
        upper = fn_name.upper()
        return f"{upper}({inner_sql})"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _fs_depth(node: Expression) -> int:
    """计算 FSScript AST 深度。叶子节点深度为 1。

    FSScript 节点没有统一的 `children()` 接口，这里针对白名单内节点类型做显式遍历。
    未识别的节点类型按深度 1 计。
    """
    children = _fs_children(node)
    if not children:
        return 1
    return 1 + max(_fs_depth(c) for c in children)


def _fs_children(node: Expression) -> list[Expression]:
    """列出 FSScript Expression 的直接子节点（仅白名单内节点类型）。"""
    if isinstance(node, BinaryExpression):
        return [node.left, node.right]
    if isinstance(node, UnaryExpression):
        return [node.operand]
    if isinstance(node, FunctionCallExpression):
        return list(node.arguments)
    if isinstance(node, ArrayExpression):
        return list(node.elements)
    # LiteralExpression / VariableExpression / 其他：无子节点
    return []


def _count_calls(node: Expression) -> int:
    """统计表达式中的 FunctionCallExpression 总数。"""
    total = 0
    stack: list[Expression] = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, FunctionCallExpression):
            total += 1
        stack.extend(_fs_children(current))
    return total


def _is_null_literal(node: Expression) -> bool:
    """判断节点是否是 null 字面量。

    FSScript 里 `null` 关键字直接解析为 NullExpression；
    也兼容 `LiteralExpression(value=None)` 形态。
    """
    if isinstance(node, NullExpression):
        return True
    if isinstance(node, LiteralExpression) and node.value is None:
        return True
    return False


def _expr_snippet(node: Expression, max_len: int = 80) -> str:
    """生成节点的短摘要，用于错误消息。"""
    try:
        s = repr(node)
    except Exception:
        s = f"{type(node).__name__}(...)"
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _maybe_drop_else_null_for_count_distinct(case_when_sql: str) -> str:
    """`count(distinct(if(cond, col, null)))` 在 SQL 输出时省略 `ELSE NULL` 子句。

    Spec parity.md §7：
        count(distinct(if(c, col, null)))
        → COUNT(DISTINCT CASE WHEN (c) THEN col END)   ← ELSE NULL 省略

    实现：检查 inner_sql 是否是 `CASE WHEN (...) THEN ... ELSE NULL END` 形式，
    若是则删掉 ` ELSE NULL` 片段。
    """
    suffix = " ELSE NULL END"
    if case_when_sql.endswith(suffix) and case_when_sql.startswith("CASE WHEN "):
        return case_when_sql[: -len(suffix)] + " END"
    return case_when_sql
