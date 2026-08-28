"""Requirement coverage — the planner's guarantee (ADR-084 / ADR-085).

The parser, the ownership rule, the imperative precursor, and the
staged run's three outcomes (covered → requirements are the task and
the proposal leaves the brief; uncovered → one re-plan, then strict
stops at plan cost or assign hands the leftovers to the seed unit; no
requirements → the pre-085 brief, recorded). Quota-free: the stand-in
session in test_run drives every path.
"""

from __future__ import annotations

import json

import pytest

from hobbes.run.coverage import (
    PlanCoverageError, assign_requirements, imperatives, imperatives_unmentioned,
    parse_requirement, requirements_from_handoff, unit_task,
)
from hobbes.run.handoff import parse_handoff
from tests.test_changespec import plan_repo  # noqa: F401
from tests.test_run import staged_session  # noqa: F401

SYMPY_ISSUE = """Add evaluation for polylog: polylog(2, 1/2) should be -log(2)**2/2 + pi**2/12.
Also, the exp_polar term in the expansion of polylog(1, z) should be removed, since -log(1-z) is correct.
This is a paragraph of background about how polylog works in sympy."""


class TestParse:
    def test_requirement_lines_keep_their_commas_and_name_their_owner(self):
        h = parse_handoff("requirements:\n"
                          "- R1: polylog(2, 1/2) evaluates to -log(2)**2/2 + pi**2/12 -> sympy/functions/special/zeta_functions.py\n"
                          "- R2: remove exp_polar from the expansion (sympy/functions/special/zeta_functions.py)\n"
                          "files: sympy/functions/special/zeta_functions.py\ntests: sympy/functions/special/tests/test_zeta_functions.py")
        reqs = requirements_from_handoff(h)
        assert [r["id"] for r in reqs] == ["R1", "R2"]
        assert reqs[0]["text"] == "polylog(2, 1/2) evaluates to -log(2)**2/2 + pi**2/12"
        assert reqs[0]["files"] == ["sympy/functions/special/zeta_functions.py"]
        assert reqs[1]["files"] == ["sympy/functions/special/zeta_functions.py"]
        # the owner clause never leaked into `files:`
        assert h["files"] == ["sympy/functions/special/zeta_functions.py"]

    def test_owner_clause_shapes_and_the_things_that_are_not_requirements(self):
        assert parse_requirement("- expand keeps the branch -> files: a.py, b.py", 3)["files"] == ["a.py", "b.py"]
        assert parse_requirement("2. the CLI rejects a missing flag", 9)["id"] == "R2"
        bare = parse_requirement("the CLI rejects a missing flag", 4)
        assert bare["id"] == "R4" and bare["files"] == []
        # prose after "in" is not an owner clause; a path inside the text still counts as named
        r = parse_requirement("R3: remove the log term in zeta_functions.py and keep the rest", 1)
        assert r["text"].endswith("keep the rest") and r["files"] == ["zeta_functions.py"]
        assert parse_requirement("sympy/functions/special/zeta_functions.py", 1) is None
        assert parse_requirement("", 1) is None
        # fractions are not paths
        assert "1/2" not in parse_requirement("R1: polylog(2, 1/2) is pi**2/12 -> a/b.py", 1)["files"]

    def test_duplicate_ids_are_renumbered(self):
        reqs = requirements_from_handoff({"requirements": ["R1: one thing", "R1: another thing"]})
        assert [r["id"] for r in reqs] == ["R1", "R2"]

    def test_json_handoff_carries_requirements_too(self):
        h = parse_handoff(json.dumps({"requirements": ["R1: a -> x/y.py"], "files": ["x/y.py"]}))
        assert requirements_from_handoff(h)[0]["files"] == ["x/y.py"]


class TestAssign:
    CONTEXTS = {
        "U1": {"unit": "U1", "modules": [{"id": "pkg.a", "path": "pkg/a.py"}]},
        "U2": {"unit": "U2", "modules": [{"id": "pkg.b", "path": "pkg/b.py"}]},
    }

    def test_named_file_owns_and_an_unknown_file_is_uncovered(self):
        reqs = [{"id": "R1", "text": "a", "files": ["pkg/a.py"]},
                {"id": "R2", "text": "b", "files": ["pkg/b.py"]},
                {"id": "R3", "text": "c", "files": ["nowhere/c.py"]}]
        cov = assign_requirements(reqs, {"pkg/a.py": "pkg.a", "pkg/b.py": "pkg.b"}, self.CONTEXTS, ["pkg/a.py"])
        assert cov["status"] == "uncovered"
        assert cov["by_unit"] == {"U1": ["R1"], "U2": ["R2"]}
        assert [r["id"] for r in cov["uncovered"]] == ["R3"]
        assert cov["seed_unit"] == "U1"

    def test_a_fileless_requirement_is_owned_only_when_the_plan_is_contained(self):
        reqs = [{"id": "R1", "text": "a", "files": []}]
        one = assign_requirements(reqs, {"pkg/a.py": "pkg.a"}, self.CONTEXTS, ["pkg/a.py"])
        assert one["status"] == "covered" and one["requirements"][0]["source"] == "contained"
        two = assign_requirements(reqs, {"pkg/a.py": "pkg.a", "pkg/b.py": "pkg.b"}, self.CONTEXTS,
                                  ["pkg/a.py", "pkg/b.py"])
        assert two["status"] == "uncovered"

    def test_assign_mode_hands_leftovers_to_the_seed_unit_and_says_so(self):
        reqs = [{"id": "R1", "text": "a", "files": ["pkg/a.py"]}, {"id": "R2", "text": "lost", "files": []}]
        cov = assign_requirements(reqs, {"pkg/a.py": "pkg.a", "pkg/b.py": "pkg.b"}, self.CONTEXTS,
                                  ["pkg/a.py", "pkg/b.py"], mode="assign")
        assert cov["status"] == "assigned" and cov["by_unit"]["U1"] == ["R1", "R2"]
        assert cov["requirements"][1]["source"] == "assigned"
        task = unit_task(cov, "U1")
        assert "R2: lost" in task and "assigned to you by the orchestrator" in task and "C-57" in task
        assert unit_task(cov, "U2") == ""

    def test_no_requirements_is_its_own_status(self):
        assert assign_requirements([], {}, self.CONTEXTS, [])["status"] == "no-requirements"

    def test_the_error_names_the_uncovered_requirement(self):
        cov = {"status": "uncovered", "uncovered": [{"id": "R3", "text": "the CLI prints the count"}]}
        assert "R3: the CLI prints the count" in str(PlanCoverageError(cov))
        assert "stated no requirements" in str(PlanCoverageError({"status": "no-requirements"}))


class TestImperatives:
    def test_the_sympy_drop_is_reported_and_the_kept_half_is_not(self):
        # The seventy-sixth BUILDLOG finding, reproduced lexically: the
        # planner's approach covered exp_polar and dropped the value.
        imps = imperatives(SYMPY_ISSUE)
        assert len(imps) == 2 and imps[0].startswith("Add evaluation")
        dropped = imperatives_unmentioned(SYMPY_ISSUE, ["approach: remove unnecessary exp_polar terms from polylog expansion"])
        assert dropped == [imps[0]]
        assert imperatives_unmentioned(SYMPY_ISSUE, [
            "requirements: R1: polylog(2, 1/2) evaluates to -log(2)**2/2 + pi**2/12\n"
            "approach: remove unnecessary exp_polar terms from polylog expansion"]) == []

    def test_background_and_short_fragments_are_not_imperatives(self):
        assert imperatives("Fix it. The thing is broken because of reasons that are long.") == []


class TestStagedCoverage:
    PROPOSAL = "improve app.core handle retry"

    def _run(self, plan_repo, staged_session, tmp_path, monkeypatch, planner, **kw):  # noqa: F811
        from hobbes.run.stages import run_staged
        monkeypatch.setenv("HOBBES_TEST_PLANNER", planner)
        return run_staged(plan_repo, self.PROPOSAL, session_bin=staged_session,
                          sessions_root=tmp_path / "s", max_units=5, **kw)

    def _briefs(self, plan_repo):  # noqa: F811
        return {p.parent.name: p.read_text() for p in plan_repo.glob(".hobbes/plans/*/agents/U*/brief.md")}

    def test_covered_requirements_are_the_task_and_the_proposal_leaves_the_brief(self, plan_repo, staged_session, tmp_path, monkeypatch):  # noqa: F811
        rec = self._run(plan_repo, staged_session, tmp_path, monkeypatch, "covered")
        cov = rec["coverage"]
        assert cov["status"] == "covered" and cov["replanned"] is False and rec["brief_task"] == "requirements"
        assert [r["id"] for r in cov["requirements"]] == ["R1", "R2"]
        # R2 names no file; the plan is contained in the unit holding core.py
        assert cov["requirements"][1]["source"] == "contained"
        plan = next(s for s in rec["stages"] if s["stage"] == "plan")
        assert plan["requirements"] and plan["imperatives_unmentioned"] == []
        briefs = self._briefs(plan_repo)
        owner = next(b for b in briefs.values() if "## Your task" in b)
        assert "R1: handle retries the call — in src/app/core.py" in owner
        assert "R2: a failed retry raises, never returns None" in owner
        assert "## Proposal" not in owner and self.PROPOSAL not in owner.split("## Obligations")[0]
        assert "you own 2 of the plan's 2 requirement(s)" in owner
        # the verifier saw the requirement checklist
        vbrief = next(plan_repo.glob(".hobbes/plans/*/agents/verifier-1/brief.md")).read_text()
        assert "## Requirements the plan set out" in vbrief and "R2:" in vbrief
        assert rec["integration"]["merged"]

    def test_proposal_in_brief_keeps_the_old_shape_for_the_removal_test(self, plan_repo, staged_session, tmp_path, monkeypatch):  # noqa: F811
        rec = self._run(plan_repo, staged_session, tmp_path, monkeypatch, "covered", proposal_in_brief=True)
        assert rec["coverage"]["status"] == "covered" and rec["brief_task"] == "proposal"
        assert all("## Proposal" in b and "## Your task" not in b for b in self._briefs(plan_repo).values())

    def test_uncovered_replans_once_then_strict_stops_at_plan_cost(self, plan_repo, staged_session, tmp_path, monkeypatch):  # noqa: F811
        with pytest.raises(PlanCoverageError, match="R2: the CLI prints the retry count"):
            self._run(plan_repo, staged_session, tmp_path, monkeypatch, "uncovered")
        # two plan stages ran; the second planner's inbox named R2
        record = json.loads(next(plan_repo.glob(".hobbes/plans/*/partition-record.json")).read_text())
        assert record["error"] == "plan coverage failed" and record["units"] == []
        assert [s["agent"] for s in record["stages"] if s["stage"] == "plan"] == ["planner", "planner-2"]
        assert record["coverage"]["replanned"] is True
        second = next(plan_repo.glob(".hobbes/plans/*/agents/planner-2/brief.md")).read_text()
        assert "## From the orchestrator" in second and "R2: the CLI prints the retry count" in second
        assert "does/not/exist.py — not found" in second
        # no implementer was ever spawned
        assert not list(plan_repo.glob(".hobbes/plans/*/agents/U*/brief.md"))

    def test_the_replan_can_recover(self, plan_repo, staged_session, tmp_path, monkeypatch):  # noqa: F811
        rec = self._run(plan_repo, staged_session, tmp_path, monkeypatch, "retry")
        assert rec["coverage"]["status"] == "covered" and rec["coverage"]["replanned"] is True
        assert rec["brief_task"] == "requirements" and rec["integration"]["merged"]

    def test_assign_mode_runs_with_the_leftover_on_the_seed_unit(self, plan_repo, staged_session, tmp_path, monkeypatch):  # noqa: F811
        rec = self._run(plan_repo, staged_session, tmp_path, monkeypatch, "uncovered", coverage_mode="assign")
        cov = rec["coverage"]
        assert cov["status"] == "assigned" and cov["replanned"] is True
        assigned = next(r for r in cov["requirements"] if r["id"] == "R2")
        assert assigned["source"] == "assigned" and assigned["units"] == [cov["seed_unit"]]
        owner = next(b for b in self._briefs(plan_repo).values() if "## Your task" in b)
        assert "R2: the CLI prints the retry count" in owner and "C-57" in owner
        assert rec["integration"]["merged"]

    def test_no_requirements_is_a_strict_plan_error_and_the_old_brief_under_assign(self, plan_repo, staged_session, tmp_path, monkeypatch):  # noqa: F811
        with pytest.raises(PlanCoverageError, match="stated no requirements"):
            self._run(plan_repo, staged_session, tmp_path, monkeypatch, "none")
        rec = self._run(plan_repo, staged_session, tmp_path, monkeypatch, "none", coverage_mode="assign")
        assert rec["coverage"]["status"] == "no-requirements" and rec["brief_task"] == "proposal"
        assert all("## Proposal" in b for b in self._briefs(plan_repo).values())

    def _rambling_planner(self, monkeypatch, calls):
        from hobbes.run import stages

        def planner(*a, **k):
            calls.append(k)
            return {"session": f"x-planner-{k.get('attempt', 1)}", "exit": 0,
                    "handoff": stages.parse_handoff("files: does/not/exist.py"), "reflections": []}
        monkeypatch.setattr(stages, "run_planner", planner)

    def test_a_fallback_under_strict_replans_once_then_stops_at_plan_cost(self, plan_repo, staged_session, tmp_path, monkeypatch):  # noqa: F811
        # D5 (ADR-093): a planner that names nothing the graph resolves
        # used to drop to the lexical seeds and spawn implementers with no
        # coverage check inside a strict run. Now it gets the one re-plan
        # an uncovered handoff gets, then strict stops.
        calls: list[dict] = []
        self._rambling_planner(monkeypatch, calls)
        with pytest.raises(PlanCoverageError, match="named nothing the graph resolves.*does/not/exist.py"):
            self._run(plan_repo, staged_session, tmp_path, monkeypatch, "covered")
        assert [c["attempt"] for c in calls] == [1, 2]
        assert "does/not/exist.py — none found" in calls[1]["orchestrator_note"]
        record = json.loads(next(plan_repo.glob(".hobbes/plans/*/partition-record.json")).read_text())
        assert record["error"] == "plan coverage failed" and record["units"] == []
        assert record["seed_source"] == "lexical-fallback"
        assert record["coverage"]["status"] == "lexical-fallback"
        assert record["coverage"]["planner_unresolved"] == ["does/not/exist.py"]
        assert record["coverage"]["replanned"] is True
        assert not list(plan_repo.glob(".hobbes/plans/*/agents/U*/brief.md"))

    def test_a_fallback_under_assign_runs_on_the_lexical_seeds_and_says_so(self, plan_repo, staged_session, tmp_path, monkeypatch):  # noqa: F811
        calls: list[dict] = []
        self._rambling_planner(monkeypatch, calls)
        rec = self._run(plan_repo, staged_session, tmp_path, monkeypatch, "covered", coverage_mode="assign")
        assert [c["attempt"] for c in calls] == [1]  # assign keeps the old shape: no re-plan for a fallback
        assert rec["coverage"]["status"] == "lexical-fallback" and rec["brief_task"] == "proposal"
        assert rec["units"] and rec["integration"]["merged"]

    def test_the_replan_can_recover_from_a_fallback(self, plan_repo, staged_session, tmp_path, monkeypatch):  # noqa: F811
        from hobbes.run import stages
        real = stages.run_planner

        def planner(*a, **k):
            if k.get("attempt", 1) == 1:
                return {"session": "x-planner", "exit": 0,
                        "handoff": stages.parse_handoff("files: does/not/exist.py"), "reflections": []}
            return real(*a, **k)
        monkeypatch.setattr(stages, "run_planner", planner)
        rec = self._run(plan_repo, staged_session, tmp_path, monkeypatch, "covered")
        assert rec["seed_source"] == "planner" and rec["coverage"]["status"] == "covered"
        assert rec["coverage"]["replanned"] is True and rec["brief_task"] == "requirements"

    def test_dry_run_records_coverage_without_judging_it(self, plan_repo, staged_session, tmp_path, monkeypatch):  # noqa: F811
        rec = self._run(plan_repo, staged_session, tmp_path, monkeypatch, "uncovered", dry_run=True)
        assert rec["coverage"]["status"] in ("lexical-fallback", "no-requirements", "uncovered")

    def test_a_bad_mode_is_refused(self, plan_repo, staged_session, tmp_path, monkeypatch):  # noqa: F811
        from hobbes.run import RunError
        with pytest.raises(RunError, match="coverage mode"):
            self._run(plan_repo, staged_session, tmp_path, monkeypatch, "covered", coverage_mode="hope")
