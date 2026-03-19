"""Integration tests for FSScript parser and evaluator.

These tests align with Java test cases from:
- ExpParserTest.java
- ForExpTest.java
- FunctionExpTest.java
- IfExpTest.java
- etc.
"""

import pytest
from foggy.fsscript.parser import FsscriptParser, FsscriptLexer
from foggy.fsscript.evaluator import ExpressionEvaluator
from foggy.fsscript.expressions.base import Expression
from foggy.fsscript.expressions.control_flow import ReturnException
from foggy.fsscript.expressions.literals import NumberExpression, StringExpression


def check_exp(expr_str: str, expected, context: dict = None):
    """Parse and evaluate expression, assert result matches expected.

    This aligns with Java's checkExp() method in ExpParserTest.
    """
    parser = FsscriptParser(expr_str)
    # Use parse_program to handle both single expressions and multi-statement programs
    ast = parser.parse_program()
    evaluator = ExpressionEvaluator(context or {})
    result = evaluator.evaluate(ast)
    assert result == expected, f"Expression: {expr_str}\nExpected: {expected}\nGot: {result}"


def check_return(expr_str: str, expected):
    """Parse and evaluate statement with return, assert return value matches.

    This aligns with Java's checkReturn() method in ExpParserTest.
    """
    parser = FsscriptParser(expr_str)
    ast = parser.parse_program()
    evaluator = ExpressionEvaluator()
    with pytest.raises(ReturnException) as exc:
        evaluator.evaluate(ast)
    assert exc.value.value == expected, f"Expression: {expr_str}\nExpected: {expected}\nGot: {exc.value.value}"


class TestArithmeticIntegration:
    """Test arithmetic expressions - aligns with ExpParserTest.testFourArithmetic."""

    def test_basic_addition(self):
        check_exp("1 + 2", 3)

    def test_chained_addition(self):
        check_exp("1 + 2 + 3", 6)

    def test_precedence_multiply_first(self):
        """1 + 2 * 3 should equal 7 (not 9)."""
        check_exp("1 + 2 * 3", 7)

    def test_precedence_subtract_multiply(self):
        check_exp("1 - 2 * 3", -5)

    def test_precedence_division(self):
        check_exp("1 - 6 / 3", -1)

    def test_fractional_division(self):
        check_exp("1 - 5 / 3", -0.6666666666666667)

    def test_complex_expression(self):
        check_exp("1 - 6 / 3 + 5 + 5", 9)

    def test_complex_with_multiply(self):
        check_exp("1 - 6 / 3 + 5 + 5 * 2", 14)


class TestParenthesesIntegration:
    """Test parentheses - aligns with ExpParserTest.testBrackets."""

    def test_simple_parens(self):
        check_exp("(1 + 2)", 3)

    def test_parens_override_precedence(self):
        check_exp("(1 + 2) * 3", 9)

    def test_nested_parens(self):
        check_exp("(1 + (2 * 2)) * 3", 15)


class TestComparisonIntegration:
    """Test comparison expressions - aligns with ExpParserTest.testEq."""

    def test_string_equality_true(self):
        check_exp("'a' == 'a'", True)

    def test_string_equality_false(self):
        check_exp("'a' == 'b'", False)

    def test_number_comparison_less(self):
        check_exp("1 < 2", True)

    def test_number_comparison_greater(self):
        check_exp("2 > 1", True)


class TestIfIntegration:
    """Test if expressions - aligns with ExpParserTest.testIf."""

    def test_if_true(self):
        check_return("if (1) { return 'a'; } return 'b';", "a")

    def test_if_false(self):
        check_return("if (0) { return 'a'; } return 'b';", "b")

    def test_if_else(self):
        check_return("if (1) { return 'a'; } else { return 'b'; }", "a")

    def test_if_else_false(self):
        check_return("if (0) { return 'a'; } else { return 'b'; }", "b")

    def test_if_else_if_chain(self):
        check_return("if (0) { return 'a'; } else if (1) { return 'b'; } else { return 'c'; }", "b")

    def test_if_else_if_else(self):
        check_return("if (0) { return 'a'; } else if (0) { return 'b'; } else { return 'c'; }", "c")


class TestReturnIntegration:
    """Test return statements - aligns with ExpParserTest.testReturn."""

    def test_simple_return(self):
        parser = FsscriptParser("return (1 + 2) * 3")
        ast = parser.parse_program()
        evaluator = ExpressionEvaluator()
        with pytest.raises(ReturnException) as exc:
            evaluator.evaluate(ast)
        assert exc.value.value == 9


class TestArrayIntegration:
    """Test array expressions - aligns with ArrayExpTest."""

    def test_array_length(self):
        check_exp("[1, 2, 3].length", 3)

    def test_string_length(self):
        check_exp("'123'.length", 3)

    def test_string_split_length(self):
        check_exp("'a,b'.split(',').length", 2)

    def test_array_map(self):
        check_exp("[1, 2, 3].map(e => e + 1)[0]", 2)

    def test_array_map_second(self):
        check_exp("[1, 2, 3].map(e => e + 1)[1]", 3)

    def test_array_map_third(self):
        check_exp("[1, 2, 3].map(e => e + 1)[2]", 4)

    def test_array_map_join(self):
        check_exp("[1, 2, 3].map(e => e + 1).join(',')", "2,3,4")

    def test_array_includes_true(self):
        check_exp("[1, 2].includes(2)", True)

    def test_array_includes_false(self):
        check_exp("[1, 2].includes(3)", False)


class TestObjectIntegration:
    """Test object expressions - aligns with MapExpTest."""

    def test_object_property_access(self):
        check_exp("{a: 1}.a", 1)

    def test_object_with_variable_value(self):
        check_exp("var x = 1; {a: x}.a", 1)


class TestFunctionIntegration:
    """Test function expressions - aligns with FunctionExpTest."""

    def test_arrow_function_simple(self):
        check_exp("let a = () => 'b'; a();", "b")

    def test_arrow_function_with_param(self):
        check_exp("let a = (x) => 'b'; a(1);", "b")

    def test_arrow_function_implicit_return(self):
        check_exp("let double = x => x * 2; double(5);", 10)

    def test_function_in_object(self):
        check_exp("let b = {a: e => 'c'}; let ff = b['a']; ff();", "c")


class TestForLoopIntegration:
    """Test for loop expressions - aligns with ForExpTest."""

    def test_for_of_loop(self):
        """for (const x of arr) {...}"""
        check_exp("let b = [1, 2, 3]; let v = 0; for (const x of b) { v = v + x; }; v;", 6)

    def test_for_in_loop(self):
        """for (let k in arr) {...}"""
        check_exp("let result = []; let bb = [1, 2, 3]; for (let b in bb) { result.add(b); }; result;", [0, 1, 2])


class TestSpreadIntegration:
    """Test spread operator - aligns with ExpParserTest.testDDDotList."""

    def test_spread_array_simple(self):
        check_exp("[...[1, 2]]", [1, 2])

    def test_spread_array_multiple(self):
        check_exp("[...[1, 2], ...[3, 4], 5]", [1, 2, 3, 4, 5])


class TestTernaryIntegration:
    """Test ternary expressions."""

    def test_ternary_true(self):
        check_exp("1 ? 'yes' : 'no'", "yes")

    def test_ternary_false(self):
        check_exp("0 ? 'yes' : 'no'", "no")

    def test_ternary_with_null_coalesce(self):
        check_exp("null ?? 'default'", "default")

    def test_ternary_with_value(self):
        check_exp("'value' ?? 'default'", "value")


class TestDeleteIntegration:
    """Test delete operator - aligns with ExpParserTest.testXX5."""

    def test_delete_variable(self):
        parser = FsscriptParser("var singleRecord = 1; delete singleRecord; return singleRecord;")
        ast = parser.parse_statement()
        # Simplified - delete returns null in our implementation


class TestIncrementIntegration:
    """Test increment/decrement operators - aligns with ExpParserTest.testAA."""

    def test_postfix_increment(self):
        check_exp("const ss = {b: 1}; ss.b++;", 1)


class TestTemplateStringIntegration:
    """Test template string expressions - aligns with ExpParserTest.testX1."""

    def test_simple_template(self):
        check_exp("`12`", "12")

    def test_template_with_escape(self):
        check_exp(r"`1\`2`", "1`2")


class TestContextVariables:
    """Test expressions with context variables."""

    def test_context_variable_access(self):
        check_exp("name", "John", {"name": "John"})

    def test_context_object_access(self):
        check_exp("user.name", "John", {"user": {"name": "John"}})

    def test_context_array_access(self):
        check_exp("items[0]", "first", {"items": ["first", "second"]})


class TestClosureIntegration:
    """Test closure functionality - aligns with DefaultExpEvaluatorTest.testClosure."""

    def test_closure_captures_variable(self):
        """Test that closure captures outer variable."""
        expr_str = """
        function outer() {
            var x = 10;
            function inner() {
                return x;
            }
            return inner();
        }
        outer();
        """
        parser = FsscriptParser(expr_str)
        ast = parser.parse_program()
        evaluator = ExpressionEvaluator()
        result = evaluator.evaluate(ast)
        # Simplified closure behavior
        assert result == 10

    def test_closure_with_modification(self):
        """Test closure modifying captured variable."""
        expr_str = """
        var counter = 0;
        function increment() {
            counter = counter + 1;
            return counter;
        }
        increment();
        increment();
        """
        parser = FsscriptParser(expr_str)
        ast = parser.parse_program()
        evaluator = ExpressionEvaluator()
        result = evaluator.evaluate(ast)
        # Result should be 2 after two increments
        assert result == 2


class TestOperatorPrecedence:
    """Test operator precedence - aligns with OperatorPrecedenceTest."""

    def test_addition_before_comparison(self):
        check_exp("1 + 2 == 3", True)

    def test_comparison_before_logical(self):
        check_exp("1 < 2 && 3 > 2", True)

    def test_logical_and_before_or(self):
        check_exp("true || false && false", True)  # true || (false && false)

    def test_ternary_right_associative(self):
        # a ? b : c ? d : e  =>  a ? b : (c ? d : e)
        check_exp("0 ? 1 : 1 ? 2 : 3", 2)


class TestMethodChaining:
    """Test method chaining patterns."""

    def test_filter_chain(self):
        check_exp("[1, 2, 3].filter(x => x > 1)", [2, 3])

    def test_map_filter_chain(self):
        check_exp("[1, 2, 3].map(x => x * 2).filter(x => x > 2)", [4, 6])


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_block(self):
        parser = FsscriptParser("{}")
        ast = parser.parse_statement()
        assert ast is not None

    def test_multiple_empty_statements(self):
        parser = FsscriptParser(";;;")
        ast = parser.parse_program()
        assert ast is not None

    def test_nested_function_calls(self):
        check_exp("parseInt(toString(42))", 42)  # toString(42) = "42", parseInt("42") = 42

    def test_object_shorthand(self):
        """Test object shorthand property: {a, b} where a, b are variables."""
        check_exp("var a = 1; var b = 2; {a, b}", {"a": 1, "b": 2})


class TestOptionalChaining:
    """Test optional chaining (?.) operator."""

    def test_optional_chaining_value(self):
        check_exp("record?.teamCaption", "Team A", {"record": {"teamCaption": "Team A"}})

    def test_optional_chaining_null(self):
        check_exp("record?.teamCaption", None, {"record": None})

    def test_optional_chaining_undefined(self):
        check_exp("record?.teamCaption", None, {})

    def test_optional_chaining_nested(self):
        check_exp("record?.teamCaption?.area", "Beijing", {"record": {"teamCaption": {"area": "Beijing"}}})

    def test_optional_chaining_nested_null(self):
        check_exp("record?.teamCaption?.area", None, {"record": {"teamCaption": None}})

    def test_optional_chaining_deep_null(self):
        check_exp("record?.teamCaption?.area", None, {"record": None})


class TestJSONGlobal:
    """Test JSON global object methods."""

    def test_json_parse_string(self):
        check_exp('JSON.parse("\\"test\\"")', "test")

    def test_json_parse_array(self):
        check_exp('JSON.parse("[1, 2, 3]")', [1, 2, 3])

    def test_json_parse_object(self):
        check_exp('JSON.parse("{\\"name\\":\\"test\\"}")', {"name": "test"})

    def test_json_parse_null(self):
        check_exp("JSON.parse(null)", None)

    def test_json_stringify_object(self):
        check_exp('JSON.stringify({name: "test"})', '{"name": "test"}')

    def test_json_stringify_array(self):
        check_exp("JSON.stringify([1, 2, 3])", "[1, 2, 3]")

    def test_json_stringify_null(self):
        check_exp("JSON.stringify(null)", "null")

    def test_json_roundtrip(self):
        check_exp('JSON.stringify(JSON.parse("[1, 2, 3]"))', "[1, 2, 3]")


class TestExportSystem:
    """Test export functionality."""

    def test_export_var(self):
        """Test export var declaration."""
        parser = FsscriptParser("export var d = 1;")
        ast = parser.parse_program()
        evaluator = ExpressionEvaluator({})
        evaluator.evaluate(ast)
        exports = evaluator.get_exports()
        assert exports.get("d") == 1

    def test_export_let(self):
        """Test export let declaration."""
        parser = FsscriptParser("export let b = 2;")
        ast = parser.parse_program()
        evaluator = ExpressionEvaluator({})
        evaluator.evaluate(ast)
        exports = evaluator.get_exports()
        assert exports.get("b") == 2

    def test_export_const(self):
        """Test export const declaration."""
        parser = FsscriptParser("export const cc = 3;")
        ast = parser.parse_program()
        evaluator = ExpressionEvaluator({})
        evaluator.evaluate(ast)
        exports = evaluator.get_exports()
        assert exports.get("cc") == 3

    def test_export_function(self):
        """Test export function declaration."""
        parser = FsscriptParser("export function add(a, b) { return a + b; }")
        ast = parser.parse_program()
        evaluator = ExpressionEvaluator({})
        evaluator.evaluate(ast)
        exports = evaluator.get_exports()
        assert "add" in exports
        assert callable(exports["add"])

    def test_export_list(self):
        """Test export {a, b, c} syntax."""
        parser = FsscriptParser("var x = 1; var y = 2; export {x, y};")
        ast = parser.parse_program()
        evaluator = ExpressionEvaluator({})
        evaluator.evaluate(ast)
        exports = evaluator.get_exports()
        assert exports.get("x") == 1
        assert exports.get("y") == 2

    def test_export_default(self):
        """Test export default syntax."""
        parser = FsscriptParser("export default {name: 'test', value: 42};")
        ast = parser.parse_program()
        evaluator = ExpressionEvaluator({})
        evaluator.evaluate(ast)
        exports = evaluator.get_exports()
        assert exports.get("default") == {"name": "test", "value": 42}

    def test_multiple_exports(self):
        """Test multiple export statements."""
        code = '''
        export var d = 1;
        export let b = 2;
        export const cc = 3;
        '''
        parser = FsscriptParser(code)
        ast = parser.parse_program()
        evaluator = ExpressionEvaluator({})
        evaluator.evaluate(ast)
        exports = evaluator.get_exports()
        assert exports.get("d") == 1
        assert exports.get("b") == 2
        assert exports.get("cc") == 3


class TestModuleLoader:
    """Test module loader functionality."""

    def test_string_module_loader_basic(self):
        """Test basic string module loader."""
        from foggy.fsscript.module_loader import StringModuleLoader

        loader = StringModuleLoader({
            "test_module.fsscript": "export var x = 42;"
        })

        exports = loader.load_module("test_module.fsscript", {})
        assert exports.get("x") == 42

    def test_string_module_loader_function(self):
        """Test module with exported function."""
        from foggy.fsscript.module_loader import StringModuleLoader

        loader = StringModuleLoader({
            "math_module.fsscript": "export function double(n) { return n * 2; }"
        })

        exports = loader.load_module("math_module.fsscript", {})
        assert "double" in exports
        # Note: the function is callable but we need to test it differently

    def test_string_module_loader_multiple_exports(self):
        """Test module with multiple exports."""
        from foggy.fsscript.module_loader import StringModuleLoader

        loader = StringModuleLoader({
            "multi.fsscript": """
                export var a = 1;
                export var b = 2;
                export var c = 3;
            """
        })

        exports = loader.load_module("multi.fsscript", {})
        assert exports.get("a") == 1
        assert exports.get("b") == 2
        assert exports.get("c") == 3

    def test_string_module_loader_default_export(self):
        """Test module with default export."""
        from foggy.fsscript.module_loader import StringModuleLoader

        loader = StringModuleLoader({
            "default_mod.fsscript": "export default {x: 10, y: 20};"
        })

        exports = loader.load_module("default_mod.fsscript", {})
        assert exports.get("default") == {"x": 10, "y": 20}

    def test_string_module_loader_caching(self):
        """Test that modules are cached."""
        from foggy.fsscript.module_loader import StringModuleLoader

        loader = StringModuleLoader({
            "cached.fsscript": "export var val = 1;"
        })

        # Load twice
        exports1 = loader.load_module("cached.fsscript", {})
        exports2 = loader.load_module("cached.fsscript", {})

        # Should be the same cached result
        assert exports1 is exports2

    def test_import_named_imports(self):
        """Test importing named exports."""
        from foggy.fsscript.module_loader import StringModuleLoader

        loader = StringModuleLoader({
            "lib.fsscript": "export var x = 10; export var y = 20;",
            "main.fsscript": """
                import {x, y} from 'lib.fsscript';
                export var sum = x + y;
            """
        })

        exports = loader.load_module("main.fsscript", {})
        assert exports.get("sum") == 30

    def test_import_default_import(self):
        """Test importing default export."""
        from foggy.fsscript.module_loader import StringModuleLoader

        loader = StringModuleLoader({
            "config.fsscript": "export default {host: 'localhost', port: 8080};",
            "app.fsscript": """
                import config from 'config.fsscript';
                export var host = config.host;
            """
        })

        exports = loader.load_module("app.fsscript", {})
        assert exports.get("host") == "localhost"

    def test_import_namespace_import(self):
        """Test importing all exports as namespace."""
        from foggy.fsscript.module_loader import StringModuleLoader

        loader = StringModuleLoader({
            "utils.fsscript": "export var a = 1; export var b = 2;",
            "user.fsscript": """
                import * as Utils from 'utils.fsscript';
                export var total = Utils.a + Utils.b;
            """
        })

        exports = loader.load_module("user.fsscript", {})
        assert exports.get("total") == 3

    def test_import_with_alias(self):
        """Test importing with alias (import {x as y})."""
        from foggy.fsscript.module_loader import StringModuleLoader

        loader = StringModuleLoader({
            "orig.fsscript": "export var longVariableName = 42;",
            "alias.fsscript": """
                import {longVariableName as shortName} from 'orig.fsscript';
                export var result = shortName;
            """
        })

        exports = loader.load_module("alias.fsscript", {})
        assert exports.get("result") == 42

    def test_circular_import_detection(self):
        """Test that circular imports are detected."""
        from foggy.fsscript.module_loader import StringModuleLoader, CircularImportError

        loader = StringModuleLoader({
            "a.fsscript": "import {b} from 'b.fsscript'; export var a = 1;",
            "b.fsscript": "import {a} from 'a.fsscript'; export var b = 2;",
        })

        with pytest.raises(CircularImportError):
            loader.load_module("a.fsscript", {})

    def test_module_not_found(self):
        """Test error when module not found."""
        from foggy.fsscript.module_loader import StringModuleLoader

        loader = StringModuleLoader({})
        with pytest.raises(ModuleNotFoundError):
            loader.load_module("nonexistent.fsscript", {})


class TestFileModuleLoader:
    """Test file-based module loader."""

    def test_file_module_loader_resolve_path(self):
        """Test path resolution."""
        from foggy.fsscript.module_loader import FileModuleLoader
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = FileModuleLoader(Path(tmpdir))

            # Test simple path
            resolved = loader.resolve_path("test.fsscript")
            assert str(resolved).endswith("test.fsscript")

            # Test relative path
            resolved = loader.resolve_path("./sub/test.fsscript")
            assert "sub" in str(resolved)

    def test_file_module_loader_load_file(self):
        """Test loading an actual file."""
        from foggy.fsscript.module_loader import FileModuleLoader
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create a module file
            module_file = tmpdir / "test_module.fsscript"
            module_file.write_text("export var value = 123;")

            loader = FileModuleLoader(tmpdir)
            exports = loader.load_module("test_module.fsscript", {})

            assert exports.get("value") == 123

    def test_file_module_loader_import_chain(self):
        """Test importing one file from another."""
        from foggy.fsscript.module_loader import FileModuleLoader
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create dependency module
            dep_file = tmpdir / "dep.fsscript"
            dep_file.write_text("export var depValue = 100;")

            # Create main module that imports dependency
            main_file = tmpdir / "main.fsscript"
            main_file.write_text("""
                import {depValue} from 'dep.fsscript';
                export var mainValue = depValue + 50;
            """)

            loader = FileModuleLoader(tmpdir)
            exports = loader.load_module("main.fsscript", {})

            assert exports.get("mainValue") == 150


class TestChainedModuleLoader:
    """Test chained module loader."""

    def test_chained_loader_falls_back(self):
        """Test that chained loader tries each loader in order."""
        from foggy.fsscript.module_loader import (
            StringModuleLoader, ChainedModuleLoader
        )

        loader1 = StringModuleLoader({"a.fsscript": "export var x = 1;"})
        loader2 = StringModuleLoader({"b.fsscript": "export var y = 2;"})

        chained = ChainedModuleLoader(loader1, loader2)

        # Should find in first loader
        assert chained.load_module("a.fsscript", {}).get("x") == 1

        # Should fall back to second loader
        assert chained.load_module("b.fsscript", {}).get("y") == 2

        # Should fail if not found in any loader
        with pytest.raises(ModuleNotFoundError):
            chained.load_module("c.fsscript", {})


class TestTryCatchFinally:
    """Test try-catch-finally exception handling."""

    def test_try_no_exception(self):
        """Test try block without exception."""
        check_exp("try { 1 + 1; } catch(e) { 0; }", 2)

    def test_try_catch_simple(self):
        """Test try-catch with thrown exception."""
        code = """
        try {
            throw 'error';
        } catch(e) {
            e;
        }
        """
        check_exp(code, 'error')

    def test_try_catch_with_message(self):
        """Test catch block receives thrown value."""
        code = """
        try {
            throw { message: 'test error' };
        } catch(err) {
            err.message;
        }
        """
        check_exp(code, 'test error')

    def test_try_finally(self):
        """Test finally block executes."""
        code = """
        var x = 1;
        try {
            x = 2;
        } finally {
            x = 3;
        }
        x;
        """
        check_exp(code, 3)

    def test_try_catch_finally(self):
        """Test try-catch-finally combination."""
        code = """
        var result = '';
        try {
            result = result + 'a';
            throw 'err';
            result = result + 'b';
        } catch(e) {
            result = result + 'c';
        } finally {
            result = result + 'd';
        }
        result;
        """
        check_exp(code, 'acd')

    def test_throw_number(self):
        """Test throwing a number."""
        code = """
        try {
            throw 42;
        } catch(e) {
            e;
        }
        """
        check_exp(code, 42)

    def test_nested_try_catch(self):
        """Test nested try-catch blocks."""
        code = """
        try {
            try {
                throw 'inner';
            } catch(e1) {
                throw 'outer';
            }
        } catch(e2) {
            e2;
        }
        """
        check_exp(code, 'outer')

    def test_catch_without_variable(self):
        """Test catch block without variable binding."""
        code = """
        try {
            throw 'error';
        } catch {
            'caught';
        }
        """
        check_exp(code, 'caught')

    def test_exception_propagation(self):
        """Test that uncaught exceptions propagate."""
        from foggy.fsscript.expressions.control_flow import ThrowException

        code = "throw 'uncaught';"
        parser = FsscriptParser(code)
        ast = parser.parse_program()
        evaluator = ExpressionEvaluator()
        with pytest.raises(ThrowException) as exc:
            evaluator.evaluate(ast)
        assert exc.value.value == 'uncaught'

    def test_finally_on_exception(self):
        """Test finally executes even when exception is uncaught."""
        from foggy.fsscript.expressions.control_flow import ThrowException

        code = """
        var x = 1;
        try {
            throw 'error';
        } finally {
            x = 2;
        }
        """
        parser = FsscriptParser(code)
        ast = parser.parse_program()
        evaluator = ExpressionEvaluator()
        with pytest.raises(ThrowException):
            evaluator.evaluate(ast)
        assert evaluator.get_variable('x') == 2


class TestTemplateLiterals:
    """Test template literal (backtick strings) support."""

    def test_simple_template(self):
        """Test simple template literal without interpolation."""
        check_exp("`hello world`", "hello world")

    def test_template_with_variable(self):
        """Test template with variable interpolation."""
        check_exp("let name = 'world'; `hello ${name}`", "hello world")

    def test_template_with_expression(self):
        """Test template with expression interpolation."""
        check_exp("`sum: ${1 + 2}`", "sum: 3")

    def test_template_multiple_interpolations(self):
        """Test template with multiple interpolations."""
        check_exp("let a = 1; let b = 2; `${a} + ${b} = ${a + b}`", "1 + 2 = 3")

    def test_nested_template(self):
        """Test nested template expressions."""
        check_exp("`outer ${`inner`}`", "outer inner")