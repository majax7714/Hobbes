"""**E4's runner** (`calvin-experiments.md` §6, the E4 card and "E4's design"; D-6 taken as recommended).

E1 asked what context is worth on one held-out body. E4 holds out a **whole file** (rung L1) and asks
whether the graph can serve a small student the pattern and the facts it needs to write that file back,
one definition at a time. It is the first run on that page that **decomposes** (P12, ADR-082): the
planner defines the units, one single-use agent answers each, and every window is smaller than the file.

**A unit is a definition, not a cell.** The held-out file's lattice cells, its non-cell helpers (the
`static inline` `hsum256_ps` and its kind) and its `init_distance_functions_<isa>` are all units, because
at L1 they are all holes. :func:`units` reads them off `scan` and orders them **leaves first** by the
calls in the *gold* bodies — an identifier token in a body's masked text naming another definition of the
same file is an edge — so a unit is only ever asked for after everything it calls has been asked for. A
cycle, if a file has one, is emitted as **one group in file order** and the plan records it; the fixture's
`distance-avx2.c` has none. A file that defines one name twice (every `#if` arm is read, `scan`'s own
rule) is :class:`DuplicateDefinition` rather than two units wearing one name.

**The skeleton is bare, whatever has been filled.** :func:`skeleton` is the file's text down to the end of
the unit's own signature with **every other definition's body replaced by `;`** — a prototype. Includes,
macros, types, comments and the helpers' signatures stay byte for byte. That is stricter than C-0's
`task.prelude_bare`, which keeps the non-cell helpers' bodies: at L1 those helpers are held out too, so
their bodies would be gold in a prompt, and a body reaches a prompt only as an arm's shot (E4-b).

**Three arms, one variable apart** (E4-c), and two named seams:

| arm | on top of the one before | isolates |
|---|---|---|
| **S-0** | the skeleton and the hole | skill |
| **S-2** | the **graph-served ISA-axis shots**: the same `(type, metric)` cell in each other native file | pattern |
| **S-3** | the ledger's callees for a cell | facts |
| *S-5* | the parser's fields (§5.2) — **the second unit's** | the parser's words |
| *S-2o* | the student's own passed bodies as shots — **the second unit's** | growing a file from its own work |

Asking :func:`plan` for `S-5` or `S-2o` is :class:`NotBuilt`, named, and not an empty arm: an arm is a
claim about what was carried, and S-2 wearing S-5's name would be recorded as the parser's result.
**Expected, from E1's own rows:** of Qwen's 18 C-2 greedy passes the answer sat nearest the *type*-axis
shot in 12, and at L1 the type neighbours are inside the held-out file, so S-2's ISA-only shots are
expected *below* E1's C-2.

**A failed unit does not cascade** (E4-d). Every unit is graded **against the gold file with that one
definition punched** — `grade`'s unit entry form — so a wrong `hsum256_ps` fails on its own and every
cell that calls it is still graded against the target's own helper. Gold never enters a prompt. Beside
the per-unit reading, :func:`file_level` builds the file **the student actually wrote**: every unit's
greedy body where that unit passed, gold elsewhere, compiled and graded once over every slot the file
installs, written to `final/<arm>/` with a unified diff against the target's own file.

**What this module does not hold.** No model appears in it: the generator and the grader are injected
callables, exactly as in :mod:`lattice.e1`, whose loop, ceiling, resume and pricing this module reuses
whole with `rounds=0` — E4 does not iterate.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, NamedTuple, Sequence

from . import e1, holes, prompts
from .cells import ISAS, NATIVE, Cell, Lattice
from .cells import build as build_lattice
from .facts import Facts
from .scan import Span

__all__ = [
    "ARMS",
    "COMPARISONS",
    "FACTS_ARMS",
    "FILE_LEVEL",
    "FINAL",
    "INSTRUCTION",
    "K",
    "KINDS",
    "NO_FACTS",
    "NO_SHOTS",
    "P12",
    "PLANNED",
    "RUNG",
    "SHOT_ARMS",
    "SYSTEM",
    "DuplicateDefinition",
    "NotBuilt",
    "Shot",
    "Unit",
    "context",
    "cycles",
    "file_level",
    "fill_units",
    "meta",
    "messages",
    "plan",
    "reaching_cells",
    "run",
    "shots",
    "skeleton",
    "turns",
    "units",
]

#: The rung: the whole file is held out (E4-a). L3 — the whole directory — is a later run.
RUNG = "L1"

#: The arms this unit builds, in the order the report reads them.
ARMS = ("S-0", "S-2", "S-3")

#: The arms E4's design names and the **second** unit builds. Named here so that asking for one is a
#: refusal that says where it is, rather than an `UnknownArm` that reads as a typo.
PLANNED = ("S-5", "S-2o")

#: The arm that carries the ledger's facts, and the arms that carry the graph's shots.
FACTS_ARMS = ("S-3",)
SHOT_ARMS = ("S-2", "S-3")

#: The two comparisons E4-f registers, each `(first, second)` and read as `second − first`, paired by unit.
COMPARISONS = (("S-0", "S-2"), ("S-3", "S-5"))

#: The P12 record (ADR-082, and ADR-086's check): planner-defined units, one single-use agent each, every
#: window smaller than the file. E1 records `arm=model+prompt`; this is the other answer.
P12 = "decomposed"

#: E4-e's sampling: greedy plus ten draws (E3's revised floor), and no iterate rounds.
K = 10

#: What a unit can be. `cell` is a lattice cell, `init` the file's `init_distance_functions_<isa>`, and
#: `helper` everything else the file defines.
KINDS = ("cell", "helper", "init")

#: The run directory's two E4 files, beside E1's own.
FILE_LEVEL = "file_level.jsonl"
FINAL = "final"

#: The one fixed system line and the closing instruction, E1's word for word: the arms are what varies,
#: and a second wording would make E4's rates incomparable with E1's.
SYSTEM = prompts.SYSTEM
INSTRUCTION = prompts.INSTRUCTION

#: What a shot arm says when it carries no shot, by the unit's kind. Silence would read as S-0.
NO_SHOTS = {
    "helper": "shots: none (helper)",
    "cell": "shots: none (no other native file defines this (type, metric))",
    "init": "shots: none (no other native file defines an init function)",
}

#: What S-3 says when it carries no facts. The ledger answers a cell's callees; a helper and the init are
#: not cells, and a cell the ledger named nothing for is a third case, said as such.
NO_FACTS = {
    "cell": "facts: none (the ledger named no callee)",
    "helper": "facts: none (helper)",
    "init": "facts: none (init)",
}

_FILE_HEADING = "The file this function is in, its other definitions as prototypes:"
_SHOTS_HEADING = "The same function in the instruction sets that stay:"
_CALLS_HEADING = "What this function calls, read from the project's graph and the compiler's own key:"
_SIGNATURE_HEADING = "The function to write:"
_NO_SIGNATURE = "(no signature)"

#: An identifier token. The grain the call edges, the order and the reach are all read at.
_IDENT = re.compile(r"[A-Za-z_]\w*")


class NotBuilt(Exception):
    """An arm E4's design names and this unit does not build, asked for by name.

    Its own type (P10, ADR-036): a general "no such arm" handler would report a planned arm as a typo,
    and filling it with the arm below it would record S-3's context under S-5's name.
    """


class DuplicateDefinition(Exception):
    """The file defines one name at more than one place, so a unit would not be one definition.

    `scan` reads **every** arm of an `#if`/`#else` (its docstring says why), so a name defined once per
    arm comes back once per definition. Two units under one name would share a request id, a seed and a
    hole, and the run would grade one of them twice without saying which.
    """


@dataclass(frozen=True)
class Unit:
    """One definition of the held-out file: what it is called, what it is, and where it sits.

    `cell` is the lattice cell id where the unit is one, and `None` for a helper and for the init. The
    spans are the file's own, so `holes.punch` reads a unit exactly as it reads a cell.
    """

    name: str
    kind: str  # one of KINDS
    cell: str | None
    signature: str
    signature_span: Span
    body_span: Span


class Shot(NamedTuple):
    """One graph-served shot: the ISA it comes from, what it is there, and its text."""

    isa: str
    source: str  # the cell id, or the init function's name
    text: str


# MARK: - the units and their order -


def calls_within(lattice: Lattice, isa: str) -> dict[str, tuple[str, ...]]:
    """Each definition's calls **inside its own file**, read off its gold body's masked text.

    The rule is one line long and is the same one the order, the reach and a helper's graded slots are
    all read by: an identifier token in the body that names another definition of this file is an edge.
    Masked, so a name in a comment or a string literal is not one — and so a call inside an `#if` in a
    body is not one either, which is what a text rule can honestly say here.
    """
    source = lattice.sources[isa]
    defined = {fn.name for fn in source.scanned.functions}
    found: dict[str, tuple[str, ...]] = {}
    for fn in source.scanned.functions:
        body = source.scanned.masked[fn.body_span.start : fn.body_span.end]
        named = {token.group(0) for token in _IDENT.finditer(body)}
        found[fn.name] = tuple(
            name for name in sorted(named & defined) if name != fn.name
        )
    return found


def units(lattice: Lattice, isa: str) -> list[Unit]:
    """Every definition of that ISA's file as a :class:`Unit`, **leaves first** (E4-b).

    A unit is emitted only once every definition it calls has been emitted; among the units with no
    callee left, the file's own order. A cycle is one group in file order — :func:`cycles` names them.
    """
    ordered, _ = _read_units(lattice, isa)
    return ordered


def cycles(lattice: Lattice, isa: str) -> list[list[str]]:
    """The call cycles in that file, each as one group in file order. Empty where the calls are a DAG."""
    _, found = _read_units(lattice, isa)
    return found


def _read_units(lattice: Lattice, isa: str) -> tuple[list[Unit], list[list[str]]]:
    source = lattice.sources[isa]
    by_name: dict[str, Unit] = {}
    cell_of = {cell.name: cell.id for cell in lattice.by_isa(isa)}
    for fn in source.scanned.functions:
        if fn.name in by_name:
            raise DuplicateDefinition(
                f"{source.file} defines {fn.name} at line {by_name[fn.name].signature_span.line} and "
                f"again at line {fn.signature_span.line}; a unit is one definition"
            )
        kind = "cell" if fn.name in cell_of else "init" if fn.name == source.init else "helper"
        by_name[fn.name] = Unit(
            name=fn.name,
            kind=kind,
            cell=cell_of.get(fn.name),
            signature=fn.signature,
            signature_span=fn.signature_span,
            body_span=fn.body_span,
        )

    calls = calls_within(lattice, isa)
    groups = _groups(list(by_name), calls)
    ordered = [by_name[name] for group in _leaves_first(groups, calls) for name in group]
    return ordered, [list(group) for group in groups if len(group) > 1]


def _groups(order: list[str], calls: dict[str, tuple[str, ...]]) -> list[list[str]]:
    """The names grouped by cycle — a name that calls itself back is one group with its cycle."""
    reach = {name: _reachable(name, calls) for name in order}
    seen: set[str] = set()
    groups: list[list[str]] = []
    for name in order:
        if name in seen:
            continue
        group = [other for other in order if other == name or (other in reach[name] and name in reach[other])]
        seen.update(group)
        groups.append(group)
    return groups


def _reachable(name: str, calls: dict[str, tuple[str, ...]]) -> set[str]:
    """Every definition *name* reaches, through any number of steps. Includes *name* itself in a cycle."""
    found: set[str] = set()
    stack = list(calls.get(name, ()))
    while stack:
        at = stack.pop()
        if at in found:
            continue
        found.add(at)
        stack.extend(calls.get(at, ()))
    return found


def _leaves_first(groups: list[list[str]], calls: dict[str, tuple[str, ...]]) -> list[list[str]]:
    """The groups, emitted in waves: every group whose callees are all out already, in file order."""
    at = {name: index for index, group in enumerate(groups) for name in group}
    needs = {
        index: {at[callee] for name in group for callee in calls.get(name, ()) if at.get(callee, index) != index}
        for index, group in enumerate(groups)
    }
    emitted: set[int] = set()
    out: list[list[str]] = []
    while len(emitted) < len(groups):
        ready = [index for index in range(len(groups)) if index not in emitted and needs[index] <= emitted]
        if not ready:  # the groups are a DAG by construction; this is the belt beside the braces
            ready = [index for index in range(len(groups)) if index not in emitted]
        for index in ready:
            out.append(groups[index])
            emitted.add(index)
    return out


def reaching_cells(lattice: Lattice, isa: str, name: str) -> tuple[Cell, ...]:
    """The lattice cells whose gold body reaches *name*, in the file's order.

    Reach is transitive over **every** definition of the file, not only the helpers: a cell that gets to
    a helper through another cell exercises it just the same, and the question this answers is which of
    the file's table slots run the helper's code at all. A helper no cell reaches is exercised by
    nothing, which `grade` records as `unexercised` rather than as a body that failed.
    """
    calls = calls_within(lattice, isa)
    return tuple(
        cell
        for cell in lattice.by_isa(isa)
        if cell.name != name and name in _reachable(cell.name, calls)
    )


# MARK: - the skeleton -


def skeleton(lattice: Lattice, isa: str, unit: Unit) -> str:
    """The file down to the end of *unit*'s signature, every other body reduced to `;` (E4-b).

    Every other definition above the hole reads as a prototype — `static inline float hsum256_ps(__m256
    v);` — whatever has been filled for grading, because a body reaches a prompt only as an arm's shot.
    Everything the mask would have blanked is the file's own bytes here: the includes, the `#if`
    guards, the macros, the types and the comments the author wrote.
    """
    source = lattice.sources[isa]
    text = source.text[: unit.signature_span.end]
    above = [
        fn
        for fn in source.scanned.functions
        if fn.name != unit.name and fn.body_span.end <= unit.signature_span.start
    ]
    for fn in sorted(above, key=lambda other: other.body_span.start, reverse=True):
        text = text[: fn.signature_span.end] + ";" + text[fn.body_span.end :]
    return text


# MARK: - the shots and the facts -


def shots(lattice: Lattice, isa: str, unit: Unit) -> list[Shot]:
    """The graph-served ISA-axis shots for *unit*, in the order of `ISAS` (E4-c).

    For a **cell**, the same `(type, metric)` cell in each other **native** file — `sse2` and `avx512`
    when `avx2` is held out, which is why E4-a holds out `avx2` first. For the **init**, the other native
    files' own init functions. For a **helper**, none: a helper has no grid position, so the lattice's
    rule has no neighbour to serve, and the arm says so (:data:`NO_SHOTS`) rather than reading as S-0.

    `cpu` is never a shot, as in E1: it is G-diff's own reference, and handing a model the reference is a
    different reading. `neon` and `rvv` do not run on this box.
    """
    if unit.kind == "helper":
        return []
    others = [other for other in ISAS if other != isa and other in NATIVE and other in lattice.sources]
    found: list[Shot] = []
    for other in others:
        if unit.kind == "init":
            source = lattice.sources[other]
            definition = next((fn for fn in source.scanned.functions if fn.name == source.init), None)
            if definition is None:
                continue
            found.append(Shot(other, source.init, source.text[definition.signature_span.start : definition.body_span.end]))
            continue
        cell = lattice.get(unit.cell)
        sibling = lattice.cells.get(f"{other}/{cell.type}/{cell.metric}")
        if sibling is None:
            continue
        found.append(Shot(other, sibling.id, prompts.definition(lattice, sibling)))
    return found


def context(lattice: Lattice, isa: str, unit: Unit, arm: str, facts: Facts | None = None) -> dict:
    """One arm's context for one unit, as data: what it carries, and what it says it does not.

    A facts arm with no ledger is `prompts.NoLedger` and never filled empty, exactly as C-1 is: an empty
    S-3 is S-2 under another name, and a row recorded under the wrong arm is worse than a row missing.
    """
    if arm in PLANNED:
        raise NotBuilt(f"{arm} is built in the second unit; the arms this one builds are {', '.join(ARMS)}")
    if arm not in ARMS:
        raise prompts.UnknownArm(f"{arm!r} is not one of {', '.join(ARMS + PLANNED)}")
    if arm in FACTS_ARMS and facts is None:
        raise prompts.NoLedger(f"{arm} is a facts arm and no ledger was given; it is never filled empty")

    carried = shots(lattice, isa, unit) if arm in SHOT_ARMS else []
    rows: list[dict] | None = None
    if arm in FACTS_ARMS:
        rows = list(facts.callees(lattice, lattice.get(unit.cell))) if unit.kind == "cell" else []
    return {
        "arm": arm,
        "rung": RUNG,
        "isa": isa,
        "unit": unit.name,
        "kind": unit.kind,
        "skeleton": skeleton(lattice, isa, unit),
        "shots": [{"isa": shot.isa, "from": shot.source, "text": shot.text} for shot in carried],
        "shots_note": None if arm not in SHOT_ARMS or carried else NO_SHOTS[unit.kind],
        "facts": rows,
        "facts_note": None if rows is None or rows else NO_FACTS[unit.kind],
        "signature": unit.signature,
    }


def messages(lattice: Lattice, isa: str, unit: Unit, arm: str, facts: Facts | None = None) -> list[dict]:
    """The chat turns for one (unit, arm): the fixed system line, and one user turn — E1's shape."""
    return turns(context(lattice, isa, unit, arm, facts))


def turns(data: dict) -> list[dict]:
    """The same turns from a context already built, so a caller that wants both does not build it twice."""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": _user(data)}]


def _user(data: dict) -> str:
    """The user turn: the skeleton, the shots (or the note), the facts (or the note), the hole."""
    parts = [_section(_FILE_HEADING, _fenced(data["skeleton"]))]
    if data["shots"]:
        blocks = "\n\n".join(f"/* {row['isa']}: {row['from']} */\n{row['text']}" for row in data["shots"])
        parts.append(_section(_SHOTS_HEADING, _fenced(blocks)))
    elif data["shots_note"]:
        parts.append(data["shots_note"])

    if data["facts"]:
        parts.append(_section(_CALLS_HEADING, "\n".join(_callee_line(row) for row in data["facts"])))
    elif data["facts_note"]:
        parts.append(data["facts_note"])

    parts.append(_section(_SIGNATURE_HEADING, _fenced(data["signature"])))
    parts.append(INSTRUCTION)
    return "\n\n".join(parts)


def _callee_line(row: dict) -> str:
    """One callee, in E1's own line: the name, the signature the ledger holds, and where it came from."""
    return f"- {row['name']}: {row.get('signature') or _NO_SIGNATURE} [{row.get('provenance')}]"


def _section(heading: str, body: str) -> str:
    return f"{heading}\n\n{body}"


def _fenced(text: str) -> str:
    return f"```c\n{text.rstrip()}\n```"


# MARK: - the plan -


def plan(
    lattice: Lattice,
    isa: str,
    arms: Sequence[str],
    model: str,
    facts: Facts | None = None,
    k: int = K,
) -> list[dict]:
    """Round 0's requests: one chat request per (unit, arm, sample), in the units' own order.

    Sample 0 is greedy and samples 1 to *k* are drawn at E1's parameters. The seeds are `e1.seed` with
    the **unit's name** where a cell id would stand, so a run planned twice asks for the same samples.
    No G-mem probe: E4 reads one file, and its cells' probes are E1's own rows.
    """
    ordered = units(lattice, isa)
    made: list[dict] = []
    for unit in ordered:
        cell = lattice.get(unit.cell) if unit.cell else None
        for arm in arms:
            data = context(lattice, isa, unit, arm, facts)
            built = turns(data)
            for sample in range(0, k + 1):
                greedy = sample == 0
                made.append(
                    {
                        # `cell` is E1's pairing key, and a unit stands where a cell does: it holds the
                        # **unit's name**, because a helper and the init have no grid position. The cell
                        # id, where the unit is one, rides beside it.
                        "cell": unit.name,
                        "unit": unit.name,
                        "cell_id": unit.cell,
                        "name": unit.name,
                        "kind": unit.kind,
                        "isa": isa,
                        "type": None if cell is None else cell.type,
                        "metric": None if cell is None else cell.metric,
                        "signature": unit.signature,
                        "id": e1.request_id(unit.name, arm, sample, 0),
                        "arm": arm,
                        "sample": sample,
                        "round": 0,
                        "mode": "chat",
                        "messages": built,
                        "shots": [{"isa": row["isa"], "from": row["from"]} for row in data["shots"]],
                        "shots_note": data["shots_note"],
                        "facts_note": data["facts_note"],
                        "params": {
                            "temperature": 0.0 if greedy else e1.TEMPERATURE,
                            "top_p": 1.0 if greedy else e1.TOP_P,
                            "max_tokens": e1.MAX_TOKENS,
                            "seed": e1.seed(model, unit.name, arm, sample, 0),
                        },
                    }
                )
    return made


def meta(
    lattice: Lattice,
    isa: str,
    requests: Sequence[dict],
    model: str,
    *,
    arms: Sequence[str],
    k: int = K,
    target: Path | str | None = None,
    facts: Facts | None = None,
) -> dict:
    """The run's `meta.json`: E1's record, plus the rung, the units' order and the P12 decomposition.

    `cells` holds the unit names — a unit stands where a cell does in E1's schema — and `units` holds the
    order with each unit's kind. **`p12` is `decomposed`** (:data:`P12`), and `decomposition` carries the
    unit count, the largest prompt and the held-out file's own length, so ADR-086's check can read off
    the record that every implementer's window was smaller than the task.
    """
    ordered, cycled = _read_units(lattice, isa)
    file_chars = len(lattice.sources[isa].text)
    largest = max((e1.prompt_chars(request) for request in requests), default=0)
    record = e1.meta(
        model,
        arms=arms,
        cells=[unit.name for unit in ordered],
        k=k,
        rounds=0,
        iterate=(),
        target=target,
        facts=facts,
    )
    record.update(
        {
            "rung": RUNG,
            "isa": isa,
            "file": lattice.sources[isa].file,
            "units": [{"name": unit.name, "kind": unit.kind, "cell": unit.cell} for unit in ordered],
            "cycles": cycled,
            "p12": P12,
            "decomposition": {
                "unit_count": len(ordered),
                "largest_prompt_chars": largest,
                "file_chars": file_chars,
                "every_window_smaller": largest < file_chars,
            },
        }
    )
    return record


# MARK: - the loop -


def run(
    run_dir: Path | str,
    target: Path | str,
    generate: Callable[[list[dict]], object],
    grade: Callable[[list[dict]], list[dict]],
    *,
    ceiling_usd: float,
) -> dict:
    """Answer and grade every unit, then build the file the student wrote, per arm.

    *generate* is E1's protocol unchanged. *grade* takes **E4's own entries** — a unit's
    `{"id", "unit", "isa", "body"}` and the file level's `{"id", "isa", "bodies"}` — and `e1.default_grade`
    is one, since `lattice grade` reads both forms. E1's loop runs with `rounds=0`: E4 does not iterate,
    so a unit is asked once and read once.
    """
    run_dir = Path(run_dir)
    record = json.loads((run_dir / e1.META).read_text(encoding="utf-8"))
    isa = record["isa"]
    summary = e1.run(
        run_dir, target, generate, _unit_grade(grade, isa), ceiling_usd=ceiling_usd, rounds=0, iterate=()
    )
    summary["file_level"] = file_level(run_dir, target, grade)
    return summary


def _unit_grade(grade: Callable[[list[dict]], list[dict]], isa: str) -> Callable[[list[dict]], list[dict]]:
    """E1's `{"id", "cell", "body"}` entries as E4's unit entries: the `cell` key holds the unit's name."""

    def graded(entries: list[dict]) -> list[dict]:
        return grade([{"id": entry["id"], "unit": entry["cell"], "isa": isa, "body": entry["body"]} for entry in entries])

    return graded


def file_level(
    run_dir: Path | str, target: Path | str, grade: Callable[[list[dict]], list[dict]]
) -> list[dict]:
    """Per arm: the held-out file with every **passing** unit's greedy body, gold elsewhere (E4-d).

    The file is written to `final/<arm>/<file>` with a unified diff against the target's own in
    `final/<arm>/<file>.patch`, and graded once through the same seam as a unit — G-diff over every slot
    the file installs, and G-reg. The row goes in `file_level.jsonl`, and an arm already in that file is
    not built again, so a resume costs nothing.

    The bodies are filled here and again by the grader, both by :func:`fill_units`, so the bytes written
    to `final/` are the bytes graded; `filled_sha256` is on both sides of that seam and on the row.
    """
    run_dir, target = Path(run_dir), Path(target)
    record = json.loads((run_dir / e1.META).read_text(encoding="utf-8"))
    isa = record["isa"]
    lattice = build_lattice(target)
    source = lattice.sources[isa]
    ordered = units(lattice, isa)
    by_name = {unit.name: unit for unit in ordered}

    greedy = [
        row
        for row in _read(run_dir / e1.ROWS)
        if row.get("round") == 0 and row.get("sample") == 0 and row.get("arm")
    ]
    done = {row["arm"] for row in _read(run_dir / FILE_LEVEL)}
    made: list[dict] = []
    for arm in record.get("arms") or sorted({row["arm"] for row in greedy}):
        if arm in done:
            continue
        bodies = {
            row["cell"]: (row.get("extract") or {}).get("body")
            for row in greedy
            if row["arm"] == arm and row.get("class") == "pass" and (row.get("extract") or {}).get("body")
        }
        written = {name: body for name, body in bodies.items() if name in by_name}
        row = {
            "arm": arm,
            "isa": isa,
            "file": source.file,
            "units": len(ordered),
            "units_passed": len(written),
            "unit_names": sorted(written),
            # a passing row whose unit this file no longer defines is named rather than dropped: it means
            # the rows and the target have come apart, which is a fact about the run and not about a body
            "not_a_unit": sorted(set(bodies) - set(written)),
        }
        try:
            filled = fill_units(source.text, [(by_name[name], body) for name, body in written.items()])
        except (holes.UnbalancedBody, holes.NoHole) as refusal:
            row.update({"class": "compile", "reason": str(refusal), "diff_pass": False, "reg": None})
            made.append(row)
            continue
        row["filled_sha256"] = hashlib.sha256(filled.encode("utf-8")).hexdigest()
        row["written"] = _write_final(run_dir, arm, source.file, source.text, filled)
        result = grade([{"id": f"file|{arm}", "isa": isa, "bodies": written}])[0]
        row.update(
            {
                "class": result.get("class"),
                "reason": result.get("reason"),
                "diff_pass": result.get("class") == "pass",
                "reg": result.get("reg"),
                "graded_sha256": result.get("filled_sha256"),
                "bulk": result.get("bulk"),
                "edge": result.get("edge"),
            }
        )
        made.append(row)
    if made:
        _append(run_dir / FILE_LEVEL, made)
    return _read(run_dir / FILE_LEVEL)


def fill_units(text: str, filled: Sequence[tuple[Unit, str]]) -> str:
    """*text* with each unit's body replaced, right to left so the spans stay the ones they were read at.

    One `holes.punch` and one `holes.fill` per unit, on the growing text: the round-trip property the
    graders rest on is `holes`' own, and a whole file rebuilt from gold bodies has to come back byte for
    byte. An unbalanced body is `UnbalancedBody` from there and nothing is written.
    """
    for unit, body in sorted(filled, key=lambda pair: pair[0].body_span.start, reverse=True):
        text = holes.fill(holes.punch(text, unit), body)
    return text


def _write_final(run_dir: Path, arm: str, file: str, gold: str, filled: str) -> str:
    """Write the arm's file and its patch under `final/<arm>/`, and return the run-relative path."""
    into = run_dir / FINAL / arm
    into.mkdir(parents=True, exist_ok=True)
    name = Path(file).name
    (into / name).write_text(filled, encoding="utf-8")
    patch = "".join(
        difflib.unified_diff(
            gold.splitlines(keepends=True),
            filled.splitlines(keepends=True),
            fromfile=f"a/{file}",
            tofile=f"b/{file}",
        )
    )
    (into / f"{name}.patch").write_text(patch, encoding="utf-8")
    return f"{FINAL}/{arm}/{name}"


# MARK: - JSONL -


def _read(path: Path | str) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append(path: Path | str, rows: Iterable[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(f"{json.dumps(row, sort_keys=True)}\n")
