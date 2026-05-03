from foggy.dataset_model.semantic.pivot.cascade_totals import append_cascade_totals
from foggy.mcp_spi import PivotRequest


def test_append_row_subtotals_and_grand_total_over_surviving_domain():
    pivot = PivotRequest(**{
        "outputFormat": "flat",
        "rows": [
            {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
            {"field": "product$subCategoryId", "limit": 1, "orderBy": ["-salesAmount"]},
        ],
        "metrics": ["salesAmount"],
        "options": {"rowSubtotals": True, "grandTotal": True},
    })
    items = [
        {"category": "A", "sub": 1, "sales": 90.0},
        {"category": "B", "sub": 3, "sales": 40.0},
    ]
    key_map = {
        "product$categoryName": "category",
        "product$subCategoryId": "sub",
        "salesAmount": "sales",
    }

    result = append_cascade_totals(items, pivot, key_map)

    subtotals = [r for r in result if r.get("_sys_meta", {}).get("isRowSubtotal")]
    assert subtotals == [
        {"category": "A", "sub": "ALL", "sales": 90.0, "_sys_meta": {"isRowSubtotal": True}},
        {"category": "B", "sub": "ALL", "sales": 40.0, "_sys_meta": {"isRowSubtotal": True}},
    ]

    grand = [r for r in result if r.get("_sys_meta", {}).get("isGrandTotal")]
    assert grand == [
        {"category": "ALL", "sub": "ALL", "sales": 130.0, "_sys_meta": {"isGrandTotal": True}},
    ]


def test_grand_total_keeps_column_domain():
    pivot = PivotRequest(**{
        "outputFormat": "grid",
        "rows": [
            {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
            {"field": "product$subCategoryId", "limit": 1, "orderBy": ["-salesAmount"]},
        ],
        "columns": ["salesDate$year"],
        "metrics": ["salesAmount"],
        "options": {"grandTotal": True},
    })
    items = [
        {"category": "A", "sub": 1, "year": 2024, "sales": 90.0},
        {"category": "B", "sub": 3, "year": 2023, "sales": 40.0},
        {"category": "B", "sub": 3, "year": 2024, "sales": 10.0},
    ]
    key_map = {
        "product$categoryName": "category",
        "product$subCategoryId": "sub",
        "salesDate$year": "year",
        "salesAmount": "sales",
    }

    result = append_cascade_totals(items, pivot, key_map)

    grand = [r for r in result if r.get("_sys_meta", {}).get("isGrandTotal")]
    assert grand == [
        {"category": "ALL", "sub": "ALL", "year": 2024, "sales": 100.0, "_sys_meta": {"isGrandTotal": True}},
        {"category": "ALL", "sub": "ALL", "year": 2023, "sales": 40.0, "_sys_meta": {"isGrandTotal": True}},
    ]


def test_empty_surviving_domain_grand_total_is_null_metric_row():
    pivot = PivotRequest(**{
        "outputFormat": "flat",
        "rows": [
            {"field": "product$categoryName", "limit": 2, "orderBy": ["-salesAmount"]},
            {"field": "product$subCategoryId", "limit": 1, "orderBy": ["-salesAmount"]},
        ],
        "metrics": ["salesAmount"],
        "options": {"rowSubtotals": True, "grandTotal": True},
    })
    key_map = {
        "product$categoryName": "category",
        "product$subCategoryId": "sub",
        "salesAmount": "sales",
    }

    result = append_cascade_totals([], pivot, key_map)

    assert result == [
        {"category": "ALL", "sub": "ALL", "sales": None, "_sys_meta": {"isGrandTotal": True}},
    ]
