"""Chart storage adapter implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel
import os
import uuid
from datetime import datetime

from foggy.mcp.storage.properties import ChartStorageProperties, StorageType


class ChartStorageException(Exception):
    """Exception for chart storage operations."""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        """Initialize with message and optional cause."""
        super().__init__(message)
        self.cause = cause


class ChartMetadata(BaseModel):
    """Metadata for a stored chart."""

    chart_id: str
    file_name: str
    file_path: str
    file_size: int
    format: str
    content_type: str
    created_at: datetime
    url: Optional[str] = None
    expires_at: Optional[datetime] = None


class ChartStorageAdapter(ABC):
    """Abstract adapter for chart storage."""

    @abstractmethod
    async def store(
        self,
        chart_data: bytes,
        format: str = "png",
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChartMetadata:
        """Store chart data and return metadata."""
        pass

    @abstractmethod
    async def retrieve(self, chart_id: str) -> bytes:
        """Retrieve chart data by ID."""
        pass

    @abstractmethod
    async def delete(self, chart_id: str) -> bool:
        """Delete a chart by ID."""
        pass

    @abstractmethod
    async def get_url(self, chart_id: str, expiration: Optional[int] = None) -> str:
        """Get a URL for accessing the chart."""
        pass

    @abstractmethod
    async def exists(self, chart_id: str) -> bool:
        """Check if a chart exists."""
        pass


class LocalChartStorageAdapter(ChartStorageAdapter):
    """Local filesystem storage adapter."""

    def __init__(self, properties: Optional[ChartStorageProperties] = None):
        """Initialize with storage properties.

        Args:
            properties: Storage properties. If None, uses default settings.
        """
        self._properties = properties or ChartStorageProperties()
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Ensure storage directory exists."""
        os.makedirs(self._properties.local_path, exist_ok=True)

    def _get_file_path(self, chart_id: str, format: str) -> str:
        """Get full file path for a chart."""
        return os.path.join(self._properties.local_path, f"{chart_id}.{format}")

    async def store(
        self,
        chart_data: bytes,
        format: str = "png",
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChartMetadata:
        """Store chart data to local filesystem."""
        # Generate unique ID
        chart_id = uuid.uuid4().hex
        file_name = f"{chart_id}.{format}"
        file_path = self._get_file_path(chart_id, format)

        # Check size limit
        max_size = self._properties.max_file_size_mb * 1024 * 1024
        if len(chart_data) > max_size:
            raise ChartStorageException(
                f"Chart size ({len(chart_data)} bytes) exceeds limit ({max_size} bytes)"
            )

        # Write file
        try:
            with open(file_path, "wb") as f:
                f.write(chart_data)
        except Exception as e:
            raise ChartStorageException(f"Failed to write chart file: {e}", e)

        # Build URL
        url = f"{self._properties.url_prefix}/{file_name}"
        if self._properties.base_url:
            url = f"{self._properties.base_url.rstrip('/')}{url}"

        # Determine content type
        content_types = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "svg": "image/svg+xml",
            "webp": "image/webp",
        }

        return ChartMetadata(
            chart_id=chart_id,
            file_name=file_name,
            file_path=file_path,
            file_size=len(chart_data),
            format=format,
            content_type=content_types.get(format.lower(), "application/octet-stream"),
            created_at=datetime.now(),
            url=url,
        )

    async def retrieve(self, chart_id: str) -> bytes:
        """Retrieve chart data from local filesystem."""
        # Try common formats
        for fmt in ["png", "jpg", "svg", "webp"]:
            file_path = self._get_file_path(chart_id, fmt)
            if os.path.exists(file_path):
                try:
                    with open(file_path, "rb") as f:
                        return f.read()
                except Exception as e:
                    raise ChartStorageException(f"Failed to read chart file: {e}", e)

        raise ChartStorageException(f"Chart not found: {chart_id}")

    async def delete(self, chart_id: str) -> bool:
        """Delete a chart from local filesystem."""
        for fmt in ["png", "jpg", "svg", "webp"]:
            file_path = self._get_file_path(chart_id, fmt)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    return True
                except Exception:
                    return False
        return False

    async def get_url(self, chart_id: str, expiration: Optional[int] = None) -> str:
        """Get URL for accessing the chart (local adapter returns static URL)."""
        # Find the actual format
        for fmt in ["png", "jpg", "svg", "webp"]:
            if os.path.exists(self._get_file_path(chart_id, fmt)):
                url = f"{self._properties.url_prefix}/{chart_id}.{fmt}"
                if self._properties.base_url:
                    url = f"{self._properties.base_url.rstrip('/')}{url}"
                return url
        raise ChartStorageException(f"Chart not found: {chart_id}")

    async def exists(self, chart_id: str) -> bool:
        """Check if chart exists."""
        for fmt in ["png", "jpg", "svg", "webp"]:
            if os.path.exists(self._get_file_path(chart_id, fmt)):
                return True
        return False

    async def cleanup_old_files(self) -> int:
        """Remove files older than retention period."""
        from datetime import timedelta

        retention = timedelta(days=self._properties.retention_days)
        cutoff = datetime.now() - retention
        removed = 0

        for file_name in os.listdir(self._properties.local_path):
            file_path = os.path.join(self._properties.local_path, file_name)

            if os.path.isfile(file_path):
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if mtime < cutoff:
                    try:
                        os.remove(file_path)
                        removed += 1
                    except Exception:
                        pass

        return removed


def create_storage_adapter(properties: ChartStorageProperties) -> ChartStorageAdapter:
    """Factory function to create a storage adapter."""
    if properties.storage_type == StorageType.LOCAL:
        return LocalChartStorageAdapter(properties)

    # Placeholder for other storage types
    # In a full implementation, we'd have S3Adapter, MinioAdapter, etc.
    raise ValueError(f"Unsupported storage type: {properties.storage_type}")