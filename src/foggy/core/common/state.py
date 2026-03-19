"""State enumeration for Foggy Framework."""

from enum import Enum


class State(Enum):
    """State enumeration for common state values."""

    # Common states
    ENABLED = 1
    DISABLED = 0

    # Status states
    ACTIVE = 1
    INACTIVE = 0

    # Boolean states
    YES = 1
    NO = 0

    # Common status
    SUCCESS = 1
    FAIL = 0

    # Delete flag
    DELETED = 1
    NOT_DELETED = 0