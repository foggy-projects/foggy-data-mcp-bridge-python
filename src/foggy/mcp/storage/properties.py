"""Storage properties and configuration."""

from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class StorageType(str, Enum):
    """Storage type enumeration."""

    LOCAL = "local"
    S3 = "s3"
    MINIO = "minio"
    OSS = "oss"  # Alibaba Cloud OSS
    COS = "cos"  # Tencent Cloud COS


class ChartStorageProperties(BaseModel):
    """Configuration for chart storage."""

    # Storage type
    storage_type: StorageType = Field(default=StorageType.LOCAL, description="Storage backend type")

    # Local storage settings
    local_path: str = Field(default="./charts", description="Local storage directory")
    url_prefix: str = Field(default="/charts", description="URL prefix for accessing charts")

    # S3/Minio settings
    endpoint: Optional[str] = Field(default=None, description="S3/Minio endpoint")
    region: Optional[str] = Field(default=None, description="S3 region")
    bucket: Optional[str] = Field(default=None, description="Bucket name")
    access_key: Optional[str] = Field(default=None, description="Access key")
    secret_key: Optional[str] = Field(default=None, description="Secret key")

    # File settings
    default_format: str = Field(default="png", description="Default image format")
    max_file_size_mb: int = Field(default=10, description="Maximum file size in MB")
    retention_days: int = Field(default=30, description="Retention period in days")

    # URL settings
    base_url: Optional[str] = Field(default=None, description="Base URL for generated links")
    signed_url_expiration: int = Field(default=3600, description="Signed URL expiration in seconds")

    model_config = {"extra": "allow"}