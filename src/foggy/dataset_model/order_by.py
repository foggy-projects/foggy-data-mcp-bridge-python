"""Shared orderBy shorthand normalization.

Both ``dataset.query_model`` and ``dataset.compose_script`` accept compact
orderBy strings.  Keep the parsing in one small helper so compile-time field
validation always sees the canonical field name.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class OrderBySpec:
    field: str
    direction: str


def normalize_order_by_item(item: Any) -> OrderBySpec:
    """Return canonical ``(field, direction)`` for supported orderBy shapes.

    Supported string forms:
      - ``"-field"`` -> ``field desc``
      - ``"+field"`` -> ``field asc``
      - ``"field"`` -> ``field asc``
      - ``"field desc"`` / ``"field asc"``
      - ``"field:desc"`` / ``"field:asc"``

    Supported object forms use ``field`` / ``fieldName`` / ``column`` and
    ``dir`` / ``direction`` / ``order``.
    """
    if isinstance(item, str):
        return _parse_string(item)
    if isinstance(item, dict):
        field = item.get("field") or item.get("fieldName") or item.get("column")
        direction = item.get("dir") or item.get("direction") or item.get("order")
        return _parse_field_and_direction(field, direction)

    field = (
        getattr(item, "field", None)
        or getattr(item, "field_name", None)
        or getattr(item, "column", None)
    )
    direction = (
        getattr(item, "dir", None)
        or getattr(item, "direction", None)
        or getattr(item, "order", None)
    )
    return _parse_field_and_direction(field, direction)


def normalize_order_by_dict(item: Any) -> dict[str, str]:
    spec = normalize_order_by_item(item)
    return {"field": spec.field, "dir": spec.direction}


def _parse_field_and_direction(
    field: Any,
    explicit_direction: Optional[Any],
) -> OrderBySpec:
    if not isinstance(field, str):
        raise TypeError(
            "orderBy object entries must include a string field/fieldName/column"
        )
    parsed = _parse_string(field)
    direction = _normalize_direction(explicit_direction, parsed.direction)
    return OrderBySpec(field=parsed.field, direction=direction)


def _parse_string(value: str) -> OrderBySpec:
    stripped = value.strip()
    direction = "asc"

    if stripped.startswith("-"):
        direction = "desc"
        stripped = stripped[1:].strip()
    elif stripped.startswith("+"):
        stripped = stripped[1:].strip()

    if ":" in stripped:
        field, raw_direction = stripped.split(":", 1)
        return OrderBySpec(
            field=field.strip(),
            direction=_normalize_direction(raw_direction, direction),
        )

    parts = stripped.rsplit(None, 1)
    if len(parts) == 2 and parts[1].lower() in {"asc", "desc"}:
        return OrderBySpec(field=parts[0].strip(), direction=parts[1].lower())

    return OrderBySpec(field=stripped, direction=direction)


def _normalize_direction(raw: Any, default: str = "asc") -> str:
    direction = str(raw or default).strip().lower()
    if direction not in {"asc", "desc"}:
        return default if default in {"asc", "desc"} else "asc"
    return direction
