"""Tests for the review page (DEC-018): its data, stamp and file, not its drawing.

The drawing is the bundle built in ``review/`` (DEC-019), JavaScript only a
browser runs; it is checked by eye, and its pure parts by ``node --test``
there. These tests inline a stand-in bundle, so ``review/`` need not be built.
"""

from __future__ import annotations

import json
import re

import pytest

from hobbes.watterson import levels, review
from hobbes.watterson.cli import main
from tests.test_watterson_levels import APP, graph, repo  # noqa: F401 - the repo fixture


def fake_app(path):
    """A stand-in for ``review/dist``."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "review.js").write_text('/*app*/console.log("</script>")')
    (path / "review.css").write_text("/*css*/")
    return path


@pytest.fixture(autouse=True)
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "APP_DIR", fake_app(tmp_path / "app"))


def embedded(html: str) -> dict:
    match = re.search(r"const DATA = (.*?);\n", html)
    assert match, "no data in the page"
    return json.loads(match.group(1))


def test_the_page_embeds_slim_views_and_a_stamp(repo):  # noqa: F811
    doc = levels.build(graph(APP, [("app.src.app.cli", "app.src.app.util")]), repo)
    data = review.page_data(doc, repo, generated=0)
    assert data["root"] == doc["root_view"] and set(data["views"]) == set(doc["views"])
    box = data["views"]["app/src/app"]["boxes"][0]
    assert "members" not in box and box["detail"] == levels.describe(doc["views"]["app/src/app"]["boxes"][0])
    assert data["stamp"]["sha"] == "abc" and data["stamp"]["dirty"] is False and data["stamp"]["path"] == str(repo)
    html = review.render(data)
    assert embedded(html)["views"]["app/src/app"]["boxes"][0]["label"] == box["label"]
    assert "/*__HOBBES_DATA__*/" not in html and "<script" in html
    assert data["agents"] is None  # no .hobbes/roles.toml


def test_the_page_carries_the_agent_mapping(repo):  # noqa: F811
    (repo / ".hobbes" / "roles").mkdir(parents=True, exist_ok=True)
    (repo / ".hobbes" / "roles" / "impl.md").write_text("You implement.\n")
    (repo / ".hobbes" / "roles.toml").write_text(
        'test = ["true"]\n[roles.impl]\nagent = "claude"\nprompt = "roles/impl.md"\nwrites = ["src/*"]\n')
    doc = levels.build(graph(APP, []), repo)
    agents = review.page_data(doc, repo, generated=0)["agents"]
    assert agents["test"] == ["true"] and [r["name"] for r in agents["roles"]] == ["impl"]
    assert agents["roles"][0]["prompt"] == "You implement.\n"


def test_no_string_in_the_data_can_end_the_script():
    html = review.render({"stamp": {"path": "/r"}, "views": {"x": {"title": "</script><b>"}}})
    assert "</script><b>" not in html and embedded(html)["views"]["x"]["title"] == "</script><b>"


def test_the_page_inlines_the_bundle(tmp_path):
    html = review.render({"stamp": {"path": "/r"}, "views": {}})
    assert "/*app*/" in html and "/*css*/" in html and "__HOBBES_" not in html
    assert "</script>\")" not in html  # the bundle's own strings cannot end its script either


def test_a_missing_bundle_names_the_build(tmp_path):
    with pytest.raises(review.AppMissing, match=re.escape(review.BUILD)):
        review.render({"stamp": {"path": "/r"}, "views": {}}, app_dir=tmp_path / "none")


def test_file_names_carry_the_stamp(tmp_path):
    assert review.file_name(tmp_path / "proj", "0123456789", False) == "proj@0123456.html"
    assert review.file_name(tmp_path / "proj", "0123456789", True) == "proj@0123456-dirty.html"
    assert review.file_name(tmp_path / "proj", None, None) == "proj@nosha.html"


def test_write_saves_into_the_review_dir(repo, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("HOBBES_REVIEW_DIR", str(tmp_path / "out"))
    path = review.write(levels.build(graph(APP), repo), repo)
    assert path == tmp_path / "out" / "repo@abc.html" and path.read_text().startswith("<!doctype html>")


def test_the_review_command(repo, tmp_path, monkeypatch, capsys):  # noqa: F811
    monkeypatch.setenv("HOBBES_REVIEW_DIR", str(tmp_path / "out"))
    assert main(["review", "--repo", str(repo), "--no-open"]) == 1
    assert "run `hobbes ingest` first" in capsys.readouterr().err
    derived = repo / ".hobbes" / "derived"
    derived.mkdir(parents=True)
    (derived / "graph.json").write_text(json.dumps(graph(APP)))
    assert main(["review", "--repo", str(repo), "--no-open"]) == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / "out" / "repo@abc.html")


def test_the_review_command_without_the_bundle(repo, tmp_path, monkeypatch, capsys):  # noqa: F811
    monkeypatch.setenv("HOBBES_REVIEW_DIR", str(tmp_path / "out"))
    monkeypatch.setattr(review, "APP_DIR", tmp_path / "none")
    derived = repo / ".hobbes" / "derived"
    derived.mkdir(parents=True)
    (derived / "graph.json").write_text(json.dumps(graph(APP)))
    assert main(["review", "--repo", str(repo), "--no-open"]) == 1
    assert review.BUILD in capsys.readouterr().err
