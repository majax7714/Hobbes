# ADR-136 — A line R1 vacated is not a clean file's: the mint reads the definition there

**Date:** 2026-09-18 · **Status:** proposed — routes for Max below; nothing built, no version move.

Follows ADR-135 (R1: a lane A C++ function or method whose own name
token the index reads as a reference is removed) and the C++ recall
list's fourth item, ScummVM as a scale read. A build would be a patch: a
constraint's fix (C-164).

## Context

ADR-129's mint refuses a definition row in a file lane A parsed without
ERROR nodes (`clean-file`): a clean parse was taken as lane A having
read the file right, so a row lane A has no symbol for is a declaration,
a local or inactive code, and none of the mint's business. ADR-135's R1
is evidence against exactly that premise, one line at a time — the index
reads the symbol's *name* as a macro reference — and on fmt the two
never met: all 18 removals were in lossy files, and the mint named the
true definition on the vacated line where its rules allowed.

## The measurement (`~/.hobbes/bench/scummvm-scale/`, key-free, nothing drawn)

ScummVM (`c54b79a6`, 19,948 C++ files, 5,958 translation units) ingested
end to end at 0.2.47-beta, exit 0, beside its 0.2.26-beta graph.

**R1 fired 401 times** (400 `macro`, 1 `term`), and the 401 lane A
functions gone from the old graph carry 27 names: 22 are function-like
macros that *generate* a definition — `DECLARE_COMMAND_OPCODE(location)
{ … }` 59 times, `APPFUNC`, `TERMINATOR`, `INITIALIZER`, the `SPELL…`
family — 4 are object-like renames (`#define yyparse HYPNO_ARC_parse`,
`luaI_openlib`, `strlib_open`, `zopen`), and one is a constructor's
member initialiser (`_RGBtoYUV`). Every name was read against the
source: none is the function's name. No false flag seen.

**`vacated.py`: what the index holds at each vacated line**, walked
through the mint's refusals other than `clean-file`:

| file parsed | removed | one definition row with a body | minted at 0.2.47-beta |
|-------------|--------:|-------------------------------:|----------------------:|
| with errors | 141     | 137 (2 no row, 2 several monikers) | **137** — 131 with a brace extent |
| clean       | **260** | **260**                        | **0** — `clean-file`  |

The 260 are in 19 files. A generator macro parses as a function
definition with no ERROR node, so the file is "clean", lane A's symbol
is named for the macro, R1 removes it, and the true definition
(`Parallaction::CommandExec_br::cmdOp_location`, `Grim::lua_strlibopen`)
gets no node: the calls written in its body are the module's, and a call
*to* it lands nowhere. Before 0.2.47-beta those 260 were wrong symbols
(59 of them sharing one name); now they are absent. Absent is the
honest side of that trade, and the index holds the right answer on the
same line.

The lossy half is the prediction for the clean half: same macros, same
rules, 137 of 137 minted, 131 with an extent.

## Decision (proposed)

The mint's `clean-file` refusal does not apply to a definition row **at
a line R1 vacated**. `contradicted` already knows those `(file, line)`
pairs; `mint` takes them beside `lossy_files`. Every other refusal
still runs (`kind`, `local-to-function`, `anonymous`,
`several-monikers`, `declaration`, `lane-a-has-type`), the extent is
ADR-134's, and `rehome` moves the module-scoped facts R1 left into it.
The rest of a clean file's rows stay refused.

## Routes for Max

- **(a) — recommended: the vacated line only.** ScummVM: 260
  definitions named, about 245 with an extent if the lossy half's rate
  (131 of 137) holds; some of R1's 7,548 re-scoped facts return to a
  right caller. fmt, args, cJSON, sqlite-vector: R1 removed nothing in a
  clean file (fmt 18 of 18 lossy; nothing fires on the other three), so
  **no graded number and no export row can move** — the check is that
  they do not.
- **(b) a file R1 fired in is lossy as a whole.** Reaches more (a
  generator macro lane A read as something other than a function), but
  it opens 19 files' every unmatched row on ScummVM on the strength of
  one line, and `clean-file` was set where a clean file's unmatched rows
  were declarations and inactive code. Not measured; measure before
  taking it.
- **(c) leave it.** The 260 stay registered under C-164 as absent.

## Alternatives considered

- **Keep lane A's symbol and rename it from the index.** A rename keeps
  lane A's extent, which for these shapes is right — but it makes lane A's
  symbol table depend on lane B for a *name*, which ADR-135 declined
  (remove, then let the mint's own rules decide).
- **R1 only in lossy files.** Would restore the 260 wrong names.

## Consequences

- `minted.refused.clean-file` is no longer every unmatched row in a
  clean file; the graph block gains a count of vacated-line mints so the
  summary can say so.
- No key judges a caller or a node, so as ADR-134 and ADR-135 this is
  checked, not graded: the four graded cells row-identical, ScummVM's
  260 read by sample against the source.
