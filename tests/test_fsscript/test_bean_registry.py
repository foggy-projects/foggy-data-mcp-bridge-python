"""Tests for BeanRegistry, BeanModuleLoader, typeof, and instanceof.

Covers:
- BeanRegistry registration and lookup
- BeanModuleLoader '@beanName' import resolution
- import { fn } from '@bean' end-to-end
- typeof operator (JS-compatible semantics)
- instanceof operator
"""

import pytest
from foggy.fsscript.parser import FsscriptParser
from foggy.fsscript.evaluator import ExpressionEvaluator
from foggy.fsscript.bean_registry import BeanRegistry, BeanModuleLoader
from foggy.fsscript.module_loader import ChainedModuleLoader, StringModuleLoader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _eval(source: str, context=None, bean_registry=None, module_loader=None):
    """Parse + evaluate, return exports dict."""
    parser = FsscriptParser(source)
    ast = parser.parse_program()
    evaluator = ExpressionEvaluator(
        context or {},
        module_loader=module_loader,
        bean_registry=bean_registry,
    )
    evaluator.evaluate(ast)
    return evaluator.get_exports()


def _eval_result(source: str, context=None, bean_registry=None):
    """Parse + evaluate, return last expression result."""
    parser = FsscriptParser(source)
    ast = parser.parse_program()
    evaluator = ExpressionEvaluator(context or {}, bean_registry=bean_registry)
    return evaluator.evaluate(ast)


# ===========================================================================
# BeanRegistry unit tests
# ===========================================================================
class TestBeanRegistry:
    """BeanRegistry registration and lookup."""

    def test_register_and_get(self):
        reg = BeanRegistry()
        reg.register("myBean", {"hello": "world"})
        assert reg.get("myBean") == {"hello": "world"}

    def test_has(self):
        reg = BeanRegistry()
        reg.register("a", 1)
        assert reg.has("a") is True
        assert reg.has("b") is False

    def test_get_missing_raises(self):
        reg = BeanRegistry()
        with pytest.raises(KeyError, match="Bean not found"):
            reg.get("missing")

    def test_register_all(self):
        reg = BeanRegistry()
        reg.register_all({"x": 1, "y": 2})
        assert reg.get("x") == 1
        assert reg.get("y") == 2

    def test_names(self):
        reg = BeanRegistry()
        reg.register_all({"a": 1, "b": 2, "c": 3})
        assert sorted(reg.names) == ["a", "b", "c"]

    def test_get_exports_dict_bean(self):
        reg = BeanRegistry()
        reg.register("svc", {"greet": lambda name: f"hi {name}", "version": "1.0"})
        exports = reg.get_exports("svc")
        assert exports["default"] == reg.get("svc")
        assert exports["version"] == "1.0"
        assert callable(exports["greet"])

    def test_get_exports_object_bean(self):
        class MyService:
            def compute(self, x):
                return x * 2

            @property
            def name(self):
                return "svc"

        reg = BeanRegistry()
        reg.register("svc", MyService())
        exports = reg.get_exports("svc")
        assert exports["default"] is not None
        assert callable(exports["compute"])


# ===========================================================================
# BeanModuleLoader tests
# ===========================================================================
class TestBeanModuleLoader:
    """BeanModuleLoader resolves '@beanName' paths."""

    def test_has_module_at_prefix(self):
        reg = BeanRegistry()
        reg.register("myBean", {})
        loader = BeanModuleLoader(reg)
        assert loader.has_module("@myBean") is True
        assert loader.has_module("@missing") is False
        assert loader.has_module("myBean") is False  # no @ prefix

    def test_load_module(self):
        reg = BeanRegistry()
        reg.register("calc", {"add": lambda a, b: a + b})
        loader = BeanModuleLoader(reg)
        exports = loader.load_module("@calc", {})
        assert callable(exports["add"])
        assert exports["add"](1, 2) == 3

    def test_load_module_strips_quotes(self):
        reg = BeanRegistry()
        reg.register("svc", {"x": 42})
        loader = BeanModuleLoader(reg)
        exports = loader.load_module("'@svc'", {})
        assert exports["x"] == 42


# ===========================================================================
# End-to-end: import '@beanName' in FSScript
# ===========================================================================
class TestBeanImportE2E:
    """End-to-end import '@beanName' through ExpressionEvaluator."""

    def test_named_import(self):
        """import { add } from '@calc'; export var r = add(1, 2);"""
        reg = BeanRegistry()
        reg.register("calc", {"add": lambda a, b: a + b, "PI": 3.14})
        exports = _eval(
            "import { add } from '@calc'; export var r = add(1, 2);",
            bean_registry=reg,
        )
        assert exports["r"] == 3

    def test_named_import_value(self):
        """import { PI } from '@calc'; export var r = PI;"""
        reg = BeanRegistry()
        reg.register("calc", {"PI": 3.14})
        exports = _eval(
            "import { PI } from '@calc'; export var r = PI;",
            bean_registry=reg,
        )
        assert exports["r"] == 3.14

    def test_default_import(self):
        """import calc from '@calc';"""
        reg = BeanRegistry()
        reg.register("calc", {"add": lambda a, b: a + b})
        exports = _eval(
            "import calc from '@calc'; export var r = calc;",
            bean_registry=reg,
        )
        assert isinstance(exports["r"], dict)

    def test_namespace_import(self):
        """import * as utils from '@utils';"""
        reg = BeanRegistry()
        reg.register("utils", {"double": lambda x: x * 2, "VERSION": "2.0"})
        exports = _eval(
            "import * as utils from '@utils'; export var v = utils.VERSION; export var r = utils.double(5);",
            bean_registry=reg,
        )
        assert exports["v"] == "2.0"
        assert exports["r"] == 10

    def test_bean_with_file_loader(self):
        """BeanModuleLoader + StringModuleLoader chained."""
        reg = BeanRegistry()
        reg.register("svc", {"greet": lambda: "hello"})

        str_loader = StringModuleLoader({"utils.fsscript": "export var x = 42;"})

        exports = _eval(
            "import { greet } from '@svc'; export var r = greet();",
            bean_registry=reg,
            module_loader=str_loader,
        )
        assert exports["r"] == "hello"

    def test_object_bean_method_import(self):
        """Import methods from a class instance bean."""
        class MathService:
            def double(self, x):
                return x * 2

            def triple(self, x):
                return x * 3

        reg = BeanRegistry()
        reg.register("mathSvc", MathService())
        exports = _eval(
            "import { double, triple } from '@mathSvc'; export var a = double(5); export var b = triple(3);",
            bean_registry=reg,
        )
        assert exports["a"] == 10
        assert exports["b"] == 9

    def test_aliased_import(self):
        """import { add as myAdd } from '@calc';"""
        reg = BeanRegistry()
        reg.register("calc", {"add": lambda a, b: a + b})
        exports = _eval(
            "import { add as myAdd } from '@calc'; export var r = myAdd(10, 20);",
            bean_registry=reg,
        )
        assert exports["r"] == 30


# ===========================================================================
# typeof operator
# ===========================================================================
class TestTypeofOperator:
    """typeof returns JS-compatible type strings."""

    def test_typeof_number(self):
        assert _eval_result("typeof 42") == "number"

    def test_typeof_string(self):
        assert _eval_result("typeof 'hello'") == "string"

    def test_typeof_boolean_true(self):
        assert _eval_result("typeof true") == "boolean"

    def test_typeof_boolean_false(self):
        assert _eval_result("typeof false") == "boolean"

    def test_typeof_null(self):
        assert _eval_result("typeof null") == "undefined"

    def test_typeof_undefined_var(self):
        assert _eval_result("typeof x") == "undefined"

    def test_typeof_function(self):
        exports = _eval("var fn = () => 1; export var t = typeof fn;")
        assert exports["t"] == "function"

    def test_typeof_object(self):
        assert _eval_result("typeof {a: 1}") == "object"

    def test_typeof_array(self):
        assert _eval_result("typeof [1, 2, 3]") == "object"

    def test_typeof_in_expression(self):
        """typeof can be used in comparisons."""
        exports = _eval("export var r = typeof 42 === 'number';")
        assert exports["r"] is True

    def test_typeof_in_ternary(self):
        exports = _eval("var x = 'hello'; export var r = typeof x === 'string' ? 'yes' : 'no';")
        assert exports["r"] == "yes"


# ===========================================================================
# instanceof operator
# ===========================================================================
class TestInstanceofOperator:
    """instanceof checks type membership."""

    def test_array_instanceof_array(self):
        exports = _eval("export var r = [1, 2] instanceof Array;")
        assert exports["r"] is True

    def test_object_instanceof_object(self):
        exports = _eval("export var r = {a: 1} instanceof Object;")
        assert exports["r"] is True

    def test_string_not_instanceof_array(self):
        exports = _eval("export var r = 'hello' instanceof Array;")
        assert exports["r"] is False

    def test_callable_typeof_function(self):
        """Since 'Function' conflicts with keyword, test via typeof instead."""
        exports = _eval("var fn = () => 1; export var r = typeof fn === 'function';")
        assert exports["r"] is True

    def test_number_not_instanceof_object(self):
        exports = _eval("export var r = 42 instanceof Object;")
        assert exports["r"] is False

    def test_null_not_instanceof_object(self):
        exports = _eval("export var r = null instanceof Object;")
        assert exports["r"] is False

    def test_instanceof_in_condition(self):
        """instanceof works in if conditions."""
        code = """
        var x = [1, 2, 3];
        if (x instanceof Array) {
            export var r = 'is array';
        } else {
            export var r = 'not array';
        }
        """
        exports = _eval(code)
        assert exports["r"] == "is array"

    def test_instanceof_combined_with_typeof(self):
        code = """
        var x = [1, 2];
        export var t = typeof x;
        export var i = x instanceof Array;
        """
        exports = _eval(code)
        assert exports["t"] == "object"
        assert exports["i"] is True
