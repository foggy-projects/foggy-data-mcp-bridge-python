"""Dictionary definition for lookup values."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from foggy.dataset_model.definitions.base import AiDef


class DbDictItemDef(BaseModel):
    """Dictionary item definition for individual lookup entries."""

    # Identity
    code: str = Field(..., description="Item code/value")
    name: str = Field(..., description="Item display name")
    alias: Optional[str] = Field(default=None, description="Item alias")

    # Hierarchy support
    parent_code: Optional[str] = Field(default=None, description="Parent item code for hierarchy")
    level: int = Field(default=1, description="Hierarchy level (1 = root)")

    # Ordering
    sort_order: int = Field(default=0, description="Sort order within parent")

    # Status
    enabled: bool = Field(default=True, description="Whether item is enabled")
    is_default: bool = Field(default=False, description="Whether this is the default item")

    # Extended attributes
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Extended attributes")

    model_config = {
        "extra": "allow",
    }


class DbDictDef(AiDef):
    """Dictionary definition for lookup/dimension values.

    Dictionaries provide predefined value sets for dimensions,
    commonly used for dropdown selections and data validation.
    """

    # Dictionary type
    dict_type: str = Field(default="static", description="Dictionary type: static, dynamic, sql")

    # Static items
    items: List[DbDictItemDef] = Field(default_factory=list, description="Dictionary items")

    # Dynamic dictionary (SQL-based)
    datasource: Optional[str] = Field(default=None, description="Data source name for dynamic dict")
    query_sql: Optional[str] = Field(default=None, description="SQL query for dynamic dict")
    code_column: Optional[str] = Field(default=None, description="Code column name")
    name_column: Optional[str] = Field(default=None, description="Name column name")
    parent_column: Optional[str] = Field(default=None, description="Parent column for hierarchy")

    # Cache settings
    cache_enabled: bool = Field(default=True, description="Enable caching")
    cache_ttl_seconds: int = Field(default=3600, description="Cache TTL in seconds")

    def get_item_by_code(self, code: str) -> Optional[DbDictItemDef]:
        """Get dictionary item by code.

        Args:
            code: Item code to look up

        Returns:
            Dictionary item or None if not found
        """
        for item in self.items:
            if item.code == code:
                return item
        return None

    def get_item_by_name(self, name: str) -> Optional[DbDictItemDef]:
        """Get dictionary item by name.

        Args:
            name: Item name to look up

        Returns:
            Dictionary item or None if not found
        """
        for item in self.items:
            if item.name == name:
                return item
        return None

    def get_children(self, parent_code: Optional[str] = None) -> List[DbDictItemDef]:
        """Get children items of a parent.

        Args:
            parent_code: Parent code (None for root items)

        Returns:
            List of child items
        """
        return [
            item for item in self.items
            if item.parent_code == parent_code
        ]

    def get_all_codes(self) -> List[str]:
        """Get all item codes.

        Returns:
            List of all codes
        """
        return [item.code for item in self.items]

    def add_item(self, item: DbDictItemDef) -> "DbDictDef":
        """Add an item to the dictionary.

        Args:
            item: Item to add

        Returns:
            Self for chaining
        """
        self.items.append(item)
        return self

    def validate_definition(self) -> List[str]:
        """Validate the dictionary definition."""
        errors = super().validate_definition()

        if self.dict_type == "dynamic":
            if not self.datasource:
                errors.append("datasource is required for dynamic dictionary")
            if not self.query_sql:
                errors.append("query_sql is required for dynamic dictionary")
            if not self.code_column:
                errors.append("code_column is required for dynamic dictionary")

        return errors