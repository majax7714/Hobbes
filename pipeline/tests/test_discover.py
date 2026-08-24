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
