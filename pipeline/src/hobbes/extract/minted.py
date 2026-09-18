"""Definitions lane A's parse lost, read back from lane B's index (ADR-129).

C++ has the lowest recall of any supported language because
tree-sitter-cpp cannot parse a declaration spelled through macros
(``FMT_API``, ``FMT_BEGIN_NAMESPACE``): the definition falls inside an
ERROR node, lane A keeps no symbol, and
:func:`hobbes.extract.scipsource.project` drops every call scip-clang
resolved there as ``below-floor`` — ``starting_at`` has nothing to
answer with. **These are not inferred edges**: the compiler resolved the
call and the index holds the definition's file, line, kind and moniker.
What is missing is a node, so this module mints one, and the symbol says
who declared it (``declared_by: "scip"``; every lane A symbol lacks the
field).

**A minted function or method also gets an extent** (ADR-134):
``end_line`` becomes the line its body's closing brace is on, matched in
the file's own text — the only evidence there is, since scip-clang's
index carries no ``enclosing_range`` to read one from. A ``calls`` or
``uses`` fact written inside such a body is then drawn from it rather
than from the module (:func:`rehome`): 1,290 of fmt's call rows, read
against the key's own caller names and none of them wrong. A minted
**type** stays a line as every mint did (ADR-129 §3) — its members are
symbols of their own, and a class head is where macros bite hardest.

The extent is refused four ways, each leaving ``end_line`` at the line:

``no-body``
    No ``{`` at parenthesis depth 0 before a ``;`` or the end of the
    file. :func:`shows_body` should have made this impossible; the read
    refuses rather than assume it did.
``runs-off``
    The opening brace never closes. Unseen on either measured cell.
``conditional-inside``
    A ``#if``/``#ifdef``/``#else``/``#elif``/``#endif`` line between the
    braces: either branch may hold the brace the compiler saw, and a
    rule here fails toward drawing less. 34 on fmt. A ``#define`` or an
    ``#include`` inside a body refuses nothing.
``holds-a-definition``
    Another function or method — lane A's or minted — starts inside the
    extent. A definition lexically inside a function body is below the
    symbol floor by decision (C-9, the ``local-to-function`` refusal), so
    a symbol found there says the brace match or the parse is wrong. 19
    on fmt: 13 macro-generated methods
    (``GTEST_REPEATER_METHOD_(OnTestStart, TestInfo)`` is a whole method
    to clang and a line with no ``{`` in the text, so the match ran on
    into the next function written out) and 6 true bodies holding a
    symbol lane A named after an annotation macro (C-164).

**When in doubt, mint nothing.** A naive rule — mint wherever lane B
defines and lane A does not — graded 98.2% on fmt with 123 contradicted
edges. Each refusal below removed measured wrong edges, and with all of
them the fmt export read 6,533 confirmed at **0 contradicted** (3,269
before), recall 14.5% → 29.1%; args, held out, added 67 edges, 67
confirmed. The refusals, with what the measurement said:

``clean-file``
    The file's lane A parse had no ERROR nodes. There a missing symbol is
    lane A's floor speaking by decision — a lambda, a local class (C-9) —
    not a loss. 1 fact of that shape on fmt. **Except at a line R1
    vacated** (ADR-136, below): that removal is evidence against this
    premise at exactly one line, and the row there is read as a lossy
    file's is.
``kind``
    The row's descriptor kind is not ``method`` (scip-clang's suffix for
    every function, member or free) or ``type``. Never ``term``: 74 on
    fmt, a data member whose initialiser is spelled like a call
    (``key_(CreateKey())``). Never ``macro``: 2,554 on fmt, and a macro is
    expanded rather than called, excluded from every grade. Never
    ``namespace``.
``local-to-function``
    The moniker's owner chain holds a function
    (``gmtime(3bbc…).dispatcher#run(c985…).``), so the definition is
    inside a function body — below the symbol floor by decision (C-9),
    and a recovery rule does not lower the floor. Measured as a floor
    question and not from a contradiction: 10 facts on fmt, 5 confirmed
    edges given up; 0 on args.
``several-monikers``
    More than one moniker has a definition row at that file and line, so
    which one the node would be is a guess. 28 lines on fmt.
``lane-a-symbol-near``
    A lane A symbol of the same terminal name starts within
    :data:`NEAR_LINES` of the row. Written as the two lanes disagreeing
    about which line a definition is on; read row by row on 2026-09-18
    (19 rows on four cells, 15 of them fmt's), one is that
    (``typedef struct sqlite3_snapshot { … } sqlite3_snapshot;``, the
    struct's line against the typedef's). The rest are a defaulted or
    deleted constructor beside an overload or its class, and the other
    arm of an ``#if`` lane A read the first arm of — each of which
    ``declaration`` or ``lane-a-has-type`` refuses next. Nothing the
    rule refuses is a definition lane A lost, so it stands as it is.
``declaration``
    :func:`shows_body` finds no body at the line. scip-clang gives a
    declaration the definition role, so the rows include gtest's forward
    declarations of ``CountIf``, ``ForEach``, ``GetElementOr`` and
    ``Shuffle`` (``gmock-gtest-all.cc:1630–1633``, defined at 677–731),
    a block-scope ``using``, and every ``= default;`` and ``= delete;``.
    308 on fmt. Lane A's own rule, kept: symbols come from definitions
    only, never a declaration.
``anonymous``
    A descriptor in the chain is one scip-clang invented for an unnamed
    struct, union or enum (``$anonymous_type_9456…_0``). There is no name
    in the source to give the symbol, and lane A names such a type by its
    ``typedef`` where it has one. Found by the built rule's first regrade,
    not by the probe — which only saw definitions some call targets: every
    symbol the C cells minted was of this shape or the next (cJSON 11,
    sqlite-vector 10), and 21 on fmt.
``lane-a-has-type``
    The row is a ``type`` and lane A already holds a ``type`` of the same
    terminal name in the module, at another line: ``typedef struct cJSON
    {…} cJSON;`` (lane A names the typedef, lane B the tag's line), or the
    two arms of an ``#if`` (fmt's ``using day = std::chrono::day;`` and
    its fallback ``class day``). Lane A did not lose that type, and its
    one-symbol-per-name rule for types already chose. Same regrade: 11 on
    fmt. Functions are not refused this way — two bodies of one name are
    overloads, and the second takes ``~b2``.
``unreadable``
    The moniker is not a descriptor chain this module can spell, so
    there is no name to give the symbol. Not in the ADR's tally: the
    reader agrees with ``scip/index.mjs``'s grammar, and a moniker it
    refuses is one no rule here can honestly name.

A row whose line already starts a lane A symbol is the normal case — the
two lanes meeting — and is counted under no reason at all.

A minted function or method also carries **how many parameters its
declaration spells** (``max_params``, ADR-130), read from the same tokens
:func:`shows_body` reads: the rule that draws no edge where a call is
written with more arguments than its target takes cannot fire on a symbol
lane A never parsed unless something reads the count, and these symbols
are precisely the ones the wrong edges land on. The read is *unknown*
wherever it is not clean, and an unknown draws the edge.

**The index also contradicts symbols lane A did keep** (ADR-135), and
:func:`contradicted` refuses those before anything is minted. Where
tree-sitter-cpp recovers from a macro it cannot read it keeps a function
named for the wrong token — ``void UnitTest::AddTestPartResult(..)
GTEST_LOCK_EXCLUDED_(mutex_) {`` is a function called
``GTEST_LOCK_EXCLUDED_``, and ``FMT_CONSTEVAL basic_fstring(const S& s) :
str_(s) {`` is ``basic_fstring::str_`` — or one whose extent runs on over
the definitions written after it. Those rows are *wrong* rather than
missing (C-164), and the calls inside are drawn from them.

``R1``
    A function's or method's own name at its definition is a definition
    occurrence, never a reference. Where lane B holds a **reference** at
    exactly the token lane A took as the name (``name_col``,
    :func:`hobbes.extract.cppsource._symbol`), resolved to a ``macro`` row
    or to a ``term`` row of that same name, the parse took the wrong
    token: the symbol is dropped and its facts take the module's id as
    their scope, which is the scope lane A gives a file-level site — so
    the mint sees the line as lost, mints the true definition where the
    index has one, and :func:`rehome` moves the facts onto it. 13
    ``macro`` and 5 ``term`` on fmt, every one of the 18 misnamed by a
    hand read, none of the 3,769 right ones flagged; 0 on args, cJSON and
    sqlite-vector. Six of ADR-134's ``holds-a-definition`` refusals were a
    minted extent holding one of these symbols, and unblock with it.
    **The position has to be exact:** read loosely — a same-named
    reference anywhere in the head or the body — the same rule flags
    *right* symbols, args' ``Base::KickOut`` beside the enumerator
    ``Options::KickOut`` among them.
``R2``
    A function or method whose extent holds a file- or class-scope
    definition row has that extent re-read from the file's braces by
    :func:`_extent`, the reader ADR-134 already mints with: a nearer end
    is taken, an end at or past the parse's is left alone (the braces
    agree, and the held row is something this rule does not understand),
    and a refusal leaves the symbol its own line. Facts written past the
    new end take the module's id. 1 on fmt after R1, 0 elsewhere.

Neither rule renames anything, and neither marks a lane A extent
``extent: "braces"`` — that field says *minted*. **P6:** with no index
there are no references and no definition rows, so neither can fire and
the graph is what it was; ``name_col`` is the only difference such a
graph shows.

**A line R1 vacated is not a clean file's** (ADR-136). A function-like
macro that *generates* a definition — ``DECLARE_COMMAND_OPCODE(location)
{ … }`` — parses with no ERROR node, so the file is clean, lane A names
the function after the macro, and R1 removes it on the index's word;
``clean-file`` would then refuse the true definition the index holds on
the same line, and the line would carry no symbol at all. So :func:`mint`
takes the ``(file, line)`` pairs R1 vacated beside *lossy_files*, and
refuses a row at neither. Nothing else is lifted: every other refusal
runs on such a row in its own order, and the rest of a clean file's rows
are refused as they were. ScummVM: 401 removals, 260 of them in 19 clean
files, each line holding exactly one definition row with a body and none
minted before this — against the lossy half's 137 of 137 minted under the
same rules, the same macros. fmt meets none of it: all 18 of its removals
are in lossy files, so no graded number moves. The mints are counted
apart (``vacated``), because ``files`` means the files lane A parsed with
errors and these are not among them.

:func:`constructor_lines` reads the same rows for a different question
(ADR-132): which lines a **constructor** is defined at, so the join can
tell a construction's reference from a type's at a declared name. It
mints nothing, and it lives here because the moniker reader does.

**P6.** With no indexer there are no ``definitions`` rows, so nothing is
minted and the floor is exactly what it was; the caller writes no
``minted`` block into the graph either.
"""

from __future__ import annotations

import dataclasses
import re
from bisect import bisect_right
from pathlib import Path
from typing import Iterable, Mapping, Sequence

#: The descriptor kinds a row may mint from (ADR-129 §1). ``method`` is
#: scip-clang's suffix for every function; ``type`` is a class, struct,
#: union or enum.
MINTABLE_KINDS = ("method", "type")

#: How far past the definition line :func:`shows_body` reads. Long enough
#: for a constructor's initialiser list or a parameter list broken over
#: several lines, short enough that a lost definition cannot borrow a
#: body written far below it.
BODY_WINDOW = 40

#: A lane A symbol of the same terminal name this close to a row's line is
#: the two lanes disagreeing about the line, not a lost definition.
NEAR_LINES = 3

#: Every reason a row was not minted, in the order the rules are read.
#: Fixed, so the block a reader meets has the same shape on every repo —
#: a reason that never fired reads ``0`` rather than being absent.
REFUSALS = (
    "clean-file",
    "kind",
    "local-to-function",
    "several-monikers",
    "lane-a-symbol-near",
    "declaration",
    "anonymous",
    "lane-a-has-type",
    "unreadable",
)

#: Every reason a minted function's extent was refused, in the order the
#: read meets them. Fixed for :data:`REFUSALS`' reason: the block reads the
#: same way on every repo.
EXTENT_REFUSALS = ("no-body", "runs-off", "conditional-inside", "holds-a-definition")

#: What the index contradicts a lane A C++ definition's name with (ADR-135,
#: R1), in the order :func:`contradicted` reads them: a reference at the
#: symbol's own name token resolving to a macro's definition, or to a data
#: member of that same name. Fixed for :data:`REFUSALS`' reason — the block
#: reads the same way on every repo.
CONTRADICTIONS = ("macro", "term")

#: Every reason R2's re-read of a **lane A** extent can refuse, which is
#: :data:`EXTENT_REFUSALS` without ``holds-a-definition``: that one belongs
#: to the mint's second pass, and here a held definition is the rule's
#: condition rather than a refusal.
READ_REFUSALS = ("no-body", "runs-off", "conditional-inside")

#: What a minted symbol's ``extent`` field says where its body was read: the
#: file's own braces, matched (ADR-134). Absent on every other symbol — a
#: lane A extent is the parse's, and needs no name.
EXTENT_BRACES = "braces"

#: The symbol kinds whose body an extent stands for, and whose line inside
#: another's extent says the brace match or the parse is wrong.
_DEFINITION_KINDS = ("function", "method")

#: A preprocessor conditional line (ADR-134 §2). Read on the blanked text,
#: so a ``#if`` written inside a comment or a string is not one.
_CONDITIONAL = re.compile(r"^[ \t]*#[ \t]*(if|ifdef|ifndef|else|elif|endif)\b")

#: scip-clang's spelling for a struct, union or enum the source does not
#: name. A chain holding one has no source name to give the symbol.
_ANONYMOUS = "$anonymous"

#: The descriptor suffixes SCIP spells, by what they denote. A method's is
#: not here: it is ``(<disambiguator>).``, read by :func:`read_moniker`.
_SUFFIXES = {"#": "type", "/": "namespace", ".": "term", ":": "meta", "!": "macro"}

#: The characters that end an unescaped descriptor name.
_NAME_END = "#/.:!("

_UNREAD = object()


def mint(
    repo_root: Path,
    definitions: Iterable[Mapping],
    lossy_files: frozenset[str],
    symbols: Sequence[Mapping],
    module_of_path: Mapping[str, str],
    vacated: frozenset[tuple[str, int]] = frozenset(),
) -> tuple[list[dict], dict]:
    """The symbols lane B's ``definitions`` rows mint, and the counts.

    *definitions* are the rows of every C or C++ file lane A walked;
    *lossy_files* the repo-relative paths whose parse had ERROR nodes;
    *symbols* lane A's, as ``graph["symbols"]`` holds them;
    *module_of_path* the graph's file-to-module map; and *vacated* the
    ``(file, line)`` pairs :func:`contradicted`'s R1 emptied, where
    ``clean-file`` does not apply (ADR-136). Pure but for reading each
    file's own text, which is rule 6's whole evidence and the extent's
    (ADR-134).

    Deterministic: the rows are deduplicated and read in
    ``(file, line, moniker)`` order, so the ids a collision hands out
    (``~b2``, ``~b3``, …) fall in line order within a file.
    """
    refused = dict.fromkeys(REFUSALS, 0)
    rows = sorted(
        {
            (row["file"], row["line"], row.get("moniker") or "", row.get("kind") or "")
            for row in definitions
        }
    )
    # Rule 4 is a property of the line, so it is read off every row at it —
    # including the kinds rule 2 refuses. A `term` beside a `method` at one
    # line is still two monikers, and minting there would pick one.
    monikers_at: dict[tuple[str, int], set[str]] = {}
    for file, line, moniker, _ in rows:
        monikers_at.setdefault((file, line), set()).add(moniker)

    lane_a_lines: dict[str, set[int]] = {}
    lane_a_named: dict[tuple[str, str], list[int]] = {}
    lane_a_types: set[tuple[str, str]] = set()
    taken = {symbol["id"] for symbol in symbols}
    for symbol in symbols:
        module = symbol.get("module")
        if module is None:
            continue  # a module node, not a symbol
        lane_a_lines.setdefault(module, set()).add(symbol["line"])
        lane_a_named.setdefault((module, symbol["name"]), []).append(symbol["line"])
        if symbol.get("kind") == "type":
            lane_a_types.add((module, symbol["name"]))

    minted: list[dict] = []
    minted_files: list[str] = []
    files: set[str] = set()
    # ADR-136's own count, kept apart from *files*: a clean file holding
    # nothing but vacated-line mints is not a file lane A parsed with
    # errors, and the summary's sentence says which is which.
    vacated_files: set[str] = set()
    vacated_symbols = 0
    sources: dict[str, list[str] | None] = {}
    blanked: dict[str, list[str] | None] = {}
    for file, line, moniker, kind in rows:
        module = module_of_path.get(file)
        if module is None:
            continue  # a file lane A never discovered; not ours to name
        if line in lane_a_lines.get(module, ()):
            continue  # the lanes meet here: the normal case, not a refusal
        if file not in lossy_files and (file, line) not in vacated:
            # ADR-136: a clean parse is the premise this refusal rests on,
            # and R1's removal is evidence against it at this one line.
            refused["clean-file"] += 1
            continue
        if kind not in MINTABLE_KINDS:
            refused["kind"] += 1
            continue
        chain = read_moniker(moniker)
        if chain is None:
            refused["unreadable"] += 1
            continue
        if any(suffix == "method" for _, suffix in chain[:-1]):
            refused["local-to-function"] += 1
            continue
        if any(part.startswith(_ANONYMOUS) for part, _ in chain):
            refused["anonymous"] += 1
            continue
        if len(monikers_at[(file, line)]) > 1:
            refused["several-monikers"] += 1
            continue
        name = chain[-1][0]
        if any(abs(at - line) <= NEAR_LINES for at in lane_a_named.get((module, name), ())):
            refused["lane-a-symbol-near"] += 1
            continue
        if not shows_body(repo_root, file, line, sources):
            refused["declaration"] += 1
            continue
        if kind == "type" and (module, name) in lane_a_types:
            refused["lane-a-has-type"] += 1
            continue
        qualname = "::".join(part for part, _ in chain)
        # A type row is a type; a function row is a `method` when a class
        # owns it (`…Foo#bar(hash).`) and a `function` otherwise — a
        # namespace owner, or none at all.
        symbol_kind = (
            "type"
            if kind == "type"
            else ("method" if len(chain) > 1 and chain[-2][1] == "type" else "function")
        )
        symbol = {
            "id": _free_id(f"{module}.{qualname}", taken),
            "module": module,
            "name": name,
            "qualname": qualname,
            "kind": symbol_kind,
            "line": line,
            # ADR-129 §3's line; the extent read below moves it to the
            # closing brace's where the file's own braces give one.
            "end_line": line,
            "declared_by": "scip",
        }
        if symbol_kind != "type":
            # ADR-130: what the definition's own parameter list can take,
            # read from its tokens. A type takes no arguments in this
            # sense — a construction's target is its constructor.
            symbol["max_params"] = read_max_params(repo_root, file, line, name, sources)
        minted.append(symbol)
        minted_files.append(file)
        if file in lossy_files:
            files.add(file)
        else:
            vacated_symbols += 1
            vacated_files.add(file)

    # ADR-134, a second pass because its last refusal is a property of the
    # whole minted list: the symbols are settled first, then each function's
    # body is matched in the file's text and `end_line` moved onto it.
    extents = _read_extents(repo_root, minted, minted_files, symbols, sources, blanked)
    return minted, {
        "symbols": len(minted),
        "files": len(files),
        "vacated": {"symbols": vacated_symbols, "files": len(vacated_files)},
        "refused": refused,
        "extents": extents,
    }


def contradicted(
    repo_root: Path,
    symbols: Sequence[Mapping],
    facts: Sequence,
    resolutions: Iterable,
    definitions: Iterable[Mapping],
    module_of_path: Mapping[str, str],
) -> tuple[list[dict], list, dict, frozenset[tuple[str, int]]]:
    """ADR-135's two rules over the joined facts: the symbols the index
    contradicts, the facts they no longer speak for, the counts, and the
    ``(file, line)`` R1 vacated.

    *symbols* are lane A's as ``graph["symbols"]`` holds them, *facts* the
    join's output, *resolutions* lane B's sites (``file``, ``line``,
    ``name``, ``col``, ``def_file``, ``def_line``), *definitions* the rows
    of every C or C++ file lane A walked, and *module_of_path* the graph's
    file-to-module map. Runs **before** :func:`mint`, so a symbol R1
    removes leaves a line the mint reads as lost.

    Only a symbol carrying ``name_col`` is looked at — lane A's C++
    functions and methods, and no minted or C symbol — and a symbol
    nothing contradicts is returned exactly as it came. Returns new lists:
    no dict this is handed is written to.

    The fourth return is the positions **R1** emptied — a symbol's file
    and its own line, one pair per symbol removed — which :func:`mint`
    reads as ADR-136's exception to ``clean-file``. R2 vacates nothing: it
    clips an extent and the symbol keeps its line. Not a key in *counts*,
    which is written to the graph as it is.

    Deterministic: the symbols are read in id order, and the resolutions
    in one pass over the positions wanted, which is also what makes this
    affordable — a large repo holds millions of them and only a few
    thousand positions are asked about.
    """
    counts = {
        "refused": dict.fromkeys(CONTRADICTIONS, 0),
        "extents": {"read": 0, "kept": 0, "refused": dict.fromkeys(READ_REFUSALS, 0)},
        "facts_rescoped": 0,
    }
    # Both rules ask the index about the symbol's own **file**, so a module
    # two paths share (a `.cpp` beside a `.c` of one stem, C-15) is left
    # out: which file a symbol of it was written in is not known here, and
    # neither rule fires on a position it cannot place.
    path_of_module: dict[str, str | None] = {}
    for path, module in module_of_path.items():
        path_of_module[module] = None if module in path_of_module else path
    candidates: list[tuple[Mapping, str]] = []
    for symbol in sorted(
        (s for s in symbols if s.get("name_col") is not None), key=lambda s: s["id"]
    ):
        file = path_of_module.get(symbol.get("module"))
        if file is not None:
            candidates.append((symbol, file))
    if not candidates:
        return list(symbols), list(facts), counts, frozenset()

    rows_at: dict[tuple[str, int], list[Mapping]] = {}
    held: dict[str, list[int]] = {}
    for row in definitions:
        rows_at.setdefault((row["file"], row["line"]), []).append(row)
        if _at_outer_scope(row):
            held.setdefault(row["file"], []).append(row["line"])
    for lines in held.values():
        lines.sort()

    # R1. The positions are known before the resolutions are read, so each
    # one is looked at once and dropped: on a repo the size of fmt this is
    # a few thousand keys against 1.8 million sites.
    wanted: dict[tuple[str, int, int], list[Mapping]] = {}
    for symbol, file in candidates:
        wanted.setdefault((file, symbol["line"], symbol["name_col"]), []).append(symbol)
    resolved_to: dict[str, set[tuple[str, int]]] = {}
    for site in resolutions:
        if site.col < 0:
            continue
        for symbol in wanted.get((site.file, site.line, site.col), ()):
            if site.name == symbol["name"]:
                resolved_to.setdefault(symbol["id"], set()).add(
                    (site.def_file, site.def_line)
                )

    refused: dict[str, str] = {}
    vacated: set[tuple[str, int]] = set()
    for symbol, file in candidates:
        reason = _contradiction(symbol, resolved_to.get(symbol["id"], ()), rows_at)
        if reason is not None:
            counts["refused"][reason] += 1
            refused[symbol["id"]] = symbol["module"]
            # Where the symbol stood: the mint reads this line even in a
            # file that parsed clean (ADR-136).
            vacated.add((file, symbol["line"]))

    # R2, on what R1 left: an extent holding a definition the index places
    # at file or class scope says the parse ran on over it, so the file's
    # own braces are asked where the definition really ends.
    sources: dict[str, list[str] | None] = {}
    blanked: dict[str, list[str] | None] = {}
    clipped: dict[str, tuple[str, int]] = {}
    for symbol, file in candidates:
        if symbol["id"] in refused:
            continue
        end = symbol.get("end_line") or symbol["line"]
        lines = held.get(file, ())
        inside = bisect_right(lines, symbol["line"])
        if inside >= len(lines) or lines[inside] > end:
            continue
        text = _blanked_lines(repo_root, file, sources, blanked)
        # A file that will not read shows no body, as it does at the mint.
        read, reason = _extent(text, symbol["line"]) if text is not None else (None, "no-body")
        if read is None:
            counts["extents"]["refused"][reason] += 1
            clipped[symbol["id"]] = (symbol["module"], symbol["line"])
        elif read >= end:
            # The braces agree with the parse: whatever the held row is,
            # this rule does not understand it, and leaves the symbol alone.
            counts["extents"]["kept"] += 1
        else:
            counts["extents"]["read"] += 1
            clipped[symbol["id"]] = (symbol["module"], read)

    if not refused and not clipped:
        return list(symbols), list(facts), counts, frozenset()
    out_symbols = [
        {**symbol, "end_line": clipped[symbol["id"]][1]}
        if symbol.get("id") in clipped
        else symbol
        for symbol in symbols
        if symbol.get("id") not in refused
    ]
    out_facts: list = []
    for fact in facts:
        # The module's id is what lane A gives a file-level C++ site, and
        # `rehome` reads it as the module speaking — so a fact freed here
        # is re-homed onto the minted definition covering it, if there is
        # one, and belongs to the module if there is not.
        module = refused.get(fact.scope)
        if module is None:
            moved = clipped.get(fact.scope)
            module = moved[0] if moved is not None and fact.line > moved[1] else None
        if module is None:
            out_facts.append(fact)
            continue
        out_facts.append(dataclasses.replace(fact, scope=module))
        counts["facts_rescoped"] += 1
    return out_symbols, out_facts, counts, frozenset(vacated)


def contradicted_fired(counts: Mapping) -> bool:
    """Whether :func:`contradicted` did anything at all — the condition its
    caller writes the graph block on, as ``operators`` and ``constructions``
    are written only where they have something to say."""
    extents = counts["extents"]
    return bool(
        any(counts["refused"].values())
        or extents["read"]
        or extents["kept"]
        or any(extents["refused"].values())
    )


def _contradiction(
    symbol: Mapping,
    resolved_to: Iterable[tuple[str, int]],
    rows_at: Mapping[tuple[str, int], list[Mapping]],
) -> str | None:
    """Which of :data:`CONTRADICTIONS` the index reads *symbol*'s own name
    token as, or ``None``.

    A reference at that token resolving to a ``macro`` definition, or to a
    ``term`` — a data member — **spelled as the symbol is**: the first is
    an annotation macro the parse took for the declarator, the second a
    member initialiser it took for one. Anything else leaves the symbol as
    it is: no reference at the token at all, a reference to a ``method`` or
    a ``type`` row (the index agreeing with lane A), a ``def_file`` the
    rows do not cover, a ``term`` of another name (a field a rightly named
    function shares a line with), or a moniker this module cannot spell.
    """
    found = None
    for where in sorted(resolved_to):
        for row in rows_at.get(where, ()):
            if row.get("kind") == "macro":
                return "macro"
            if row.get("kind") == "term" and _terminal_name(row) == symbol["name"]:
                found = "term"
    return found


def _at_outer_scope(row: Mapping) -> bool:
    """Is *row* a function definition the index places at file or class
    scope — the shape whose presence inside a lane A extent says the parse
    swallowed it (ADR-135, R2)?

    :func:`mint`'s ``local-to-function`` question, asked of a row rather
    than of a mint: a moniker whose chain holds a ``method`` before its
    last describes a lambda's or a local class's method, which is inside a
    body by right (C-9) and contradicts nothing.
    """
    if row.get("kind") != "method":
        return False
    chain = read_moniker(row.get("moniker") or "")
    return chain is not None and not any(suffix == "method" for _, suffix in chain[:-1])


def _terminal_name(row: Mapping) -> str | None:
    """The last descriptor's name in *row*'s moniker, or ``None`` where it
    is not one :func:`read_moniker` can spell."""
    chain = read_moniker(row.get("moniker") or "")
    return chain[-1][0] if chain else None


def rehome(
    facts: Sequence,
    minted_symbols: Sequence[Mapping],
    symbols: Iterable[Mapping],
    module_of_path: Mapping[str, str],
) -> tuple[list, int]:
    """The facts, with each one written inside a minted body drawn from it
    (ADR-134 §3), and how many moved.

    :func:`hobbes.extract.scipsource.project` reads a fact's caller as
    ``fact.scope or index.enclosing(module, line) or module``, so a fact
    with **no scope** re-homes by itself the moment ``end_line`` is real —
    ``enclosing`` takes the innermost symbol holding the line, and the
    minted one now holds it. This is the other half: a fact whose scope
    names a symbol that starts *before* the extent — the module-scope
    definition lane A's recovery gave it, or the class above — belongs to
    the definition it is written in. A scope starting at or inside the
    extent is left alone, and so is a scope naming nothing this graph
    knows: drawing less where the answer is not certain.

    The scopeless facts are not touched and **are** counted, once for each
    one ``enclosing`` will now answer with the minted symbol — that is,
    where no symbol of the module starting after the extent holds the line
    too. The count is what moved in the graph, not what this function
    rewrote.

    **A scope that is the module's own id is the module speaking**, not a
    symbol: lane A's C and C++ sites at file scope carry it, and since it
    is truthy the projection never reaches ``enclosing`` for them. They
    are the rule's main case — args' first check through the real ingest
    moved 2 rows of 16 until this was read — and they take the extent on
    the same condition as a scopeless fact.

    Only ``calls`` and ``uses``: an ``implements`` fact's ends are both
    definitions, read by ``starting_at`` and not by a scope. Only a symbol
    whose extent **was read** (``extent: "braces"``) takes facts — a body
    of one line too, since ``int f() { return g(); }`` holds a call whose
    module-scoped site would otherwise stay the module's (56 rows on fmt).
    A refused symbol takes none, its own line included: ``end_line ==
    line`` alone cannot tell the two apart, which is why the mint marks
    the read.
    Pure: it reads no file and writes no symbol.
    """
    extents: dict[str, list[tuple[int, int, str]]] = {}
    for symbol in minted_symbols:
        if symbol["kind"] in _DEFINITION_KINDS and symbol.get("extent") == EXTENT_BRACES:
            extents.setdefault(symbol["module"], []).append(
                (symbol["line"], symbol["end_line"], symbol["id"])
            )
    if not extents:
        return list(facts), 0
    for rows in extents.values():
        rows.sort()

    # Every symbol the graph holds, twice over: where a scope starts, and
    # what each module's lines are spoken for by. *symbols* may already hold
    # the minted ones — the caller merges them before the projection — so
    # the id map settles a duplicate and the ranges do not mind one. Both
    # are read once per fact, so each carries its own list of starts to
    # bisect rather than a scan over the module.
    starts: dict[str, tuple[str, int]] = {}
    ranges: dict[str, list[tuple[int, int]]] = {}
    for symbol in [*symbols, *minted_symbols]:
        module = symbol.get("module")
        if module is None:
            continue  # a module node, not a symbol
        starts[symbol["id"]] = (module, symbol["line"])
        ranges.setdefault(module, []).append(
            (symbol["line"], symbol.get("end_line") or symbol["line"])
        )
    for rows in ranges.values():
        rows.sort()
    at_extent = {module: [row[0] for row in rows] for module, rows in extents.items()}
    at_symbol = {module: [row[0] for row in rows] for module, rows in ranges.items()}

    out: list = []
    moved = 0
    for fact in facts:
        module = (
            module_of_path.get(fact.source_file) if fact.kind in ("calls", "uses") else None
        )
        holder = (
            _holding(extents.get(module), at_extent.get(module), fact.line)
            if module
            else None
        )
        if holder is None:
            out.append(fact)
            continue
        start, _, symbol_id = holder
        if not fact.scope or fact.scope == module:
            # The caller is the module, said one of two ways: the join's
            # own facts carry no scope and `enclosing` answers for them,
            # while a lane A site at file scope carries **the module's id**
            # (`cppsource`, `csource`) — truthy, so `project` never asks
            # `enclosing` and the fact would stay the module's for ever.
            # Both mean the same thing here, and both go to this extent
            # unless something starting inside it holds the line too (a
            # local type lane A did parse): that one is the caller already
            # for a scopeless fact, and the nearer truth for a scoped one.
            lines = at_symbol.get(module, [])
            inside = ranges[module][
                bisect_right(lines, start) : bisect_right(lines, fact.line)
            ]
            if any(fact.line <= end for _, end in inside):
                out.append(fact)
                continue
            moved += 1
            out.append(dataclasses.replace(fact, scope=symbol_id) if fact.scope else fact)
            continue
        scope = starts.get(fact.scope)
        if scope is None or scope[0] != module or scope[1] >= start:
            out.append(fact)
            continue
        out.append(dataclasses.replace(fact, scope=symbol_id))
        moved += 1
    return out, moved


def _holding(
    rows: Sequence[tuple[int, int, str]] | None,
    at: Sequence[int] | None,
    line: int,
) -> tuple[int, int, str] | None:
    """The extent holding *line*, or ``None``. A module's extents are
    disjoint — ``holds-a-definition`` refuses one that starts inside
    another — so the last one starting at or before the line is the only
    candidate there is."""
    if not rows:
        return None
    index = bisect_right(at, line) - 1
    if index < 0:
        return None
    return rows[index] if line <= rows[index][1] else None


def _read_extents(
    repo_root: Path,
    minted_symbols: Sequence[dict],
    minted_files: Sequence[str],
    symbols: Sequence[Mapping],
    sources: dict[str, list[str] | None],
    blanked: dict[str, list[str] | None],
) -> dict:
    """Move each minted function's ``end_line`` onto its body's closing
    brace (ADR-134 §1), and the counts that says what happened.

    Two passes, because ``holds-a-definition`` asks about the other minted
    symbols: every extent is matched first, then each is refused where a
    function or method of the same module — lane A's or minted — starts
    inside it. The second pass reads the first's answers and not its
    refusals, so a row's fate never depends on the order they are read in:
    two macro-generated rows whose matches both run into a written-out
    body are both refused, and what survives is disjoint.
    """
    refused = dict.fromkeys(EXTENT_REFUSALS, 0)
    matched: list[tuple[int, int]] = []
    for index, symbol in enumerate(minted_symbols):
        if symbol["kind"] not in _DEFINITION_KINDS:
            continue  # a type stays a line, and is counted nowhere here
        lines = _blanked_lines(repo_root, minted_files[index], sources, blanked)
        if lines is None:
            refused["no-body"] += 1  # a file that will not read shows no body
            continue
        end, reason = _extent(lines, symbol["line"])
        if end is None:
            refused[reason] += 1
        else:
            matched.append((index, end))

    starts: dict[str, set[int]] = {}
    for symbol in [*symbols, *minted_symbols]:
        module = symbol.get("module")
        if module is not None and symbol.get("kind") in _DEFINITION_KINDS:
            starts.setdefault(module, set()).add(symbol["line"])

    read = 0
    for index, end in matched:
        symbol = minted_symbols[index]
        line = symbol["line"]
        if any(line < at <= end for at in starts.get(symbol["module"], ())):
            refused["holds-a-definition"] += 1
            continue
        symbol["end_line"] = end
        # Said on the symbol, because `end_line == line` is both a body of
        # one line and a refusal, and `rehome` and `who_calls` each need to
        # know which.
        symbol["extent"] = EXTENT_BRACES
        read += 1
    return {"read": read, "refused": refused}


def _extent(lines: Sequence[str], line: int) -> tuple[int | None, str]:
    """Where the definition at *line* closes, or ``(None, reason)``.

    *lines* are the file's own, comments and literals blanked, so a brace
    inside either is text rather than structure. From the definition's line:
    the first ``{`` at parenthesis depth 0 — a ``;`` before it, or no brace
    at all, is ``no-body`` — matched to its ``}`` by brace depth. Nothing is
    parsed, for the reason nothing is parsed anywhere in this module: these
    are the definitions the grammar could not read.
    """
    depth = 0
    braces = 0
    opened = None
    for index in range(max(line - 1, 0), len(lines)):
        for char in lines[index]:
            if opened is None:
                if char in "([":
                    depth += 1
                elif char in ")]":
                    depth -= 1
                elif depth == 0:
                    if char == "{":
                        opened, braces = index, 1
                    elif char == ";":
                        return None, "no-body"
            elif char == "{":
                braces += 1
            elif char == "}":
                braces -= 1
                if braces == 0:
                    # Either branch of an `#if` may hold the brace the
                    # compiler saw, so a conditional anywhere between the
                    # braces makes this match a guess.
                    for source in lines[opened : index + 1]:
                        if _CONDITIONAL.match(source):
                            return None, "conditional-inside"
                    return index + 1, ""
    return (None, "runs-off") if opened is not None else (None, "no-body")


def constructor_lines(definitions: Iterable[Mapping]) -> frozenset[tuple[str, int]]:
    """The ``(file, line)`` of every definition row that is a constructor's
    — ADR-132's second half, and the whole of what tells a construction's
    reference apart from a type's.

    A constructor's moniker ends in the same name twice, a type then a
    method of it (``…/T#T(hash).``), which is scip-clang's spelling and no
    other entity's: a destructor is ``~T``, an operator is spelled as
    written, and a free function has no type before it. A moniker
    :func:`read_moniker` refuses names nothing here can stand behind.

    A line carrying **more than one distinct moniker** is left out, for
    :func:`mint`'s ``several-monikers`` reason: which definition the
    reference lands on would be a guess, and a wrong one here draws a call
    that is not there.
    """
    monikers_at: dict[tuple[str, int], set[str]] = {}
    for row in definitions:
        monikers_at.setdefault((row["file"], row["line"]), set()).add(
            row.get("moniker") or ""
        )
    out: set[tuple[str, int]] = set()
    for where, monikers in monikers_at.items():
        if len(monikers) > 1:
            continue
        chain = read_moniker(next(iter(monikers)))
        if chain is None or len(chain) < 2:
            continue
        (owner, owner_kind), (name, name_kind) = chain[-2], chain[-1]
        if owner_kind == "type" and name_kind == "method" and owner == name:
            out.add(where)
    return frozenset(out)


def read_moniker(moniker: str) -> list[tuple[str, str]] | None:
    """A SCIP moniker's descriptor chain as ``(name, kind)`` pairs, or
    ``None`` when it is not one this module can spell.

    ``cxx . . $ fmt/v12/detail/write(9f…).`` reads as ``fmt`` (namespace),
    ``v12``, ``detail``, ``write`` (method); ``cxx . . $
    testing/internal/FilePath#`` ends in a type. The package part — the
    scheme, the manager, the package name and its version — is dropped,
    a method's disambiguator with it, and a backtick-escaped name is
    unescaped (```src.a`/Engine#`` is ``src.a`` then ``Engine``).

    The grammar is ``scip/index.mjs``'s (``classify``, ``terminalName``),
    read there so the two agree: anything it would call ``local``,
    ``malformed`` or a parameter descriptor is refused here rather than
    named by a guess.
    """
    if not moniker or moniker.startswith("local "):
        return None
    parts = moniker.split(" ")
    if len(parts) < 5:
        return None
    chain = " ".join(parts[4:])
    descriptors: list[tuple[str, str]] = []
    i = 0
    while i < len(chain):
        if chain[i] == "`":
            name, i = _escaped_name(chain, i)
            if name is None:
                return None
        else:
            start = i
            while i < len(chain) and chain[i] not in _NAME_END:
                i += 1
            name = chain[start:i]
        if not name or i >= len(chain):
            return None
        if chain[i] == "(":
            # `foo(<disambiguator>).` — scip-clang's signature hash, or
            # scip-java's overload counter. A `(name)` parameter
            # descriptor has no name in front of it and never reaches here.
            close = chain.find(")", i)
            if close < 0 or chain[close + 1 : close + 2] != ".":
                return None
            if not all(char.isalnum() or char in "_+" for char in chain[i + 1 : close]):
                return None
            descriptors.append((name, "method"))
            i = close + 2
            continue
        suffix = _SUFFIXES.get(chain[i])
        if suffix is None:
            return None
        descriptors.append((name, suffix))
        i += 1
    return descriptors or None


def _escaped_name(chain: str, i: int) -> tuple[str | None, int]:
    """The backtick-escaped name starting at *i*, and where it ends. SCIP
    doubles an interior backtick; an unterminated name is no name."""
    out: list[str] = []
    i += 1
    while i < len(chain):
        if chain[i] != "`":
            out.append(chain[i])
            i += 1
            continue
        if chain[i + 1 : i + 2] == "`":
            out.append("`")
            i += 2
            continue
        return "".join(out), i + 1
    return None, i


def shows_body(
    repo_root: Path, file: str, line: int, sources: dict[str, list[str] | None]
) -> bool:
    """Does the file's own text show a body at *line* (ADR-129 §1, rule 6)?

    A token read, as :func:`hobbes.extract.cppsource._lost_template_header`
    reads a ``template <>`` header the parse lost: from the definition
    line, at most :data:`BODY_WINDOW` lines on and with ``//`` comments
    dropped, a ``{`` met at bracket depth 0 is a body and a ``;`` met
    first is not. Nothing is parsed here — the shapes this has to tell
    apart are exactly the ones the grammar could not read.

    The depth is over ``(``/``[`` so a ``;`` inside a parameter list
    (``void f(int a = g(1, 2)) {``) does not end the read, and a ``{`` in
    a default argument does not start a body. A file that will not read
    shows no body: minting less, never more.

    *sources* caches each file's lines across a run; a file holds many
    rows and the read is the only impure thing here.
    """
    lines = _lines(repo_root, file, sources)
    if lines is None:
        return False
    depth = 0
    for source in lines[max(line - 1, 0) : max(line - 1, 0) + BODY_WINDOW]:
        for char in source.split("//", 1)[0]:
            if char in "([":
                depth += 1
            elif char in ")]":
                depth -= 1
            elif depth == 0:
                if char == "{":
                    return True
                if char == ";":
                    return False
    return False


def _lines(
    repo_root: Path, file: str, sources: dict[str, list[str] | None]
) -> list[str] | None:
    """The file's own lines, read once per run, or ``None`` where it will
    not read. Shared by this module's two token reads."""
    lines = sources.get(file, _UNREAD)
    if lines is _UNREAD:
        try:
            text = (Path(repo_root) / file).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = None
        lines = text.splitlines() if text is not None else None
        sources[file] = lines
    return lines  # type: ignore[return-value]


def _blanked_lines(
    repo_root: Path,
    file: str,
    sources: dict[str, list[str] | None],
    blanked: dict[str, list[str] | None],
) -> list[str] | None:
    """The file's lines with :func:`_blank_source` over them, read and
    blanked once per file per run — the extent read asks for a whole file
    and a file holds many rows. ``None`` where the file will not read."""
    lines = blanked.get(file, _UNREAD)
    if lines is _UNREAD:
        source = _lines(repo_root, file, sources)
        lines = None if source is None else _blank_source("\n".join(source)).split("\n")
        blanked[file] = lines
    return lines  # type: ignore[return-value]


def _blank_source(text: str) -> str:
    """*text* with every comment, string, raw string and character literal
    blanked to spaces — the length and the newlines kept, so a line still
    numbers as it did.

    :func:`_blank_literals`' question over a whole file rather than a
    window, and two more shapes with it, because a brace match reads far
    enough to meet them: a ``//`` or ``/* */`` comment, and a raw string
    (``R"x(})x"``), whose delimiter is what closes it and whose backslash
    escapes nothing. A ``'`` between two alphanumerics is C++14's digit
    separator (``1'000``), not a literal. An unterminated literal blanks to
    the end of the file, which reads as no body: blanking more here refuses
    an extent, and refusing is this rule's failure direction.
    """
    out = list(text)
    end = len(text)

    def blank(start: int, stop: int) -> None:
        for at in range(start, min(stop, end)):
            if out[at] != "\n":
                out[at] = " "

    i = 0
    while i < end:
        char = text[i]
        if char == "/" and text[i + 1 : i + 2] in ("/", "*"):
            closer = "\n" if text[i + 1] == "/" else "*/"
            at = text.find(closer, i + 2)
            stop = end if at < 0 else at + (0 if closer == "\n" else 2)
            blank(i, stop)
            i = stop
            continue
        if char == '"' and text[i - 1 : i] == "R":
            # `R"delim(` … `)delim"`: the delimiter is the only thing that
            # closes it. No delimiter, or no close, and the rest of the file
            # is inside the literal as far as this read is concerned.
            at = text.find("(", i + 1)
            if at < 0:
                blank(i, end)
                break
            closer = ")" + text[i + 1 : at] + '"'
            close = text.find(closer, at + 1)
            if close < 0:
                blank(i + 1, end)
                break
            blank(i + 1, close + len(closer) - 1)
            i = close + len(closer)
            continue
        if char in "\"'":
            if char == "'" and _digit_separator(text, i):
                i += 1  # part of a number, and a number is not a literal
                continue
            at = i + 1
            while at < end:
                if text[at] == "\\":
                    at += 2
                    continue
                if text[at] == char:
                    break
                at += 1
            blank(i + 1, at)
            i = min(at + 1, end)
            continue
        i += 1
    return "".join(out)


def _digit_separator(text: str, i: int) -> bool:
    """Is the ``'`` at *i* C++14's digit separator (``1'000``, ``0xFF'FF``)
    rather than a character literal?

    It is, where it sits between two alphanumerics **and** the token it
    continues starts with a digit. The second half is what tells a number
    from a wide literal: ``L'a'`` and ``u8'x'`` are literals whose ``'``
    also follows an alphanumeric, and reading one as a number would leave
    its closing quote to open a literal that blanks whatever follows —
    including a brace, which is the one direction this read must not fail
    in.
    """
    if not text[i + 1 : i + 2].isalnum():
        return False
    start = i
    while start and (text[start - 1].isalnum() or text[start - 1] in "_'"):
        start -= 1
    return start < i and text[start].isdigit()


#: An ALL_CAPS identifier directly followed by ``(`` inside a parameter
#: list is a macro, and what it expands to is not in this file's tokens.
_MACRO_CALL = re.compile(r"(?<![A-Za-z0-9_])[A-Z][A-Z0-9_]*\(")


def read_max_params(
    repo_root: Path,
    file: str,
    line: int,
    name: str,
    sources: dict[str, list[str] | None],
) -> int | None:
    """How many parameters the definition at *line* spells (ADR-130), or
    ``None`` where the read is not clean.

    :func:`shows_body`'s read, one question over: from the definition
    line, at most :data:`BODY_WINDOW` lines on and with ``//`` comments
    dropped, the first parenthesised list after the terminal *name* at
    bracket depth 0, split on depth-0 commas. ``()`` and ``(void)`` are 0.
    String and character literals are blanked first, so a comma or a
    bracket inside one is text rather than structure.

    ``None`` — unknown, and an unknown draws the edge — wherever the read
    is not one this module can stand behind: no list found, an unbalanced
    bracket, a ``...`` (a C ellipsis or a parameter pack), an empty part
    between two commas, or a macro in the list, whose expansion is not
    here to count. Nothing is parsed: these are the definitions the
    grammar could not read, which is why they are minted at all.
    """
    lines = _lines(repo_root, file, sources)
    if lines is None:
        return None
    start = max(line - 1, 0)
    text = _blank_literals(
        " ".join(source.split("//", 1)[0] for source in lines[start : start + BODY_WINDOW])
    )
    found = re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text)
    if found is None:
        return None
    opened = _list_start(text, found.end())
    if opened < 0:
        return None
    inside = _list_body(text, opened)
    if inside is None or "..." in inside or _MACRO_CALL.search(inside):
        return None
    parts = _split_parameters(inside)
    if parts is None:
        return None
    if not parts or (len(parts) == 1 and parts[0] == "void"):
        return 0
    if any(not part for part in parts):
        return None  # a part between two commas that holds nothing
    return len(parts)


def _blank_literals(text: str) -> str:
    """*text* with every string and character literal's contents replaced
    by spaces, the length kept so indices still line up. An unterminated
    literal blanks to the end of the window, which reads as no list."""
    out: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char not in "\"'":
            out.append(char)
            i += 1
            continue
        quote, i = char, i + 1
        out.append(" ")
        while i < len(text):
            if text[i] == "\\" and i + 1 < len(text):
                out.append("  ")
                i += 2
                continue
            closed = text[i] == quote
            out.append(" " if not closed else quote)
            i += 1
            if closed:
                break
    return "".join(out)


def _list_start(text: str, at: int) -> int:
    """Where the first parenthesised list at bracket depth 0 opens after
    *at*, or -1: a ``<`` or ``[`` before it is a template argument list or
    an attribute, and a ``;`` or ``{`` reached first means there is no
    parameter list to read here."""
    depth = 0
    for i in range(at, len(text)):
        char = text[i]
        if char in "<[":
            depth += 1
        elif char in ">]":
            depth -= 1
            if depth < 0:
                return -1
        elif depth == 0:
            if char == "(":
                return i
            if char in ";{":
                return -1
    return -1


def _list_body(text: str, opened: int) -> str | None:
    """What the list opened at *opened* holds, or ``None`` when it does
    not close inside the window — including when what closes it is not a
    ``)``, which is a ``>`` written as a comparison rather than as a
    template bracket, and a read this module does not stand behind."""
    depth = 0
    for i in range(opened, len(text)):
        char = text[i]
        if char in "([{<":
            depth += 1
        elif char in ")]}>":
            depth -= 1
            if depth == 0:
                return text[opened + 1 : i] if char == ")" else None
            if depth < 0:
                return None
    return None


def _split_parameters(inside: str) -> list[str] | None:
    """The list's parts, split on its own commas — a comma inside a
    nested list (``map<int, int> m``, a default argument's call) belongs
    to that list. ``None`` on an unbalanced bracket."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in inside:
        if char in "([{<":
            depth += 1
        elif char in ")]}>":
            depth -= 1
            if depth < 0:
                return None
        elif char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if depth != 0:
        return None
    last = "".join(current).strip()
    if last or parts:
        parts.append(last)
    return parts


def _free_id(wanted: str, taken: set[str]) -> str:
    """*wanted*, or ``~b2``, ``~b3``, … when a lane A symbol or an earlier
    mint has it. No lane A id moves, and the suffix is deliberately not
    lane A's numeric one (``~2``, the C++ overload counter): a reader can
    tell which lane spelled an id apart from which overload it is, and
    :func:`hobbes.extract.cppsource._bare` reads ``~b2`` as part of the
    name rather than as a suffix to strip."""
    candidate = wanted
    n = 1
    while candidate in taken:
        n += 1
        candidate = f"{wanted}~b{n}"
    taken.add(candidate)
    return candidate
