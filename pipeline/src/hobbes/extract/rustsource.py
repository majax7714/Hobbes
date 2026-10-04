"""Lane A for Rust: structure, symbols, and call *sites* (ADR-040).

The fourth syntax provider, on the `gosource.py` contract — same bundle
shape, same division of labour, so the graph builder and the range join
need no Rust-specific code (P7).

**Why Rust needs a lane A at all:** rust-analyzer populates `syntax_kind`
for **0 of 169** occurrences on the spike repo, exactly as `scip-python`
(0/8,575) and `scip-go` (0/18,682) do. Three independent indexers, the
same omission (C-6): none can say whether an occurrence is a call, so
without a syntax provider Rust would get references and no `calls` edges
at all — no `who_calls`, no test reach (ADR-037's correction, confirmed
a third time).

**Macro arguments are token trees.** tree-sitter's Rust grammar leaves
everything between ``!`` and ``;`` unparsed, so ``assert_eq!(add(1, 2),
3)`` contains no ``call_expression`` — and nearly every Rust test asserts
through macros, so a walk that stops at real call expressions produces a
language whose tests reach nothing. rust-analyzer, meanwhile, *expands*
macros and emits the ``add`` occurrence at its real pre-expansion
position. So this walk applies **call-shape detection** inside token
trees: an identifier token immediately followed by a parenthesized token
tree is recorded as a call site at that identifier. That is syntax-level
honesty, not resolution — a false-shaped site becomes an edge only if a
resolution or the fallback lands on exactly that (file, line, name), so
noise dies in the join (ADR-040 decision 4).

**Module ids are per file** (the ADR-021 rule), and — like Go — lane A
emits **no in-repo import edges**: a ``use`` names an item path, not a
file, and the join raises file-level edges from what calls actually
reach. Lane A's ``imports`` edges point only at ``ext:`` crates, whose
names have no in-repo file to be confused with.
"""

from __future__ import annotations

import re
import tomllib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import tree_sitter_rust
from tree_sitter import Language, Node, Parser

from hobbes.extract.discover import SKIPPED_DIR_NAMES, is_linked_copy, too_deep
from hobbes.extract.graph import _edge_list

_PARSER = Parser(Language(tree_sitter_rust.language()))

#: Directories pruned in addition to the shared set. `target/` is cargo's
#: build output: checked in rarely, enormous always.
_RUST_SKIPPED = SKIPPED_DIR_NAMES | {"target"}

#: Path roots that name the current crate rather than another one.
_LOCAL_ROOTS = {"crate", "self", "super"}


@dataclass
class RustFile:
    """One parsed ``.rs`` file, in the shape the join consumes."""

    path: str
    imports: list[dict] = field(default_factory=list)  # use declarations
    mods: list[dict] = field(default_factory=list)  # declared child modules
    symbols: list[dict] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    tests: list[dict] = field(default_factory=list)
    #: Names declared by ``trait`` items in this file. Kept apart from
    #: `symbols` (where a trait is a ``type``) because the fallback must
    #: refuse ``Trait::method(..)`` — dispatch, lane B's — and nothing
    #: else needs to tell a trait from a struct (C-72).
    traits: list[str] = field(default_factory=list)
    #: Each symbol's ``(line, end_line, header)`` by qualname, where
    #: *header* is the text of the ``impl`` block it was declared in, up
    #: to the body and whitespace-collapsed (``""`` outside any impl).
    #: Read by :func:`shared_qualnames` alone (ADR-163, C-180); keyed by
    #: the qualname after ADR-174's ordinal, so it lists nothing unless an
    #: id scheme lets two blocks share an id again.
    defs: dict[str, list[tuple[int, int, str]]] = field(default_factory=dict)
    #: The ``(qualname, line)`` of each def a ``#[cfg(…)]`` gates, on the
    #: item itself or on an enclosing ``mod`` or ``impl``. Read by
    #: :func:`cfg_twins` alone (ADR-165, C-182).
    cfg_gated: set[tuple[str, int]] = field(default_factory=set)


def has_rust_files(repo_root: Path) -> bool:
    """Cheap detection: does this repo contain Rust at all?"""
    return any(True for _ in iter_rust_files(Path(repo_root)))


def iter_rust_files(repo_root: Path):
    """Repo-relative ``.rs`` paths, pruned like every other discovery."""
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
                    child.name not in _RUST_SKIPPED
                    and not child.name.startswith(".")
                    and not is_linked_copy(child, repo_root)
                ):
                    stack.append(child)
            elif child.suffix == ".rs":
                yield child


def module_id(path: str) -> str:
    """Repo-relative path sans ``.rs`` — the ADR-021 id rule, unchanged."""
    pure = PurePosixPath(path)
    return str(pure.with_suffix("")) if pure.suffix == ".rs" else str(pure)


def iter_cargo_manifests(repo_root: Path):
    """Every ``Cargo.toml`` in the repo, pruned like the ``.rs`` walk.

    Public because the CLI pack's binary-target discovery needs the same
    pruned walk (C-14): ``rglob`` would descend into ``target/``.
    """
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
                    child.name not in _RUST_SKIPPED
                    and not child.name.startswith(".")
                    and not is_linked_copy(child, repo_root)
                ):
                    stack.append(child)
            elif child.name == "Cargo.toml":
                yield child


def local_crate_names(repo_root: Path) -> dict[str, str]:
    """``{crate name: lib target file}`` for every manifest in the repo.

    Read so a ``use serde::…`` can be told from a ``use mylib::…`` without
    guessing: the crate a repo provides is named only in its
    ``Cargo.toml`` — ``[package] name`` (hyphens underscored, which is how
    code spells it) and ``[lib] name`` when the target is renamed. The
    value is the lib root file the fallback resolves the name to
    (``[lib] path``, defaulting to ``src/lib.rs`` beside the manifest).
    """
    repo_root = Path(repo_root).resolve()
    names: dict[str, str] = {}
    for child in iter_cargo_manifests(repo_root):
        try:
            manifest = tomllib.loads(child.read_text())
        except (OSError, ValueError):
            continue
        base = child.parent.relative_to(repo_root)
        lib = manifest.get("lib") or {}
        lib_path = lib.get("path", "src/lib.rs")
        lib_file = str(PurePosixPath(base) / lib_path).removeprefix("./")
        package = (manifest.get("package") or {}).get("name")
        if isinstance(package, str) and package:
            names.setdefault(package.replace("-", "_"), lib_file)
        lib_name = lib.get("name")
        if isinstance(lib_name, str) and lib_name:
            names[lib_name] = lib_file
    return names


def extract_rust(repo_root: Path) -> dict | None:
    """The Rust layer for *repo_root*, or ``None`` when it has no Rust.

    Never raises on a malformed file: tree-sitter is error-tolerant by
    design (§3.1), and a file that will not parse yields whatever the
    walk could see.
    """
    repo_root = Path(repo_root).resolve()
    files: list[RustFile] = []
    errors: list[dict] = []
    for absolute in iter_rust_files(repo_root):
        rel = absolute.relative_to(repo_root).as_posix()
        try:
            source = absolute.read_bytes()
        except OSError:
            continue
        try:
            files.append(_parse_file(rel, source))
        except RecursionError:
            # C-171: the file stays a module and is read as empty.
            files.append(_parse_file(rel, b""))
            errors.append(too_deep(rel, "Rust"))
    if not files:
        return None
    bundle = _join(files, local_crate_names(repo_root))
    bundle["errors"] = list(bundle["errors"]) + errors
    return bundle


# ---------------------------------------------------------------- parsing


def _text(node: Node) -> str:
    return (node.text or b"").decode("utf-8", "replace")


def _parse_file(rel: str, source: bytes) -> RustFile:
    root = _PARSER.parse(source).root_node
    parsed = RustFile(path=rel)
    _walk_items(root, parsed, prefix="")
    _ordinal_impl_repeats(parsed.symbols)

    for symbol in parsed.symbols:
        parsed.defs.setdefault(symbol["qualname"], []).append(
            (symbol["line"], symbol["end_line"], symbol.pop("impl", ""))
        )
        if symbol.pop("cfg", False):
            parsed.cfg_gated.add((symbol["qualname"], symbol["line"]))
        if symbol.pop("is_test", False):
            parsed.tests.append(
                {
                    "id": f"{rel}::{symbol['name']}",
                    "name": symbol["name"],
                    "file": rel,
                    "line": symbol["line"],
                    "framework": "cargo-test",
                }
            )

    parsed.calls = _calls(root, parsed.symbols)
    return parsed


def _walk_items(
    container: Node,
    parsed: RustFile,
    prefix: str,
    in_impl: bool = False,
    header: str = "",
    gated: bool = False,
):
    """Collect declarations, recursing into mod and impl bodies only.

    Nested *functions* are not architecture (the gosource rule), but a
    ``#[cfg(test)] mod tests`` block is where Rust keeps its unit tests,
    and an ``impl`` block is where it keeps its methods — stopping at the
    top level would make both invisible. *prefix* carries the dotted
    qualname path (``tests.test_add``, ``Counter.incr``). *header* is the
    enclosing ``impl`` block's header text, kept on each symbol for
    :func:`shared_qualnames` (ADR-163). *gated* says an enclosing ``mod``
    or ``impl`` carries a ``#[cfg(…)]``, kept for :func:`cfg_twins`
    (ADR-165).
    """
    pending_attrs: list[Node] = []
    for node in container.children:
        if node.type == "attribute_item":
            pending_attrs.append(node)
            continue
        attrs, pending_attrs = pending_attrs, []
        own = gated or _is_cfg_attr(attrs)
        start = len(parsed.symbols)

        if node.type == "use_declaration":
            parsed.imports.extend(_use_entries(node))
        elif node.type == "mod_item":
            name = _child_text(node, "identifier")
            if not name:
                continue
            body = _child_of_type(node, "declaration_list")
            if body is None:
                parsed.mods.append(
                    {
                        "name": name,
                        "line": node.start_point.row + 1,
                        "path_attr": _path_attribute(attrs),
                    }
                )
            else:
                _walk_items(body, parsed, _dotted(prefix, name), gated=own)
        elif node.type == "impl_item":
            type_name = _impl_type(node)
            body = _child_of_type(node, "declaration_list")
            if body is not None:
                _walk_items(
                    body,
                    parsed,
                    _dotted(prefix, type_name) if type_name else prefix,
                    in_impl=True,
                    header=_impl_header(node, body),
                    gated=own,
                )
        elif node.type == "function_item":
            name = _child_text(node, "identifier")
            if not name:
                continue
            kind = "method" if in_impl else "function"
            if not in_impl and _is_proc_macro_attr(attrs):
                kind = "macro"
            parsed.symbols.append(
                _symbol(name, _dotted(prefix, name), kind, node)
                | {"is_test": _is_test_attr(attrs), "impl": header}
            )
        elif node.type in ("struct_item", "enum_item", "trait_item", "union_item"):
            name = _child_text(node, "type_identifier")
            if name:
                parsed.symbols.append(
                    _symbol(name, _dotted(prefix, name), "type", node) | {"impl": header}
                )
                if node.type == "trait_item":
                    parsed.traits.append(name)
        elif node.type == "type_item":
            name = _child_text(node, "type_identifier")
            if name:
                parsed.symbols.append(
                    _symbol(name, _dotted(prefix, name), "type", node) | {"impl": header}
                )
        elif node.type in ("const_item", "static_item"):
            name = _child_text(node, "identifier")
            if name:
                parsed.symbols.append(
                    _symbol(name, _dotted(prefix, name), "const", node) | {"impl": header}
                )
        elif node.type == "macro_definition":
            name = _child_text(node, "identifier")
            if name:
                parsed.symbols.append(
                    _symbol(name, _dotted(prefix, name), "macro", node) | {"impl": header}
                )
        # A nested walk set its own symbols' gate; these are this item's.
        for symbol in parsed.symbols[start:]:
            symbol.setdefault("cfg", own)


def _ordinal_impl_repeats(symbols: list[dict]) -> None:
    """Tell apart the items two differently written ``impl`` blocks (or two
    kinds) name alike, in place (ADR-174, C-180 lifted).

    The defs of one qualname fall into groups by ``(impl header, kind)`` in
    source order: the first group keeps the qualname, the n-th becomes
    ``qualname~n``, as Java's and C++'s overloads are suffixed. A cfg twin
    or a same-header repeat shares its group and keeps the id (C-182)."""
    groups: dict[str, list[tuple[str, str]]] = {}
    for symbol in symbols:
        seen = groups.setdefault(symbol["qualname"], [])
        group = (symbol.get("impl", ""), symbol["kind"])
        if group not in seen:
            seen.append(group)
        n = seen.index(group) + 1
        if n > 1:
            symbol["qualname"] = f"{symbol['qualname']}~{n}"


def _base_qualname(qualname: str) -> str:
    """The qualname before an ordinal ADR-174 gave it."""
    return qualname.split("~", 1)[0]


def _impl_header(node: Node, body: Node) -> str:
    """``impl<T> Pointer for *const T { … }`` → ``impl<T> Pointer for
    *const T``: the block's text up to its body, whitespace collapsed.
    Two blocks that :func:`_impl_type` names alike differ here unless
    they are written alike — a cfg twin (ADR-163)."""
    text = (node.text or b"")[: body.start_byte - node.start_byte]
    return " ".join(text.decode("utf-8", "replace").split())


def _dotted(prefix: str, name: str) -> str:
    return f"{prefix}.{name}" if prefix else name


def _symbol(name: str, qualname: str, kind: str, node: Node) -> dict:
    return {
        "name": name,
        "qualname": qualname,
        "kind": kind,
        "line": node.start_point.row + 1,
        "end_line": node.end_point.row + 1,
    }


def _child_text(node: Node, child_type: str) -> str | None:
    for child in node.children:
        if child.type == child_type:
            return _text(child)
    return None


def _child_of_type(node: Node, child_type: str) -> Node | None:
    for child in node.children:
        if child.type == child_type:
            return child
    return None


def _impl_type(node: Node) -> str | None:
    """``impl Counter { … }`` / ``impl Display for Counter`` → ``Counter``."""
    type_node = node.child_by_field_name("type")
    if type_node is None:
        return None
    if type_node.type == "type_identifier":
        return _text(type_node)
    for child in _walk(type_node):
        if child.type == "type_identifier":
            return _text(child)
    return None


def _path_attribute(attrs: list[Node]) -> str | None:
    """``#[path = "./utils/utils.rs"]`` → the literal path, if present."""
    for item in attrs:
        attribute = _child_of_type(item, "attribute")
        if attribute is None:
            continue
        if _child_text(attribute, "identifier") != "path":
            continue
        literal = _child_of_type(attribute, "string_literal")
        if literal is not None:
            return _text(literal).strip('"')
    return None


_TEST_ATTR = re.compile(r"^(?:\w+::)*test$")


def _is_test_attr(attrs: list[Node]) -> bool:
    """``#[test]`` and friends (``#[tokio::test]``), never ``#[cfg(test)]``.

    The rule is the attribute *path*: it must be or end in ``test``.
    ``cfg(test)``'s path is ``cfg``, so a config gate does not mark the
    item it gates. Criterion benches carry no attribute at all — they are
    registered by macro, which is framework knowledge and pack territory
    (§3.5), parked in `future_additions.md` rather than half-detected.
    """
    for item in attrs:
        attribute = _child_of_type(item, "attribute")
        if attribute is None:
            continue
        path = None
        for child in attribute.children:
            if child.type in ("identifier", "scoped_identifier"):
                path = _text(child)
                break
        if path is not None and _TEST_ATTR.match(path):
            return True
    return False


#: The attributes that make a ``fn`` a macro definition: the compiler runs
#: it at expansion, and dependents can only invoke it as a macro.
_PROC_MACRO_ATTRS = frozenset({"proc_macro", "proc_macro_attribute", "proc_macro_derive"})


def _is_proc_macro_attr(attrs: list[Node]) -> bool:
    """Whether one of *attrs* is ``#[proc_macro]``, ``#[proc_macro_attribute]``
    or ``#[proc_macro_derive(…)]``. Such a fn is minted as a ``macro``, as a
    ``macro_rules!`` is: read as a ``function``, an invocation ``raw_sql!(..)``
    was drawn as a runtime call of it (sea-query, 2026-10-03: 16 contradicted
    rows, the key holding the expansion's calls instead)."""
    for item in attrs:
        attribute = _child_of_type(item, "attribute")
        if attribute is None:
            continue
        for child in attribute.children:
            if child.type in ("identifier", "scoped_identifier"):
                if _text(child) in _PROC_MACRO_ATTRS:
                    return True
                break
    return False


def _is_cfg_attr(attrs: list[Node]) -> bool:
    """Whether one of *attrs* is ``#[cfg(…)]`` — the path ``cfg`` itself,
    not ``cfg_attr``, which gates an attribute, not the item."""
    for item in attrs:
        attribute = _child_of_type(item, "attribute")
        if attribute is None:
            continue
        for child in attribute.children:
            if child.type in ("identifier", "scoped_identifier"):
                if _text(child) == "cfg":
                    return True
                break
    return False


def _use_entries(declaration: Node) -> list[dict]:
    """Every item a ``use`` brings into scope: path segments + alias.

    ``use a::{b, c as d};`` yields two entries. Globs are skipped — a
    ``use x::*`` binds names nobody spelled, and resolving it needs the
    target's export list, which is lane B's job.
    """
    line = declaration.start_point.row + 1
    entries: list[dict] = []
    for child in declaration.children:
        if child.type in ("identifier", "scoped_identifier", "use_as_clause",
                          "scoped_use_list", "use_list"):
            _expand_use(child, [], entries, line)
    return entries


def _expand_use(node: Node, prefix: list[str], entries: list[dict], line: int):
    if node.type == "identifier":
        segments = prefix + [_text(node)]
        entries.append({"segments": segments, "alias": segments[-1], "line": line})
    elif node.type == "scoped_identifier":
        segments = prefix + _path_segments(node)
        entries.append({"segments": segments, "alias": segments[-1], "line": line})
    elif node.type == "use_as_clause":
        inner = node.children[0]
        alias = _text(node.children[-1])
        segments = prefix + (
            _path_segments(inner) if inner.type == "scoped_identifier" else [_text(inner)]
        )
        entries.append({"segments": segments, "alias": alias, "line": line})
    elif node.type == "scoped_use_list":
        head = node.children[0]
        head_segments = (
            _path_segments(head) if head.type == "scoped_identifier" else [_text(head)]
        )
        use_list = _child_of_type(node, "use_list")
        if use_list is not None:
            _expand_use(use_list, prefix + head_segments, entries, line)
    elif node.type == "use_list":
        for item in node.named_children:
            _expand_use(item, prefix, entries, line)
    # use_wildcard and anything else: skipped, deliberately.


def _path_segments(scoped: Node) -> list[str]:
    """``a::b::c`` (nested scoped_identifiers) → ``["a", "b", "c"]``."""
    segments: list[str] = []
    for node in _walk(scoped):
        if node.type == "identifier":
            segments.append(_text(node))
        elif node.type in ("crate", "self", "super"):
            segments.append(node.type)
    return segments


def _walk(node: Node):
    """*node* and everything under it in pre-order — the node, then its
    children left to right, depth first. An explicit stack, as
    ``csource._walk``: a recursive generator overflowed Python's stack on
    a 537-call builder chain and ended the whole ingest (moonlab's
    ``build.rs``, the E3 draw, 2026-09-26)."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def _enclosing(symbols: list[dict], line: int) -> str | None:
    """The declaration containing *line*, innermost last."""
    best = None
    for symbol in symbols:
        if symbol["line"] <= line <= symbol["end_line"]:
            best = symbol["qualname"]
    return best


def _calls(root: Node, symbols: list[dict]) -> list[dict]:
    """Every call site: call expressions, macro invocations, and
    call-shaped sequences inside macro token trees.

    Position is the **callee identifier's**, not the expression's — the
    ADR-029 correction, needed here for the same reason: SCIP reports the
    occurrence of the name (measured: pre-expansion positions, even for
    macro arguments), so the join keys on where the name is.
    """
    found: list[dict] = []
    for node in _walk(root):
        if node.type == "call_expression":
            function = node.child_by_field_name("function")
            if function is None:
                continue
            terminal = _terminal_identifier(function)
            if terminal is None:
                continue
            found.append(
                _call(
                    terminal,
                    path=_qualifier_segments(function),
                    dotted=_is_dotted(function),
                    scope=_enclosing(symbols, node.start_point.row + 1),
                    first_str=_first_string(node.child_by_field_name("arguments")),
                    qualified=_is_path_qualified(function),
                )
            )
        elif node.type == "macro_invocation":
            macro = node.child_by_field_name("macro")
            if macro is None:
                continue
            terminal = (
                macro if macro.type == "identifier" else _terminal_identifier(macro)
            )
            if terminal is None:
                continue
            tree = _child_of_type(node, "token_tree")
            found.append(
                _call(
                    terminal,
                    path=_qualifier_segments(macro) if macro.type != "identifier" else [],
                    dotted=False,
                    scope=_enclosing(symbols, node.start_point.row + 1),
                    first_str=_first_string(tree),
                    macro=True,
                )
            )
            if tree is not None:
                found.extend(_token_tree_calls(tree, symbols))
    return found


def _call(
    terminal: Node,
    path: list[str],
    dotted: bool,
    scope: str | None,
    first_str: str | None,
    macro: bool = False,
    qualified: bool | None = None,
) -> dict:
    return {
        "name": _text(terminal),
        "path": path,
        "dotted": dotted,
        # `a::b::name(..)` — written with a path, whether or not `path`
        # could read it (`Option::<T>::deserialize` reads as []): the
        # fallback must not treat such a call as a bare name (C-72).
        "qualified": bool(path) if qualified is None else qualified,
        "line": terminal.start_point.row + 1,
        "col": terminal.start_point.column,
        "scope": scope,
        "first_str": first_str,
        # `name!(...)`: the callee is a macro and can only be one — a
        # function of the same name in scope is not what is invoked.
        "macro": macro,
    }


#: How far each token moves a turbofish's angle-bracket depth. ``->`` is
#: its own token (``fn() -> u8``), so it closes nothing.
_ANGLE_DEPTH = {"<": 1, ">": -1, ">>": -2}


def _past_turbofish(children: list[Node], at: int) -> int:
    """The index after a turbofish starting at *at* (``::`` then a
    balanced ``<…>`` at this token tree's level), or *at* itself when there
    is none or it does not close cleanly. hecs (2026-10-03): 175 of its
    misses were ``x.f::<T>(..)`` inside ``assert!``/``assert_eq!``, which
    lane B resolved and the join filed as ``uses``, because no call site
    claimed them."""
    if at + 1 >= len(children) or children[at].type != "::" or children[at + 1].type != "<":
        return at
    depth = 0
    for i in range(at + 1, len(children)):
        depth += _ANGLE_DEPTH.get(children[i].type, 0)
        if depth == 0:
            return i + 1
        if depth < 0:
            return at
    return at


def _token_tree_calls(tree: Node, symbols: list[dict]) -> list[dict]:
    """Call-shape detection inside an unparsed macro body (ADR-040 §4).

    An identifier immediately followed by a ``(``-delimited token tree is
    recorded as a call site, and so is one followed by a turbofish first
    (``x.has::<T>(..)``, ``W::get::<T>(..)``: ``::``, a balanced ``<…>``,
    then the ``(``); the ``::``-joined identifiers before it are its path,
    a ``.`` before it marks a method call. Without the ``::``, ``a < b >
    (c)`` is two comparisons and is left alone, as is anything else in the
    token soup. The shape can lie — and a lying shape produces no edge,
    because nothing resolves at it.
    """
    found: list[dict] = []
    children = tree.children
    for at, node in enumerate(children):
        if node.type != "identifier":
            continue
        args = _past_turbofish(children, at + 1)
        nxt = children[args] if args < len(children) else None
        if nxt is None or nxt.type != "token_tree" or not _text(nxt).startswith("("):
            continue
        path: list[str] = []
        dotted = False
        back = at - 1
        while back >= 1 and children[back].type == "::" and children[back - 1].type == "identifier":
            path.insert(0, _text(children[back - 1]))
            back -= 2
        if back >= 0 and children[back].type == ".":
            dotted = True
        found.append(
            _call(
                node,
                path=path,
                qualified=bool(path) or (at >= 1 and children[at - 1].type == "::"),
                dotted=dotted,
                scope=_enclosing(symbols, node.start_point.row + 1),
                first_str=_first_string(nxt),
            )
        )
    for node in children:
        if node.type == "token_tree":
            found.extend(_token_tree_calls(node, symbols))
    return found


def _terminal_identifier(function: Node) -> Node | None:
    if function.type == "identifier":
        return function
    if function.type == "scoped_identifier":
        name = function.child_by_field_name("name")
        return name if name is not None and name.type == "identifier" else None
    if function.type == "field_expression":
        field_node = function.child_by_field_name("field")
        return field_node if field_node is not None and field_node.type == "field_identifier" else None
    if function.type == "generic_function":
        inner = function.child_by_field_name("function")
        return _terminal_identifier(inner) if inner is not None else None
    return None


def _is_dotted(function: Node) -> bool:
    """Whether a callee is a value's method: ``x.name(..)``, or with a
    turbofish, ``x.name::<T>(..)``, which tree-sitter parses as a
    ``generic_function`` around the ``field_expression``. Read as a bare
    name, the turbofish form bound to a same-file free fn of that name
    (hecs, 2026-10-03: ``world.reserve::<T>(1)`` → the test ``fn reserve``)."""
    if function.type == "generic_function":
        inner = function.child_by_field_name("function")
        return inner is not None and _is_dotted(inner)
    return function.type == "field_expression"


def _is_path_qualified(function: Node) -> bool:
    """Whether a callee is written with a ``::`` path — including one whose
    segments `_qualifier_segments` cannot read, such as the generic
    ``Option::<T>::deserialize`` (its head is a type, not an identifier)."""
    if function.type == "generic_function":
        inner = function.child_by_field_name("function")
        return inner is not None and _is_path_qualified(inner)
    return function.type == "scoped_identifier"


def _qualifier_segments(function: Node) -> list[str]:
    """``combined::mod1::module1`` → ``["combined", "mod1"]`` (sans name)."""
    if function.type == "scoped_identifier":
        segments = _path_segments(function)
        return segments[:-1]
    if function.type == "generic_function":
        inner = function.child_by_field_name("function")
        return _qualifier_segments(inner) if inner is not None else []
    return []


def _first_string(node: Node | None) -> str | None:
    if node is None:
        return None
    for child in _walk(node):
        if child.type == "string_literal":
            return _text(child).strip('"')
    return None


# ---------------------------------------------------------------- joining


#: ``std::env::var("X")`` / ``env::var_os("X")`` — the cross-layer join's
#: Rust end (M3's ``env:VAR`` nodes, now spanning Py + TF + JS + Go + Rust).
_ENV_FUNCS = {"var", "var_os"}


def _join(files: list[RustFile], crates: dict[str, str]) -> dict:
    """Assemble the layer bundle — the `tssource.join_facts` contract."""
    nodes: dict[str, dict] = {}
    module_edges: dict[tuple, list] = defaultdict(list)
    symbols: list[dict] = []
    known_files = {parsed.path for parsed in files}
    mod_map = _mod_tree(files, known_files)

    for parsed in files:
        mid = module_id(parsed.path)
        nodes[mid] = {"id": mid, "kind": "module", "path": parsed.path}

        declared_here = {m["name"] for m in parsed.mods}
        for entry in parsed.imports:
            root = entry["segments"][0]
            if root in _LOCAL_ROOTS or root in crates or root in declared_here:
                # The join raises in-repo edges from what calls actually
                # reach — see the module docstring.
                continue
            ext_id = f"ext:{root}"
            nodes.setdefault(ext_id, {"id": ext_id, "kind": "external", "name": root})
            module_edges[(mid, ext_id, "imports")].append(
                {"path": parsed.path, "line": entry["line"]}
            )

        for call in parsed.calls:
            if call["name"] in _ENV_FUNCS and call["path"][-1:] == ["env"] and call["first_str"]:
                env_id = f"env:{call['first_str']}"
                nodes.setdefault(
                    env_id, {"id": env_id, "kind": "env", "name": call["first_str"]}
                )
                module_edges[(mid, env_id, "env-read")].append(
                    {"path": parsed.path, "line": call["line"]}
                )

        for symbol in parsed.symbols:
            symbols.append({"id": f"{mid}.{symbol['qualname']}", "module": mid, **symbol})

    return {
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "module_edges": _edge_list(module_edges),
        "symbols": sorted(symbols, key=lambda s: s["id"]),
        "call_sites": _call_sites(files),
        "call_fallback": _call_fallback(files, crates, mod_map),
        "shared_qualnames": shared_qualnames(files),
        "cfg_twins": cfg_twins(files),
        "same_header_repeats": same_header_repeats(files),
        "files": files,
        "tests": sorted(
            (test for parsed in files for test in parsed.tests),
            key=lambda t: t["id"],
        ),
        "languages": ["rust"],
        "errors": [],
    }


def shared_qualnames(files: list[RustFile]) -> dict[str, list[tuple[int, int]]]:
    """Every symbol id two differently written ``impl`` headers mint in one
    file, with the ``(line, end_line)`` of each of its defs (ADR-163, C-180).

    :func:`_impl_type` names an impl block after its first type
    identifier, so ``impl Pointer for *const T`` and ``impl Pointer for
    *mut T`` both hang their ``distance`` off ``T``, and a trait impl and
    the inherent impl of one type share every method name they both
    declare. The node sits at the first def; the others are different
    functions with no node of their own. A qualname whose defs all carry
    the same header text — a cfg twin, the same item compiled under
    another configuration — is not listed: there the later def is the
    node's own code, as before. One whose defs are of two kinds (Rust's
    type and value namespaces allow ``struct B`` beside ``const B``) is
    listed whatever its headers: they are two items (C-182's residual).
    """
    out: dict[str, list[tuple[int, int]]] = {}
    for parsed in files:
        mid = module_id(parsed.path)
        kinds = {(s["qualname"], s["line"]): s["kind"] for s in parsed.symbols}
        for qualname, defs in parsed.defs.items():
            if len(defs) > 1 and (
                len({header for _, _, header in defs}) > 1
                or len({kinds.get((qualname, line)) for line, _, _ in defs}) > 1
            ):
                out[f"{mid}.{qualname}"] = sorted((line, end) for line, end, _ in defs)
    return out


def same_header_repeats(files: list[RustFile]) -> dict[str, dict[str, list[tuple[int, int]]]]:
    """By file, every id written two or more times with one header and one
    kind that is not a cfg twin (C-182's residual): some def carries no
    ``#[cfg]``, so lane A cannot say they are one item compiled two ways.
    In a crate that compiles this cannot occur; a file no crate compiles
    (memchr's ``benchmarks/haystacks``) writes it freely. Neither refused
    nor mapped: the node is the first def and what a later def holds is
    filed under it. Listed only so a record can name them.
    """
    shared = shared_qualnames(files)
    twins = {symbol_id for by_id in cfg_twins(files).values() for symbol_id in by_id}
    out: dict[str, dict[str, list[tuple[int, int]]]] = {}
    for parsed in files:
        mid = module_id(parsed.path)
        for qualname, defs in parsed.defs.items():
            symbol_id = f"{mid}.{qualname}"
            if len(defs) > 1 and symbol_id not in shared and symbol_id not in twins:
                out.setdefault(parsed.path, {})[symbol_id] = sorted(
                    (line, end) for line, end, _ in defs
                )
    return out


def cfg_twins(files: list[RustFile]) -> dict[str, dict[str, list[tuple[int, int]]]]:
    """Every cfg twin, by file: ``{path: {symbol id: [(line, end_line), …]}}``
    (ADR-165, C-182).

    One item written under two or more ``#[cfg]`` arms: an id with two or
    more defs in one file whose headers are all the same, whose kinds are
    all the same, and each of which a ``#[cfg(…)]`` gates (on the item or
    an enclosing ``mod``/``impl``). They are one node, at the first def;
    lane A reads no features, so it cannot say which arm the build
    compiles, and lane B names the one it did.

    The gate is required because a same-header repeat is not always one
    item: Rust keeps types and values in separate namespaces (``struct
    B`` beside ``const B``), and a file no crate compiles — memchr's
    ``benchmarks/haystacks`` copy of the standard library — repeats names
    freely. Neither is listed; each stays what it was.
    """
    out: dict[str, dict[str, list[tuple[int, int]]]] = {}
    for parsed in files:
        mid = module_id(parsed.path)
        kinds = {(s["qualname"], s["line"]): s["kind"] for s in parsed.symbols}
        for qualname, defs in parsed.defs.items():
            if (
                len(defs) > 1
                and len({header for _, _, header in defs}) == 1
                and len({kinds.get((qualname, line)) for line, _, _ in defs}) == 1
                and all((qualname, line) in parsed.cfg_gated for line, _, _ in defs)
            ):
                out.setdefault(parsed.path, {})[f"{mid}.{qualname}"] = sorted(
                    (line, end) for line, end, _ in defs
                )
    return out


def _mod_tree(files: list[RustFile], known_files: set[str]) -> dict[tuple[str, str], str]:
    """``(declaring file, mod name) → child file``, by rustc's own rules.

    ``mod x;`` in a module-root file (``lib.rs``, ``main.rs``, ``mod.rs``,
    and target roots generally share those names) maps to ``x.rs`` or
    ``x/mod.rs`` beside it; in any other file ``name.rs``, to
    ``name/x.rs`` or ``name/x/mod.rs``. A ``#[path]`` attribute overrides,
    resolved against the declaring file's directory. A candidate that is
    not a discovered file simply produces no mapping — the fallback
    under-approximates, never guesses (ADR-031).
    """
    tree: dict[tuple[str, str], str] = {}
    for parsed in files:
        pure = PurePosixPath(parsed.path)
        parent = pure.parent
        is_root = pure.name in ("lib.rs", "main.rs", "mod.rs")
        for mod in parsed.mods:
            candidates: list[PurePosixPath] = []
            if mod["path_attr"]:
                raw = PurePosixPath(mod["path_attr"])
                candidates.append(parent / raw)
            else:
                base = parent if is_root else parent / pure.stem
                candidates.append(base / f"{mod['name']}.rs")
                candidates.append(base / mod["name"] / "mod.rs")
            for candidate in candidates:
                normal = str(PurePosixPath(*[p for p in candidate.parts if p != "."]))
                if normal in known_files:
                    tree[(parsed.path, mod["name"])] = normal
                    break
    return tree


def _call_sites(files: list[RustFile]) -> list:
    """Lane A's Rust call sites, in evidence-IR shape (ADR-029)."""
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


def _call_fallback(
    files: list[RustFile],
    crates: dict[str, str],
    mod_map: dict[tuple[str, str], str],
) -> dict[tuple[str, int, str], tuple[str, int]]:
    """Lane A's own resolutions, keyed by call site (ADR-031).

    Rust is tractable the way Go is, through a different door: the module
    system's file mapping is deterministic, so a qualified path resolves
    segment-by-segment through ``mod`` declarations, a crate name resolves
    to its lib target, and a ``use`` alias expands to the path it named.
    Deliberately under-approximated, as every fallback is: method calls on
    values (``x.unwrap()``), ``crate::``/``super::`` chains (whose root
    depends on which cargo target is compiling the file), glob imports,
    and re-exports are all left to lane B.

    Four abstentions since C-72 (2026-09-03), ADR-098's rule in Rust's
    shape — when the path's head does not single out a declaration, say
    nothing rather than pick: a path-qualified call whose path could not
    be read (``Option::<T>::deserialize``) is never looked up as a bare
    name; a bare name never binds to a ``method`` (Rust needs a path or a
    receiver to reach one); ``Trait::method(..)`` is dispatch and is left
    to lane B; and ``Type::name`` with more than one declaration under
    that qualname in the file (two ``impl X for Type { fn fmt }`` blocks)
    is an overload set. The tail names the first three ``path-call``.
    """
    by_file: dict[str, RustFile] = {parsed.path: parsed for parsed in files}
    where: dict[tuple[str, str], tuple[str, int]] = {}
    kinds: dict[tuple[str, int], str] = {}
    declared: dict[tuple[str, str], int] = {}
    traits: set[tuple[str, str]] = set()
    for parsed in files:
        traits.update((parsed.path, name) for name in parsed.traits)
        for symbol in parsed.symbols:
            where.setdefault(
                (parsed.path, symbol["qualname"]), (parsed.path, symbol["line"])
            )
            kinds.setdefault((parsed.path, symbol["line"]), symbol["kind"])
            # By the qualname before its ordinal (ADR-174): `Type::name`
            # declared in two impl blocks is still an overload set.
            key = (parsed.path, _base_qualname(symbol["qualname"]))
            declared[key] = declared.get(key, 0) + 1

    def resolve_segments(start: str, segments: list[str], name: str) -> tuple[str, int] | None:
        """Walk *segments* from file *start*, then look *name* up there."""
        at = start
        for segment in segments:
            if (at, segment) in mod_map:
                at = mod_map[(at, segment)]
            elif segment in crates and crates[segment] in by_file:
                at = crates[segment]
            elif (at, segment) in where and where[(at, segment)][0] == at:
                # `Type::assoc()` — the segment is a type in the current
                # file; the method lives under its qualname. Not a trait
                # (dispatch), and not a name two impl blocks both declare.
                if (at, segment) in traits:
                    return None
                if declared.get((at, f"{segment}.{name}"), 0) > 1:
                    return None
                return where.get((at, f"{segment}.{name}"))
            else:
                return None
        return where.get((at, name))

    fallback: dict[tuple[str, int, str], tuple[str, int]] = {}
    for parsed in files:
        aliases = {entry["alias"]: entry["segments"] for entry in parsed.imports}
        for call in parsed.calls:
            if call["dotted"]:
                continue  # a value's method: needs a type checker (lane B)
            target: tuple[str, int] | None = None
            path = call["path"]
            if path and path[0] in _LOCAL_ROOTS:
                target = None  # target-dependent root; lane B's job
            elif path:
                expanded = aliases.get(path[0])
                if expanded is not None and expanded[0] not in _LOCAL_ROOTS:
                    path = expanded + path[1:]
                target = resolve_segments(parsed.path, path, call["name"])
            elif call.get("qualified"):
                target = None  # a path nobody could read; not a bare name
            else:
                target = where.get((parsed.path, call["name"]))
                if target is None:
                    expanded = aliases.get(call["name"])
                    if expanded is not None and expanded[0] not in _LOCAL_ROOTS:
                        target = resolve_segments(
                            parsed.path, expanded[:-1], expanded[-1]
                        )
                if target is not None and kinds.get(target) == "method":
                    target = None  # a bare name never reaches a method
            if target is None:
                continue
            if target == (parsed.path, call["line"]):
                continue  # a declaration is not a call of itself
            if (kinds.get(target) == "macro") != bool(call.get("macro")):
                # `format!(..)` never invokes `fn format`, and `twice(..)`
                # never invokes `macro_rules! twice` (O7's twelve
                # contradictions on dagger's SDK, all this shape).
                continue
            fallback[(parsed.path, call["line"], call["name"])] = target
    return fallback


def collect_rust_tests(files: list[RustFile], symbol_edges: list[dict]) -> list[dict]:
    """Rust test inventory with reach, measured over the join's edges.

    Reach is the closure over ``calls`` edges from the test function, the
    same rule every other framework's reach uses (ADR-007), so a
    `cargo-test` row means what a pytest row means.
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
        by_name = {s["name"]: s["qualname"] for s in parsed.symbols}
        for test in parsed.tests:
            symbol_id = f"{mid}.{by_name.get(test['name'], test['name'])}"
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
