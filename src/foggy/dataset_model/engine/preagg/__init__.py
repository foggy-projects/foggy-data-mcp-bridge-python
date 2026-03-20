"""
PreAggregation Engine - 预聚合引擎
"""

from foggy.dataset_model.engine.preagg.matcher import (
    TimeGranularity,
    PreAggregation,
    PreAggQueryRequirement,
    PreAggregationMatchResult,
    PreAggregationMatcher
)
from foggy.dataset_model.engine.preagg.interceptor import (
    PreAggRewriteResult,
    PreAggQueryRequirementBuilder,
    PreAggQueryRewriter,
    PreAggAggregateSqlResult,
    PreAggregationInterceptor,
)

__all__ = [
    # Matcher
    "TimeGranularity",
    "PreAggregation",
    "PreAggQueryRequirement",
    "PreAggregationMatchResult",
    "PreAggregationMatcher",
    # Interceptor
    "PreAggRewriteResult",
    "PreAggQueryRequirementBuilder",
    "PreAggQueryRewriter",
    "PreAggAggregateSqlResult",
    "PreAggregationInterceptor",
]
