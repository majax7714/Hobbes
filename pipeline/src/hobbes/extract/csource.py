"""Lane A for C: structure, symbols, and call *sites*.

The first unit of the C work (architecture §3.7 step 2), on the
`rustsource.py` / `javasource.py` contract — same bundle shape, same
division of labour, so the graph builder and the range join need no
C-specific code (P7).

**No lane B in this unit.** There is no C indexer yet (scip-clang and a
compile database are a later unit and need a design decision), so every
C edge is lane A's fallback, at ``syntactic`` tier: :func:`_call_fallback`
is the only resolver, and it is what :mod:`hobbes.extract` pools into
the join with an empty semantic side — the normal degraded path (P6),
not a special case.

**Discovery.** ``.c`` and ``.h`` files are C; a ``.h`` is always read as
C, never guessed at as C++. C++ (``.cc``/``.cpp``/``.cxx``/``.hpp``/
``.hh``) is out of scope and is never discovered. Pruned like every
other walk, plus ``build/`` and any ``cmake-build-*`` directory.

**Module ids** follow the ADR-021 rule with one wrinkle: a ``.c`` file's
id drops its extension (``src/util.c`` → ``src/util``), but a ``.h``
file **keeps** it (``src/util.h`` stays ``src/util.h``) — a ``foo.c``/
``foo.h`` pair sharing one directory is C's norm, and dropping both
extensions would collide their ids.

**Symbols come from definitions only**, never a prototype: a function
with a body is kind ``function`` (a ``static`` one is recorded as
file-local, C's own linkage rule); a ``struct``/``union``/``enum`` with
a body, and a ``typedef``, are kind ``type``; a function-like macro
(``#define F(x) ...``) is kind ``macro``. An object-like macro
(``#define X 1``) is never a symbol — nothing calls it.

**The universal header guard is transparent to the walk.** A
``linkage_specification`` (``extern "C" { ... }``) nests everything it
wraps one level deeper, same as a ``preproc_*`` conditional; the walk
recurses through it and its ``declaration_list`` body exactly as it
recurses through a header guard, so the ``#ifdef __cplusplus`` /
``extern "C" {`` idiom hides nothing from it (symbols, includes,
function-pointer bindings inside are all recorded). Tree-sitter cannot
balance that idiom's brace against the preprocessor conditional that
opens it, so a file using it parses with ``has_error`` set and draws
this layer's ordinary syntax-error record — a cosmetic flag, not a
missed declaration.

**Includes.** For ``#include "p"``, resolution tries, in order: relative
to the including file's directory; relative to the repo root; the
*unique* repo ``.h`` whose path ends with ``/p``. A step whose ``..``
would climb above the repo root is not a candidate for that step — it
returns no path rather than resolving into whatever the climb happens to
reach outside the tree, and the other steps still apply. An ambiguous or
unmatched include draws no edge. ``#include <p>`` tries the same three
rules first — a project routinely spells its own headers with ``<>``
under an ``-I`` — and only when none resolves does it become an
``imports`` edge to ``ext:<p>``. A resolved include, either form, is an
in-repo ``imports`` module edge with file:line.

**Call sites and their shapes.** A ``call_expression`` records a site at
its terminal identifier: a plain identifier is a plain call (a
function-like macro invocation parses identically — C's preprocessor
never runs here, so tree-sitter cannot tell the two apart, and neither
needs to); a ``field_expression`` (``s->fn(x)``, ``s.fn(x)``) is an
attribute call through a struct's field; a parenthesized dereference
(``(*fp)(x)``) is a call through a value. Calls inside a macro's body are
never walked — moot in practice, since a macro's replacement text is an
unparsed ``preproc_arg`` to begin with.

**The fallback** (:func:`_call_fallback`, the syntactic floor) resolves
only a plain call, and only by name, in this order: (1) a function or
function-like macro named ``f`` defined in the same file; (2) a
function-like macro named ``f`` defined in a header this file directly
includes (one level); (3) the unique non-``static`` function named
``f`` defined anywhere in the repo — external linkage is one namespace.
Two candidates at the same rank means abstaining, never picking, and
the walk does not fall through to the next rank when a rank is
ambiguous — rank 1 included: two or more same-file definitions of ``f``
(a function and a function-like macro count together, the common shape
being a ``#ifdef``/``#else`` preprocessor alternative) is a same-file
tie, and abstains rather than picking whichever definition happened to
parse last. A name bound as a parameter or local variable in the
enclosing function (the shape a function pointer takes) is never
resolved, even when it shadows a real global of the same name. Field
and dereference calls are never resolved by any rank.

**One symbol per id.** When a file defines the same name twice at the
same kind-of-thing (again, typically ``#ifdef``/``#else`` arms), the
layer keeps only the first definition in file order as that id's one
symbol and records the rest in one ``errors`` entry per file (stage
``"parse"``) naming the duplicated names — never two rows sharing one
id, and never a fallback target naming a definition the layer already
dropped (the rank-1 tie above abstains on exactly this case, so no
fallback ever points at it in the first place).

**Tests.** A test is a function named ``test_*``, defined in a file
under a directory named ``test``/``tests``, or in a file named
``test_*.c``/``*_test.c``. The framework string is ``"c-convention"``;
reach is the closure over ``calls`` edges, as for every language.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import tree_sitter_c
from tree_sitter import Language, Node, Parser

from hobbes.extract.discover import SKIPPED_DIR_NAMES, is_linked_copy
from hobbes.extract.graph import _edge_list

_PARSER = Parser(Language(tree_sitter_c.language()))

#: Directories pruned in addition to the shared set: generic build
#: output, and CMake's own out-of-tree build directories (``cmake-build-*``,
#: pruned by prefix rather than an exact name below).
_C_SKIPPED = SKIPPED_DIR_NAMES | {"build"}

#: Preprocessor conditional wrappers whose contents are transparent to
#: the top-level walk — a header guard (``#ifndef``/``#define``/…/
#: ``#endif``) nests every declaration it wraps one level deeper in the
#: tree, and a walk that only looked at ``translation_unit``'s direct
#: children would see nothing inside a guarded header at all.
_PREPROC_CONTAINERS = {"preproc_ifdef", "preproc_if", "preproc_elif", "preproc_else"}


@dataclass
class CFile:
    """One parsed ``.c``/``.h`` file, in the shape the join consumes."""

    path: str
    includes: list[dict] = field(default_factory=list)
    symbols: list[dict] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    tests: list[dict] = field(default_factory=list)
    #: ``(name, start, end)`` — a parameter or local variable bound to a
    #: function-pointer type, with its enclosing function's line extent.
    #: Never resolved by the fallback (decision 6), and fed to the tail
    #: as this language's ``local_bindings`` so a call through one
    #: classifies `local-binding` rather than `unclassified`.
    local_bindings: list[tuple[str, int, int]] = field(default_factory=list)
    #: Qualnames defined more than once in this file (decision 3) — the
    #: kept symbol is the first in file order; the fallback's rank 1
    #: (decision 6) abstains on any of these rather than picking it.
    duplicate_names: set[str] = field(default_factory=set)


def has_c_files(repo_root: Path) -> bool:
    """Cheap detection: does this repo contain C at all?"""
    return any(True for _ in iter_c_files(Path(repo_root)))


def iter_c_files(repo_root: Path):
    """Repo-relative ``.c``/``.h`` paths, pruned like every other walk."""
    stack = [Path(repo_root)]
    while stack:
        directory = stack.pop()
        try:
            children = sorted(directory.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_dir():
                if (
                    child.name not in _C_SKIPPED
                    and not child.name.startswith(".")
                    and not child.name.startswith("cmake-build-")
                    and not is_linked_copy(child, repo_root)
                ):
                    stack.append(child)
            elif child.suffix in (".c", ".h"):
                yield child


def module_id(path: str) -> str:
    """The ADR-021 id rule, with C's own wrinkle: a ``.c`` file's id drops
    the extension; a ``.h`` file's id keeps it, so a ``foo.c``/``foo.h``
    pair in one directory never collides."""
    pure = PurePosixPath(path)
    if pure.suffix == ".c":
        return str(pure.with_suffix(""))
    return str(pure)


def extract_c(repo_root: Path) -> dict | None:
    """The C layer for *repo_root*, or ``None`` when it has no C.

    Never raises: a file that will not read or will not parse yields
    whatever the walk could see, and one degradation record names it
    (decision 10) — tree-sitter is error-tolerant by design (§3.1), and
    the layer must never take an ingest down.
    """
    repo_root = Path(repo_root).resolve()
    files: list[CFile] = []
    errors: list[dict] = []
    for absolute in iter_c_files(repo_root):
        rel = absolute.relative_to(repo_root).as_posix()
        try:
            source = absolute.read_bytes()
        except OSError as exc:
            errors.append(
                {"path": rel, "stage": "discover", "message": f"could not read {rel}: {exc}"}
            )
            continue
        parsed, had_error, duplicated = _parse_file(rel, source)
        files.append(parsed)
        if had_error:
            errors.append(
                {
                    "path": rel,
                    "stage": "parse",
                    "message": (
                        f"{rel} parsed with syntax errors (tree-sitter ERROR nodes); "
                        "the sites it could still see are kept"
                    ),
                }
            )
        if duplicated:
            errors.append(
                {
                    "path": rel,
                    "stage": "parse",
                    "message": (
                        f"{', '.join(duplicated)} defined more than once in {rel} "
                        "(preprocessor alternatives); calls to them are left "
                        "unresolved rather than guessed"
                    ),
                }
            )
    if not files:
        return None
    bundle = _join(files)
    bundle["errors"] = errors
    return bundle


# ---------------------------------------------------------------- parsing


def _text(node: Node) -> str:
    return (node.text or b"").decode("utf-8", "replace")


def _parse_file(rel: str, source: bytes) -> tuple[CFile, bool, list[str]]:
    tree = _PARSER.parse(source)
    root = tree.root_node
    parsed = CFile(path=rel)
    _walk_top_level(root, parsed)
    duplicated = _dedupe_symbols(parsed)

    for symbol in parsed.symbols:
        if symbol["kind"] == "function" and symbol["name"].startswith("test_") and _is_test_file(rel):
            parsed.tests.append(
                {
                    "id": f"{rel}::{symbol['name']}",
                    "name": symbol["name"],
                    "file": rel,
                    "line": symbol["line"],
                    "framework": "c-convention",
                }
            )

    parsed.calls = _calls(root, parsed.symbols)
    return parsed, root.has_error, duplicated


def _dedupe_symbols(parsed: CFile) -> list[str]:
    """Decision 3: one symbol per id, the first definition in file order.

    A same-file preprocessor alternative (``#ifdef``/``#else`` arms
    defining the same name twice) would otherwise leave two rows sharing
    one id; this keeps the first and returns the names that had more
    than one definition, so the caller can register one ``errors``
    record per file.
    """
    counts: dict[str, int] = defaultdict(int)
    for symbol in parsed.symbols:
        counts[symbol["qualname"]] += 1
    kept: list[dict] = []
    first_seen: set[str] = set()
    for symbol in parsed.symbols:
        name = symbol["qualname"]
        if counts[name] > 1:
            if name in first_seen:
                continue
            first_seen.add(name)
        kept.append(symbol)
    parsed.symbols = kept
    duplicated = sorted(name for name, count in counts.items() if count > 1)
    parsed.duplicate_names = set(duplicated)
    return duplicated


def _is_test_file(path: str) -> bool:
    """Rule 7: a directory named ``test``/``tests``, or a ``test_*.c``/
    ``*_test.c`` file name."""
    pure = PurePosixPath(path)
    if any(part in ("test", "tests") for part in pure.parent.parts):
        return True
    name = pure.name
    return name.endswith(".c") and (name.startswith("test_") or name.endswith("_test.c"))


def _walk_top_level(node: Node, parsed: CFile) -> None:
    """Top-level declarations, recursing transparently through header
    guards (``#ifndef``/``#if`` and their ``#elif``/``#else`` arms) and
    through a ``linkage_specification`` (``extern "C" { ... }``) — the
    universal ``#ifdef __cplusplus`` idiom nests a whole header's worth
    of declarations one level deeper still, in that node's
    ``declaration_list`` body, and would otherwise hide all of it from a
    walk that only looked at ``translation_unit``'s direct children."""
    for child in node.children:
        if child.type in _PREPROC_CONTAINERS:
            _walk_top_level(child, parsed)
        elif child.type == "linkage_specification":
            body = child.child_by_field_name("body")
            if body is None:
                continue
            if body.type == "declaration_list":
                _walk_top_level(body, parsed)
            else:
                _top_level(body, parsed)  # a brace-less `extern "C" decl;`
        else:
            _top_level(child, parsed)


def _top_level(node: Node, parsed: CFile) -> None:
    if node.type == "preproc_include":
        entry = _include_entry(node)
        if entry is not None:
            parsed.includes.append(entry)
    elif node.type == "preproc_function_def":
        name = node.child_by_field_name("name")
        if name is not None:
            parsed.symbols.append(_symbol(_text(name), "macro", name, node))
    elif node.type == "function_definition":
        body = node.child_by_field_name("body")
        declarator = node.child_by_field_name("declarator")
        ident = _declarator_identifier(declarator)
        if body is None or ident is None:
            return
        is_static = any(
            c.type == "storage_class_specifier" and _text(c) == "static" for c in node.children
        )
        parsed.symbols.append(_symbol(_text(ident), "function", ident, node) | {"static": is_static})
        _collect_bindings(node, declarator, parsed)
    elif node.type == "type_definition":
        declarator = node.child_by_field_name("declarator")
        ident = _type_identifier(declarator) if declarator is not None else None
        if ident is not None:
            parsed.symbols.append(_symbol(_text(ident), "type", ident, node))
    elif node.type in ("struct_specifier", "union_specifier", "enum_specifier"):
        if node.child_by_field_name("body") is not None:
            tag = node.child_by_field_name("name")
            if tag is not None:
                parsed.symbols.append(_symbol(_text(tag), "type", tag, node))
    # `preproc_def` (an object-like macro) and a bare `declaration` (a
    # prototype, or a plain variable) are never symbols — decision 3.


def _symbol(name: str, kind: str, ident: Node, extent: Node) -> dict:
    """C has no nesting, so ``qualname`` is always the bare *name*; *ident*
    gives the identifying line, *extent* the symbol's full span (used to
    scope the calls inside a function's body)."""
    return {
        "name": name,
        "qualname": name,
        "kind": kind,
        "line": ident.start_point.row + 1,
        "end_line": extent.end_point.row + 1,
    }


def _include_entry(node: Node) -> dict | None:
    path_node = node.child_by_field_name("path")
    if path_node is None:
        return None
    line = node.start_point.row + 1
    if path_node.type == "system_lib_string":
        return {"spec": _text(path_node).strip("<>"), "angle": True, "line": line}
    if path_node.type == "string_literal":
        content = _child_of_type(path_node, "string_content")
        spec = _text(content) if content is not None else _text(path_node).strip('"')
        return {"spec": spec, "angle": False, "line": line}
    return None


def _child_of_type(node: Node, child_type: str) -> Node | None:
    for child in node.children:
        if child.type == child_type:
            return child
    return None


def _sole_named_child(node: Node) -> Node | None:
    named = [c for c in node.children if c.is_named]
    return named[0] if named else None


def _declarator_identifier(node: Node | None) -> Node | None:
    """Unwrap a declarator chain — pointer, array, function, and the
    parens a function-pointer declarator requires — down to the bound
    ``identifier``."""
    while node is not None and node.type != "identifier":
        if node.type in ("function_declarator", "pointer_declarator", "array_declarator"):
            node = node.child_by_field_name("declarator")
        elif node.type in ("parenthesized_declarator", "init_declarator"):
            node = node.child_by_field_name("declarator") or _sole_named_child(node)
        else:
            return None
    return node


def _type_identifier(declarator: Node) -> Node | None:
    """A ``typedef``'s alias name — ordinarily the declarator itself
    (``type_identifier``), or nested inside one for a function-pointer
    typedef (``typedef int (*Callback)(int);``)."""
    if declarator.type == "type_identifier":
        return declarator
    for child in _walk(declarator):
        if child.type == "type_identifier":
            return child
    return None


def _function_declarator_of(declarator: Node | None) -> Node | None:
    """The ``function_declarator`` a function definition's own declarator
    wraps — direct for an ordinary function, one level under a
    pointer/array declarator when the function returns one."""
    node = declarator
    while node is not None and node.type != "function_declarator":
        if node.type in ("pointer_declarator", "array_declarator"):
            node = node.child_by_field_name("declarator")
        else:
            return None
    return node


def _function_pointer_binding(node: Node) -> str | None:
    """The bound name if *node* (a ``parameter_declaration`` or a
    ``declaration``) declares a function pointer — ``int (*fp)(int)`` —
    else ``None``. An initialized local wraps its declarator in
    ``init_declarator`` first; a parameter never does."""
    declarator = node.child_by_field_name("declarator")
    if declarator is not None and declarator.type == "init_declarator":
        declarator = declarator.child_by_field_name("declarator")
    if declarator is None or declarator.type != "function_declarator":
        return None
    inner = declarator.child_by_field_name("declarator")
    if inner is None or inner.type != "parenthesized_declarator":
        return None
    pointer = _sole_named_child(inner)
    if pointer is None or pointer.type != "pointer_declarator":
        return None
    ident = pointer.child_by_field_name("declarator")
    return _text(ident) if ident is not None and ident.type == "identifier" else None


def _collect_bindings(func_node: Node, declarator: Node, parsed: CFile) -> None:
    """Function-pointer parameters and locals of *func_node*, with its own
    line extent — decision 6's binding, and the tail's `local-binding`."""
    start = func_node.start_point.row + 1
    end = func_node.end_point.row + 1
    function_declarator = _function_declarator_of(declarator)
    if function_declarator is not None:
        params = function_declarator.child_by_field_name("parameters")
        if params is not None:
            for param in params.children:
                if param.type != "parameter_declaration":
                    continue
                name = _function_pointer_binding(param)
                if name:
                    parsed.local_bindings.append((name, start, end))
    body = func_node.child_by_field_name("body")
    if body is not None:
        for node in _walk(body):
            if node.type == "declaration":
                name = _function_pointer_binding(node)
                if name:
                    parsed.local_bindings.append((name, start, end))


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _enclosing(symbols: list[dict], line: int) -> str | None:
    """The function containing *line*, if any — the only kind whose body
    can hold a call."""
    best = None
    for symbol in symbols:
        if symbol["kind"] == "function" and symbol["line"] <= line <= symbol["end_line"]:
            best = symbol["qualname"]
    return best


def _callee_shape(function: Node) -> tuple[str, Node | None]:
    """``(shape, terminal identifier)`` for a call's callee — ``plain``,
    ``field`` (``s->fn(x)`` / ``s.fn(x)``, an attribute call through a
    struct), or ``deref`` (``(*fp)(x)``, a call through a value). Anything
    else records no site: there is no terminal identifier to put it on.
    """
    if function.type == "identifier":
        return "plain", function
    if function.type == "field_expression":
        field_node = function.child_by_field_name("field")
        return "field", field_node if field_node is not None and field_node.type == "field_identifier" else None
    if function.type == "parenthesized_expression":
        inner = _sole_named_child(function)
        if inner is not None and inner.type == "pointer_expression":
            operator = inner.child_by_field_name("operator")
            argument = inner.child_by_field_name("argument")
            if (
                operator is not None
                and _text(operator) == "*"
                and argument is not None
                and argument.type == "identifier"
            ):
                return "deref", argument
    return "other", None


def _calls(root: Node, symbols: list[dict]) -> list[dict]:
    """Every call site — decision 5's three callee shapes. Position is the
    terminal identifier's, so the (never-run, in this unit) semantic join
    would key on where the name is, same as every other language."""
    found: list[dict] = []
    for node in _walk(root):
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        if function is None:
            continue
        shape, terminal = _callee_shape(function)
        if terminal is None:
            continue
        found.append(
            {
                "name": _text(terminal),
                "shape": shape,
                "line": terminal.start_point.row + 1,
                "col": terminal.start_point.column,
                "scope": _enclosing(symbols, node.start_point.row + 1),
            }
        )
    return found


# ---------------------------------------------------------------- joining


def _normalize(base: PurePosixPath, spec: str) -> str | None:
    """``base / spec``, collapsing ``.``/``..`` without touching the
    filesystem — a repo-relative POSIX path, never an absolute one.
    ``None`` when *spec* climbs above the repo root: that step is not a
    candidate, rather than a hit on whatever the climb happens to reach
    outside the tree (decision 4's fourth rule)."""
    parts: list[str] = []
    for part in (base / spec).parts:
        if part == ".":
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
            continue
        parts.append(part)
    return str(PurePosixPath(*parts)) if parts else "."


def _resolve_include(
    including_path: str, spec: str, known_files: set[str], headers: set[str]
) -> str | None:
    """Decision 4's three steps, shared by ``"p"`` and (when tried first)
    ``<p>``: relative to the including file's directory; relative to the
    repo root; the unique repo header whose path ends with ``/p``."""
    candidate = _normalize(PurePosixPath(including_path).parent, spec)
    if candidate is not None and candidate in known_files:
        return candidate
    candidate = _normalize(PurePosixPath("."), spec)
    if candidate is not None and candidate in known_files:
        return candidate
    suffix = "/" + spec
    matches = [f for f in headers if f.endswith(suffix)]
    return matches[0] if len(matches) == 1 else None


def _join(files: list[CFile]) -> dict:
    """Assemble the layer bundle — the `rustsource._join` contract."""
    nodes: dict[str, dict] = {}
    module_edges: dict[tuple, list] = defaultdict(list)
    symbols: list[dict] = []
    known_files = {parsed.path for parsed in files}
    headers = {p for p in known_files if p.endswith(".h")}

    for parsed in files:
        nodes[module_id(parsed.path)] = {
            "id": module_id(parsed.path), "kind": "module", "path": parsed.path
        }

    for parsed in files:
        mid = module_id(parsed.path)
        for inc in parsed.includes:
            resolved = _resolve_include(parsed.path, inc["spec"], known_files, headers)
            if resolved is not None:
                target_mid = module_id(resolved)
                if target_mid != mid:
                    module_edges[(mid, target_mid, "imports")].append(
                        {"path": parsed.path, "line": inc["line"]}
                    )
                continue
            if inc["angle"]:
                # Neither in-repo rule matched: a dependency header,
                # named the way `#include <p>` spells it.
                ext_id = f"ext:{inc['spec']}"
                nodes.setdefault(ext_id, {"id": ext_id, "kind": "external", "name": inc["spec"]})
                module_edges[(mid, ext_id, "imports")].append(
                    {"path": parsed.path, "line": inc["line"]}
                )
            # A quoted include that resolves nowhere (ambiguous, or
            # unmatched) draws no edge — decision 4.

        for symbol in parsed.symbols:
            symbols.append({"id": f"{mid}.{symbol['qualname']}", "module": mid, **symbol})

    return {
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "module_edges": _edge_list(module_edges),
        "symbols": sorted(symbols, key=lambda s: s["id"]),
        "call_sites": _call_sites(files),
        "call_fallback": _call_fallback(files, known_files, headers),
        "local_bindings": {
            parsed.path: tuple(parsed.local_bindings) for parsed in files if parsed.local_bindings
        },
        "files": files,
        "tests": sorted(
            (test for parsed in files for test in parsed.tests), key=lambda t: t["id"]
        ),
        "languages": ["c"],
        "errors": [],
    }


def _call_sites(files: list[CFile]) -> list:
    """Lane A's C call sites, in evidence-IR shape (ADR-029)."""
    from hobbes.extract import evidence as ev

    return [
        ev.Site(
            provider=ev.TREE_SITTER,
            kind=ev.CALL_SITE,
            file=parsed.path,
            line=call["line"],
            name=call["name"],
            col=call["col"],
            scope=(
                f"{module_id(parsed.path)}.{call['scope']}"
                if call["scope"]
                else module_id(parsed.path)
            ),
        )
        for parsed in files
        for call in parsed.calls
    ]


def _resolve_fallback(
    parsed: CFile,
    call: dict,
    local_defs: dict[tuple[str, str], tuple[str, int]],
    ambiguous_locals: set[tuple[str, str]],
    macros_by_file: dict[str, dict[str, tuple[str, int]]],
    includes_by_file: dict[str, list[str]],
    globals_by_name: dict[str, list[tuple[str, int]]],
) -> tuple[str, int] | None:
    """Decision 6's three ranks. A rank with more than one candidate is an
    abstention, not a fall-through to the next rank."""
    name = call["name"]
    key = (parsed.path, name)
    if key in ambiguous_locals:
        return None  # rank 1 tie: abstain, never fall through to rank 2
    same_file = local_defs.get(key)
    if same_file is not None:
        return same_file
    header_matches = [
        macros_by_file[inc][name]
        for inc in includes_by_file[parsed.path]
        if name in macros_by_file.get(inc, {})
    ]
    if len(header_matches) == 1:
        return header_matches[0]
    if header_matches:
        return None
    candidates = globals_by_name.get(name, [])
    return candidates[0] if len(candidates) == 1 else None


def _call_fallback(
    files: list[CFile], known_files: set[str], headers: set[str]
) -> dict[tuple[str, int, str], tuple[str, int]]:
    """Lane A's own resolutions, keyed by call site — the syntactic floor
    this unit's whole graph rests on, since there is no semantic lane to
    hand off to (module docstring)."""
    local_defs: dict[tuple[str, str], tuple[str, int]] = {}
    ambiguous_locals: set[tuple[str, str]] = set()
    macros_by_file: dict[str, dict[str, tuple[str, int]]] = defaultdict(dict)
    globals_by_name: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for parsed in files:
        for symbol in parsed.symbols:
            if symbol["kind"] in ("function", "macro"):
                key = (parsed.path, symbol["name"])
                # `parsed.symbols` already holds one row per id (the
                # first definition, decision 3); a name that had more
                # than one same-file definition is rank 1's tie, and
                # abstains rather than resolving to the survivor.
                if symbol["name"] in parsed.duplicate_names:
                    ambiguous_locals.add(key)
                else:
                    local_defs[key] = (parsed.path, symbol["line"])
            if symbol["kind"] == "macro":
                macros_by_file[parsed.path][symbol["name"]] = (parsed.path, symbol["line"])
            if symbol["kind"] == "function" and not symbol.get("static", False):
                globals_by_name[symbol["name"]].append((parsed.path, symbol["line"]))

    includes_by_file: dict[str, list[str]] = {}
    for parsed in files:
        includes_by_file[parsed.path] = [
            resolved
            for inc in parsed.includes
            if (resolved := _resolve_include(parsed.path, inc["spec"], known_files, headers))
            is not None
        ]

    fallback: dict[tuple[str, int, str], tuple[str, int]] = {}
    for parsed in files:
        for call in parsed.calls:
            if call["shape"] != "plain":
                continue  # field and dereference calls are never resolved
            name = call["name"]
            if any(
                n == name and start <= call["line"] <= end for (n, start, end) in parsed.local_bindings
            ):
                continue  # a function-pointer parameter or local: never resolved
            target = _resolve_fallback(
                parsed,
                call,
                local_defs,
                ambiguous_locals,
                macros_by_file,
                includes_by_file,
                globals_by_name,
            )
            if target is None or target == (parsed.path, call["line"]):
                continue
            fallback[(parsed.path, call["line"], name)] = target
    return fallback


def collect_c_tests(files: list[CFile], symbol_edges: list[dict]) -> list[dict]:
    """C test inventory with reach, measured over the join's edges — the
    same rule every other framework's reach uses (ADR-007)."""
    from hobbes.extract.testmap import _closure

    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in symbol_edges:
        if edge["type"] == "calls":
            adjacency[edge["from"]].add(edge["to"])

    known_modules = {module_id(parsed.path) for parsed in files}
    out = []
    for parsed in files:
        mid = module_id(parsed.path)
        for test in parsed.tests:
            symbol_id = f"{mid}.{test['name']}"
            reached = _closure(symbol_id, adjacency)
            out.append(
                {
                    "id": test["id"],
                    "file": test["file"],
                    "line": test["line"],
                    "framework": test["framework"],
                    "symbol": symbol_id,
                    "reaches": sorted(reached),
                    "reaches_modules": sorted(
                        {r.rsplit(".", 1)[0] for r in reached} & known_modules
                    ),
                }
            )
    return out
