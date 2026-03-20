"""
数据库查询结果容器

基于 Java DbQueryResult 迁移
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from foggy.dataset_model.engine.query.jdbc_query_visitor import JdbcQuery


@dataclass
class QueryMetadata:
    """查询元数据"""
    column_names: List[str] = field(default_factory=list)
    column_types: Dict[str, str] = field(default_factory=dict)
    column_captions: Dict[str, str] = field(default_factory=dict)


@dataclass
class QueryStatistics:
    """查询统计信息"""
    total_rows: int = 0
    execution_time_ms: float = 0.0
    sql: str = ""
    has_more: bool = False


class DbQueryResult:
    """
    数据库查询结果容器

    封装查询结果、元数据和统计信息。
    """

    def __init__(
        self,
        items: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[QueryMetadata] = None,
        statistics: Optional[QueryStatistics] = None
    ):
        """
        初始化查询结果

        Args:
            items: 查询结果项列表
            metadata: 查询元数据
            statistics: 查询统计信息
        """
        self._items = items or []
        self._metadata = metadata or QueryMetadata()
        self._statistics = statistics or QueryStatistics()
        self._query_engine: Optional[Any] = None
        self._jdbc_query_model: Optional['JdbcQuery'] = None

    @property
    def items(self) -> List[Dict[str, Any]]:
        """获取结果项"""
        return self._items

    @items.setter
    def items(self, value: List[Dict[str, Any]]) -> None:
        """设置结果项"""
        self._items = value

    @property
    def metadata(self) -> QueryMetadata:
        """获取元数据"""
        return self._metadata

    @property
    def statistics(self) -> QueryStatistics:
        """获取统计信息"""
        return self._statistics

    @property
    def query_engine(self) -> Optional[Any]:
        """获取查询引擎"""
        return self._query_engine

    @query_engine.setter
    def query_engine(self, value: Any) -> None:
        """设置查询引擎"""
        self._query_engine = value

    @property
    def jdbc_query_model(self) -> Optional['JdbcQuery']:
        """获取 JDBC 查询模型"""
        return self._jdbc_query_model

    @jdbc_query_model.setter
    def jdbc_query_model(self, value: 'JdbcQuery') -> None:
        """设置 JDBC 查询模型"""
        self._jdbc_query_model = value

    def get_query_engine(self) -> Optional[Any]:
        """获取查询引擎"""
        return self._query_engine

    def get_jdbc_query_model(self) -> Optional['JdbcQuery']:
        """获取 JDBC 查询模型"""
        return self._jdbc_query_model

    def is_empty(self) -> bool:
        """检查结果是否为空"""
        return len(self._items) == 0

    def count(self) -> int:
        """获取结果数量"""
        return len(self._items)

    def first(self) -> Optional[Dict[str, Any]]:
        """获取第一个结果项"""
        return self._items[0] if self._items else None

    def first_or_default(self, default: Dict[str, Any]) -> Dict[str, Any]:
        """获取第一个结果项或默认值"""
        return self._items[0] if self._items else default

    def to_list(self) -> List[Dict[str, Any]]:
        """转换为列表"""
        return self._items.copy()

    def to_dataframe(self):
        """转换为 Pandas DataFrame"""
        try:
            import pandas as pd
            return pd.DataFrame(self._items)
        except ImportError:
            raise ImportError("pandas is required for to_dataframe()")

    def get_column_values(self, column_name: str) -> List[Any]:
        """获取指定列的所有值"""
        return [item.get(column_name) for item in self._items]

    def group_by(self, key_column: str) -> Dict[Any, List[Dict[str, Any]]]:
        """按键列分组"""
        result: Dict[Any, List[Dict[str, Any]]] = {}
        for item in self._items:
            key = item.get(key_column)
            if key not in result:
                result[key] = []
            result[key].append(item)
        return result

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __getitem__(self, index):
        return self._items[index]

    def __repr__(self) -> str:
        return f"DbQueryResult(items={len(self._items)}, rows={self._statistics.total_rows})"


class DbQueryResultBuilder:
    """
    查询结果构建器

    提供流畅的 API 来构建查询结果。
    """

    def __init__(self):
        self._items: List[Dict[str, Any]] = []
        self._metadata = QueryMetadata()
        self._statistics = QueryStatistics()

    def add_item(self, item: Dict[str, Any]) -> 'DbQueryResultBuilder':
        """添加结果项"""
        self._items.append(item)
        return self

    def add_items(self, items: List[Dict[str, Any]]) -> 'DbQueryResultBuilder':
        """添加多个结果项"""
        self._items.extend(items)
        return self

    def set_columns(self, columns: List[str]) -> 'DbQueryResultBuilder':
        """设置列名"""
        self._metadata.column_names = columns
        return self

    def set_column_type(self, column_name: str, column_type: str) -> 'DbQueryResultBuilder':
        """设置列类型"""
        self._metadata.column_types[column_name] = column_type
        return self

    def set_column_caption(self, column_name: str, caption: str) -> 'DbQueryResultBuilder':
        """设置列标题"""
        self._metadata.column_captions[column_name] = caption
        return self

    def set_total_rows(self, total: int) -> 'DbQueryResultBuilder':
        """设置总行数"""
        self._statistics.total_rows = total
        return self

    def set_execution_time(self, time_ms: float) -> 'DbQueryResultBuilder':
        """设置执行时间"""
        self._statistics.execution_time_ms = time_ms
        return self

    def set_sql(self, sql: str) -> 'DbQueryResultBuilder':
        """设置 SQL 语句"""
        self._statistics.sql = sql
        return self

    def set_has_more(self, has_more: bool) -> 'DbQueryResultBuilder':
        """设置是否有更多数据"""
        self._statistics.has_more = has_more
        return self

    def build(self) -> DbQueryResult:
        """构建结果"""
        return DbQueryResult(
            items=self._items,
            metadata=self._metadata,
            statistics=self._statistics
        )


# 便捷函数
def query_result(items: Optional[List[Dict[str, Any]]] = None) -> DbQueryResult:
    """创建查询结果"""
    return DbQueryResult(items=items)


def query_result_builder() -> DbQueryResultBuilder:
    """创建查询结果构建器"""
    return DbQueryResultBuilder()