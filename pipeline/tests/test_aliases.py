"""A call through a local alias, drawn to what the alias's right-hand side
names (ADR-160, C-9).

The rule, :func:`hobbes.extract.aliases.alias_calls`, is handed a graph
whose ``semantic`` edges are written out, because those edges are exactly
what it is allowed to believe; each abstention, and each edge it must not
read, has a case of its own. Lane A's fact is pinned in
``test_pysource.py``.
"""

from hobbes.extract import _add_alias_call_edges
from hobbes.extract.aliases import (
    ALIAS,
    ALREADY_DRAWN,
    AMBIGUOUS_RHS,
    NO_RHS_EDGE,
    REASONS,
    alias_calls,
)
from hobbes.extract.discover import discover_modules
from hobbes.extract.graph import build_graph
from hobbes.extract.pysource import parse_source
from hobbes.extract.schema import (
    LANE_SCIP,
    LANE_TREE_SITTER,
    SEMANTIC,
    SYNTACTIC,
    tiered_edge,
)


def line_of(text: str, needle: str, nth: int = 0) -> int:
    """The 1-based line of the *nth* line of *text* holding *needle*, so no
    case pins a literal line number."""
    return [i + 1 for i, line in enumerate(text.splitlines()) if needle in line][nth]


SEG = (
    "class Segment:\n"
    "    pass\n"
    "\n"
    "\n"
    "def cell_len(text):\n"
    "    return len(text)\n"
)

USE = (
    "from pkg.seg import Segment, cell_len\n"
    "\n"
    "\n"
    "def f(texts):\n"
    "    _Segment = Segment\n"
    "    first = _Segment(texts)\n"
    "    return [_Segment(t) for t in texts]\n"
    "\n"
    "\n"
    "def g(text):\n"
    "    _len = cell_len\n"
    "    return _len(text)\n"
    "\n"
    "\n"
    "class Box:\n"
    "    def get_style(self, name):\n"
    "        return name\n"
    "\n"
    "    def m(self):\n"
    "        get_style = self.get_style\n"
    '        return get_style("x")\n'
    "\n"
    "    def k(self):\n"
    "        _Seg = Segment\n"
    "        return _Seg()\n"
)

SEG_PATH = "pkg/seg.py"
USE_PATH = "pkg/use.py"
F = "pkg.use.f"
G = "pkg.use.g"
M = "pkg.use.Box.m"
K = "pkg.use.Box.k"
SEGMENT = "pkg.seg.Segment"
CELL_LEN = "pkg.seg.cell_len"
GET_STYLE = "pkg.use.Box.get_style"

F_ALIAS = line_of(USE, "_Segment = Segment")
F_FIRST = line_of(USE, "first = _Segment(")
F_COMPREHENSION = line_of(USE, "[_Segment(t)")
G_ALIAS = line_of(USE, "_len = cell_len")
G_CALL = line_of(USE, "return _len(")
M_ALIAS = line_of(USE, "get_style = self.get_style")
M_CALL = line_of(USE, 'get_style("x")')
K_ALIAS = line_of(USE, "_Seg = Segment")
K_CALL = line_of(USE, "return _Seg()")

#: Every site in ``USE``: f's two, g's, m's and k's.
SITES = 5


def semantic(source: str, target: str, line: int, edge_type: str = "uses") -> dict:
    """One edge as the index draws it, in ``use.py``."""
    return tiered_edge(
        source, target, edge_type, [{"path": USE_PATH, "line": line}], tier=SEMANTIC, lane=LANE_SCIP
    )


def run(tmp_path, edges: tuple = (), use: str = USE):
    """Write the tree, then run the rule over the symbols lane A found and
    exactly the *edges* handed in — :func:`build_graph` draws no symbol edge
    (the join is their only producer), so the graph a case builds is the
    graph the rule reads."""
    tree = {"pkg/__init__.py": "", SEG_PATH: SEG, USE_PATH: use}
    for name, text in tree.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    modules = discover_modules(tmp_path)
    parsed = {m.id: parse_source((tmp_path / m.path).read_bytes()) for m in modules}
    graph = build_graph(modules, parsed)
    return alias_calls(modules, parsed, graph["symbols"], list(edges))


def pairs(rows: list[dict]) -> list[tuple]:
    return [(r["from"], r["to"], r["path"], r["line"]) for r in rows]


class TestTheRuleDraws:
    def test_a_function_to_a_class_at_every_site(self, tmp_path):
        """One site in a comprehension: lane A's scope is the innermost
        definition, so it is ``f``'s."""
        rows, counts = run(tmp_path, (semantic(F, SEGMENT, F_ALIAS),))
        assert pairs(rows) == [
            (F, SEGMENT, USE_PATH, F_FIRST),
            (F, SEGMENT, USE_PATH, F_COMPREHENSION),
        ]
        assert counts["aliases"] == 4
        assert counts["sites"] == SITES
        assert counts["drawn"] == 2
        assert counts["abstained"][NO_RHS_EDGE] == SITES - 2
        assert set(counts["abstained"]) == set(REASONS)

    def test_a_function_to_a_function(self, tmp_path):
        rows, _ = run(tmp_path, (semantic(G, CELL_LEN, G_ALIAS),))
        assert pairs(rows) == [(G, CELL_LEN, USE_PATH, G_CALL)]

    def test_a_method_to_a_method(self, tmp_path):
        rows, _ = run(tmp_path, (semantic(M, GET_STYLE, M_ALIAS),))
        assert pairs(rows) == [(M, GET_STYLE, USE_PATH, M_CALL)]

    def test_a_method_to_a_class(self, tmp_path):
        """R's last name, not N, is what the target's last name must be."""
        rows, _ = run(tmp_path, (semantic(K, SEGMENT, K_ALIAS),))
        assert pairs(rows) == [(K, SEGMENT, USE_PATH, K_CALL)]


class TestTheRuleAbstains:
    def test_no_edge_at_the_right_hand_side(self, tmp_path):
        rows, counts = run(tmp_path)
        assert rows == []
        assert counts["drawn"] == 0
        assert counts["abstained"][NO_RHS_EDGE] == SITES

    def test_two_targets_named_alike_are_ambiguous(self, tmp_path):
        edges = (
            semantic(G, CELL_LEN, G_ALIAS),
            semantic(G, "pkg.other.cell_len", G_ALIAS),
        )
        rows, counts = run(tmp_path, edges)
        assert rows == []
        assert counts["abstained"][AMBIGUOUS_RHS] == 1

    def test_one_target_twice_is_not_ambiguous(self, tmp_path):
        """A ``uses`` and a ``calls`` at R naming one target are one target;
        the ``calls`` edge is the pair itself, so the site is drawn already."""
        edges = (
            semantic(G, CELL_LEN, G_ALIAS),
            semantic(G, CELL_LEN, G_ALIAS, "calls"),
        )
        rows, counts = run(tmp_path, edges)
        assert rows == []
        assert counts["abstained"][AMBIGUOUS_RHS] == 0
        assert counts["abstained"][ALREADY_DRAWN] == 1

    def test_a_pair_already_drawn_is_left_alone(self, tmp_path):
        edges = (
            semantic(G, CELL_LEN, G_ALIAS),
            semantic(G, CELL_LEN, G_CALL, "calls"),
        )
        rows, counts = run(tmp_path, edges)
        assert rows == []
        assert counts["abstained"][ALREADY_DRAWN] == 1

    def test_a_syntactic_edge_at_the_right_hand_side_is_not_read(self, tmp_path):
        edge = tiered_edge(
            G,
            CELL_LEN,
            "uses",
            [{"path": USE_PATH, "line": G_ALIAS}],
            tier=SYNTACTIC,
            lane=LANE_TREE_SITTER,
        )
        rows, counts = run(tmp_path, (edge,))
        assert rows == []
        assert counts["abstained"][NO_RHS_EDGE] == SITES

    def test_an_edge_from_another_scope_is_not_read(self, tmp_path):
        """``f``'s right-hand side, drawn from ``g`` at ``f``'s line."""
        rows, counts = run(tmp_path, (semantic(G, SEGMENT, F_ALIAS),))
        assert rows == []
        assert counts["abstained"][NO_RHS_EDGE] == SITES

    def test_the_evidence_line_must_be_the_assignments(self, tmp_path):
        rows, _ = run(tmp_path, (semantic(G, CELL_LEN, G_ALIAS + 1),))
        assert rows == []

    def test_a_target_of_another_name_is_not_read(self, tmp_path):
        rows, _ = run(tmp_path, (semantic(G, "pkg.seg.other_len", G_ALIAS),))
        assert rows == []


class TestTheCounts:
    def test_no_alias_anywhere_is_an_empty_block(self, tmp_path):
        use = "from pkg.seg import cell_len\n\n\ndef f(t):\n    return cell_len(t)\n"
        rows, counts = run(tmp_path, use=use)
        assert (rows, counts) == ([], {})

    def test_the_rows_are_deterministic_and_sorted(self, tmp_path):
        edges = (
            semantic(M, GET_STYLE, M_ALIAS),
            semantic(K, SEGMENT, K_ALIAS),
            semantic(G, CELL_LEN, G_ALIAS),
            semantic(F, SEGMENT, F_ALIAS),
        )
        rows, counts = run(tmp_path, edges)
        again, _ = run(tmp_path, tuple(reversed(edges)))
        assert rows == again
        assert pairs(rows) == sorted(pairs(rows))
        assert [r["from"] for r in rows] == [K, M, F, F, G]
        assert counts["drawn"] == SITES


class TestTheEdgesDrawn:
    def test_one_syntactic_calls_edge_per_pair_with_every_site(self):
        graph = {
            "symbols": [{"id": F}, {"id": SEGMENT}],
            "nodes": [],
            "symbol_edges": [],
        }
        rows = [
            {"from": F, "to": SEGMENT, "path": USE_PATH, "line": F_COMPREHENSION},
            {"from": F, "to": SEGMENT, "path": USE_PATH, "line": F_FIRST},
            {"from": F, "to": "pkg.gone", "path": USE_PATH, "line": F_FIRST},
        ]
        _add_alias_call_edges(graph, rows)
        (edge,) = graph["symbol_edges"]
        assert (edge["from"], edge["to"], edge["type"]) == (F, SEGMENT, "calls")
        assert edge["tier"] == SYNTACTIC
        assert edge["evidence"] == [
            {"path": USE_PATH, "line": F_FIRST, "via": ALIAS, "lane": LANE_TREE_SITTER},
            {"path": USE_PATH, "line": F_COMPREHENSION, "via": ALIAS, "lane": LANE_TREE_SITTER},
        ]
