"""
属性实现类

基于 Java DbPropertyImpl 迁移
"""

from typing import Any, Dict, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field
from enum import Enum

from foggy.dataset_model.definitions.base import ColumnType

if TYPE_CHECKING:
    from foggy.dataset_model.impl.model import DbTableModelImpl
    from foggy.dataset_model.impl.dimension import DbModelDimensionImpl


class PropertyType(str, Enum):
    """属性类型"""
    BASIC = "basic"
    CALCULATED = "calculated"
    DICT = "dict"


class DbPropertyImpl(BaseModel):
    """
    属性实现类

    表示模型中的属性（非维度、非度量的列）
    """

    name: str = Field(..., description="属性名称")
    alias: Optional[str] = Field(default=None, description="显示别名")
    description: Optional[str] = Field(default=None, description="描述")
    column: str = Field(..., description="源列名")
    table: Optional[str] = Field(default=None, description="源表名")
    property_type: PropertyType = Field(default=PropertyType.BASIC, description="属性类型")
    data_type: ColumnType = Field(default=ColumnType.STRING, description="数据类型")
    format_pattern: Optional[str] = Field(default=None, description="格式化模式")
    decimals: int = Field(default=2, description="小数位数")
    dict_ref: Optional[str] = Field(default=None, description="字典引用ID")
    expression: Optional[str] = Field(default=None, description="计算表达式")
    ext_data: Dict[str, Any] = Field(default_factory=dict, description="扩展数据")
    visible: bool = Field(default=True, description="是否可见")
    sortable: bool = Field(default=True, description="是否可排序")
    filterable: bool = Field(default=True, description="是否可筛选")
    table_model: Optional["DbTableModelImpl"] = Field(default=None, description="所属表模型")
    db_dimension: Optional["DbModelDimensionImpl"] = Field(default=None, description="所属维度")

    model_config = {"extra": "allow", "arbitrary_types_allowed": True}

    def get_display_name(self) -> str:
        return self.alias or self.name

    def get_ext_data_value(self, key: str) -> Optional[Any]:
        return self.ext_data.get(key)

    def is_dict(self) -> bool:
        return self.property_type == PropertyType.DICT or bool(self.dict_ref)

    def init(self) -> None:
        if not self.column:
            raise ValueError(f"Property column cannot be empty: {self.name}")
        if not self.alias:
            self.alias = self._to_alias_name(self.column)
        if not self.name:
            self.name = self.alias

    @staticmethod
    def _to_alias_name(column: str) -> str:
        return column.replace("_", " ").title()


class DbPropertyColumn(BaseModel):
    """属性列包装类"""
    property: DbPropertyImpl = Field(..., description="所属属性")
    name: str = Field(..., description="列名")
    alias: Optional[str] = Field(default=None, description="别名")
    data_type: ColumnType = Field(default=ColumnType.STRING, description="数据类型")
    nullable: bool = Field(default=True, description="是否可空")

    model_config = {"extra": "allow"}

    def get_declare(self, alias: Optional[str] = None) -> str:
        col_alias = alias or self.alias or self.name
        if self.property.expression:
            return f"{self.property.expression} AS {col_alias}"
        return f"{self.name} AS {col_alias}"


__all__ = ["PropertyType", "DbPropertyImpl", "DbPropertyColumn"]