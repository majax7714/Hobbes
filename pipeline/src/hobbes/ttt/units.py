"""Gold-diff units and the two prompts an arm sees (ADR-099 §2.3, §4.3).

A **unit** is a task with a known answer: a proposal in the task's own
words, the files it touches, and the gold diff. Two sources, reported
apart:

- **git history** — for a repo without a benchmark: every commit after a
  base, split per file, each hunk small enough to be one unit. The
  graph is ingested at the *base*, so a unit's context is what Hobbes
  could see before the change existed; the drift between the base and
  a later commit's parent is the same for every arm.
- **DeepSWE tasks** — ``instruction.md`` as the proposal, the withheld
  ``solution/solution.patch`` as the gold diff, at ``base_commit_hash``.

The **context block** is arm A1's prompt aid: the ADR-077 wording
(``aided_brief``), derived deterministically the way the DeepSWE
prototype derived it (C-55) — seeds from the unit's files, symbols the
proposal names, one hop of the symbol graph, the tests that reach the
seeds — never a planner. The **NLL prompt** is the same for every arm
but for that block; the adapter is the other variable.

The prompt's **conditioning** — what precedes the diff tokens — is a
named variable (review item 2, 2026-09-03). The first run scored every
unit under ``message``: the commit subject and body and the target
path, which the write-up did not say. Three more are rendered beside
it when the unit can carry them: ``none`` (the target path only),
``subject`` (the commit's first line and the path), ``task`` (a
proposal in a task's words — a DeepSWE instruction, or a hand-written
proposal attached by commit — and the path). A unit without a subject
or a task has no row under that conditioning; the scorer counts it.
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from hobbes.run.stages import aided_brief

#: Files a git unit may come from when no prefixes are given: everything.
ANY_PREFIX: tuple[str, ...] = ()
#: Body text a proposal keeps from a commit message.
BODY_CAP = 1_200
#: Added-plus-removed lines a git hunk may hold to be a unit.
DEFAULT_MAX_LINES = 120
DEFAULT_MIN_LINES = 3
#: Tests named in a context block.
TESTS_CAP = 8
#: Generated or lock files never make a unit: nothing to understand.
SKIP_BASENAMES = re.compile(r"(^|/)(go\.sum|uv\.lock|package-lock\.json|yarn\.lock|Cargo\.lock|pnpm-lock\.yaml|.*\.snap)$")
#: Commit-message trailers (``Co-Authored-By: …``) are not the task's words.
_TRAILER = re.compile(r"^[A-Z][A-Za-z-]+: \S.*$")


class UnitError(RuntimeError):
    """A task directory or a git range that cannot yield units."""


@dataclass
class Unit:
    id: str
    repo: str
    sha: str
    source: str
    proposal: str
    files: list[str]
    gold_diff: str
    #: Arm A1's block — empty until :func:`attach_context` runs.
    context: str = ""
    #: What the unit builder could not do (a file absent from the graph).
    notes: list[str] = field(default_factory=list)
    #: The commit's first line (git units); empty for a DeepSWE task.
    subject: str = ""
    #: A proposal in a task's words: the DeepSWE instruction, or a
    #: hand-written proposal attached by commit (:func:`attach_tasks`).
    task: str = ""

    @property
    def diff_lines(self) -> int:
        return sum(1 for ln in self.gold_diff.splitlines() if ln[:1] in "+-" and ln[:3] not in ("+++", "---"))


def files_in_patch(diff: str) -> list[str]:
    """The ``b/`` paths a unified diff touches, in order, deduplicated."""
    out: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:].split("\t")[0].strip()
            path = path[2:] if path.startswith("b/") else path
            if path != "/dev/null" and path not in out:
                out.append(path)
        elif line.startswith("--- ") and "/dev/null" not in line:
            # A deletion has no +++ path worth keeping; the --- one is it.
            path = line[4:].split("\t")[0].strip()
            path = path[2:] if path.startswith("a/") else path
            if path not in out:
                out.append(path)
    return out


def strip_trailers(body: str) -> str:
    """Drop the trailer block a commit body ends with, if any."""
    lines = body.rstrip().splitlines()
    while lines and (_TRAILER.match(lines[-1]) or not lines[-1].strip()):
        lines.pop()
    return "\n".join(lines).strip()


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError as exc:
        raise UnitError(f"git {' '.join(args)}: {exc.stderr.strip()}") from exc


def units_from_git(repo_root: Path, base: str, head: str = "HEAD", *, name: str | None = None,
                   prefixes: tuple[str, ...] = ANY_PREFIX, max_lines: int = DEFAULT_MAX_LINES,
                   min_lines: int = DEFAULT_MIN_LINES) -> list[Unit]:
    """One unit per (commit after *base*, file), for hunks within the line bounds."""
    repo_root = Path(repo_root)
    repo = name or repo_root.resolve().name
    base_sha = _git(repo_root, "rev-parse", base).strip()
    commits = _git(repo_root, "rev-list", "--reverse", f"{base}..{head}").split()
    units: list[Unit] = []
    for commit in commits:
        subject = _git(repo_root, "log", "-1", "--format=%s", commit).strip()
        body = strip_trailers(_git(repo_root, "log", "-1", "--format=%b", commit))
        files = [f for f in _git(repo_root, "show", "--name-only", "--format=", commit).split("\n") if f]
        for path in files:
            if (prefixes and not any(path.startswith(p) for p in prefixes)) or SKIP_BASENAMES.search(path):
                continue
            diff = _git(repo_root, "show", "--format=", "--no-color", commit, "--", path)
            if not diff or "Binary files" in diff.splitlines()[-1:] or "GIT binary patch" in diff:
                continue
            unit = Unit(id=f"{commit[:12]}:{path}", repo=repo, sha=base_sha, source="git",
                        proposal=f"{subject}\n\n{body[:BODY_CAP]}".strip() + f"\n\nIn `{path}`.",
                        files=[path], gold_diff=diff, subject=subject)
            if min_lines <= unit.diff_lines <= max_lines:
                units.append(unit)
    return units


def unit_from_deepswe(task_dir: Path, name: str | None = None) -> Unit:
    """One unit from a DeepSWE task directory."""
    task_dir = Path(task_dir)
    try:
        meta = tomllib.loads((task_dir / "task.toml").read_text())
        instruction = (task_dir / "instruction.md").read_text()
        patch = (task_dir / "solution" / "solution.patch").read_text()
    except (OSError, ValueError) as exc:
        raise UnitError(f"{task_dir}: {exc}") from exc
    md = meta.get("metadata", {})
    repo = name or md.get("repository_url", "").rstrip("/").rsplit("/", 1)[-1] or task_dir.name
    return Unit(id=md.get("task_id", task_dir.name), repo=repo, sha=md.get("base_commit_hash", ""),
                source="deepswe", proposal=instruction.strip(), files=files_in_patch(patch), gold_diff=patch,
                task=instruction.strip())


def read_tasks(path: Path) -> dict[str, str]:
    """``commit → task`` from a JSONL of ``{"commit", "task"}`` rows (a row
    without both keys is ignored — the file may open with a note)."""
    out: dict[str, str] = {}
    for line in Path(path).read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("commit") and row.get("task"):
                out[row["commit"]] = row["task"].strip()
    return out


def attach_tasks(units: list[Unit], tasks: dict[str, str]) -> int:
    """Attach a hand-written task to every git unit whose commit prefix
    matches a key (either may be the shorter); returns how many got one."""
    n = 0
    for unit in units:
        if unit.source != "git":
            continue
        commit = unit.id.split(":", 1)[0]
        for key, task in tasks.items():
            if commit.startswith(key) or key.startswith(commit):
                unit.task = task; n += 1
                break
    return n


_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


def context_block(graph: dict, tests: dict, proposal: str, files: list[str]) -> tuple[str, list[str]]:
    """Arm A1's aid for a unit, and the builder's notes.

    Seeds are the unit's files that the graph knows; symbols are the
    graph's symbols in those files whose name the proposal uses as a
    word (code-shaped or capitalised, the C-55 rule, so prose words do
    not seed); tests are those reaching a seed module. The text is
    ``aided_brief``'s "What Hobbes can see … cannot confirm" span, so the
    wording is ADR-077's and not this experiment's.
    """
    by_path = {n.get("path"): n["id"] for n in graph.get("nodes", []) if n.get("path")}
    notes: list[str] = []
    modules: list[str] = []
    known_files: list[str] = []
    for path in files:
        if path in by_path:
            modules.append(by_path[path]); known_files.append(path)
        else:
            notes.append(f"{path}: not in the graph at this SHA (new file, or outside extraction)")
    words = set(_WORD.findall(proposal))
    symbols = sorted({
        f"{s['module']}.{s['name']}" for s in graph.get("symbols", [])
        if s.get("module") in modules and s.get("name") in words
        and (s["name"][:1].isupper() or "_" in s["name"] or any(c.isupper() for c in s["name"]))
    })[:20]
    guarding = sorted({
        t.get("file") or t["id"].split("::")[0] for t in tests.get("tests", [])
        if any(m in modules for m in (t.get("reaches_modules") or []))
    })[:TESTS_CAP]
    stage = {"files": known_files, "symbols": symbols, "tests": guarding, "approach": "", "handoff": ""}
    brief = aided_brief(proposal, stage, graph)
    block = brief.split("## What Hobbes can see", 1)[1].split("## How to work", 1)[0]
    block = ("## What Hobbes can see" + block).rstrip()
    block += f"\n\n(graph @ {graph.get('sha', '')[:12]}; derived without a planner pass — files from the unit, symbols by name match, C-55)"
    return block, notes


def attach_context(units: list[Unit], graph: dict, tests: dict) -> None:
    for unit in units:
        unit.context, notes = context_block(graph, tests, unit.proposal, unit.files)
        unit.notes.extend(notes)


SYSTEM = "You are a single-use software engineer working in {repo} at commit {sha12}."
ASK = "Write the unified diff that implements the task. Output only the diff."


#: What precedes the diff tokens. ``message`` is what the first run scored.
CONDITIONINGS = ("none", "subject", "message", "task")


def _path_line(u: dict) -> str:
    return "In " + ", ".join(f"`{f}`" for f in u.get("files", [])) + "."


def nll_messages(unit: Unit | dict, with_context: bool, conditioning: str = "message") -> list[dict] | None:
    """The chat the NLL is scored under: system, user (the task under
    *conditioning*, the A1 block when *with_context*), and the gold diff
    as the assistant turn. ``message`` is the unit's proposal as written
    (byte-identical to the first run); ``none`` is the target path alone;
    ``subject`` and ``task`` need the unit to carry one and return None
    when it does not."""
    u = unit if isinstance(unit, dict) else asdict(unit)
    if conditioning not in CONDITIONINGS:
        raise ValueError(f"unknown conditioning {conditioning!r}; one of {', '.join(CONDITIONINGS)}")
    if conditioning == "message":
        head = [u["proposal"].strip()]
    elif conditioning == "none":
        head = [_path_line(u)]
    else:
        text = (u.get(conditioning) or "").strip()
        if not text:
            return None
        head = [text, "", _path_line(u)]
    parts = ["## Task", *head]
    if with_context and u.get("context"):
        parts += ["", u["context"].strip()]
    parts += ["", ASK]
    return [
        {"role": "system", "content": SYSTEM.format(repo=u["repo"], sha12=u["sha"][:12])},
        {"role": "user", "content": "\n".join(parts)},
        {"role": "assistant", "content": u["gold_diff"]},
    ]


def message_keys(conditioning: str) -> tuple[str, str]:
    """The units-file keys of a conditioning's bare and aided chats:
    ``messages_bare`` / ``messages_aided`` for ``message`` (the first
    run's names), ``messages_<conditioning>_bare`` / ``_aided`` otherwise."""
    if conditioning == "message":
        return "messages_bare", "messages_aided"
    return f"messages_{conditioning}_bare", f"messages_{conditioning}_aided"


def write_units(units: list[Unit], path: Path) -> None:
    """One JSON line per unit, carrying the NLL prompts (``messages_bare``,
    ``messages_aided`` for the ``message`` conditioning; ``messages_<c>_bare``
    / ``_aided`` for every other conditioning the unit can carry) so the
    scorer needs nothing but the file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for u in units:
        row = asdict(u)
        for conditioning in CONDITIONINGS:
            bare, aided = message_keys(conditioning)
            chat = nll_messages(u, False, conditioning)
            if chat is not None:
                row[bare] = chat
                row[aided] = nll_messages(u, True, conditioning)
        rows.append(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    path.write_text("".join(rows))


def read_units(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
