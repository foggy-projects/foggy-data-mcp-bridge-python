"""Tests for foggy.dataset_model.semantic.member_loader."""

import time

import pytest

from foggy.dataset_model.semantic.member_loader import (
    DimensionMemberLoader,
    DimensionMembers,
    MemberItem,
)


# ---------------------------------------------------------------------------
# TestMemberItem
# ---------------------------------------------------------------------------

class TestMemberItem:
    def test_create(self):
        item = MemberItem(id=1, caption="A")
        assert item.id == 1
        assert item.caption == "A"
        assert item.extra == {}

    def test_with_extra(self):
        item = MemberItem(id=2, caption="B", extra={"color": "red"})
        assert item.extra == {"color": "red"}

    def test_default_extra_independent(self):
        a = MemberItem(id=1, caption="A")
        b = MemberItem(id=2, caption="B")
        a.extra["x"] = 1
        assert "x" not in b.extra


# ---------------------------------------------------------------------------
# TestDimensionMembers
# ---------------------------------------------------------------------------

class TestDimensionMembers:
    def test_create(self):
        dm = DimensionMembers("dim_product")
        assert dm.table_name == "dim_product"
        assert dm.size == 0

    def test_merge(self):
        dm = DimensionMembers("dim_product")
        items = [MemberItem(1, "Product A"), MemberItem(2, "Product B")]
        dm.merge(items, "model1")
        assert dm.size == 2

    def test_find_id_by_caption(self):
        dm = DimensionMembers("dim_product")
        dm.merge([MemberItem(1, "Product A"), MemberItem(2, "Product B")], "m")
        assert dm.find_id_by_caption("Product A") == 1

    def test_find_caption_by_id(self):
        dm = DimensionMembers("dim_product")
        dm.merge([MemberItem(1, "Product A")], "m")
        assert dm.find_caption_by_id(1) == "Product A"

    def test_not_found(self):
        dm = DimensionMembers("dim_product")
        dm.merge([MemberItem(1, "Product A")], "m")
        assert dm.find_id_by_caption("Nonexistent") is None
        assert dm.find_caption_by_id(999) is None

    def test_search_contains(self):
        dm = DimensionMembers("dim_product")
        dm.merge([MemberItem(1, "Product A"), MemberItem(2, "Item B")], "m")
        results = dm.search_by_caption("%rod%")
        assert len(results) == 1
        assert results[0].id == 1

    def test_search_prefix(self):
        dm = DimensionMembers("dim_product")
        dm.merge([MemberItem(1, "Product A"), MemberItem(2, "Promo B")], "m")
        results = dm.search_by_caption("Pro%")
        assert len(results) == 2

    def test_search_suffix(self):
        dm = DimensionMembers("dim_product")
        dm.merge([MemberItem(1, "Product A"), MemberItem(2, "Product B")], "m")
        results = dm.search_by_caption("%ct A")
        assert len(results) == 1
        assert results[0].caption == "Product A"

    def test_search_exact(self):
        dm = DimensionMembers("dim_product")
        dm.merge([MemberItem(1, "Product A"), MemberItem(2, "Product AB")], "m")
        results = dm.search_by_caption("Product A")
        assert len(results) == 1
        assert results[0].id == 1

    def test_search_limit(self):
        dm = DimensionMembers("dim_product")
        items = [MemberItem(i, f"Product {i}") for i in range(10)]
        dm.merge(items, "m")
        results = dm.search_by_caption("%Product%", limit=2)
        assert len(results) == 2

    def test_search_case_insensitive(self):
        dm = DimensionMembers("dim_product")
        dm.merge([MemberItem(1, "Product A")], "m")
        results = dm.search_by_caption("%product%")
        assert len(results) == 1

    def test_is_expired_new(self):
        dm = DimensionMembers("dim_product")
        dm.merge([MemberItem(1, "A")], "m")
        assert dm.is_expired("m") is False

    def test_is_expired_old(self):
        dm = DimensionMembers("dim_product")
        dm.merge([MemberItem(1, "A")], "m")
        # Manually set the load time to 60 minutes ago
        dm._model_load_times["m"] = time.time() - 3600
        assert dm.is_expired("m", ttl_seconds=3000) is True

    def test_is_expired_unknown_model(self):
        dm = DimensionMembers("dim_product")
        assert dm.is_expired("unknown_model") is True

    def test_merge_dedup(self):
        dm = DimensionMembers("dim_product")
        dm.merge([MemberItem(1, "A"), MemberItem(1, "A-dup")], "m")
        assert dm.size == 1
        assert dm.find_caption_by_id(1) == "A"

    def test_model_load_time(self):
        dm = DimensionMembers("dim_product")
        before = time.time()
        dm.merge([MemberItem(1, "A")], "model_x")
        after = time.time()
        assert before <= dm._model_load_times["model_x"] <= after

    def test_merge_multiple_models(self):
        dm = DimensionMembers("dim_product")
        dm.merge([MemberItem(1, "A")], "model1")
        dm.merge([MemberItem(2, "B")], "model2")
        assert dm.size == 2
        assert "model1" in dm._model_load_times
        assert "model2" in dm._model_load_times


# ---------------------------------------------------------------------------
# TestDimensionMemberLoader
# ---------------------------------------------------------------------------

class TestDimensionMemberLoader:
    def test_create(self):
        loader = DimensionMemberLoader()
        assert loader.cache_size == 0

    def test_load_and_find(self):
        loader = DimensionMemberLoader()
        items = [MemberItem(1, "Product A"), MemberItem(2, "Product B")]
        loader.load_members("dim_product", "model1", items)
        assert loader.find_id_by_caption("dim_product", "Product A") == 1
        assert loader.find_caption_by_id("dim_product", 2) == "Product B"

    def test_cache_key(self):
        loader = DimensionMemberLoader(cache_prefix="test")
        key = loader._cache_key("dim_product")
        assert key == "test-DIM_PRODUCT"

    def test_cross_model_cache(self):
        loader = DimensionMemberLoader()
        loader.load_members("dim_product", "model1", [MemberItem(1, "A")])
        loader.load_members("dim_product", "model2", [MemberItem(2, "B")])
        assert loader.cache_size == 1
        members = loader.get_or_create("dim_product")
        assert members.size == 2

    def test_invalidate_single(self):
        loader = DimensionMemberLoader()
        loader.load_members("dim_product", "m", [MemberItem(1, "A")])
        loader.load_members("dim_customer", "m", [MemberItem(2, "B")])
        assert loader.cache_size == 2
        loader.invalidate("dim_product")
        assert loader.cache_size == 1
        assert loader.find_id_by_caption("dim_product", "A") is None
        assert loader.find_id_by_caption("dim_customer", "B") == 2

    def test_invalidate_all(self):
        loader = DimensionMemberLoader()
        loader.load_members("dim_product", "m", [MemberItem(1, "A")])
        loader.load_members("dim_customer", "m", [MemberItem(2, "B")])
        loader.invalidate()
        assert loader.cache_size == 0

    def test_cache_size(self):
        loader = DimensionMemberLoader()
        loader.load_members("t1", "m", [MemberItem(1, "A")])
        loader.load_members("t2", "m", [MemberItem(2, "B")])
        loader.load_members("t3", "m", [MemberItem(3, "C")])
        assert loader.cache_size == 3

    def test_search(self):
        loader = DimensionMemberLoader()
        items = [MemberItem(1, "Product A"), MemberItem(2, "Product B")]
        loader.load_members("dim_product", "m", items)
        results = loader.search("dim_product", "%Product%")
        assert len(results) == 2

    def test_search_empty(self):
        loader = DimensionMemberLoader()
        results = loader.search("dim_product", "%anything%")
        assert results == []

    def test_custom_prefix(self):
        loader = DimensionMemberLoader(cache_prefix="tenant-1")
        key = loader._cache_key("dim_product")
        assert key == "tenant-1-DIM_PRODUCT"

    def test_find_on_empty(self):
        loader = DimensionMemberLoader()
        assert loader.find_id_by_caption("dim_product", "A") is None
        assert loader.find_caption_by_id("dim_product", 1) is None

    def test_get_or_create(self):
        loader = DimensionMemberLoader()
        members = loader.get_or_create("dim_product")
        assert isinstance(members, DimensionMembers)
        assert members.table_name == "dim_product"
        # Same instance returned on second call
        assert loader.get_or_create("dim_product") is members
