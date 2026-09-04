"""Tests for hobbes.extract.discover — module identity and collisions."""

from pathlib import Path

from hobbes.extract.discover import discover_modules

FIXTURE = Path(__file__).parent / "fixtures" / "miniapp"


class TestMiniappDiscovery:
    def test_modules_and_kinds(self):
        modules = {m.id: m for m in discover_modules(FIXTURE)}
        assert modules["miniapp"].kind == "package"
        assert modules["miniapp"].path == "src/miniapp/__init__.py"
        assert modules["miniapp.core"].kind == "module"
        assert modules["miniapp.core"].root == "src"
        assert modules["tests.test_core"].root == "."
        assert set(modules) == {
            "miniapp",
            "miniapp.api",
            "miniapp.cli",
            "miniapp.core",
            "miniapp.util",
            "miniapp.web",
            "tests",
            "tests.test_core",
        }

    def test_sorted_and_deterministic(self):
        first = discover_modules(FIXTURE)
        assert first == discover_modules(FIXTURE)
        assert [m.id for m in first] == sorted(m.id for m in first)


class TestCollisions:
    def test_same_import_name_two_roots_disambiguates(self, tmp_path):
        for project in ("alpha", "beta"):
            pkg = tmp_path / project / "tests"
            pkg.mkdir(parents=True)
            (pkg / "__init__.py").write_text("")
        modules = discover_modules(tmp_path)
        assert {m.id for m in modules} == {"alpha:tests", "beta:tests"}
        assert all(m.import_name == "tests" for m in modules)

    def test_skips_dot_dirs_and_caches(self, tmp_path):
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "__init__.py").write_text("")
        for skipped in (".venv/lib", "__pycache__", ".hobbes/derived"):
            d = tmp_path / skipped
            d.mkdir(parents=True)
            (d / "junk.py").write_text("")
        assert {m.id for m in discover_modules(tmp_path)} == {"pkg"}

    def test_script_outside_any_package(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "deploy.py").write_text("")
        modules = discover_modules(tmp_path)
        assert [(m.id, m.kind, m.root) for m in modules] == [
            ("deploy", "module", "scripts")
        ]


class TestLinkedCopies:
    """C-73 (lifted): a directory symlink inside the repo is one tree, not
    two — serde's `serde/src/core -> ../../serde_core/src` doubled 19
    modules and 1,356 call sites, the copy with no lane B evidence."""

    @staticmethod
    def _repo(tmp_path):
        pkg = tmp_path / "core" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "a.py").write_text("def f():\n    pass\n")
        (tmp_path / "shared").mkdir()
        (tmp_path / "shared" / "src").symlink_to(tmp_path / "core", target_is_directory=True)
        (tmp_path / "shared" / "here.py").write_text("x = 1\n")
        return tmp_path

    def test_the_linked_tree_is_discovered_once_at_its_target(self, tmp_path):
        from hobbes.extract.discover import discover_modules, linked_copies

        repo = self._repo(tmp_path)
        assert linked_copies(repo) == [("shared/src", "core")]
        paths = sorted(m.path for m in discover_modules(repo))
        assert paths == ["core/pkg/__init__.py", "core/pkg/a.py", "shared/here.py"]

    def test_a_link_outside_the_repo_is_the_only_copy_and_is_walked(self, tmp_path):
        from hobbes.extract.discover import discover_modules, linked_copies

        outside = tmp_path / "elsewhere"
        outside.mkdir()
        (outside / "m.py").write_text("y = 2\n")
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "vendored").symlink_to(outside, target_is_directory=True)
        assert linked_copies(repo) == []
        assert [m.path for m in discover_modules(repo)] == ["vendored/m.py"]

    def test_a_link_to_an_ancestor_does_not_loop(self, tmp_path):
        from hobbes.extract.discover import discover_modules, linked_copies

        (tmp_path / "a.py").write_text("")
        (tmp_path / "loop").symlink_to(tmp_path, target_is_directory=True)
        assert linked_copies(tmp_path) == [("loop", ".")]
        assert [m.path for m in discover_modules(tmp_path)] == ["a.py"]

    def test_every_language_walk_skips_the_copy_and_the_ingest_records_it(self, tmp_path):
        from hobbes.extract import extract_repo
        from hobbes.extract.gosource import iter_go_files
        from hobbes.extract.interfaces import iter_pyprojects
        from hobbes.extract.javasource import iter_java_files
        from hobbes.extract.rustsource import iter_cargo_manifests, iter_rust_files
        from hobbes.extract.terraform import discover_tf
        from hobbes.extract.tssource import has_ts_files

        repo = self._repo(tmp_path)
        (repo / "core" / "x.go").write_text("package core\n")
        (repo / "core" / "X.java").write_text("class X {}\n")
        (repo / "core" / "x.rs").write_text("")
        (repo / "core" / "Cargo.toml").write_text("[package]\nname = \"c\"\n")
        (repo / "core" / "pyproject.toml").write_text("[project]\nname = \"c\"\n")
        (repo / "core" / "main.tf").write_text("")
        for walk in (iter_go_files, iter_java_files, iter_rust_files, iter_cargo_manifests, iter_pyprojects):
            found = [str(p.relative_to(repo)) for p in walk(repo)]
            assert found and all(f.startswith("core/") for f in found), (walk.__name__, found)
        assert discover_tf(repo) == ["core/main.tf"]
        assert not has_ts_files(repo)
        result = extract_repo(repo)
        records = [e for e in result.graph["extraction_errors"] if e["stage"] == "discover"]
        assert [(r["path"], "C-73" in r["message"]) for r in records] == [("shared/src", True)]
        assert "shared/src" not in {n["id"] for n in result.graph["nodes"]}
