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

from hobbes.extract.discover import SKIPPED_DIR_NAMES
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
                if child.name not in _RUST_SKIPPED and not child.name.startswith("."):
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
                if child.name not in _RUST_SKIPPED and not child.name.startswith("."):
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
    for absolute in iter_rust_files(repo_root):
        rel = absolute.relative_to(repo_root).as_posix()
        try:
            source = absolute.read_bytes()
        except OSError:
            continue
        files.append(_parse_file(rel, source))
    if not files:
        return None
    return _join(files, local_crate_names(repo_root))


# ---------------------------------------------------------------- parsing


def _text(node: Node) -> str:
    return (node.text or b"").decode("utf-8", "replace")


def _parse_file(rel: str, source: bytes) -> RustFile:
    root = _PARSER.parse(source).root_node
    parsed = RustFile(path=rel)
    _walk_items(root, parsed, prefix="")

    for symbol in parsed.symbols:
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


def _walk_items(container: Node, parsed: RustFile, prefix: str, in_impl: bool = False):
    """Collect declarations, recursing into mod and impl bodies only.

    Nested *functions* are not architecture (the gosource rule), but a
    ``#[cfg(test)] mod tests`` block is where Rust keeps its unit tests,
    and an ``impl`` block is where it keeps its methods — stopping at the
    top level would make both invisible. *prefix* carries the dotted
    qualname path (``tests.test_add``, ``Counter.incr``).
    """
    pending_attrs: list[Node] = []
    for node in container.children:
        if node.type == "attribute_item":
            pending_attrs.append(node)
            continue
        attrs, pending_attrs = pending_attrs, []

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
                _walk_items(body, parsed, _dotted(prefix, name))
        elif node.type == "impl_item":
            type_name = _impl_type(node)
            body = _child_of_type(node, "declaration_list")
            if body is not None:
                _walk_items(
                    body,
                    parsed,
                    _dotted(prefix, type_name) if type_name else prefix,
                    in_impl=True,
                )
        elif node.type == "function_item":
            name = _child_text(node, "identifier")
            if not name:
                continue
            kind = "method" if in_impl else "function"
            parsed.symbols.append(
                _symbol(name, _dotted(prefix, name), kind, node)
                | {"is_test": _is_test_attr(attrs)}
            )
        elif node.type in ("struct_item", "enum_item", "trait_item", "union_item"):
            name = _child_text(node, "type_identifier")
            if name:
                parsed.symbols.append(_symbol(name, _dotted(prefix, name), "type", node))
        elif node.type == "type_item":
            name = _child_text(node, "type_identifier")
            if name:
                parsed.symbols.append(_symbol(name, _dotted(prefix, name), "type", node))
        elif node.type in ("const_item", "static_item"):
            name = _child_text(node, "identifier")
            if name:
                parsed.symbols.append(_symbol(name, _dotted(prefix, name), "const", node))
        elif node.type == "macro_definition":
            name = _child_text(node, "identifier")
            if name:
                parsed.symbols.append(_symbol(name, _dotted(prefix, name), "macro", node))


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
                    dotted=function.type == "field_expression",
                    scope=_enclosing(symbols, node.start_point.row + 1),
                    first_str=_first_string(node.child_by_field_name("arguments")),
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
) -> dict:
    return {
        "name": _text(terminal),
        "path": path,
        "dotted": dotted,
        "line": terminal.start_point.row + 1,
        "col": terminal.start_point.column,
        "scope": scope,
        "first_str": first_str,
        # `name!(...)`: the callee is a macro and can only be one — a
        # function of the same name in scope is not what is invoked.
        "macro": macro,
    }


def _token_tree_calls(tree: Node, symbols: list[dict]) -> list[dict]:
    """Call-shape detection inside an unparsed macro body (ADR-040 §4).

    An identifier immediately followed by a ``(``-delimited token tree is
    recorded as a call site; the ``::``-joined identifiers before it are
    its path, a ``.`` before it marks a method call. Anything else in the
    token soup is left alone. The shape can lie — and a lying shape
    produces no edge, because nothing resolves at it.
    """
    found: list[dict] = []
    children = tree.children
    for at, node in enumerate(children):
        if node.type != "identifier":
            continue
        nxt = children[at + 1] if at + 1 < len(children) else None
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
        "files": files,
        "tests": sorted(
            (test for parsed in files for test in parsed.tests),
            key=lambda t: t["id"],
        ),
        "languages": ["rust"],
        "errors": [],
    }


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
    """
    by_file: dict[str, RustFile] = {parsed.path: parsed for parsed in files}
    where: dict[tuple[str, str], tuple[str, int]] = {}
    kinds: dict[tuple[str, int], str] = {}
    for parsed in files:
        for symbol in parsed.symbols:
            where.setdefault(
                (parsed.path, symbol["qualname"]), (parsed.path, symbol["line"])
            )
            kinds.setdefault((parsed.path, symbol["line"]), symbol["kind"])

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
                # file; the method lives under its qualname.
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
            else:
                target = where.get((parsed.path, call["name"]))
                if target is None:
                    expanded = aliases.get(call["name"])
                    if expanded is not None and expanded[0] not in _LOCAL_ROOTS:
                        target = resolve_segments(
                            parsed.path, expanded[:-1], expanded[-1]
                        )
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
