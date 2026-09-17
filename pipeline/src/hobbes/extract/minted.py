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

**A minted symbol is a target, not a scope** — ``end_line`` is its line.
Finding a body's end through unexpanded macros is a guess this change
does not make, so a call written *inside* a lost definition keeps the
caller it has today (ADR-129 §3).

**When in doubt, mint nothing.** A naive rule — mint wherever lane B
defines and lane A does not — graded 98.2% on fmt with 123 contradicted
edges. Each refusal below removed measured wrong edges, and with all of
them the fmt export read 6,533 confirmed at **0 contradicted** (3,269
before), recall 14.5% → 29.1%; args, held out, added 67 edges, 67
confirmed. The refusals, with what the measurement said:

``clean-file``
    The file's lane A parse had no ERROR nodes. There a missing symbol is
    lane A's floor speaking by decision — a lambda, a local class (C-9) —
    not a loss. 1 fact of that shape on fmt.
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
    :data:`NEAR_LINES` of the row. That is the two lanes disagreeing
    about which line a definition is on, not a definition lane A lost —
    counted here and fixed as its own item. 20 on fmt.
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

**P6.** With no indexer there are no ``definitions`` rows, so nothing is
minted and the floor is exactly what it was; the caller writes no
``minted`` block into the graph either.
"""

from __future__ import annotations

import re
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
) -> tuple[list[dict], dict]:
    """The symbols lane B's ``definitions`` rows mint, and the counts.

    *definitions* are the rows of every C or C++ file lane A walked;
    *lossy_files* the repo-relative paths whose parse had ERROR nodes;
    *symbols* lane A's, as ``graph["symbols"]`` holds them; and
    *module_of_path* the graph's file-to-module map. Pure but for reading
    each file's own text, which is rule 6's whole evidence.

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
    files: set[str] = set()
    sources: dict[str, list[str] | None] = {}
    for file, line, moniker, kind in rows:
        module = module_of_path.get(file)
        if module is None:
            continue  # a file lane A never discovered; not ours to name
        if line in lane_a_lines.get(module, ()):
            continue  # the lanes meet here: the normal case, not a refusal
        if file not in lossy_files:
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
            # ADR-129 §3: a target, not a scope.
            "end_line": line,
            "declared_by": "scip",
        }
        if symbol_kind != "type":
            # ADR-130: what the definition's own parameter list can take,
            # read from its tokens. A type takes no arguments in this
            # sense — a construction's target is its constructor.
            symbol["max_params"] = read_max_params(repo_root, file, line, name, sources)
        minted.append(symbol)
        files.add(file)

    return minted, {"symbols": len(minted), "files": len(files), "refused": refused}


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
