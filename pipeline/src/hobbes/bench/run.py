"""The run: selection → checkout → arms → records → verdicts (ADR-055).

``hobbes bench run`` is a loop, not an agent: for every selected
instance, for every model, for every arm, check the repo out at the
base commit, run the arm, append the record. Afterwards, when asked,
hand every (arm, model) group's patches to the evaluator and write the
verdicts back. A run directory holds ``run.json`` (the selection and
every parameter — the run is reproducible from it), ``records.jsonl``,
the predictions and evaluator logs, and per-instance workspaces under
``work/`` (kept, so a failure can be read in place; ``--clean``
removes them as each instance finishes).

Resumable: an (instance, arm, model) that already has a record is
skipped, so an interrupted run continues where it stopped.
"""

from __future__ import annotations

import os
import threading

import json
import shutil
import subprocess
import time
from pathlib import Path

from hobbes.bench import arms, environment, results, verdict, workspace
from hobbes.bench.instances import Selection

ARMS = ("pure", "harness")


def _tool_version(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()[:80]
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"


def write_manifest(run_dir: Path, selection: Selection, models: list[str], which: list[str], params: dict) -> Path:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "selection": selection.to_dict(),
        "models": models,
        "arms": which,
        "params": params,
        "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "claude": _tool_version(["claude", "--version"]),
        "evaluator": f"swebench=={verdict.SWEBENCH_VERSION}",
    }
    (run_dir / "run.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    return run_dir / "run.json"


#: The brief limit when the endpoint cannot say how wide the window is
#: (ADR-058's 60,000 ≈ 15k tokens of a 32k window, C-45).
DEFAULT_BRIEF_LIMIT = 60_000


def run(
    run_dir: Path,
    selection: Selection,
    models: list[str],
    which: list[str] = ARMS,
    session_bin: str | None = None,
    sessions_root: Path | None = None,
    session_args: list[str] | None = None,
    budget: int | None = None,
    clean: bool = False,
    timeout: float = 3600.0,
    runtime: arms.Runtime | None = None,
    environment_kind: str = "none",
    network: str = "pasta",
    max_units: int | None = None,
    brief_limit: int | None = None,
    brief_window_share: float | None = None,
    human_first: str = "park",
    stages: tuple[str, ...] | None = None,
    parallel_setting: str | int | None = 1,
    instance_workers: int = 1,
    implement_mode: str = "unit",
    coverage_mode: str = "strict",
    proposal_in_brief: bool = False,
    planner_args: list[str] | None = None,
    log=print,
) -> list[results.Record]:
    """Run every (instance, model, arm) not yet recorded; return all records.

    *environment_kind* ``swebench`` binds both arms to the instance's
    own image (ADR-058); ``none`` runs the pure arm on the host and the
    harness arm in the bare session image. *max_units* caps the
    harness arm's plan (C-44). *network* is the podman network both
    arms get when an environment is bound, and the harness arm's
    ``--network`` unless a session arg already names one."""
    run_dir = Path(run_dir)
    runtime = runtime or arms.Runtime()
    if environment_kind not in environment.KINDS:
        raise ValueError(f"environment must be one of {environment.KINDS}, not {environment_kind!r}")
    session_args = list(session_args or [])
    if not any(a == "--network" or a.startswith("--network=") for a in session_args):
        session_args += [f"--network={network}"]
    # Parallel implementers (ADR-063) only pay off on an endpoint that
    # batches; `auto` asks it once and falls back to sequential, saying
    # why (C-51). Only the staged harness arm schedules units.
    workers, parallel_reason = 1, "sequential: the harness arm is not staged"
    if stages and "harness" in which:
        from hobbes.run.parallel import resolve_workers
        workers, parallel_reason = resolve_workers(parallel_setting, runtime.base_url,
                                                   os.environ.get(runtime.api_key_env or "") or None)
    log(f"  parallel implementers: {parallel_reason} (ADR-063)")
    # The brief is sized to the model's window (ADR-069): `None` asks the
    # endpoint for max_model_len and takes a share of it; an explicit
    # limit is the owner's call; 0 is no limit. No window known → the
    # old absolute default, said so.
    window, brief_reason = None, "explicit"
    if brief_limit is None:
        from hobbes.run.agents import BRIEF_WINDOW_SHARE, brief_limit_for_window
        from hobbes.run.parallel import endpoint_window
        share = brief_window_share if brief_window_share is not None else BRIEF_WINDOW_SHARE
        window, window_reason = endpoint_window(runtime.base_url, os.environ.get(runtime.api_key_env or "") or None)
        if window:
            brief_limit = brief_limit_for_window(window, share)
            brief_reason = f"{share:.0%} of a {window:,}-token window ({window_reason})"
        else:
            brief_limit = DEFAULT_BRIEF_LIMIT
            brief_reason = f"absolute default — {window_reason}"
    elif brief_limit == 0:
        brief_limit, brief_reason = None, "none"
    if human_first == "spawn":
        log("  human-first units: spawned anyway — the benchmark runs alone; the abstention is recorded per unit (C-53)")
    else:
        log("  human-first units: parked (ADR-047) — a benchmark with no human counts them as empty; --human-first spawn runs them (C-53)")
    log(f"  brief limit: {f'{brief_limit:,} chars' if brief_limit else 'none'} — {brief_reason} (C-45, ADR-069)")
    write_manifest(run_dir, selection, models, list(which), {
        "session_bin": session_bin, "session_args": session_args, "budget": budget,
        "max_units": max_units, "brief_limit": brief_limit, "brief_window": window, "brief_reason": brief_reason,
        "environment": environment_kind, "network": network, "human_first": human_first,
        "stages": list(stages) if stages else None,
        "parallel": {"setting": str(parallel_setting), "workers": workers, "reason": parallel_reason},
        "timeout": timeout, "clean": clean,
        "runtime": runtime.describe(),
    })
    done = {(r.instance_id, r.arm, r.model) for r in results.load(run_dir)}

    def record_arm(arm: str) -> str:
        # P12 (ADR-082): a staged aided harness run is recorded — and
        # resumed — under the arm it actually is: model+prompt, never
        # harness. The machinery refuses the label, not a person.
        if arm == "harness" and stages and implement_mode == "aided":
            return "model+prompt"
        return arm
    # Appends and log lines are shared across instance threads; a lock
    # keeps a record and its planner line intact and the JSONL uncorrupted.
    write_lock = threading.Lock()

    def emit(record, result, instance, arm, model):
        arm = record.arm  # the recorded arm names the patch the evaluator reads
        with write_lock:
            results.append(run_dir, record)
            log(f"{instance.instance_id} [{arm}/{model or 'default'}] "
                + f"→ {record.outcome}, {len(record.patch_files)} files, "
                + (f"usage unobserved: {', '.join(record.usage['unobserved'])}"
                   if record.usage["unobserved"] else f"{record.usage['total_tokens']} tokens")
                + (f"; {record.error[:120]}" if record.error else ""))
            planner = record.detail.get("planner")
            if planner and "hit" in planner:
                log(f"  → {instance.instance_id} seed_source {record.detail.get('seed_source')}; planner "
                    + (f"hit {planner['hits']}/{planner['gold']} gold files" if planner["hit"]
                       else f"missed the {planner['gold']} gold files")
                    + "; stage wall " + ", ".join(f"{k} {v:.0f}s" for k, v in
                                                  record.detail.get("run", {}).get("stage_wall", {}).items()))
            (run_dir / "patches").mkdir(exist_ok=True)
            (run_dir / "patches" / f"{instance.instance_id}.{arm}.{(model or 'default').replace('/', '_')}.diff"
             ).write_text(result.patch)

    def run_instance(instance):
        """One instance end to end (both arms): pull its image, then run
        each pending (model, arm). Runs on its own thread so instances
        overlap — the shared Modal endpoint batches their requests
        (ADR-065). The intra-instance unit pool (ADR-063) still runs
        beneath this, so peak concurrency is instance_workers × workers."""
        pending = [(m, a) for m in models for a in which if (instance.instance_id, record_arm(a), m) not in done]
        if not pending:
            return
        env: environment.Environment | None = None
        env_error = ""
        if environment_kind == "swebench":
            try:
                env = environment.ensure_image(environment.swebench_environment(instance), log=log)
            except environment.EnvironmentError_ as exc:
                env_error = str(exc)
        # Session dirs are named from the proposal hash; two instances
        # that happen to share a proposal would collide under a pool, so
        # each instance gets its own sessions subtree (ADR-065).
        inst_sessions = (sessions_root / instance.instance_id) if sessions_root else None
        for model, arm in pending:
            ws = run_dir / "work" / instance.instance_id / f"{arm}-{model or 'default'}".replace("/", "_")
            log(f"{instance.instance_id} [{arm}/{model or 'default'}] checkout {instance.base_commit[:12]}"
                + (f" in {env.image}" if env else ""))
            if env_error:
                result = arms.ArmResult(record_arm(arm), model, "env-error", error=env_error)
                emit(results.make_record(instance, result), result, instance, arm, model)
                continue
            try:
                workspace.checkout(instance, ws)
            except workspace.WorkspaceError as exc:
                result = arms.ArmResult(record_arm(arm), model,
                                        "ingest-error" if arm == "harness" else "claude-error",
                                        error=f"checkout: {exc}")
            else:
                if arm == "pure":
                    result = arms.run_pure_arm(instance, ws, model, timeout=timeout, runtime=runtime,
                                               environment=env, network=network)
                else:
                    result = arms.run_harness_arm(
                        instance, ws, model, session_bin=session_bin, sessions_root=inst_sessions,
                        extra_session_args=session_args, budget=budget, runtime=runtime,
                        environment=env, max_units=max_units, human_first=human_first, brief_limit=brief_limit,
                        stages=stages, workers=workers, implement_mode=implement_mode,
                        coverage_mode=coverage_mode, proposal_in_brief=proposal_in_brief,
                        planner_args=planner_args,
                    )
            emit(results.make_record(instance, result), result, instance, arm, model)
            if clean:
                shutil.rmtree(ws, ignore_errors=True)

    if max(1, instance_workers) == 1:
        for instance in selection.selected:
            run_instance(instance)
    else:
        # Instances overlap on the shared endpoint (ADR-065). One failing
        # instance must not sink the others: a thread that raises is
        # logged and the rest continue, the record for its unreached arm
        # simply absent (resumable — a re-run picks it up).
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=min(instance_workers, len(selection.selected) or 1)) as pool:
            futs = {pool.submit(run_instance, ins): ins for ins in selection.selected}
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as exc:  # noqa: BLE001 — one instance's failure is not the run's
                    log(f"{futs[fut].instance_id}: instance failed: {type(exc).__name__}: {exc}")
    return results.load(run_dir)


def evaluate(run_dir: Path, dataset: str, max_workers: int = 1, timeout: float | None = None,
             modal: bool = False, log=print) -> list[results.Record]:
    """Judge every unjudged record through the benchmark's evaluator,
    one call per (arm, model), and write verdicts back."""
    run_dir = Path(run_dir)
    records = results.load(run_dir)
    groups: dict[tuple[str, str], list[results.Record]] = {}
    for r in records:
        if r.solved is None:
            groups.setdefault((r.arm, r.model), []).append(r)
    patches = run_dir / "patches"
    for (arm, model), rs in sorted(groups.items()):
        name = verdict.model_name(arm, model)
        rows = []
        for r in rs:
            path = patches / f"{r.instance_id}.{arm}.{(model or 'default').replace('/', '_')}.diff"
            rows.append({"instance_id": r.instance_id, "model_name_or_path": name,
                         "model_patch": path.read_text() if path.is_file() else ""})
        preds = verdict.write_predictions(run_dir / "eval" / f"{name}.predictions.json", rows)
        run_id = run_dir.name
        log(f"evaluating {len(rows)} {arm}/{model or 'default'} patches ({name}) …")
        try:
            verdicts = verdict.evaluate(dataset, preds, run_id, name, [r.instance_id for r in rs],
                                        cwd=run_dir / "eval", max_workers=max_workers, timeout=timeout,
                                        modal=modal)
        except verdict.VerdictError as exc:
            log(f"  evaluator failed: {exc}")
            continue
        for r in rs:
            r.verdict = verdicts.get(r.instance_id, "unjudged")
        log("  " + ", ".join(f"{v} {sum(1 for x in verdicts.values() if x == v)}" for v in verdict.VERDICTS
                            if any(x == v for x in verdicts.values())))
    results.rewrite(run_dir, records)
    return records
