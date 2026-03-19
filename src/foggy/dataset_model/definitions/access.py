"""Access control definition for semantic layer."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from foggy.dataset_model.definitions.base import AiDef


class AccessType(str, Enum):
    """Access type enumeration."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


class RowFilterType(str, Enum):
    """Row filter type for access control."""

    NONE = "none"
    SQL = "sql"
    EXPRESSION = "expression"
    ROLE_BASED = "role_based"


class DbAccessDef(AiDef):
    """Access control definition for data security.

    Defines row-level security and column-level security rules
    for semantic models.
    """

    # Access control
    enabled: bool = Field(default=True, description="Whether access control is enabled")
    access_type: AccessType = Field(default=AccessType.READ, description="Type of access")

    # Row-level security
    row_filter_enabled: bool = Field(default=False, description="Enable row-level filtering")
    row_filter_type: RowFilterType = Field(
        default=RowFilterType.NONE, description="Type of row filter"
    )
    row_filter_expression: Optional[str] = Field(
        default=None, description="Row filter expression (SQL or DSL)"
    )

    # Column-level security
    column_mask_enabled: bool = Field(default=False, description="Enable column masking")
    masked_columns: List[str] = Field(default_factory=list, description="Columns to mask")
    mask_pattern: Optional[str] = Field(default=None, description="Mask pattern (e.g., '***')")

    # Role-based access
    allowed_roles: List[str] = Field(default_factory=list, description="Roles allowed access")
    denied_roles: List[str] = Field(default_factory=list, description="Roles denied access")

    # Audit
    audit_enabled: bool = Field(default=False, description="Enable access audit logging")

    def get_row_filter_sql(self, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get the SQL row filter expression.

        Args:
            context: Optional context for expression evaluation

        Returns:
            SQL expression for row filtering or None
        """
        if not self.row_filter_enabled or not self.row_filter_expression:
            return None
        # TODO: Support expression evaluation with context
        return self.row_filter_expression

    def is_role_allowed(self, roles: List[str]) -> bool:
        """Check if any of the given roles are allowed access.

        Args:
            roles: List of roles to check

        Returns:
            True if access is allowed, False otherwise
        """
        if not self.enabled:
            return True

        # Check denied roles first
        if any(role in self.denied_roles for role in roles):
            return False

        # If no allowed roles specified, allow all (except denied)
        if not self.allowed_roles:
            return True

        # Check allowed roles
        return any(role in self.allowed_roles for role in roles)

    def validate_definition(self) -> List[str]:
        """Validate the access definition."""
        errors = super().validate_definition()

        if self.row_filter_enabled and not self.row_filter_expression:
            errors.append("row_filter_expression is required when row_filter_enabled is True")

        if self.column_mask_enabled and not self.masked_columns:
            errors.append("masked_columns is required when column_mask_enabled is True")

        return errors