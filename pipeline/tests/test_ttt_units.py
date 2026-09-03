"""Gold-diff units and the navigation scorer (ADR-099): units from a git
range and from a DeepSWE task, the A1 context block, the NLL prompt, and
a scorer that reads what a reply names rather than how it says it."""

import json
import subprocess
from pathlib import Path

import pytest

from hobbes.ttt import score, units
from hobbes.ttt.units import (
    CONDITIONINGS, Unit, UnitError, attach_context, attach_tasks, context_block, files_in_patch, message_keys,
    nll_messages, read_tasks, read_units, unit_from_deepswe, units_from_git, write_units,
)
from tests.test_ttt_corpus import graph_fixture, testmap_fixture

PATCH = """diff --git a/src/app/core.py b/src/app/core.py
--- a/src/app/core.py
+++ b/src/app/core.py
@@ -1,3 +1,4 @@
 def handle_request(req):
+    log(req)
     return render_page(req)
diff --git a/docs/new.md b/docs/new.md
new file mode 100644
--- /dev/null
+++ b/docs/new.md
@@ -0,0 +1 @@
+hello
diff --git a/old.txt b/old.txt
deleted file mode 100644
--- a/old.txt
+++ /dev/null
@@ -1 +0,0 @@
-bye
"""


@pytest.fixture
def history(tmp_path) -> Path:
    """A repo with a base commit and two commits after it."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "src" / "a.py").write_text("def a():\n    return 1\n")
    (repo / "README").write_text("x\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "base"], check=True)
    subprocess.run([*git, "tag", "base"], check=True)
    (repo / "src" / "a.py").write_text("def a():\n    return 2\n\ndef b():\n    return a()\n")
    (repo / "README").write_text("x\ny\nz\nw\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "feat: add b\n\nb calls a; the README grows.\n\nCo-Authored-By: X <x@y>\nClaude-Session: https://z"], check=True)
    (repo / "src" / "big.py").write_text("".join(f"x{i} = {i}\n" for i in range(200)))
    (repo / "go.sum").write_text("a v1 h1:x\nb v2 h1:y\nc v3 h1:z\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "chore: a big file"], check=True)
    return repo


class TestGitUnits:
    def test_one_unit_per_commit_and_file_within_bounds(self, history):
        got = units_from_git(history, "base", name="demo", max_lines=50, min_lines=2)
        ids = [u.id.split(":", 1)[1] for u in got]
        assert ids == ["README", "src/a.py"]  # the 200-line file is over the bound; go.sum is skipped
        a = next(u for u in got if u.files == ["src/a.py"])
        assert a.repo == "demo" and a.source == "git"
        assert a.sha == subprocess.run(["git", "-C", str(history), "rev-parse", "base"], capture_output=True, text=True).stdout.strip()
        assert a.proposal == "feat: add b\n\nb calls a; the README grows.\n\nIn `src/a.py`."  # trailers stripped
        assert "+def b():" in a.gold_diff and a.diff_lines == 5

    def test_prefixes_filter_files(self, history):
        got = units_from_git(history, "base", prefixes=("src/",), max_lines=50, min_lines=2)
        assert [u.files for u in got] == [["src/a.py"]]

    def test_a_bad_range_is_an_error(self, history):
        with pytest.raises(UnitError, match="rev-parse"):
            units_from_git(history, "nope")


class TestDeepsweUnit:
    def test_reads_task_instruction_and_solution(self, tmp_path):
        task = tmp_path / "httpx-thing"
        (task / "solution").mkdir(parents=True)
        (task / "task.toml").write_text('[metadata]\ntask_id = "httpx-thing"\nrepository_url = "https://github.com/encode/httpx"\n'
                                        'base_commit_hash = "b5addb64f0161ff6bfe94c124ef76f6a1fba5254"\nlanguage = "python"\n')
        (task / "instruction.md").write_text("Add multipart parsing.\n")
        (task / "solution" / "solution.patch").write_text(PATCH)
        u = unit_from_deepswe(task)
        assert (u.id, u.repo, u.sha[:12], u.source) == ("httpx-thing", "httpx", "b5addb64f016", "deepswe")
        assert u.proposal == "Add multipart parsing." and u.files == ["src/app/core.py", "docs/new.md", "old.txt"]

    def test_a_task_without_a_solution_is_an_error(self, tmp_path):
        (tmp_path / "task.toml").write_text("[metadata]\n")
        (tmp_path / "instruction.md").write_text("x")
        with pytest.raises(UnitError):
            unit_from_deepswe(tmp_path)


class TestContext:
    def test_files_in_patch_reads_additions_and_deletions(self):
        assert files_in_patch(PATCH) == ["src/app/core.py", "docs/new.md", "old.txt"]

    def test_block_seeds_from_files_and_named_symbols(self):
        block, notes = context_block(graph_fixture(), testmap_fixture(),
                                     "Make handle_request log before it calls render_page.", ["src/app/core.py", "docs/new.md"])
        assert block.startswith("## What Hobbes can see")
        assert "files the change centers on: src/app/core.py" in block
        assert "symbols: app.core.handle_request, app.core.render_page" in block
        assert "tests that guard this behavior: tests/test_api.py, tests/test_core.py" in block
        assert "## What Hobbes cannot confirm" in block and "## How to work" not in block
        assert "C-55" in block and graph_fixture()["sha"][:12] in block
        assert notes == ["docs/new.md: not in the graph at this SHA (new file, or outside extraction)"]

    def test_prose_words_do_not_seed_symbols(self):
        graph = graph_fixture()
        graph["symbols"].append({"id": "app.core.token", "kind": "function", "module": "app.core",
                                 "name": "token", "qualname": "token", "line": 30, "end_line": 31})
        block, _ = context_block(graph, testmap_fixture(), "the token is read once", ["src/app/core.py"])
        assert "symbols:" not in block

    def test_nll_messages_differ_only_by_the_block(self):
        u = Unit(id="x", repo="demo", sha="c" * 40, source="git", proposal="Do the thing.",
                 files=["src/a.py"], gold_diff="--- a\n+++ b\n", context="## What Hobbes can see\nfiles: src/a.py")
        bare, aided = nll_messages(u, False), nll_messages(u, True)
        assert [m["role"] for m in bare] == ["system", "user", "assistant"]
        assert bare[0] == aided[0] and bare[2]["content"] == "--- a\n+++ b\n"
        assert "What Hobbes can see" in aided[1]["content"] and "What Hobbes can see" not in bare[1]["content"]
        assert aided[1]["content"].replace(u.context + "\n\n", "") == bare[1]["content"]
        assert "demo at commit cccccccccccc" in bare[0]["content"]

    def test_round_trip_and_attach(self, tmp_path):
        u = Unit(id="x", repo="demo", sha="c" * 40, source="git", proposal="Change handle_request.",
                 files=["src/app/core.py"], gold_diff="+x\n")
        attach_context([u], graph_fixture(), testmap_fixture())
        write_units([u], tmp_path / "u.jsonl")
        back = read_units(tmp_path / "u.jsonl")
        assert back[0]["context"].startswith("## What Hobbes can see") and back[0]["id"] == "x"
        assert nll_messages(back[0], True)[1]["content"] == nll_messages(u, True)[1]["content"]
        assert back[0]["messages_bare"] == nll_messages(u, False) and back[0]["messages_aided"] == nll_messages(u, True)


class TestConditioning:
    """Review item 2: what precedes the diff tokens is a named variable."""

    def unit(self, **kw) -> Unit:
        base = dict(id="abc123def456:src/a.py", repo="demo", sha="c" * 40, source="git",
                    proposal="fix: a thing\n\nbody line\n\nIn `src/a.py`.", files=["src/a.py"], gold_diff="+x\n",
                    subject="fix: a thing", context="## What Hobbes can see\nfiles: src/a.py")
        base.update(kw)
        return Unit(**base)

    def test_message_is_the_first_runs_prompt(self):
        u = self.unit()
        assert nll_messages(u, False, "message") == nll_messages(u, False)
        assert "## Task\nfix: a thing\n\nbody line\n\nIn `src/a.py`." in nll_messages(u, False)[1]["content"]

    def test_none_is_the_path_alone(self):
        user = nll_messages(self.unit(), False, "none")[1]["content"]
        assert user.startswith("## Task\nIn `src/a.py`.\n\nWrite the unified diff")
        assert "fix: a thing" not in user and "body line" not in user

    def test_subject_and_task_carry_the_path_and_need_text(self):
        u = self.unit(task="Make the thing not break.")
        assert nll_messages(u, False, "subject")[1]["content"].startswith("## Task\nfix: a thing\n\nIn `src/a.py`.")
        task = nll_messages(u, True, "task")[1]["content"]
        assert task.startswith("## Task\nMake the thing not break.\n\nIn `src/a.py`.\n\n## What Hobbes can see")
        assert "body line" not in task
        assert nll_messages(self.unit(subject=""), False, "subject") is None
        assert nll_messages(self.unit(), False, "task") is None
        with pytest.raises(ValueError):
            nll_messages(u, False, "vibes")

    def test_git_units_carry_the_subject_and_deepswe_the_task(self, history, tmp_path):
        got = units_from_git(history, "base", name="demo")
        assert all(u.subject and u.proposal.startswith(u.subject) for u in got)
        task = tmp_path / "t"; (task / "solution").mkdir(parents=True)
        (task / "task.toml").write_text('[metadata]\ntask_id = "t-1"\nrepository_url = "https://x/y/demo"\nbase_commit_hash = "d1"\n')
        (task / "instruction.md").write_text("Add a thing.\n")
        (task / "solution" / "solution.patch").write_text(PATCH)
        d = unit_from_deepswe(task)
        assert d.task == "Add a thing." and d.subject == ""
        assert nll_messages(d, False, "subject") is None
        assert nll_messages(d, False, "task")[1]["content"].startswith(
            "## Task\nAdd a thing.\n\nIn `src/app/core.py`, `docs/new.md`, `old.txt`.")

    def test_tasks_attach_by_commit_prefix(self, tmp_path):
        f = tmp_path / "tasks.jsonl"
        f.write_text(json.dumps({"_note": "x"}) + "\n" + json.dumps({"commit": "abc123", "task": "  Do it.  "}) + "\n"
                     + json.dumps({"commit": "ffffff", "task": "Other."}) + "\n")
        tasks = read_tasks(f)
        assert tasks == {"abc123": "Do it.", "ffffff": "Other."}
        u, d = self.unit(), self.unit(id="t-1", source="deepswe")
        assert attach_tasks([u, d], tasks) == 1
        assert u.task == "Do it." and d.task == ""

    def test_write_units_emits_every_conditioning_the_unit_carries(self, tmp_path):
        u = self.unit(task="Do it.")
        write_units([u, self.unit(id="n:src/a.py", subject="")], tmp_path / "u.jsonl")
        rows = read_units(tmp_path / "u.jsonl")
        assert message_keys("message") == ("messages_bare", "messages_aided")
        assert message_keys("task") == ("messages_task_bare", "messages_task_aided")
        for c in CONDITIONINGS:
            bare, aided = message_keys(c)
            assert rows[0][bare] == nll_messages(u, False, c) and rows[0][aided] == nll_messages(u, True, c)
        assert "messages_subject_bare" not in rows[1] and "messages_task_bare" not in rows[1]
        assert "messages_none_bare" in rows[1] and "messages_bare" in rows[1]


def record(family, symbol, answer):
    return {"kind": "qa", "family": family, "symbol": symbol, "split": "eval",
            "messages": [{"role": "user", "content": "?"}, {"role": "assistant", "content": answer}]}


class TestScore:
    known = score.known_names(graph_fixture())

    def test_truth_items_per_family(self):
        assert score.truth_items(record("defines", "a.f", "`a.f` is defined in `src/a.py` at lines 1–2 (function).")) == ["src/a.py"]
        assert score.truth_items(record("callers", "a.f", "Semantic-tier callers of `a.f`: `b.g`, `c.h`.")) == ["b.g", "c.h"]
        assert score.truth_items(record("callers", "a.f", "No semantic-tier caller of `a.f` is recorded at x.")) == []
        assert score.truth_items(record("impact", "a.f", "Beyond `a` itself, a change to `a.f` reaches: `b`, `c`.")) == ["b", "c"]

    def test_set_family_is_f1_over_named_ids(self):
        rec = record("callees", "app.api.serve", "Semantic-tier callees of `app.api.serve`: `app.core.handle_request`, `app.auth.token`.")
        full = score.score_reply(rec, "It calls app.core.handle_request and app.auth.token.", self.known)
        assert full["score"] == 1.0 and full["missed"] == []
        half = score.score_reply(rec, "It calls app.core.handle_request.", self.known)
        assert half["score"] == pytest.approx(2 * 1 * 0.5 / 1.5, abs=1e-3) and half["missed"] == ["app.auth.token"]
        wrong = score.score_reply(rec, "It calls app.core.render_page.", self.known)
        assert wrong["score"] == 0.0 and wrong["extra"] == ["app.core.render_page"]

    def test_empty_truth_rewards_naming_nothing(self):
        rec = record("callers", "app.api.serve", "No semantic-tier caller of `app.api.serve` is recorded at x.")
        assert score.score_reply(rec, "Nothing calls it.", self.known)["score"] == 1.0
        assert score.score_reply(rec, "No caller of `app.api.serve` is recorded.", self.known)["score"] == 1.0  # its module is not an offer
        rec3 = record("callers", "app.api.Router.dispatch", "No semantic-tier caller of `app.api.Router.dispatch` is recorded at x.")
        assert score.score_reply(rec3, "Nothing calls `app.api.Router.dispatch`.", self.known)["score"] == 1.0  # nor its class
        assert score.score_reply(rec, "app.core.handle_request calls it.", self.known)["score"] == 0.0

    def test_defines_needs_the_path(self):
        rec = record("defines", "app.api.serve", "`app.api.serve` is defined in `src/app/api.py` at lines 4–12 (function).")
        assert score.score_reply(rec, "In src/app/api.py, around line 4.", self.known)["score"] == 1.0
        assert score.score_reply(rec, "In src/app/core.py.", self.known)["score"] == 0.0

    def test_absent_rewards_refusal_and_punishes_invention(self):
        rec = record("absent", "app.api.Serve", "`app.api.Serve` is not defined in this repo at x.")
        assert score.score_reply(rec, "There is no such symbol in the repo.", self.known)["refused"]
        # Spelling the question back — its module `app.api` is a known node — is not an offer.
        assert score.score_reply(rec, "`app.api.Serve` is not defined in this repo at x.", self.known)["score"] == 1.0
        rec2 = record("absent", "app.api.Router.dispatch2", "`app.api.Router.dispatch2` is not defined in this repo at x.")
        assert score.score_reply(rec2, "`app.api.Router.dispatch2` is not defined here.", self.known)["score"] == 1.0
        assert score.score_reply(rec, "It is defined in src/app/api.py.", self.known)["score"] == 0.0
        assert score.score_reply(rec, "Not sure, but see app.api.serve.", self.known)["score"] == 0.0

    def test_summary(self):
        rows = [{"family": "defines", "score": 1.0}, {"family": "defines", "score": 0.0},
                {"family": "absent", "score": 1.0}, {"family": "absent", "score": 0.0}, {"family": "absent", "score": 0.0}]
        s = score.summarise(rows)
        assert s["n"] == 5 and s["families"]["defines"]["mean"] == 0.5
        assert s["absent_false_acceptance"] == pytest.approx(2 / 3, abs=1e-3) and s["navigation_mean"] == 0.5
