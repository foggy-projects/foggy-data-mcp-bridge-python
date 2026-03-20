"""
预聚合拦截器

基于 Java PreAggregationInterceptor 迁移
在查询执行前检查是否可以使用预聚合表，并进行查询重写。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import logging

from foggy.dataset_model.engine.preagg.matcher import (
    PreAggregation,
    PreAggQueryRequirement,
    PreAggregationMatchResult,
    PreAggregationMatcher,
)

if TYPE_CHECKING:
    from foggy.dataset_model.impl.model import DbTableModelImpl

logger = logging.getLogger(__name__)


@dataclass
class PreAggRewriteResult:
    """预聚合重写结果"""
    applied: bool = False
    sql: Optional[str] = None
    pre_aggregation: Optional[PreAggregation] = None
    needs_rollup: bool = False
    is_hybrid: bool = False
    watermark: Optional[Any] = None
    original_sql: Optional[str] = None

    @classmethod
    def not_applied(cls) -> 'PreAggRewriteResult':
        """创建未应用的结果"""
        return cls(applied=False)

    @classmethod
    def applied_result(
        cls,
        sql: str,
        pre_agg: PreAggregation,
        needs_rollup: bool = False,
        is_hybrid: bool = False,
        watermark: Optional[Any] = None,
        original_sql: Optional[str] = None
    ) -> 'PreAggRewriteResult':
        """创建已应用的结果"""
        return cls(
            applied=True,
            sql=sql,
            pre_aggregation=pre_agg,
            needs_rollup=needs_rollup,
            is_hybrid=is_hybrid,
            watermark=watermark,
            original_sql=original_sql
        )


class PreAggQueryRequirementBuilder:
    """
    预聚合查询需求构建器

    从查询请求和 JDBC 查询中提取需求
    """

    def build(
        self,
        query_request: Dict[str, Any],
        jdbc_query: Any,
        query_model: Any
    ) -> PreAggQueryRequirement:
        """
        构建查询需求

        Args:
            query_request: 查询请求定义
            jdbc_query: JDBC 查询对象
            query_model: 查询模型

        Returns:
            PreAggQueryRequirement: 查询需求
        """
        requirement = PreAggQueryRequirement()

        # 从 SELECT 列中提取维度和度量
        select_columns = query_request.get("select", [])
        group_by = query_request.get("groupBy", [])

        # 设置是否有 GROUP BY
        requirement.has_group_by = bool(group_by)

        # 提取维度
        for col in select_columns:
            if col.get("isDimension", False):
                requirement.dimensions.append(col.get("name"))

        # 从 GROUP BY 提取维度
        for dim in group_by:
            if dim not in requirement.dimensions:
                requirement.dimensions.append(dim)

        # 提取度量
        for col in select_columns:
            if col.get("isMeasure", False):
                requirement.measures.append(col.get("name"))

        # 提取 slice 条件
        slices = query_request.get("slice", [])
        for slice_cond in slices:
            field = slice_cond.get("field", "")
            if field:
                requirement.slice_columns.append(field)

        return requirement


class PreAggQueryRewriter:
    """
    预聚合查询重写器

    将原始查询重写为使用预聚合表的查询
    """

    def rewrite(
        self,
        match_result: PreAggregationMatchResult,
        jdbc_query: Any,
        query_request: Dict[str, Any],
        query_engine: Any
    ) -> PreAggRewriteResult:
        """
        重写查询

        Args:
            match_result: 匹配结果
            jdbc_query: 原始 JDBC 查询
            query_request: 查询请求
            query_engine: 查询引擎

        Returns:
            PreAggRewriteResult: 重写结果
        """
        if not match_result.matched:
            return PreAggRewriteResult.not_applied()

        pre_agg = match_result.pre_aggregation
        if not pre_agg:
            return PreAggRewriteResult.not_applied()

        # 获取原始 SQL
        original_sql = getattr(jdbc_query, 'sql', None) or str(jdbc_query)

        # 构建新的 SQL（简单实现：替换表名）
        new_sql = self._build_pre_agg_sql(pre_agg.table_name, original_sql)

        return PreAggRewriteResult.applied_result(
            sql=new_sql,
            pre_agg=pre_agg,
            needs_rollup=match_result.needs_rollup,
            is_hybrid=match_result.needs_hybrid,
            watermark=match_result.watermark,
            original_sql=original_sql
        )

    def _build_pre_agg_sql(self, pre_agg_table: str, original_sql: str) -> str:
        """
        构建预聚合 SQL

        Args:
            pre_agg_table: 预聚合表名
            original_sql: 原始 SQL

        Returns:
            重写后的 SQL
        """
        # 简单实现：在注释中标记使用预聚合表
        # 实际实现需要解析 SQL 并替换表名
        return f"/* PreAgg: {pre_agg_table} */ {original_sql}"

    def build_aggregate_sql(
        self,
        pre_agg: PreAggregation,
        jdbc_query: Any,
        query_request: Dict[str, Any],
        match_result: PreAggregationMatchResult
    ) -> Optional['PreAggAggregateSqlResult']:
        """
        构建聚合 SQL（用于 returnTotal）

        Args:
            pre_agg: 预聚合定义
            jdbc_query: JDBC 查询
            query_request: 查询请求
            match_result: 匹配结果

        Returns:
            PreAggAggregateSqlResult 或 None
        """
        # 获取度量
        measures = query_request.get("select", [])
        agg_expressions = []

        for m in measures:
            if m.get("isMeasure", False):
                name = m.get("name", "")
                agg = m.get("aggregation", "SUM").upper()
                agg_expressions.append(f"{agg}({name}) AS {name}")

        if not agg_expressions:
            return None

        # 构建 SQL
        sql = f"SELECT {', '.join(agg_expressions)} FROM {pre_agg.table_name}"

        return PreAggAggregateSqlResult(
            sql=sql,
            pre_aggregation=pre_agg,
            is_hybrid=match_result.needs_hybrid,
            watermark=match_result.watermark
        )


@dataclass
class PreAggAggregateSqlResult:
    """聚合 SQL 结果"""
    sql: str
    pre_aggregation: PreAggregation
    is_hybrid: bool = False
    watermark: Optional[Any] = None


class PreAggregationInterceptor:
    """
    预聚合拦截器

    在查询执行前检查是否可以使用预聚合表，并进行查询重写。
    支持两种查询模式：
    - 完全预聚合模式：仅从预聚合表查询
    - 混合查询模式（Lambda 架构）：预聚合表 UNION 原始表
    """

    def __init__(self, hybrid_query_enabled: bool = True):
        """
        初始化拦截器

        Args:
            hybrid_query_enabled: 是否启用混合查询
        """
        self._hybrid_query_enabled = hybrid_query_enabled
        self._matcher = PreAggregationMatcher(hybrid_query_enabled=hybrid_query_enabled)
        self._requirement_builder = PreAggQueryRequirementBuilder()
        self._rewriter = PreAggQueryRewriter()

    def set_hybrid_query_enabled(self, enabled: bool) -> None:
        """设置是否启用混合查询"""
        self._hybrid_query_enabled = enabled
        self._matcher.set_hybrid_query_enabled(enabled)

    def try_rewrite(
        self,
        query_engine: Any,
        query_model: Any,
        query_request: Dict[str, Any]
    ) -> PreAggRewriteResult:
        """
        尝试使用预聚合重写查询

        Args:
            query_engine: 查询引擎
            query_model: 查询模型
            query_request: 查询请求

        Returns:
            PreAggRewriteResult: 重写结果
        """
        # 1. 获取可用的预聚合列表
        pre_aggregations = self._get_pre_aggregations(query_model)
        if not pre_aggregations:
            logger.debug(f"No pre-aggregations configured for model")
            return PreAggRewriteResult.not_applied()

        # 2. 从查询中提取需求
        jdbc_query = getattr(query_engine, 'jdbc_query', None)
        requirement = self._requirement_builder.build(query_request, jdbc_query, query_model)

        logger.debug(f"Query requirement: {requirement}")

        # 3. 匹配最佳预聚合
        match_result = self._matcher.find_best_match(requirement, pre_aggregations)

        if not match_result.matched:
            logger.debug(f"No pre-aggregation matched: {match_result.message}")
            return PreAggRewriteResult.not_applied()

        # 4. 记录匹配结果
        if match_result.needs_hybrid:
            logger.info(f"Using hybrid query mode for pre-aggregation '{match_result.pre_aggregation.name}'")
        else:
            logger.info(f"Using full pre-aggregation query for '{match_result.pre_aggregation.name}'")

        # 5. 重写查询
        return self._rewriter.rewrite(match_result, jdbc_query, query_request, query_engine)

    def try_build_aggregate_sql(
        self,
        query_engine: Any,
        query_model: Any,
        query_request: Dict[str, Any]
    ) -> Optional[PreAggAggregateSqlResult]:
        """
        尝试为聚合查询构建预聚合 SQL

        Args:
            query_engine: 查询引擎
            query_model: 查询模型
            query_request: 查询请求

        Returns:
            PreAggAggregateSqlResult 或 None
        """
        pre_aggregations = self._get_pre_aggregations(query_model)
        if not pre_aggregations:
            return None

        jdbc_query = getattr(query_engine, 'jdbc_query', None)
        requirement = self._build_aggregate_requirement(query_request, jdbc_query, query_model)

        match_result = self._matcher.find_best_match(requirement, pre_aggregations)

        if not match_result.matched:
            return None

        return self._rewriter.build_aggregate_sql(
            match_result.pre_aggregation,
            jdbc_query,
            query_request,
            match_result
        )

    def _get_pre_aggregations(self, query_model: Any) -> List[PreAggregation]:
        """获取模型的预聚合列表"""
        if query_model is None:
            return []

        # 从 TableModel 获取预聚合配置
        table_model = getattr(query_model, 'table_model', None)
        if table_model is None:
            return []

        pre_aggs = getattr(table_model, 'pre_aggregations', None)
        return pre_aggs or []

    def _build_aggregate_requirement(
        self,
        query_request: Dict[str, Any],
        jdbc_query: Any,
        query_model: Any
    ) -> PreAggQueryRequirement:
        """构建聚合查询需求"""
        requirement = PreAggQueryRequirement()

        # 聚合查询设置 has_group_by = True
        requirement.has_group_by = True

        # 从 SELECT 列中提取度量
        for col in query_request.get("select", []):
            if col.get("isMeasure", False):
                requirement.measures.append(col.get("name"))

        # 提取 slice 列
        for slice_cond in query_request.get("slice", []):
            field = slice_cond.get("field", "")
            if field:
                requirement.slice_columns.append(field)

        return requirement


__all__ = [
    "PreAggRewriteResult",
    "PreAggQueryRequirementBuilder",
    "PreAggQueryRewriter",
    "PreAggAggregateSqlResult",
    "PreAggregationInterceptor",
]