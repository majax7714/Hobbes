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

import re
from collections import Counter, defaultdict
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


class _Unknown:
    """The single inhabitant of :data:`UNKNOWN`."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNKNOWN"


#: The one value ADR-148's fold could not read: a name the site passed, an
#: argument behind a ``*`` or ``**``, a default the walk cannot spell, a
#: value two branches disagree about. It is a value like any other in the
#: digest — hashable, and equal only to itself — so a rule that meets it
#: abstains rather than guessing what it stood for.
UNKNOWN = _Unknown()


class _NoDefault:
    """The single inhabitant of :data:`NO_DEFAULT`."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "NO_DEFAULT"


#: A parameter written with no default at all — which is not the same
#: fact as a default the walk could not read (:data:`UNKNOWN`), and the
#: fold binds the two differently only in what it says about them.
NO_DEFAULT = _NoDefault()


@dataclass(frozen=True)
class Bound:
    """The arguments one call-form decorator writes, for ADR-148's fold.

    ``args`` holds the positional arguments as **values**, in written
    order, each one a literal (``None``, ``True``, ``False``, an int, a
    float, a plain string, the empty tuple) or :data:`UNKNOWN`; ``kwargs``
    holds the keyword arguments as ``(name, value)`` pairs in written
    order, read the same way; ``splat`` says a ``*x`` or ``**x`` appears,
    which makes the whole binding unknown (ADR-148 step 2) because the
    walk cannot say which parameter it fills.

    Deliberately beside :attr:`Decorator.args` and
    :attr:`Decorator.kwargs` rather than inside them: those two are the
    route and fixture digest, which keeps string literals and silently
    drops everything else, and a fold that could not tell a dropped
    argument from an argument that was never written would read a site
    the source does not hold.
    """

    args: tuple = ()
    kwargs: tuple[tuple[str, object], ...] = ()
    splat: bool = False


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
    #: What this site writes between its parentheses, for ADR-148's fold,
    #: or ``None`` — for a bare ``@f``, which writes no arguments and
    #: whose application is ADR-146's rather than a factory's, and for a
    #: mark digested out of a module's ``pytestmark``, which is not a
    #: decorator site and is never folded over.
    bound: Bound | None = None


# ADR-148 reads a decorator factory's own body as a small program and
# folds it over the site's arguments. The records below are the **whole**
# language that fold understands: an expression it cannot read is
# :data:`UNKNOWN`, and a statement it cannot read is kept as the names it
# binds and nothing more — so the fold meets what the walk could not read
# as an unknown rather than as silence.


@dataclass(frozen=True)
class Literal:
    """A value written in the source: ``None``, a bool, a number, a plain
    string, or the empty tuple."""

    value: object


@dataclass(frozen=True)
class NameRef:
    """A bare name, read from the fold's environment."""

    name: str


@dataclass(frozen=True)
class Not:
    """``not x``."""

    operand: object


@dataclass(frozen=True)
class BoolOp:
    """``x and y`` / ``x or y``, short-circuit as Python's (ADR-148 step 4:
    a known operand settles the test even beside an unknown one)."""

    op: str  # "and" | "or"
    left: object
    right: object


@dataclass(frozen=True)
class IsNone:
    """``x is None``, or ``x is not None`` when *negated*."""

    operand: object
    negated: bool = False


@dataclass(frozen=True)
class IsCallable:
    """``callable(x)`` with one positional argument — the builtin, read
    only where the module binds no ``callable`` of its own
    (:attr:`InnerFold.shadows_callable`)."""

    operand: object


@dataclass(frozen=True)
class Assign:
    """``x = <literal>`` or ``x = y``: the only assignment the fold reads
    as a value. Every other one is a :class:`Binds`."""

    name: str
    value: object


@dataclass(frozen=True)
class Chain:
    """The call one ``return`` of a factory hands back (ADR-149).

    ``return command(name, cls, **attrs)``: *dotted* is the callee's name
    chain as :func:`_dotted` reads it, *line* the line of its terminal
    identifier — where the index puts the occurrence, so a rule asking
    what it resolved there has that line to match on — and the rest is
    what the return forwards, read exactly as ADR-148 reads a site's own
    arguments. *args* holds the positionals written **before** any ``*x``
    as operands (a :class:`Literal`, a :class:`NameRef` to be read in the
    factory's own environment, or :data:`UNKNOWN`), *kwargs* the keywords
    in written order, *star* the index of the first ``*x`` among the
    positionals, and *double_star* whether a ``**x`` is written at all.

    Recorded only where :func:`_dotted` can name the callee: click's
    ``command(cls=cls, **attrs)(name)`` — a call on a call — and
    ``handlers[0](x)`` name nothing for any index to have resolved, so
    they carry no chain and the rule that reads this refuses rather than
    guessing which function ran.
    """

    dotted: str
    line: int
    args: tuple = ()
    kwargs: tuple[tuple[str, object], ...] = ()
    star: int | None = None
    double_star: bool = False


@dataclass(frozen=True)
class Return:
    """A ``return`` in the factory's own body. *inner* says it is
    ``return g`` — the only return ADR-148 may draw a call from.

    *chain* is the call the return hands back (ADR-149), and ``None``
    for every return that is not one **and** in every program built to
    name an inner def: ADR-148's digest is left exactly as it measured
    it, a factory carrying one program or the other and never both
    (:func:`_statements`).
    """

    inner: bool
    chain: Chain | None = None


@dataclass(frozen=True)
class Raise:
    """A ``raise``: the path ends here and reaches no return at all."""


@dataclass(frozen=True)
class Binds:
    """Any other statement, kept as the names it binds — each made
    unknown, because what it bound them to was not read."""

    names: tuple[str, ...] = ()


@dataclass(frozen=True)
class Opaque:
    """A statement that holds a ``return`` and is not an ``if``: a
    ``for``, ``while``, ``with``, ``try`` or ``match``. The names bound
    anywhere inside it are made unknown and every ``return`` written
    inside it stays reachable — whether the block runs, and how often, is
    exactly what the walk does not read."""

    names: tuple[str, ...] = ()
    returns: tuple[bool, ...] = ()


@dataclass(frozen=True)
class Branch:
    """One arm of an ``if`` / ``elif`` / ``else``. *test* is ``None`` for
    the ``else``; *unknown* names what the test itself bound — a walrus,
    which makes the test unreadable and the name with it."""

    test: object
    unknown: tuple[str, ...]
    body: tuple


@dataclass(frozen=True)
class If:
    """An ``if`` with its ``elif`` and ``else`` arms, in written order."""

    branches: tuple[Branch, ...]


@dataclass(frozen=True)
class Param:
    """One parameter of a factory: its name, and its default — a literal,
    :data:`UNKNOWN` where the walk cannot read the default written, or
    :data:`NO_DEFAULT` where none is written at all."""

    name: str
    default: object = NO_DEFAULT


@dataclass(frozen=True)
class InnerFold:
    """A decorator factory ADR-147's strict wording does not settle, in
    the shape ADR-148 folds over a site's own arguments (step 1).

    Set on a function or method only, where :attr:`Symbol.returns_inner`
    is ``None`` and the body is a factory all the same: not ``async``, no
    ``yield`` of its own, exactly one nested definition — a plain,
    undecorated, non-``async`` ``def`` named :attr:`inner`, not a
    parameter and not bound again — and at least one ``return`` of it.

    Everything the fold needs is here, so
    :func:`hobbes.extract.decorators.fold_guards` reads no tree and opens
    no file: *params*, *star*, *kwonly* and *double_star* are the
    signature a site's arguments bind into, *shadows_callable* says the
    **module** binds a ``callable`` of its own — and every ``callable(x)``
    guard in it is then unreadable, being some other function — and
    *body* is the own body's top-level statements as the program above.
    """

    inner: str
    params: tuple[Param, ...] = ()
    star: str | None = None
    kwonly: tuple[Param, ...] = ()
    double_star: str | None = None
    shadows_callable: bool = False
    body: tuple = ()


@dataclass(frozen=True)
class ChainFold:
    """A decorator factory that hands back **another factory's call**, in
    the shape ADR-149 folds over a site's own arguments (step 1).

    Set on a function or method where :attr:`Symbol.returns_inner` and
    :attr:`Symbol.inner_fold` are both ``None`` and the body is a factory
    all the same: not ``async``, no ``yield`` of its own, a signature
    :func:`_signature` can name, and at least one own-body ``return`` of
    a call this walk can name. The nested defs do not matter here, of any
    number: what such a factory returns is written in the call, not in a
    def beside it — click's ``group`` writes none at all.

    The fields are :class:`InnerFold`'s but for the inner name it has
    none of: the signature a site's arguments bind into,
    *shadows_callable* as that record carries it, and the own body as the
    same small program — recorded with no inner name to match, so every
    :attr:`Return.inner` in it is ``False`` and every return that is a
    call carries its :class:`Chain`.
    """

    params: tuple[Param, ...] = ()
    star: str | None = None
    kwonly: tuple[Param, ...] = ()
    double_star: str | None = None
    shadows_callable: bool = False
    body: tuple = ()


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
    #: ``yield`` carrying a value and that value is either ``C(…)`` — a
    #: call on a bare name — or a bare name ``x`` a single top-level
    #: ``x = C(…)`` bound before it (ADR-145's amendment). A construction
    #: fixes the runtime class exactly, which is the whole of the claim a
    #: reader may make from it, and a local bound once by a construction
    #: holds nothing else; ``return a.b()``, ``yield from …`` and a second
    #: valued return are each ``None``, and so is a bare ``return``, which
    #: carries no value.
    value: tuple[str, int] | None = None
    #: The local :attr:`value` came through, or ``None`` when the returned
    #: value *was* the construction (ADR-145's amendment). The two forms
    #: are one fact to a reader that wants the class, and two to a reader
    #: that wants to know what else was done to the object before it was
    #: handed back — a patch on ``x`` is a patch on what the caller holds.
    value_local: str | None = None
    #: The parameter names the definition's own body binds again, sorted
    #: (ADR-145): by assignment (plain, augmented, annotated with a value,
    #: walrus), a ``for`` / ``with`` / ``except`` / ``import`` target,
    #: ``del``, ``global`` or ``nonlocal``. A reader that takes a parameter
    #: to still hold what was passed in — the fixture value rule — has to
    #: know when it does not. Own body only: a nested ``def``'s assignment
    #: binds in that def, not here.
    rebound: tuple[str, ...] = ()
    #: What a function or method stores onto, or deletes from, a bare name
    #: it holds — as sorted ``(name, attribute)`` pairs, read from the own
    #: body (ADR-145's amendment). ``p.m = f`` and ``del p.m`` are
    #: ``(p, m)``; ``p.__class__ = K`` and ``setattr(p, …)`` —
    #: ``monkeypatch.setattr`` included — are ``(p, "*")``, because what
    #: they move is not one named attribute. A rule that reads a class's
    #: ``def`` for what ``p.m(…)`` runs has to know when the instance no
    #: longer answers with it. Empty on a class, which patches nothing of
    #: its own.
    patched: tuple[tuple[str, str], ...] = ()
    #: The names a **class**'s own body binds by any form other than a
    #: ``def``, sorted (ADR-145's amendment): an assignment of every kind,
    #: an import, a ``for`` / ``with`` target, a walrus, a ``del``, and a
    #: nested ``class``. A class attribute named ``m`` shadows whatever a
    #: base's ``def m`` would have been, so a walk up the bases stops at
    #: it. A nested ``def`` is a method, not one of these. Empty on a
    #: function.
    binds: tuple[str, ...] = ()
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
    #: The same factory, digested for ADR-148's fold, where
    #: :attr:`returns_inner` is ``None`` and step 1's shape holds all the
    #: same — one nested ``def`` and a body that returns it on *some*
    #: path. A factory ADR-147 settles carries no fold: it is drawn as
    #: ADR-147 draws it and never re-folded. ``None`` everywhere else,
    #: and on every class.
    inner_fold: InnerFold | None = None
    #: The factory that returns *another factory's call*, digested for
    #: ADR-149's fold, where :attr:`returns_inner` and :attr:`inner_fold`
    #: are both ``None`` and step 1's shape holds all the same. The three
    #: readings are asked in that order and a body carries at most one of
    #: them: a factory an earlier rule settles is drawn as that rule draws
    #: it and never re-read. ``None`` everywhere else, and on every class.
    chain_fold: ChainFold | None = None
    #: A ``def``'s return annotation, as its head name and the line the
    #: annotation is written on, or ``None`` (ADR-156 step 1). The head is
    #: the last identifier of a name or dotted name (``mod.C`` → ``C``), of
    #: a string literal holding exactly one (``"pkg.mod.C"``), or of a
    #: subscript's value (``C[int]`` → ``C``). Every other form is ``None``
    #: — a union, ``Optional[…]``, ``None``, a call, a string that is not
    #: one dotted name — because the head is only which reference the
    #: index resolved, and a form naming two types names no one class.
    #: Lane A does not resolve it. ``None`` on every class.
    returns: tuple[str, int] | None = None


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
class WithItem:
    """One item of a sync ``with`` statement whose context expression is a
    call (ADR-156 step 1).

    ``scope`` is as :attr:`Call.scope`; ``line`` is the line the item's own
    call's :class:`Call` record carries (its callee's terminal identifier);
    ``name`` is that identifier — the name the item's **own**, outermost,
    call writes: ``Live`` for ``Live(…)``, ``capture`` for
    ``console.capture()``, ``get`` for ``app.test_client().get(…)``, never
    ``test_client``. A callee that is not a name or attribute records no
    item, and neither does an ``async with``.
    """

    scope: str | None
    line: int
    name: str


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


#: The condition of a test lane A cannot read statically (ADR-154): an
#: operand of an ``and``/``or`` that decides nothing on its own.
UNREAD: tuple = ("unread",)


@dataclass(frozen=True)
class StaticTest:
    """One place Pyright 0.6.6 may read a test statically (ADR-154).

    Collected here, where the grammar is (I-4), and evaluated by
    :mod:`hobbes.extract.pystatic`, which holds none. ``condition`` is the
    test, encoded as nested tuples, exactly the forms ADR-154 lists:

    - ``("const", True | False)``
    - ``("sys.platform", S, op, "<str>")`` — ``S.platform ==|!= "<str>"``
    - ``("os.name", op, "<str>")`` — the name ``os`` literally
    - ``("sys.version_info", S, op, (major,) | (major, minor))``
    - ``("sys.version_info[0]", S, op, major)``
    - ``("TYPE_CHECKING", None | T)`` — the bare name, or ``T.TYPE_CHECKING``
    - ``("not", c)``, ``("and", (c, …))``, ``("or", (c, …))``
    - :data:`UNREAD` for anything else (only ever inside ``and``/``or``)

    ``S`` and ``T`` are the receiver names as written; whether each is a
    ``sys`` or ``typing`` alias at ``line`` is the evaluator's question,
    asked of :attr:`ParsedFile.sys_aliases` and
    :attr:`ParsedFile.typing_aliases`. ``on_true`` / ``on_false`` are the
    ``(first line, last line)`` spans the test kills when it reads that
    way, 1-based; a line the test itself is written on is never in one.
    """

    line: int
    condition: tuple
    on_true: tuple[tuple[int, int], ...] = ()
    on_false: tuple[tuple[int, int], ...] = ()


#: A type lane A cannot read (ADR-168): anything but a name, ``None``, a
#: ``|`` union, ``Union[…]``/``Optional[…]`` or a string holding one.
UNREAD_TYPE = ("?",)


@dataclass(frozen=True)
class ReceiverRead:
    """How the receiver ``R`` of a method call ``R.m(…)`` inside a function
    reads (ADR-168): ``how`` is ``param`` (``key``: its annotation's type),
    ``local`` (bound once, from a call: ``key`` is the callee's last name),
    ``attribute`` (``key``: the attribute's name), ``subscript`` (``key``:
    None) or ``result`` (a call's result: ``key`` is the callee's last name).
    ``line``/``col`` are the method name's, where the call site sits."""

    line: int
    col: int
    method: str
    how: str
    key: object


@dataclass(frozen=True)
class TypeFacts:
    """What a file writes about types, as lane A reads it (ADR-168, C-184).
    A type is a name (its last segment), ``"None"``, ``("|", members)`` or
    :data:`UNREAD_TYPE`. Nothing is resolved here; :mod:`pyunion` decides."""

    aliases: tuple[tuple[str, object], ...] = ()
    #: ``(name, methods, bases)`` per class, bases by last name.
    classes: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = ()
    attributes: tuple[tuple[str, object], ...] = ()
    returns: tuple[tuple[str, object], ...] = ()
    getitems: tuple[object, ...] = ()
    receivers: tuple[ReceiverRead, ...] = ()
    #: ``(class line, last base's line, base head names)`` per class with a
    #: base (C-185, ADR-169): where scip-python resolves the base it writes.
    heads: tuple[tuple[int, int, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class DynamicLoad:
    """One call that loads a module by name (C-179, ADR-167): ``via`` is the
    callee's last name, ``written`` what the call names as written — a
    module name, a path tail ending in ``.py`` — or ``""`` when nothing
    literal says."""

    line: int
    via: str
    written: str


@dataclass
class ParsedFile:
    """Everything one walk collects from one file."""

    imports: list = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    env_reads: list[EnvRead] = field(default_factory=list)
    local_bindings: list[LocalBinding] = field(default_factory=list)
    #: Every by-name module load, in written order (C-179, ADR-167).
    dynamic_loads: tuple[DynamicLoad, ...] = ()
    #: What the file writes about types (C-184, ADR-168).
    type_facts: TypeFacts = field(default_factory=TypeFacts)
    #: Per classmethod written directly in a class body, ``(qualname, first
    #: line, last line, class qualname)`` (ADR-170): a bare ``cls(…)`` in its
    #: own body constructs that class. One whose body rebinds ``cls`` is left
    #: out.
    classmethods: tuple[tuple[str, int, int, str], ...] = ()
    #: The module docstring's literal, exactly as written, or None.
    #: This module extracts, it does not interpret.
    docstring: str | None = None
    #: The file holds no statement but, at most, one bare string — its
    #: docstring — comments aside, and parsed cleanly. Such a module is not
    #: own code to guard (ADR-117's amendment); never set on a failed parse.
    no_code: bool = False
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
    #: Per function or method qualname, one ``(first line, last line,
    #: names)`` per definition written under it: the names that
    #: definition's scope binds exactly once, by a ``def`` written in its
    #: own body (ADR-153 step 1), sorted. A bare call of one of them,
    #: written in that scope, calls that ``def`` — which is the rule
    #: :func:`hobbes.extract.graph._resolve_call` asks before the module's.
    #: The lines are there because a qualname is not always one
    #: definition: an ``@overload``'s stubs and the implementation share
    #: one, and a call's scope names the qualname, so the call's line
    #: says which definition it is written in. A definition binding no
    #: such name is left out, so most files carry an empty mapping, and a
    #: class never has an entry. A name whose ``def`` shares *its*
    #: qualname with another definition in the file is left out too: the
    #: graph keeps one symbol per qualname, the first, and an edge to it
    #: from the second's caller would name the wrong ``def``.
    local_defs: dict[str, tuple[tuple[int, int, tuple[str, ...]], ...]] = field(
        default_factory=dict
    )
    #: Per function or method qualname, one ``(first line, last line,
    #: aliases)`` per definition written under it, shaped as
    #: :attr:`local_defs` and for the same reason (a qualname is not always
    #: one definition; the call's line says which): each alias is ``(N,
    #: the assignment's line, R's last name)`` for a name the definition's
    #: scope binds exactly once, by a plain ``N = R`` whose right-hand side
    #: is an identifier or an attribute chain of identifiers (ADR-160 step
    #: 1, :func:`_local_aliases`), sorted. Only an alias some bare call
    #: ``N(…)`` written in that definition's own scope uses is recorded: a
    #: fact nobody reads would cost every file a field. A definition left
    #: with no alias is left out, so most files carry an empty mapping;
    #: a class, and a module body, never has an entry.
    #: :mod:`hobbes.extract.aliases` reads the target off the settled graph
    #: at the assignment's line.
    local_aliases: dict[
        str, tuple[tuple[int, int, tuple[tuple[str, int, str], ...]], ...]
    ] = field(default_factory=dict)
    #: Whether the file binds the name ``callable`` anywhere (ADR-148).
    #: A module fact, read once per file and copied onto every
    #: :attr:`Symbol.inner_fold` the walk digests, because the fold must
    #: carry it: a ``callable(x)`` guard is only the builtin's answer
    #: where the module has not written a ``callable`` of its own.
    shadows_callable: bool = False
    #: Every test Pyright may read statically, in source order (ADR-154):
    #: an ``if`` / ``elif``, a ``while``, an ``assert``, an operand of an
    #: ``and`` / ``or``, a conditional expression's test. A test whose
    #: condition holds no form ADR-154 lists is not recorded.
    static_tests: list[StaticTest] = field(default_factory=list)
    #: ``(name, line)`` for each name an ``import sys [as X]`` binds, and
    #: for each an ``import typing [as X]`` / ``import typing_extensions
    #: [as X]`` binds, anywhere in the file (ADR-154). Pyright's binder
    #: learns them in order, so a test reads an alias written above it.
    sys_aliases: tuple[tuple[str, int], ...] = ()
    typing_aliases: tuple[tuple[str, int], ...] = ()
    #: Each name an ``import`` / ``from … import`` binds inside a function,
    #: with that innermost function's extent (ADR-154 step 6). Kept apart
    #: from :attr:`local_bindings` on purpose: the tail's ``local-binding``
    #: class names a binding the file writes itself, and an import names
    #: another module's; the fallback reads these to refuse a bare call they
    #: shadow.
    local_imports: list[LocalBinding] = field(default_factory=list)
    #: Every item of a sync ``with`` statement whose context expression is
    #: a call, in source order (ADR-156 step 1). The language runs the
    #: item's ``__enter__`` and ``__exit__`` and the source writes neither,
    #: so :mod:`hobbes.extract.withstmt` reads the class off the settled
    #: graph at the item's own call.
    with_items: list[WithItem] = field(default_factory=list)


def parse_source(source: bytes) -> ParsedFile:
    """Walk one file's source and collect its raw facts."""
    parsed = ParsedFile()
    root = _PARSER.parse(source).root_node
    parsed.shadows_callable = _binds_callable(root, source)
    parsed.docstring = _module_docstring(root)
    parsed.no_code = _holds_no_code(root)
    parsed.pytestmark = _pytestmark(root)
    parsed.pytestmark_usefixtures = sum(1 for m in parsed.pytestmark if not m.args)
    _walk(root, [], parsed, ())
    parsed.local_defs = _unshared_local_defs(parsed)
    parsed.local_aliases = _called_local_aliases(parsed)
    parsed.local_bindings = _collect_local_bindings(root)
    parsed.local_imports = _collect_local_imports(root)
    parsed.static_tests = _collect_static_tests(root)
    parsed.dynamic_loads = _dynamic_loads(root)
    parsed.type_facts = _type_facts(root)
    parsed.classmethods = _classmethods(root)
    parsed.sys_aliases, parsed.typing_aliases = _module_aliases(root)
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


def _import_bound_names(node: Node) -> list[str]:
    """The names one ``import`` / ``from … import`` statement binds: the
    alias if any, ``a`` for ``import a.b``, nothing for ``*``."""
    names: list[str] = []
    if node.type == "import_statement":
        children = node.named_children
    elif any(c.type == "wildcard_import" for c in node.children):
        return names
    else:
        children = node.children_by_field_name("name")
    for child in children:
        if child.type == "dotted_name":
            names.append(_text(child).split(".")[0])
        elif child.type == "aliased_import":
            names.append(_text(child.child_by_field_name("alias")))
    return names


def _collect_local_imports(root: Node) -> list[LocalBinding]:
    """Every name an import binds inside a function, with the innermost
    enclosing function's extent (ADR-154 step 6).

    A walk of its own beside :func:`_collect_local_bindings`, not part of
    it: ADR-046's list is what the tail classes ``local-binding``, a
    binding the file writes itself, and an imported name is not. A class
    body is its own namespace, so an import written there binds nothing
    in the function around it, as in :func:`_collect_local_bindings`.
    """
    out: list[LocalBinding] = []

    def walk(node: Node, extent: tuple[int, int] | None) -> None:
        kind = node.type
        if kind == "function_definition":
            own = (node.start_point.row + 1, node.end_point.row + 1)
            body = node.child_by_field_name("body")
            if body is not None:
                for child in body.children:
                    walk(child, own)
            return
        if kind == "class_definition":
            for child in node.children:
                walk(child, None)
            return
        if kind in ("import_statement", "import_from_statement"):
            if extent is not None:
                for name in _import_bound_names(node):
                    out.append(LocalBinding(name, extent[0], extent[1]))
            return
        for child in node.children:
            walk(child, extent)

    walk(root, None)
    return out


#: The modules whose aliases a static test reads (ADR-154): ``sys`` for
#: the platform and version forms, ``typing`` and ``typing_extensions``
#: for ``T.TYPE_CHECKING``.
_SYS_MODULES = ("sys",)
_TYPING_MODULES = ("typing", "typing_extensions")


def _module_aliases(
    root: Node,
) -> tuple[tuple[tuple[str, int], ...], tuple[tuple[str, int], ...]]:
    """``(name, line)`` for each name ``import sys [as X]`` binds, and for
    each ``import typing [as X]`` / ``import typing_extensions [as X]``
    binds, in source order, anywhere in the file (ADR-154). ``from sys
    import platform`` is not one: Pyright reads only the module's name."""
    sys_aliases: list[tuple[str, int]] = []
    typing_aliases: list[tuple[str, int]] = []

    def walk(node: Node) -> None:
        if node.type == "import_statement":
            for child in node.named_children:
                if child.type == "dotted_name":
                    module, bound = _text(child), _text(child)
                elif child.type == "aliased_import":
                    module = _text(child.child_by_field_name("name"))
                    bound = _text(child.child_by_field_name("alias"))
                else:
                    continue
                if module in _SYS_MODULES:
                    sys_aliases.append((bound, _line(node)))
                elif module in _TYPING_MODULES:
                    typing_aliases.append((bound, _line(node)))
            return
        for child in node.children:
            walk(child)

    walk(root)
    return tuple(sys_aliases), tuple(typing_aliases)


_STATIC_COMPARISONS = ("<", "<=", ">", ">=", "==", "!=")


def _last_line(node: Node) -> int:
    """The last line *node* holds text on, 1-based: an end point at column
    0 of a later row is the newline closing the line before it."""
    row = node.end_point.row
    if node.end_point.column == 0 and row > node.start_point.row:
        row -= 1
    return row + 1


def _clipped(first: int, last: int, after: int = 0, before: int | None = None):
    """``(first, last)`` less any line at or before *after* and at or
    after *before*, or None when nothing is left — a line the deciding
    test is written on holds live code, so it is never killed."""
    first = max(first, after + 1)
    if before is not None:
        last = min(last, before - 1)
    return (first, last) if first <= last else None


def _static_string(node: Node) -> str | None:
    """A string literal's value for a static comparison — a concatenated
    literal joined — or None for an f-string and anything else."""
    if node.type == "concatenated_string":
        parts = [_static_string(c) for c in node.named_children if c.type != "comment"]
        return None if any(p is None for p in parts) else "".join(parts)
    if node.type != "string":
        return None
    parts = []
    for child in node.children:
        if child.type == "string_start" and "f" in _text(child).lower():
            return None
        if child.type == "interpolation":
            return None
        if child.type == "string_content":
            parts.append(_text(child))
    return "".join(parts)


def _static_int(node: Node) -> int | None:
    """An integer literal's value, or None."""
    if node.type != "integer":
        return None
    try:
        return int(_text(node), 0)
    except ValueError:
        return None


def _static_comparison(node: Node) -> tuple:
    """One ``comparison_operator`` as ADR-154's encoding, or :data:`UNREAD`."""
    operands = [c for c in node.named_children if c.type != "comment"]
    operators = node.children_by_field_name("operators")
    if len(operands) != 2 or len(operators) != 1:
        return UNREAD
    op = _text(operators[0])
    if op not in _STATIC_COMPARISONS:
        return UNREAD
    left, right = operands
    if left.type == "attribute":
        obj = left.child_by_field_name("object")
        attr = _text(left.child_by_field_name("attribute"))
        if obj is None or obj.type != "identifier":
            return UNREAD
        receiver = _text(obj)
        if attr == "platform" and op in ("==", "!="):
            value = _static_string(right)
            if value is not None:
                return ("sys.platform", receiver, op, value)
        elif attr == "name" and receiver == "os" and op in ("==", "!="):
            value = _static_string(right)
            if value is not None:
                return ("os.name", op, value)
        elif attr == "version_info" and right.type == "tuple":
            # Pyright 0.6.6 reads a tuple of two or more elements by its
            # first two and ignores the rest, and a one-element tuple by
            # its one; each read element must be an integer literal.
            items = [c for c in right.named_children if c.type != "comment"]
            ints = [_static_int(c) for c in items[:2]]
            if ints and all(i is not None for i in ints):
                return ("sys.version_info", receiver, op, tuple(ints))
        return UNREAD
    if left.type == "subscript":
        value = left.child_by_field_name("value")
        index = left.children_by_field_name("subscript")
        if (
            value is not None
            and value.type == "attribute"
            and _text(value.child_by_field_name("attribute")) == "version_info"
            and value.child_by_field_name("object").type == "identifier"
            and len(index) == 1
            and _static_int(index[0]) == 0
        ):
            major = _static_int(right)
            if major is not None:
                receiver = _text(value.child_by_field_name("object"))
                return ("sys.version_info[0]", receiver, op, major)
    return UNREAD


def _bool_operands(node: Node) -> list[Node]:
    """A ``boolean_operator``'s operands, left to right, flattening the
    left-nested chain Python groups ``a and b and c`` into. A parenthesized
    operand is one operand."""
    op = _text(node.child_by_field_name("operator"))
    left = node.child_by_field_name("left")
    right = node.child_by_field_name("right")
    if left.type == "boolean_operator" and _text(left.child_by_field_name("operator")) == op:
        head = _bool_operands(left)
    else:
        head = [left]
    return [*head, right]


def _static_condition(node: Node) -> tuple:
    """A test expression as ADR-154's encoding (:class:`StaticTest`)."""
    kind = node.type
    if kind == "parenthesized_expression":
        inner = [c for c in node.named_children if c.type != "comment"]
        return _static_condition(inner[0]) if len(inner) == 1 else UNREAD
    if kind == "true":
        return ("const", True)
    if kind == "false":
        return ("const", False)
    if kind == "identifier":
        return ("TYPE_CHECKING", None) if _text(node) == "TYPE_CHECKING" else UNREAD
    if kind == "attribute":
        obj = node.child_by_field_name("object")
        if (
            obj is not None
            and obj.type == "identifier"
            and _text(node.child_by_field_name("attribute")) == "TYPE_CHECKING"
        ):
            return ("TYPE_CHECKING", _text(obj))
        return UNREAD
    if kind == "not_operator":
        argument = node.child_by_field_name("argument")
        return ("not", _static_condition(argument)) if argument is not None else UNREAD
    if kind == "boolean_operator":
        op = _text(node.child_by_field_name("operator"))
        return (op, tuple(_static_condition(o) for o in _bool_operands(node)))
    if kind == "comparison_operator":
        return _static_comparison(node)
    return UNREAD


def _has_static_form(condition: tuple) -> bool:
    """Whether *condition* holds any form ADR-154 lists."""
    head = condition[0]
    if head == "unread":
        return False
    if head == "not":
        return _has_static_form(condition[1])
    if head in ("and", "or"):
        return any(_has_static_form(c) for c in condition[1])
    return True


def _ends_in_raise(block: Node | None) -> bool:
    """Whether *block*'s last statement, comments aside, is a ``raise``."""
    if block is None:
        return False
    statements = [c for c in block.named_children if c.type != "comment"]
    return bool(statements) and statements[-1].type == "raise_statement"


def _rest_of_block(node: Node) -> tuple[int, int] | None:
    """The span of the statements after *node* in its block, or None."""
    rest = []
    sibling = node.next_named_sibling
    while sibling is not None:
        if sibling.type != "comment":
            rest.append(sibling)
        sibling = sibling.next_named_sibling
    if not rest:
        return None
    return _clipped(_line(rest[0]), _last_line(rest[-1]), _last_line(node))


def _collect_static_tests(root: Node) -> list[StaticTest]:
    """Every test Pyright 0.6.6 may read statically, with the spans each
    kills on True and on False (ADR-154).

    The contexts, exactly ADR-154's: an ``if`` and each ``elif`` (False
    kills its own consequence, True every later clause; and, C-173's
    widening, the rest of the block after the ``if`` where the branch that
    reading runs ends in ``raise``: the ``if`` on True, its ``else`` on
    False when there is no ``elif``); a ``while``
    (False its body, True its ``else``); an ``assert`` (False the rest of
    its block); each operand of an ``and`` / ``or`` but the last (the
    operands after it, on False for ``and``, on True for ``or``); and a
    conditional expression's test (True kills the ``else`` arm, False the
    first). What the test reads as is :mod:`hobbes.extract.pystatic`'s
    question; this records only what is written.
    """
    out: list[StaticTest] = []

    def record(test: Node, on_true, on_false) -> None:
        condition = _static_condition(test)
        on_true = tuple(s for s in on_true if s is not None)
        on_false = tuple(s for s in on_false if s is not None)
        if _has_static_form(condition) and (on_true or on_false):
            out.append(StaticTest(_line(test), condition, on_true, on_false))

    def span(node: Node, after: int):
        return _clipped(_line(node), _last_line(node), after)

    def walk(node: Node) -> None:
        kind = node.type
        if kind == "if_statement":
            clauses = [node, *node.children_by_field_name("alternative")]
            # C-173's widening: a branch that ends in `raise` ends its block
            # when it runs, so the rest of the block after the `if` is never
            # run either. Only where the branch's running is one test's
            # reading: the `if` on True, and its `else` on False when no
            # `elif` stands between them.
            rest = _rest_of_block(node)
            for i, clause in enumerate(clauses):
                test = clause.child_by_field_name("condition")
                body = clause.child_by_field_name("consequence")
                if test is None or body is None:
                    continue
                after = _last_line(test)
                on_true = [span(later, after) for later in clauses[i + 1 :]]
                on_false = [span(body, after)]
                if i == 0 and rest is not None:
                    if _ends_in_raise(body):
                        on_true.append(rest)
                    if len(clauses) == 2 and clauses[1].type == "else_clause":
                        if _ends_in_raise(clauses[1].child_by_field_name("body")):
                            on_false.append(rest)
                record(test, on_true, on_false)
        elif kind == "while_statement":
            test = node.child_by_field_name("condition")
            body = node.child_by_field_name("body")
            other = node.child_by_field_name("alternative")
            if test is not None and body is not None:
                after = _last_line(test)
                record(test, [span(other, after)] if other is not None else [], [span(body, after)])
        elif kind == "assert_statement":
            named = [c for c in node.named_children if c.type != "comment"]
            rest = []
            sibling = node.next_named_sibling
            while sibling is not None:
                if sibling.type != "comment":
                    rest.append(sibling)
                sibling = sibling.next_named_sibling
            if named and rest:
                killed = _clipped(_line(rest[0]), _last_line(rest[-1]), _last_line(node))
                record(named[0], [], [killed])
        elif kind == "boolean_operator":
            operands = _bool_operands(node)
            is_and = _text(node.child_by_field_name("operator")) == "and"
            for i, operand in enumerate(operands[:-1]):
                killed = _clipped(
                    _line(operands[i + 1]), _last_line(operands[-1]), _last_line(operand)
                )
                record(operand, [] if is_and else [killed], [killed] if is_and else [])
            for operand in operands:
                walk(operand)
            return
        elif kind == "conditional_expression":
            parts = [c for c in node.named_children if c.type != "comment"]
            if len(parts) == 3:
                then, test, other = parts
                record(
                    test,
                    [span(other, _last_line(test))],
                    [_clipped(_line(then), _last_line(then), before=_line(test))],
                )
        for child in node.children:
            walk(child)

    walk(root)
    return out


def _type_of(node: Node | None) -> object:
    """A type annotation or alias value as ADR-168 reads it."""
    if node is None:
        return UNREAD_TYPE
    kind = node.type
    if kind in ("type", "parenthesized_expression"):
        inner = [c for c in node.named_children if c.type != "comment"]
        return _type_of(inner[0]) if len(inner) == 1 else UNREAD_TYPE
    if kind == "identifier":
        return _text(node)
    if kind == "attribute":
        attribute = node.child_by_field_name("attribute")
        return _text(attribute) if attribute is not None else UNREAD_TYPE
    if kind == "none":
        return "None"
    if kind == "binary_operator" and _text(node.child_by_field_name("operator")) == "|":
        return ("|", (_type_of(node.child_by_field_name("left")), _type_of(node.child_by_field_name("right"))))
    if kind in ("subscript", "generic_type"):
        if kind == "subscript":
            head = node.child_by_field_name("value")
            args = node.children_by_field_name("subscript")
        else:
            head = node.named_children[0] if node.named_children else None
            parameter = next((c for c in node.named_children if c.type == "type_parameter"), None)
            args = [c for c in parameter.named_children if c.type != "comment"] if parameter is not None else []
        name = _type_of(head) if head is not None else UNREAD_TYPE
        if name == "Union" and args:
            return ("|", tuple(_type_of(a) for a in args))
        if name == "Optional" and len(args) == 1:
            return ("|", (_type_of(args[0]), "None"))
        return UNREAD_TYPE
    if kind == "string":
        text = _static_string(node)
        if text is None:
            return UNREAD_TYPE
        inner = _PARSER.parse(text.encode()).root_node
        statement = inner.named_children[0] if inner.named_children else None
        if statement is None or statement.type != "expression_statement" or not statement.named_children:
            return UNREAD_TYPE
        return _type_of(statement.named_children[0])
    return UNREAD_TYPE


def _last_name(node: Node | None) -> str | None:
    if node is None:
        return None
    if node.type == "identifier":
        return _text(node)
    if node.type == "attribute":
        attribute = node.child_by_field_name("attribute")
        return _text(attribute) if attribute is not None else None
    return None


def _own_nodes(body: Node):
    """Every node under *body* except what a nested def or class holds."""
    stack = list(reversed(body.children))
    while stack:
        node = stack.pop()
        yield node
        if node.type in ("function_definition", "class_definition", "lambda"):
            continue
        stack.extend(reversed(node.children))


def _type_facts(root: Node) -> TypeFacts:
    """The type facts ADR-168 reads; see :class:`TypeFacts`."""
    aliases: list[tuple[str, object]] = []
    for statement in root.named_children:
        if statement.type == "type_alias_statement":
            left = statement.child_by_field_name("left")
            name = _type_of(left)
            if isinstance(name, str):
                aliases.append((name, _type_of(statement.child_by_field_name("right"))))
            continue
        inner = statement.named_children[0] if statement.type == "expression_statement" and statement.named_children else None
        if inner is None or inner.type != "assignment":
            continue
        left = inner.child_by_field_name("left")
        right = inner.child_by_field_name("right")
        if left is None or left.type != "identifier" or right is None:
            continue
        annotation = inner.child_by_field_name("type")
        value = _type_of(right)
        if annotation is not None and _type_of(annotation) == "TypeAlias":
            aliases.append((_text(left), value))
        elif annotation is None and isinstance(value, tuple) and value[0] == "|":
            aliases.append((_text(left), value))

    classes: list = []
    attributes: list = []
    returns: list = []
    getitems: list = []
    receivers: list[ReceiverRead] = []
    heads: list = []
    for node in _walk_all(root):
        kind = node.type
        if kind == "class_definition":
            name = node.child_by_field_name("name")
            body = node.child_by_field_name("body")
            supers = node.child_by_field_name("superclasses")
            bases = tuple(
                n for n in (_last_name(c) for c in (supers.named_children if supers is not None else ())) if n
            )
            methods = []
            for child in body.named_children if body is not None else ():
                definition = child.child_by_field_name("definition") if child.type == "decorated_definition" else child
                if definition is not None and definition.type == "function_definition":
                    methods.append(_text(definition.child_by_field_name("name")))
                if child.type == "expression_statement" and child.named_children:
                    assign = child.named_children[0]
                    target = assign.child_by_field_name("left") if assign.type == "assignment" else None
                    if target is not None and target.type == "identifier" and assign.child_by_field_name("type") is not None:
                        attributes.append((_text(target), _type_of(assign.child_by_field_name("type"))))
            if name is not None:
                classes.append((_text(name), tuple(methods), bases))
            base_nodes = [
                c for c in (supers.named_children if supers is not None else ())
                if c.type not in ("keyword_argument", "comment")
            ]
            heads_named = tuple(
                n for n in (
                    _last_name(c.child_by_field_name("value") if c.type in ("subscript", "generic_type") else c)
                    for c in base_nodes
                ) if n
            )
            if heads_named:
                heads.append((_line(node), _last_line(base_nodes[-1]), heads_named))
        elif kind == "assignment":
            target = node.child_by_field_name("left")
            annotation = node.child_by_field_name("type")
            if (
                annotation is not None and target is not None and target.type == "attribute"
                and _last_name(target.child_by_field_name("object")) == "self"
            ):
                attributes.append((_text(target.child_by_field_name("attribute")), _type_of(annotation)))
        elif kind == "function_definition":
            name = _text(node.child_by_field_name("name"))
            returned = node.child_by_field_name("return_type")
            if returned is not None:
                returns.append((name, _type_of(returned)))
                if name == "__getitem__":
                    getitems.append(_type_of(returned))
            receivers.extend(_receiver_reads(node))
    return TypeFacts(
        tuple(aliases), tuple(classes), tuple(attributes), tuple(returns), tuple(getitems), tuple(receivers),
        tuple(heads),
    )


def _classmethods(root: Node) -> tuple[tuple[str, int, int, str], ...]:
    """Every ``@classmethod`` written directly in a class body (ADR-170)."""
    out: list[tuple[str, int, int, str]] = []

    def visit(node: Node, stack: list[str]) -> None:
        for child in node.named_children:
            definition = child.child_by_field_name("definition") if child.type == "decorated_definition" else child
            if definition is None or definition.type not in ("class_definition", "function_definition"):
                if child.type not in ("function_definition", "class_definition", "decorated_definition"):
                    visit(child, stack)
                continue
            name = _text(definition.child_by_field_name("name"))
            body = definition.child_by_field_name("body")
            if definition.type == "class_definition":
                if body is not None:
                    for member in body.named_children:
                        inner = member.child_by_field_name("definition") if member.type == "decorated_definition" else None
                        if (
                            inner is not None
                            and inner.type == "function_definition"
                            and any(
                                _text(d.named_children[0]) == "classmethod"
                                for d in member.named_children
                                if d.type == "decorator" and d.named_children
                                and d.named_children[0].type == "identifier"
                            )
                            and not _rebinds_cls(inner)
                        ):
                            qualname = ".".join([*stack, name, _text(inner.child_by_field_name("name"))])
                            out.append((qualname, _line(member), _last_line(inner), ".".join([*stack, name])))
            if body is not None:
                visit(body, [*stack, name])

    visit(root, [])
    return tuple(out)


def _rebinds_cls(function: Node) -> bool:
    """Whether *function*'s own body binds the name ``cls`` again."""
    body = function.child_by_field_name("body")
    for node in _own_nodes(body) if body is not None else ():
        if node.type in ("assignment", "augmented_assignment", "for_statement", "for_in_clause"):
            target = node.child_by_field_name("left")
            if target is not None and any(
                n.type == "identifier" and _text(n) == "cls" for n in _walk_all(target)
            ):
                return True
        if node.type in ("as_pattern_target", "named_expression"):
            name = node.child_by_field_name("name") if node.type == "named_expression" else node
            if name is not None and any(n.type == "identifier" and _text(n) == "cls" for n in _walk_all(name)):
                return True
    return False


def _walk_all(root: Node):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def _receiver_reads(function: Node) -> list[ReceiverRead]:
    """Each method call in *function*'s own body with a receiver ADR-168 can read."""
    body = function.child_by_field_name("body")
    if body is None:
        return []
    params: dict[str, object] = {}
    parameters = function.child_by_field_name("parameters")
    for parameter in parameters.named_children if parameters is not None else ():
        if parameter.type in ("typed_parameter", "typed_default_parameter"):
            ident = parameter.child_by_field_name("name") or next(
                (c for c in parameter.named_children if c.type == "identifier"), None
            )
            if ident is not None:
                params[_text(ident)] = _type_of(parameter.child_by_field_name("type"))
    nodes = list(_own_nodes(body))
    binds: dict[str, list[Node]] = defaultdict(list)
    for node in nodes:
        if node.type == "assignment":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is not None and left.type == "identifier":
                binds[_text(left)].append(right)
    out: list[ReceiverRead] = []
    for node in nodes:
        if node.type != "call":
            continue
        function_node = node.child_by_field_name("function")
        if function_node is None or function_node.type != "attribute":
            continue
        receiver = function_node.child_by_field_name("object")
        attribute = function_node.child_by_field_name("attribute")
        if receiver is None or attribute is None:
            continue
        read = None
        if receiver.type == "identifier":
            name = _text(receiver)
            if name in params:
                read = ("param", params[name])
            elif len(binds.get(name, ())) == 1 and binds[name][0] is not None and binds[name][0].type == "call":
                callee = _last_name(binds[name][0].child_by_field_name("function"))
                if callee:
                    read = ("local", callee)
        elif receiver.type == "attribute":
            name = _last_name(receiver)
            if name:
                read = ("attribute", name)
        elif receiver.type == "subscript":
            read = ("subscript", None)
        elif receiver.type == "call":
            callee = _last_name(receiver.child_by_field_name("function"))
            if callee:
                read = ("result", callee)
        if read is not None:
            out.append(ReceiverRead(
                attribute.start_point.row + 1, attribute.start_point.column, _text(attribute), *read
            ))
    return out


#: The callees, by last name, that load a module by name (ADR-167).
_LOADERS = ("import_module", "__import__", "spec_from_file_location")


def _dynamic_loads(root: Node) -> tuple[DynamicLoad, ...]:
    """Every call to a loader, with what it names as written (ADR-167).

    ``import_module`` and ``__import__``: the first argument, when it is a
    plain string literal. ``spec_from_file_location``: the location (second
    argument, or ``location=``) — a string literal, or the trailing string
    literals of a ``/`` chain — followed through one module-level
    assignment when it is a bare name, and kept only when it ends in
    ``.py``. Nothing is resolved here; the graph places what is written.
    """
    counts: Counter = Counter()
    values: dict[str, Node] = {}
    for statement in root.named_children:
        inner = statement.named_children[0] if statement.named_children else None
        if statement.type != "expression_statement" or inner is None or inner.type != "assignment":
            continue
        left = inner.child_by_field_name("left")
        right = inner.child_by_field_name("right")
        if left is not None and left.type == "identifier" and right is not None:
            counts[_text(left)] += 1
            values[_text(left)] = right
    module_values = {name: node for name, node in values.items() if counts[name] == 1}

    out: list[DynamicLoad] = []

    def walk(node: Node) -> None:
        if node.type == "call":
            function = node.child_by_field_name("function")
            name = None
            if function is not None and function.type == "identifier":
                name = _text(function)
            elif function is not None and function.type == "attribute":
                attribute = function.child_by_field_name("attribute")
                name = _text(attribute) if attribute is not None else None
            if name in _LOADERS:
                out.append(DynamicLoad(_line(node), name, _load_written(
                    name, node.child_by_field_name("arguments"), module_values
                )))
        for child in node.children:
            walk(child)

    walk(root)
    return tuple(out)


def _load_written(via: str, arguments: Node | None, module_values: dict[str, Node]) -> str:
    if arguments is None:
        return ""
    named = [c for c in arguments.named_children if c.type != "comment"]
    positional = [c for c in named if c.type != "keyword_argument"]
    if via != "spec_from_file_location":
        return (_static_string(positional[0]) or "") if positional else ""
    location = positional[1] if len(positional) > 1 else None
    for keyword in (c for c in named if c.type == "keyword_argument"):
        if _text(keyword.child_by_field_name("name")) == "location":
            location = keyword.child_by_field_name("value")
    if location is not None and location.type == "identifier":
        location = module_values.get(_text(location))
    tail = _path_tail(location) if location is not None else None
    return tail if tail and tail.endswith(".py") else ""


def _path_tail(node: Node) -> str | None:
    """A string literal, or a ``/`` chain's trailing string literals joined."""
    if node.type == "binary_operator" and _text(node.child_by_field_name("operator")) == "/":
        right = _static_string(node.child_by_field_name("right"))
        if right is None:
            return None
        left = _path_tail(node.child_by_field_name("left"))
        return f"{left}/{right}" if left else right
    return _static_string(node)


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


def _holds_no_code(root: Node) -> bool:
    """Whether the file is, comments aside, empty or one bare string
    (ADR-117's amendment). A parse with an error says nothing."""
    if root.has_error:
        return False
    statements = [child for child in root.named_children if child.type != "comment"]
    if not statements:
        return True
    if len(statements) > 1 or statements[0].type != "expression_statement":
        return False
    inner = statements[0].named_children
    return len(inner) == 1 and inner[0].type == "string"


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


def _call(expr: Node, line: int, *, at_a_decorator: bool = True) -> Decorator:
    """Digest one ``call`` node written as a mark: its dotted name, its
    string-literal positionals, and the keywords the walk can read.

    Split out of :func:`_decorator` because a mark is the same expression
    wherever it is written — after an ``@``, or as the value of a
    module-level ``pytestmark`` (ADR-139's amendment).

    Everything digested here is call-form, so ``called`` is True and
    ``callee_line`` is the callee's terminal identifier — where the
    semantic lane puts its occurrence, which is not *line* whenever the
    chain wraps (ADR-147). ``bound`` — the arguments ADR-148 folds a
    factory's guards over — is read only where the call really is a
    decorator site: a ``pytestmark`` entry applies to no definition here
    and is never folded, so it is left ``None`` rather than digested
    twice over.
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
        bound=_bound_arguments(arguments) if at_a_decorator else None,
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
                _call(mark, _line(mark), at_a_decorator=False)
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


def _own_nodes(node: Node):
    """*node* itself and every descendant written in the same scope.

    :func:`_own_body`'s containment rule, asked about one statement
    rather than about a whole body (ADR-148): the descent stops **at** a
    nested ``def``, ``class`` or ``lambda`` but still yields it, because
    what such a definition binds outside itself is its name — a fact
    :func:`_bound_here` reads and a fold must not lose.
    """
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        if current.type in ("function_definition", "class_definition", "lambda"):
            continue
        stack.extend(current.children)


def _valued_exit(node: Node) -> Node | None:
    """The one value a definition's own body hands back, or ``None``.

    Exactly one ``return`` or ``yield`` in the own body may carry a value:
    two valued exits mean the definition chooses, a bare ``return``
    carries nothing and is not one of them, and ``yield from g()``
    delegates — a valued exit this walk cannot read, so it counts and
    then refuses.
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
    if len(values) != 1:
        return None
    return values[0]


def _returned_value(node: Node) -> tuple[tuple[str, int] | None, str | None]:
    """The class a definition constructs and hands back, and the local it
    came through (ADR-145 and its amendment).

    Returns ``(value, local)``: the written class name with its line, and
    the local the value passed through or ``None`` where the returned
    value *was* the construction. ``return CliRunner()`` names
    ``CliRunner`` directly; ``app = Flask("x")`` … ``return app`` names
    ``Flask`` through ``app``, because a local bound once, by a
    construction, at the top level of the body, before the return, holds
    nothing else.

    Everything else is ``(None, None)``, because everything else leaves
    the runtime class of what comes back open: ``return a.b()`` is a call
    on a value, and a returned name the body binds twice, binds in a
    branch, binds from a factory, or a nested ``def`` could rebind
    through ``nonlocal`` is a name this walk cannot settle.
    """
    value = _valued_exit(node)
    if value is None:
        return None, None
    if value.type == "call":
        function = value.child_by_field_name("function")
        if function is None or function.type != "identifier":
            return None, None
        return (_text(function), _line(function)), None
    if value.type == "identifier":
        return _value_through_local(node, value)
    return None, None


def _value_through_local(
    node: Node, returned: Node
) -> tuple[tuple[str, int] | None, str | None]:
    """Condition 2's local form (ADR-145's amendment), asked of the bare
    name a definition returns.

    The name must be no parameter of the definition; the own body must
    bind it **exactly once** — nodes counted, not names unioned, so a
    second binding of any form refuses — and that one binding must be a
    plain assignment written as a statement of the body itself (not in a
    branch, not in a loop), with one bare-identifier target, a call on a
    bare name as its value, and a line before the return's. And no
    ``global`` or ``nonlocal`` anywhere in the definition may name it: a
    nested ``def`` declaring it could rebind it between the assignment
    and the return. A nested ``def x`` or ``class x`` is a second binding
    like any other.
    """
    name = _text(returned)
    if name in _parameter_names(node):
        return None, None
    binders = [current for current in _own_body(node) if name in _bound_here(current)]
    if len(binders) != 1 or binders[0].type != "assignment":
        return None, None
    binder = binders[0]
    body = node.child_by_field_name("body")
    statement = binder.parent
    if (
        body is None
        or statement is None
        or statement.type != "expression_statement"
        or statement.parent is None
        or statement.parent.id != body.id
    ):
        return None, None
    left = binder.child_by_field_name("left")
    right = binder.child_by_field_name("right")
    if left is None or left.type != "identifier":
        return None, None
    if right is None or right.type != "call":
        return None, None
    function = right.child_by_field_name("function")
    if function is None or function.type != "identifier":
        return None, None
    if _line(binder) >= _line(returned):
        return None, None
    if _declared_outer(node, name):
        return None, None
    # A nested `def x` or `class x` binds the name too, and `_own_body`
    # never yields one: the walk it does not do is `_own_definitions`'.
    if any(
        _text(definition.child_by_field_name("name") or definition) == name
        for definition, _decorated in _own_definitions(node)
    ):
        return None, None
    return (_text(function), _line(function)), name


def _declared_outer(node: Node, name: str) -> bool:
    """Whether a ``global`` or ``nonlocal`` anywhere in the definition's
    subtree — nested definitions included — names *name* (ADR-145's
    amendment). The one walk here that deliberately does not stop at a
    nested ``def``: what such a declaration reaches is this scope's
    binding, from inside another."""
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type in ("global_statement", "nonlocal_statement") and any(
            _text(child) == name for child in current.named_children
        ):
            return True
        stack.extend(current.children)
    return False


def _attribute_targets(node: Node | None):
    """The ``a.b`` nodes in an assignment or ``del`` target expression,
    through the list forms a statement may write several in."""
    if node is None:
        return
    if node.type == "attribute":
        yield node
    elif node.type in (
        "expression_list",
        "pattern_list",
        "tuple_pattern",
        "list_pattern",
        "tuple",
        "list",
        "parenthesized_expression",
    ):
        for child in node.named_children:
            yield from _attribute_targets(child)


def _setattr_target(call: Node) -> str | None:
    """The bare name a ``setattr``-named call patches, or ``None``.

    Read by the callee's last component, as a decorator's spelling is:
    ``setattr(p, …)`` and ``monkeypatch.setattr(p, …)`` are the same act
    reached two ways. Only a bare identifier written as the first
    positional argument counts — anything else is a receiver this walk
    cannot name.
    """
    function = call.child_by_field_name("function")
    if function is None:
        return None
    if function.type == "identifier":
        named = function
    elif function.type == "attribute":
        named = function.child_by_field_name("attribute")
    else:
        return None
    if named is None or _text(named) != "setattr":
        return None
    arguments = call.child_by_field_name("arguments")
    if arguments is None:
        return None
    for argument in arguments.named_children:
        if argument.type in ("keyword_argument", "comment"):
            continue
        return _text(argument) if argument.type == "identifier" else None
    return None


def _patched(node: Node) -> tuple[tuple[str, str], ...]:
    """What a definition's own body stores onto, or deletes from, the bare
    names it holds (ADR-145's amendment).

    ``p.m = f``, ``p.m += 1``, ``p.m: T = f`` and ``del p.m`` are each
    ``(p, m)``; ``p.__class__ = K`` and any ``setattr`` on ``p`` are
    ``(p, "*")``, because neither leaves one named attribute the class's
    ``def`` still answers for. An annotation with no value stores
    nothing. Own body only: what a nested ``def`` patches, it patches
    when something calls it, and this walk does not say when that is.
    """
    out: set[tuple[str, str]] = set()
    for current in _own_body(node):
        kind = current.type
        if kind == "call":
            patched = _setattr_target(current)
            if patched is not None:
                out.add((patched, "*"))
            continue
        if kind not in ("assignment", "augmented_assignment", "delete_statement"):
            continue
        if kind == "assignment" and current.child_by_field_name("right") is None:
            continue  # `p.m: int` declares a type and stores nothing
        targets = (
            list(current.named_children)
            if kind == "delete_statement"
            else [current.child_by_field_name("left")]
        )
        for target in targets:
            for attribute in _attribute_targets(target):
                obj = attribute.child_by_field_name("object")
                name = attribute.child_by_field_name("attribute")
                if obj is None or obj.type != "identifier" or name is None:
                    continue
                written = _text(name)
                out.add((_text(obj), "*" if written == "__class__" else written))
    return tuple(sorted(out))


def _class_binds(node: Node) -> tuple[str, ...]:
    """The names a class's own body binds by any form other than a ``def``
    (ADR-145's amendment).

    :func:`_own_body` stops at every nested definition, so what it yields
    is exactly the non-definition forms; the nested ``class`` statements
    are added back from :func:`_own_definitions`, because a class written
    in a class body binds its name there as an attribute. A nested ``def``
    is not added: that is a method, which the rule reading this fact looks
    for first and by itself.
    """
    bound = _bound_in(_own_body(node))
    for definition, _decorated in _own_definitions(node):
        if definition.type == "class_definition":
            name = definition.child_by_field_name("name")
            if name is not None:
                bound.add(_text(name))
    return tuple(sorted(bound))


def _import_binding(node: Node) -> str | None:
    """The bare name one import clause binds: the alias where it renames,
    else the first component (``import a.b`` binds ``a``)."""
    if node.type == "aliased_import":
        alias = node.child_by_field_name("alias")
        return _text(alias) if alias is not None else None
    if node.type == "dotted_name" and node.named_children:
        return _text(node.named_children[0])
    return None


#: The node kinds :func:`_bound_here` reads. Every other kind binds no
#: bare name, and the check is worth writing out: the walks below ask
#: this question of every node in a file.
_BINDING_NODES = frozenset(
    {
        "assignment",
        "augmented_assignment",
        "for_statement",
        "named_expression",
        "as_pattern",
        "delete_statement",
        "global_statement",
        "nonlocal_statement",
        "import_statement",
        "import_from_statement",
        "function_definition",
        "class_definition",
    }
)


def _bound_here(current: Node) -> set[str]:
    """The bare names **one** node binds in the scope it is written in.

    Every form that binds a bare name: assignment and augmented
    assignment, an annotation *with* a value (``x: int`` alone binds
    nothing), a walrus, a ``for`` / ``with`` / ``except`` target, an
    import, ``del``, ``global``, ``nonlocal``, and a nested ``def`` or
    ``class``, which binds its own name outside itself. Attribute and
    subscript targets bind no name, so ``p.x = 1`` is not a binding of
    ``p``.

    One node, so a caller chooses the walk: :func:`_rebound` asks it over
    a definition's own body (ADR-145), :func:`_statement_binds` over one
    statement (ADR-148), :func:`_binds_callable` over a whole file.
    """
    kind = current.type
    if kind not in _BINDING_NODES:
        return set()
    bound: set[str] = set()

    def take(target: Node) -> None:
        for ident in _target_identifiers(target):
            bound.add(_text(ident))

    if kind == "assignment" and current.child_by_field_name("right") is None:
        return bound  # `x: int` declares a type and binds nothing
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
    elif kind in ("function_definition", "class_definition"):
        name = current.child_by_field_name("name")
        if name is not None:
            bound.add(_text(name))
    bound.discard("")
    return bound


def _bound_in(nodes) -> set[str]:
    """Every bare name the given nodes bind, unioned."""
    bound: set[str] = set()
    for current in nodes:
        bound |= _bound_here(current)
    return bound


def _rebound(node: Node, params: tuple[tuple[str, int], ...]) -> tuple[str, ...]:
    """Which of *params* the definition's own body binds again (ADR-145).

    :func:`_own_body` never yields a nested ``def`` or ``class``, so the
    name one of those binds is not a rebinding here — a definition
    written inside the body binds in that body, but the walk that reads
    this fact deliberately does not descend to it.
    """
    names = {name for name, _ in params}
    if not names:
        return ()
    return tuple(sorted(_bound_in(_own_body(node)) & names))


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


def _lambda_and_comprehension_binds(node: Node) -> set[str]:
    """Every name a ``lambda``'s parameters or a comprehension's ``for``
    target binds in a definition's **own** scope (ADR-153 step 1).

    The two binding forms the walk's other reads leave out:
    :func:`_own_body` stops *at* a ``lambda`` and never yields it, and
    :func:`_bound_here` reads neither a ``lambda_parameters`` nor a
    ``for_in_clause``. A rule that claims a name is the definition's one
    nested ``def`` has to see them, because a call written inside that
    lambda or that comprehension sees the parameter or the target under
    the name, not the ``def``.

    The descent goes *into* every lambda — a lambda written in a lambda
    is still written in this scope — and stops at a nested ``def`` or
    ``class``, whose own lambdas and comprehensions are that definition's.
    """
    bound: set[str] = set()
    body = node.child_by_field_name("body")
    if body is None:
        return bound
    stack = list(body.children)
    while stack:
        current = stack.pop()
        kind = current.type
        if kind in ("function_definition", "class_definition"):
            continue
        if kind == "lambda":
            bound |= _parameter_names(current)
        elif kind == "for_in_clause":
            left = current.child_by_field_name("left")
            if left is not None:
                for ident in _target_identifiers(left):
                    bound.add(_text(ident))
        stack.extend(current.children)
    return bound


def _local_defs(node: Node) -> tuple[str, ...]:
    """The names a function's own scope binds **exactly once, by a**
    ``def`` **written in its own body**, sorted (ADR-153 step 1).

    Python's own rule for such a name is syntax: the name is local to the
    function, and the function's only binding of it is that ``def``, so a
    call of the name that succeeds calls it. The claim holds only while
    nothing else in the scope can have bound the name, and every way it
    can is refused here:

    - a second ``def`` of the name, or a ``class`` of it, in the own body
      (counted from :func:`_own_definitions`, which is where a nested
      definition's name is visible at all); a **decorated** ``def``
      counts as the one binding (ADR-153 step 4 — ``@dec`` binds the name
      to what ``dec`` returned, which is still what a call of the name
      reaches);
    - a parameter of the definition, of any kind;
    - any of :func:`_bound_here`'s forms over the own body — assignment,
      augmented and annotated-with-a-value, walrus, ``for`` / ``with`` /
      ``except`` target, import, ``del``;
    - a ``global`` or ``nonlocal`` naming it anywhere under the
      definition, nested definitions included;
    - a lambda parameter or a comprehension target of the name written in
      the own scope (:func:`_lambda_and_comprehension_binds`).

    A body holding a ``match`` statement or a ``type`` alias statement
    has no such names at all: both bind names, and this walk's binding
    read covers neither, so the function is refused whole rather than
    read with a gap. Order the walk cannot settle — a call written above
    the ``def``, a ``def`` in a branch that did not run — is *not*
    guarded (ADR-153 step 5): the name has no other binding, so such a
    call raises ``UnboundLocalError`` rather than reaching anything else.
    """
    own = list(_own_body(node))
    for current in own:
        if current.type in ("match_statement", "type_alias_statement"):
            return ()
    counts: dict[str, int] = {}
    kinds: dict[str, str] = {}
    for definition, _decorated in _own_definitions(node):
        name_node = definition.child_by_field_name("name")
        if name_node is None:
            continue
        name = _text(name_node)
        counts[name] = counts.get(name, 0) + 1
        kinds[name] = definition.type
    if not counts:
        return ()
    otherwise = (
        _parameter_names(node) | _bound_in(own) | _lambda_and_comprehension_binds(node)
    )
    return tuple(
        sorted(
            name
            for name, count in counts.items()
            if count == 1
            and kinds[name] == "function_definition"
            and name not in otherwise
            and not _declared_outer(node, name)
        )
    )


def _unshared_local_defs(parsed: ParsedFile) -> dict:
    """:attr:`ParsedFile.local_defs` as the walk collected it, less every
    name whose target the graph cannot name (ADR-153 step 1).

    The target of the rule is the symbol ``F.N``, and the graph keeps one
    symbol per qualname — the first written. Where two definitions in the
    file are both ``F.N`` (an ``if``/``else`` pair of ``def F``, each
    nesting its own ``def N``), an edge from the second ``F`` would land
    on the first one's ``N``, so the name is dropped from both. A
    qualname written more than once is otherwise no refusal: click's
    ``Group.command`` is two ``@overload`` stubs and the implementation,
    and only the implementation writes ``decorator``. Definitions left
    with no name, and qualnames left with no definition, go.
    """
    written: dict[str, int] = {}
    for symbol in parsed.symbols:
        written[symbol.qualname] = written.get(symbol.qualname, 0) + 1
    out: dict[str, tuple[tuple[int, int, tuple[str, ...]], ...]] = {}
    for qualname, definitions in parsed.local_defs.items():
        kept = []
        for start, end, names in definitions:
            names = tuple(n for n in names if written.get(f"{qualname}.{n}") == 1)
            if names:
                kept.append((start, end, names))
        if kept:
            out[qualname] = tuple(kept)
    return out


def _alias_binder(current: Node) -> tuple[str, str, str] | None:
    """``(N, R's root, R's last name)`` where *current* is ADR-160's binder,
    else None.

    A plain ``N = R``: one identifier target, no annotation (``N: T = R``
    is another binder), and a right-hand side that is an identifier or an
    attribute chain of identifiers and nothing else — no call, subscript,
    string or other expression anywhere in it. A chained ``N = M = R``
    nests one assignment as the other's right-hand side, and neither one
    is the binder: the outer's right is no name, and the inner is refused
    by its parent. The fields are read by name, never by position, so a
    comment child is never mistaken for a side.
    """
    if current.type != "assignment" or current.child_by_field_name("type") is not None:
        return None
    if current.parent is not None and current.parent.type == "assignment":
        return None
    left = current.child_by_field_name("left")
    right = current.child_by_field_name("right")
    if left is None or left.type != "identifier" or right is None:
        return None
    dotted = _dotted(right)
    if dotted is None:
        return None
    root, _, _ = dotted.partition(".")
    return _text(left), root, dotted.rpartition(".")[2]


def _local_aliases(node: Node) -> tuple[tuple[str, int, str], ...]:
    """``(N, the assignment's line, R's last name)`` for each name a
    function's own scope binds **exactly once, by a plain** ``N = R``
    (ADR-160 step 1), sorted.

    :func:`_alias_binder` says what the one binding must be, and R's root
    must not be N (``N = N.x`` reads N before it binds it). Everything
    else is :func:`_local_defs`' refusal, read for this binder: N is left
    out where the own body binds it a second time by any of
    :func:`_bound_here`'s forms — nodes counted, so the alias's own
    assignment is one and anything else is a second — or where a nested
    ``def`` or ``class`` writes it (:func:`_own_definitions`), a parameter
    is named it, a lambda parameter or comprehension target in the own
    scope is named it (:func:`_lambda_and_comprehension_binds`), or a
    ``global`` / ``nonlocal`` anywhere under the definition names it. A
    body holding a ``match`` or a ``type`` alias statement is refused
    whole. Order is not guarded (ADR-160 step 6): with one binding, a call
    the binding has not reached raises rather than reaching anything else.
    """
    own = list(_own_body(node))
    candidates: list[tuple[str, int, str]] = []
    for current in own:
        if current.type in ("match_statement", "type_alias_statement"):
            return ()
        binder = _alias_binder(current)
        if binder is not None and binder[1] != binder[0]:
            candidates.append((binder[0], _line(current), binder[2]))
    if not candidates:
        return ()
    counts: Counter = Counter()
    for current in own:
        counts.update(_bound_here(current))
    for definition, _decorated in _own_definitions(node):
        name_node = definition.child_by_field_name("name")
        if name_node is not None:
            counts[_text(name_node)] += 1
    otherwise = _parameter_names(node) | _lambda_and_comprehension_binds(node)
    return tuple(
        sorted(
            (name, line, last)
            for name, line, last in candidates
            if counts[name] == 1
            and name not in otherwise
            and not _declared_outer(node, name)
        )
    )


def _called_local_aliases(parsed: ParsedFile) -> dict:
    """:attr:`ParsedFile.local_aliases` as the walk collected it, less every
    alias no call uses (ADR-160 step 2).

    An alias is kept where some :class:`Call` whose callee is the bare name
    N has the definition's qualname as its scope and a line inside that
    definition's extent. A call in a nested ``def`` or class has another
    scope and keeps nothing here; one in a lambda or a comprehension is
    the definition's own, as lane A records its scope. Definitions left
    with no alias, and qualnames left with no definition, go.
    """
    if not parsed.local_aliases:
        return {}
    sites: dict[tuple[str, str], list[int]] = defaultdict(list)
    for call in parsed.calls:
        if call.scope is not None and "." not in call.callee:
            sites[(call.scope, call.callee)].append(call.line)
    out: dict = {}
    for qualname, definitions in parsed.local_aliases.items():
        kept = []
        for start, end, aliases in definitions:
            aliases = tuple(
                alias
                for alias in aliases
                if any(start <= line <= end for line in sites.get((qualname, alias[0]), ()))
            )
            if aliases:
                kept.append((start, end, aliases))
        if kept:
            out[qualname] = tuple(kept)
    return out


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


#: The builtin ADR-148's fold reads a guard through, by name. A module
#: that binds it means something else by it, and the guard is unreadable.
CALLABLE = "callable"


def _literal(node: Node | None) -> object:
    """One argument, default or operand as a **value**, or :data:`UNKNOWN`
    (ADR-148 step 2).

    The literals the fold carries are exactly the ones every test it
    reads is decidable on: ``None``, ``True``, ``False``, an integer, a
    float, a plain string and the empty tuple. Everything else is the one
    unknown — a name, a call, an f-string, a negated number, a non-empty
    tuple — because a value the walk cannot name is a value no guard can
    be folded over.
    """
    if node is None:
        return UNKNOWN
    kind = node.type
    if kind == "parenthesized_expression":
        children = node.named_children
        return _literal(children[0]) if len(children) == 1 else UNKNOWN
    if kind == "none":
        return None
    if kind == "true":
        return True
    if kind == "false":
        return False
    if kind in ("integer", "float"):
        try:
            return int(_text(node), 0) if kind == "integer" else float(_text(node))
        except ValueError:
            return UNKNOWN
    if kind == "string":
        literal = _string_literal(node)
        return UNKNOWN if literal is None else literal
    if kind == "tuple" and not node.named_children:
        return ()
    return UNKNOWN


def _bound_arguments(arguments: Node | None) -> Bound:
    """One call's arguments as ADR-148 step 2 reads them: the positionals
    as values in order, the keywords as ``(name, value)`` pairs, and
    whether a ``*x`` or ``**x`` was written — which makes the whole
    binding unknown, the walk not being able to say what it fills."""
    args: list[object] = []
    kwargs: list[tuple[str, object]] = []
    splat = False
    for arg in arguments.named_children if arguments else []:
        if arg.type in ("list_splat", "dictionary_splat"):
            splat = True
        elif arg.type == "keyword_argument":
            name = arg.child_by_field_name("name")
            if name is None:
                splat = True  # `f(**{...})` in the grammar's other spelling
            else:
                kwargs.append((_text(name), _literal(arg.child_by_field_name("value"))))
        elif arg.type != "comment":
            args.append(_literal(arg))
    return Bound(tuple(args), tuple(kwargs), splat)


def _binds_callable(root: Node, source: bytes) -> bool:
    """Whether a file binds the name ``callable`` anywhere (ADR-148).

    Anywhere, and by any form — a module-level assignment, an import, a
    ``def``, a parameter of some unrelated function. A narrower reading
    would have to model scope to be right, and being wrong here is
    reading someone else's ``callable`` as the builtin's answer: the
    whole file is the honest unit, and it costs a fold in the rare file
    that shadows the name somewhere else entirely.

    The walk is the whole tree, so it is asked only of a file whose text
    holds the word at all — a file that never writes ``callable`` cannot
    bind it, and this question is asked of every file ingested.
    """
    if CALLABLE.encode() not in source:
        return False
    stack = [root]
    while stack:
        current = stack.pop()
        if CALLABLE in _bound_here(current):
            return True
        if current.type == "function_definition" and CALLABLE in _parameter_names(current):
            return True
        stack.extend(current.children)
    return False


def _signature(node: Node) -> tuple | None:
    """A definition's parameters as the fold binds into them (ADR-148
    step 3): the positional ones in order, the ``*args`` name, the
    keyword-only ones, and the ``**kwargs`` name.

    ``None`` where a parameter cannot be named at all — the fold then has
    nowhere to put an argument and the factory is not read.
    """
    params: list[Param] = []
    kwonly: list[Param] = []
    star: str | None = None
    double_star: str | None = None
    after_star = False
    node_params = node.child_by_field_name("parameters")
    for param in node_params.named_children if node_params else []:
        kind = param.type
        if kind == "typed_parameter" and param.named_children and param.named_children[
            0
        ].type in ("list_splat_pattern", "dictionary_splat_pattern"):
            # `*args: T` / `**kwargs: T`: the grammar wraps the splat in a
            # `typed_parameter`, and the annotation says nothing the fold
            # binds — read it as the bare splat (click writes every one of
            # its factories this way).
            param = param.named_children[0]
            kind = param.type
        if kind == "positional_separator":
            continue
        if kind == "keyword_separator":  # a bare `*`
            after_star = True
            continue
        if kind in ("list_splat_pattern", "dictionary_splat_pattern"):
            children = param.named_children
            if not children or children[0].type != "identifier":
                return None
            if kind == "list_splat_pattern":
                star, after_star = _text(children[0]), True
            else:
                double_star = _text(children[0])
            continue
        if kind == "identifier":
            entry = Param(_text(param))
        elif kind == "typed_parameter":
            children = param.named_children
            if not children or children[0].type != "identifier":
                return None
            entry = Param(_text(children[0]))
        elif kind in ("default_parameter", "typed_default_parameter"):
            name = param.child_by_field_name("name")
            if name is None or name.type != "identifier":
                return None
            entry = Param(_text(name), _literal(param.child_by_field_name("value")))
        else:
            return None
        (kwonly if after_star else params).append(entry)
    return tuple(params), star, tuple(kwonly), double_star


def _statement_binds(node: Node) -> tuple[str, ...]:
    """The names one statement binds, for ADR-148's program.

    :func:`_bound_here`'s forms over the statement's own scope, with one
    addition ADR-145's reader does not need: a **chained** assignment
    (``x = y = 1``), which the grammar nests under the outer assignment's
    ``type`` field, so the outer target is not one of the names that walk
    sees. A fold that kept a stale value for ``x`` there would answer a
    guard wrongly, so the chain's targets are taken; :func:`_rebound` is
    left exactly as ADR-145 measured it.
    """
    names = _bound_in(_own_nodes(node))
    for current in _own_nodes(node):
        if current.type != "assignment" or current.child_by_field_name("right") is not None:
            continue
        nested = current.child_by_field_name("type")
        left = current.child_by_field_name("left")
        if nested is not None and nested.type == "assignment" and left is not None:
            names |= {_text(ident) for ident in _target_identifiers(left)}
    return tuple(sorted(names))


def _operand(node: Node | None) -> object:
    """One side of a guard: a literal, a bare name, or :data:`UNKNOWN`."""
    if node is None:
        return UNKNOWN
    if node.type == "parenthesized_expression":
        children = node.named_children
        return _operand(children[0]) if len(children) == 1 else UNKNOWN
    if node.type == "identifier":
        return NameRef(_text(node))
    value = _literal(node)
    return UNKNOWN if value is UNKNOWN else Literal(value)


def _test(node: Node | None) -> object:
    """One ``if`` / ``elif`` test as the small expression tree ADR-148
    step 1 keeps, or :data:`UNKNOWN`.

    The whole grammar: a literal, a name, ``not``, ``and`` / ``or``,
    ``x is None``, ``x is not None``, and ``callable(x)`` with one
    positional argument. Anything else the fold meets as an unknown,
    which takes both branches rather than the wrong one.
    """
    if node is None:
        return UNKNOWN
    kind = node.type
    if kind == "parenthesized_expression":
        children = node.named_children
        return _test(children[0]) if len(children) == 1 else UNKNOWN
    if kind == "identifier":
        return NameRef(_text(node))
    if kind == "not_operator":
        return Not(_test(node.child_by_field_name("argument")))
    if kind == "boolean_operator":
        operator = node.child_by_field_name("operator")
        if operator is None or _text(operator) not in ("and", "or"):
            return UNKNOWN
        return BoolOp(
            _text(operator),
            _test(node.child_by_field_name("left")),
            _test(node.child_by_field_name("right")),
        )
    if kind == "comparison_operator":
        operators = node.children_by_field_name("operators")
        children = node.children
        if len(operators) == 1 and len(children) == 3 and children[2].type == "none":
            if operators[0].type == "is":
                return IsNone(_operand(children[0]))
            if operators[0].type == "is not":
                return IsNone(_operand(children[0]), negated=True)
        return UNKNOWN
    if kind == "call":
        function = node.child_by_field_name("function")
        arguments = node.child_by_field_name("arguments")
        positional = [
            arg
            for arg in (arguments.named_children if arguments else [])
            if arg.type != "comment"
        ]
        if (
            function is not None
            and function.type == "identifier"
            and _text(function) == CALLABLE
            and len(positional) == 1
            and positional[0].type
            not in ("keyword_argument", "list_splat", "dictionary_splat")
        ):
            return IsCallable(_operand(positional[0]))
        return UNKNOWN
    value = _literal(node)
    return UNKNOWN if value is UNKNOWN else Literal(value)


def _branch(test: Node | None, block: Node | None, inner: str | None) -> Branch:
    """One arm of an ``if``. A walrus anywhere in the test makes the test
    unreadable **and** the name it binds unknown: the assignment ran, and
    what it assigned is what the fold could not read."""
    walrus = tuple(
        sorted(
            _text(name)
            for current in (_own_nodes(test) if test is not None else ())
            if current.type == "named_expression"
            for name in [current.child_by_field_name("name")]
            if name is not None and name.type == "identifier"
        )
    )
    return Branch(
        UNKNOWN if walrus else _test(test),
        walrus,
        _statements(block, inner),
    )


def _if_statement(node: Node, inner: str | None) -> If:
    """An ``if`` with its arms in written order. ``elif`` is an
    ``elif_clause`` of its own in this grammar, not a nested ``if``, and
    ``else`` is an ``else_clause`` whose statements are under ``body``."""
    branches = [
        _branch(
            node.child_by_field_name("condition"),
            node.child_by_field_name("consequence"),
            inner,
        )
    ]
    for alternative in node.children_by_field_name("alternative"):
        if alternative.type == "elif_clause":
            branches.append(
                _branch(
                    alternative.child_by_field_name("condition"),
                    alternative.child_by_field_name("consequence"),
                    inner,
                )
            )
        elif alternative.type == "else_clause":
            branches.append(
                Branch(None, (), _statements(alternative.child_by_field_name("body"), inner))
            )
    return If(tuple(branches))


def _returns_in(node: Node, inner: str | None) -> tuple[bool, ...]:
    """Every ``return`` written inside one statement, in the scope it is
    written in: ``True`` for each ``return g``, ``False`` for each other.
    """
    return tuple(
        bool(current.named_children)
        and current.named_children[0].type == "identifier"
        and _text(current.named_children[0]) == inner
        for current in _own_nodes(node)
        if current.type == "return_statement"
    )


def _chain(node: Node | None) -> Chain | None:
    """The call a ``return`` hands back, as ADR-149 step 1 records it, or
    ``None`` where the value is not a call this walk can name.

    The callee must be a name chain — the claim the rule above makes is
    that *the index resolved this line*, and a callee with no terminal
    identifier gave it nothing to resolve. A positional written after a
    ``*x`` is left out: which parameter it fills is decided by the
    splat's own length, which is exactly what is not read.
    """
    if node is None or node.type != "call":
        return None
    function = node.child_by_field_name("function")
    dotted = _dotted(function) if function is not None else None
    terminal = _terminal(function) if function is not None else None
    if dotted is None or terminal is None:
        return None
    args: list[object] = []
    kwargs: list[tuple[str, object]] = []
    star: int | None = None
    double_star = False
    arguments = node.child_by_field_name("arguments")
    for arg in arguments.named_children if arguments else []:
        if arg.type == "list_splat":
            if star is None:
                star = len(args)
        elif arg.type == "dictionary_splat":
            double_star = True
        elif arg.type == "keyword_argument":
            name = arg.child_by_field_name("name")
            if name is None:
                double_star = True  # `f(**{...})` in the grammar's other spelling
            else:
                kwargs.append((_text(name), _operand(arg.child_by_field_name("value"))))
        elif arg.type != "comment" and star is None:
            args.append(_operand(arg))
    return Chain(dotted, _line(terminal), tuple(args), tuple(kwargs), star, double_star)


def _statement(node: Node, inner: str | None) -> object | None:
    """One top-level statement of a factory's own body, as ADR-148 step 1
    records it, or ``None`` for one that neither binds, branches nor
    returns (a ``pass``, a docstring, a comment).

    The ``if`` is the one block read as branches. Every other statement
    that holds a ``return`` — a ``for``, ``while``, ``with``, ``try`` or
    ``match``, and anything else a grammar might call them — is an
    :class:`Opaque`: whether it runs, and how often, is not read, so each
    of its returns stays reachable and each name it binds goes unknown.
    Reading that off the returns rather than off a list of block kinds is
    the safe direction: a block this walk did not recognize keeps its
    returns instead of dropping them.
    """
    kind = node.type
    if kind in ("comment", "pass_statement"):
        return None
    if kind == "return_statement":
        value = node.named_children[0] if node.named_children else None
        return Return(
            value is not None and value.type == "identifier" and _text(value) == inner,
            _chain(value) if inner is None else None,
        )
    if kind == "raise_statement":
        return Raise()
    if kind == "if_statement":
        return _if_statement(node, inner)
    if kind == "expression_statement":
        children = [child for child in node.named_children if child.type != "comment"]
        if len(children) == 1 and children[0].type == "assignment":
            left = children[0].child_by_field_name("left")
            right = children[0].child_by_field_name("right")
            if left is not None and left.type == "identifier" and right is not None:
                value = _operand(right)
                if value is not UNKNOWN:
                    return Assign(_text(left), value)
    returns = _returns_in(node, inner)
    binds = _statement_binds(node)
    if returns:
        return Opaque(binds, returns)
    return Binds(binds) if binds else None


def _statements(block: Node | None, inner: str | None) -> tuple:
    """A block's statements, in written order.

    *inner* is the nested def the returns are read against, and ``None``
    where there is none to read them against — which is ADR-149's
    program and the one place a return records the :class:`Chain` it
    hands back. ADR-148's digest is then exactly what it was when that
    rule was measured: a factory carries one program or the other, so
    neither reading pays for the other's fact.
    """
    out = []
    for child in block.children if block is not None else ():
        statement = _statement(child, inner)
        if statement is not None:
            out.append(statement)
    return tuple(out)


def _inner_fold(node: Node, shadows_callable: bool) -> InnerFold | None:
    """A factory ADR-147 could not settle, digested for ADR-148's fold.

    Step 1's shape, and nothing wider: not ``async``, no ``yield`` of its
    own, **exactly one** nested definition — which must be a plain,
    undecorated, non-``async`` ``def`` — that name neither a parameter
    nor bound again, and at least one ``return`` of it. Two nested defs
    (attrs' ``define``) are refused here rather than folded, because
    which of them a return names is the whole question.
    """
    if any(child.type == "async" for child in node.children):
        return None
    definitions = list(_own_definitions(node))
    if len(definitions) != 1:
        return None
    definition, decorated = definitions[0]
    if decorated or definition.type != "function_definition":
        return None
    if any(child.type == "async" for child in definition.children):
        return None
    name = definition.child_by_field_name("name")
    if name is None:
        return None
    inner = _text(name)
    if inner in _parameter_names(node) or _rebound(node, ((inner, 0),)):
        return None
    returns_it = False
    for current in _own_body(node):
        if current.type == "yield":
            return None  # a generator hands back values, never itself
        if (
            current.type == "return_statement"
            and current.named_children
            and current.named_children[0].type == "identifier"
            and _text(current.named_children[0]) == inner
        ):
            returns_it = True
    if not returns_it:
        return None
    signature = _signature(node)
    if signature is None:
        return None
    params, star, kwonly, double_star = signature
    return InnerFold(
        inner=inner,
        params=params,
        star=star,
        kwonly=kwonly,
        double_star=double_star,
        shadows_callable=shadows_callable,
        body=_statements(node.child_by_field_name("body"), inner),
    )


def _holds_a_chain(body: tuple) -> bool:
    """Whether a recorded program holds a ``return`` of a named call
    (ADR-149 step 1's last condition).

    The ``if`` arms are descended into, because a factory whose only such
    return sits in one is the shape itself (click's ``group``); an
    :class:`Opaque`'s returns are bools and hold no chain by
    construction, so a body whose every ``return G(…)`` is written in a
    ``for``, ``while``, ``with``, ``try`` or ``match`` carries no fold.
    """
    for statement in body:
        if isinstance(statement, Return) and statement.chain is not None:
            return True
        if isinstance(statement, If) and any(
            _holds_a_chain(branch.body) for branch in statement.branches
        ):
            return True
    return False


def _chain_fold(node: Node, shadows_callable: bool) -> ChainFold | None:
    """A factory that hands back another factory's call, digested for
    ADR-149's fold (step 1).

    Asked only where neither ADR-147 nor ADR-148 read the body, and the
    shape is theirs less the nested def — which this rule does not look
    for at all, of any number: not ``async``, no ``yield`` of its own, a
    nameable signature, and at least one own-body ``return`` of a call
    this walk can name.
    """
    if any(child.type == "async" for child in node.children):
        return None
    for current in _own_body(node):
        if current.type == "yield":
            return None  # a generator hands back values, never a call's
    signature = _signature(node)
    if signature is None:
        return None
    body = _statements(node.child_by_field_name("body"), None)
    if not _holds_a_chain(body):
        return None
    params, star, kwonly, double_star = signature
    return ChainFold(
        params=params,
        star=star,
        kwonly=kwonly,
        double_star=double_star,
        shadows_callable=shadows_callable,
        body=body,
    )


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


#: One dotted name and nothing else: what a string annotation must hold for
#: :attr:`Symbol.returns` to read a head from it (ADR-156).
_DOTTED_NAME = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*")

#: Subscript heads that name more than one type, or none, rather than a
#: class: ``Optional[C]`` is ``C | None`` and ``Union[…]`` is a union.
_UNION_HEADS = frozenset({"Optional", "Union"})


def _annotation_head(node: Node) -> str | None:
    """The head :attr:`Symbol.returns` records for one return annotation's
    expression, or None for every form ADR-156 does not read."""
    if node.type in ("identifier", "attribute"):
        dotted = _dotted(node)
        return None if dotted is None else dotted.rpartition(".")[2]
    if node.type == "string":
        literal = _string_literal(node)
        if literal is None or not _DOTTED_NAME.fullmatch(literal):
            return None
        return literal.rpartition(".")[2]
    if node.type in ("generic_type", "subscript"):
        value = node.child_by_field_name("value") if node.type == "subscript" else (
            node.named_children[0] if node.named_children else None
        )
        if value is None or value.type not in ("identifier", "attribute"):
            return None
        head = _annotation_head(value)
        return None if head in _UNION_HEADS else head
    return None


def _returns(node: Node) -> tuple[str, int] | None:
    """A ``def``'s return annotation as ``(head, line)`` (ADR-156 step 1)."""
    annotation = node.child_by_field_name("return_type")
    if annotation is None:
        return None
    expr = annotation.named_children[0] if annotation.type == "type" else annotation
    if expr is None:
        return None
    head = _annotation_head(expr)
    return None if head is None else (head, _line(annotation))


def _with_items(node: Node, stack: list[tuple[str, str]]) -> list[WithItem]:
    """The items of one ``with_statement`` that :attr:`ParsedFile.with_items`
    records: none for an ``async with``, and of the rest only those whose
    context expression is a call on a name or an attribute."""
    if any(child.type == "async" for child in node.children):
        return []
    items: list[WithItem] = []
    for clause in node.children:
        if clause.type != "with_clause":
            continue
        for item in clause.named_children:
            if item.type != "with_item":
                continue
            value = item.child_by_field_name("value")
            if value is not None and value.type == "as_pattern":
                value = value.named_children[0] if value.named_children else None
            # `with (a\n.b\n.open()):` — the parentheses only wrap the line.
            while value is not None and value.type == "parenthesized_expression":
                value = value.named_children[0] if len(value.named_children) == 1 else None
            if value is None or value.type != "call":
                continue
            terminal = _terminal(value.child_by_field_name("function"))
            if terminal is None:
                continue
            items.append(
                WithItem(_scope_qualname(stack), terminal.start_point.row + 1, _text(terminal))
            )
    return items


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
        # A class is no decorator factory under any of the three rules:
        # ADR-147 and ADR-148 both read a `def` that returns a `def`, and
        # ADR-149 a `def` that returns another factory's call. Each is
        # asked only where the one before it settled nothing — a factory
        # ADR-147 draws is never re-folded (ADR-148 step 5), and one
        # either of them reads is never asked the chain question.
        returns_inner = _returns_inner(node) if is_function else None
        inner_fold = (
            _inner_fold(node, parsed.shadows_callable)
            if is_function and returns_inner is None
            else None
        )
        chain_fold = (
            _chain_fold(node, parsed.shadows_callable)
            if is_function and returns_inner is None and inner_fold is None
            else None
        )
        # A class body returns nothing and rebinds no parameter, having
        # none, and patches nothing of its own: those three are a
        # function's (ADR-145). What a class body binds, and a function
        # never has, is the other way round.
        value, value_local = _returned_value(node) if is_function else (None, None)
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
                value=value,
                value_local=value_local,
                rebound=_rebound(node, params) if is_function else (),
                patched=_patched(node) if is_function else (),
                binds=_class_binds(node) if not is_function else (),
                returns_inner=returns_inner,
                inner_fold=inner_fold,
                chain_fold=chain_fold,
                returns=_returns(node) if is_function else None,
            )
        )
        # ADR-153 step 1, recorded per qualname rather than on the symbol:
        # the rule that reads it is asked about a call's *scope*, which is
        # a qualname. One entry per definition, with its lines, because a
        # qualname can be written more than once (an `@overload`'s stubs)
        # and the call's line is what says which one it is in. A class
        # has no such names.
        if is_function:
            parsed.local_defs[qualname] = (
                *parsed.local_defs.get(qualname, ()),
                (_line(node), node.end_point.row + 1, _local_defs(node)),
            )
            # ADR-160 step 1, kept the same way; the aliases no call uses
            # are dropped once every call is recorded (_called_local_aliases).
            aliases = _local_aliases(node)
            if aliases:
                parsed.local_aliases[qualname] = (
                    *parsed.local_aliases.get(qualname, ()),
                    (_line(node), node.end_point.row + 1, aliases),
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

    if kind == "with_statement":
        # ADR-156: the item is recorded here and its call is walked below
        # as any call is, so the item and the `Call` share one line.
        parsed.with_items.extend(_with_items(node, stack))

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
