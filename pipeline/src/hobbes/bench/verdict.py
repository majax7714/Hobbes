"""The verdict is the benchmark's own (ADR-055).

A SWE-bench instance is solved when its ``FAIL_TO_PASS`` tests pass
and its ``PASS_TO_PASS`` tests still pass after the candidate patch,
in the instance's own environment. That judgement needs per-repo test
commands, per-version environments, and log parsers — all of which
the benchmark publishes and maintains. Hobbes does not reimplement
them: the pinned ``swebench`` package's ``run_evaluation`` runs as a
subprocess over a predictions file, and its report is the verdict.
That makes the evaluator a provider in P9's sense — its blind spots
are ours, and the register entry names it with its version.

It needs a container engine. ``swebench`` speaks the Docker API;
rootless podman serves it through its socket
(``systemctl --user enable --now podman.socket`` and
``DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock``). The
command is overridable (``HOBBES_SWEBENCH_CMD``) — the tests point it
at a stand-in that writes a report in the same shape.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

#: Pinned evaluator (P9: a provider's limits are ours, and can end on
#: an upstream release — the version is part of the claim).
SWEBENCH_VERSION = "5.0.2"

#: The evaluator's schema dataset. swebench 5.0.2's ``make_test_spec``
#: reads ``instance["image"]``/``eval_script``/``log_parser`` — fields
#: only the ``SWE-bench/SWE-bench_Verified`` HF dataset (the new image
#: schema, images named ``swebench/sweb.eval.*``) carries. The classic
#: ``princeton-nlp/SWE-bench_Verified`` and a plain instances export do
#: not, so the evaluator (local *or* Modal) dies with ``KeyError:
#: 'image'`` after the patches are already produced. This is the dataset
#: the evaluator is pointed at unless the caller names another; instance
#: *selection* is still the local file, this only supplies the eval
#: schema per id.
EVAL_DATASET = "SWE-bench/SWE-bench_Verified"


def docker_host_env(env: dict | None = None) -> dict:
    """A subprocess env in which docker-py (and so swebench's local
    evaluator) can reach a container engine. On this box the engine is
    rootless podman (D2), which exposes a Docker-compatible API socket
    at ``$XDG_RUNTIME_DIR/podman/podman.sock``. If ``DOCKER_HOST`` is
    already set we respect it; otherwise, when that socket exists (or we
    can start it via ``systemctl --user start podman.socket``), we point
    ``DOCKER_HOST`` at it. swebench 5.0.2's ``--modal`` path is broken
    upstream (C-50), so the local path over this socket is the working
    evaluator."""
    import subprocess as sp
    env = dict(env if env is not None else os.environ)
    if env.get("DOCKER_HOST"):
        return env
    runtime = env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    sock = Path(runtime) / "podman" / "podman.sock"
    if not sock.exists():
        try:
            sp.run(["systemctl", "--user", "start", "podman.socket"],
                   capture_output=True, timeout=15)
        except (OSError, sp.SubprocessError):
            pass
    if sock.exists():
        env["DOCKER_HOST"] = f"unix://{sock}"
    return env
CMD_ENV = "HOBBES_SWEBENCH_CMD"

VERDICTS = ("resolved", "unresolved", "error", "empty-patch", "unjudged")


class VerdictError(RuntimeError):
    """The evaluator could not run or left no report."""


def model_name(arm: str, model: str) -> str:
    """The ``model_name_or_path`` a prediction carries — one per
    (arm, model), because the evaluator names its report after it."""
    return f"hobbes-{arm}-{model or 'default'}".replace("/", "_")


def write_predictions(path: Path, rows: list[dict]) -> Path:
    """``[{instance_id, model_name_or_path, model_patch}]`` — the
    evaluator's input. Empty patches are written too, so the report
    counts them rather than the harness quietly dropping them."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([
        {"instance_id": r["instance_id"], "model_name_or_path": r["model_name_or_path"],
         "model_patch": r.get("model_patch") or ""}
        for r in rows
    ], indent=1))
    return path


def evaluator_command(dataset: str, predictions: Path, run_id: str, instance_ids: list[str],
                      max_workers: int = 1, modal: bool = False) -> list[str]:
    """The subprocess argv. The prefix defaults to a pinned, isolated
    ``swebench`` via uv; ``HOBBES_SWEBENCH_CMD`` replaces it. With
    *modal*, the evaluator builds and runs the instance images on Modal
    (its own ``--modal`` mode; ``MODAL_TOKEN_ID``/``_SECRET`` must be in
    the environment) instead of a local Docker-API engine."""
    # The evaluator runs from run_dir/eval (cwd), so a dataset given as a
    # *file* must be absolute or it will not resolve there — the first
    # full-stage run passed `../verified.jsonl` and every judge died with
    # FileNotFoundError after the patches were already produced. A HF
    # dataset *name* (no such file) is left untouched.
    if os.path.exists(dataset):
        dataset = os.path.abspath(dataset)
    prefix = os.environ.get(CMD_ENV)
    head = shlex.split(prefix) if prefix else [
        "uv", "run", "--no-project", "--with", f"swebench[modal]=={SWEBENCH_VERSION}" if modal
        else f"swebench=={SWEBENCH_VERSION}",  # local path over the podman socket (C-50: --modal is broken upstream)
        "python", "-m", "swebench.harness.run_evaluation",
    ]
    return head + [
        "--dataset_name", dataset, "--predictions_path", str(predictions),
        "--max_workers", str(max_workers), "--run_id", run_id,
        *(["--modal", "true"] if modal else []),
        "--instance_ids", *instance_ids,
    ]


def evaluate(dataset: str, predictions: Path, run_id: str, name: str, instance_ids: list[str],
             cwd: Path, max_workers: int = 1, timeout: float | None = None, modal: bool = False) -> dict[str, str]:
    """Run the evaluator; return ``instance_id -> verdict`` for every id
    asked about (``unjudged`` when the report does not mention one)."""
    cwd = Path(cwd)
    cwd.mkdir(parents=True, exist_ok=True)
    cmd = evaluator_command(dataset, predictions, run_id, instance_ids, max_workers, modal=modal)
    # Local eval needs a container engine; point docker-py at the podman
    # socket unless the caller set DOCKER_HOST or is running on Modal.
    env = os.environ if modal else docker_host_env()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env)
    except FileNotFoundError as exc:
        raise VerdictError(f"evaluator not runnable: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise VerdictError(f"evaluator timed out after {timeout}s") from exc
    (cwd / f"{name}.{run_id}.log").write_text(proc.stdout + proc.stderr)
    report = cwd / f"{name}.{run_id}.json"
    if not report.is_file():
        raise VerdictError(
            f"evaluator exited {proc.returncode} and left no report at {report}: "
            f"{(proc.stderr or proc.stdout).strip()[-400:]}"
        )
    return read_report(report, instance_ids)


def read_report(report: Path, instance_ids: list[str]) -> dict[str, str]:
    """Verdicts from a ``run_evaluation`` report."""
    doc = json.loads(Path(report).read_text())
    out = {i: "unjudged" for i in instance_ids}
    for key, verdict in (("resolved_ids", "resolved"), ("unresolved_ids", "unresolved"),
                         ("error_ids", "error"), ("empty_patch_ids", "empty-patch")):
        for iid in doc.get(key, []) or []:
            if iid in out and (out[iid] == "unjudged" or verdict == "resolved"):
                out[iid] = verdict
    return out
