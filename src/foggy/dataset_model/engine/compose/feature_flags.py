"""Feature flag dispatch for Compose Query engine evolutions.

Centralises every "is this evolution enabled?" decision so feature code
never reads ``os.environ`` directly. Tests can flip flags via
:func:`override_g10_enabled` without recreating module state; the
override clears with ``override_g10_enabled(None)``.

G10 — plan-aware engine refactor
================================

Property: ``foggy.compose.g10.enabled`` — default ``False``.

Looked up from (in order):

1. Test override slot (when set non-None);
2. Environment variable ``FOGGY_COMPOSE_G10_ENABLED``;
3. Default ``False``.

When ``True``:

* :func:`derive_schema` on a ``JoinPlan`` marks overlapping columns
  ``is_ambiguous=True`` + sets ``plan_provenance`` instead of throwing
  ``JOIN_OUTPUT_COLUMN_CONFLICT``.
* :class:`OutputSchema` accepts ambiguous duplicates; ``get(name)``
  fails fast on ambiguity (callers use ``require_unique`` /
  ``get_all``).
* ``ComposePlanner`` compiles ``PlanColumnRef`` via plan-alias routing
  (PR3, follow-up).
* Compose plan-aware permission validator activates per-plan (PR4,
  follow-up).

When ``False`` (default during PR2 rollout):

* ``derive_join`` preserves the legacy ``JOIN_OUTPUT_COLUMN_CONFLICT``
  throw on column overlap.
* :class:`OutputSchema` rejects all duplicates as today.

Cross-repo invariant: mirrors Java
``foggy.dataset.db.model.engine.compose.ComposeFeatureFlags``.
"""

from __future__ import annotations

import os
from typing import Optional


G10_ENV_VAR: str = "FOGGY_COMPOSE_G10_ENABLED"
"""Environment variable name (uppercase, dotted → underscored)."""


_g10_override: Optional[bool] = None


def _parse_bool(raw: Optional[str]) -> Optional[bool]:
    if raw is None:
        return None
    s = raw.strip().lower()
    if s in ("true", "1", "yes", "on"):
        return True
    if s in ("false", "0", "no", "off", ""):
        return False
    return False  # unknown → conservative default


def g10_enabled() -> bool:
    """Return whether the G10 feature flag is enabled.

    Resolution order:

    1. Test override (when non-None);
    2. Environment variable ``FOGGY_COMPOSE_G10_ENABLED``;
    3. Default ``False``.
    """
    if _g10_override is not None:
        return _g10_override
    env = _parse_bool(os.environ.get(G10_ENV_VAR))
    return env if env is not None else False


def override_g10_enabled(value: Optional[bool]) -> None:
    """Test-only: pin the G10 flag to a specific value. Pass ``None``
    to clear the override (env-var resolution resumes).

    Always pair with ``try`` / ``finally`` (or a pytest fixture) —
    leaking an override across test classes corrupts the matrix.
    """
    global _g10_override
    _g10_override = value
