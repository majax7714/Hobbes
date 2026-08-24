"""The execution half — `hobbes run` and the short-term channel (ADR-054).

Everything here is quota-free and podman-free: a stand-in session
binary plays the sandbox, writing the flight log, the mail, and a
harvested branch the way the real `hobbes-session` does, so the
orchestrator's reading of all three is tested against the shapes the
Go side writes.
"""

import json
import os
import stat
import subprocess

import pytest
import yaml

from hobbes import cli
from hobbes.derive import derive_plan, write_spec
from hobbes.run import agents, mail, orchestrate
from hobbes.run.roles import ROLE_POLICIES, ensure_role_policies
from hobbes.run.spec import SpecError, list_plans, load_spec, plan_dir, resolve_task
from tests.test_changespec import plan_repo  # noqa: F401 — fixture
from hobbes.run.spec import plan_dir


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture
def planned(plan_repo):  # noqa: F811
    """plan_repo with a two-unit change-spec written."""
    spec = derive_plan(plan_repo, "improve app.core handle", budget=100)
    write_spec(plan_repo, spec)
    return plan_repo, spec.task


#: A stand-in hobbes-session: records its argv, writes a flight log with
#: one knowledge call in scope and one fault, one exec allow, a
#: reflection, and harvests a branch with one commit that touches one
#: interior file and one file outside the manifest.
FAKE_SESSION = """\
#!/bin/sh
set -e
repo=""; session=""; sessions=""; agent=""; dry=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) repo="$2"; shift 2;;
    --session) session="$2"; shift 2;;
    --sessions) sessions="$2"; shift 2;;
    --agent-dir) agent="$2"; shift 2;;
    --task) shift 2;;
    --dry-run) dry=1; shift;;
    --commit-on-exit) echo "hobbes-session: committed 2 uncommitted file(s) at exit" >&2; shift;;
    *) shift;;
  esac
done
echo "$@" > /dev/null
mkdir -p "$sessions/$session"
printf '%s\\n' "$agent" > "$sessions/$session/argv.txt"
[ -n "$dry" ] && { echo "dry run"; exit 0; }
cat > "$sessions/$session/flight.jsonl" <<EOT
{"tool":"graph_neighborhood","argv":["app.core"],"decision":"allow"}
{"tool":"graph_neighborhood","argv":["billing"],"decision":"allow","context_fault":true}
{"tool":"exec","argv":["/bin/sh","-c","git status"],"decision":"allow"}
{"tool":"exec","argv":["/bin/sh","-c","git push"],"decision":"deny"}
{"tool":"reflect","argv":["done: handle retried"],"decision":"allow"}
EOT
cat > "$sessions/$session/mail.jsonl" <<EOT
{"seq":1,"session":"$session","role":"implementer","text":"done: handle retried"}
EOT
wt="$sessions/$session/worktree"
git clone -q --local --no-hardlinks "$repo" "$wt"
git -C "$wt" checkout -q -b "hobbes/$session"
echo "# changed" >> "$wt/src/app/core.py"
echo "stray" > "$wt/src/stray.py"
git -C "$wt" -c user.name=a -c user.email=a@a add -A
git -C "$wt" -c user.name=a -c user.email=a@a commit -qm "feat: retry handle"
git -C "$repo" fetch -q "$wt" "hobbes/$session:hobbes/$session"
rm -rf "$wt"
echo "harvested"
"""


@pytest.fixture
def fake_session(tmp_path):
    path = tmp_path / "hobbes-session"
    path.write_text(FAKE_SESSION)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


class TestSpec:
    def test_list_resolve_and_load(self, planned):
        repo, task = planned
        assert list_plans(repo) == [task]
        assert resolve_task(repo, task[:4]) == task
        assert load_spec(repo, task[:4])["task"] == task

    def test_unknown_and_ambiguous_are_errors(self, planned):
        repo, task = planned
        with pytest.raises(SpecError, match="no plan"):
            resolve_task(repo, "zzz")
        write_spec(repo, derive_plan(repo, "improve app.core"))
        with pytest.raises(SpecError, match="ambiguous"):
            resolve_task(repo, "")


class TestRoles:
    def test_scaffolds_missing_and_never_overwrites(self, plan_repo):  # noqa: F811
        assert sorted(ensure_role_policies(plan_repo)) == sorted(ROLE_POLICIES)
        path = plan_repo / ".hobbes/policies/roles/implementer.policy"
        path.write_text("version: 1\nscope: role\nrules: []\n")
        assert ensure_role_policies(plan_repo) == []
        assert path.read_text() == "version: 1\nscope: role\nrules: []\n"

    def test_every_role_policy_declares_role_scope(self):
        for role, text in ROLE_POLICIES.items():
            doc = yaml.safe_load(text)
            assert doc["scope"] == "role", role
            assert doc["version"] == 1


class TestMail:
    def test_post_read_and_fold_back(self, tmp_path):
        inbox = tmp_path / "U1"
        first = mail.post(inbox, "orchestrator", "what does handle return?")
        second = mail.post(inbox, "human", "use the existing retry helper", kind="reply")
        assert (first["seq"], second["seq"]) == (1, 2)
        assert [m["from"] for m in mail.read(inbox)] == ["orchestrator", "human"]
        session = tmp_path / "sess"
        session.mkdir()
        (session / "mail.jsonl").write_text('{"seq":1,"text":"blocked on K1"}\n')
        orchestrator = tmp_path / "orchestrator"
        assert mail.fold_back(orchestrator, "U1", mail.reflections(session)) == 1
        folded = mail.read(orchestrator)[0]
        assert folded["from"] == "U1" and folded["kind"] == "handoff"
        assert mail.reflections(tmp_path / "nowhere") == []

    def test_only_the_handoff_is_forwarded(self, tmp_path):
        # The first live 7B run reflected 123 progress lines from one unit;
        # short memory is the handoff, the record keeps the rest.
        session = tmp_path / "sess"
        session.mkdir()
        lines = [{"seq": i, "kind": "progress", "text": f"step {i}"} for i in range(1, 6)]
        lines.insert(3, {"seq": 99, "kind": "handoff", "text": "changed core; tests unrun"})
        (session / "mail.jsonl").write_text("".join(json.dumps(l) + "\n" for l in lines))
        orchestrator = tmp_path / "orchestrator"
        assert mail.fold_back(orchestrator, "U1", mail.reflections(session)) == 1
        [folded] = mail.read(orchestrator)
        assert folded["text"] == "changed core; tests unrun (5 earlier reflection(s) not forwarded)"
        # no handoff marked: the last reflection stands in, and says what was dropped
        chosen, dropped = mail.handoff(lines[:3])
        assert chosen["text"] == "step 3" and dropped == 2
        assert mail.handoff([]) == (None, 0)
        assert mail.fold_back(orchestrator, "U2", []) == 0


class TestAgents:
    def test_materialize_writes_policy_context_and_inbox(self, planned):
        repo, task = planned
        spec = load_spec(repo, task)
        tests = json.loads((repo / ".hobbes/derived/tests.json").read_text())
        dirs = agents.materialize(plan_dir(repo, task), spec, tests)
        assert set(dirs) == {u["name"] for u in spec["units"]}
        for unit, directory in dirs.items():
            policy = yaml.safe_load((directory / "policy.yaml").read_text())
            assert policy["scope"] == "agent" and policy["default"] == "escalate"
            # The guarantees come first, as denies (P10).
            assert [r["decision"] for r in policy["rules"][:3]] == ["deny"] * 3
            assert policy["rules"][1]["pattern"] == "git push*"
            context = json.loads((directory / "context.json").read_text())
            assert context["unit"] == unit
            assert context["interior"] and context["paths"]
            text = (directory / "context.md").read_text()
            assert "What Hobbes cannot see here" in text
            assert "C-38" in text
            assert (directory / mail.INBOX).is_file()
        assert (agents.agent_dir(plan_dir(repo, task), "orchestrator") / mail.INBOX).is_file()

    def test_guarding_tests_become_allow_rules(self, planned):
        repo, task = planned
        spec = load_spec(repo, task)
        tests = json.loads((repo / ".hobbes/derived/tests.json").read_text())
        guarded = next(c for c in spec["contexts"] if c["guarding_tests"])
        policy = agents.build_policy(spec, guarded["unit"],
                                     {t["id"]: t["file"] for t in tests["tests"]})
        allows = [r for r in policy["rules"] if r["decision"] == "allow"]
        assert allows and allows[0]["pattern"].startswith("uv run pytest tests/")

    def test_human_first_denies_every_write(self, planned):
        repo, task = planned
        spec = load_spec(repo, task)
        spec["contexts"][0]["human_first"] = True
        spec["contexts"][0]["human_first_reason"] = "blind"
        policy = agents.build_policy(spec, spec["contexts"][0]["unit"], {})
        denied = {r["pattern"] for r in policy["rules"] if r["decision"] == "deny"}
        assert {"git commit*", "git add *"} <= denied
        # C-53: a benchmark that runs alone may spawn it with its write scope kept
        spawned = agents.build_policy(spec, spec["contexts"][0]["unit"], {}, human_first="spawn")
        assert not {"git commit*", "git add *"} & {r["pattern"] for r in spawned["rules"] if r["decision"] == "deny"}

    def test_boundary_is_the_far_side_of_each_contract(self, planned):
        repo, task = planned
        spec = load_spec(repo, task)
        for unit in spec["units"]:
            context = agents.build_context_json(spec, unit["name"])
            assert not set(context["boundary"]) & set(context["interior"])
        if spec["contracts"]:
            c = spec["contracts"][0]
            consumer = c["from_unit"] if c["owner"] == c["to_unit"] else c["to_unit"]
            far = agents.build_context_json(spec, consumer)["boundary"]
            assert far, "a consumer's boundary names the owner's declaration"

    def test_interior_renders_paths_first_and_names_pathless_modules(self, planned):
        # The first live run's model created a file literally named
        # `.:conftest` — the module id had been rendered before the path.
        repo, task = planned
        spec = load_spec(repo, task)
        unit = spec["units"][0]["name"]
        context = next(c for c in spec["contexts"] if c["unit"] == unit)
        context["modules"] = [{"id": ".:conftest", "path": "conftest.py"}, {"id": "ghost", "path": None}]
        text = agents.render_context(spec, unit)
        assert "- conftest.py (module `.:conftest`)" in text
        assert "- module `ghost` — no file path: not a file you can edit" in text
        assert "- `.:conftest` —" not in text

    def test_brief_carries_both_horizons_and_obligations(self, planned):
        repo, task = planned
        spec = load_spec(repo, task)
        unit = spec["units"][0]["name"]
        brief = agents.render_brief(spec, unit, "implementer",
                                    [{"seq": 1, "from": "orchestrator", "kind": "request",
                                      "text": "report the return type of handle"}], "s1")
        assert "single-use implementer" in brief
        assert "report the return type of handle" in brief
        assert "reflect" in brief and "hobbes/s1" in brief
        assert "Standing context" in brief and "What Hobbes cannot see" in brief
        empty = agents.render_brief(spec, unit, "implementer", [], "s1")
        assert "inbox" in empty and "empty" in empty


class TestOrder:
    def test_owner_before_consumer(self):
        spec = {"units": [{"name": "U1"}, {"name": "U2"}, {"name": "U3"}],
                "contracts": [{"from_unit": "U1", "to_unit": "U3", "owner": "U3"},
                              {"from_unit": "U2", "to_unit": "U1", "owner": "U1"}]}
        assert orchestrate.order_units(spec) == ["U3", "U1", "U2"]

    def test_a_cycle_falls_back_to_name_order(self):
        spec = {"units": [{"name": "U2"}, {"name": "U1"}],
                "contracts": [{"from_unit": "U1", "to_unit": "U2", "owner": "U2"},
                              {"from_unit": "U2", "to_unit": "U1", "owner": "U1"}]}
        assert orchestrate.order_units(spec) == ["U1", "U2"]


class TestRun:
    def test_dry_run_writes_agents_briefs_and_record_without_spawning(self, planned, tmp_path):
        repo, task = planned
        record = orchestrate.run_task(repo, task, dry_run=True, session_bin=None,
                                      sessions_root=tmp_path / "sessions")
        assert all(not u["spawned"] for u in record["units"])
        assert record["integration"] == {"skipped": "dry run"}
        pdir = plan_dir(repo, task)
        assert (pdir / orchestrate.RECORD).is_file()
        for unit in record["order"]:
            d = agents.agent_dir(pdir, unit)
            assert (d / "brief.md").is_file() and (d / "spawn.txt").is_file()
            assert "--agent-dir" in (d / "spawn.txt").read_text()
        assert (repo / ".hobbes/policies/roles/implementer.policy").is_file()
        assert "re-ingest" in record["standing_context"]

    def test_full_loop_reads_flight_mail_and_branch(self, planned, fake_session, tmp_path):
        repo, task = planned
        sessions = tmp_path / "sessions"
        record = orchestrate.run_task(repo, task, session_bin=fake_session, sessions_root=sessions)
        units = {u["unit"]: u for u in record["units"]}
        for unit, u in units.items():
            assert u["spawned"] and u["exit"] == 0
            assert u["knowledge_calls"] == 2 and u["context_faults"] == 1
            assert u["exec"] == {"allow": 1, "deny": 1, "escalate": 0}
            assert u["reflections"] == ["done: handle retried"]
            assert u["commits"] == 1
            assert "src/stray.py" in u["rework_files"]
            # the agent dir reached the session binary
            assert (sessions / u["session"] / "argv.txt").read_text().strip().endswith(unit)
        # reflections folded into the orchestrator's inbox
        inbox = mail.read(agents.agent_dir(plan_dir(repo, task), "orchestrator"))
        assert [m["kind"] for m in inbox].count("handoff") == len(units)
        # integration: the first branch merges; the second touches the same
        # lines and conflicts — recorded at the cut, never guessed
        integ = record["integration"]
        assert integ["branch"] == f"hobbes/{task}"
        assert len(integ["merged"]) + len(integ["failed"]) == len(units)
        assert git(repo, "rev-parse", "--verify", integ["branch"])
        assert "contract_failures" in record["loss"]["terms"]
        assert record["loss"]["unobserved"] == ["tokens", "wall_time"]
        assert record["loss"]["value"] > 0  # rework alone makes it positive
        # the human's checkout was never touched
        assert [l for l in git(repo, "status", "--porcelain").splitlines()
                if not l.endswith(".hobbes/")] == []

    def test_human_first_unit_is_not_spawned(self, planned, fake_session, tmp_path):
        repo, task = planned
        path = plan_dir(repo, task) / "change-spec.yaml"
        spec = yaml.safe_load(path.read_text())
        spec["contexts"][0]["human_first"] = True
        spec["contexts"][0]["human_first_reason"] = "blind scope"
        path.write_text(yaml.safe_dump(spec, sort_keys=False))
        flagged = spec["contexts"][0]["unit"]
        record = orchestrate.run_task(repo, task, session_bin=fake_session,
                                      sessions_root=tmp_path / "sessions", only_units=[flagged])
        (u,) = record["units"]
        assert not u["spawned"] and u["reason"].startswith("human-first")
        notices = [m for m in mail.read(agents.agent_dir(plan_dir(repo, task), "orchestrator"))
                   if m["kind"] == "human-first"]
        assert notices and notices[0]["from"] == flagged

    def test_stale_plan_warns_in_the_orchestrator_inbox(self, planned, tmp_path):
        repo, task = planned
        (repo / "src/app/auth.py").write_text("def token():\n    return 2\n")
        git(repo, "commit", "-qam", "two")
        orchestrate.run_task(repo, task, dry_run=True, session_bin=None,
                             sessions_root=tmp_path / "sessions")
        inbox = mail.read(agents.agent_dir(plan_dir(repo, task), "orchestrator"))
        assert any(m["kind"] == "warning" and "stale" in m["text"] for m in inbox)

    def test_no_session_binary_is_an_error_unless_dry(self, planned, tmp_path, monkeypatch):
        repo, task = planned
        monkeypatch.delenv("HOBBES_SESSION_BIN", raising=False)
        monkeypatch.setattr("shutil.which", lambda _name: None)
        with pytest.raises(orchestrate.RunError, match="hobbes-session not found"):
            orchestrate.run_task(repo, task, sessions_root=tmp_path / "s")


class TestCLI:
    def test_run_dry_and_mail_round_trip(self, planned, tmp_path, capsys):
        repo, task = planned
        assert cli.main(["mail", "post", task[:4], "U1", "check the retry helper first",
                         "--repo", str(repo)]) == 0
        assert cli.main(["mail", "read", task, "U1", "--repo", str(repo)]) == 0
        assert "check the retry helper first" in capsys.readouterr().out
        code = cli.main(["run", task, "--dry-run", "--sessions", str(tmp_path / "s"),
                         "--repo", str(repo)])
        out = capsys.readouterr().out
        assert code == 0
        assert f"run {task}" in out and "loss (declared weights, C-35)" in out
        brief = (agents.agent_dir(plan_dir(repo, task), "U1") / "brief.md").read_text()
        assert "check the retry helper first" in brief

    def test_unknown_task_is_2(self, plan_repo, capsys):  # noqa: F811
        assert cli.main(["run", "nope", "--dry-run", "--repo", str(plan_repo)]) == 2
        assert "no plan" in capsys.readouterr().err

    def test_full_loop_exit_reflects_integration(self, planned, fake_session, tmp_path, capsys):
        repo, task = planned
        code = cli.main(["run", task, "--session-bin", fake_session,
                         "--sessions", str(tmp_path / "s"), "--repo", str(repo), "--json"])
        record = json.loads(capsys.readouterr().out)
        expected = 1 if (record["integration"]["failed"] or record["review"].get("needs_attention")) else 0
        assert code == expected


class TestBriefLimit:
    """ADR-058/C-45: a brief is held to the model's window, protected
    sections intact, every cut stated; and it travels as a file."""

    def test_limit_context_cuts_unprotected_sections_and_says_so(self):
        from hobbes.run.agents import limit_context
        big = "\n".join(f"line {i}" for i in range(2000))
        doc = ("# Standing context — unit U1\n\nintro\n\n"
               "## Interior (full resolution — yours to change)\n- src/a.py\n"
               f"## Guarding tests (run these)\n{big}\n"
               "## Invariants in scope (breaking one is a review failure)\n- I-1\n"
               "## Contracts at your boundary (the only interface to other units)\n- c1\n"
               f"## Neighborhood (one hop out)\n{big}\n"
               "## What Hobbes cannot see here (read this before trusting the rest)\n- complement\n"
               f"## Module docs (pinned claims)\n{big}\n"
               "## Derived policy (advisory at path grain)\n- deny: x\n")
        out, dropped = limit_context(doc, 6000)
        assert dropped > 0 and len(out) <= 6000
        for kept in ("- complement", "- deny: x", "- c1", "- I-1", "- src/a.py", "## Neighborhood"):
            assert kept in out
        assert out.count("… cut:") == 3 and "C-45" in out
        same, none = limit_context(doc, len(doc) + 1)
        assert same == doc and none == 0

    @staticmethod
    def _inflate(monkeypatch):
        """The fixture's context is tiny; give its neighborhood 3,000
        lines (the interior is never cut — ADR-062)."""
        real = agents.render_context

        def big(spec, unit):
            doc = real(spec, unit)
            pad = "\n".join(f"    # neighbour line {i}" for i in range(3000))
            return doc.replace("## What Hobbes cannot see", pad + "\n## What Hobbes cannot see", 1)
        monkeypatch.setattr(agents, "render_context", big)

    def test_limit_never_cuts_the_interior(self):
        from hobbes.run.agents import limit_context
        interior = "\n".join(f"- src/pkg/mod{i}.py (module `pkg.mod{i}`)" for i in range(300))
        doc = ("# Standing context — unit U1\n\n## Interior (full resolution)\n" + interior +
               "\n\n## Guarding tests\n" + "\n".join(f"- t{i}" for i in range(300)) +
               "\n\n## Neighborhood\n" + "\n".join(f"- `n{i}`: a, b" for i in range(300)) +
               "\n\n## What Hobbes cannot see here\n- x\n")
        out, dropped = limit_context(doc, len(doc) // 3)
        assert dropped > 0
        assert "src/pkg/mod299.py" in out  # every interior path survives (ADR-062)
        assert "## Guarding tests" in out and "… cut:" in out

    def test_planner_note_projects_onto_the_unit(self):
        from hobbes.run.stages import _planner_note, planner_slice
        plan = {"stage": "plan", "files": ["pkg/a.py", "./pkg/b.py", "pkg/new_file.py"], "symbols": ["pkg.c.run"],
                "terms": {"pkg/a.py": "pkg.a", "pkg/b.py": "pkg.b", "pkg/new_file.py": None, "pkg.c.run": "pkg.c"},
                "approach": "move the helper", "handoff": "files: …", "tests": ["tests/test_a.py"]}
        owner = {"unit": "U1", "modules": [{"id": "pkg.a", "path": "pkg/a.py"}, {"id": "pkg.x", "path": "pkg/x.py"}]}
        other = {"unit": "U2", "modules": [{"id": "pkg.z", "path": "pkg/z.py"}]}
        assert planner_slice(plan, owner) == (["pkg/a.py"], ["./pkg/b.py", "pkg/new_file.py", "pkg.c.run"])
        note = _planner_note("planner", [plan], owner)
        assert note.startswith("planner: your slice of the change — the planner named these IN YOUR INTERIOR: pkg/a.py.")
        assert "approach: move the helper" in note and "3 location(s) owned by other units" in note
        assert note.endswith("run these tests: tests/test_a.py")
        none = _planner_note("planner", [plan], other)
        assert none.startswith("planner: nothing the planner named lies in your interior. It named: pkg/a.py, ./pkg/b.py")
        assert "approach: move the helper" in none and "owned by other units (" not in none
        # a path-shaped term the graph could not resolve still lands by suffix
        newfile = {"unit": "U3", "modules": [{"id": "pkg.new_file", "path": "src/pkg/new_file.py"}]}
        assert planner_slice(plan, newfile)[0] == ["pkg/new_file.py"]
        # the fallback seed source carries no planner note at all
        assert _planner_note("lexical-fallback", [plan], owner) == ""
        # and without a unit the old whole-handoff shape still stands
        assert _planner_note("planner", [plan], None).startswith("planner: files: …")

    def test_render_brief_limit_is_visible_at_the_top(self, planned, monkeypatch):
        self._inflate(monkeypatch)
        repo, task = planned
        spec = load_spec(repo, task)
        unit = spec["units"][0]["name"]
        full = agents.render_brief(spec, unit, "implementer", [], "s1")
        cut = agents.render_brief(spec, unit, "implementer", [], "s1", limit=len(full) // 2)
        assert len(cut) <= len(full) // 2
        assert "(standing context cut by" in cut.splitlines()[1] and "C-45" in cut
        assert "## What Hobbes cannot see" in cut and "## Obligations" in cut and "… cut:" in cut
        assert "## What Hobbes cannot see" in cut and "## Obligations" in cut

    def test_run_passes_the_brief_as_a_file_and_records_the_cut(self, planned, fake_session, tmp_path, monkeypatch):
        self._inflate(monkeypatch)
        repo, task = planned
        record = orchestrate.run_task(repo, task, session_bin=fake_session, sessions_root=tmp_path / "s",
                                      brief_limit=6000)
        unit = record["units"][0]
        assert unit["brief_chars"] <= 6000 and unit["brief_cut"] > 0
        spawn = (repo / ".hobbes" / "plans" / task / "agents" / unit["unit"] / "spawn.txt").read_text()
        assert "--task-file" in spawn and "--task " not in spawn


class TestCommitOnExit:
    def test_the_wrappers_exit_commit_is_counted_per_unit(self, planned, fake_session, tmp_path):
        repo, task = planned
        record = orchestrate.run_task(repo, task, session_bin=fake_session, sessions_root=tmp_path / "s",
                                      extra_args=["--commit-on-exit"])
        assert record["units"][0]["exit_commit_files"] == 2
        plain = orchestrate.run_task(repo, task, session_bin=fake_session, sessions_root=tmp_path / "s2")
        assert plain["units"][0]["exit_commit_files"] == 0


#: A role-aware stand-in session for the staged flow (ADR-059): the
#: planner hands off a real file, an implementer edits its unit's first
#: interior path and commits, the verifier hands off pass. It writes the
#: same shapes (mail.jsonl, a harvested branch) the Go side writes.
STAGED_SESSION = """\
#!/bin/sh
set -e
repo=""; role=""; session=""; sessions=""; agent=""; ref=""; dry=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) repo="$2"; shift 2;;
    --role) role="$2"; shift 2;;
    --session) session="$2"; shift 2;;
    --sessions) sessions="$2"; shift 2;;
    --agent-dir) agent="$2"; shift 2;;
    --ref) ref="$2"; shift 2;;
    --task-file) shift 2;;
    --dry-run) dry=1; shift;;
    *) shift;;
  esac
done
mkdir -p "$sessions/$session"
[ -n "$dry" ] && { echo "dry run"; exit 0; }
handoff() { printf '{"seq":1,"session":"%s","role":"%s","kind":"handoff","text":%s}\\n' "$session" "$role" "$1" > "$sessions/$session/mail.jsonl"; }
case "$role" in
  planner)
    # ADR-085: the planner hands off requirements with owners. The
    # shape is driven by HOBBES_TEST_PLANNER: covered (default),
    # uncovered (R2 names a file no unit holds), none (the pre-085
    # handoff), retry (uncovered first, covered on the re-plan).
    mode="${HOBBES_TEST_PLANNER:-covered}"
    case "$session" in *-planner-2) second=1;; *) second="";; esac
    if [ "$mode" = retry ] && [ -n "$second" ]; then mode=covered; fi
    if [ "$mode" = retry ]; then mode=uncovered; fi
    case "$mode" in
      none) handoff '"files: src/app/core.py\\ntests: tests/test_api.py\\napproach: fix handle"';;
      uncovered) handoff '"requirements:\\n- R1: handle retries the call -> src/app/core.py\\n- R2: the CLI prints the retry count -> does/not/exist.py\\nfiles: src/app/core.py\\ntests: tests/test_api.py\\napproach: fix handle"';;
      *) handoff '"requirements:\\n- R1: handle retries the call -> src/app/core.py\\n- R2: a failed retry raises, never returns None\\nfiles: src/app/core.py\\ntests: tests/test_api.py\\napproach: fix handle"';;
    esac;;
  reviewer) handoff '"verdict: approve"';;
  verifier) handoff "\\"verdict: ${HOBBES_TEST_VERDICT:-pass}\\"";;
  *)
    path=$(python3 -c "import json,sys; print((json.load(open('$agent/context.json')).get('paths') or [''])[0])")
    wt="$sessions/$session/worktree"
    rm -rf "$wt"; git clone -q --local --no-hardlinks "$repo" "$wt"
    br="hobbes/$session"
    if [ -n "$ref" ]; then git -C "$wt" checkout -q -b "$br" "$ref"; else git -C "$wt" checkout -q -b "$br"; fi
    [ -n "$path" ] && printf '\\n# %s edit\\n' "$session" >> "$wt/$path"
    git -C "$wt" -c user.name=a -c user.email=a@a add -A
    git -C "$wt" -c user.name=a -c user.email=a@a commit -qm "feat: $session" || true
    git -C "$repo" fetch -q "$wt" "$br:$br" || true
    rm -rf "$wt"
    handoff '"changed the unit"'
  ;;
esac
echo "session $role done"
"""


@pytest.fixture
def staged_session(tmp_path):
    path = tmp_path / "hobbes-session-staged"
    path.write_text(STAGED_SESSION)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


class TestStagedRun:
    def _proposal(self):
        return "improve app.core handle retry"

    def test_aided_mode_is_one_free_implementer_not_a_partition(self, plan_repo, staged_session, tmp_path):  # noqa: F811
        # ADR-077: implement_mode="aided" spawns ONE implementer on the
        # planner's task, free on the whole worktree — no partition units,
        # the whole diff integrated, and a brief that says so.
        from hobbes.run.stages import run_staged
        rec = run_staged(plan_repo, self._proposal(), session_bin=staged_session,
                         sessions_root=tmp_path / "s", implement_mode="aided")
        assert rec["implement_mode"] == "aided"
        assert [u["unit"] for u in rec["units"]] == ["impl"]
        assert rec["units"][0]["spawned"] and rec["integration"]["merged"] == ["impl"]
        assert rec["contracts"] == 0 and rec["units_not_selected"] == []
        # the brief carries the aid-not-boundary framing and no write-scope fence
        brief = (plan_dir(plan_repo, rec["task"]) / "agents" / "impl" / "brief.md").read_text()
        assert "an aid, not a boundary" in brief
        assert "edit ANY file" in brief and "write scope" not in brief

    def test_planner_seeds_drive_the_plan_and_units_are_implemented(self, plan_repo, staged_session, tmp_path):  # noqa: F811
        from hobbes.run.stages import run_staged
        rec = run_staged(plan_repo, self._proposal(), session_bin=staged_session,
                         sessions_root=tmp_path / "s", max_units=5)
        assert rec["seed_source"] == "planner"
        # the planner's handoff is a stage, its resolved seed is app.core
        plan = next(s for s in rec["stages"] if s["stage"] == "plan")
        assert "app.core" in plan["resolved"] and plan["unresolved"] == []
        # and the planner's seeds REPLACE the lexical ones: the proposal's
        # own words ("handle", "retry") seed nothing on the planner path
        assert set(rec["seeds"]) == set(plan["resolved"]), rec["seeds"]
        # every implementer's inbox carried the planner note
        assert any(u["spawned"] for u in rec["units"])
        assert rec["integration"]["merged"]
        # the integration branch really advanced past base (phase 3 found
        # it pinned at base: branch -f ran in the repo, not the worktree)
        diff = subprocess.run(["git", "-C", str(plan_repo), "diff", "--stat", rec["base"], rec["integration"]["branch"]],
                              capture_output=True, text=True).stdout
        assert "file changed" in diff
        # every stage has a wall time; implementers appear as stages too
        assert all(s["wall_seconds"] is not None for s in rec["stages"])
        assert [s["stage"] for s in rec["stages"]][0] == "plan" and "implement" in [s["stage"] for s in rec["stages"]]
        assert "wall_time" not in rec["loss"]["unobserved"] and rec["loss"]["terms"]["wall_seconds"] > 0
        # the verifier ran and passed
        verify = rec["verify"]
        assert verify["verdict"] == "pass" and verify["verdict_source"] == "keyed"

    def test_unit_selection_keeps_named_units_and_drops_the_rest(self):
        # ADR-064: the decision, isolated from the partition. A unit with
        # a planner-named file in its interior is kept; one with none is
        # dropped; a path-suffix match (an unresolvable named file) keeps
        # its owner.
        from hobbes.run.stages import unit_has_planner_work
        plan = {"stage": "plan", "files": ["pkg/a.py", "pkg/new.py"], "symbols": [],
                "terms": {"pkg/a.py": "pkg.a", "pkg/new.py": None}}
        owner = {"unit": "U1", "modules": [{"id": "pkg.a", "path": "pkg/a.py"}]}
        newfile = {"unit": "U2", "modules": [{"id": "pkg.new", "path": "src/pkg/new.py"}]}
        bystander = {"unit": "U3", "modules": [{"id": "pkg.z", "path": "pkg/z.py"}]}
        assert unit_has_planner_work(plan, owner) is True
        assert unit_has_planner_work(plan, newfile) is True     # suffix match on the unresolved name
        assert unit_has_planner_work(plan, bystander) is False

    def test_a_planner_seeded_run_records_selection_and_spawns_the_owner(self, plan_repo, staged_session, tmp_path):  # noqa: F811
        # On this single-unit fixture the owner has the named file, so it
        # is kept and nothing is skipped — the wiring is present and the
        # selection list exists.
        from hobbes.run.stages import run_staged
        rec = run_staged(plan_repo, self._proposal(), session_bin=staged_session,
                         sessions_root=tmp_path / "s", max_units=5)
        assert rec["seed_source"] == "planner"
        assert isinstance(rec["units_not_selected"], list)
        assert [u["unit"] for u in rec["units"] if u["spawned"]]  # the owner ran
        assert rec["units_not_selected"] == []                   # it held the named file
        assert rec["integration"]["merged"]

    def test_the_planner_handoff_is_projected_per_unit(self, plan_repo, staged_session, tmp_path):  # noqa: F811
        # ADR-062: the unit whose interior holds the planner's file is told
        # it is ITS slice; every other unit is told plainly that nothing
        # the planner named is in its interior — no unit is handed the
        # global list as if it were its own job.
        from hobbes.run.stages import run_staged
        rec = run_staged(plan_repo, self._proposal(), session_bin=staged_session,
                         sessions_root=tmp_path / "s", max_units=5)
        plan = next(s for s in rec["stages"] if s["stage"] == "plan")
        assert plan["terms"] == {"src/app/core.py": "app.core"}
        briefs = {p.parent.name: p.read_text() for p in plan_repo.glob(".hobbes/plans/*/agents/U*/brief.md")}
        owners = [u for u, b in briefs.items() if "IN YOUR INTERIOR: src/app/core.py" in b]
        assert len(owners) == 1, briefs.keys()
        for unit, brief in briefs.items():
            if unit != owners[0]:
                assert "nothing the planner named lies in your interior" in brief
                assert "IN YOUR INTERIOR" not in brief
        assert len({b.split("## Short-term context")[1].split("#")[0] for b in briefs.values()}) == len(briefs) or len(briefs) == 1

    def test_lexical_fallback_when_the_planner_names_nothing_real(self, plan_repo, staged_session, tmp_path, monkeypatch):  # noqa: F811
        # a planner that resolves nothing → the deterministic seeds stand,
        # recorded as the fallback, never a failed run
        from hobbes.run import stages
        monkeypatch.setattr(stages, "run_planner", lambda *a, **k: {
            "session": "x-planner", "exit": 0,
            "handoff": stages.parse_handoff("files: does/not/exist.py"), "reflections": []})
        rec = stages.run_staged(plan_repo, self._proposal(), session_bin=staged_session,
                                sessions_root=tmp_path / "s", max_units=5)
        assert rec["seed_source"] == "lexical-fallback"
        assert rec["planner_unresolved"] == ["does/not/exist.py"]
        assert rec["units"]  # still planned and ran on the lexical seeds

    def test_rework_runs_when_the_verifier_fails(self, plan_repo, staged_session, tmp_path, monkeypatch):  # noqa: F811
        from hobbes.run import stages
        monkeypatch.setenv("HOBBES_TEST_VERDICT", "fail")
        rec = stages.run_staged(plan_repo, self._proposal(), session_bin=staged_session,
                                sessions_root=tmp_path / "s", max_units=5,
                                stages=("plan", "implement", "verify", "rework"), max_rework=1)
        assert rec["rework"] == 1
        # a fail then one rework then a second verify — two verify stages
        assert len([s for s in rec["stages"] if s["stage"] == "verify"]) == 2

    def test_a_second_run_of_the_same_proposal_clears_stale_session_dirs(self, plan_repo, staged_session, tmp_path):  # noqa: F811
        # session names are deterministic; the full-stage probe's U3 died
        # on "worktree already exists" from the planner-only probe
        from hobbes.run.stages import run_staged
        first = run_staged(plan_repo, self._proposal(), session_bin=staged_session,
                           sessions_root=tmp_path / "s", max_units=5)
        unit = next(u for u in first["units"] if u["spawned"])
        (tmp_path / "s" / unit["session"] / "worktree").mkdir(parents=True, exist_ok=True)
        (tmp_path / "s" / unit["session"] / "worktree" / "stale").write_text("x")
        second = run_staged(plan_repo, self._proposal(), session_bin=staged_session,
                            sessions_root=tmp_path / "s", max_units=5)
        assert all(u["exit"] == 0 for u in second["units"] if u["spawned"])

    def test_out_of_scope_writes_are_dropped_at_integration(self, plan_repo, tmp_path):  # noqa: F811
        # the astropy probe finding: units edited files outside their
        # interior (a neighbour's source, a session_commit.txt scratch
        # note) and the whole branch was merged, so the clobber + leak
        # landed in the patch. C-38 is now enforced at the cut.
        from hobbes.run.stages import run_staged
        import stat as _stat, subprocess as _sp
        script = tmp_path / "hobbes-session-scope"
        script.write_text(STAGED_SESSION.replace(
            '[ -n "$path" ] && printf \'\\n# %s edit\\n\' "$session" >> "$wt/$path"',
            '[ -n "$path" ] && printf \'\\n# %s edit\\n\' "$session" >> "$wt/$path"\n'
            '    printf \'scratch\' > "$wt/session_commit.txt"\n'
            '    printf \'x\' > "$wt/src/billing.py"'))  # billing.py is another unit\'s interior
        script.chmod(script.stat().st_mode | _stat.S_IEXEC)
        rec = run_staged(plan_repo, self._proposal(), session_bin=str(script),
                         sessions_root=tmp_path / "s", max_units=5)
        branch = rec["integration"]["branch"]
        names = _sp.run(["git", "-C", str(plan_repo), "diff", "--name-only", rec["base"], branch],
                        capture_output=True, text=True).stdout
        # the scratch note and the neighbour's file never entered the patch
        assert "session_commit.txt" not in names
        # each unit contributed only its own interior; nothing was clobbered
        dropped = rec["integration"].get("dropped", {})
        assert any("session_commit.txt" in d for d in dropped.values()), dropped
        # the in-scope edits are still there
        assert names.strip()

    def test_dry_run_spawns_nothing(self, plan_repo, tmp_path):  # noqa: F811


        from hobbes.run.stages import run_staged
        rec = run_staged(plan_repo, self._proposal(), session_bin=None,
                         sessions_root=tmp_path / "s", max_units=5, dry_run=True)
        assert rec["seed_source"] in ("planner", "lexical-fallback")
        assert all(not u["spawned"] for u in rec["units"])


class TestHandoffParsing:
    def test_keyed_lists_backticks_and_json(self):
        from hobbes.run.handoff import parse_handoff
        keyed = parse_handoff("\n".join(["files: a.py, `b/c.py`", "symbols: Foo", "tests: t.py"]))
        assert keyed["files"] == ["a.py", "b/c.py"] and keyed["symbols"] == ["Foo"]
        js = parse_handoff('{"files": ["x.py"], "verdict": "PASS"}')
        assert js["files"] == ["x.py"] and js["verdict"] == "pass" and js["verdict_source"] == "keyed"

    def test_prose_headings_name_their_fields(self):
        # the first live 7B planner's handoff, verbatim (astropy-13398):
        # it named a gold file, and the strict key parse read files: []
        from hobbes.run.handoff import parse_handoff
        text = ("Handoff: The proposed changes touch the following files:\n\n"
                "- astropy/coordinates/builtin_frames/altaz.py\n"
                "- astropy/coordinates/builtin_frames/hadec.py\n"
                "- astropy/coordinates/builtin_frames/itrs.py\n"
                "- astropy/coordinates/transformations.py\n\n"
                "Symbols to change: None\n\n"
                "Tests guarding this behavior: test_intermediate_transformations.py\n\n"
                "Approach: Implement direct transformations between ITRS, AltAz, and HADec frames.\n\n"
                "Risks: Uncertainty about potential side effects on existing transformations.")
        h = parse_handoff(text)
        assert h["files"] == ["astropy/coordinates/builtin_frames/altaz.py",
                              "astropy/coordinates/builtin_frames/hadec.py",
                              "astropy/coordinates/builtin_frames/itrs.py",
                              "astropy/coordinates/transformations.py"]
        assert h["symbols"] == [] and h["tests"] == ["test_intermediate_transformations.py"]
        assert h["approach"].startswith("Implement direct") and "files_source" not in h
        # path-shaped bullets under no heading at all are kept, flagged as such
        loose = parse_handoff("Affected:\n- src/a.py\n- src/b.py\nnot a path")
        assert loose["files"] == ["src/a.py", "src/b.py"] and loose["files_source"] == "path-shaped"
        # prose with no path names nothing
        assert "files" not in parse_handoff("change the frame code and run the tests")

    def test_inline_fields_on_one_line_are_split_not_swallowed(self):
        # the xarray planner (2026-08-22) wrote every field on ONE line
        # after a markdown prefix; the line-only parser swallowed
        # symbols:/tests:/approach: into files. ADR-066.
        from hobbes.run.handoff import parse_handoff
        h = parse_handoff("**Handoff:** files: xarray/core/dataset.py, xarray/core/dataarray.py   "
                          "symbols: xarray.Dataset.integrate, xarray.DataArray.integrate   "
                          "tests: xarray/tests/test_core.py   approach: change 'dim' to 'coord'")
        assert h["files"] == ["xarray/core/dataset.py", "xarray/core/dataarray.py"]
        assert h["symbols"] == ["xarray.Dataset.integrate", "xarray.DataArray.integrate"]
        assert h["tests"] == ["xarray/tests/test_core.py"]
        assert h["approach"].startswith("change 'dim'")
        # a normal multi-line handoff is untouched by the splitter
        multi = parse_handoff("\n".join(["files: a.py, b.py", "symbols: Foo", "approach: do the thing"]))
        assert multi["files"] == ["a.py", "b.py"] and multi["symbols"] == ["Foo"]
        assert multi["approach"] == "do the thing"

    def test_dotted_symbol_names_resolve_to_their_module(self):
        # the second live planner wrote `SlicedLowLevelWCS.world_to_pixel`
        # (an inherited method — no such symbol id); the class is unique
        from hobbes.derive.impact import resolve_terms
        graph = {"nodes": [{"id": "pkg.sliced", "path": "pkg/sliced.py"}, {"id": "pkg.other", "path": "pkg/other.py"}],
                 "symbols": [{"id": "pkg.sliced.Sliced", "name": "Sliced", "module": "pkg.sliced", "kind": "class"},
                             {"id": "pkg.sliced.Sliced.run", "name": "run", "module": "pkg.sliced", "kind": "method"},
                             {"id": "pkg.other.Other.run", "name": "run", "module": "pkg.other", "kind": "method"}]}
        hits, misses = resolve_terms(graph, ["Sliced.run", "Sliced.missing", "Other.run", "Nope.run", "run"])
        assert hits == ["pkg.sliced", "pkg.other"]
        # `run` alone is ambiguous and `Nope.run` names nothing — neither is guessed
        assert misses == ["Nope.run", "run"]

    def test_named_tests_resolve_to_repo_paths(self):
        # the probe's verifier ran `pytest test_intermediate_transformations.py`
        # at the root: the planner named the file bare
        from hobbes.run.stages import resolve_tests
        files = {"a/tests/test_x.py::test_one": "a/tests/test_x.py",
                 "b/tests/test_y.py::test_two": "b/tests/test_y.py",
                 "c/tests/test_y.py::test_three": "c/tests/test_y.py"}
        ok, bad = resolve_tests(["test_x.py", "tests/test_x.py::test_one", "b/tests/test_y.py",
                                 "test_y.py", "nope.py"], files)
        assert ok == ["a/tests/test_x.py", "a/tests/test_x.py::test_one", "b/tests/test_y.py"]
        assert bad == ["test_y.py", "nope.py"]  # ambiguous and absent: stated, never guessed

    def test_verdict_inference_is_marked_not_asserted(self):
        from hobbes.run.handoff import parse_handoff
        assert parse_handoff("everything passes")["verdict"] == "pass"
        assert parse_handoff("everything passes")["verdict_source"] == "inferred"
        assert parse_handoff("I looked around")["verdict_source"] == "none"

    def test_paths_with_trailing_reasons_are_cleaned(self):
        from hobbes.run.handoff import parse_handoff
        h = parse_handoff("\n".join(["files:", "- src/wcs.py (the slicer)", "- src/utils.py — helpers"]))
        assert h["files"] == ["src/wcs.py", "src/utils.py"]


class TestWindowRelativeBrief:
    """ADR-069: the brief is sized to the model's window and filled by
    priority, no single section starving the rest."""

    def test_limit_for_window_is_a_share_in_chars(self):
        from hobbes.run.agents import brief_limit_for_window, CHARS_PER_TOKEN, BRIEF_WINDOW_SHARE
        assert brief_limit_for_window(32768) == int(32768 * BRIEF_WINDOW_SHARE * CHARS_PER_TOKEN)
        assert brief_limit_for_window(131072, 0.25) == int(131072 * 0.25 * CHARS_PER_TOKEN)
        assert brief_limit_for_window(32768) < 60_000 < brief_limit_for_window(131072)

    def test_priority_fill_and_the_per_section_cap(self):
        from hobbes.run.agents import limit_context, CUT_SECTION_MAX_SHARE
        tests = "\n".join(f"- tests/test_{i}.py::test_{i}" for i in range(1500))   # ~45k
        neigh = "\n".join(f"- `pkg.mod{i}`: a, b, c" for i in range(1500))          # ~35k
        doc = ("# Standing context — unit U1\n\n## Interior (full resolution)\n- src/a.py\n\n"
               f"## Guarding tests (run these)\n{tests}\n\n"
               f"## Neighborhood (one hop out)\n{neigh}\n\n"
               "## What Hobbes cannot see here\n- x\n")
        out, dropped = limit_context(doc, 20_000)
        assert dropped > 0 and len(out) <= 20_000
        kept_tests = out.count("tests/test_")
        kept_neigh = out.count("`pkg.mod")
        # guarding tests are filled first, but capped — the neighborhood still gets its share
        assert kept_tests > kept_neigh > 50
        assert out.count("… cut:") == 2
        sec_tests = out.split("## Neighborhood")[0].split("## Guarding tests")[1]
        assert len(sec_tests) <= CUT_SECTION_MAX_SHARE * 20_000 + 400

    def test_endpoint_window_reads_max_model_len(self):
        import json as _json
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import threading
        from hobbes.run.parallel import endpoint_window

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                body = _json.dumps({"data": [{"id": "m", "owned_by": "vllm", "max_model_len": 32768}]}).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
                self.wfile.write(body)
        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            window, reason = endpoint_window(f"http://127.0.0.1:{srv.server_port}/v1")
        finally:
            srv.shutdown()
        assert window == 32768 and "max_model_len=32768" in reason
        assert endpoint_window("") == (None, "no endpoint: the runtime is not an OpenAI-compatible server")


def test_planner_brief_bounds_the_handoff():
    from hobbes.run.stages import planner_brief
    brief = planner_brief("fix it", {"nodes": [], "edges": []})
    assert "at most 5" in brief and "under 30 lines" in brief and "ADR-070" in brief
    # ADR-085: the planner is asked for requirements with owners
    assert "requirements:" in brief and "-> <owning file>" in brief


def test_handoff_paths_lose_trailing_sentence_punctuation():
    from hobbes.run.handoff import parse_handoff
    h = parse_handoff("files: sympy/functions/special/zeta_functions.py, sympy/tests/test_zeta_functions.py.\nsymbols: polylog.")
    assert h["files"] == ["sympy/functions/special/zeta_functions.py", "sympy/tests/test_zeta_functions.py"]
    assert h["symbols"] == ["polylog"]


class TestHumanFirstInABenchmark:
    """C-53 / ADR-071: a benchmark that runs alone may spawn a human-first
    unit; the abstention is still on the record."""

    def test_park_skips_and_spawn_runs_with_the_reason_recorded(self, plan_repo, staged_session, tmp_path, monkeypatch):  # noqa: F811
        from hobbes.derive import manifests
        from hobbes.run.stages import run_staged
        # every unit's complement "rivals" the captured fraction
        import dataclasses
        real = manifests.build_complement

        def blind(*a, **k):
            return dataclasses.replace(real(*a, **k), sites=20, unresolved=19, tail={"unclassified": 19})
        monkeypatch.setattr(manifests, "build_complement", blind)
        parked = run_staged(plan_repo, "improve app.core handle retry", session_bin=staged_session,
                            sessions_root=tmp_path / "park", max_units=5)
        assert parked["units"] and all(not u["spawned"] for u in parked["units"])
        assert all(u["reason"].startswith("human-first: not spawned") for u in parked["units"])
        spawned = run_staged(plan_repo, "improve app.core handle retry", session_bin=staged_session,
                             sessions_root=tmp_path / "spawn", max_units=5, human_first="spawn")
        live = [u for u in spawned["units"] if u["spawned"]]
        assert live and all("spawned anyway" in u["reason"] and "C-53" in u["reason"] for u in live)


class TestPlannerMapIsRelevant:
    """ADR-072: the planner's map ranks by the proposal, and carries the
    whole repo's shape — not the first 60 modules of the alphabet."""

    GRAPH = {
        "languages": ["python"], "resolution_coverage": [],
        "nodes": [
            {"id": "sphinx.domains.c", "kind": "module", "path": "sphinx/domains/c.py"},
            {"id": "sphinx.domains.cpp", "kind": "module", "path": "sphinx/domains/cpp.py"},
            {"id": "sphinx.domains.python", "kind": "module", "path": "sphinx/domains/python.py"},
            {"id": "sphinx.ext.autodoc", "kind": "package", "path": "sphinx/ext/autodoc/__init__.py"},
            {"id": "sphinx.ext.autodoc.importer", "kind": "module", "path": "sphinx/ext/autodoc/importer.py"},
            {"id": "sphinx.util.inspect", "kind": "module", "path": "sphinx/util/inspect.py"},
            {"id": "zeta", "kind": "module", "path": "sympy/functions/special/zeta_functions.py"},
        ],
        "symbols": [
            {"id": "sphinx.ext.autodoc.importer.get_object_members", "name": "get_object_members", "module": "sphinx.ext.autodoc.importer", "kind": "function"},
            {"id": "zeta.polylog", "name": "polylog", "module": "zeta", "kind": "class"},
        ],
    }

    def test_the_gold_package_is_first_by_name_and_symbol(self):
        from hobbes.run.stages import repo_context, related_modules
        ctx = repo_context(self.GRAPH, "autodoc inherited-members won't work for inherited attributes")
        related = [n["id"] for n, _ in related_modules(self.GRAPH, "autodoc inherited-members won't work")]
        assert set(related[:2]) == {"sphinx.ext.autodoc", "sphinx.ext.autodoc.importer"}
        assert "sphinx.domains.c" not in related
        assert "(matches: autodoc)" in ctx and "sphinx/ext/autodoc/ (2 modules)" in ctx and "sphinx/domains/ (3 modules)" in ctx
        # a symbol name reaches its module: "polylog" names zeta_functions
        byname = [n["id"] for n, hits in related_modules(self.GRAPH, "polylog expansion is wrong")]
        assert byname == ["zeta"]
        # old shape gone: the alphabetical first-N list
        assert "## Modules (id — path)" not in ctx

    def test_no_match_says_so_and_keeps_the_tree(self):
        from hobbes.run.stages import repo_context
        ctx = repo_context(self.GRAPH, "the thing is broken")
        assert "none: no proposal term matches" in ctx and "## Package tree" in ctx


class TestBoundaryLevers:
    """P12 levers (2026-08-23): a hub on the boundary is one collapsed line,
    a package root does not make the neighborhood the repo."""

    def _spec(self, contracts, neighborhood):
        return {
            "task": "t", "graph_sha": "abc", "proposal": "p",
            "contexts": [{"unit": "U1", "modules": [{"id": "m", "path": "m.py"}],
                          "guarding_tests": [], "invariants": [], "neighborhood": neighborhood,
                          "complement": {}, "human_first": False}],
            "policies": [{"unit": "U1", "floor": "deny", "guarantees": [], "write_mounts": [], "flags": []}],
            "contracts": contracts,
        }

    def test_import_uses_contracts_collapse_per_target_module(self):
        cs = [{"id": f"K{i}", "from_unit": f"U{i+2}", "to_unit": "U1", "caller": f"pkg.caller{i}",
               "target": "hub", "edge_type": "imports", "tier": "syntactic", "target_kind": "module",
               "declared_at": "hub.py", "owner": "U1", "pin": ""} for i in range(200)]
        out = agents.render_context(self._spec(cs, []), "U1")
        body = out.split("## Contracts", 1)[1].split("## Neighborhood", 1)[0]
        assert body.count("\n- ") <= agents.CONTRACTS_MAX + 1
        assert "200 edge(s)" in body  # the hub is one line carrying the count

    def test_calls_contracts_stay_per_edge_but_capped(self):
        cs = [{"id": f"K{i}", "from_unit": "U1", "to_unit": "U9", "caller": "m.f",
               "target": f"other.g{i}", "edge_type": "calls", "tier": "semantic", "target_kind": "function",
               "declared_at": f"other.py:{i}-{i+2}", "owner": "U9", "pin": ""} for i in range(60)]
        out = agents.render_context(self._spec(cs, []), "U1")
        body = out.split("## Contracts", 1)[1].split("## Neighborhood", 1)[0]
        assert "elided" in body and body.count("(calls,") <= agents.CONTRACTS_MAX

    def test_neighborhood_is_bounded_and_package_roots_sort_last(self):
        hood = [{"id": "pkg", "symbols": [f"s{i}" for i in range(50)]}]  # a root: no dot
        hood += [{"id": f"pkg.mod{i}", "symbols": ["a", "b"]} for i in range(40)]
        out = agents.render_context(self._spec([], hood), "U1")
        body = out.split("## Neighborhood", 1)[1]
        assert body.count("\n- `") <= agents.NEIGHBORHOOD_MAX_ENTRIES + 1
        assert "elided" in body
        # the package root, expanded, would dominate — it must not be shown first
        first = body.split("\n- `", 2)[1]
        assert not first.startswith("pkg`")


def test_guarding_tests_are_bounded_for_a_hub_module(monkeypatch):
    spec = {"task": "t", "graph_sha": "abc", "proposal": "p",
            "contexts": [{"unit": "U1", "modules": [{"id": "cfg", "path": "cfg.py"}],
                          "guarding_tests": [f"t{i}.py::test" for i in range(500)],
                          "invariants": [], "neighborhood": [], "complement": {}, "human_first": False}],
            "policies": [{"unit": "U1", "floor": "deny", "guarantees": [], "write_mounts": [], "flags": []}],
            "contracts": []}
    body = agents.render_context(spec, "U1").split("## Guarding", 1)[1].split("## ", 1)[0]
    assert body.count("\n- ") <= agents.GUARDING_TESTS_MAX + 1 and "elided" in body
