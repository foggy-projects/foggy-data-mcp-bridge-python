"""Tests for foggy.dataset_model.proxy — TableModelProxy, ColumnRef, DimensionProxy, JoinBuilder."""

import pytest

from foggy.dataset_model.proxy import (
    ColumnRef,
    DimensionProxy,
    JoinBuilder,
    TableModelProxy,
)


# ---------------------------------------------------------------------------
# TestColumnRef
# ---------------------------------------------------------------------------

class TestColumnRef:
    def test_simple_column(self):
        ref = ColumnRef("M", "orderId")
        assert ref.model_name == "M"
        assert ref.field_ref == "orderId"
        assert ref.is_dimension_ref is False
        assert ref.is_nested is False
        assert ref.dimension_name is None
        assert ref.property_name is None

    def test_dimension_ref(self):
        ref = ColumnRef("M", "customer$id")
        assert ref.is_dimension_ref is True
        assert ref.dimension_name == "customer"
        assert ref.property_name == "id"
        assert ref.is_nested is False

    def test_nested_ref(self):
        ref = ColumnRef("M", "product.category$id")
        assert ref.is_dimension_ref is True
        assert ref.is_nested is True
        assert ref.dimension_name == "product.category"
        assert ref.property_name == "id"

    def test_no_alias(self):
        ref = ColumnRef("M", "orderId")
        assert ref.alias is None

    def test_with_alias(self):
        ref = ColumnRef("M", "col", alias="my_col")
        assert ref.alias == "my_col"

    def test_frozen(self):
        ref = ColumnRef("M", "orderId")
        with pytest.raises(AttributeError):
            ref.model_name = "X"  # type: ignore[misc]

    def test_equality(self):
        a = ColumnRef("M", "orderId")
        b = ColumnRef("M", "orderId")
        assert a == b

    def test_hash(self):
        a = ColumnRef("M", "orderId")
        b = ColumnRef("M", "orderId")
        assert hash(a) == hash(b)
        assert len({a, b}) == 1


# ---------------------------------------------------------------------------
# TestDimensionProxy
# ---------------------------------------------------------------------------

class TestDimensionProxy:
    def test_simple_property(self):
        proxy = TableModelProxy("M")
        result = proxy.customer
        assert isinstance(result, DimensionProxy)

    def test_dollar_access(self):
        proxy = TableModelProxy("M")
        dim = proxy.customer
        ref = getattr(dim, "customer$id")
        assert isinstance(ref, ColumnRef)
        assert ref.field_ref == "customer.customer$id"

    def test_chained_access(self):
        proxy = TableModelProxy("M")
        dim1 = proxy.product
        assert isinstance(dim1, DimensionProxy)
        dim2 = dim1.category
        assert isinstance(dim2, DimensionProxy)

    def test_chained_dollar(self):
        proxy = TableModelProxy("M")
        dim = proxy.product.category
        ref = getattr(dim, "sub$name")
        assert isinstance(ref, ColumnRef)
        assert ref.field_ref == "product.category.sub$name"
        assert ref.model_name == "M"

    def test_field_ref(self):
        proxy = TableModelProxy("M")
        dim = proxy.product.category
        assert dim._field_ref == "product.category"

    def test_repr(self):
        proxy = TableModelProxy("M")
        dim = proxy.product
        r = repr(dim)
        assert "M" in r
        assert "product" in r

    def test_internal_attr_raises(self):
        proxy = TableModelProxy("M")
        dim = proxy.product
        with pytest.raises(AttributeError):
            _ = dim._secret


# ---------------------------------------------------------------------------
# TestTableModelProxy
# ---------------------------------------------------------------------------

class TestTableModelProxy:
    def test_create(self):
        proxy = TableModelProxy("FactSales")
        assert proxy.model_name == "FactSales"

    def test_with_alias(self):
        proxy = TableModelProxy("M", alias="fo")
        assert proxy.effective_alias == "fo"

    def test_effective_alias_default(self):
        proxy = TableModelProxy("M")
        assert proxy.effective_alias == "M"

    def test_dimension_property_access(self):
        proxy = TableModelProxy("M")
        ref = getattr(proxy, "customer$id")
        assert isinstance(ref, ColumnRef)
        assert ref.model_name == "M"
        assert ref.field_ref == "customer$id"

    def test_dimension_proxy_access(self):
        proxy = TableModelProxy("M")
        result = proxy.product
        assert isinstance(result, DimensionProxy)

    def test_fact_field_can_be_used_in_join_on(self):
        proxy = TableModelProxy("M")
        ref = proxy.orderId
        assert isinstance(ref, DimensionProxy)
        assert ref.field_ref == "orderId"
        assert ref.model_name == "M"

    def test_left_join(self):
        p1 = TableModelProxy("A")
        p2 = TableModelProxy("B")
        builder = p1.left_join(p2)
        assert isinstance(builder, JoinBuilder)
        assert builder.join_type == "LEFT"
        assert builder.left is p1
        assert builder.right is p2

    def test_inner_join(self):
        p1 = TableModelProxy("A")
        p2 = TableModelProxy("B")
        builder = p1.inner_join(p2)
        assert builder.join_type == "INNER"

    def test_right_join(self):
        p1 = TableModelProxy("A")
        p2 = TableModelProxy("B")
        builder = p1.right_join(p2)
        assert builder.join_type == "RIGHT"

    def test_camel_case_join_methods(self):
        p1 = TableModelProxy("A")
        p2 = TableModelProxy("B")
        assert p1.leftJoin(p2).join_type == "LEFT"
        assert p1.innerJoin(p2).join_type == "INNER"
        assert p1.rightJoin(p2).join_type == "RIGHT"

    def test_join_on(self):
        p1 = TableModelProxy("A")
        p2 = TableModelProxy("B")
        builder = p1.left_join(p2).on("orderId", "orderId")
        assert builder.on_left_key == "orderId"
        assert builder.on_right_key == "orderId"

    def test_join_on_with_column_ref(self):
        p1 = TableModelProxy("A")
        p2 = TableModelProxy("B")
        ref1 = ColumnRef("A", "orderId")
        ref2 = ColumnRef("B", "orderId")
        builder = p1.left_join(p2).on(ref1, ref2)
        assert builder.on_left_key == "orderId"
        assert builder.on_right_key == "orderId"

    def test_repr(self):
        proxy = TableModelProxy("FactSales")
        assert "FactSales" in repr(proxy)

    def test_repr_with_alias(self):
        proxy = TableModelProxy("FactSales", alias="fs")
        r = repr(proxy)
        assert "FactSales" in r
        assert "fs" in r

    def test_internal_attr_raises(self):
        proxy = TableModelProxy("M")
        with pytest.raises(AttributeError):
            _ = proxy._hidden


# ---------------------------------------------------------------------------
# TestJoinBuilder
# ---------------------------------------------------------------------------

class TestJoinBuilder:
    def test_create(self):
        p1 = TableModelProxy("A")
        p2 = TableModelProxy("B")
        builder = JoinBuilder(p1, p2)
        assert builder.left is p1
        assert builder.right is p2

    def test_on_strings(self):
        p1 = TableModelProxy("A")
        p2 = TableModelProxy("B")
        builder = JoinBuilder(p1, p2)
        result = builder.on("a", "b")
        assert result.on_left_key == "a"
        assert result.on_right_key == "b"

    def test_on_column_refs(self):
        p1 = TableModelProxy("A")
        p2 = TableModelProxy("B")
        builder = JoinBuilder(p1, p2)
        result = builder.on(ColumnRef("A", "x"), ColumnRef("B", "y"))
        assert result.on_left_key == "x"
        assert result.on_right_key == "y"

    def test_join_type_default(self):
        p1 = TableModelProxy("A")
        p2 = TableModelProxy("B")
        builder = JoinBuilder(p1, p2)
        assert builder.join_type == "LEFT"

    def test_on_returns_self(self):
        p1 = TableModelProxy("A")
        p2 = TableModelProxy("B")
        builder = JoinBuilder(p1, p2)
        result = builder.on("a", "b")
        assert result is builder

    def test_and_adds_second_condition(self):
        p1 = TableModelProxy("A")
        p2 = TableModelProxy("B")
        builder = p1.left_join(p2).on(p1.orderId, p2.orderId).and_(p1.orderLineNo, p2.orderLineNo)
        assert len(builder.conditions) == 2
        assert builder.conditions[0].left_field_ref == "orderId"
        assert builder.conditions[0].right_field_ref == "orderId"
        assert builder.conditions[1].left_field_ref == "orderLineNo"
        assert builder.conditions[1].right_field_ref == "orderLineNo"

    def test_keyword_and_member_works(self):
        p1 = TableModelProxy("A")
        p2 = TableModelProxy("B")
        builder = getattr(p1.leftJoin(p2).on(p1.orderId, p2.orderId), "and")(p1.orderLineNo, p2.orderLineNo)
        assert len(builder.conditions) == 2
