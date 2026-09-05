"""Lane B's SCIP facts, and their projection onto lane A's ids (ADR-029).

The join itself lives in `test_evidence.py` — this covers getting SCIP's
references *into* the evidence IR, and projecting the joined result back
onto module and symbol ids. Both are pure, so no indexer runs here; the
end-to-end path is the M2 exit check.
"""

import json
import subprocess
from pathlib import Path

import pytest

from hobbes.extract import evidence as ev
from hobbes.extract import containment, scipsource, staging
from hobbes.extract.schema import LANE_SCIP, LANE_TREE_SITTER, SEMANTIC, SYNTACTIC

NODES = [
    {"id": "app.core", "kind": "module", "path": "src/app/core.py"},
    {"id": "app.api", "kind": "module", "path": "src/app/api.py"},
    {"id": "ext:requests", "kind": "external"},
]
SYMBOLS = [
    {"id": "app.core.Engine", "module": "app.core", "kind": "class",
     "line": 10, "end_line": 30},
    {"id": "app.core.Engine.run", "module": "app.core", "kind": "function",
     "line": 15, "end_line": 20},
    {"id": "app.api.handler", "module": "app.api", "kind": "function",
     "line": 5, "end_line": 9},
]


class TestResolutionSites:
    def test_references_become_evidence_ir_sites(self):
        sites = scipsource.resolution_sites(
            {"references": [{"file": "a.py", "line": 3, "col": 8, "name": "run",
                             "def_file": "b.py", "def_line": 5}]}
        )
        assert len(sites) == 1
        site = sites[0]
        assert (site.provider, site.kind) == (ev.SCIP, ev.RESOLUTION)
        assert (site.file, site.line, site.col, site.name) == ("a.py", 3, 8, "run")
        assert (site.def_file, site.def_line) == ("b.py", 5)

    def test_facts_without_references_yield_nothing(self):
        assert scipsource.resolution_sites({}) == []


def resolved(kind, file, line, def_file, def_line, tier=SEMANTIC, scope="",
             lanes=(ev.TREE_SITTER, ev.SCIP)):
    return ev.Resolved(kind, file, line, scope, def_file, def_line, tier, lanes)


class TestProjection:
    def test_a_call_projects_onto_symbol_ids(self):
        out = scipsource.project(
            [resolved("calls", "src/app/api.py", 7, "src/app/core.py", 15)],
            NODES, SYMBOLS,
        )
        edge = out["symbol_edges"][0]
        assert (edge["from"], edge["to"]) == ("app.api.handler", "app.core.Engine.run")
        assert edge["type"] == "calls"
        assert edge["tier"] == SEMANTIC
        assert edge["evidence"][0]["lane"] == LANE_SCIP

    def test_a_cross_module_fact_also_makes_a_module_edge(self):
        out = scipsource.project(
            [resolved("calls", "src/app/api.py", 7, "src/app/core.py", 15)],
            NODES, SYMBOLS,
        )
        edge = out["module_edges"][0]
        assert (edge["from"], edge["to"], edge["type"]) == ("app.api", "app.core", "imports")

    def test_a_same_module_fact_makes_no_module_edge(self):
        out = scipsource.project(
            [resolved("calls", "src/app/core.py", 16, "src/app/core.py", 15)],
            NODES, SYMBOLS,
        )
        assert out["module_edges"] == []

    def test_an_explicit_scope_wins_over_the_enclosing_lookup(self):
        # tree-sitter already knows the enclosing definition; when it says
        # so, that is better evidence than a range lookup.
        out = scipsource.project(
            [resolved("calls", "src/app/core.py", 17, "src/app/api.py", 5,
                      scope="app.core.Engine")],
            NODES, SYMBOLS,
        )
        assert out["symbol_edges"][0]["from"] == "app.core.Engine"

    def test_module_level_code_is_attributed_to_the_module(self):
        out = scipsource.project(
            [resolved("calls", "src/app/api.py", 2, "src/app/core.py", 15)],
            NODES, SYMBOLS,
        )
        assert out["symbol_edges"][0]["from"] == "app.api"

    def test_a_file_lane_a_never_discovered_is_dropped(self):
        out = scipsource.project(
            [resolved("calls", "vendor/x.py", 1, "src/app/core.py", 15)],
            NODES, SYMBOLS,
        )
        assert out["module_edges"] == [] and out["symbol_edges"] == []

    def test_a_syntactic_fact_keeps_its_tier_and_lane(self):
        out = scipsource.project(
            [resolved("calls", "src/app/api.py", 7, "src/app/core.py", 15,
                      tier=SYNTACTIC, lanes=(ev.TREE_SITTER,))],
            NODES, SYMBOLS,
        )
        edge = out["symbol_edges"][0]
        assert edge["tier"] == SYNTACTIC
        assert edge["evidence"][0]["lane"] == LANE_TREE_SITTER

    def test_references_stay_a_distinct_edge_type(self):
        out = scipsource.project(
            [resolved("uses", "src/app/api.py", 7, "src/app/core.py", 15,
                      lanes=(ev.SCIP,))],
            NODES, SYMBOLS,
        )
        assert out["symbol_edges"][0]["type"] == "uses"

    def test_facts_of_different_tiers_do_not_collapse(self):
        # One proven, one guessed, same endpoints: two claims, not one.
        out = scipsource.project(
            [
                resolved("calls", "src/app/api.py", 7, "src/app/core.py", 15),
                resolved("calls", "src/app/api.py", 8, "src/app/core.py", 15,
                         tier=SYNTACTIC, lanes=(ev.TREE_SITTER,)),
            ],
            NODES, SYMBOLS,
        )
        tiers = sorted(e["tier"] for e in out["symbol_edges"])
        assert tiers == [SEMANTIC, SYNTACTIC]

    def test_repeated_sightings_merge_into_one_edge(self):
        out = scipsource.project(
            [
                resolved("calls", "src/app/api.py", 7, "src/app/core.py", 15),
                resolved("calls", "src/app/api.py", 8, "src/app/core.py", 15),
                resolved("calls", "src/app/api.py", 8, "src/app/core.py", 15),
            ],
            NODES, SYMBOLS,
        )
        assert len(out["symbol_edges"]) == 1
        assert len(out["symbol_edges"][0]["evidence"]) == 2  # deduped


class TestOneUnitFailsAlone:
    """One zone/module/crate failing must not cost the others their
    semantics (P6 at the failure's own granularity). Before the per-unit
    catch, dagger's one docs zone missing `@docusaurus/tsconfig` zeroed
    all 84 TypeScript zones."""

    FACTS = {
        "definitions": [], "references": [{"file": "ok"}],
        "external_refs": [], "packages": {}, "degraded": [],
        "dependency_coverage": {"declared": 0, "resolved": 0, "missing": []},
    }

    def _enable(self, monkeypatch):
        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")

    def test_a_broken_ts_zone_degrades_alone(self, monkeypatch, tmp_path):
        self._enable(monkeypatch)
        monkeypatch.setattr(
            scipsource, "ts_zones",
            lambda *a: {"docs": ["docs/a.ts"], "web": ["web/b.ts"]},
        )

        def index(repo_root, zone, files, sha):
            if zone == "docs":
                raise scipsource.ScipError("tsconfig not found")
            return dict(self.FACTS)

        monkeypatch.setattr(scipsource, "_index_ts_zone", index)
        merged = scipsource.extract_scip_typescript(tmp_path, ["web/b.ts"])
        assert merged["references"] == [{"file": "ok"}]
        (record,) = merged["degraded"]
        assert record["path"] == "docs" and record["stage"] == "scip-typescript"
        assert "alone" in record["message"] and "tsconfig" in record["message"]

    def test_a_broken_go_module_degrades_alone(self, monkeypatch, tmp_path):
        self._enable(monkeypatch)
        monkeypatch.setattr(
            scipsource, "go_modules",
            lambda *a: {"e2e": ["e2e/a.go"], "": ["main.go"]},
        )

        def index(repo_root, module_root, files, sha, grouped=None):
            if module_root == "e2e":
                raise scipsource.ScipError("loader failed")
            return dict(self.FACTS)

        monkeypatch.setattr(scipsource, "_index_go_module", index)
        merged = scipsource.extract_scip_go(tmp_path, ["main.go", "e2e/a.go"])
        assert merged["references"] == [{"file": "ok"}]
        (record,) = merged["degraded"]
        assert record["path"] == "e2e" and record["stage"] == "scip-go"

    def test_a_broken_cargo_root_degrades_alone(self, monkeypatch, tmp_path):
        self._enable(monkeypatch)
        monkeypatch.setattr(
            scipsource, "cargo_crates",
            lambda *a: {"sdk/rust": ["sdk/rust/a.rs"], "": ["src/lib.rs"]},
        )

        def index(repo_root, root, files, sha):
            if root == "sdk/rust":
                raise scipsource.ScipError("cargo metadata failed")
            return dict(self.FACTS)

        monkeypatch.setattr(scipsource, "_index_cargo_root", index)
        merged = scipsource.extract_scip_rust(
            tmp_path, ["src/lib.rs", "sdk/rust/a.rs"]
        )
        assert merged["references"] == [{"file": "ok"}]
        (record,) = merged["degraded"]
        assert record["path"] == "sdk/rust" and record["stage"] == "scip-rust"

    def test_the_unit_catch_is_no_broader_than_the_language_catch(self):
        # P10: the per-unit tuple must not quietly absorb anything the
        # per-language handler would have let through.
        assert scipsource.UNIT_ERRORS == (
            scipsource.ScipError, staging.StagingError, OSError,
        )


class TestCrossUnitJoin:
    """ADR-049: external references join sibling units' definitions by
    exact moniker equality — never heuristically — and ambiguity
    abstains, reported (C-28's rule across units)."""

    MONIKER = "scip-go gomod dagger.io/dagger 0 `dagger.io/dagger`/Hello()."

    def merged(self, definitions, external_refs):
        return {
            "definitions": definitions,
            "references": [],
            "external_refs": external_refs,
            "packages": {},
            "degraded": [],
            "dependency_coverage": {"declared": 0, "resolved": 0, "missing": []},
        }

    def test_an_external_ref_joins_a_sibling_units_definition(self):
        merged = self.merged(
            [{"moniker": self.MONIKER, "file": "sdk/go/api.go", "line": 4,
              "end_line": 4, "kind": "method"}],
            [{"file": "main.go", "line": 6, "col": 5, "name": "Hello",
              "package": "gomod:dagger.io/dagger", "moniker": self.MONIKER}],
        )
        scipsource.join_cross_unit(merged)
        (ref,) = merged["references"]
        assert ref["def_file"] == "sdk/go/api.go" and ref["def_line"] == 4
        assert ref["file"] == "main.go" and ref["name"] == "Hello"
        assert merged["external_refs"] == []

    def test_a_truly_external_ref_stays_external(self):
        rows = [{"file": "main.go", "line": 2, "col": 0, "name": "Sprintf",
                 "package": "gomod:github.com/golang/go/src",
                 "moniker": "scip-go gomod github.com/golang/go/src go1.26 fmt/Sprintf()."}]
        merged = self.merged([], list(rows))
        scipsource.join_cross_unit(merged)
        assert merged["references"] == [] and merged["external_refs"] == rows

    def test_a_ref_without_a_moniker_stays_external(self):
        # A v2 helper's rows carry no moniker; the join must not invent one.
        rows = [{"file": "main.go", "line": 2, "col": 0, "name": "Hello",
                 "package": "gomod:dagger.io/dagger"}]
        merged = self.merged(
            [{"moniker": self.MONIKER, "file": "sdk/go/api.go", "line": 4,
              "end_line": 4, "kind": "method"}],
            list(rows),
        )
        scipsource.join_cross_unit(merged)
        assert merged["references"] == [] and merged["external_refs"] == rows

    def test_a_moniker_two_units_define_abstains_and_reports(self):
        merged = self.merged(
            [{"moniker": self.MONIKER, "file": "sdk/go/api.go", "line": 4,
              "end_line": 4, "kind": "method"},
             {"moniker": self.MONIKER, "file": "modules/x/api.go", "line": 9,
              "end_line": 9, "kind": "method"}],
            [{"file": "main.go", "line": 6, "col": 5, "name": "Hello",
              "package": "gomod:dagger.io/dagger", "moniker": self.MONIKER}],
        )
        scipsource.join_cross_unit(merged)
        assert merged["references"] == []
        assert len(merged["external_refs"]) == 1
        (record,) = merged["degraded"]
        assert record["stage"] == "scip-merge"
        assert "more than one indexing unit" in record["message"]

    def test_same_file_re_definition_is_not_ambiguous(self):
        # Two units emitting the identical definition (same file) agree;
        # abstaining there would drop a join both sides support.
        merged = self.merged(
            [{"moniker": self.MONIKER, "file": "sdk/go/api.go", "line": 4,
              "end_line": 4, "kind": "method"},
             {"moniker": self.MONIKER, "file": "sdk/go/api.go", "line": 4,
              "end_line": 4, "kind": "method"}],
            [{"file": "main.go", "line": 6, "col": 5, "name": "Hello",
              "package": "gomod:dagger.io/dagger", "moniker": self.MONIKER}],
        )
        scipsource.join_cross_unit(merged)
        assert len(merged["references"]) == 1 and merged["degraded"] == []


class TestGoReplaceTargets:
    def write_mod(self, tmp_path, root, body):
        p = tmp_path / root / "go.mod" if root else tmp_path / "go.mod"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)

    def test_single_line_and_block_path_replaces(self, tmp_path):
        self.write_mod(tmp_path, "", (
            "module example.com/root\n\n"
            "replace example.com/one => ./sdk/go\n"
            "replace (\n"
            "\texample.com/two v1.2.3 => ./engine/consts\n"
            "\texample.com/three => example.com/other v0.9.0\n"
            ")\n"
        ))
        assert scipsource.go_replace_targets(tmp_path, "") == [
            "engine/consts", "sdk/go",
        ]

    def test_relative_replace_from_a_submodule_resolves(self, tmp_path):
        self.write_mod(tmp_path, "e2e", (
            "module example.com/e2e\n"
            "replace example.com/root => ../\n"
        ))
        assert scipsource.go_replace_targets(tmp_path, "e2e") == [""]

    def test_a_replace_escaping_the_repo_is_not_ours_to_stage(self, tmp_path):
        self.write_mod(tmp_path, "", (
            "module example.com/root\n"
            "replace example.com/x => ../elsewhere\n"
        ))
        assert scipsource.go_replace_targets(tmp_path, "") == []

    def test_a_module_replacement_is_not_a_path(self, tmp_path):
        self.write_mod(tmp_path, "", (
            "module example.com/root\n"
            "replace example.com/x => example.com/y v1.0.0\n"
        ))
        assert scipsource.go_replace_targets(tmp_path, "") == []

    def test_no_manifest_is_no_targets(self, tmp_path):
        assert scipsource.go_replace_targets(tmp_path, "") == []


class TestZoneDependencyLinks:
    """ADR-050: resolution walks up from the *file*, so every
    node_modules on a zone file's path gets a link — not just the zone
    root's. This repo's tsconfig-less tsextract/ and scip/ in the root
    zone are the case the first version missed."""

    def test_each_files_walk_up_tree_is_linked(self, tmp_path):
        (tmp_path / "tsextract" / "node_modules").mkdir(parents=True)
        (tmp_path / "scip" / "node_modules").mkdir(parents=True)
        links = scipsource.zone_dependency_links(
            tmp_path, ["tsextract/extract.mjs", "scip/index.mjs", "lib/x.mjs"]
        )
        assert links == {
            "tsextract/node_modules": str(
                (tmp_path / "tsextract" / "node_modules").resolve()
            ),
            "scip/node_modules": str((tmp_path / "scip" / "node_modules").resolve()),
        }

    def test_a_root_tree_serves_every_file(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        links = scipsource.zone_dependency_links(tmp_path, ["web/src/App.tsx"])
        assert links == {"node_modules": str((tmp_path / "node_modules").resolve())}

    def test_no_trees_is_no_links(self, tmp_path):
        assert scipsource.zone_dependency_links(tmp_path, ["a/b.ts"]) == {}


class TestDetectInstaller:
    def test_package_lock_is_npm(self, tmp_path):
        (tmp_path / "package-lock.json").write_text("{}")
        assert scipsource.detect_installer(tmp_path) == ("npm", "package-lock.json")

    def test_v1_yarn_lock_is_yarn1(self, tmp_path):
        (tmp_path / "yarn.lock").write_text("# yarn lockfile v1\n")
        assert scipsource.detect_installer(tmp_path) == ("yarn1", "yarn.lock")

    def test_berry_is_declined_by_name(self, tmp_path):
        (tmp_path / "yarn.lock").write_text('__metadata:\n  version: 8\n')
        installer, why = scipsource.detect_installer(tmp_path)
        assert installer is None and "Berry" in why

    def test_pnpm_is_declined_by_name(self, tmp_path):
        (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n")
        installer, why = scipsource.detect_installer(tmp_path)
        assert installer is None and "pnpm" in why

    def test_no_lockfile_names_the_drift(self, tmp_path):
        installer, why = scipsource.detect_installer(tmp_path)
        assert installer is None and "drift" in why

    def test_npm_lock_outranks_yarn_lock(self, tmp_path):
        (tmp_path / "package-lock.json").write_text("{}")
        (tmp_path / "yarn.lock").write_text("# yarn lockfile v1\n")
        assert scipsource.detect_installer(tmp_path)[0] == "npm"


class TestProvisionNodeModules:
    """The install is a fetch step through the containment planner
    (ADR-092): the cache lives under ``staging.cache_root()`` so the one
    rw mount covers it, and ``containment.run`` is the only spawn."""

    def repo(self, tmp_path, monkeypatch):
        (tmp_path / "package.json").write_text('{"name": "x"}')
        (tmp_path / "package-lock.json").write_text("{}")
        monkeypatch.setenv("HOBBES_CACHE_DIR", str(tmp_path / "cache"))
        return tmp_path

    def _never_runs(self, monkeypatch):
        monkeypatch.setattr(
            containment, "run",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("installed")),
        )

    def test_a_complete_cache_is_reused_without_installing(
        self, tmp_path, monkeypatch
    ):
        import hashlib
        repo = self.repo(tmp_path, monkeypatch)
        digest = hashlib.sha256(
            (repo / "package.json").read_bytes()
            + (repo / "package-lock.json").read_bytes()
        ).hexdigest()[:16]
        cache = tmp_path / "cache" / "npm" / digest
        (cache / "node_modules").mkdir(parents=True)
        (cache / ".complete").write_text("")
        self._never_runs(monkeypatch)
        tree, why = scipsource.provision_node_modules(repo, "")
        assert why is None and tree == cache / "node_modules"

    def test_an_install_failure_returns_the_reason(self, tmp_path, monkeypatch):
        repo = self.repo(tmp_path, monkeypatch)
        seen = {}

        def run(plan, *, timeout):
            seen["plan"] = plan
            proc = subprocess.CompletedProcess(
                plan.command, 1, stdout="", stderr="npm error ERESOLVE\n"
            )
            return containment.Outcome(proc, True)

        monkeypatch.setattr(containment, "run", run)
        tree, why = scipsource.provision_node_modules(repo, "")
        assert tree is None and "ERESOLVE" in why
        # An incomplete cache must not be reused as complete.
        assert not list((tmp_path / "cache").rglob(".complete"))
        # It was the npm fetch step, with scripts off, and no other.
        plan = seen["plan"]
        assert plan.profile.step == "fetch-npm"
        assert "--ignore-scripts" in plan.command

    def test_no_lockfile_is_not_an_install(self, tmp_path, monkeypatch):
        (tmp_path / "package.json").write_text("{}")
        self._never_runs(monkeypatch)
        tree, why = scipsource.provision_node_modules(tmp_path, "")
        assert tree is None and "drift" in why


class TestLaneBCanBeTurnedOff:
    def test_disabled_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "0")
        assert scipsource.extract_scip(tmp_path, ["a.py"], ["."], "x", "sha") is None

    def test_no_files_returns_none(self, tmp_path):
        assert scipsource.extract_scip(tmp_path, [], ["."], "x", "sha") is None


class TestDeclaredDependencies:
    """Decision 4's degradation check needs something to compare against.

    Without these, an index that resolved nothing looks exactly like one
    with nothing to resolve — the conflation that let private-repo-A report 72.7%
    coverage with no warning at all.
    """

    def _write(self, tmp_path, body):
        (tmp_path / "pyproject.toml").write_text(body)
        return tmp_path

    def test_reads_project_dependencies(self, tmp_path):
        repo = self._write(tmp_path, '[project]\ndependencies = ["pyyaml>=6", "httpx"]\n')
        assert scipsource.declared_dependencies(repo) == ["httpx", "pyyaml"]

    def test_includes_optional_groups(self, tmp_path):
        repo = self._write(
            tmp_path,
            '[project]\ndependencies = ["a"]\n'
            '[project.optional-dependencies]\ndev = ["pytest>=8"]\n',
        )
        assert scipsource.declared_dependencies(repo) == ["a", "pytest"]

    def test_strips_extras_and_version_specifiers(self, tmp_path):
        repo = self._write(
            tmp_path, '[project]\ndependencies = ["uvicorn[standard]==0.30.0"]\n'
        )
        assert scipsource.declared_dependencies(repo) == ["uvicorn"]

    def test_no_pyproject_is_not_an_error(self, tmp_path):
        assert scipsource.declared_dependencies(tmp_path) == []

    def test_malformed_pyproject_is_not_an_error(self, tmp_path):
        repo = self._write(tmp_path, "this is not toml {{{")
        assert scipsource.declared_dependencies(repo) == []

    def test_subdirectory_manifests_are_walked(self, tmp_path):
        # C-16 (lifted): a src-layout repo whose manifest lives below the
        # root — this repo's own shape, deps in pipeline/pyproject.toml —
        # must not run the degradation check against an empty list.
        sub = tmp_path / "pipeline"
        sub.mkdir()
        (sub / "pyproject.toml").write_text(
            '[project]\ndependencies = ["tree-sitter<0.26"]\n'
        )
        assert scipsource.declared_dependencies(tmp_path) == ["tree-sitter"]

    def test_manifests_union_across_packages(self, tmp_path):
        self._write(tmp_path, '[project]\ndependencies = ["httpx"]\n')
        sub = tmp_path / "worker"
        sub.mkdir()
        (sub / "pyproject.toml").write_text('[project]\ndependencies = ["httpx", "redis"]\n')
        assert scipsource.declared_dependencies(tmp_path) == ["httpx", "redis"]

    def test_setup_cfg_install_requires_and_extras_are_read(self, tmp_path):
        """C-79 (lifted): setuptools' declarative form — multi-line,
        commented — read statically."""
        (tmp_path / "setup.cfg").write_text(
            "[metadata]\nname = x\n\n"
            "[options]\ninstall_requires =\n    numpy>=1.20  # arrays\n    torch\n\n"
            "[options.extras_require]\ndev =\n    pytest\n    ruff==0.5\n"
        )
        assert scipsource.declared_dependencies(tmp_path) == [
            "numpy", "pytest", "ruff", "torch"
        ]

    def test_requirements_files_are_read_and_nothing_is_followed(self, tmp_path):
        """C-79 (lifted): peft's shape — `setup.py` plus `requirements*.txt`.
        Options, comments, URLs and paths are skipped; an included file is
        walked on its own only if it matches the name pattern."""
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()\n")
        (tmp_path / "requirements.txt").write_text(
            "# runtime\n-r requirements-dev.txt\n-e .\n"
            "accelerate>=0.21 ; python_version < '3.13'\n"
            "safetensors @ https://example.com/s.whl\n"
            "git+https://github.com/x/y.git#egg=y\n"
            "./vendor/local\n"
            "--index-url https://pypi.org/simple\n"
        )
        (tmp_path / "requirements-dev.txt").write_text("pytest\n")
        (tmp_path / "notes.txt").write_text("pandas\n")
        assert scipsource.declared_dependencies(tmp_path) == [
            "accelerate", "pytest", "safetensors"
        ]

    def test_setup_py_alone_declares_nothing_and_is_not_executed(self, tmp_path):
        (tmp_path / "setup.py").write_text(
            "import sys\nsys.exit(99)\nsetup(install_requires=['numpy'])\n"
        )
        assert scipsource.declared_dependencies(tmp_path) == []

    def test_poetry_tables_are_read_by_key_whatever_the_value(self, tmp_path):
        """C-79's residual, closed 2026-09-05: a Poetry repo has no
        `[project]` table; its dependencies are name-keyed tables whose
        values take every shape Poetry allows. The key is the package;
        `python` is the interpreter."""
        repo = self._write(
            tmp_path,
            '[tool.poetry]\nname = "x"\n'
            '[tool.poetry.dependencies]\npython = "^3.9"\nrequests = "^2.31"\n'
            'uvicorn = { version = "0.30", extras = ["standard"], optional = true }\n'
            'mylib = { path = "../mylib", develop = true }\n'
            'numpy = [{ version = "<2", python = "<3.12" }, { version = ">=2", python = ">=3.12" }]\n'
            '[tool.poetry.dev-dependencies]\nblack = "*"\n'
            '[tool.poetry.group.test.dependencies]\npytest = "^8"\n'
            '[tool.poetry.group.docs]\noptional = true\n'
            '[tool.poetry.group.docs.dependencies]\nsphinx = "^7"\n',
        )
        assert scipsource.declared_dependencies(repo) == [
            "black", "mylib", "numpy", "pytest", "requests", "sphinx", "uvicorn"
        ]

    def test_dependency_groups_pdm_and_uv_dev_dependencies_are_read(self, tmp_path):
        """PEP 735 `[dependency-groups]` (an include-group entry names no
        package), PDM's and uv's dev tables — the spec-list shapes."""
        repo = self._write(
            tmp_path,
            '[project]\nname = "x"\n'
            '[dependency-groups]\ntest = ["pytest>=8", "coverage[toml]"]\n'
            'all = [{ include-group = "test" }, "tox"]\n'
            '[tool.pdm.dev-dependencies]\nlint = ["ruff==0.5"]\n'
            '[tool.uv]\ndev-dependencies = ["mypy"]\n',
        )
        assert scipsource.declared_dependencies(repo) == [
            "coverage", "mypy", "pytest", "ruff", "tox"
        ]

    def test_lock_files_are_not_read(self, tmp_path):
        """A lock file is the resolver's closure, not the declaration:
        counting it would put every transitive package in the denominator
        of a number that means 'declared and resolved by the index'."""
        self._write(tmp_path, '[project]\nname = "x"\n')
        (tmp_path / "uv.lock").write_text('[[package]]\nname = "idna"\nversion = "3.7"\n')
        (tmp_path / "poetry.lock").write_text('[[package]]\nname = "certifi"\n')
        (tmp_path / "pdm.lock").write_text('[[package]]\nname = "six"\n')
        assert scipsource.declared_dependencies(tmp_path) == []

    def test_a_tool_table_of_the_wrong_shape_is_not_an_error(self, tmp_path):
        repo = self._write(
            tmp_path,
            '[tool.poetry]\ndependencies = "not a table"\n'
            '[tool.pdm]\ndev-dependencies = ["not", "a", "table"]\n'
            '[tool.uv]\ndev-dependencies = "not a list"\n'
            'dependency-groups = 3\n',
        )
        assert scipsource.declared_dependencies(repo) == []

    def test_find_venv_at_the_repo_root(self, tmp_path):
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "pyvenv.cfg").write_text("home = /usr\n")
        assert scipsource.find_venv(tmp_path) == (str(tmp_path.resolve()), ".venv")

    def test_find_venv_beside_a_subdirectory_manifest(self, tmp_path):
        # C-27's discovery: this repo's own shape, venv at pipeline/.venv.
        sub = tmp_path / "pipeline"
        sub.mkdir()
        (sub / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (sub / ".venv").mkdir()
        (sub / ".venv" / "pyvenv.cfg").write_text("home = /usr\n")
        assert scipsource.find_venv(tmp_path) == (str(sub.resolve()), ".venv")

    def test_find_venv_requires_the_pyvenv_marker(self, tmp_path):
        # A directory merely named .venv is not an environment, and handing
        # it to the indexer would trade one silent zero for another.
        (tmp_path / ".venv").mkdir()
        assert scipsource.find_venv(tmp_path) is None

    def test_find_venv_prefers_the_root_and_dot_venv(self, tmp_path):
        for name in (".venv", "venv"):
            (tmp_path / name).mkdir()
            (tmp_path / name / "pyvenv.cfg").write_text("home = /usr\n")
        assert scipsource.find_venv(tmp_path) == (str(tmp_path.resolve()), ".venv")

    @pytest.mark.lane_b
    def test_venv_environment_lists_the_venvs_own_distributions(self, tmp_path):
        # Since ADR-092 the listing runs in the ingest container (the
        # venv's python is repo-provided code); needs podman + the image.
        from hobbes.extract import containment as _c
        why = _c.unavailable_reason()
        if why is not None:
            pytest.skip(f"containment unavailable here: {why}")
        # C-27: the listing must come from the venv's interpreter, because
        # scip-python's fallback (first pip3 on PATH) describes whatever
        # environment the shell happens to have. A fake venv whose python
        # is this suite's interpreter answers with this suite's packages.
        import sys

        venv = tmp_path / ".venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = /usr\n")
        (venv / "bin" / "python").symlink_to(sys.executable)

        listing = scipsource.venv_environment(str(tmp_path), ".venv")
        assert listing is not None
        by_name = {d["name"] for d in listing}
        assert "pytest" in by_name
        sample = next(d for d in listing if d["name"] == "pytest")
        assert sample["version"] and isinstance(sample["files"], list)

    def test_venv_environment_degrades_to_none_without_an_interpreter(self, tmp_path):
        # No python in the venv: attribution is skipped, never guessed —
        # the index still runs and dependency_coverage reports the gap.
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "pyvenv.cfg").write_text("home = /usr\n")
        assert scipsource.venv_environment(str(tmp_path), ".venv") is None

    def test_walk_prunes_hidden_and_vendored_directories(self, tmp_path):
        # node_modules can be 222 MB on a real app; a dependency's own
        # manifest is not this repo's declaration either way.
        hidden = tmp_path / ".venv"
        vendored = tmp_path / "node_modules" / "pkg"
        for d in (hidden, vendored):
            d.mkdir(parents=True)
            (d / "pyproject.toml").write_text('[project]\ndependencies = ["wrong"]\n')
        assert scipsource.declared_dependencies(tmp_path) == []


class TestProjectionKeepsRecursionAndRefusesCallsToTypes:
    """O4 (oracle lane, 2026-08-25): a function's call to itself is an
    edge — C-59 lifted — and a Go `calls` fact whose target is a type is
    a conversion, projected as `uses` (40 of 40 dagger contradictions)."""

    NODES = [{"id": "pkg/a", "kind": "module", "path": "pkg/a.go"}]
    SYMBOLS = [
        {"id": "pkg/a.Walk", "module": "pkg/a", "kind": "function", "line": 3, "end_line": 8, "name": "Walk", "qualname": "Walk"},
        {"id": "pkg/a.JSON", "module": "pkg/a", "kind": "type", "line": 10, "end_line": 10, "name": "JSON", "qualname": "JSON"},
        {"id": "pkg/a.Node", "module": "pkg/a", "kind": "type", "line": 12, "end_line": 14, "name": "Node", "qualname": "Node"},
    ]

    def _fact(self, kind, line, def_line, scope="pkg/a.Walk", file="pkg/a.go"):
        from hobbes.extract.evidence import Resolved

        return Resolved(kind=kind, source_file=file, line=line, scope=scope, def_file=file, def_line=def_line, tier="semantic", lanes=("scip",))

    def test_a_self_call_is_an_edge(self):
        from hobbes.extract.scipsource import project

        out = project([self._fact("calls", 6, 3)], self.NODES, self.SYMBOLS)
        assert [(e["from"], e["to"], e["type"]) for e in out["symbol_edges"]] == [("pkg/a.Walk", "pkg/a.Walk", "calls")]

    def test_a_type_naming_itself_is_still_not_an_edge(self):
        from hobbes.extract.scipsource import project

        out = project([self._fact("uses", 13, 12, scope="pkg/a.Node")], self.NODES, self.SYMBOLS)
        assert out["symbol_edges"] == []

    def test_a_go_call_whose_target_is_a_type_is_a_conversion(self):
        from hobbes.extract.scipsource import project

        out = project([self._fact("calls", 5, 10)], self.NODES, self.SYMBOLS)
        assert [(e["to"], e["type"]) for e in out["symbol_edges"]] == [("pkg/a.JSON", "uses")]

    def test_a_rust_call_whose_target_is_a_type_is_a_constructor(self):
        # memchr (O7, 2026-08-27): `FinderRev(Hash::new(..))` — rustc
        # lowers the tuple-struct constructor to an aggregate; the only
        # call on the line is inside the argument. 7 of 7 contradictions.
        from hobbes.extract.scipsource import project

        nodes = [{"id": "src/lib", "kind": "module", "path": "src/lib.rs"}]
        symbols = [
            {"id": "src/lib.build", "module": "src/lib", "kind": "function", "line": 1, "end_line": 3, "name": "build", "qualname": "build"},
            {"id": "src/lib.FinderRev", "module": "src/lib", "kind": "type", "line": 5, "end_line": 5, "name": "FinderRev", "qualname": "FinderRev"},
        ]
        out = project([self._fact("calls", 2, 5, scope="src/lib.build", file="src/lib.rs")], nodes, symbols)
        assert [(e["to"], e["type"]) for e in out["symbol_edges"]] == [("src/lib.FinderRev", "uses")]

    def test_the_guard_is_go_and_rust_only(self):
        from hobbes.extract.scipsource import project

        nodes = [{"id": "m", "kind": "module", "path": "m.py"}]
        symbols = [
            {"id": "m.f", "module": "m", "kind": "function", "line": 1, "end_line": 3, "name": "f", "qualname": "f"},
            {"id": "m.T", "module": "m", "kind": "type", "line": 5, "end_line": 5, "name": "T", "qualname": "T"},
        ]
        out = project([self._fact("calls", 2, 5, scope="m.f", file="m.py")], nodes, symbols)
        assert out["symbol_edges"][0]["type"] == "calls"


class TestBelowFloor:
    def test_a_semantic_call_with_no_symbol_at_the_target_is_reported(self):
        # C-58's surfacing: the lane resolved the site (to a closure, an
        # interface method — a line lane A keeps no symbol for); the site
        # counts as resolved, draws no edge, and is named per file.
        out = scipsource.project(
            [resolved("calls", "src/app/api.py", 7, "src/app/core.py", 9999)],
            NODES, SYMBOLS,
        )
        assert out["symbol_edges"] == []
        assert out["below_floor"] == [("src/app/api.py", 7)]

    def test_a_syntactic_guess_at_a_missing_target_is_not_below_floor(self):
        from hobbes.extract.evidence import TREE_SITTER
        from hobbes.extract.schema import SYNTACTIC

        out = scipsource.project(
            [resolved("calls", "src/app/api.py", 7, "src/app/core.py", 9999,
                      tier=SYNTACTIC, lanes=(TREE_SITTER,))],
            NODES, SYMBOLS,
        )
        assert out["below_floor"] == []


class TestJavaUnits:
    """Java's indexing unit is the build root (ADR-096, decision 7)."""

    def _repo(self, tmp_path):
        for rel, text in {
            "proj/pom.xml": "<project xmlns='http://maven.apache.org/POM/4.0.0'><groupId>com.acme</groupId><artifactId>root</artifactId><modules><module>core</module></modules></project>",
            "proj/core/pom.xml": "<project xmlns='http://maven.apache.org/POM/4.0.0'><parent><groupId>com.acme</groupId></parent><artifactId>core</artifactId><dependencies><dependency><groupId>org.junit.jupiter</groupId><artifactId>junit-jupiter</artifactId></dependency><dependency><groupId>${project.groupId}</groupId><artifactId>x</artifactId></dependency><dependency><groupId>${other}</groupId><artifactId>y</artifactId></dependency><dependency><groupId>com.h2database</groupId><artifactId>h2</artifactId><scope>runtime</scope></dependency><dependency><groupId>org.bom</groupId><artifactId>b</artifactId><type>pom</type></dependency></dependencies></project>",
            "proj/core/src/main/java/a/A.java": "package a; class A {}",
            "proj/core/src/checkstyle/rules.xml": "<x/>",
            "proj/core/target/classes/A.class": "",
            "tool/settings.gradle": "rootProject.name = 'tool'",
            "tool/build.gradle": "dependencies {\n implementation 'com.google.guava:guava:33.0.0'\n runtimeOnly 'org.postgresql:postgresql:42.7.0'\n}",
            "tool/gradle/libs.versions.toml": "[libraries]\nokio = { module = 'com.squareup.okio:okio', version = '3.0' }\n",
            "tool/sub/build.gradle.kts": "",
            "tool/sub/src/main/java/b/B.java": "package b; class B {}",
            "tool/gradlew": "#!/bin/sh\n",
            "loose/C.java": "class C {}",
        }.items():
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return tmp_path

    def test_files_group_by_reactor_root_or_settings_root(self, tmp_path):
        repo = self._repo(tmp_path)
        units = scipsource.java_units(repo, [
            "proj/core/src/main/java/a/A.java", "tool/sub/src/main/java/b/B.java", "loose/C.java",
        ])
        assert units == {
            "proj": ("maven", ["proj/core/src/main/java/a/A.java"]),
            "tool": ("gradle", ["tool/sub/src/main/java/b/B.java"]),
        }
        orphans = scipsource.go_orphans(["loose/C.java"], {r: f for r, (_, f) in units.items()})
        assert orphans == {"loose": ["loose/C.java"]}

    def test_a_directory_with_both_build_files_is_maven(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project/>")
        (tmp_path / "build.gradle").write_text("")
        (tmp_path / "A.java").write_text("class A {}")
        assert scipsource.java_units(tmp_path, ["A.java"]) == {"": ("maven", ["A.java"])}

    def test_the_stage_carries_every_unpruned_non_source_file(self, tmp_path):
        repo = self._repo(tmp_path)
        staged = scipsource.java_build_files(repo, "proj")
        assert "proj/core/src/checkstyle/rules.xml" in staged  # petclinic's lesson
        assert "proj/core/pom.xml" in staged and "proj/pom.xml" in staged
        assert not any(p.startswith("proj/core/target/") for p in staged)
        assert not any(p.endswith(".java") for p in staged)
        assert not any(p.startswith("tool/") for p in staged)  # another unit
        tool = scipsource.java_build_files(repo, "tool")
        assert "tool/gradlew" in tool and "tool/gradle/libs.versions.toml" in tool

    def test_declared_dependencies_are_groups_read_not_resolved(self, tmp_path):
        repo = self._repo(tmp_path)
        groups = scipsource.declared_java_dependencies(
            repo, scipsource.java_build_files(repo, "proj") + scipsource.java_build_files(repo, "tool")
        )
        # The pom's junit group; `${project.groupId}` is the repo's own,
        # `${other}` is unreadable, the runtime driver and the BOM are
        # never referenced from source — all left out. Gradle: the
        # catalog's module group and the script's literal, as text, the
        # `runtimeOnly` line skipped by the same rule.
        assert groups == ["maven/com.google.guava", "maven/com.squareup.okio", "maven/org.junit.jupiter"]

    def test_the_jdk_the_build_runs_on_is_derived_from_what_it_spells(self, tmp_path):
        cases = {
            "build.gradle": ("sourceCompatibility = targetCompatibility = JavaVersion.VERSION_25\n", "/usr/local/java-25"),
            "sub/build.gradle.kts": ("java { toolchain { languageVersion.set(JavaLanguageVersion.of(17)) } }\n", "/usr/local/java-21"),
            "pom.xml": ("<project><properties><maven.compiler.release>25</maven.compiler.release></properties></project>", "/usr/local/java-25"),
            "old/pom.xml": ("<project><properties><java.version>8</java.version></properties></project>", "/usr/local/java-21"),
        }
        for rel, (text, want) in cases.items():
            (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / rel).write_text(text)
            assert scipsource.java_home_for(tmp_path, [rel]) == want, rel
        assert scipsource.java_home_for(tmp_path, []) == "/usr/local/java-21"

    def test_the_derived_gradle_properties_name_the_image_jdks(self):
        text = scipsource.gradle_user_properties()
        assert "/usr/local/java-17,/usr/local/java-21,/usr/local/java-25" in text
        assert "auto-download=false" in text and "daemon=false" in text


class TestLaneAgreementCountsOnlySemanticModuleEdges:
    """C-75: the join raises module edges from lane A's fallback too; the
    self-test must not read those as lane B's (date-fns: 200 "lane B
    only" edges, every one tree-sitter's, one real semantic edge)."""

    @staticmethod
    def _edge(src, dst, lane):
        from hobbes.extract.schema import tiered_edge

        return tiered_edge(src, dst, "imports", [{"path": "a.py", "line": 1}], lane=lane)

    def test_fallback_edges_leave_lane_b_empty(self):
        from hobbes.extract import _lane_agreement
        from hobbes.extract.schema import LANE_TREE_SITTER

        lane_a = [self._edge("pkg.a", "pkg.b", LANE_TREE_SITTER)]
        projected = [
            self._edge("pkg.a", "pkg.b", LANE_TREE_SITTER),
            self._edge("pkg.a", "pkg.c", LANE_TREE_SITTER),
        ]
        report = _lane_agreement([], [], {}, lane_a, projected)
        assert report["module_edges_lane_b_produced"] == 0
        assert report["module_edges_compared"] == 0
        assert report["module_edges_lane_a_only"] == []
        assert report["module_edges_lane_b_only"] == []

    def test_a_semantic_edge_counts_and_compares(self):
        from hobbes.extract import _lane_agreement
        from hobbes.extract.schema import LANE_SCIP, LANE_TREE_SITTER

        lane_a = [self._edge("pkg.a", "pkg.b", LANE_TREE_SITTER)]
        projected = [
            self._edge("pkg.a", "pkg.b", LANE_TREE_SITTER),
            self._edge("pkg.a", "pkg.c", LANE_SCIP),
        ]
        report = _lane_agreement([], [], {}, lane_a, projected)
        assert report["module_edges_lane_b_produced"] == 1
        assert report["module_edges_compared"] == 2
        assert report["module_edges_lane_a_only"] == [{"from": "pkg.a", "to": "pkg.b"}]
        assert report["module_edges_lane_b_only"] == [{"from": "pkg.a", "to": "pkg.c"}]


class TestCoverageGapRecord:
    """C-79 (lifted): the environment check that had nothing to check
    against says so, instead of leaving `dependency_coverage` absent."""

    def test_python_with_no_declared_dependencies_gets_a_record(self):
        from hobbes.extract import _coverage_gap_records

        facts = {"dependency_coverage": {"declared": 0, "resolved": 0, "missing": []}}
        records = _coverage_gap_records("python", facts)
        assert len(records) == 1
        assert records[0]["stage"] == "scip-python"
        assert "C-79" in records[0]["message"]
        assert "setup.py is code" in records[0]["message"]

    def test_a_declared_list_or_another_language_gets_none(self):
        from hobbes.extract import _coverage_gap_records

        declared = {"dependency_coverage": {"declared": 3, "resolved": 3, "missing": []}}
        assert _coverage_gap_records("python", declared) == []
        assert _coverage_gap_records("typescript", {"dependency_coverage": {}}) == []
        assert _coverage_gap_records("go", {}) == []


class TestHelperExitClassification:
    """C-85 / C-74 (lifted): an indexer that died inside the container is
    recorded as the indexer's failure; only a helper that could not run
    says "install Node and run npm install"."""

    @staticmethod
    def _run_returning(monkeypatch, code, stderr):
        def run(plan, *, timeout):
            proc = subprocess.CompletedProcess(plan.command, code, stdout="", stderr=stderr)
            return containment.Outcome(proc, True)

        monkeypatch.setattr(containment, "run", run)

    def test_an_indexer_exit_names_the_indexer(self, tmp_path, monkeypatch):
        self._run_returning(monkeypatch, scipsource.INDEXER_EXIT, "scip-python exited 1: main-impl.ts:47")
        (tmp_path / "stage").mkdir()
        with pytest.raises(scipsource.ScipError) as caught:
            scipsource.run_helper({"stage": str(tmp_path / "stage"), "language": "python"})
        assert "python indexer exited inside the container" in str(caught.value)
        assert "main-impl.ts:47" in str(caught.value)
        assert "unusable" not in str(caught.value)

    def test_a_helper_failure_still_says_how_to_install_it(self, tmp_path, monkeypatch):
        self._run_returning(monkeypatch, 1, "Cannot find module")
        (tmp_path / "stage").mkdir()
        with pytest.raises(scipsource.ScipError) as caught:
            scipsource.run_helper({"stage": str(tmp_path / "stage"), "language": "python"})
        assert "unusable" in str(caught.value)


class TestNoVenvStillIndexes:
    """C-85 (lifted): with no venv the index runs against an empty
    environment listing and the record says to create one — it does not
    let scip-python run its own discovery, which dies in the image."""

    def test_an_empty_listing_is_passed_and_the_record_says_why(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOBBES_CACHE_DIR", str(tmp_path / "cache"))
        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")  # the suite runs lane B off
        repo = tmp_path / "repo"
        (repo / "pkg").mkdir(parents=True)
        (repo / "pkg" / "__init__.py").write_text("")
        (repo / "pkg" / "a.py").write_text("def f():\n    pass\n")
        seen = {}

        def run(plan, *, timeout):
            config = json.loads(Path(plan.command[plan.command.index("--config") + 1]).read_text())
            seen["environment"] = json.loads(Path(config["environment"]).read_text())
            seen["ro"] = tuple(plan.ro) if hasattr(plan, "ro") else ()
            facts = {
                "helper_version": scipsource.HELPER_VERSION, "definitions": [],
                "references": [], "external_refs": [], "packages": {}, "degraded": [],
                "dependency_coverage": {"declared": 0, "resolved": 0, "missing": []},
            }
            proc = subprocess.CompletedProcess(plan.command, 0, stdout=json.dumps(facts), stderr="")
            return containment.Outcome(proc, True)

        monkeypatch.setattr(containment, "run", run)
        facts = scipsource.extract_scip(repo, ["pkg/__init__.py", "pkg/a.py"], ["."], "repo", "0" * 40)
        assert seen["environment"] == []
        (record,) = [r for r in facts["degraded"] if "C-85" in r["message"]]
        assert record["stage"] == "scip-python"
        assert "uv venv .venv" in record["message"]


class TestWorkspaceLinkTargets:
    """C-74 (lifted): the repo packages a workspace's node_modules links to
    are mounted beside the tree, so the links resolve in the container."""

    def test_links_out_of_the_tree_are_listed_once_each(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "pkgs" / "dev").mkdir(parents=True)
        (repo / "pkgs" / "plain").mkdir()
        nm = repo / "pkgs" / "core" / "node_modules"
        (nm / "@x").mkdir(parents=True)
        (nm / "@x" / "dev").symlink_to("../../../dev", target_is_directory=True)
        (nm / "plain").symlink_to("../../plain", target_is_directory=True)
        (nm / "again").symlink_to("../../plain", target_is_directory=True)
        (nm / ".pnpm" / "lodash@4" / "node_modules" / "lodash").mkdir(parents=True)
        (nm / "lodash").symlink_to(".pnpm/lodash@4/node_modules/lodash", target_is_directory=True)
        (nm / "gone").symlink_to("../../missing", target_is_directory=True)
        (nm / "real").mkdir()
        targets = scipsource.workspace_link_targets(nm)
        assert targets == sorted({str((repo / "pkgs" / "dev").resolve()), str((repo / "pkgs" / "plain").resolve())})

    def test_a_zone_record_sits_at_its_zone(self):
        facts = {"degraded": [{"path": ".", "stage": "scip-resolve", "message": "m"},
                              {"path": "sub", "stage": "scip-decode", "message": "m"}]}
        out = scipsource._rebase(facts, "pkgs/core")
        assert [r["path"] for r in out["degraded"]] == ["pkgs/core", "pkgs/core/sub"]


class TestReferencedTsConfigs:
    """C-90 (lifted): a tsconfig reached through `extends` or project
    `references` is staged with the zone — date-fns's `pkgs/dev`
    (`extends "./config/tsconfig"`) and its solution-style root."""

    def test_extends_and_references_are_followed_transitively(self, tmp_path):
        (tmp_path / "pkgs" / "dev" / "config").mkdir(parents=True)
        (tmp_path / "pkgs" / "core").mkdir()
        (tmp_path / "pkgs" / "dev" / "tsconfig.json").write_text(
            '{\n  // comment\n  "extends": "./config/tsconfig",\n  "include": ["src"],\n}\n'
        )
        (tmp_path / "pkgs" / "dev" / "config" / "tsconfig.json").write_text(
            '{ "extends": ["../../../base.json", "@x/dev/tsconfig"], "compilerOptions": {} }'
        )
        (tmp_path / "base.json").write_text("{}")
        (tmp_path / "tsconfig.json").write_text(
            '{ "files": [], "references": [ { "path": "pkgs/core" }, { "path": "./pkgs/dev" }, { "path": "../outside" } ] }'
        )
        (tmp_path / "pkgs" / "core" / "tsconfig.json").write_text('{ "extends": "../dev/config/tsconfig.json" }')
        (tmp_path.parent / "outside").mkdir(exist_ok=True)
        (tmp_path.parent / "outside" / "tsconfig.json").write_text("{}")
        out = scipsource.referenced_ts_configs(tmp_path, ["tsconfig.json"])
        assert out == [
            "base.json",
            "pkgs/core/tsconfig.json",
            "pkgs/dev/config/tsconfig.json",
            "pkgs/dev/tsconfig.json",
        ]
        assert scipsource.referenced_ts_configs(tmp_path, ["pkgs/dev/tsconfig.json"]) == [
            "base.json", "pkgs/dev/config/tsconfig.json",
        ]

    def test_the_zone_stage_includes_them(self, tmp_path):
        (tmp_path / "pkgs" / "dev" / "config").mkdir(parents=True)
        (tmp_path / "pkgs" / "dev" / "src").mkdir()
        (tmp_path / "pkgs" / "dev" / "tsconfig.json").write_text('{ "extends": "./config/tsconfig" }')
        (tmp_path / "pkgs" / "dev" / "config" / "tsconfig.json").write_text("{}")
        (tmp_path / "pkgs" / "dev" / "src" / "a.ts").write_text("export const a = 1;\n")
        staged = scipsource._staged_ts_configs(tmp_path, ["pkgs/dev/src/a.ts"])
        assert "pkgs/dev/config/tsconfig.json" in staged and "pkgs/dev/tsconfig.json" in staged

    def test_a_solution_style_root_is_replaced_by_a_generated_config(self, tmp_path):
        """date-fns's root: `include: []` + `references` — the two files no
        package claims (`vitest.config.ts`, a codemod) must be indexed
        under a config that names them, not under the solution file."""
        (tmp_path / "tsconfig.json").write_text(
            '{\n  "include": [],\n  "references": [ { "path": "./pkgs/core/" } ]\n}\n'
        )
        assert scipsource.is_solution_tsconfig(tmp_path / "tsconfig.json")
        (tmp_path / "real.json").write_text('{ "include": ["src"], "references": [ { "path": "./x" } ] }')
        assert not scipsource.is_solution_tsconfig(tmp_path / "real.json")
        (tmp_path / "plain.json").write_text('{ "compilerOptions": {} }')
        assert not scipsource.is_solution_tsconfig(tmp_path / "plain.json")
        (tmp_path / "files.json").write_text('{ "files": ["a.ts"], "references": [] }')
        assert not scipsource.is_solution_tsconfig(tmp_path / "files.json")
