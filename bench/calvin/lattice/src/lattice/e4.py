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
| **S-3h** | S-2h plus **what this file can use** of what those shots use: the intrinsics by availability, and the other file's own names | the ISA's own facts |
| **S-3hd** | S-3h's round 0, copied, and **one retry round**: E1's own feedback | the retry |
| **S-3hf** | S-3hd's retry plus **one fact line per name the answer named** | the facts in the loop |

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

**S-3h serves the ISA's own facts beside the pattern** (D-12 a, pre-registered before this build). D-11's
reading was that a name-family shot carries the pattern and **not what the target ISA has**: on sse2 the
dominant class is `invented`, because the student copies a wider sibling's `_mm_shuffle_epi8` into a file
that includes only `<emmintrin.h>`, and copies that file's own helper names with it. So S-3h is S-2h plus
one block, headed *"What this file can use, of what the examples above use…"*, built from the unit's shot
texts and nothing else:

- **the intrinsics** the shots write, the available ones on one line and each unavailable one on a line of
  its own — with **its form here** where rule R (:func:`lattice.available.rename`) has one, and the
  statement that there is none where it has not;
- **the other file's own names** a shot writes — a function, a `#define` or a file-scope `static` object of
  the *shot's* file that the held-out file does not define — each answered by **rule W's** family among this
  file's units: the one member, the two that make it ambiguous, or no such definition.

Availability is read the way the **grader** meets it, from the file's own includes preprocessed under the
build flags (:mod:`lattice.available`), never from the intrinsic index, which reads both arms of every
`#if` and would call `_mm_shuffle_epi8` real on sse2. The arm is stated for **every** unit whose S-2h
context carries shots; a unit with no shots carries :data:`NO_EXAMPLES` and nothing else, since a block
about examples nobody was shown would be a claim about a prompt that does not exist. Everything else in
S-3h — the shots included — is S-2h's byte for byte, which is why the registered comparison `S-3h − S-2h`
is over **every** unit. Without a record it is :class:`NoAvailability` and is **never filled empty**, for
the reason `prompts.NoLedger` and :class:`NoFields` are: an empty S-3h is S-2h under another name.

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

**S-3hd and S-3hf put the facts in the loop** (D-13 a, pre-registered before this build). D-12's reading
was that the block is *read and not acted on*: on sse2, 132 of S-3h's 194 invented intrinsics are exactly
the same-width rename the block had said has no form here. So D-13 asks the same fact again where the
compiler has just disagreed with the student — in a **retry** — and asks it two ways, one variable apart:

- **round 0 is D-12's own S-3h, copied and not asked** (:func:`loop`). One file's S-3h requests and graded
  rows are copied twice, as S-3hd and S-3hf, with only `arm` and `id` changed: `messages`, `params`,
  `grade`, `text` and `class` are the source run's, so the two arms start from one answer and round 0 costs
  nothing. The run records the source's directory and the digests of its three files, and it **refuses**
  (:class:`LoopSource`) a source with no S-3h, an S-3h request with no graded row, or one missing any of
  the four fields it would carry over (`target_sha`, `model`, `k`, `params`).
- **a chain is retried at round 1 when its round-0 class is `invented` or `compile`** (:data:`RETRY_CLASSES`),
  in both arms; every other class keeps its round-0 row as its final row.
- **S-3hd's retry is E1's own**, byte for byte what `e1._retry` sends. **S-3hf's is that text plus one
  section** of fact lines for the names the round-0 answer named (:func:`loop_facts`): every invented name
  that is not a renamed parameter, and every name clang's feature diagnostics quoted. A name available
  here, a type, a local — anything the rule has nothing to say about — gets **no line** and is counted
  `unlined`, and where no name has a line **S-3hf's retry is S-3hd's byte for byte**.
- **the two arms share round 1's seed** (`seed(model, cell, "S-3h", sample, 1)`), so a chain with no fact
  line is *one* request: `e1._call` sends one question once and writes both rows from the one answer. That
  is what makes the pair an exact tie where the facts have nothing to add, and it is why the difference
  between the arms is the lines and not the draw.

Registered: **S-3hf − S-3hd through round 1**, paired by unit, and **S-3hf's round 0 against its final rows
through round 1** — which cannot be negative by construction, and says so wherever it is printed.

**What this module does not hold.** No model appears in it: the generator and the grader are injected
callables, exactly as in :mod:`lattice.e1`, whose loop, ceiling, resume and pricing this module reuses
whole — at `rounds=0` for every arm but D-13's, which runs E1's own iterate loop at `rounds=1` through the
hooks `e1.run` lends out.
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

from . import available as available_of
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
    "AVAILABLE_HERE",
    "COMPARISONS",
    "DECLARED_NOWHERE",
    "DECLARED_NOWHERE_FORM",
    "FACTS_ARMS",
    "FACTS_ISA_ARMS",
    "FAMILY_ARMS",
    "FIELD_ARMS",
    "FILE_LEVEL",
    "FINAL",
    "INSTRUCTION",
    "K",
    "KINDS",
    "LATER",
    "LOOP_ARMS",
    "LOOP_CARRIED",
    "LOOP_MAX_LINES",
    "LOOP_MORE",
    "LOOP_PAIR",
    "LOOP_ROUNDS",
    "LOOP_SOURCE_ARM",
    "LOOP_SOURCE_FILES",
    "NEIGHBOUR_FAILED",
    "NOT_HERE",
    "NOWHERE",
    "OTHER_FILE",
    "RETRY_CLASSES",
    "UNLINED",
    "NOT_AVAILABLE",
    "NOT_AVAILABLE_FORM",
    "NOTHING_IN_SHOTS",
    "NO_EXAMPLES",
    "NO_FACTS",
    "NO_FIELDS",
    "NO_NEIGHBOUR",
    "NO_OWN",
    "NO_SHOTS",
    "NO_SIBLING",
    "OTHERS_AMBIGUOUS",
    "OTHERS_NONE",
    "OTHERS_ONE",
    "OWN_ARMS",
    "OWN_AXES",
    "P12",
    "PARSER",
    "PARSER_INSTRUCTION",
    "PARSER_SYSTEM",
    "PARSE_MAX_TOKENS",
    "PARSE_STAGE",
    "POOL_ARMS",
    "RUNG",
    "SHOT_ARMS",
    "SYSTEM",
    "WIDTH",
    "Designated",
    "DuplicateDefinition",
    "LoopMoved",
    "LoopSource",
    "NoAvailability",
    "NoFields",
    "Own",
    "Shot",
    "Sibling",
    "Unit",
    "availability",
    "context",
    "cycles",
    "designated",
    "family_key",
    "file_scope",
    "file_level",
    "fill_units",
    "helper_siblings",
    "loop",
    "loop_facts",
    "loop_names",
    "loop_retry",
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
    "registered_pair",
    "registered_rounds",
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
#: **S-2h** next to S-2 (the arm it is read against), **S-3h** next to S-2h (likewise), and the described
#: arm S-2o beside them.
ARMS = ("S-0", "S-2", "S-2h", "S-3h", "S-2o", "S-3", "S-5")

#: The arms that carry the ledger's facts, the graph's shots, the student's own shots, and the parser's
#: fields. S-5 is S-3 and the fields, so it is a facts arm and a shot arm too.
FACTS_ARMS = ("S-3", "S-5")
SHOT_ARMS = ("S-2", "S-2h", "S-3h", "S-2o", "S-3", "S-5")
OWN_ARMS = ("S-2o",)
FIELD_ARMS = ("S-5",)

#: The arms that carry the **held-out file's own availability** — which of the shots' intrinsics this file
#: can use, and which of their names are the other file's (D-12 a). One arm, and it is S-2h plus the block.
FACTS_ISA_ARMS = ("S-3h",)

#: **D-13's two arms** (D-13 a): one round-1 retry each, from one copied S-3h round 0. `S-3hd` is E1's own
#: retry and `S-3hf` is that text plus the fact lines, which is the one variable between them.
LOOP_ARMS = ("S-3hd", "S-3hf")

#: The arm a D-13 run's round 0 is copied from, and — because both arms share it — the arm round 1's seed
#: is made from. Two byte-identical retries are then one request and one answer (`e1._distinct`).
LOOP_SOURCE_ARM = "S-3h"

#: The round-0 classes a chain is retried from (D-13 a). `invented` and `compile` are the two the block is
#: aimed at: a name that resolves nowhere, and a body the compiler refused. Every other class — `wrong`,
#: `edge`, `no-body`, `not-installed`, `pass` — keeps its round-0 row as its chain's final row.
RETRY_CLASSES = ("invented", "compile")

#: One retry round, and one only (D-13 a): K-3's lightest form.
LOOP_ROUNDS = 1

#: The registered pair, read `second − first` through round :data:`LOOP_ROUNDS`, over every unit.
LOOP_PAIR = LOOP_ARMS

#: How many fact lines one retry carries before it says how many it left out. S-3hd's own text is never
#: cut to make room for them: the variable between the arms is what the lines add, not what they displace.
LOOP_MAX_LINES = 10

#: The arms every reader will take as an arm name, D-13's included. :data:`ARMS` stays the arms a **plan**
#: may ask for — a loop arm's round 0 is copied and never built, so `e4 plan --arms S-3hd` would be a
#: request for a prompt this module does not write.
POOL_ARMS = (*ARMS, *LOOP_ARMS)

#: The arms whose shots a **helper** gets by rule W's name family rather than by the grid (D-11 a). Every
#: other kind of unit reads these arms as S-2 does, byte for byte. S-3h is one of them because its shots
#: **are** S-2h's: the block it adds is the one thing between the two arms.
FAMILY_ARMS = ("S-2h", "S-3h")

#: The registered comparisons, each `(first, second, kind)` and read as `second − first`, paired by unit.
#: `kind` is `None` where every unit is read, and a member of :data:`KINDS` where the comparison is only
#: about that kind: E4-f's two are over every unit, and **D-11's `S-2h − S-2` is the helper units**, since
#: S-2h *is* S-2 for a cell and for the init. S-2o is in none of them: it is described, not registered.
#: **D-12's `S-3h − S-2h` is every unit**, because the block is stated for every unit that carries a shot —
#: a cell's and the init's shots are the grid's and a helper's are rule W's, and all three get the block.
COMPARISONS = (
    ("S-0", "S-2", None),
    ("S-3", "S-5", None),
    ("S-2", "S-2h", "helper"),
    ("S-2h", "S-3h", None),
)

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

#: S-3h's lines, the pre-registration's own wording (D-12 a). :data:`NO_EXAMPLES` is the whole of the arm
#: for a unit with no shots: there is no block, because there is nothing the block would be about.
#: :data:`NOTHING_IN_SHOTS` is the block's body where the shots exist and name neither an intrinsic nor a
#: definition of their own — a heading with no lines under it would read as a section that went missing.
NO_EXAMPLES = "nothing to check: no examples above"
NOTHING_IN_SHOTS = "nothing to check: the examples above name no intrinsic and no definition of their own"
AVAILABLE_HERE = "available here: {names}"
NOT_AVAILABLE_FORM = "`{name}` is not available in this file; its form here: `{form}`"
NOT_AVAILABLE = "`{name}` is not available in this file, and no same-named form is"
OTHERS_ONE = "`{name}` is the other file's own; this file's: `{mine}`"
OTHERS_AMBIGUOUS = "`{name}` is the other file's own; this file's candidates: {mine} (ambiguous)"
OTHERS_NONE = "`{name}` is the other file's own; this file has no such definition"

#: D-13's two further lines, for a name **no header of this compiler declares** — the 34% class of D-12's
#: step 0, which no fact about the shots can reach and which the availability record cannot answer either:
#: it only holds what this file's own includes declare. The intrinsic index is what says "nowhere".
DECLARED_NOWHERE_FORM = "`{name}` is declared by no header of this compiler; its form here: `{form}`"
DECLARED_NOWHERE = "`{name}` is declared by no header of this compiler, and no same-named form is"

#: What a retry says of the lines past :data:`LOOP_MAX_LINES`. A count, not a silent cut.
LOOP_MORE = "({count} more names.)"

#: A fact line's status, on the request's record. :data:`NOT_HERE` is declared somewhere and not available
#: here, :data:`NOWHERE` is declared by no header at all, :data:`OTHER_FILE` is another kernel file's own
#: definition, and :data:`UNLINED` is not a status but the count of names the rule had nothing to say about.
NOT_HERE = "not-here"
NOWHERE = "nowhere"
OTHER_FILE = "other-file"
UNLINED = "unlined"

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
#: S-3h's heading, the pre-registration's own sentence. It names both instruments the block was read with —
#: this file's includes under its build flags, and this file's own definitions — because a student told
#: "not available" without being told who said so has been handed an assertion and not a fact.
_AVAILABLE_HEADING = (
    "What this file can use, of what the examples above use (read from this file's own includes under its "
    "build flags, and from its own definitions):"
)
#: S-3hf's heading (D-13 a, as worded). It is S-3h's sentence with "of what the examples above use" replaced
#: by "of the names above": the names are the model's own answer's this time, not the shots'.
_LOOP_HEADING = (
    "What this file can use, of the names above (read from this file's own includes under its build "
    "flags, and from its own definitions):"
)
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

#: An intrinsic **call** in a shot, as D-12's pre-registration words it. Over the shot's text as written,
#: not its masked text: that is the rule that was registered, and it means a name in a comment is read as
#: used. It cannot make an unavailable name read as available — only add a line about one nobody calls.
_INTRINSIC = re.compile(r"\b(_mm\w*|_cvt\w*)\s*\(")

#: An intrinsic-**shaped** name, for D-13's lines: the whole token, not a call site. A retry's names come
#: off the graded row's `invented` list and the compiler's diagnostics, where there is no `(` to key on.
_INTRINSIC_SHAPED = re.compile(r"\A(?:_mm|_cvt)\w*\Z")

#: clang's two feature refusals, the forms D-13's step 0 read on D-12's rows:
#: `always_inline function '_mm256_add_ps' requires target feature 'avx2', but would be inlined into …`
#: and `'_mm512_abs_epi32' needs target feature avx512vl`. The name they quote is a name the body wrote and
#: this file cannot use, which is the same fact a line carries and is not in `invented` (it compiled far
#: enough to be *declared*), so the two sources are read together and deduplicated.
_FEATURE_DIAGNOSTICS = (
    re.compile(r"always_inline function '(\w+)' requires target feature"),
    re.compile(r"'(\w+)' needs target feature"),
)

#: A file-scope `static` object: `static const char popcount_lut_bytes[32] = {…}`. The name is the one a
#: `[` or an `=` follows, and the line is one **outside every definition** — a parameter written `int a[]`
#: would otherwise read as an object of the file.
_STATIC_OBJECT = re.compile(r"\bstatic\b.*?\b([A-Za-z_]\w*)\s*(?:\[|=)")


class NoFields(Exception):
    """S-5 was asked for without the parser's fields, or without the fields for that unit.

    Its own type (P10, ADR-036), and the same rule `prompts.NoLedger` keeps: an S-5 with no fields is
    S-3 wearing S-5's name, and a row recorded under the wrong arm is worse than a row missing. A unit
    whose parse *failed* is a different thing and is not this: it carries :data:`NO_FIELDS`, which says
    so in the prompt.
    """


class NoAvailability(Exception):
    """S-3h was asked for without a record of what the held-out file can use, or without that file's ISA.

    Its own type (P10, ADR-036), and the rule `prompts.NoLedger` and :class:`NoFields` keep: an S-3h whose
    block says nothing is S-2h under another name, and a row recorded under the wrong arm is worse than a
    row missing. Worse here than elsewhere — an empty availability table marks **every** intrinsic
    unavailable, so the arm would not be merely silent but actively wrong, and the run would read as a
    finding about the block rather than about the missing record.
    """


class LoopSource(Exception):
    """A D-13 run's round 0 cannot be copied from that source run, so nothing was written.

    Its own type (P10, ADR-036), and a refusal rather than a smaller run. D-13's whole design is that round
    1 is asked from **D-12's own round 0**: a source with no S-3h, an S-3h request the source never graded
    (an unfinished run), or one whose model, `k`, `params` or `target_sha` this plan cannot carry over is
    not that round 0, and a run built from it would report a comparison against something else.
    """


class LoopMoved(Exception):
    """The availability record or the intrinsic index is not the bytes the loop's plan was written from.

    Its own type, and the same refusal :class:`~lattice.e1.TargetMoved` is: the fact lines a retry carries
    are one compiler's answer at one moment, and a run that read half its lines from one record and half
    from another would put two instruments under one reading without either of them saying so.
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


# MARK: - S-3h's availability block -


def file_scope(lattice: Lattice, isa: str) -> dict[str, str]:
    """Every name one file defines at file scope, by what it is: `function`, `define` or `object`.

    The three the pre-registration names. Functions and `#define`s come from `scan`, this package's own
    scanner, and an **object** is a file-scope `static` — a line outside every definition where a `[` or an
    `=` follows the name (:data:`_STATIC_OBJECT`). `popcount_lut_bytes` is the case that matters: avx2's
    `popcount_avx2` reads it, and a student writing sse2's or avx512's has no such array.

    Not `extern`, which is a declaration of something another file owns (`dispatch_distance_table`), and not
    a local: the definitions' spans are blanked before the scan, so nothing inside a body is read. A name a
    file defines twice is named once, the first kind wins, and `scan`'s own limits are inherited whole.
    """
    source = lattice.sources[isa]
    found = {fn.name: "function" for fn in source.scanned.functions}
    for name in source.scanned.defines:
        found.setdefault(name, "define")
    for name in _static_objects(lattice, isa):
        found.setdefault(name, "object")
    return found


def _static_objects(lattice: Lattice, isa: str) -> list[str]:
    """The file-scope `static` objects, in the file's order, read outside every definition."""
    source = lattice.sources[isa]
    text = list(source.scanned.masked)
    for fn in source.scanned.functions:
        for at in range(fn.signature_span.start, min(fn.body_span.end, len(text))):
            if text[at] != "\n":
                text[at] = " "
    names: list[str] = []
    for line in "".join(text).splitlines():
        found = _STATIC_OBJECT.search(line)
        if found is not None and found.group(1) not in names:
            names.append(found.group(1))
    return names


def availability(
    lattice: Lattice, isa: str, unit: Unit, carried: Sequence[Shot], record: dict
) -> dict:
    """S-3h's block for one unit, as data: the shots' intrinsics by availability, and their file's own names.

    *carried* is the unit's S-2h shots and *record* is :func:`lattice.available.load`'s, from which only the
    **held-out** ISA's names are read — the question is what *this* file can use. A unit with no shots gets
    :data:`NO_EXAMPLES` and no lists: the block is about the examples above it, and there are none.
    """
    if not carried:
        return {"shots": 0, "intrinsics": [], "names": [], "note": NO_EXAMPLES}
    table = available_of.names_for(record, isa)
    intrinsics = _intrinsic_rows(carried, isa, table)
    names = _other_rows(lattice, isa, carried)
    return {
        "shots": len(carried),
        "intrinsics": intrinsics,
        "names": names,
        "note": None if (intrinsics or names) else NOTHING_IN_SHOTS,
    }


def _intrinsic_rows(carried: Sequence[Shot], isa: str, table: dict[str, dict]) -> list[dict]:
    """Each intrinsic the shots call, deduplicated in first-appearance order, with its status and its form.

    `form` is rule R's answer and is `None` both where the rule found nothing and where the name is
    available anyway — the two are told apart by `available`, and the prompt says which sentence it is.
    """
    seen: list[str] = []
    for shot in carried:
        for found in _INTRINSIC.finditer(shot.text):
            if found.group(1) not in seen:
                seen.append(found.group(1))
    rows: list[dict] = []
    for name in seen:
        ok = bool((table.get(name) or {}).get("available"))
        rows.append(
            {
                "name": name,
                "available": ok,
                "form": None if ok else available_of.rename(name, isa, table),
            }
        )
    return rows


def _other_rows(lattice: Lattice, isa: str, carried: Sequence[Shot]) -> list[dict]:
    """Each name of the **shot's own file** the held-out file does not define, answered by rule W's family.

    Only a **function** has a family: rule W is a rule over the names of definitions, and the members it is
    matched against are the held-out file's units. A `#define` and a file-scope object therefore read "this
    file has no such definition", which is what the held-out file will say to the compiler too.

    A shot's own name is in its own text and is answered here like any other — `hsum128_ps` is sse2's and
    this file's is `hsum256_ps`, which is exactly the fact D-12's card asks the block to carry.
    """
    mine = file_scope(lattice, isa)
    ordered = units(lattice, isa)
    rows: list[dict] = []
    seen: set[str] = set()
    for shot in carried:
        theirs = file_scope(lattice, shot.isa)
        for token in _IDENT.finditer(shot.text):
            name = token.group(0)
            if name in seen or name in mine or name not in theirs:
                continue
            seen.add(name)
            candidates = (
                [other.name for other in ordered if family_key(other.name) == family_key(name)]
                if theirs[name] == "function"
                else []
            )
            rows.append(
                {
                    "name": name,
                    "from": shot.isa,
                    "kind": theirs[name],
                    "mine": candidates,
                    "status": "one" if len(candidates) == 1 else AMBIGUOUS if candidates else "none",
                }
            )
    return rows


def _availability_section(found: dict) -> str:
    """The block as the prompt carries it, or :data:`NO_EXAMPLES` alone where there were no shots."""
    if not found["shots"]:
        return NO_EXAMPLES
    lines: list[str] = []
    here = [row["name"] for row in found["intrinsics"] if row["available"]]
    if here:
        lines.append(AVAILABLE_HERE.format(names=", ".join(f"`{name}`" for name in here)))
    for row in found["intrinsics"]:
        if row["available"]:
            continue
        lines.append(
            NOT_AVAILABLE_FORM.format(name=row["name"], form=row["form"])
            if row["form"]
            else NOT_AVAILABLE.format(name=row["name"])
        )
    lines += [_other_line(row) for row in found["names"]]
    return _section(_AVAILABLE_HEADING, "\n".join(lines) if lines else NOTHING_IN_SHOTS)


def _other_line(row: dict) -> str:
    """One name of the other file's own: this file's member, its two candidates, or neither."""
    if row["status"] == "one":
        return OTHERS_ONE.format(name=row["name"], mine=row["mine"][0])
    if row["status"] == AMBIGUOUS:
        return OTHERS_AMBIGUOUS.format(
            name=row["name"], mine=", ".join(f"`{mine}`" for mine in row["mine"])
        )
    return OTHERS_NONE.format(name=row["name"])


# MARK: - D-13's fact lines: the same facts, in the loop -


def loop_facts(lattice: Lattice, isa: str, row: dict, record: dict, index: dict) -> dict:
    """The fact lines for one graded round-0 row (D-13 a): the names it named, and what this file has.

    *record* is :func:`lattice.available.load`'s — the compiler's answer for the **held-out** file, read
    under the grader's own flags — and *index* is the intrinsic index (`facts/intrinsics-clang18.json`),
    a JSON object keyed by intrinsic name. Both are needed and they answer different questions: the record
    says what *this file* can use, and only the index can say a name is declared by **no** header of this
    compiler, since the record holds nothing but what this file's own includes declare.

    The names are the pre-registration's two sources, in first-appearance order and deduplicated: every
    `invented` entry whose bucket is not :data:`lattice.e1.PARAM` — a renamed parameter is the runner's own
    re-bucketing and not a name the student invented — then every name clang's feature diagnostics quoted
    (:data:`_FEATURE_DIAGNOSTICS`).

    A name the rule has nothing to say about gets **no line** and lands in `unlined`: one available here
    (there is nothing to correct), a type, a local, and anything not intrinsic-shaped that no other kernel
    file defines either. `facts` is the lines in the names' own order, each `{"name", "status", "form",
    "line"}`.
    """
    table = available_of.names_for(record, isa)
    mine = file_scope(lattice, isa)
    ordered = units(lattice, isa)
    names = loop_names(row)
    facts: list[dict] = []
    unlined: list[str] = []
    for name in names:
        found = _loop_fact(lattice, isa, name, table, index, mine, ordered)
        (facts if found is not None else unlined).append(found if found is not None else name)
    return {"names": names, "facts": facts, "unlined": unlined}


def loop_names(row: dict) -> list[str]:
    """The names one graded row named, deduplicated in first-appearance order (the two sources above)."""
    found: list[str] = []
    for entry in row.get("invented") or ():
        name = entry.get("name")
        if name and entry.get("bucket") != e1.PARAM and name not in found:
            found.append(name)
    for diagnostic in (row.get("grade") or {}).get("diagnostics") or ():
        message = diagnostic.get("message") or ""
        for pattern in _FEATURE_DIAGNOSTICS:
            for quoted in pattern.findall(message):
                if quoted not in found:
                    found.append(quoted)
    return found


def _loop_fact(
    lattice: Lattice,
    isa: str,
    name: str,
    table: dict[str, dict],
    index: dict,
    mine: dict[str, str],
    ordered: Sequence[Unit],
) -> dict | None:
    """One name's line, or `None` where the rule has nothing to say about it (:data:`UNLINED`)."""
    if _INTRINSIC_SHAPED.match(name):
        entry = table.get(name) or {}
        if entry.get("available"):
            return None  # the body may use it: there is nothing here to correct
        form = available_of.rename(name, isa, table)
        declared = name in table or name in index
        status = NOT_HERE if declared else NOWHERE
        if declared:
            line = (
                NOT_AVAILABLE_FORM.format(name=name, form=form) if form else NOT_AVAILABLE.format(name=name)
            )
        else:
            line = (
                DECLARED_NOWHERE_FORM.format(name=name, form=form)
                if form
                else DECLARED_NOWHERE.format(name=name)
            )
        return {"name": name, "status": status, "form": form, "line": line}

    if name in mine:
        return None  # this file defines it, so the student may write it
    for other in other_natives(lattice, isa):
        theirs = file_scope(lattice, other)
        if name not in theirs:
            continue
        candidates = (
            [unit.name for unit in ordered if family_key(unit.name) == family_key(name)]
            if theirs[name] == "function"
            else []
        )
        return {
            "name": name,
            "status": OTHER_FILE,
            "form": candidates[0] if len(candidates) == 1 else None,
            "line": _other_line(
                {
                    "name": name,
                    "mine": candidates,
                    "status": "one" if len(candidates) == 1 else AMBIGUOUS if candidates else "none",
                }
            ),
        }
    return None


def loop_retry(base: str, found: dict) -> str:
    """S-3hf's retry: *base* — S-3hd's own text — then one section of fact lines, where there are any.

    `base` is **never cut**: the one variable between the two arms is what the lines add, so a retry whose
    lines crowded the graders' own message out would be two variables. Past :data:`LOOP_MAX_LINES` the
    section says how many names it left out (:data:`LOOP_MORE`) rather than stopping silently. Where no
    name has a line this returns *base* unchanged, which is what makes the two arms' retries byte-identical
    on such a chain.
    """
    lines = [fact["line"] for fact in found["facts"]]
    if not lines:
        return base
    shown = lines[:LOOP_MAX_LINES]
    if len(lines) > LOOP_MAX_LINES:
        shown.append(LOOP_MORE.format(count=len(lines) - LOOP_MAX_LINES))
    body = "\n".join(shown)
    return f"{base}\n\n{_section(_LOOP_HEADING, body)}"


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
    available: dict | None = None,
) -> dict:
    """One arm's context for one unit, as data: what it carries, and what it says it does not.

    A facts arm with no ledger is `prompts.NoLedger`, an S-5 with no parser row is :class:`NoFields`, and an
    S-3h with no availability record — or one that does not cover the held-out ISA — is
    :class:`NoAvailability`. None of the three is ever filled empty: an empty S-3 is S-2 under another name,
    an empty S-5 is S-3 under another name, an empty S-3h is S-2h under another name, and a row recorded
    under the wrong arm is worse than a row missing.

    *bodies* is S-2o's own-pass bodies (:func:`own_shots`). `None` is the same as none written yet, which
    is what **wave 0** is: a wave-0 unit has no designated neighbour, so no axis of it can read
    `neighbour-failed` for want of a body. Every later wave is built by :func:`run`, which always passes
    the rows it has.

    *available* is :func:`lattice.available.load`'s whole record, `{isa: {…, "names": {…}}}`.
    """
    if arm not in ARMS:
        raise prompts.UnknownArm(f"{arm!r} is not one of {', '.join(ARMS)}")
    if arm in FACTS_ARMS and facts is None:
        raise prompts.NoLedger(f"{arm} is a facts arm and no ledger was given; it is never filled empty")
    if arm in FIELD_ARMS and fields is None:
        raise NoFields(f"{arm} carries the parser's fields and none were given; it is never filled empty")
    if arm in FACTS_ISA_ARMS and not available_of.names_for(available or {}, isa):
        raise NoAvailability(
            f"{arm} carries what {isa}'s file can use and "
            + ("no availability record was given" if not available else f"the record does not cover {isa}")
            + "; it is never filled empty"
        )

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
        "available": (
            availability(lattice, isa, unit, carried, available) if arm in FACTS_ISA_ARMS else None
        ),
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
    available: dict | None = None,
) -> list[dict]:
    """The chat turns for one (unit, arm): the fixed system line, and one user turn — E1's shape."""
    return turns(context(lattice, isa, unit, arm, facts, fields, bodies, available))


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
    # S-3h's block is about the shots, so it goes directly under them and their note and nowhere else
    if data["available"] is not None:
        parts.append(_availability_section(data["available"]))

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
    available: dict | None = None,
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
                lattice, isa, unit, arm, model, k, facts=facts, fields=fields, available=available, wave=0
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
    available: dict | None = None,
    wave: int = 0,
) -> list[dict]:
    """One unit's requests on one arm: the greedy sample and *k* drawn ones, over one built context."""
    data = context(lattice, isa, unit, arm, facts, fields, bodies, available)
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
                # S-3h's block as data and not only as text: what each name's status was is the record of
                # what the arm served, and re-deriving it from a prompt afterwards would be reading it back
                # out of prose
                "available": data["available"],
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
    availability: dict | None = None,
) -> dict:
    """The run's `meta.json`: E1's record, plus the rung, the units' order and the P12 decomposition.

    `cells` holds the unit names — a unit stands where a cell does in E1's schema — and `units` holds the
    order with each unit's kind. **`p12` is `decomposed`** (:data:`P12`), and `decomposition` carries the
    unit count, the largest prompt and the held-out file's own length, so ADR-086's check can read off
    the record that every implementer's window was smaller than the task.

    `waves` is S-2o's order as names, one list per wave, and `parser` is :func:`parser_meta`'s block —
    which model filled S-5's fields and the digest of the file they were read from, so the arm names its
    own input. *availability* is `available.record_meta`'s block and lands under `available`, for the same
    reason: the digest of the record S-3h was built from, and per ISA the flags and the clang line that
    answered, so "not available in this file" on a prompt can be traced to the compiler that said it.
    `decomposition` is restated by :func:`run` as a wave adds requests the plan could not hold.
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
            "available": availability,
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


# MARK: - D-13's plan: one source run's round 0, copied twice -

#: What a D-13 plan carries over from its source unchanged, and refuses to invent where the source has none.
#: The model and the parameters because round 1 is asked of the same model at the same settings; `k` because
#: the chains are the source's chains; `target_sha` because the bodies are graded against that tree.
LOOP_CARRIED = ("model", "k", "params", "target_sha")

#: The source's three files, whose digests a D-13 plan records: round 0 is their bytes and not this run's.
LOOP_SOURCE_FILES = (e1.META, e1.REQUESTS, e1.ROWS)


def loop(
    source_dir: Path | str,
    run_dir: Path | str,
    *,
    available_path: Path | str,
    intrinsics_path: Path | str,
) -> Path:
    """Write a D-13 run: one finished E4 run's S-3h round 0, copied as S-3hd and S-3hf, with one round to go.

    **Nothing is asked here and nothing is spent.** Each S-3h request and its graded row is written twice,
    with only `arm` and `id` changed — `messages`, `params`, `grade`, `text`, `class` and the rest are the
    source's bytes — so the two arms begin from one answer and the only thing between them is the retry that
    :func:`run` will build. No `calls.jsonl` row is written either: round 0's spend is the source run's, and
    a row here would count it twice.

    *available_path* and *intrinsics_path* are the two instruments the lines are read with; their digests go
    on the record and :func:`run` refuses when either file's bytes have moved (:class:`LoopMoved`).
    """
    source_dir, run_dir = Path(source_dir), Path(run_dir)
    record = json.loads((source_dir / e1.META).read_text(encoding="utf-8"))
    for field in LOOP_CARRIED:
        if record.get(field) is None:
            raise LoopSource(
                f"{source_dir.name}'s {e1.META} has no {field}, and a D-13 run carries the source's "
                f"{', '.join(LOOP_CARRIED)} over unchanged; nothing was written"
            )

    asked = [request for request in _read(source_dir / e1.REQUESTS) if request.get("arm") == LOOP_SOURCE_ARM]
    if not asked:
        raise LoopSource(
            f"{source_dir.name} has no {LOOP_SOURCE_ARM} request; D-13's round 0 **is** {LOOP_SOURCE_ARM}'s, "
            "so there is nothing to copy and nothing was written"
        )
    rows = {row["id"]: row for row in _read(source_dir / e1.ROWS)}
    ungraded = [request["id"] for request in asked if request["id"] not in rows]
    if ungraded:
        raise LoopSource(
            f"{source_dir.name} answered no row for {', '.join(ungraded[:5])}"
            + (f" and {len(ungraded) - 5} more" if len(ungraded) > 5 else "")
            + "; a D-13 run is retried from a graded round 0, so nothing was written"
        )

    requests = [_loop_copy(request, arm) for request in asked for arm in LOOP_ARMS]
    copied = [_loop_copy(rows[request["id"]], arm) for request in asked for arm in LOOP_ARMS]
    plan_record = dict(record)
    plan_record.update(
        {
            "arms": list(LOOP_ARMS),
            "rounds": LOOP_ROUNDS,
            "iterate": list(LOOP_ARMS),
            "retry_classes": list(RETRY_CLASSES),
            "source": {
                "run": source_dir.name,
                "dir": str(source_dir),
                "arm": LOOP_SOURCE_ARM,
                "requests": len(asked),
                "rows": len(asked),
                **{
                    f"{name}_sha256": hashlib.sha256((source_dir / name).read_bytes()).hexdigest()
                    for name in LOOP_SOURCE_FILES
                },
            },
            "loop": {
                "arms": list(LOOP_ARMS),
                "rounds": LOOP_ROUNDS,
                "retry_classes": list(RETRY_CLASSES),
                "seed_arm": LOOP_SOURCE_ARM,
                "max_lines": LOOP_MAX_LINES,
                "available": _loop_instrument(available_path),
                "intrinsics": _loop_instrument(intrinsics_path),
            },
        }
    )
    written = e1.write_plan(run_dir, requests, plan_record)
    _append(written / e1.ROWS, copied)
    return written


def _loop_copy(row: dict, arm: str) -> dict:
    """One request or row under another arm's name: `arm` and `id`, and not one other field."""
    return {
        **row,
        "arm": arm,
        "id": e1.request_id(row["cell"], arm, row["sample"], row.get("round") or 0),
    }


def _loop_instrument(path: Path | str) -> dict:
    """One instrument on the record: where it was read from, and the digest :func:`run` holds it to."""
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def registered_pair(first: str, second: str, kind: str | None, through: int = 0) -> bool:
    """Whether `second − first` over *kind*, read through round *through*, is a registered comparison.

    :data:`COMPARISONS` is the round-0 list; D-13's pair is registered **through round 1** and over every
    unit, because that is what its card registered — the same two arms read at round 0 alone is a tie by
    construction (their round 0 is one row copied twice) and is a description of nothing.
    """
    if through <= 0:
        return (first, second, kind) in COMPARISONS
    return kind is None and (first, second) == LOOP_PAIR


def registered_rounds(arm: str, rounds: Sequence[int]) -> bool:
    """Whether one arm's round reading is D-13's second registered one: S-3hf, round 0 against round 1."""
    return arm == LOOP_PAIR[1] and tuple(rounds) == (0, LOOP_ROUNDS)


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

    **A D-13 run iterates once** (:func:`loop`). `rounds`, `iterate` and `retry_classes` are read off
    `meta.json`, so what a run does is the plan's and not this call's: a plan without them is `rounds=0`,
    exactly as before. Where they are there, E1's loop runs with D-13's hooks — the retry builder, the two
    retried classes and the seed both arms share — and the instruments' digests are checked first
    (:class:`LoopMoved`).
    """
    run_dir = Path(run_dir)
    record = json.loads((run_dir / e1.META).read_text(encoding="utf-8"))
    isa = record["isa"]
    graded = _unit_grade(grade, isa)
    rounds = int(record.get("rounds") or 0)
    iterate = tuple(record.get("iterate") or ())
    hooks = _loop_hooks(target, record) if rounds and iterate else {}
    summary = e1.run(
        run_dir, target, generate, graded, ceiling_usd=ceiling_usd, rounds=rounds, iterate=iterate, **hooks
    )
    if any(arm in OWN_ARMS for arm in record.get("arms") or ()):
        summary = _own_waves(run_dir, target, record, generate, graded, ceiling_usd, summary)
    summary["file_level"] = file_level(run_dir, target, grade)
    return summary


def _loop_hooks(target: Path | str, record: dict) -> dict:
    """D-13's four hooks for `e1.run`, with both instruments held to the digests the plan named.

    The retry is the one place the two arms differ: S-3hd gets `e1._retry`'s text — called, not copied, so
    there is one definition of what E1 sends back — and S-3hf gets that text plus :func:`loop_retry`'s
    section. `fields` puts the lines on the fresh request as **data**, because a prompt is not a record:
    what each name's status was is what the arm served, and reading it back out of prose afterwards would
    be a second rule beside this one.
    """
    block = record.get("loop") or {}
    available = _loop_read(block.get("available") or {}, "availability record")
    index = _loop_read(block.get("intrinsics") or {}, "intrinsic index")
    lattice = build_lattice(target)
    isa = record["isa"]
    named = block.get("seed_arm") or LOOP_SOURCE_ARM
    facts = LOOP_PAIR[1]

    def found(row: dict) -> dict:
        return loop_facts(lattice, isa, row, available, index)

    def retry(request: dict, row: dict) -> str:
        base = e1._retry(request, row)
        return loop_retry(base, found(row)) if request.get("arm") == facts else base

    def fields(request: dict, row: dict) -> dict:
        if request.get("arm") != facts:
            # S-3hd carries no lines, by design: its record says so rather than leaving the field out
            return {"loop_facts": [], "unlined": []}
        lines = found(row)
        return {"loop_facts": lines["facts"], "unlined": lines["unlined"]}

    return {
        "retry_classes": tuple(record.get("retry_classes") or RETRY_CLASSES),
        "retry": retry,
        "seed_arm": lambda arm: named,
        "fields": fields,
    }


def _loop_read(block: dict, what: str) -> dict:
    """One instrument's JSON, refused unless its bytes still digest to what the plan recorded."""
    path = Path(block.get("path") or "")
    digest = block.get("sha256")
    if not block.get("path") or digest is None:
        raise LoopMoved(f"the plan records no {what} for its fact lines, so nothing was sent")
    try:
        raw = path.read_bytes()
    except OSError as missing:
        raise LoopMoved(f"the {what} {path} could not be read ({missing}), so nothing was sent") from missing
    now = hashlib.sha256(raw).hexdigest()
    if now != digest:
        raise LoopMoved(
            f"the plan's {what} digested {digest[:12]} and {path} now digests {now[:12]}; its lines would "
            "be another instrument's answer, so nothing was sent"
        )
    return json.loads(raw.decode("utf-8"))


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

    **On a loop run the chain's final row is the one that counts** (D-13): a unit retried at round 1 is
    written from round 1 where that row passed, and from round 0 where it was never retried. A run with no
    rounds reads exactly as before, since round 0 is then the only round there is.
    """
    run_dir, target = Path(run_dir), Path(target)
    record = json.loads((run_dir / e1.META).read_text(encoding="utf-8"))
    isa = record["isa"]
    lattice = build_lattice(target)
    source = lattice.sources[isa]
    ordered = units(lattice, isa)
    by_name = {unit.name: unit for unit in ordered}

    greedy = _greedy_final(_read(run_dir / e1.ROWS), int(record.get("rounds") or 0))
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


def _greedy_final(rows: Sequence[dict], through: int) -> list[dict]:
    """Each (arm, unit) greedy chain's row of the **highest round ≤ through**, in the rows' own order.

    With `through = 0` this is the round-0 greedy rows and nothing else, which is every run but D-13's.
    """
    best: dict[tuple[str, str], dict] = {}
    for row in rows:
        if row.get("sample") != 0 or not row.get("arm"):
            continue
        at_round = int(row.get("round") or 0)
        if at_round > through:
            continue
        chain = (row["arm"], row["cell"])
        if chain not in best or at_round > int(best[chain].get("round") or 0):
            best[chain] = row
    return list(best.values())


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
