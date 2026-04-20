"""SQL dialect abstraction for formula compiler.

Spec v1 grammar.md §6.2 定义了三个方言特化函数：
- date_diff(a, b) 返回 a - b 天数
- date_add(d, n, unit) 单位 ∈ {day, month, year}
- now() 当前时间戳

其他函数（if / in / coalesce / is_null / between / abs / round / ceil / floor）
在 §6.1 四方言一致，不走本模块。

本模块是 M2 Step 2.4 的产出骨架，M2 Step 2.3 SQL 生成时调用。

实现位置：
- Python 端：本模块提供方言 SQL 片段
- Java 端：对应 `DialectAwareFunctionExp` + `FDialect.buildDateDiffExpression/buildDateAddExpression`（M3 Step 3.4）

Parity 要求：Java/Python 两端对同一方言输出的 SQL 字符串**归一化后一致**。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

# 合法单位（Spec v1 §3.6）
DateAddUnit = Literal["day", "month", "year"]


class SqlDialect(ABC):
    """方言抽象。每方言实现 SQL 片段生成。

    实例化前应调用 `SqlDialect.of(name)` 工厂方法。
    """

    # 方言名（'mysql' / 'postgres' / 'sqlserver' / 'sqlite'）
    name: str

    @abstractmethod
    def date_diff_expr(self, a_sql: str, b_sql: str) -> str:
        """生成 `a - b` 天数的 SQL 片段（Spec v1 §6.2）。

        Args:
            a_sql: 左表达式编译好的 SQL 片段
            b_sql: 右表达式编译好的 SQL 片段

        Returns:
            方言特化的 SQL 片段
        """
        raise NotImplementedError

    @abstractmethod
    def date_add_expr(self, d_sql: str, n_param_placeholder: str, unit: DateAddUnit) -> str:
        """生成 `d + n unit` 的 SQL 片段（Spec v1 §6.2）。

        Args:
            d_sql: 日期表达式编译好的 SQL 片段
            n_param_placeholder: n 的参数占位符（通常是 '?'；n 必须走 bind_params）
            unit: 单位，必须是 DateAddUnit 之一

        Returns:
            方言特化的 SQL 片段
        """
        raise NotImplementedError

    @abstractmethod
    def now_expr(self) -> str:
        """生成当前时间戳的 SQL 片段。"""
        raise NotImplementedError

    @classmethod
    def of(cls, name: str) -> "SqlDialect":
        """工厂方法，按名字返回方言实例。

        Args:
            name: 'mysql' / 'postgres' / 'sqlserver' / 'sqlite'

        Raises:
            ValueError: 未知方言名
        """
        name_lower = name.lower()
        mapping: dict[str, type[SqlDialect]] = {
            "mysql": MysqlDialect,
            "postgres": PostgresDialect,
            "postgresql": PostgresDialect,
            "sqlserver": SqlServerDialect,
            "mssql": SqlServerDialect,
            "sqlite": SqliteDialect,
        }
        cls_ref = mapping.get(name_lower)
        if cls_ref is None:
            raise ValueError(
                f"Unknown dialect: {name}. Supported: mysql, postgres, sqlserver, sqlite"
            )
        return cls_ref()


class MysqlDialect(SqlDialect):
    """MySQL 5.7+ 方言。"""

    name = "mysql"

    def date_diff_expr(self, a_sql: str, b_sql: str) -> str:
        return f"DATEDIFF({a_sql}, {b_sql})"

    def date_add_expr(self, d_sql: str, n_param_placeholder: str, unit: DateAddUnit) -> str:
        return f"DATE_ADD({d_sql}, INTERVAL {n_param_placeholder} {unit.upper()})"

    def now_expr(self) -> str:
        return "NOW()"


class PostgresDialect(SqlDialect):
    """PostgreSQL 12+ 方言。"""

    name = "postgres"

    def date_diff_expr(self, a_sql: str, b_sql: str) -> str:
        return f"({a_sql}::date - {b_sql}::date)"

    def date_add_expr(self, d_sql: str, n_param_placeholder: str, unit: DateAddUnit) -> str:
        # B-4: PG 走 make_interval 让 n 走参数绑定（不拼接到 INTERVAL 字符串）
        unit_field = {"day": "days", "month": "months", "year": "years"}[unit]
        return f"({d_sql} + make_interval({unit_field} => {n_param_placeholder}))"

    def now_expr(self) -> str:
        return "NOW()"


class SqlServerDialect(SqlDialect):
    """SQL Server 2012+ 方言。"""

    name = "sqlserver"

    def date_diff_expr(self, a_sql: str, b_sql: str) -> str:
        # MSSQL DATEDIFF(unit, start, end) 返回 end - start，
        # Spec 约定 date_diff(a, b) = a - b，所以 MSSQL 是 DATEDIFF(day, b, a)
        return f"DATEDIFF(day, {b_sql}, {a_sql})"

    def date_add_expr(self, d_sql: str, n_param_placeholder: str, unit: DateAddUnit) -> str:
        return f"DATEADD({unit}, {n_param_placeholder}, {d_sql})"

    def now_expr(self) -> str:
        return "GETDATE()"


class SqliteDialect(SqlDialect):
    """SQLite 3.30+ 方言。"""

    name = "sqlite"

    def date_diff_expr(self, a_sql: str, b_sql: str) -> str:
        return f"CAST((julianday({a_sql}) - julianday({b_sql})) AS INTEGER)"

    def date_add_expr(self, d_sql: str, n_param_placeholder: str, unit: DateAddUnit) -> str:
        # SQLite date 修饰符：`+N unit`，走字符串拼接；n 需要作为参数绑定后再拼
        return f"date({d_sql}, '+' || {n_param_placeholder} || ' {unit}')"

    def now_expr(self) -> str:
        return "datetime('now')"
