"""Lane A for Go: structure, symbols, and call *sites* (ADR-037).

The third syntax provider, on the `tssource.py` contract — same bundle
shape, same division of labour, so the graph builder and the range join
need no Go-specific code (P7).

**Why Go needs a lane A at all**, when §3.7 called one optional: `scip-go`
populates `syntax_kind` for **0 of 18,682** occurrences, exactly as
`scip-python` does for 0 of 8,575. No SCIP indexer we have measured says
whether an occurrence is a call, a type name or a plain mention, so
without a syntax provider a language gets references and no `calls` edges
at all — no `who_calls`, no test reach (ADR-037, C-6).

**Module ids are per file**, not per package, though Go's unit is the
package. The range join keys symbols by module and line
(`scipsource._SymbolIndex`), so a package holding `policy.go` and
`merge.go` would confuse line 42 of one with line 42 of the other. Per-file
ids keep the join working with no change to it.

That leaves Go's package-level imports with nowhere to point — an
``import "…/internal/policy"`` names a directory, and picking one of its
files would be a guess. So lane A emits import edges only for **external**
packages (stdlib and third-party, which have no in-repo file), and
in-repo package imports become *resolution* rather than structure: the
fallback table resolves ``policy.Merge`` to the file that defines ``Merge``,
and the join turns that into a file-level ``imports`` edge. Precise
instead of approximate, and it works in both lanes because `project()`
raises module edges from any resolution, semantic or fallback.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import tree_sitter_go
from tree_sitter import Language, Node, Parser

from hobbes.extract.discover import SKIPPED_DIR_NAMES
from hobbes.extract.graph import _edge_list

_PARSER = Parser(Language(tree_sitter_go.language()))

#: Directories pruned in addition to the shared set. `vendor/` is a
#: checked-in copy of other people's code: real files, but not this repo's
#: architecture, and indexing them would swamp every graph that has one.
_GO_SKIPPED = SKIPPED_DIR_NAMES | {"vendor", "testdata"}

#: Declarations that become graph symbols, → symbol kind.
_DECL_KINDS = {
    "function_declaration": "function",
    "method_declaration": "method",
    "type_declaration": "type",
    "const_declaration": "const",
    "var_declaration": "var",
}


@dataclass
class GoFile:
    """One parsed ``.go`` file, in the shape the join consumes."""

    path: str
    package: str
    imports: list[dict] = field(default_factory=list)
    symbols: list[dict] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    env_reads: list[dict] = field(default_factory=list)
    tests: list[dict] = field(default_factory=list)
    #: (name, start, end): names bound below package level — parameters
    #: (receivers and named results included), `:=` and `var` targets,
    #: range targets — with the enclosing function's line extent, so the
    #: tail view can match a bare call by scope containment (ADR-046).
    local_bindings: list[tuple] = field(default_factory=list)


def has_go_files(repo_root: Path) -> bool:
    """Cheap detection: does this repo contain Go at all?"""
    return any(True for _ in iter_go_files(Path(repo_root)))


def iter_go_files(repo_root: Path):
    """Repo-relative ``.go`` paths, pruned like every other discovery."""
    stack = [Path(repo_root)]
    while stack:
        directory = stack.pop()
        try:
            children = sorted(directory.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_dir():
                if child.name not in _GO_SKIPPED and not child.name.startswith("."):
                    stack.append(child)
            elif child.suffix == ".go":
                yield child


def module_id(path: str) -> str:
    """Repo-relative path sans ``.go`` — the ADR-021 id rule, unchanged."""
    pure = PurePosixPath(path)
    return str(pure.with_suffix("")) if pure.suffix == ".go" else str(pure)


def package_dir(path: str) -> str:
    """The directory a file's package lives in; ``.`` at the repo root."""
    parent = str(PurePosixPath(path).parent)
    return parent if parent not in ("", ".") else "."


def extract_go(repo_root: Path) -> dict | None:
    """The Go layer for *repo_root*, or ``None`` when it has no Go.

    Never raises on a malformed file: tree-sitter is error-tolerant by
    design (§3.1) and a file that will not parse yields whatever the walk
    could see, which is the point of having a syntax lane at all.
    """
    repo_root = Path(repo_root).resolve()
    files: list[GoFile] = []
    for absolute in iter_go_files(repo_root):
        rel = absolute.relative_to(repo_root).as_posix()
        try:
            source = absolute.read_bytes()
        except OSError:
            continue
        files.append(_parse_file(rel, source))
    if not files:
        return None
    return _join(files)


def _parse_file(rel: str, source: bytes) -> GoFile:
    root = _PARSER.parse(source).root_node
    parsed = GoFile(path=rel, package=_package_name(root))

    for node in root.children:
        if node.type == "import_declaration":
            parsed.imports.extend(_imports(node))
        kind = _DECL_KINDS.get(node.type)
        if kind is not None:
            parsed.symbols.extend(_symbols(node, kind))

    for symbol in parsed.symbols:
        if _is_test(rel, symbol):
            parsed.tests.append(
                {
                    "id": f"{rel}::{symbol['name']}",
                    "name": symbol["name"],
                    "file": rel,
                    "line": symbol["line"],
                    "framework": "go-test",
                }
            )

    parsed.calls = _calls(root, parsed.symbols)
    parsed.env_reads = _env_reads(root)
    parsed.local_bindings = _local_bindings(root)
    return parsed


def _local_bindings(root: Node) -> list[tuple]:
    """Names bound below package level, with enclosing-function extents.

    The observation the tail view needs (ADR-046): a bare unresolved Go
    call is usually a closure-typed local (``cleanup := func() {...}``,
    ``ctx, cancel := context.WithCancel(...)``) — bound here, invisible
    to both lanes' resolvers, and previously "unclassified". Recorded
    forms: parameters (receiver and named results included), ``:=`` and
    ``var`` targets, and ``range`` targets, each inside the innermost
    ``func``. Package-level declarations are symbols, not bindings.
    """
    out: list[tuple] = []

    def idents(node: Node):
        if node.type == "identifier":
            yield node
        elif node.type == "expression_list":
            for child in node.named_children:
                yield from idents(child)

    def walk(node: Node, extent: tuple[int, int] | None) -> None:
        kind = node.type
        if kind in ("function_declaration", "method_declaration", "func_literal"):
            own = (node.start_point.row + 1, node.end_point.row + 1)
            for part in node.children:  # receiver, params, named results
                if part.type == "parameter_list":
                    for decl in part.named_children:
                        for child in decl.children:
                            if child.type == "identifier":
                                out.append((_text(child), *own))
            body = node.child_by_field_name("body")
            if body is not None:
                for child in body.children:
                    walk(child, own)
            return
        if extent is not None:
            if kind == "short_var_declaration":
                left = node.child_by_field_name("left")
                if left is not None:
                    for ident in idents(left):
                        out.append((_text(ident), *extent))
            elif kind == "var_declaration":
                for spec in node.named_children:
                    if spec.type == "var_spec":
                        for name in spec.children_by_field_name("name"):
                            out.append((_text(name), *extent))
            elif kind == "range_clause":
                left = node.child_by_field_name("left")
                if left is not None:
                    for ident in idents(left):
                        out.append((_text(ident), *extent))
        for child in node.children:
            walk(child, extent)

    walk(root, None)
    return out


def _text(node: Node) -> str:
    return (node.text or b"").decode("utf-8", "replace")


def _package_name(root: Node) -> str:
    for child in root.children:
        if child.type == "package_clause":
            for ident in child.children:
                if ident.type == "package_identifier":
                    return _text(ident)
    return ""


def _imports(declaration: Node) -> list[dict]:
    """Import paths with their line. Aliases are kept: a call's receiver is
    the alias, and the fallback table has to match on what the code says."""
    found = []
    for node in _walk(declaration):
        if node.type != "import_spec":
            continue
        alias = None
        path = None
        for child in node.children:
            if child.type in ("package_identifier", "blank_identifier", "dot"):
                alias = _text(child)
            elif child.type == "interpreted_string_literal":
                path = _text(child).strip('"')
        if path is None:
            continue
        found.append(
            {
                "path": path,
                "alias": alias or PurePosixPath(path).name,
                "line": node.start_point.row + 1,
            }
        )
    return found


def _symbols(declaration: Node, kind: str) -> list[dict]:
    """Top-level declarations only — nested funcs are not architecture."""
    line = declaration.start_point.row + 1
    end_line = declaration.end_point.row + 1

    if kind in ("function_declaration", "function"):
        name = _child_text(declaration, "identifier")
        if not name:
            return []
        return [_symbol(name, name, "function", line, end_line)]

    if kind == "method":
        name = _child_text(declaration, "field_identifier")
        if not name:
            return []
        receiver = _receiver_type(declaration)
        qualname = f"{receiver}.{name}" if receiver else name
        return [_symbol(name, qualname, "method", line, end_line)]

    # type / const / var declarations hold one or more specs.
    out = []
    spec_types = {
        "type": ("type_spec",),
        "const": ("const_spec",),
        "var": ("var_spec",),
    }[kind]
    for node in _walk(declaration):
        if node.type not in spec_types:
            continue
        # The spec's *name* field, never its first identifier-shaped
        # child: `var mavenImage string` has a type_identifier too, and
        # reading that one minted a symbol called `string` for every
        # typed var and const (58 of them in dagger) — which lane A's
        # fallback then bound `string(x)` conversions to (oracle lane O4,
        # the last 3 contradictions after the join fixes).
        names = [_text(child) for child in node.children_by_field_name("name")]
        if not names:
            fallback = _child_text(node, "type_identifier") or _child_text(node, "identifier")
            names = [fallback] if fallback else []
        for name in names:
            out.append(
                _symbol(
                    name,
                    name,
                    kind,
                    node.start_point.row + 1,
                    node.end_point.row + 1,
                )
            )
    return out


def _symbol(name: str, qualname: str, kind: str, line: int, end_line: int) -> dict:
    return {
        "name": name,
        "qualname": qualname,
        "kind": kind,
        "line": line,
        "end_line": end_line,
    }


def _child_text(node: Node, child_type: str) -> str | None:
    for child in node.children:
        if child.type == child_type:
            return _text(child)
    return None


def _receiver_type(method: Node) -> str | None:
    """``func (m *Merger) Merge(...)`` → ``Merger``. The pointer star and
    the receiver name are noise; the type is the thing symbols hang off."""
    for child in method.children:
        if child.type != "parameter_list":
            continue
        for node in _walk(child):
            if node.type == "type_identifier":
                return _text(node)
        return None
    return None


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _enclosing(symbols: list[dict], line: int) -> str | None:
    """The declaration containing *line*, innermost last."""
    best = None
    for symbol in symbols:
        if symbol["line"] <= line <= symbol["end_line"]:
            best = symbol["qualname"]
    return best


def _calls(root: Node, symbols: list[dict]) -> list[dict]:
    """Every call site, with the column and terminal name the join needs.

    Position is the **callee identifier's**, not the call expression's —
    the same correction `pysource` needed at ADR-029, and for the same
    reason: SCIP reports the occurrence of the name, so a join keyed on
    the expression's start would miss on any wrapped or chained call.
    """
    found = []
    for node in _walk(root):
        if node.type == "type_conversion_expression":
            # ``Ref[string](v)`` parses as a conversion to a generic type,
            # because syntactically it is one; whether ``Ref`` is a type
            # or a generic function is the conversion filter's question,
            # the same one it answers for ``Decision(s)``. Emit the site
            # and let it decide (O4: generic instantiation calls had no
            # site at all).
            generic = _generic_callee(node)
            if generic is None:
                continue
            terminal, receiver = generic
            found.append(
                {
                    "name": _text(terminal),
                    "receiver": receiver,
                    "line": terminal.start_point.row + 1,
                    "col": terminal.start_point.column,
                    "scope": _enclosing(symbols, node.start_point.row + 1),
                    "args": _literal_args(node),
                    "call_line": node.start_point.row + 1,
                }
            )
            continue
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        if function is None:
            continue
        terminal = _terminal_identifier(function)
        if terminal is None:
            continue
        receiver = None
        if function.type == "selector_expression":
            operand = function.child_by_field_name("operand")
            if operand is not None and operand.type == "identifier":
                receiver = _text(operand)
            else:
                receiver = _EXPR_RECEIVER
        found.append(
            {
                "name": _text(terminal),
                "receiver": receiver,
                "line": terminal.start_point.row + 1,
                "col": terminal.start_point.column,
                "scope": _enclosing(symbols, node.start_point.row + 1),
                "args": _literal_args(node),
                # The call expression's own start, which is where a
                # registration reads naturally, as against the callee's
                # position that the join keys on.
                "call_line": node.start_point.row + 1,
            }
        )
    return found


def _literal_args(call: Node) -> list[dict]:
    """A call's statically visible arguments: string literals and names.

    Generic syntax, not framework knowledge — an argument that is a literal
    is a fact about the source, and recording it here is what lets a pack
    read routes *from the lane* instead of re-parsing the file behind its
    back (§3.5). Anything computed is simply absent, which is the same
    under-approximation every other statically-read fact makes (C-5).
    """
    arguments = call.child_by_field_name("arguments")
    if arguments is None:
        return []
    out = []
    for argument in arguments.named_children:
        if argument.type == "interpreted_string_literal":
            out.append({"kind": "string", "value": _text(argument).strip('"')})
        elif argument.type == "identifier":
            out.append({"kind": "ident", "value": _text(argument)})
        elif argument.type == "selector_expression":
            field_node = argument.child_by_field_name("field")
            if field_node is not None:
                out.append({"kind": "ident", "value": _text(field_node)})
    return out


def _generic_callee(conversion: Node) -> tuple[Node, str | None] | None:
    """``(name node, receiver)`` of a ``T[X](v)`` form, or None if the
    converted type is not a generic instantiation."""
    typ = conversion.child_by_field_name("type")
    if typ is None or typ.type != "generic_type":
        return None
    inner = typ.child_by_field_name("type") or (typ.named_children[0] if typ.named_children else None)
    if inner is None:
        return None
    if inner.type == "type_identifier":
        return inner, None
    if inner.type == "qualified_type":
        name = inner.child_by_field_name("name")
        pkg = inner.child_by_field_name("package")
        if name is not None:
            return name, (_text(pkg) if pkg is not None else None)
    return None


#: The receiver recorded for a call whose operand is an expression rather
#: than a name — ``b.Cfg().Base``, ``x.y.Name()``, ``(*T).M(...)``. Such
#: a call can be neither a package-qualified name nor a bare one, so the
#: conversion filter and the fallback must not read it as same-package
#: (the O4 finding: ``m.Discovery.UserConfig()`` was dropped as a
#: conversion because a type ``UserConfig`` exists in the package).
_EXPR_RECEIVER = "<expr>"


def _terminal_identifier(function: Node) -> Node | None:
    """The callee's name node, through the wrappers Go allows around it.

    ``Ref[string](v)`` is a call whose function is an index expression
    (a generic instantiation); ``(*T).M(x)``'s function is a selector on
    a parenthesised operand. Both name a callee and both were sites the
    oracle lane found missing (O4).
    """
    if function.type == "identifier":
        return function
    if function.type == "selector_expression":
        return function.child_by_field_name("field")
    if function.type in ("index_expression", "generic_type"):
        operand = function.child_by_field_name("operand") or function.child_by_field_name("type")
        return _terminal_identifier(operand) if operand is not None else None
    if function.type == "parenthesized_expression" and function.named_child_count == 1:
        return _terminal_identifier(function.named_children[0])
    return None


#: ``os.Getenv("X")`` and ``os.LookupEnv("X")`` — the cross-layer join's
#: Go end (M3's ``env:VAR`` nodes, now spanning Py + TF + JS + Go).
_ENV_FUNCS = {"Getenv", "LookupEnv"}


def _env_reads(root: Node) -> list[dict]:
    found = []
    for node in _walk(root):
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        if function is None or function.type != "selector_expression":
            continue
        operand = function.child_by_field_name("operand")
        field_node = function.child_by_field_name("field")
        if operand is None or field_node is None:
            continue
        if _text(operand) != "os" or _text(field_node) not in _ENV_FUNCS:
            continue
        arguments = node.child_by_field_name("arguments")
        literal = _first_string(arguments) if arguments is not None else None
        if literal:
            found.append({"var": literal, "line": node.start_point.row + 1})
    return found


def _first_string(arguments: Node) -> str | None:
    for node in _walk(arguments):
        if node.type == "interpreted_string_literal":
            return _text(node).strip('"')
    return None


_TEST_NAME = re.compile(r"^(Test|Benchmark|Fuzz|Example)[A-Z_]?")


def _is_test(rel: str, symbol: dict) -> bool:
    return (
        rel.endswith("_test.go")
        and symbol["kind"] == "function"
        and bool(_TEST_NAME.match(symbol["name"]))
    )


def _join(files: list[GoFile]) -> dict:
    """Assemble the layer bundle — the `tssource.join_facts` contract."""
    nodes: dict[str, dict] = {}
    module_edges: dict[tuple, list] = defaultdict(list)
    symbols: list[dict] = []

    # Package directories that exist in this repo, so an import can be told
    # from a third-party one without consulting go.mod.
    packages: dict[str, list[GoFile]] = defaultdict(list)
    for parsed in files:
        packages[package_dir(parsed.path)].append(parsed)

    for parsed in files:
        mid = module_id(parsed.path)
        nodes[mid] = {"id": mid, "kind": "module", "path": parsed.path}

        for imp in parsed.imports:
            target = _repo_package(imp["path"], packages)
            if target is not None:
                # In-repo package imports become resolution, not structure —
                # see the module docstring. The join raises the file-level
                # edge from whatever the call actually reaches.
                continue
            ext_id = f"ext:{imp['path']}"
            nodes.setdefault(ext_id, {"id": ext_id, "kind": "external", "name": imp["path"]})
            module_edges[(mid, ext_id, "imports")].append(
                {"path": parsed.path, "line": imp["line"]}
            )

        for read in parsed.env_reads:
            env_id = f"env:{read['var']}"
            nodes.setdefault(env_id, {"id": env_id, "kind": "env", "name": read["var"]})
            module_edges[(mid, env_id, "env-read")].append(
                {"path": parsed.path, "line": read["line"]}
            )

        for symbol in parsed.symbols:
            symbols.append({"id": f"{mid}.{symbol['qualname']}", "module": mid, **symbol})

    sorted_symbols = sorted(symbols, key=lambda s: s["id"])
    conversions = _type_names(files)
    return {
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "module_edges": _edge_list(module_edges),
        "symbols": sorted_symbols,
        "local_bindings": {
            parsed.path: tuple(parsed.local_bindings)
            for parsed in files
            if parsed.local_bindings
        },
        "call_sites": _call_sites(files, packages, conversions),
        "call_fallback": _call_fallback(files, packages, conversions),
        "files": files,
        "tests": sorted(
            (test for parsed in files for test in parsed.tests),
            key=lambda t: t["id"],
        ),
        "languages": ["go"],
        "errors": [],
    }


def _repo_package(import_path: str, packages: dict[str, list[GoFile]]) -> str | None:
    """The repo directory an import path names, if it names one.

    Matched by suffix rather than by parsing ``go.mod``: an import is
    ``<module>/<dir>`` and the repo holds ``<dir>``, so the longest
    directory that the import path ends with is the package. Guessing from
    go.mod would be more precise and needs a second file to be right;
    this needs none and cannot resolve to a directory that is not there.
    """
    best = None
    for directory in packages:
        if directory == ".":
            continue
        if import_path == directory or import_path.endswith("/" + directory):
            if best is None or len(directory) > len(best):
                best = directory
    return best


def _type_names(files: list[GoFile]) -> set[tuple[str, str]]:
    """``(package directory, name)`` for every type declared in the repo.

    Go writes a conversion exactly like a call — ``Decision(s)`` and
    ``Resolve(s)`` are the same node type — and no indexer can separate
    them either, because that is what `syntax_kind` was for (C-6). What
    lane A *does* know is which names are types, and a type is never
    called. Filtering here keeps a conversion from becoming a `calls` edge
    pointing at a struct, which would be a false edge, and false edges are
    worse than missing ones (ADR-007).
    """
    return {
        (package_dir(parsed.path), symbol["qualname"])
        for parsed in files
        for symbol in parsed.symbols
        if symbol["kind"] == "type"
    }


def _resolvable_package(
    parsed: GoFile, call: dict, packages: dict[str, list[GoFile]]
) -> str | None:
    """Which repo package a call's name would resolve in, if any."""
    if call["receiver"] is None:
        return package_dir(parsed.path)
    for imp in parsed.imports:
        if imp["alias"] != call["receiver"]:
            continue
        return _repo_package(imp["path"], packages)
    return None


def _is_conversion(
    parsed: GoFile,
    call: dict,
    packages: dict[str, list[GoFile]],
    conversions: set[tuple[str, str]],
) -> bool:
    directory = _resolvable_package(parsed, call, packages)
    return directory is not None and (directory, call["name"]) in conversions


def _call_sites(
    files: list[GoFile],
    packages: dict[str, list[GoFile]],
    conversions: set[tuple[str, str]],
) -> list:
    """Lane A's Go call sites, in evidence-IR shape (ADR-029).

    Type conversions are dropped rather than emitted, so they are absent
    from the join's *left* side and cannot become an edge down either
    arm — semantic or fallback. Dropping them at the source is the only
    place one filter covers both, and it needs no change to the join.
    """
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
        if not _is_conversion(parsed, call, packages, conversions)
    ]


def _call_fallback(
    files: list[GoFile],
    packages: dict[str, list[GoFile]],
    conversions: set[tuple[str, str]],
) -> dict[tuple[str, int, str], tuple[str, int]]:
    """Lane A's own resolutions, keyed by call site (ADR-031).

    Go is unusually tractable here: a top-level name is unique within its
    package, and a qualified call names its package by alias. So
    ``policy.Merge(...)`` resolves exactly, given the import list — no
    inference, no ranking. Unqualified calls resolve within the file's own
    package, which is the same rule the compiler uses.

    Deliberately under-approximated, as every fallback is: method calls on
    a value (``m.Merge()``) are skipped, because knowing what ``m`` is
    needs a type checker and that is lane B's job.
    """
    where: dict[tuple[str, str], tuple[str, int]] = {}
    for parsed in files:
        directory = package_dir(parsed.path)
        for symbol in parsed.symbols:
            where.setdefault(
                (directory, symbol["qualname"]), (parsed.path, symbol["line"])
            )

    fallback: dict[tuple[str, int, str], tuple[str, int]] = {}
    for parsed in files:
        own_dir = package_dir(parsed.path)
        by_alias = {}
        for imp in parsed.imports:
            target = _repo_package(imp["path"], packages)
            if target is not None:
                by_alias[imp["alias"]] = target

        for call in parsed.calls:
            if _is_conversion(parsed, call, packages, conversions):
                continue
            if call["receiver"] is None:
                if _shadowed(parsed, call["name"], call["line"]):
                    continue
                target = where.get((own_dir, call["name"]))
            elif call["receiver"] in by_alias:
                target = where.get((by_alias[call["receiver"]], call["name"]))
            else:
                target = None  # a value's method, or a third-party package
            if target is None:
                continue
            if target == (parsed.path, call["line"]):
                continue  # a declaration is not a call of itself
            fallback[(parsed.path, call["line"], call["name"])] = target
    return fallback


def _shadowed(parsed: GoFile, name: str, line: int) -> bool:
    """A bare name bound in the enclosing function (``assert := func(...)``,
    a parameter, a ``range`` target — ADR-046's bindings) is *that*
    binding, never the package-level namesake: ADR-090's scope rule, the
    Go shape. The oracle lane's fzf cell (2026-08-27): all 87 syntactic
    contradictions were a test's local ``assert`` closure bound to
    ``merger_test.assert`` in another file of the package, and a local
    ``atoi`` to ``options.atoi``. A local ``func`` literal is never a
    symbol, so there is no nested-declaration exemption to keep here."""
    return any(
        b[0] == name and b[1] <= line <= b[2] for b in parsed.local_bindings
    )


def collect_go_tests(files: list[GoFile], symbol_edges: list[dict]) -> list[dict]:
    """Go test inventory with reach, measured over the join's edges.

    Reach is the closure over ``calls`` edges from the test function, the
    same rule pytest and vitest reach use (ADR-007), so a Go row means what
    a Python row means.
    """
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
            # Exactly the v3 row shape every other framework emits — a Go
            # row has to mean what a pytest row means, field for field.
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
