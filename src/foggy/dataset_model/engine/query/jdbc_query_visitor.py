"""
SQL Query Visitor - SQL 生成访问者

基于 Java JdbcQueryVisitor 接口迁移
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from enum import Enum


class JdbcQuery:
    """JDBC 查询对象"""

    @dataclass
    class JdbcSelect:
        """SELECT 子句"""
        columns: List[str] = field(default_factory=list)
        distinct: bool = False

    @dataclass
    class JdbcFrom:
        """FROM 子句"""
        table_name: str = ""
        alias: Optional[str] = None
        joins: List['JdbcQuery.JdbcJoin'] = field(default_factory=list)

    @dataclass
    class JdbcJoin:
        """JOIN 子句"""
        join_type: str = "INNER"  # INNER, LEFT, RIGHT, FULL
        table_name: str = ""
        alias: Optional[str] = None
        on_condition: Optional[str] = None

    @dataclass
    class JdbcWhere:
        """WHERE 子句"""
        conditions: List[str] = field(default_factory=list)
        params: List[Any] = field(default_factory=list)

    @dataclass
    class JdbcGroupBy:
        """GROUP BY 子句"""
        columns: List[str] = field(default_factory=list)
        having: Optional[str] = None

    @dataclass
    class JdbcHaving:
        """HAVING 子句"""
        conditions: List[str] = field(default_factory=list)
        params: List[Any] = field(default_factory=list)

    @dataclass
    class JdbcOrder:
        """ORDER BY 子句"""
        columns: List[str] = field(default_factory=list)
        directions: List[str] = field(default_factory=list)  # ASC, DESC

    def __init__(self):
        self.select: Optional[JdbcQuery.JdbcSelect] = None
        self.from_clause: Optional[JdbcQuery.JdbcFrom] = None
        self.where: Optional[JdbcQuery.JdbcWhere] = None
        self.group_by: Optional[JdbcQuery.JdbcGroupBy] = None
        self.having: Optional[JdbcQuery.JdbcHaving] = None
        self.order: Optional[JdbcQuery.JdbcOrder] = None
        self.limit: Optional[int] = None
        self.offset: Optional[int] = None


class JdbcQueryVisitor(ABC):
    """
    JDBC 查询访问者接口

    用于遍历查询对象并生成 SQL。
    遵循访问者模式，允许不同的实现方式。
    """

    @abstractmethod
    def accept_select(self, select: JdbcQuery.JdbcSelect) -> None:
        """接受 SELECT 子句"""
        pass

    @abstractmethod
    def accept_from(self, from_clause: JdbcQuery.JdbcFrom) -> None:
        """接受 FROM 子句"""
        pass

    @abstractmethod
    def accept_where(self, where: JdbcQuery.JdbcWhere) -> None:
        """接受 WHERE 子句"""
        pass

    @abstractmethod
    def accept_group(self, group: JdbcQuery.JdbcGroupBy) -> None:
        """接受 GROUP BY 子句"""
        pass

    @abstractmethod
    def accept_having(self, having: JdbcQuery.JdbcHaving) -> None:
        """接受 HAVING 子句"""
        pass

    @abstractmethod
    def accept_order(self, order: JdbcQuery.JdbcOrder) -> None:
        """接受 ORDER BY 子句"""
        pass


class DefaultJdbcQueryVisitor(JdbcQueryVisitor):
    """
    默认的 JDBC 查询访问者实现

    生成标准 SQL 语句。
    """

    def __init__(self, dialect: Optional[Any] = None):
        """
        初始化访问者

        Args:
            dialect: 数据库方言，用于生成特定数据库的 SQL
        """
        self.dialect = dialect
        self._sql_parts: List[str] = []
        self._params: List[Any] = []

    def accept_select(self, select: JdbcQuery.JdbcSelect) -> None:
        """处理 SELECT 子句"""
        if not select.columns:
            self._sql_parts.append("SELECT *")
            return

        distinct = "DISTINCT " if select.distinct else ""
        columns = ", ".join(select.columns)
        self._sql_parts.append(f"SELECT {distinct}{columns}")

    def accept_from(self, from_clause: JdbcQuery.JdbcFrom) -> None:
        """处理 FROM 子句"""
        table = from_clause.table_name
        if from_clause.alias:
            table = f"{table} AS {from_clause.alias}"
        self._sql_parts.append(f"FROM {table}")

        # 处理 JOIN
        for join in from_clause.joins:
            join_table = join.table_name
            if join.alias:
                join_table = f"{join_table} AS {join.alias}"

            join_sql = f"{join.join_type} JOIN {join_table}"
            if join.on_condition:
                join_sql += f" ON {join.on_condition}"
            self._sql_parts.append(join_sql)

    def accept_where(self, where: JdbcQuery.JdbcWhere) -> None:
        """处理 WHERE 子句"""
        if where.conditions:
            condition = " AND ".join(where.conditions)
            self._sql_parts.append(f"WHERE {condition}")
            self._params.extend(where.params)

    def accept_group(self, group: JdbcQuery.JdbcGroupBy) -> None:
        """处理 GROUP BY 子句"""
        if group.columns:
            columns = ", ".join(group.columns)
            self._sql_parts.append(f"GROUP BY {columns}")

    def accept_having(self, having: JdbcQuery.JdbcHaving) -> None:
        """处理 HAVING 子句"""
        if having.conditions:
            condition = " AND ".join(having.conditions)
            self._sql_parts.append(f"HAVING {condition}")
            self._params.extend(having.params)

    def accept_order(self, order: JdbcQuery.JdbcOrder) -> None:
        """处理 ORDER BY 子句"""
        if order.columns:
            order_parts = []
            for col, direction in zip(order.columns, order.directions):
                order_parts.append(f"{col} {direction}")
            self._sql_parts.append(f"ORDER BY {', '.join(order_parts)}")

    def get_sql(self) -> str:
        """获取生成的 SQL"""
        return "\n".join(self._sql_parts)

    def get_params(self) -> List[Any]:
        """获取参数列表"""
        return self._params

    def reset(self) -> None:
        """重置状态"""
        self._sql_parts = []
        self._params = []


class SqlQueryBuilder:
    """
    SQL 查询构建器

    提供流畅的 API 来构建 SQL 查询。
    """

    def __init__(self, dialect: Optional[Any] = None):
        self._query = JdbcQuery()
        self._dialect = dialect

    def select(self, *columns: str) -> 'SqlQueryBuilder':
        """设置 SELECT 列"""
        if not self._query.select:
            self._query.select = JdbcQuery.JdbcSelect()
        self._query.select.columns.extend(columns)
        return self

    def distinct(self, value: bool = True) -> 'SqlQueryBuilder':
        """设置 DISTINCT"""
        if not self._query.select:
            self._query.select = JdbcQuery.JdbcSelect()
        self._query.select.distinct = value
        return self

    def from_table(self, table_name: str, alias: Optional[str] = None) -> 'SqlQueryBuilder':
        """设置 FROM 表"""
        self._query.from_clause = JdbcQuery.JdbcFrom(
            table_name=table_name,
            alias=alias
        )
        return self

    def join(self, join_type: str, table_name: str,
             alias: Optional[str] = None,
             on_condition: Optional[str] = None) -> 'SqlQueryBuilder':
        """添加 JOIN"""
        if self._query.from_clause:
            join = JdbcQuery.JdbcJoin(
                join_type=join_type,
                table_name=table_name,
                alias=alias,
                on_condition=on_condition
            )
            self._query.from_clause.joins.append(join)
        return self

    def left_join(self, table_name: str,
                  alias: Optional[str] = None,
                  on_condition: Optional[str] = None) -> 'SqlQueryBuilder':
        """LEFT JOIN"""
        return self.join("LEFT", table_name, alias, on_condition)

    def inner_join(self, table_name: str,
                   alias: Optional[str] = None,
                   on_condition: Optional[str] = None) -> 'SqlQueryBuilder':
        """INNER JOIN"""
        return self.join("INNER", table_name, alias, on_condition)

    def where(self, *conditions: str, params: Optional[List[Any]] = None) -> 'SqlQueryBuilder':
        """添加 WHERE 条件"""
        if not self._query.where:
            self._query.where = JdbcQuery.JdbcWhere()
        self._query.where.conditions.extend(conditions)
        if params:
            self._query.where.params.extend(params)
        return self

    def group_by(self, *columns: str) -> 'SqlQueryBuilder':
        """设置 GROUP BY"""
        if not self._query.group_by:
            self._query.group_by = JdbcQuery.JdbcGroupBy()
        self._query.group_by.columns.extend(columns)
        return self

    def having(self, *conditions: str, params: Optional[List[Any]] = None) -> 'SqlQueryBuilder':
        """添加 HAVING 条件"""
        if not self._query.having:
            self._query.having = JdbcQuery.JdbcHaving()
        self._query.having.conditions.extend(conditions)
        if params:
            self._query.having.params.extend(params)
        return self

    def order_by(self, column: str, direction: str = "ASC") -> 'SqlQueryBuilder':
        """添加 ORDER BY"""
        if not self._query.order:
            self._query.order = JdbcQuery.JdbcOrder()
        self._query.order.columns.append(column)
        self._query.order.directions.append(direction)
        return self

    def limit(self, value: int) -> 'SqlQueryBuilder':
        """设置 LIMIT"""
        self._query.limit = value
        return self

    def offset(self, value: int) -> 'SqlQueryBuilder':
        """设置 OFFSET"""
        self._query.offset = value
        return self

    def build(self, visitor: Optional[JdbcQueryVisitor] = None) -> tuple:
        """
        构建 SQL

        Returns:
            tuple: (sql, params)
        """
        if visitor is None:
            visitor = DefaultJdbcQueryVisitor(self._dialect)

        if self._query.select:
            visitor.accept_select(self._query.select)
        if self._query.from_clause:
            visitor.accept_from(self._query.from_clause)
        if self._query.where:
            visitor.accept_where(self._query.where)
        if self._query.group_by:
            visitor.accept_group(self._query.group_by)
        if self._query.having:
            visitor.accept_having(self._query.having)
        if self._query.order:
            visitor.accept_order(self._query.order)

        if isinstance(visitor, DefaultJdbcQueryVisitor):
            sql = visitor.get_sql()
            params = visitor.get_params()

            # 添加分页
            if self._query.limit is not None:
                if self._query.offset is not None:
                    sql += f"\nLIMIT {self._query.limit} OFFSET {self._query.offset}"
                else:
                    sql += f"\nLIMIT {self._query.limit}"

            return sql, params

        return "", []


# 便捷函数
def select(*columns: str) -> SqlQueryBuilder:
    """创建 SELECT 查询"""
    builder = SqlQueryBuilder()
    return builder.select(*columns)


def query() -> SqlQueryBuilder:
    """创建查询构建器"""
    return SqlQueryBuilder()