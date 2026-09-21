"""A decorator factory's application, read as a call of the def it
returns (ADR-147).

``@click.option("--count")`` is two calls. The first — ``option(…)`` — the
index names at the token and ADR-146 draws. The second is the application
of what it returned to the definition below it, and the source writes no
token for it at all: there is no name for any indexer to resolve, so the
join can never produce that edge. Where the factory's shape settles what
it returns, though, the second call is exact, and this module draws it —
a ``calls`` edge at the **``syntactic``** tier, evidenced at the callee's
line with ``via: decorator-factory``, from the decorator's caller to the
nested def.

The shape it reads, and nothing wider (:func:`factory_calls` asks the
five conditions in the ADR's order, and the first that fails is the one
counted):

1. the settled graph carries a ``semantic`` ``calls`` edge with evidence
   at the decorator's callee line whose target is a function or method
   **named as written** — the index naming ``f``, never lane A's reading
   — and exactly one such target. The edge's ``from`` is the caller, as
   ADR-146 scoped it: the decorator runs where it is written;
2. ``f`` has one body: of the definitions of its qualname, exactly one is
   not an ``@overload`` stub, and that one carries no decorator at all
   (the drawn symbol may *be* the first stub — H-19's grain — so the body
   is looked up rather than assumed);
3-4. that body's :attr:`~hobbes.extract.pysource.Symbol.returns_inner`
   names ``g``: every return in its own body is ``return g``, and ``g``
   is one plain undecorated nested ``def`` bound once;
5. ``<f's id>.<g>`` is exactly one symbol of kind ``function``.

**What it refuses**, each counted by reason: more than one answer at the
line (:data:`TWO_TARGETS`), no single body (:data:`NO_SINGLE_BODY`), a
decorated factory (:data:`DECORATED` — flask's ``Scaffold.route`` under
``@setupmethod``), a factory whose returns the strict wording does not
settle (:data:`NO_RETURNED_DEF`), no such inner symbol
(:data:`NO_SYMBOL`), and a ``(from, to)`` pair the graph already carries
a ``calls`` edge for (:data:`ALREADY_DRAWN` — the join's edge stands, and
this rule never restates it). :data:`NO_RETURNED_DEF` is one reason for
what the ADR lists as three — ``async``, a generator, and a return shape
the rule cannot settle — because the walk keeps one fact for all three
and a second walk here would be a second reading of the same body. Since
ADR-148, the third of those is the fold's question rather than this
refusal's: what stays counted here is a body that is no single-nested-def
factory at all.

**Not counted, because nothing was asked**: a decorator with no
``semantic`` in-repo edge at its line (``@pytest.fixture()``, an untyped
``@app.route(…)``), a bare ``@f`` — which applies ``f`` itself, ADR-146's
edge, not this one — a callee that is not a name chain, and a callee
whose terminal identifier is not on the decorator's own line (a wrapped
chain is not asked). Without lane B the rule draws nothing at all:
condition 1 cannot hold.

The counts block is written where **some site was asked** — where the
index named a factory at a decorator's line — rather than only where one
reached condition 2 as the ADR words it: the one site those two readings
differ over is a line with more than one answer, which is a refusal, and
a refusal a reader cannot see is worse than a block that says one thing
was asked and refused.

**ADR-148 — the factory's guards, folded over the site's own
arguments.** ADR-147's strict wording asks that *every* return be
``return g``, so click's ``command`` — ``return decorator(func)`` beside
``return decorator`` — is refused whole. But the path that other return
sits on is decided by the arguments the site itself writes: at
``@command()`` no positional is passed, ``name`` is ``None``,
``callable(None)`` is false, ``func`` stays ``None``, and the only return
the call can reach is ``return decorator``. Where conditions 1, 2 and 5
hold and 3–4 do not, this module folds the factory's own guards over the
site's own arguments (:func:`fold_guards`, a pure function over the two
digests — :attr:`~hobbes.extract.pysource.Symbol.inner_fold` and
:attr:`~hobbes.extract.pysource.Decorator.bound` — that reads no tree and
opens no file) and draws when **at least one return is reachable and
every reachable return is** ``return g``. Same edge, same tier
(``syntactic``), ``via: decorator-factory-folded``. The fold is
three-valued throughout: an unknown test takes both branches and their
names merge, so what it cannot read costs a draw rather than buying one.

Its two refusals join the list: :data:`METHOD_POSITIONAL` — a method
factory at a site passing **any** positional argument, because lane A
cannot tell ``@obj.f(x)`` from ``@Cls.f(x)``, where ``x`` would be
``self`` — and :data:`GUARD_UNKNOWN`, a reachable return other than
``return g``, or none at all. A factory ADR-147 already settles is drawn
as ADR-147 draws it and never re-folded.

**Not claimed:** what ``g`` returns, or what a later call of the
decorated name reaches; and, under the fold, nothing about the path any
*other* call of the same factory takes. C-58 keeps every other function
value.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from hobbes.extract.discover import ModuleInfo
from hobbes.extract.pysource import (
    NO_DEFAULT,
    UNKNOWN,
    Assign,
    Binds,
    BoolOp,
    Bound,
    If,
    InnerFold,
    IsCallable,
    IsNone,
    Literal,
    NameRef,
    Not,
    Opaque,
    ParsedFile,
    Raise,
    Return,
    Symbol,
)
from hobbes.extract.schema import SEMANTIC

#: What an edge drawn on a decorator factory's application is evidenced as
#: (ADR-147), on the row and on the evidence entry it becomes.
DECORATOR_FACTORY = "decorator-factory"

#: What an edge drawn by folding the factory's guards over the site's own
#: arguments is evidenced as (ADR-148). The same edge and the same tier as
#: :data:`DECORATOR_FACTORY`; a different reading, so a different word.
DECORATOR_FACTORY_FOLDED = "decorator-factory-folded"

#: The decorator that makes a definition a typing stub rather than a body:
#: read by its dotted name's last component, so ``@overload`` and
#: ``@t.overload`` are one thing.
OVERLOAD = "overload"

#: Why a decorator-factory application drew nothing, in the order the
#: conditions are asked — but for the last two, ADR-148's, which are
#: appended so the tuple's older entries keep their place and which are
#: asked where :data:`NO_RETURNED_DEF` would otherwise have fallen. Each
#: is a place the rule chose to draw less rather than guess, so each is
#: counted at the site it was refused at.
TWO_TARGETS = "two-targets"
NO_SINGLE_BODY = "no-single-body"
DECORATED = "decorated"
NO_RETURNED_DEF = "no-returned-def"
NO_SYMBOL = "no-symbol"
ALREADY_DRAWN = "already-drawn"
#: The site passes a positional argument to a **method** factory: lane A
#: cannot tell `@obj.f(x)` from `@Cls.f(x)`, where `x` fills `self` and
#: every later binding shifts by one (ADR-148 step 3).
METHOD_POSITIONAL = "method-positional"
#: The fold left a reachable return other than ``return g``, or left none
#: reachable at all (ADR-148 step 5).
GUARD_UNKNOWN = "guard-unknown"
FACTORY_REASONS = (
    TWO_TARGETS,
    NO_SINGLE_BODY,
    DECORATED,
    NO_RETURNED_DEF,
    NO_SYMBOL,
    ALREADY_DRAWN,
    METHOD_POSITIONAL,
    GUARD_UNKNOWN,
)


def factory_calls(
    modules: list[ModuleInfo],
    parsed: dict[str, ParsedFile],
    symbols: list[dict],
    symbol_edges: list[dict],
) -> tuple[list[dict], dict]:
    """Every call-form decorator whose factory's shape settles what it
    returns (ADR-147).

    *symbols* and *symbol_edges* are the graph's, **settled**: condition 1
    is an edge the index put there, and this rule only reads it.

    Returns ``(calls, counts)``. A call is ``{"from", "to", "path",
    "line", "via", "factory"}`` — the decorator's caller, the nested def,
    the decorating file and the callee's line, which reading drew it
    (:data:`DECORATOR_FACTORY` or :data:`DECORATOR_FACTORY_FOLDED`), and
    the factory whose return the chain went through — sorted by
    ``(from, to, path, line)``, one row per decorator site. *counts* is
    ``{"drawn", "folded", "refused"}`` with every one of
    :data:`FACTORY_REASONS`, ``folded`` being how many of the drawn came
    from ADR-148's fold; or ``{}`` where no site was asked at all: a repo
    whose decorators the index resolved to nothing in-repo was never
    asked this question, and a block of zeroes would say otherwise.
    """
    by_id = {symbol["id"]: symbol for symbol in symbols}
    already = {
        (edge["from"], edge["to"]) for edge in symbol_edges if edge["type"] == "calls"
    }
    resolved: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for edge in symbol_edges:
        if edge["type"] != "calls" or edge["tier"] != SEMANTIC:
            continue
        for row in edge["evidence"]:
            resolved[(row.get("path"), row.get("line"))].append(edge)

    drawn: list[dict] = []
    refused: Counter = Counter()
    asked = 0
    for module in modules:
        for symbol in parsed[module.id].symbols:
            for decorator in symbol.decorators:
                if not decorator.called or decorator.callee_line is None:
                    continue
                if decorator.callee_line != decorator.line:
                    # A chain wrapped across lines: the ADR does not ask
                    # about a site whose callee is not where the `@` is.
                    continue
                written = (decorator.dotted or "").rpartition(".")[2]
                answers = [
                    edge
                    for edge in resolved.get((module.path, decorator.callee_line), ())
                    if _named_as_written(by_id.get(edge["to"]), written)
                ]
                if not answers:
                    # The index resolved the factory to nothing in this
                    # repo — a plugin's, a dependency's, or nothing at all.
                    continue
                asked += 1
                targets = {edge["to"] for edge in answers}
                callers = {edge["from"] for edge in answers}
                if len(targets) != 1 or len(callers) != 1:
                    # One line, one enclosing scope and one factory, or the
                    # rule cannot name which call it is drawing the second
                    # half of.
                    refused[TWO_TARGETS] += 1
                    continue
                target = by_id[next(iter(targets))]
                caller = next(iter(callers))
                reason, inner_id, via = _returned_def(
                    target, parsed, by_id, decorator.bound
                )
                if reason is not None:
                    refused[reason] += 1
                    continue
                if (caller, inner_id) in already:
                    refused[ALREADY_DRAWN] += 1
                    continue
                drawn.append(
                    {
                        "from": caller,
                        "to": inner_id,
                        "path": module.path,
                        "line": decorator.callee_line,
                        "via": via,
                        "factory": target["id"],
                    }
                )

    drawn.sort(key=lambda c: (c["from"], c["to"], c["path"], c["line"]))
    if not asked:
        return drawn, {}
    return drawn, {
        "drawn": len(drawn),
        "folded": sum(1 for call in drawn if call["via"] == DECORATOR_FACTORY_FOLDED),
        "refused": {reason: refused[reason] for reason in FACTORY_REASONS},
    }


def _returned_def(
    target: dict, parsed: dict[str, ParsedFile], by_id: dict, bound: Bound | None
) -> tuple[str | None, str | None, str | None]:
    """Conditions 2 to 5 of ADR-147, and ADR-148's fold where 3–4 leave
    the body unsettled: the factory has one undecorated body, that body
    returns one nested ``def`` — outright, or on every path the site's own
    arguments can reach — and the graph carries it.

    Returns ``(reason, symbol id, via)`` — a reason and nothing else, or
    no reason with the id to draw to and the reading that drew it. The
    definitions are counted in the target's module record rather than in
    the graph's symbols, because duplicate qualnames collapse to one
    record there (:func:`hobbes.extract.graph._symbol_records`) and a
    factory written twice would read as one clean answer.
    """
    facts = parsed.get(target["module"])
    if facts is None:
        return NO_SINGLE_BODY, None, None
    bodies = [
        definition
        for definition in _definitions(facts, target["qualname"])
        if not _is_overload(definition)
    ]
    if len(bodies) != 1:
        return NO_SINGLE_BODY, None, None
    body = bodies[0]
    if body.decorators:
        # A decorated factory hands back what its own decorator returned,
        # which is not the def written inside it.
        return DECORATED, None, None
    if body.returns_inner is not None:
        inner, via = body.returns_inner, DECORATOR_FACTORY
    elif body.inner_fold is None:
        # Not a factory this rule can read at all: no single nested def to
        # return, or async, or a generator (ADR-147's one reason).
        return NO_RETURNED_DEF, None, None
    else:
        reason = fold_guards(body.inner_fold, bound, target["kind"] == "method")
        if reason is not None:
            return reason, None, None
        inner, via = body.inner_fold.inner, DECORATOR_FACTORY_FOLDED
    qualname = f"{target['qualname']}.{inner}"
    inner_id = f"{target['module']}.{qualname}"
    found = [
        definition
        for definition in _definitions(facts, qualname)
        if definition.kind == "function"
    ]
    if len(found) != 1 or inner_id not in by_id:
        return NO_SYMBOL, None, None
    return None, inner_id, via


def fold_guards(fold: InnerFold, bound: Bound | None, method: bool) -> str | None:
    """ADR-148 steps 3 to 5: fold one factory's guards over one site's
    own arguments, and say whether the site reaches ``return g`` and
    nothing else.

    A pure function over the two digests — no tree, no file, no graph —
    so what it claims is exactly what lane A wrote down. Returns ``None``
    where the site draws, else the reason it did not
    (:data:`METHOD_POSITIONAL` or :data:`GUARD_UNKNOWN`).

    *method* is the target symbol's kind: a method factory's first
    parameter is the receiver, which the site never passes, and a site
    that passes **any** positional is refused outright — ``@obj.f(x)``
    and ``@Cls.f(x)`` are one text to lane A, and in the second ``x`` is
    ``self`` and every later binding shifts by one.
    """
    if bound is None:
        # A bare `@f` applies `f` itself (ADR-146) and writes no
        # arguments to fold; the caller asks only at call-form sites.
        return GUARD_UNKNOWN
    if method and bound.args:
        return METHOD_POSITIONAL
    params = fold.params[1:] if method else fold.params
    if len(bound.args) > len(params) and fold.star is None:
        # More positionals than parameters to take them: the call the
        # site wrote is not one this factory can serve, and folding over
        # a call that raises is claiming a path that never runs.
        return GUARD_UNKNOWN
    exits, _ = _run(fold.body, _bind(fold, bound, method), fold)
    # At least one return reachable, and every reachable one `return g`.
    return None if exits == {True} else GUARD_UNKNOWN


def _default(param) -> object:
    """A parameter's value where the site filled it with nothing: what it
    defaults to, or unknown where it defaults to nothing at all."""
    return UNKNOWN if param.default is NO_DEFAULT else param.default


def _bind(fold: InnerFold, bound: Bound, method: bool) -> dict:
    """ADR-148 step 3: the factory's parameters, as this site leaves them.

    Positionals in order (after the receiver, for a method), keywords by
    name, an unfilled parameter at its literal default, an unfilled
    ``*args`` at ``()`` — and everything else unknown, which is where the
    receiver, ``**kwargs`` and a ``*x``/``**x`` at the site all land.
    """
    params = fold.params[1:] if method else fold.params
    names = [param.name for param in (*fold.params, *fold.kwonly)]
    if fold.star:
        names.append(fold.star)
    if fold.double_star:
        names.append(fold.double_star)
    env: dict = {name: UNKNOWN for name in names}
    if bound.splat:
        return env
    keywords: dict = {}
    for name, value in bound.kwargs:
        # A keyword the signature does not name lands in `**kwargs`,
        # which is unknown either way; one written twice is no call.
        keywords[name] = UNKNOWN if name in keywords else value
    for index, param in enumerate(params):
        if index < len(bound.args):
            env[param.name] = UNKNOWN if param.name in keywords else bound.args[index]
        elif param.name in keywords:
            env[param.name] = keywords[param.name]
        else:
            env[param.name] = _default(param)
    for param in fold.kwonly:
        env[param.name] = (
            keywords[param.name] if param.name in keywords else _default(param)
        )
    if fold.star:
        env[fold.star] = () if len(bound.args) <= len(params) else UNKNOWN
    return env


def _forget(env: dict, names) -> dict:
    """*env* with each of *names* made unknown."""
    return {**env, **{name: UNKNOWN for name in names}}


def _merge(envs: list[dict]) -> dict | None:
    """The environments of several possible paths, as one: a name keeps
    its value only where every path agrees on it (ADR-148 step 4), and
    ``None`` where no path arrives at all."""
    if not envs:
        return None
    first, *rest = envs
    merged: dict = {}
    for name, value in first.items():
        agreed = all(
            name in other
            and type(other[name]) is type(value)
            and other[name] == value
            for other in rest
        )
        merged[name] = value if agreed else UNKNOWN
    for other in rest:
        for name in other:
            merged.setdefault(name, UNKNOWN)
    return merged


def _run(body: tuple, env: dict, fold: InnerFold) -> tuple[set, dict | None]:
    """Walk one block of the factory's program under *env*.

    Returns ``(exits, env)``: *exits* holds ``True`` for each reachable
    ``return g`` and ``False`` for each other reachable return, and *env*
    is the environment of the paths that fall out of the block — ``None``
    where none do, every one of them having returned or raised.
    """
    exits: set = set()
    current: dict | None = dict(env)
    for statement in body:
        if current is None:
            break  # nothing after a return or a raise is reached
        if isinstance(statement, Assign):
            current = {**current, statement.name: _value(statement.value, current)}
        elif isinstance(statement, Return):
            exits.add(statement.inner)
            current = None
        elif isinstance(statement, Raise):
            current = None
        elif isinstance(statement, Binds):
            current = _forget(current, statement.names)
        elif isinstance(statement, Opaque):
            # The block may run or not, once or many times: every return
            # written in it is reachable, every name it binds is unknown,
            # and the path falls through all the same.
            exits.update(statement.returns)
            current = _forget(current, statement.names)
        elif isinstance(statement, If):
            branch_exits, current = _run_if(statement, current, fold)
            exits |= branch_exits
    return exits, current


def _run_if(statement: If, env: dict, fold: InnerFold) -> tuple[set, dict | None]:
    """One ``if`` / ``elif`` / ``else``: a known test takes its one arm,
    an unknown one takes both — that arm *and* everything after it — and
    the arms that fall through merge."""
    exits: set = set()
    fell_through: list[dict] = []
    reached = env
    for branch in statement.branches:
        # A walrus in the test ran whether or not its arm did.
        reached = _forget(reached, branch.unknown)
        truth = True if branch.test is None else _truth(branch.test, reached, fold)
        if truth is False:
            continue
        branch_exits, branch_env = _run(branch.body, reached, fold)
        exits |= branch_exits
        if branch_env is not None:
            fell_through.append(branch_env)
        if truth is True:
            # This arm runs, so no later one does and the statement
            # cannot be fallen past except out of this arm.
            return exits, _merge(fell_through)
    # No arm was certainly taken, so the path that takes none is live.
    fell_through.append(reached)
    return exits, _merge(fell_through)


def _value(expr: object, env: dict) -> object:
    """One expression's **value**: a literal as written, a name as the
    environment holds it, and unknown for everything else — the fold
    reads a value out of nothing wider than that."""
    if isinstance(expr, Literal):
        return expr.value
    if isinstance(expr, NameRef):
        return env.get(expr.name, UNKNOWN)
    return UNKNOWN


def _truth(expr: object, env: dict, fold: InnerFold) -> bool | None:
    """One guard's **truth**: ``True``, ``False``, or ``None`` for a test
    the fold cannot read (ADR-148 step 4).

    ``and`` / ``or`` short-circuit as Python's do, which settles a test
    on a known operand even beside an unknown one: ``x and False`` is
    false whatever ``x`` is, and ``x or True`` is true. ``callable`` is
    the builtin's answer only where the module binds no ``callable`` of
    its own, and it is false on every literal the fold can carry — none
    of them is a function.
    """
    if isinstance(expr, Literal):
        return bool(expr.value)
    if isinstance(expr, NameRef):
        value = env.get(expr.name, UNKNOWN)
        return None if value is UNKNOWN else bool(value)
    if isinstance(expr, Not):
        inner = _truth(expr.operand, env, fold)
        return None if inner is None else not inner
    if isinstance(expr, BoolOp):
        left = _truth(expr.left, env, fold)
        right = _truth(expr.right, env, fold)
        if expr.op == "and":
            if left is False or right is False:
                return False
            return True if left is True and right is True else None
        if left is True or right is True:
            return True
        return False if left is False and right is False else None
    if isinstance(expr, IsNone):
        value = _value(expr.operand, env)
        if value is UNKNOWN:
            return None
        return (value is None) != expr.negated
    if isinstance(expr, IsCallable):
        if fold.shadows_callable:
            return None  # some other `callable`, and not one this reads
        value = _value(expr.operand, env)
        if value is None or isinstance(value, (bool, int, float, str, tuple)):
            return False
        return None
    return None


def _definitions(facts: ParsedFile, qualname: str) -> list[Symbol]:
    """Every definition of one qualname in a module's record — more than
    one where it is written twice (an ``@overload`` set, an ``if``/``else``
    pair)."""
    return [symbol for symbol in facts.symbols if symbol.qualname == qualname]


def _is_overload(definition: Symbol) -> bool:
    """Whether a definition is a typing stub rather than a body."""
    return any(
        (decorator.dotted or "").rpartition(".")[2] == OVERLOAD
        for decorator in definition.decorators
    )


def _named_as_written(record: dict | None, written: str) -> bool:
    """Whether a graph symbol is a function or method the decorator named.

    The written chain's last component against the symbol's own name: the
    index resolving ``f`` is the claim, and an edge at the line onto
    anything else — the class of a receiver, an argument's function — is
    not the factory this decorator applied.
    """
    return (
        record is not None
        and record["kind"] in ("function", "method")
        and record["name"] == written
    )
