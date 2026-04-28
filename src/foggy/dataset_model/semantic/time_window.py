"""TimeWindow DSL helpers aligned with the Java 8.3.0.beta contract."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from foggy.dataset_model.definitions.base import AggregationType, DimensionType
from foggy.dataset_model.impl.model import (
    DbModelMeasureImpl,
    DbTableModelImpl,
    DimensionJoinDef,
)


RELATIVE_PATTERN = re.compile(r"^([+-]?)(\d+)([YDMWQ])$", re.IGNORECASE)


class RelativeDateParser:
    """Validate relative or absolute date expressions used by timeWindow."""

    @staticmethod
    def is_valid(expr: Optional[str]) -> bool:
        if expr is None or not str(expr).strip():
            return False
        value = str(expr).strip()
        if value.lower() == "now":
            return True
        if RELATIVE_PATTERN.match(value):
            return True
        return _is_absolute_date(value)

    @staticmethod
    def resolve(expr: str, today: Optional[date] = None) -> str:
        """Resolve a supported timeWindow value into a bind parameter.

        Absolute values keep their original shape because models may use either
        ISO dates or compact date keys. Relative values are anchored to
        ``today`` and emitted as ISO dates.
        """
        value = str(expr).strip()
        anchor = today or date.today()
        if value.lower() == "now":
            return anchor.isoformat()

        match = RELATIVE_PATTERN.match(value)
        if match:
            sign_text, amount_text, unit = match.groups()
            amount = int(amount_text)
            if sign_text == "-":
                amount = -amount
            unit = unit.upper()
            if unit == "D":
                return (anchor + timedelta(days=amount)).isoformat()
            if unit == "W":
                return (anchor + timedelta(weeks=amount)).isoformat()
            if unit == "M":
                return _add_months(anchor, amount).isoformat()
            if unit == "Q":
                return _add_months(anchor, amount * 3).isoformat()
            if unit == "Y":
                return _add_months(anchor, amount * 12).isoformat()

        if _is_absolute_date(value):
            return value

        raise ValueError("TIMEWINDOW_VALUE_PARSE_FAILED")


@dataclass(frozen=True)
class TimeWindowDef:
    """Declarative time window definition from ``SemanticQueryRequest``."""

    field: str
    grain: str
    comparison: str
    range: str = "[)"
    value: Tuple[str, ...] = ()
    target_metrics: Optional[Tuple[str, ...]] = None
    rolling_aggregator: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.field or not str(self.field).strip():
            raise ValueError("timeWindow.field is required")
        if not self.grain or not str(self.grain).strip():
            raise ValueError("timeWindow.grain is required")
        if not self.comparison or not str(self.comparison).strip():
            raise ValueError("timeWindow.comparison is required")
        object.__setattr__(self, "field", str(self.field))
        object.__setattr__(self, "grain", str(self.grain))
        object.__setattr__(self, "comparison", str(self.comparison))
        object.__setattr__(self, "range", self.range or "[)")
        object.__setattr__(self, "value", tuple(str(v) for v in (self.value or ())))
        if self.target_metrics is not None:
            object.__setattr__(
                self,
                "target_metrics",
                tuple(str(v) for v in self.target_metrics),
            )

    @classmethod
    def from_map(cls, payload: Optional[Dict[str, Any]]) -> Optional["TimeWindowDef"]:
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ValueError("timeWindow must be an object")
        value = payload.get("value")
        metrics = payload.get("targetMetrics")
        return cls(
            field=payload.get("field"),
            grain=payload.get("grain"),
            comparison=payload.get("comparison"),
            range=payload.get("range") or "[)",
            value=tuple(value) if isinstance(value, list) else (),
            target_metrics=tuple(metrics) if isinstance(metrics, list) else None,
            rolling_aggregator=payload.get("rollingAggregator"),
        )

    def is_comparative(self) -> bool:
        return self.comparison in {"yoy", "mom", "wow"}

    def is_cumulative(self) -> bool:
        return self.comparison in {"ytd", "mtd"}

    def is_rolling(self) -> bool:
        return self.comparison.startswith("rolling_")

    def rolling_window_size(self) -> int:
        if not self.is_rolling():
            raise ValueError(f"Not a rolling comparison: {self.comparison}")
        return int(re.sub(r"[^0-9]", "", self.comparison))


class TimeWindowValidator:
    """Validate a ``TimeWindowDef`` against model fields and Java matrix."""

    FIELD_NOT_FOUND = "TIMEWINDOW_FIELD_NOT_FOUND"
    FIELD_NOT_TIME = "TIMEWINDOW_FIELD_NOT_TIME"
    GRAIN_INCOMPATIBLE = "TIMEWINDOW_GRAIN_INCOMPATIBLE"
    GRAIN_FIELD_NOT_FOUND = "TIMEWINDOW_GRAIN_FIELD_NOT_FOUND"
    VALUE_PARSE_FAILED = "TIMEWINDOW_VALUE_PARSE_FAILED"
    TARGET_NOT_AGGREGATE = "TIMEWINDOW_TARGET_NOT_AGGREGATE"
    RANGE_INVALID = "TIMEWINDOW_RANGE_INVALID"
    AGG_INVALID = "TIMEWINDOW_AGG_INVALID"

    VALID_GRAINS = {"day", "week", "month", "quarter", "year"}
    VALID_COMPARISONS = {
        "yoy",
        "mom",
        "wow",
        "ytd",
        "mtd",
        "rolling_7d",
        "rolling_30d",
        "rolling_90d",
    }
    VALID_RANGES = {"[)", "[]"}
    VALID_ROLLING_AGGS = {"sum", "avg", "count", "min", "max"}
    GRAIN_TO_PROPERTY = {
        "year": "year",
        "quarter": "quarter",
        "month": "month",
        "week": "week",
        "day": "id",
    }
    COMPATIBLE_GRAINS = {
        "yoy": {"week", "month", "quarter", "year"},
        "mom": {"month"},
        "wow": {"day", "week"},
        "ytd": {"day", "week", "month", "quarter"},
        "mtd": {"day"},
        "rolling_7d": {"day"},
        "rolling_30d": {"day"},
        "rolling_90d": {"day", "week"},
    }

    @classmethod
    def validate(
        cls,
        tw: TimeWindowDef,
        available_fields: Set[str],
        time_fields: Set[str],
        measure_fields: Set[str],
    ) -> Optional[str]:
        if tw.field not in available_fields:
            return cls.FIELD_NOT_FOUND
        if tw.field not in time_fields:
            return cls.FIELD_NOT_TIME
        if tw.grain not in cls.VALID_GRAINS:
            return cls.VALUE_PARSE_FAILED
        if tw.comparison not in cls.VALID_COMPARISONS:
            return cls.VALUE_PARSE_FAILED

        allowed_grains = cls.COMPATIBLE_GRAINS.get(tw.comparison)
        if allowed_grains is not None and tw.grain not in allowed_grains:
            return cls.GRAIN_INCOMPATIBLE

        if tw.is_comparative():
            grain_prop = cls.GRAIN_TO_PROPERTY.get(tw.grain)
            if grain_prop and grain_prop != "id":
                base_dim = _base_time_field(tw.field)
                expected = f"{base_dim}${grain_prop}"
                dim_prefix = f"{base_dim}$"
                has_property_fields = any(
                    f.startswith(dim_prefix)
                    and f not in {f"{base_dim}$id", f"{base_dim}$caption"}
                    for f in available_fields
                )
                if has_property_fields and expected not in available_fields:
                    return cls.GRAIN_FIELD_NOT_FOUND

        if tw.range not in cls.VALID_RANGES:
            return cls.RANGE_INVALID

        if tw.value:
            if len(tw.value) != 2:
                return cls.VALUE_PARSE_FAILED
            if any(not RelativeDateParser.is_valid(v) for v in tw.value):
                return cls.VALUE_PARSE_FAILED

        if tw.target_metrics is not None:
            for metric in tw.target_metrics:
                if metric not in measure_fields:
                    return cls.TARGET_NOT_AGGREGATE

        if (
            tw.rolling_aggregator is not None
            and tw.rolling_aggregator.lower() not in cls.VALID_ROLLING_AGGS
        ):
            return cls.AGG_INVALID

        return None


@dataclass(frozen=True)
class TimeWindowProjectedColumn:
    """Generated rolling/cumulative projection before SQL lowering."""

    metric: str
    alias: str
    agg: str
    partition_by: Tuple[str, ...]
    order_by: Tuple[str, ...]
    window_frame: str

    def to_calculated_field(self) -> Dict[str, Any]:
        """Return a CalculatedFieldDef-compatible dict."""
        return {
            "name": self.alias,
            "expression": self.metric,
            "agg": self.agg,
            "partition_by": list(self.partition_by),
            "window_order_by": [
                {"field": field, "dir": "asc"} for field in self.order_by
            ],
            "window_frame": self.window_frame,
        }


@dataclass(frozen=True)
class TimeWindowExpansionResult:
    """Intermediate expansion result aligned with Java ExpansionResult."""

    additional_columns: Tuple[TimeWindowProjectedColumn, ...]
    order_by_field: str
    partition_by_fields: Tuple[str, ...]
    window_frame: str
    description: str


class TimeWindowExpander:
    """Expand supported timeWindow modes into window projection IR."""

    @classmethod
    def expand_rolling(
        cls,
        tw: TimeWindowDef,
        group_by_fields: Iterable[str],
        measure_fields: Set[str],
    ) -> TimeWindowExpansionResult:
        if not tw.is_rolling():
            raise ValueError(f"Not a rolling time window: {tw.comparison}")

        n_rows = tw.rolling_window_size()
        frame = f"ROWS BETWEEN {n_rows - 1} PRECEDING AND CURRENT ROW"
        partition_by = tuple(_non_time_group_by_fields(tw, group_by_fields))
        agg = (tw.rolling_aggregator or "sum").upper()
        additional = tuple(
            TimeWindowProjectedColumn(
                metric=metric,
                alias=f"{metric}__{tw.comparison}",
                agg=agg,
                partition_by=partition_by,
                order_by=(tw.field,),
                window_frame=frame,
            )
            for metric in _resolve_target_metrics(tw, measure_fields)
        )
        return TimeWindowExpansionResult(
            additional_columns=additional,
            order_by_field=tw.field,
            partition_by_fields=partition_by,
            window_frame=frame,
            description=(
                f"{tw.comparison} window logic via OVER("
                f"ROWS BETWEEN {n_rows - 1} PRECEDING AND CURRENT ROW)"
            ),
        )

    @classmethod
    def expand_cumulative(
        cls,
        tw: TimeWindowDef,
        group_by_fields: Iterable[str],
        measure_fields: Set[str],
    ) -> TimeWindowExpansionResult:
        if not tw.is_cumulative():
            raise ValueError(f"Not a cumulative time window: {tw.comparison}")

        frame = "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"
        partition_by = list(_non_time_group_by_fields(tw, group_by_fields))
        base_field = _base_time_field(tw.field)
        if tw.comparison == "ytd":
            partition_by.append(f"{base_field}$year")
        elif tw.comparison == "mtd":
            partition_by.append(f"{base_field}$year")
            partition_by.append(f"{base_field}$month")

        partition_tuple = tuple(partition_by)
        agg = (tw.rolling_aggregator or "sum").upper()
        additional = tuple(
            TimeWindowProjectedColumn(
                metric=metric,
                alias=f"{metric}__{tw.comparison}",
                agg=agg,
                partition_by=partition_tuple,
                order_by=(tw.field,),
                window_frame=frame,
            )
            for metric in _resolve_target_metrics(tw, measure_fields)
        )
        return TimeWindowExpansionResult(
            additional_columns=additional,
            order_by_field=tw.field,
            partition_by_fields=partition_tuple,
            window_frame=frame,
            description=(
                f"{tw.comparison} window logic via OVER("
                "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)"
            ),
        )


def collect_time_window_field_sets(
    model: DbTableModelImpl,
) -> Tuple[Set[str], Set[str], Set[str]]:
    """Collect available/time/measure field sets for TimeWindow validation."""

    available_fields: Set[str] = set(model.columns.keys())
    time_fields: Set[str] = set()
    measure_fields = {
        name for name, measure in model.measures.items()
        if _is_aggregate_measure(measure)
    }
    available_fields.update(model.measures.keys())

    for name, dim in model.dimensions.items():
        available_fields.add(name)
        available_fields.add(f"{name}$id")
        available_fields.add(f"{name}$caption")
        if dim.is_time_dimension():
            time_fields.add(name)
            time_fields.add(f"{name}$id")

    for join in model.dimension_joins:
        _add_join_fields(join, available_fields)
        if _is_time_join(join):
            time_fields.add(f"{join.name}$id")

    return available_fields, time_fields, measure_fields


def _add_join_fields(join: DimensionJoinDef, available_fields: Set[str]) -> None:
    available_fields.add(f"{join.name}$id")
    available_fields.add(f"{join.name}$caption")
    for prop in join.properties:
        available_fields.add(f"{join.name}${prop.get_name()}")


def _is_time_join(join: DimensionJoinDef) -> bool:
    text_parts = [
        join.name or "",
        join.table_name or "",
        join.caption or "",
        join.description or "",
    ]
    text = " ".join(text_parts).lower()
    return "date" in text or "日期" in text


def _is_aggregate_measure(measure: DbModelMeasureImpl) -> bool:
    aggregation = measure.aggregation
    if aggregation is None:
        return False
    value = aggregation.value if isinstance(aggregation, AggregationType) else str(aggregation)
    return value.lower() != AggregationType.NONE.value


def _base_time_field(field: str) -> str:
    return field.rsplit("$", 1)[0] if "$" in field else field


def _non_time_group_by_fields(
    tw: TimeWindowDef,
    group_by_fields: Iterable[str],
) -> List[str]:
    base_field = _base_time_field(tw.field)
    result: List[str] = []
    for field in group_by_fields or ():
        if not isinstance(field, str):
            continue
        if field != base_field and not field.startswith(f"{base_field}$"):
            result.append(field)
    return result


def _resolve_target_metrics(tw: TimeWindowDef, measure_fields: Set[str]) -> List[str]:
    if tw.target_metrics:
        return list(tw.target_metrics)
    return sorted(measure_fields)


def _is_absolute_date(value: str) -> bool:
    for pattern in ("%Y-%m-%d", "%Y%m%d"):
        try:
            datetime.strptime(value, pattern)
            return True
        except ValueError:
            continue
    return False


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
