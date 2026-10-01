"""A ``with`` statement's ``__enter__`` and ``__exit__``, where the item's
class is known (ADR-156, C-174).

Two halves. Lane A records each sync ``with`` item that is a call — its
scope, its own call's line and the name that call writes — and each
``def``'s return annotation head; the cases below pin every form ADR-156
step 1 reads and every form it leaves ``None``. The rule,
:func:`hobbes.extract.withstmt.with_calls`, is then handed a graph whose
``semantic`` edges are written out, because those edges are exactly what it
is allowed to believe, and each abstention has a case of its own.

The last case is rich v15.0.0's ``Capture`` / ``Console.capture``,
verbatim but for the elisions its constant names: the shape the held-out
cell measured.
"""

from hobbes.extract import _add_with_call_edges
from hobbes.extract.discover import discover_modules
from hobbes.extract.fixtures import MULTIPLE_BASES
from hobbes.extract.graph import build_graph
from hobbes.extract.pysource import parse_source
from hobbes.extract.schema import LANE_SCIP, SEMANTIC, SYNTACTIC, tiered_edge
from hobbes.extract.withstmt import (
    ALREADY_DRAWN,
    ANNOTATION_UNRESOLVED,
    NO_ANNOTATION,
    NO_CALL_EDGE,
    REASONS,
    WITH,
    with_calls,
)


def line_of(text: str, needle: str, nth: int = 0) -> int:
    """The 1-based line of the *nth* line of *text* holding *needle*, so no
    case pins a literal line number."""
    return [i + 1 for i, line in enumerate(text.splitlines()) if needle in line][nth]


def items(source: str) -> list[tuple]:
    return [(i.scope, i.line, i.name) for i in parse_source(source.encode()).with_items]


def returns(source: str, qualname: str = "f"):
    symbols = {s.qualname: s for s in parse_source(source.encode()).symbols}
    return symbols[qualname].returns


class TestLaneARecordsTheItems:
    def test_a_constructor(self):
        assert items("def f(x):\n    with Live(x):\n        pass\n") == [("f", 2, "Live")]

    def test_a_method_call_with_a_target(self):
        source = "def f(console):\n    with console.capture() as c:\n        pass\n"
        assert items(source) == [("f", 2, "capture")]

    def test_the_items_own_call_never_an_inner_one(self):
        source = 'def f(app):\n    with app.test_client().get("/") as rv:\n        pass\n'
        assert items(source) == [("f", 2, "get")]

    def test_two_items_are_two_records(self):
        assert items("def f():\n    with A(), B():\n        pass\n") == [
            ("f", 2, "A"),
            ("f", 2, "B"),
        ]

    def test_a_bare_name_records_nothing(self):
        assert items("def f(ctx):\n    with ctx:\n        pass\n") == []

    def test_async_with_records_nothing(self):
        assert items("async def f():\n    async with X():\n        pass\n") == []

    def test_a_module_level_item_has_no_scope(self):
        assert items("with open(p):\n    pass\n") == [(None, 1, "open")]

    def test_the_line_is_the_items_call_records_line(self):
        """The item's line is the one its own :class:`Call` carries — the
        callee's terminal identifier, where a wrapped chain puts it."""
        source = "def f(a):\n    with (a\n          .b\n          .open()):\n        pass\n"
        parsed = parse_source(source.encode())
        (item,) = parsed.with_items
        call = next(c for c in parsed.calls if c.callee == "a.b.open")
        assert (item.line, item.name) == (call.line, "open")


class TestLaneARecordsTheReturnAnnotation:
    def test_a_name(self):
        assert returns("def f() -> C:\n    pass\n") == ("C", 1)

    def test_a_string(self):
        assert returns('def f() -> "C":\n    pass\n') == ("C", 1)

    def test_a_dotted_name(self):
        assert returns("def f() -> mod.C:\n    pass\n") == ("C", 1)

    def test_a_string_holding_a_dotted_name(self):
        assert returns('def f() -> "pkg.mod.C":\n    pass\n') == ("C", 1)

    def test_a_subscript(self):
        assert returns("def f() -> C[int]:\n    pass\n") == ("C", 1)

    def test_optional_is_none(self):
        assert returns("def f() -> Optional[C]:\n    pass\n") is None

    def test_a_union_is_none(self):
        assert returns("def f() -> A | B:\n    pass\n") is None

    def test_no_annotation_is_none(self):
        assert returns("def f():\n    pass\n") is None

    def test_none_and_a_call_and_a_string_of_two_names_are_none(self):
        assert returns("def f() -> None:\n    pass\n") is None
        assert returns("def f() -> g():\n    pass\n") is None
        assert returns('def f() -> "A | B":\n    pass\n') is None

    def test_a_multi_line_signature_records_the_annotations_line(self):
        source = "def f(\n    a,\n    b,\n) -> C:\n    pass\n"
        assert returns(source) == ("C", line_of(source, "-> C"))

    def test_a_class_has_none(self):
        assert returns("class K:\n    pass\n", "K") is None


#: The classes and the factory every rule case reads.
CTX = (
    "class Box:\n"
    "    def __enter__(self):\n"
    "        return self\n"
    "\n"
    "    def __exit__(self, *a):\n"
    "        pass\n"
    "\n"
    "\n"
    "def make() -> Box:\n"
    "    return Box()\n"
    "\n"
    "\n"
    "def test_client() -> Box:\n"
    "    return Box()\n"
    "\n"
    "\n"
    "class Base:\n"
    "    def __exit__(self, *a):\n"
    "        pass\n"
    "\n"
    "\n"
    "class Sub(Base):\n"
    "    def __enter__(self):\n"
    "        return self\n"
    "\n"
    "\n"
    "class Other:\n"
    "    pass\n"
    "\n"
    "\n"
    "class Two(Base, Other):\n"
    "    def __exit__(self, *a):\n"
    "        pass\n"
)

USE = (
    "from pkg.ctx import Box, Sub, Two, make\n"
    "\n"
    "\n"
    "def f(app):\n"
    "    with Box():\n"
    "        pass\n"
    "    with make():\n"
    "        pass\n"
    '    with app.test_client().get("/"):\n'
    "        pass\n"
    "    with Sub():\n"
    "        pass\n"
    "    with Two():\n"
    "        pass\n"
)

CTX_PATH = "pkg/ctx.py"
USE_PATH = "pkg/use.py"
F = "pkg.use.f"
BOX_LINE = line_of(USE, "with Box()")
MAKE_LINE = line_of(USE, "with make()")
GET_LINE = line_of(USE, ".get(")
SUB_LINE = line_of(USE, "with Sub()")
TWO_LINE = line_of(USE, "with Two()")
MAKE_ANNOTATION = line_of(CTX, "def make()")
CLIENT_ANNOTATION = line_of(CTX, "def test_client()")
SUB_HEADER = line_of(CTX, "class Sub(")


def semantic(source: str, target: str, edge_type: str, path: str, line: int) -> dict:
    """One edge as the index draws it."""
    return tiered_edge(
        source, target, edge_type, [{"path": path, "line": line}], tier=SEMANTIC, lane=LANE_SCIP
    )


def call(target: str, line: int) -> dict:
    """The index's edge at one of ``f``'s items."""
    return semantic(F, target, "calls", USE_PATH, line)


def run(tmp_path, edges: tuple = (), tree: dict | None = None):
    """Write the tree, then run the rule over the symbols lane A found and
    exactly the *edges* handed in — :func:`build_graph` draws no symbol edge
    (the join is their only producer), so the graph a case builds is the
    graph the rule reads."""
    tree = tree if tree is not None else {"pkg/__init__.py": "", CTX_PATH: CTX, USE_PATH: USE}
    for name, text in tree.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    modules = discover_modules(tmp_path)
    parsed = {m.id: parse_source((tmp_path / m.path).read_bytes()) for m in modules}
    graph = build_graph(modules, parsed)
    return with_calls(modules, parsed, graph["symbols"], list(edges))


def pairs(rows: list[dict]) -> list[tuple]:
    return [(r["from"], r["to"], r["path"], r["line"]) for r in rows]


class TestTheRuleDraws:
    def test_a_constructor_whose_class_defines_both(self, tmp_path):
        rows, counts = run(tmp_path, (call("pkg.ctx.Box", BOX_LINE),))
        assert pairs(rows) == [
            (F, "pkg.ctx.Box.__enter__", USE_PATH, BOX_LINE),
            (F, "pkg.ctx.Box.__exit__", USE_PATH, BOX_LINE),
        ]
        assert counts["drawn"] == 2
        assert counts["items"] == 5
        assert set(counts["abstained"]) == set(REASONS)

    def test_a_factory_whose_annotation_names_the_class(self, tmp_path):
        edges = (
            call("pkg.ctx.make", MAKE_LINE),
            semantic("pkg.ctx.make", "pkg.ctx.Box", "uses", CTX_PATH, MAKE_ANNOTATION),
        )
        rows, counts = run(tmp_path, edges)
        assert pairs(rows) == [
            (F, "pkg.ctx.Box.__enter__", USE_PATH, MAKE_LINE),
            (F, "pkg.ctx.Box.__exit__", USE_PATH, MAKE_LINE),
        ]
        assert counts["drawn"] == 2

    def test_a_uses_edge_at_another_line_does_not_resolve_it(self, tmp_path):
        edges = (
            call("pkg.ctx.make", MAKE_LINE),
            semantic("pkg.ctx.make", "pkg.ctx.Box", "uses", CTX_PATH, MAKE_ANNOTATION + 1),
        )
        rows, counts = run(tmp_path, edges)
        assert rows == []
        assert counts["abstained"][ANNOTATION_UNRESOLVED] == 1

    def test_an_inner_call_on_the_line_is_not_the_items(self, tmp_path):
        """``app.test_client().get(…)``: the index answers at
        ``test_client``, whose annotation names ``Box`` — and the item's own
        call is ``get``. Binding to the line rather than the call read
        ``FlaskClient.__exit__`` five times wrong on flask."""
        edges = (
            call("pkg.ctx.test_client", GET_LINE),
            semantic("pkg.ctx.test_client", "pkg.ctx.Box", "uses", CTX_PATH, CLIENT_ANNOTATION),
        )
        rows, counts = run(tmp_path, edges)
        assert rows == []
        assert counts["abstained"][NO_CALL_EDGE] == counts["items"]

    def test_a_method_on_the_single_named_base(self, tmp_path):
        edges = (
            call("pkg.ctx.Sub", SUB_LINE),
            semantic("pkg.ctx.Sub", "pkg.ctx.Base", "uses", CTX_PATH, SUB_HEADER),
        )
        rows, _ = run(tmp_path, edges)
        assert pairs(rows) == [
            (F, "pkg.ctx.Base.__exit__", USE_PATH, SUB_LINE),
            (F, "pkg.ctx.Sub.__enter__", USE_PATH, SUB_LINE),
        ]

    def test_two_bases_stop_the_walk(self, tmp_path):
        rows, counts = run(tmp_path, (call("pkg.ctx.Two", TWO_LINE),))
        assert pairs(rows) == [(F, "pkg.ctx.Two.__exit__", USE_PATH, TWO_LINE)]
        assert counts["abstained"][MULTIPLE_BASES] == 1

    def test_a_pair_already_drawn_is_left_alone(self, tmp_path):
        edges = (
            call("pkg.ctx.Box", BOX_LINE),
            call("pkg.ctx.Box.__enter__", BOX_LINE),
        )
        rows, counts = run(tmp_path, edges)
        assert pairs(rows) == [(F, "pkg.ctx.Box.__exit__", USE_PATH, BOX_LINE)]
        assert counts["abstained"][ALREADY_DRAWN] == 1

    def test_an_unannotated_factory_abstains(self, tmp_path):
        ctx = CTX.replace("def make() -> Box:", "def make():")
        tree = {"pkg/__init__.py": "", CTX_PATH: ctx, USE_PATH: USE}
        rows, counts = run(tmp_path, (call("pkg.ctx.make", MAKE_LINE),), tree)
        assert rows == []
        assert counts["abstained"][NO_ANNOTATION] == 1

    def test_no_items_is_no_block(self, tmp_path):
        tree = {"pkg/__init__.py": "", CTX_PATH: CTX}
        assert run(tmp_path, (), tree) == ([], {})

    def test_without_semantic_edges_nothing_is_drawn(self, tmp_path):
        rows, counts = run(tmp_path)
        assert rows == []
        assert counts["drawn"] == 0
        assert counts["abstained"][NO_CALL_EDGE] == counts["items"]


class TestTheEdgesAreDrawn:
    def test_one_syntactic_calls_edge_per_pair_marked_with(self):
        graph = {
            "nodes": [{"id": "m"}],
            "symbols": [{"id": "m.K.__exit__"}, {"id": "m.f"}],
            "symbol_edges": [],
        }
        rows = [
            {"from": "m.f", "to": "m.K.__exit__", "path": "m.py", "line": 4},
            {"from": "m.f", "to": "m.K.__exit__", "path": "m.py", "line": 2},
            {"from": "m", "to": "m.K.__exit__", "path": "m.py", "line": 9},
            {"from": "m.f", "to": "nowhere", "path": "m.py", "line": 2},
        ]
        _add_with_call_edges(graph, rows)
        assert [(e["from"], e["to"], e["type"], e["tier"]) for e in graph["symbol_edges"]] == [
            ("m", "m.K.__exit__", "calls", SYNTACTIC),
            ("m.f", "m.K.__exit__", "calls", SYNTACTIC),
        ]
        assert [(r["line"], r["via"]) for r in graph["symbol_edges"][1]["evidence"]] == [
            (2, WITH),
            (4, WITH),
        ]


#: rich v15.0.0 ``rich/console.py``: ``Capture`` (lines 310–341) and
#: ``Console.capture`` (1096–1111), verbatim but for the elisions —
#: ``CaptureError``, the docstring's example and ``Console``'s other
#: members; ``begin_capture``, ``end_capture`` and ``use`` are the
#: excerpt's own, so it parses and runs on its own.
RICH_EXCERPT = '''from types import TracebackType
from typing import Optional, Type


class Capture:
    """Context manager to capture the result of printing to the console.
    See :meth:`~rich.console.Console.capture` for how to use.

    Args:
        console (Console): A console instance to capture output.
    """

    def __init__(self, console: "Console") -> None:
        self._console = console
        self._result: Optional[str] = None

    def __enter__(self) -> "Capture":
        self._console.begin_capture()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self._result = self._console.end_capture()

    def get(self) -> str:
        """Get the result of the capture."""
        return self._result


class Console:
    def begin_capture(self) -> None:
        pass

    def end_capture(self) -> str:
        return ""

    def capture(self) -> Capture:
        """A context manager to *capture* the result of print() or log() in a string,
        rather than writing it to the console.
        """
        capture = Capture(self)
        return capture


def use(console: Console) -> str:
    with console.capture() as capture:
        pass
    return capture.get()
'''

RICH_CAPTURE_DEF = line_of(RICH_EXCERPT, "def capture(self) -> Capture:")
RICH_WITH = line_of(RICH_EXCERPT, "with console.capture() as capture:")


class TestTheRealSource:
    def test_rich_capture(self):
        parsed = parse_source(RICH_EXCERPT.encode())
        symbols = {s.qualname: s for s in parsed.symbols}
        assert symbols["Console.capture"].returns == ("Capture", RICH_CAPTURE_DEF)
        assert symbols["Capture.__enter__"].returns == (
            "Capture",
            line_of(RICH_EXCERPT, "def __enter__"),
        )
        # `-> None` names no class.
        assert symbols["Capture.__exit__"].returns is None
        assert [(i.scope, i.line, i.name) for i in parsed.with_items] == [
            ("use", RICH_WITH, "capture")
        ]
