"""The Calvin hole language v0 (`hobbes.derive.holes`): the hand-written template validates, fills are checked by shape, the render is fillable, and the template's facts match the ledger where it is present."""
import json
import os
import subprocess
from pathlib import Path

import pytest

from hobbes.derive import holes

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "bench" / "calvin" / "templates" / "c59916fe2222.template.json"
LEDGER = Path(os.path.expanduser("~/.hobbes/bench/calvin/graphs-laneb/c59916fe2222.json"))


@pytest.fixture
def t():
    return json.loads(TEMPLATE.read_text())


def test_hand_written_template_is_valid(t):
    assert holes.validate_template(t) == []
    ids = [h["id"] for h in t["holes"]]
    assert len(ids) == len(set(ids))
    assert {h["type"] for h in t["holes"]} >= set(holes.HOLE_TYPES) - {"ANCHOR"}, "every hole type but ANCHOR is exercised (anchors resolved)"


def test_validator_names_defects(t):
    bad = json.loads(json.dumps(t))
    bad["holes"][0]["id"] = bad["holes"][1]["id"]
    bad["holes"].append({"id": "z", "type": "BODY", "span": None, "constraints": {}, "provenance": {}, "fill_schema": holes.FILL_SHAPES["BODY"]})
    bad["holes"].append({"id": "y", "type": "NOPE"})
    errs = holes.validate_template(bad)
    assert any("duplicate" in e for e in errs)
    assert any("z: a BODY hole needs a span" in e for e in errs)
    assert any("unknown type" in e for e in errs)


def test_fill_shapes():
    body = {"type": "BODY", "id": "h"}
    assert holes.validate_fill(body, "unchanged") == []
    assert holes.validate_fill(body, {"code": "x"}) == []
    assert holes.validate_fill(body, {"cod": "x"})
    cu = {"type": "CALLER_UPDATE", "id": "h"}
    assert holes.validate_fill(cu, {"decision": "no", "reason": "signature unchanged"}) == []
    assert holes.validate_fill(cu, {"decision": "yes", "reason": "new arg"}) == ["a 'yes' carries a body"]
    ns = {"type": "NEW_SYMBOL", "id": "n"}
    assert holes.validate_fill(ns, {"covered_by": ["h2", "h5"]}) == []
    assert holes.validate_fill(ns, {"name": "NoTests", "file": "a.go", "body": "..."}), "a placed symbol names where"
    un = {"type": "UNRESOLVED", "id": "u", "terms": [{"term": "go-rta", "nearest": []}, {"term": "x", "nearest": []}]}
    errs = holes.validate_fill(un, {"classes": {"go-rta": "refers"}})
    assert "'go-rta': 'refers' names its node in refers_to" in errs and "'x': not classified" in errs


def test_fills_document_against_template(t):
    doc = {"fills": {"h1": "unchanged", "h2": {"code": "type Options struct{}"}, "h3": "unchanged", "h4": {"code": "..."},
                     "h5": {"decision": "yes", "reason": "pass the flag", "body": "..."}, "n1": {"covered_by": ["h2", "h5"]}, "f1": {"code": "", "span": {"path": "a", "start": 1, "end": 1}}},
           "patterns": {"CALLER_UPDATE": "unchanged", "MODULE_REGION": "unchanged", "TEST_EXPECTATION": "unchanged", "COCHANGE_TOUCH": "unchanged"}}
    assert holes.validate_fills(t, doc) == {}
    del doc["patterns"]["MODULE_REGION"]
    missing = holes.validate_fills(t, doc)
    assert missing and all(v == ["missing"] and k.startswith("m") for k, v in missing.items())


def test_render_lists_every_open_hole_and_reads_spans_from_git(t):
    try:
        subprocess.run(["git", "cat-file", "-e", t["key"]["parent_sha"]], cwd=ROOT, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("parent sha not in this checkout")
    md = holes.render(t, ROOT)
    for h in t["holes"]:
        if "fill" not in h and h.get("closed") is None:
            assert f"### {h['id']} · {h['type']}" in md
    assert "func Run(o Options) (*edges.OracleExport, error)" in md, "h3's one-line span is the signature at the parent"
    assert '"tests": true' not in md and "Tests: true," in md, "h4 shows the body at the parent"
    assert "## Closed before you" in md and "h6" in md
    assert "## How to answer" in md


@pytest.mark.skipif(not LEDGER.exists(), reason="the parent ledger is a local, regenerable artifact (calvin_probe.py ingest --lane-b)")
def test_template_facts_match_the_ledger(t):
    g = json.loads(LEDGER.read_text())
    assert g["sha"] == t["key"]["parent_sha"]
    spans = {(s["module"].rsplit("/", 1)[-1] if False else s["id"]): (s["line"], s["end_line"]) for s in g["symbols"]}
    path_of = {n["id"]: n["path"] for n in g["nodes"] if n.get("path")}
    by_span = {(path_of[s["module"]], s["line"], s["end_line"]): s["id"] for s in g["symbols"] if s["module"] in path_of}
    # every symbol-shaped hole sits exactly on a symbol span (h3 is Run's signature line; h6 the call line)
    for h in t["holes"]:
        if h["type"] in ("BODY", "TEST_EXPECTATION") or (h["type"] == "CALLER_UPDATE" and h["id"] not in ("h6",)):
            s = h["span"]
            assert (s["path"], s["start"], s["end"]) in by_span, h["id"]
    # module regions never overlap a symbol span
    for h in t["holes"]:
        if h["type"] == "MODULE_REGION":
            s = h["span"]
            for (p, a, b) in by_span:
                if p == s["path"]:
                    assert b < s["start"] or a > s["end"], (h["id"], (a, b))
    # the edges the CALLER_UPDATE holes cite exist, semantic
    edges = {(e["from"], e["to"], e["type"], e["tier"]) for e in g["symbol_edges"]}
    assert ("bench/oracle/cmd/oracle/main.runGoRTA", "bench/oracle/internal/gorta/gorta.Run", "calls", "semantic") in edges
    assert ("bench/oracle/internal/grade/grade_test.cell", "bench/oracle/internal/gorta/gorta.Run", "calls", "semantic") in edges
    # the tests the TEST_EXPECTATION holes cite reach Run in the testmap
    tm = json.loads(LEDGER.with_name("c59916fe2222.tests.json").read_text())
    reach = {tc["id"] for tc in tm["tests"] if "bench/oracle/internal/gorta/gorta.Run" in tc.get("reaches", [])}
    assert len([h for h in t["holes"] if h["type"] == "TEST_EXPECTATION"]) == len(reach) == 9


def test_gold_fills_answer_every_open_hole(t):
    """The exit criterion of step 1, checked: the gold diff expressed as fills validates against the hand-written template with nothing missing."""
    gold = json.loads(TEMPLATE.with_name("c59916fe2222.fills-gold.json").read_text())
    assert holes.validate_fills(t, gold) == {}
    assert "NoTests bool" in gold["fills"]["h2"]["code"] and "Tests: !o.NoTests" in gold["fills"]["h4"]["code"]
    assert gold["fills"]["n1"] == {"covered_by": ["h2", "h5"]}, "the new thing is a field and a local, not a top-level symbol"
