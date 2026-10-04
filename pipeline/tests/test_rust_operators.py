"""A Rust operator applied to a repo impl is a call where rust-analyzer names
the impl's method at the operator token (ADR-178, C-174 narrowed).

hecs, probed: rust-analyzer writes a reference named ``deref`` at the ``*``
of ``*world.get::<&T>(e).unwrap()``, onto ``impl Deref for Ref``'s method;
no call site claims it, so before this rule it was a ``uses`` edge. Lane A
records the file's operator tokens (expressions and macro token trees);
the join turns a reference named for an operator method, at exactly a
token of a spelling that method answers, into a ``calls`` fact.
"""

from array import array

import pytest

import hobbes.extract as extract
from hobbes.extract import evidence as ev
from hobbes.extract import extract_repo, rustsource
from hobbes.extract.cppsource import pack_operator
from hobbes.extract.schema import SEMANTIC

SOURCE = (
    "use std::ops::{Deref, Mul};\n"  # 1
    "pub struct Ref(i32);\n"  # 2
    "impl Deref for Ref {\n"  # 3
    "    type Target = i32;\n"  # 4
    "    fn deref(&self) -> &i32 { &self.0 }\n"  # 5
    "}\n"  # 6
    "pub struct V(i32);\n"  # 7
    "impl Mul for V { type Output = V; fn mul(self, o: V) -> V { V(self.0 * o.0) } }\n"  # 8
    "pub fn read(r: Ref) -> i32 {\n"  # 9
    "    assert_eq!(*r, 1);\n"  # 10
    "    *r\n"  # 11
    "}\n"  # 12
    "pub fn scale(a: V, b: V) -> V { a * b }\n"  # 13
)
STAR_IN_MACRO = SOURCE.splitlines()[9].index("*r")
STAR = SOURCE.splitlines()[10].index("*r")
MUL = SOURCE.splitlines()[12].index("a * b") + 2


def _ref(line, col, name, def_line, file="src/lib.rs"):
    return ev.Site(
        provider=ev.SCIP, kind=ev.RESOLUTION, file=file, line=line, col=col, name=name,
        def_file="src/lib.rs", def_line=def_line,
    )


class TestTheJoin:
    TOKENS = {"src/lib.rs": array("Q", sorted([
        pack_operator(10, STAR_IN_MACRO, "*", False),
        pack_operator(11, STAR, "*", False),
        pack_operator(13, MUL, "*", False),
    ]))}

    def _join(self, refs, tokens=TOKENS):
        counts = {}
        out = ev.join([], refs, rust_operators=tokens, counts=counts)
        return [(r.kind, r.line, r.def_line) for r in out], counts

    def test_a_method_reference_at_its_token_is_a_call(self):
        out, counts = self._join([_ref(11, STAR, "deref", 5), _ref(13, MUL, "mul", 8)])
        assert out == [("calls", 11, 5), ("calls", 13, 8)]
        assert counts == {"rust_drawn": 2}

    def test_inside_a_macro_token_tree_too(self):
        out, _ = self._join([_ref(10, STAR_IN_MACRO, "deref", 5)])
        assert out == [("calls", 10, 5)]

    @pytest.mark.parametrize(
        "ref",
        [
            _ref(13, MUL - 1, "mul", 8),  # rust-analyzer's `mul` on the space beside `*`
            _ref(11, STAR, "index", 5),  # a name whose spelling is not `*`
            _ref(11, STAR, "get", 5),  # not an operator method at all
            _ref(11, -1, "deref", 5),  # no column
        ],
    )
    def test_anything_else_stays_a_use(self, ref):
        out, counts = self._join([ref])
        assert out == [("uses", ref.line, ref.def_line)]
        assert "rust_drawn" not in counts

    def test_without_tokens_nothing_changes(self):
        out, _ = self._join([_ref(11, STAR, "deref", 5)], tokens=None)
        assert out == [("uses", 11, 5)]


def test_lane_a_records_the_tokens_in_expressions_and_token_trees():
    parsed = rustsource._parse_file("src/lib.rs", SOURCE.encode())
    from hobbes.extract.cppsource import unpack_operator

    stars = [(line, col) for line, col, spelling, _ in map(unpack_operator, parsed.operators) if spelling == "*"]
    assert (10, STAR_IN_MACRO) in stars and (11, STAR) in stars and (13, MUL) in stars


def test_the_ingest_draws_the_call_from_the_enclosing_fn(tmp_path, monkeypatch):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "m"\nversion = "0.1.0"\n')
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text(SOURCE)
    facts = {
        "language": "rust",
        "definitions": [],
        "references": [_ref(11, STAR, "deref", 5), _ref(13, MUL, "mul", 8), _ref(13, MUL + 1, "mul", 8)],
        "external_refs": [],
        "degraded": [],
    }
    monkeypatch.setattr(extract, "_lane_b_facts", lambda *a, **k: iter([facts]))
    graph = extract_repo(tmp_path).graph
    edges = {(e["from"], e["to"], e["type"]): e for e in graph["symbol_edges"]}
    assert edges[("src/lib.read", "src/lib.Ref.deref", "calls")]["tier"] == SEMANTIC
    assert edges[("src/lib.scale", "src/lib.V.mul", "calls")]["tier"] == SEMANTIC
    # the reference one column past the token is still the `uses` it was
    assert ("src/lib.scale", "src/lib.V.mul", "uses") in edges
    assert graph["operators"]["rust_drawn"] == 2
