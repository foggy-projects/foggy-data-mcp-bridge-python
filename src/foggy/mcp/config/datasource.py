"""DataSource configuration for MCP server."""

from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class DataSourceType(str, Enum):
    """Supported data source types."""

    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    SQLSERVER = "sqlserver"
    MONGODB = "mongodb"


class DataSourceConfig(BaseModel):
    """Data source configuration."""

    name: str = Field(..., description="Data source name/identifier")
    source_type: DataSourceType = Field(..., description="Data source type")
    enabled: bool = Field(default=True, description="Whether data source is enabled")

    # Connection settings
    host: Optional[str] = Field(default=None, description="Database host")
    port: Optional[int] = Field(default=None, description="Database port")
    database: Optional[str] = Field(default=None, description="Database name")
    schema_name: Optional[str] = Field(default=None, description="Schema name")
    username: Optional[str] = Field(default=None, description="Username")
    password: Optional[str] = Field(default=None, description="Password")

    # Connection pool settings
    pool_size: int = Field(default=10, description="Connection pool size")
    pool_timeout: int = Field(default=30, description="Pool timeout in seconds")
    idle_timeout: int = Field(default=300, description="Idle connection timeout")

    # Connection URL (alternative to individual settings)
    connection_url: Optional[str] = Field(default=None, description="Full connection URL")

    # Additional properties
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional connection properties")

    model_config = {"extra": "allow"}

    def get_connection_url(self) -> str:
        """Build connection URL from settings or return provided URL."""
        if self.connection_url:
            return self.connection_url

        if self.source_type == DataSourceType.MYSQL:
            return f"mysql+aiomysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.source_type == DataSourceType.POSTGRESQL:
            return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.source_type == DataSourceType.SQLITE:
            return f"sqlite+aiosqlite:///{self.database}"
        elif self.source_type == DataSourceType.SQLSERVER:
            return f"mssql+aiodbc://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.source_type == DataSourceType.MONGODB:
            return f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

        raise ValueError(f"Unsupported data source type: {self.source_type}")


class DataSourceManager(BaseModel):
    """Manager for multiple data sources."""

    data_sources: Dict[str, DataSourceConfig] = Field(default_factory=dict, description="Registered data sources")
    default_source: Optional[str] = Field(default=None, description="Default data source name")

    def register(self, config: DataSourceConfig, set_default: bool = False) -> None:
        """Register a data source."""
        self.data_sources[config.name] = config
        if set_default or self.default_source is None:
            self.default_source = config.name

    def get(self, name: Optional[str] = None) -> Optional[DataSourceConfig]:
        """Get a data source by name or default."""
        if name:
            return self.data_sources.get(name)
        if self.default_source:
            return self.data_sources.get(self.default_source)
        return None

    def list_names(self) -> List[str]:
        """List all registered data source names."""
        return list(self.data_sources.keys())

    def remove(self, name: str) -> bool:
        """Remove a data source."""
        if name in self.data_sources:
            del self.data_sources[name]
            if self.default_source == name:
                self.default_source = next(iter(self.data_sources), None) if self.data_sources else None
            return True
        return False