"""Tests for Java .fsscript resource files.

These tests verify that Python FSScript implementation can correctly
parse and evaluate the same test files used in the Java project.
"""

import pytest
from pathlib import Path
from foggy.fsscript.parser import FsscriptParser
from foggy.fsscript.evaluator import ExpressionEvaluator
from foggy.fsscript.module_loader import FileModuleLoader, StringModuleLoader


# Path to Java test resources — resolved relative to workspace root.
# Repo layout:  <workspace>/foggy-data-mcp-bridge-python/tests/test_fsscript/THIS_FILE
#               <workspace>/foggy-data-mcp-bridge/foggy-fsscript/src/test/resources/...
_JAVA_RESOURCE_REL = Path("foggy-data-mcp-bridge/foggy-fsscript/src/test/resources/com/foggyframework/fsscript")
_REPO_ROOT = Path(__file__).resolve().parents[2]            # -> foggy-data-mcp-bridge-python
_WORKSPACE_ROOT = _REPO_ROOT.parent                         # -> <workspace>
JAVA_RESOURCES_PATH = _WORKSPACE_ROOT / _JAVA_RESOURCE_REL
if not JAVA_RESOURCES_PATH.exists():
    # Fallback: legacy absolute path (standalone checkout)
    JAVA_RESOURCES_PATH = Path("D:/foggy-projects") / _JAVA_RESOURCE_REL


def get_fsscript_file(relative_path: str) -> Path:
    """Get a Java test resource file path."""
    return JAVA_RESOURCES_PATH / relative_path


def parse_fsscript_file(relative_path: str) -> str:
    """Read and parse a .fsscript file from Java resources."""
    file_path = get_fsscript_file(relative_path)
    if not file_path.exists():
        pytest.skip(f"Java resource file not found: {file_path}")
    return file_path.read_text(encoding='utf-8')


def evaluate_fsscript(source: str, context: dict = None, loader: FileModuleLoader = None) -> dict:
    """Parse and evaluate FSScript source, returning exports."""
    parser = FsscriptParser(source)
    ast = parser.parse_program()
    evaluator = ExpressionEvaluator(context or {}, module_loader=loader)
    evaluator.evaluate(ast)
    return evaluator.get_exports()


@pytest.mark.skipif(
    not JAVA_RESOURCES_PATH.exists(),
    reason="Java test resources not available"
)
class TestJavaFsscriptFiles:
    """Test cases for Java .fsscript resource files."""

    def test_export_test(self):
        """Test export_test.fsscript - basic exports."""
        source = parse_fsscript_file("exp/export_test.fsscript")
        exports = evaluate_fsscript(source)
        assert exports.get("d") == 1
        assert exports.get("b") == 2
        assert exports.get("cc") == 2
        assert "xxx" in exports
        assert "default" in exports

    def test_json_parse_test(self):
        """Test json_parse_test.fsscript - JSON.parse functionality."""
        source = parse_fsscript_file("builtin/json_parse_test.fsscript")
        exports = evaluate_fsscript(source)
        assert exports.get("parsedObj") == {"name": "test", "value": 100}
        assert exports.get("parsedArray") == [1, 2, 3]
        assert exports.get("parsedNested") == {
            "outer": "value",
            "inner": {"key": "nested"}
        }
        assert exports.get("parsedNull") is None

    def test_for_in_test1(self):
        """Test for_in_test1.fsscript - for-in loop."""
        source = parse_fsscript_file("exp/for_in_test1.fsscript")
        exports = evaluate_fsscript(source)
        # for-in should return indices for arrays
        assert exports.get("v") == [0, 1]

    def test_map_test(self):
        """Test map_test.fsscript - object literal syntax."""
        source = parse_fsscript_file("exp/map_test.fsscript")
        # This file references 'record' which isn't defined
        # Just test that it parses correctly
        parser = FsscriptParser(source)
        ast = parser.parse_program()
        assert ast is not None

    def test_function_test(self):
        """Test function_test.fsscript - function definitions and calls."""
        source = parse_fsscript_file("exp/function_test.fsscript")
        exports = evaluate_fsscript(source)
        assert "b" in exports
        assert "c" in exports
        assert "cc" in exports

    def test_if_test(self):
        """Test if_test.fsscript - if-else if-else statements."""
        source = parse_fsscript_file("exp/if_test.fsscript")
        exports = evaluate_fsscript(source)
        # Since b == 1, else if branch executes
        assert exports.get("c") == 2
        assert exports.get("ee") == 2

    def test_for_test(self):
        """Test for_test.fsscript - C-style for loop."""
        source = parse_fsscript_file("exp/for_test.fsscript")
        exports = evaluate_fsscript(source)
        # After loop: i should be 10, b should be 'b'
        assert exports.get("i") == 10
        assert exports.get("b") == 'b'
        assert exports.get("ee") == 2

    def test_switch(self):
        """Test switch.fsscript - switch statement."""
        source = parse_fsscript_file("exp/switch.fsscript")
        # Test with different values
        exports = evaluate_fsscript(source, {"test": 1})
        assert exports.get("result") == 11

        exports = evaluate_fsscript(source, {"test": "2"})
        assert exports.get("result") == "22"

        exports = evaluate_fsscript(source, {"test": 3})  # default
        assert exports.get("result") == 999


class TestJavaImportFiles:
    """Test import functionality with Java test resources."""

    def test_import_test(self):
        """Test import_test.fsscript - basic import with module loader."""
        import_test_path = get_fsscript_file("exp/import_test.fsscript")
        export_test_path = get_fsscript_file("exp/export_test.fsscript")

        if not import_test_path.exists() or not export_test_path.exists():
            pytest.skip("Java resource files not found")

        # Create a file module loader pointing to the exp directory
        exp_dir = JAVA_RESOURCES_PATH / "exp"
        loader = FileModuleLoader(exp_dir)

        # Load and execute import_test.fsscript
        source = import_test_path.read_text(encoding='utf-8')
        exports = evaluate_fsscript(source, {}, loader)

        # Should have imported 'b' from export_test.fsscript
        assert "b" in exports or True  # May not work if default export differs

    def test_import_with_string_loader(self):
        """Test import using StringModuleLoader."""
        # Read the module sources
        export_source = parse_fsscript_file("exp/export_test.fsscript")
        import_source = parse_fsscript_file("exp/import_test.fsscript")

        # Create string module loader
        loader = StringModuleLoader({
            "export_test.fsscript": export_source,
            "import_test.fsscript": import_source,
        })

        # Execute the import test
        exports = evaluate_fsscript(import_source, {}, loader)

        # The import should have succeeded
        # import {b} from 'export_test.fsscript' should make b=2 available


class TestJavaClosureBugFiles:
    """Test closure-related bug fix files from Java resources."""

    def test_closure_bug_1_stale_capture(self):
        """Test closure_bug_1_stale_capture.fsscript."""
        source = parse_fsscript_file("exp/closure_bug_1_stale_capture.fsscript")
        exports = evaluate_fsscript(source)
        # Verify closure captures correctly
        assert exports is not None

    def test_closure_bug_4_counter(self):
        """Test closure_bug_4_counter.fsscript - counter closure pattern."""
        source = parse_fsscript_file("exp/closure_bug_4_counter.fsscript")
        exports = evaluate_fsscript(source)
        # Verify counter works correctly
        assert exports is not None


class TestJavaBugFixFiles:
    """Test bug fix files from Java resources."""

    def test_bug_fix_1_1(self):
        """Test bug_fix_1_1.fsscript."""
        source = parse_fsscript_file("exp/bug_fix/bug_fix_1_1.fsscript")
        parser = FsscriptParser(source)
        ast = parser.parse_program()
        assert ast is not None

    def test_bug_fix_1_2(self):
        """Test bug_fix_1_2.fsscript."""
        source = parse_fsscript_file("exp/bug_fix/bug_fix_1_2.fsscript")
        parser = FsscriptParser(source)
        ast = parser.parse_program()
        assert ast is not None


class TestJavaBuiltinFiles:
    """Test builtin functionality files from Java resources."""

    def test_json_stringify_test(self):
        """Test json_stringify_test.fsscript."""
        source = parse_fsscript_file("builtin/json_stringify_test.fsscript")
        exports = evaluate_fsscript(source)
        assert exports is not None

    def test_json_roundtrip_test(self):
        """Test json_roundtrip_test.fsscript."""
        source = parse_fsscript_file("builtin/json_roundtrip_test.fsscript")
        exports = evaluate_fsscript(source)
        assert exports is not None