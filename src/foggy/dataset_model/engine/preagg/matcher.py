"""
PreAggregation Matcher - 预聚合匹配器

基于 Java PreAggregationMatcher 迁移
实现查询优化能力，选择最佳的预聚合表。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import date, datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TimeGranularity(Enum):
    """时间粒度枚举"""
    SECOND = 1
    MINUTE = 2
    HOUR = 3
    DAY = 4
    WEEK = 5
    MONTH = 6
    QUARTER = 7
    YEAR = 8

    def is_finer_than(self, other: 'TimeGranularity') -> bool:
        """检查当前粒度是否比另一个更细"""
        return self.value < other.value


@dataclass
class PreAggregation:
    """预聚合定义"""
    name: str
    table_name: str
    enabled: bool = True
    priority: int = 0
    dimensions: List[str] = field(default_factory=list)
    measures: List[str] = field(default_factory=list)
    granularities: Dict[str, TimeGranularity] = field(default_factory=dict)
    data_watermark: Optional[Any] = None
    supports_hybrid: bool = False

    def is_enabled(self) -> bool:
        """是否启用"""
        return self.enabled

    def get_dimension_count(self) -> int:
        """获取维度数量"""
        return len(self.dimensions)

    def get_granularity_level(self) -> int:
        """获取粒度级别（最细粒度的值）"""
        if not self.granularities:
            return 0
        return min(g.value for g in self.granularities.values())

    def supports_hybrid_query(self) -> bool:
        """是否支持混合查询"""
        return self.supports_hybrid

    def get_data_watermark(self) -> Optional[Any]:
        """获取数据水位线"""
        return self.data_watermark


@dataclass
class PreAggQueryRequirement:
    """预聚合查询需求"""
    dimensions: List[str] = field(default_factory=list)
    measures: List[str] = field(default_factory=list)
    granularities: Dict[str, TimeGranularity] = field(default_factory=dict)
    has_group_by: bool = False
    has_custom_sql_conditions: bool = False
    slice_columns: List[str] = field(default_factory=list)

    def get_dimension_count(self) -> int:
        """获取维度数量"""
        return len(self.dimensions)

    def get_granularity_level(self) -> int:
        """获取粒度级别"""
        if not self.granularities:
            return 0
        return max(g.value for g in self.granularities.values())

    def get_query_granularities(self) -> Dict[str, TimeGranularity]:
        """获取查询粒度"""
        return self.granularities

    def is_satisfiable_by(self, pre_agg: PreAggregation) -> bool:
        """
        检查预聚合是否满足查询需求

        Args:
            pre_agg: 预聚合定义

        Returns:
            bool: 是否满足需求
        """
        # 检查维度覆盖
        for dim in self.dimensions:
            if dim not in pre_agg.dimensions:
                return False

        # 检查度量覆盖
        for measure in self.measures:
            if measure not in pre_agg.measures:
                return False

        # 检查粒度（预聚合粒度必须比查询粒度更细或相同）
        # 粒度值越小越细：DAY=4 < MONTH=6 < YEAR=8
        # 如果预聚合粒度比查询粒度更粗（值更大），不满足需求
        for dim, query_gran in self.granularities.items():
            if dim in pre_agg.granularities:
                pre_agg_gran = pre_agg.granularities[dim]
                if pre_agg_gran.value > query_gran.value:
                    # 预聚合粒度比查询粒度粗，无法满足
                    return False

        # 检查 slice 列是否在预聚合中
        for slice_col in self.slice_columns:
            if slice_col not in pre_agg.dimensions:
                return False

        return True


@dataclass
class PreAggregationMatchResult:
    """预聚合匹配结果"""
    matched: bool = False
    pre_aggregation: Optional[PreAggregation] = None
    needs_rollup: bool = False
    needs_hybrid: bool = False
    watermark: Optional[Any] = None
    score: int = 0
    message: str = ""

    @classmethod
    def no_match(cls, reason: str) -> 'PreAggregationMatchResult':
        """创建无匹配结果"""
        return cls(matched=False, message=reason)

    @classmethod
    def matched(
        cls,
        pre_agg: PreAggregation,
        needs_rollup: bool,
        score: int
    ) -> 'PreAggregationMatchResult':
        """创建匹配结果"""
        return cls(
            matched=True,
            pre_aggregation=pre_agg,
            needs_rollup=needs_rollup,
            score=score
        )

    @classmethod
    def hybrid(
        cls,
        pre_agg: PreAggregation,
        needs_rollup: bool,
        watermark: Any,
        score: int
    ) -> 'PreAggregationMatchResult':
        """创建混合查询结果"""
        return cls(
            matched=True,
            pre_aggregation=pre_agg,
            needs_rollup=needs_rollup,
            needs_hybrid=True,
            watermark=watermark,
            score=score
        )


@dataclass
class Candidate:
    """匹配候选"""
    pre_aggregation: PreAggregation
    score: int
    needs_rollup: bool
    needs_hybrid: bool
    watermark: Optional[Any] = None


class PreAggregationMatcher:
    """
    预聚合匹配器

    根据查询需求选择最佳的预聚合表。

    选择策略：
    1. 满足所有查询需求（维度、属性、度量、粒度）
    2. 优先级（priority）高的优先
    3. 维度数最接近查询维度数的优先（避免冗余数据）
    4. 粒度最接近查询粒度的优先（减少 rollup 开销）

    混合查询支持：
    当预聚合数据不完整时（watermark 不是最新），自动启用混合查询模式，
    将预聚合表和原始表的数据合并查询。
    """

    def __init__(self, hybrid_query_enabled: bool = True):
        """
        初始化匹配器

        Args:
            hybrid_query_enabled: 是否启用混合查询
        """
        self._hybrid_query_enabled = hybrid_query_enabled

    def set_hybrid_query_enabled(self, enabled: bool) -> None:
        """设置是否启用混合查询"""
        self._hybrid_query_enabled = enabled

    def find_best_match(
        self,
        requirement: PreAggQueryRequirement,
        pre_aggregations: List[PreAggregation]
    ) -> PreAggregationMatchResult:
        """
        从可用的预聚合列表中选择最佳匹配

        Args:
            requirement: 查询需求
            pre_aggregations: 可用的预聚合列表

        Returns:
            PreAggregationMatchResult: 匹配结果
        """
        if not pre_aggregations:
            return PreAggregationMatchResult.no_match("No pre-aggregations configured")

        if requirement is None:
            return PreAggregationMatchResult.no_match("Query requirement is null")

        # 只有有分组的查询才考虑预聚合
        if not requirement.has_group_by:
            return PreAggregationMatchResult.no_match(
                "Query has no GROUP BY, pre-aggregation not applicable"
            )

        # 有自定义 SQL 条件时不使用预聚合
        if requirement.has_custom_sql_conditions:
            return PreAggregationMatchResult.no_match(
                "Query has custom SQL conditions, pre-aggregation not supported"
            )

        # 过滤满足条件的预聚合并计算分数
        candidates: List[Candidate] = []

        for pre_agg in pre_aggregations:
            # 跳过未启用的预聚合
            if not pre_agg.is_enabled():
                logger.debug(f"Skipping disabled pre-aggregation: {pre_agg.name}")
                continue

            # 检查是否满足需求
            if requirement.is_satisfiable_by(pre_agg):
                score = self._calculate_score(pre_agg, requirement)
                needs_rollup = self._check_needs_rollup(pre_agg, requirement)
                needs_hybrid = self._check_needs_hybrid_query(pre_agg, requirement)
                watermark = needs_hybrid and pre_agg.get_data_watermark()

                candidates.append(Candidate(
                    pre_aggregation=pre_agg,
                    score=score,
                    needs_rollup=needs_rollup,
                    needs_hybrid=needs_hybrid,
                    watermark=watermark if needs_hybrid else None
                ))

                logger.debug(
                    f"Pre-aggregation '{pre_agg.name}' is a candidate: "
                    f"score={score}, needsRollup={needs_rollup}, needsHybrid={needs_hybrid}"
                )
            else:
                logger.debug(
                    f"Pre-aggregation '{pre_agg.name}' does not satisfy requirements"
                )

        if not candidates:
            return PreAggregationMatchResult.no_match(
                "No pre-aggregation satisfies the query requirements"
            )

        # 按分数排序（降序）
        candidates.sort(key=lambda c: c.score, reverse=True)

        # 选择最高分的候选
        best = candidates[0]

        logger.info(
            f"Selected pre-aggregation '{best.pre_aggregation.name}' "
            f"with score {best.score} "
            f"(needsRollup={best.needs_rollup}, hybridQuery={best.needs_hybrid})"
        )

        # 根据是否需要混合查询返回不同的结果
        if best.needs_hybrid:
            return PreAggregationMatchResult.hybrid(
                best.pre_aggregation,
                best.needs_rollup,
                best.watermark,
                best.score
            )
        else:
            return PreAggregationMatchResult.matched(
                best.pre_aggregation,
                best.needs_rollup,
                best.score
            )

    def _check_needs_hybrid_query(
        self,
        pre_agg: PreAggregation,
        requirement: PreAggQueryRequirement
    ) -> bool:
        """
        检查是否需要混合查询

        混合查询条件：
        1. 混合查询功能已启用
        2. 预聚合支持混合查询（配置了 watermark 列）
        3. 预聚合数据不是最新的（有 watermark 且不是今天）
        """
        # 混合查询未启用
        if not self._hybrid_query_enabled:
            return False

        # 预聚合不支持混合查询
        if not pre_agg.supports_hybrid_query():
            return False

        # 检查数据是否过期
        watermark = pre_agg.get_data_watermark()
        if watermark is None:
            # 没有 watermark，需要混合查询
            return True

        # 检查 watermark 是否是今天
        today = date.today()

        if isinstance(watermark, date):
            return watermark < today
        elif isinstance(watermark, datetime):
            return watermark.date() < today

        # 无法判断，保守起见使用混合查询
        return True

    def _calculate_score(
        self,
        pre_agg: PreAggregation,
        requirement: PreAggQueryRequirement
    ) -> int:
        """
        计算预聚合的匹配分数

        评分规则：
        - priority * 100（权重最高）
        - - (预聚合维度数 - 查询维度数) * 10（维度数接近）
        - - (预聚合粒度级别 - 查询粒度级别)（粒度接近）
        """
        score = pre_agg.priority * 100

        # 维度数惩罚：预聚合维度越多，分数越低
        dim_diff = pre_agg.get_dimension_count() - requirement.get_dimension_count()
        score -= dim_diff * 10

        # 粒度惩罚
        gran_diff = pre_agg.get_granularity_level() - requirement.get_granularity_level()
        if gran_diff < 0:
            # 预聚合粒度比查询粒度粗，这不应该发生
            score -= 1000
        else:
            score -= gran_diff

        return score

    def _check_needs_rollup(
        self,
        pre_agg: PreAggregation,
        requirement: PreAggQueryRequirement
    ) -> bool:
        """
        检查是否需要 rollup

        当预聚合的粒度比查询粒度更细时，需要进行二次聚合。
        """
        query_granularities = requirement.get_query_granularities()
        pre_agg_granularities = pre_agg.granularities

        if not query_granularities or not pre_agg_granularities:
            return False

        for dim_name, query_gran in query_granularities.items():
            pre_agg_gran = pre_agg_granularities.get(dim_name)

            if pre_agg_gran and query_gran:
                # 如果预聚合粒度比查询粒度更细，需要 rollup
                if pre_agg_gran.is_finer_than(query_gran):
                    return True

        return False