"""Dictionary definition for lookup values."""

from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, List, Optional
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


class DbDictionaryDiscoveryAliasDef(BaseModel):
    """Business alias for runtime observed dictionary values."""

    values: List[Any] = Field(default_factory=list, description="Underlying values for the alias")
    description: Optional[str] = Field(default=None, description="Business description")

    model_config = {
        "extra": "allow",
    }


class DbDictionaryDiscoveryDef(BaseModel):
    """Field-level runtime dictionary value discovery contract.

    Aligned with the Java ``DbDictionaryDiscoveryDef`` contract. This is an
    explicit opt-in metadata aid for low-cardinality fields, not a replacement
    for governed static dictionary definitions.
    """

    STRATEGY_GROUP_BY: ClassVar[str] = "group_by"
    STRATEGY_DISTINCT: ClassVar[str] = "distinct"
    DEFAULT_MAX_VALUES: ClassVar[int] = 50
    MAX_ALLOWED_VALUES: ClassVar[int] = 500
    DEFAULT_REFRESH_TTL_SECONDS: ClassVar[int] = 3600

    enabled: bool = Field(default=False, description="Enable runtime dictionary discovery")
    strategy: Optional[str] = Field(default=None, description="group_by or distinct")
    max_values: Optional[int] = Field(default=None, alias="maxValues", description="Maximum exposed values")
    refresh_ttl_seconds: Optional[int] = Field(
        default=None,
        alias="refreshTtlSeconds",
        description="Cache refresh TTL in seconds",
    )
    expose_to_llm: Optional[bool] = Field(
        default=None,
        alias="exposeToLlm",
        description="Whether discovery metadata may be exposed to LLM context",
    )
    sensitive: bool = Field(default=False, description="Sensitive fields never expose runtime values")
    aliases: Dict[str, DbDictionaryDiscoveryAliasDef] = Field(
        default_factory=dict,
        description="Governed business aliases for underlying values",
    )

    model_config = {
        "extra": "allow",
        "populate_by_name": True,
    }

    @property
    def effective_strategy(self) -> str:
        return self.strategy or self.STRATEGY_GROUP_BY

    @property
    def effective_max_values(self) -> int:
        return self.max_values if self.max_values is not None else self.DEFAULT_MAX_VALUES

    @property
    def effective_refresh_ttl_seconds(self) -> int:
        if self.refresh_ttl_seconds is None:
            return self.DEFAULT_REFRESH_TTL_SECONDS
        return self.refresh_ttl_seconds

    @property
    def llm_visible(self) -> bool:
        expose = True if self.expose_to_llm is None else bool(self.expose_to_llm)
        return bool(self.enabled) and expose and not bool(self.sensitive)

    def validate_contract(self, owner_path: str) -> None:
        """Fail closed for invalid enabled discovery definitions."""
        if not self.enabled:
            return

        if self.effective_strategy not in {self.STRATEGY_GROUP_BY, self.STRATEGY_DISTINCT}:
            raise ValueError(f"{owner_path} dictionaryDiscovery.strategy only supports group_by or distinct")

        if self.effective_max_values < 1 or self.effective_max_values > self.MAX_ALLOWED_VALUES:
            raise ValueError(
                f"{owner_path} dictionaryDiscovery.maxValues must be between 1 and "
                f"{self.MAX_ALLOWED_VALUES}"
            )

        if self.effective_refresh_ttl_seconds < 0:
            raise ValueError(f"{owner_path} dictionaryDiscovery.refreshTtlSeconds cannot be negative")

        for alias_name, alias_def in (self.aliases or {}).items():
            if not str(alias_name or "").strip():
                raise ValueError(f"{owner_path} dictionaryDiscovery.aliases does not allow empty alias")
            if alias_def is None or not alias_def.values:
                raise ValueError(
                    f"{owner_path} dictionaryDiscovery.aliases.{alias_name}.values cannot be empty"
                )


class DictionaryDiscoveryValueEntry(BaseModel):
    """Runtime observed dictionary value entry."""

    value: Any
    count: Optional[int] = None


class DictionaryDiscoveryResult(BaseModel):
    """Runtime observed dictionary values for a semantic field."""

    STATUS_SAMPLED: ClassVar[str] = "sampled"
    STATUS_FAILED: ClassVar[str] = "failed"

    status: str
    values: List[DictionaryDiscoveryValueEntry] = Field(default_factory=list)
    truncated: bool = False
    sampled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="sampledAt")
    error: Optional[str] = None

    model_config = {
        "populate_by_name": True,
    }

    @classmethod
    def sampled(
        cls,
        values: List[DictionaryDiscoveryValueEntry],
        truncated: bool,
        sampled_at: Optional[datetime] = None,
    ) -> "DictionaryDiscoveryResult":
        return cls(
            status=cls.STATUS_SAMPLED,
            values=values or [],
            truncated=truncated,
            sampled_at=sampled_at or datetime.now(timezone.utc),
        )

    @classmethod
    def failed(cls, error: str) -> "DictionaryDiscoveryResult":
        return cls(
            status=cls.STATUS_FAILED,
            values=[],
            truncated=False,
            sampled_at=datetime.now(timezone.utc),
            error=error,
        )
