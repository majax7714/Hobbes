"""The Calvin M0 probe's pure pieces (`scripts/calvin_probe.py`): hunk ranges, absent-file classes, span overlap, the `new` term test."""
import importlib.util
import json
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
