"""Tests for the Docs tab's listing (DEC-021): which files, in what order,
and how they are embedded. Real files in a temp repo, with and without git."""

from __future__ import annotations

import base64
import gzip
import subprocess

import pytest

from hobbes.watterson import repodocs, review
from tests.test_watterson_review import fake_app


def write(root, path, text):
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(text)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    write(root, "README.md", "# The *repo*\n\nHello.\n")
    write(root, "docs/guide.md", "Intro without a heading.\n")
    write(root, "docs/README.md", "# Docs\n")
    write(root, "CONTRIBUTING.md", "# Contributing\n")
    write(root, "app/tests/fixtures/mini/README.md", "# fixture\n")
    write(root, "node_modules/pkg/README.md", "# dependency\n")
    write(root, "app/main.py", "")
    return root


def text(entry):
    return gzip.decompress(base64.b64decode(entry["gz"])).decode()


def test_markdown_only_without_fixtures_or_dependencies(repo):
    files = repodocs.collect(repo)["files"]
    assert [f["path"] for f in files] == ["README.md", "CONTRIBUTING.md", "docs/README.md", "docs/guide.md"]
    assert [f["title"] for f in files] == ["The repo", "Contributing", "Docs", "guide.md"]
    assert text(files[0]) == "# The *repo*\n\nHello.\n" and files[0]["bytes"] == len("# The *repo*\n\nHello.\n")


def test_git_decides_what_counts(repo):
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    write(repo, ".gitignore", "secret/\n")
    write(repo, "secret/notes.md", "# private\n")
    paths = [f["path"] for f in repodocs.collect(repo)["files"]]
    assert "secret/notes.md" not in paths and "README.md" in paths  # untracked but not ignored still counts
    assert "node_modules/pkg/README.md" not in paths


def test_big_files_are_listed_not_embedded(repo, monkeypatch):
    monkeypatch.setattr(repodocs, "MAX_DOC_BYTES", 10)
    big = next(f for f in repodocs.collect(repo)["files"] if f["path"] == "README.md")
    assert "gz" not in big and big["skipped"] and big["title"] == "README.md"


def test_a_moved_head_is_noted(repo):
    assert repodocs.collect(repo, "abc1234", "abc1234")["notes"] == []
    assert repodocs.collect(repo, "abc1234", "def5678")["notes"] == [
        repodocs.STALE_NOTE.format(head="def5678", sha="abc1234")]


def test_the_page_embeds_the_docs(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(review, "APP_DIR", fake_app(tmp_path / "app"))
    (repo / "app" / "pyproject.toml").write_text("")
    data = review.page_data({"views": {}, "root_view": "", "sha": "abc"}, repo, generated=0)
    assert [f["path"] for f in data["docs"]["files"]][0] == "README.md"
    given = {"files": [], "notes": []}
    assert review.page_data({"views": {}, "root_view": ""}, repo, generated=0, docs=given)["docs"] is given
