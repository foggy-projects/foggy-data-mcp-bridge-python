"""DimensionMemberLoader — caches dimension members with bidirectional lookup.

Aligned with Java DimensionMemberLoaderImpl.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemberItem:
    """A single dimension member entry."""

    id: Any
    caption: Any
    extra: Dict[str, Any] = field(default_factory=dict)


class DimensionMembers:
    """Cached dimension members with bidirectional ID<->caption mapping."""

    def __init__(self, table_name: str):
        self.table_name = table_name
        self._id_to_caption: Dict[Any, Any] = {}
        self._caption_to_id: Dict[Any, Any] = {}
        self._all_members: List[MemberItem] = []
        self._model_load_times: Dict[str, float] = {}

    def merge(self, items: List[MemberItem], model_name: str) -> None:
        """Merge new member items and update load timestamp."""
        for item in items:
            if item.id not in self._id_to_caption:
                self._id_to_caption[item.id] = item.caption
                self._caption_to_id[item.caption] = item.id
                self._all_members.append(item)
        self._model_load_times[model_name] = time.time()

    def find_id_by_caption(self, caption: Any) -> Optional[Any]:
        return self._caption_to_id.get(caption)

    def find_caption_by_id(self, id_val: Any) -> Optional[Any]:
        return self._id_to_caption.get(id_val)

    def search_by_caption(self, pattern: str, limit: int = 100) -> List[MemberItem]:
        """Search members by caption pattern.

        Supports:
            prefix%     - starts with prefix
            %suffix     - ends with suffix
            %contains%  - contains substring
            exact       - exact match (no wildcards)

        Matching is case-insensitive.
        """
        starts = pattern.startswith("%")
        ends = pattern.endswith("%")
        core = pattern.strip("%")
        core_lower = core.lower()

        results: List[MemberItem] = []
        for member in self._all_members:
            caption_str = str(member.caption).lower()
            matched = False
            if starts and ends:
                # %contains%
                matched = core_lower in caption_str
            elif starts:
                # %suffix
                matched = caption_str.endswith(core_lower)
            elif ends:
                # prefix%
                matched = caption_str.startswith(core_lower)
            else:
                # exact
                matched = caption_str == core_lower
            if matched:
                results.append(member)
                if len(results) >= limit:
                    break
        return results

    def is_expired(self, model_name: str, ttl_seconds: float = 3000) -> bool:
        """Check if cache is expired for a specific model (default 50 minutes)."""
        load_time = self._model_load_times.get(model_name)
        if load_time is None:
            return True
        return time.time() - load_time > ttl_seconds

    @property
    def size(self) -> int:
        return len(self._all_members)


class DimensionMemberLoader:
    """Loads and caches dimension members, provides caption<->id lookup.

    Cache key is table_name (not model_name) to avoid duplication
    when multiple models reference the same dimension table.
    """

    def __init__(self, cache_prefix: str = "default"):
        self._cache: Dict[str, DimensionMembers] = {}
        self._cache_prefix = cache_prefix

    def _cache_key(self, table_name: str) -> str:
        return f"{self._cache_prefix}-{table_name.upper()}"

    def get_or_create(self, table_name: str) -> DimensionMembers:
        key = self._cache_key(table_name)
        if key not in self._cache:
            self._cache[key] = DimensionMembers(table_name)
        return self._cache[key]

    def load_members(
        self, table_name: str, model_name: str, items: List[MemberItem]
    ) -> DimensionMembers:
        """Load member items into cache."""
        members = self.get_or_create(table_name)
        members.merge(items, model_name)
        return members

    def find_id_by_caption(self, table_name: str, caption: Any) -> Optional[Any]:
        key = self._cache_key(table_name)
        members = self._cache.get(key)
        return members.find_id_by_caption(caption) if members else None

    def find_caption_by_id(self, table_name: str, id_val: Any) -> Optional[Any]:
        key = self._cache_key(table_name)
        members = self._cache.get(key)
        return members.find_caption_by_id(id_val) if members else None

    def search(
        self, table_name: str, pattern: str, limit: int = 100
    ) -> List[MemberItem]:
        key = self._cache_key(table_name)
        members = self._cache.get(key)
        return members.search_by_caption(pattern, limit) if members else []

    def invalidate(self, table_name: Optional[str] = None) -> None:
        """Invalidate cache. If table_name given, invalidate only that table."""
        if table_name:
            key = self._cache_key(table_name)
            self._cache.pop(key, None)
        else:
            self._cache.clear()

    @property
    def cache_size(self) -> int:
        return len(self._cache)
