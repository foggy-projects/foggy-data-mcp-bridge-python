"""Smoke: ``foggy.dataset_model.engine.compose.authority`` public API stability.

The subpackage exports five symbols. If any of them disappear or rename,
downstream consumers (foggy-odoo-bridge-pro's ``OdooEmbeddedAuthorityResolver``
integration, the script runner, future REST bridges) break at import time.
Lock that surface here so drift is caught in unit tests rather than in
integration.
"""

from __future__ import annotations


def test_public_exports_present():
    import foggy.dataset_model.engine.compose.authority as authority

    # Functions / classes explicitly re-exported.
    assert hasattr(authority, "ModelInfoProvider")
    assert hasattr(authority, "NullModelInfoProvider")
    assert hasattr(authority, "collect_base_models")
    assert hasattr(authority, "resolve_authority_for_plan")
    assert hasattr(authority, "apply_field_access_to_schema")


def test_all_matches_documented_set():
    import foggy.dataset_model.engine.compose.authority as authority

    assert sorted(authority.__all__) == sorted(
        [
            "ModelInfoProvider",
            "NullModelInfoProvider",
            "collect_base_models",
            "resolve_authority_for_plan",
            "apply_field_access_to_schema",
        ]
    )


def test_model_info_provider_is_runtime_checkable_protocol():
    from foggy.dataset_model.engine.compose.authority import (
        ModelInfoProvider,
        NullModelInfoProvider,
    )

    # Null provider satisfies the Protocol structurally.
    assert isinstance(NullModelInfoProvider(), ModelInfoProvider)

    class NotAProvider:
        pass

    assert not isinstance(NotAProvider(), ModelInfoProvider)
