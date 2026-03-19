"""Pytest configuration for FSScript tests."""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture
def evaluator():
    """Create a fresh ExpressionEvaluator for each test."""
    from foggy.fsscript.evaluator import ExpressionEvaluator
    return ExpressionEvaluator()


@pytest.fixture
def empty_context():
    """Create an empty evaluation context."""
    return {}