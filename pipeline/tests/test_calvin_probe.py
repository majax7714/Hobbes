"""The Calvin M0 probe's pure pieces (`scripts/calvin_probe.py`): hunk ranges, absent-file classes, span overlap, the `new` term test."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("calvin_probe", Path(__file__).resolve().parents[1] / "scripts" / "calvin_probe.py")
cp = importlib.util.module_from_spec(spec)
sys.modules["calvin_probe"] = cp
spec.loader.exec_module(cp)


DIFF = """diff --git a/pipeline/src/hobbes/x.py b/pipeline/src/hobbes/x.py
--- a/pipeline/src/hobbes/x.py
+++ b/pipeline/src/hobbes/x.py
@@ -1,3 +1,4 @@
+import os
@@ -10,2 +11,6 @@ def f():
+    return 1
@@ -30 +35 @@
"""


def test_hunk_ranges_are_post_image_and_never_empty():
    assert cp.hunk_ranges(DIFF) == [(1, 4), (11, 16), (35, 35)]


def test_absent_class_by_extension():
    assert cp.absent_class("a/b.py") == "code"
    assert cp.absent_class("a/b.go") == "code"
    assert cp.absent_class("README.md") == "docs"
    assert cp.absent_class("LICENSE") == "docs"
    assert cp.absent_class("go/go.mod") == "other:.mod"


def test_classify_hunks_splits_absent_inside_and_outside():
    path2mod = {"pipeline/src/hobbes/x.py": "hobbes.x"}
    spans = {"hobbes.x": [(10, 20)]}
    # 3 hunks: (1,4) outside any span, (11,16) inside, (35,35) outside
    assert cp.classify_hunks(DIFF, "pipeline/src/hobbes/x.py", path2mod, spans) == (3, 0, 1, 0)
    # a file the graph lacks: every hunk absent; a created code file counts as new
    assert cp.classify_hunks(DIFF, "pipeline/src/hobbes/y.py", path2mod, spans) == (3, 3, 0, 0)
    assert cp.classify_hunks("new file mode 100644\n" + DIFF, "pipeline/src/hobbes/y.py", path2mod, spans) == (3, 3, 0, 3)
    assert cp.classify_hunks("new file mode 100644\n" + DIFF, "docs/y.md", path2mod, spans) == (3, 3, 0, 0)


def test_unresolved_term_is_new_when_the_added_lines_carry_its_last_segment():
    added = "+def merge_ranges(a, b):\n+    pass"
    assert cp.unresolved_is_new("merge_ranges", added)
    assert cp.unresolved_is_new("hobbes.extract.merge_ranges", added)
    assert not cp.unresolved_is_new("range_join", added)


TWO_FILE_DIFF = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,2 +1,3 @@
+x = 1
diff --git a/tests/test_a.py b/tests/test_a.py
--- a/tests/test_a.py
+++ b/tests/test_a.py
@@ -7 +7,2 @@
+assert x
"""


def test_hunks_by_file_keys_post_image_ranges_by_the_new_path():
    assert cp.hunks_by_file(TWO_FILE_DIFF) == {"a.py": [(1, 3)], "tests/test_a.py": [(7, 8)]}


def _v1_template():
    return {"holes": [
        {"id": "u1", "type": "UNRESOLVED", "provenance": {}},
        {"id": "c1", "type": "ANCHOR_CONFIRM", "provenance": {"anchor": "helper"}},
        {"id": "c2", "type": "ANCHOR_CONFIRM", "provenance": {"anchor": "make"}},
        {"id": "c3", "type": "ANCHOR_CONFIRM", "provenance": {"anchor": "cont", "module": "m.cont", "symbol": "m.cont.f"}},
        {"id": "c4", "type": "ANCHOR_CONFIRM", "provenance": {"anchor": "cont", "module": "m.cont", "symbol": "m.cont.g"}},
        {"id": "c5", "type": "ANCHOR_CONFIRM", "provenance": {"anchor": "other", "module": "m.other", "symbol": "m.other.h"}},
        {"id": "f1", "type": "FREEFORM", "provenance": {}},
    ]}


def _v0_record():
    return {"template_round1": {"holes": [
        {"id": "u1", "type": "UNRESOLVED"},
        {"id": "c1", "type": "ANCHOR_CONFIRM", "provenance": {"anchor": "helper"}},
        {"id": "c2", "type": "ANCHOR_CONFIRM", "provenance": {"anchor": "make"}},
        {"id": "c3", "type": "ANCHOR_CONFIRM", "provenance": {"anchor": "cont"}},
        {"id": "c4", "type": "ANCHOR_CONFIRM", "provenance": {"anchor": "other"}},
    ]}, "rounds": [{"round": 1, "fills": {"fills": {
        "u1": {"classes": {"zz": "not-code"}},
        "c1": {"confirm": True}, "c2": {"confirm": False}, "c3": {"confirm": True}, "c4": {"confirm": False},
    }}}]}


def test_replay_fills_gold_mode_confirms_only_the_symbols_the_gold_edits_and_keeps_the_word_answers():
    fills, yes = cp.replay_fills(_v1_template(), _v0_record(), "gold", lambda sid: sid == "m.cont.g")
    assert fills["u1"] == {"classes": {"zz": "not-code"}}
    assert fills["c1"] == {"confirm": True} and fills["c2"] == {"confirm": False}  # the recorded word answers
    assert fills["c3"] == {"confirm": False} and fills["c4"] == {"confirm": True}  # the gold edits g, not f
    assert fills["c5"] == {"confirm": False}  # the gold does not edit h, whatever the run said of its module
    assert yes == 2
    assert "f1" not in fills


def test_replay_fills_max_mode_confirms_every_symbol_of_a_module_the_run_confirmed():
    fills, yes = cp.replay_fills(_v1_template(), _v0_record(), "max", lambda sid: False)
    assert fills["c3"] == {"confirm": True} and fills["c4"] == {"confirm": True}  # `cont` was confirmed in v0
    assert fills["c5"] == {"confirm": False}  # `other` was refused
    assert yes == 3


def test_split_diff_keys_each_file_by_its_b_path():
    d = ("diff --git a/x.go b/x.go\n--- a/x.go\n+++ b/x.go\n@@ -1 +1 @@\n-a\n+b\n"
         "diff --git a/n.go b/n.go\nnew file mode 100644\n--- /dev/null\n+++ b/n.go\n@@ -0,0 +1 @@\n+c\n")
    parts = cp.split_diff(d)
    assert [p for p, _ in parts] == ["x.go", "n.go"] and "".join(x for _, x in parts) == d


def test_perturb_site_renames_one_site_by_byte_column_and_near_name_avoids_taken():
    text = "package p\n\nfunc f() {\n\tRun(Run())\n}\n"
    assert cp.perturb_site(text, 4, 5, "Run", "RunZq") == "package p\n\nfunc f() {\n\tRun(RunZq())\n}\n", "the second site only"
    with pytest.raises(ValueError):
        cp.perturb_site(text, 4, 2, "Run", "X")
    assert cp.near_name("Run", {"RunZq"}) == "RunQz"


def test_rta_sites_collects_in_repo_implementers_per_interface_method(tmp_path):
    key = {"oracle": "go-rta", "sites": [
        {"mode": "dynamic", "interface": {"name": "m/p.Source.Fragments"}, "targets": [{"name": "(*m/p.Git).Fragments"}, {"name": "(*ext.X).Fragments", "external": True}]},
        {"mode": "dynamic", "interface": {"name": "m/p.Source.Fragments"}, "targets": [{"name": "(*m/p.File).Fragments"}]},
        {"mode": "dynamic", "interface": {"name": "io.Writer.Write", "external": True}, "targets": [{"name": "(*m/p.W).Write"}]},
        {"mode": "static", "targets": [{"name": "m/p.f"}]}]}
    (tmp_path / "k.json").write_text(json.dumps(key))
    assert cp.rta_sites(tmp_path / "k.json", "label") == {"source": "label", "sites": {"m/p.Source.Fragments": ["(*m/p.File).Fragments", "(*m/p.Git).Fragments"]}}
    assert cp.rta_sites(None) is None


class _Ep:
    """An endpoint that returns fixed usage: 200k tokens in, 10k out ($0.25 at Haiku 4.5's list)."""
    max_tokens = 1000

    def __init__(self):
        self.n = 0

    def chat(self, messages, tools, max_tokens=None):
        self.n += 1
        return {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 200_000, "completion_tokens": 10_000}}


def test_usd_prices_the_returned_counts_at_haiku_list():
    assert cp.usd(1_000_000, 0) == 1.0 and cp.usd(0, 1_000_000) == 5.0 and cp.usd(200_000, 10_000) == pytest.approx(0.25)
    assert cp.usd(None, None) == 0.0


def test_metered_prices_each_call_and_refuses_one_whose_worst_case_passes_the_cap(tmp_path):
    ep = _Ep()
    m = cp.Metered(ep, cap_usd=0.6, ledger=tmp_path / "k.usage.jsonl", chars_per_token=2.0)
    msg = [{"role": "user", "content": "x" * 20_000}]  # 10k tokens in; with 1,000 out the worst case is $0.015
    m.chat(msg, [], 1000)
    m.chat(msg, [], 1000)
    assert m.spent == pytest.approx(0.5) and ep.n == 2
    with pytest.raises(cp.BudgetStop):
        m.chat(msg, [], 100_000)  # $0.50 spent + a $0.51 worst case passes $0.60: the call is not made
    assert ep.n == 2
    m.chat(msg, [], None)  # max_tokens from the endpoint: $0.515 fits
    assert ep.n == 3
    rows = [json.loads(l) for l in open(tmp_path / "k.usage.jsonl")]
    assert [r["usd"] for r in rows] == [0.25, 0.25, 0.25] and rows[-1]["spent_usd"] == 0.75
    (tmp_path / "j.usage.jsonl").write_text(json.dumps({"usd": 0.125}) + "\n")
    assert cp.spent_in(tmp_path) == pytest.approx(0.875), "every ledger in the directory, so a later process sees what an earlier one spent"


def test_confirmations_count_round_one_answers_with_the_capped_callees_apart():
    t1 = {"holes": [{"id": "c1", "type": "ANCHOR_CONFIRM", "provenance": {"anchor": "x"}},
                    {"id": "c2", "type": "ANCHOR_CONFIRM", "provenance": {"anchor": "y", "symbol": "p.f", "callee_of": "p.main"}},
                    {"id": "c3", "type": "ANCHOR_CONFIRM", "provenance": {"anchor": "z", "symbol": "p.g", "callee_of": "p.main"}},
                    {"id": "u1", "type": "UNRESOLVED", "terms": []}]}
    rec = {"template_round1": t1, "template_round2": {"holes": []},
           "rounds": [{"round": 1, "holes_asked": ["u1", "c1", "c2", "c3"], "fills": {"fills": {"c1": {"confirm": True}, "c2": {"confirm": False}}}},
                      {"round": 2, "holes_asked": ["c9"], "fills": {"fills": {}}}]}
    assert cp.confirmations(rec) == {"asked": 1, "yes": 1, "capped_asked": 2, "capped_no": 1, "capped_unanswered": 1}


def test_changed_files_reads_the_diff_headers_not_the_files_the_grounder_wrote():
    d = ("diff --git a/x.go b/x.go\n--- a/x.go\n+++ b/x.go\n@@ -1 +1 @@\n-a\n+b\n"
         "diff --git a/n.go b/n.go\nnew file mode 100644\n--- /dev/null\n+++ b/n.go\n@@ -0,0 +1 @@\n+c\n"
         "diff --git a/gone.go b/gone.go\ndeleted file mode 100644\n--- a/gone.go\n+++ /dev/null\n@@ -1 +0,0 @@\n-d\n")
    assert cp.changed_files(d) == ["gone.go", "n.go", "x.go"]
    assert cp.changed_files("") == []


def test_key_from_reads_one_named_line_and_tolerates_names_the_bench_reader_refuses(tmp_path):
    f = tmp_path / "keys.txt"
    f.write_text("# owner's keys\nllm_key=abc\nanthropic_key = \"sk-x\"\nempty_key=\n")
    assert cp.key_from(f, "anthropic_key") == "sk-x" and cp.key_from(f, "llm_key") == "abc"
    with pytest.raises(KeyError):
        cp.key_from(f, "empty_key")
    with pytest.raises(KeyError):
        cp.key_from(f, "missing")


def test_estimate_by_key_reads_the_expected_band_per_arm(tmp_path):
    est = {"rows": [{"key": "k1", "arm": "T", "band": "exp", "per_run": {"usd": 0.06}}, {"key": "k1", "arm": "T-loop", "band": "exp", "per_run": {"usd": 0.01}},
                    {"key": "k1", "arm": "T", "band": "high", "per_run": {"usd": 0.2}}, {"key": "k2", "arm": "O", "band": "exp", "per_run": {"usd": 1.0}}]}
    (tmp_path / "e.json").write_text(json.dumps(est))
    assert cp.estimate_by_key(tmp_path / "e.json") == {"k1": {"T": 0.06, "T-loop": 0.01, "total": 0.07}}


def test_o_worst_usd_is_the_budget_plus_one_windows_overshoot_and_every_turns_output():
    assert cp.o_worst_usd(1_000_000, 30, 4096) == pytest.approx(1.2 + 30 * 4096 * 5 / 1e6)
    assert cp.o_worst_usd(0, 10, 1000, window=100_000) == pytest.approx(1.0 + 0.05), "no budget: every turn at the window"


def test_o_session_usage_prices_each_call_in_the_t_units_ledger_shape():
    rows = cp.o_session_usage([{"prompt_tokens": 200_000, "completion_tokens": 10_000, "finish_reason": "tool_calls"}, {"prompt_tokens": None}])
    assert [r["usd"] for r in rows] == [0.25, 0.0] and rows[-1]["spent_usd"] == 0.25 and rows[0]["call"] == 1


class _Ledger:
    def __init__(self, graph, tests):
        self.sha = graph["sha"]


def _o_fixture(tmp_path):
    (tmp_path / "g.json").write_text(json.dumps({"sha": "p" * 40}))
    (tmp_path / "t.json").write_text("{}")
    (tmp_path / "gold.diff").write_text("diff --git a/a.go b/a.go\n--- a/a.go\n+++ b/a.go\n@@ -1 +1 @@\n-x\n+y\n"
                                        "diff --git a/b.go b/b.go\n--- a/b.go\n+++ b/b.go\n@@ -1 +1 @@\n-x\n+y\n")
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "k1.template.json").write_text(json.dumps({"holes": []}))
    (tmp_path / "keys.txt").write_text("anthropic_key=sk-test\n")
    u = {"key": "k1", "shape": "single-file", "parent_sha": "p" * 40, "W": 1.0, "a2_rev": 3, "A2": "fix the thing", "gold_diff": str(tmp_path / "gold.diff"),
         "parent_graph": str(tmp_path / "g.json"), "parent_tests": str(tmp_path / "t.json")}
    (tmp_path / "units.jsonl").write_text(json.dumps(u) + "\n")
    return ["o-units", str(tmp_path / "units.jsonl"), "--keys", "k1", "--templates", str(tmp_path / "templates"), "--clone", str(tmp_path / "clone"),
            "--out", str(tmp_path / "out"), "--sessions", str(tmp_path / "sessions"), "--base-url", "https://x/v1", "--model", "m",
            "--secrets", str(tmp_path / "keys.txt"), "--key-name", "anthropic_key", "--wp", "wp-6"]


def test_o_units_does_not_launch_a_session_whose_worst_case_passes_the_cap(tmp_path, monkeypatch):
    import os
    from hobbes.derive import harness as H
    from hobbes.derive import template as T
    monkeypatch.setattr(T, "Ledger", _Ledger)
    monkeypatch.setattr(H, "run_o", lambda *a, **k: pytest.fail("launched"))
    monkeypatch.delenv("HOBBES_LLM_API_KEY", raising=False)
    assert cp.main(_o_fixture(tmp_path) + ["--total-cap", "1.5"]) == 4, "a 1M-token session's worst case is $1.81"
    assert "HOBBES_LLM_API_KEY" not in os.environ


def test_o_units_meters_the_session_from_its_calls_and_writes_one_row(tmp_path, monkeypatch):
    import os
    from hobbes.derive import harness as H
    from hobbes.derive import template as T
    monkeypatch.setattr(T, "Ledger", _Ledger)
    monkeypatch.delenv("HOBBES_LLM_API_KEY", raising=False)
    seen, roots = {}, []

    def fake_run_o(clone, sha, task, L, source, graphs, *, session_id, sessions_root, out_dir, template, token_budget, loop_args, **kw):
        seen.update(key=os.environ.get("HOBBES_LLM_API_KEY"), task=task, sha=sha, budget=token_budget, loop_args=loop_args)
        roots.append((sessions_root, session_id))
        (sessions_root / session_id).mkdir(parents=True)
        (sessions_root / session_id / "calls.jsonl").write_text(json.dumps({"prompt_tokens": 400_000, "completion_tokens": 2_000}) + "\n")
        (out_dir / f"{session_id}.session.log").write_text('{"type": "result", "is_error": false, "num_turns": 7, "tool_calls": 9}\n')
        (out_dir / f"{session_id}.o.diff").write_text("diff --git a/a.go b/a.go\n--- a/a.go\n+++ b/a.go\n@@ -1 +1 @@\n-x\n+z\n")
        return {"session_rc": 0, "plan": {"units": ["u"], "paths": ["a.go", "c.go"], "refusal": None}, "patch_files": ["a.go"], "wall_s": 3.0,
                "verify": {"verdict": "fail", "applies": True, "summary": {"P2F": 1}, "containment": {"all_contained": True}, "wall_s": 1.0}}
    monkeypatch.setattr(H, "run_o", fake_run_o)
    assert cp.main(_o_fixture(tmp_path) + ["--total-cap", "5", "--loop-arg=--sampling=model-default"]) == 0
    assert seen == {"key": "sk-test", "task": "fix the thing", "sha": "p" * 40, "budget": 1_000_000, "loop_args": ["--sampling=model-default"]}
    assert "HOBBES_LLM_API_KEY" not in os.environ, "the key is handed to the session only while it runs"
    ledger = [json.loads(l) for l in open(tmp_path / "out" / "k1.usage.jsonl")]
    assert [r["usd"] for r in ledger] == [0.41] and cp.spent_in(tmp_path / "out") == pytest.approx(0.41)
    row = json.loads((tmp_path / "out" / "rows.jsonl").read_text())
    assert (row["wp"], row["arm"], row["usd"], row["turns"], row["stop"]) == ("wp-6", "O", 0.41, 7, "done")
    assert row["rfe_gold"] == [0.5, 1.0, 0.5] and row["plan_rfe"] == [0.33, 0.5, 0.5] and row["files_changed"] == ["a.go"]
    assert row["verify"]["verdict"] == "fail" and row["verify"]["all_contained"] is True
    assert row["recall"]["rule"] == cp.RECALL_RULE and "error" in row["recall"], "a clone the scan cannot read is said in the row, not raised"
    assert row["recall"]["upper"] == cp.RECALL_UPPER[:12], "no flag, no unit field: gitleaks' pin, rounds 1-2 unchanged"
    assert roots == [(tmp_path / "sessions" / row["session"], row["session"])], "D-x: one sessions root per session"
    assert "sk-test" not in (tmp_path / "out" / "rows.jsonl").read_text()
    # §2.5's fields (WP-18b, D-v): gold touches no test here, so gold_tests is n/a; the verdict is the verifier's
    assert (row["gold_tests"], row["verdict"], row["turns_to_first_edit"]) == ({"verdict": "n/a", "ids": []}, "fail", None)


def test_first_edit_turn_reads_the_first_successful_edit_from_a_transcript(tmp_path):
    """WP-18b, D-v: WP-20's post-hoc reading, reused — a failed edit is not an edit; no transcript is None."""
    call = lambda i, name: {"id": i, "type": "function", "function": {"name": name, "arguments": "{}"}}
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "b"},
            {"role": "assistant", "tool_calls": [call("r1", "read_file")]}, {"role": "tool", "tool_call_id": "r1", "content": "1\tx"},
            {"role": "assistant", "tool_calls": [call("e1", "edit_file")]}, {"role": "tool", "tool_call_id": "e1", "content": "ERROR: old_text occurs 0 times"},
            {"role": "assistant", "tool_calls": [call("w1", "write_file")]}, {"role": "tool", "tool_call_id": "w1", "content": "wrote a.go"}]
    (tmp_path / "t.jsonl").write_text("".join(json.dumps(m) + "\n" for m in msgs))
    assert cp.first_edit_turn(tmp_path / "t.jsonl") == 3 and cp.first_edit_turn(tmp_path / "none.jsonl") is None


def test_o_units_reads_recall_at_the_units_upper_and_an_edit_less_session_is_empty(tmp_path, monkeypatch):
    """WP-18b, D-u: recall's range ends at the repo's own pin — --recall-upper, else the unit's `recall_upper`, else gitleaks'
    RECALL_UPPER. D-v: a session that left no diff reads `verdict: empty` (neither pass nor blocked): the gate clears the empty diff, no
    repair turn is launched, gold_tests reads `empty-diff` and there is no recall."""
    from hobbes.derive import harness as H
    from hobbes.derive import template as T
    monkeypatch.setattr(T, "Ledger", _Ledger)
    monkeypatch.delenv("HOBBES_LLM_API_KEY", raising=False)
    uppers = []
    real = cp.recall_scan
    monkeypatch.setattr(cp, "recall_scan", lambda diff, gold, repo, parent, upper=cp.RECALL_UPPER: uppers.append(upper) or real(diff, gold, repo, parent, upper))
    one = "diff --git a/a.go b/a.go\n--- a/a.go\n+++ b/a.go\n@@ -1 +1 @@\n-x\n+z\n"
    patches = iter([one, one, one, ""])

    def fake_run_o(clone, sha, task, L, source, graphs, *, session_id, sessions_root, out_dir, **kw):
        (out_dir / f"{session_id}.o.diff").write_text(next(patches))
        return {"session_rc": 0, "plan": {}, "patch_files": [], "wall_s": 1.0, "verify": None}
    monkeypatch.setattr(H, "run_o", fake_run_o)
    monkeypatch.setattr(cp, "gate_session", lambda patch, *a, **k: _gate_rec("clear" if not patch else "blocked"))
    monkeypatch.setattr(cp, "launch", lambda *a, **k: pytest.fail("a repair turn launched"))
    args = _o_fixture(tmp_path) + ["--total-cap", "9"]
    assert cp.main(args) == 0 and cp.main(args + ["--recall-upper", "f7ae439ff5b2"]) == 0
    u = json.loads((tmp_path / "units.jsonl").read_text())
    (tmp_path / "units.jsonl").write_text(json.dumps({**u, "recall_upper": "0123abcd"}) + "\n")
    assert cp.main(args) == 0
    assert uppers == [cp.RECALL_UPPER, "f7ae439ff5b2", "0123abcd"]
    assert cp.main(args + ["--gate-repair"]) == 0, "the edit-less session: its gate clears, nothing is launched"
    empty = [json.loads(l) for l in open(tmp_path / "out" / "rows.jsonl")][-1]
    assert (empty["verdict"], empty["verdict_gate"], empty["gold_tests"], empty["recall"], empty["gate"]["verdict"]) == \
        ("empty", "empty", {"verdict": "empty-diff"}, None, "clear")
    assert not (tmp_path / "out" / "repair-rows.jsonl").exists()


def test_gate_inputs_prefer_the_units_partition_then_the_templates_and_carry_the_map(tmp_path):
    t = tmp_path / "k.template.json"
    t.write_text(json.dumps({"constraints": {"write_partition": ["b.go", "a.go"]}}))
    m = {"partition": ["a.go"], "files": [], "symbols": []}
    assert cp.gate_inputs({"partition": ["a.go"], "blind_spot_map": m}, t) == (["a.go"], "unit", m)
    assert cp.gate_inputs({}, t) == (["b.go", "a.go"], "template", None)
    assert cp.gate_inputs({}, tmp_path / "missing.json") == (None, None, None)


def test_repair_command_resumes_the_recorded_argv_for_one_turn():
    rec = ["/bin/hobbes-session", "start", "--repo", "/old", "--ref", "p" * 40, "--session", "S1", "--sessions", "/s", "--runtime", "/old/loop.py",
           "--model", "haiku", "--task-file", "/old/brief.md", "--max-turns", "30", "--loop-arg=--sampling=model-default",
           "--loop-arg=--script=/sessions/S1/script.json"]
    cmd = cp.repair_command(rec, session_id="S1-repair1", ref="h" * 40, brief=Path("/o/b.md"), runtime=Path("/new/loop.py"), repo=Path("/clone"))
    assert cmd == ["/bin/hobbes-session", "start", "--repo", "/clone", "--ref", "h" * 40, "--session", "S1-repair1", "--sessions", "/s",
                   "--runtime", "/new/loop.py", "--model", "haiku", "--task-file", "/o/b.md", "--max-turns", "1",
                   "--loop-arg=--sampling=model-default", "--loop-arg=--resume-transcript=/sessions/S1-repair1/resume.jsonl"]


def _gate_rec(verdict):
    from hobbes.derive import gate as gt
    rows = [{"class": "invented", "grounder_class": "invented", "path": "a.go", "line": 1, "term": "frob", "kind": "call", "reason": None,
             "nearest": [], "scope": None, "site": None}] if verdict == "blocked" else []
    return {"verdict": verdict, "blocking": ["invented"] if rows else [], "counts": {**{c: 0 for c in gt.GATE_CLASSES}, "invented": len(rows)},
            "route": False, "unknown_reasons": {}, "rows": rows, "siblings": [], "parent": "p" * 40, "map": None, "record_hash": verdict,
            "partition": {"outside": [], "exempt": [], "source": "template"}, "integrity": {"applies": True, "post_agrees": True}}


def _fake_gate(calls):
    def fake(patch, u, repo, L, out, session_id, template, rule="reach"):
        verdict = "clear" if session_id.endswith("-repair1") else "blocked"
        calls.append((session_id, verdict))
        fake.rules.append(rule)
        (Path(out) / f"{session_id}.gate.json").write_text(json.dumps(_gate_rec(verdict)))
        return _gate_rec(verdict)
    fake.rules = []
    return fake


def _recorded(tmp_path):
    """A recorded o-units run of key k1 (its row, its session's record, diff and transcript) and a clone holding the harvested branch."""
    _o_fixture(tmp_path)
    clone = tmp_path / "clone"
    clone.mkdir()
    _git(clone, "init", "-q")
    (clone / "a.go").write_text("x\n")
    _git(clone, "add", ".")
    _git(clone, "commit", "-q", "-m", "p")
    _git(clone, "checkout", "-q", "-b", "hobbes/S1")
    (clone / "a.go").write_text("z\n")
    _git(clone, "commit", "-q", "-am", "o")
    head = _git(clone, "rev-parse", "HEAD").strip()
    _git(clone, "checkout", "-q", "-b", "later", "HEAD~1")  # the key's gold, past the parent: never in a session's repo (D-x)
    (clone / "b.go").write_text("gold\n")
    _git(clone, "add", ".")
    _git(clone, "commit", "-q", "-m", "gold")
    gold = _git(clone, "rev-parse", "HEAD").strip()
    sroot = tmp_path / "sessions"
    (sroot / "S1").mkdir(parents=True)
    (sroot / "S1" / "transcript.jsonl").write_text(json.dumps({"role": "system", "content": "s"}) + "\n" + json.dumps({"role": "user", "content": "b"}) + "\n")
    rec = tmp_path / "recorded"
    rec.mkdir()
    cmd = ["/bin/hobbes-session", "start", "--repo", "/old", "--ref", "p" * 40, "--session", "S1", "--sessions", str(sroot), "--runtime", "/old/loop.py",
           "--model", "claude-haiku-4-5-20251001", "--task-file", "/old/brief.md", "--max-turns", "30", "--max-tokens", "4096",
           "--loop-arg=--sampling=model-default"]
    (rec / "S1.o.json").write_text(json.dumps({"session": "S1", "command": cmd, "environment": {"links": []}}))
    (rec / "S1.o.diff").write_text("diff --git a/a.go b/a.go\n--- a/a.go\n+++ b/a.go\n@@ -1 +1 @@\n-x\n+z\n")
    (rec / "rows.jsonl").write_text(json.dumps({"key": "k1", "arm": "O", "session": "S1", "verify": {"verdict": "fail"}}) + "\n")
    argv = ["o-units", str(tmp_path / "units.jsonl"), "--keys", "k1", "--templates", str(tmp_path / "templates"), "--clone", str(clone),
            "--out", str(tmp_path / "out"), "--wp", "wp-21", "--recorded", str(rec)]
    return argv, head, sroot, gold


def test_o_units_gate_recorded_gates_each_recorded_session_and_launches_nothing(tmp_path, monkeypatch):
    import os
    from hobbes.derive import template as T
    monkeypatch.setattr(T, "Ledger", _Ledger)
    monkeypatch.delenv("HOBBES_LLM_API_KEY", raising=False)
    argv, *_ = _recorded(tmp_path)
    calls = []
    gs = _fake_gate(calls)
    monkeypatch.setattr(cp, "gate_session", gs)
    monkeypatch.setattr(cp, "launch", lambda *a, **k: pytest.fail("launched"))
    assert cp.main(argv) == 2, "--recorded alone has nothing to do"
    assert cp.main(argv + ["--gate"]) == 0 and calls == [("S1", "blocked")]
    assert gs.rules == ["reach"], "D-s: the drivers gate under reach by default"
    import inspect
    assert inspect.signature(cp.gate_session).parameters["rule"].default == "reach" == inspect.signature(cp.repair_session).parameters["rule"].default
    row = json.loads((tmp_path / "out" / "gate-rows.jsonl").read_text())
    assert (row["wp"], row["arm"], row["session"], row["gate"]["verdict"], row["gate"]["blocking"], row["verify"]) == ("wp-21", "O+gate", "S1", "blocked", ["invented"], "fail")
    assert "HOBBES_LLM_API_KEY" not in os.environ and not (tmp_path / "out" / "rows.jsonl").exists(), "no O row: O is never re-run"
    assert cp.main(argv + ["--gate-repair"]) == 2, "a repair turn needs a key and a cap"


def test_o_units_gate_repair_resumes_the_recorded_session_for_one_bounded_turn(tmp_path, monkeypatch):
    import os
    from hobbes.derive import harness as H
    from hobbes.derive import template as T
    monkeypatch.setattr(T, "Ledger", _Ledger)
    monkeypatch.delenv("HOBBES_LLM_API_KEY", raising=False)
    argv, head, sroot, gold = _recorded(tmp_path)
    calls, launched = [], {}
    monkeypatch.setattr(cp, "gate_session", _fake_gate(calls))

    def fake_launch(cmd, timeout):
        launched.update(cmd=cmd, key=os.environ.get("HOBBES_LLM_API_KEY"))
        repo = cp.argv_value(cmd, "--repo")  # D-x: what the repair turn's container would clone, read while the turn runs
        g = lambda *a: subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)
        launched["cut"] = (g("cat-file", "-e", gold).returncode != 0, set(g("rev-list", "--all").stdout.split()), g("remote").stdout,
                           (Path(repo) / ".git" / "objects" / "info" / "alternates").exists(), (Path(repo) / ".hobbes" / "derived" / "graph.json").exists())
        (sroot / cp.argv_value(cmd, "--session") / "calls.jsonl").write_text(json.dumps({"prompt_tokens": 50_000, "completion_tokens": 1_000}) + "\n")
        edit = {"id": "e1", "type": "function", "function": {"name": "edit_file", "arguments": "{}"}}
        (sroot / cp.argv_value(cmd, "--session") / "transcript.jsonl").write_text(
            "".join(json.dumps(m) + "\n" for m in ({"role": "system", "content": "s"}, {"role": "user", "content": "b"},
                                                    {"role": "assistant", "tool_calls": [edit]}, {"role": "tool", "tool_call_id": "e1", "content": "edited a.go"})))
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"type": "result", "is_error": True, "num_turns": 1, "tool_calls": 1, "edited": True,
                                                                "result": "turn budget (1) exhausted", "resumed": {"messages": 2}}) + "\n", "")
    monkeypatch.setattr(cp, "launch", fake_launch)
    monkeypatch.setattr(H, "session_patch", lambda clone, sha, sid, env=None: "diff --git a/a.go b/a.go\n--- a/a.go\n+++ b/a.go\n@@ -1 +1 @@\n-x\n+w\n")
    monkeypatch.setattr(H, "verify", lambda *a, **k: {"verdict": "pass", "applies": True, "summary": {"F2P": 1}})
    keys = ["--secrets", str(tmp_path / "keys.txt"), "--key-name", "anthropic_key", "--total-cap", "5"]
    assert cp.main(argv + ["--gate-repair"] + keys) == 0
    cmd = launched["cmd"]
    assert [cp.argv_value(cmd, f) for f in ("--session", "--ref", "--max-turns", "--repo", "--runtime", "--model")] == \
        ["S1-repair1", head, "1", str(tmp_path / "out" / "S1-repair1.repo"), str(H.LOOP_PATH), "claude-haiku-4-5-20251001"]
    parent = _git(tmp_path / "clone", "rev-parse", f"{head}~1").strip()
    assert launched["cut"] == (True, {head, parent}, "", False, True), "the repair's repo: O's commit and the parent's ancestry, no gold, no remote"
    assert not (tmp_path / "out" / "S1-repair1.repo").exists(), "the cut repo is removed after the turn"
    assert "--loop-arg=--sampling=model-default" in cmd and cmd[-1] == "--loop-arg=--resume-transcript=/sessions/S1-repair1/resume.jsonl"
    assert (sroot / "S1-repair1" / "resume.jsonl").read_text() == (sroot / "S1" / "transcript.jsonl").read_text()
    brief = Path(cp.argv_value(cmd, "--task-file")).read_text()
    assert brief.startswith("Hobbes checked your change") and "- a.go:1 `frob`" in brief
    assert launched["key"] == "sk-test" and "HOBBES_LLM_API_KEY" not in os.environ, "the key only while the turn runs"
    assert calls == [("S1", "blocked"), ("S1-repair1", "clear")]
    r = json.loads((tmp_path / "out" / "repair-rows.jsonl").read_text())
    assert (r["arm"], r["gate_before"]["verdict"], r["gate_after"]["verdict"], r["verify_after"]["verdict"], r["turns"], r["usd"], r["resumed"]) == \
        ("O+gate+repair", "blocked", "clear", "pass", 1, 0.055, {"messages": 2})
    assert cp.spent_in(tmp_path / "out") == pytest.approx(0.055), "the repair turn is metered under the cap"
    # §2.5's fields on the repair row too (WP-18b, D-u/D-v)
    assert (r["verdict_after"], r["turns_to_first_edit"], r["gold_tests"]) == ("pass", 1, {"verdict": "n/a", "ids": []})
    assert r["recall"]["upper"] == cp.RECALL_UPPER[:12] and "error" in r["recall"]
    # a record without the transcript cannot be resumed faithfully: said in the row, nothing launched
    (sroot / "S1" / "transcript.jsonl").unlink()
    launched.clear()
    assert cp.main(argv + ["--gate-repair"] + keys) == 0 and not launched
    last = [json.loads(l) for l in open(tmp_path / "out" / "repair-rows.jsonl")][-1]
    assert last["error"] == "cannot resume: the record lacks the transcript"
    # the cap stops a repair turn whose worst case would pass it
    (sroot / "S1" / "transcript.jsonl").write_text(json.dumps({"role": "system", "content": "s"}) + "\n")
    assert cp.main(argv + ["--gate-repair"] + keys[:-1] + ["0.2"]) == 4 and not launched


PRE = Path.home() / ".hobbes/bench/calvin-gate/wp-20"


@pytest.mark.skipif(not (PRE / "preflight/manifest/posthoc.jsonl").exists(), reason="calvin-gate WP-20's pre-flight records are not on this box")
def test_recall_and_first_edit_read_the_preflight_as_wp21_posthoc_does():
    """WP-18b, D-u/D-v on WP-20's pre-flight: at the fzf pin (--recall-upper's value) the driver's recall reads on all eight diffs (the
    manifest and withheld runs, O and repair) and equals wp21_posthoc.py's recorded values, as turns-to-first-edit does."""
    units = {u["key"]: u for u in map(json.loads, open(Path.home() / ".hobbes/bench/calvin-gate/wp-17/units.jsonl"))}
    clone = PRE / "repos" / "fzf"
    want = {(r["key"], r["arm"]): r for r in map(json.loads, open(PRE / "preflight/manifest/posthoc.jsonl"))}
    seen = 0
    for run in ("manifest", "withheld"):
        d = PRE / "preflight" / run
        reps = {r["session"]: r for r in map(json.loads, open(d / "repair-rows.jsonl"))}
        for r in map(json.loads, open(d / "rows.jsonl")):
            u = units[r["key"]]
            gold = Path(u["gold_diff"]).read_text(errors="surrogateescape")
            upper = cp.recall_upper_of(u, "f7ae439ff5b2", clone)
            for arm, sess in (("O", r["session"]), ("O+gate+repair", reps[r["session"]]["repair_session"])):
                rec = cp.recall_scan((d / f"{sess}.o.diff").read_text(errors="surrogateescape"), gold, clone, u["parent_sha"], upper)
                assert "error" not in rec and rec == want[(r["key"], arm)]["recall"], (run, r["key"], arm, rec)
                assert cp.first_edit_turn(PRE / "sessions" / run / sess / "transcript.jsonl") == want[(r["key"], arm)]["turns_to_first_edit"]
                seen += 1
    assert seen == 8


def test_recall_norm_excludes_short_and_punctuation_only_lines():
    for line in ("   }", "\t}, {", "// ----------", "break", ""):
        assert cp.recall_norm(line) is None, line
    assert cp.recall_norm('\t\tKeywords: []string{"x"},  ') == 'Keywords: []string{"x"},'
    assert cp.recall_norm("return") == "return"  # six characters: counted (it is in every Go parent, so never novel)


def test_added_lines_reads_hunk_counts_not_header_shapes():
    diff = ("diff --git a/a b/a\n--- a/a\n+++ b/a\n@@ -1,2 +1,3 @@\n ctx\n-old\n+++plus\n+new\n\\ No newline at end of file\n"
            "diff --git a/b b/b\nnew file mode 100644\n--- /dev/null\n+++ b/b\n@@ -0,0 +1 @@\n+only\n")
    assert cp.added_lines(diff) == ["++plus", "new", "only"]
    assert cp.added_lines("") == []


def _git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
                          cwd=repo, check=True, capture_output=True, text=True).stdout


def _history(tmp_path):
    """parent → gold (adds Gold) → later (adds a line only later history holds); returns (repo, parent, gold diff, upper)."""
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    base = "package a\n\nfunc Existing() int {\n\treturn 1\n}\n"
    (repo / "a.go").write_text(base)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "parent")
    parent = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "a.go").write_text(base + '\nfunc Gold() string {\n\treturn "gold line"\n}\n')
    _git(repo, "commit", "-qam", "gold")
    gold = _git(repo, "show", "--format=", "HEAD")
    (repo / "b.go").write_text('package a\n\nvar later = "only upstream later"\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "later")
    return repo, parent, gold, _git(repo, "rev-parse", "HEAD").strip()


ARM = ("diff --git a/a.go b/a.go\n--- a/a.go\n+++ b/a.go\n@@ -1,0 +1,6 @@\n+\treturn 1\n+func Gold() string {\n"
       '+  return "gold line"\n+var later = "only upstream later"\n+invented := "nowhere at all"\n+}\n')


def test_recall_scan_splits_novel_lines_by_gold_and_later_history(tmp_path):
    repo, parent, gold, upper = _history(tmp_path)
    rec = cp.recall_scan(ARM, gold, repo, parent, upper)
    # 5 counted (`}` excluded); `return 1` is in the parent, so 4 novel: 2 gold (indentation ignored), 1 only later, 1 nowhere
    assert {k: rec[k] for k in ("added", "novel", "in_gold", "gold", "in_upstream", "upstream", "upstream_not_gold", "recalled")} == \
        {"added": 5, "novel": 4, "in_gold": 2, "gold": 0.5, "in_upstream": 3, "upstream": 0.75, "upstream_not_gold": 1, "recalled": False}
    assert rec["rule"] == cp.RECALL_RULE and rec["upper"] == upper[:12]
    # history stops at the pin: read up to the gold commit, the later line is not upstream
    assert cp.recall_scan(ARM, gold, repo, parent, _git(repo, "rev-parse", "HEAD~1").strip())["in_upstream"] == 2


def test_recall_scan_marks_recalled_at_the_stated_threshold(tmp_path, monkeypatch):
    repo, parent, gold, upper = _history(tmp_path)
    assert cp.RECALLED_AT == (10, 0.5)
    monkeypatch.setattr(cp, "RECALLED_AT", (3, 0.75))
    assert cp.recall_scan(ARM, gold, repo, parent, upper)["recalled"] is True
    monkeypatch.setattr(cp, "RECALLED_AT", (3, 0.8))
    assert cp.recall_scan(ARM, gold, repo, parent, upper)["recalled"] is False


def test_recall_scan_with_no_novel_line_or_no_repo_never_raises(tmp_path):
    repo, parent, gold, upper = _history(tmp_path)
    rec = cp.recall_scan("", gold, repo, parent, upper)
    assert (rec["novel"], rec["gold"], rec["upstream"], rec["recalled"]) == (0, None, None, False)
    assert "error" in cp.recall_scan(ARM, gold, tmp_path / "missing", parent, upper)
    assert cp.recall_scan(ARM, gold, repo, "f" * 40, upper)["error"].startswith("parent")
