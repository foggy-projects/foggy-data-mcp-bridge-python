"""Replay Java P0-8 real Pivot output snapshots against Python SQLite."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset.db.executor import SQLiteExecutor
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_pivot_output_snapshot_parity.json"
)


def _load_snapshot() -> dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        pytest.skip(
            "Java pivot output snapshot export not available yet: "
            f"{SNAPSHOT_PATH}. P0-8 keeps replay optional until the Java "
            "worktree exports real flat/grid Pivot output snapshots.",
        )
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_snapshot_schema() -> None:
    snapshot = _load_snapshot()
    assert snapshot["schemaVersion"] == 1
    assert snapshot["feature"] == "pivotOutput"
    assert snapshot["source"] == "JavaPivotOutputSnapshotTest"
    assert snapshot.get("seed", {}).get("rows")
    assert snapshot.get("cases")


def test_java_pivot_output_snapshot_replays_in_python(tmp_path) -> None:
    snapshot = _load_snapshot()
    db_path = tmp_path / "java_pivot_output_snapshot.sqlite"
    _seed_db(db_path, snapshot["seed"])
    executor = SQLiteExecutor(str(db_path))
    service = SemanticQueryService(executor=executor)
    service.register_model(create_fact_sales_model())

    try:
        for case in snapshot["cases"]:
            request_payload = case["request"]
            pivot_payload = {
                key: request_payload[key]
                for key in ("outputFormat", "rows", "columns", "metrics", "options")
                if key in request_payload
            }
            request = SemanticQueryRequest(
                pivot=pivot_payload,
                slice=request_payload.get("slice"),
            )
            response = service.query_model("FactSalesModel", request, mode="execute")
            assert response.error is None, f"{case['id']}: {response.error}"

            if case["type"] == "flat-output":
                actual = _canonical_flat(
                    response.items,
                    include_year=bool(pivot_payload["columns"]),
                    include_subcategory=_has_row_field(
                        pivot_payload,
                        "product$subCategoryName",
                    ),
                    extra_metrics=_derived_metric_names(pivot_payload),
                )
            elif case["type"] == "grid-output":
                actual = _canonical_grid(
                    response.items,
                    include_subcategory=_has_row_field(
                        pivot_payload,
                        "product$subCategoryName",
                    ),
                )
            else:
                raise AssertionError(
                    f"Unsupported pivot output case type: {case['type']!r}"
                )

            assert actual == case["javaCanonical"], case["id"]
    finally:
        service._run_async_in_sync(executor.close())


def _seed_db(db_path: Path, seed: dict[str, Any]) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE dim_date (
                date_key INTEGER PRIMARY KEY,
                full_date TEXT,
                year INTEGER
            );
            CREATE TABLE dim_product (
                product_key INTEGER PRIMARY KEY,
                product_name TEXT,
                product_id TEXT,
                category_id TEXT,
                category_name TEXT,
                sub_category_id TEXT,
                sub_category_name TEXT
            );
            CREATE TABLE fact_sales (
                date_key INTEGER,
                product_key INTEGER,
                order_status TEXT,
                sales_amount REAL
            );
            """
        )
        product_keys: dict[tuple[str, str], int] = {}
        date_keys: dict[int, int] = {}
        next_product_key = 1
        for row in seed["rows"]:
            category = row["category"]
            sub_category = row.get("subCategory") or f"{category}-Sub"
            year = int(row["year"])
            product_key = (category, sub_category)
            if product_key not in product_keys:
                product_keys[product_key] = next_product_key
                next_product_key += 1
            if year not in date_keys:
                date_keys[year] = year * 10000 + 101

        conn.executemany(
            "INSERT INTO dim_product "
            "(product_key, product_name, product_id, category_id, category_name, sub_category_id, sub_category_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    key,
                    sub_category,
                    f"P{key}",
                    f"C{key}",
                    category,
                    f"S{key}",
                    sub_category,
                )
                for (category, sub_category), key in product_keys.items()
            ],
        )
        conn.executemany(
            "INSERT INTO dim_date (date_key, full_date, year) VALUES (?, ?, ?)",
            [
                (date_key, f"{year:04d}-01-01", year)
                for year, date_key in date_keys.items()
            ],
        )
        conn.executemany(
            "INSERT INTO fact_sales (date_key, product_key, order_status, sales_amount) "
            "VALUES (?, ?, ?, ?)",
            [
                (
                    date_keys[int(row["year"])],
                    product_keys[
                        (
                            row["category"],
                            row.get("subCategory") or f"{row['category']}-Sub",
                        )
                    ],
                    seed["slice"]["value"],
                    float(row["sales"]),
                )
                for row in seed["rows"]
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _canonical_flat(
    items: list[dict[str, Any]],
    *,
    include_year: bool,
    include_subcategory: bool,
    extra_metrics: list[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        row: dict[str, Any] = {
            "category": _pick(item, "product$categoryName", "一级品类名称"),
        }
        if include_subcategory:
            row["subCategory"] = _pick(
                item,
                "product$subCategoryName",
                "二级品类名称",
            )
        if include_year:
            row["year"] = _number(_pick(item, "salesDate$year", "年"))
        row["sales"] = _number(_pick(item, "salesAmount", "销售金额"))
        for metric in extra_metrics:
            row[metric] = _number(_pick(item, metric))
        out.append(row)
    return sorted(
        out,
        key=lambda row: (
            row["category"],
            row.get("subCategory", ""),
            row.get("year", 0),
        ),
    )


def _canonical_grid(
    items: list[dict[str, Any]],
    *,
    include_subcategory: bool,
) -> list[dict[str, Any]]:
    assert len(items) == 1
    grid = items[0]
    assert grid["format"] == "grid"
    row_headers = grid["rowHeaders"]
    column_headers = grid["columnHeaders"]
    cells = grid["cells"]

    out: list[dict[str, Any]] = []
    for row_index, row_header in enumerate(row_headers):
        for column_index, column_header in enumerate(column_headers):
            row = {
                "category": _pick(
                    row_header,
                    "product$categoryName",
                    "一级品类名称",
                ),
            }
            if include_subcategory:
                row["subCategory"] = _pick(
                    row_header,
                    "product$subCategoryName",
                    "二级品类名称",
                )
            row.update(
                {
                    "year": _number(
                        _pick(column_header, "salesDate$year", "年"),
                    ),
                    "metric": _pick(column_header, "metric"),
                    "value": _number(cells[row_index][column_index]),
                },
            )
            out.append(row)
    return sorted(
        out,
        key=lambda row: (
            row["category"],
            row.get("subCategory", ""),
            row["year"],
            row["metric"],
        ),
    )


def _has_row_field(pivot_payload: dict[str, Any], field: str) -> bool:
    return field in pivot_payload.get("rows", [])


def _derived_metric_names(pivot_payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for metric in pivot_payload.get("metrics", []):
        if isinstance(metric, dict) and metric.get("type") in {
            "parentShare",
            "baselineRatio",
        }:
            names.append(metric["name"])
    return names


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    raise AssertionError(f"Missing any key {keys!r} in {row!r}")


def _number(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if float(value).is_integer():
            return int(value)
        return float(value)
    return value
