"""
语义查询服务 V3 实现

基于 Java SemanticQueryServiceV3Impl 迁移
核心简化：字段名直接使用，无需判断和拼接后缀
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class SliceItem:
    """切片条件项"""
    field: str
    op: str = "="
    value: Any = None
    # 逻辑组支持
    or_conditions: Optional[List['SliceItem']] = None
    and_conditions: Optional[List['SliceItem']] = None

    def is_logical_group(self) -> bool:
        """是否是逻辑组"""
        return self.or_conditions is not None or self.and_conditions is not None

    def is_or_group(self) -> bool:
        """是否是 OR 组"""
        return self.or_conditions is not None

    def get_group_children(self) -> List['SliceItem']:
        """获取子条件"""
        return self.or_conditions or self.and_conditions or []


@dataclass
class GroupByItem:
    """分组项"""
    field: str
    agg: Optional[str] = None  # SUM, AVG, COUNT, MAX, MIN


@dataclass
class OrderByItem:
    """排序项"""
    field: str
    dir: str = "ASC"


@dataclass
class SemanticQueryRequest:
    """语义查询请求"""
    columns: List[str] = field(default_factory=list)
    slice: List[SliceItem] = field(default_factory=list)
    group_by: List[GroupByItem] = field(default_factory=list)
    order_by: List[OrderByItem] = field(default_factory=list)
    start: Optional[int] = None
    limit: Optional[int] = None
    return_total: bool = False
    distinct: bool = False
    with_subtotals: bool = False
    hints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PaginationInfo:
    """分页信息"""
    start: int = 0
    limit: int = 20
    returned: int = 0
    total_count: Optional[int] = None
    has_more: bool = False
    range_description: str = ""


@dataclass
class ColumnDef:
    """列定义"""
    name: str
    title: Optional[str] = None
    data_type: Optional[str] = None


@dataclass
class SchemaInfo:
    """Schema 信息"""
    columns: List[ColumnDef] = field(default_factory=list)
    summary: Optional[str] = None


@dataclass
class DebugInfo:
    """调试信息"""
    duration_ms: float = 0


@dataclass
class SemanticQueryResponse:
    """语义查询响应"""
    items: List[Dict[str, Any]] = field(default_factory=list)
    pagination: Optional[PaginationInfo] = None
    total: int = 0
    has_next: bool = False
    total_data: Optional[Dict[str, Any]] = None
    warnings: Optional[List[str]] = None
    schema: Optional[SchemaInfo] = None
    truncation_info: Optional[Dict[str, Any]] = None
    debug: Optional[DebugInfo] = None


@dataclass
class QueryContext:
    """查询上下文"""
    model: str = ""
    original_request: Optional[SemanticQueryRequest] = None
    ext_data: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


class SemanticQueryServiceV3:
    """
    V3 版本语义查询服务

    核心简化：字段名直接使用，无需判断和拼接后缀

    与 V2 的区别：
    - 不再需要将 $caption 归一化为 $id
    - 不再需要自动补全 $id/$caption 后缀
    - 所有字段直接透传给底层服务
    """

    def __init__(
        self,
        query_facade: Optional[Any] = None,
        query_model_loader: Optional[Any] = None,
        dimension_member_loader: Optional[Any] = None
    ):
        """
        初始化服务

        Args:
            query_facade: 查询门面
            query_model_loader: 查询模型加载器
            dimension_member_loader: 维度成员加载器
        """
        self._query_facade = query_facade
        self._query_model_loader = query_model_loader
        self._dimension_member_loader = dimension_member_loader

    def query_model(
        self,
        model: str,
        request: SemanticQueryRequest,
        mode: str = "",
        context: Optional[Dict[str, Any]] = None
    ) -> SemanticQueryResponse:
        """
        执行查询

        Args:
            model: 模型名称
            request: 查询请求
            mode: 查询模式（"validate" 表示验证模式）
            context: 请求上下文

        Returns:
            SemanticQueryResponse: 查询响应
        """
        if mode == "validate":
            return self._validate_query(model, request)

        if not request.columns:
            raise ValueError("请指定查询字段")

        start_time = time.time()

        # 创建上下文
        query_ctx = QueryContext()
        query_ctx.model = model
        query_ctx.original_request = request

        # 构建 JDBC 请求
        jdbc_request = self._build_jdbc_request(model, request, query_ctx)

        # 处理 slice 值转换
        if request.slice:
            processed_slice = self._process_slice_values(model, request.slice)
            jdbc_request["slice"] = processed_slice

        # 执行查询（这里需要实际的查询执行器）
        # TODO: 集成实际的查询执行
        query_result = {"items": [], "total": 0}

        # 构建响应
        response = self._build_response(jdbc_request, query_result, query_ctx)

        # 添加调试信息
        if logger.isEnabledFor(logging.DEBUG):
            response.debug = DebugInfo(
                duration_ms=(time.time() - start_time) * 1000
            )

        return response

    def validate_query(
        self,
        model: str,
        request: SemanticQueryRequest,
        context: Optional[Dict[str, Any]] = None
    ) -> SemanticQueryResponse:
        """验证查询"""
        return self._validate_query(model, request)

    def generate_sql(
        self,
        model: str,
        request: SemanticQueryRequest,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成 SQL（不执行）

        Args:
            model: 模型名称
            request: 查询请求
            context: 请求上下文

        Returns:
            SQL 生成结果
        """
        if not request.columns:
            raise ValueError("请指定查询字段")

        query_ctx = QueryContext()
        query_ctx.model = model
        query_ctx.original_request = request

        jdbc_request = self._build_jdbc_request(model, request, query_ctx)

        return {
            "sql": "SELECT ... FROM ...",
            "params": [],
            "request": jdbc_request
        }

    def _validate_query(
        self,
        model: str,
        request: SemanticQueryRequest
    ) -> SemanticQueryResponse:
        """验证查询（内部方法）"""
        response = SemanticQueryResponse()

        # 检查模型是否存在
        # TODO: 实际的模型检查

        warnings = []

        # 检查 columns 中的字段
        if request.columns:
            # TODO: 实际的字段检查
            pass

        # 检查 slice
        for slice_item in request.slice:
            if not slice_item.field:
                raise ValueError("slice 中的 field 不能为空")

        # 检查 groupBy 和 columns 的对齐
        if request.group_by and request.columns:
            self._validate_group_by_fields(request.group_by, request.columns, warnings)

        if warnings:
            response.warnings = warnings

        return response

    def _build_jdbc_request(
        self,
        model: str,
        request: SemanticQueryRequest,
        context: QueryContext
    ) -> Dict[str, Any]:
        """构建 JDBC 查询请求"""
        query_def = {
            "query_model": model,
            "return_total": request.return_total,
            "strict_columns": True,
            "distinct": request.distinct,
            "with_subtotals": request.with_subtotals
        }

        columns = list(request.columns)
        group_by_items = list(request.group_by) if request.group_by else []

        # 自动对齐 columns 和 groupBy
        if group_by_items:
            self._align_columns_and_group_by(columns, group_by_items, context)
            self._validate_group_by_fields(group_by_items, columns)

        query_def["columns"] = columns

        # 转换过滤条件
        if request.slice:
            query_def["slice"] = [
                self._convert_to_jdbc_slice(s) for s in request.slice
            ]

        # 转换分组
        if group_by_items:
            query_def["group_by"] = [
                {"field": item.field, "agg": item.agg}
                for item in group_by_items
            ]

        # 转换排序
        if request.order_by:
            query_def["order_by"] = [
                {"field": item.field, "dir": item.dir}
                for item in request.order_by
            ]

        jdbc_request = {"param": query_def}

        if request.start is not None:
            jdbc_request["start"] = request.start
        if request.limit is not None:
            jdbc_request["page_size"] = request.limit

        return jdbc_request

    def _process_slice_values(
        self,
        model: str,
        slice_items: List[SliceItem]
    ) -> List[Dict[str, Any]]:
        """处理 slice 值转换"""
        processed = []

        for item in slice_items:
            # 逻辑组：递归转换
            if item.is_logical_group():
                converted = self._convert_to_jdbc_slice(item)
                processed.append(converted)
                continue

            processed.append({
                "field": item.field,
                "op": item.op,
                "value": item.value
            })

        return processed

    def _convert_to_jdbc_slice(self, item: SliceItem) -> Dict[str, Any]:
        """转换为 JDBC slice"""
        # 逻辑组：递归转换
        if item.is_logical_group():
            children = [
                self._convert_to_jdbc_slice(c)
                for c in item.get_group_children()
            ]
            if item.is_or_group():
                return {"or": children}
            else:
                return {"and": children}

        return {
            "field": item.field,
            "op": item.op,
            "value": item.value
        }

    def _build_response(
        self,
        jdbc_request: Dict[str, Any],
        query_result: Dict[str, Any],
        context: QueryContext
    ) -> SemanticQueryResponse:
        """构建响应"""
        response = SemanticQueryResponse()

        # 转换数据项
        items = query_result.get("items", [])
        response.items = items
        returned_count = len(items)

        # 分页信息
        total = query_result.get("total", 0)
        start = jdbc_request.get("start", 0)
        limit = jdbc_request.get("page_size", 20)

        has_more = total > start + returned_count

        response.pagination = PaginationInfo(
            start=start,
            limit=limit,
            returned=returned_count,
            total_count=total if total > 0 else None,
            has_more=has_more,
            range_description=self._build_range_description(
                start, returned_count, limit, total, has_more
            )
        )

        response.total = total
        response.has_next = has_more
        response.total_data = query_result.get("total_data")

        # 设置警告信息
        if context.warnings:
            response.warnings = context.warnings

        return response

    def _build_range_description(
        self,
        start: int,
        returned: int,
        limit: int,
        total: int,
        has_more: bool
    ) -> str:
        """构建数据范围描述"""
        if returned == 0:
            return "无数据"

        from_idx = start + 1
        to_idx = start + returned

        desc = f"显示第 {from_idx}-{to_idx} 条"

        if total > 0:
            desc += f"，共 {total} 条"
        elif has_more:
            if returned == limit:
                desc += "，可能还有更多数据"
            else:
                desc += "，还有更多数据"

        return desc

    def _align_columns_and_group_by(
        self,
        columns: List[str],
        group_by_items: List[GroupByItem],
        context: QueryContext
    ) -> None:
        """自动对齐 columns 和 groupBy"""
        # 收集 columns 中的维度字段
        column_dimensions: Dict[str, set] = {}
        for col in columns:
            if "$" in col:
                base_name = col.rsplit("$", 1)[0]
                suffix = col.rsplit("$", 1)[1]
                if base_name not in column_dimensions:
                    column_dimensions[base_name] = set()
                column_dimensions[base_name].add(suffix)

        # 收集 groupBy 中的维度字段
        group_by_dimensions: Dict[str, set] = {}
        for item in group_by_items:
            if item.agg:  # 跳过度量字段
                continue
            field = item.field
            if "$" in field:
                base_name = field.rsplit("$", 1)[0]
                suffix = field.rsplit("$", 1)[1]
                if base_name not in group_by_dimensions:
                    group_by_dimensions[base_name] = set()
                group_by_dimensions[base_name].add(suffix)

        # 找出需要对齐的字段
        all_bases = set(column_dimensions.keys()) | set(group_by_dimensions.keys())
        columns_set = set(columns)
        group_by_fields = {item.field for item in group_by_items}

        for base in all_bases:
            col_suffixes = column_dimensions.get(base, set())
            grp_suffixes = group_by_dimensions.get(base, set())

            # 补充缺失的字段
            # TODO: 实际的字段补充逻辑

    def _validate_group_by_fields(
        self,
        group_by_items: List[GroupByItem],
        columns: List[str],
        warnings: Optional[List[str]] = None
    ) -> None:
        """校验 groupBy 字段"""
        columns_set = set(columns)

        for item in group_by_items:
            if item.agg:  # 跳过度量字段
                continue

            if item.field not in columns_set:
                msg = f"groupBy 字段 {item.field} 必须出现在 columns 中"
                if warnings is not None:
                    warnings.append(msg)
                else:
                    raise ValueError(msg)


# 便捷函数
def query_request(
    columns: List[str],
    **kwargs
) -> SemanticQueryRequest:
    """创建查询请求"""
    return SemanticQueryRequest(columns=columns, **kwargs)