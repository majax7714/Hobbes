"""**G-graph** (`calvin-experiments.md` §5.5): the generated body's callees against the gold's.

The other graders ask whether a body *works*. This one asks whether it is **wired the way the target's
own body is wired** — does it call the file's `hsum256_ps`, does it reach the `_impl`, does it invent a
helper that happens to compile. The answer comes from an ingest of the patched tree, so it is Hobbes'
own edges at the `semantic` tier with `file:line` evidence, and not a regex over the body.

**One ingest per wave, not per body.** An ingest is the expensive step, so bodies are batched: a *wave*
is a set of entries no two of which fill the same cell, because two bodies in one file's one hole is not
a tree. :func:`waves` splits a run's entries into the fewest such sets, deterministically and purely —
the *n*-th body offered for a cell goes in wave *n*. A run of 93 one-body cells is one wave; a run of
five candidates per cell is five.

**Only bodies that compiled go into a wave.** Lane B is a compiler: a translation unit that does not
compile has no semantic answer at all, and grading it would read as "this body calls nothing" when the
truth is that nothing was asked. :func:`keep` drops the `compile` and `invented` classes with that
reason on the row, and says so rather than dropping them silently.

**The work copy is a git repo with one commit.** Hobbes stamps its artifact with the repo's SHA and a
`dirty` flag, so a patched tree is `git init`-ed and committed before it is ingested — the copy is a
tree in its own right, not a dirty checkout of the target.

**`ingest` is injected.** The default, :func:`hobbes_ingest`, runs `uv run --project <checkout>/pipeline
hobbes ingest` in the work copy and reads `.hobbes/derived/graph.json` back. Hobbes contains its own
lane B (ADR-092): the ingest is what puts the *target's* build in the image, so this runs on the host
like `uv run hobbes ingest` does. Nothing in this module compiles or runs a body itself — that is
`grade`'s, and it has already happened by the time a wave is built.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import holes
from .cells import Cell, Lattice, UnknownCell
from .cells import build as build_lattice
from .facts import module_paths, symbol_for

__all__ = [
    "CANNOT_ANSWER",
    "IngestFailed",
    "compare",
    "gold_callees",
    "got_callees",
    "grade",
    "grade_wave",
    "hobbes_ingest",
    "keep",
    "waves",
]

#: The `grade` classes a wave will not carry: lane B has no answer where the compiler had none.
CANNOT_ANSWER = ("compile", "invented")

#: What a work copy is committed as. A bench copy has no author; this one is named for what made it.
_AUTHOR = ("-c", "user.email=lattice@example.invalid", "-c", "user.name=lattice G-graph")

#: Never copied into a work copy: the target's own history, and a derived artifact of another tree.
_NOT_COPIED = frozenset({".git", ".hobbes"})


class IngestFailed(Exception):
    """The ingest of a work copy did not produce a graph, so no body in that wave was graded.

    Its own type (P10, ADR-036): every other answer here is a fact about a body, and this is a fact
    about the instrument. A wave with no graph is not a wave of empty callee sets.
    """


# MARK: - which bodies, in which waves -


def keep(rows) -> tuple[list[dict], list[dict]]:
    """A grading run's rows split into the ones a wave can carry and the ones it cannot.

    A row is an entry (`{"id", "cell", "body"}`) with its `grade` result's `class` beside it. It is
    kept when it has a body and its class is not in :data:`CANNOT_ANSWER`; otherwise it comes back in
    the second list with a `reason`, because a row dropped without one is a row nobody can audit.
    """
    kept: list[dict] = []
    skipped: list[dict] = []
    for row in rows:
        entry = {"id": row.get("id"), "cell": row.get("cell"), "body": row.get("body")}
        if row.get("body") is None:
            skipped.append({**entry, "reason": "the row carries no body"})
        elif row.get("class") in CANNOT_ANSWER:
            skipped.append(
                {**entry, "reason": f"class {row['class']}: a TU that does not compile has no lane B answer"}
            )
        else:
            kept.append(entry)
    return kept, skipped


def waves(entries) -> list[list[dict]]:
    """*entries* split so that no wave holds two bodies for one cell. Deterministic, and pure.

    The *n*-th entry offered for a cell goes into wave *n*, and each wave keeps the order the entries
    came in. Nothing is sorted and nothing is randomised: the same list gives the same waves, which is
    what lets a run be resumed or re-read.
    """
    built: list[list[dict]] = []
    counted: dict[str, int] = {}
    for entry in entries:
        cell = entry.get("cell")
        index = counted.get(cell, 0)
        counted[cell] = index + 1
        while len(built) <= index:
            built.append([])
        built[index].append(entry)
    return built


# MARK: - the comparison -


def gold_callees(graph: dict, cell: Cell) -> set[str]:
    """The in-repo names the target's own body for *cell* calls, at the `semantic` tier.

    In-repo means the edge's target is a symbol this graph holds: an intrinsic is not defined in the
    repo, so the graph draws no edge to it and G-graph does not ask about one (`facts` does, from the
    clang key). `semantic` only — a syntactic edge is a guess, and a guess is not a gold.
    """
    return _callees(graph, cell)


def got_callees(graph: dict, cell: Cell) -> set[str]:
    """The same question of the patched tree's graph. Two names because a comparison has two sides."""
    return _callees(graph, cell)


def _callees(graph: dict, cell: Cell) -> set[str]:
    paths = module_paths(graph)
    symbol = symbol_for(graph, cell, paths)
    if symbol is None:
        return set()
    symbols = {entry.get("id"): entry for entry in graph.get("symbols") or ()}
    found = set()
    for edge in graph.get("symbol_edges") or ():
        if edge.get("from") != symbol.get("id") or edge.get("type") != "calls":
            continue
        if edge.get("tier") != "semantic":
            continue
        target = symbols.get(edge.get("to"))
        if target is not None and target.get("name"):
            found.add(target["name"])
    return found


def compare(gold, got) -> dict:
    """Two callee sets as a JSON-able row: both sides sorted, what is missing, what is extra, Jaccard.

    Jaccard is `|gold ∩ got| / |gold ∪ got|`, and two empty sets score 1.0 — a body that calls nothing
    where the gold calls nothing agrees with it perfectly, which is the only reading that composes.
    """
    gold, got = set(gold), set(got)
    union = gold | got
    return {
        "gold": sorted(gold),
        "got": sorted(got),
        "missing": sorted(gold - got),
        "extra": sorted(got - gold),
        "jaccard": 1.0 if not union else round(len(gold & got) / len(union), 6),
    }


# MARK: - grading a wave -


def grade_wave(
    target: Path | str,
    wave,
    ingest,
    *,
    gold_graph: dict | None = None,
    workdir: Path | str | None = None,
    rename: dict[str, str] | None = None,
) -> list[dict]:
    """Fill every body of *wave* into one work copy of *target*, ingest it, and compare each cell.

    *ingest* takes the work copy's root and returns a graph dict; :func:`hobbes_ingest` builds the
    default. *gold_graph* is the target's own ingest — without one, *ingest* is run over an unpatched
    copy first, which costs a second ingest and asks nobody to supply what the instrument can read.
    *rename* is a shadow's reverse map, passed through to `cells.build`.

    One row per entry: its `cell`, the two callee sets and their comparison, or a `reason` when the
    entry named no cell of this lattice or its body would not fill the hole.
    """
    target = Path(target)
    lattice = build_lattice(target, rename=rename)
    made = Path(workdir) if workdir is not None else None
    with _scratch(made) as scratch:
        if gold_graph is None:
            gold_graph = _ingested(ingest, _copy(target, scratch / "gold"))
        filled, rows = _fill(lattice, wave, _copy(target, scratch / "work"))
        if not filled:
            return rows
        got_graph = _ingested(ingest, scratch / "work")
    for row in rows:
        if row.get("reason") is not None:
            continue
        cell = lattice.get(row["cell"])
        gold = gold_callees(gold_graph, cell)
        got = got_callees(got_graph, cell)
        row.update(compare(gold, got))
        if symbol_for(got_graph, cell) is None:
            row["reason"] = f"the patched tree's graph names no {cell.name} in {cell.file}"
    return rows


def grade(
    target: Path | str,
    entries,
    ingest,
    *,
    gold_graph: dict | None = None,
    workdir: Path | str | None = None,
    rename: dict[str, str] | None = None,
) -> list[dict]:
    """:func:`grade_wave` over every wave of *entries*, the rows back in the order they came.

    The gold is ingested once for the whole run, not once per wave: it is the same tree every time.
    """
    if gold_graph is None:
        with _scratch(None) as scratch:
            gold_graph = _ingested(ingest, _copy(Path(target), scratch / "gold"))
    by_id: dict = {}
    for wave in waves(entries):
        for row in grade_wave(
            target, wave, ingest, gold_graph=gold_graph, workdir=workdir, rename=rename
        ):
            by_id[(row.get("id"), row.get("cell"))] = row
    return [by_id[(entry.get("id"), entry.get("cell"))] for entry in entries]


def _fill(lattice: Lattice, wave, root: Path) -> tuple[bool, list[dict]]:
    """Write each entry's body into *root*, then commit it. Returns (anything filled, the rows)."""
    rows: list[dict] = []
    filled = False
    for entry in wave:
        row = {"id": entry.get("id"), "cell": entry.get("cell"), "reason": None}
        rows.append(row)
        try:
            cell = lattice.get(entry.get("cell", ""))
        except UnknownCell:
            row["reason"] = f"no cell {entry.get('cell')!r} in this lattice"
            continue
        path = root / cell.file
        text = path.read_text(encoding="utf-8")
        body = holes.gold_body(text, cell) if entry.get("body") == "gold" else entry.get("body", "")
        try:
            path.write_text(holes.fill(holes.punch(text, cell), body), encoding="utf-8")
        except (holes.UnbalancedBody, holes.NoHole) as refusal:
            row["reason"] = str(refusal)
            continue
        filled = True
    _commit(root)
    return filled, rows


def _copy(target: Path, dest: Path) -> Path:
    """The target's tree at *dest*, its history and its derived artifacts left behind, committed once."""
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(target, dest, ignore=lambda _, names: [n for n in names if n in _NOT_COPIED])
    _run(["git", "-C", str(dest), "init", "-q"])
    _commit(dest)
    return dest


def _commit(root: Path) -> None:
    _run(["git", "-C", str(root), "add", "-A"])
    done = subprocess.run(
        ["git", "-C", str(root), *_AUTHOR, "commit", "-q", "-m", "the tree G-graph ingests"],
        capture_output=True,
        text=True,
        check=False,
    )
    # "nothing to commit" is an answer, not a failure: an unpatched copy is already what it will be.
    if done.returncode != 0 and "nothing to commit" not in (done.stdout + done.stderr):
        raise IngestFailed(f"the work copy could not be committed: {(done.stderr or done.stdout).strip()}")


def _run(argv: list[str]) -> None:
    done = subprocess.run(argv, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise IngestFailed(f"{' '.join(argv[:3])} failed: {done.stderr.strip()}")


def _ingested(ingest, root: Path) -> dict:
    graph = ingest(root)
    if not isinstance(graph, dict) or not graph.get("symbols"):
        raise IngestFailed(f"the ingest of {root.name} returned no symbols")
    return graph


class _scratch:
    """The scratch dir: the one given, or a temporary one removed on the way out."""

    def __init__(self, given: Path | None):
        self.given = given
        self.temporary: str | None = None

    def __enter__(self) -> Path:
        if self.given is not None:
            self.given.mkdir(parents=True, exist_ok=True)
            return self.given
        self.temporary = tempfile.mkdtemp(prefix="lattice-graph-")
        return Path(self.temporary)


    def __exit__(self, *_) -> None:
        if self.temporary is not None:
            shutil.rmtree(self.temporary, ignore_errors=True)


# MARK: - the default ingest -


def hobbes_ingest(checkout: Path | str, *, timeout: int = 3600):
    """An `ingest(workdir) -> graph` that runs a Hobbes checkout's own CLI over the copy.

    `uv run --project <checkout>/pipeline hobbes ingest`, in the copy, then `.hobbes/derived/graph.json`
    read back. Always that checkout's `hobbes` and never one on `PATH` — the 2026-08-28 incident
    (ADR-094) was a `hobbes` from another tree answering about this one.
    """
    project = Path(checkout) / "pipeline"

    def ingest(workdir: Path) -> dict:
        done = subprocess.run(
            ["uv", "run", "--project", str(project), "hobbes", "ingest"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        graph = Path(workdir) / ".hobbes" / "derived" / "graph.json"
        if done.returncode != 0 or not graph.is_file():
            raise IngestFailed(f"hobbes ingest in {workdir} exited {done.returncode}: {done.stderr.strip()[:1000]}")
        return json.loads(graph.read_text(encoding="utf-8"))

    return ingest
