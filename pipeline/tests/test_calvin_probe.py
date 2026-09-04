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
