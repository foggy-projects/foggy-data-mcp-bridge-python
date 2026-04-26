import pytest
from foggy.dataset_model.engine.compose.plan.plan import BaseModelPlan
from foggy.dataset_model.engine.compose.plan.query_factory import INSTANCE as Query

def test_query_plan_property_access():
    plan = Query._from_impl("SaleOrderQM")
    col_ref = plan.partnerId
    assert col_ref.name == "partnerId"
    assert col_ref.to_column_expr() == "partnerId"
    
    proj = col_ref.as_("pid", "Partner ID")
    assert proj.to_column_expr() == "partnerId$Partner ID AS pid"

def test_query_plan_aggregation():
    plan = Query._from_impl("SaleOrderQM")
    agg = plan.amountTotal.sum()
    assert agg.to_column_expr() == "SUM(amountTotal)"
    
    proj = agg.as_("total", "Total Amount")
    assert proj.to_column_expr() == "SUM(amountTotal)$Total Amount AS total"

def test_chainable_where_group_by_select():
    plan = Query._from_impl("SaleOrderQM")
    
    derived = plan.where([{"field": "status", "op": "=", "value": "done"}]) \
                  .groupBy(plan.partnerId) \
                  .select(
                      plan.partnerId,
                      plan.amountTotal.sum().as_("totalSales", "Total Sales")
                  )
                  
    assert derived.source.source.source == plan
    assert derived.source.source.slice_ == ({"field": "status", "op": "=", "value": "done"},)
    assert derived.source.group_by == ("partnerId",)
    assert derived.columns == ("partnerId", "SUM(amountTotal)$Total Sales AS totalSales")

def test_join_builder():
    customers = Query._from_impl("ResPartnerQM")
    orders = Query._from_impl("SaleOrderQM")
    
    joined = customers.leftJoin(orders) \
        .on(customers.id, orders.partnerId) \
        .and_(customers.companyId, orders.companyId)
        
    assert joined.type == "left"
    assert joined.left == customers
    assert joined.right == orders
    assert len(joined.on) == 2
    assert joined.on[0].left == "id"
    assert joined.on[0].right == "partnerId"
    assert joined.on[1].left == "companyId"
    assert joined.on[1].right == "companyId"
    
def test_select_ambiguous_column_fails():
    customers = Query._from_impl("ResPartnerQM")
    orders = Query._from_impl("SaleOrderQM")
    
    joined = customers.leftJoin(orders).on(customers.id, orders.partnerId)
    
    with pytest.raises(ValueError, match="ambiguous"):
        joined.select(customers.name, orders.name)
        
def test_select_resolved_columns():
    customers = Query._from_impl("ResPartnerQM")
    orders = Query._from_impl("SaleOrderQM")
    
    joined = customers.leftJoin(orders).on(customers.id, orders.partnerId)
    
    derived = joined.select(
        customers.id,
        customers.name.as_("customerName"),
        orders.name.as_("orderNo")
    )
    
    assert derived.columns == ("id", "name AS customerName", "name AS orderNo")
