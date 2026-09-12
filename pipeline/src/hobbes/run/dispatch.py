"""`hobbes dispatch` — Calvin as a harness (ADR-107, `docs/calvin/calvin-harness.md`).

The developer's own session keeps the intent. One implementation task at a time is handed to a *doer* that runs under the whole
environment and is judged at its end:

1. **the knowledge layer** — the repo's ingest, which must be at the parent the session starts from (the gate reads that graph);
2. **`hobbes-session`** — a fresh clone on ``hobbes/<session>``, exec only through the policy proxy, every command in the flight log;
3. **the egress allowlist** — the session on its own internal network, the model endpoint the one host it reaches, every decision
   in the session's ``egress.jsonl``;
4. **the doer** — Claude Code: the host's binary, the owner's subscription token (``CLAUDE_CODE_OAUTH_TOKEN``, passed by name),
   no Bash tool;
5. **`hobbes gate`** on the harvested diff at its parent, the blind-spot map derived from the parent's graph (`gate.derive_map`);
6. **`hobbes verify`** on the same diff, when asked.

Each dispatch writes one file under ``docs/calvin/sessions/`` — the per-session log the harness is validated by — and the full
record beside the flight log. The log's review block is the developer's: whether the gate's verdict was right. Nothing here
merges; the branch waits for the developer.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import secrets as _secrets
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from hobbes import __version__

#: The one host a Claude Code doer needs.
DEFAULT_EGRESS = ("api.anthropic.com",)
DEFAULT_MAX_TURNS = 40
#: Where the per-session logs go, under the repo.
LOG_DIR = Path("docs") / "calvin" / "sessions"
#: The variable Claude Code reads its token from (`claude setup-token`); the Go side's `sandbox.ClaudeTokenEnv`.
TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"
DISPATCH_VERSION = 1
#: The doer's commits say who made them: the verify environment's `hobbes-verify` identity is replaced. The author email is also
#: what `ttt.units` reads to keep a doer's commits out of any training unit (ADR-107's retention amendment).
DISPATCH_EMAIL = "dispatch@hobbes.local"
IDENTITY = ("GIT_AUTHOR_NAME=hobbes-dispatch", f"GIT_AUTHOR_EMAIL={DISPATCH_EMAIL}",
            "GIT_COMMITTER_NAME=hobbes-dispatch", f"GIT_COMMITTER_EMAIL={DISPATCH_EMAIL}")
#: ADR-107's retention amendment, stated on every record and every session file.
RETENTION_RULE = ("The doer's transcript, its reasoning included, is never kept: Claude Code runs with --no-session-persistence, and "
                  "hobbes-session and then dispatch remove any state it left in its HOME (the session dir). A session keeps its output: "
                  "the diff, the envelope's result, the flight and egress logs, the gate and verify records. Recorded sessions are "
                  "evaluation rows, never model training data.")
#: What Claude Code leaves in its HOME beside the doer's output (`sandbox.DoerStateNames`; `.claude.json.*` backups by prefix).
DOER_STATE = (".claude", ".claude.json")
#: The doer's state below a shared directory of its HOME (`sandbox.DoerStatePaths`): Claude Code's MCP logs.
DOER_STATE_PATHS = (".cache/claude-cli-nodejs",)
#: The marker a stored reasoning block carries in a Claude Code transcript.
THINKING_MARKER = '"type":"thinking"'
#: What the log's review block asks, and the verdicts it takes.
REVIEW_VERDICTS = ("right-clear", "right-block", "false-block", "missed")


class DispatchError(RuntimeError):
    """A refusal before any session starts: the ingest not at the parent, no session binary, no token."""


@dataclass
class Dispatch:
    """One task's dispatch, settled before anything runs."""

    repo_root: Path
    task: str
    parent: str
    session_id: str
    sessions_root: Path
    session_bin: str
    egress: list[str] = field(default_factory=lambda: list(DEFAULT_EGRESS))
    model: str | None = None
    max_turns: int = DEFAULT_MAX_TURNS
    partition: list[str] | None = None
    claude_bin: str | None = None
    verify: bool = True
    timeout: float = 3600.0
    log_dir: Path | None = None

    @property
    def session_dir(self) -> Path:
        return self.sessions_root / self.session_id


def new_session_id(now: _dt.datetime | None = None) -> str:
    """A sortable session id in hobbes-session's own form (``S-<utc>-<4 hex>``)."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    return f"S-{now.strftime('%Y%m%dT%H%M%SZ')}-{_secrets.token_hex(2)}"


def key_from(path: Path, name: str) -> str:
    """The value of one ``name=value`` line in the owner's key file — read, never printed. The file may hold names
    `hobbes.bench.secrets` does not know, which that reader refuses whole."""
    for line in Path(path).read_text().splitlines():
        n, sep, v = line.strip().partition("=")
        v = v.strip().strip('"').strip("'")
        if sep and not n.startswith("#") and n.strip() == name and v:
            return v
    raise DispatchError(f"no {name!r} line in the key file")


def token(secrets: Path | None, key_name: str, environ: dict | None = None) -> str:
    """The doer's token: ``$CLAUDE_CODE_OAUTH_TOKEN`` when set, else the key file's *key_name* line."""
    environ = os.environ if environ is None else environ
    if environ.get(TOKEN_ENV):
        return environ[TOKEN_ENV]
    if secrets is None:
        raise DispatchError(f"no token: set ${TOKEN_ENV} (claude setup-token) or pass --secrets with a {key_name!r} line")
    return key_from(secrets, key_name)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _session_bin(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("HOBBES_SESSION_BIN")
    if env:
        return env
    here = Path(__file__).resolve().parents[4] / "go" / "bin" / "hobbes-session"
    if here.is_file():
        return str(here)
    found = shutil.which("hobbes-session")
    if found:
        return found
    raise DispatchError("hobbes-session not found: build go/bin/hobbes-session, set $HOBBES_SESSION_BIN or pass --session-bin")


def load_graph(repo_root: Path) -> tuple[dict, dict, Path, Path | None]:
    """The repo's ingest: graph, tests and their paths."""
    derived = Path(repo_root) / ".hobbes" / "derived"
    gpath, tpath = derived / "graph.json", derived / "tests.json"
    if not gpath.is_file():
        raise DispatchError(f"no ingest at {derived}: `uv run hobbes ingest` first — the gate reads the parent's graph")
    graph = json.loads(gpath.read_text())
    tests = json.loads(tpath.read_text()) if tpath.is_file() else {"tests": []}
    return graph, tests, gpath, tpath if tpath.is_file() else None


def prepare(repo_root: Path, task: str, *, ref: str = "HEAD", model: str | None = None, max_turns: int = DEFAULT_MAX_TURNS,
            egress: list[str] | None = None, partition: list[str] | None = None, claude_bin: str | None = None,
            session_bin: str | None = None, sessions_root: Path | None = None, verify: bool = True, timeout: float = 3600.0,
            log_dir: Path | None = None, session_id: str | None = None) -> Dispatch:
    """Settle a dispatch and refuse what would fail later: an empty task, a ref that names no commit, an ingest at another SHA
    (the gate would refuse the graph after the session had run), no session binary."""
    repo_root = Path(repo_root).resolve()
    if not task.strip():
        raise DispatchError("the task is empty")
    r = _git(repo_root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
    parent = r.stdout.strip()
    if r.returncode or not parent:
        raise DispatchError(f"{ref!r} names no commit of {repo_root}")
    graph = load_graph(repo_root)[0]
    if graph.get("sha") != parent:
        raise DispatchError(f"the ingest is at {str(graph.get('sha'))[:12]}, the parent is {parent[:12]}: `uv run hobbes ingest` "
                            "first — the gate reads the parent's graph")
    return Dispatch(repo_root=repo_root, task=task, parent=parent, session_id=session_id or new_session_id(),
                    sessions_root=Path(sessions_root) if sessions_root else Path.home() / ".hobbes" / "sessions",
                    session_bin=_session_bin(session_bin), egress=list(egress or DEFAULT_EGRESS), model=model, max_turns=max_turns,
                    partition=partition, claude_bin=claude_bin, verify=verify, timeout=timeout, log_dir=log_dir)


def brief(d: Dispatch, notes: list[str]) -> str:
    """The doer's prompt: the task as given, then how the session works — the tool names as the session serves them, the route,
    the commit, the report."""
    lines = [d.task.rstrip(), "", "---", "How this session works (hobbes dispatch, ADR-107):",
             f"- You are in a fresh clone of {d.repo_root.name} at {d.parent[:12]}, on the branch `hobbes/{d.session_id}`, inside a "
             "sandbox. Edit files under /work.",
             "- There is no Bash tool. Run shell commands through `mcp__hobbes__exec`: it is policy-checked and every command is "
             "logged. A denied command is the policy's answer, not a fault to work around.",
             "- The knowledge tools answer from this repo's ingest at the parent. CLAUDE.md calls them `mcp__hobbes-knowledge__*`; "
             "here they are `mcp__hobbes__who_calls`, `mcp__hobbes__tests_guarding`, `mcp__hobbes__graph_neighborhood`, "
             "`mcp__hobbes__get_module_doc`, `mcp__hobbes__list_invariants` and `mcp__hobbes__list_blind_spots`.",
             "- The network reaches the model endpoint and nothing else: nothing installs, nothing is fetched.",
             "- Commit your work with `git add` and `git commit` through exec when you are done; what is left uncommitted is "
             "committed for you at exit. Never push.",
             "- End with a few lines: what you changed, and what you ran to check it."]
    if d.partition:
        lines.append("- Write only these files (the gate checks it): " + ", ".join(d.partition) + ".")
    lines += [f"- {n}" for n in notes]
    return "\n".join(lines) + "\n"


def session_argv(d: Dispatch, brief_path: Path, env) -> list[str]:
    """The ``hobbes-session start`` argv — no secret in it: the token rides the environment and is passed by name."""
    from hobbes.derive import harness
    from hobbes.extract import containment

    bins = sorted({"/work/" + os.path.dirname(os.path.join(rel, interp)).lstrip("/") for rel, interp in env.python.items()})
    argv = [d.session_bin, "start", "--repo", str(d.repo_root), "--ref", d.parent, "--role", "implementer",
            "--session", d.session_id, "--sessions", str(d.sessions_root), "--task-file", str(brief_path),
            "--box", str(harness.CALVIN_BOX), "--escalation-timeout", "5s", "--commit-on-exit", "--max-turns", str(d.max_turns),
            "--path", ":".join(bins + [containment.CONTAINER_PATH]), "--pre", harness.pre_command(env)]
    for kv in [kv for kv in env.env if not kv.startswith("GIT_")] + list(IDENTITY):
        argv += ["--env", kv]
    for p in list(env.ro) + list(env.ro_cache):
        argv += ["--mount", p]
    if d.model:
        argv += ["--model", d.model]
    if d.claude_bin:
        argv += ["--claude-bin", d.claude_bin]
    for h in d.egress:
        argv += ["--egress", h]
    return argv


def _environment(d: Dispatch):
    from hobbes.derive import harness
    return harness.environment(d.repo_root, d.repo_root, container_root="/work", gocache=f"/sessions/{d.session_id}/go-build")


def _write_brief(d: Dispatch, env) -> Path:
    d.session_dir.mkdir(parents=True, exist_ok=True)
    path = d.session_dir / "brief.md"
    path.write_text(brief(d, env.notes))
    return path


def dry_run(d: Dispatch) -> str:
    """The brief and the argv, then hobbes-session's own dry run of them: the whole stack shown, nothing run, nothing logged."""
    env = _environment(d)
    bpath = _write_brief(d, env)
    argv = session_argv(d, bpath, env)
    plan = subprocess.run(argv + ["--dry-run"], capture_output=True, text=True)
    return (f"brief: {bpath}\n\n{bpath.read_text()}\nhobbes-session argv:\n  " + " ".join(argv) + "\n\n"
            + (plan.stdout or "") + (plan.stderr if plan.returncode else ""))


def parse_envelope(stdout: str) -> dict:
    """Claude Code's ``--output-format json`` result (turns, cost, the final text), or ``{}``: the last JSON object on stdout."""
    text = stdout.strip()
    for cand in [text] + [ln for ln in reversed(text.splitlines()) if ln.lstrip().startswith("{")]:
        try:
            obj = json.loads(cand)
        except ValueError:
            continue
        if isinstance(obj, dict):
            # `subtype` can read "success" beside an API error (a 401 does), so the error fields ride along
            keep = ("type", "subtype", "is_error", "api_error_status", "terminal_reason", "num_turns", "total_cost_usd", "duration_ms",
                    "session_id", "result")
            out = {k: obj.get(k) for k in keep if k in obj}
            if isinstance(out.get("result"), str) and len(out["result"]) > 4000:
                out["result"] = out["result"][:4000] + " …"
            return out
    return {}


def summarize_flight(path: Path) -> dict:
    """The flight log's exec decisions: counts by decision, and the commands denied or escalated (first ten each)."""
    out: dict = {"events": 0, "by_decision": {}, "denied": [], "escalated": [], "context_faults": 0}
    if not Path(path).is_file():
        out["missing"] = True
        return out
    for line in Path(path).read_text().splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        out["events"] += 1
        dec = str(ev.get("decision") or "none")
        out["by_decision"][dec] = out["by_decision"].get(dec, 0) + 1
        cmd = " ".join(ev.get("argv") or [])[:160]
        if dec == "deny" and len(out["denied"]) < 10:
            out["denied"].append(cmd)
        if dec == "escalate" and len(out["escalated"]) < 10:
            res = (ev.get("escalation") or {}).get("resolution")
            out["escalated"].append(cmd + (f" → {res}" if res else ""))
        out["context_faults"] += bool(ev.get("context_fault"))
    return out


def summarize_egress(path: Path) -> dict:
    """The egress log: whether the proxy listened, the allowlist, tunnels opened and refusals per target (`egress.Summarize`)."""
    out: dict = {"listened": False, "allow": [], "opened": {}, "refused": {}, "errors": 0}
    if not Path(path).is_file():
        out["missing"] = True
        return out
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            out["errors"] += 1
            continue
        ev, target = rec.get("event"), rec.get("target")
        if ev == "listen":
            out["listened"], out["allow"] = True, rec.get("allow") or []
        elif ev == "connect":
            out["opened"][target] = out["opened"].get(target, 0) + 1
        elif ev == "refuse":
            out["refused"][target] = out["refused"].get(target, 0) + 1
        elif ev == "close" and rec.get("error"):
            out["errors"] += 1
    return out


def purge_doer_state(session_dir: Path) -> list[str]:
    """Remove the doer's own state from *session_dir* (`DOER_STATE` and ``.claude.json.*``), as hobbes-session already does at
    exit; returns the names removed. The second pass is deliberate: a record must not depend on the launcher's build."""
    session_dir = Path(session_dir)
    removed = []
    for p in sorted(session_dir.iterdir()) if session_dir.is_dir() else []:
        if p.name in DOER_STATE or p.name.startswith(".claude.json."):
            shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()
            removed.append(p.name)
    for rel in DOER_STATE_PATHS:
        p = session_dir / rel
        if p.is_symlink() or p.exists():
            shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()
            removed.append(rel)
            try:
                p.parent.rmdir()  # only when nothing else is left in it
            except OSError:
                pass
    return sorted(removed)


def reasoning_left(session_dir: Path) -> list[str]:
    """Files under *session_dir* that still carry a stored reasoning block — expected none; the record says which if any."""
    out = []
    for p in sorted(Path(session_dir).rglob("*")) if Path(session_dir).is_dir() else []:
        if p.is_file() and not p.is_symlink() and "worktree" not in p.relative_to(session_dir).parts:
            try:
                if THINKING_MARKER in p.read_text(errors="replace"):
                    out.append(str(p.relative_to(session_dir)))
            except OSError:
                continue
    return out


def _doer_version(claude_bin: str | None) -> str | None:
    try:
        r = subprocess.run([claude_bin or "claude", "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() or None if r.returncode == 0 else None


def _cleanup_route(session_id: str) -> None:
    """After a killed session: the proxy container and the session's network (whose forced removal takes the session container)."""
    sid = session_id.lower()
    subprocess.run(["podman", "rm", "-f", "-t", "0", f"hobbes-egress-{sid}"], capture_output=True)
    subprocess.run(["podman", "network", "rm", "-f", f"hobbes-int-{sid}"], capture_output=True)


def gate_patch(d: Dispatch, patch: str) -> dict:
    """`hobbes gate` over the harvested diff at the parent, the map derived from the parent's graph over the diff's files (or the
    partition) and a created file's neighbours; the record written beside the flight log."""
    from hobbes.derive import gate as gt
    from hobbes.derive import template as T

    graph, tests, gpath, tpath = load_graph(d.repo_root)
    bmap = gt.derive_map(graph, gt.map_files(patch, d.repo_root, d.parent, d.partition), d.repo_root, d.parent)
    rec = gt.gate(patch, d.parent, d.repo_root, T.Ledger(graph, tests), inputs=gt.input_hashes(patch, gpath, tpath, d.partition, bmap),
                  partition=d.partition, partition_source="dispatch" if d.partition else None, bmap=bmap)
    (d.session_dir / "gate.json").write_text(gt.dumps(rec))
    return {"verdict": rec["verdict"], "blocking": rec["blocking"], "counts": rec["counts"], "record_hash": rec["record_hash"],
            "gate_version": rec["gate_version"], "grounder_version": rec["grounder_version"],
            "partition": {k: rec["partition"].get(k) for k in ("checked", "size", "outside", "reached") if k in rec["partition"]},
            "rows": [{k: r.get(k) for k in ("class", "path", "line", "term", "reason")} for r in rec["rows"]],
            "map": {"files": len(bmap["files"]), "created": bmap["created"], "fraction_uncaptured": bmap["fraction_uncaptured"]},
            "integrity_ok": rec["integrity"].get("post_agrees") is not False, "record": str(d.session_dir / "gate.json")}


def verify_patch(d: Dispatch, patch: str) -> dict:
    """`hobbes verify` over the same diff at the parent, contained; any refusal is recorded, never raised."""
    from hobbes.derive import harness
    from hobbes.derive import template as T

    graph, tests, _, _ = load_graph(d.repo_root)
    try:
        rec = harness.verify(d.repo_root, d.parent, patch, T.Ledger(graph, tests), d.repo_root, out=d.session_dir / "verify.json")
    except Exception as exc:  # a refusal (no containment) or an instrument fault: the dispatch still logs what it has
        return {"verdict": "error", "error": f"{type(exc).__name__}: {exc}"}
    return {"verdict": rec.get("verdict"), "applies": rec.get("applies"), "summary": rec.get("summary"),
            "tests": len(rec.get("tests", [])), "regressions": len(rec.get("regressions", [])), "build_summary": rec.get("build_summary"),
            "record": str(d.session_dir / "verify.json")}


def dispatch(d: Dispatch, tok: str) -> dict:
    """Run one dispatch end to end and return its record; the per-session log is written as the last step."""
    from hobbes.derive import harness
    from hobbes.bench.workspace import candidate_patch

    env = _environment(d)
    bpath = _write_brief(d, env)
    argv = session_argv(d, bpath, env)
    rec: dict = {"dispatch_version": DISPATCH_VERSION, "hobbes_version": __version__, "session": d.session_id, "repo": d.repo_root.name,
                 "parent": d.parent, "date": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d"),
                 "task": {"first_line": d.task.strip().splitlines()[0][:200], "sha256": hashlib.sha256(d.task.encode()).hexdigest(),
                          "brief": str(bpath)},
                 "doer": {"kind": "claude-code", "binary": d.claude_bin, "version": _doer_version(d.claude_bin), "model": d.model,
                          "max_turns": d.max_turns},
                 "egress_allow": list(d.egress), "partition": d.partition, "argv": argv,
                 "repo_dirty": bool(_git(d.repo_root, "status", "--porcelain", "--untracked-files=no").stdout.strip())}
    t0 = time.monotonic()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=d.timeout, env={**os.environ, TOKEN_ENV: tok})
        rec["session_rc"] = proc.returncode
        rec["envelope"] = parse_envelope(proc.stdout)
        rec["session_stderr_tail"] = proc.stderr[-2000:]
        (d.session_dir / "session.log").write_text(proc.stdout + proc.stderr)
    except subprocess.TimeoutExpired:
        rec["session_rc"] = None
        rec["envelope"] = {}
        rec["error"] = f"the session was stopped after {d.timeout:.0f}s"
        _cleanup_route(d.session_id)
    rec["wall_s"] = round(time.monotonic() - t0, 1)
    removed = purge_doer_state(d.session_dir)
    rec["retention"] = {"doer_state_removed_by_dispatch": removed, "reasoning_left": reasoning_left(d.session_dir),
                        "launcher_removed": "retention: removed the doer's own state" in rec.get("session_stderr_tail", ""),
                        "rule": RETENTION_RULE}
    rec["flight"] = summarize_flight(d.session_dir / "flight.jsonl")
    rec["egress"] = summarize_egress(d.session_dir / "egress.jsonl")

    branch = f"hobbes/{d.session_id}"
    has = _git(d.repo_root, "rev-parse", "--verify", "-q", f"refs/heads/{branch}").returncode == 0
    rec["branch"] = branch if has else None
    patch = candidate_patch(d.repo_root, d.parent, branch) if has else ""
    links = {rel for rel, _ in env.links}
    patch = "".join(text for path, text in harness.split_patch(patch) if path not in links)
    rec["commits"] = int(_git(d.repo_root, "rev-list", "--count", f"{d.parent}..{branch}").stdout.strip() or 0) if has else 0
    rec["files"] = [p for p, _ in harness.split_patch(patch)]
    rec["patch_sha256"] = hashlib.sha256(patch.encode()).hexdigest() if patch else None
    (d.session_dir / "dispatch.diff").write_text(patch)
    rec["gate"] = gate_patch(d, patch)
    rec["verify"] = verify_patch(d, patch) if d.verify and patch else {"verdict": "skipped" if not d.verify else "empty"}
    rec["log"] = str(write_log(d, rec))
    (d.session_dir / "dispatch.json").write_text(json.dumps(rec, indent=1, sort_keys=True))
    return rec


def _counts(m: dict) -> str:
    return ", ".join(f"`{k}`×{v}" for k, v in sorted(m.items())) or "none"


def render_log(rec: dict) -> str:
    """The per-session log: what ran, under what, what the gate and verify said — and the review block the developer fills."""
    g, v, e, f, env = rec["gate"], rec["verify"], rec["egress"], rec["flight"], rec.get("envelope") or {}
    doer = rec["doer"]
    cost = env.get("total_cost_usd")
    lines = [f"# Harness session `{rec['session']}`", "",
             f"*{rec['date']} · `hobbes dispatch` v{rec['dispatch_version']} · Hobbes {rec['hobbes_version']} · ADR-107.* "
             "The record above the review block is written by the harness; the review block is the developer's.", "",
             f"- **Task:** {rec['task']['first_line']} (brief `{rec['task']['brief']}`, task sha256 `{rec['task']['sha256'][:12]}`)",
             f"- **Parent:** `{rec['parent'][:12]}` of `{rec['repo']}`" + (" — the working tree had uncommitted changes the session did "
                                                                            "not see" if rec.get("repo_dirty") else ""),
             f"- **Doer:** {doer.get('version') or 'Claude Code'}; model {doer.get('model') or 'the default'}; "
             f"turns {env.get('num_turns', '—')} of {doer.get('max_turns')}; result `{env.get('subtype', '—')}`"
             + (f" **with an error** (API status {env.get('api_error_status')}, `{env.get('terminal_reason')}`)" if env.get("is_error") else "")
             + (f"; reported cost ${cost:.4f} (the envelope's figure, on the subscription)" if isinstance(cost, (int, float)) else "")
             + f"; wall {rec.get('wall_s')} s; session exit {rec.get('session_rc')}" + (f" — {rec['error']}" if rec.get("error") else ""),
             f"- **Egress:** " + ("the proxy never listened" if not e.get("listened") else
                                  f"allow {', '.join(e['allow'])}; opened {_counts(e['opened'])}; refused {_counts(e['refused'])}")
             + (f"; {e['errors']} error(s)" if e.get("errors") else ""),
             f"- **Policy:** {f['events']} exec decision(s) — {_counts(f['by_decision'])}"
             + (f"; denied: " + "; ".join(f"`{c}`" for c in f["denied"]) if f["denied"] else "")
             + (f"; escalated: " + "; ".join(f"`{c}`" for c in f["escalated"]) if f["escalated"] else "")
             + ("; no flight log" if f.get("missing") else ""),
             f"- **Branch:** " + (f"`{rec['branch']}`, {rec['commits']} commit(s); files: " + (", ".join(f"`{p}`" for p in rec["files"]) or "none")
                                  if rec.get("branch") else "none harvested — the session left no commit"),
             f"- **Gate:** **{g['verdict']}** at `{rec['parent'][:12]}` (gate v{g['gate_version']}, grounder v{g['grounder_version']}, "
             f"record `{g['record_hash'][:12]}`)" + (f" — blocking: {', '.join(g['blocking'])}" if g["blocking"] else "")
             + f"; unknown {g['counts'].get('unknown', 0)}; map over {g['map']['files']} file(s), "
             f"{g['map']['fraction_uncaptured']:.1%} of their lines uncaptured"
             + ("; partition checked" + (f", outside: {', '.join(g['partition']['outside'])}" if g['partition'].get('outside') else "")
                if g["partition"].get("checked") else "; partition not checked")
             + ("" if g["integrity_ok"] else "; WARNING: the gate read the diff differently from `git apply`")]
    for r in g["rows"][:20]:
        lines.append(f"  - `{r['class']}` {r['path']}:{r['line']} `{r['term']}`" + (f" — {r['reason']}" if r.get("reason") else ""))
    if len(g["rows"]) > 20:
        lines.append(f"  - … {len(g['rows']) - 20} more in `{g['record']}`")
    ret = rec.get("retention") or {}
    lines.append("- **Retention:** the doer's transcript and reasoning are not stored; this file and the session dir keep its output "
                 "only. Recorded sessions are evaluation rows, never model training data."
                 + ("" if not ret.get("reasoning_left") else f" WARNING: reasoning found in {', '.join(ret['reasoning_left'])}"))
    lines.append(f"- **Verify:** {v.get('verdict')}"
                 + (f"; tests {v['tests']}, regressions {v['regressions']}; {v.get('summary')}" if "tests" in v else "")
                 + (f"; build {v['build_summary']}" if v.get("build_summary") else "") + (f" — {v['error']}" if v.get("error") else ""))
    if env.get("result"):
        lines += ["", "**The doer's closing words:**", ""] + ["> " + ln for ln in str(env["result"]).strip().splitlines()[:30]]
    lines += ["", "## Review", "",
              "*The developer's, after reading the diff. `gate`: " + " | ".join(f"`{x}`" for x in REVIEW_VERDICTS)
              + " — was the verdict right; `missed` is an error the gate's classes cover that it let through. `outcome`: merged, "
              "reworked, or discarded.*", "",
              "- gate: pending", "- outcome: pending", "- notes:", ""]
    return "\n".join(lines)


def write_log(d: Dispatch, rec: dict) -> Path:
    """One file per session under the log dir, named by the session id (so they sort by time)."""
    out = Path(d.log_dir) if d.log_dir else d.repo_root / LOG_DIR
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{d.session_id}.md"
    path.write_text(render_log(rec))
    return path


def summary_line(rec: dict) -> str:
    g, v = rec["gate"], rec["verify"]
    return (f"dispatch {rec['session']} @ {rec['parent'][:12]}: gate {g['verdict']}"
            + (f" ({', '.join(g['blocking'])})" if g["blocking"] else "") + f"; verify {v.get('verdict')}; "
            f"files {len(rec['files'])}; egress refused {sum(rec['egress']['refused'].values())}; log {rec['log']}")


def exit_code(rec: dict) -> int:
    """0 clear and verify not failing; 1 blocked or verify failing; 3 the session did not finish and left nothing."""
    if rec.get("session_rc") is None or (rec.get("session_rc") and not rec.get("branch")):
        return 3
    if rec["gate"]["verdict"] == "blocked" or rec["verify"].get("verdict") == "fail" or rec["verify"].get("regressions"):
        return 1
    return 0
