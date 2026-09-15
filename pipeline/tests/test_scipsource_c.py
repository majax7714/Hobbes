"""C's lane B, the ingest side (ADR-109).

Covered here: build roots, where each root's compile database comes from,
the carried database's rebase, and the shape of one root's run through
``extract_scip_c``. ``run_helper`` is replaced, so every case but the last
runs without the image. The last case is the real thing: the ``minic``
fixture through bear over its Makefile, inside the image.
"""
import json
from pathlib import Path

import pytest

from hobbes.extract import scipsource, staging

MINIC = Path(__file__).parent / "fixtures" / "minic"
MINICPP = Path(__file__).parent / "fixtures" / "minicpp"


def write(root: Path, rel: str, text: str = "") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class TestBuildRoots:
    def test_the_outermost_cmake_root_owns_its_subprojects(self, tmp_path):
        write(tmp_path, "CMakeLists.txt")
        write(tmp_path, "lib/CMakeLists.txt")
        assert scipsource.c_units(tmp_path, ["b.c", "lib/a.c"]) == {"": ["b.c", "lib/a.c"]}

    def test_a_cmake_root_wins_over_an_outer_makefile(self, tmp_path):
        # A root Makefile that only drives docs must not swallow a CMake project below it.
        write(tmp_path, "Makefile")
        write(tmp_path, "src/CMakeLists.txt")
        assert scipsource.c_units(tmp_path, ["src/a.c"]) == {"src": ["src/a.c"]}

    def test_the_outermost_makefile_when_there_is_no_cmake(self, tmp_path):
        write(tmp_path, "Makefile")
        write(tmp_path, "src/Makefile")
        assert scipsource.c_units(tmp_path, ["src/a.c"]) == {"": ["src/a.c"]}

    def test_a_file_under_no_build_file_is_an_orphan(self, tmp_path):
        grouped = scipsource.c_units(tmp_path, ["tools/x.c"])
        assert grouped == {}
        assert scipsource.go_orphans(["tools/x.c"], grouped) == {"tools": ["tools/x.c"]}

    def test_a_cpp_only_repo_groups_under_its_build_file_like_any_other(self, tmp_path):
        # The grouping never looks at an extension: scip-clang indexes what
        # the compile database names, and C++ is C's indexer (ADR-113 §2).
        write(tmp_path, "Makefile")
        assert scipsource.c_units(tmp_path, ["src/a.cpp", "src/b.hpp"]) == {
            "": ["src/a.cpp", "src/b.hpp"]
        }

    def test_a_mixed_root_is_one_unit(self, tmp_path):
        write(tmp_path, "CMakeLists.txt")
        assert scipsource.c_units(tmp_path, ["src/a.c", "src/b.cpp"]) == {
            "": ["src/a.c", "src/b.cpp"]
        }


class TestCompdbSource:
    def test_cmake_then_make_then_nothing(self, tmp_path):
        write(tmp_path, "a/CMakeLists.txt")
        write(tmp_path, "a/Makefile")
        write(tmp_path, "b/GNUmakefile")
        (tmp_path / "c").mkdir()
        assert scipsource.c_compdb_source(tmp_path, "a") == ("cmake", "")
        assert scipsource.c_compdb_source(tmp_path, "b") == ("make", "")
        source, why = scipsource.c_compdb_source(tmp_path, "c")
        assert source is None and "no compile_commands.json, CMakeLists.txt or Makefile" in why

    def test_a_carried_database_under_this_checkout_is_used(self, tmp_path):
        entries = [{"directory": str(tmp_path / "build"), "file": str(tmp_path / "src" / "a.c"),
                    "arguments": ["cc", "-I" + str(tmp_path / "include"), "-c", str(tmp_path / "src" / "a.c")]}]
        write(tmp_path, "build/compile_commands.json", json.dumps(entries))
        write(tmp_path, "CMakeLists.txt")
        assert scipsource.c_compdb_source(tmp_path, "") == ("repo", "build/compile_commands.json")

    def test_another_machines_database_is_skipped_and_said(self, tmp_path):
        write(tmp_path, "compile_commands.json", json.dumps([{"directory": "/home/someone/proj", "file": "a.c"}]))
        write(tmp_path, "Makefile")
        source, note = scipsource.c_compdb_source(tmp_path, "")
        assert source == "make"
        assert "compile_commands.json is not usable here" in note and "/home/someone/proj" in note

    def test_the_carried_database_is_rebased_into_the_stage(self, tmp_path):
        repo, stage = tmp_path / "repo", tmp_path / "stage"
        entries = [
            {"directory": str(repo / "build"), "file": str(repo / "src" / "a.c"),
             "arguments": ["cc", "-I" + str(repo / "include"), "-c", str(repo / "src" / "a.c")]},
            {"directory": "..", "file": "src/b.c", "command": "cc -c src/b.c"},
        ]
        out = scipsource.rebased_compdb(repo, "build", entries, stage)
        assert out[0]["directory"] == str(stage / "build")
        assert out[0]["file"] == str(stage / "src" / "a.c")
        assert out[0]["arguments"][1] == "-I" + str(stage / "include")
        assert out[1]["directory"] == str(stage / "build" / "..")  # relative: taken from the database's own directory
        assert out[1]["command"] == "cc -c src/b.c"


class TestExtract:
    @pytest.fixture
    def lane_b_on(self, tmp_path, monkeypatch):
        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")
        monkeypatch.setenv(staging._CACHE_ENV, str(tmp_path / "cache"))

    def test_one_root_stages_its_whole_tree_with_a_scratch_build_dir(self, tmp_path, monkeypatch, lane_b_on):
        repo = tmp_path / "repo"
        write(repo, "proj/Makefile", "all:\n\tcc -c src/a.c\n")
        write(repo, "proj/src/a.c", "int f(void) { return 0; }\n")
        write(repo, "proj/tools/gen.sh", "#!/bin/sh\n")
        write(repo, "proj/build/old.o", "stale")
        seen = {}

        def fake(config, **kw):
            stage = Path(config["stage"])
            seen.update(config=config, root=kw.get("root"),
                        files=sorted(p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()),
                        build_dir_existed=Path(config["buildDir"]).is_dir())
            # run_helper puts the root in front of every path as it reads
            # the facts (ADR-116; `TestReadFacts`), so its rows come re-rooted.
            return {"definitions": [{"moniker": "m", "file": f"{kw['root']}/src/a.c", "line": 1, "end_line": 1, "kind": "method"}],
                    "references": [], "external_refs": [], "degraded": []}

        monkeypatch.setattr(scipsource, "run_helper", fake)
        merged = scipsource.extract_scip_c(repo, ["proj/src/a.c"])
        assert seen["config"]["language"] == "c" and seen["config"]["compdbSource"] == "make"
        assert seen["files"] == ["Makefile", "src/a.c", "tools/gen.sh"], "the whole tree, less build output"
        assert seen["build_dir_existed"] and not Path(seen["config"]["buildDir"]).exists(), "made before, removed after"
        assert seen["root"] == "proj", "the root rides into run_helper, which re-roots paths as it reads"
        assert merged["definitions"][0]["file"] == "proj/src/a.c"

    def test_a_failed_build_degrades_its_root_alone(self, tmp_path, monkeypatch, lane_b_on):
        repo = tmp_path / "repo"
        write(repo, "ok/Makefile")
        write(repo, "bad/Makefile")

        def fake(config, **kw):
            if config["stage"].endswith("/bad"):
                raise scipsource.ScipError("the c indexer exited: make: *** [all] Error 1")
            return {"definitions": [], "references": [], "external_refs": [], "degraded": []}

        monkeypatch.setattr(scipsource, "run_helper", fake)
        merged = scipsource.extract_scip_c(repo, ["bad/x.c", "ok/y.c", "loose/z.c"])
        records = {r["path"]: r["message"] for r in merged["degraded"]}
        assert "semantic indexing failed for this C build alone" in records["bad"] and "Error 1" in records["bad"]
        assert "sit below no CMakeLists.txt or Makefile" in records["loose"]
        assert "ok" not in records

    def test_a_root_with_nothing_to_derive_from_says_why(self, tmp_path, monkeypatch, lane_b_on):
        facts = scipsource._index_c_unit(tmp_path, "empty", "")
        assert facts["degraded"][0]["stage"] == "scip-c"
        assert "no compile database can be derived" in facts["degraded"][0]["message"]

    def test_a_cpp_root_says_so_in_that_record_too(self, tmp_path, monkeypatch, lane_b_on):
        facts = scipsource._index_c_unit(tmp_path, "empty", "", "cpp")
        assert facts["degraded"][0]["stage"] == "scip-cpp"
        assert "this C++ build root" in facts["degraded"][0]["message"]

    def test_the_roots_own_record_and_the_helpers_both_sit_at_the_root(self, tmp_path, monkeypatch, lane_b_on):
        # The helper's records are root-relative and the caller's is
        # repo-relative. The caller's was appended before the rebase, so a
        # root below the repo's read `proj/proj` (2026-09-15, 0.2.27-beta).
        repo = tmp_path / "repo"
        write(repo, "proj/Makefile", "all:\n\tcc -c src/a.c\n")
        write(repo, "proj/src/a.c", "int f(void) { return 0; }\n")
        write(repo, "proj/compile_commands.json", json.dumps([{"directory": "/home/someone/proj", "file": "a.c"}]))

        def fake(config, **kw):
            return {"definitions": [], "references": [], "external_refs": [],
                    "degraded": [{"path": ".", "stage": "scip-decode", "message": "the helper's, at the unit's root"}]}

        monkeypatch.setattr(scipsource, "run_helper", fake)
        merged = scipsource.extract_scip_c(repo, ["proj/src/a.c"])
        (own,) = [r for r in merged["degraded"] if "derived with make instead" in r["message"]]
        (helpers,) = [r for r in merged["degraded"] if r["stage"] == "scip-decode"]
        assert own["path"] == "proj", merged["degraded"]
        assert helpers["path"] == "proj", merged["degraded"]


class TestRootLanguage:
    """ADR-113 §2: a root holding any C++ file is a C++ root — one index
    for both languages, and records that say which one it was."""

    @pytest.fixture
    def lane_b_on(self, tmp_path, monkeypatch):
        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")
        monkeypatch.setenv(staging._CACHE_ENV, str(tmp_path / "cache"))

    def _configs(self, repo, monkeypatch, files, cpp_files):
        seen = []

        def fake(config, **kw):
            seen.append(config)
            return {"definitions": [], "references": [], "external_refs": [], "degraded": []}

        monkeypatch.setattr(scipsource, "run_helper", fake)
        merged = scipsource.extract_scip_c(repo, files, cpp_files=cpp_files)
        return seen, merged

    def test_a_root_with_no_cpp_file_is_a_c_root(self, tmp_path, monkeypatch, lane_b_on):
        repo = tmp_path / "repo"
        write(repo, "Makefile")
        write(repo, "src/a.c", "int f(void) { return 0; }\n")
        seen, _ = self._configs(repo, monkeypatch, ["src/a.c"], ["other/x.cpp"])
        assert [c["language"] for c in seen] == ["c"]

    def test_one_cpp_file_makes_the_whole_root_a_cpp_root(self, tmp_path, monkeypatch, lane_b_on):
        # A mixed root is one index (scip-clang indexes whichever units the
        # database names), so the root's language is the wider of the two.
        repo = tmp_path / "repo"
        write(repo, "Makefile")
        write(repo, "src/a.c")
        write(repo, "src/b.cpp")
        seen, _ = self._configs(repo, monkeypatch, ["src/a.c", "src/b.cpp"], ["src/b.cpp"])
        assert [c["language"] for c in seen] == ["cpp"]

    def test_a_claimed_header_makes_its_root_a_cpp_root(self, tmp_path, monkeypatch, lane_b_on):
        # The C++ layer claims a `.h`, so it arrives in `cpp_files` and the
        # root it sits in is C++'s, extension or no extension.
        repo = tmp_path / "repo"
        write(repo, "Makefile")
        write(repo, "src/a.h")
        seen, _ = self._configs(repo, monkeypatch, ["src/a.h"], ["src/a.h"])
        assert [c["language"] for c in seen] == ["cpp"]

    def test_a_failed_cpp_build_is_reported_in_cpp_s_words(self, tmp_path, monkeypatch, lane_b_on):
        repo = tmp_path / "repo"
        write(repo, "Makefile")
        write(repo, "src/a.cpp")

        def fake(config, **kw):
            raise scipsource.ScipError("the cpp indexer exited: make: *** [all] Error 1")

        monkeypatch.setattr(scipsource, "run_helper", fake)
        merged = scipsource.extract_scip_c(repo, ["src/a.cpp"], cpp_files=["src/a.cpp"])
        [record] = merged["degraded"]
        assert record["stage"] == "scip-cpp"
        assert "semantic indexing failed for this C++ build alone" in record["message"]

    def test_an_orphan_directory_is_named_by_whose_files_are_in_it(self, tmp_path, monkeypatch, lane_b_on):
        repo = tmp_path / "repo"
        merged = scipsource.extract_scip_c(
            repo,
            ["pure/a.cpp", "mixed/b.c", "mixed/c.cpp", "plain/d.c"],
            cpp_files=["pure/a.cpp", "mixed/c.cpp"],
        )
        records = {r["path"]: r["message"] for r in merged["degraded"]}
        assert "1 C++ file(s) under 'pure'" in records["pure"]
        assert "2 C and C++ file(s) under 'mixed'" in records["mixed"]
        assert "1 C file(s) under 'plain'" in records["plain"]

    def test_the_build_disclosure_names_the_languages_its_roots_hold(self, tmp_path, monkeypatch, lane_b_on, capsys):
        # C-29's disclosure prints once per run: a C++ project must not be
        # told its build logic runs for "c semantics".
        cpp_repo = tmp_path / "cpp"
        write(cpp_repo, "Makefile")
        write(cpp_repo, "src/a.cpp")
        self._configs(cpp_repo, monkeypatch, ["src/a.cpp"], ["src/a.cpp"])
        assert "NOTE: c++ semantics:" in capsys.readouterr().err
        c_repo = tmp_path / "c"
        write(c_repo, "Makefile")
        write(c_repo, "src/a.c")
        self._configs(c_repo, monkeypatch, ["src/a.c"], [])
        assert "NOTE: c semantics:" in capsys.readouterr().err


@pytest.mark.lane_b
def test_minic_gets_semantic_c_edges_through_bear_over_its_makefile():
    """The fixture's Makefile builds main.c, util.c and shapes.c (the link fails on the duplicate `scale`, which is
    the point: make's own exit decides nothing). So those three files get lane B; platform.c and tests/ are not in
    the database and stay lane A's."""
    from hobbes.extract import containment, extract_repo

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINIC).graph
    calls = {(e["from"], e["to"]): e["tier"] for e in graph["symbol_edges"] if e["type"] == "calls"}
    why = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]
    assert calls[("src/main.main", "src/util.add")] == "semantic", why
    assert calls[("src/main.main", "include/minic/config.h.MINIC_MAX")] == "semantic", "a macro joins by its name"
    assert calls[("src/util.add", "src/util.helper")] == "semantic", "a file-static in its own file"
    # platform.c is outside the Makefile's targets, so it has no lane B, and lane A's same-file tie on `sep` abstains.
    assert ("src/platform.path_separator", "src/platform.sep") not in calls
    steps = {s["step"]: s["contained"] for s in graph["containment"]["steps"]}
    assert steps.get("index-c") is True
    c_disagreements = [d for d in graph["lane_agreement"]["site_disagreements"] if d["file"].endswith((".c", ".h"))]
    assert c_disagreements == [], "where both lanes answer for C, they agree"

    # ADR-111 (C-138's own shape): `mentions_add`'s call to `strcasestr`
    # has a same-file rank-1 fallback naming the dead `#if defined(_WIN32)`
    # shim; lane B resolves the call to glibc's declaration, outside the
    # repo, and the join must veto the guess rather than draw it.
    assert ("src/util.mentions_add", "src/util.strcasestr") not in calls
    [row] = [r for r in graph["resolution_coverage"] if r["file"] == "src/util.c"]
    assert row["external"] >= 1, "the site's fate is external, as C-138 already counted it"
    assert graph["lane_agreement"]["external_vetoes"]["sites"] == 1


@pytest.mark.lane_b
def test_minicpp_gets_semantic_cpp_edges_through_bear_over_its_makefile():
    """C++ at lane B (ADR-113 §2), end to end: the fixture holds no `.c` file
    at all, so its root is a C++ root — scip-clang's own language — and the
    edges lane A could only abstain on come back semantic. The three the
    unit exists for: each overload on its own symbol (C-144), a construction
    on the constructor rather than on its class, and a member call on the
    receiver's static type."""
    from hobbes.extract import containment, extract_repo

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINICPP).graph
    errors = graph.get("extraction_errors", [])
    why = [e for e in errors if e["stage"].startswith("scip")]
    edges = {(e["from"], e["to"], e["type"]): e for e in graph["symbol_edges"]}
    calls = {(f, t): e for (f, t, kind), e in edges.items() if kind == "calls"}

    def lines(edge):
        return sorted({site["line"] for site in edge["evidence"]})

    assert calls[("src/main.main", "src/util.scale")]["tier"] == "semantic", why
    # C-144's fix, measured: `shapes::area(1)` at main.cpp:8 is the `int`
    # overload, `shapes::area(2.5)` at :12 the `double` one. Lane A abstains
    # on both — only argument types tell them apart — and before the fix the
    # second had no symbol to land on at all.
    first = calls[("src/main.main", "src/shapes.shapes::area")]
    second = calls[("src/main.main", "src/shapes.shapes::area~2")]
    assert (first["tier"], lines(first)) == ("semantic", [8]), why
    assert (second["tier"], lines(second)) == ("semantic", [12]), why

    # The construction rule: `shapes::Circle c(3)` draws the constructor,
    # not the class, and the class keeps no `calls` edge at all.
    ctor = "include/minicpp/shapes.h.shapes::Circle::Circle"
    assert calls[("src/main.main", ctor)]["tier"] == "semantic", why
    assert ("src/main.main", "include/minicpp/shapes.h.shapes::Circle") not in calls
    # `Circle made(2)` and `new Circle(1)`, the two spellings, one target.
    assert lines(calls[("src/shapes.shapes::measure", ctor)]) == [38, 39], why

    # `p->area()` and `Circle::unit()`: the receiver's type is lane B's to know.
    assert ("src/shapes.shapes::measure", "src/shapes.shapes::Circle::area") in calls
    assert ("src/shapes.shapes::measure", "src/shapes.shapes::Circle::unit") in calls

    steps = {s["step"]: s["contained"] for s in graph["containment"]["steps"]}
    assert steps.get("index-c") is True, "C++ runs in C's profile (ADR-113 §2)"
    # Rule 2 of §2's third amendment: every file the Makefile's default
    # target builds is one scip-clang compiled, so no guess of lane A's
    # survives in it. The count is reported whether or not anything was
    # withheld. `tests/test_shapes.cpp` is built only by `make test`, which
    # bear over the default target never runs: lane B holds no occurrence
    # there, and the file keeps its fallback (the rule's other half).
    assert isinstance(graph["lane_agreement"]["cpp_withheld"]["sites"], int)
    built = ("src/main.cpp", "src/shapes.cpp", "src/util.cpp")
    guessed = [
        (f, t, site["path"], site["line"])
        for (f, t, kind), e in edges.items()
        if kind == "calls" and e["tier"] == "syntactic"
        for site in e["evidence"]
        if site["path"] in built
    ]
    assert guessed == [], "a file lane B compiled draws no fallback edge"
    assert calls[("tests/test_shapes.Shapes.Scale", "src/util.scale")]["tier"] == "syntactic", (
        "a C++ file lane B did not index keeps its fallback"
    )
    disagreements = [
        d for d in graph["lane_agreement"]["site_disagreements"]
        if d["file"].endswith((".cpp", ".h"))
    ]
    assert disagreements == [], "where both lanes answer for C++, they agree"
    assert [e for e in errors if e["stage"] == "parse" and e["path"] == "src/shapes.cpp"] == [], (
        "an overload set is not a duplicate definition"
    )
    # scip-clang declares `shapes/` from every file that opens it, so the
    # duplicate-symbol record fires — in C++'s words, not C's statics-only ones.
    statics = [e for e in errors if e["stage"] == "scip-decode" and "file-`static`s" in e["message"]]
    assert all(
        "a namespace is declared from every file that opens it" in e["message"] for e in statics
    ), statics
