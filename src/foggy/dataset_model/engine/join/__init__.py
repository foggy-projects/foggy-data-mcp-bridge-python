"""JoinGraph — BFS-based path finding for multi-hop table joins.

Aligned with Java engine/join/JoinGraph.java + JoinEdge.java.
Supports star schema and snowflake schema patterns.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set

__all__ = [
    "JoinType",
    "JoinEdge",
    "JoinGraph",
]


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------

class JoinType(Enum):
    """SQL join types."""
    LEFT = "LEFT JOIN"
    INNER = "INNER JOIN"
    RIGHT = "RIGHT JOIN"
    FULL = "FULL JOIN"


@dataclass(frozen=True)
class JoinEdge:
    """A directed edge in the join graph.

    Represents a relationship from *from_table* to *to_table* via a
    foreign-key / primary-key pair (or a custom ON condition).
    """

    from_table: str
    """Source table alias."""

    to_table: str
    """Target table alias."""

    to_table_name: str
    """Actual table name (used in SQL FROM clause)."""

    foreign_key: str
    """FK column on *from_table*."""

    primary_key: str
    """PK column on *to_table*."""

    join_type: JoinType = JoinType.LEFT
    """Join type (default LEFT)."""

    on_condition: Optional[str] = None
    """Custom ON condition (overrides FK/PK when set)."""

    @property
    def edge_key(self) -> str:
        """Unique key identifying this directed edge."""
        return f"{self.from_table}->{self.to_table}"


# ---------------------------------------------------------------------------
# JoinGraph
# ---------------------------------------------------------------------------

class JoinGraph:
    """Directed graph of table joins with BFS-based path finding.

    Parameters
    ----------
    root:
        Root table alias (e.g. ``"t"`` for the fact table).
    """

    def __init__(self, root: str) -> None:
        self._root = root
        self._adjacency: Dict[str, List[JoinEdge]] = defaultdict(list)
        self._edge_keys: Set[str] = set()
        self._nodes: Set[str] = {root}
        self._path_cache: Dict[FrozenSet[str], List[JoinEdge]] = {}

    # -- mutators -----------------------------------------------------------

    def add_edge(
        self,
        from_alias: str,
        to_alias: str,
        to_table_name: str,
        foreign_key: str,
        primary_key: str,
        join_type: JoinType = JoinType.LEFT,
        on_condition: Optional[str] = None,
    ) -> "JoinGraph":
        """Add a directed join edge.  Returns *self* for chaining."""
        edge = JoinEdge(
            from_table=from_alias,
            to_table=to_alias,
            to_table_name=to_table_name,
            foreign_key=foreign_key,
            primary_key=primary_key,
            join_type=join_type,
            on_condition=on_condition,
        )
        if edge.edge_key in self._edge_keys:
            return self  # duplicate — ignore

        self._edge_keys.add(edge.edge_key)
        self._adjacency[from_alias].append(edge)
        self._nodes.add(from_alias)
        self._nodes.add(to_alias)
        # Invalidate cache when topology changes
        self._path_cache.clear()
        return self

    # -- path finding -------------------------------------------------------

    def get_path(self, targets: Set[str]) -> List[JoinEdge]:
        """Return the minimal list of :class:`JoinEdge` needed to reach all
        *targets* from the root, topologically sorted.

        Raises :class:`ValueError` if any target is unreachable.
        """
        # Trivial: root-only or empty
        real_targets = targets - {self._root}
        if not real_targets:
            return []

        cache_key = frozenset(real_targets)
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]

        # BFS from root
        queue: deque[str] = deque([self._root])
        visited: Set[str] = {self._root}
        parent_edge: Dict[str, JoinEdge] = {}

        found: Set[str] = set()
        while queue and found != real_targets:
            node = queue.popleft()
            for edge in self._adjacency.get(node, []):
                if edge.to_table not in visited:
                    visited.add(edge.to_table)
                    parent_edge[edge.to_table] = edge
                    queue.append(edge.to_table)
                    if edge.to_table in real_targets:
                        found.add(edge.to_table)

        unreachable = real_targets - found
        if unreachable:
            raise ValueError(
                f"Unreachable table(s) from root '{self._root}': "
                f"{', '.join(sorted(unreachable))}"
            )

        # Backtrack to collect all needed edges
        edges: Set[JoinEdge] = set()
        for target in found:
            node = target
            while node in parent_edge:
                edge = parent_edge[node]
                edges.add(edge)
                node = edge.from_table

        # Topological sort
        result = self._topological_sort(edges)
        self._path_cache[cache_key] = result
        return result

    # -- validation ---------------------------------------------------------

    def validate(self) -> None:
        """Run DFS cycle detection.  Raises :class:`ValueError` if a cycle exists."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {n: WHITE for n in self._nodes}

        def dfs(node: str, path: List[str]) -> None:
            color[node] = GRAY
            path.append(node)
            for edge in self._adjacency.get(node, []):
                nb = edge.to_table
                if color.get(nb, WHITE) == GRAY:
                    cycle_start = path.index(nb)
                    cycle = path[cycle_start:] + [nb]
                    raise ValueError(
                        f"Cycle detected: {' -> '.join(cycle)}"
                    )
                if color.get(nb, WHITE) == WHITE:
                    dfs(nb, path)
            path.pop()
            color[node] = BLACK

        for node in self._nodes:
            if color[node] == WHITE:
                dfs(node, [])

    # -- properties ---------------------------------------------------------

    @property
    def root(self) -> str:
        return self._root

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edge_keys)

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _topological_sort(edges: Set[JoinEdge]) -> List[JoinEdge]:
        """Kahn's algorithm on the sub-graph defined by *edges*."""
        if not edges:
            return []

        # Build local adjacency and in-degree
        edge_by_key: Dict[str, JoinEdge] = {e.edge_key: e for e in edges}
        nodes: Set[str] = set()
        out_edges: Dict[str, List[JoinEdge]] = defaultdict(list)
        in_degree: Dict[str, int] = defaultdict(int)

        for e in edges:
            nodes.add(e.from_table)
            nodes.add(e.to_table)
            out_edges[e.from_table].append(e)
            in_degree.setdefault(e.from_table, 0)
            in_degree[e.to_table] = in_degree.get(e.to_table, 0) + 1

        # Seed queue with nodes that have in-degree 0
        queue: deque[str] = deque(
            sorted(n for n in nodes if in_degree.get(n, 0) == 0)
        )
        result: List[JoinEdge] = []

        while queue:
            node = queue.popleft()
            for edge in sorted(out_edges.get(node, []), key=lambda e: e.to_table):
                result.append(edge)
                in_degree[edge.to_table] -= 1
                if in_degree[edge.to_table] == 0:
                    queue.append(edge.to_table)

        return result
