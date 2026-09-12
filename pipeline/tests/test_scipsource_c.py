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
            seen.update(config=config, files=sorted(p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()),
                        build_dir_existed=Path(config["buildDir"]).is_dir())
            return {"definitions": [{"moniker": "m", "file": "src/a.c", "line": 1, "end_line": 1, "kind": "method"}],
                    "references": [], "external_refs": [], "degraded": []}

        monkeypatch.setattr(scipsource, "run_helper", fake)
        merged = scipsource.extract_scip_c(repo, ["proj/src/a.c"])
        assert seen["config"]["language"] == "c" and seen["config"]["compdbSource"] == "make"
        assert seen["files"] == ["Makefile", "src/a.c", "tools/gen.sh"], "the whole tree, less build output"
        assert seen["build_dir_existed"] and not Path(seen["config"]["buildDir"]).exists(), "made before, removed after"
        assert merged["definitions"][0]["file"] == "proj/src/a.c", "paths come back re-rooted at the repo"

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
