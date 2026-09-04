"""The Calvin M0 probe's pure pieces (`scripts/calvin_probe.py`): hunk ranges, absent-file classes, span overlap, the `new` term test."""
import importlib.util
import sys
from pathlib import Path

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
