"""**The five context arms** (`calvin-experiments.md` §5.3, C-0 to C-4) as prompts, by rule.

E1 asks how much each kind of context moves the pass rate on a held-out kernel body, so the arms differ
in exactly one thing each and nothing else may vary between them:

| arm | on top of the file's own context | isolates |
|---|---|---|
| **C-0** | nothing | skill |
| **C-1** | the ledger's `callees`, and the callers the lattice knows | facts |
| **C-2** | one pattern shot per axis (`shots`) | pattern |
| **C-3** | C-1 and C-2 together | the pair |
| **C-4** | the same number of lines of non-neighbour bodies (`control`) | volume |

**The prelude is always the bare one.** `task.prelude_bare` reduces every *other* lattice cell above the
hole to its prototype, and the full `prelude` does not: on a real kernel file that text carries the
sibling bodies, which are the shots C-2 is meant to add (session `2fd4`'s review). Handing them to C-0
would make every arm a pattern arm and the experiment unreadable. Non-cell helpers keep their bodies in
both, because a static `hsum256_ps` is a fact about the file the body must be able to call.

**The shot rule is E1-a's, and it is a rule, not a model.** A task record lists up to 14 axis
neighbours, among them `cpu`, `neon`, `rvv` and the one-line wrappers, so "one step on each axis" has to
say which one. At most one shot per axis, in the order ISA, type, metric; each is a real body (`body` or
`impl`) unless the hole is a wrapper, in which case its shots are wrappers, since a wrapper's whole
content is the one call its siblings also make. Shots never come from `cpu`, `neon` or `rvv`: `cpu` is
G-diff's own reference and handing a model the reference is a different reading, and the other two do
not run on this box. **The ISA axis has the pairing and no fallback**: E1-a fixes one crossing per ISA,
so every row crosses the same distance. The type and metric axes fall back to the first qualifying
neighbour in the record's order, and where nothing qualifies the arm carries fewer shots and says so.

**C-4 is the control for "more code in context"** (E1-b), not a second pattern arm: whole real bodies
from the hole's own file that differ from it on **both** type and metric, taken in the file's order from
a start derived from the cell id with SHA-256 — never Python's `hash()`, which is salted per process and
would make a run unrepeatable. They are added until their line count reaches the C-2 shots' count for
the same cell, the last one cut at a line boundary, so C-2 − C-4 reads as pattern rather than volume.

**A facts arm without a ledger is refused** (`NoLedger`), never filled empty: C-1 with no callees is
C-0 under another name, and a row recorded under the wrong arm is worse than a row missing. What the
ledger did not answer is simply not in the prompt — `missing` is read from `lattice facts`, and nothing
here infers a callee.

Every function here reads text and returns data. The same inputs give the same bytes, and nothing in
the output names the target's path: the prelude, the definitions and the signatures are the files' own
bytes, and a cell is named by its `<isa>/<type>/<metric>` id.
"""

from __future__ import annotations

import hashlib
from typing import NamedTuple

from . import task
from .cells import NATIVE, Cell, Lattice
from .facts import Facts

__all__ = [
    "ARMS",
    "CONTROL_ARMS",
    "FACTS_ARMS",
    "INSTRUCTION",
    "SHOT_ARMS",
    "SYSTEM",
    "Control",
    "NoLedger",
    "Shot",
    "UnknownArm",
    "callers",
    "context",
    "control",
    "definition",
    "line_count",
    "messages",
    "shots",
    "turns",
]

#: The five arms of §5.3, in the order the report reads them.
ARMS = ("C-0", "C-1", "C-2", "C-3", "C-4")

#: The arms that carry the ledger's facts, the ones that carry shots, and the one that carries the control.
FACTS_ARMS = ("C-1", "C-3")
SHOT_ARMS = ("C-2", "C-3")
CONTROL_ARMS = ("C-4",)

#: The one fixed system line. It is the same in every arm, because the arms are what is varied.
SYSTEM = (
    "You write C. Given a source file's context and one function's signature, "
    "you write that function's definition and nothing else."
)

#: The instruction the user turn ends on, word for word (E1-c).
INSTRUCTION = "Write this function. Reply with one C code block holding the whole definition."

#: The ISA a shot may cross to. `avx2` is one step from both `sse2` and `avx512`, and `sse2` from `avx2`.
ISA_PAIR = {"sse2": "avx2", "avx512": "avx2", "avx2": "sse2"}

#: The type a shot crosses to, and the metric. A wrapper hole adds `l2 ↔ l2_squared` to the metrics.
TYPE_PAIR = {"float32": "float16", "float16": "float32", "bfloat16": "float16", "uint8": "int8", "int8": "uint8"}
METRIC_PAIR = {"l2_impl": "l1", "l1": "l2_impl", "dot": "cosine", "cosine": "dot"}
WRAPPER_METRIC_PAIR = {"l2": "l2_squared", "l2_squared": "l2"}

#: The ISAs a shot may come from. The same three the lattice calls `NATIVE`, for two reasons that
#: coincide here: `cpu` is G-diff's reference, and `neon` and `rvv` do not run on this box.
SHOT_ISAS = NATIVE

#: What counts as a real body, as against a wrapper's one call.
REAL_BODY = ("body", "impl")

_NO_SIGNATURE = "(no signature)"
_FILE_HEADING = "The file this function is in, above it:"
_RELATED_HEADING = "Related functions:"
_CALLS_HEADING = "What this function calls, read from the project's graph and the compiler's own key:"
_CALLERS_HEADING = "What calls it:"
_SIGNATURE_HEADING = "The function to write:"


class NoLedger(Exception):
    """A facts arm (C-1, C-3) was asked for without a ledger, so it was not built.

    Its own type, because a general "something was missing" handler must not absorb it (P10, ADR-036):
    an empty facts arm is C-0 wearing C-1's name, and the run would record the wrong arm.
    """


class UnknownArm(ValueError):
    """That is not one of `ARMS`."""


class Shot(NamedTuple):
    """One pattern shot: the neighbour, the axis it crosses, and the rule that chose it."""

    cell: Cell
    axis: str  # "isa" | "type" | "metric"
    rule: str  # "pairing" | "fallback"


class Control(NamedTuple):
    """One of C-4's bodies: the cell, the text carried, and whether that text was cut short."""

    cell: Cell
    text: str
    cut: bool


def definition(lattice: Lattice, cell: Cell) -> str:
    """The cell's whole definition — signature and body — exactly as its own file writes it."""
    return lattice.text(cell)[cell.signature_span.start : cell.body_span.end]


def line_count(text: str) -> int:
    """The lines a piece of context carries, which is the unit C-4 is matched in.

    `split` and not `splitlines`: a body cut at a line boundary can end on a blank line the file wrote,
    and that blank line is one of the lines carried — `splitlines` drops it and the arm would then read as
    one line short of the match it made.
    """
    return len(text.split("\n")) if text else 0


# MARK: - C-2, the shots -


def shots(lattice: Lattice, cell: Cell) -> list[Shot]:
    """At most one shot per axis for *cell*, in the order ISA, type, metric (E1-a).

    An axis with no qualifying neighbour contributes nothing, so the list runs from three shots down to
    none; `bit1` on the real target has neither a type nor a metric neighbour and keeps its ISA sibling
    alone.
    """
    found = [_axis_shot(lattice, cell, axis) for axis in ("isa", "type", "metric")]
    return [shot for shot in found if shot is not None]


def _axis_shot(lattice: Lattice, cell: Cell, axis: str) -> Shot | None:
    paired = _paired_id(cell, axis)
    if paired is not None:
        candidate = lattice.cells.get(paired)
        if candidate is not None and _qualifies(candidate, cell):
            return Shot(candidate, axis, "pairing")
    if axis == "isa":
        # no fallback here: E1-a fixes one crossing per ISA so that every row crosses the same distance,
        # and the neighbours a fallback could otherwise reach are `cpu` — G-diff's own reference — `neon`,
        # `rvv`, or the third native ISA, which is a reading of its own
        return None
    for neighbour in lattice.neighbours(cell):
        if _axis_of(neighbour, cell) == axis and _qualifies(neighbour, cell):
            return Shot(neighbour, axis, "fallback")
    return None


def _paired_id(cell: Cell, axis: str) -> str | None:
    """The id of the cell one *axis* step away under the pairing, or `None` where the pairing has none."""
    if axis == "isa":
        crossed = ISA_PAIR.get(cell.isa)
        return None if crossed is None else f"{crossed}/{cell.type}/{cell.metric}"
    if axis == "type":
        crossed = TYPE_PAIR.get(cell.type)
        return None if crossed is None else f"{cell.isa}/{crossed}/{cell.metric}"
    pairs = {**METRIC_PAIR, **WRAPPER_METRIC_PAIR} if cell.kind == "wrapper" else METRIC_PAIR
    crossed = pairs.get(cell.metric)
    return None if crossed is None else f"{cell.isa}/{cell.type}/{crossed}"


def _axis_of(other: Cell, cell: Cell) -> str | None:
    """Which axis *other* crosses from *cell*. A `Lattice.neighbours` row crosses exactly one."""
    if other.isa != cell.isa:
        return "isa"
    if other.type != cell.type:
        return "type"
    if other.metric != cell.metric:
        return "metric"
    return None


def _qualifies(candidate: Cell, cell: Cell) -> bool:
    """A shot is a real body on a native ISA — or a wrapper, when the hole is one — and never the hole."""
    if candidate.id == cell.id or candidate.isa not in SHOT_ISAS:
        return False
    return candidate.kind == "wrapper" if cell.kind == "wrapper" else candidate.kind in REAL_BODY


# MARK: - C-4, the volume control -


def control(lattice: Lattice, cell: Cell, lines: int) -> list[Control]:
    """*lines* lines of non-neighbour bodies from the hole's own file (E1-b).

    The candidates are that file's real bodies differing from the hole on **both** type and metric — so
    neither a shot nor the hole itself can be among them — taken in the file's order from a start
    derived from the cell id. Bodies are added whole until one would overshoot; that one is cut at a
    line boundary, so the total equals *lines* exactly, and falls short of it only when the file runs
    out of candidates.
    """
    candidates = _control_candidates(lattice, cell)
    if lines <= 0 or not candidates:
        return []
    start = _start(cell.id, len(candidates))
    rows: list[Control] = []
    carried = 0
    for candidate in candidates[start:] + candidates[:start]:
        if carried >= lines:
            break
        text = definition(lattice, candidate)
        written = text.split("\n")
        room = lines - carried
        cut = len(written) > room
        rows.append(Control(candidate, "\n".join(written[:room]) if cut else text, cut))
        carried += room if cut else len(written)
    return rows


def _control_candidates(lattice: Lattice, cell: Cell) -> list[Cell]:
    """The file's real bodies that differ from the hole on both type and metric, in the file's order."""
    taken = {shot.cell.id for shot in shots(lattice, cell)}
    return [
        other
        for other in lattice.by_isa(cell.isa)
        # differing on both axes already excludes the hole and every shot; the rule is stated, not implied
        if other.kind in REAL_BODY
        and other.type != cell.type
        and other.metric != cell.metric
        and other.id != cell.id
        and other.id not in taken
    ]


def _start(cell_id: str, count: int) -> int:
    """Where in the file's candidates to start, from the cell id: stable across processes and runs."""
    digest = hashlib.sha256(cell_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % count


# MARK: - the callers the lattice knows -


def callers(lattice: Lattice, cell: Cell) -> list[dict]:
    """What reaches *cell*: the wrappers whose one call is to it, and the table slots it is installed in.

    An `_impl` has no slot of its own and is reached through its type's two wrappers, which is what
    `Cell.graded_via` holds and why the wrapper rows carry their own slots. Everything here is the
    lattice's own reading of the files — no ledger is consulted for it.
    """
    rows = [
        {
            "kind": "wrapper",
            "name": wrapper.name,
            "cell": wrapper.id,
            "signature": wrapper.signature,
            "slots": [list(slot) for slot in wrapper.slots],
        }
        for wrapper in _wrappers_of(lattice, cell)
    ]
    rows += [
        {"kind": "slot", "name": _slot_name(slot), "cell": None, "signature": None, "slots": [list(slot)]}
        for slot in cell.slots
    ]
    return rows


def _wrappers_of(lattice: Lattice, cell: Cell) -> list[Cell]:
    """The wrappers that call *cell*: its type's two, when *cell* is the `_impl` they are classified by."""
    if cell.kind != "impl":
        return []
    found = [
        other
        for other in lattice.cells.values()
        if other.kind == "wrapper" and other.isa == cell.isa and other.type == cell.type
    ]
    return sorted(found, key=lambda other: other.body_span.start)


def _slot_name(slot) -> str:
    metric_enum, type_enum = slot
    return f"dispatch_distance_table[VECTOR_DISTANCE_{metric_enum}][VECTOR_TYPE_{type_enum}]"


# MARK: - an arm as data, and as messages -


def context(lattice: Lattice, cell: Cell, arm: str, facts: Facts | None = None) -> dict:
    """One arm's context for one cell, as data: what it carries and how much of it.

    `lines["shots"]` is the figure C-4 is matched to, so on C-4 it is non-zero while `shots` is empty —
    that is the point of the arm, and the two numbers beside each other are how a reader sees whether
    the control reached its match or the file ran out.
    """
    if arm not in ARMS:
        raise UnknownArm(f"{arm!r} is not one of {', '.join(ARMS)}")
    if arm in FACTS_ARMS and facts is None:
        raise NoLedger(f"{arm} is a facts arm and no ledger was given; it is never filled empty")

    measured = shots(lattice, cell) if arm in SHOT_ARMS + CONTROL_ARMS else []
    matched = sum(line_count(definition(lattice, shot.cell)) for shot in measured)
    carried = measured if arm in SHOT_ARMS else []
    controls = control(lattice, cell, matched) if arm in CONTROL_ARMS else []
    return {
        "arm": arm,
        "prelude": task.prelude_bare(lattice, cell),
        "shots": [
            {"cell": shot.cell.id, "rule": shot.rule, "text": definition(lattice, shot.cell)}
            for shot in carried
        ],
        "control": [{"cell": row.cell.id, "text": row.text, "cut": row.cut} for row in controls],
        "facts": None if arm not in FACTS_ARMS else list(facts.callees(lattice, cell)),
        "callers": None if arm not in FACTS_ARMS else callers(lattice, cell),
        "lines": {"shots": matched, "control": sum(line_count(row.text) for row in controls)},
    }


def messages(lattice: Lattice, cell: Cell, arm: str, facts: Facts | None = None) -> list[dict]:
    """The chat turns for one (cell, arm): the fixed system line, and one user turn (E1-c).

    The user turn is plain text with fenced C blocks, in a fixed order — the file's context, the related
    functions, the facts, the signature, the instruction — and a section the arm does not carry takes
    its heading with it.
    """
    return turns(cell, context(lattice, cell, arm, facts))


def turns(cell: Cell, data: dict) -> list[dict]:
    """The same turns from a context already built, so a caller that wants both does not build it twice."""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": _user(cell, data)}]


def _user(cell: Cell, data: dict) -> str:
    parts = [_section(_FILE_HEADING, _fenced(data["prelude"]))]

    related = data["shots"] or data["control"]
    if related:
        blocks = "\n\n".join(f"/* {row['cell']} */\n{row['text']}" for row in related)
        parts.append(_section(_RELATED_HEADING, _fenced(blocks)))

    if data["facts"]:
        parts.append(_section(_CALLS_HEADING, "\n".join(_callee_line(row) for row in data["facts"])))
    if data["callers"]:
        parts.append(_section(_CALLERS_HEADING, "\n".join(_caller_line(row) for row in data["callers"])))

    parts.append(_section(_SIGNATURE_HEADING, _fenced(cell.signature)))
    parts.append(INSTRUCTION)
    return "\n\n".join(parts)


def _callee_line(row: dict) -> str:
    return f"- {row['name']}: {row.get('signature') or _NO_SIGNATURE} [{row.get('provenance')}]"


def _caller_line(row: dict) -> str:
    if row["kind"] != "wrapper":
        return f"- it is installed as {row['name']}"
    line = f"- {row['name']} calls it: {row['signature']}"
    slots = ", ".join(_slot_name(slot) for slot in row["slots"])
    return f"{line}; installed as {slots}" if slots else line


def _section(heading: str, body: str) -> str:
    return f"{heading}\n\n{body}"


def _fenced(text: str) -> str:
    """One fenced C block. Trailing whitespace goes, so the closing fence sits under the last line."""
    return f"```c\n{text.rstrip()}\n```"
