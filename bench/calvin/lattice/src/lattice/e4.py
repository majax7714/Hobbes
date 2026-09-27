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

**Five arms, one variable apart** (E4-c):

| arm | on top of the one before | isolates |
|---|---|---|
| **S-0** | the skeleton and the hole | skill |
| **S-2** | the **graph-served ISA-axis shots**: the same `(type, metric)` cell in each other native file | pattern |
| **S-3** | the ledger's callees for a cell | facts |
| **S-5** | the **parser's fields** (§5.2: the contract and the edge cases) | the parser's words |
| **S-2o** | S-2 plus the student's **own passed bodies** on the type and metric axes | growing a file from its own work |
| **S-2h** | for a **helper**, the shots rule W's **name family** serves; for every other kind, S-2 byte for byte | pattern where the grid has no neighbour |

**Rule W, the helper's name family** (D-11 a, pre-registered before this build). E4's record named the
file's weak point: the three native files' 13, 6 and 12 helpers pass at 0.00 to 0.23 in every arm, and
**none of them carries a shot** — a helper has no grid position, so :func:`shots` has nothing to cross.
Their siblings exist by
*name*: `hsum128_ps`, `hsum256_ps`, `hsum512_ps`. So S-2h matches by name. Two names are one family when
:func:`family_key` is equal — over `families.isa_tokens`, in this order: a trailing all-digit token is
dropped where the name has more than one token, every ISA token becomes `*`, a vector width `128`/`256`/
`512` inside a token becomes `#`, and a lane count written `x<N>` becomes `x#`. On the real target that
reaches **26 of 31** helpers in 11 families with **none ambiguous**, where E3's rule as worded
(`families.isa_families`, one ISA token differing) reaches 3 — which is why W is a rule of its own here
and :mod:`lattice.families`, a line-for-line port of the draw's scripts, is not touched. Two members of
one family in one other file are **ambiguous**: that file serves no shot and the request names both
(:func:`helper_siblings`).

S-2h is **byte-identical to S-2** for a cell and for the init — only the arm's name, and so the request id
and the seed, differ. That is why the registered comparison `S-2h − S-2` is read on the **helper** units
only, and why the same pair over the cells is a *noise* read: identical prompts under two seeds.

**Expected, from E1's own rows:** of Qwen's 18 C-2 greedy passes the answer sat nearest the *type*-axis
shot in 12, and at L1 the type neighbours are inside the held-out file, so S-2's ISA-only shots are
expected *below* E1's C-2. S-2o is the arm that asks whether the student's own passes can stand in for
those holes; it is **described and not registered** (E4-c), so the report shows it beside S-2 with what
it carried and the comparisons stay the two E4-f named.

**The parser is a step of its own, and it never sees a body** (§5.2, K-1: a parser into the task format,
not an author). :func:`parse` asks one greedy question per unit from `API.md`, the unit's name, kind and
signature, its grid position where it is a cell, and the **names** of the callees S-3 would list — no
skeleton, no shot, no gold, and its whole prompt carries no `{` of this module's writing. The answer is
one JSON object with `contract` and `edge_cases`; an answer that is not that is **kept raw** with
`parsed: false` and a stated reason, and is never repaired, guessed at or filled empty. The rows go to
`parser.jsonl`, which one run's arms all read, so S-5 is one set of fields and not one per sample.

**S-2o runs in waves, because its shots are the run's own output.** Each cell's **designated neighbour**
on an axis is the one E1's rule would pick *if it comes earlier in the units' order*, and otherwise that
axis has no own shot and the request says `later-in-order`. That rule is fixed before the run and breaks
E1's symmetric pairs — `float32 ↔ int8` on the type axis would otherwise make each unit its own
neighbour's neighbour. The shot is that neighbour's **S-2o greedy body, and only where it passed**;
otherwise `neighbour-failed`. **Gold is never a shot.** Wave(u) is 0 where u has no designated
neighbour and 1 + the largest of theirs otherwise, and :func:`run` answers wave by wave — wave *w*'s
requests are built from the rows already graded, appended, and answered by another `e1.run` call, which
sends only what has no row yet. Every other arm needs no wave and goes in the first call.

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
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, NamedTuple, Sequence

from . import e1, families, holes, prompts
from .cells import ISAS, NATIVE, Cell, Lattice
from .cells import build as build_lattice
from .facts import Facts
from .scan import Span

__all__ = [
    "AMBIGUOUS",
    "ANY_ISA",
    "API_DOC",
    "ARMS",
    "COMPARISONS",
    "FACTS_ARMS",
    "FAMILY_ARMS",
    "FIELD_ARMS",
    "FILE_LEVEL",
    "FINAL",
    "INSTRUCTION",
    "K",
    "KINDS",
    "LATER",
    "NEIGHBOUR_FAILED",
    "NO_FACTS",
    "NO_FIELDS",
    "NO_NEIGHBOUR",
    "NO_OWN",
    "NO_SHOTS",
    "NO_SIBLING",
    "OWN_ARMS",
    "OWN_AXES",
    "P12",
    "PARSER",
    "PARSER_INSTRUCTION",
    "PARSER_SYSTEM",
    "PARSE_MAX_TOKENS",
    "PARSE_STAGE",
    "RUNG",
    "SHOT_ARMS",
    "SYSTEM",
    "WIDTH",
    "Designated",
    "DuplicateDefinition",
    "NoFields",
    "Own",
    "Shot",
    "Sibling",
    "Unit",
    "context",
    "cycles",
    "designated",
    "family_key",
    "file_level",
    "fill_units",
    "helper_siblings",
    "meta",
    "messages",
    "other_natives",
    "own_shots",
    "parse",
    "parse_context",
    "parse_requests",
    "parse_turns",
    "parser_meta",
    "plan",
    "read_answer",
    "read_api",
    "read_fields",
    "reaching_cells",
    "requests_for",
    "run",
    "shots",
    "skeleton",
    "turns",
    "units",
    "waves",
]

#: The rung: the whole file is held out (E4-a). L3 — the whole directory — is a later run.
RUNG = "L1"

#: Every arm E4 has, in the order the report reads them: the escalation S-0 → S-2 → S-3 → S-5, with
#: **S-2h** next to S-2 (the arm it is read against) and the described arm S-2o beside them.
ARMS = ("S-0", "S-2", "S-2h", "S-2o", "S-3", "S-5")

#: The arms that carry the ledger's facts, the graph's shots, the student's own shots, and the parser's
#: fields. S-5 is S-3 and the fields, so it is a facts arm and a shot arm too.
FACTS_ARMS = ("S-3", "S-5")
SHOT_ARMS = ("S-2", "S-2h", "S-2o", "S-3", "S-5")
OWN_ARMS = ("S-2o",)
FIELD_ARMS = ("S-5",)

#: The arms whose shots a **helper** gets by rule W's name family rather than by the grid (D-11 a). Every
#: other kind of unit reads these arms as S-2 does, byte for byte.
FAMILY_ARMS = ("S-2h",)

#: The registered comparisons, each `(first, second, kind)` and read as `second − first`, paired by unit.
#: `kind` is `None` where every unit is read, and a member of :data:`KINDS` where the comparison is only
#: about that kind: E4-f's two are over every unit, and **D-11's `S-2h − S-2` is the helper units**, since
#: S-2h *is* S-2 for a cell and for the init. S-2o is in none of them: it is described, not registered.
COMPARISONS = (("S-0", "S-2", None), ("S-3", "S-5", None), ("S-2", "S-2h", "helper"))

#: The P12 record (ADR-082, and ADR-086's check): planner-defined units, one single-use agent each, every
#: window smaller than the file. E1 records `arm=model+prompt`; this is the other answer.
P12 = "decomposed"

#: E4-e's sampling: greedy plus ten draws (E3's revised floor), and no iterate rounds.
K = 10

#: What a unit can be. `cell` is a lattice cell, `init` the file's `init_distance_functions_<isa>`, and
#: `helper` everything else the file defines.
KINDS = ("cell", "helper", "init")

#: The run directory's three E4 files, beside E1's own.
FILE_LEVEL = "file_level.jsonl"
FINAL = "final"
PARSER = "parser.jsonl"

#: What the parse step's `calls.jsonl` rows are marked with. They are priced exactly as E1's are, so
#: `e1.spent` counts them; the mark is what lets a reader tell the parser's spend from the student's.
PARSE_STAGE = "parse"

#: What the parser may answer in. Two fields of prose is a short answer, and a limit this size is also a
#: statement: there is no room in it for a body, and the parser is not asked for one.
PARSE_MAX_TOKENS = 512

#: The target's own documentation, which is all the parser is shown of the project (§5.2, E4's card).
API_DOC = "API.md"

#: The two axes an own-pass shot may come from. The ISA axis is already S-2's, served from the files that
#: stay; these two are the holes at L1, which is what S-2o asks about.
OWN_AXES = ("type", "metric")

#: Why an axis carries no own shot. The first two are facts about the order fixed before the run, the
#: third about what the student did: each is recorded on the request rather than left as silence.
NO_NEIGHBOUR = "no-neighbour"
LATER = "later-in-order"
NEIGHBOUR_FAILED = "neighbour-failed"

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

#: Rule W's two wildcards: the one every ISA token collapses to, and the one a vector width or a lane
#: count collapses to. They are characters no C identifier holds, so a key cannot collide with a name.
ANY_ISA = "*"
WIDTH = "#"

#: Why one other native file serves a helper no name-family shot. The first is the pre-registration's own
#: wording, so a reader of a prompt meets the sentence D-11 wrote; the second is the case where the family
#: has **two** members there, which makes neither of them *the* sibling.
NO_SIBLING = "no name-family sibling"
AMBIGUOUS = "ambiguous"

#: What S-2h says about the files a helper's family reached nothing in: every one of them, with its reason,
#: because a shot missing and a shot never looked for read the same in silence.
FAMILY_NONE = "shots: none ({gaps})"
FAMILY_GAP = "no shot from {gaps}"

#: What S-3 says when it carries no facts. The ledger answers a cell's callees; a helper and the init are
#: not cells, and a cell the ledger named nothing for is a third case, said as such.
NO_FACTS = {
    "cell": "facts: none (the ledger named no callee)",
    "helper": "facts: none (helper)",
    "init": "facts: none (init)",
}

#: What S-2o says when an axis carries no own shot, and what it says for a unit that has no axis at all.
#: Silence on either would read as S-2.
NO_OWN = {
    "helper": "own shots: none (helper)",
    "init": "own shots: none (init)",
}
OWN_NOTE = "own shots: none on the {axis} axis ({reason})"

#: What S-5 says for a unit whose parse did not come back as the two fields. The reason is the parser
#: row's own, so a reader of the prompt meets the same sentence a reader of `parser.jsonl` does. The arm
#: is never filled empty and never filled from somewhere else.
NO_FIELDS = "no parser fields (the parse failed: {reason})"

_FILE_HEADING = "The file this function is in, its other definitions as prototypes:"
_SHOTS_HEADING = "The same function in the instruction sets that stay:"
#: S-2h's heading for a helper. It says the basis, because a name family is not the grid: these are not
#: "the same function", they are the functions rule W reads as one family, and the prompt says which.
_FAMILY_HEADING = (
    "Functions of the same name family in the instruction sets that stay "
    "(matched by name, not by the grid):"
)
_OWN_HEADING = "The same function on this file's other axes, as you wrote it and it passed:"
_CALLS_HEADING = "What this function calls, read from the project's graph and the compiler's own key:"
_FIELDS_HEADING = "What this function must do:"
_SIGNATURE_HEADING = "The function to write:"
_NO_SIGNATURE = "(no signature)"

#: The parser's one fixed system line and the instruction its turn ends on (§5.2, K-1). Both are fixed
#: text: the parser is one call per unit and every arm reads its answer, so a second wording would make
#: two units' fields incomparable. **Neither writes a `{`** — the JSON's shape is spelled out in words —
#: so the whole of what this module puts in a parse prompt can be held to carrying no brace at all, which
#: is the cheapest true statement of "the parser was shown no body".
PARSER_SYSTEM = (
    "You read a C library's documentation and one function's place in it, and you answer with JSON. "
    "You never write code."
)
PARSER_INSTRUCTION = (
    "Reply with one JSON object and nothing else. It has exactly two keys: \"contract\", a string of one "
    "or two sentences saying what this function must do, and \"edge_cases\", a list of strings, one short "
    "sentence each, naming the inputs that need care."
)

_API_HEADING = "The library's API documentation:"
_NO_API = f"the project has no {API_DOC} at its root, so none is shown"
_UNIT_HEADING = "The function to describe:"

#: An identifier token. The grain the call edges, the order and the reach are all read at.
_IDENT = re.compile(r"[A-Za-z_]\w*")


class NoFields(Exception):
    """S-5 was asked for without the parser's fields, or without the fields for that unit.

    Its own type (P10, ADR-036), and the same rule `prompts.NoLedger` keeps: an S-5 with no fields is
    S-3 wearing S-5's name, and a row recorded under the wrong arm is worse than a row missing. A unit
    whose parse *failed* is a different thing and is not this: it carries :data:`NO_FIELDS`, which says
    so in the prompt.
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


class Sibling(NamedTuple):
    """One other native file's answer for a helper's name family: a shot, or why there is none (D-11 a).

    `shot` and `reason` are exclusive — exactly one of them is set — and `candidates` names what was found
    in that file either way: the one member the shot came from, or the two or more that made it
    :data:`AMBIGUOUS`, or nothing at all beside :data:`NO_SIBLING`. The three are told apart on the request
    rather than left as one silence.
    """

    isa: str
    shot: Shot | None
    reason: str | None  # NO_SIBLING | AMBIGUOUS, or None where a shot was carried
    candidates: tuple[str, ...]


class Designated(NamedTuple):
    """S-2o's designated neighbour on one axis: which unit it is, or why there is none.

    `unit` is the neighbour E1's rule picked, and is named even where it is unusable — a `later-in-order`
    row says which unit came later — so the record shows the rule's answer and the order's answer apart.
    `reason` is `None` exactly when the neighbour may be asked for a shot.
    """

    axis: str  # one of OWN_AXES
    unit: str | None
    reason: str | None  # NO_NEIGHBOUR | LATER, or None


class Own(NamedTuple):
    """One axis of S-2o: the designated neighbour, its own passed body, or the reason there is neither."""

    axis: str
    unit: str | None
    text: str | None
    reason: str | None  # NO_NEIGHBOUR | LATER | NEIGHBOUR_FAILED, or None where a shot was carried


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
    found: list[Shot] = []
    for other in other_natives(lattice, isa):
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


def other_natives(lattice: Lattice, isa: str) -> list[str]:
    """The **files that stay** at L1, in `ISAS` order: every other native ISA the target has a file for.

    One list, read by every arm that serves a shot, so `cpu`, `neon` and `rvv` are excluded in one place
    and for the reasons :func:`shots` gives: `cpu` is G-diff's own reference, and the other two do not run
    on this box.
    """
    return [other for other in ISAS if other != isa and other in NATIVE and other in lattice.sources]


# MARK: - S-2h's name families (rule W) -

#: Rule W's step 3: a vector width inside a token, and **not** part of a longer digit run — so `hsum256`
#: is a width and the `16` of `bf16` and the `8` of `epi8` are not, which is the distinction that keeps an
#: element width from reading as a vector width (`epi8` and `epi16` are two families, not one).
_VECTOR_WIDTH = re.compile(r"(?<!\d)(128|256|512)(?!\d)")

#: Rule W's step 4: a lane count written `x<N>` — `bf16x8` against `bf16x16`.
_LANE_COUNT = re.compile(r"x\d+")


def family_key(name: str) -> tuple[str, ...]:
    """*name*'s **width family** key (rule W, D-11 a), as the pre-registration words it.

    Over `families.isa_tokens` — the draw's own tokeniser, `_` and camelCase only — in this order:

    1. a trailing all-digit token is dropped, where the name has more than one token
       (`dot_epu8_512` → `dot epu8`, `block_has_l2_inf_mismatch_8` → `block has l2 inf mismatch`);
    2. every token in `families.ISA` becomes :data:`ANY_ISA` (`popcount_avx2` → `popcount *`);
    3. a vector width `128`, `256` or `512` inside a token becomes :data:`WIDTH` (`hsum256` → `hsum#`);
    4. a lane count `x<N>` becomes `x#` (`bf16x8` → `bf16x#`).

    Two names are one family when their keys are equal. The order matters: step 1 removes the trailing
    `512` of `abs_diff_epu8_512` before step 3 could read it as a width, which is what makes that name and
    `abs_diff_epu8` one family. :mod:`lattice.families` is **not** changed by any of this — it is a port
    held against the draw's scripts, and its `isa_families` is a different rule with its own record.
    """
    tokens = list(families.isa_tokens(name))
    if len(tokens) > 1 and tokens[-1].isdigit():
        tokens.pop()
    key: list[str] = []
    for token in tokens:
        if token in families.ISA:
            key.append(ANY_ISA)
            continue
        key.append(_LANE_COUNT.sub(f"x{WIDTH}", _VECTOR_WIDTH.sub(WIDTH, token)))
    return tuple(key)


def helper_siblings(lattice: Lattice, isa: str, unit: Unit) -> list[Sibling]:
    """S-2h's shots for a **helper**: one row per file that stays, with a shot or the reason there is none.

    The candidates in each other file are that file's own **helper** units (:func:`units`, kind `helper`),
    matched by :func:`family_key`: a cell and the init have the grid's own crossing and are not a name
    family's business. One member is the shot — the whole definition, signature and body, as that file
    writes it. **Two members are ambiguous**: the file serves nothing and the request names both, because
    picking one of two by any other rule would be a rule that was not pre-registered.
    """
    key = family_key(unit.name)
    found: list[Sibling] = []
    for other in other_natives(lattice, isa):
        source = lattice.sources[other]
        members = [
            candidate
            for candidate in units(lattice, other)
            if candidate.kind == "helper" and family_key(candidate.name) == key
        ]
        names = tuple(candidate.name for candidate in members)
        if not members:
            found.append(Sibling(other, None, NO_SIBLING, ()))
        elif len(members) > 1:
            found.append(Sibling(other, None, AMBIGUOUS, names))
        else:
            member = members[0]
            text = source.text[member.signature_span.start : member.body_span.end]
            found.append(Sibling(other, Shot(other, member.name, text), None, names))
    return found


# MARK: - S-2o's own-pass shots -


def designated(lattice: Lattice, isa: str, unit: Unit, ordered: Sequence[Unit]) -> list[Designated]:
    """The designated neighbour on each of :data:`OWN_AXES` for *unit*, or why there is none (E4-c).

    The neighbour is the one **E1's own rule** would pick — `prompts.shots`, unchanged — kept only when
    it comes **earlier in the units' order**, since at L1 a later unit has not been written yet. That
    one condition breaks E1's symmetric pairs: `float32 ↔ int8` on the type axis would otherwise make
    each unit its own neighbour's neighbour, and no wave could ever be first. A helper and the init have
    no grid position and so no axis at all, which is an empty list here and :data:`NO_OWN` in the prompt.
    """
    if unit.kind != "cell":
        return []
    at = {other.name: index for index, other in enumerate(ordered)}
    cell = lattice.get(unit.cell)
    picked = {shot.axis: shot.cell for shot in prompts.shots(lattice, cell) if shot.axis in OWN_AXES}
    found: list[Designated] = []
    for axis in OWN_AXES:
        neighbour = picked.get(axis)
        if neighbour is None:
            found.append(Designated(axis, None, NO_NEIGHBOUR))
        elif at.get(neighbour.name, len(at)) >= at[unit.name]:
            found.append(Designated(axis, neighbour.name, LATER))
        else:
            found.append(Designated(axis, neighbour.name, None))
    return found


def own_shots(
    lattice: Lattice, isa: str, unit: Unit, ordered: Sequence[Unit], bodies: dict[str, str]
) -> list[Own]:
    """S-2o's shots for *unit*: each designated neighbour's own **passed** body, or the reason it has none.

    *bodies* is `{unit name: the body that unit's S-2o greedy sample wrote and the graders passed}` —
    :func:`_own_bodies` reads it off the run's rows. A neighbour that is not in it did not pass, and the
    axis carries `neighbour-failed` rather than a body nobody verified. **Gold is never here**: this
    function reads the run's own output and never the target's text, and the only thing it takes from the
    lattice is the neighbour's signature, which every prompt already carries as a prototype.
    """
    by_name = {other.name: other for other in ordered}
    found: list[Own] = []
    for row in designated(lattice, isa, unit, ordered):
        if row.reason is not None:
            found.append(Own(row.axis, row.unit, None, row.reason))
            continue
        body = bodies.get(row.unit)
        if not body:
            found.append(Own(row.axis, row.unit, None, NEIGHBOUR_FAILED))
            continue
        found.append(Own(row.axis, row.unit, f"{by_name[row.unit].signature}\n{body}", None))
    return found


def waves(lattice: Lattice, isa: str) -> dict[str, int]:
    """Each unit's S-2o wave: 0 with no designated neighbour, else 1 + the largest of theirs.

    Well founded because a designated neighbour is strictly earlier in the units' order, so the map can
    be read off in that order in one pass. Every other arm is wave 0: only S-2o waits on the run itself.
    """
    ordered = units(lattice, isa)
    found: dict[str, int] = {}
    for unit in ordered:
        names = [row.unit for row in designated(lattice, isa, unit, ordered) if row.reason is None]
        found[unit.name] = 1 + max(found[name] for name in names) if names else 0
    return found


# MARK: - an arm as data, and as messages -


def context(
    lattice: Lattice,
    isa: str,
    unit: Unit,
    arm: str,
    facts: Facts | None = None,
    fields: dict[str, dict] | None = None,
    bodies: dict[str, str] | None = None,
) -> dict:
    """One arm's context for one unit, as data: what it carries, and what it says it does not.

    A facts arm with no ledger is `prompts.NoLedger` and an S-5 with no parser row is :class:`NoFields`,
    and neither is ever filled empty: an empty S-3 is S-2 under another name, an empty S-5 is S-3 under
    another name, and a row recorded under the wrong arm is worse than a row missing.

    *bodies* is S-2o's own-pass bodies (:func:`own_shots`). `None` is the same as none written yet, which
    is what **wave 0** is: a wave-0 unit has no designated neighbour, so no axis of it can read
    `neighbour-failed` for want of a body. Every later wave is built by :func:`run`, which always passes
    the rows it has.
    """
    if arm not in ARMS:
        raise prompts.UnknownArm(f"{arm!r} is not one of {', '.join(ARMS)}")
    if arm in FACTS_ARMS and facts is None:
        raise prompts.NoLedger(f"{arm} is a facts arm and no ledger was given; it is never filled empty")
    if arm in FIELD_ARMS and fields is None:
        raise NoFields(f"{arm} carries the parser's fields and none were given; it is never filled empty")

    carried = shots(lattice, isa, unit) if arm in SHOT_ARMS else []
    family: list[Sibling] = []
    if arm in FAMILY_ARMS and unit.kind == "helper":
        # the one place S-2h is not S-2: a helper's shots come from rule W's name family, and every other
        # kind falls through to the grid's own crossing above, byte for byte
        family = helper_siblings(lattice, isa, unit)
        carried = [row.shot for row in family if row.shot is not None]
    own = own_shots(lattice, isa, unit, units(lattice, isa), bodies or {}) if arm in OWN_ARMS else []
    rows: list[dict] | None = None
    if arm in FACTS_ARMS:
        rows = list(facts.callees(lattice, lattice.get(unit.cell))) if unit.kind == "cell" else []

    parsed = None
    if arm in FIELD_ARMS:
        parsed = fields.get(unit.name)
        if parsed is None:
            raise NoFields(
                f"{arm} on {unit.name}: the parser's fields do not cover it; the arm is never filled empty"
            )
    return {
        "arm": arm,
        "rung": RUNG,
        "isa": isa,
        "unit": unit.name,
        "kind": unit.kind,
        "skeleton": skeleton(lattice, isa, unit),
        "shots": [{"isa": shot.isa, "from": shot.source, "text": shot.text} for shot in carried],
        "shots_note": _shots_note(unit, arm, carried, family),
        "own": [{"axis": row.axis, "unit": row.unit, "text": row.text} for row in own if row.text],
        "own_notes": _own_notes(unit, arm, own),
        "facts": rows,
        "facts_note": None if rows is None or rows else NO_FACTS[unit.kind],
        "fields": _fields_carried(parsed),
        "fields_note": _fields_note(parsed),
        "signature": unit.signature,
    }


def _shots_note(unit: Unit, arm: str, carried: Sequence[Shot], family: Sequence[Sibling]) -> str | None:
    """What a shot arm says about the shots it did not carry, and `None` where it carried them all.

    S-2h on a helper says it per file, with the reason — :data:`NO_SIBLING` or :data:`AMBIGUOUS` and the
    candidates — because "the family reached nothing there" and "the family reached two things there" are
    different facts and the second is the one a later rule would have to answer. Every other (arm, kind)
    keeps the note it had: one sentence naming which silence this is.
    """
    if arm not in SHOT_ARMS:
        return None
    if arm in FAMILY_ARMS and unit.kind == "helper":
        gaps = "; ".join(f"{row.isa} — {_gap(row)}" for row in family if row.shot is None)
        if not gaps:
            return None
        return (FAMILY_GAP if carried else FAMILY_NONE).format(gaps=gaps)
    return None if carried else NO_SHOTS[unit.kind]


def _gap(row: Sibling) -> str:
    """One file's reason, with the ambiguous family's members named: the prompt says what was found."""
    if row.reason == AMBIGUOUS:
        return f"{AMBIGUOUS}: {', '.join(row.candidates)}"
    return NO_SIBLING


def _own_notes(unit: Unit, arm: str, own: Sequence[Own]) -> list[dict]:
    """What S-2o says about the axes it carries nothing on. A unit with no axis at all says that instead."""
    if arm not in OWN_ARMS:
        return []
    if unit.kind != "cell":
        return [{"axis": None, "unit": None, "reason": unit.kind}]
    return [{"axis": row.axis, "unit": row.unit, "reason": row.reason} for row in own if row.reason]


def _fields_carried(parsed: dict | None) -> dict | None:
    """The parser's two fields, where its answer really was those two fields and nowhere else from."""
    if parsed is None or not parsed.get("parsed"):
        return None
    return {"contract": parsed["contract"], "edge_cases": list(parsed.get("edge_cases") or ())}


def _fields_note(parsed: dict | None) -> str | None:
    """What S-5 says for a unit the parser did not answer in its format: the parse's own reason."""
    if parsed is None or parsed.get("parsed"):
        return None
    return NO_FIELDS.format(reason=parsed.get("reason") or "no reason was recorded")


def messages(
    lattice: Lattice,
    isa: str,
    unit: Unit,
    arm: str,
    facts: Facts | None = None,
    fields: dict[str, dict] | None = None,
    bodies: dict[str, str] | None = None,
) -> list[dict]:
    """The chat turns for one (unit, arm): the fixed system line, and one user turn — E1's shape."""
    return turns(context(lattice, isa, unit, arm, facts, fields, bodies))


def turns(data: dict) -> list[dict]:
    """The same turns from a context already built, so a caller that wants both does not build it twice."""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": _user(data)}]


def _user(data: dict) -> str:
    """The user turn: the skeleton, the shots, the own shots, the facts, the fields, the hole.

    A section the arm does not carry takes its heading with it, and a section it carries *nothing* in
    leaves its note behind — an arm is a claim about what was given, and silence would read as S-0.
    """
    parts = [_section(_FILE_HEADING, _fenced(data["skeleton"]))]
    if data["shots"]:
        blocks = "\n\n".join(f"/* {row['isa']}: {row['from']} */\n{row['text']}" for row in data["shots"])
        parts.append(_section(_FAMILY_HEADING if _by_name(data) else _SHOTS_HEADING, _fenced(blocks)))
    # a note beside shots is S-2h's: a helper can carry one file's sibling and have the other say why it
    # carried none. Every other arm's note is `None` whenever it carried a shot, so this reads as it did
    if data["shots_note"]:
        parts.append(data["shots_note"])

    if data["own"]:
        blocks = "\n\n".join(
            f"/* {row['unit']}, the {row['axis']} axis: your own body, which passed */\n{row['text']}"
            for row in data["own"]
        )
        parts.append(_section(_OWN_HEADING, _fenced(blocks)))
    parts += [_own_line(note) for note in data["own_notes"]]

    if data["facts"]:
        parts.append(_section(_CALLS_HEADING, "\n".join(_callee_line(row) for row in data["facts"])))
    elif data["facts_note"]:
        parts.append(data["facts_note"])

    if data["fields"]:
        parts.append(_section(_FIELDS_HEADING, _fields_lines(data["fields"])))
    elif data["fields_note"]:
        parts.append(data["fields_note"])

    parts.append(_section(_SIGNATURE_HEADING, _fenced(data["signature"])))
    parts.append(INSTRUCTION)
    return "\n\n".join(parts)


def _by_name(data: dict) -> bool:
    """Whether these shots were matched by the name family (S-2h on a helper) or by the grid.

    Read off the arm and the kind the context already carries, so the heading is decided in one place and
    a request row carries no field whose only job is to name its own heading.
    """
    return data["arm"] in FAMILY_ARMS and data["kind"] == "helper"


def _own_line(note: dict) -> str:
    """One axis S-2o carried nothing on, or the one line a unit with no axis at all carries."""
    if note["axis"] is None:
        return NO_OWN[note["reason"]]
    return OWN_NOTE.format(axis=note["axis"], reason=note["reason"])


def _fields_lines(fields: dict) -> str:
    """The parser's words: the contract, then the edge cases as a list. Its own text, never edited."""
    lines = [fields["contract"]]
    lines += [f"- {case}" for case in fields["edge_cases"]]
    return "\n".join(lines)


def _callee_line(row: dict) -> str:
    """One callee, in E1's own line: the name, the signature the ledger holds, and where it came from."""
    return f"- {row['name']}: {row.get('signature') or _NO_SIGNATURE} [{row.get('provenance')}]"


def _section(heading: str, body: str) -> str:
    return f"{heading}\n\n{body}"


def _fenced(text: str) -> str:
    return f"```c\n{text.rstrip()}\n```"


# MARK: - the parser's fields (S-5) -


def read_api(target: Path | str) -> str | None:
    """The target's own `API.md`, or `None` where it has none — which the prompt then says (:data:`_NO_API`)."""
    path = Path(target) / API_DOC
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else None


def parse_context(
    lattice: Lattice, isa: str, unit: Unit, facts: Facts | None = None, api: str | None = None
) -> dict:
    """What the parser is shown for one unit, as data (§5.2, K-1). **No body of any kind is in it.**

    The documentation, the unit's name, kind and signature, its grid position where it is a cell, and the
    **names** of the callees S-3 would list — names only, because a signature is the ledger's answer to
    the student and the parser's job is the contract in words. No skeleton, no shot, no gold: the parser
    has never read this file's code, and a contract written from a body would be a description of the
    answer rather than of the task.
    """
    cell = lattice.get(unit.cell) if unit.cell else None
    rows = list(facts.callees(lattice, cell)) if facts is not None and cell is not None else []
    return {
        "unit": unit.name,
        "kind": unit.kind,
        "isa": isa,
        "cell": unit.cell,
        "type": None if cell is None else cell.type,
        "metric": None if cell is None else cell.metric,
        "signature": unit.signature,
        "callees": [row["name"] for row in rows],
        "callees_asked": facts is not None,
        "api": api,
    }


def parse_turns(data: dict) -> list[dict]:
    """The parser's chat turns: its one fixed system line, and one user turn ending on its instruction."""
    return [{"role": "system", "content": PARSER_SYSTEM}, {"role": "user", "content": _parser_user(data)}]


def _parser_user(data: dict) -> str:
    """The parse prompt. Everything this function writes is prose, a name or a signature — never a body."""
    parts = [_section(_API_HEADING, data["api"]) if data["api"] else _NO_API]
    lines = [
        f"- name: {data['unit']}",
        f"- kind: {data['kind']}",
        f"- instruction set: {data['isa']}",
    ]
    if data["cell"]:
        lines.append(f"- element type: {data['type']}")
        lines.append(f"- distance metric: {data['metric']}")
    lines.append(f"- signature: {data['signature']}")
    lines.append(f"- what it calls, by name: {_callee_names(data)}")
    parts.append(_section(_UNIT_HEADING, "\n".join(lines)))
    parts.append(PARSER_INSTRUCTION)
    return "\n\n".join(parts)


def _callee_names(data: dict) -> str:
    """The callees by name, or which silence this is — the three S-3 tells apart, told apart here too."""
    if data["callees"]:
        return ", ".join(data["callees"])
    if not data["callees_asked"]:
        return "none (no ledger was given, so none was asked for)"
    if data["cell"] is None:
        return f"none (the ledger answers a cell's callees; this unit's kind is {data['kind']})"
    return "none (the ledger named no callee)"


def parse_requests(
    lattice: Lattice, isa: str, model: str, facts: Facts | None = None, api: str | None = None
) -> list[dict]:
    """One greedy request per unit, in the units' own order: the parse is a step, not a sample (E4-e)."""
    made: list[dict] = []
    for unit in units(lattice, isa):
        data = parse_context(lattice, isa, unit, facts, api)
        made.append(
            {
                "id": e1.request_id(unit.name, PARSE_STAGE, 0, 0),
                "unit": unit.name,
                "kind": unit.kind,
                "stage": PARSE_STAGE,
                "mode": "chat",
                "messages": parse_turns(data),
                "params": {
                    "temperature": 0.0,
                    "top_p": 1.0,
                    "max_tokens": PARSE_MAX_TOKENS,
                    "seed": e1.seed(model, unit.name, PARSE_STAGE, 0, 0),
                },
            }
        )
    return made


def read_answer(text: str) -> tuple[dict | None, str | None]:
    """The parser's two fields from one completion, or `None` and the reason it was not those two fields.

    The answer is the whole text, or the contents of the **first** fenced block where the model fenced it
    — `extract`'s own rule, and for the same reason: "whichever part parses" quietly rewards a second
    attempt inside one completion. Nothing else is tried. A brace-scan that digs an object out of prose,
    or a missing `edge_cases` read as `[]`, is a **repair**, and a repaired answer is not the answer the
    parser gave; such a completion is kept raw instead, which is what `parsed: false` means.
    """
    block = _first_block(text)
    try:
        found = json.loads((block if block is not None else text).strip())
    except ValueError as broken:
        return None, f"the answer is not JSON ({broken})"
    if not isinstance(found, dict):
        return None, f"the answer is JSON but not an object (it is a {type(found).__name__})"
    contract = found.get("contract")
    cases = found.get("edge_cases")
    if not isinstance(contract, str) or not contract.strip():
        return None, "the answer carries no `contract` string"
    if not isinstance(cases, list) or not all(isinstance(case, str) for case in cases):
        return None, "the answer's `edge_cases` is not a list of strings"
    return {"contract": contract.strip(), "edge_cases": [case.strip() for case in cases]}, None


#: One fenced block, whatever its tag, run to the end of the text where its closing fence never came —
#: a completion cut off at `max_tokens`, which `extract` reads the same way.
_FENCE = re.compile(r"```[A-Za-z0-9_+-]*\n(.*?)(?:```|\Z)", re.DOTALL)


def _first_block(text: str) -> str | None:
    found = _FENCE.search(text)
    return None if found is None else found.group(1)


def parse(
    run_dir: Path | str,
    lattice: Lattice,
    isa: str,
    generate: Callable[[list[dict]], object],
    model: str,
    *,
    ceiling_usd: float,
    facts: Facts | None = None,
    api: str | None = None,
) -> list[dict]:
    """Fill `parser.jsonl`: one greedy answer per unit, priced and capped exactly as an E1 call is.

    **Resume is `parser.jsonl`**, as E1's is `rows.jsonl`: a unit already in it is neither asked again nor
    paid for again, and a call that came back short leaves the units it *did* answer on disk before the
    :class:`~lattice.e1.MissingCompletion` goes up. The call's cost goes to the run's own `calls.jsonl`
    with `stage: "parse"` on it, so `e1.spent` counts the parser's spend against the same ceiling the
    student's is counted against — one run, one budget.

    *generate* is E1's protocol unchanged, so `replay_generator` drives this in the tests and nothing is
    spent. No model appears here either.
    """
    run_dir = Path(run_dir)
    made = parse_requests(lattice, isa, model, facts, api)
    held = {row["unit"] for row in _read(run_dir / PARSER)}
    pending = [request for request in made if request["unit"] not in held]
    if not pending:
        return _read(run_dir / PARSER)

    guess = e1.estimate(model, pending)
    already = e1.spent(run_dir)
    if already + guess["usd"] > ceiling_usd:
        raise e1.CeilingReached(
            f"the parse: ${already:.4f} already spent plus an estimated ${guess['usd']:.4f} for "
            f"{len(pending)} request(s) passes the ${ceiling_usd:.4f} ceiling; nothing was sent"
        )

    started = time.time()
    try:
        answer = generate(pending)
    except e1.GenerateFailed as failure:
        # the same rule E1 keeps: a call that failed still ran, so its row goes down before the refusal
        # goes up. The price rule is E1's own, called rather than copied — one place decides what a call
        # cost, and a second copy of it is how two numbers for one run come about
        _append(run_dir / e1.CALLS, [_staged(e1._failed_call_row(0, pending, guess, failure))])
        raise
    wall = round(time.time() - started, 3)
    answered = e1._completions(answer)
    reported = answer if isinstance(answer, dict) else {}
    _append(run_dir / e1.CALLS, [_staged(e1._call_row(0, pending, answered, reported, guess, wall))])

    rows = [
        _parser_row(request, model, answered[request["id"]])
        for request in pending
        if request["id"] in answered
    ]
    if rows:
        _append(run_dir / PARSER, rows)
    lost = [request["unit"] for request in pending if request["id"] not in answered]
    if lost:
        raise e1.MissingCompletion(f"the parser returned no completion for {', '.join(lost)}")
    return _read(run_dir / PARSER)


def _staged(row: dict) -> dict:
    """One `calls.jsonl` row, marked as the parse step's."""
    return {**row, "stage": PARSE_STAGE}


def _parser_row(request: dict, model: str, got: dict) -> dict:
    """One unit's parser row: the two fields where they came back, and the whole text either way."""
    text = got.get("text") or ""
    fields, reason = read_answer(text)
    return {
        "unit": request["unit"],
        "model": model,
        "contract": None if fields is None else fields["contract"],
        "edge_cases": None if fields is None else fields["edge_cases"],
        "raw": text,
        "parsed": fields is not None,
        "reason": reason,
    }


def read_fields(run_dir: Path | str) -> dict[str, dict]:
    """`parser.jsonl` as `{unit name: row}` — what S-5 is built from, and `{}` where there is no parse."""
    return {row["unit"]: row for row in _read(Path(run_dir) / PARSER)}


def parser_meta(run_dir: Path | str) -> dict | None:
    """The `parser` block of a plan's `meta.json`: which model filled the fields, and over which bytes.

    `sha256` is `parser.jsonl`'s own bytes, so a plan names the exact fields it was built from. A file
    holding more than one model's rows names them all and leaves `model` `None` rather than picking one:
    two parsers' fields under one arm is a fact a reader has to meet.
    """
    rows = _read(Path(run_dir) / PARSER)
    if not rows:
        return None
    models = sorted({row.get("model") for row in rows if row.get("model")})
    return {
        "model": models[0] if len(models) == 1 else None,
        "models": models,
        "sha256": hashlib.sha256((Path(run_dir) / PARSER).read_bytes()).hexdigest(),
        "units": len(rows),
        "parsed": sum(1 for row in rows if row.get("parsed")),
    }


# MARK: - the plan -


def plan(
    lattice: Lattice,
    isa: str,
    arms: Sequence[str],
    model: str,
    facts: Facts | None = None,
    k: int = K,
    fields: dict[str, dict] | None = None,
) -> list[dict]:
    """Round 0's requests: one chat request per (unit, arm, sample), in the units' own order.

    Sample 0 is greedy and samples 1 to *k* are drawn at E1's parameters. The seeds are `e1.seed` with
    the **unit's name** where a cell id would stand, so a run planned twice asks for the same samples.
    No G-mem probe: E4 reads one file, and its cells' probes are E1's own rows.

    **S-2o is planned as far as wave 0 and no further.** A later wave's shots are bodies nobody has
    written yet, so :func:`run` builds those requests when the rows they rest on exist. Every other arm
    is planned whole.
    """
    ordered = units(lattice, isa)
    waved = waves(lattice, isa)
    made: list[dict] = []
    for unit in ordered:
        for arm in arms:
            if arm in OWN_ARMS and waved[unit.name] > 0:
                continue
            made += requests_for(
                lattice, isa, unit, arm, model, k, facts=facts, fields=fields, wave=0
            )
    return made


def requests_for(
    lattice: Lattice,
    isa: str,
    unit: Unit,
    arm: str,
    model: str,
    k: int,
    *,
    facts: Facts | None = None,
    fields: dict[str, dict] | None = None,
    bodies: dict[str, str] | None = None,
    wave: int = 0,
) -> list[dict]:
    """One unit's requests on one arm: the greedy sample and *k* drawn ones, over one built context."""
    data = context(lattice, isa, unit, arm, facts, fields, bodies)
    built = turns(data)
    cell = lattice.get(unit.cell) if unit.cell else None
    made: list[dict] = []
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
                "wave": wave,
                "mode": "chat",
                "messages": built,
                "shots": [{"isa": row["isa"], "from": row["from"]} for row in data["shots"]],
                "shots_note": data["shots_note"],
                # what S-2o carried and what it did not, on the request itself: the report reads the
                # arm's own-shot counts off these rather than re-deriving a rule the run already applied
                "own": [{"axis": row["axis"], "unit": row["unit"]} for row in data["own"]],
                "own_notes": data["own_notes"],
                "facts_note": data["facts_note"],
                "fields_note": data["fields_note"],
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
    parser: dict | None = None,
) -> dict:
    """The run's `meta.json`: E1's record, plus the rung, the units' order and the P12 decomposition.

    `cells` holds the unit names — a unit stands where a cell does in E1's schema — and `units` holds the
    order with each unit's kind. **`p12` is `decomposed`** (:data:`P12`), and `decomposition` carries the
    unit count, the largest prompt and the held-out file's own length, so ADR-086's check can read off
    the record that every implementer's window was smaller than the task.

    `waves` is S-2o's order as names, one list per wave, and `parser` is :func:`parser_meta`'s block —
    which model filled S-5's fields and the digest of the file they were read from, so the arm names its
    own input. `decomposition` is restated by :func:`run` as a wave adds requests the plan could not hold.
    """
    ordered, cycled = _read_units(lattice, isa)
    file_chars = len(lattice.sources[isa].text)
    largest = max((e1.prompt_chars(request) for request in requests), default=0)
    waved = waves(lattice, isa)
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
            "waves": [
                [unit.name for unit in ordered if waved[unit.name] == wave]
                for wave in range(0, max(waved.values(), default=0) + 1)
            ],
            "parser": parser,
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

    **S-2o then runs wave by wave** (:func:`_own_waves`), because its shots are this run's own graded
    output. Every other arm is answered in the first call; a run without S-2o among its arms makes exactly
    the one call it made before.
    """
    run_dir = Path(run_dir)
    record = json.loads((run_dir / e1.META).read_text(encoding="utf-8"))
    isa = record["isa"]
    graded = _unit_grade(grade, isa)
    summary = e1.run(run_dir, target, generate, graded, ceiling_usd=ceiling_usd, rounds=0, iterate=())
    if any(arm in OWN_ARMS for arm in record.get("arms") or ()):
        summary = _own_waves(run_dir, target, record, generate, graded, ceiling_usd, summary)
    summary["file_level"] = file_level(run_dir, target, grade)
    return summary


def _own_waves(
    run_dir: Path,
    target: Path | str,
    record: dict,
    generate: Callable[[list[dict]], object],
    graded: Callable[[list[dict]], list[dict]],
    ceiling_usd: float,
    summary: dict,
) -> dict:
    """S-2o's waves 1 upward: build each from the rows already graded, append them, answer them.

    `e1.run` answers whatever `requests.jsonl` holds no row for, so appending a wave and calling it again
    sends only that wave. **A resume rebuilds nothing already answered**: a request whose id is already in
    the file is not written twice, and one already in `rows.jsonl` is not sent again — which is also why a
    wave's shots cannot change under it, since the rows they are read from are the rows of earlier waves.
    """
    lattice = build_lattice(target)
    isa = record["isa"]
    ordered = units(lattice, isa)
    waved = waves(lattice, isa)
    model, k = record["model"], int(record.get("k") or 0)
    known = {request["id"] for request in _read(run_dir / e1.REQUESTS)}
    for wave in range(1, max(waved.values(), default=0) + 1):
        bodies = _own_bodies(run_dir)
        fresh = [
            request
            for unit in ordered
            if waved[unit.name] == wave
            for request in requests_for(
                lattice, isa, unit, OWN_ARMS[0], model, k, bodies=bodies, wave=wave
            )
            if request["id"] not in known
        ]
        if fresh:
            _append(run_dir / e1.REQUESTS, fresh)
            known |= {request["id"] for request in fresh}
            _restate_window(run_dir, record)
        summary = e1.run(run_dir, target, generate, graded, ceiling_usd=ceiling_usd, rounds=0, iterate=())
    summary["waves"] = len(record.get("waves") or ())
    return summary


def _own_bodies(run_dir: Path) -> dict[str, str]:
    """Each unit's **own** S-2o greedy body, and only where the graders passed it (E4-c).

    Greedy, because one unit serves one shot and a drawn sample is not the unit's answer; passed, because
    an unverified body is not a pattern; and read from `rows.jsonl`, so **gold cannot get in** — the only
    text here is what the student wrote.
    """
    found: dict[str, str] = {}
    for row in _read(run_dir / e1.ROWS):
        if row.get("arm") not in OWN_ARMS or row.get("sample") != 0 or row.get("round") != 0:
            continue
        if row.get("class") != "pass":
            continue
        body = (row.get("extract") or {}).get("body")
        if body:
            found[row["cell"]] = body
    return found


def _restate_window(run_dir: Path, record: dict) -> None:
    """Put `meta.json`'s P12 window record back in step with the requests a wave has added.

    `plan` cannot hold S-2o's later waves, so the largest prompt it recorded is not the largest the run
    sent. ADR-086's check reads the claim that every implementer's window was smaller than the task off
    this record, and a record that quietly stops being true is worse than one that was never written.
    """
    window = dict(record.get("decomposition") or {})
    largest = max((e1.prompt_chars(request) for request in _read(run_dir / e1.REQUESTS)), default=0)
    window["largest_prompt_chars"] = largest
    window["every_window_smaller"] = largest < window.get("file_chars", 0)
    record["decomposition"] = window
    (run_dir / e1.META).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")


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
