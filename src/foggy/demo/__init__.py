"""Demo module with sample models and configuration."""

from foggy.demo.models.sample_models import create_sample_table_model, create_sample_query_model
from foggy.demo.config import DemoConfig

__all__ = [
    "create_sample_table_model",
    "create_sample_query_model",
    "DemoConfig",
]