"""Grid Shaper for S3 Pivot.

Implements Phase 4: Transforms memory cube into Grid JSON structure.
"""

from typing import Any, Dict, List, Set, Tuple

from foggy.mcp_spi.semantic import PivotRequest


class GridShaper:
    def __init__(self, items: List[Dict[str, Any]], pivot: PivotRequest, key_map: Dict[str, str]):
        self.items = items
        self.pivot = pivot
        self.key_map = key_map

    def shape(self) -> Dict[str, Any]:
        if not self.items:
            # Empty case
            return {
                "format": "grid",
                "layout": {"metricPlacement": self.pivot.layout.metric_placement if self.pivot.layout else "columns"},
                "rowHeaders": [],
                "columnHeaders": [],
                "cells": []
            }

        metric_placement = self.pivot.layout.metric_placement if self.pivot.layout else "columns"

        row_fields = [f if isinstance(f, str) else f.field for f in self.pivot.rows]
        col_fields = [f if isinstance(f, str) else f.field for f in self.pivot.columns]
        metrics = [m if isinstance(m, str) else m.name for m in self.pivot.metrics]

        row_keys = [self.key_map.get(f, f) for f in row_fields]
        col_keys = [self.key_map.get(f, f) for f in col_fields]
        metric_keys = [self.key_map.get(m, m) for m in metrics]

        # 1. Extract ordered unique Row Headers and Col Headers
        row_headers_list = []
        col_headers_list = []
        row_meta_lookup = {}

        seen_rows = set()
        seen_cols = set()

        for row in self.items:
            r_tup = tuple(row.get(k) for k in row_keys)
            c_tup = tuple(row.get(k) for k in col_keys)

            if r_tup not in seen_rows:
                seen_rows.add(r_tup)
                row_headers_list.append(r_tup)
                row_meta_lookup[r_tup] = row.get("_sys_meta")

            if c_tup not in seen_cols:
                seen_cols.add(c_tup)
                col_headers_list.append(c_tup)

        # 2. Build explicit Header dictionaries
        final_row_headers = []
        final_col_headers = []

        if metric_placement == "rows":
            for r_tup in row_headers_list:
                for i, m in enumerate(metrics):
                    h = {}
                    for j, f in enumerate(row_fields):
                        h[f] = r_tup[j]
                    h["isSubtotal"] = bool(row_meta_lookup.get(r_tup))
                    h["metric"] = m
                    final_row_headers.append(h)

            for c_tup in col_headers_list:
                h = {}
                for j, f in enumerate(col_fields):
                    h[f] = c_tup[j]
                final_col_headers.append(h)

        else: # columns
            for r_tup in row_headers_list:
                h = {}
                for j, f in enumerate(row_fields):
                    h[f] = r_tup[j]
                h["isSubtotal"] = bool(row_meta_lookup.get(r_tup))
                final_row_headers.append(h)

            for c_tup in col_headers_list:
                for i, m in enumerate(metrics):
                    h = {}
                    for j, f in enumerate(col_fields):
                        h[f] = c_tup[j]
                    h["metric"] = m
                    final_col_headers.append(h)

        # Handle the case where there are no columns and no rows but metrics exist
        if not final_row_headers:
            if metric_placement == "rows":
                for m in metrics:
                    final_row_headers.append({"isSubtotal": False, "metric": m})
            else:
                final_row_headers.append({"isSubtotal": False})

        if not final_col_headers:
            if metric_placement == "columns":
                for m in metrics:
                    final_col_headers.append({"metric": m})
            else:
                final_col_headers.append({})

        # 3. Build lookup for metrics
        data_lookup = {}
        for row in self.items:
            r_tup = tuple(row.get(k) for k in row_keys)
            c_tup = tuple(row.get(k) for k in col_keys)
            data_lookup[(r_tup, c_tup)] = row

        # 4. Fill matrix
        cells = []
        if metric_placement == "rows":
            for r_tup in row_headers_list if row_headers_list else [()]:
                for m_key in metric_keys:
                    row_data = []
                    for c_tup in col_headers_list if col_headers_list else [()]:
                        row_dict = data_lookup.get((r_tup, c_tup), {})
                        row_data.append(row_dict.get(m_key))
                    cells.append(row_data)
        else:
            for r_tup in row_headers_list if row_headers_list else [()]:
                row_data = []
                for c_tup in col_headers_list if col_headers_list else [()]:
                    row_dict = data_lookup.get((r_tup, c_tup), {})
                    for m_key in metric_keys:
                        row_data.append(row_dict.get(m_key))
                cells.append(row_data)

        return {
            "format": "grid",
            "layout": {"metricPlacement": metric_placement},
            "rowHeaders": final_row_headers,
            "columnHeaders": final_col_headers,
            "cells": cells
        }
