"""Lane B's SCIP facts, and their projection onto lane A's ids (ADR-029).

The join itself lives in `test_evidence.py` — this covers getting SCIP's
references *into* the evidence IR, and projecting the joined result back
onto module and symbol ids. Both are pure, so no indexer runs here; the
end-to-end path is the M2 exit check.
"""

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
