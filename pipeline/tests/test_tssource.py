"""TS/JS extraction (ADR-021): hobbes.extract.tssource.

The join is tested hermetically against canned facts; the helper's own
behavior has its node --test suite in tsextract/. The integration tests
at the bottom run the real helper over the minits fixture and skip when
Node or the helper's node_modules are absent.
"""

import json
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from hobbes.extract import SCHEMA_VERSION

from hobbes.extract.tssource import (
    HELPER_VERSION,
    collect_ts_tests,
    TsExtractError,
    extract_ts,
    has_ts_files,
    join_facts,
    module_id,
    run_helper,
)

FIXTURE = Path(__file__).parent / "fixtures" / "minits"
HELPER = Path(__file__).parents[2] / "tsextract" / "extract.mjs"


def facts(files):
    return {"helper_version": HELPER_VERSION, "tsconfigs": [], "files": files}


def file_facts(path, **overrides):
    base = {
        "path": path,
        "imports": [],
        "symbols": [],
        "calls": [],
        "env_reads": [],
        "routes": [],
        "test_framework": None,
        "tests": [],
    }
    base.update(overrides)
    # helper v2 positions a site on its terminal identifier and names it;
    # filled in here so the cases stay about the join, not the shape.
    base["calls"] = [
        {"name": (call.get("callee") or "").rsplit(".", 1)[-1], "col": 0, **call}
        for call in base["calls"]
    ]
    base["tests"] = [
        {"end_line": case["line"], **case} for case in base["tests"]
    ]
    return base


def symbol_layer(joined):
    """The symbol edges these facts produce, lane A only.

    Since ADR-031 `join_facts` emits no edges: ts-morph's resolutions are
    the join's fallback, and the join is the only edge producer. With no
    semantic input every site falls to the fallback arm, which is the
    degraded path P6 promises and the one the suite runs by default.
    """
    from hobbes.extract import evidence as ev
    from hobbes.extract.scipsource import project

    resolved = ev.join(joined["call_sites"], [], fallback=joined["call_fallback"])
    return project(resolved, joined["nodes"], joined["symbols"])["symbol_edges"]


class TestModuleId:
    def test_strips_known_extensions_only(self):
        assert module_id("src/flow.js") == "src/flow"
        assert module_id("src/a.test.mjs") == "src/a.test"
        assert module_id("src/data.json") == "src/data.json"


class TestJoinFacts:
    def test_modules_imports_externals_and_env(self):
        joined = join_facts(
            facts(
                [
                    file_facts(
                        "src/main.js",
                        imports=[
                            {
                                "specifier": "./util.js",
                                "resolved": "src/util.js",
                                "external": None,
                                "names": ["helper"],
                                "line": 1,
                            },
                            {
                                "specifier": "express",
                                "resolved": None,
                                "external": "express",
                                "names": [],
                                "line": 2,
                            },
                            # A Node builtin, kept as an external since
                            # ADR-038 lifted C-3 — normalised to node:fs
                            # by the helper's externalName.
                            {
                                "specifier": "node:fs",
                                "resolved": None,
                                "external": "node:fs",
                                "names": [],
                                "line": 3,
                            },
                        ],
                        env_reads=[{"var": "API_URL", "line": 5}],
                    ),
                    file_facts("src/util.js"),
                ]
            )
        )
        assert [n["id"] for n in joined["nodes"]] == [
            "env:API_URL",
            "ext:express",
            "ext:node:fs",
            "src/main",
            "src/util",
        ]
        assert joined["languages"] == ["javascript"]
        edges = {(e["from"], e["to"], e["type"]) for e in joined["module_edges"]}
        assert edges == {
            ("src/main", "src/util", "imports"),
            ("src/main", "ext:express", "imports"),
            ("src/main", "ext:node:fs", "imports"),
            ("src/main", "env:API_URL", "env-read"),
        }

    def test_duplicate_imports_merge_evidence(self):
        imp = {
            "specifier": "./util.js",
            "resolved": "src/util.js",
            "external": None,
            "names": [],
        }
        joined = join_facts(
            facts(
                [
                    file_facts(
                        "src/main.js",
                        imports=[{**imp, "line": 1}, {**imp, "line": 9}],
                    ),
                    file_facts("src/util.js"),
                ]
            )
        )
        (edge,) = joined["module_edges"]
        assert [e["line"] for e in edge["evidence"]] == [1, 9]

    def test_symbols_and_calls_are_module_qualified(self):
        joined = join_facts(
            facts(
                [
                    file_facts(
                        "src/util.js",
                        symbols=[
                            {
                                "name": "helper",
                                "qualname": "helper",
                                "kind": "function",
                                "line": 1,
                                "end_line": 3,
                            }
                        ],
                    ),
                    file_facts(
                        "src/main.js",
                        symbols=[
                            {
                                "name": "run",
                                "qualname": "run",
                                "kind": "function",
                                "line": 2,
                                "end_line": 4,
                            }
                        ],
                        calls=[
                            {
                                "callee": "helper",
                                "callee_path": "src/util.js",
                                "scope": "run",
                                "line": 3,
                            },
                            {
                                "callee": "run",
                                "callee_path": "src/main.js",
                                "scope": None,
                                "line": 6,
                            },
                        ],
                    ),
                ]
            )
        )
        assert [s["id"] for s in joined["symbols"]] == [
            "src/main.run",
            "src/util.helper",
        ]
        assert {(e["from"], e["to"]) for e in symbol_layer(joined)} == {
            ("src/main.run", "src/util.helper"),
            ("src/main", "src/main.run"),
        }

    def test_languages_ts_and_js(self):
        joined = join_facts(
            facts([file_facts("src/a.ts"), file_facts("src/b.js")])
        )
        assert joined["languages"] == ["javascript", "typescript"]

    def test_routes_module_qualify_resolved_handlers(self):
        joined = join_facts(
            facts(
                [
                    file_facts(
                        "src/server.js",
                        routes=[
                            {
                                "framework": "express",
                                "method": "GET",
                                "path": "/items",
                                "handler": "listItems",
                                "handler_path": "src/server.js",
                                "line": 4,
                            },
                            {
                                "framework": "express",
                                "method": "POST",
                                "path": "/items",
                                "handler": "<inline>",
                                "handler_path": None,
                                "line": 5,
                            },
                        ],
                    )
                ]
            )
        )
        assert [r["handler"] for r in joined["routes"]] == [
            "src/server.listItems",
            "<inline>",
        ]

    def test_tests_file_level_reach_with_closure(self):
        joined = join_facts(
            facts(
                [
                    file_facts(
                        "src/util.js",
                        symbols=[
                            {"name": "helper", "qualname": "helper", "kind": "function", "line": 1, "end_line": 2},
                            {"name": "inner", "qualname": "inner", "kind": "function", "line": 3, "end_line": 4},
                        ],
                        calls=[
                            {"callee": "inner", "callee_path": "src/util.js", "scope": "helper", "line": 2}
                        ],
                    ),
                    file_facts(
                        "tests/util.test.mjs",
                        imports=[
                            {
                                "specifier": "../src/util.js",
                                "resolved": "src/util.js",
                                "external": None,
                                "names": ["helper"],
                                "line": 2,
                            }
                        ],
                        calls=[
                            {"callee": "helper", "callee_path": "src/util.js", "scope": None, "line": 5},
                            {"callee": "helper", "callee_path": "src/util.js", "scope": None, "line": 9},
                        ],
                        test_framework="node:test",
                        tests=[
                            {"qualname": "helper works", "line": 4, "end_line": 6},
                            {"qualname": "suite > helper again", "line": 8, "end_line": 10},
                        ],
                    ),
                ]
            )
        )
        first, second = collect_ts_tests(
            joined["files"], joined["symbols"], symbol_layer(joined)
        )
        assert first["id"] == "tests/util.test.mjs::helper works"
        assert first["framework"] == "node:test"
        # Each case calls helper inside its own range, and reach closes
        # over helper -> inner. Reach is call-based, exactly as pytest's
        # is (ADR-007) — importing a name is not exercising it (C-11).
        assert first["reaches"] == ["src/util.helper", "src/util.inner"]
        assert second["reaches"] == first["reaches"]
        # Module-level guarding stays file-level: importing a module
        # guards it even when nothing named is in the symbol layer.
        assert first["reaches_modules"] == ["src/util"]

    def test_test_file_own_symbols_excluded_from_reach(self):
        joined = join_facts(
            facts(
                [
                    file_facts(
                        "tests/x.test.js",
                        symbols=[
                            {"name": "fake", "qualname": "fake", "kind": "function", "line": 1, "end_line": 2}
                        ],
                        calls=[
                            {"callee": "fake", "callee_path": "tests/x.test.js", "scope": None, "line": 3}
                        ],
                        test_framework="jest",
                        tests=[{"qualname": "uses a local fake", "line": 4}],
                    )
                ]
            )
        )
        (record,) = collect_ts_tests(
            joined["files"], joined["symbols"], symbol_layer(joined)
        )
        assert record["reaches"] == []
        assert record["reaches_modules"] == []


    def test_imported_module_guarded_even_without_symbol_match(self, tmp_path):
        # A test importing a module guards it even when nothing it names
        # is in the symbol layer (zustand stores, mocked modules).
        joined = join_facts(
            facts(
                [
                    file_facts("src/store.ts"),  # no modeled symbols
                    file_facts(
                        "tests/store.test.ts",
                        imports=[
                            {
                                "specifier": "@/store",
                                "resolved": "src/store.ts",
                                "external": None,
                                "names": ["useStore"],
                                "line": 1,
                            }
                        ],
                        test_framework="vitest",
                        tests=[{"qualname": "store works", "line": 3}],
                    ),
                ]
            )
        )
        (record,) = collect_ts_tests(
            joined["files"], joined["symbols"], symbol_layer(joined)
        )
        assert record["reaches"] == []
        assert record["reaches_modules"] == ["src/store"]


class TestPerCaseReach:
    """C-11: a JS case reaches what *it* calls, not what its file calls.

    File-level reach made `tests_guarding` over-report on TS repos — the
    only number in the system larger than the truth — and a JS row was
    indistinguishable from a precise pytest one.
    """

    @staticmethod
    def _facts():
        return facts(
            [
                file_facts(
                    "src/a.ts",
                    symbols=[
                        {"name": n, "qualname": n, "kind": "function", "line": ln, "end_line": ln + 1}
                        for n, ln in (("alpha", 1), ("beta", 5), ("setup", 9))
                    ],
                ),
                file_facts(
                    "tests/x.test.ts",
                    imports=[
                        {
                            "specifier": "../src/a.js",
                            "resolved": "src/a.ts",
                            "external": None,
                            "names": [],
                            "line": 1,
                        }
                    ],
                    calls=[
                        # shared setup, outside every case
                        {"callee": "setup", "callee_path": "src/a.ts", "scope": None, "line": 3},
                        # inside case one (lines 5-7)
                        {"callee": "alpha", "callee_path": "src/a.ts", "scope": None, "line": 6},
                        # inside case two (lines 9-11)
                        {"callee": "beta", "callee_path": "src/a.ts", "scope": None, "line": 10},
                    ],
                    test_framework="vitest",
                    tests=[
                        {"qualname": "one", "line": 5, "end_line": 7},
                        {"qualname": "two", "line": 9, "end_line": 11},
                    ],
                ),
            ]
        )

    def test_each_case_reaches_only_its_own_calls(self):
        joined = join_facts(self._facts())
        one, two = collect_ts_tests(
            joined["files"], joined["symbols"], symbol_layer(joined)
        )
        assert one["id"].endswith("::one") and two["id"].endswith("::two")
        assert "src/a.alpha" in one["reaches"]
        assert "src/a.beta" not in one["reaches"], "case one must not claim case two's call"
        assert "src/a.beta" in two["reaches"]
        assert "src/a.alpha" not in two["reaches"]

    def test_shared_setup_reaches_every_case(self):
        """beforeEach and describe-level calls really do run for each case.

        Attributing only in-range calls would trade the old over-report
        for an under-report, which is not an improvement.
        """
        joined = join_facts(self._facts())
        rows = collect_ts_tests(
            joined["files"], joined["symbols"], symbol_layer(joined)
        )
        assert all("src/a.setup" in r["reaches"] for r in rows)


class TestHasTsFiles:
    def test_finds_and_skips(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "x.js").write_text("")
        assert not has_ts_files(tmp_path)
        (tmp_path / "app.mjs").write_text("")
        assert has_ts_files(tmp_path)


class TestRunHelper:
    def fake_helper(self, tmp_path, monkeypatch, body):
        script = tmp_path / "fake-tsextract"
        script.write_text(f"#!/bin/sh\n{body}\n")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        monkeypatch.setenv("HOBBES_TSEXTRACT_CMD", str(script))
        return script

    def test_canned_facts_roundtrip(self, tmp_path, monkeypatch):
        canned = facts([file_facts("src/a.js")])
        self.fake_helper(
            tmp_path, monkeypatch, f"cat <<'EOF'\n{json.dumps(canned)}\nEOF"
        )
        assert run_helper(tmp_path) == canned

    def test_missing_binary_says_how_to_fix(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOBBES_TSEXTRACT_CMD", "/nonexistent/helper")
        with pytest.raises(TsExtractError, match="npm install"):
            run_helper(tmp_path)

    def test_nonzero_exit_carries_stderr(self, tmp_path, monkeypatch):
        self.fake_helper(tmp_path, monkeypatch, "echo doom >&2\nexit 3")
        with pytest.raises(TsExtractError, match="exited 3: doom"):
            run_helper(tmp_path)

    def test_wrong_version_rejected(self, tmp_path, monkeypatch):
        self.fake_helper(
            tmp_path, monkeypatch, 'echo \'{"helper_version": 99, "files": []}\''
        )
        with pytest.raises(TsExtractError, match="version 99"):
            run_helper(tmp_path)

    def test_extract_ts_none_without_ts_files(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOBBES_TSEXTRACT_CMD", "/nonexistent/helper")
        (tmp_path / "only.py").write_text("x = 1\n")
        assert extract_ts(tmp_path) is None


def helper_available() -> bool:
    return (
        shutil.which("node") is not None
        and (HELPER.parent / "node_modules" / "ts-morph").is_dir()
    )


@pytest.fixture(scope="module")
def joined(tmp_path_factory):
    if not helper_available():
        pytest.skip("node/ts-morph not installed")
    # Copy the fixture so the repo root is exactly minits.
    root = tmp_path_factory.mktemp("minits-repo")
    shutil.copytree(FIXTURE, root / "minits")
    return extract_ts(root / "minits")


@pytest.mark.skipif(not helper_available(), reason="node/ts-morph not installed")
class TestIntegrationMinits:
    """The real helper over the minits fixture (ADR-021 end to end)."""

    def test_languages_and_nodes(self, joined):
        assert joined["languages"] == ["javascript", "typescript"]
        ids = [n["id"] for n in joined["nodes"]]
        assert "src/server" in ids and "src/util" in ids
        assert "ext:express" in ids and "ext:@nestjs/common" in ids
        assert "env:MINITS_API_URL" in ids

    def test_import_and_env_edges(self, joined):
        edges = {(e["from"], e["to"], e["type"]) for e in joined["module_edges"]}
        assert ("src/server", "src/util", "imports") in edges
        assert ("src/items.controller", "src/util", "imports") in edges
        assert ("src/util", "env:MINITS_API_URL", "env-read") in edges

    def test_call_edge_into_util(self, joined):
        assert {
            (e["from"], e["to"]) for e in symbol_layer(joined)
        } >= {("src/server.listItems", "src/util.normalize")}

    def test_routes_express_and_nest(self, joined):
        routes = {(r["framework"], r["method"], r["path"]) for r in joined["routes"]}
        assert routes == {
            ("express", "GET", "/items"),
            ("express", "POST", "/items"),
            ("nest", "GET", "/items/:id"),
        }

    def test_test_inventory_both_frameworks(self, joined):
        by_framework = {}
        for t in collect_ts_tests(
            joined["files"], joined["symbols"], symbol_layer(joined)
        ):
            by_framework.setdefault(t["framework"], []).append(t)
        assert len(by_framework["node:test"]) == 2
        assert by_framework["node:test"][0]["reaches_modules"] == ["src/util"]
        assert [t["id"] for t in by_framework["vitest"]] == [
            "src/math.spec.ts::math > adds"
        ]


@pytest.mark.skipif(not helper_available(), reason="node/ts-morph not installed")
class TestLinkedCopiesAgree:
    """C-73's residual, closed 2026-09-05: the helper's walk follows the
    Python rule — an in-repo directory link is walked once at its
    target, a link to outside the repo and a file link are followed —
    so `has_ts_files` and the helper's file set cannot disagree on a
    link. Before, the helper skipped every symlink, and a repo whose only
    copy sat behind a link was lane-A-less there."""

    def test_the_helper_walks_what_the_python_walk_walks(self, tmp_path):
        from hobbes.extract.discover import linked_copies

        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "m.ts").write_text("export const m = 1;\n")
        repo = tmp_path / "repo"
        (repo / "core").mkdir(parents=True)
        (repo / "core" / "a.ts").write_text("export const a = 1;\n")
        (repo / "shared").mkdir()
        (repo / "shared" / "src").symlink_to(repo / "core", target_is_directory=True)
        (repo / "vendored").symlink_to(outside, target_is_directory=True)
        (repo / "alias.ts").symlink_to(repo / "core" / "a.ts")

        assert has_ts_files(repo)
        assert linked_copies(repo) == [("shared/src", "core")]
        facts = run_helper(repo)
        assert sorted(f["path"] for f in facts["files"]) == ["alias.ts", "core/a.ts", "vendored/m.ts"]

    def test_a_repo_whose_only_ts_sits_behind_an_outside_link_is_not_lane_a_less(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "only.ts").write_text("export function only() { return 1; }\n")
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "vendored").symlink_to(outside, target_is_directory=True)

        assert has_ts_files(repo)
        joined = extract_ts(repo)
        assert joined is not None
        assert "vendored/only" in {n["id"] for n in joined["nodes"]}


@pytest.mark.skipif(not helper_available(), reason="node/ts-morph not installed")
class TestIntegrationIngest:
    def test_full_ingest_merges_layers(self, tmp_path):
        repo = tmp_path / "repo"
        shutil.copytree(FIXTURE, repo)
        (repo / "app.py").write_text("import json\nVALUE = 1\n")
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git[:3], "init", "-q"], check=True)
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-qm", "one"], check=True)

        from hobbes.extract import ingest

        paths = {p.name: json.loads(p.read_text()) for p in ingest(repo)}
        graph = paths["graph.json"]
        assert graph["schema_version"] == SCHEMA_VERSION
        assert graph["languages"] == ["javascript", "python", "typescript"]
        ids = {n["id"] for n in graph["nodes"]}
        assert {"app", "src/server", "src/util"} <= ids
        tests = paths["tests.json"]["tests"]
        assert {t["framework"] for t in tests} == {"node:test", "vitest"}
        assert "framework" not in paths["tests.json"]
        routes = paths["interfaces.json"]["routes"]
        assert {r["framework"] for r in routes} == {"express", "nest"}

    def test_ts_only_repo_claims_no_python(self, tmp_path):
        repo = tmp_path / "tsrepo"
        shutil.copytree(FIXTURE, repo)
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git[:3], "init", "-q"], check=True)
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-qm", "one"], check=True)

        from hobbes.extract import ingest

        graph = {p.name: json.loads(p.read_text()) for p in ingest(repo)}["graph.json"]
        assert graph["languages"] == ["javascript", "typescript"]



@pytest.mark.skipif(not helper_available(), reason="node/ts-morph not installed")
class TestRenderOnlyTestReach:
    """C-24, lifted: a test that only renders a component reaches it.

    The whole pipeline on a real .tsx repo — helper, join, fallback arm,
    test collection — because the debt was end-to-end: `<Card />` was a
    `uses` edge, reach follows `calls`, and a render-only test showed an
    empty reach that read as "nothing guards this".
    """

    def test_rendering_a_component_reaches_it(self, tmp_path):
        repo = tmp_path / "app"
        (repo / "src").mkdir(parents=True)
        (repo / "src" / "card.tsx").write_text(
            "import { label } from \"./label.js\";\n"
            "export function Card() {\n"
            "  return <div>{label()}</div>;\n"
            "}\n"
        )
        (repo / "src" / "label.tsx").write_text(
            "export function label() { return \"hi\"; }\n"
        )
        (repo / "src" / "card.test.tsx").write_text(
            "import { test } from \"vitest\";\n"
            "import { render } from \"@testing-library/react\";\n"
            "import { Card } from \"./card.js\";\n"
            "test(\"renders\", () => {\n"
            "  render(<Card />);\n"
            "});\n"
        )

        from hobbes.extract import extract_repo

        extraction = extract_repo(repo)
        (record,) = [
            t
            for t in extraction.tests["tests"]
            if t["id"].endswith("::renders")
        ]
        # The render is a call site, so reach closes over Card and what
        # Card itself calls — not empty, and not just the direct render.
        assert "src/card.Card" in record["reaches"]
        assert "src/label.label" in record["reaches"]

        # The honesty half: the calls edge exists and carries evidence at
        # the JSX site's own line.
        edges = [
            e
            for e in extraction.graph["symbol_edges"]
            if e["type"] == "calls"
            and e["to"] == "src/card.Card"
            and e["from"].startswith("src/card.test")
        ]
        assert edges, "the render site must be a calls edge"
        assert edges[0]["evidence"][0]["line"] == 5
