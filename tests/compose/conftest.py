"""Shared fixtures for the Compose Query test suite.

Lives at ``tests/compose/conftest.py`` so its autouse fixtures apply to
every test under ``tests/compose/``. Subpackage-specific fixtures
(e.g. M6 compilation's `svc` / `ctx`) stay in their own
``conftest.py`` files.
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose import feature_flags


@pytest.fixture(autouse=True)
def _clear_g10_override():
    """Ensure each test starts with the G10 feature flag at its
    default (env / production) state, regardless of what previous tests
    overrode. Tests that want a specific flag value call
    ``feature_flags.override_g10_enabled(True | False)`` and the
    fixture clears the override on teardown.

    Autouse so test files in this tree don't have to re-declare the
    cleanup themselves — eliminates the previous duplication across
    ``test_plan_alias_map.py`` / ``test_output_schema_lookup_api.py`` /
    ``test_schema_derivation_g10_join.py``.
    """
    yield
    feature_flags.override_g10_enabled(None)
