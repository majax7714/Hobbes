"""One file's depth never ends a repo's ingest (C-171, 0.2.71-beta).

The E3 draw met moonlab's ``build.rs``: a bindgen builder chain of 537 calls in
one expression, deeper than a recursive walk's stack, and the ingest ended on
the ``RecursionError``. Two guarantees are held here, at the level a user meets
them:

- **The walks are iterative**, so Rust, Go and Java read a 5,000-call chain in
  full, every call site included.
- **C's and C++'s walks are linear in depth.** Their unevaluated-operand,
  template and body checks once read ``Node.parent`` back to the root, and
  tree-sitter finds a parent by descending from the root, so a chain of
  depth N cost N³: 6 s in C and 15 s in C++ at 800 calls. The answers are
  now carried down the walk, and a 2,000-call chain reads in well under a
  second, its graph unchanged.
- **Every lane A provider contains the rest per file.** A file whose parse still
  overflows keeps its module, is read as empty, and is named in
  ``extraction_errors`` with C-171, while the repo's other files are read as
  before. Python's walk is a structural visitor that still overflows (about 600
  levels, where CPython compiles 2,000), so its guarantee is the containment.
"""

from __future__ import annotations

import time

import pytest

from hobbes.extract import cppsource, csource, extract_repo, gosource, javasource, rustsource

N = 5000
CHAIN = ".".join(["b()"] * N)


@pytest.mark.parametrize(
    ("module", "name", "source"),
    [
        (rustsource, "deep.rs", f"fn main() {{ let x = a().{CHAIN}; }}\n"),
        (gosource, "deep.go", f"package p\nfunc f() {{ x := a().{CHAIN}; _ = x }}\n"),
        (javasource, "Deep.java", f"class Deep {{ void f() {{ Object x = a().{CHAIN}; }} }}\n"),
    ],
    ids=["rust", "go", "java"],
)
def test_a_five_thousand_call_chain_is_read_in_full(module, name, source):
    parsed = module._parse_file(name, source.encode())
    assert len(parsed.calls) >= N  # every `b()` in the chain is a call site


LINEAR_N = 2000
_C_CHAIN = ".".join(["b()"] * LINEAR_N)
_ARROW_CHAIN = "->".join(["b()"] * LINEAR_N)


@pytest.mark.parametrize(
    ("module", "name", "source"),
    [
        (csource, "deep.c", f"void f(void) {{ int x = a().{_C_CHAIN}; }}\n"),
        (cppsource, "deep.cpp", f"void f() {{ auto x = a().{_C_CHAIN}; }}\n"),
    ],
    ids=["c", "cpp"],
)
def test_c_and_cpp_read_a_two_thousand_call_chain_in_linear_time(module, name, source):
    # The old walk took about 90 s (C) and 230 s (C++) here; the bound is
    # some 40 times what the linear walk needs, so only a superlinear walk
    # fails it.
    started = time.perf_counter()
    parsed, _, _ = module._parse_file(name, source.encode())
    elapsed = time.perf_counter() - started
    assert len(parsed.calls) == LINEAR_N + 1  # `a()` and every `b()`
    assert elapsed < 2.0, f"{name}: {elapsed:.1f} s for a {LINEAR_N}-call chain"


@pytest.mark.parametrize(
    ("module", "name", "wrap"),
    [
        (csource, "deep.c", "void f(void) {{ int z = sizeof({chain}); }}\n"),
        (cppsource, "deep.cpp", "void f() {{ int z = sizeof({chain}); }}\n"),
        (cppsource, "deep.cpp", "void f() {{ decltype({chain}) z; }}\n"),
        (cppsource, "deep.cpp", "void f() {{ bool z = noexcept({chain}); }}\n"),
    ],
    ids=["c-sizeof", "cpp-sizeof", "cpp-decltype", "cpp-noexcept"],
)
def test_the_carried_operand_answer_holds_at_depth(module, name, wrap):
    # Carried down rather than read back up, the unevaluated answer still
    # reaches the deepest call: nothing in the operand is a site.
    chain = f"a()->{_ARROW_CHAIN}"
    parsed, _, _ = module._parse_file(name, wrap.format(chain=chain).encode())
    assert parsed.calls == []
    if module is cppsource:
        assert len(parsed.operators) == 0  # no `->` in the operand is applied
    evaluated, _, _ = module._parse_file(name, f"void f() {{ int z = ({chain}); }}\n".encode())
    assert len(evaluated.calls) == LINEAR_N + 1
    if module is cppsource:
        spellings = [cppsource.unpack_operator(p)[2] for p in evaluated.operators]
        assert spellings.count("->") == LINEAR_N  # one `->` token each
        assert spellings.count("()") == LINEAR_N + 1  # and each call's `(` (ADR-175)


def _overflow_on(module, monkeypatch, deep_name):
    """Make *module*'s parse overflow on one file, as a deep one does."""
    real = module._parse_file

    def parse(rel, source):
        if rel.endswith(deep_name) and source:
            raise RecursionError("maximum recursion depth exceeded")
        return real(rel, source)

    monkeypatch.setattr(module, "_parse_file", parse)


def _c171(errors, path):
    return [e for e in errors if e["path"] == path and "C-171" in e["message"]]


@pytest.mark.parametrize(
    ("module", "extract", "good", "deep", "good_source", "symbol"),
    [
        (rustsource, rustsource.extract_rust, "good.rs", "deep.rs", "pub fn good() -> i64 { 1 }\n", "good.good"),
        (gosource, gosource.extract_go, "good.go", "deep.go", "package p\nfunc Good() int { return 1 }\n", None),
        (javasource, javasource.extract_java, "Good.java", "Deep.java", "class Good { int g() { return 1; } }\n", None),
        (csource, csource.extract_c, "good.c", "deep.c", "int good(void) { return 1; }\n", None),
        (cppsource, cppsource.extract_cpp, "good.cpp", "deep.cpp", "int good() { return 1; }\n", None),
    ],
    ids=["rust", "go", "java", "c", "cpp"],
)
def test_a_file_that_still_overflows_is_named_and_the_rest_is_read(
    module, extract, good, deep, good_source, symbol, tmp_path, monkeypatch
):
    (tmp_path / good).write_text(good_source)
    (tmp_path / deep).write_text(good_source.replace("good", "deep").replace("Good", "Deep"))
    _overflow_on(module, monkeypatch, deep)

    layer = extract(tmp_path)

    assert len(_c171(layer["errors"], deep)) == 1
    names = {s["name"] for s in layer["symbols"]}
    assert any(n.lower() == "good" or n == "g" for n in names)  # the other file is read
    assert not any("deep" in n.lower() for n in names)  # the deep one is read as empty
    if symbol:
        assert any(s["id"] == symbol for s in layer["symbols"])


def test_python_contains_a_chain_deeper_than_its_walk_and_names_it(tmp_path):
    (tmp_path / "good.py").write_text("def good():\n    return 1\n")
    (tmp_path / "deep.py").write_text("x = a()." + ".".join(["b()"] * 1500) + "\n")
    compile((tmp_path / "deep.py").read_text(), "deep.py", "exec")  # it is valid Python

    graph = extract_repo(tmp_path).graph

    assert len(_c171(graph["extraction_errors"], "deep.py")) == 1
    assert any(s["id"] == "good.good" for s in graph["symbols"])
    assert any(n["id"] == "deep" for n in graph["nodes"])  # the module stays a node
