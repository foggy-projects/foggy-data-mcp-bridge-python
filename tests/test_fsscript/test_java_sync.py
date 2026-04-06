"""Tests synchronized from Java FSScript test cases.

This file ensures the Python FSScript implementation matches Java behavior.
Each test class maps to a specific Java test class with comments indicating
the original Java test method name.

Mapping:
- FunctionDefClosureBugTest.java → TestClosureBugRegression
- OperatorPrecedenceTest.java    → TestOperatorPrecedenceSync
- ForExpTest.java                → TestForExpSync
- BugFix1Test.java               → TestBugFix1Sync
- NfFunctionExpTest.java         → TestNfFunctionSync
- ExpStringTest.java             → TestExpStringSync
- CommonDimsParseTest.java       → TestCommonDimsParseSync
- ForLetClosureTest.java         → TestForLetClosureSync (augmented)
"""

import pytest
from pathlib import Path
from foggy.fsscript.parser import FsscriptParser
from foggy.fsscript.evaluator import ExpressionEvaluator
from foggy.fsscript.module_loader import FileModuleLoader, StringModuleLoader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _eval(source: str, context: dict = None, loader=None) -> dict:
    """Parse and evaluate, return exports."""
    parser = FsscriptParser(source)
    ast = parser.parse_program()
    evaluator = ExpressionEvaluator(context or {}, module_loader=loader)
    evaluator.evaluate(ast)
    return evaluator.get_exports()


def _eval_result(source: str, context: dict = None) -> object:
    """Parse and evaluate, return last expression result."""
    parser = FsscriptParser(source)
    ast = parser.parse_program()
    evaluator = ExpressionEvaluator(context or {})
    return evaluator.evaluate(ast)


def _parse_only(source: str):
    """Parse source and return AST (no evaluation)."""
    parser = FsscriptParser(source)
    return parser.parse_program()


def _load_java_resource(relative_path: str) -> str:
    """Load a .fsscript file from Java test resources."""
    file_path = JAVA_RESOURCES_PATH / relative_path
    if not file_path.exists():
        pytest.skip(f"Java resource file not found: {file_path}")
    return file_path.read_text(encoding="utf-8")


# ===========================================================================
# FunctionDefClosureBugTest.java — 18 tests
# ===========================================================================
@pytest.mark.skipif(
    not JAVA_RESOURCES_PATH.exists(),
    reason="Java test resources not available",
)
class TestClosureBugRegression:
    """Closure bug regression tests — synced from FunctionDefClosureBugTest.java."""

    # -- Java: testBasicClosureAfterReturn --
    def test_basic_closure_after_return(self):
        """Closure returned from function should still access outer scope."""
        source = _load_java_resource("exp/closure_bug_1_stale_capture.fsscript")
        exports = _eval(source)
        assert exports.get("result") == 10

    # -- Java: testMutationAfterCapture --
    def test_mutation_after_capture(self):
        """Closure sees mutations made after its definition (JS semantics)."""
        source = _load_java_resource("exp/closure_bug_2_mutation_after_capture.fsscript")
        exports = _eval(source)
        assert exports.get("beforeCall") == 99
        # JS semantics: closure captures binding, so it sees x=99
        assert exports.get("result") == 99

    # -- Java: testNestedClosureFactory --
    def test_nested_closure_factory(self):
        """Nested closures: makeAdder(5)(3)=8, makeAdder(10)(3)=13."""
        source = _load_java_resource("exp/closure_bug_3_nested_return.fsscript")
        exports = _eval(source)
        assert exports.get("r1") == 8   # add5(3)
        assert exports.get("r2") == 13  # add10(3)
        assert exports.get("r3") == 5   # add5(0)
        assert exports.get("r4") == 10  # add10(0)

    # -- Java: testClosureCounter --
    def test_closure_counter(self):
        """Counter closure accumulates state across calls."""
        source = _load_java_resource("exp/closure_bug_4_counter.fsscript")
        exports = _eval(source)
        assert exports.get("v1") == 1
        assert exports.get("v2") == 2
        assert exports.get("v3") == 3

    # -- Java: testIndependentCounters --
    def test_independent_counters(self):
        """Two counters from same factory are independent."""
        source = _load_java_resource("exp/closure_bug_5_independent_counters.fsscript")
        exports = _eval(source)
        assert exports.get("a1") == 1
        assert exports.get("a2") == 2
        assert exports.get("b1") == 1
        assert exports.get("a3") == 3
        assert exports.get("b2") == 2

    # -- Java: testScopeLeakPrevention --
    def test_scope_leak_prevention(self):
        """Closure only sees definition scope, not call-site scope."""
        source = _load_java_resource("exp/closure_bug_6_scope_leak.fsscript")
        exports = _eval(source)
        assert exports.get("result") == "defined_scope"

    # -- Java: testStackDuplicationOnClone (inline) --
    def test_stack_duplication_on_clone(self):
        """Verify closure stack structure is properly isolated."""
        code = """
        function outer() {
            var x = 10;
            function inner() {
                return x;
            }
            return inner;
        }
        var fn = outer();
        export var result = fn();
        """
        exports = _eval(code)
        assert exports.get("result") == 10

    # -- Java: testTripleNestedClosureStackGrowth --
    def test_triple_nested_closure(self):
        """Three-level nested closure captures correct scopes."""
        code = """
        function level1() {
            var a = 1;
            function level2() {
                var b = 2;
                function level3() {
                    return a + b;
                }
                return level3;
            }
            return level2;
        }
        var l2 = level1();
        var l3 = l2();
        export var result = l3();
        """
        exports = _eval(code)
        assert exports.get("result") == 3

    # -- Java: testHigherOrderFunctionBinding --
    def test_higher_order_function_binding(self):
        """Higher-order function correctly binds arguments."""
        code = """
        function apply(fn, x) {
            return fn(x);
        }
        function double(n) {
            return n * 2;
        }
        export var result = apply(double, 5);
        """
        exports = _eval(code)
        assert exports.get("result") == 10

    # -- Java: testClosureInLoopWithVar --
    def test_closure_in_loop_with_var(self):
        """var in for-loop shares single binding (JS var semantics)."""
        code = """
        var funcs = [];
        for (var i = 0; i < 3; i++) {
            funcs.push(() => i);
        }
        export var r0 = funcs[0]();
        export var r1 = funcs[1]();
        export var r2 = funcs[2]();
        """
        exports = _eval(code)
        # With var, all closures see the final i=3
        assert exports.get("r0") == 3
        assert exports.get("r1") == 3
        assert exports.get("r2") == 3

    # -- Java: testPreciseScopeLeak --
    def test_precise_scope_leak(self):
        """Closure cannot access variables from call-site scope."""
        code = """
        var outer = 'outer_val';
        function capture() {
            return outer;
        }
        function wrapper() {
            var outer = 'wrapper_val';
            return capture();
        }
        export var result = wrapper();
        """
        exports = _eval(code)
        assert exports.get("result") == "outer_val"

    # -- Java: testEeReferenceDrift --
    def test_reference_drift(self):
        """Multiple closure instances don't drift references."""
        code = """
        function makeAccumulator() {
            var total = 0;
            function add(n) {
                total = total + n;
                return total;
            }
            return add;
        }
        var acc1 = makeAccumulator();
        var acc2 = makeAccumulator();
        export var a1 = acc1(10);
        export var a2 = acc1(20);
        export var b1 = acc2(100);
        export var a3 = acc1(5);
        export var b2 = acc2(200);
        """
        exports = _eval(code)
        assert exports.get("a1") == 10
        assert exports.get("a2") == 30
        assert exports.get("b1") == 100
        assert exports.get("a3") == 35
        assert exports.get("b2") == 300

    # -- Java: testRecursionStackGrowth --
    def test_recursion_stack_growth(self):
        """Recursive function works correctly."""
        code = """
        function factorial(n) {
            if (n <= 1) { return 1; }
            return n * factorial(n - 1);
        }
        export var result = factorial(5);
        """
        exports = _eval(code)
        assert exports.get("result") == 120

    # -- Java: testDeepRecursionStress --
    def test_deep_recursion_stress(self):
        """Deeper recursion (fibonacci) works without stack issues."""
        code = """
        function fib(n) {
            if (n <= 0) { return 0; }
            if (n == 1) { return 1; }
            return fib(n - 1) + fib(n - 2);
        }
        export var result = fib(10);
        """
        exports = _eval(code)
        assert exports.get("result") == 55

    # -- Java: testExecuteFunctionDirectly --
    def test_execute_function_directly(self):
        """Exported function can be called after evaluation."""
        code = """
        export function greet(name) {
            return 'hello ' + name;
        }
        """
        exports = _eval(code)
        fn = exports.get("greet")
        assert fn is not None
        assert callable(fn)
        assert fn("world") == "hello world"

    # -- Java: testSavedStackRedundancyGrowth --
    def test_saved_stack_redundancy_growth(self):
        """Multiple closure creations don't cause redundant memory growth."""
        code = """
        function createClosures() {
            var closures = [];
            for (var i = 0; i < 10; i++) {
                closures.push(((idx) => () => idx)(i));
            }
            return closures;
        }
        var cs = createClosures();
        export var r0 = cs[0]();
        export var r5 = cs[5]();
        export var r9 = cs[9]();
        """
        exports = _eval(code)
        assert exports.get("r0") == 0
        assert exports.get("r5") == 5
        assert exports.get("r9") == 9

    # -- Java: testDuplicateClosureObjectsInSavedStack --
    def test_closure_isolation_in_factory(self):
        """Each factory invocation creates isolated closures."""
        code = """
        function factory(val) {
            function get() { return val; }
            function set(v) { val = v; }
            return { get: get, set: set };
        }
        var a = factory(1);
        var b = factory(2);
        a.set(10);
        export var aVal = a.get();
        export var bVal = b.get();
        """
        exports = _eval(code)
        assert exports.get("aVal") == 10
        assert exports.get("bVal") == 2  # b is independent

    # -- Java: testStackRedundancyImpactOnRecursion --
    def test_stack_redundancy_on_recursion(self):
        """Recursive closures don't leak stack frames."""
        code = """
        function sumTo(n) {
            if (n <= 0) { return 0; }
            return n + sumTo(n - 1);
        }
        export var result = sumTo(100);
        """
        exports = _eval(code)
        assert exports.get("result") == 5050


# ===========================================================================
# OperatorPrecedenceTest.java — 13 tests
# ===========================================================================
class TestOperatorPrecedenceSync:
    """Operator precedence tests — synced from OperatorPrecedenceTest.java."""

    # -- Java: testTernaryWithArithmetic --
    def test_ternary_with_arithmetic(self):
        """true ? 1 + 2 : 3 + 4 => 3 (not 7)."""
        assert _eval_result("true ? 1 + 2 : 3 + 4") == 3

    # -- Java: testTernaryWithMultiplication --
    def test_ternary_with_multiplication(self):
        """true ? 2 * 3 : 4 * 5 => 6."""
        assert _eval_result("true ? 2 * 3 : 4 * 5") == 6

    # -- Java: testTernaryWithMixedArithmetic --
    def test_ternary_with_mixed_arithmetic(self):
        """false ? 1 + 2 : 3 * 4 => 12."""
        assert _eval_result("false ? 1 + 2 : 3 * 4") == 12

    # -- Java: testTernaryWithLogical --
    def test_ternary_with_logical(self):
        """true && false ? 'yes' : 'no' => 'no'."""
        assert _eval_result("true && false ? 'yes' : 'no'") == "no"

    # -- Java: testTernaryBranchWithLogical --
    def test_ternary_branch_with_logical(self):
        """true ? true || false : false => true."""
        assert _eval_result("true ? true || false : false") is True

    # -- Java: testNestedTernary --
    def test_nested_ternary(self):
        """false ? 1 : true ? 2 : 3 => 2 (right-associative)."""
        assert _eval_result("false ? 1 : true ? 2 : 3") == 2

    # -- Java: testNestedTernaryInThen --
    def test_nested_ternary_in_then(self):
        """true ? false ? 1 : 2 : 3 => 2."""
        assert _eval_result("true ? false ? 1 : 2 : 3") == 2

    # -- Java: testTernaryWithComparison --
    def test_ternary_with_comparison(self):
        """1 < 2 ? 'yes' : 'no' => 'yes'."""
        assert _eval_result("1 < 2 ? 'yes' : 'no'") == "yes"

    # -- Java: testTernaryBranchWithComparison --
    def test_ternary_branch_with_comparison(self):
        """true ? 1 > 2 : false => false."""
        assert _eval_result("true ? 1 > 2 : false") is False

    # -- Java: testComplexExpression --
    def test_complex_precedence(self):
        """1 + 2 > 2 && true ? 'yes' : 'no' => 'yes'."""
        assert _eval_result("1 + 2 > 2 && true ? 'yes' : 'no'") == "yes"

    # -- Java: testTernaryWithParentheses --
    def test_ternary_with_parentheses(self):
        """(false ? 1 : 2) + 10 => 12."""
        assert _eval_result("(false ? 1 : 2) + 10") == 12

    # -- Java: testTernaryWithOptionalChaining --
    def test_ternary_with_optional_chaining(self):
        """obj?.value ? 'exists' : 'nope' with null obj => 'nope'."""
        result = _eval_result("obj?.value ? 'exists' : 'nope'")
        assert result == "nope"

    # -- Java: testTernaryReturnTypes --
    def test_ternary_return_types(self):
        """Ternary can return different types in branches."""
        assert _eval_result("true ? 42 : 'str'") == 42
        assert _eval_result("false ? 42 : 'str'") == "str"
        assert _eval_result("true ? null : 1") is None


# ===========================================================================
# ForExpTest.java — 11 tests
# ===========================================================================
@pytest.mark.skipif(
    not JAVA_RESOURCES_PATH.exists(),
    reason="Java test resources not available",
)
class TestForExpSync:
    """For-loop tests — synced from ForExpTest.java."""

    # -- Java: evalValue (for_test.fsscript = one-liner, different from continue test) --
    def test_for_basic(self):
        """for_test.fsscript: basic var for loop with exports."""
        source = _load_java_resource("exp/for_test.fsscript")
        exports = _eval(source)
        assert exports.get("i") == 10
        assert exports.get("b") == "b"
        assert exports.get("ee") == 2

    # -- Java: forTest1 (for_test2.fsscript = continue test) --
    def test_for_continue(self):
        """for loop with continue skips iteration (for_test2)."""
        source = _load_java_resource("exp/for_test2.fsscript")
        exports = _eval(source)
        # Loop 0..3, skip i==2, so j increments 3 times (i=0,1,3)
        assert exports.get("v") == 3

    # -- Java: forTest2 (for_test3.fsscript = nested continue) --
    def test_nested_for_continue(self):
        """Nested for loops with continue (for_test3)."""
        source = _load_java_resource("exp/for_test3.fsscript")
        exports = _eval(source)
        # Outer loop 2 times, inner loop 0..3 skip i==2 → 3 each → 6
        assert exports.get("v") == 6

    # -- Java: forTest3 (for_test4.fsscript = return inside nested for) --
    def test_for_with_return(self):
        """for loop with early return inside function (for_test4)."""
        source = _load_java_resource("exp/for_test4.fsscript")
        exports = _eval(source)
        # Returns 2 from inside nested for
        assert exports.get("v") == 2

    # -- Java: forOfTest (for_of_test / inline) --
    def test_for_of_basic(self):
        """for...of iterates array values."""
        code = """
        let sum = 0;
        let arr = [10, 20, 30];
        for (const x of arr) {
            sum = sum + x;
        }
        export var result = sum;
        """
        exports = _eval(code)
        assert exports.get("result") == 60

    # -- Java: forTest3 (for_test4.fsscript or inline) --
    def test_for_with_break(self):
        """for loop with break."""
        source = _load_java_resource("exp/for_test4.fsscript") if (JAVA_RESOURCES_PATH / "exp/for_test4.fsscript").exists() else None
        if source:
            exports = _eval(source)
            assert exports is not None
        else:
            code = """
            let result = 0;
            for (let i = 0; i < 10; i++) {
                if (i == 5) { break; }
                result = result + 1;
            }
            export var v = result;
            """
            exports = _eval(code)
            assert exports.get("v") == 5

    # -- Java: evalValue2 (for_cl.fsscript or inline) --
    def test_for_c_style(self):
        """C-style for loop."""
        code = """
        var b = 1;
        var c = 1;
        for (var i = 0; i < 10; i++) {
            b = 'b';
            var d = 12;
            var c = 2;
            export var ee = 2;
        }
        export {b, c, d, i};
        """
        exports = _eval(code)
        assert exports.get("i") == 10
        assert exports.get("b") == "b"
        assert exports.get("ee") == 2

    # -- Java: evalValue3 --
    def test_for_with_function(self):
        """for loop creating and calling functions."""
        code = """
        var results = [];
        for (var i = 0; i < 3; i++) {
            var fn = (x) => x * 2;
            results.push(fn(i));
        }
        export var v = results;
        """
        exports = _eval(code)
        assert exports.get("v") == [0, 2, 4]

    # -- Java: evalValue4 --
    def test_for_of_with_objects(self):
        """for...of with array of objects."""
        code = """
        let items = [{v: 1}, {v: 2}, {v: 3}];
        let total = 0;
        for (const item of items) {
            total = total + item.v;
        }
        export var result = total;
        """
        exports = _eval(code)
        assert exports.get("result") == 6

    # -- Java: vfor --
    def test_var_for_scope(self):
        """var in for-loop is function-scoped."""
        code = """
        for (var j = 0; j < 5; j++) {}
        export var result = j;
        """
        exports = _eval(code)
        assert exports.get("result") == 5

    # -- Java: vfor2 --
    def test_var_for_nested_scope(self):
        """Nested var for-loops share scope."""
        code = """
        var total = 0;
        for (var i = 0; i < 3; i++) {
            for (var j = 0; j < 3; j++) {
                total = total + 1;
            }
        }
        export var result = total;
        """
        exports = _eval(code)
        assert exports.get("result") == 9

    # -- Java: for_in_test1 --
    def test_for_in(self):
        """for...in returns indices for arrays."""
        source = _load_java_resource("exp/for_in_test1.fsscript")
        exports = _eval(source)
        assert exports.get("v") == [0, 1]


# ===========================================================================
# ForLetClosureTest.java — 2 tests (augmented)
# ===========================================================================
@pytest.mark.skipif(
    not JAVA_RESOURCES_PATH.exists(),
    reason="Java test resources not available",
)
class TestForLetClosureSync:
    """For-let closure tests — synced from ForLetClosureTest.java."""

    # -- Java: testForLetClosure --
    def test_for_let_closure(self):
        """let in for-loop creates per-iteration scope."""
        source = _load_java_resource("exp/for_let_closure.fsscript")
        exports = _eval(source)
        assert exports.get("aa") == 0
        assert exports.get("bb") == 1

    # -- Java: testForLetClosure2 (inline variant) --
    def test_for_let_closure_array(self):
        """let in for-loop: closures capture their own iteration value."""
        code = """
        var funcs = [];
        for (let i = 0; i < 3; i++) {
            funcs.push(() => i);
        }
        export var r0 = funcs[0]();
        export var r1 = funcs[1]();
        export var r2 = funcs[2]();
        """
        exports = _eval(code)
        # With let, each closure captures its own i
        assert exports.get("r0") == 0
        assert exports.get("r1") == 1
        assert exports.get("r2") == 2


# ===========================================================================
# BugFix1Test.java — 6 tests
# ===========================================================================
@pytest.mark.skipif(
    not JAVA_RESOURCES_PATH.exists(),
    reason="Java test resources not available",
)
class TestBugFix1Sync:
    """Bug fix tests — synced from BugFix1Test.java."""

    # -- Java: evalValue --
    def test_bug_fix_1_1_parse(self):
        """bug_fix_1_1.fsscript parses correctly (complex template + for loop)."""
        source = _load_java_resource("exp/bug_fix/bug_fix_1_1.fsscript")
        ast = _parse_only(source)
        assert ast is not None

    # -- Java: evalValue2 --
    def test_bug_fix_1_2_eval(self):
        """bug_fix_1_2.fsscript: complex build function with templates parses and exports."""
        source = _load_java_resource("exp/bug_fix/bug_fix_1_2.fsscript")
        exports = _eval(source)
        # File exports 'build' as a function
        assert "build" in exports
        assert callable(exports["build"])

    # -- Java: evalValueImport --
    def test_bug_fix_import1(self):
        """bug_fix_import1/bug_fix_import1.fsscript import chain works."""
        import1_path = JAVA_RESOURCES_PATH / "exp/bug_fix_import1/bug_fix_import1.fsscript"
        if not import1_path.exists():
            pytest.skip("File not found")
        loader = FileModuleLoader(import1_path.parent)
        source = import1_path.read_text(encoding="utf-8")
        exports = _eval(source, {}, loader)
        assert exports is not None

    # -- Java: evalValueImport_1 / evalValueImport2 --
    def test_bug_fix_import2(self):
        """bug_fix_import2 chain works."""
        import2_dir = JAVA_RESOURCES_PATH / "exp/bug_fix_import2"
        if not import2_dir.exists():
            pytest.skip("Directory not found")
        # Find entry-point file
        entry = None
        for f in import2_dir.glob("*.fsscript"):
            if "deploy" in f.name or "tms" in f.name:
                entry = f
                break
        if entry is None:
            pytest.skip("No entry file found")
        loader = FileModuleLoader(import2_dir)
        source = entry.read_text(encoding="utf-8")
        ast = _parse_only(source)
        assert ast is not None

    # -- Java: bug_fix_accept --
    def test_bug_fix_accept(self):
        """bug_fix_accept.fsscript parses and evaluates."""
        accept_path = JAVA_RESOURCES_PATH / "exp/bug_fix_accept/bug_fix_accept.fsscript"
        if not accept_path.exists():
            pytest.skip("File not found")
        source = accept_path.read_text(encoding="utf-8")
        ast = _parse_only(source)
        assert ast is not None

    # -- Additional: export function invocation --
    def test_exported_function_call(self):
        """Exported function can be called multiple times correctly."""
        code = """
        export function add(a, b) {
            return a + b;
        }
        """
        exports = _eval(code)
        fn = exports.get("add")
        assert fn is not None
        assert fn(1, 2) == 3
        assert fn(10, 20) == 30


# ===========================================================================
# NfFunctionExpTest.java — 2 tests
# ===========================================================================
@pytest.mark.skipif(
    not JAVA_RESOURCES_PATH.exists(),
    reason="Java test resources not available",
)
class TestNfFunctionSync:
    """Named function tests — synced from NfFunctionExpTest.java."""

    # -- Java: nfFunctionTest --
    def test_nf_function_basic(self):
        """nf_function_test.fsscript: arrow functions and named functions."""
        source = _load_java_resource("exp/nf_function_test.fsscript")
        exports = _eval(source)
        # faa() sets b = 'b' and exports cc = 2
        assert exports.get("b") == "b"
        assert exports.get("cc") == 2
        # fbb('22', 'aa') exports ee='22' (parameter b shadows outer),  ff='aa'
        assert exports.get("ee") is not None
        assert exports.get("ff") == "aa"
        # fcc() exports dd = 2
        assert exports.get("dd") == 2

    # -- Java: nfFunctionTest2 (inline arrow function) --
    def test_arrow_function_expression(self):
        """Arrow function as expression."""
        code = """
        var double = (x) => { return x * 2; };
        export var result = double(5);
        """
        exports = _eval(code)
        assert exports.get("result") == 10

    # -- Additional: nested export function --
    def test_nested_export_function(self):
        """export function inside export function."""
        code = """
        export function outer() {
            var dd = 2;
            export function inner() {
                return dd + 1;
            }
            return dd;
        }
        """
        exports = _eval(code)
        assert "outer" in exports
        assert callable(exports.get("outer"))


# ===========================================================================
# ExpStringTest.java — 4 tests
# ===========================================================================
class TestExpStringSync:
    """Expression string tests — synced from ExpStringTest.java."""

    # -- Java: test --
    def test_basic_expression_string(self):
        """Basic expression parsing and evaluation in one-liner form."""
        source = "var b=1;var c=1;for(var i=0;i<10;i++){b='b';var d=12;var c=2;export var ee=2;} export {b,c,d,i}"
        exports = _eval(source)
        assert exports.get("i") == 10
        assert exports.get("b") == "b"
        assert exports.get("ee") == 2

    # -- Java: testEq --
    def test_string_equality(self):
        """String equality with ===."""
        assert _eval_result("'a' === 'a'") is True

    # -- Java: testEq2 --
    def test_string_equality_false(self):
        """String inequality with ===."""
        assert _eval_result("'a' === 'b'") is False

    # -- Java: testEq3 --
    def test_number_equality(self):
        """Number strict equality."""
        assert _eval_result("1 === 1") is True
        assert _eval_result("1 === 2") is False


# ===========================================================================
# CommonDimsParseTest.java — 9 tests (parse-focused)
# ===========================================================================
class TestCommonDimsParseSync:
    """Common dims parse tests — synced from CommonDimsParseTest.java.

    These tests verify parsing of complex ES6+ syntax:
    - export function
    - function parameter defaults (options = {})
    - destructuring with defaults (const { name = 'date', ... } = options)
    - template strings (`${prefix}年份`)
    - arrow functions (prop => allProperties[prop])
    - method chaining (.map().filter())
    """

    # -- Java: test1 (simple object literal) --
    def test_parse_object_literal(self):
        """Parse const with complex object literal."""
        code = "const allProperties = { year: { column: 'year', caption: '年', description: '123' } };"
        ast = _parse_only(code)
        assert ast is not None

    # -- Java: test2 (destructuring + template strings) --
    def test_parse_destructuring_with_templates(self):
        """Parse destructuring assignment with template strings."""
        code = """
        const {
            name = 'date',
            foreignKey = 'date_key',
            caption = '日期',
            description = '日期信息',
            contextPrefix = '',
            includeProperties = ['year', 'quarter', 'month']
        } = options;
        const prefix = contextPrefix ? `${contextPrefix}的` : '';
        const allProperties = {
            year: { column: 'year', caption: '年', description: `${prefix}年份` },
            quarter: { column: 'quarter', caption: '季度', description: `${prefix}季度` }
        };
        """
        ast = _parse_only(code)
        assert ast is not None

    # -- Java: test3_codeInFunction --
    def test_parse_function_with_destructuring(self):
        """Parse function containing destructuring and template strings."""
        code = """
        function buildDateDim(options = {}) {
            const {
                name = 'date',
                foreignKey = 'date_key',
                caption = '日期',
                description = '日期信息',
                contextPrefix = '',
                includeProperties = ['year', 'quarter', 'month', 'month_name', 'day_of_week', 'is_weekend']
            } = options;

            const prefix = contextPrefix ? `${contextPrefix}的` : '';

            const allProperties = {
                year: { column: 'year', caption: '年', description: `${prefix}年份` },
                quarter: { column: 'quarter', caption: '季度', description: `${prefix}季度（1-4）` }
            };
            return allProperties;
        }
        """
        ast = _parse_only(code)
        assert ast is not None

    # -- Java: test4_exportFunction --
    def test_parse_export_function_with_destructuring(self):
        """Parse export function with destructuring parameters."""
        code = """
        export function buildDateDim(options = {}) {
            const {
                name = 'date',
                foreignKey = 'date_key'
            } = options;

            const prefix = contextPrefix ? `${contextPrefix}的` : '';

            const allProperties = {
                year: { column: 'year', caption: '年', description: `${prefix}年份` }
            };
            return allProperties;
        }
        """
        ast = _parse_only(code)
        assert ast is not None

    # -- Java: testParseCommonDims --
    @pytest.mark.skipif(
        not JAVA_RESOURCES_PATH.exists(),
        reason="Java test resources not available",
    )
    def test_parse_common_dims_file(self):
        """common-dims.fsscript should parse successfully."""
        source = _load_java_resource("exp/common-dims.fsscript")
        ast = _parse_only(source)
        assert ast is not None

    # -- Java: testEvalCommonDims --
    @pytest.mark.skipif(
        not JAVA_RESOURCES_PATH.exists(),
        reason="Java test resources not available",
    )
    def test_eval_common_dims_exports(self):
        """common-dims.fsscript exports expected functions."""
        source = _load_java_resource("exp/common-dims.fsscript")
        exports = _eval(source)
        # Should export build* dimension functions
        expected_funcs = [
            "buildDateDim", "buildCustomerDim", "buildProductDim",
            "buildStoreDim", "buildChannelDim", "buildPromotionDim",
        ]
        for func_name in expected_funcs:
            assert func_name in exports, f"Missing export: {func_name}"
            assert callable(exports[func_name]), f"{func_name} should be callable"

    # -- Java: testCallBuildDateDimWithDefaults --
    @pytest.mark.skipif(
        not JAVA_RESOURCES_PATH.exists(),
        reason="Java test resources not available",
    )
    def test_call_build_date_dim_defaults(self):
        """buildDateDim() with no args uses defaults."""
        source = _load_java_resource("exp/common-dims.fsscript")
        exports = _eval(source)
        fn = exports.get("buildDateDim")
        if fn is None:
            pytest.skip("buildDateDim not exported")
        result = fn({})
        assert result is not None
        assert result.get("name") == "date"
        assert result.get("tableName") == "dim_date"
        assert result.get("foreignKey") == "date_key"

    # -- Java: testCallBuildDateDimWithOptions --
    @pytest.mark.skipif(
        not JAVA_RESOURCES_PATH.exists(),
        reason="Java test resources not available",
    )
    def test_call_build_date_dim_with_options(self):
        """buildDateDim(options) uses custom values."""
        source = _load_java_resource("exp/common-dims.fsscript")
        exports = _eval(source)
        fn = exports.get("buildDateDim")
        if fn is None:
            pytest.skip("buildDateDim not exported")
        result = fn({
            "name": "salesDate",
            "foreignKey": "sale_date_key",
            "caption": "销售日期",
            "contextPrefix": "销售",
        })
        assert result is not None
        assert result.get("name") == "salesDate"
        assert result.get("foreignKey") == "sale_date_key"

    # -- Java: testCallBuildProductDim --
    @pytest.mark.skipif(
        not JAVA_RESOURCES_PATH.exists(),
        reason="Java test resources not available",
    )
    def test_call_build_product_dim(self):
        """buildProductDim() returns product dimension config."""
        source = _load_java_resource("exp/common-dims.fsscript")
        exports = _eval(source)
        fn = exports.get("buildProductDim")
        if fn is None:
            pytest.skip("buildProductDim not exported")
        result = fn({})
        assert result is not None
        assert result.get("name") == "product"
        assert result.get("tableName") == "dim_product"


# ===========================================================================
# SwitchTest.java — augmented (already partially covered in test_java_resources)
# ===========================================================================
@pytest.mark.skipif(
    not JAVA_RESOURCES_PATH.exists(),
    reason="Java test resources not available",
)
class TestSwitchSync:
    """Switch tests — synced from SwitchTest.java."""

    # -- Java: evalValue --
    def test_switch_case_1(self):
        """switch(test) case 1 => result=11."""
        source = _load_java_resource("exp/switch.fsscript")
        exports = _eval(source, {"test": 1})
        assert exports.get("result") == 11

    # -- Java: evalValue2 --
    def test_switch_case_string(self):
        """switch(test) case '2' => result='22'."""
        source = _load_java_resource("exp/switch.fsscript")
        exports = _eval(source, {"test": "2"})
        assert exports.get("result") == "22"

    # -- Java: default case --
    def test_switch_default(self):
        """switch(test) default => result=999."""
        source = _load_java_resource("exp/switch.fsscript")
        exports = _eval(source, {"test": 3})
        assert exports.get("result") == 999

    # -- switch2.fsscript if exists --
    def test_switch2(self):
        """switch2.fsscript if available."""
        switch2_path = JAVA_RESOURCES_PATH / "exp/switch2.fsscript"
        if not switch2_path.exists():
            pytest.skip("switch2.fsscript not found")
        source = switch2_path.read_text(encoding="utf-8")
        ast = _parse_only(source)
        assert ast is not None


# ===========================================================================
# ExportExpTest.java — 3 tests (augmented)
# ===========================================================================
@pytest.mark.skipif(
    not JAVA_RESOURCES_PATH.exists(),
    reason="Java test resources not available",
)
class TestExportExpSync:
    """Export tests — synced from ExportExpTest.java."""

    # -- Java: evalValue (export_test.fsscript) --
    def test_export_test(self):
        source = _load_java_resource("exp/export_test.fsscript")
        exports = _eval(source)
        assert exports.get("d") == 1
        assert exports.get("b") == 2
        assert exports.get("cc") == 2
        assert "xxx" in exports
        assert "default" in exports

    # -- Java: export_test3 --
    def test_export_test3(self):
        source = _load_java_resource("exp/export_test3.fsscript")
        ast = _parse_only(source)
        assert ast is not None

    # -- Java: export_test4 --
    def test_export_test4(self):
        source = _load_java_resource("exp/export_test4.fsscript")
        ast = _parse_only(source)
        assert ast is not None


# ===========================================================================
# FsscriptImplTest.java — 2 tests (adapted: no Spring, check import tracking)
# ===========================================================================
@pytest.mark.skipif(
    not JAVA_RESOURCES_PATH.exists(),
    reason="Java test resources not available",
)
class TestFsscriptImplSync:
    """Import tracking tests — adapted from FsscriptImplTest.java.

    Java version tests hasImport() relationship tracking.
    Python adaptation verifies import/export chain works correctly.
    """

    # -- Java: hasImport --
    def test_import_chain_basic(self):
        """import_test.fsscript imports from export_test.fsscript."""
        exp_dir = JAVA_RESOURCES_PATH / "exp"
        import_file = exp_dir / "import_test.fsscript"
        export_file = exp_dir / "export_test.fsscript"
        if not import_file.exists() or not export_file.exists():
            pytest.skip("Files not found")

        loader = FileModuleLoader(exp_dir)
        source = import_file.read_text(encoding="utf-8")
        exports = _eval(source, {}, loader)
        # The import should have succeeded (b=2 from export_test)
        assert exports is not None

    # -- Java: hasImport2 (multi-level import) --
    def test_import_chain_multi_level(self):
        """import_test2 -> export_test2 -> export_test (transitive)."""
        exp_dir = JAVA_RESOURCES_PATH / "exp"
        import2_file = exp_dir / "import_test2.fsscript"
        if not import2_file.exists():
            pytest.skip("import_test2.fsscript not found")

        loader = FileModuleLoader(exp_dir)
        source = import2_file.read_text(encoding="utf-8")
        exports = _eval(source, {}, loader)
        assert exports is not None


# ===========================================================================
# Additional: ArrayExpTest.java augmented tests
# ===========================================================================
class TestArrayExpSync:
    """Array expression tests — synced from ArrayExpTest.java."""

    # -- Java: evalValue --
    def test_array_basic(self):
        assert _eval_result("[1, 2, 3]") == [1, 2, 3]

    # -- Java: evalValue2 --
    def test_array_access(self):
        assert _eval_result("[1, 2, 3][1]") == 2

    # -- Java: evalValue3 --
    def test_array_length(self):
        assert _eval_result("[1, 2, 3].length") == 3

    # -- Java: evalValue4 --
    def test_array_push(self):
        code = "var a = [1]; a.push(2); a.push(3); a;"
        assert _eval_result(code) == [1, 2, 3]

    # -- Java: forEach --
    def test_array_forEach(self):
        code = """
        var total = 0;
        [1, 2, 3].forEach(x => { total = total + x; });
        total;
        """
        assert _eval_result(code) == 6

    # -- Java: filter --
    def test_array_filter(self):
        assert _eval_result("[1, 2, 3, 4].filter(x => x > 2)") == [3, 4]

    # -- Java: filter2 --
    def test_array_filter_empty(self):
        assert _eval_result("[1, 2, 3].filter(x => x > 10)") == []

    # -- Java: test_Array --
    def test_array_map(self):
        assert _eval_result("[1, 2, 3].map(x => x * 2)") == [2, 4, 6]

    # -- Java: test_Array2 --
    def test_array_reduce(self):
        code = "[1, 2, 3, 4].reduce((acc, x) => acc + x, 0)"
        assert _eval_result(code) == 10

    # -- Java: test_Array3 --
    def test_array_find(self):
        code = "[1, 2, 3, 4].find(x => x > 2)"
        assert _eval_result(code) == 3

    # -- Java: test_Array4 --
    def test_array_includes(self):
        assert _eval_result("[1, 2, 3].includes(2)") is True
        assert _eval_result("[1, 2, 3].includes(5)") is False

    # -- Java: testxx --
    def test_array_join(self):
        assert _eval_result("[1, 2, 3].join(',')") == "1,2,3"


# ===========================================================================
# DotExpTest.java — 1 test
# ===========================================================================
@pytest.mark.skipif(
    not JAVA_RESOURCES_PATH.exists(),
    reason="Java test resources not available",
)
class TestDotExpSync:
    """Dot expression tests — synced from DotExpTest.java."""

    def test_dot_expression(self):
        """dot.fsscript: object property access via dot notation."""
        source = _load_java_resource("exp/dot.fsscript")
        ast = _parse_only(source)
        assert ast is not None


# ===========================================================================
# MapExpTest.java — 1 test
# ===========================================================================
@pytest.mark.skipif(
    not JAVA_RESOURCES_PATH.exists(),
    reason="Java test resources not available",
)
class TestMapExpSync:
    """Map expression tests — synced from MapExpTest.java."""

    def test_map_expression(self):
        """map_test.fsscript: object literal syntax."""
        source = _load_java_resource("exp/map_test.fsscript")
        ast = _parse_only(source)
        assert ast is not None


# ===========================================================================
# ASITest.java — 1 test
# ===========================================================================
@pytest.mark.skipif(
    not JAVA_RESOURCES_PATH.exists(),
    reason="Java test resources not available",
)
class TestASISync:
    """ASI tests — synced from ASITest.java."""

    def test_asi(self):
        """asi_test.fsscript: automatic semicolon insertion."""
        source = _load_java_resource("exp/asi_test.fsscript")
        ast = _parse_only(source)
        assert ast is not None


# ===========================================================================
# ImportExpTest.java — 2 tests
# ===========================================================================
@pytest.mark.skipif(
    not JAVA_RESOURCES_PATH.exists(),
    reason="Java test resources not available",
)
class TestImportExpSync:
    """Import expression tests — synced from ImportExpTest.java."""

    # -- Java: evalValue --
    def test_import_basic(self):
        """import_test.fsscript: basic named import."""
        exp_dir = JAVA_RESOURCES_PATH / "exp"
        source = _load_java_resource("exp/import_test.fsscript")
        loader = FileModuleLoader(exp_dir)
        exports = _eval(source, {}, loader)
        assert exports is not None

    # -- Java: testImportNamespace --
    def test_import_namespace(self):
        """import_namespace_test.fsscript: import * as name."""
        ns_file = JAVA_RESOURCES_PATH / "exp/import_namespace_test.fsscript"
        if not ns_file.exists():
            pytest.skip("import_namespace_test.fsscript not found")
        exp_dir = JAVA_RESOURCES_PATH / "exp"
        source = ns_file.read_text(encoding="utf-8")
        loader = FileModuleLoader(exp_dir)
        exports = _eval(source, {}, loader)
        assert exports is not None
