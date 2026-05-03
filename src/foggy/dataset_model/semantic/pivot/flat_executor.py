"""Pivot Flat Executor (Shim).

This module provides backwards compatibility for S1/S2 tests that import
`validate_and_translate_flat_pivot`. S3 moved the implementation to `executor.py`.
"""

from .executor import (
    PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON,
    validate_and_translate_pivot as validate_and_translate_flat_pivot,
)
