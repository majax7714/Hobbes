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

What is still C-4's remainder: the injected value's type, a module-level
``pytestmark`` (counted, not followed — no key row has judged it), an
``autouse=`` whose value is not the literal ``True`` or ``False``
(counted), a ``usefixtures`` argument that is not a string literal (the
walk keeps no such argument, so it cannot be counted either), and every
abstention above.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import PurePosixPath

from hobbes.extract.discover import ModuleInfo
from hobbes.extract.graph import symbol_imports
from hobbes.extract.pysource import ParsedFile, Symbol
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
