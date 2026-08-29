"""Lane A for Java: structure, symbols, and call *sites* (ADR-096).

The sixth syntax provider, on the `gosource.py` / `rustsource.py`
contract — same bundle shape, same division of labour, so the graph
builder and the range join need no Java-specific code (P7).

**Why Java needs a lane A at all:** the J.M0 spike measured
`syntax_kind` on scip-java's output the way ADR-037/ADR-040 measured
the other three indexers; the number is in ADR-096. Nothing separates a
call from a mention but a syntax walk, so the walk is mandatory.

**What Java adds that no earlier language forced** (ADR-096):

- **Overloads.** One name, several declarations. Symbol ids must stay
  unique, so the first declaration of a qualname keeps it and each later
  one carries an ordinal suffix (``Outer.helper``, ``Outer.helper~2``);
  the ``name`` field is the bare name either way, which is what a call
  site spells. The fallback resolver **abstains** when a name it would
  bind has more than one declaration in the scope it resolved to —
  choosing an overload needs argument types, which is lane B's job, and
  a wrong guess would be a false edge (ADR-007) *and* a false lane
  disagreement on every overloaded call.
- **Nested types** are symbols with dotted qualnames (``Outer.Inner.go``);
  **anonymous classes and lambdas** are not — their bodies attribute to
  the enclosing declaration, the closure rule every provider follows
  (C-9's floor, C-58's face). An anonymous class's *methods* are still
  recorded as local bindings with the body's extent, so a call of one
  reads `local-binding` in the tail rather than unknown (ADR-046).
- **An import names a type, and a type is a file** — Java's own rule
  (one public top-level type per file, named after it). So unlike Go and
  Rust, lane A *can* emit in-repo ``imports`` edges precisely: an
  ``import a.b.C;`` whose ``a/b/C.java`` is exactly one discovered file
  is an edge to it. Same-package references need no import statement,
  so the join still raises most module edges from calls; Java files
  therefore sit in the lane-agreement exclusion with Go and Rust.
  Packages the repo does not declare become ``ext:<package>`` nodes.
- **Constructors** are ``method`` symbols named after their type; a
  ``new T(..)`` site is recorded at ``T`` under the name ``T``, and the
  helper maps scip-java's ``<init>`` descriptor back to the type name so
  the two lanes meet (``terminalName``, ADR-096).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import tree_sitter_java
from tree_sitter import Language, Node, Parser

from hobbes.extract.discover import SKIPPED_DIR_NAMES
from hobbes.extract.graph import _edge_list

_PARSER = Parser(Language(tree_sitter_java.language()))

#: Directories pruned in addition to the shared set: Maven's and
#: Gradle's build output, IntelliJ's, and the Gradle daemon's.
_JAVA_SKIPPED = SKIPPED_DIR_NAMES | {"target", "build", "out", ".gradle"}

#: Declarations that open a type. ``annotation_type_declaration`` is
#: ``@interface``.
_TYPE_DECLS = {
    "class_declaration",
    "interface_declaration",
    "enum_declaration",
    "record_declaration",
    "annotation_type_declaration",
}

#: JUnit's test-method annotations, 4 and 5 alike (the ``@Test`` of
#: either; the Jupiter family beside it). An annotation is an attribute
#: the way ``#[test]`` is (ADR-040 decision 7): syntax, not pack
#: territory — a route pack (Spring) stays a pack.
_TEST_ANNOTATIONS = {
    "Test", "ParameterizedTest", "RepeatedTest", "TestFactory", "TestTemplate",
}


@dataclass
class JavaFile:
    """One parsed ``.java`` file, in the shape the join consumes."""

    path: str
    package: str = ""
    imports: list[dict] = field(default_factory=list)
    symbols: list[dict] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    tests: list[dict] = field(default_factory=list)
    #: Simple names of the top-level types this file declares.
    top_types: list[str] = field(default_factory=list)
    #: Methods declared inside anonymous class bodies — an enum
    #: constant's body, a ``new Runnable() {..}`` — as ``(name, start,
    #: end)`` with the body's extent (ADR-046): below the modelled
    #: vocabulary, seen, so a call of one classifies `local-binding`.
    local_bindings: list[tuple[str, int, int]] = field(default_factory=list)


def has_java_files(repo_root: Path) -> bool:
    """Cheap detection: does this repo contain Java at all?"""
    return any(True for _ in iter_java_files(Path(repo_root)))


def iter_java_files(repo_root: Path):
    """Repo-relative ``.java`` paths, pruned like every other discovery."""
    stack = [Path(repo_root)]
    while stack:
        directory = stack.pop()
        try:
            children = sorted(directory.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_dir():
                if child.name not in _JAVA_SKIPPED and not child.name.startswith("."):
                    stack.append(child)
            elif child.suffix == ".java":
                yield child


def module_id(path: str) -> str:
    """Repo-relative path sans ``.java`` — the ADR-021 id rule, unchanged."""
    pure = PurePosixPath(path)
    return str(pure.with_suffix("")) if pure.suffix == ".java" else str(pure)


def extract_java(repo_root: Path) -> dict | None:
    """The Java layer for *repo_root*, or ``None`` when it has no Java.

    Never raises on a malformed file: tree-sitter is error-tolerant by
    design (§3.1), and a file that will not parse yields whatever the
    walk could see.
    """
    repo_root = Path(repo_root).resolve()
    files: list[JavaFile] = []
    for absolute in iter_java_files(repo_root):
        rel = absolute.relative_to(repo_root).as_posix()
        try:
            source = absolute.read_bytes()
        except OSError:
            continue
        files.append(_parse_file(rel, source))
    if not files:
        return None
    return _join(files)


# ---------------------------------------------------------------- parsing


def _text(node: Node) -> str:
    return (node.text or b"").decode("utf-8", "replace")


def _parse_file(rel: str, source: bytes) -> JavaFile:
    root = _PARSER.parse(source).root_node
    parsed = JavaFile(path=rel)
    for node in root.children:
        if node.type == "package_declaration":
            parsed.package = _dotted_name(node)
        elif node.type == "import_declaration":
            entry = _import_entry(node)
            if entry is not None:
                parsed.imports.append(entry)
        elif node.type in _TYPE_DECLS:
            _walk_type(node, parsed, prefix="")

    _suffix_overloads(parsed.symbols)

    for symbol in parsed.symbols:
        if symbol.pop("is_test", False):
            parsed.tests.append(
                {
                    "id": f"{rel}::{symbol['qualname']}",
                    "name": symbol["name"],
                    "qualname": symbol["qualname"],
                    "file": rel,
                    "line": symbol["line"],
                    "framework": "junit",
                }
            )

    parsed.calls = _calls(root, parsed.symbols)
    parsed.local_bindings = _anonymous_members(root)
    return parsed


def _anonymous_members(root: Node) -> list[tuple[str, int, int]]:
    """Methods of anonymous classes, with the body's line extent.

    jsoup's ``HtmlTreeBuilderState`` is an enum whose constants each
    carry a body with private helpers (``anythingElse(t, tb)``), and
    scip-java gives such members ``local`` symbols — the 44 sites the
    first real ingest could not classify. They are bound below the
    modelled vocabulary in the same file (C-9), and a bare call of one
    inside the body is an observation, not a guess.
    """
    out: list[tuple[str, int, int]] = []
    for node in _walk(root):
        if node.type == "object_creation_expression" or node.type == "enum_constant":
            body = _child_of_type(node, "class_body")
            if body is None:
                continue
            for member in body.children:
                if member.type == "method_declaration":
                    name = _child_text(member, "identifier")
                    if name:
                        out.append((name, body.start_point.row + 1, body.end_point.row + 1))
    return out


def _dotted_name(node: Node) -> str:
    """The ``a.b.c`` spelled by a package/import declaration's identifier
    chain (``scoped_identifier`` nests leftward)."""
    for child in node.children:
        if child.type in ("scoped_identifier", "identifier"):
            return _text(child)
    return ""


def _import_entry(node: Node) -> dict | None:
    """``import a.b.C;`` → segments; ``import static a.b.C.m;`` binds
    ``m``; a wildcard (``a.b.*``) is recorded with ``wildcard`` set and
    binds no name — resolving it needs the target's member list, which is
    lane B's job (the Rust glob rule)."""
    static = any(child.type == "static" for child in node.children)
    wildcard = any(child.type == "asterisk" for child in node.children)
    name = _dotted_name(node)
    if not name:
        return None
    segments = name.split(".")
    return {
        "segments": segments,
        "static": static,
        "wildcard": wildcard,
        # What the statement binds in this file: a type's simple name, or
        # a static member's name. Nothing, for a wildcard.
        "alias": None if wildcard else segments[-1],
        "line": node.start_point.row + 1,
    }


def _walk_type(decl: Node, parsed: JavaFile, prefix: str):
    """One type declaration: its symbol, its members, its nested types.

    Anonymous classes (an ``object_creation_expression`` with a body) and
    local classes inside method bodies are not walked: they are below the
    modelled vocabulary (C-9), and their calls attribute to the enclosing
    declaration like a closure's do.
    """
    name = _child_text(decl, "identifier")
    if not name:
        return
    qualname = _dotted(prefix, name)
    if not prefix:
        parsed.top_types.append(name)
    parsed.symbols.append(
        _symbol(name, qualname, "type", decl)
        # Whether a name not declared here may still be *inherited*: an
        # `extends`/`implements` clause, or the implicit supertypes of an
        # enum (`valueOf`, `values`) and a record. The fallback stops at
        # such a type rather than walking outward (ADR-096: jsoup's
        # `Response.cookie(..)` bound to the outer class's `cookie` where
        # Java binds the inherited one).
        | {"has_supertypes": decl.type in ("enum_declaration", "record_declaration")
           or any(c.type in ("superclass", "super_interfaces") for c in decl.children)}
    )
    body = None
    for child in decl.children:
        if child.type in ("class_body", "interface_body", "enum_body",
                          "annotation_type_body"):
            body = child
            break
    if body is None:
        return
    members = list(body.children)
    # An enum keeps its methods under `enum_body_declarations`.
    for child in body.children:
        if child.type == "enum_body_declarations":
            members.extend(child.children)
    for member in members:
        if member.type in _TYPE_DECLS:
            _walk_type(member, parsed, qualname)
        elif member.type == "method_declaration":
            mname = _child_text(member, "identifier")
            if mname:
                parsed.symbols.append(
                    _symbol(mname, _dotted(qualname, mname), "method", member)
                    | {"is_test": _is_test_method(member), "arity": _arity(member)}
                )
        elif member.type in ("constructor_declaration", "compact_constructor_declaration"):
            # Named after the type, so `new T(..)` and `this(..)` can be
            # bound to it by name; scip-java calls it `<init>` and the
            # helper maps that back (ADR-096).
            parsed.symbols.append(
                _symbol(name, _dotted(qualname, name), "method", member)
                | {"arity": _arity(member)}
            )


def _suffix_overloads(symbols: list[dict]) -> None:
    """Keep symbol ids unique across overloads: the first declaration of
    a qualname keeps it, later ones get ``~2``, ``~3``, … in source
    order. Deterministic, and the bare ``name`` survives on every one."""
    seen: dict[str, int] = {}
    for symbol in symbols:
        base = symbol["qualname"]
        n = seen.get(base, 0) + 1
        seen[base] = n
        if n > 1:
            symbol["qualname"] = f"{base}~{n}"
        symbol["overload_of"] = base if n > 1 else None
    for symbol in symbols:
        if symbol.pop("overload_of", None) is None and seen.get(symbol["qualname"], 1) > 1:
            pass  # the first declaration keeps the bare qualname


def _arity(decl: Node) -> tuple[int, bool]:
    """``(fixed parameter count, varargs?)`` of a method or constructor —
    the one thing about a signature syntax can read, and enough to keep
    the fallback off an overload the argument count rules out (jsoup:
    `error(t, "..")` bound to the local `error(String)` where the
    superclass's two-argument overload is the callee)."""
    params = _child_of_type(decl, "formal_parameters")
    if params is None:
        return (0, False)  # a compact record constructor: the record's own
    fixed = sum(1 for c in params.children if c.type == "formal_parameter")
    spread = any(c.type == "spread_parameter" for c in params.children)
    return (fixed, spread)


def _args(call: Node) -> int:
    arguments = call.child_by_field_name("arguments")
    return sum(1 for c in arguments.named_children) if arguments is not None else 0


def _dotted(prefix: str, name: str) -> str:
    return f"{prefix}.{name}" if prefix else name


def _symbol(name: str, qualname: str, kind: str, node: Node) -> dict:
    # Position is the identifier's line (the oracle lane's convention:
    # never an annotation's or a modifier's line above it).
    ident = node.child_by_field_name("name")
    line = (ident or node).start_point.row + 1
    return {
        "name": name,
        "qualname": qualname,
        "kind": kind,
        "line": line,
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


def _is_test_method(method: Node) -> bool:
    """``@Test`` and the Jupiter family, by the annotation's simple name
    (``@org.junit.Test`` spells the same last segment)."""
    modifiers = _child_of_type(method, "modifiers")
    if modifiers is None:
        return False
    for child in modifiers.children:
        if child.type in ("marker_annotation", "annotation"):
            name = child.child_by_field_name("name")
            if name is not None and _text(name).split(".")[-1] in _TEST_ANNOTATIONS:
                return True
    return False


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


def _enclosing_type(symbols: list[dict], line: int) -> str | None:
    best = None
    for symbol in symbols:
        if symbol["kind"] == "type" and symbol["line"] <= line <= symbol["end_line"]:
            best = symbol["qualname"]
    return best


def _calls(root: Node, symbols: list[dict]) -> list[dict]:
    """Every call site: method invocations, constructor calls, and
    explicit ``this(..)``/``super(..)`` invocations.

    Position is the **callee identifier's** (the ADR-029 correction):
    scip-java reports the occurrence of the name, so the join keys on
    where the name is. A method reference (``Foo::bar``) is a *use*, not
    a call — no site is recorded; the join draws it as ``uses`` from lane
    B's reference alone. Annotations are not calls either.
    """
    found: list[dict] = []
    for node in _walk(root):
        if node.type == "method_invocation":
            name = node.child_by_field_name("name")
            if name is None:
                continue
            receiver = node.child_by_field_name("object")
            via_new = _creation_type_path(receiver)
            found.append(
                _call(
                    name,
                    path=via_new if via_new is not None else _qualifier_segments(receiver),
                    dotted=receiver is not None,
                    scope=_enclosing(symbols, name.start_point.row + 1),
                    first_str=_first_string(node.child_by_field_name("arguments")),
                )
                | {"via_new": via_new is not None, "args": _args(node)}
            )
        elif node.type == "object_creation_expression":
            if _child_of_type(node, "class_body") is not None:
                # `new T() {..}`: what is constructed is the anonymous
                # subclass, whose constructor has no line; scip-java
                # references the *type* here, which the join draws as
                # `uses`. Not a call site (ADR-096).
                continue
            type_node = node.child_by_field_name("type")
            if type_node is None:
                continue
            terminal = _type_terminal(type_node)
            if terminal is None:
                continue
            found.append(
                _call(
                    terminal,
                    path=_type_qualifier(type_node),
                    dotted=False,
                    scope=_enclosing(symbols, terminal.start_point.row + 1),
                    first_str=_first_string(node.child_by_field_name("arguments")),
                    ctor=True,
                )
                | {"args": _args(node)}
            )
        elif node.type == "explicit_constructor_invocation":
            keyword = next((c for c in node.children if c.type in ("this", "super")), None)
            if keyword is None:
                continue
            line = keyword.start_point.row + 1
            owner = _enclosing_type(symbols, line)
            if owner is None:
                continue
            found.append(
                {
                    # `this(..)` calls a sibling constructor: the callee
                    # is named after the enclosing type. `super(..)` is
                    # left to lane B — the superclass is a resolution.
                    "name": owner.rsplit(".", 1)[-1] if keyword.type == "this" else "super",
                    "path": [],
                    "dotted": False,
                    "line": line,
                    "col": keyword.start_point.column,
                    "scope": _enclosing(symbols, line),
                    "first_str": _first_string(node.child_by_field_name("arguments")),
                    "ctor": True,
                    "explicit": keyword.type,
                    "via_new": False,
                    "args": _args(node),
                }
            )
    return found


def _call(
    terminal: Node,
    path: list[str],
    dotted: bool,
    scope: str | None,
    first_str: str | None,
    ctor: bool = False,
) -> dict:
    return {
        "name": _text(terminal),
        "path": path,
        "dotted": dotted,
        "line": terminal.start_point.row + 1,
        "col": terminal.start_point.column,
        "scope": scope,
        "first_str": first_str,
        "ctor": ctor,
        "explicit": None,
        "via_new": False,
        "args": 0,
    }


def _qualifier_segments(receiver: Node | None) -> list[str]:
    """A receiver that is a bare name or a dotted chain of names
    (``Outer``, ``a.b.C``) → its segments; an expression (``x.foo()``'s
    ``foo()`` result, ``new T()``, ``this``) → ``[]``. The O4 rule: a name
    can be a type, an expression cannot."""
    if receiver is None:
        return []
    if receiver.type == "identifier":
        return [_text(receiver)]
    if receiver.type == "field_access":
        inner = receiver.child_by_field_name("object")
        head = _qualifier_segments(inner)
        fld = receiver.child_by_field_name("field")
        if head and fld is not None and fld.type == "identifier":
            return head + [_text(fld)]
        return []
    if receiver.type == "scoped_identifier":
        return _text(receiver).split(".")
    return []


def _creation_type_path(receiver: Node | None) -> list[str] | None:
    """``new T(..).m()`` — the one expression receiver whose type is
    syntactically certain: the segments of ``T``, or None for anything
    else. The O4 rule says an expression cannot be a *type name*; a
    creation expression's type is not a guess, it is spelled."""
    if receiver is None or receiver.type != "object_creation_expression":
        return None
    if _child_of_type(receiver, "class_body") is not None:
        return None  # an anonymous class: its type is the anonymous one
    type_node = receiver.child_by_field_name("type")
    terminal = _type_terminal(type_node) if type_node is not None else None
    if terminal is None:
        return None
    return _type_qualifier(type_node) + [_text(terminal)]


def _type_terminal(type_node: Node) -> Node | None:
    """``new a.b.Foo<T>(..)`` → the ``Foo`` identifier node."""
    if type_node.type == "type_identifier":
        return type_node
    if type_node.type == "generic_type":
        for child in type_node.children:
            if child.type in ("type_identifier", "scoped_type_identifier"):
                return _type_terminal(child)
        return None
    if type_node.type == "scoped_type_identifier":
        last = None
        for child in type_node.children:
            if child.type == "type_identifier":
                last = child
        return last
    return None


def _type_qualifier(type_node: Node) -> list[str]:
    if type_node.type == "generic_type":
        for child in type_node.children:
            if child.type in ("type_identifier", "scoped_type_identifier"):
                return _type_qualifier(child)
        return []
    if type_node.type == "scoped_type_identifier":
        segments = [
            _text(c) for c in _walk(type_node)
            if c.type in ("identifier", "type_identifier")
        ]
        return segments[:-1]
    return []


def _first_string(node: Node | None) -> str | None:
    if node is None:
        return None
    for child in _walk(node):
        if child.type == "string_literal":
            return _text(child).strip('"')
    return None


# ---------------------------------------------------------------- joining


def _join(files: list[JavaFile]) -> dict:
    """Assemble the layer bundle — the `tssource.join_facts` contract."""
    nodes: dict[str, dict] = {}
    module_edges: dict[tuple, list] = defaultdict(list)
    symbols: list[dict] = []
    fqn_map = fqn_to_file(files)
    packages = {parsed.package for parsed in files}

    for parsed in files:
        mid = module_id(parsed.path)
        nodes[mid] = {"id": mid, "kind": "module", "path": parsed.path}

        for entry in parsed.imports:
            target = _import_target(entry, fqn_map)
            if target is not None:
                if target != parsed.path:
                    module_edges[(mid, module_id(target), "imports")].append(
                        {"path": parsed.path, "line": entry["line"]}
                    )
                continue
            package = _import_package(entry, fqn_map)
            if package in packages:
                # A repo package whose member this import names but no
                # file declares (a second top-level type, a generated
                # class): an in-repo target lane A cannot place — left to
                # the join, never an `ext:` node for the repo's own code.
                continue
            ext_id = f"ext:{package}"
            nodes.setdefault(ext_id, {"id": ext_id, "kind": "external", "name": package})
            module_edges[(mid, ext_id, "imports")].append(
                {"path": parsed.path, "line": entry["line"]}
            )

        for call in parsed.calls:
            if call["name"] == "getenv" and call["path"][-1:] == ["System"] and call["first_str"]:
                env_id = f"env:{call['first_str']}"
                nodes.setdefault(
                    env_id, {"id": env_id, "kind": "env", "name": call["first_str"]}
                )
                module_edges[(mid, env_id, "env-read")].append(
                    {"path": parsed.path, "line": call["line"]}
                )

        for symbol in parsed.symbols:
            symbols.append({"id": f"{mid}.{symbol['qualname']}", "module": mid, **symbol})

    fallback, overloads, inherited = _call_fallback(files, fqn_map)
    return {
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "module_edges": _edge_list(module_edges),
        "symbols": sorted(symbols, key=lambda s: s["id"]),
        "call_sites": _call_sites(files),
        "call_fallback": fallback,
        # The sites the fallback abstained on because the name has more
        # than one declaration in the scope it resolved to (an overload
        # set, a constructor pair): the tail names them `overload-set`.
        "overload_sites": overloads,
        "inherited_sites": inherited,
        # What each file's imports bind, for the tail: a static member's
        # name (`assertEquals`) or a type's (`ArrayList`, which `new
        # ArrayList<>()` spells as a bare site). Lane A's own parse.
        "import_bindings": {
            parsed.path: frozenset(e["alias"] for e in parsed.imports if e["alias"])
            for parsed in files
            if any(e["alias"] for e in parsed.imports)
        },
        "local_bindings": {
            parsed.path: tuple(parsed.local_bindings)
            for parsed in files
            if parsed.local_bindings
        },
        "files": files,
        "tests": sorted(
            (test for parsed in files for test in parsed.tests),
            key=lambda t: t["id"],
        ),
        "languages": ["java"],
        "errors": [],
    }


def fqn_to_file(files: list[JavaFile]) -> dict[str, str | None]:
    """``package.Type`` → the one file declaring it, or ``None`` when two
    do (a duplicated source root, a test double under the same package):
    unattributed rather than guessed, the C-28 rule at lane A."""
    out: dict[str, str | None] = {}
    for parsed in files:
        for name in parsed.top_types:
            fqn = f"{parsed.package}.{name}" if parsed.package else name
            out[fqn] = None if fqn in out else parsed.path
    return out


def _import_target(entry: dict, fqn_map: dict[str, str | None]) -> str | None:
    """The repo file an import names, if exactly one does.

    ``import a.b.C`` names the type ``a.b.C``; ``import static a.b.C.m``
    names a member of it; ``import a.b.C.Inner`` a nested type of it. The
    longest prefix that is a declared top-level type wins.
    """
    segments = entry["segments"]
    for cut in range(len(segments), 0, -1):
        fqn = ".".join(segments[:cut])
        if fqn in fqn_map:
            return fqn_map[fqn]
    return None


def _import_package(entry: dict, fqn_map: dict[str, str | None]) -> str:
    """The package an import reaches into: everything before the type.
    A static import drops the member too; a wildcard has no type."""
    segments = entry["segments"]
    if entry["wildcard"]:
        return ".".join(segments)
    drop = 2 if entry["static"] else 1
    # A capitalised segment is a type by convention; walk back to the
    # package prefix so `import a.b.C.Inner` reports package `a.b`.
    head = segments[:-drop] if len(segments) > drop else segments[:1]
    while len(head) > 1 and head[-1][:1].isupper():
        head = head[:-1]
    return ".".join(head)


def _call_sites(files: list[JavaFile]) -> list:
    """Lane A's Java call sites, in evidence-IR shape (ADR-029)."""
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
        if call["explicit"] != "super"
    ]


def _call_fallback(
    files: list[JavaFile], fqn_map: dict[str, str | None]
) -> tuple[dict[tuple[str, int, str], tuple[str, int]], set[tuple[str, int, str]], set[tuple[str, int, str]]]:
    """Lane A's own resolutions, keyed by call site (ADR-031).

    Java is tractable where a name is a *type*: a bare name in the
    enclosing type chain, an imported type, a same-package sibling file,
    or a fully qualified name each map to one file by the language's own
    rules. Deliberately under-approximated: a method call on a value
    (``x.foo()``), an inherited or interface method, an overload set with
    more than one candidate, a wildcard import, ``super(..)`` — all left
    to lane B. Abstaining on overloads is the join-safety rule ADR-096
    states: a guessed overload is a false edge and a false disagreement.
    """
    by_file = {parsed.path: parsed for parsed in files}
    # (file, owner qualname, member name) -> [(file, line, arity)]
    members: dict[tuple[str, str, str], list[tuple[str, int, tuple[int, bool]]]] = defaultdict(list)
    # (file, simple type name) -> [type qualname]
    types_in: dict[tuple[str, str], list[str]] = defaultdict(list)
    # (file, type qualname) -> may inherit members
    inherits: dict[tuple[str, str], bool] = {}
    for parsed in files:
        for symbol in parsed.symbols:
            if symbol["kind"] == "type":
                types_in[(parsed.path, symbol["name"])].append(symbol["qualname"])
                inherits[(parsed.path, symbol["qualname"])] = symbol.get("has_supertypes", False)
                continue
            owner, _, _ = symbol["qualname"].rpartition(".")
            members[(parsed.path, owner, symbol["name"])].append(
                (parsed.path, symbol["line"], symbol.get("arity", (0, False)))
            )

    def fitting(candidates, args: int) -> list[tuple[str, int]]:
        """The declarations *args* arguments could call: the fixed count
        matches, or a varargs one accepts at least its fixed count."""
        return [
            (file, line) for file, line, (fixed, spread) in candidates
            if args == fixed or (spread and args >= fixed)
        ]

    #: Sites lane A located a declaration set for and declined to pick
    #: from — the overload residue the tail names (ADR-096).
    overloads: set[tuple[str, int, str]] = set()
    #: Sites resolved into a type that declares supertypes — bare, or
    #: `T.foo()` through such a T: whether the callee is a local
    #: declaration or an inherited overload of the same arity depends on
    #: argument types lane A does not have, so it abstains and the tail
    #: says why. Constructors are never inherited and are excepted.
    inherited: set[tuple[str, int, str]] = set()

    def type_file(parsed: JavaFile, simple: str) -> tuple[str, str] | None:
        """Where the type *simple* names from *parsed*: (file, qualname)."""
        # Declared in this file (top-level or nested, if unambiguous).
        local = types_in.get((parsed.path, simple), [])
        if len(local) == 1:
            return parsed.path, local[0]
        if local:
            return None
        # Imported by name.
        for entry in parsed.imports:
            if entry["alias"] == simple and not entry["static"]:
                target = _import_target(entry, fqn_map)
                if target is not None and (target, simple) in types_in:
                    quals = types_in[(target, simple)]
                    return (target, quals[0]) if len(quals) == 1 else None
                return None
        # A same-package sibling: `<package>.<simple>` declared once.
        fqn = f"{parsed.package}.{simple}" if parsed.package else simple
        target = fqn_map.get(fqn)
        if target is not None:
            quals = types_in.get((target, simple), [])
            return (target, quals[0]) if len(quals) == 1 else None
        return None

    def qualified_type(parsed: JavaFile, path: list[str]) -> tuple[str, str] | None:
        """``a.b.C`` (a fully qualified name) or ``Outer.Inner``."""
        fqn = ".".join(path)
        target = fqn_map.get(fqn)
        if target is not None:
            quals = types_in.get((target, path[-1]), [])
            return (target, quals[0]) if len(quals) == 1 else None
        head = type_file(parsed, path[0])
        if head is None:
            return None
        file, qual = head
        for segment in path[1:]:
            qual = f"{qual}.{segment}"
            if (file, segment) not in types_in or qual not in types_in[(file, segment)]:
                return None
        return file, qual

    fallback: dict[tuple[str, int, str], tuple[str, int]] = {}
    for parsed in files:
        for call in parsed.calls:
            if call["explicit"] == "super":
                continue
            target: tuple[str, int] | None = None
            name, path = call["name"], call["path"]
            key = (parsed.path, call["line"], name)
            # A member of an anonymous class body whose extent spans the
            # site is the nearer declaration than anything inherited or
            # enclosing (jsoup's 44 `anythingElse(t, tb)` sites): the
            # tail's `local-binding`, never `inherited-member`.
            if not call["dotted"] and any(
                n == name and start <= call["line"] <= end
                for (n, start, end) in parsed.local_bindings
            ):
                continue

            def unique(candidates, key=key, args=call["args"]) -> tuple[str, int] | None:
                fits = fitting(candidates, args)
                if len(fits) > 1:
                    overloads.add(key)
                return fits[0] if len(fits) == 1 else None

            if call["ctor"]:
                located = (
                    qualified_type(parsed, path + [name]) if path
                    else (
                        # `this(..)`: the enclosing type itself.
                        (parsed.path, _enclosing_type(parsed.symbols, call["line"]))
                        if call["explicit"] == "this"
                        else type_file(parsed, name)
                    )
                )
                if located is None or located[1] is None:
                    continue
                file, qual = located
                ctors = members.get((file, qual, name), [])
                if ctors:
                    target = unique(ctors)
                elif call["explicit"] is None and not inherits.get((file, qual), False):
                    # No declared constructor: the default one, which
                    # has no line of its own — the type is the target.
                    target = (file, next(
                        s["line"] for s in by_file[file].symbols if s["qualname"] == qual
                    ))
            elif not call["dotted"]:
                # Unqualified: the enclosing type chain, innermost first —
                # stopping at a type that declares supertypes, because an
                # inherited member outranks an enclosing class's (Java's
                # rule), an inherited overload can share a local one's
                # arity (jsoup: `error(String)` from the superclass beside
                # the local `error(HtmlTreeBuilderState)`), and lane A
                # cannot see the hierarchy — then a static import.
                owner = _enclosing_type(parsed.symbols, call["line"])
                while owner is not None and target is None:
                    if inherits.get((parsed.path, owner), False):
                        inherited.add(key)
                        break
                    found = members.get((parsed.path, owner, name), [])
                    if found:
                        target = unique(found)
                        break
                    owner = owner.rpartition(".")[0] or None
                if target is None:
                    for entry in parsed.imports:
                        if entry["static"] and entry["alias"] == name:
                            file = _import_target(entry, fqn_map)
                            if file is not None:
                                owner_simple = entry["segments"][-2]
                                quals = types_in.get((file, owner_simple), [])
                                if len(quals) == 1:
                                    target = unique(members.get((file, quals[0], name), []))
                            break
            elif path:
                # `T.foo()` / `a.b.T.foo()` / `Outer.Inner.foo()` — a
                # static call through a type name, if the name is one —
                # and `new T(..).foo()`, whose receiver type is spelled.
                located = qualified_type(parsed, path)
                if located is not None and not inherits.get(located, False):
                    target = unique(members.get((located[0], located[1], name), []))
                elif located is not None:
                    inherited.add(key)  # a static through a type with supertypes
            if target is None or target == (parsed.path, call["line"]):
                continue
            fallback[key] = target
            inherited.discard(key)
    return fallback, overloads, inherited


def collect_java_tests(files: list[JavaFile], symbol_edges: list[dict]) -> list[dict]:
    """Java test inventory with reach, measured over the join's edges.

    Reach is the closure over ``calls`` edges from the test method, the
    same rule every other framework's reach uses (ADR-007), so a `junit`
    row means what a pytest row means.
    """
    from hobbes.extract.testmap import _closure

    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in symbol_edges:
        if edge["type"] == "calls":
            adjacency[edge["from"]].add(edge["to"])

    # Every Java symbol hangs off a type, so a symbol id's module is not
    # its last-dot prefix: map ids to modules from the layer's own facts.
    module_of = {
        f"{module_id(parsed.path)}.{s['qualname']}": module_id(parsed.path)
        for parsed in files
        for s in parsed.symbols
    }
    out = []
    for parsed in files:
        mid = module_id(parsed.path)
        for test in parsed.tests:
            symbol_id = f"{mid}.{test['qualname']}"
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
                        {module_of[r] for r in reached if r in module_of}
                    ),
                }
            )
    return out
