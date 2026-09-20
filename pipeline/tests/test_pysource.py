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

    def test_a_trailing_comment_does_not_blind_the_digest(self):
        # The comment is a child of the `decorator` node; read as the
        # expression it left `dotted` None, so the fixture was no fixture.
        p = parse(
            "@pytest.fixture  # shared\n"
            '@app.route("/x")  # type: ignore\n'
            '@pytest.mark.parametrize("a", [1])  # one\n'
            "def handler(a):\n"
            "    pass\n"
        )
        (symbol,) = p.symbols
        fixture, route, _ = symbol.decorators
        assert fixture.dotted == "pytest.fixture"
        assert (route.dotted, route.args) == ("app.route", ("/x",))
        assert symbol.parametrized == ("a",)
        assert [(c.callee, c.line) for c in p.calls] == [
            ("pytest.fixture", 1),
            ("app.route", 2),
            ("pytest.mark.parametrize", 3),
        ]

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


class TestReturnedValue:
    """What a definition constructs and hands back (ADR-145): one valued
    exit, and that value a call on a bare name. Everything else is None,
    because everything else leaves the runtime class open."""

    def test_one_return_of_a_construction(self):
        p = parse("def f():\n    return C()\n")
        (symbol,) = p.symbols
        assert symbol.value == ("C", 2)

    def test_one_yield_of_a_construction(self):
        p = parse("def f():\n    yield C()\n")
        (symbol,) = p.symbols
        assert symbol.value == ("C", 2)

    def test_two_valued_returns_settle_nothing(self):
        p = parse("def f(flag):\n    if flag:\n        return C()\n    return D()\n")
        (symbol,) = p.symbols
        assert symbol.value is None

    def test_a_yield_from_is_a_delegation_not_a_construction(self):
        p = parse("def f():\n    yield from C()\n")
        (symbol,) = p.symbols
        assert symbol.value is None

    def test_returning_a_name_says_nothing(self):
        p = parse("def f():\n    app = C()\n    return app\n")
        (symbol,) = p.symbols
        assert symbol.value is None

    def test_returning_a_call_on_a_value_says_nothing(self):
        p = parse("def f():\n    return a.b()\n")
        (symbol,) = p.symbols
        assert symbol.value is None

    def test_a_nested_defs_return_is_that_defs(self):
        p = parse(
            "def f():\n"
            "    def g():\n"
            "        return C()\n"
            "    return D()\n"
        )
        outer = next(s for s in p.symbols if s.qualname == "f")
        inner = next(s for s in p.symbols if s.qualname == "f.g")
        assert outer.value == ("D", 4)
        assert inner.value == ("C", 3)

    def test_a_bare_return_carries_no_value_and_is_not_a_second(self):
        p = parse("def f(flag):\n    if flag:\n        return\n    return C()\n")
        (symbol,) = p.symbols
        assert symbol.value == ("C", 4)

    def test_a_class_has_no_value(self):
        p = parse("class C:\n    pass\n")
        (symbol,) = p.symbols
        assert symbol.value is None


class TestRebound:
    """Which parameters the definition's own body binds again (ADR-145):
    a reader that takes a parameter to still hold what was passed in has
    to know when it does not."""

    def _rebound(self, body: str) -> tuple[str, ...]:
        p = parse(f"def f(p):\n{body}")
        return next(s for s in p.symbols if s.qualname == "f").rebound

    def test_a_plain_assignment(self):
        assert self._rebound("    p = 1\n") == ("p",)

    def test_an_augmented_assignment(self):
        assert self._rebound("    p += 1\n") == ("p",)

    def test_an_annotated_assignment_with_a_value(self):
        assert self._rebound("    p: int = 1\n") == ("p",)

    def test_an_annotation_without_a_value_binds_nothing(self):
        assert self._rebound("    p: int\n") == ()

    def test_a_walrus(self):
        assert self._rebound("    if (p := 1):\n        pass\n") == ("p",)

    def test_a_for_target(self):
        assert self._rebound("    for p in xs:\n        pass\n") == ("p",)

    def test_a_with_target(self):
        assert self._rebound("    with open(x) as p:\n        pass\n") == ("p",)

    def test_an_except_target(self):
        assert self._rebound(
            "    try:\n        pass\n    except E as p:\n        pass\n"
        ) == ("p",)

    def test_an_import(self):
        assert self._rebound("    import p\n") == ("p",)

    def test_an_import_alias(self):
        assert self._rebound("    from m import thing as p\n") == ("p",)

    def test_a_del(self):
        assert self._rebound("    del p\n") == ("p",)

    def test_a_global(self):
        assert self._rebound("    global p\n") == ("p",)

    def test_a_nonlocal(self):
        assert self._rebound("    nonlocal p\n") == ("p",)

    def test_an_attribute_target_binds_no_name(self):
        assert self._rebound("    p.x = 1\n") == ()

    def test_a_nested_defs_assignment_binds_in_that_def(self):
        p = parse("def f(p):\n    def g():\n        p = 1\n    return C()\n")
        assert next(s for s in p.symbols if s.qualname == "f").rebound == ()

    def test_only_parameters_are_reported(self):
        p = parse("def f(p):\n    other = 1\n")
        assert next(s for s in p.symbols if s.qualname == "f").rebound == ()


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


class TestBooleanKeywords:
    """What the walk keeps of a keyword that is not a string (ADR-139):
    ``True`` by name, and the spellings it could not read at all."""

    @staticmethod
    def decorator(text: str):
        p = parse(f"{text}\ndef repo():\n    return 1\n")
        (symbol,) = p.symbols
        return symbol.decorators[0]

    def test_true_is_kept_by_name(self):
        decorator = self.decorator("@pytest.fixture(autouse=True)")
        assert decorator.true_kwargs == ("autouse",)
        assert decorator.unread_kwargs == ()

    def test_false_is_read_and_kept_nowhere(self):
        decorator = self.decorator("@pytest.fixture(autouse=False)")
        assert (decorator.true_kwargs, decorator.unread_kwargs) == ((), ())

    def test_a_name_or_a_call_is_unread(self):
        assert self.decorator("@pytest.fixture(autouse=FLAG)").unread_kwargs == (
            "autouse",
        )
        assert self.decorator("@pytest.fixture(autouse=flag())").unread_kwargs == (
            "autouse",
        )

    def test_a_string_keyword_is_still_a_string(self):
        decorator = self.decorator('@pytest.fixture(name="alias")')
        assert decorator.kwargs == {"name": "alias"}
        assert (decorator.true_kwargs, decorator.unread_kwargs) == ((), ())


class TestPytestmark:
    """A module-level ``pytestmark`` applies its marks to every test in the
    file; the walk records its ``usefixtures`` calls for the lookup to
    follow (ADR-139's amendment), and counts the ones it cannot — those
    with no string argument at all."""

    @staticmethod
    def marks(p):
        return [(m.dotted, m.args, m.line) for m in p.pytestmark]

    def test_one_call_is_recorded_with_its_names_and_line(self):
        p = parse('import pytest\n\npytestmark = pytest.mark.usefixtures("a")\n')
        assert self.marks(p) == [("pytest.mark.usefixtures", ("a",), 3)]
        assert p.pytestmark_usefixtures == 0

    def test_a_list_records_each_at_its_own_line(self):
        p = parse(
            "pytestmark = [\n"
            '    pytest.mark.usefixtures("a"),\n'
            '    usefixtures("b", "c"),\n'
            "]\n"
        )
        assert self.marks(p) == [
            ("pytest.mark.usefixtures", ("a",), 2),
            ("usefixtures", ("b", "c"), 3),
        ]
        assert p.pytestmark_usefixtures == 0

    def test_a_tuple_is_read_like_a_list(self):
        p = parse(
            "pytestmark = (\n"
            '    pytest.mark.usefixtures("a"),\n'
            '    pytest.mark.usefixtures("b"),\n'
            ")\n"
        )
        assert self.marks(p) == [
            ("pytest.mark.usefixtures", ("a",), 2),
            ("pytest.mark.usefixtures", ("b",), 3),
        ]

    def test_a_mark_with_no_string_argument_is_counted_not_followed(self):
        p = parse("pytestmark = pytest.mark.usefixtures(*names)\n")
        assert self.marks(p) == [("pytest.mark.usefixtures", (), 1)]
        assert p.pytestmark_usefixtures == 1

    def test_another_mark_is_not_recorded(self):
        p = parse('pytestmark = pytest.mark.skipif(True, reason="x")\n')
        assert p.pytestmark == () and p.pytestmark_usefixtures == 0

    def test_below_module_level_is_not_the_modules_pytestmark(self):
        p = parse(
            "class TestOne:\n"
            '    pytestmark = pytest.mark.usefixtures("a")\n\n\n'
            "def build():\n"
            '    pytestmark = pytest.mark.usefixtures("b")\n'
        )
        assert p.pytestmark == () and p.pytestmark_usefixtures == 0

    def test_an_annotated_or_augmented_assignment_is_not_read(self):
        # Neither binds the name plainly: one carries an annotation the walk
        # does not read, the other adds to whatever was already there.
        p = parse(
            'pytestmark: list = [pytest.mark.usefixtures("a")]\n'
            'pytestmark += [pytest.mark.usefixtures("b")]\n'
        )
        assert p.pytestmark == () and p.pytestmark_usefixtures == 0


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

    def test_a_decorator_call_is_a_site_on_its_callee(self):
        """ADR-146, part 1: `@app.get("/x")` is the call it is written as.
        Until 0.2.65-beta the expression was not walked at all — on click,
        1,652 of 2,459 missed pairs sat on a decorator line."""
        p = parse('@app.get("/x")\ndef h():\n    pass\n')
        assert [(c.scope, c.callee, c.line, c.col) for c in p.calls] == [
            (None, "app.get", 1, 5)  # on `get`, not on `app`
        ]

    def test_a_decorators_scope_is_the_enclosing_definition(self):
        """The decorated def is not running yet: the call belongs to
        whatever holds the `@`."""
        p = parse(
            "def outer():\n"
            '    @register("x")\n'
            "    def inner():\n"
            "        pass\n"
        )
        assert [(c.scope, c.callee) for c in p.calls] == [("outer", "register")]

    def test_a_decorated_method_takes_the_class_body_scope(self):
        """`_scope_qualname` gives a class body its own qualname, as it
        does for any call written there."""
        p = parse(
            "class C:\n"
            '    @register("x")\n'
            "    def m(self):\n"
            "        pass\n"
        )
        assert [(c.scope, c.callee) for c in p.calls] == [("C", "register")]

    def test_a_bare_decorator_is_an_application_of_what_it_names(self):
        """ADR-146, part 2: `@pass_context` is `pass_context(h)` by the
        language's own definition, recorded at the name."""
        p = parse("@pass_context\ndef h():\n    pass\n")
        assert [(c.scope, c.callee, c.line, c.col) for c in p.calls] == [
            (None, "pass_context", 1, 1)
        ]

    def test_a_bare_dotted_decorator_sits_on_its_terminal_identifier(self):
        p = parse("@a.b.c\ndef h():\n    pass\n")
        assert [(c.callee, c.line, c.col) for c in p.calls] == [("a.b.c", 1, 5)]

    def test_a_call_in_a_decorators_arguments_is_a_site_too(self):
        p = parse("@f(g(1))\ndef h():\n    pass\n")
        assert sorted((c.callee, c.col) for c in p.calls) == [("f", 1), ("g", 3)]

    def test_an_expression_decorator_applies_no_name(self):
        """A subscript and a lambda name nothing to apply, so part 2
        records nothing for them — the calls written inside them are
        still walked, as anywhere else."""
        p = parse(
            "@decos[0]\n"
            "def h():\n"
            "    pass\n"
            "\n"
            "\n"
            "@(lambda f: f)\n"
            "def i():\n"
            "    pass\n"
            "\n"
            "\n"
            "@decos[pick()]\n"
            "def j():\n"
            "    pass\n"
        )
        assert [(c.scope, c.callee, c.line) for c in p.calls] == [(None, "pick", 11)]

    def test_a_decorated_class_is_the_same_rule(self):
        """The grammar's `decorated_definition` holds both, and so does
        the rule."""
        p = parse('@register("x")\nclass C:\n    pass\n')
        assert [(c.scope, c.callee, c.line) for c in p.calls] == [
            (None, "register", 1)
        ]

    def test_stacked_decorators_are_one_site_each_in_written_order(self):
        p = parse(
            "@first\n"
            '@second("x")\n'
            "@third.fourth\n"
            "def h():\n"
            "    pass\n"
        )
        assert [(c.callee, c.line) for c in p.calls] == [
            ("first", 1),
            ("second", 2),
            ("third.fourth", 3),
        ]

    def test_the_digest_and_a_parametrize_reading_are_unchanged(self):
        """The walk adds call sites and nothing else: what the route and
        test packs read off a symbol is the same digest as before."""
        p = parse(
            "import pytest\n"
            "\n"
            "\n"
            '@pytest.mark.parametrize("a, b", [("x", "y")])\n'
            '@app.get("/x")\n'
            "def test_h(a, b):\n"
            "    pass\n"
        )
        (symbol,) = [s for s in p.symbols if s.qualname == "test_h"]
        assert [(d.dotted, d.args, d.line) for d in symbol.decorators] == [
            ("pytest.mark.parametrize", ("a, b",), 4),
            ("app.get", ("/x",), 5),
        ]
        assert symbol.parametrized == ("a", "b")
        assert [c.callee for c in p.calls] == ["pytest.mark.parametrize", "app.get"]

    def test_an_env_read_in_a_decorators_arguments_is_recorded(self):
        """A decorator's arguments are ordinary code: an `os.environ.get`
        written there is the env read it is anywhere else."""
        p = parse(
            '@app.get(os.environ.get("ROUTE_PREFIX"))\n'
            "def h():\n"
            "    pass\n"
        )
        assert [(e.var, e.line) for e in p.env_reads] == [("ROUTE_PREFIX", 1)]
        assert [c.callee for c in p.calls] == ["app.get", "os.environ.get"]

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
