"""Memory Cube Processor for S3 Pivot.

Implements Phase 2: Having, TopN (Limit/OrderBy), and Crossjoin in memory.
"""

from typing import Any, Dict, List, Set, Tuple
import itertools

from foggy.mcp_spi.semantic import PivotRequest, PivotAxisField, PivotMetricFilter


class MemoryCubeProcessor:
    def __init__(self, items: List[Dict[str, Any]], pivot: PivotRequest, key_map: Dict[str, str]):
        self.items = items
        self.pivot = pivot
        self.key_map = key_map

    def process(self) -> List[Dict[str, Any]]:
        if not self.items:
            return self.items

        # 1. Apply Having
        self._apply_having()

        # 2. Apply TopN (limit and order_by)
        self._apply_topn_truncation()

        # 3. Apply Crossjoin
        if self.pivot.options and self.pivot.options.crossjoin:
            self._apply_crossjoin()

        return self.items

    def _apply_having(self):
        """Evaluate MetricFilter predicates and remove violating rows."""
        # Collect all having filters from rows and columns
        having_filters: List[PivotMetricFilter] = []
        for axis_item in list(self.pivot.rows) + list(self.pivot.columns):
            if isinstance(axis_item, PivotAxisField) and axis_item.having:
                having_filters.append(axis_item.having)

        if not having_filters:
            return

        def eval_filter(row: Dict[str, Any], f: PivotMetricFilter) -> bool:
            metric_key = self.key_map.get(f.metric, f.metric)
            val = row.get(metric_key)
            if val is None:
                # If metric is null, we can assume it fails most predicates except maybe IS NULL, but we only support basic ops
                return False

            try:
                if f.op == ">": return float(val) > float(f.value)
                elif f.op == ">=": return float(val) >= float(f.value)
                elif f.op == "<": return float(val) < float(f.value)
                elif f.op == "<=": return float(val) <= float(f.value)
                elif f.op == "=": return float(val) == float(f.value)
                elif f.op == "!=": return float(val) != float(f.value)
            except (ValueError, TypeError):
                # Fallback to string comparison if not numeric
                if f.op == "=": return str(val) == str(f.value)
                elif f.op == "!=": return str(val) != str(f.value)

            # Fail closed for unsupported operators
            return False

        surviving = []
        for row in self.items:
            passed = True
            for f in having_filters:
                if not eval_filter(row, f):
                    passed = False
                    break
            if passed:
                surviving.append(row)

        self.items = surviving

    def _apply_topn_truncation(self):
        """Apply TopN truncation based on order_by and limit."""
        # We must apply this for both rows and columns independently if they have limit.
        # Actually, TopN groups by "implicit parent axes" which means all preceding axes in the same list.

        self.items = self._apply_axis_truncation(self.pivot.rows)
        self.items = self._apply_axis_truncation(self.pivot.columns)

    def _apply_axis_truncation(self, axis_fields: List[Any]) -> List[Dict[str, Any]]:
        current_items = self.items

        parent_fields = []
        for axis_item in axis_fields:
            if isinstance(axis_item, str):
                field_name = axis_item
                limit = None
                order_by = None
            else:
                field_name = axis_item.field
                limit = axis_item.limit
                order_by = axis_item.order_by

            if limit is not None:
                # Need to group by parent_fields
                groups = {}
                for row in current_items:
                    # Construct parent key
                    group_key = tuple(row.get(self.key_map.get(pf, pf)) for pf in parent_fields)
                    if group_key not in groups:
                        groups[group_key] = []
                    groups[group_key].append(row)

                # Default order_by is the first metric if none provided
                sort_specs = order_by
                if not sort_specs and self.pivot.metrics:
                    first_metric = self.pivot.metrics[0]
                    if isinstance(first_metric, str):
                        sort_specs = [f"-{first_metric}"]
                    else:
                        sort_specs = [f"-{first_metric.name}"]
                elif not sort_specs:
                    sort_specs = []

                new_items = []
                for group_key, group_rows in groups.items():
                    # We need to sort group_rows by sort_specs.
                    # Since group_rows can have multiple rows with the same field_name (due to cross-axis cardinality),
                    # we must sort the UNIQUE members of field_name by their aggregated metrics, then filter.

                    # To do this correctly:
                    # 1. Aggregate metrics for each unique member of `field_name` within this group.
                    # 2. Sort the unique members.
                    # 3. Take Top N members.
                    # 4. Keep all rows in group_rows that have a member in the Top N.

                    member_aggregates = {}
                    field_key = self.key_map.get(field_name, field_name)

                    for row in group_rows:
                        member = row.get(field_key)
                        if member not in member_aggregates:
                            member_aggregates[member] = {}
                            # Initialize all metrics to 0
                            for m in self.pivot.metrics:
                                m_name = m if isinstance(m, str) else m.name
                                m_key = self.key_map.get(m_name, m_name)
                                member_aggregates[member][m_key] = 0.0

                        # Sum metrics for this member
                        for m in self.pivot.metrics:
                            m_name = m if isinstance(m, str) else m.name
                            m_key = self.key_map.get(m_name, m_name)
                            val = row.get(m_key)
                            if val is not None:
                                try:
                                    member_aggregates[member][m_key] += float(val)
                                except (ValueError, TypeError):
                                    pass

                    # Create a list of tuples (member, metrics_dict) for sorting
                    member_list = list(member_aggregates.items())

                    # Sort function
                    def sort_key(m_tuple):
                        member, metrics = m_tuple
                        keys = []
                        for spec in sort_specs:
                            desc = spec.startswith("-")
                            m_name = spec.lstrip("-")
                            m_key = self.key_map.get(m_name, m_name)
                            val = metrics.get(m_key, 0.0)
                            keys.append(-val if desc else val)
                        # Add member itself as secondary sort for stability
                        keys.append(str(member) if member is not None else "")
                        return tuple(keys)

                    member_list.sort(key=sort_key)

                    top_members = {m[0] for m in member_list[:limit]}

                    # Keep rows that match the top members
                    for row in group_rows:
                        if row.get(field_key) in top_members:
                            new_items.append(row)

                current_items = new_items

            # Current field becomes a parent for the next axis field
            parent_fields.append(field_name)

        return current_items

    def _apply_crossjoin(self):
        """Cartesian product of distinct row tuples and column tuples."""
        row_fields = [self.key_map.get(f if isinstance(f, str) else f.field, f if isinstance(f, str) else f.field) for f in self.pivot.rows]
        col_fields = [self.key_map.get(f if isinstance(f, str) else f.field, f if isinstance(f, str) else f.field) for f in self.pivot.columns]

        row_domain = set()
        col_domain = set()

        existing_matrix = {}

        for row in self.items:
            r_tup = tuple(row.get(f) for f in row_fields)
            c_tup = tuple(row.get(f) for f in col_fields)

            row_domain.add(r_tup)
            col_domain.add(c_tup)

            # Save original row for metrics
            existing_matrix[(r_tup, c_tup)] = row

        # If either domain is empty, we don't crossjoin (nothing to join)
        if not row_domain or not col_domain:
            return

        new_items = []
        # Maintain order if possible, though sets lose order. We could extract ordered domains, but sorting is safer.
        # Let's extract ordered domains from the original items to maintain SQL order
        ordered_row_domain = []
        seen_rows = set()
        for row in self.items:
            r_tup = tuple(row.get(f) for f in row_fields)
            if r_tup not in seen_rows:
                seen_rows.add(r_tup)
                ordered_row_domain.append(r_tup)

        ordered_col_domain = []
        seen_cols = set()
        for row in self.items:
            c_tup = tuple(row.get(f) for f in col_fields)
            if c_tup not in seen_cols:
                seen_cols.add(c_tup)
                ordered_col_domain.append(c_tup)

        # Generate cartesian product
        for r_tup in ordered_row_domain:
            for c_tup in ordered_col_domain:
                if (r_tup, c_tup) in existing_matrix:
                    new_items.append(existing_matrix[(r_tup, c_tup)])
                else:
                    # Construct empty row
                    empty_row = {}
                    for i, rf in enumerate(row_fields):
                        empty_row[rf] = r_tup[i]
                    for i, cf in enumerate(col_fields):
                        empty_row[cf] = c_tup[i]
                    # Fill metrics with None
                    for m in self.pivot.metrics:
                        m_name = m if isinstance(m, str) else m.name
                        m_key = self.key_map.get(m_name, m_name)
                        empty_row[m_key] = None
                    new_items.append(empty_row)

        self.items = new_items
