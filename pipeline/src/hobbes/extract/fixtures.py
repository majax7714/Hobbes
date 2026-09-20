"""pytest's fixture lookup, read as syntax (ADR-137, C-4).

Injection is dynamic — pytest calls the fixture, on the test's behalf,
before the test body runs — but the *lookup* that decides which function
gets called is not. A parameter name resolves by a fixed order that is all
in the tree lane A already parses: the requester's class chain, then its
file (a name imported into the file counts as the file's), then
``conftest.py`` in the file's directory and each directory above it. This
module walks that order and nothing else.

What it produces is never a ``calls`` edge. The test wrote no call, and a
name-matched ``calls`` edge from a fixture parameter to the fixture
function was wrong six times of six at the oracle lane's first Python
triage (:func:`hobbes.extract.graph._shadowed` carries the finding). The
caller draws a ``uses`` edge instead, and the test map follows it as an
injection because it is handed one, not because it is a ``uses`` edge.

It abstains — and counts the abstention — wherever the order does not end
in exactly one definition it can name: a parameter no scope in the repo
defines (``tmp_path``, ``monkeypatch``, a plugin's), a fixture name defined
twice at the winning scope (duplicate qualnames collapse to one symbol
record, so there is no id to trust), and every parameter of a definition
whose ``parametrize`` mark the walk could not read. A requester in a class
that names a base class abstains too, unless the class chain itself defines
the name: a base class's fixture is inherited and outranks the file's and
the conftest's, the walk does not resolve bases, and an edge drawn past
an inherited fixture of the same name would be a wrong one, not a missing
one.

A fixture no parameter names is still looked up by name (ADR-139), and
two shapes are followed through the same order, drawn as the same ``uses``
edge and marked with which they are: a ``usefixtures`` mark's string, on
the test or on a class around it, and the name of a fixture defined
``autouse=True`` in any scope of the test's chain, which pytest adds to
the test's request. A mark's evidence is the mark's line; autouse's is the
test's own, because nothing on the test names the fixture. Only a test
gets either — pytest ignores a mark on a fixture, and autouse names are
added to tests. Where a pair is seen twice, the first of parameter,
``usefixtures``, ``autouse`` is the one drawn.

One thing the injected value's *type* does say is followed (ADR-145):
where a fixture's body is a single ``return C(…)``, the construction
fixes the runtime class exactly, so ``p.m(…)`` written on that parameter
is a call on ``C.m``. :func:`value_calls` draws it — a ``calls`` edge at
the ``syntactic`` tier, over the two hops the graph already carries (the
``uses`` injection above, and the ``semantic`` edge the index drew from
the fixture to the class it constructs). It refuses, and counts, wherever
the construction is not the whole story: a rebound parameter, a value
that is not a construction, no class edge at that line, and a method the
class's own body does not define exactly once.

What is still C-4's remainder: a fixture value that is not a
construction (``return app``, ``return app.test_client()`` — a value's
type, which the rule above does not read) and an **inherited** method
(the rule walks no base classes), a module-level ``pytestmark`` (counted,
not followed — no key row has judged it), an ``autouse=`` whose value is
not the literal ``True`` or ``False`` (counted), a ``usefixtures``
argument that is not a string literal (the walk keeps no such argument,
so it cannot be counted either), and every abstention above.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import PurePosixPath

from hobbes.extract.discover import ModuleInfo
from hobbes.extract.graph import symbol_imports
from hobbes.extract.pysource import ParsedFile, Symbol
from hobbes.extract.schema import SEMANTIC
from hobbes.extract.testmap import is_test_file, is_test_symbol

#: The decorators that define a fixture, by their dotted name's last
#: component — so ``@pytest.fixture``, a bare ``@fixture`` from
#: ``from pytest import fixture``, ``@pytest_asyncio.fixture`` and the old
#: ``@pytest.yield_fixture`` are all one thing.
FIXTURE_DECORATORS = frozenset({"fixture", "yield_fixture"})

#: Parameters the lookup never fills: pytest binds them itself.
SELF_NAMES = frozenset({"self", "cls"})

CONFTEST = "conftest.py"

#: How the fixture came to be requested (ADR-139), recorded on every
#: injection: written as a parameter, named by a ``usefixtures`` mark, or
#: applied by ``autouse=True``. One pair keeps the first of the three.
PARAMETER = "parameter"
USEFIXTURES = "usefixtures"
AUTOUSE = "autouse"
VIAS = (PARAMETER, USEFIXTURES, AUTOUSE)

#: Why a parameter drew nothing. Every one of them is a place the graph
#: stays silent on purpose, so they are counted rather than guessed at.
NOT_IN_REPO = "not-in-repo"
TWO_DEFINITIONS = "two-definitions"
PARAMETRIZE_UNREAD = "parametrize-unread"
BASE_CLASS = "base-class"
REASONS = (NOT_IN_REPO, TWO_DEFINITIONS, PARAMETRIZE_UNREAD, BASE_CLASS)

#: What an edge drawn on the value a fixture constructs is evidenced as
#: (ADR-145), on the row and on the evidence entry it becomes.
FIXTURE_VALUE = "fixture-value"

#: The decorators that make ``C.m`` something other than a method to call.
PROPERTY_DECORATORS = frozenset({"property", "cached_property"})

#: Why a ``p.m(…)`` on an injected parameter drew nothing (ADR-145), in
#: the order the conditions are asked. Each is a place the rule chose to
#: draw less rather than guess, so each is counted at the call site it
#: was refused at.
REBOUND = "rebound"
NO_CONSTRUCTION = "no-construction"
NO_CLASS_EDGE = "no-class-edge"
NO_METHOD = "no-method"
PROPERTY = "property"
ALREADY_DRAWN = "already-drawn"
VALUE_REASONS = (
    REBOUND,
    NO_CONSTRUCTION,
    NO_CLASS_EDGE,
    NO_METHOD,
    PROPERTY,
    ALREADY_DRAWN,
)


def injections(
    modules: list[ModuleInfo], parsed: dict[str, ParsedFile]
) -> tuple[list[dict], dict]:
    """Every name pytest's lookup resolves to one repo fixture.

    Returns ``(injections, counts)``. An injection is
    ``{"from", "to", "path", "line", "name", "via"}`` — the requester's
    symbol id, the fixture's, the requester's file, the line the request is
    evidenced at, the name looked up and which of :data:`VIAS` asked for it
    — sorted by ``(from, to, line)``. *counts* is ``{"drawn", "requesters",
    "fixtures", "abstained", "usefixtures", "via", "autouse_fixtures",
    "unread"}``, or ``{}`` on a repo where no fixture is defined and no name
    was looked up: nothing was asked there, and a block of zeroes would say
    otherwise.
    """
    files = [m for m in modules if _is_fixture_file(m.path)]
    scopes = _Scopes(modules, files, parsed)

    drawn: list[dict] = []
    abstained: Counter = Counter()
    by_via: Counter = Counter()
    seen: set[tuple[str, str]] = set()
    usefixtures = 0
    looked_up = 0
    for module in files:
        facts = parsed[module.id]
        quals = {s.qualname: s for s in facts.symbols}
        kinds = {}
        for symbol in facts.symbols:
            kinds.setdefault(symbol.qualname, symbol.kind)
        for symbol in facts.symbols:
            is_test = is_test_symbol(symbol, quals)
            requester = is_test or _fixture_decorator(symbol) is not None
            if requester or symbol.kind == "class":
                usefixtures += sum(
                    1 for d in symbol.decorators if _last(d.dotted) == "usefixtures"
                )
            if not requester:
                continue
            requester_id = f"{module.id}.{symbol.qualname}"
            chain = scopes.chain(module, symbol, kinds)
            own_classes = _class_scopes(symbol, kinds)
            inherits = any(quals[c].bases for c in _class_chain(symbol, kinds) if c in quals)

            def request(name: str, line: int, via: str) -> None:
                """One name this requester asks for, walked down pytest's
                order: the same walk and the same abstentions whichever of
                the three asked (ADR-139)."""
                nonlocal looked_up
                if symbol.parametrized is not None and name in symbol.parametrized:
                    # The mark fills it, not a fixture: not a lookup at all.
                    return
                looked_up += 1
                if symbol.parametrized is None:
                    abstained[PARAMETRIZE_UNREAD] += 1
                    return
                target, reason = _resolve(name, chain, requester_id)
                if (
                    target is not None
                    and inherits
                    and not _in_scopes(name, chain[:own_classes], requester_id)
                ):
                    # Found past the class chain, in a class that inherits: a
                    # base class may define the name, and that definition
                    # would win over the one found further out.
                    target, reason = None, BASE_CLASS
                if target is None:
                    abstained[reason] += 1
                    return
                if via != PARAMETER and (requester_id, target) in seen:
                    # One pair, one via: the parameter or the mark that
                    # already drew it says why the fixture runs.
                    return
                seen.add((requester_id, target))
                by_via[via] += 1
                drawn.append(
                    {
                        "from": requester_id,
                        "to": target,
                        "path": module.path,
                        "line": line,
                        "name": name,
                        "via": via,
                    }
                )

            for name, line in symbol.params:
                if name in SELF_NAMES:
                    continue
                request(name, line, PARAMETER)
            if not is_test:
                # A fixture definition requests through its parameters only:
                # pytest ignores a mark on a fixture, and an autouse name is
                # added to the tests, not to the other fixtures.
                continue
            for decorator in _usefixtures_decorators(symbol, quals, kinds):
                for name in decorator.args:
                    request(name, decorator.line, USEFIXTURES)
            for name in _autouse_names(chain, scopes.autouse):
                request(name, symbol.line, AUTOUSE)

    drawn.sort(key=lambda i: (i["from"], i["to"], i["line"]))
    if not scopes.definitions and not looked_up:
        return drawn, {}
    return drawn, {
        "drawn": len(drawn),
        "requesters": len({i["from"] for i in drawn}),
        "fixtures": len({i["to"] for i in drawn}),
        "abstained": {reason: abstained[reason] for reason in REASONS},
        "usefixtures": usefixtures,
        "via": {via: by_via[via] for via in VIAS},
        "autouse_fixtures": scopes.autouse_definitions,
        "unread": {
            "autouse-value": scopes.autouse_unread,
            "pytestmark": sum(parsed[m.id].pytestmark_usefixtures for m in modules),
        },
    }


def value_calls(
    modules: list[ModuleInfo],
    parsed: dict[str, ParsedFile],
    injected: list[dict],
    symbols: list[dict],
    symbol_edges: list[dict],
) -> tuple[list[dict], dict]:
    """Every ``p.m(…)`` on an injected parameter whose fixture constructs
    the class ``m`` is defined on (ADR-145).

    *injected* is what :func:`injections` drew; *symbols* and
    *symbol_edges* are the graph's, settled — the class of condition 3 is
    an edge the index put there, and this rule only reads it.

    Returns ``(calls, counts)``. A call is ``{"from", "to", "path",
    "line", "via", "fixture"}`` — the requester's symbol id, the method's,
    the requester's file and the call's line, :data:`FIXTURE_VALUE`, and
    the fixture whose value the chain went through — sorted by ``(from,
    to, path, line)``, one row per call site. *counts* is ``{"drawn",
    "refused"}`` with every one of :data:`VALUE_REASONS`, or ``{}`` where
    no such call site exists at all: nothing was asked there, and a block
    of zeroes would say otherwise.

    The four conditions are asked in the ADR's order and the first that
    fails is the one counted, so a refusal reads as the earliest reason
    the rule had. A pair the graph already carries a ``calls`` edge for is
    refused last: the join's answer stands, and this rule never restates
    it.
    """
    by_id = {symbol["id"]: symbol for symbol in symbols}
    module_by_path = {module.path: module for module in modules}
    already = {
        (edge["from"], edge["to"]) for edge in symbol_edges if edge["type"] == "calls"
    }
    constructed: dict[str, list[dict]] = defaultdict(list)
    for edge in symbol_edges:
        if edge["type"] == "calls" and edge["tier"] == SEMANTIC:
            constructed[edge["from"]].append(edge)

    drawn: list[dict] = []
    refused: Counter = Counter()
    looked = 0
    for injection in injected:
        if injection["via"] != PARAMETER:
            # A mark and an autouse fixture bind no name in the body, so
            # there is no `p` to have written a call on (ADR-139).
            continue
        module = module_by_path.get(injection["path"])
        requester = by_id.get(injection["from"])
        if module is None or requester is None:
            continue
        prefix = f"{injection['name']}."
        sites = [
            call
            for call in parsed[module.id].calls
            # The requester's *own* body: a nested def's calls carry that
            # def's qualname as their scope, and `p` is not its parameter.
            if call.scope == requester["qualname"]
            and call.callee.startswith(prefix)
            and call.callee.count(".") == 1
        ]
        if not sites:
            continue
        looked += len(sites)

        reason, fixture_value = _fixture_value(injection, parsed, by_id)
        if reason is not None:
            refused[reason] += len(sites)
            continue
        klass, line = fixture_value
        found = [
            edge
            for edge in constructed.get(injection["to"], ())
            if _is_class_named(by_id.get(edge["to"]), klass)
            and any(row.get("line") == line for row in edge["evidence"])
        ]
        if len(found) != 1:
            refused[NO_CLASS_EDGE] += len(sites)
            continue
        class_id = found[0]["to"]
        for call in sites:
            method_reason, method_id = _class_method(
                class_id, call.callee.partition(".")[2], parsed, by_id
            )
            if method_reason is not None:
                refused[method_reason] += 1
                continue
            if (injection["from"], method_id) in already:
                refused[ALREADY_DRAWN] += 1
                continue
            drawn.append(
                {
                    "from": injection["from"],
                    "to": method_id,
                    "path": injection["path"],
                    "line": call.line,
                    "via": FIXTURE_VALUE,
                    "fixture": injection["to"],
                }
            )

    drawn.sort(key=lambda c: (c["from"], c["to"], c["path"], c["line"]))
    if not looked:
        return drawn, {}
    return drawn, {
        "drawn": len(drawn),
        "refused": {reason: refused[reason] for reason in VALUE_REASONS},
    }


def _fixture_value(
    injection: dict, parsed: dict[str, ParsedFile], by_id: dict
) -> tuple[str | None, tuple[str, int] | None]:
    """Conditions 1 and 2 of ADR-145: the parameter still holds what was
    injected, and the fixture's body is one construction.

    Returns ``(reason, value)`` — a reason and no value, or no reason and
    the written class name with its line. A fixture whose qualname is
    written twice in its file reads as no construction: the graph keeps
    the first record of the two
    (:func:`hobbes.extract.graph._symbol_records`), so there is no single
    body that can be said to have returned anything.
    """
    requester = _definitions(by_id[injection["from"]], parsed)
    if any(injection["name"] in definition.rebound for definition in requester):
        return REBOUND, None
    fixture = by_id.get(injection["to"])
    if fixture is None:
        return NO_CONSTRUCTION, None
    definitions = _definitions(fixture, parsed)
    if len(definitions) != 1 or definitions[0].value is None:
        return NO_CONSTRUCTION, None
    return None, definitions[0].value


def _class_method(
    class_id: str, method: str, parsed: dict[str, ParsedFile], by_id: dict
) -> tuple[str | None, str | None]:
    """Conditions 4 and 5 of ADR-145: ``m`` is one ``def`` in the class's
    **own** body and not a property.

    No base is walked: an inherited method is refused (the simulation met
    none, and a rule ships as far as it was probed). The definitions are
    counted in the class's own module record rather than in the graph's
    symbols, because duplicate qualnames collapse to one record there and
    a method defined twice would read as one clean answer.
    """
    klass = by_id.get(class_id)
    facts = parsed.get(klass["module"]) if klass is not None else None
    if klass is None or facts is None:
        return NO_METHOD, None
    qualname = f"{klass['qualname']}.{method}"
    found = [
        symbol
        for symbol in facts.symbols
        if symbol.qualname == qualname and symbol.kind in ("method", "function")
    ]
    method_id = f"{klass['module']}.{qualname}"
    if len(found) != 1 or method_id not in by_id:
        return NO_METHOD, None
    if any(_last(d.dotted) in PROPERTY_DECORATORS for d in found[0].decorators):
        # An attribute read written as a call is not this rule's business,
        # and `C.name()` would be a call on whatever the property returned.
        return PROPERTY, None
    return None, method_id


def _is_class_named(record: dict | None, name: str) -> bool:
    """Whether a graph symbol is a class written under *name* — the name
    as the fixture spelled it, so an alias (``import Runner as R``) is
    not this class and is refused."""
    return record is not None and record["kind"] == "class" and record["name"] == name


def _definitions(record: dict, parsed: dict[str, ParsedFile]) -> list[Symbol]:
    """Every definition in the module record behind one graph symbol —
    more than one where a qualname is written twice."""
    facts = parsed.get(record["module"])
    if facts is None:
        return []
    return [symbol for symbol in facts.symbols if symbol.qualname == record["qualname"]]


def _usefixtures_decorators(symbol: Symbol, quals: dict, kinds: dict) -> list:
    """Every ``usefixtures`` mark that applies to *symbol*: its own, and
    each enclosing class's — a class's decorators sit on the class's own
    :class:`~hobbes.extract.pysource.Symbol`, which the file's qualname map
    holds."""
    owners = [symbol, *(quals[c] for c in _class_chain(symbol, kinds) if c in quals)]
    return [
        decorator
        for owner in owners
        for decorator in owner.decorators
        if _last(decorator.dotted) == "usefixtures"
    ]


def _autouse_names(chain: list[dict], autouse: set[str]) -> list[str]:
    """The fixture names some autouse definition binds anywhere in *chain*,
    sorted. pytest adds each of them to the test's request and then resolves
    it like any other name — so a nearer non-autouse definition of the same
    name is what runs, and the lookup below is the one that decides."""
    return sorted(
        {
            name
            for scope in chain
            for name, targets in scope.items()
            if any(target in autouse for target in targets)
        }
    )


def _resolve(
    name: str, chain: list[dict], requester_id: str
) -> tuple[str | None, str]:
    """pytest's order, stopped at the first scope that defines *name*.

    A fixture requesting its own name — ``def repo(repo)``, the override
    idiom — does not request itself: its own definition is dropped, and if
    that empties the scope the search carries on outward.
    """
    for scope in chain:
        found = [target for target in scope.get(name, ()) if target != requester_id]
        if not found:
            continue
        if len(found) > 1:
            return None, TWO_DEFINITIONS
        return found[0], ""
    return None, NOT_IN_REPO


def _class_chain(symbol: Symbol, kinds: dict) -> list[str]:
    """The qualnames of the classes around *symbol*, innermost outward."""
    out = []
    owner = symbol.qualname.rpartition(".")[0]
    while owner:
        if kinds.get(owner) == "class":
            out.append(owner)
        owner = owner.rpartition(".")[0]
    return out


def _class_scopes(symbol: Symbol, kinds: dict) -> int:
    """How many of :meth:`_Scopes.chain`'s leading scopes are classes."""
    return len(_class_chain(symbol, kinds))


def _in_scopes(name: str, scopes: list[dict], requester_id: str) -> bool:
    return any(t != requester_id for scope in scopes for t in scope.get(name, ()))


class _Scopes:
    """The fixture definitions each file, class and conftest provides.

    Built once for the repo: a scope is ``{fixture name: [symbol id, …]}``,
    and a name with more than one entry is a name no injection can point
    at. The list keeps duplicates on purpose — two definitions of one
    qualname collapse to a single symbol record
    (:func:`hobbes.extract.graph._symbol_records`), so counting ids would
    read a redefinition as a single clean answer.
    """

    def __init__(
        self,
        modules: list[ModuleInfo],
        files: list[ModuleInfo],
        parsed: dict[str, ParsedFile],
    ):
        self.definitions = 0
        #: The symbol ids of the definitions written ``autouse=True``, and
        #: the two counts beside them: how many there were, and how many
        #: spelled ``autouse=`` as something the walk could not read.
        self.autouse: set[str] = set()
        self.autouse_definitions = 0
        self.autouse_unread = 0
        self._file: dict[str, dict[str, list[str]]] = {}
        self._classes: dict[str, dict[str, dict[str, list[str]]]] = {}
        self._conftests: dict[str, str] = {}  # directory -> module id
        # module id -> {qualname: (registered name, renamed?, symbol id)}
        by_qualname: dict[str, dict[str, list[tuple[str, bool, str]]]] = {}

        for module in files:
            top: dict[str, list[str]] = defaultdict(list)
            classes: dict[str, dict[str, list[str]]] = defaultdict(
                lambda: defaultdict(list)
            )
            quals: dict[str, list[tuple[str, bool, str]]] = defaultdict(list)
            for symbol in parsed[module.id].symbols:
                decorator = _fixture_decorator(symbol)
                if decorator is None:
                    continue
                self.definitions += 1
                symbol_id = f"{module.id}.{symbol.qualname}"
                if AUTOUSE in decorator.true_kwargs:
                    self.autouse.add(symbol_id)
                    self.autouse_definitions += 1
                elif AUTOUSE in decorator.unread_kwargs:
                    self.autouse_unread += 1
                alias = decorator.kwargs.get("name")
                renamed = isinstance(alias, str)
                name = alias if renamed else symbol.name
                owner = symbol.qualname.rpartition(".")[0]
                if not owner:
                    top[name].append(symbol_id)
                    quals[symbol.qualname].append((name, renamed, symbol_id))
                elif symbol.kind == "method":
                    classes[owner][name].append(symbol_id)
            self._file[module.id] = top
            self._classes[module.id] = classes
            by_qualname[module.id] = quals
            if PurePosixPath(module.path).name == CONFTEST:
                self._conftests[_directory(module.path)] = module.id

        # A fixture imported into a file is that file's, under the name it
        # is bound to here — unless the fixture renamed itself, which
        # pytest registers it under wherever it is seen.
        # Resolved against the whole repo, not just its test files: the
        # import rules are the repo's, and a binding onto a module that
        # defines no fixture simply finds nothing below.
        for module, bindings in symbol_imports(modules, parsed).items():
            if module not in self._file:
                continue
            for bound, (target, original) in bindings.items():
                for name, renamed, symbol_id in by_qualname.get(target, {}).get(
                    original, ()
                ):
                    self._file[module][name if renamed else bound].append(symbol_id)

    def chain(self, module: ModuleInfo, symbol: Symbol, kinds: dict) -> list[dict]:
        """The scopes pytest searches for *symbol*'s parameters, in order:
        its class chain innermost outward, its file, then the conftest of
        its directory and of each directory above it."""
        scopes: list[dict[str, list[str]]] = []
        owner = symbol.qualname.rpartition(".")[0]
        while owner:
            if kinds.get(owner) == "class":
                scopes.append(self._classes[module.id].get(owner, {}))
            owner = owner.rpartition(".")[0]
        scopes.append(self._file[module.id])
        for directory in _directories(module.path):
            conftest = self._conftests.get(directory)
            # A requester inside a conftest already searched that file.
            if conftest is not None and conftest != module.id:
                scopes.append(self._file[conftest])
        return scopes


def _is_fixture_file(path: str) -> bool:
    """Where pytest reads fixture definitions: a test file, or a
    ``conftest.py`` — which :func:`hobbes.extract.testmap.is_test_file` does
    not call a test file, and which is a source module to the test map."""
    return is_test_file(path) or PurePosixPath(path).name == CONFTEST


def _fixture_decorator(symbol: Symbol):
    """The fixture decorator on *symbol*, or None when it has none."""
    if symbol.kind not in ("function", "method"):
        return None
    for decorator in symbol.decorators:
        if _last(decorator.dotted) in FIXTURE_DECORATORS:
            return decorator
    return None


def _last(dotted: str | None) -> str:
    """A decorator's last dotted component: how the spelling is recognised,
    since ``pytest.fixture``, ``fixture`` and ``pytest_asyncio.fixture`` are
    the same decorator reached three ways."""
    return (dotted or "").rpartition(".")[2]


def _directory(path: str) -> str:
    parent = str(PurePosixPath(path).parent)
    return "" if parent == "." else parent


def _directories(path: str) -> list[str]:
    """A file's directory and each one above it, up to the repo root."""
    out = []
    current = _directory(path)
    while True:
        out.append(current)
        if not current:
            return out
        current = _directory(current)
