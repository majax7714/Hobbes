"""Tests for hobbes.extract.interfaces — routes and CLI entry points."""

from pathlib import Path

import pytest

from hobbes.extract.discover import discover_modules
from hobbes.extract.interfaces import extract_cli_entry_points, extract_routes
from hobbes.extract.pysource import parse_source

FIXTURE = Path(__file__).parent / "fixtures" / "miniapp"


@pytest.fixture(scope="module")
def routes():
    modules = discover_modules(FIXTURE)
    parsed = {m.id: parse_source((FIXTURE / m.path).read_bytes()) for m in modules}
    return extract_routes(modules, parsed)


class TestRoutes:
    def test_fastapi_verb_decorators(self, routes):
        fastapi = {(r["method"], r["path"], r["handler"]) for r in routes if r["framework"] == "fastapi"}
        assert fastapi == {
            ("GET", "/items/{item_id}", "miniapp.api.read_item"),
            ("POST", "/items", "miniapp.api.create_item"),
            ("WEBSOCKET", "/ws", "miniapp.api.ws"),
        }

    def test_flask_route_decorators(self, routes):
        flask = {(r["method"], r["path"]) for r in routes if r["framework"] == "flask"}
        assert flask == {
            ("GET", "/health"),
            ("GET", "/admin"),
            ("POST", "/admin"),
        }

    def test_evidence_fields(self, routes):
        health = next(r for r in routes if r["path"] == "/health")
        assert health["file"] == "src/miniapp/web.py"
        assert health["line"] == 8
        assert health["handler"] == "miniapp.web.health"

    def test_non_route_decorators_ignored(self, tmp_path):
        (tmp_path / "m.py").write_text(
            "@functools.cache\n"
            "def cached():\n"
            "    pass\n"
            "\n"
            "@app.get(dynamic_path)\n"
            "def no_literal():\n"
            "    pass\n"
        )
        modules = discover_modules(tmp_path)
        parsed = {m.id: parse_source((tmp_path / m.path).read_bytes()) for m in modules}
        assert extract_routes(modules, parsed) == []


class TestCliEntryPoints:
    def test_fixture_pyproject(self):
        assert extract_cli_entry_points(FIXTURE) == [
            {"name": "mini", "target": "miniapp.cli:main", "source": "pyproject.toml"}
        ]

    def test_no_pyproject(self, tmp_path):
        assert extract_cli_entry_points(tmp_path) == []
