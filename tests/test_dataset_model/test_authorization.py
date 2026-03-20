"""Tests for access control (DbAccessDef) and query conditions (QueryConditionDef)."""

import pytest

from foggy.dataset_model.definitions.access import (
    AccessType,
    DbAccessDef,
    RowFilterType,
)
from foggy.dataset_model.definitions.query_model import QueryConditionDef


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_access(name: str = "test_access", **kwargs) -> DbAccessDef:
    return DbAccessDef(name=name, **kwargs)


# ===========================================================================
# TestDbAccessDef
# ===========================================================================

class TestDbAccessDef:
    """Tests for DbAccessDef creation, role checks, and validation."""

    def test_create_access_def(self):
        """Basic creation with defaults."""
        acc = _make_access()
        assert acc.name == "test_access"
        assert acc.enabled is True
        assert acc.access_type == AccessType.READ

    def test_access_type_enum(self):
        """All expected AccessType values exist."""
        assert AccessType.READ.value == "read"
        assert AccessType.WRITE.value == "write"
        assert AccessType.DELETE.value == "delete"
        assert AccessType.ADMIN.value == "admin"

    def test_row_filter_type_enum(self):
        assert RowFilterType.NONE.value == "none"
        assert RowFilterType.SQL.value == "sql"
        assert RowFilterType.EXPRESSION.value == "expression"
        assert RowFilterType.ROLE_BASED.value == "role_based"

    def test_row_filter_sql(self):
        """Row filter returns expression when enabled."""
        acc = _make_access(
            row_filter_enabled=True,
            row_filter_type=RowFilterType.SQL,
            row_filter_expression="region = 'EAST'",
        )
        assert acc.get_row_filter_sql() == "region = 'EAST'"

    def test_row_filter_disabled(self):
        """Row filter returns None when disabled."""
        acc = _make_access(row_filter_enabled=False, row_filter_expression="1=1")
        assert acc.get_row_filter_sql() is None

    def test_row_filter_missing_expression(self):
        """Row filter returns None when expression is missing even if enabled."""
        acc = _make_access(row_filter_enabled=True, row_filter_expression=None)
        assert acc.get_row_filter_sql() is None

    def test_column_mask(self):
        acc = _make_access(
            column_mask_enabled=True,
            masked_columns=["ssn", "credit_card"],
            mask_pattern="***",
        )
        assert acc.column_mask_enabled is True
        assert "ssn" in acc.masked_columns

    def test_role_allowed_basic(self):
        acc = _make_access(allowed_roles=["analyst", "admin"])
        assert acc.is_role_allowed(["analyst"]) is True
        assert acc.is_role_allowed(["guest"]) is False

    def test_role_denied_overrides_allowed(self):
        acc = _make_access(allowed_roles=["analyst"], denied_roles=["analyst"])
        assert acc.is_role_allowed(["analyst"]) is False

    def test_role_no_restrictions(self):
        """When no allowed/denied roles, everyone is allowed."""
        acc = _make_access()
        assert acc.is_role_allowed(["random_role"]) is True

    def test_disabled_access_allows_all(self):
        """When access control is disabled, all roles are allowed."""
        acc = _make_access(enabled=False, denied_roles=["everyone"])
        assert acc.is_role_allowed(["everyone"]) is True

    def test_multiple_roles_one_allowed(self):
        acc = _make_access(allowed_roles=["admin"])
        assert acc.is_role_allowed(["guest", "admin"]) is True

    def test_multiple_roles_one_denied(self):
        acc = _make_access(denied_roles=["banned"])
        assert acc.is_role_allowed(["user", "banned"]) is False


# ===========================================================================
# TestDbAccessDefValidation
# ===========================================================================

class TestDbAccessDefValidation:
    """Validation logic for DbAccessDef."""

    def test_valid_access_def(self):
        acc = _make_access()
        assert acc.validate_definition() == []

    def test_row_filter_enabled_without_expression(self):
        acc = _make_access(row_filter_enabled=True)
        errors = acc.validate_definition()
        assert any("row_filter_expression" in e for e in errors)

    def test_column_mask_enabled_without_columns(self):
        acc = _make_access(column_mask_enabled=True)
        errors = acc.validate_definition()
        assert any("masked_columns" in e for e in errors)

    def test_row_filter_with_expression_valid(self):
        acc = _make_access(
            row_filter_enabled=True,
            row_filter_expression="status = 'active'",
        )
        errors = acc.validate_definition()
        assert not any("row_filter" in e for e in errors)

    def test_column_mask_with_columns_valid(self):
        acc = _make_access(
            column_mask_enabled=True,
            masked_columns=["ssn"],
        )
        errors = acc.validate_definition()
        assert not any("masked_columns" in e for e in errors)


# ===========================================================================
# TestQueryConditionDef
# ===========================================================================

class TestQueryConditionDef:
    """Tests for QueryConditionDef.to_sql()."""

    def test_equal_condition(self):
        cond = QueryConditionDef(column="status", operator="=", value="active")
        sql = cond.to_sql()
        assert sql == "status = 'active'"

    def test_numeric_equal_condition(self):
        cond = QueryConditionDef(column="age", operator=">=", value=18)
        sql = cond.to_sql()
        assert sql == "age >= 18"

    def test_in_condition(self):
        cond = QueryConditionDef(column="region", operator="IN", value=["EAST", "WEST"])
        sql = cond.to_sql()
        assert "region IN" in sql
        assert "'EAST'" in sql
        assert "'WEST'" in sql

    def test_not_in_condition(self):
        cond = QueryConditionDef(column="status", operator="NOT IN", value=["deleted", "archived"])
        sql = cond.to_sql()
        assert "status NOT IN" in sql
        assert "'deleted'" in sql

    def test_like_condition(self):
        cond = QueryConditionDef(column="name", operator="LIKE", value="%Smith%")
        sql = cond.to_sql()
        assert sql == "name LIKE '%Smith%'"

    def test_null_condition(self):
        cond = QueryConditionDef(column="deleted_at", operator="IS NULL")
        sql = cond.to_sql()
        assert sql == "deleted_at IS NULL"

    def test_is_not_null_condition(self):
        cond = QueryConditionDef(column="email", operator="IS NOT NULL")
        sql = cond.to_sql()
        assert sql == "email IS NOT NULL"

    def test_nested_and_conditions(self):
        cond = QueryConditionDef(
            condition_type="nested",
            logic="and",
            conditions=[
                QueryConditionDef(column="a", operator="=", value=1),
                QueryConditionDef(column="b", operator="=", value=2),
            ],
        )
        sql = cond.to_sql()
        assert "a = 1" in sql
        assert "b = 2" in sql
        assert " AND " in sql

    def test_nested_or_conditions(self):
        cond = QueryConditionDef(
            condition_type="or",
            logic="or",
            conditions=[
                QueryConditionDef(column="x", operator="=", value="a"),
                QueryConditionDef(column="y", operator="=", value="b"),
            ],
        )
        sql = cond.to_sql()
        assert " OR " in sql

    def test_in_with_numeric_values(self):
        cond = QueryConditionDef(column="id", operator="IN", value=[1, 2, 3])
        sql = cond.to_sql()
        assert "id IN (1, 2, 3)" == sql
