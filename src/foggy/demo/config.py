"""Demo configuration."""

from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class DemoDataSource(str, Enum):
    """Available demo data sources."""

    SQLITE_MEMORY = "sqlite_memory"
    SQLITE_FILE = "sqlite_file"
    H2_MEMORY = "h2_memory"


class DemoConfig(BaseModel):
    """Configuration for the demo application."""

    # Data source settings
    data_source: DemoDataSource = Field(
        default=DemoDataSource.SQLITE_MEMORY,
        description="Demo data source type"
    )
    database_path: Optional[str] = Field(
        default=None,
        description="Path for SQLite file database"
    )

    # Sample data settings
    sample_data_size: int = Field(
        default=1000,
        description="Number of sample records to generate"
    )
    seed: Optional[int] = Field(
        default=42,
        description="Random seed for reproducible data"
    )

    # Server settings
    server_port: int = Field(default=8080, description="Server port")
    server_host: str = Field(default="0.0.0.0", description="Server host")

    # Model settings
    load_sample_models: bool = Field(
        default=True,
        description="Load sample TM/QM models"
    )
    model_directory: str = Field(
        default="./models",
        description="Directory for model files"
    )

    # Feature toggles
    enable_swagger_ui: bool = Field(default=True, description="Enable Swagger UI")
    enable_query_logging: bool = Field(default=True, description="Enable query logging")

    model_config = {"extra": "allow"}