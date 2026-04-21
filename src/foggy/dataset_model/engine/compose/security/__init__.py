"""Compose Query authority resolution SPI (8.2.0.beta M1).

This subpackage defines the ``AuthorityResolver`` Protocol and its data
carriers. A host (e.g. ``foggy-odoo-bridge-pro``) implements
``AuthorityResolver`` and injects it into :class:`ComposeQueryContext` so
the Compose Query pipeline can batch-resolve per-model authority bindings
before exposing any ``BaseModelPlan`` schema.

Public API:
    - :class:`AuthorityResolver`        (Protocol)
    - :class:`AuthorityRequest`
    - :class:`ModelQuery`
    - :class:`AuthorityResolution`
    - :class:`ModelBinding`
    - :class:`AuthorityResolutionError`
    - ``error_codes`` — module of frozen code strings
"""

from __future__ import annotations

from . import error_codes
from .authority_resolver import AuthorityResolver
from .exceptions import AuthorityResolutionError
from .models import (
    AuthorityRequest,
    AuthorityResolution,
    ModelBinding,
    ModelQuery,
)

__all__ = [
    "AuthorityResolver",
    "AuthorityRequest",
    "ModelQuery",
    "AuthorityResolution",
    "ModelBinding",
    "AuthorityResolutionError",
    "error_codes",
]
