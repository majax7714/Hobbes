"""The probe's templates and version-aware file scoring (ADR-099 §4.4; review items 4 and 10)."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

from hobbes.ttt.probe import (CONTEXTS, REFUSE_INSTRUCTION, generic, listed_files, render_context, score_files,
                              tag_trees, template_hash)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ttt_probe.py"


def load_script():
    spec = importlib.util.spec_from_file_location("ttt_probe", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestTemplates:
    def test_hash_is_stable_and_distinct_per_context(self):
        hashes = {c: template_hash(c) for c in CONTEXTS}
        assert all(len(h) == 16 for h in hashes.values())
        assert len(set(hashes.values())) == len(CONTEXTS)
        assert template_hash("card") == hashes["card"]

    def test_unknown_context_refused(self):
        with pytest.raises(ValueError):
            template_hash("cards")

    def test_card_refuse_carries_the_instruction_verbatim_after_the_card(self):
        text = render_context("card-refuse", "m.f", "symbol: m.f\nfile: m.py", "abc123abc123")
        assert "symbol: m.f" in text
        assert text.index("symbol: m.f") < text.index(REFUSE_INSTRUCTION)
        assert REFUSE_INSTRUCTION == ("If the symbol is not listed in the derived context above, reply that it is not "
                                      "defined in this repo at this SHA. Do not guess a file.")
        assert render_context("card", "m.f", "symbol: m.f\nfile: m.py", "abc123abc123") == text.replace(REFUSE_INSTRUCTION + "\n\n", "")

    def test_no_card_note_under_both_card_contexts(self):
        for ctx in ("card", "card-refuse"):
            text = render_context(ctx, "m.Ghost", None, "abc123abc123")
            assert "no card for `m.Ghost`" in text
            assert (REFUSE_INSTRUCTION in text) == (ctx == "card-refuse")
        assert render_context("none", "m.f", "card", "abc") == ""


class TestStoplist:
    def test_generic_names(self):
        for name in ("README.md", "readme.rst", "LICENSE", "LICENSE.txt", "__init__.py", "setup.py", "pyproject.toml",
                     "Makefile", ".gitignore", "CHANGELOG.md", "CONTRIBUTING.md", "package.json", "go.mod", "Cargo.toml"):
            assert generic(name), name
        for name in ("client.py", "_client.py", "readme_parser.py", "main.go", "licenses.py"):
            assert not generic(name), name

    def test_listed_files_takes_basenames(self):
        assert listed_files("- `httpx/client.py`\n- models.py\n- README.md") == {"client.py", "models.py", "README.md"}


@pytest.fixture
def tagged_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "r"
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com"); git("config", "user.name", "t")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "client.py").write_text("x = 1\n")
    (repo / "README.md").write_text("r\n")
    git("add", "."); git("commit", "-q", "-m", "one"); git("tag", "v1")
    git("mv", "pkg/client.py", "pkg/_client.py")
    git("commit", "-q", "-m", "rename"); git("tag", "v2")
    return repo


class TestVersions:
    def test_tag_trees_reads_every_tag(self, tagged_repo: Path):
        trees = tag_trees(tagged_repo)
        assert set(trees) == {"v1", "v2"}
        assert "pkg/client.py" in trees["v1"] and "pkg/_client.py" in trees["v2"]
        assert "pkg/client.py" not in trees["v2"]
        assert tag_trees(tagged_repo, cap=1) and len(tag_trees(tagged_repo, cap=1)) == 1

    def test_no_tags_is_empty(self, tmp_path: Path):
        assert tag_trees(tmp_path) == {}

    def test_pre_rename_name_scores_zero_at_sha_and_one_any_version(self, tagged_repo: Path):
        trees = tag_trees(tagged_repo)
        real = {p.name for p in (tagged_repo / "pkg").iterdir()}
        row = score_files({"client.py"}, real, trees, "pkg")
        assert row["precision_at_sha"] == 0.0 and row["precision"] == 0.0
        assert row["precision_any_version"] == 1.0
        assert row["best_tag"] == "v1" and row["best_tag_hits"] == 1

    def test_at_sha_name_hits_both(self, tagged_repo: Path):
        trees = tag_trees(tagged_repo)
        row = score_files({"_client.py", "ghost.py"}, {"_client.py"}, trees, "pkg")
        assert row["precision_at_sha"] == 0.5 and row["precision_any_version"] == 0.5
        assert row["best_tag"] == "v2"

    def test_nothing_hits_means_no_best_tag(self, tagged_repo: Path):
        row = score_files({"ghost.py"}, {"_client.py"}, tag_trees(tagged_repo), "pkg")
        assert row["best_tag"] is None and row["precision_any_version"] == 0.0
        assert score_files(set(), {"a.py"}, {}, "pkg")["best_tag"] is None

    def test_stoplist_changes_the_number(self):
        row = score_files({"README.md", "__init__.py", "ghost.py"}, {"README.md", "__init__.py", "real.py"}, {}, "pkg")
        assert row["precision_at_sha"] == round(2 / 3, 3)
        assert row["precision_at_sha_stoplisted"] == 0.0
        assert row["listed_stoplisted"] == 1 and row["truth_stoplisted"] == 1


class TestScriptRecord:
    def test_finish_keeps_the_gate_and_adds_the_variants(self):
        mod = load_script()
        out = {"parts": {
            "files": [{"dir": "a", "precision": 0.0, "precision_at_sha": 0.0, "precision_at_sha_stoplisted": 0.0,
                       "precision_any_version": 1.0, "best_tag": "v1"},
                      {"dir": "b", "precision": 1.0, "precision_at_sha": 1.0, "precision_at_sha_stoplisted": 0.5,
                       "precision_any_version": 1.0, "best_tag": "v1"}],
            "definitions": [{"recall": 0.3}],
            "navigation": {"navigation_mean": 0.6}}}
        mod.finish(out)
        assert out["score"] == round((0.5 + 0.3 + 0.6) / 3, 3) == out["score_at_sha"]
        assert out["score_any_version"] == round((1.0 + 0.3 + 0.6) / 3, 3)
        assert out["score_stoplisted"] == round((0.25 + 0.3 + 0.6) / 3, 3)
        assert out["best_tags"] == {"v1": 2}
        assert out["cell"] == "neither"

    def test_old_rows_without_variant_fields_still_score(self):
        mod = load_script()
        out = {"parts": {"files": [{"dir": "a", "precision": 0.4}], "definitions": [], "navigation": {"navigation_mean": None}}}
        mod.finish(out)
        assert out["score"] == round(0.4 / 3, 3) and out["cell"] == "U" and out["best_tags"] == {}
