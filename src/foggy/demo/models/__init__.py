"""Demo models package."""

from foggy.demo.models.sample_models import (
    create_sample_table_model,
    create_sample_query_model,
    create_inventory_table_model,
    create_all_sample_models,
    create_sample_query_models,
    generate_sample_sales_data,
)

__all__ = [
    "create_sample_table_model",
    "create_sample_query_model",
    "create_inventory_table_model",
    "create_all_sample_models",
    "create_sample_query_models",
    "generate_sample_sales_data",
]