"""ADR-128 §4: lane A's C++ file cache — one unchanged file's parse kept
under the hash of the path, the bytes and the pipeline's code, decoded
back into the object `_parse_file` returned, and never able to fail an
extraction."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from hobbes.extract import cppsource, laneacache
from hobbes.extract.cppsource import extract_cpp

#: Every test here writes a store, so every test opts in; the suite's
#: default is off, so no other test can reach the developer's own cache.
pytestmark = pytest.mark.lanea_cache

#: One file carrying every shape the encoding has to survive: a qualified
#: call and an out-of-line definition (``qualifiers`` tuples inside
#: dicts), a namespace and a same-signature duplicate (sets), a lambda
#: (a ``local_bindings`` tuple), a template pattern, and a ``TEST_CASE``
#: the walk can attach no symbol to.
BOX = """namespace shapes {

int scale(int n) { return n * 2; }

struct Box {
    int w;
    int h;
    int area() const { return shapes::scale(w * h); }
};

struct Counter {
    int n;
    int bump();
};

template <typename T>
T twice(T value) { return value + value; }

int doubled(int n) {
    auto doubler = [](int v) { return v * 2; };
    return doubler(n);
}

#ifdef FAST
int perimeter(int w, int h) { return 2 * (w + h); }
#else
int perimeter(int w, int h) { return (w + h) << 1; }
#endif

}  // namespace shapes

int shapes::Counter::bump() { return ++n; }

TEST_CASE("a box knows its area") {
    shapes::Box box{2, 3};
    box.area();
}
"""

UTIL = """int scale_by_ten(int a) {
    return a * 10;
}
"""


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """The store under a tmp_path, and a process ledger of this test's own."""
    root = tmp_path / "cache"
    monkeypatch.setenv("HOBBES_CACHE_DIR", str(root))
    laneacache.reset_ledger()
    laneacache._swept.clear()
    return root


@pytest.fixture
def repo(tmp_path):
    """Two C++ sources and no header, so a run's lookups are exactly two."""
    root = tmp_path / "repo" / "src"
    root.mkdir(parents=True)
    (root / "box.cpp").write_text(BOX)
    (root / "util.cpp").write_text(UTIL)
    return root.parent


def entries(store: Path) -> list[Path]:
    return sorted(store.rglob("*.json"))


def test_a_record_round_trips_through_json_with_its_tuples_and_sets_intact(cache):
    # The first prototype's plain JSON turned a `qualifiers` tuple into a
    # list; what is read back must be the object that was parsed.
    result = cppsource._parse_file("src/box.cpp", BOX.encode())
    text = json.dumps(laneacache.encode_record(result), sort_keys=True)
    decoded = laneacache.decode_record(json.loads(text))

    assert decoded == result
    parsed, had_error, duplicated = decoded
    assert had_error is result[1] and duplicated == result[2]
    qualified = next(c for c in parsed.calls if c["shape"] == "qualified")
    assert qualified["qualifiers"] == ("shapes",)
    out_of_line = next(s for s in parsed.symbols if "qualifiers" in s)
    assert out_of_line["qualifiers"] == ("shapes", "Counter")
    assert all(isinstance(binding, tuple) for binding in parsed.local_bindings)
    assert parsed.duplicate_names == {"shapes::perimeter"}
    assert parsed.namespaces == {"shapes"}
    assert parsed.unattached_tests == 1


def test_the_two_counts_the_arity_rule_reads_survive_the_round_trip(cache):
    # ADR-130: a call's written argument count and a symbol's parameter
    # count decide whether an edge is drawn, so an entry read back without
    # them would be a parse that never counted. The format tag moved to v2
    # with them, and an entry a v1 store holds is never read.
    def through(rel: str, source: bytes):
        result = cppsource._parse_file(rel, source)
        text = json.dumps(laneacache.encode_record(result), sort_keys=True)
        assert laneacache.decode_record(json.loads(text)) == result
        return laneacache.decode_record(json.loads(text))[0]

    parsed = through("src/box.cpp", BOX.encode())
    assert {c["name"]: c["argc"] for c in parsed.calls}["scale"] == 1
    assert {s["name"]: s.get("max_params") for s in parsed.symbols}["twice"] == 1

    # Unknown is a value the record has to keep as itself: a null read
    # back as 0 would withhold an edge nothing contradicted.
    unknown = through(
        "src/u.cpp", b"template <typename... A> void f(A... a) { g(a...); }\n"
    )
    assert [c["argc"] for c in unknown.calls] == [None]
    assert [s["max_params"] for s in unknown.symbols] == [None]


def test_the_operator_tokens_the_join_reads_survive_as_an_array(cache):
    # ADR-131: the join binary-searches a packed `array`, so a record read
    # back as a list would be a parse whose tokens the join cannot search
    # — and one read back empty would be a file that applied no operator.
    from array import array

    result = cppsource._parse_file("src/box.cpp", BOX.encode())
    text = json.dumps(laneacache.encode_record(result), sort_keys=True)
    decoded = laneacache.decode_record(json.loads(text))

    assert decoded == result
    operators = decoded[0].operators
    assert isinstance(operators, array) and operators.typecode == "Q"
    assert list(operators) == list(result[0].operators)
    # `n * 2`, `w * h`, `value + value`, `v * 2`, `2 * (w + h)`, `w + h`,
    # `(w + h) << 1` and `++n`: the file applies operators, so an empty
    # array here would be an assertion that passes by saying nothing.
    assert len(operators) > 1


def test_the_construction_tokens_the_join_reads_survive_as_an_array(cache):
    # ADR-132: the same packing, the same binary search, and the same
    # failure if a record read back as a list — or empty, which would be a
    # parse that saw no construction and a call the join never draws.
    from array import array

    result = cppsource._parse_file("src/box.cpp", BOX.encode())
    text = json.dumps(laneacache.encode_record(result), sort_keys=True)
    decoded = laneacache.decode_record(json.loads(text))

    assert decoded == result
    constructions = decoded[0].constructions
    assert isinstance(constructions, array) and constructions.typecode == "Q"
    assert list(constructions) == list(result[0].constructions)
    # `shapes::Box box{2, 3};` in the `TEST_CASE` body: the file does
    # construct, so an empty array here would be an assertion that passes
    # by saying nothing.
    assert len(constructions) > 0


def test_the_format_tag_moved_so_a_v3_entry_is_never_read_back(cache, repo, monkeypatch):
    # An entry written before the tokens existed would read back as a file
    # that applied no operator and constructed nothing, and the join would
    # draw nothing there. The tag is hashed into the key, so the v3 entry
    # is not a decode failure per file: it is a key this Hobbes never
    # looks up.
    assert laneacache.FORMAT == "lanea-cpp v4"
    source = (repo / "src" / "box.cpp").read_bytes()
    monkeypatch.setattr(laneacache, "FORMAT", "lanea-cpp v3")
    extract_cpp(repo)
    stale = laneacache.entry_path(laneacache.key("src/box.cpp", source))
    assert stale.is_file()

    monkeypatch.setattr(laneacache, "FORMAT", "lanea-cpp v4")
    laneacache.reset_ledger()
    extract_cpp(repo)
    assert laneacache.summary()["hits"] == 0
    assert laneacache.entry_path(laneacache.key("src/box.cpp", source)) != stale


def test_a_second_extraction_is_all_hits_and_the_same_bundle(cache, repo):
    first = extract_cpp(repo)
    cold = laneacache.summary()
    assert (cold["hits"], cold["misses"]) == (0, 2)
    assert len(entries(laneacache.store_root())) == 2

    laneacache.reset_ledger()
    second = extract_cpp(repo)
    warm = laneacache.summary()
    assert (warm["hits"], warm["misses"]) == (2, 0)
    assert first == second  # nodes, module edges, symbols, sites, errors
    assert warm["store"] == str(cache / "lanea" / "cpp")


def test_a_hit_gives_the_join_the_file_a_parse_would_have(cache, repo, monkeypatch):
    warm: list[cppsource.CppFile] = []
    cppsource._read_and_parse(repo, "src/box.cpp", warm)  # a miss, stored
    laneacache.reset_ledger()
    hit: list[cppsource.CppFile] = []
    cppsource._read_and_parse(repo, "src/box.cpp", hit)
    assert laneacache.summary()["hits"] == 1

    monkeypatch.setenv(laneacache.ENABLE_ENV, "0")
    fresh: list[cppsource.CppFile] = []
    cppsource._read_and_parse(repo, "src/box.cpp", fresh)
    assert hit[0] == fresh[0]
    # A new object every time: the join's in-place edits (the member-kind
    # settlement pops `qualifiers`) cannot reach the store.
    assert hit[0] is not warm[0]


def test_a_hit_reports_had_error_so_the_lossy_set_survives_a_warm_ingest(cache, repo):
    """ADR-129's first condition is read off ``had_error``, which rides in
    the cached triple: a file whose parse the store answered must still
    report that its parse had ERROR nodes, or the second ingest of a repo
    would mint nothing where the first minted."""
    (repo / "src" / "lossy.cpp").write_text(
        "#define BEGIN_NS namespace lib { inline namespace v1 {\n"
        "BEGIN_NS\n"
        "template <typename T> struct Holder { T v; };\n"
        "int lost(int x) { return x + 1; }\n"
        "} }\n"
    )
    cold = extract_cpp(repo)
    assert "src/lossy.cpp" in cold["lossy_files"]

    laneacache.reset_ledger()
    warm = extract_cpp(repo)
    assert laneacache.summary()["misses"] == 0
    assert warm["lossy_files"] == cold["lossy_files"]


def test_one_changed_byte_misses_only_the_file_it_changed(cache, repo):
    extract_cpp(repo)
    (repo / "src" / "util.cpp").write_text(UTIL.replace("10", "11"))

    laneacache.reset_ledger()
    extract_cpp(repo)
    counts = laneacache.summary()
    assert (counts["hits"], counts["misses"]) == (1, 1)
    assert len(entries(laneacache.store_root())) == 3  # the old util.cpp stays


def test_a_changed_code_fingerprint_misses_everywhere(cache, repo, monkeypatch):
    # The key's whole point: a change to the extraction code cannot be
    # read past (ADR-128 §4), so every file is walked again.
    extract_cpp(repo)
    monkeypatch.setattr(laneacache, "_FINGERPRINT", "a-later-pipeline")

    laneacache.reset_ledger()
    extract_cpp(repo)
    counts = laneacache.summary()
    assert (counts["hits"], counts["misses"]) == (0, 2)
    assert len(entries(laneacache.store_root())) == 4


def test_a_truncated_entry_is_dropped_and_written_again(cache, repo, monkeypatch):
    extract_cpp(repo)
    source = (repo / "src" / "box.cpp").read_bytes()
    entry = laneacache.entry_path(laneacache.key("src/box.cpp", source))
    stored = entry.read_text()
    entry.write_text(stored[: len(stored) // 2])

    laneacache.reset_ledger()
    with_a_bad_entry = extract_cpp(repo)
    counts = laneacache.summary()
    assert (counts["hits"], counts["misses"]) == (1, 1)

    monkeypatch.setenv(laneacache.ENABLE_ENV, "0")
    assert with_a_bad_entry == extract_cpp(repo)
    assert json.loads(entry.read_text())["file"]["path"] == "src/box.cpp"


def test_the_cache_off_writes_nothing_and_counts_nothing(cache, repo, monkeypatch):
    monkeypatch.setenv(laneacache.ENABLE_ENV, "0")
    assert extract_cpp(repo) is not None
    assert not laneacache.store_root().exists()
    assert laneacache.summary() is None


def test_a_missing_fingerprint_parses_every_file(cache, repo, monkeypatch):
    # No version to read is not a reason to trust a key that cannot see
    # the grammar: nothing is stored and nothing is counted.
    monkeypatch.setattr(laneacache, "_FINGERPRINT", None)
    assert extract_cpp(repo) is not None
    assert not laneacache.store_root().exists()
    assert laneacache.summary() is None


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes a read-only directory anyway")
def test_a_store_that_cannot_be_written_never_fails_the_extraction(cache, repo):
    store = laneacache.store_root()
    store.mkdir(parents=True)
    store.chmod(0o500)
    try:
        bundle = extract_cpp(repo)
    finally:
        store.chmod(0o700)
    assert bundle is not None and bundle["symbols"]
    assert entries(store) == []
    counts = laneacache.summary()
    assert (counts["hits"], counts["misses"]) == (0, 2)


def test_a_value_the_encoding_refuses_is_not_stored_and_the_parse_still_returns(
    cache, repo, monkeypatch
):
    parse = cppsource._parse_file

    def carrying_an_object(rel, source):
        parsed, had_error, duplicated = parse(rel, source)
        parsed.symbols[0]["owner"] = object()
        return parsed, had_error, duplicated

    monkeypatch.setattr(cppsource, "_parse_file", carrying_an_object)
    bundle = extract_cpp(repo)
    assert bundle is not None and bundle["symbols"]
    assert entries(laneacache.store_root()) == []
    assert laneacache.summary()["misses"] == 2


def test_an_encoding_that_lost_a_tuple_would_keep_nothing(cache, tmp_path, monkeypatch):
    # The write-side assertion itself: a record that does not decode back
    # to its object is dropped rather than read as an answer later.
    monkeypatch.setattr(laneacache, "decode_record", lambda record: ("not the parse",))
    path = laneacache.entry_path(laneacache.key("src/box.cpp", BOX.encode()))
    laneacache._store(path, cppsource._parse_file("src/box.cpp", BOX.encode()))
    assert not path.exists()


def test_sweep_takes_partials_and_stale_entries_and_leaves_fresh_ones(cache):
    store = laneacache.store_root()
    (store / "ab").mkdir(parents=True)
    (store / "cd").mkdir(parents=True)
    now = time.time()
    stale = store / "ab" / "old.json"
    stale.write_text("{}")
    os.utime(stale, (now - (laneacache.KEEP_DAYS + 1) * 86400,) * 2)
    partial = store / "ab" / "killed.json.partial"
    partial.write_text("{")
    fresh = store / "cd" / "new.json"
    fresh.write_text("{}")

    assert laneacache.sweep(now=now) == 2
    assert not stale.exists() and not partial.exists()
    assert fresh.exists()


def test_the_sweep_runs_once_per_process_per_store(cache, repo, monkeypatch):
    # Two files are stored; the sweep costs a directory walk and runs at
    # the first of them.
    swept: list[Path] = []
    monkeypatch.setattr(laneacache, "sweep", lambda root=None, now=None: swept.append(root))
    extract_cpp(repo)
    assert swept == [laneacache.store_root()]
