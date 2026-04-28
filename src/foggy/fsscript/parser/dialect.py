"""FSScript dialect abstraction.

一个 dialect 描述 parser 对保留字的处理差异。让上层使用者（如 formula
compiler）可以声明 "在我的场景里 `if` 不是保留字，是普通函数名"，而无需
在源码字符串层面做预处理。

设计目标
========
- **零对外行为变化（默认路径）**：未指定 dialect 或显式指定 `DEFAULT_DIALECT` 时，
  `FsscriptLexer` 行为与历史完全一致（直接复用模块级 `KEYWORDS`）。
- **per-parser-instance**：dialect 是 parser 实例局部状态，不引入全局开关，
  不修改 `KEYWORDS` 模块常量本身。
- **零循环依赖**：本模块只依赖 `tokens.py`；`lexer.py` 不会回头 import 本模块。

Thread-safe
===========
`FsscriptDialect` 是 `frozen=True` dataclass，无可变状态，可在多线程共享。
`effective_keywords()` 每次返回新 dict，调用方可自由 mutate 不污染源。

Usage
=====
    from foggy.fsscript.parser import FsscriptParser, SQL_EXPRESSION_DIALECT

    tree = FsscriptParser(
        "if(a > 0, a, 0)", dialect=SQL_EXPRESSION_DIALECT,
    ).parse_expression()
    # tree -> FunctionCallExpression(function=VariableExpression('if'), ...)

    # 自定义方言示例
    custom = FsscriptDialect(
        name="permissive",
        keywords_override={"if": None, "switch": None},
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from foggy.fsscript.parser.tokens import KEYWORDS, TokenType


@dataclass(frozen=True)
class FsscriptDialect:
    """FSScript 方言。

    Attributes:
        name: 方言名（日志 / 调试 / 错误消息用）。
        keywords_override: 关键字覆写映射。
            - 键：lower-case 标识符（与 KEYWORDS 保持同一 case 规范）。
            - 值为 ``TokenType``：在该 dialect 下把这个词识别为指定保留字 token。
            - 值为 ``None``：把这个词从保留字集合移除，让它走 IDENTIFIER 路径。
            - 未在此映射的词：沿用默认 ``KEYWORDS`` 行为。
    """

    name: str
    keywords_override: Mapping[str, Optional[TokenType]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Materialize the merged dict once and cache it on the (frozen) instance.
        # FormulaCompiler.compile() instantiates a parser per expression, which
        # in turn would re-merge this ~37-entry dict on every call without the
        # cache. Predefined singletons (DEFAULT_DIALECT / SQL_EXPRESSION_DIALECT)
        # compute it exactly once at module import.
        merged = dict(KEYWORDS)
        for key, value in self.keywords_override.items():
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
        # frozen=True blocks normal assignment; bypass via object.__setattr__.
        object.__setattr__(self, "_effective_keywords", merged)

    def effective_keywords(self) -> dict[str, TokenType]:
        """返回合并后的 keywords 字典（供 Lexer 查表）。

        合并规则：
          1. 以模块级 ``KEYWORDS`` 为基线（不污染原始常量）。
          2. ``keywords_override`` 中值为 ``TokenType`` 的项，覆盖基线。
          3. ``keywords_override`` 中值为 ``None`` 的项，从基线中删除该键
             （该词将作为 IDENTIFIER 处理）。

        合并在 ``__post_init__`` 里完成且仅一次；此方法每次返回**同一份**
        缓存字典——调用方不应 mutate 它。Lexer 也只读不改。
        """
        return self._effective_keywords  # type: ignore[attr-defined]


# ---- 预定义方言 ---------------------------------------------------------- #


DEFAULT_DIALECT: FsscriptDialect = FsscriptDialect(
    name="default", keywords_override={},
)
"""默认方言：与历史 FSScript 行为完全一致，不做任何 keywords 修改。

`FsscriptLexer(source)` / `FsscriptParser(source)` 不传 dialect 时等价于
此方言（实际实现走更快的"直接引用 KEYWORDS 常量"路径，但对外行为一致）。
"""


SQL_EXPRESSION_DIALECT: FsscriptDialect = FsscriptDialect(
    name="sql-expression",
    # 移除 `if` 保留字 → 让 `if(...)` 走 IDENTIFIER token 路径，被 parser
    # 识别为普通 FunctionCallExpression(function=VariableExpression('if'))。
    # 移除 `between` 保留字 → formula 场景用 `between(age, 18, 65)` 函数形态
    # （Stage 6 新增 BETWEEN keyword 会与此冲突，需在 formula dialect 中解保留）。
    # 其他控制流关键字（switch / for / while / try / ...）保持保留字身份，
    # 因为 SQL formula 表达式上下文不需要它们作为函数名。
    keywords_override={"if": None, "between": None},
)
"""SQL 表达式方言：用于 formula compiler / calculated field 等需要
``if(c, a, b)`` 函数形态的场景。

与 ``DEFAULT_DIALECT`` 的唯一差异：``if`` 不再是保留字。
"""


COMPOSE_QUERY_DIALECT: FsscriptDialect = FsscriptDialect(
    name="compose-query",
    # 移除 `from` 保留字 → 让 `from(...)` 走 IDENTIFIER token 路径，被
    # parser 识别为普通 FunctionCallExpression(function=VariableExpression('from'))。
    # 8.2.0.beta Compose Query 的顶层入口就叫 `from(...)`，对齐 JS 宿主
    # 脚本里 `from({model: 'X'})` 的字面形态。
    #
    # 只移除 `from`；其他保留字（包括 `if`/`import`/`export` 等）保持原状。
    # 如 compose 脚本内出现 `if(...)` 函数调用需求，另行合并
    # ``SQL_EXPRESSION_DIALECT.keywords_override``。
    keywords_override={"from": None},
)
"""Compose Query 方言：8.2.0.beta 的脚本入口需要把 ``from`` 作为普通函数名
使用（跨语言 JS 侧 ``from({model: 'X'})`` 形态的 Python 对应）。

与 ``DEFAULT_DIALECT`` 的唯一差异：``from`` 不再是保留字。

跨语言对齐：Java 侧 fsscript 在本版本里没有 `from` 保留字冲突，直接作为
标识符使用；Python 因为 fsscript 沿用 Python-风格的 `import ... from ...`
语法保留了 `FROM` token，所以需要本方言显式解保留。
"""


__all__ = [
    "FsscriptDialect",
    "DEFAULT_DIALECT",
    "SQL_EXPRESSION_DIALECT",
    "COMPOSE_QUERY_DIALECT",
]
