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


class TestParameters:
    """What pytest's fixture lookup needs from the walk (ADR-137): the
    parameters a fixture could fill, each with the line it is written on."""

    def test_params_carry_their_names_and_lines(self):
        p = parse("def f(\n    a,\n    b,\n):\n    pass\n")
        (symbol,) = p.symbols
        assert symbol.params == (("a", 2), ("b", 3))

    def test_defaults_and_splats_are_left_out(self):
        p = parse("def f(a, b=1, *args, **kwargs):\n    pass\n")
        (symbol,) = p.symbols
        assert symbol.params == (("a", 1),)

    def test_keyword_only_positional_only_and_typed_are_kept(self):
        p = parse("def f(a, /, b: int, *, c: str, d=2):\n    pass\n")
        (symbol,) = p.symbols
        # The `/` and `*` separators bind nothing; `d` has a default.
        assert symbol.params == (("a", 1), ("b", 1), ("c", 1))

    def test_a_typed_splat_is_still_a_splat(self):
        p = parse("def f(a, *args: int, **kw: str):\n    pass\n")
        (symbol,) = p.symbols
        assert symbol.params == (("a", 1),)

    def test_self_is_recorded_like_any_other_parameter(self):
        p = parse("class C:\n    def m(self, repo):\n        pass\n")
        method = next(s for s in p.symbols if s.kind == "method")
        assert method.params == (("self", 2), ("repo", 2))

    def test_a_class_has_no_parameters(self):
        p = parse("class C(Base):\n    pass\n")
        (symbol,) = p.symbols
        assert symbol.params == ()


class TestParametrized:
    """The names a ``parametrize`` mark binds, in every spelling the walk
    can read — and ``None`` where it cannot read one at all."""

    def test_from_a_string(self):
        p = parse(
            '@pytest.mark.parametrize("a, b", [(1, 2)])\n'
            "def test_x(a, b):\n    pass\n"
        )
        (symbol,) = p.symbols
        assert symbol.parametrized == ("a", "b")

    def test_from_a_list(self):
        p = parse(
            '@pytest.mark.parametrize(["a", "b"], [(1, 2)])\n'
            "def test_x(a, b):\n    pass\n"
        )
        (symbol,) = p.symbols
        assert symbol.parametrized == ("a", "b")

    def test_from_a_tuple(self):
        p = parse(
            '@pytest.mark.parametrize(("path", "expected"), [(1, 2)])\n'
            "def test_x(path, expected):\n    pass\n"
        )
        (symbol,) = p.symbols
        assert symbol.parametrized == ("path", "expected")

    def test_stacked_decorators_are_unioned(self):
        p = parse(
            '@pytest.mark.parametrize("a", [1])\n'
            '@parametrize("b, c", [(1, 2)])\n'
            "def test_x(a, b, c):\n    pass\n"
        )
        (symbol,) = p.symbols
        assert symbol.parametrized == ("a", "b", "c")

    def test_a_name_argument_is_unreadable(self):
        # The names live in a constant defined elsewhere: the walk says so
        # rather than guessing, and the lookup abstains on the whole test.
        p = parse(
            "@pytest.mark.parametrize(CASES, [1])\n"
            "def test_x(a):\n    pass\n"
        )
        (symbol,) = p.symbols
        assert symbol.parametrized is None

    def test_an_undecorated_definition_binds_nothing(self):
        p = parse("def test_x(repo):\n    pass\n")
        (symbol,) = p.symbols
        assert symbol.parametrized == ()


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

    def test_dynamic_callees_are_sites_the_fallback_cannot_name(self):
        from hobbes.extract.pysource import EXPR_RECEIVER

        p = parse("def f(handlers):\n    handlers[0]()\n    getattr(x, 'y')()\n")
        # subscript-call and call-of-call yield no dotted callee: until
        # 2026-09-05 they were skipped; now each is a site under the marker
        # (C-63's shape, C-80's residual). The inner getattr call itself is
        # a plain name and is recorded as before.
        assert sorted(c.callee for c in p.calls) == [EXPR_RECEIVER, EXPR_RECEIVER, "getattr"]

    def test_expression_receivers_are_sites(self):
        """C-80 (lifted): `super().m()`, `f().m()`, `xs[i].m()` are calls
        whose callee name is plain; only the receiver is an expression.
        peft: 252 such calls were `uses` edges glossed as "not a call"."""
        from hobbes.extract.pysource import EXPR_RECEIVER

        p = parse(
            "class C(B):\n"
            "    def __init__(self):\n"
            "        super().__init__()\n"
            "        self.model.cpu().save_pretrained(d)\n"
            "        handlers[0].run()\n"
        )
        assert sorted((c.callee, c.line, c.col) for c in p.calls) == [
            (f"{EXPR_RECEIVER}.__init__", 3, 16),
            (f"{EXPR_RECEIVER}.run", 5, 20),
            (f"{EXPR_RECEIVER}.save_pretrained", 4, 25),
            ("self.model.cpu", 4, 19),
            ("super", 3, 8),
        ]

    def test_expression_callees_are_sites(self):
        """C-63's shape in Python (C-80's residual, closed 2026-09-05):
        a callee that is itself an expression is a site named by the
        marker alone, positioned where the callee starts; the inner
        calls keep their own named sites."""
        from hobbes.extract.pysource import EXPR_RECEIVER

        p = parse(
            "def go(handlers, x, a, b, f):\n"
            "    handlers[0]()\n"
            "    getattr(x, 'y')()\n"
            "    (a or b)()\n"
            "    f()()\n"
            "    (lambda: 1)()\n"
        )
        assert sorted((c.callee, c.line, c.col) for c in p.calls) == [
            (EXPR_RECEIVER, 2, 4),
            (EXPR_RECEIVER, 3, 4),
            (EXPR_RECEIVER, 4, 4),
            (EXPR_RECEIVER, 5, 4),
            (EXPR_RECEIVER, 6, 4),
            ("f", 5, 4),
            ("getattr", 3, 4),
        ]
        assert all(c.scope == "go" for c in p.calls)

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


class TestClassBases:
    """How many base classes a class names (ADR-137's base-class abstention)."""

    def test_bases_are_counted_and_keywords_are_not(self):
        parsed = parse_source(
            b"class A: pass\nclass B(A): pass\nclass C(A, B, metaclass=type): pass\nclass D(): pass\n"
        )
        assert {s.name: s.bases for s in parsed.symbols} == {"A": 0, "B": 1, "C": 2, "D": 0}

    def test_a_function_has_none(self):
        parsed = parse_source(b"def f(a): pass\n")
        assert parsed.symbols[0].bases == 0
