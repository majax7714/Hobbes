"""The staged run — a proposal to a verified patch (harness restructure, ADR-059).

The owner's structure: single-use **derived-context** agents, one alive
at a time, each agent's job arriving as its short memory (the previous
agent's handoff). One does its job and sends to the next; some agents'
whole job is to feed the next agent's short memory. The stages:

1. **plan** — a *planner* session (read-only) breaks the proposal down
   over the repo's derived context and hands off the **requirements**
   (what must become true, each with its owning file — the planner is
   the requirement-decomposer, ADR-084/085) plus the files, symbols and
   tests the change touches. Its handoff becomes the seeds — this is the
   generative layer C-36 always said would sit *above* the lexical seeds,
   never inside them.
2. (derive) — ``hobbes plan`` runs deterministically on the planner's
   seeds; ``seed_source`` records whether they came from the planner or,
   when the planner resolved nothing, from the lexical fallback. Then
   **coverage** (:mod:`hobbes.run.coverage`): every requirement must
   have an owning unit; one bounded re-plan, then a plan error at plan
   cost (``strict``) or assignment to the seed unit, said so (``assign``).
   On a covered plan each implementer's brief carries its owned
   requirements as its task and the proposal is absent by design.
3. **review** (opt-in) — a *reviewer* session judges the change-spec;
   ``amend`` re-plans once.
4. **implement** — one *implementer* per unit, in contract order, each
   cloned at the **current** ``hobbes/<task>`` head so a consumer sees
   its owner's commit; the branch is integrated immediately after
   harvest, a conflict recorded at the cut.
5. **verify** — a *verifier* session over the integrated head runs the
   planner's named tests and hands off ``pass``/``fail``.
6. **rework** (opt-in) — on ``fail``, one implementer over the unit(s)
   the verifier named, then verify once more.

Everything a session does is its brief (standing context + inbox) and
its handoff (short memory forward); nothing is a chat transcript. The
whole flow is quota-free to exercise: ``dry_run`` spawns nothing and the
suite drives it with the stand-in session binary.
"""

from __future__ import annotations

import re
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from hobbes import artifacts
from hobbes.derive import derive_plan, write_spec
from hobbes.derive.changespec import task_id
from hobbes.derive.impact import build_lookup, resolve_terms
from hobbes.run import agents, mail, parallel
from hobbes.run.coverage import (
    COVERAGE_MODES, PlanCoverageError, assign_requirements, imperatives_unmentioned,
    in_interior, requirements_from_handoff, unit_task,
)
from hobbes.run.handoff import parse_handoff
from hobbes.run.orchestrate import (
    handoff_status,
    RunError, UnitRecord, integrate, loss, order_units, read_branch,
    read_flight, review_integration, _branch_exists, _git,
)
from hobbes.run.roles import ensure_role_policies
from hobbes.run.spec import plan_dir

DEFAULT_STAGES = ("plan", "implement", "verify")
ALL_STAGES = ("plan", "review", "implement", "verify", "rework")


#: How many lexically related modules the planner's map lists (ADR-072).
#: Measured on the 5-fresh graphs: at 80 every gold file of every
#: instance is in the list (worst rank 71); at 60, sympy's was not.
MAP_RELATED = 80
#: A module's score is its best MAP_TOP_TERMS term weights in full plus
#: MAP_REST_WEIGHT of the rest — so a giant module matching many weak
#: terms cannot outrank the one module whose symbol the proposal names
#: (sympy's `polylog`), while breadth still counts a little. Declared
#: guesses (ADR-072), measured on the same five graphs.
MAP_TOP_TERMS = 5
MAP_REST_WEIGHT = 0.25
#: How many package-tree lines the map carries before it says it cut.
MAP_TREE_LINES = 400


def _tokens(text: str) -> set[str]:
    """Lowercased identifier-ish tokens: split on non-alphanumerics and
    camelCase, stopwords and short words dropped (the C-36 term shape)."""
    from hobbes.derive.impact import STOPWORDS
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text or "")
    return {t for t in re.split(r"[^A-Za-z0-9]+", spaced.lower())
            if len(t) >= 3 and t not in STOPWORDS and not t.isdigit()}


def related_modules(graph: dict, proposal: str, limit: int = MAP_RELATED) -> list[tuple[dict, list[str]]]:
    """Modules ranked by lexical overlap with *proposal*: tokens of the
    module's id/path and of its symbol names against the proposal's
    tokens, each term weighted by its rarity across modules (a term
    that names one module — `polylog` — outweighs one that names
    hundreds — `function`), a path hit counting double. Returns
    ``[(node, matched_terms)]`` for modules with at least one match,
    best first, the terms in weight order (ADR-072). A lexical match is
    a hint, not a location — the C-36 limit applies and is said in the map."""
    import math
    terms = _tokens(proposal)
    if not terms:
        return []
    by_module: dict[str, set[str]] = {}
    for sym in graph.get("symbols", []) or []:
        if sym.get("module") and sym.get("name"):
            by_module.setdefault(sym["module"], set()).update(_tokens(sym["name"]))
    modules = [n for n in graph.get("nodes", []) if n.get("kind") in ("module", "package") and n.get("path")]
    own = {n["id"]: _tokens(n["id"]) | _tokens(n["path"]) for n in modules}
    df: dict[str, int] = {}
    for n in modules:
        for t in (own[n["id"]] | by_module.get(n["id"], set())) & terms:
            df[t] = df.get(t, 0) + 1
    weight = {t: 1.0 / (1.0 + math.log(df[t])) for t in df}
    ranked = []
    for n in modules:
        path_hits = own[n["id"]] & terms
        sym_hits = by_module.get(n["id"], set()) & terms
        hits = path_hits | sym_hits
        if not hits:
            continue
        ws = sorted((weight[t] * (2.0 if t in path_hits else 1.0) for t in hits), reverse=True)
        score = sum(ws[:MAP_TOP_TERMS]) + MAP_REST_WEIGHT * sum(ws[MAP_TOP_TERMS:])
        ranked.append((score, n, sorted(hits, key=lambda t: -weight[t])))
    ranked.sort(key=lambda r: (-r[0], r[1]["path"]))
    return [(n, hits) for _, n, hits in ranked[:limit]]


def package_tree(graph: dict, depth: int = 3, limit: int = MAP_TREE_LINES) -> list[str]:
    """Every directory holding modules, to *depth*, with counts — the
    whole repo's shape in a few hundred lines, whatever its size."""
    counts: dict[str, int] = {}
    for n in graph.get("nodes", []):
        if n.get("kind") not in ("module", "package") or not n.get("path"):
            continue
        parts = n["path"].split("/")[:-1]
        for d in range(1, min(len(parts), depth) + 1):
            key = "/".join(parts[:d]) + "/"
            counts[key] = counts.get(key, 0) + 1
    lines = [f"- {d} ({c} module{'s' if c != 1 else ''})" for d, c in sorted(counts.items())]
    if len(lines) > limit:
        lines = lines[:limit] + [f"- … +{len(lines) - limit} more directories not shown"]
    return lines


def repo_context(graph: dict, proposal: str = "", limit: int = MAP_RELATED) -> str:
    """The planner's standing context: the capture line, the modules
    lexically related to the proposal (ADR-072 — the map used to be the
    first *limit* modules alphabetically, which put the right package in
    front of the planner in 1 of 5 benchmark instances), and the package
    tree of the whole repo — enough to name where a change lands,
    deliberately not the source (the planner reads for that)."""
    lines = ["# Repository map (for planning — read the files for detail)", ""]
    langs = ", ".join(graph.get("languages", [])) or "unknown"
    lines.append(f"Languages: {langs}. This is a graph-derived map, not the source.")
    cov = graph.get("resolution_coverage", []) or []
    sites = sum(r.get("sites", 0) for r in cov)
    unresolved = sum(r.get("unresolved", 0) for r in cov)
    if sites:
        pct = round(100.0 * (sites - unresolved) / sites, 1)
        lines.append(f"Capture: {pct}% of {sites:,} detected call sites resolved — "
                     f"{unresolved:,} are unresolved (calls Hobbes cannot see, not absent).")
    total = sum(1 for n in graph.get("nodes", []) if n.get("kind") in ("module", "package") and n.get("path"))
    lines.append("")
    related = related_modules(graph, proposal, limit)
    lines.append(f"## Modules related to the proposal by name (lexical match, C-36 — a hint, not a location; "
                 f"{len(related)} of {total})")
    for n, hits in related:
        lines.append(f"- `{n['id']}` — {n['path']}  (matches: {', '.join(hits)})")
    if not related:
        lines.append("- none: no proposal term matches a module path or symbol name — use the package tree and search_file")
    lines.append("")
    lines.append(f"## Package tree (every directory with modules; {total} modules in all)")
    lines += package_tree(graph)
    lines.append("")
    lines.append("Use search_file / read_file and the knowledge tools (graph_neighborhood, who_calls, "
                 "tests_guarding) to confirm a location before naming it.")
    lines.append("")
    return "\n".join(lines)


def planner_brief(proposal: str, graph: dict, orchestrator_note: str = "") -> str:
    """The planner's prompt: the proposal, the repo map, and the exact
    handoff shape the orchestrator will parse. The planner is the
    **requirement-decomposer** (ADR-084/085): it is the one role that
    reads the whole request, and its handoff must say what must become
    true — each requirement with the file that owns it — not only where
    the change goes. *orchestrator_note* is the re-plan's short memory:
    the requirements the first handoff left without an owner."""
    return "\n".join([
        "You are a single-use planner. You do not change any files. You are the ONLY agent",
        "that reads the whole request below: the implementers after you each see only the",
        "requirements you hand them, never this text. Your job is to (1) break the request",
        "into the REQUIREMENTS that must become true, (2) name the file that owns each one,",
        "and (3) hand that off. A requirement you leave out is never implemented by anyone.",
        "",
        "## Proposal",
        proposal.strip(),
        "",
        *([f"## From the orchestrator (your previous handoff, re-planned once)", orchestrator_note, ""]
          if orchestrator_note else []),
        "## How to work",
        "- Read the proposal twice. List every behavior it asks for — a value it names, a",
        "  term to remove, an error to raise, an option to add — as its own requirement, in",
        "  the proposal's own words. Two requirements stated in one sentence are two lines.",
        "- Use the knowledge tools (graph_neighborhood, who_calls, tests_guarding) and read",
        "  the relevant files to find the file that owns each requirement. Name real files.",
        "- Do not describe a fix in prose only. Your deliverable is the handoff below.",
        "",
        "## Your handoff (call reflect with kind \"handoff\" and exactly this shape)",
        "requirements: one per line, `R1: <what must become true, in the proposal's words> -> <owning file>`",
        "files: at most 6 repo-relative paths — the ones the change MUST edit, comma-separated",
        "symbols: at most 5 functions/classes to change (optional)",
        "tests: at most 5 test files or ids that guard this behavior, comma-separated",
        "approach: two or three sentences on the fix",
        "risks: one or two sentences on what you are unsure of",
        "",
        "Every requirement needs an owning file — the implementers are spawned per file set,",
        "and a requirement with no owner is a plan error that stops the run. Keep the whole",
        "handoff under 30 lines; a long one is cut at the model's output limit and lost",
        "entirely (ADR-070).",
        "",
        repo_context(graph, proposal),
    ])


def spawn(session_bin: str | None, repo: Path, role: str, agent_dir: Path, session: str,
          brief_path: Path, sessions_root: Path, extra_args: list[str], ref: str | None,
          dry_run: bool) -> subprocess.CompletedProcess | None:
    """Start one single-use session; returns the completed process (or
    None on a dry run with no binary). The caller blocks on it; in a
    staged run several may be alive in one wave (ADR-063), never two of
    the same unit. The
    process carries ``wall_seconds`` (measured from outside, so it is
    observed even when the session emits no envelope) and its output is
    the agent's ``session.log`` — every stage's meter, whatever the role."""
    cmd = [session_bin or "hobbes-session", "start", "--repo", str(repo), "--role", role,
           "--agent-dir", str(agent_dir), "--session", session,
           "--sessions", str(sessions_root), "--task-file", str(brief_path)]
    if ref:
        cmd += ["--ref", ref]
    if dry_run:
        cmd.append("--dry-run")
    cmd += list(extra_args or [])
    (agent_dir / "spawn.txt").write_text(" ".join(cmd) + "\n")
    if dry_run and not session_bin:
        return None
    # Session names are deterministic (task id + role/unit), so a previous
    # run of the same proposal leaves a session dir behind and the clone
    # refuses a non-empty worktree (the full-stage probe's U3). The old
    # dir's record was captured by its own run; clear it.
    stale = Path(sessions_root) / session
    if stale.is_dir() and not dry_run:
        shutil.rmtree(stale, ignore_errors=True)
    started = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    proc.wall_seconds = round(time.monotonic() - started, 3)  # type: ignore[attr-defined]
    (agent_dir / "session.log").write_text(proc.stdout + proc.stderr)
    # A rework reuses the unit's agent dir; the per-session copy keeps
    # the first pass's meter readable after the second overwrites session.log.
    (agent_dir / f"{session}.log").write_text(proc.stdout + proc.stderr)
    return proc


def _wall(proc) -> float | None:
    return getattr(proc, "wall_seconds", None) if proc else None


def _head_sha(repo: Path, target: str, base: str) -> str:
    """The commit at *target* (the running integration branch), falling
    back to *base* — passed as ``--ref`` so a --local clone reaches it by
    object, not by a branch name it did not copy."""
    code, sha = _git(repo, "rev-parse", "--verify", "-q", target)
    return sha.strip() if code == 0 and sha.strip() else base


def _resolve_binaries(session_bin, sessions_root, dry_run):
    session_bin = session_bin or os.environ.get("HOBBES_SESSION_BIN") or shutil.which("hobbes-session")
    if not session_bin and not dry_run:
        raise RunError("hobbes-session not found; build go/bin/hobbes-session or set HOBBES_SESSION_BIN")
    sessions_root = Path(sessions_root or os.environ.get("HOBBES_SESSIONS") or Path.home() / ".hobbes" / "sessions")
    return session_bin, sessions_root


def run_planner(repo: Path, proposal: str, graph: dict, pdir: Path, session_bin, sessions_root,
                extra_args, brief_limit, dry_run, planner_args: list[str] | None = None,
                attempt: int = 1, orchestrator_note: str = "") -> dict:
    """Spawn the planner and return its parsed handoff plus the raw text
    and the misses when its named files did not resolve. *planner_args*
    follow *extra_args* on the command line, so a per-role turn/token
    budget overrides the run's (the weight belongs to the planner,
    ADR-084 §4). *attempt* 2 is the one bounded re-plan, its inbox the
    *orchestrator_note* naming what the first handoff left unowned."""
    name = "planner" if attempt == 1 else f"planner-{attempt}"
    directory = agents.agent_dir(pdir, name)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / mail.INBOX).touch()
    if orchestrator_note:
        mail.post(directory, "orchestrator", orchestrator_note, kind="handoff")
    (directory / "policy.yaml").write_text(json.dumps(
        {"version": 1, "scope": "agent", "default": "escalate",
         "rules": [{"pattern": "git commit*", "decision": "deny", "reason": "the planner writes nothing"},
                   {"pattern": "git add *", "decision": "deny", "reason": "the planner writes nothing"}]}))
    brief = planner_brief(proposal, graph, orchestrator_note)
    if brief_limit and len(brief) > brief_limit:
        brief = brief[:brief_limit] + "\n… (repo map truncated to the brief limit; use the knowledge tools)\n"
    (directory / "brief.md").write_text(brief)
    session = f"{task_id(proposal)}-{name}"
    proc = spawn(session_bin, repo, "planner", directory, session, directory / "brief.md",
                 sessions_root, list(extra_args or []) + list(planner_args or []), ref=None, dry_run=dry_run)
    reflected = mail.reflections(sessions_root / session)
    chosen, _ = mail.handoff(reflected)
    parsed = parse_handoff(chosen.get("text", "") if chosen else "")
    return {"session": session, "exit": proc.returncode if proc else None, "wall_seconds": _wall(proc),
            "handoff": parsed, "requirements": requirements_from_handoff(parsed), "attempt": attempt,
            "reflections": [m.get("text", "") for m in reflected]}


def plan_stage_entry(result: dict, graph: dict, proposal: str) -> tuple[dict, list[str], list[str]]:
    """The plan stage's record from a planner result: the handoff's
    fields, the named terms resolved (requirement files included — a
    requirement's owner is a seed), the requirements, and the cheap
    coverage precursor (ADR-084): the proposal's imperative sentences
    the handoff never mentions. Returns ``(entry, hits, misses)``."""
    handoff = result["handoff"]
    requirements = result.get("requirements", [])
    req_files = [f for r in requirements for f in r.get("files", [])]
    named = list(dict.fromkeys(handoff.get("files", []) + req_files + handoff.get("symbols", [])))
    hits, misses = resolve_terms(graph, named)
    entry = {"stage": "plan", "role": "planner", "agent": "planner" if result.get("attempt", 1) == 1
             else f"planner-{result['attempt']}", "attempt": result.get("attempt", 1),
             **{k: result.get(k) for k in ("session", "exit", "wall_seconds")},
             "handoff": handoff.get("raw", ""), "approach": handoff.get("approach", ""),
             "files": list(dict.fromkeys(handoff.get("files", []) + req_files)),
             "symbols": list(handoff.get("symbols", [])),
             "requirements": requirements,
             "imperatives_unmentioned": imperatives_unmentioned(proposal, [handoff.get("raw", "")]),
             "terms": term_modules(graph, named),
             "resolved": hits, "unresolved": misses, "tests": handoff.get("tests", [])}
    return entry, hits, misses


def fallback_note(misses: list[str]) -> str:
    """What the re-planned planner is told when its first handoff named
    nothing the graph resolves (ADR-093): the names that missed, and
    that a real path is required."""
    named = f" (you named: {', '.join(misses)} — none found)" if misses else ""
    return ("your previous handoff named no file or symbol that exists in this repository"
            + named + ". Hand off again naming real paths — read the tree to find them — "
            "with a `requirements:` list, each line `-> <owning file>`.")


def replan_note(coverage: dict) -> str:
    """What the re-planned planner is told: the requirements its first
    handoff left without an owning file, or that it stated none."""
    if coverage.get("status") == "no-requirements":
        return ("your previous handoff stated no requirements. Hand off again with a "
                "`requirements:` list — one line per thing the proposal asks to become true, "
                "each with `-> <owning file>`.")
    rows = coverage.get("uncovered", [])
    lines = ["these requirements from your previous handoff name no file any unit owns — "
             "re-hand off with an owning file for each (a real path; read the code to find it):"]
    lines += [f"- {r['id']}: {r['text']}" + (f" (you named: {', '.join(r['files'])} — not found)" if r.get("files") else "")
              for r in rows]
    return "\n".join(lines)



def _named_symbol_neighborhood(graph: dict, symbols: list[str], cap: int = 14) -> list[str]:
    """What Hobbes can see *around* the planner's named symbols: the
    symbols they call/use and that call them, one hop, from the symbol
    graph (ADR-077). These are the likely co-change targets a single-file
    plan misses — e.g. ``field_choices`` reaching ``get_choices``. Bare
    heads are matched tolerantly (``Class.method`` or ``method``)."""
    edges = graph.get("symbol_edges", [])
    heads = {sym.strip() for sym in symbols if sym.strip()}
    if not heads or not edges:
        return []
    def touches(node: str) -> bool:
        node = node or ""
        tail = node.rsplit(".", 1)[-1]
        return any(node == h or node.endswith("." + h) or tail == h.rsplit(".", 1)[-1] for h in heads)
    calls, callers = [], []
    for e in edges:
        frm, to = e.get("from", ""), e.get("to", "")
        if touches(frm) and not touches(to):
            calls.append(to)
        elif touches(to) and not touches(frm):
            callers.append(frm)
    def uniq(xs):
        seen, out = set(), []
        for x in xs:
            if x and x not in seen and not touches(x):
                seen.add(x); out.append(x)
        return out
    lines = []
    for label, xs in (("it calls / uses", uniq(calls)), ("callers of it", uniq(callers))):
        if xs:
            lines.append(f"  {label}: " + ", ".join(xs[:cap]) + (" …" if len(xs) > cap else ""))
    return lines


def aided_brief(proposal: str, plan_stage: dict, graph: dict) -> str:
    """The aided implementer's prompt (ADR-077): task + what Hobbes can
    see (the planner's localisation and the neighborhood around it) +
    what Hobbes cannot confirm (the full file set), with the change made
    explicit that the derived context is an **aid, not a boundary** — the
    agent is free to edit any file the fix needs. This is the corrective
    to the multi-unit fence that fragmented multi-file fixes (the
    27B five-fresh read): Hobbes secures a fraction of understanding and
    hands it over; it does not narrow the model below the task."""
    files = plan_stage.get("files", []) if plan_stage else []
    symbols = plan_stage.get("symbols", []) if plan_stage else []
    approach = plan_stage.get("approach", "") if plan_stage else ""
    tests = plan_stage.get("tests", []) if plan_stage else []
    raw = plan_stage.get("handoff", "") if plan_stage else ""
    hood = _named_symbol_neighborhood(graph, symbols or files)
    seen = ["## What Hobbes can see (derived context — an aid, not a boundary)"]
    if files:    seen.append("files the change centers on: " + ", ".join(files))
    if symbols:  seen.append("symbols: " + ", ".join(symbols))
    if approach: seen.append("approach (the planner's read): " + approach)
    if tests:    seen.append("tests that guard this behavior: " + ", ".join(tests))
    if hood:
        seen.append("around the named symbols, the graph shows (likely co-change sites):")
        seen.extend(hood)
    if not (files or symbols or approach):
        seen.append("the planner resolved nothing specific — work from the task and the repo.")
    return "\n".join([
        "You are a single-use software engineer. Make the change the task describes,",
        "in this repository. The working directory is the repo root.",
        "",
        "## Task",
        proposal.strip(),
        "",
        *seen,
        "",
        "## What Hobbes cannot confirm — you are free here",
        "- The files above are where the change STARTS, not necessarily every file it",
        "  touches. A real fix usually spans the functions the named code calls or that",
        "  call it (see the co-change sites above). You may read and edit ANY file in the",
        "  repository the fix requires. Do NOT limit yourself to the files named above.",
        "- Hobbes gives you a head start on understanding, not a boundary on your work.",
        *(["- The planner was unsure about: " + raw.split("risks:", 1)[1].strip()] if "risks:" in raw else []),
        "",
        "## How to work",
        "- Read the relevant code, make the complete coherent change across every file it",
        "  needs, then run the guarding tests through the exec tool.",
        "- Commit your work on this branch when the tests pass. Do not create branches,",
        "  merge, rebase, or push.",
    ])


def run_staged(
    repo_root: Path,
    proposal: str,
    stages: tuple[str, ...] = DEFAULT_STAGES,
    session_bin: str | None = None,
    sessions_root: Path | None = None,
    extra_args: list[str] | None = None,
    brief_limit: int | None = None,
    workers: int = 1,
    max_units: int | None = None,
    budget: int | None = None,
    seeds: list[str] | None = None,
    dry_run: bool = False,
    max_rework: int = 1,
    human_first: str = "park",
    implement_mode: str = "unit",
    coverage_mode: str = "strict",
    proposal_in_brief: bool = False,
    planner_args: list[str] | None = None,
) -> dict:
    """Run a proposal end to end through the stages. Returns the
    partition record, extended with a ``stages`` list, ``seed_source``
    and ``coverage`` (ADR-085).

    *coverage_mode* is what happens when the planner's requirements do
    not all have an owning unit after the one bounded re-plan:
    ``strict`` stops at plan cost (:class:`PlanCoverageError`, the
    record written first); ``assign`` hands the leftovers to the seed
    unit and says so (C-57). A planner whose handoff resolves to no
    file is re-planned once like an uncovered one; if it still resolves
    nothing, ``strict`` stops (the lexical seeds are not a plan whose
    coverage can be checked — ADR-093) and ``assign`` runs on them,
    recorded ``lexical-fallback``. *proposal_in_brief* keeps the full
    proposal in every implementer brief even when its requirements are
    covered — the pre-085 shape, kept for the removal test (ADR-084
    §3); on the lexical fallback or with no requirements it stays
    regardless. *planner_args* are session flags for the planner alone
    (a larger turn/token budget — the weight belongs to it)."""
    if coverage_mode not in COVERAGE_MODES:
        raise RunError(f"coverage mode must be one of {COVERAGE_MODES}, not {coverage_mode!r}")
    repo = Path(repo_root).resolve()
    session_bin, sessions_root = _resolve_binaries(session_bin, sessions_root, dry_run)
    extra_args = list(extra_args or [])
    graph = artifacts.load_graph(repo, accepts=artifacts.V4_ONLY)
    tests_doc = artifacts.load_tests(repo) if (repo / ".hobbes/derived/tests.json").is_file() else {"tests": []}
    ensure_role_policies(repo)
    task = task_id(proposal)
    pdir = plan_dir(repo, task)
    pdir.mkdir(parents=True, exist_ok=True)
    stage_log: list[dict] = []

    # 1. plan — the planner names the change AND its requirements; its
    #    handoff is the seeds. 2. derive — deterministic, on the
    #    planner's seeds *alone* (the lexical layer is the fallback, not
    #    a co-seeder). Then coverage: every requirement must have an
    #    owning unit (ADR-084); one bounded re-plan when it does not,
    #    the uncovered requirements as the planner's short memory.
    planner_seeds = list(seeds or [])
    seed_source = "explicit" if seeds else "lexical-fallback"
    planner_misses: list[str] = []
    planner_tests: list[str] = []
    coverage: dict = {"status": "not-planned", "mode": coverage_mode, "requirements": [],
                      "uncovered": [], "by_unit": {}}
    orchestrator_note = ""
    for attempt in (1, 2):
        if "plan" in stages:
            result = run_planner(repo, proposal, graph, pdir, session_bin, sessions_root,
                                 extra_args, brief_limit, dry_run, planner_args=planner_args,
                                 attempt=attempt, orchestrator_note=orchestrator_note)
            handoff = result["handoff"]
            entry, hits, planner_misses = plan_stage_entry(result, graph, proposal)
            planner_tests = handoff.get("tests", [])
            stage_log.append(entry)
            if hits:
                planner_seeds, seed_source = hits, "planner"
            elif attempt == 1:
                planner_seeds, seed_source = list(seeds or []), "explicit" if seeds else "lexical-fallback"
                if coverage_mode == "strict" and not dry_run and implement_mode != "aided":
                    # A planner that named nothing the graph resolves gets
                    # the same one re-plan an uncovered handoff gets: under
                    # strict the lexical seeds are not a plan (D5, ADR-093).
                    orchestrator_note = fallback_note(planner_misses)
                    continue
        if implement_mode == "aided":
            break
        kwargs = {"seeds": planner_seeds, "max_units": max_units, "lexical": seed_source != "planner"}
        if budget:
            kwargs["budget"] = budget
        spec_obj = derive_plan(repo, proposal, **kwargs)
        write_spec(repo, spec_obj)
        spec = artifacts_spec(repo, task)
        contexts = {c["unit"]: c for c in spec.get("contexts", [])}
        plan_stage = next((st for st in reversed(stage_log) if st.get("stage") == "plan"), None)
        if not plan_stage or seed_source != "planner":
            coverage = {"status": "no-planner" if not plan_stage else "lexical-fallback",
                        "mode": coverage_mode, "requirements": [], "uncovered": [], "by_unit": {},
                        "planner_unresolved": list(planner_misses)}
            break
        coverage = assign_requirements(plan_stage.get("requirements", []), plan_stage.get("terms") or {},
                                       contexts, plan_stage.get("files", []), mode="strict")
        if coverage["status"] == "covered" or dry_run or "plan" not in stages:
            break
        if attempt == 1:
            orchestrator_note = replan_note(coverage)
            continue
    # The guarantee has three failure shapes and strict stops on every
    # one: uncovered, no requirements, and the lexical fallback (a planner
    # that named nothing the graph resolves — D5, ADR-093). `assign` runs
    # the fallback through and records it, as before.
    if coverage["status"] in ("uncovered", "no-requirements", "lexical-fallback") and not dry_run \
            and implement_mode != "aided" and "plan" in stages:
        if coverage_mode == "assign" and coverage["status"] == "uncovered":
            plan_stage = next(st for st in reversed(stage_log) if st.get("stage") == "plan")
            coverage = assign_requirements(plan_stage.get("requirements", []), plan_stage.get("terms") or {},
                                           contexts, plan_stage.get("files", []), mode="assign")
        elif coverage_mode == "strict":
            # Plan cost, not session cost: the record is written with
            # the coverage so the failure is readable, then the run stops.
            coverage["replanned"] = len([st for st in stage_log if st.get("stage") == "plan"]) > 1
            (pdir / "partition-record.json").write_text(json.dumps(
                {"task": task, "proposal": proposal, "seed_source": seed_source, "stages": stage_log,
                 "coverage": coverage, "units": [], "integration": {"merged": [], "failed": []},
                 "error": "plan coverage failed"}, indent=2, sort_keys=True) + "\n")
            raise PlanCoverageError(coverage)
    coverage["replanned"] = len([st for st in stage_log if st.get("stage") == "plan"]) > 1

    # Aided mode (ADR-077): skip the partition entirely. One implementer
    # gets the task + the planner's localisation + the neighborhood
    # around it + explicit freedom to edit any file, and integrates its
    # whole diff. Hobbes aids, it does not fence.
    if implement_mode == "aided":
        return _run_aided(repo, proposal, task, pdir, graph, tests_doc, stage_log,
                          seed_source, planner_tests, planner_misses, stages,
                          session_bin, sessions_root, extra_args, brief_limit, dry_run)

    # 3. review — opt-in; an amend re-plans once (bounded).
    if "review" in stages:
        verdict = run_review(repo, spec, pdir, session_bin, sessions_root, extra_args, brief_limit, dry_run)
        stage_log.append(verdict["stage"])

    dirs = agents.materialize(pdir, spec, tests_doc, role="implementer", human_first=human_first)
    orchestrator = agents.agent_dir(pdir, agents.ORCHESTRATOR)
    # The planner's handoff is the first short memory every implementer
    # gets — PROJECTED onto the unit (ADR-062): each inbox carries only
    # the part of the change that lies in its own interior, and says so
    # when none does. One global handoff led every unit to the same file.
    # With coverage, the unit's owned requirements ARE its task
    # (ADR-085): the brief carries them in place of the proposal.
    unit_tasks: dict[str, str] = {}
    for unit in dirs:
        planner_note = _planner_note(seed_source, stage_log, contexts.get(unit), coverage)
        if planner_note:
            mail.post(dirs[unit], "planner", planner_note, kind="handoff")
        if coverage["status"] in ("covered", "assigned") and not proposal_in_brief:
            unit_tasks[unit] = unit_task(coverage, unit)
    brief_task = "requirements" if unit_tasks else "proposal"

    code, head = _git(repo, "rev-parse", "HEAD")
    base = head if code == 0 else spec.get("graph_sha", "")
    test_files = {t["id"]: t.get("file", "") for t in tests_doc.get("tests", [])}
    order = order_units(spec)
    records: list[UnitRecord] = []
    sessions: dict[str, str] = {}
    target = f"hobbes/{task}"
    integ = {"branch": target, "merged": [], "failed": []}

    implement_wall: float | None = None
    waves: list[list[str]] = []
    if "implement" in stages:
        _git(repo, "branch", "-f", target, base)
        implement_started = time.monotonic()
        deps = parallel.unit_dependencies(spec)
        pending = list(order)
        done: set[str] = set()

        def start(unit: str):
            """Brief + spawn for one unit; runs on a worker thread. Only
            reads the repo (the clone is at the integration head as of
            now) — harvest and integration happen on the caller's thread."""
            session = f"{task}-{unit.lower()}"
            record = UnitRecord(unit=unit, role="implementer", session=session, spawned=False)
            inbox = mail.read(dirs[unit])
            full = agents.render_brief(spec, unit, "implementer", inbox, session, task=unit_tasks.get(unit))
            brief = agents.render_brief(spec, unit, "implementer", inbox, session, limit=brief_limit,
                                        task=unit_tasks.get(unit))
            (dirs[unit] / "brief.md").write_text(brief)
            record.brief_chars, record.brief_cut = len(brief), max(0, len(full) - len(brief))
            # Chained: start at the current integration head so a consumer
            # sees its owner's commit. The ref is the *commit*, not the
            # branch name — a --local clone exposes other branches only as
            # origin/*, but the object is in the copied store.
            head_ref = _head_sha(repo, target, base)
            proc = spawn(session_bin, repo, "implementer", dirs[unit], session, dirs[unit] / "brief.md",
                         sessions_root, extra_args, ref=head_ref, dry_run=dry_run)
            record.spawned = not dry_run
            record.exit = proc.returncode if proc else None
            record.wall_seconds = _wall(proc)
            if contexts[unit].get("human_first"):
                record.reason = ("human-first: spawned anyway (--human-first spawn, C-53) — "
                                 + contexts[unit].get("human_first_reason", ""))
            return record

        def finish(unit: str, record: UnitRecord):
            sessions[unit] = record.session
            _harvest_unit(repo, base, record.session, contexts[unit], test_files, sessions_root, record,
                          orchestrator, unit)
            # Integrate this one immediately, scoped to the unit's own
            # files (C-38 enforced at the cut).
            _integrate_one(repo, target, unit, record.session, integ, _manifest_paths(contexts[unit], test_files))
            records.append(record)
            stage_log.append(_unit_stage("implement", unit, record))
            done.add(unit)

        # Human-first units are never spawned; they count as done for
        # their consumers (the orchestrator's inbox says why). With
        # human_first="spawn" (a benchmark Hobbes runs alone, C-53)
        # they run anyway, the abstention recorded on the unit.
        for unit in list(pending):
            if contexts[unit].get("human_first") and human_first != "spawn":
                record = UnitRecord(unit=unit, role="implementer", session=f"{task}-{unit.lower()}", spawned=False)
                record.reason = "human-first: not spawned — " + contexts[unit].get("human_first_reason", "")
                mail.post(orchestrator, unit, record.reason, kind="human-first")
                records.append(record)
                pending.remove(unit)
                done.add(unit)

        # Task-tailored selection (ADR-064): on the planner path a unit
        # the planner named nothing in is not brought in at all — the
        # re-probe showed such units burn a session to plan editing
        # someone else's file. A skipped unit counts as done so its
        # consumers still become ready. On the lexical fallback there is
        # no per-unit naming, so every unit stays (the seeds are the
        # whole signal). C-52.
        plan_stage = next((st for st in reversed(stage_log) if st.get("stage") == "plan"), None)
        if seed_source == "planner" and plan_stage:
            for unit in list(pending):
                if not unit_has_planner_work(plan_stage, contexts[unit]) and unit not in coverage.get("by_unit", {}):
                    record = UnitRecord(unit=unit, role="implementer",
                                        session=f"{task}-{unit.lower()}", spawned=False)
                    record.reason = ("not spawned — the planner named no file in this unit's "
                                     "interior (task-tailored selection, ADR-064)")
                    mail.post(orchestrator, unit, record.reason, kind="not-selected")
                    records.append(record)
                    pending.remove(unit)
                    done.add(unit)

        # Waves over the contract DAG (ADR-063): every unit whose owners
        # are integrated may run at once, up to *workers*; each finishes
        # on this thread (harvest + scoped integration are serial), which
        # may free the next wave. workers == 1 is exactly the old order.
        from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            running: dict = {}
            while pending or running:
                ready = parallel.ready_units(pending, done, deps)
                if not ready and not running and pending:
                    ready = [pending[0]]  # cycle: by order, as order_units breaks it
                started_now = []
                for unit in ready:
                    if len(running) >= max(1, workers):
                        break
                    pending.remove(unit)
                    running[pool.submit(start, unit)] = unit
                    started_now.append(unit)
                if started_now:
                    waves.append(started_now)
                if not running:
                    continue
                finished, _ = wait(list(running), return_when=FIRST_COMPLETED)
                for fut in finished:
                    unit = running.pop(fut)
                    finish(unit, fut.result())
        implement_wall = round(time.monotonic() - implement_started, 3)

    review = {"skipped": "dry run" if dry_run else "not run"}
    if not dry_run and integ["merged"]:
        review = review_integration(repo, base, target)

    # 5. verify — a read-only session over the integrated head.
    verify: dict = {"skipped": "not requested"}
    reworked = 0
    if "verify" in stages and not dry_run and integ["merged"]:
        verify = run_verifier(repo, task, _head_sha(repo, target, base), planner_tests, spec, pdir,
                              session_bin, sessions_root, extra_args, brief_limit, dry_run, test_files=test_files,
                              requirements=coverage.get("requirements", []))
        stage_log.append(verify["stage"])
        while (verify.get("verdict") == "fail" and "rework" in stages and reworked < max_rework):
            reworked += 1
            _run_rework(repo, task, target, base, verify, spec, contexts, test_files, dirs,
                        orchestrator, records, sessions, integ, session_bin, sessions_root,
                        extra_args, brief_limit, stage_log, unit_tasks)
            verify = run_verifier(repo, task, _head_sha(repo, target, base), planner_tests, spec, pdir,
                                  session_bin, sessions_root, extra_args, brief_limit, dry_run, attempt=reworked + 1,
                                  test_files=test_files, requirements=coverage.get("requirements", []))
            stage_log.append(verify["stage"])

    contract_failures = len(integ.get("failed", []))
    record_doc = {
        "task": task, "proposal": proposal, "base": base,
        "graph_sha": spec.get("graph_sha", ""), "order": order, "selected": order,
        "seed_source": seed_source, "seeds": spec.get("seeds", {}),
        "units_not_selected": [r.unit for r in records if r.reason and "task-tailored selection" in r.reason],
        "planner_unresolved": planner_misses,
        "units_deferred": [u.get("name") for u in spec.get("units_deferred", [])],
        "coverage": coverage, "brief_task": brief_task,
        "stages": stage_log,
        "units": [{**r.__dict__, "fault_rate": round(r.fault_rate, 4)} for r in records],
        "contracts": len(spec.get("contracts", [])),
        "integration": integ, "review": review, "verify": verify,
        "rework": reworked,
        # Outside-measured: with parallel units the sum of per-unit walls
        # overstates the stage (ADR-063); this is what the clock saw.
        "implement_wall_seconds": implement_wall,
        "parallel": {"workers": max(1, workers), "waves": waves},
        "loss": loss(records, contract_failures),
    }
    (pdir / "partition-record.json").write_text(json.dumps(record_doc, indent=2, sort_keys=True) + "\n")
    return record_doc


def _run_aided(repo, proposal, task, pdir, graph, tests_doc, stage_log, seed_source,
               planner_tests, planner_misses, stages, session_bin, sessions_root,
               extra_args, brief_limit, dry_run) -> dict:
    """One free implementer on the planner's task (ADR-077). No partition,
    no per-unit write scope: the session runs on the whole worktree and
    its entire diff is the candidate patch. Returns a record shaped like
    run_staged's so the bench adapter reads it unchanged."""
    plan_stage = next((st for st in stage_log if st.get("stage") == "plan"), {})
    test_files = {t["id"]: t.get("file", "") for t in tests_doc.get("tests", [])}
    directory = agents.agent_dir(pdir, "impl")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / mail.INBOX).touch()
    # A solo implementer needs to edit anywhere and run tests; the box
    # policy (bench) already grants tests+commit. No write-scope note.
    (directory / "policy.yaml").write_text(json.dumps(
        {"version": 1, "scope": "agent", "default": "escalate", "rules": []}))
    # A context.json of the planner's files — a *hint* (what Hobbes
    # localized), not a fence: the harvest below takes the whole diff
    # (allowed=None), and the brief says edit any file. Served like any
    # agent context (ADR-054).
    (directory / "context.json").write_text(json.dumps(
        {"unit": "impl", "paths": list(plan_stage.get("files", [])),
         "symbols": list(plan_stage.get("symbols", []))}))
    brief = aided_brief(proposal, plan_stage, graph)
    full = brief
    if brief_limit and len(brief) > brief_limit:
        brief = brief[:brief_limit] + "\n[brief truncated]\n"
    (directory / "brief.md").write_text(brief)

    task_target = f"hobbes/{task}"
    session = f"{task}-impl"
    record = UnitRecord(unit="impl", role="implementer", session=session, spawned=False)
    record.brief_chars, record.brief_cut = len(brief), max(0, len(full) - len(brief))
    integ = {"branch": task_target, "merged": [], "failed": []}
    orchestrator = agents.agent_dir(pdir, agents.ORCHESTRATOR)
    orchestrator.mkdir(parents=True, exist_ok=True)
    (orchestrator / mail.INBOX).touch()

    code, head = _git(repo, "rev-parse", "HEAD")
    base = head if code == 0 else graph.get("sha", "")
    implement_wall = None
    if "implement" in stages:
        _git(repo, "branch", "-f", task_target, base)
        started = time.monotonic()
        proc = spawn(session_bin, repo, "implementer", directory, session, directory / "brief.md",
                     sessions_root, extra_args, ref=base, dry_run=dry_run)
        record.spawned = not dry_run
        record.exit = proc.returncode if proc else None
        record.wall_seconds = _wall(proc)
        if not dry_run:
            session_dir = sessions_root / session
            read_flight(session_dir, record)
            reflected = mail.reflections(session_dir)
            record.reflections = [m.get("text", "") for m in reflected]
            record.handoff = handoff_status(reflected)
            mail.fold_back(orchestrator, "impl", reflected)
            # rework_files here MEASURES how far the agent ranged beyond
            # the planner's named files (not a fence) — the multi-file
            # reach the unit mode could not make. Integration is unfenced
            # (allowed=None): the whole diff is the candidate patch.
            planned_files = set(plan_stage.get("files", []))
            read_branch(repo, base, session, planned_files, record)
            _integrate_one(repo, task_target, "impl", session, integ, allowed=None)
        implement_wall = round(time.monotonic() - started, 3)
    stage_log.append(_unit_stage("implement", "impl", record))

    review = {"skipped": "dry run" if dry_run else "not run"}
    if not dry_run and integ["merged"]:
        review = review_integration(repo, base, task_target)

    verify: dict = {"skipped": "not requested"}
    if "verify" in stages and not dry_run and integ["merged"]:
        minimal_spec = {"proposal": proposal, "contexts": [], "graph_sha": graph.get("sha", "")}
        verify = run_verifier(repo, task, _head_sha(repo, task_target, base), planner_tests,
                              minimal_spec, pdir, session_bin, sessions_root, extra_args,
                              brief_limit, dry_run, test_files=test_files)
        stage_log.append(verify["stage"])

    record_doc = {
        "task": task, "proposal": proposal, "base": base,
        "graph_sha": graph.get("sha", ""), "order": ["impl"], "selected": ["impl"],
        "seed_source": seed_source, "seeds": {}, "units_not_selected": [],
        "planner_unresolved": planner_misses, "units_deferred": [],
        "implement_mode": "aided",
        "stages": stage_log,
        "units": [{**record.__dict__, "fault_rate": round(record.fault_rate, 4)}],
        "contracts": 0, "integration": integ, "review": review, "verify": verify, "rework": 0,
        "implement_wall_seconds": implement_wall,
        "parallel": {"workers": 1, "waves": [["impl"]] if not dry_run else []},
        "loss": loss([record], len(integ.get("failed", []))),
    }
    (pdir / "partition-record.json").write_text(json.dumps(record_doc, indent=2, sort_keys=True) + "\n")
    return record_doc


def _unit_stage(stage: str, unit: str, record: UnitRecord) -> dict:
    """An implementer's entry in the stage log: the same session the
    unit record names, so the bench adapter can find its meter."""
    return {"stage": stage, "role": "implementer", "agent": unit, "unit": unit,
            "session": record.session, "exit": record.exit, "wall_seconds": record.wall_seconds,
            "commits": record.commits, "files_changed": list(record.files_changed)}


def artifacts_spec(repo: Path, task: str) -> dict:
    from hobbes.run.spec import load_spec
    return load_spec(repo, task)


def term_modules(graph: dict, terms: list[str]) -> dict[str, str | None]:
    """Each planner-named term → the module id it resolves to (``None``
    when it does not), the same tolerant lookup :func:`resolve_terms`
    uses. Kept on the plan stage so the handoff can be projected per
    unit (ADR-062)."""
    lookup = build_lookup(graph, dotted_head=True)
    out: dict[str, str | None] = {}
    for term in terms:
        cleaned = (term or "").strip()
        if cleaned and cleaned not in out:
            out[cleaned] = lookup(cleaned)
    return out


def planner_slice(plan: dict, context: dict) -> tuple[list[str], list[str]]:
    """Split the planner's named terms into (in this unit's interior,
    owned elsewhere). A term is the unit's when it resolved to one of
    its interior modules or path-matches one of its interior files."""
    ids = {m.get("id") for m in context.get("modules", [])}
    paths = [m.get("path", "") for m in context.get("modules", [])]
    terms = plan.get("terms") or {}
    named = [t for t in plan.get("files", []) + plan.get("symbols", []) if t and t.strip()]
    mine, others = [], []
    for term in dict.fromkeys(t.strip() for t in named):
        (mine if in_interior(term, terms.get(term), ids, paths) else others).append(term)
    return mine, others


def unit_has_planner_work(plan_stage: dict, context: dict) -> bool:
    """True when the planner named at least one file/symbol in this
    unit's interior (ADR-064). A unit for which this is false is not
    brought into a planner-seeded run — it would only plan editing
    another unit's file."""
    mine, _ = planner_slice(plan_stage, context)
    return bool(mine)


def _planner_note(seed_source: str, stage_log: list[dict], context: dict | None = None,
                  coverage: dict | None = None) -> str:
    """The planner's handoff as ONE unit's short memory (ADR-062): its
    slice of the change, the approach, and a plain statement that the
    rest is owned elsewhere — or that nothing named lies in its interior.
    With *coverage* (ADR-085) the unit's owned requirements lead the
    note and the count of requirements owned elsewhere is stated.
    Without *context* the whole handoff is returned (the pre-062 shape)."""
    if seed_source != "planner":
        return ""
    plan = next((s for s in reversed(stage_log) if s.get("stage") == "plan"), None)
    if not plan:
        return ""
    approach = (plan.get("approach") or "").strip() or plan.get("handoff", "").strip()[:600]
    tests = "run these tests: " + ", ".join(plan["tests"]) if plan.get("tests") else ""
    if context is None:
        return "\n".join(p for p in [f"planner: {plan['handoff'].strip()[:800]}", tests] if p)
    mine, others = planner_slice(plan, context)
    parts = []
    unit = context.get("unit")
    owned = unit_task(coverage, unit) if coverage and unit else ""
    if owned:
        total = len(coverage.get("requirements", []))
        n_mine = len(coverage.get("by_unit", {}).get(unit, []))
        parts.append(f"planner: you own {n_mine} of the plan's {total} requirement(s) — they are your task "
                     "(see the brief's task section). The others are owned by other units; do not do them.")
    if mine:
        parts.append("planner: your slice of the change — the planner named these IN YOUR INTERIOR: "
                     + ", ".join(mine) + ". Edit those paths (see Interior below).")
    elif not owned:
        parts.append("planner: nothing the planner named lies in your interior. It named: "
                     + (", ".join(others[:8]) + (" …" if len(others) > 8 else "") or "nothing") +
                     " — all owned by other units. You are in the plan because the graph reaches "
                     "you from the change: change a file here only if a contract at your boundary "
                     "requires it; otherwise hand off that no change was needed. Do not create or "
                     "edit files outside your interior — they are dropped at integration.")
    if approach:
        parts.append(f"approach: {approach[:600]}")
    if mine and others:
        parts.append(f"the planner also named {len(others)} location(s) owned by other units ("
                     + ", ".join(others[:8]) + (" …" if len(others) > 8 else "") +
                     "): not yours — do not create or edit them; edits outside your interior are "
                     "dropped at integration.")
    if tests:
        parts.append(tests)
    return "\n".join(parts)


def _harvest_unit(repo, base, session, context, test_files, sessions_root, record, orchestrator, unit):
    session_dir = sessions_root / session
    read_flight(session_dir, record)
    reflected = mail.reflections(session_dir)
    record.reflections = [m.get("text", "") for m in reflected]
    record.handoff = handoff_status(reflected)
    mail.fold_back(orchestrator, unit, reflected)
    read_branch(repo, base, session, _manifest_paths(context, test_files), record)


def _manifest_paths(context: dict, test_files: dict[str, str]) -> set[str]:
    """A unit's write scope: its interior module paths plus the files of
    the tests it guards. The partition makes interiors disjoint, so a
    file belongs to at most one unit — which is why scoping the harvest
    to these paths lets no two units write the same file."""
    paths = {m["path"] for m in context.get("modules", []) if m.get("path")}
    paths |= {test_files[t] for t in context.get("guarding_tests", []) if test_files.get(t)}
    return paths


def _integrate_one(repo: Path, target: str, unit: str, session: str, integ: dict,
                   allowed: set[str] | None = None) -> None:
    """Integrate one unit's contribution onto the running target,
    **scoped to its manifest paths** (C-38 enforced at the cut, not just
    measured as rework). The unit branch was cloned from the current
    target, so ``target..branch`` is exactly the unit's own change; we
    take only the part of it that touches files the unit owns and apply
    that to the target. Files the model wrote outside its scope — a
    neighbour's source (the astropy probe's four units that all created
    ``wcsapi.py``) or a scratch note (``session_commit.txt``) — never
    enter the candidate patch, and no other unit can be clobbered."""
    branch = f"hobbes/{session}"
    if not _branch_exists(repo, branch):
        return
    # The unit's change is what it did since it was cloned — the
    # merge-base, not the target's tip, which may have advanced under a
    # parallel unit (ADR-063). Its scoped files are disjoint from
    # anything that landed meanwhile, so the base-relative patch still
    # applies onto the tip; a failure is a real conflict at the cut.
    code, merge_base = _git(repo, "merge-base", target, branch)
    since = merge_base if code == 0 and merge_base else target
    # What the unit changed, and what of it is out of scope (dropped).
    _, names = _git(repo, "diff", "--name-only", f"{since}..{branch}")
    changed = [n for n in names.splitlines() if n]
    dropped = sorted(n for n in changed if allowed is not None and n not in allowed)
    if dropped:
        integ.setdefault("dropped", {})[unit] = dropped
    # The in-scope diff. With no manifest (allowed None) fall back to the
    # whole change, preserving the pre-C-38 behaviour for callers that
    # pass no scope. Captured raw (bytes) — _git strips and merges
    # stderr, which corrupts a patch's trailing newline.
    diff_args = ["diff", "--binary", f"{since}..{branch}"]
    if allowed is not None:
        in_scope = sorted(n for n in changed if n in allowed)
        if not in_scope:
            integ.setdefault("empty", []).append(unit)
            return
        diff_args += ["--", *in_scope]
    proc = subprocess.run(["git", "-C", str(repo), *diff_args], capture_output=True)
    patch = proc.stdout
    if proc.returncode != 0 or not patch.strip():
        integ.setdefault("empty", []).append(unit)
        return
    tmp = repo / ".hobbes" / "plans" / target.split("/", 1)[-1] / ".integrate"
    shutil.rmtree(tmp, ignore_errors=True)
    code, out = _git(repo, "worktree", "add", "-q", "--detach", str(tmp), target)
    if code != 0:
        integ["failed"].append({"unit": unit, "branch": branch, "error": out[-400:]})
        return
    try:
        # The scoped diff touches only this unit's files, so it applies
        # cleanly (no 3-way needed) — a failure here is a real conflict at
        # the cut (two units guarded by one test file both edited it).
        ap = subprocess.run(["git", "-C", str(tmp), "apply", "--whitespace=nowarn"],
                            input=patch, capture_output=True)
        if ap.returncode == 0:
            _git(tmp, "add", "-A")
            _git(tmp, "-c", "user.name=hobbes", "-c", "user.email=hobbes@local",
                 "commit", "-q", "-m", f"integrate {unit} ({branch}, scoped)")
            _git(tmp, "branch", "-f", target, "HEAD")
            integ["merged"].append(unit)
        else:
            integ["failed"].append({"unit": unit, "branch": branch,
                                    "error": ap.stderr.decode(errors="replace")[-400:]})
    finally:
        _git(repo, "worktree", "remove", "--force", str(tmp))
        shutil.rmtree(tmp, ignore_errors=True)
    return


def run_review(repo, spec, pdir, session_bin, sessions_root, extra_args, brief_limit, dry_run) -> dict:
    """A reviewer session judges the change-spec; ``amend`` is recorded
    (the re-plan is a future step — the base records the verdict)."""
    directory = agents.agent_dir(pdir, "reviewer")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / mail.INBOX).touch()
    (directory / "policy.yaml").write_text(json.dumps(
        {"version": 1, "scope": "agent", "default": "escalate", "rules": [
            {"pattern": "git commit*", "decision": "deny", "reason": "a reviewer writes nothing"}]}))
    brief = "\n".join([
        "You are a single-use plan reviewer. You change nothing. Read the change-spec below and",
        "judge whether the units and their assigned files match the proposal.",
        "", f"## Proposal\n{spec.get('proposal', '')}", "",
        "## Units",
        "\n".join(
            f"- {u['name']}: " + ", ".join(
                m['path'] for m in next((x for x in spec['contexts'] if x['unit'] == u['name']), {}).get('modules', [])
                if m.get('path'))
            for u in spec.get("units", [])),
        "", "## Your handoff (reflect kind \"handoff\")",
        "verdict: approve or amend", "reason: one line",
    ])
    (directory / "brief.md").write_text(brief)
    session = f"{spec['task']}-reviewer"
    proc = spawn(session_bin, repo, "reviewer", directory, session, directory / "brief.md",
                 sessions_root, extra_args, ref=None, dry_run=dry_run)
    chosen, _ = mail.handoff(mail.reflections(sessions_root / session))
    parsed = parse_handoff(chosen.get("text", "") if chosen else "")
    return {"verdict": parsed.get("verdict", ""), "stage": {
        "stage": "review", "role": "reviewer", "agent": "reviewer", "session": session,
        "exit": proc.returncode if proc else None, "wall_seconds": _wall(proc),
        "verdict": parsed.get("verdict", ""), "verdict_source": parsed.get("verdict_source"),
        "reason": parsed.get("reason", "")}}


def resolve_tests(named: list[str], test_files: dict[str, str]) -> tuple[list[str], list[str]]:
    """Map a planner's named tests to what the repo actually has: a test
    id, a file path, or a bare filename / path suffix matching exactly
    one test file. Returns (resolved, unresolved). The probe's verifier
    ran ``pytest test_intermediate_transformations.py`` at the root and
    found nothing — the planner had named the file bare."""
    files = sorted(set(test_files.values()))
    ids = set(test_files)
    resolved: list[str] = []
    unresolved: list[str] = []
    for name in named:
        n = name.strip().strip("`'\"")
        if not n:
            continue
        base = n.split("::", 1)[0]
        if n in ids or base in files:
            hit = n
        else:
            suffix = [f for f in files if f == base or f.endswith("/" + base)]
            if len(suffix) != 1:
                stem = [f for f in files if f.rsplit("/", 1)[-1] == base.rsplit("/", 1)[-1]]
                suffix = stem if len(stem) == 1 else suffix
            if len(suffix) == 1:
                hit = suffix[0] + (n[len(base):] if "::" in n else "")
            else:
                unresolved.append(n)
                continue
        if hit not in resolved:
            resolved.append(hit)
    return resolved, unresolved


def run_verifier(repo, task, head, planner_tests, spec, pdir, session_bin, sessions_root,
                 extra_args, brief_limit, dry_run, attempt: int = 1, test_files: dict[str, str] | None = None,
                 requirements: list[dict] | None = None) -> dict:
    """A verifier session over the integrated head: run the guarding
    tests and hand off pass/fail. Read-only worktree — the brief tells it
    to keep pytest from writing (``-p no:cacheprovider``); a write-denied
    failure is the harness's, classified ``verifier-env``, not a fail."""
    directory = agents.agent_dir(pdir, f"verifier-{attempt}")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / mail.INBOX).touch()
    (directory / "policy.yaml").write_text(json.dumps(
        {"version": 1, "scope": "agent", "default": "escalate", "rules": [
            {"pattern": "git commit*", "decision": "deny", "reason": "a verifier writes nothing"}]}))
    guards = sorted({t for c in spec.get("contexts", []) for t in _guard_files(c, spec)})
    tests, tests_unresolved = resolve_tests(planner_tests, test_files or {}) if test_files is not None else (list(planner_tests), [])
    tests = tests or guards
    brief = "\n".join([
        "You are a single-use verifier. You change nothing; you run the tests and report.",
        "", f"## Proposal\n{spec.get('proposal', '')}", "",
        *(["## Requirements the plan set out (ADR-085) — each should now be true",
           *(f"- {r['id']}: {r['text']}" + (f" (owner: {', '.join(r['units'])})" if r.get("units") else "")
             for r in requirements), ""] if requirements else []),
        "## Run these tests (through the exec tool)",
        "\n".join(f"- {t}" for t in tests) or "- none named; run the repo's test suite for the changed area",
        *( ["", "Named but not found in the repo (do not guess a path; say so if nothing else runs): "
            + ", ".join(tests_unresolved)] if tests_unresolved else []),
        "", "## Important",
        "- The worktree is read-only. Run pytest with `-p no:cacheprovider` and do not write files.",
        "- If a test cannot run because the tree is read-only, say so in `reason` — that is not a fail.",
        "", "## Your handoff (reflect kind \"handoff\")",
        "verdict: pass or fail", "units: the units to redo if fail (optional)", "reason: what failed",
    ])
    (directory / "brief.md").write_text(brief)
    session = f"{task}-verifier-{attempt}"
    proc = spawn(session_bin, repo, "verifier", directory, session, directory / "brief.md",
                 sessions_root, extra_args, ref=head, dry_run=dry_run)
    log = (proc.stdout + proc.stderr) if proc else ""
    chosen, _ = mail.handoff(mail.reflections(sessions_root / session))
    parsed = parse_handoff(chosen.get("text", "") if chosen else "")
    verdict = parsed.get("verdict", "")
    # A read-only-mount failure is the harness's, not the model's.
    reason = parsed.get("reason", "")
    if verdict == "fail" and ("Read-only file system" in log or "EROFS" in reason or "read-only" in reason.lower()):
        verdict, environment_flag = "verifier-env", True
    else:
        environment_flag = False
    return {"verdict": verdict, "units": parsed.get("units", []), "reason": reason,
            "verdict_source": parsed.get("verdict_source"),
            "stage": {"stage": "verify", "role": "verifier", "agent": f"verifier-{attempt}",
                      "session": session, "attempt": attempt,
                      "exit": proc.returncode if proc else None, "wall_seconds": _wall(proc), "verdict": verdict,
                      "verdict_source": parsed.get("verdict_source"), "reason": reason,
                      "verifier_env": environment_flag, "tests": tests, "tests_unresolved": tests_unresolved}}


def _run_rework(repo, task, target, base, verify, spec, contexts, test_files, dirs,
                orchestrator, records, sessions, integ, session_bin, sessions_root,
                extra_args, brief_limit, stage_log: list[dict], unit_tasks: dict[str, str] | None = None) -> None:
    """One implementer redoes the unit(s) the verifier named, its inbox
    the verifier's handoff. Chained on the current target like the first
    pass."""
    named = [u for u in (verify.get("units") or []) if u in dirs] or [r.unit for r in records if r.spawned]
    for unit in named[:2]:
        session = f"{task}-{unit.lower()}-rw"
        sessions[unit] = session
        record = UnitRecord(unit=unit, role="implementer", session=session, spawned=False)
        mail.post(dirs[unit], "verifier", f"the verifier failed this: {verify.get('reason', '')}", kind="handoff")
        inbox = mail.read(dirs[unit])
        brief = agents.render_brief(spec, unit, "implementer", inbox, session, limit=brief_limit,
                                    task=(unit_tasks or {}).get(unit))
        (dirs[unit] / "brief.md").write_text(brief)
        proc = spawn(session_bin, repo, "implementer", dirs[unit], session, dirs[unit] / "brief.md",
                     sessions_root, extra_args, ref=_head_sha(repo, target, base), dry_run=False)
        record.spawned = True
        record.exit = proc.returncode if proc else None
        record.wall_seconds = _wall(proc)
        _harvest_unit(repo, base, session, contexts[unit], test_files, sessions_root, record, orchestrator, unit)
        _integrate_one(repo, target, unit, session, integ, _manifest_paths(contexts[unit], test_files))
        records.append(record)
        stage_log.append(_unit_stage("rework", unit, record))


def _guard_files(context: dict, spec: dict) -> list[str]:
    test_files = {t: t for t in context.get("guarding_tests", [])}
    return list(test_files)
