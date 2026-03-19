"""UUID utilities for Foggy Framework."""

import uuid
from typing import Optional


class UuidUtils:
    """UUID utility functions."""

    @staticmethod
    def random_uuid() -> str:
        """Generate random UUID string (UUID4)."""
        return str(uuid.uuid4())

    @staticmethod
    def random_uuid_no_dash() -> str:
        """Generate random UUID string without dashes."""
        return uuid.uuid4().hex

    @staticmethod
    def random_uuid_bytes() -> bytes:
        """Generate random UUID as bytes."""
        return uuid.uuid4().bytes

    @staticmethod
    def uuid_from_string(s: str) -> uuid.UUID:
        """Parse UUID from string.

        Args:
            s: UUID string (with or without dashes)

        Returns:
            UUID object
        """
        # Handle UUID without dashes
        if len(s) == 32 and "-" not in s:
            s = f"{s[:8]}-{s[8:12]}-{s[12:16]}-{s[16:20]}-{s[20:]}"
        return uuid.UUID(s)

    @staticmethod
    def is_valid_uuid(s: str) -> bool:
        """Check if string is valid UUID.

        Args:
            s: String to check

        Returns:
            True if valid UUID
        """
        try:
            UuidUtils.uuid_from_string(s)
            return True
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def uuid_to_string(u: uuid.UUID, with_dashes: bool = True) -> str:
        """Convert UUID to string.

        Args:
            u: UUID object
            with_dashes: Whether to include dashes

        Returns:
            UUID string
        """
        if with_dashes:
            return str(u)
        return u.hex

    @staticmethod
    def uuid_from_bytes(b: bytes) -> uuid.UUID:
        """Create UUID from bytes.

        Args:
            b: 16 bytes

        Returns:
            UUID object
        """
        return uuid.UUID(bytes=b)

    @staticmethod
    def short_uuid() -> str:
        """Generate short UUID (first 8 characters of UUID4)."""
        return uuid.uuid4().hex[:8]

    @staticmethod
    def timed_uuid() -> str:
        """Generate time-ordered UUID (UUID1).

        Note: UUID1 includes host info and is not suitable for security purposes.
        """
        return str(uuid.uuid1())

    @staticmethod
    def is_uuid_prefix(s: str, prefix: str) -> bool:
        """Check if UUID starts with prefix.

        Args:
            s: UUID string
            prefix: Prefix to check

        Returns:
            True if UUID starts with prefix
        """
        return s.replace("-", "").startswith(prefix.replace("-", ""))

    @staticmethod
    def format_with_prefix(prefix: str, separator: str = "_") -> str:
        """Generate UUID with prefix.

        Args:
            prefix: Prefix string
            separator: Separator between prefix and UUID

        Returns:
            Prefixed UUID string (e.g., "fmcp_a1b2c3d4...")
        """
        return f"{prefix}{separator}{UuidUtils.random_uuid()}"