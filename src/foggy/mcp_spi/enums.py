"""Enums for MCP SPI — aligned with Java constants."""

from enum import Enum


class AccessMode(str, Enum):
    """Access mode for dataset accessor."""

    LOCAL = "local"
    REMOTE = "remote"


class QueryMode(str, Enum):
    """Query execution mode — aligned with Java QueryMode."""

    EXECUTE = "execute"
    VALIDATE = "validate"


class MetadataFormat(str, Enum):
    """Metadata output format — aligned with Java MetadataFormat."""

    JSON = "json"
    MARKDOWN = "markdown"
