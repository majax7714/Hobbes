"""Tests for hobbes.extract.pysource — the per-file tree-sitter walk."""

from hobbes.extract.pysource import (
    FromImport,
    PlainImport,
    parse_source,
)


def parse(text: str):
    return parse_source(text.encode())


class TestImports:
    def test_plain_aliased_and_multiple(self):
        p = parse("import os, sys\nimport a.b as ab\n")
        assert p.imports == [
            PlainImport("os", None, 1),
            PlainImport("sys", None, 1),
            PlainImport("a.b", "ab", 2),
        ]

    def test_from_imports(self):
        p = parse("from x.y import f, g as h\n")
        assert p.imports == [
            FromImport("x.y", 0, (("f", "f"), ("g", "h")), 1)
        ]

    def test_relative_and_wildcard(self):
        p = parse("from . import sibling\nfrom ..pkg import thing\nfrom z import *\n")
        assert p.imports == [
            FromImport("", 1, (("sibling", "sibling"),), 1),
            FromImport("pkg", 2, (("thing", "thing"),), 2),
            FromImport("z", 0, (("*", "*"),), 3),
        ]

    def test_function_level_imports_count(self):
        p = parse("def f():\n    import late\n")
        assert p.imports == [PlainImport("late", None, 2)]


class TestSymbols:
    def test_kinds_and_qualnames(self):
        p = parse(
            "def func():\n"
            "    def inner():\n"
            "        pass\n"
            "class C:\n"
            "    def method(self):\n"
            "        pass\n"
            "    class Nested:\n"
            "        def deep(self):\n"
            "            pass\n"
        )
        got = {(s.qualname, s.kind) for s in p.symbols}
        assert got == {
            ("func", "function"),
            ("func.inner", "function"),
            ("C", "class"),
            ("C.method", "method"),
            ("C.Nested", "class"),
            ("C.Nested.deep", "method"),
        }

    def test_lines_span_the_definition(self):
        p = parse("def f():\n    a = 1\n    return a\n")
        (symbol,) = p.symbols
        assert (symbol.line, symbol.end_line) == (1, 3)

    def test_decorators_with_string_args_and_kwargs(self):
        p = parse(
            '@app.route("/admin", methods=["GET", "POST"])\n'
            "@property\n"
            "def handler():\n"
            "    pass\n"
        )
        (symbol,) = p.symbols
        route, prop = symbol.decorators
        assert route.dotted == "app.route"
        assert route.args == ("/admin",)
        assert route.kwargs == {"methods": ("GET", "POST")}
        assert prop.dotted == "property"

    def test_fstring_decorator_arg_is_skipped(self):
        p = parse('@app.get(f"/items/{prefix}")\ndef h():\n    pass\n')
        (symbol,) = p.symbols
        assert symbol.decorators[0].args == ()


class TestCalls:
    def test_scopes(self):
        p = parse(
            "top()\n"
            "def f():\n"
            "    mid()\n"
            "class C:\n"
            "    def m(self):\n"
            "        self.n()\n"
        )
        assert {(c.scope, c.callee) for c in p.calls} == {
            (None, "top"),
            ("f", "mid"),
            ("C.m", "self.n"),
        }

    def test_nested_and_chained_calls(self):
        p = parse("def f():\n    return outer(inner(3))\n")
        assert {c.callee for c in p.calls} == {"outer", "inner"}

    def test_dynamic_callees_are_skipped(self):
        p = parse("def f(handlers):\n    handlers[0]()\n    getattr(x, 'y')()\n")
        # subscript-call and call-of-call yield no dotted callee; the inner
        # getattr call itself is a plain name and is recorded.
        assert {c.callee for c in p.calls} == {"getattr"}

    def test_decorator_expressions_do_not_pollute_calls(self):
        p = parse('@app.get("/x")\ndef h():\n    pass\n')
        assert p.calls == []

    def test_wrapped_chain_is_positioned_on_the_callee(self):
        """A site's line must be the callee's, not the expression's.

        SCIP puts its occurrence on the terminal identifier. When a chain
        wraps, the call expression starts lines earlier, and reporting that
        line leaves the site permanently unjoinable (ADR-029) — a missing
        edge and a hole in coverage, neither of which raises anything.
        """
        p = parse(
            "result = (client\n"
            "          .session\n"
            "          .get(url))\n"
        )
        (call,) = p.calls
        assert call.callee == "client.session.get"
        assert call.line == 3  # `.get`, not `client` on line 1

    def test_same_line_calls_are_separated_by_column(self):
        p = parse("out = first(second())\n")
        assert sorted((c.callee, c.col) for c in p.calls) == [
            ("first", 6),
            ("second", 12),
        ]


class TestEnvReads:
    def test_all_four_patterns(self):
        p = parse(
            'import os\n'
            'a = os.getenv("A")\n'
            'b = os.environ["B"]\n'
            'c = os.environ.get("C")\n'
            'from os import environ, getenv\n'
            'd = getenv("D")\n'
            'e = environ["E"]\n'
        )
        assert [(r.var, r.line) for r in p.env_reads] == [
            ("A", 2),
            ("B", 3),
            ("C", 4),
            ("D", 6),
            ("E", 7),
        ]

    def test_dynamic_var_names_are_skipped(self):
        p = parse('import os\nx = os.getenv(name)\ny = os.environ[f"PRE_{n}"]\n')
        assert p.env_reads == []


class TestResilience:
    def test_syntax_errors_yield_partial_facts(self):
        p = parse("def ok():\n    pass\n\ndef broken(:\n")
        assert any(s.qualname == "ok" for s in p.symbols)

    def test_empty_file(self):
        p = parse("")
        assert (p.imports, p.symbols, p.calls, p.env_reads) == ([], [], [], [])


class TestLocalBindings:
    """Sub-module bindings with enclosing-function extents (ADR-046)."""

    def bindings(self, text):
        from hobbes.extract.pysource import parse_source
        return {(b.name, b.start, b.end)
                for b in parse_source(text.encode()).local_bindings}

    def test_parameters_bind_within_their_function(self):
        got = self.bindings(
            "def test_x(fake_policy_bin, tmp_path):\n"
            "    pass\n")
        assert ("fake_policy_bin", 1, 2) in got
        assert ("tmp_path", 1, 2) in got

    def test_typed_and_defaulted_parameters_bind_too(self):
        got = self.bindings(
            "def run(count: int, retry=False, *args, **kwargs):\n"
            "    pass\n")
        assert {n for n, _, _ in got} == {"count", "retry", "args", "kwargs"}

    def test_assignments_and_tuple_targets_bind(self):
        got = self.bindings(
            "def go():\n"
            "    out = make()\n"
            "    a, b = pair()\n")
        assert {n for n, _, _ in got} >= {"out", "a", "b"}

    def test_a_nested_def_binds_in_the_enclosing_function(self):
        got = self.bindings(
            "def outer():\n"
            "    def symbol_at(line):\n"
            "        pass\n"
            "    symbol_at(3)\n")
        # the nested def's *name* carries the outer extent; its param
        # carries its own
        assert ("symbol_at", 1, 4) in got
        assert ("line", 2, 3) in got

    def test_for_with_and_except_targets_bind(self):
        got = self.bindings(
            "def go():\n"
            "    for item in xs:\n"
            "        pass\n"
            "    with open(p) as fh:\n"
            "        pass\n"
            "    try:\n"
            "        pass\n"
            "    except ValueError as exc:\n"
            "        pass\n")
        assert {n for n, _, _ in got} >= {"item", "fh", "exc"}

    def test_module_level_names_are_not_local_bindings(self):
        got = self.bindings("X = make()\nfor y in xs:\n    pass\n")
        assert got == set()

    def test_a_local_class_binds_its_name_but_not_its_methods(self):
        got = self.bindings(
            "def outer():\n"
            "    class Helper:\n"
            "        def ping(self):\n"
            "            pass\n"
            "    return Helper\n")
        names = {n for n, _, _ in got}
        assert "Helper" in names
        assert "ping" not in names  # a method is not a bare-callable local
        assert ("self", 3, 4) in got  # but its params bind in the method
