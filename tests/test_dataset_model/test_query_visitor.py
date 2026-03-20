"""
JdbcQueryVisitor 单元测试
"""

import pytest
from foggy.dataset_model.engine.query.jdbc_query_visitor import (
    JdbcQuery,
    JdbcQueryVisitor,
    DefaultJdbcQueryVisitor,
    SqlQueryBuilder,
    select,
    query
)


class TestJdbcQuery:
    """测试 JdbcQuery 类"""

    def test_jdbc_select_creation(self):
        """测试 SELECT 子句创建"""
        select = JdbcQuery.JdbcSelect(
            columns=["id", "name"],
            distinct=True
        )
        assert select.columns == ["id", "name"]
        assert select.distinct is True

    def test_jdbc_from_creation(self):
        """测试 FROM 子句创建"""
        from_clause = JdbcQuery.JdbcFrom(
            table_name="users",
            alias="u"
        )
        assert from_clause.table_name == "users"
        assert from_clause.alias == "u"

    def test_jdbc_where_creation(self):
        """测试 WHERE 子句创建"""
        where = JdbcQuery.JdbcWhere(
            conditions=["id = ?", "status = ?"],
            params=[1, "active"]
        )
        assert len(where.conditions) == 2
        assert len(where.params) == 2


class TestDefaultJdbcQueryVisitor:
    """测试 DefaultJdbcQueryVisitor"""

    def test_simple_select(self):
        """测试简单 SELECT"""
        visitor = DefaultJdbcQueryVisitor()
        select = JdbcQuery.JdbcSelect(columns=["id", "name"])
        visitor.accept_select(select)
        assert "SELECT id, name" in visitor.get_sql()

    def test_distinct_select(self):
        """测试 DISTINCT SELECT"""
        visitor = DefaultJdbcQueryVisitor()
        select = JdbcQuery.JdbcSelect(columns=["name"], distinct=True)
        visitor.accept_select(select)
        assert "SELECT DISTINCT name" in visitor.get_sql()

    def test_from_with_alias(self):
        """测试 FROM 带别名"""
        visitor = DefaultJdbcQueryVisitor()
        from_clause = JdbcQuery.JdbcFrom(table_name="users", alias="u")
        visitor.accept_from(from_clause)
        assert "FROM users AS u" in visitor.get_sql()

    def test_where_conditions(self):
        """测试 WHERE 条件"""
        visitor = DefaultJdbcQueryVisitor()
        where = JdbcQuery.JdbcWhere(
            conditions=["id = ?", "status = ?"],
            params=[1, "active"]
        )
        visitor.accept_where(where)
        sql = visitor.get_sql()
        assert "WHERE" in sql
        assert "id = ?" in sql
        assert visitor.get_params() == [1, "active"]

    def test_group_by(self):
        """测试 GROUP BY"""
        visitor = DefaultJdbcQueryVisitor()
        group = JdbcQuery.JdbcGroupBy(columns=["department", "status"])
        visitor.accept_group(group)
        assert "GROUP BY department, status" in visitor.get_sql()

    def test_order_by(self):
        """测试 ORDER BY"""
        visitor = DefaultJdbcQueryVisitor()
        order = JdbcQuery.JdbcOrder(
            columns=["created_at", "name"],
            directions=["DESC", "ASC"]
        )
        visitor.accept_order(order)
        assert "ORDER BY created_at DESC, name ASC" in visitor.get_sql()


class TestSqlQueryBuilder:
    """测试 SqlQueryBuilder"""

    def test_simple_query(self):
        """测试简单查询构建"""
        sql, params = (query()
            .select("id", "name")
            .from_table("users")
            .build())
        assert "SELECT id, name" in sql
        assert "FROM users" in sql

    def test_where_clause(self):
        """测试 WHERE 子句"""
        sql, params = (query()
            .select("*")
            .from_table("users")
            .where("id = ?", "status = ?", params=[1, "active"])
            .build())
        assert "WHERE" in sql
        assert params == [1, "active"]

    def test_join(self):
        """测试 JOIN"""
        sql, params = (query()
            .select("u.name", "o.total")
            .from_table("users", "u")
            .left_join("orders", "o", "u.id = o.user_id")
            .build())
        assert "LEFT JOIN orders AS o" in sql
        assert "ON u.id = o.user_id" in sql

    def test_group_by_order_by(self):
        """测试 GROUP BY 和 ORDER BY"""
        sql, params = (query()
            .select("department", "COUNT(*) as count")
            .from_table("employees")
            .group_by("department")
            .order_by("count", "DESC")
            .build())
        assert "GROUP BY department" in sql
        assert "ORDER BY count DESC" in sql

    def test_pagination(self):
        """测试分页"""
        sql, params = (query()
            .select("*")
            .from_table("users")
            .limit(10)
            .offset(20)
            .build())
        assert "LIMIT 10" in sql
        assert "OFFSET 20" in sql

    def test_distinct(self):
        """测试 DISTINCT"""
        sql, params = (query()
            .select("category")
            .distinct()
            .from_table("products")
            .build())
        assert "SELECT DISTINCT category" in sql


class TestSelectHelper:
    """测试 select 辅助函数"""

    def test_select_function(self):
        """测试 select 函数"""
        builder = select("id", "name", "email")
        assert builder is not None
        sql, _ = builder.from_table("users").build()
        assert "SELECT id, name, email" in sql