"""A decorator factory's application is a call of the def it returns
(ADR-147), and its guards folded over the site's own arguments (ADR-148).

``@factory("a")`` is two calls: ``factory("a")``, which the index names at
the token and ADR-146 draws, and the application of what it returned to
the definition below — a call of ``factory.<locals>.decorator``, written
nowhere. No indexer emits anything for the second, so the rule reads the
settled graph's own answer at the decorator's line and the factory's
written shape.

The cases below hand :func:`hobbes.extract.decorators.factory_calls` a
graph whose ``semantic`` edge is written out, because that edge is
exactly what the rule is allowed to believe. Each refusal has a case of
its own: the conditions fail toward drawing less, and what each one
declined is the size of what a factory's shape did not settle. Where the
index answered nothing in the repo, nothing was asked at all — and a
block of zeroes would say otherwise.

ADR-148's fold is tested twice over: as the pure function it is, on
digests with no tree behind them (:class:`TestTheFold`, one case per rule
of step 4), and through the whole rule, where what a site wrote decides
which of two readings drew the edge.
"""

from pathlib import Path

import pytest

from hobbes.extract.decorators import (
    ALREADY_DRAWN,
    DECORATED,
    DECORATOR_FACTORY,
    DECORATOR_FACTORY_FOLDED,
    FACTORY_REASONS,
    GUARD_UNKNOWN,
    METHOD_POSITIONAL,
    NO_RETURNED_DEF,
    NO_SINGLE_BODY,
    NO_SYMBOL,
    TWO_TARGETS,
    factory_calls,
    fold_guards,
)
from hobbes.extract.discover import discover_modules
from hobbes.extract.graph import build_graph
from hobbes.extract.pysource import (
    UNKNOWN,
    Assign,
    Binds,
    BoolOp,
    Bound,
    Branch,
    If,
    InnerFold,
    IsCallable,
    IsNone,
    Literal,
    NameRef,
    Not,
    Opaque,
    Param,
    Raise,
    Return,
    parse_source,
)
from hobbes.extract.schema import LANE_SCIP, SEMANTIC, SYNTACTIC, tiered_edge

MINIDECO = Path(__file__).parent / "fixtures" / "minideco"

#: One factory and one method factory, each returning a nested ``def``.
DECO = (
    "def factory(label):\n"
    "    def decorator(fn):\n"
    "        return fn\n"
    "\n"
    "    return decorator\n"
    "\n"
    "\n"
    "class Registry:\n"
    "    def register(self, name):\n"
    "        def decorator(fn):\n"
    "            return fn\n"
    "\n"
    "        return decorator\n"
)

#: The three shapes that draw: a module-level decorator, a method
#: factory's, and one inside ``outer`` — whose ``@`` runs where it is
#: written, so ``outer`` is the caller and never the def it wraps.
APP = (
    "from pkg.deco import Registry, factory\n"
    "\n"
    "registry = Registry()\n"
    "\n"
    "\n"
    '@factory("a")\n'
    "def one():\n"
    "    return 1\n"
    "\n"
    "\n"
    '@registry.register("b")\n'
    "def two():\n"
    "    return 2\n"
    "\n"
    "\n"
    "def outer():\n"
    '    @factory("c")\n'
    "    def nested():\n"
    "        return 3\n"
    "\n"
    "    return nested\n"
)

#: One decorator, on line 4 — the line every refusal case's edge sits on.
SIMPLE_APP = (
    "from pkg.deco import factory\n"
    "\n"
    "\n"
    '@factory("a")\n'
    "def one():\n"
    "    return 1\n"
)

SIMPLE_DECO = (
    "def factory(label):\n"
    "    def decorator(fn):\n"
    "        return fn\n"
    "\n"
    "    return decorator\n"
)

#: click's ``command``: the optional-parentheses idiom ADR-147 refuses
#: whole and ADR-148 folds. At ``@factory("a")`` — or at ``@factory()`` —
#: ``func`` cannot be anything but ``None``, so ``return decorator`` is
#: the only return the site can reach.
FOLDING_DECO = (
    "def factory(name=None, **attrs):\n"
    "    func = None\n"
    "    if callable(name):\n"
    "        func = name\n"
    "\n"
    "    def decorator(fn):\n"
    "        return fn\n"
    "\n"
    "    if func is not None:\n"
    "        return decorator(func)\n"
    "    return decorator\n"
)

#: The same shape as a method — click's ``Group.command`` — on a class the
#: app constructs at module level.
FOLDING_METHOD_DECO = (
    "class Registry:\n"
    "    def command(self, *args, **kwargs):\n"
    "        func = None\n"
    "        if args and callable(args[0]):\n"
    "            (func,) = args\n"
    "\n"
    "        def decorator(fn):\n"
    "            return fn\n"
    "\n"
    "        if func is not None:\n"
    "            return decorator(func)\n"
    "        return decorator\n"
)

#: A module-level ``@factory("a")`` (line 4) and one inside ``outer``
#: written ``@factory()`` (line 10): the two callers a folded draw has.
FOLDING_APP = (
    "from pkg.deco import factory\n"
    "\n"
    "\n"
    '@factory("a")\n'
    "def one():\n"
    "    return 1\n"
    "\n"
    "\n"
    "def outer():\n"
    "    @factory()\n"
    "    def nested():\n"
    "        return 2\n"
    "\n"
    "    return nested\n"
)


def files(deco: str = DECO, app: str = APP, **overrides) -> dict:
    tree = {"pkg/__init__.py": "", "pkg/deco.py": deco, "app.py": app}
    tree.update(overrides)
    return tree


def edge(
    target: str = "pkg.deco.factory",
    line: int = 4,
    source: str = "app",
    tier: str = SEMANTIC,
    to: str = None,
) -> dict:
    """The edge the index draws at the decorator's callee, which ADR-146
    put there and this rule only reads."""
    return tiered_edge(
        source,
        to or target,
        "calls",
        [{"path": "app.py", "line": line}],
        tier=tier,
        lane=LANE_SCIP,
    )


def run(tmp_path, tree: dict, edges: tuple = ()):
    """Write a small tree, then run the rule over the symbols lane A found
    and exactly the *edges* handed in — :func:`build_graph` draws no symbol
    edges at all (the join is their only producer), so the graph a case
    builds is the graph the rule reads."""
    for name, text in tree.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    modules = discover_modules(tmp_path)
    parsed = {m.id: parse_source((tmp_path / m.path).read_bytes()) for m in modules}
    graph = build_graph(modules, parsed)
    return factory_calls(modules, parsed, graph["symbols"], list(edges))


class TestTheShapeDraws:
    def test_every_shape_is_a_call_of_the_def_the_factory_returns(self, tmp_path):
        drawn, counts = run(
            tmp_path,
            files(),
            (
                edge(line=6),
                edge(target="pkg.deco.Registry.register", line=11),
                edge(line=17, source="app.outer"),
            ),
        )
        assert drawn == [
            {
                "from": "app",
                "to": "pkg.deco.Registry.register.decorator",
                "path": "app.py",
                "line": 11,
                "via": DECORATOR_FACTORY,
                "factory": "pkg.deco.Registry.register",
            },
            {
                "from": "app",
                "to": "pkg.deco.factory.decorator",
                "path": "app.py",
                "line": 6,
                "via": DECORATOR_FACTORY,
                "factory": "pkg.deco.factory",
            },
            {
                "from": "app.outer",
                "to": "pkg.deco.factory.decorator",
                "path": "app.py",
                "line": 17,
                "via": DECORATOR_FACTORY,
                "factory": "pkg.deco.factory",
            },
        ]
        assert counts["drawn"] == 3
        assert sum(counts["refused"].values()) == 0

    def test_the_counts_name_every_reason(self, tmp_path):
        _, counts = run(tmp_path, files(), (edge(line=6),))
        assert set(counts["refused"]) == set(FACTORY_REASONS)

    def test_an_overload_stub_is_not_the_body_that_is_read(self, tmp_path):
        # The drawn symbol may *be* the first stub (H-19's grain), so the
        # body is looked up among the qualname's definitions.
        deco = (
            "import typing as t\n"
            "\n"
            "\n"
            "@t.overload\n"
            "def factory(label: str):\n"
            "    ...\n"
            "\n"
            "\n"
            "def factory(label):\n"
            "    def decorator(fn):\n"
            "        return fn\n"
            "\n"
            "    return decorator\n"
        )
        drawn, counts = run(
            tmp_path, files(deco=deco, app=SIMPLE_APP), (edge(),)
        )
        assert [(c["to"], c["line"]) for c in drawn] == [
            ("pkg.deco.factory.decorator", 4)
        ]
        assert counts["drawn"] == 1


class TestTheIndexMustNameOneFactory:
    def test_two_targets_at_the_line_draw_nothing(self, tmp_path):
        # Two functions written `factory`, both answered at the one line:
        # the rule cannot say which factory the decorator applied.
        other = SIMPLE_DECO
        drawn, counts = run(
            tmp_path,
            files(app=SIMPLE_APP, **{"pkg/other.py": other}),
            (edge(), edge(target="pkg.other.factory")),
        )
        assert drawn == []
        assert counts["refused"][TWO_TARGETS] == 1

    def test_a_syntactic_edge_is_not_the_index_answering(self, tmp_path):
        drawn, counts = run(
            tmp_path, files(app=SIMPLE_APP), (edge(tier=SYNTACTIC),)
        )
        assert (drawn, counts) == ([], {})

    def test_no_edge_at_the_line_asks_nothing(self, tmp_path):
        drawn, counts = run(tmp_path, files(app=SIMPLE_APP))
        assert (drawn, counts) == ([], {})

    def test_an_edge_onto_another_name_is_not_this_factory(self, tmp_path):
        # `@factory("a")` resolved to something not written `factory` —
        # an argument's function, a receiver's class: not asked.
        drawn, counts = run(
            tmp_path, files(app=SIMPLE_APP), (edge(target="pkg.deco.Registry.register"),)
        )
        assert (drawn, counts) == ([], {})


class TestTheFactoryMustHaveOneUndecoratedBody:
    def test_two_non_overload_definitions_draw_nothing(self, tmp_path):
        drawn, counts = run(
            tmp_path,
            files(deco=SIMPLE_DECO + "\n\n" + SIMPLE_DECO, app=SIMPLE_APP),
            (edge(),),
        )
        assert drawn == []
        assert counts["refused"][NO_SINGLE_BODY] == 1

    def test_a_decorated_factory_draws_nothing(self, tmp_path):
        # flask's `Scaffold.route`, under `@setupmethod`: what the factory
        # hands back is what its own decorator returned.
        deco = "@setupmethod\n" + SIMPLE_DECO
        drawn, counts = run(tmp_path, files(deco=deco, app=SIMPLE_APP), (edge(),))
        assert drawn == []
        assert counts["refused"][DECORATED] == 1

    def test_a_body_with_no_single_nested_def_draws_nothing(self, tmp_path):
        # Two nested defs: which one a return names is the whole
        # question, so neither ADR-147 nor ADR-148's fold reads it.
        deco = (
            "def factory(func):\n"
            "    def decorator(fn):\n"
            "        return fn\n"
            "\n"
            "    def other(fn):\n"
            "        return fn\n"
            "\n"
            "    if func:\n"
            "        return other\n"
            "    return decorator\n"
        )
        drawn, counts = run(tmp_path, files(deco=deco, app=SIMPLE_APP), (edge(),))
        assert drawn == []
        assert counts["refused"][NO_RETURNED_DEF] == 1

    def test_a_body_whose_returns_the_site_does_not_settle(self, tmp_path):
        # `@factory("a")` makes `func` truthy, so the return this site
        # reaches is `decorator(func)` — which the site does not call.
        # ADR-147 counted this `no-returned-def`; ADR-148 asks the fold
        # first and counts what the fold could not settle.
        deco = (
            "def factory(func):\n"
            "    def decorator(fn):\n"
            "        return fn\n"
            "\n"
            "    if func:\n"
            "        return decorator(func)\n"
            "    return decorator\n"
        )
        drawn, counts = run(tmp_path, files(deco=deco, app=SIMPLE_APP), (edge(),))
        assert drawn == []
        assert counts["refused"][GUARD_UNKNOWN] == 1
        assert counts["refused"][NO_RETURNED_DEF] == 0


def fold(body, *, params=(), bound=None, method=False, **overrides):
    """ADR-148's fold over digests alone — no tree, no file, no graph.

    The whole of what :func:`hobbes.extract.decorators.fold_guards` is
    given is written out here, which is the point of the function being
    pure: a case says what lane A wrote down and what the rule made of
    it, with nothing in between to read differently.
    """
    return fold_guards(
        InnerFold("g", params=tuple(params), body=tuple(body), **overrides),
        Bound() if bound is None else bound,
        method,
    )


class TestTheFold:
    """Step 4, rule by rule: three-valued throughout, and an unknown
    costs a draw rather than buying one."""

    def test_the_shape_that_draws(self):
        # `if x: return other` / `return g`, with `x` a literal false.
        assert (
            fold(
                (
                    If((Branch(NameRef("x"), (), (Return(False),)),)),
                    Return(True),
                ),
                params=(Param("x", False),),
            )
            is None
        )

    def test_an_unknown_test_takes_both_branches(self):
        assert (
            fold(
                (
                    If((Branch(NameRef("x"), (), (Return(False),)),)),
                    Return(True),
                ),
                params=(Param("x"),),
            )
            == GUARD_UNKNOWN
        )

    def test_an_unfilled_parameter_takes_its_literal_default(self):
        assert (
            fold(
                (
                    If((Branch(IsNone(NameRef("x"), negated=True), (), (Return(False),)),)),
                    Return(True),
                ),
                params=(Param("x", None),),
            )
            is None
        )

    def test_a_positional_argument_binds_in_order(self):
        assert (
            fold(
                (
                    If((Branch(NameRef("b"), (), (Return(False),)),)),
                    Return(True),
                ),
                params=(Param("a"), Param("b")),
                bound=Bound(args=(1, "")),
            )
            is None
        )

    def test_a_keyword_argument_binds_by_name(self):
        assert (
            fold(
                (
                    If((Branch(NameRef("b"), (), (Return(False),)),)),
                    Return(True),
                ),
                params=(Param("a"), Param("b", True)),
                bound=Bound(kwargs=(("b", False),)),
            )
            is None
        )

    def test_a_splat_makes_the_whole_binding_unknown(self):
        assert (
            fold(
                (
                    If((Branch(NameRef("x"), (), (Return(False),)),)),
                    Return(True),
                ),
                params=(Param("x", False),),
                bound=Bound(splat=True),
            )
            == GUARD_UNKNOWN
        )

    def test_an_unfilled_star_args_is_empty(self):
        assert (
            fold(
                (
                    If((Branch(NameRef("rest"), (), (Return(False),)),)),
                    Return(True),
                ),
                star="rest",
            )
            is None
        )

    def test_and_short_circuits_on_a_known_operand(self):
        # `UNK and False` is false whatever the unknown stood for.
        assert (
            fold(
                (
                    If(
                        (
                            Branch(
                                BoolOp("and", NameRef("x"), Literal(False)),
                                (),
                                (Return(False),),
                            ),
                        )
                    ),
                    Return(True),
                ),
                params=(Param("x"),),
            )
            is None
        )

    def test_or_short_circuits_on_a_known_operand(self):
        # `UNK or True` is true, so that arm runs and no other does.
        assert (
            fold(
                (
                    If(
                        (
                            Branch(
                                BoolOp("or", NameRef("x"), Literal(True)),
                                (),
                                (Return(True),),
                            ),
                        )
                    ),
                    Return(False),
                ),
                params=(Param("x"),),
            )
            is None
        )

    def test_and_with_two_unknowns_settles_nothing(self):
        assert (
            fold(
                (
                    If(
                        (
                            Branch(
                                BoolOp("and", NameRef("x"), NameRef("y")),
                                (),
                                (Return(False),),
                            ),
                        )
                    ),
                    Return(True),
                ),
                params=(Param("x"), Param("y")),
            )
            == GUARD_UNKNOWN
        )

    def test_not_negates_a_known_test(self):
        assert (
            fold(
                (
                    If((Branch(Not(Literal(True)), (), (Return(False),)),)),
                    Return(True),
                )
            )
            is None
        )

    def test_callable_is_false_on_a_literal(self):
        assert (
            fold(
                (
                    If((Branch(IsCallable(Literal("x")), (), (Return(False),)),)),
                    Return(True),
                )
            )
            is None
        )

    def test_callable_of_an_unknown_settles_nothing(self):
        assert (
            fold(
                (
                    If((Branch(IsCallable(NameRef("x")), (), (Return(False),)),)),
                    Return(True),
                ),
                params=(Param("x"),),
            )
            == GUARD_UNKNOWN
        )

    def test_callable_is_unreadable_where_the_module_binds_it(self):
        assert (
            fold(
                (
                    If((Branch(IsCallable(Literal("x")), (), (Return(False),)),)),
                    Return(True),
                ),
                shadows_callable=True,
            )
            == GUARD_UNKNOWN
        )

    def test_branches_merge_on_what_they_agree(self):
        # Both paths leave `a` None, so the guard below reads it.
        assert (
            fold(
                (
                    Assign("a", Literal(None)),
                    If((Branch(NameRef("x"), (), (Assign("a", Literal(None)),)),)),
                    If(
                        (
                            Branch(
                                IsNone(NameRef("a"), negated=True),
                                (),
                                (Return(False),),
                            ),
                        )
                    ),
                    Return(True),
                ),
                params=(Param("x"),),
            )
            is None
        )

    def test_branches_that_disagree_merge_to_unknown(self):
        assert (
            fold(
                (
                    Assign("a", Literal(None)),
                    If((Branch(NameRef("x"), (), (Assign("a", Literal(1)),)),)),
                    If(
                        (
                            Branch(
                                IsNone(NameRef("a"), negated=True),
                                (),
                                (Return(False),),
                            ),
                        )
                    ),
                    Return(True),
                ),
                params=(Param("x"),),
            )
            == GUARD_UNKNOWN
        )

    def test_a_raise_ends_a_path(self):
        assert (
            fold(
                (
                    If((Branch(NameRef("x"), (), (Raise(),)),)),
                    Return(True),
                ),
                params=(Param("x"),),
            )
            is None
        )

    def test_an_else_arm_is_taken_where_its_test_is_false(self):
        assert (
            fold(
                (
                    If(
                        (
                            Branch(Literal(False), (), (Return(False),)),
                            Branch(Literal(False), (), (Return(False),)),
                            Branch(None, (), (Return(True),)),
                        )
                    ),
                )
            )
            is None
        )

    def test_a_walrus_makes_the_test_and_the_name_unknown(self):
        assert (
            fold(
                (
                    Assign("a", Literal(None)),
                    If((Branch(UNKNOWN, ("a",), ()),)),
                    If((Branch(IsNone(NameRef("a")), (), (Return(True),)),)),
                    Return(False),
                )
            )
            == GUARD_UNKNOWN
        )

    def test_a_loops_returns_stay_reachable(self):
        assert fold((Opaque(("y",), (False,)), Return(True))) == GUARD_UNKNOWN

    def test_a_statement_that_binds_makes_its_names_unknown(self):
        assert (
            fold(
                (
                    Assign("a", Literal(None)),
                    Binds(("a",)),
                    If((Branch(IsNone(NameRef("a")), (), (Return(True),)),)),
                    Return(False),
                )
            )
            == GUARD_UNKNOWN
        )

    def test_no_reachable_return_at_all(self):
        assert fold((Raise(),)) == GUARD_UNKNOWN

    def test_a_method_skips_the_receiver(self):
        assert (
            fold(
                (
                    If((Branch(NameRef("x"), (), (Return(False),)),)),
                    Return(True),
                ),
                params=(Param("self"), Param("x", False)),
                method=True,
            )
            is None
        )

    def test_a_method_refuses_any_positional(self):
        assert (
            fold(
                (Return(True),),
                params=(Param("self"), Param("x", False)),
                bound=Bound(args=("a",)),
                method=True,
            )
            == METHOD_POSITIONAL
        )

    def test_more_positionals_than_parameters_is_no_call_to_fold(self):
        assert fold((Return(True),), bound=Bound(args=("a",))) == GUARD_UNKNOWN


class TestTheFoldDraws:
    """ADR-148 through the whole rule: the same edge, one tier down from
    the index as ever, and a ``via`` that says which reading drew it."""

    def test_a_module_caller_and_a_function_caller(self, tmp_path):
        drawn, counts = run(
            tmp_path,
            files(deco=FOLDING_DECO, app=FOLDING_APP),
            (edge(), edge(line=10, source="app.outer")),
        )
        assert drawn == [
            {
                "from": "app",
                "to": "pkg.deco.factory.decorator",
                "path": "app.py",
                "line": 4,
                "via": DECORATOR_FACTORY_FOLDED,
                "factory": "pkg.deco.factory",
            },
            {
                "from": "app.outer",
                "to": "pkg.deco.factory.decorator",
                "path": "app.py",
                "line": 10,
                "via": DECORATOR_FACTORY_FOLDED,
                "factory": "pkg.deco.factory",
            },
        ]
        assert (counts["drawn"], counts["folded"]) == (2, 2)
        assert sum(counts["refused"].values()) == 0

    def test_a_factory_adr_147_settles_is_not_counted_as_folded(self, tmp_path):
        drawn, counts = run(tmp_path, files(app=SIMPLE_APP), (edge(),))
        assert [call["via"] for call in drawn] == [DECORATOR_FACTORY]
        assert (counts["drawn"], counts["folded"]) == (1, 0)

    def test_an_argument_the_fold_cannot_read_refuses(self, tmp_path):
        app = (
            "from pkg.deco import factory\n"
            "\n"
            "\n"
            "@factory(one)\n"
            "def two():\n"
            "    return 2\n"
        )
        drawn, counts = run(tmp_path, files(deco=FOLDING_DECO, app=app), (edge(),))
        assert drawn == []
        assert counts["refused"][GUARD_UNKNOWN] == 1

    def test_a_module_that_binds_callable_refuses(self, tmp_path):
        # The guard reads someone else's `callable`, so what it answers
        # is not the builtin's answer and the fold abstains.
        deco = "from shims import callable\n\n\n" + FOLDING_DECO
        drawn, counts = run(tmp_path, files(deco=deco, app=SIMPLE_APP), (edge(),))
        assert drawn == []
        assert counts["refused"][GUARD_UNKNOWN] == 1

    def test_a_method_factory_draws_with_no_positional(self, tmp_path):
        app = (
            "from pkg.deco import Registry\n"
            "\n"
            "registry = Registry()\n"
            "\n"
            "\n"
            "@registry.command()\n"
            "def one():\n"
            "    return 1\n"
        )
        drawn, counts = run(
            tmp_path,
            files(deco=FOLDING_METHOD_DECO, app=app),
            (edge(target="pkg.deco.Registry.command", line=6),),
        )
        assert [(call["to"], call["via"]) for call in drawn] == [
            ("pkg.deco.Registry.command.decorator", DECORATOR_FACTORY_FOLDED)
        ]
        assert (counts["drawn"], counts["folded"]) == (1, 1)

    def test_a_method_factory_refuses_a_positional(self, tmp_path):
        # `@obj.m("x")` and `@Cls.m("x")` are one text to lane A, and in
        # the second `"x"` is `self`.
        app = (
            "from pkg.deco import Registry\n"
            "\n"
            "registry = Registry()\n"
            "\n"
            "\n"
            '@registry.command("x")\n'
            "def one():\n"
            "    return 1\n"
        )
        drawn, counts = run(
            tmp_path,
            files(deco=FOLDING_METHOD_DECO, app=app),
            (edge(target="pkg.deco.Registry.command", line=6),),
        )
        assert drawn == []
        assert counts["refused"][METHOD_POSITIONAL] == 1

    def test_the_fold_reads_the_digests_the_walk_wrote(self, tmp_path):
        # The unit cases above hand-build their digests; this one is the
        # seam, so a walk that stopped writing `bound` or `inner_fold`
        # could not pass both.
        parsed = parse_source(FOLDING_DECO.encode())
        factory = next(s for s in parsed.symbols if s.qualname == "factory")
        (site,) = parse_source(SIMPLE_APP.encode()).symbols[0].decorators
        assert factory.returns_inner is None
        assert fold_guards(factory.inner_fold, site.bound, False) is None


class TestTheInnerDefMustBeOneSymbol:
    def test_an_inner_qualname_written_twice_draws_nothing(self, tmp_path):
        # The stub carries a `decorator` of its own, so `factory.decorator`
        # is two definitions collapsed into one record: no id to trust.
        deco = (
            "import typing as t\n"
            "\n"
            "\n"
            "@t.overload\n"
            "def factory(label: str):\n"
            "    def decorator(fn):\n"
            "        return fn\n"
            "\n"
            "    return decorator\n"
            "\n"
            "\n"
            "def factory(label):\n"
            "    def decorator(fn):\n"
            "        return fn\n"
            "\n"
            "    return decorator\n"
        )
        drawn, counts = run(tmp_path, files(deco=deco, app=SIMPLE_APP), (edge(),))
        assert drawn == []
        assert counts["refused"][NO_SYMBOL] == 1


class TestTheJoinsEdgeStands:
    def test_a_pair_the_graph_already_carries_is_left_alone(self, tmp_path):
        existing = tiered_edge(
            "app",
            "pkg.deco.factory.decorator",
            "calls",
            [{"path": "app.py", "line": 4}],
            tier=SEMANTIC,
            lane=LANE_SCIP,
        )
        drawn, counts = run(
            tmp_path, files(app=SIMPLE_APP), (edge(), existing)
        )
        assert drawn == []
        assert counts["refused"][ALREADY_DRAWN] == 1


class TestWhatIsNotAsked:
    """Nothing reached the rule, so there is nothing to refuse and no block
    to write: a count of zeroes would say the rule had been asked."""

    def test_a_bare_decorator_never_asks(self, tmp_path):
        # `@f` applies `f` itself — ADR-146's edge, at the semantic tier.
        # What `f` would have returned is not applied to anything.
        app = "from pkg.deco import factory\n\n\n@factory\ndef one():\n    return 1\n"
        drawn, counts = run(tmp_path, files(app=app), (edge(),))
        assert (drawn, counts) == ([], {})

    def test_a_callee_the_walk_cannot_name_asks_nothing(self, tmp_path):
        app = (
            "from pkg.deco import factory\n"
            "\n"
            "decos = [factory]\n"
            "\n"
            "\n"
            '@decos[0]("a")\n'
            "def one():\n"
            "    return 1\n"
        )
        drawn, counts = run(tmp_path, files(app=app), (edge(line=6),))
        assert (drawn, counts) == ([], {})

    def test_a_chain_wrapped_across_lines_asks_nothing(self, tmp_path):
        app = (
            "from pkg import deco\n"
            "\n"
            "\n"
            "@deco.\\\n"
            '    factory("a")\n'
            "def one():\n"
            "    return 1\n"
        )
        drawn, counts = run(tmp_path, files(app=app), (edge(line=5),))
        assert (drawn, counts) == ([], {})


def calls(graph):
    """Every ``calls`` edge, keyed by its (from, to) pair."""
    return {
        (e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "calls"
    }


@pytest.mark.lane_b
def test_the_minideco_factories_are_called_and_the_refusals_are_counted():
    """End to end with the index running. Eight applications are drawn,
    each one ``calls`` / ``syntactic``: three ADR-147 settles from the
    factory's shape alone — ``@factory("a")`` at the module,
    ``@factory("c")`` inside ``outer``, ``@registry.register("b")`` —
    and five ADR-148 folds over the site's own arguments, evidenced
    ``decorator-factory-folded``.

    What is refused is counted at the site: ``@optional(TAG)`` passes a
    name the fold cannot read, ``@either("d")`` reaches the return that
    calls ``decorator`` itself — a ``guard-unknown`` where ADR-147
    counted it ``no-returned-def``, the whole factory having been refused
    before a site was looked at — and ``wrapped`` is decorated, which no
    fold changes."""
    from hobbes.extract import containment, extract_repo

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINIDECO).graph
    drawn = calls(graph)
    err = [
        e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")
    ]
    expected = {
        ("minideco.app", "minideco.deco.factory.decorator"): [
            (19, DECORATOR_FACTORY)
        ],
        ("minideco.app", "minideco.deco.Registry.register.decorator"): [
            (24, DECORATOR_FACTORY)
        ],
        ("minideco.app.outer", "minideco.deco.factory.decorator"): [
            (30, DECORATOR_FACTORY)
        ],
        ("minideco.app", "minideco.deco.optional.decorator"): [
            (63, DECORATOR_FACTORY_FOLDED),
            (68, DECORATOR_FACTORY_FOLDED),
        ],
        ("minideco.app", "minideco.deco.Registry.command.decorator"): [
            (83, DECORATOR_FACTORY_FOLDED)
        ],
        ("minideco.app", "minideco.deco.either.decorator"): [
            (88, DECORATOR_FACTORY_FOLDED)
        ],
        ("minideco.app.folding", "minideco.deco.optional.decorator"): [
            (94, DECORATOR_FACTORY_FOLDED)
        ],
    }
    for pair, evidence in expected.items():
        found = drawn.get(pair)
        assert found is not None, (pair, err)
        assert found["tier"] == SYNTACTIC, (pair, err)
        assert [
            (row["line"], row.get("via")) for row in found["evidence"]
        ] == evidence, (pair, err)
    # The refused sites draw nothing to the inner defs: `wrapped`'s is
    # never reached from `app` at all, and `either`'s is reached from the
    # one folded site above and from nowhere else — `@either("d")` on
    # line 37 drew nothing. (`app` does call `either`, `wrapped` and
    # `optional` themselves — ADR-146 — and each of their bodies calls
    # its own `decorator` by name; those stand.)
    assert [
        pair
        for pair in drawn
        if pair[0].startswith("minideco.app")
        and pair[1].startswith("minideco.deco.wrapped.")
    ] == []
    counts = graph["decorators"]["factory_calls"]
    assert (counts["drawn"], counts["folded"]) == (8, 5)
    assert counts["refused"][GUARD_UNKNOWN] == 2  # `@either("d")`, `@optional(TAG)`
    assert counts["refused"][DECORATED] == 1  # wrapped
    assert counts["refused"][NO_RETURNED_DEF] == 0
    assert sum(counts["refused"].values()) == 3


def test_minideco_draws_nothing_without_the_index():
    """Condition 1 is the index's edge, so lane A alone asks nothing at
    all and the block is absent — not a row of zeroes."""
    from hobbes.extract import extract_repo

    graph = extract_repo(MINIDECO).graph
    assert [pair for pair in calls(graph) if pair[1].endswith(".decorator")] == []
    assert "decorators" not in graph


def test_a_module_level_application_is_drawn_from_the_module_node():
    """A top-level `@factory("a")` runs at import, and its caller is the
    module *node*, not a symbol. The edge append once kept symbol callers
    only, as ADR-145's does, and the block counted rows the graph did not
    hold — caught on the host by the `lane_b` case above, pinned here
    where no index is needed."""
    from hobbes.extract import _add_factory_call_edges

    graph = {
        "nodes": [{"id": "pkg.app", "kind": "module"}],
        "symbols": [{"id": "pkg.deco.factory.decorator", "kind": "function"}],
        "symbol_edges": [],
    }
    row = {
        "from": "pkg.app",
        "to": "pkg.deco.factory.decorator",
        "path": "src/pkg/app.py",
        "line": 3,
        "via": DECORATOR_FACTORY,
        "factory": "pkg.deco.factory",
    }
    _add_factory_call_edges(graph, [row, {**row, "from": "pkg.nowhere"}])
    (edge,) = graph["symbol_edges"]
    assert (edge["from"], edge["to"], edge["tier"]) == (
        "pkg.app",
        "pkg.deco.factory.decorator",
        SYNTACTIC,
    )
