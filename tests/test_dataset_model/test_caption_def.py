"""
Tests for captionDef support in DimensionJoinDef and resolve_field().

Covers:
- B-02: Partner country JSONB caption embedded engine fix
- dialectFormulaDef builder callable resolution
- formulaDef builder callable resolution
- Fallback to captionColumn / primaryKey
- FSScript loading integration
"""

import pytest
from pathlib import Path

from foggy.dataset_model.impl.model import (
    DimensionJoinDef,
    DimensionPropertyDef,
    DbTableModelImpl,
    _resolve_caption_sql,
)


# ==================== _resolve_caption_sql unit tests ====================


class TestResolveCaptionSql:
    """Unit tests for _resolve_caption_sql helper."""

    def test_dialect_formula_def_postgresql(self):
        """dialectFormulaDef.postgresql.builder is called with table alias."""
        join_def = DimensionJoinDef(
            name="country",
            table_name="res_country",
            foreign_key="country_id",
            primary_key="id",
            caption_def_raw={
                "column": "name",
                "dialectFormulaDef": {
                    "postgresql": {
                        "builder": lambda alias: f"{alias}.name ->> 'en_US'",
                    },
                },
            },
        )
        result = _resolve_caption_sql(join_def, "rc")
        assert result == "rc.name ->> 'en_US'"

    def test_formula_def_universal(self):
        """formulaDef.builder (universal) is used when no dialectFormulaDef."""
        join_def = DimensionJoinDef(
            name="product",
            table_name="dim_product",
            foreign_key="product_key",
            primary_key="product_key",
            caption_def_raw={
                "column": "product_name",
                "formulaDef": {
                    "builder": lambda alias: f"COALESCE({alias}.product_name, 'Unknown')",
                },
            },
        )
        result = _resolve_caption_sql(join_def, "dp")
        assert result == "COALESCE(dp.product_name, 'Unknown')"

    def test_dialect_formula_takes_priority_over_formula(self):
        """dialectFormulaDef is preferred over formulaDef when both exist."""
        join_def = DimensionJoinDef(
            name="store",
            table_name="dim_store",
            foreign_key="store_key",
            primary_key="store_key",
            caption_def_raw={
                "column": "store_name",
                "formulaDef": {
                    "builder": lambda alias: f"UNIVERSAL({alias}.store_name)",
                },
                "dialectFormulaDef": {
                    "postgresql": {
                        "builder": lambda alias: f"{alias}.store_name || ' [PG]'",
                    },
                },
            },
        )
        result = _resolve_caption_sql(join_def, "ds")
        assert result == "ds.store_name || ' [PG]'"

    def test_caption_def_column_only(self):
        """captionDef with column only (no formula) falls through to captionColumn."""
        join_def = DimensionJoinDef(
            name="customer",
            table_name="dim_customer",
            foreign_key="customer_key",
            primary_key="customer_key",
            caption_column="customer_name",
            caption_def_raw={
                "column": "customer_name",
            },
        )
        result = _resolve_caption_sql(join_def, "dc")
        assert result == "dc.customer_name"

    def test_fallback_to_caption_column(self):
        """No caption_def_raw — falls back to caption_column."""
        join_def = DimensionJoinDef(
            name="product",
            table_name="dim_product",
            foreign_key="product_key",
            primary_key="product_key",
            caption_column="product_name",
        )
        result = _resolve_caption_sql(join_def, "dp")
        assert result == "dp.product_name"

    def test_fallback_to_primary_key(self):
        """No caption_def_raw and no caption_column — falls back to primary_key."""
        join_def = DimensionJoinDef(
            name="region",
            table_name="dim_region",
            foreign_key="region_id",
            primary_key="id",
        )
        result = _resolve_caption_sql(join_def, "dr")
        assert result == "dr.id"

    def test_none_caption_def_raw(self):
        """caption_def_raw=None is handled gracefully."""
        join_def = DimensionJoinDef(
            name="channel",
            table_name="dim_channel",
            foreign_key="channel_id",
            primary_key="id",
            caption_column="channel_name",
            caption_def_raw=None,
        )
        result = _resolve_caption_sql(join_def, "dch")
        assert result == "dch.channel_name"


# ==================== resolve_field integration ====================


class TestResolveFieldCaptionWithFormula:
    """Integration tests: resolve_field('dim$caption') uses captionDef formula."""

    def _build_model_with_caption_def(self, caption_def_raw):
        """Helper to build a minimal model with one dimension using captionDef."""
        model = DbTableModelImpl(
            name="TestModel",
            table_name="fact_test",
            source_table="fact_test",
        )
        from foggy.dataset_model.impl.model import DbModelDimensionImpl
        dim = DbModelDimensionImpl(
            name="country",
            column="country_id",
        )
        model.add_dimension(dim)

        join_def = DimensionJoinDef(
            name="country",
            table_name="res_country",
            foreign_key="country_id",
            primary_key="id",
            caption_column="name",
            caption_def_raw=caption_def_raw,
        )
        model.dimension_joins.append(join_def)
        return model

    def test_resolve_field_uses_dialect_formula(self):
        """resolve_field('country$caption') returns formula-based SQL expression."""
        model = self._build_model_with_caption_def({
            "column": "name",
            "dialectFormulaDef": {
                "postgresql": {
                    "builder": lambda alias: f"{alias}.name ->> 'en_US'",
                },
            },
        })
        result = model.resolve_field("country$caption")
        assert result is not None
        assert result["sql_expr"] == "rc.name ->> 'en_US'"
        assert result["is_measure"] is False

    def test_resolve_field_no_formula_uses_column(self):
        """resolve_field('country$caption') without formula uses caption_column."""
        model = self._build_model_with_caption_def(None)
        result = model.resolve_field("country$caption")
        assert result is not None
        assert result["sql_expr"] == "rc.name"


# ==================== FSScript loading integration ====================


class TestFsscriptCaptionDefLoading:
    """Integration test: loading FactSalesCaptionDefModel.tm preserves captionDef."""

    def test_caption_def_loaded_from_fsscript(self):
        """FactSalesCaptionDefModel.tm dimensions have caption_def_raw after loading."""
        from foggy.dataset_model.impl.loader import load_models_from_directory

        model_dir = Path(__file__).parent.parent.parent / "src" / "foggy" / "demo" / "models" / "ecommerce"
        models = load_models_from_directory(str(model_dir))

        # Find the CaptionDef model
        caption_model = None
        for m in models:
            if m.name == "FactSalesCaptionDefModel":
                caption_model = m
                break
        assert caption_model is not None, (
            f"FactSalesCaptionDefModel not found in loaded models: {[m.name for m in models]}"
        )

        # Check that dimension joins have caption_def_raw
        joins_with_formula = []
        for jd in caption_model.dimension_joins:
            if jd.caption_def_raw is not None:
                joins_with_formula.append(jd.name)

        assert len(joins_with_formula) > 0, (
            f"No dimension joins have caption_def_raw. "
            f"Joins: {[(j.name, j.caption_column) for j in caption_model.dimension_joins]}"
        )

    def test_caption_def_formula_callable_after_loading(self):
        """Loaded captionDef builder callables work correctly."""
        from foggy.dataset_model.impl.loader import load_models_from_directory

        model_dir = Path(__file__).parent.parent.parent / "src" / "foggy" / "demo" / "models" / "ecommerce"
        models = load_models_from_directory(str(model_dir))

        caption_model = None
        for m in models:
            if m.name == "FactSalesCaptionDefModel":
                caption_model = m
                break
        assert caption_model is not None

        # Find a join with dialectFormulaDef
        for jd in caption_model.dimension_joins:
            cdr = jd.caption_def_raw
            if cdr and isinstance(cdr, dict):
                dfd = cdr.get("dialectFormulaDef")
                if dfd:
                    # Verify the builder is callable and produces valid SQL
                    for dialect_name, entry in dfd.items():
                        if isinstance(entry, dict) and callable(entry.get("builder")):
                            sql = entry["builder"]("t1")
                            assert isinstance(sql, str), f"Builder for {jd.name}/{dialect_name} should return str"
                            assert "t1" in sql, f"Builder output should contain table alias: {sql}"
                            return  # Found at least one working builder

        pytest.fail("No dimension join with a callable dialectFormulaDef builder found")
