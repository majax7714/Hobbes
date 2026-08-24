"""The two arms (ADR-055): Hobbes as a harness, and the model pure.

Both start from the same checkout (:mod:`hobbes.bench.workspace`) and
end in a candidate patch; everything between is what the comparison
measures.

**Harness arm.** ``ingest`` → ``plan`` → ``run`` → patch, exactly the
commands a human runs (ADR-051/054), with the issue text as the
proposal. The seeds are lexical (C-36): an instance whose issue names
no identifier the graph knows seeds nothing, and that is recorded as
the harness outcome ``no-seed`` — a failure of the harness arm, counted
against it, never dropped from the denominator (dropping it would
inflate the arm the benchmark exists to test). Every unit's session
runs in the ADR-018 sandbox through ``hobbes-session``; the partition
record, the plan summary, and the per-unit meters ride the record.

**Pure arm.** Claude Code on the same checkout with its own tools and
nothing of Hobbes — no MCP server, no policy, no derived context — the
issue text as the prompt. It runs where ``claude`` runs, on the host,
with shell access to the checkout (the benchmark repo's code can run;
the containment of the pure arm is an owner decision recorded with
ADR-055, not a default taken here). The result envelope is the meter.

Neither arm interprets its result. The verdict is the benchmark's
(:mod:`hobbes.bench.verdict`).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from hobbes.bench import accounting
from hobbes.bench.instances import Instance
from hobbes.bench.workspace import candidate_patch
from hobbes.bench.environment import Environment
from hobbes.narrate.runner import CLAUDE_BIN_ENV

#: The owned agent loop (ADR-056): one stdlib-only file, run by the host
#: python for the pure arm and copied into the sandbox for the harness arm.
LOOP_PATH = Path(__file__).resolve().parent.parent / "agent" / "loop.py"

#: The solo/benchmark session floor (ADR-057): a benchmark checkout is a
#: committed-only clone, so the repo and role policies never reach the
#: session, and there is no human to approve escalations. This box policy
#: grants a solo implementer the tests-and-commit it needs while the
#: specific guarantees stay denied — passed to ``hobbes-session --box``.
BENCH_BOX = Path(__file__).resolve().parent / "bench.box.policy"

#: How long an escalated command parks before expire-to-deny on the solo
#: path. Short by design: no human approves, so parking is dead time.
BENCH_ESCALATION = "5s"
RUNTIMES = ("claude", "openai")


@dataclass
class Runtime:
    """Which loop the arms run on. ``claude`` is Claude Code; ``openai``
    is :mod:`hobbes.agent.loop` against an OpenAI-compatible endpoint
    (``base_url`` required) — the small-model ladder's runtime."""

    kind: str = "claude"
    base_url: str = ""
    api_key_env: str = "HOBBES_LLM_API_KEY"
    max_turns: int = 60
    #: Completion cap per turn, both arms. The first full-stage probe
    #: spent 45% of its harness wall on ~2,800-token prose turns that
    #: never called a tool; the cap cuts the essay and brings the nudge
    #: forward. Big enough for a whole-file write of ~120 lines.
    max_tokens: int = 1536
    #: How completions are sampled (ADR-074), both arms. The 7B ladder
    #: ran greedy; a thinking rung (Qwen3.8) is run at its card's own
    #: sampling with its reasoning on, because greedy decoding loops
    #: its reasoning and thinking is what its agentic numbers rest on.
    temperature: float = 0.0
    top_p: float | None = None
    reasoning_effort: str | None = None
    thinking: str = "server"
    #: Loop discipline knobs (ADR-076), both arms. ``None`` leaves the
    #: loop's own default (6 / 3), which was cut for the 7B; a thinking
    #: model investigates more turns before its first edit, so a
    #: benchmark on such a rung raises these rather than have a model
    #: that is *searching* stopped as if it were stalled. The 7B record
    #: stands because its runs left these unset.
    stall_after: int | None = None
    nudge_after: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in RUNTIMES:
            raise ValueError(f"runtime must be one of {RUNTIMES}, not {self.kind!r}")
        if self.kind == "openai" and not self.base_url:
            raise ValueError("the openai runtime needs a base_url")

    def loop_args(self) -> list[str]:
        """The sampling flags the owned loop takes (ADR-074) — the same
        list on both arms, so a rung's sampling is one declaration."""
        args = [f"--temperature={self.temperature}"]
        if self.top_p is not None:
            args.append(f"--top-p={self.top_p}")
        if self.reasoning_effort:
            args.append(f"--reasoning-effort={self.reasoning_effort}")
        if self.thinking != "server":
            args.append(f"--thinking={self.thinking}")
        if self.stall_after is not None:
            args.append(f"--stall-after={self.stall_after}")
        if self.nudge_after is not None:
            args.append(f"--nudge-after={self.nudge_after}")
        return args

    def session_args(self) -> list[str]:
        """Flags for ``hobbes-session`` so the harness arm runs the same loop."""
        if self.kind != "openai":
            return []
        return ["--runtime", str(LOOP_PATH), "--llm-base-url", self.base_url,
                "--max-turns", str(self.max_turns), "--max-tokens", str(self.max_tokens),
                *(f"--loop-arg={a}" for a in self.loop_args())]

    def describe(self) -> dict:
        """The runtime as the run record states it."""
        return {"kind": self.kind, "base_url": self.base_url, "max_turns": self.max_turns,
                "max_tokens": self.max_tokens, "temperature": self.temperature, "top_p": self.top_p,
                "reasoning_effort": self.reasoning_effort, "thinking": self.thinking,
                "stall_after": self.stall_after, "nudge_after": self.nudge_after}

#: Harness-arm outcome classes — the error stream ADR-052 asked for.
HARNESS_OUTCOMES = ("patch", "empty-patch", "no-seed", "plan-error", "run-error", "ingest-error", "env-error")
PURE_OUTCOMES = ("patch", "empty-patch", "claude-error", "env-error")


@dataclass
class ArmResult:
    """What one arm produced for one instance."""

    arm: str
    model: str
    outcome: str
    patch: str = ""
    usage: accounting.Usage = field(default_factory=accounting.Usage)
    detail: dict = field(default_factory=dict)
    error: str = ""

    @property
    def patch_files(self) -> list[str]:
        return sorted({
            line.split(" b/", 1)[1] for line in self.patch.splitlines()
            if line.startswith("diff --git ") and " b/" in line
        })


def _classify_patch(patch: str) -> str:
    return "patch" if patch.strip() else "empty-patch"


def pure_prompt(instance: Instance) -> str:
    """The pure arm's prompt: the issue, and the one instruction the
    benchmark protocol needs (a diff of the tree is the answer)."""
    return (
        f"You are working in a checkout of {instance.repo} at commit "
        f"{instance.base_commit[:12]}. Resolve the issue below by changing "
        "the code in this working tree. Do not commit, push, or create "
        "branches; the diff of the working tree is your answer.\n\n"
        f"{instance.problem_statement.strip()}\n"
    )


def run_pure_arm(
    instance: Instance,
    workspace: Path,
    model: str,
    timeout: float = 3600.0,
    permission_mode: str = "acceptEdits",
    allowed_tools: str = "Bash,Edit,Write,Read,Glob,Grep",
    runtime: Runtime | None = None,
    environment: Environment | None = None,
    network: str = "pasta",
) -> ArmResult:
    """The model, pure, on *workspace*: Claude Code (``HOBBES_CLAUDE_BIN``
    names the binary — the narrate runner's precedent and the tests'
    stand-in), or the owned loop with bash and file tools when
    *runtime* is ``openai``. With an *environment* (ADR-058) the owned
    loop runs inside the benchmark's image over the mounted workspace
    — the same binding the harness arm gets, so the arms differ in
    Hobbes and nothing else."""
    runtime = runtime or Runtime()
    bin_ = os.environ.get(CLAUDE_BIN_ENV, "claude")
    if runtime.kind == "openai" and environment is not None:
        loop = ["--base-url", runtime.base_url, "--model", model, "--api-key-env", runtime.api_key_env,
                "--prompt", pure_prompt(instance), "--workdir", "/work", "--max-turns", str(runtime.max_turns),
                "--max-tokens", str(runtime.max_tokens), *runtime.loop_args(),
                # ADR-068: the pure arm had no transcript, so its window
                # use could only be guessed from the envelope's sums.
                "--transcript", "/work/.hobbes/transcript.jsonl"]
        inner = [environment.runtime_python, "/hobbes/loop.py", *loop]
        if environment.pre:
            inner = ["/bin/sh", "-c", environment.pre + ' && exec "$@"', "hobbes-pre", *inner]
        cmd = ["podman", "run", "--rm", "--network", network, "--env", "HOME=/tmp",
               *environment.podman_env(),
               "--env", f"{runtime.api_key_env}={os.environ.get(runtime.api_key_env, '')}",
               "-v", f"{Path(workspace).resolve()}:/work:rw,z",
               "-v", f"{LOOP_PATH}:/hobbes/loop.py:ro,z",
               "--workdir", "/work", environment.image, *inner]
    elif runtime.kind == "openai":
        cmd = [sys.executable, str(LOOP_PATH), "--base-url", runtime.base_url, "--model", model,
               "--api-key-env", runtime.api_key_env, "--prompt", pure_prompt(instance),
               "--workdir", str(workspace), "--max-turns", str(runtime.max_turns),
               "--max-tokens", str(runtime.max_tokens), *runtime.loop_args(),
               "--transcript", str(Path(workspace) / ".hobbes" / "transcript.jsonl")]
    else:
        cmd = [bin_, "-p", pure_prompt(instance), "--output-format", "json",
               "--permission-mode", permission_mode, "--allowedTools", allowed_tools]
        if model:
            cmd += ["--model", model]
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=str(workspace), capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return ArmResult("pure", model, "claude-error", error=f"claude binary not found ({bin_!r})")
    except subprocess.TimeoutExpired:
        return ArmResult("pure", model, "claude-error", error=f"claude timed out after {timeout:.0f}s",
                         usage=accounting.Usage(wall_seconds=timeout, envelopes=0))
    elapsed = time.monotonic() - started
    usage = accounting.from_text(proc.stdout)
    if usage.wall_seconds is None:
        usage.wall_seconds = round(elapsed, 3)
    (Path(workspace) / ".hobbes").mkdir(exist_ok=True)
    (Path(workspace) / ".hobbes" / "pure-arm.log").write_text(proc.stdout + proc.stderr)
    patch = candidate_patch(workspace, instance.base_commit)
    detail = {"exit": proc.returncode, "turns": usage.turns, "runtime": runtime.kind}
    if environment is not None:
        detail["environment"] = environment.to_dict()
    result = ArmResult("pure", model, _classify_patch(patch), patch=patch, usage=usage, detail=detail)
    if proc.returncode != 0:
        result.outcome = "claude-error" if not patch.strip() else result.outcome
        result.error = (proc.stderr or proc.stdout).strip()[-400:]
    return result


def run_harness_arm(
    instance: Instance,
    workspace: Path,
    model: str,
    session_bin: str | None = None,
    sessions_root: Path | None = None,
    extra_session_args: list[str] | None = None,
    environment: Environment | None = None,
    max_units: int | None = None,
    brief_limit: int | None = None,
    budget: int | None = None,
    seeds: list[str] | None = None,
    runtime: Runtime | None = None,
    stages: tuple[str, ...] | None = None,
    implement_mode: str = "unit",
    workers: int = 1,
    human_first: str = "park",
    coverage_mode: str = "strict",
    proposal_in_brief: bool = False,
    planner_args: list[str] | None = None,
) -> ArmResult:
    """``ingest`` → ``plan`` → ``run`` → patch on *workspace*. The
    sessions run on *runtime* (Claude Code, or the owned loop through
    ``hobbes-session --runtime``). With *stages* the run is **staged**
    (ADR-059): a planner names the change, the plan derives on its
    seeds, implementers run chained, a verifier checks — instead of
    planning lexically and spawning one session per unit."""
    runtime = runtime or Runtime()
    from hobbes import artifacts
    from hobbes.derive import DeriveError, derive_plan, write_spec
    from hobbes.derive.changespec import ComplementError
    from hobbes.derive.impact import SeedError
    from hobbes.derive.manifests import GuaranteeError
    from hobbes.extract import ingest
    from hobbes.extract.emit import StampError
    from hobbes.extract.packs import PackRefusal
    from hobbes.invariants import ValidationError
    from hobbes.run import RunError, run_task

    workspace = Path(workspace)
    detail: dict = {"model": model, "runtime": runtime.kind}
    started = time.monotonic()
    try:
        ingest(workspace)
    except PackRefusal:
        # P10: a refusal is a specific guarantee; the arm's catch-all
        # below must not absorb it into an outcome class.
        raise
    except (StampError, Exception) as exc:  # noqa: BLE001 — recorded as the arm's outcome
        return ArmResult("harness", model, "ingest-error", error=f"{type(exc).__name__}: {exc}")
    graph = artifacts.load_graph(workspace)
    detail["ingest"] = {
        "languages": graph.get("languages", []),
        "nodes": len(graph.get("nodes", [])),
        "call_edges": len(graph.get("symbol_edges", [])),
        "capture": _capture(graph),
    }
    if stages:
        return _run_staged_arm(instance, workspace, model, detail, started, stages,
                               session_bin, sessions_root, extra_session_args, environment,
                               max_units, brief_limit, budget, seeds, runtime, workers, human_first,
                               implement_mode, coverage_mode, proposal_in_brief, planner_args)
    try:
        kwargs = {"seeds": seeds or [], "max_units": max_units}
        if budget:
            kwargs["budget"] = budget
        spec = derive_plan(workspace, instance.problem_statement, **kwargs)
    except SeedError as exc:
        detail["plan"] = {"unresolved_terms": _unresolved_from(str(exc))}
        return ArmResult("harness", model, "no-seed", detail=detail, error=str(exc))
    except (DeriveError, GuaranteeError, ComplementError, ValidationError, artifacts.ArtifactError) as exc:
        return ArmResult("harness", model, "plan-error", detail=detail, error=f"{type(exc).__name__}: {exc}")
    write_spec(workspace, spec)
    detail["plan"] = {
        "task": spec.task,
        "seeds": dict(spec.seeds),
        "unresolved_terms": list(spec.unresolved_terms),
        "units": len(spec.units),
        "max_units": max_units,
        "capped": sum(1 for u in spec.units if any(f.startswith("capped") for f in u.flags)),
        "deferred": len(spec.units_deferred),
        "contracts": len(spec.contracts),
        "human_first": [c.unit for c in spec.contexts if c.human_first],
        "gate": spec.gate.result,
    }
    session_args = solo_session_args(extra_session_args) + runtime.session_args()
    if environment is not None:
        session_args += environment.session_args()
        detail["environment"] = environment.to_dict()
    if model:
        session_args += ["--model", model]
    try:
        record = run_task(workspace, spec.task, session_bin=session_bin,
                          sessions_root=sessions_root, extra_args=session_args, brief_limit=brief_limit)
    except (RunError, artifacts.ArtifactError, Exception) as exc:  # noqa: BLE001
        return ArmResult("harness", model, "run-error", detail=detail, error=f"{type(exc).__name__}: {exc}")
    usage = accounting.Usage()
    from hobbes.run.agents import agent_dir
    from hobbes.run.spec import plan_dir
    pdir = plan_dir(workspace, spec.task)
    for unit in record.get("units", []):
        log = agent_dir(pdir, unit["unit"]) / "session.log"
        if log.is_file():
            usage = usage.add(accounting.from_text(log.read_text()))
    if usage.wall_seconds is None and usage.envelopes == 0:
        # The harness arm's wall time is observable from outside the
        # sessions even when no envelope was emitted inside them.
        usage.wall_seconds = round(time.monotonic() - started, 3)
    detail["run"] = {
        "units": [{k: u.get(k) for k in ("unit", "spawned", "exit", "knowledge_calls", "context_faults",
                                          "commits", "rework_files", "reflections", "reason",
                                          "brief_chars", "brief_cut", "exit_commit_files")}
                  for u in record.get("units", [])],
        "integration": record.get("integration", {}),
        "review": {k: v for k, v in record.get("review", {}).items() if k in ("needs_attention", "error", "skipped")},
        "loss": record.get("loss", {}),
    }
    branch = record.get("integration", {}).get("branch")
    patch = candidate_patch(workspace, instance.base_commit, ref=branch) if branch and _ref_exists(workspace, branch) else ""
    return ArmResult("harness", model, _classify_patch(patch), patch=patch, usage=usage, detail=detail)


def _run_staged_arm(instance, workspace, model, detail, started, stages, session_bin,
                    sessions_root, extra_session_args, environment, max_units, brief_limit,
                    budget, seeds, runtime, workers: int = 1, human_first: str = "park",
                    implement_mode: str = "unit", coverage_mode: str = "strict",
                    proposal_in_brief: bool = False, planner_args: list[str] | None = None) -> ArmResult:
    """The staged harness arm (ADR-059): run_staged does ingest's
    successor stages. The candidate patch is the integration branch's
    diff, exactly as the per-unit path. The record carries every stage
    (role, session, exit, handoff verdict, **wall time and tokens** from
    that stage's own session log), ``seed_source``, and the planner's
    named files — the error stream ADR-052 asked for, one layer richer.
    The usage is the sum over every stage's session, the planner and
    the verifier included: a read-only stage costs turns too (H3)."""
    from hobbes import artifacts
    from hobbes.derive.impact import SeedError
    from hobbes.run import RunError
    from hobbes.run.coverage import PlanCoverageError
    from hobbes.run.stages import run_staged
    # P12 (ADR-082): an aided implement stage is one free agent on the
    # whole task — the machinery refuses the Hobbes label; a person
    # never gets to grant it. Every record this run writes carries the
    # arm it actually was.
    arm_label = "model+prompt" if implement_mode == "aided" else "harness"
    detail["implement_mode"] = implement_mode
    session_args = solo_session_args(extra_session_args) + runtime.session_args()
    if environment is not None:
        session_args += environment.session_args()
        detail["environment"] = environment.to_dict()
    if model:
        session_args += ["--model", model]
    try:
        record = run_staged(workspace, instance.problem_statement, stages=stages,
                            session_bin=session_bin, sessions_root=sessions_root,
                            extra_args=session_args, brief_limit=brief_limit,
                            max_units=max_units, budget=budget, seeds=seeds or None, workers=workers,
                            human_first=human_first, implement_mode=implement_mode,
                            coverage_mode=coverage_mode, proposal_in_brief=proposal_in_brief,
                            planner_args=planner_args)
    except SeedError as exc:
        detail["plan"] = {"unresolved_terms": _unresolved_from(str(exc))}
        return ArmResult(arm_label, model, "no-seed", detail=detail, error=str(exc))
    except PlanCoverageError as exc:
        # The planner's guarantee failed at plan cost (ADR-085): a
        # plan-error, its coverage on the record — not a run-error.
        detail["coverage"] = exc.coverage
        return ArmResult(arm_label, model, "plan-error", detail=detail, error=str(exc))
    except (RunError, artifacts.ArtifactError, Exception) as exc:  # noqa: BLE001
        return ArmResult(arm_label, model, "run-error", detail=detail, error=f"{type(exc).__name__}: {exc}")
    from hobbes.run.agents import agent_dir
    from hobbes.run.spec import plan_dir
    pdir = plan_dir(workspace, record["task"])
    usage = accounting.Usage()
    stage_rows = []
    stage_wall: dict[str, float] = {}
    for st in record.get("stages", []):
        row = {k: st.get(k) for k in ("stage", "role", "unit", "session", "verdict", "verdict_source",
                                      "exit", "resolved", "unresolved", "verifier_env", "wall_seconds")}
        stage_usage = _stage_usage(agent_dir(pdir, st.get("agent") or ""), st.get("session") or "")
        row["tokens"] = stage_usage.total_tokens
        usage = usage.add(stage_usage)
        if st.get("wall_seconds") is not None:
            stage_wall[st["stage"]] = round(stage_wall.get(st["stage"], 0.0) + st["wall_seconds"], 3)
        stage_rows.append(row)
    # With parallel implementers (ADR-063) the per-unit walls overlap;
    # the stage's clock time is what the record measured from outside.
    if record.get("implement_wall_seconds") is not None and "implement" in stage_wall:
        stage_wall["implement_units_sum"] = stage_wall["implement"]
        stage_wall["implement"] = round(record["implement_wall_seconds"], 3)
    if usage.wall_seconds is None:
        # Stage wall times are measured from outside the sessions, so the
        # arm's wall time is observed even when no envelope was emitted.
        walls = [v for k, v in stage_wall.items() if k != "implement_units_sum"]
        usage.wall_seconds = round(sum(walls), 3) if walls else round(time.monotonic() - started, 3)
    detail["seed_source"] = record.get("seed_source")
    detail["stages"] = stage_rows
    # The LAST plan stage: a re-plan (ADR-085) supersedes the first.
    plan_stage = next((st for st in reversed(record.get("stages", [])) if st.get("stage") == "plan"), {})
    graph = artifacts.load_graph(workspace)
    detail["planner"] = {
        "files": list(plan_stage.get("files", [])), "symbols": list(plan_stage.get("symbols", [])),
        "resolved": list(plan_stage.get("resolved", [])), "unresolved": list(plan_stage.get("unresolved", [])),
        "requirements": list(plan_stage.get("requirements", [])),
        "imperatives_unmentioned": list(plan_stage.get("imperatives_unmentioned", [])),
        # The paths the planner's handoff reaches: named files plus the
        # files of the modules its names resolved to. What results.py
        # checks against the gold patch — after the arm, never inside it.
        "paths": planner_paths(graph, plan_stage),
    }
    detail["plan"] = {"task": record["task"], "seeds": record.get("seeds", {}),
                      "units": len(record.get("units", [])),
                      "deferred": len(record.get("units_deferred", [])),
                      "planner_unresolved": record.get("planner_unresolved", []),
                      "contracts": record.get("contracts", 0)}
    detail["coverage"] = record.get("coverage", {})
    detail["brief_task"] = record.get("brief_task")
    detail["run"] = {"seed_source": record.get("seed_source"),
                     "stage_wall": stage_wall,
                     "parallel": record.get("parallel"),
                     "units": [{k: u.get(k) for k in ("unit", "spawned", "exit", "commits", "wall_seconds",
                                                       "reflections", "reason", "brief_cut")}
                               for u in record.get("units", [])],
                     "integration": record.get("integration", {}),
                     "verify": {k: record.get("verify", {}).get(k) for k in ("verdict", "verdict_source", "reason")},
                     "rework": record.get("rework", 0), "loss": record.get("loss", {})}
    branch = record.get("integration", {}).get("branch")
    patch = candidate_patch(workspace, instance.base_commit, ref=branch) if branch and _ref_exists(workspace, branch) else ""
    return ArmResult(arm_label, model, _classify_patch(patch), patch=patch, usage=usage, detail=detail)


def _stage_usage(directory: Path, session: str) -> accounting.Usage:
    """One stage's meter from its own session log (the per-session copy
    first — a rework overwrites the unit's ``session.log``)."""
    for name in (f"{session}.log" if session else "", "session.log"):
        if name and (directory / name).is_file():
            return accounting.from_text((directory / name).read_text())
    return accounting.Usage()


def planner_paths(graph: dict, plan_stage: dict) -> list[str]:
    """The file paths a planner's handoff names, directly or through the
    modules its names resolved to. Sorted, unique; a name that resolved
    to nothing and is not path-shaped contributes nothing."""
    by_id = {n["id"]: n.get("path") for n in graph.get("nodes", [])}
    paths = {by_id[m] for m in plan_stage.get("resolved", []) if by_id.get(m)}
    paths.update(f.strip().lstrip("./") for f in plan_stage.get("files", []) if "/" in f or "." in f)
    return sorted(p for p in paths if p)


def solo_session_args(extra: list[str] | None) -> list[str]:
    """The benchmark session's floor and escalation backstop, unless the
    caller already set them (a --session-arg wins, so a run can override
    the policy or the timeout deliberately)."""
    args = list(extra or [])
    joined = " ".join(args)
    if "--box" not in joined:
        args += ["--box", str(BENCH_BOX)]
    if "--escalation-timeout" not in joined:
        args += ["--escalation-timeout", BENCH_ESCALATION]
    if "--commit-on-exit" not in joined:
        # A solo session's uncommitted edits would vanish with the clone
        # (ADR-058); the wrapper commits them, named as its own.
        args.append("--commit-on-exit")
    return args


def _ref_exists(repo: Path, ref: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "-q", ref],
                          capture_output=True).returncode == 0


def _capture(graph: dict) -> dict[str, float]:
    """Per-language capture (% of detected call sites resolved) from the
    coverage rows — the ingest summary's number, kept on the record so
    a harness failure can be read against how much the graph saw."""
    out: dict[str, list[int]] = {}
    for row in graph.get("resolution_coverage", []):
        lang = row.get("language") or "all"
        sites, unresolved = int(row.get("sites", 0)), int(row.get("unresolved", 0))
        acc = out.setdefault(lang, [0, 0])
        acc[0] += sites
        acc[1] += unresolved
    return {lang: round(100.0 * (s - u) / s, 1) for lang, (s, u) in out.items() if s}


def _unresolved_from(message: str) -> list[str]:
    marker = "unmatched code-shaped terms: "
    if marker not in message:
        return []
    tail = message.split(marker, 1)[1].split(")", 1)[0]
    return [t.strip() for t in tail.split(",") if t.strip()]
