"""Sample TM/QM models for demo."""

from typing import Dict, List, Optional
from datetime import datetime

from foggy.dataset_model.definitions.base import (
    AiDef,
    ColumnType,
    AggregationType,
    DimensionType,
    DbColumnDef,
)
from foggy.dataset_model.definitions.measure import DbMeasureDef
from foggy.dataset_model.definitions.query_model import DbQueryModelDef, QueryModelType
from foggy.dataset_model.impl.model import (
    DbTableModelImpl,
    DbModelDimensionImpl,
    DbModelMeasureImpl,
)


def create_sample_table_model() -> DbTableModelImpl:
    """Create a sample table model for sales data.

    This demonstrates a typical TM (Table Model) for e-commerce sales analytics.

    Example:
        >>> model = create_sample_table_model()
        >>> print(model.name)  # 'sales_tm'
        >>> print(list(model.dimensions.keys()))  # ['date', 'product', 'region', 'customer']
    """
    model = DbTableModelImpl(
        name="sales_tm",
        source_table="sales",
        # Note: source_schema is None for SQLite compatibility
        source_schema=None,
        dimensions={
            "date": DbModelDimensionImpl(
                name="date",
                column="sale_date",
                alias="Sale Date",
                dimension_type=DimensionType.TIME,
                description="Date of the sale",
                ai_description="The date when the transaction occurred. Can be used for time-based analysis like daily, weekly, monthly trends.",
                ai_examples=[
                    "Show sales by date",
                    "What were the sales last month?",
                    "Compare sales this week vs last week",
                ]
            ),
            "product": DbModelDimensionImpl(
                name="product",
                column="product_id",
                alias="Product",
                dimension_type=DimensionType.REGULAR,
                description="Product identifier",
                ai_description="The product that was sold. Use this to analyze sales by product.",
            ),
            "product_name": DbModelDimensionImpl(
                name="product_name",
                column="product_name",
                alias="Product Name",
                dimension_type=DimensionType.REGULAR,
                description="Name of the product",
            ),
            "category": DbModelDimensionImpl(
                name="category",
                column="category_name",
                alias="Category",
                dimension_type=DimensionType.REGULAR,
                description="Product category",
                ai_description="The category of the product. Examples: Electronics, Clothing, Food.",
            ),
            "region": DbModelDimensionImpl(
                name="region",
                column="region_code",
                alias="Region",
                dimension_type=DimensionType.REGULAR,
                description="Sales region",
            ),
            "region_name": DbModelDimensionImpl(
                name="region_name",
                column="region_name",
                alias="Region Name",
                dimension_type=DimensionType.REGULAR,
                description="Name of the sales region",
                ai_description="The geographic region where the sale occurred. Examples: North, South, East, West.",
            ),
            "customer": DbModelDimensionImpl(
                name="customer",
                column="customer_id",
                alias="Customer",
                dimension_type=DimensionType.REGULAR,
                description="Customer identifier",
            ),
            "customer_segment": DbModelDimensionImpl(
                name="customer_segment",
                column="customer_segment",
                alias="Customer Segment",
                dimension_type=DimensionType.REGULAR,
                description="Customer segment (e.g., VIP, Regular, New)",
                ai_description="The customer segment classification. Values: VIP, Regular, New, Enterprise.",
            ),
        },
        measures={
            "sales_amount": DbModelMeasureImpl(
                name="sales_amount",
                column="amount",
                alias="Sales Amount",
                aggregation=AggregationType.SUM,
                description="Total sales amount",
                ai_description="The sum of all sales values. Use for revenue analysis.",
            ),
            "quantity": DbModelMeasureImpl(
                name="quantity",
                column="quantity",
                alias="Quantity",
                aggregation=AggregationType.SUM,
                description="Total quantity sold",
            ),
            "order_count": DbModelMeasureImpl(
                name="order_count",
                column="order_id",
                alias="Order Count",
                aggregation=AggregationType.COUNT_DISTINCT,
                description="Number of unique orders",
            ),
            "avg_order_value": DbModelMeasureImpl(
                name="avg_order_value",
                column="amount",
                alias="Average Order Value",
                aggregation=AggregationType.AVG,
                description="Average value per order",
            ),
            "profit": DbModelMeasureImpl(
                name="profit",
                column="profit",
                alias="Profit",
                aggregation=AggregationType.SUM,
                description="Total profit",
            ),
        }
    )

    return model


def create_sample_query_model() -> DbQueryModelDef:
    """Create a sample query model for sales analytics.

    This demonstrates a QM (Query Model) that provides a simplified view
    for business users to query sales data.

    Example:
        >>> qm = create_sample_query_model()
        >>> print(qm.name)  # 'sales_qm'
        >>> print(qm.source_table)  # 'sales'
    """
    qm = DbQueryModelDef(
        name="sales_qm",
        alias="Sales Analysis",
        description="Query model for sales analysis and reporting",
        model_type=QueryModelType.TABLE,
        source_table="sales",
        # Note: source_schema is None for SQLite compatibility
        source_schema=None,
        ai_description="A query model for analyzing sales data. Supports filtering by date, product, region, and customer segment. Provides metrics like sales amount, quantity, order count, and profit.",
        ai_examples=[
            "Show total sales by region for this month",
            "What are the top 10 products by revenue?",
            "Compare profit by customer segment",
            "Show daily sales trend for the last week",
            "Which category has the highest average order value?",
        ],
    )

    return qm


def create_inventory_table_model() -> DbTableModelImpl:
    """Create a sample table model for inventory data."""
    model = DbTableModelImpl(
        name="inventory_tm",
        source_table="inventory",
        # Note: source_schema is None for SQLite compatibility
        source_schema=None,
        dimensions={
            "product": DbModelDimensionImpl(
                name="product",
                column="product_id",
                alias="Product",
                dimension_type=DimensionType.REGULAR,
            ),
            "warehouse": DbModelDimensionImpl(
                name="warehouse",
                column="warehouse_id",
                alias="Warehouse",
                dimension_type=DimensionType.REGULAR,
            ),
            "date": DbModelDimensionImpl(
                name="date",
                column="inventory_date",
                alias="Date",
                dimension_type=DimensionType.TIME,
            ),
        },
        measures={
            "stock_level": DbModelMeasureImpl(
                name="stock_level",
                column="quantity",
                alias="Stock Level",
                aggregation=AggregationType.SUM,
            ),
            "reorder_count": DbModelMeasureImpl(
                name="reorder_count",
                column="reorder_flag",
                alias="Items to Reorder",
                aggregation=AggregationType.SUM,
            ),
        }
    )

    return model


def create_all_sample_models() -> Dict[str, DbTableModelImpl]:
    """Create all sample models and return as a dictionary."""
    return {
        "sales_tm": create_sample_table_model(),
        "inventory_tm": create_inventory_table_model(),
    }


def create_sample_query_models() -> Dict[str, DbQueryModelDef]:
    """Create all sample query models."""
    return {
        "sales_qm": create_sample_query_model(),
    }


# Sample data generation utilities

def generate_sample_sales_data(num_records: int = 1000, seed: Optional[int] = None) -> List[Dict]:
    """Generate sample sales data for testing.

    Args:
        num_records: Number of records to generate
        seed: Random seed for reproducibility

    Returns:
        List of sample sales records
    """
    import random
    from datetime import timedelta

    if seed is not None:
        random.seed(seed)

    categories = ["Electronics", "Clothing", "Food", "Books", "Home"]
    regions = ["North", "South", "East", "West"]
    segments = ["VIP", "Regular", "New", "Enterprise"]

    base_date = datetime(2024, 1, 1)
    records = []

    for i in range(num_records):
        category = random.choice(categories)
        region = random.choice(regions)
        segment = random.choice(segments)

        quantity = random.randint(1, 10)
        unit_price = random.uniform(10, 500)
        amount = quantity * unit_price
        profit = amount * random.uniform(0.1, 0.4)

        record = {
            "order_id": f"ORD-{10000 + i}",
            "sale_date": (base_date + timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d"),
            "product_id": f"PRD-{random.randint(1, 100):03d}",
            "product_name": f"Product {random.randint(1, 100)}",
            "category_name": category,
            "region_code": region[:2].upper(),
            "region_name": region,
            "customer_id": f"CUST-{random.randint(1, 500):04d}",
            "customer_segment": segment,
            "quantity": quantity,
            "amount": round(amount, 2),
            "profit": round(profit, 2),
        }
        records.append(record)

    return records


# Run demo if executed directly
if __name__ == "__main__":
    # Create and print sample models
    print("=== Sample Table Model ===")
    tm = create_sample_table_model()
    print(f"Name: {tm.name}")
    print(f"Dimensions: {list(tm.dimensions.keys())}")
    print(f"Measures: {list(tm.measures.keys())}")

    print("\n=== Sample Query Model ===")
    qm = create_sample_query_model()
    print(f"Name: {qm.name}")
    print(f"Description: {qm.description}")

    print("\n=== Sample Data (5 records) ===")
    data = generate_sample_sales_data(5, seed=42)
    for record in data:
        print(record)