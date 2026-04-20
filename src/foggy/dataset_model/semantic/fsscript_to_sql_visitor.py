"""fsscript AST → SQL visitor for calculated-field expression compilation.

v1.5 Phase 3 — Architectural alignment with Java's ``CalculatedFieldService`` +
``SqlExpContext`` + ``SqlExpFactory``.  Replaces the character-level
``SemanticQueryService._render_expression`` tokenizer for the subset of
expressions the Python fsscript parser can handle.

Scope
-----
SUPPORTED AST nodes (raises ``AstCompileError`` for anything else):
  - Literals: NumberExpression / StringExpression / BooleanExpression /
    NullExpression / ArrayExpression
  - VariableExpression — resolved via ``_resolve_single_field`` with
    ``compiled_calcs`` support (Phase 2)
  - MemberAccessExpression — for ``dim$prop`` style access via
    identifier path compaction; real method calls are handled via
    ``FunctionCallExpression`` dispatch.
  - BinaryExpression — all ``BinaryOperator`` variants
  - UnaryExpression — NEGATE / NOT
  - TernaryExpression — ``a ? b : c`` → ``CASE WHEN a THEN b ELSE c END``
  - FunctionCallExpression —
    * plain call (``function=VariableExpression``) → arity validation +
      dialect routing (``SemanticQueryService._emit_function_call``)
    * method call (``function=MemberAccessExpression``) → translation
      table below
  - Sentinel ``__FSQL_IF__`` — the textual rewrite of ``IF(...)`` done
    by :func:`_preprocess_if` before parsing

UNSUPPORTED (calls ``AstCompileError`` to trigger fallback):
  - Anything else (assignment, function def, return, block, for/while, etc.)

Expression kinds the Python fsscript parser **cannot** currently parse
(``IS NULL``, ``BETWEEN``, ``LIKE``, ``CAST (x AS type)``, SQL ``CASE
WHEN ... END``) do not reach this module at all — the caller catches the
parser error and falls back to the character-level tokenizer.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from foggy.fsscript.expressions.literals import (
    NumberExpression,
    StringExpression,
    BooleanExpression,
    NullExpression,
    ArrayExpression,
    LiteralExpression,
)
from foggy.fsscript.expressions.operators import (
    BinaryExpression,
    BinaryOperator,
    UnaryExpression,
    UnaryOperator,
    TernaryExpression,
)
from foggy.fsscript.expressions.variables import (
    VariableExpression,
    MemberAccessExpression,
)
from foggy.fsscript.expressions.functions import FunctionCallExpression
from foggy.fsscript.parser import FsscriptParser
from foggy.fsscript.parser.errors import ParseError
from foggy.fsscript.parser.tokens import TokenType
from foggy.dataset_model.semantic.inline_expression import skip_string_literal

if TYPE_CHECKING:
    from foggy.dataset_model.semantic.service import SemanticQueryService
    from foggy.dataset_model.impl.model import DbTableModelImpl


__all__ = [
    "render_with_ast",
    "AstCompileError",
    "FsscriptToSqlVisitor",
]


# Sentinel name used to route ``IF(a, b, c)`` through the function-call
# node (the fsscript parser treats bare ``IF`` as a statement keyword).
_IF_SENTINEL = "__FSQL_IF__"


class AstCompileError(ValueError):
    """Raised when the visitor encounters a node it cannot translate.

    Callers (typically ``SemanticQueryService._render_expression``) catch
    this and fall back to the character-level tokenizer.  Inheriting from
    ``ValueError`` keeps the usual exception hierarchy intact.
    """


# --------------------------------------------------------------------------- #
# IF(...) pre-processing
# --------------------------------------------------------------------------- #

# Matches IF followed by optional whitespace and an open-paren at a word
# boundary.  Skips the case where IF is inside an identifier (e.g.
# ``MODIFIED_AT``) because ``\b`` won't fire between two word chars.
_IF_RE = re.compile(r"\bIF\s*\(", re.IGNORECASE)


def _preprocess_if(source: str) -> str:
    """Rename ``IF(`` → ``__FSQL_IF__(`` outside string literals.

    Needed because the fsscript parser treats ``IF``/``if`` as a
    reserved statement keyword and rejects it in expression position.
    Uses :func:`skip_string_literal` to step past quoted sections so
    ``'IF(x)'`` inside a string stays unchanged.
    """
    if not source:
        return source
    out: List[str] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch in ("'", '"'):
            end = skip_string_literal(source, i)
            out.append(source[i:end])
            i = end
            continue
        m = _IF_RE.match(source, i)
        if m and not (i > 0 and source[i - 1] == "$"):
            # `$` is a fsscript identifier-continuation char; guard
            # against rewriting e.g. ``dim$IF(...)``.
            out.append(_IF_SENTINEL + "(")
            i = m.end()
            continue
        out.append(ch)
        i += 1
    return "".join(out)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def render_with_ast(
    expression: str,
    *,
    service: "SemanticQueryService",
    model: "DbTableModelImpl",
    ensure_join: Optional[Callable] = None,
    compiled_calcs: Optional[Dict[str, str]] = None,
) -> str:
    """Compile ``expression`` to SQL via the fsscript AST visitor.

    Raises:
        AstCompileError: if (a) the expression fails to parse, or (b)
            contains an AST node the visitor cannot translate.  The caller
            is expected to fall back to the character-level tokenizer.
    """
    if expression is None:
        raise AstCompileError("expression is None")
    rewritten = _preprocess_if(expression)
    try:
        parser = FsscriptParser(rewritten)
        ast = parser.parse_expression()
    except ParseError as e:
        raise AstCompileError(f"fsscript parser failed: {e}") from e
    # ``parse_expression`` silently stops at the first un-parseable token
    # without raising.  Any trailing content (other than EOF or a
    # statement-terminator) signals a construct the visitor cannot
    # handle safely — fall back to the char tokenizer.
    remaining = getattr(parser, "_current_token", None)
    if remaining is not None and remaining.type not in (
        TokenType.EOF,
        TokenType.SEMICOLON,
    ):
        raise AstCompileError(
            f"trailing tokens after expression: {remaining.type.name}"
        )

    visitor = FsscriptToSqlVisitor(
        service=service,
        model=model,
        ensure_join=ensure_join,
        compiled_calcs=compiled_calcs,
    )
    return visitor.visit(ast)


# --------------------------------------------------------------------------- #
# Visitor
# --------------------------------------------------------------------------- #


class FsscriptToSqlVisitor:
    """Walks a fsscript AST and emits dialect-aware SQL fragments."""

    def __init__(
        self,
        service: "SemanticQueryService",
        model: "DbTableModelImpl",
        ensure_join: Optional[Callable] = None,
        compiled_calcs: Optional[Dict[str, str]] = None,
    ):
        self.service = service
        self.model = model
        self.ensure_join = ensure_join
        self.compiled_calcs = compiled_calcs or {}

    # -- Main dispatch ---------------------------------------------------- #

    def visit(self, node: Any) -> str:
        # Order by expected frequency for minor perf.
        if isinstance(node, VariableExpression):
            return self._visit_variable(node)
        if isinstance(node, BinaryExpression):
            return self._visit_binary(node)
        if isinstance(node, FunctionCallExpression):
            return self._visit_function_call(node)
        if isinstance(node, NumberExpression):
            return self._visit_number(node)
        if isinstance(node, StringExpression):
            return self._visit_string(node)
        if isinstance(node, BooleanExpression):
            return self._visit_bool(node)
        if isinstance(node, NullExpression):
            return "NULL"
        if isinstance(node, ArrayExpression):
            return self._visit_array(node)
        if isinstance(node, UnaryExpression):
            return self._visit_unary(node)
        if isinstance(node, TernaryExpression):
            return self._visit_ternary(node)
        if isinstance(node, MemberAccessExpression):
            return self._visit_member_access(node)
        if isinstance(node, LiteralExpression):
            # Generic literal fallback (not typically hit for NUMBER/STRING)
            return self._emit_literal(node.value)

        raise AstCompileError(
            f"AST node not supported by SQL visitor: {type(node).__name__}"
        )

    # -- Literals --------------------------------------------------------- #

    def _visit_number(self, node: NumberExpression) -> str:
        v = node.value
        # Preserve integer-looking numbers to avoid ``1.0`` → ``1.0`` in SQL
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)

    def _visit_string(self, node: StringExpression) -> str:
        # Re-quote as SQL single-quoted, doubling embedded quotes.  The
        # parser already unescaped the literal so we're operating on the
        # logical value.
        raw = node.value or ""
        return "'" + raw.replace("'", "''") + "'"

    def _visit_bool(self, node: BooleanExpression) -> str:
        return "TRUE" if node.value else "FALSE"

    def _visit_array(self, node: ArrayExpression) -> str:
        # Arrays appear as the RHS of `IN` / `NOT IN`; the binary handler
        # formats them as ``(a, b, c)``.  Any other context is unusual —
        # emit a parenthesized comma list as a sane default and let the
        # caller handle semantics.
        parts = [self.visit(e) for e in (node.elements or [])]
        return "(" + ", ".join(parts) + ")"

    def _emit_literal(self, v: Any) -> str:
        if v is None:
            return "NULL"
        if isinstance(v, bool):
            return "TRUE" if v else "FALSE"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, str):
            return "'" + v.replace("'", "''") + "'"
        raise AstCompileError(f"Cannot emit literal of type {type(v).__name__}")

    # -- Identifiers ------------------------------------------------------ #

    def _visit_variable(self, node: VariableExpression) -> str:
        name = node.name
        # fsscript builtins that leak into expressions (NULL / TRUE / FALSE
        # are parsed as dedicated literal nodes, so we don't see them here
        # as VariableExpression).  Fall through to field resolution.
        return self.service._resolve_single_field(
            name,
            self.model,
            self.ensure_join,
            self.compiled_calcs,
        )

    def _visit_member_access(self, node: MemberAccessExpression) -> str:
        """Handle ``a.b`` / ``a.b.c`` as a **dotted identifier chain**.

        fsscript's parser builds MemberAccessExpression for any ``.``
        operator; in SQL context we treat the chain as a single dotted
        field name (``dim.sub`` etc.) and delegate to
        ``_resolve_single_field``.  If the field can't be resolved the
        fallback behaviour (return literal name) matches the char
        tokenizer.

        Note: when this node is the function of a ``FunctionCallExpression``,
        it's handled by ``_visit_function_call`` as a method call — this
        path is only reached when the member expression stands alone.
        """
        path = self._collect_member_path(node)
        dotted = ".".join(path)
        return self.service._resolve_single_field(
            dotted,
            self.model,
            self.ensure_join,
            self.compiled_calcs,
        )

    @staticmethod
    def _collect_member_path(node: MemberAccessExpression) -> List[str]:
        parts: List[str] = []
        cur: Any = node
        while isinstance(cur, MemberAccessExpression):
            parts.insert(0, cur.member)
            cur = cur.obj
        if isinstance(cur, VariableExpression):
            parts.insert(0, cur.name)
        else:
            raise AstCompileError(
                f"Member access base must be a variable, got {type(cur).__name__}"
            )
        return parts

    # -- Operators -------------------------------------------------------- #

    _BINARY_SQL_OP = {
        BinaryOperator.ADD: "+",
        BinaryOperator.SUBTRACT: "-",
        BinaryOperator.MULTIPLY: "*",
        BinaryOperator.DIVIDE: "/",
        BinaryOperator.MODULO: "%",
        # POWER has no universal SQL infix; fall through to POWER() call
        # via a dedicated branch.
        BinaryOperator.EQUAL: "=",
        BinaryOperator.NOT_EQUAL: "<>",  # normalized from != for SQL portability
        BinaryOperator.LESS: "<",
        BinaryOperator.LESS_EQUAL: "<=",
        BinaryOperator.GREATER: ">",
        BinaryOperator.GREATER_EQUAL: ">=",
        BinaryOperator.AND: "AND",
        BinaryOperator.OR: "OR",
        BinaryOperator.CONCAT: None,  # handled via dialect string concat
    }

    def _visit_binary(self, node: BinaryExpression) -> str:
        op = node.operator

        # IN / NOT IN: RHS is an ArrayExpression; emit `(a, b, c)` directly.
        if op in (BinaryOperator.IN, BinaryOperator.NOT_IN):
            left_sql = self.visit(node.left)
            right_sql = self._emit_in_rhs(node.right)
            sql_op = "IN" if op == BinaryOperator.IN else "NOT IN"
            return f"{left_sql} {sql_op} {right_sql}"

        # NULL coalescing: `a ?? b` → COALESCE(a, b)
        if op == BinaryOperator.NULL_COALESCE:
            left_sql = self.visit(node.left)
            right_sql = self.visit(node.right)
            # Route through dialect for potential IFNULL/ISNULL rename;
            # default emission is COALESCE which is ANSI-standard.
            return self.service._emit_function_call("COALESCE", [left_sql, right_sql])

        # INSTANCEOF has no SQL equivalent
        if op == BinaryOperator.INSTANCEOF:
            raise AstCompileError("`instanceof` is not translatable to SQL")

        # POWER: emit POWER() function call via dialect routing
        if op == BinaryOperator.POWER:
            left_sql = self.visit(node.left)
            right_sql = self.visit(node.right)
            return self.service._emit_function_call("POWER", [left_sql, right_sql])

        # String concat: route through dialect (||/CONCAT/+)
        if op == BinaryOperator.CONCAT:
            left_sql = self.visit(node.left)
            right_sql = self.visit(node.right)
            dialect = getattr(self.service, "_dialect", None)
            if dialect is not None and hasattr(dialect, "get_string_concat_sql"):
                return dialect.get_string_concat_sql(left_sql, right_sql)
            # Default to ANSI ||
            return f"{left_sql} || {right_sql}"

        sql_op = self._BINARY_SQL_OP.get(op)
        if sql_op is None:
            raise AstCompileError(f"Binary operator not supported: {op.value}")

        left_sql = self.visit(node.left)
        right_sql = self.visit(node.right)
        # Wrap operands defensively when they themselves carry lower-precedence
        # operators.  The fsscript parser already builds a correctly-nested
        # AST, so each operand visit() result is already well-formed; we only
        # need outer parens if the operand is a BinaryExpression / UnaryExpression
        # / TernaryExpression to avoid operator-precedence surprises when the
        # same SQL string is embedded as a sub-expression elsewhere.
        left_sql = self._maybe_wrap(node.left, left_sql)
        right_sql = self._maybe_wrap(node.right, right_sql)
        return f"{left_sql} {sql_op} {right_sql}"

    def _emit_in_rhs(self, node: Any) -> str:
        if isinstance(node, ArrayExpression):
            parts = [self.visit(e) for e in (node.elements or [])]
            return "(" + ", ".join(parts) + ")"
        # Variable / function call that evaluates to a list — not typical
        # in SQL; wrap the value in parens and hope for the best.
        return "(" + self.visit(node) + ")"

    @staticmethod
    def _maybe_wrap(node: Any, sql: str) -> str:
        if isinstance(node, (BinaryExpression, TernaryExpression)):
            return f"({sql})"
        return sql

    def _visit_unary(self, node: UnaryExpression) -> str:
        operand_sql = self.visit(node.operand)
        if isinstance(node.operand, (BinaryExpression, TernaryExpression)):
            operand_sql = f"({operand_sql})"

        op = node.operator
        if op == UnaryOperator.NEGATE:
            return f"-{operand_sql}"
        if op == UnaryOperator.NOT:
            return f"NOT {operand_sql}"
        if op == UnaryOperator.BITWISE_NOT:
            return f"~{operand_sql}"
        # TYPEOF is non-SQL
        raise AstCompileError(f"Unary operator not supported: {op.value}")

    def _visit_ternary(self, node: TernaryExpression) -> str:
        cond_sql = self.visit(node.condition)
        then_sql = self.visit(node.then_expr)
        else_sql = self.visit(node.else_expr)
        return f"CASE WHEN {cond_sql} THEN {then_sql} ELSE {else_sql} END"

    # -- Function / method calls ----------------------------------------- #

    def _visit_function_call(self, node: FunctionCallExpression) -> str:
        fn = node.function

        # Method call: function is a MemberAccessExpression (``obj.method``)
        if isinstance(fn, MemberAccessExpression):
            return self._visit_method_call(fn, node.arguments)

        # Plain call: function must be a simple name
        if not isinstance(fn, VariableExpression):
            raise AstCompileError(
                f"Cannot compile call on {type(fn).__name__}; expected "
                f"an identifier or method reference."
            )
        func_name_raw = fn.name
        func_name = func_name_raw.upper()

        # Demangle the IF sentinel back to "IF" for error messages and
        # CASE WHEN emission.
        if func_name == _IF_SENTINEL:
            return self._emit_if(node.arguments)

        # Whitelist + arity check via service helpers (Phase 1).
        if func_name not in self.service._ALLOWED_FUNCTIONS and \
                func_name not in self.service._SQL_KEYWORDS:
            raise AstCompileError(
                f"Function '{func_name_raw}' is not in the allowed whitelist"
            )

        args_sql = [self.visit(a) for a in node.arguments]

        if func_name not in self.service._KEYWORD_DELIMITED_FUNCTIONS:
            self.service._validate_function_arity(
                func_name,
                len(args_sql),
                f"{func_name_raw}(...)",  # source context for error msg
            )

        return self.service._emit_function_call(func_name, args_sql)

    def _emit_if(self, args: List[Any]) -> str:
        """Emit ``CASE WHEN cond THEN then ELSE else END`` for ``IF(...)``.

        Validates arity using the regular service helper so the error
        message matches pre-Phase-3 wording (``Function 'IF' expects
        exactly 3 arguments, got N``).
        """
        self.service._validate_function_arity("IF", len(args), "IF(...)")
        cond_sql = self.visit(args[0])
        then_sql = self.visit(args[1])
        else_sql = self.visit(args[2])
        return f"CASE WHEN {cond_sql} THEN {then_sql} ELSE {else_sql} END"

    def _visit_method_call(
        self,
        member: MemberAccessExpression,
        args: List[Any],
    ) -> str:
        """Translate ``s.method(...)`` into SQL.

        Dispatched on ``method.lower()``; all translations assume ``s``
        is a string-valued expression (field or expression).  For
        non-string receivers the generated SQL will be rejected by the
        database, same as other type-related errors.
        """
        obj_sql = self.visit(member.obj)
        method_name_raw = member.member
        method_name = method_name_raw.lower()
        args_sql = [self.visit(a) for a in args]
        return self._emit_string_method(obj_sql, method_name, args_sql, method_name_raw)

    # --- Method translations ---

    def _emit_string_method(
        self,
        obj_sql: str,
        method: str,
        args_sql: List[str],
        method_raw: str,
    ) -> str:
        """Emit SQL for a supported string method.

        Mapping rules (mirror Java fsscript intent):
          startsWith(x) → ``s LIKE concat(x, '%')``
          endsWith(x)   → ``s LIKE concat('%', x)``
          contains(x)   → ``s LIKE concat('%', x, '%')``
          toUpperCase() → ``UPPER(s)``
          toLowerCase() → ``LOWER(s)``
          trim()        → ``TRIM(s)``
          length()      → ``LENGTH(s)`` (dialect may rename to LEN)
        """
        if method == "startswith":
            self._check_method_arity(method_raw, args_sql, 1)
            prefix_concat = self._dialect_concat([args_sql[0], "'%'"])
            return f"{obj_sql} LIKE {prefix_concat}"
        if method == "endswith":
            self._check_method_arity(method_raw, args_sql, 1)
            suffix_concat = self._dialect_concat(["'%'", args_sql[0]])
            return f"{obj_sql} LIKE {suffix_concat}"
        if method == "contains":
            self._check_method_arity(method_raw, args_sql, 1)
            mid_concat = self._dialect_concat(["'%'", args_sql[0], "'%'"])
            return f"{obj_sql} LIKE {mid_concat}"
        if method == "touppercase":
            self._check_method_arity(method_raw, args_sql, 0)
            return self.service._emit_function_call("UPPER", [obj_sql])
        if method == "tolowercase":
            self._check_method_arity(method_raw, args_sql, 0)
            return self.service._emit_function_call("LOWER", [obj_sql])
        if method == "trim":
            self._check_method_arity(method_raw, args_sql, 0)
            return self.service._emit_function_call("TRIM", [obj_sql])
        if method == "length":
            # length() — with or without parens is acceptable
            if args_sql:
                raise AstCompileError(
                    f"Method '.length' takes no arguments, got {len(args_sql)}"
                )
            return self.service._emit_function_call("LENGTH", [obj_sql])
        raise AstCompileError(f"Unsupported string method: {method_raw}")

    @staticmethod
    def _check_method_arity(method_raw: str, args_sql: List[str], expected: int) -> None:
        if len(args_sql) != expected:
            raise AstCompileError(
                f"Method '.{method_raw}' expects {expected} "
                f"argument{'s' if expected != 1 else ''}, got {len(args_sql)}"
            )

    def _dialect_concat(self, parts_sql: List[str]) -> str:
        """Emit a dialect-appropriate string concatenation expression.

        Uses ``FDialect.get_string_concat_sql`` when available (pre-existing
        interface), otherwise defaults to ANSI ``||``.
        """
        dialect = getattr(self.service, "_dialect", None)
        if dialect is not None and hasattr(dialect, "get_string_concat_sql"):
            return dialect.get_string_concat_sql(*parts_sql)
        return " || ".join(parts_sql)
