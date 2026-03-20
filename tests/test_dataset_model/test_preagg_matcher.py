"""
PreAggregation Matcher 单元测试
"""

import pytest
from datetime import date, datetime, timedelta
from foggy.dataset_model.engine.preagg.matcher import (
    TimeGranularity,
    PreAggregation,
    PreAggQueryRequirement,
    PreAggregationMatchResult,
    PreAggregationMatcher
)


class TestTimeGranularity:
    """测试时间粒度"""

    def test_granularity_values(self):
        """测试粒度值"""
        assert TimeGranularity.DAY.value == 4
        assert TimeGranularity.MONTH.value == 6
        assert TimeGranularity.YEAR.value == 8

    def test_is_finer_than(self):
        """测试粒度比较"""
        assert TimeGranularity.DAY.is_finer_than(TimeGranularity.MONTH)
        assert TimeGranularity.HOUR.is_finer_than(TimeGranularity.DAY)
        assert not TimeGranularity.MONTH.is_finer_than(TimeGranularity.DAY)


class TestPreAggregation:
    """测试预聚合定义"""

    def test_basic_properties(self):
        """测试基本属性"""
        pre_agg = PreAggregation(
            name="daily_sales",
            table_name="agg_daily_sales",
            dimensions=["product_id", "date"],
            measures=["total_sales", "quantity"]
        )
        assert pre_agg.name == "daily_sales"
        assert pre_agg.get_dimension_count() == 2
        assert pre_agg.is_enabled()

    def test_granularity_level(self):
        """测试粒度级别"""
        pre_agg = PreAggregation(
            name="monthly_sales",
            table_name="agg_monthly_sales",
            granularities={"date": TimeGranularity.MONTH}
        )
        assert pre_agg.get_granularity_level() == 6


class TestPreAggQueryRequirement:
    """测试查询需求"""

    def test_satisfiable_by_dimensions(self):
        """测试维度满足检查"""
        requirement = PreAggQueryRequirement(
            dimensions=["product_id", "category"],
            measures=["total_sales"],
            has_group_by=True
        )

        # 满足需求的预聚合
        pre_agg_ok = PreAggregation(
            name="full_agg",
            table_name="agg_full",
            dimensions=["product_id", "category", "date"],
            measures=["total_sales", "quantity"]
        )
        assert requirement.is_satisfiable_by(pre_agg_ok)

        # 不满足需求的预聚合（缺少维度）
        pre_agg_missing = PreAggregation(
            name="partial_agg",
            table_name="agg_partial",
            dimensions=["product_id"],
            measures=["total_sales"]
        )
        assert not requirement.is_satisfiable_by(pre_agg_missing)

    def test_satisfiable_by_granularity(self):
        """测试粒度满足检查"""
        requirement = PreAggQueryRequirement(
            dimensions=["date"],
            granularities={"date": TimeGranularity.MONTH},
            has_group_by=True
        )

        # 粒度相同，满足
        pre_agg_same = PreAggregation(
            name="monthly",
            table_name="agg_monthly",
            dimensions=["date"],
            granularities={"date": TimeGranularity.MONTH}
        )
        assert requirement.is_satisfiable_by(pre_agg_same)


class TestPreAggregationMatchResult:
    """测试匹配结果"""

    def test_no_match(self):
        """测试无匹配结果"""
        result = PreAggregationMatchResult.no_match("No pre-aggregations")
        assert not result.matched
        assert "No pre-aggregations" in result.message

    def test_matched(self):
        """测试匹配结果"""
        pre_agg = PreAggregation(name="test", table_name="test_table")
        result = PreAggregationMatchResult.matched(pre_agg, needs_rollup=False, score=100)
        assert result.matched
        assert result.pre_aggregation.name == "test"
        assert result.score == 100

    def test_hybrid(self):
        """测试混合查询结果"""
        pre_agg = PreAggregation(name="test", table_name="test_table")
        watermark = date.today() - timedelta(days=1)
        result = PreAggregationMatchResult.hybrid(
            pre_agg,
            needs_rollup=True,
            watermark=watermark,
            score=80
        )
        assert result.matched
        assert result.needs_hybrid
        assert result.needs_rollup
        assert result.watermark == watermark


class TestPreAggregationMatcher:
    """测试预聚合匹配器"""

    def test_no_pre_aggregations(self):
        """测试无预聚合配置"""
        matcher = PreAggregationMatcher()
        requirement = PreAggQueryRequirement(has_group_by=True)
        result = matcher.find_best_match(requirement, [])
        assert not result.matched
        assert "No pre-aggregations configured" in result.message

    def test_no_group_by(self):
        """测试无分组查询"""
        matcher = PreAggregationMatcher()
        requirement = PreAggQueryRequirement(has_group_by=False)
        pre_agg = PreAggregation(name="test", table_name="test_table")
        result = matcher.find_best_match(requirement, [pre_agg])
        assert not result.matched
        assert "no GROUP BY" in result.message

    def test_select_best_match(self):
        """测试选择最佳匹配"""
        matcher = PreAggregationMatcher()

        requirement = PreAggQueryRequirement(
            dimensions=["product_id"],
            measures=["total_sales"],
            has_group_by=True
        )

        # 低优先级预聚合
        pre_agg_low = PreAggregation(
            name="low_priority",
            table_name="agg_low",
            dimensions=["product_id", "category", "date"],
            measures=["total_sales"],
            priority=0
        )

        # 高优先级预聚合
        pre_agg_high = PreAggregation(
            name="high_priority",
            table_name="agg_high",
            dimensions=["product_id"],
            measures=["total_sales"],
            priority=10
        )

        result = matcher.find_best_match(requirement, [pre_agg_low, pre_agg_high])
        assert result.matched
        assert result.pre_aggregation.name == "high_priority"
        assert result.score >= 1000  # priority * 100

    def test_disabled_pre_aggregation(self):
        """测试禁用的预聚合"""
        matcher = PreAggregationMatcher()
        requirement = PreAggQueryRequirement(has_group_by=True)

        pre_agg = PreAggregation(
            name="disabled",
            table_name="agg_disabled",
            enabled=False,
            dimensions=["id"]
        )

        result = matcher.find_best_match(requirement, [pre_agg])
        assert not result.matched

    def test_hybrid_query_detection(self):
        """测试混合查询检测"""
        matcher = PreAggregationMatcher(hybrid_query_enabled=True)

        requirement = PreAggQueryRequirement(
            dimensions=["product_id"],
            has_group_by=True
        )

        # 数据过期的预聚合
        yesterday = date.today() - timedelta(days=1)
        pre_agg = PreAggregation(
            name="stale",
            table_name="agg_stale",
            dimensions=["product_id"],
            data_watermark=yesterday,
            supports_hybrid=True
        )

        result = matcher.find_best_match(requirement, [pre_agg])
        assert result.matched
        assert result.needs_hybrid
        assert result.watermark == yesterday

    def test_hybrid_query_disabled(self):
        """测试禁用混合查询"""
        matcher = PreAggregationMatcher(hybrid_query_enabled=False)

        requirement = PreAggQueryRequirement(
            dimensions=["product_id"],
            has_group_by=True
        )

        yesterday = date.today() - timedelta(days=1)
        pre_agg = PreAggregation(
            name="stale",
            table_name="agg_stale",
            dimensions=["product_id"],
            data_watermark=yesterday,
            supports_hybrid=True
        )

        result = matcher.find_best_match(requirement, [pre_agg])
        assert result.matched
        assert not result.needs_hybrid

    def test_score_calculation(self):
        """测试分数计算"""
        matcher = PreAggregationMatcher()

        requirement = PreAggQueryRequirement(
            dimensions=["product_id"],
            has_group_by=True
        )

        # 精确匹配
        pre_agg_exact = PreAggregation(
            name="exact",
            table_name="agg_exact",
            dimensions=["product_id"],
            priority=5
        )

        # 多余维度
        pre_agg_extra = PreAggregation(
            name="extra",
            table_name="agg_extra",
            dimensions=["product_id", "category", "date"],
            priority=5
        )

        result = matcher.find_best_match(requirement, [pre_agg_exact, pre_agg_extra])
        assert result.pre_aggregation.name == "exact"
        # 精确匹配分数更高