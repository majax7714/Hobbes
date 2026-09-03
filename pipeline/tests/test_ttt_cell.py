"""The primary cell's instruments (ADR-099 review item 9): derived units
from a change-spec, the arm briefs, and the model-free scorer — HSR over
what an agent emits, RFE against the unit's interior, manifest_ignore."""

import json
from pathlib import Path

from hobbes.ttt import cell
from tests.test_ttt_corpus import graph_fixture


def spec_for(proposal, units):
    return {"task": "t1", "proposal": proposal, "seeds": {"app.core": "lexical"},
            "units": [{"name": n, "deferred": d} for n, d in units],
            "contexts": [{"unit": n, "modules": [{"id": "app.core", "path": "src/app/core.py"}],
                          "guarding_tests": ["tests/test_core.py::test_handle"]} for n, _ in units]}


class TestUnits:
    def test_one_unit_per_non_deferred_plan_unit_with_manifest(self, tmp_path):
        derive = lambda proposal, seeds: spec_for(proposal, [("U1", False), ("U2", False), ("U3", True)])
        render = lambda spec, unit: f"## Interior for {unit}\n- src/app/core.py"
        units, errors = cell.derive_units(tmp_path, {"abc123def456": "Do the thing.", "ffffff000000": "Other."},
                                          {"abc123def456": ["src/app/core.py"]}, derive=derive, render=render)
        assert [u.id for u in units] == ["abc123def456/U1", "abc123def456/U2", "ffffff000000/U1", "ffffff000000/U2"]
        assert units[0].paths == ["src/app/core.py"] and units[0].guarding_tests == ["tests/test_core.py::test_handle"]
        assert units[0].manifest.startswith("## Interior for U1") and errors == []
        cell.write_units(units, tmp_path / "u.jsonl", [{"commit": "x", "error": "SeedError: no seed"}])
        back, errs = cell.read_units(tmp_path / "u.jsonl")
        assert [b["id"] for b in back] == [u.id for u in units] and errs == [{"commit": "x", "error": "SeedError: no seed"}]

    def test_a_refused_proposal_is_recorded_not_dropped(self, tmp_path):
        def derive(proposal, seeds):
            if "bad" in proposal:
                raise RuntimeError("every seed is a hub")
            return spec_for(proposal, [("U1", False)])
        units, errors = cell.derive_units(tmp_path, {"a": "good", "b": "bad"}, derive=derive, render=lambda s, u: "m")
        assert [u.id for u in units] == ["a/U1"] and errors == [{"commit": "b", "error": "RuntimeError: every seed is a hub"}]


class TestBrief:
    def test_aided_differs_from_unaided_by_the_manifest_only(self):
        u = {"proposal": "Do the thing.", "manifest": "## Interior\n- src/app/core.py"}
        bare, aided = cell.brief(u, "demo", "abcdef123456", False), cell.brief(u, "demo", "abcdef123456", True)
        assert bare.startswith("You are working in a checkout of demo at commit abcdef123456")
        assert "There is no shell" in bare and "## Task\nDo the thing." in bare and "Interior" not in bare
        assert aided.startswith(bare) and "## Derived context (Hobbes, graph @ abcdef123456" in aided and "- src/app/core.py" in aided

    def test_a_long_manifest_is_cut_and_the_cut_stated(self):
        u = {"proposal": "x", "manifest": "y" * (cell.MANIFEST_CAP + 500)}
        text = cell.brief(u, "demo", "abcdef123456", True)
        assert "cut by 500 characters" in text and len(text) < cell.MANIFEST_CAP + 900


def assistant(content="", calls=()):
    return {"role": "assistant", "content": content,
            "tool_calls": [{"function": {"name": n, "arguments": json.dumps(a)}} for n, a in calls]}


class TestScore:
    def names(self):
        return cell.graph_names(graph_fixture())

    def test_references_come_from_code_writes_and_backticks_and_own_definitions_are_known(self):
        msgs = [assistant("I will edit `app.core.handle_request` and mention `render_page`; plain words stay out.",
                          [("write_file", {"path": "src/app/new.py", "content": "def fresh_helper(x):\n    return render_page(x)\n"})]),
                assistant("```python\nfresh_helper(1)\nMadeUp.thing()\n```")]
        refs, defined = cell.references(msgs)
        assert defined == {"fresh_helper"}
        assert "app.core.handle_request" in refs and "render_page" in refs and "MadeUp.thing" in refs
        assert "plain" not in refs and "words" not in refs

    def test_resolution_buckets(self):
        names = self.names()
        assert cell.resolve("app.core.handle_request", names, set()) == "in-graph"
        assert cell.resolve("handle_request", names, set()) == "in-graph"
        assert cell.resolve("src/app/core.py", names, set()) == "in-graph"
        assert cell.resolve("core.py", names, set()) == "in-graph"
        assert cell.resolve("fresh_helper", names, {"fresh_helper"}) == "defined"
        assert cell.resolve("MadeUp.thing", names, set()) == "hallucinated"
        assert cell.resolve("nothing_here", names, set()) == "hallucinated"

    def test_external_imports_are_unverifiable(self):
        graph = graph_fixture()
        graph["nodes"].append({"id": "ext:requests", "kind": "external"})
        names = cell.graph_names(graph)
        assert cell.resolve("requests.get", names, set()) == "unverifiable"

    def test_hsr_counts_only_judged_references(self):
        names = self.names()
        msgs = [assistant("", [("edit_file", {"path": "src/app/core.py", "old_text": "a", "new_text": "handle_request(1)\nGhost_fn()\n"})])]
        s = cell.score_transcript(msgs, names)
        assert s["in-graph"] == 1 and s["hallucinated"] == 1 and s["hsr"] == 0.5 and s["invented"] == ["Ghost_fn"]
        assert cell.score_transcript([assistant("nothing code shaped here")], names)["hsr"] is None

    def test_rfe_and_manifest_ignore(self):
        unit = {"paths": ["src/app/core.py", "src/app/util.py"], "guarding_tests": ["tests/test_core.py::test_handle"]}
        r = cell.rfe(["src/app/core.py", "docs/x.md"], unit["paths"])
        assert r["jaccard"] == round(1 / 3, 4) and r["precision"] == 0.5 and r["recall"] == 0.5 and r["outside"] == ["docs/x.md"]
        msgs = [assistant("The file src/app/util.py does not exist in this checkout. I will create it.")]
        mi = cell.manifest_ignore(msgs, ["src/app/core.py"], unit)
        assert mi["ignored"] and mi["denials"][0]["named"] == ["src/app/util.py"] and not mi["edits_elsewhere"]
        mi = cell.manifest_ignore([assistant("Editing now.")], ["docs/x.md"], unit)
        assert mi["ignored"] and mi["edits_elsewhere"] and mi["denials"] == []
        assert not cell.manifest_ignore([assistant("Editing now.")], ["src/app/core.py"], unit)["ignored"]

    def test_score_run_and_report(self, tmp_path):
        names = self.names()
        t = tmp_path / "t.jsonl"
        t.write_text(json.dumps(assistant("", [("edit_file", {"path": "src/app/core.py", "old_text": "a", "new_text": "handle_request(1)\n"})])) + "\n")
        patch = "diff --git a/src/app/core.py b/src/app/core.py\n--- a/src/app/core.py\n+++ b/src/app/core.py\n@@ -1 +1 @@\n-a\n+b\n"
        unit = {"id": "c/U1", "paths": ["src/app/core.py"], "guarding_tests": []}
        rows = []
        for arm, aided in (("A0", False), ("A1", True), ("A2", False), ("A3", True)):
            run = {"arm": arm, "transcript": str(t), "patch": patch, "envelope": {"num_turns": 2}, "wall_s": 3.0, "model": "m"}
            rows.append(cell.score_run(run, unit, names, aided))
        assert rows[0]["hsr_hsr"] == 0.0 and rows[0]["rfe"]["jaccard"] == 1.0 and rows[0]["manifest_ignore"] is None
        assert rows[1]["manifest_ignore"]["ignored"] is False and rows[1]["outcome"] == "patch" and rows[1]["applies"]
        rep = cell.cell_report(rows, resamples=50)
        assert rep["n_units"] == 1 and rep["arms"]["A1"]["manifest_ignore"]["mean"] == 0.0
        assert "manifest_ignore" not in rep["arms"]["A0"] and rep["arms"]["A0"]["outcomes"]["patch"] == 1
        assert "hsr:A2-A1" in rep["comparisons"]
        text = cell.format_cell_report(rep)
        assert text.startswith("units 1") and "A3" in text and "model + prompt" in text
