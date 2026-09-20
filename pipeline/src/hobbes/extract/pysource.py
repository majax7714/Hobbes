"""Single-file Python extraction: the tree-sitter walk (ADR-005).

:func:`parse_source` turns one file's bytes into the raw facts later stages
assemble into graphs: imports, symbols (with decorators, for routes and test
detection), call sites, and environment-variable reads. Everything here is
per-file and unresolved — cross-module resolution is :mod:`hobbes.extract.graph`'s
job (ADR-007).

Tree-sitter parses error-tolerantly, so files with syntax errors yield
partial facts instead of failing the ingest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import tree_sitter_python
from tree_sitter import Language, Node, Parser

_PARSER = Parser(Language(tree_sitter_python.language()))

#: Dotted callee texts recognized as environment reads (ADR-007). Pattern
#: match on the text, not on whether `os` is really the os module — the
#: false-positive risk (a local `os` that isn't the module) is negligible
#: against the value of the env: join keys for M3's cross-layer edges.
_ENV_CALLS = {"os.getenv", "getenv", "os.environ.get", "environ.get"}
_ENV_SUBSCRIPTS = {"os.environ", "environ"}


@dataclass(frozen=True)
class PlainImport:
    """``import a.b`` / ``import a.b as c``."""

    module: str
    alias: str | None
    line: int


@dataclass(frozen=True)
class FromImport:
    """``from a.b import x as y, z`` / ``from . import x`` / ``from a import *``.

    ``names`` holds (imported name, bound name) pairs; a wildcard import is
    the single pair ``("*", "*")``. ``level`` counts leading dots.
    """

    module: str
    level: int
    names: tuple[tuple[str, str], ...]
    line: int


@dataclass(frozen=True)
class Decorator:
    """One decorator site, pre-digested for route/test detection.

    ``dotted`` is the decorator's name chain (``app.get`` for
    ``@app.get("/x")``), or None when the expression is not a plain
    name/attribute (subscripts, lambdas). ``args`` holds the positional
    *string-literal* arguments only; ``kwargs`` maps keyword names to a
    string or tuple of strings, dropping anything not statically literal.

    A keyword whose value is a boolean is in neither — ``kwargs`` holds
    strings — so ``true_kwargs`` names the ones written ``True``, which is
    the only spelling of ``autouse=`` the fixture lookup reads (ADR-139),
    and ``unread_kwargs`` names those whose value is none of the four
    literals the walk can read at all.
    """

    dotted: str | None
    args: tuple[str, ...]
    kwargs: dict
    line: int
    #: Keyword names whose value is the literal ``True``, in written order.
    true_kwargs: tuple[str, ...] = ()
    #: Keyword names whose value is neither a string, a list of strings,
    #: ``True`` nor ``False``: a name, a call, an expression. ``autouse=FLAG``
    #: is here; ``autouse=False`` is in neither tuple, having been read.
    unread_kwargs: tuple[str, ...] = ()
    #: Whether the decorator is written **call-form** — ``@f(…)`` rather
    #: than a bare ``@f`` (ADR-147). The two digest identically otherwise
    #: (a bare ``@f`` has no arguments, and neither does ``@f()``), and
    #: they are different applications: ``@f`` applies ``f`` itself, while
    #: ``@f(…)`` applies what ``f(…)`` returned.
    called: bool = False
    #: The line of the callee's terminal identifier for a call-form
    #: decorator whose callee is a name chain — the line the semantic lane
    #: puts its occurrence on, and therefore the one a rule asking what the
    #: index resolved there has to match (ADR-147). ``None`` for a bare
    #: decorator and for a callee :func:`_dotted` cannot name (``@decos[0]()``).
    callee_line: int | None = None


@dataclass(frozen=True)
class Symbol:
    """A function, method, or class definition."""

    qualname: str
    name: str
    kind: str  # "function" | "method" | "class"
    line: int
    end_line: int
    decorators: tuple[Decorator, ...]
    #: Each parameter pytest could fill from a fixture, as (name, line):
    #: no default, not ``*args``/``**kwargs``. ``self`` and ``cls`` are
    #: recorded like any other — which names the lookup ignores is
    #: :mod:`hobbes.extract.fixtures`' business, not the walk's (ADR-137).
    params: tuple[tuple[str, int], ...] = ()
    #: The argument names every ``parametrize`` decorator on the
    #: definition binds, unioned; ``None`` when one of them spells its
    #: first argument as something this walk cannot read (a name, a call).
    #: A parametrized parameter is filled by the mark, not by a fixture,
    #: and ``None`` makes the lookup abstain on the whole definition.
    parametrized: tuple[str, ...] | None = ()
    #: For a class, how many base classes it names (keyword arguments such
    #: as ``metaclass=`` are not bases). The walk does not resolve them; a
    #: reader that needs a class's own namespace to be the whole story —
    #: the fixture lookup, where a base class's fixture is inherited —
    #: abstains when this is not zero (ADR-137).
    bases: int = 0
    #: What a function or method constructs and hands back, as the written
    #: name and the line it is written on, or ``None`` (ADR-145). Set only
    #: where the definition's own body holds exactly one ``return`` /
    #: ``yield`` carrying a value and that value is ``C(…)`` — a call on a
    #: bare name. A construction fixes the runtime class exactly, which is
    #: the whole of the claim a reader may make from it; ``return x``,
    #: ``return a.b()``, ``yield from …`` and a second valued return are
    #: each ``None``, and so is a bare ``return``, which carries no value.
    value: tuple[str, int] | None = None
    #: The parameter names the definition's own body binds again, sorted
    #: (ADR-145): by assignment (plain, augmented, annotated with a value,
    #: walrus), a ``for`` / ``with`` / ``except`` / ``import`` target,
    #: ``del``, ``global`` or ``nonlocal``. A reader that takes a parameter
    #: to still hold what was passed in — the fixture value rule — has to
    #: know when it does not. Own body only: a nested ``def``'s assignment
    #: binds in that def, not here.
    rebound: tuple[str, ...] = ()
    #: The name a **decorator factory** hands back, or ``None`` (ADR-147).
    #: Set on a function or method only, and only where every path returns
    #: one and the same nested ``def``: the definition is not ``async``, its
    #: own body holds no ``yield``, it holds at least one ``return``, every
    #: one of them is ``return g`` for the same bare name ``g``, ``g`` is
    #: not a parameter, and the own body binds ``g`` exactly once — by a
    #: plain nested ``def`` carrying no decorator. Under that shape
    #: whatever ``f(…)`` returns *is* ``g``, on every path, which is the
    #: whole of the claim a reader may make from it; ``return g(x)``,
    #: ``return a.g``, a bare ``return``, two names, a re-assigned or
    #: decorated or class-shaped ``g`` are each ``None``.
    returns_inner: str | None = None


#: The receiver recorded for a call whose object is an expression — a
#: call, a subscript, ``super()`` — rather than a name chain (C-80,
#: lifted 2026-09-03). The callee name after it is real; the receiver is
#: what lane A cannot name, and the fallback abstains on it. Alone, as
#: the whole callee, it marks a call whose *callee* is an expression —
#: ``handlers[0]()``, ``getattr(x, "y")()``, ``(a or b)()``, ``f()()`` —
#: a site with no name for either lane to resolve (C-63's shape in
#: Python; C-80's residual, closed 2026-09-05): counted, classed
#: ``expr-callee`` by the tail view, never joined and never drawn.
EXPR_RECEIVER = "<expr>"


@dataclass(frozen=True)
class Call:
    """A call site whose callee is a name/attribute chain, an attribute
    on an expression receiver (``EXPR_RECEIVER.<name>``), or an
    expression itself (``callee == EXPR_RECEIVER``).

    ``scope`` is the qualname of the innermost enclosing definition, or None
    for module-body calls (attributed to the module node itself, ADR-007).
    """

    scope: str | None
    callee: str
    line: int
    #: Column of the callee's terminal identifier (0-based), or -1 when
    #: unknown. One line routinely holds several calls, so the range join
    #: (ADR-029) needs more than a line to match a call to its resolution.
    col: int = -1


@dataclass(frozen=True)
class EnvRead:
    """A statically visible environment-variable read."""

    var: str
    line: int


@dataclass(frozen=True)
class LocalBinding:
    """A name bound below module level: a parameter, an assignment or
    ``for``/``with``/``except``-target inside a function, or a nested
    ``def``/``class`` name — carrying the line extent of the enclosing
    function it is visible in (ADR-046). The tail view matches a bare
    unresolved call against these **by containment** (the site's line
    inside the extent), so the observation is "bound in a scope that
    spans this call", not a file-wide name coincidence."""

    name: str
    start: int
    end: int


@dataclass
class ParsedFile:
    """Everything one walk collects from one file."""

    imports: list = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    env_reads: list[EnvRead] = field(default_factory=list)
    local_bindings: list[LocalBinding] = field(default_factory=list)
    #: The module docstring's literal, exactly as written, or None.
    #: This module extracts, it does not interpret.
    docstring: str | None = None
    #: Every ``usefixtures`` call a module-level ``pytestmark`` holds, in
    #: written order (ADR-139's amendment). The mark applies to every test
    #: in the file and the lookup follows its string arguments, so the walk
    #: records the calls themselves — read exactly as a decorator's call is,
    #: so a non-string argument is simply not in ``args``.
    pytestmark: tuple[Decorator, ...] = ()
    #: How many of :attr:`pytestmark`'s calls the lookup does not follow:
    #: the ones with no string argument at all, which name no fixture this
    #: walk can read.
    pytestmark_usefixtures: int = 0


def parse_source(source: bytes) -> ParsedFile:
    """Walk one file's source and collect its raw facts."""
    parsed = ParsedFile()
    root = _PARSER.parse(source).root_node
    parsed.docstring = _module_docstring(root)
    parsed.pytestmark = _pytestmark(root)
    parsed.pytestmark_usefixtures = sum(1 for m in parsed.pytestmark if not m.args)
    _walk(root, [], parsed, ())
    parsed.local_bindings = _collect_local_bindings(root)
    return parsed


def _target_identifiers(node: Node):
    """Identifier nodes in an assignment/for/with target expression.
    Attribute and subscript targets bind no new local name, so they
    yield nothing."""
    if node.type == "identifier":
        yield node
    elif node.type in (
        "tuple_pattern",
        "list_pattern",
        "pattern_list",
        "tuple",
        "list",
        "parenthesized_expression",
    ):
        for child in node.named_children:
            yield from _target_identifiers(child)


def _collect_local_bindings(root: Node) -> list[LocalBinding]:
    """Every sub-module binding with its enclosing function's extent.

    A second, deliberately separate walk: :func:`_walk` collects what the
    graph models; this collects what the graph *deliberately does not*
    (C-9's floor), so the tail view can say "seen, below the floor"
    instead of "unknown" (ADR-046). Recorded forms: function parameters
    (a pytest fixture argument is one), assignment and walrus targets,
    ``for``/``with``/``except`` targets, and nested ``def``/``class``
    names — each visible within the innermost enclosing function.
    """
    out: list[LocalBinding] = []

    def record(name: str, extent: tuple[int, int]) -> None:
        out.append(LocalBinding(name, extent[0], extent[1]))

    def walk(node: Node, extent: tuple[int, int] | None) -> None:
        kind = node.type
        if kind == "function_definition":
            own = (node.start_point.row + 1, node.end_point.row + 1)
            if extent is not None:
                name = node.child_by_field_name("name")
                if name is not None:
                    record(_text(name), extent)  # nested def binds outside
            params = node.child_by_field_name("parameters")
            if params is not None:
                for param in params.named_children:
                    ident = param if param.type == "identifier" else None
                    if ident is None:
                        for child in param.children:
                            if child.type == "identifier":
                                ident = child
                                break
                    if ident is not None:
                        record(_text(ident), own)
            body = node.child_by_field_name("body")
            if body is not None:
                for child in body.children:
                    walk(child, own)
            return
        if kind == "class_definition":
            if extent is not None:
                name = node.child_by_field_name("name")
                if name is not None:
                    record(_text(name), extent)  # local class binds its name
            # A class body is its own namespace: methods and class attrs
            # do not bind bare names in the enclosing function, so the
            # descent resets the extent (methods then bind their own
            # params under their own extents, exactly like any def).
            for child in node.children:
                walk(child, None)
            return
        if extent is not None:
            if kind in ("assignment", "augmented_assignment"):
                left = node.child_by_field_name("left")
                if left is not None:
                    for ident in _target_identifiers(left):
                        record(_text(ident), extent)
            elif kind == "named_expression":
                name = node.child_by_field_name("name")
                if name is not None and name.type == "identifier":
                    record(_text(name), extent)
            elif kind == "for_statement":
                left = node.child_by_field_name("left")
                if left is not None:
                    for ident in _target_identifiers(left):
                        record(_text(ident), extent)
            elif kind == "as_pattern":  # `with ... as f`, `except E as e`
                alias = node.child_by_field_name("alias")
                if alias is not None:
                    for ident in _target_identifiers(alias):
                        record(_text(ident), extent)
                    if alias.type == "as_pattern_target":
                        for child in alias.named_children:
                            for ident in _target_identifiers(child):
                                record(_text(ident), extent)
        for child in node.children:
            walk(child, extent)

    walk(root, None)
    return out


def _module_docstring(root: Node) -> str | None:
    """The module docstring literal: the file's first statement, if it is
    a bare string. Anything else means the module has none."""
    for child in root.named_children:
        if child.type != "expression_statement":
            return None
        inner = child.named_children[0] if child.named_children else None
        if inner is None or inner.type != "string":
            return None
        return (inner.text or b"").decode("utf-8", "replace")
    return None


def _text(node: Node) -> str:
    return (node.text or b"").decode("utf-8", "replace")


def _line(node: Node) -> int:
    return node.start_point.row + 1


def _terminal(node: Node) -> Node | None:
    """The last identifier in an identifier/attribute chain.

    ``a.b.c`` resolves to ``c`` — the name SCIP records an occurrence for,
    and therefore the one the ADR-029 join matches on.
    """
    if node is None:
        return None
    if node.type == "identifier":
        return node
    if node.type == "attribute":
        return node.child_by_field_name("attribute")
    return None


def _dotted(node: Node) -> str | None:
    """The text of a pure identifier/attribute chain, else None."""
    if node.type == "identifier":
        return _text(node)
    if node.type == "attribute":
        obj = _dotted(node.child_by_field_name("object"))
        if obj is None:
            return None
        return f"{obj}.{_text(node.child_by_field_name('attribute'))}"
    return None


def _string_literal(node: Node) -> str | None:
    """A plain string literal's content; None for f-strings and non-strings."""
    if node is None or node.type != "string":
        return None
    parts = []
    for child in node.children:
        if child.type == "interpolation":
            return None
        if child.type == "string_content":
            parts.append(_text(child))
    return "".join(parts)


def _decorator_expr(node: Node) -> Node:
    """The expression a ``decorator`` node applies: its first named child
    that is not a comment. Not the last child — a trailing comment
    (``@pytest.fixture  # shared``) is a child of the node too, and read
    as the expression it left the digest with no name: the fixture was
    no fixture, the route no route (found reviewing ADR-146's unit)."""
    for child in node.named_children:
        if child.type != "comment":
            return child
    return node.children[-1]


def _decorator(node: Node) -> Decorator:
    """Digest one ``decorator`` node.

    Which of the two forms it was is kept (ADR-147): a bare ``@f`` applies
    ``f``, a call-form ``@f(…)`` applies what ``f(…)`` returned, and the
    digest of ``@f`` and ``@f()`` is otherwise the same record.
    """
    expr = _decorator_expr(node)
    if expr.type != "call":
        return Decorator(_dotted(expr), (), {}, _line(node))
    return _call(expr, _line(node))


def _call(expr: Node, line: int) -> Decorator:
    """Digest one ``call`` node written as a mark: its dotted name, its
    string-literal positionals, and the keywords the walk can read.

    Split out of :func:`_decorator` because a mark is the same expression
    wherever it is written — after an ``@``, or as the value of a
    module-level ``pytestmark`` (ADR-139's amendment).

    Everything digested here is call-form, so ``called`` is True and
    ``callee_line`` is the callee's terminal identifier — where the
    semantic lane puts its occurrence, which is not *line* whenever the
    chain wraps (ADR-147).
    """
    function = expr.child_by_field_name("function")
    dotted = _dotted(function) if function is not None else None
    terminal = _terminal(function) if function is not None else None
    args: list[str] = []
    kwargs: dict = {}
    true_kwargs: list[str] = []
    unread_kwargs: list[str] = []
    arguments = expr.child_by_field_name("arguments")
    for arg in arguments.named_children if arguments else []:
        if arg.type == "string":
            literal = _string_literal(arg)
            if literal is not None:
                args.append(literal)
        elif arg.type == "keyword_argument":
            key = _text(arg.child_by_field_name("name"))
            value = arg.child_by_field_name("value")
            literal = _string_literal(value)
            items = (
                [_string_literal(el) for el in value.named_children]
                if value is not None and value.type == "list"
                else []
            )
            if literal is not None:
                kwargs[key] = literal
            elif items and all(i is not None for i in items):
                kwargs[key] = tuple(items)
            elif value is not None and value.type == "true":
                true_kwargs.append(key)
            elif value is None or value.type != "false":
                # Read as nothing: a name, a call, an expression, a list the
                # walk could not read whole. `False` is read, and says only
                # that the keyword is off (ADR-139).
                unread_kwargs.append(key)
    return Decorator(
        dotted,
        tuple(args),
        kwargs,
        line,
        tuple(true_kwargs),
        tuple(unread_kwargs),
        called=True,
        callee_line=(
            _line(terminal) if dotted is not None and terminal is not None else None
        ),
    )


def _pytestmark(root: Node) -> tuple[Decorator, ...]:
    """The ``usefixtures`` calls a module-level ``pytestmark`` holds.

    The mark applies to every test in the file, and the lookup follows the
    string arguments of each of these (ADR-139's amendment). Each call is
    digested as a decorator's is, at its own line, so a mark written in a
    list is evidenced where it is written.

    The scope is a **plain** module-level assignment: the value may be one
    call or a list or tuple of them, but an assignment inside a class or a
    function is not the module's ``pytestmark``, and neither is an
    annotated (``pytestmark: list = …``) or augmented (``pytestmark += …``)
    one — the walk reads what a name is bound to, not what is added to it.
    """
    out: list[Decorator] = []
    for statement in root.named_children:
        if statement.type != "expression_statement":
            continue
        for node in statement.named_children:
            if node.type != "assignment":
                continue
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or _text(left) != "pytestmark" or right is None:
                continue
            if node.child_by_field_name("type") is not None:
                continue
            marks = right.named_children if right.type in ("list", "tuple") else [right]
            out.extend(
                _call(mark, _line(mark))
                for mark in marks
                if mark.type == "call"
                and (_dotted(mark.child_by_field_name("function")) or "").rpartition(".")[2]
                == "usefixtures"
            )
    return tuple(out)


def _parameters(node: Node) -> tuple[tuple[str, int], ...]:
    """A definition's parameters that a fixture could fill (ADR-137).

    Positional-only, plain and keyword-only alike; a typed parameter counts,
    by its name. A defaulted parameter and ``*args`` / ``**kwargs`` are
    left out — pytest fills none of them — and so are the ``/`` and ``*``
    separators, which bind nothing. A class definition has no parameters
    field and yields nothing.
    """
    params = node.child_by_field_name("parameters")
    out: list[tuple[str, int]] = []
    for param in params.named_children if params else []:
        # `x: int` wraps its name; `*args: int` wraps a splat, whose name
        # is not a parameter a fixture can fill either way.
        ident = param.named_children[0] if param.type == "typed_parameter" else param
        if ident is not None and ident.type == "identifier":
            out.append((_text(ident), _line(ident)))
    return tuple(out)


def _own_body(node: Node):
    """Every node inside a definition's own body, stopping at a nested
    ``def``, ``class`` or ``lambda`` (ADR-145).

    What the definition itself runs, in other words: a ``return`` written
    in a nested function is that function's, and an assignment written
    there binds in that function's scope. The same containment question
    :func:`_collect_local_bindings` answers per binding, asked once per
    definition.
    """
    body = node.child_by_field_name("body")
    if body is None:
        return
    stack = list(body.children)
    while stack:
        current = stack.pop()
        if current.type in ("function_definition", "class_definition", "lambda"):
            continue
        yield current
        stack.extend(current.children)


def _returned_value(node: Node) -> tuple[str, int] | None:
    """The class a definition constructs and hands back (ADR-145).

    Exactly one ``return`` or ``yield`` in the own body may carry a value,
    and that value must be a call on a bare name: ``return CliRunner()``
    names ``CliRunner``. Anything else is None, because anything else
    leaves the runtime class of what comes back open — ``return x`` says
    nothing, ``return a.b()`` is a call on a value, ``yield from g()``
    delegates, and two valued exits mean the fixture chooses.
    """
    values: list[Node | None] = []
    for current in _own_body(node):
        if current.type == "return_statement":
            if current.named_children:
                values.append(current.named_children[0])
        elif current.type == "yield":
            if any(child.type == "from" for child in current.children):
                # `yield from g()` hands back what `g()` yields, never a
                # `g`: a valued exit this rule cannot read.
                values.append(None)
            elif current.named_children:
                values.append(current.named_children[0])
    if len(values) != 1 or values[0] is None:
        return None
    value = values[0]
    if value.type != "call":
        return None
    function = value.child_by_field_name("function")
    if function is None or function.type != "identifier":
        return None
    return _text(function), _line(function)


def _import_binding(node: Node) -> str | None:
    """The bare name one import clause binds: the alias where it renames,
    else the first component (``import a.b`` binds ``a``)."""
    if node.type == "aliased_import":
        alias = node.child_by_field_name("alias")
        return _text(alias) if alias is not None else None
    if node.type == "dotted_name" and node.named_children:
        return _text(node.named_children[0])
    return None


def _rebound(node: Node, params: tuple[tuple[str, int], ...]) -> tuple[str, ...]:
    """Which of *params* the definition's own body binds again (ADR-145).

    Every form that rebinds a bare name: assignment and augmented
    assignment, an annotation *with* a value (``x: int`` alone binds
    nothing), a walrus, a ``for`` / ``with`` / ``except`` target, an
    import, ``del``, ``global`` and ``nonlocal``. Attribute and subscript
    targets bind no name, so ``p.x = 1`` is not a rebinding of ``p``.
    """
    names = {name for name, _ in params}
    if not names:
        return ()
    bound: set[str] = set()

    def take(target: Node) -> None:
        for ident in _target_identifiers(target):
            bound.add(_text(ident))

    for current in _own_body(node):
        kind = current.type
        if kind == "assignment" and current.child_by_field_name("right") is None:
            continue  # `x: int` declares a type and binds nothing
        if kind in ("assignment", "augmented_assignment", "for_statement"):
            left = current.child_by_field_name("left")
            if left is not None:
                take(left)
        elif kind == "named_expression":
            name = current.child_by_field_name("name")
            if name is not None and name.type == "identifier":
                bound.add(_text(name))
        elif kind == "as_pattern":  # `with … as f`, `except E as e`
            alias = current.child_by_field_name("alias")
            if alias is not None:
                take(alias)
                if alias.type == "as_pattern_target":
                    for child in alias.named_children:
                        take(child)
        elif kind in ("delete_statement", "global_statement", "nonlocal_statement"):
            for child in current.named_children:
                take(child)
        elif kind in ("import_statement", "import_from_statement"):
            clauses = (
                current.named_children
                if kind == "import_statement"
                else current.children_by_field_name("name")
            )
            for clause in clauses:
                bound.add(_import_binding(clause) or "")
    return tuple(sorted(bound & names))


def _own_definitions(node: Node):
    """Every ``def`` and ``class`` written in a definition's own body, as
    ``(definition node, decorated?)`` (ADR-147).

    The companion of :func:`_own_body`, which stops *at* these nodes and so
    never yields them: what a definition's own scope binds by writing a
    nested definition is exactly what that walk leaves out. A decorated
    nested def is its ``decorated_definition``'s child, and whether it
    carried a decorator is the fact the rule needs — a decorated ``g`` is
    not the ``g`` the ``def`` wrote. The descent stops at each one: a
    definition written inside another binds in *that* one's scope.
    """
    body = node.child_by_field_name("body")
    if body is None:
        return
    stack = list(body.children)
    while stack:
        current = stack.pop()
        kind = current.type
        if kind == "decorated_definition":
            definition = current.child_by_field_name("definition")
            if definition is not None:
                yield definition, True
            continue
        if kind in ("function_definition", "class_definition"):
            yield current, False
            continue
        if kind == "lambda":
            continue
        stack.extend(current.children)


def _parameter_names(node: Node) -> frozenset[str]:
    """Every name a definition's parameter list binds, of any kind.

    Wider than :func:`_parameters`, which keeps the ones pytest could fill:
    a defaulted parameter, ``*args`` and ``**kwargs`` bind names too, and a
    rule asking whether a returned name is the definition's own (ADR-147)
    has to see all of them.
    """
    params = node.child_by_field_name("parameters")
    out: set[str] = set()
    for param in params.named_children if params else []:
        # `y=1` and `z: int = 2` name themselves; `x: int` wraps its name;
        # `*args` and `**kw` wrap theirs under a splat pattern.
        target = param.child_by_field_name("name") or param
        if target.type == "typed_parameter" and target.named_children:
            target = target.named_children[0]
        if (
            target.type in ("list_splat_pattern", "dictionary_splat_pattern")
            and target.named_children
        ):
            target = target.named_children[0]
        if target.type == "identifier":
            out.add(_text(target))
    return frozenset(out)


def _returns_inner(node: Node) -> str | None:
    """The nested ``def`` a decorator factory hands back (ADR-147).

    The strict wording: *every* return in the definition's own body is
    ``return g`` for one bare name, and that name is one plain,
    undecorated nested ``def``. Then whatever ``f(…)`` returns is ``g`` on
    every path, and a reader may say so exactly; the loose reading (some
    return is ``g``, another is anything) would claim it where click's
    ``command`` — ``return decorator(func)`` beside ``return decorator`` —
    does not call ``decorator`` at all.

    Everything else is None, and the refusals are the shape of the claim:
    an ``async`` def or a generator never returns the def itself, a bare
    ``return`` is a path returning ``None``, and a ``g`` that is also
    assigned, imported, declared ``global``, defined twice or written as a
    ``class`` is not the def the rule read.
    """
    if any(child.type == "async" for child in node.children):
        return None
    name: str | None = None
    for current in _own_body(node):
        if current.type == "yield":
            return None  # a generator hands back values, never itself
        if current.type != "return_statement":
            continue
        value = current.named_children[0] if current.named_children else None
        if value is None or value.type != "identifier":
            return None
        written = _text(value)
        if name is not None and written != name:
            return None
        name = written
    if name is None or name in _parameter_names(node):
        return None
    # Bound exactly once, and by the nested `def`. The assignment forms are
    # :func:`_rebound`'s walk, asked about this one name; the definitions
    # are the walk that one deliberately does not do.
    if _rebound(node, ((name, 0),)):
        return None
    definitions = [
        (definition, decorated)
        for definition, decorated in _own_definitions(node)
        if _text(definition.child_by_field_name("name") or definition) == name
    ]
    if len(definitions) != 1:
        return None
    definition, decorated = definitions[0]
    if decorated or definition.type != "function_definition":
        return None
    if any(child.type == "async" for child in definition.children):
        return None
    return name


def _parametrize_names(node: Node) -> tuple[str, ...] | None:
    """The argument names one ``parametrize`` decorator binds, in either
    spelling — ``"a, b"`` or ``["a", "b"]`` / ``("a", "b")`` — or None when
    its first argument is neither (a name, a call, a constant defined
    elsewhere). :class:`Decorator` keeps string literals only, so the names
    are read from the node here rather than from the digest.
    """
    expr = _decorator_expr(node)
    if expr.type != "call":
        return None
    arguments = expr.child_by_field_name("arguments")
    first = arguments.named_children[0] if arguments and arguments.named_children else None
    if first is None:
        return None
    if first.type == "string":
        literal = _string_literal(first)
        return None if literal is None else tuple(n.strip() for n in literal.split(","))
    if first.type in ("list", "tuple"):
        items = [_string_literal(el) for el in first.named_children]
        if items and all(i is not None for i in items):
            return tuple(items)
    return None


def _parametrized(nodes: list[Node], digested: tuple[Decorator, ...]) -> tuple[str, ...] | None:
    """Every ``parametrize`` decorator's names, unioned in written order;
    None as soon as one of them is unreadable (the definition then abstains
    whole, rather than looking a parametrized name up as a fixture)."""
    names: list[str] = []
    for node, decorator in zip(nodes, digested):
        if (decorator.dotted or "").rpartition(".")[2] != "parametrize":
            continue
        read = _parametrize_names(node)
        if read is None:
            return None
        names.extend(read)
    return tuple(dict.fromkeys(names))


def _scope_qualname(stack: list[tuple[str, str]]) -> str | None:
    return ".".join(name for name, _ in stack) or None


def _base_count(node: Node) -> int:
    """How many base classes a ``class_definition`` names."""
    bases = node.child_by_field_name("superclasses")
    if bases is None:
        return 0
    return sum(1 for child in bases.named_children if child.type != "keyword_argument")


def _walk(
    node: Node,
    stack: list[tuple[str, str]],
    parsed: ParsedFile,
    pending_decorators: tuple[Decorator, ...],
    pending_parametrized: tuple[str, ...] | None = (),
) -> None:
    kind = node.type

    if kind == "import_statement":
        line = _line(node)
        for child in node.named_children:
            if child.type == "dotted_name":
                parsed.imports.append(PlainImport(_text(child), None, line))
            elif child.type == "aliased_import":
                parsed.imports.append(
                    PlainImport(
                        _text(child.child_by_field_name("name")),
                        _text(child.child_by_field_name("alias")),
                        line,
                    )
                )
        return

    if kind == "import_from_statement":
        module_node = node.child_by_field_name("module_name")
        level, module = 0, ""
        if module_node.type == "relative_import":
            for child in module_node.children:
                if child.type == "import_prefix":
                    level = len(_text(child))
                elif child.type == "dotted_name":
                    module = _text(child)
        else:
            module = _text(module_node)
        names: list[tuple[str, str]] = []
        if any(c.type == "wildcard_import" for c in node.children):
            names.append(("*", "*"))
        else:
            for child in node.children_by_field_name("name"):
                if child.type == "dotted_name":
                    name = _text(child)
                    names.append((name, name))
                elif child.type == "aliased_import":
                    names.append(
                        (
                            _text(child.child_by_field_name("name")),
                            _text(child.child_by_field_name("alias")),
                        )
                    )
        parsed.imports.append(FromImport(module, level, tuple(names), _line(node)))
        return

    if kind == "decorated_definition":
        decorator_nodes = [c for c in node.children if c.type == "decorator"]
        decorators = tuple(_decorator(c) for c in decorator_nodes)
        # A decorator is a call of what it names (ADR-146). Each
        # expression is walked as any expression is, so `@app.get("/x")`
        # records the `app.get` site its `call` node already is; and a
        # *bare* `@name` or `@a.b`, which the language defines as
        # `name(fn)`, records the application the source does not spell,
        # on the terminal identifier where the semantic lane puts its
        # occurrence. The scope is the **enclosing** definition — the
        # decorator runs where it is written, at the module or in the
        # body that holds it, before the definition it wraps exists — so
        # `stack` is passed unchanged and no decorator is pending inside
        # one. Any other bare expression (a subscript, a lambda) names
        # nothing to apply and records only the calls written in it.
        for decorator_node in decorator_nodes:
            expr = _decorator_expr(decorator_node)
            _walk(expr, stack, parsed, ())
            dotted = _dotted(expr)
            terminal = _terminal(expr)
            if dotted is not None and terminal is not None:
                parsed.calls.append(
                    Call(
                        _scope_qualname(stack),
                        dotted,
                        terminal.start_point.row + 1,
                        terminal.start_point.column,
                    )
                )
        definition = node.child_by_field_name("definition")
        if definition is not None:
            _walk(
                definition,
                stack,
                parsed,
                decorators,
                _parametrized(decorator_nodes, decorators),
            )
        return

    if kind in ("function_definition", "class_definition"):
        name = _text(node.child_by_field_name("name"))
        qualname = ".".join([*(n for n, _ in stack), name])
        if kind == "class_definition":
            symbol_kind = "class"
        elif stack and stack[-1][1] == "class":
            symbol_kind = "method"
        else:
            symbol_kind = "function"
        params = _parameters(node)
        is_function = kind == "function_definition"
        parsed.symbols.append(
            Symbol(
                qualname=qualname,
                name=name,
                kind=symbol_kind,
                line=_line(node),
                end_line=node.end_point.row + 1,
                decorators=pending_decorators,
                params=params,
                parametrized=pending_parametrized,
                bases=_base_count(node) if kind == "class_definition" else 0,
                # A class body returns nothing and rebinds no parameter,
                # having none: both facts are a function's (ADR-145).
                value=_returned_value(node) if is_function else None,
                rebound=_rebound(node, params) if is_function else (),
                # A class is no decorator factory under this rule either:
                # ADR-147 reads a `def` that returns a `def`.
                returns_inner=_returns_inner(node) if is_function else None,
            )
        )
        body = node.child_by_field_name("body")
        if body is not None:
            child_stack = [*stack, (name, "class" if kind == "class_definition" else "function")]
            for child in body.children:
                _walk(child, child_stack, parsed, ())
        return

    if kind == "call":
        function = node.child_by_field_name("function")
        dotted = _dotted(function) if function is not None else None
        if dotted is None and function is not None and function.type == "attribute":
            # C-80 (lifted): `super().m()`, `f().m()`, `xs[i].m()` — the
            # callee name is still a plain attribute; only the receiver
            # is an expression lane A cannot name. Recorded as a site so
            # the join can pair it with the semantic occurrence (peft:
            # 252 such calls were `uses` edges glossed as "not a call");
            # the fallback abstains on the receiver (graph._resolve_call).
            attribute = function.child_by_field_name("attribute")
            if attribute is not None:
                dotted = f"{EXPR_RECEIVER}.{_text(attribute)}"
        if dotted is None and function is not None:
            # C-63's shape in Python (C-80's residual, closed 2026-09-05):
            # the callee is itself an expression — a subscript, a call's
            # result, a conditional, a lambda in parentheses — so there
            # is no identifier for the semantic lane to put an occurrence
            # on and nothing can resolve it. It is still a call: recorded
            # as a site named by the marker alone, positioned where the
            # callee expression starts, so the denominator counts it and
            # the tail view classes it `expr-callee` (before this the
            # site did not exist and a dispatch table read as accounted).
            parsed.calls.append(
                Call(
                    _scope_qualname(stack),
                    EXPR_RECEIVER,
                    function.start_point.row + 1,
                    function.start_point.column,
                )
            )
        if dotted is not None:
            line = _line(node)
            if dotted in _ENV_CALLS:
                arguments = node.child_by_field_name("arguments")
                first = arguments.named_children[0] if arguments and arguments.named_children else None
                var = _string_literal(first)
                if var is not None:
                    parsed.env_reads.append(EnvRead(var, line))
            terminal = _terminal(function)
            column = terminal.start_point.column if terminal is not None else -1
            # Position the site on the *callee identifier*, not on the call
            # expression, because that is where the semantic provider puts
            # its occurrence. They differ whenever a chain wraps —
            #
            #     result = (client
            #               .session
            #               .get(url))
            #
            # — where the call starts at `client` and SCIP resolves `get`
            # two lines down. Reporting the call's line leaves the site
            # permanently unjoinable: not an error, just an edge that never
            # appears and a hole in coverage's numerator (ADR-029).
            if terminal is not None:
                line = terminal.start_point.row + 1
            parsed.calls.append(
                Call(_scope_qualname(stack), dotted, line, column)
            )
        for child in node.children:
            _walk(child, stack, parsed, ())
        return

    if kind == "subscript":
        value = node.child_by_field_name("value")
        dotted = _dotted(value) if value is not None else None
        if dotted in _ENV_SUBSCRIPTS:
            var = _string_literal(node.child_by_field_name("subscript"))
            if var is not None:
                parsed.env_reads.append(EnvRead(var, _line(node)))
        for child in node.children:
            _walk(child, stack, parsed, ())
        return

    for child in node.children:
        _walk(child, stack, parsed, ())
