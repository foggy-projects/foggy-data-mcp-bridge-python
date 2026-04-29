"""Compose Script capability registry — v1.7 controlled extension mechanism.

Provides a fail-closed, descriptor-driven registry for business systems to
register trusted functions and object facades for Compose Script consumption.

Trust model:  Trusted Provider + Untrusted Script.
  - Providers register descriptors + handlers.  The engine validates
    descriptors, applies runtime policy, and enforces sandbox boundaries.
  - Scripts can only invoke capabilities that are registered, policy-allowed,
    and descriptor-authorized for the current surface.

Default state:  Registry empty, policy empty, visible surface unchanged.

Public API
----------
* :class:`FunctionDescriptor` / :class:`MethodDescriptor` / :class:`ObjectFacadeDescriptor`
* :class:`LibraryDescriptor`
* :class:`CapabilityRegistry`
* :class:`CapabilityPolicy`
* :class:`ControlledLibraryModuleLoader`
* :class:`SqlFragment`
* :class:`ObjectFacadeProxy`
* :class:`CapabilityError` and subclasses
"""

from __future__ import annotations

from .descriptors import (
    FunctionDescriptor,
    LibraryDescriptor,
    MethodDescriptor,
    ObjectFacadeDescriptor,
)
from .errors import (
    CapabilityError,
    CapabilityImportCycleError,
    CapabilityImportNotAllowedError,
    CapabilityInvalidDescriptorError,
    CapabilityMethodNotDeclaredError,
    CapabilityNotAllowedError,
    CapabilityNotRegisteredError,
    CapabilityReturnTypeDeniedError,
    CapabilitySideEffectDeniedError,
    CapabilitySymbolCollisionError,
    CapabilitySymbolNotDeclaredError,
    CapabilityTimeoutError,
    CapabilityUnsupportedDialectError,
)
from .facade_proxy import ObjectFacadeProxy
from .library_loader import ControlledLibraryModuleLoader
from .policy import CapabilityPolicy
from .registry import CapabilityRegistry
from .sql_fragment import SqlFragment

__all__ = [
    "CapabilityError",
    "CapabilityImportCycleError",
    "CapabilityImportNotAllowedError",
    "CapabilityInvalidDescriptorError",
    "CapabilityMethodNotDeclaredError",
    "CapabilityNotAllowedError",
    "CapabilityNotRegisteredError",
    "CapabilityPolicy",
    "CapabilityRegistry",
    "CapabilityReturnTypeDeniedError",
    "CapabilitySideEffectDeniedError",
    "CapabilitySymbolCollisionError",
    "CapabilitySymbolNotDeclaredError",
    "CapabilityTimeoutError",
    "CapabilityUnsupportedDialectError",
    "ControlledLibraryModuleLoader",
    "FunctionDescriptor",
    "LibraryDescriptor",
    "MethodDescriptor",
    "ObjectFacadeDescriptor",
    "ObjectFacadeProxy",
    "SqlFragment",
]
