"""The port: `families` draws the members `bench/calvin/e3-draw/` drew, on the same synthetic clones.

The draw's recorded figures (33,902 union tasks, 24,222 unique) were read by those scripts, so the only
useful test of this module is the scripts themselves: `count.py` and `measure.py` are imported by path
and run beside `families` over two hand-written clones — an ISA family, a body-shape family, thin
helpers, and one body that appears in both clones. `dedupe.py` is a driver that reads its inputs at
import time, so its one rule is restated here as the assertion `families.body_hash` has to meet.
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

from lattice import corpus, families

E3_DRAW = Path(__file__).resolve().parents[2] / "e3-draw"

# MARK: - the clones' code -

FINISH = """
static float finish_total(float t) { return t + 1.0f; }
"""

DOT_SSE2 = """
float dot_product_sse2(const float *a, const float *b, int n) {
    float total = 0.0f;
    for (int i = 0; i < n; i++) {
        total += a[i] * b[i];
    }
    return finish_total(total);
}
"""

DOT_AVX2 = """
float dot_product_avx2(const float *a, const float *b, int n) {
    float total = 0.0f;
    for (int i = 0; i < n; i += 8) {
        total += a[i] * b[i] * 2.0f;
    }
    return finish_total(total);
}
"""

WEIGHT_F32 = """
static int float32_weight(float v) { return (int)(v * 2.0f); }
"""

WEIGHT_F16 = """
static int float16_weight(float v) { return (int)(v * 3.0f); }
"""

SUM_F32 = """
int sum_float32_scalar(const float32_t *v, int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += float32_weight(v[i]);
    }
    return total;
}
"""

SUM_F16 = """
int sum_float16_scalar(const float16_t *v, int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += float16_weight(v[i]);
    }
    return total;
}
"""

HASH_NEON = """
unsigned hash_block_neon(const unsigned char *p, int n) {
    unsigned acc = 5381u;
    for (int i = 0; i < n; i++) {
        acc = acc * 33u + p[i];
    }
    return acc;
}
"""

HASH_AVX2 = """
unsigned hash_block_avx2(const unsigned char *p, int n) {
    unsigned acc = 5381u;
    for (int i = 0; i < n; i += 4) {
        acc = acc * 31u + p[i];
    }
    return acc;
}
"""


# MARK: - the clone writer -


def write_clone(root, sources, *, edges=(), ghosts=(), tests=(), sha="0123456789abcdef"):
    """A tiny ingested clone: the C files, and the `graph.json` and `tests.json` a draw reads them through.

    *sources* is `{relative path: [(name, definition text), …]}` and the line numbers the graph records
    are computed from what is written, so a fixture cannot drift from its own graph. *ghosts* is
    `(path, name, line, end_line)` for a symbol whose file is **not** written — how a callee the clone
    cannot be read for is planted.
    """
    root = Path(root)
    nodes, symbols = [], []
    for rel, defined in sources.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["/* written by the test */", ""]
        for name, text in defined:
            body = text.strip("\n").split("\n")
            symbols.append({"id": f"{rel}.{name}", "kind": "function", "name": name, "module": rel,
                            "qualname": name, "line": len(lines) + 1, "end_line": len(lines) + len(body)})
            lines += body + [""]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        nodes.append({"id": rel, "kind": "module", "path": rel})
    for rel, name, line, end_line in ghosts:
        if not any(node["id"] == rel for node in nodes):
            nodes.append({"id": rel, "kind": "module", "path": rel})
        symbols.append({"id": f"{rel}.{name}", "kind": "function", "name": name, "module": rel,
                        "qualname": name, "line": line, "end_line": end_line})
    graph = {
        "schema_version": 4, "sha": sha, "built_by": {"version": "test", "sha": sha, "dirty": False},
        "languages": ["c"], "nodes": nodes, "symbols": symbols,
        "symbol_edges": [{"from": a, "to": b, "type": "calls", "tier": "semantic"} for a, b in edges],
    }
    derived = root / ".hobbes" / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    (derived / "graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (derived / "tests.json").write_text(json.dumps({"tests": list(tests)}), encoding="utf-8")
    return root


def alpha(root):
    """One repo: an ISA family, a body-shape family, two thin helpers, and the calls between them."""
    return write_clone(
        root,
        {
            "src/kernels.c": [("finish_total", FINISH), ("dot_product_sse2", DOT_SSE2),
                              ("dot_product_avx2", DOT_AVX2)],
            "src/sums.c": [("float32_weight", WEIGHT_F32), ("float16_weight", WEIGHT_F16),
                           ("sum_float32_scalar", SUM_F32), ("sum_float16_scalar", SUM_F16)],
        },
        edges=[
            ("src/kernels.c.dot_product_sse2", "src/kernels.c.finish_total"),
            ("src/kernels.c.dot_product_avx2", "src/kernels.c.finish_total"),
            ("src/sums.c.sum_float32_scalar", "src/sums.c.float32_weight"),
            ("src/sums.c.sum_float16_scalar", "src/sums.c.float16_weight"),
        ],
        tests=[{"file": "tests/test_kernels.c", "reaches": ["src/kernels.c.dot_product_avx2"]}],
        sha="a" * 40,
    )


def beta(root):
    """A second repo: its own ISA family, and `kernels.c` copied whole out of the first."""
    return write_clone(
        root,
        {
            "src/kernels.c": [("finish_total", FINISH), ("dot_product_sse2", DOT_SSE2),
                              ("dot_product_avx2", DOT_AVX2)],
            "src/hash.c": [("hash_block_neon", HASH_NEON), ("hash_block_avx2", HASH_AVX2)],
        },
        edges=[
            ("src/kernels.c.dot_product_sse2", "src/kernels.c.finish_total"),
            ("src/kernels.c.dot_product_avx2", "src/kernels.c.finish_total"),
        ],
        sha="b" * 40,
    )


@pytest.fixture
def clones(tmp_path):
    """The two clones, in the taken order: `alpha` first, so it keeps the shared bodies."""
    return [("alpha", alpha(tmp_path / "alpha")), ("beta", beta(tmp_path / "beta"))]


@pytest.fixture(scope="module")
def draw():
    """`count` and `measure` as they ran, imported from `bench/calvin/e3-draw` by path."""
    sys.path.insert(0, str(E3_DRAW))
    import count
    import measure

    return count, measure


# MARK: - the union -


def draw_union(draw, name, root):
    """The draw's own union over a clone: the ISA families and the body-shape families, non-thin."""
    count, measure = draw
    repo = count.Repo(name, root)
    nonthin = [m for m in repo.members.values() if not m["thin"]]
    isa = measure.isa_families(nonthin)
    body, _, _ = measure.body_families(count.loose_groups(nonthin))
    return {m["id"] for f in isa + body for m in f["members"]}


def ported_union(name, root):
    """The same union through `families`, composed the way `corpus` composes it."""
    repo = families.Repo(name, root)
    return set(corpus._union(corpus._families_of(repo)))


def test_the_port_draws_the_same_union_members(draw, clones):
    for name, root in clones:
        assert ported_union(name, root) == draw_union(draw, name, root), name


def test_the_union_is_what_the_clones_were_written_to_hold(clones):
    alpha_root = clones[0][1]
    assert ported_union("alpha", alpha_root) == {
        "src/kernels.c.dot_product_sse2",
        "src/kernels.c.dot_product_avx2",
        "src/sums.c.sum_float32_scalar",
        "src/sums.c.sum_float16_scalar",
    }
    # the helpers are thin — one statement, at most one call — so they are in no family
    assert ported_union("beta", clones[1][1]) == {
        "src/kernels.c.dot_product_sse2",
        "src/kernels.c.dot_product_avx2",
        "src/hash.c.hash_block_neon",
        "src/hash.c.hash_block_avx2",
    }


def test_the_isa_rule_and_the_body_rule_each_find_their_own_family(clones):
    repo = families.Repo("alpha", clones[0][1])
    nonthin = [m for m in repo.members.values() if not m["thin"]]
    isa = families.isa_families(nonthin)
    assert [" ".join(f["key"][2]) for f in isa] == ["dot product *"]
    body, skipped, over = families.body_families(families.loose_groups(nonthin))
    assert sorted(" ".join(f["key"][2]) for f in body) == ["dot product *", "sum * scalar"]
    assert (skipped, over) == (0, {})


# MARK: - the dedupe -


def draw_unique(draw, clones):
    """`dedupe.py`'s rule as that script wrote it, over the taken order."""
    count, measure = draw
    seen, unique = {}, {}
    for name, root in clones:
        repo = count.Repo(name, root)
        nonthin = [m for m in repo.members.values() if not m["thin"]]
        isa = measure.isa_families(nonthin)
        body, _, _ = measure.body_families(count.loose_groups(nonthin))
        union = {m["id"]: m for f in isa + body for m in f["members"]}
        first, own = 0, set()
        for m in union.values():
            digest = hashlib.sha1(" ".join((m["body"] or "").split()).encode()).hexdigest()
            if digest in seen and seen[digest] != name:
                continue
            if digest in own:
                continue
            first += 1
            seen.setdefault(digest, name)
            own.add(digest)
        unique[name] = first
    return unique


def test_the_port_deduplicates_as_the_draw_did(draw, clones):
    seen, ported = {}, {}
    for name, root in clones:
        repo = families.Repo(name, root)
        union = corpus._union(corpus._families_of(repo))
        unique, duplicate = corpus._deduplicate(name, union, seen)
        ported[name] = len(unique)
        assert len(unique) + duplicate == len(union), name
    assert ported == draw_unique(draw, clones)
    # alpha keeps both copies of `kernels.c`'s bodies, beta keeps only its own two
    assert ported == {"alpha": 4, "beta": 2}


def test_body_hash_is_the_dedupe_scripts_own_key():
    body = " a  +=\n b;\t"
    assert families.body_hash(body) == hashlib.sha1(b"a += b;").hexdigest()
    assert families.body_hash(None) == hashlib.sha1(b"").hexdigest()


# MARK: - the two tokenisers, which are not one -


def test_the_isa_tokeniser_keeps_a_digit_to_letter_run_and_counts_tokens_splits_it():
    # gate.py's rule is `_` and camelCase boundaries only, which is what makes `avx512vnni` one ISA token
    assert families.isa_tokens("dot_avx512vnni_kernel") == ("dot", "avx512vnni", "kernel")
    assert families.isa_tokens("sse4_1_dot") == ("sse41", "dot")
    assert families.isa_tokens("hsum256d_ps") == ("hsum256d", "ps")
    # count.py's splits a letter run off the digits that precede it, which is why both are ported
    assert families.tokens("dot_avx512vnni_kernel") == ("dot", "avx512", "vnni", "kernel")
    assert families.tokens("hsum256d_ps") == ("hsum256", "d", "ps")


def test_a_test_or_vendored_path_is_not_a_member(clones):
    assert families.classify_path("third_party/zlib/adler32.c") == "vendor"
    assert families.classify_path("src/tests/kernels.c") == "test"
    assert families.classify_path("src/test_kernels.c") == "test"
    assert families.classify_path("src/kernels.c") is None
