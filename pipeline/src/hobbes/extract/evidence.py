"""The evidence IR and the range join (ADR-029).

Two providers, one shape. **tree-sitter** knows what a thing *is* — this is
a call site, this is an import statement, this symbol spans these lines —
and never what it resolves to. **SCIP** knows what an occurrence *resolves
to* and never what it syntactically was, because scip-python populates
``syntax_kind`` for none of its occurrences.

So neither provider is asked a question it would have to guess at, and the
answer that matters — *a call, pointing where it actually goes* — is
produced by joining them on ranges before any graph exists:

    tree-sitter ─┐
                 ├─► evidence IR ──(join)──► semantic IR ──► graph builder
    SCIP ────────┘

A post-hoc merge of finished edges could never produce that: it can only
compare edges that already exist, and the edge wanted here belongs to
neither lane alone.
"""

from __future__ import annotations

from array import array
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field

#: Providers. Values double as the ``lane`` on emitted evidence, so the
#: artifact says which of them saw each sighting (P3).
TREE_SITTER = "tree-sitter"
SCIP = "scip"

#: Evidence kinds a syntax provider emits.
CALL_SITE = "call-site"
IMPORT_SITE = "import-site"
DEFINITION = "definition"

#: Evidence kinds a semantic provider emits. A ``resolution`` is an
#: occurrence resolved to its declaration; an ``implements`` site
#: (ADR-120) is the override set — one definition stated by the index to
#: implement or override another — which no syntax site claims and the
#: join draws as an ``implements`` edge at semantic tier.
RESOLUTION = "resolution"
IMPLEMENTS = "implements"


@dataclass(frozen=True, slots=True)
class Site:
    """One range-anchored observation.

    *name* is the identifying text the provider saw — a callee's last
    segment for a call site, a symbol's terminal descriptor for a
    resolution. It is what disambiguates several sightings sharing a line.

    Slotted (ADR-116): a large root holds millions at once — ScummVM's
    4.16 million resolutions and 1.53 million C++ call sites — and a
    per-instance dictionary was most of each one's weight.
    """

    provider: str
    kind: str
    file: str
    line: int
    name: str = ""
    col: int = -1
    #: Syntax provider only: the symbol id enclosing this site, if any.
    scope: str = ""
    #: Semantic provider only: where the resolved definition lives — for
    #: an ``implements`` site, where the implemented declaration lives,
    #: ``file``/``line`` being the implementor's own definition.
    def_file: str = ""
    def_line: int = 0
    #: Syntax provider only: the name of an ambiguity the provider saw
    #: at a call site and abstained on — ``union-member`` (ADR-104,
    #: C-97): a member of a union-typed receiver whose members do not
    #: share one declaration. Any single target is one possible dispatch
    #: presented as the resolved one, so the join draws nothing here
    #: from either lane and the tail names the site.
    ambiguous: str = ""
    #: Syntax provider only: the qualifier the callee was **written**
    #: through, where it carries template arguments (ADR-125) — C++'s
    #: ``test_format<20>`` in ``test_format<20>::format(..)``, the
    #: immediate one, never the whole chain. Empty everywhere else: it
    #: exists so the projection can read the source's own claim about
    #: which class is meant against the one lane B resolved (C-153).
    qualifier: str = ""
    #: Syntax provider only: how many arguments the call was **written**
    #: with (ADR-130) — C++'s ``copy<Char>(begin, end, out)`` is 3.
    #: ``None`` everywhere else and wherever the parse could not count
    #: them (a pack expansion, a braced initialiser, an ERROR node): it
    #: exists so the projection can read the source's own count against
    #: what the declaration lane B resolved to can take (C-153), and an
    #: unknown count draws the edge.
    argc: int | None = None


@dataclass
class Resolved:
    """One semantic-IR fact: a role, a target, and the tier it earned."""

    kind: str
    source_file: str
    line: int
    scope: str
    def_file: str
    def_line: int
    tier: str
    lanes: tuple[str, ...]
    evidence: list[dict] = field(default_factory=list)
    #: The site's written qualifier (:attr:`Site.qualifier`, ADR-125),
    #: carried onto the fact **only** where lane B answered — a fallback
    #: edge is lane A's own guess, and there is no index answer for the
    #: source text to contradict.
    qualifier: str = ""
    #: The site's written argument count (:attr:`Site.argc`, ADR-130),
    #: carried onto the fact on the same condition and for the same
    #: reason: only lane B's answer can be contradicted.
    argc: int | None = None


def index_resolutions(sites: list[Site]) -> dict[tuple[str, int], list[Site]]:
    """SCIP resolutions, bucketed by the line they sit on."""
    buckets: dict[tuple[str, int], list[Site]] = defaultdict(list)
    for site in sites:
        if site.kind == RESOLUTION:
            buckets[(site.file, site.line)].append(site)
    return buckets


def match_resolution(
    site: Site, buckets: dict[tuple[str, int], list[Site]]
) -> Site | None:
    """The resolution for a syntax *site*, or None.

    Line alone is ambiguous — one line routinely holds several references —
    so the name must agree too. Column breaks the remaining ties by
    proximity, which is why the evidence IR carries it.
    """
    candidates = buckets.get((site.file, site.line), [])
    if not candidates:
        return None
    named = [c for c in candidates if c.name and c.name == site.name]
    if not named:
        return None
    if len(named) == 1 or site.col < 0:
        return named[0]
    return min(named, key=lambda c: abs(c.col - site.col) if c.col >= 0 else 1 << 30)


def _veto_set(external: list[dict] | None) -> set[tuple[str, int, str]]:
    """Sites whose ``(file, line, name)`` lane B resolved outside the repo
    (ADR-111). A reference the helper or :func:`~hobbes.extract.scipsource.
    join_cross_unit` marked ``in_repo`` is not outside it — an ambiguous or
    otherwise ungraphed in-repo moniker — and never enters this set."""
    return {
        (e["file"], e["line"], e.get("name", ""))
        for e in (external or [])
        if not e.get("in_repo")
    }


def _operator_call(hit: Site, operators: Mapping) -> bool | None:
    """Whether *hit* is a C++ operator the source applied **by symbol** at
    a token lane A recorded, and if so whether that token sits inside a
    template (ADR-131). ``None`` wherever any part of that does not hold.

    The three answers are three fates: ``False`` is the ``calls`` fact,
    ``True`` is **nothing at all** — neither a call nor a ``uses``, since
    the index answers a dependent operator with its single by-name
    candidate (C-153) and no key grades a ``uses`` that would contradict
    it — and ``None`` is the ``uses`` fact the reference is today.

    scip-clang names such a reference ``operator<<`` and puts it at the
    operator token's own column, which no call site claims — so this is
    the whole of what tells that reference apart from every other
    unclaimed one, and it is deliberately exact: one column off, another
    spelling at that position, or a reference with no column at all is
    ``None`` and stays the ``uses`` fact it is today.
    """
    if hit.col < 0 or not hit.name.startswith("operator"):
        return None
    packed = operators.get(hit.file)
    if not packed:
        return None
    from hobbes.extract.cppsource import operator_token

    return operator_token(packed, hit.line, hit.col, hit.name[len("operator"):].strip())


def _construction_call(
    hit: Site, constructions: Mapping, constructors: frozenset[tuple[str, int]]
) -> bool | None:
    """Whether *hit* is a C++ construction — a reference onto a
    constructor, at a construction token lane A recorded — and if so
    whether that token sits inside a template (ADR-132). ``None`` wherever
    any part of that does not hold, which is the ``uses`` fact the
    reference is today.

    Two conditions, and both are needed. **Exact position**, as the
    operator rule is exact: scip-clang puts the reference on the variable's
    name, the member's name, the ``{``, the ``=`` or the type's start, so
    the token is the whole of what says a construction was written there —
    one column off, or a reference with no column, is another occurrence
    on the same line. **The constructor set**, because the token alone
    cannot say what was constructed: ``T x;`` writes a type reference at
    the declaration too, and drawing a call from every reference at a
    declared name was 95 contradicted rows on fmt. The target's own
    definition row has to be a constructor's.
    """
    if hit.col < 0 or (hit.def_file, hit.def_line) not in constructors:
        return None
    packed = constructions.get(hit.file)
    if not packed:
        return None
    from hobbes.extract.cppsource import construction_token

    return construction_token(packed, hit.line, hit.col)


def _ts_construction_call(
    hit: Site, constructions: Mapping, targets: Mapping
) -> tuple[str, int] | bool | None:
    """What a TS/JS construction reference draws, ADR-142 — the sibling of
    :func:`_construction_call`, read where lane B ran for TypeScript.

    Three answers, as the C++ rule has three. The ``(file, line)`` to draw
    a ``calls`` fact at; ``False`` where the index named a **class** at
    the token, which draws nothing and is counted; and ``None`` wherever
    any part of the rule does not hold — no token here, no reading of that
    definition — which is the ``uses`` fact the reference is today.

    **Exact position**, as both C++ rules are exact: lane A's token is the
    `new` expression's callee terminal identifier, and the index puts its
    occurrence on the same identifier, so one column off or a reference
    with no column at all is another occurrence on the same line.
    *targets* answers the other half — what was constructed — because the
    token alone cannot: at a class that declares no constructor the index
    names the class while the base's constructor is what runs.
    """
    if hit.col < 0:
        return None
    tokens = constructions.get(hit.file)
    if not tokens or (hit.line, hit.col) not in tokens:
        return None
    where = (hit.def_file, hit.def_line)
    if where not in targets:
        return None
    return targets[where] or False


def join(
    syntax: list[Site],
    semantic: list[Site],
    fallback: dict[tuple[str, int, str], tuple[str, int]] | None = None,
    external: list[dict] | None = None,
    withhold: frozenset[str] = frozenset(),
    operators: Mapping[str, array] | None = None,
    counts: dict | None = None,
    constructions: Mapping[str, array] | None = None,
    constructors: frozenset[tuple[str, int]] | None = None,
    construction_counts: dict | None = None,
    ts_constructions: Mapping[str, frozenset[tuple[int, int]]] | None = None,
    ts_targets: Mapping[tuple[str, int], tuple[str, int] | None] | None = None,
    ts_construction_counts: dict | None = None,
) -> list[Resolved]:
    """Join syntax sites against semantic resolutions (ADR-029's table).

    A matched site claims the resolution it matched **by position** —
    ``(file, line, name, col)`` (ADR-133) — so every other resolution of
    that name on the line still reaches the unclaimed loop below. Claiming
    by name alone withheld them all, and they are true facts: the declared
    type in ``Element el = new Element("div")``, hidden by the
    constructor's claim; the return type in ``func (r *body) StreamID()
    quic.StreamID``, hidden by the method call's. A resolution at the
    matched hit's **own** column stays hidden, and that is wanted — the
    index puts a declaration and its override at one position, and
    ADR-104's abstention claims its resolution precisely so the alternates
    do not resurface. A **site** without a column keeps the by-name claim:
    :func:`match_resolution` took the first resolution of the name there,
    so which one it matched is not known, and an unsure claim draws less.

    *fallback* is lane A's own resolution for a site, keyed by
    ``(file, line, name)`` — used only where SCIP resolved nothing, and
    marked ``syntactic`` when it is. Sites nothing resolves are dropped:
    an unresolved call is not an edge, which is ADR-007's rule unchanged.

    *external* is lane B's external references (ADR-111): a site whose
    key lane B resolved to a declaration outside the repo vetoes the
    fallback there — lane A's guess is dropped rather than drawn, because
    lane B already answered "not in this repo" and the fallback's guess is
    exactly where lane A is most likely to be wrong (C-138). The site's
    fate is unchanged elsewhere: it is still counted ``external``
    (:func:`_dispositions`), only the edge is not drawn.

    An ``implements`` site in *semantic* (ADR-120) is the index's own
    statement that one definition implements or overrides another. No
    syntax site claims it and no fallback stands in for it: it becomes an
    ``implements`` fact at semantic tier, lane B alone, as a ``uses``
    reference does.

    *withhold* is the files lane B **compiled** and whose call sites it
    may therefore be trusted to have answered or not answered (ADR-113 §2,
    C-152): a C++ file scip-clang indexed. Where it answered nothing at a
    call site there, lane A's name guess is withheld rather than drawn —
    on fmt that guess was wrong 74 times in 182, because C's
    namespace-blind ranks reach a mock by name and rank 3's "unique" is
    not unique once a parse error has lost the real definition (C-145).
    The veto above wins where both apply, so a site lane B placed outside
    the repo is never also counted withheld. Import sites are untouched:
    a C++ include is lane A's fact about the source, which lane B neither
    contradicts nor replaces.

    *operators* is lane A's packed operator tokens per C++ file (ADR-131,
    :func:`~hobbes.extract.cppsource.pack_operator`). A resolution no call
    site claimed, named ``operator`` + a spelling, at exactly one of those
    positions and **outside a template**, is a ``calls`` fact rather than
    the ``uses`` reference it would otherwise be: the index names the
    overload and lane A proves the operator was written there. Inside a
    template the same reference is **withheld** — no ``calls`` fact and no
    ``uses`` fact either (ADR-131's amendment): scip-clang answers a
    dependent operator with its single by-name candidate, at the same
    arity, so ``val * x`` reads onto whatever ``operator*`` it can name,
    and a ``uses`` edge no key grades would be believed as a true
    dependency. Every other reference is untouched. The fact carries no
    ``qualifier`` and no ``argc``: there is no written callee for R-qual
    or R-arity to read.

    *counts* is an out-parameter for the two numbers that rule produces —
    ``drawn`` and ``in_template``, the second now the number **withheld**
    — added into the dict the caller passes, so the return type is what
    every existing caller already reads. Left ``None``, nothing is counted
    and the withholding is the same: it is the rule, not the tally.

    *constructions* is lane A's packed construction tokens per C++ file
    (ADR-132, :func:`~hobbes.extract.cppsource.pack_construction`) and
    *constructors* the ``(file, line)`` of every definition lane B's
    moniker names a constructor (:func:`~hobbes.extract.minted.
    constructor_lines`). A resolution no call site claimed, onto one of
    those definitions, at exactly one of those positions and **outside a
    template**, is a ``calls`` fact rather than the ``uses`` reference it
    would otherwise be: ``T x(1);`` calls a constructor and names no
    callee lane A can record, so this edge too belongs to neither lane
    alone. Both arguments are needed for either to be read — the operator
    rule is tried first, and answers for its own tokens.

    **Inside a template the reference stays the ``uses`` fact it is**, and
    is counted rather than withheld. That is not ADR-131's amendment, and
    deliberately so: a dependent type's construction gets no reference at
    all, so what scip-clang does emit inside a template is a
    non-dependent type's, and all 45 such rows across the two measured
    cells read right. *construction_counts* takes ``drawn`` and
    ``in_template`` as *counts* does.

    *ts_constructions* is lane A's ``new`` tokens per TS/JS file
    (ADR-142, :func:`~hobbes.extract.tssource._constructions`) and
    *ts_targets* what each of lane B's definitions would be constructed
    as (:func:`~hobbes.extract.scipsource.ts_construction_targets`).
    C++'s pair and this one answer for different files and neither can
    reach the other's; both are read only where lane B ran for the
    language they belong to. A resolution no call site claimed, at
    exactly one of those tokens, onto a definition the index names a
    **constructor**, is a ``calls`` fact to the class that declares it —
    a constructor starts no symbol, so the reference falls below the
    floor today and the edge is nobody's; onto anything that is not a
    class it is a ``calls`` fact to that definition. Onto a **class** it
    stays the ``uses`` reference it is, and is counted: there the written
    class declares no constructor and the one that runs is a base's,
    which is the shape the keys contradict. *ts_construction_counts*
    takes ``drawn`` and ``named_class``.
    """
    from hobbes.extract.schema import SEMANTIC, SYNTACTIC

    buckets = index_resolutions(semantic)
    fallback = fallback or {}
    vetoed = _veto_set(external)
    out: list[Resolved] = []
    claimed: set[tuple[str, int, str, int]] = set()
    #: The by-name claims of the sites lane A recorded no column for
    #: (ADR-133): there the whole name on the line is hidden, as it was
    #: everywhere before the column entered the key.
    claimed_by_name: set[tuple[str, int, str]] = set()

    for site in syntax:
        if site.kind not in (CALL_SITE, IMPORT_SITE):
            continue
        kind = "calls" if site.kind == CALL_SITE else "imports"
        hit = match_resolution(site, buckets)
        if site.ambiguous:
            # Lane A saw the receiver's type and abstained (ADR-104): a
            # union whose members resolve the member differently has no
            # single static target, and lane B's occurrence there is the
            # first member's — one possible dispatch. Its resolution is
            # claimed so it does not resurface as a `uses` reference,
            # and no edge is drawn; the site is counted in the tail. The
            # claim is the one below, by position: it takes the alternates
            # the index states at that same occurrence with it, and leaves
            # the line's other references alone.
            if hit is not None:
                claimed.add((hit.file, hit.line, hit.name, hit.col))
                if site.col < 0:
                    claimed_by_name.add((hit.file, hit.line, hit.name))
            continue
        if hit is not None:
            # By position (ADR-133): the column keeps the abstention and
            # the same-reference alternates hidden — the index states
            # both a declaration and its override at one occurrence — and
            # releases the line's other references, which are their own
            # facts. Where lane A recorded no column the match was the
            # first resolution of the name, and which one that was is not
            # known, so there the claim is the by-name one it always was.
            claimed.add((hit.file, hit.line, hit.name, hit.col))
            if site.col < 0:
                claimed_by_name.add((hit.file, hit.line, hit.name))
            out.append(
                Resolved(
                    kind=kind,
                    source_file=site.file,
                    line=site.line,
                    scope=site.scope,
                    def_file=hit.def_file,
                    def_line=hit.def_line,
                    tier=SEMANTIC,
                    lanes=(TREE_SITTER, SCIP),
                    evidence=[{"path": site.file, "line": site.line}],
                    # Only here (ADR-125, ADR-130): the projection compares
                    # the written qualifier and the written argument count
                    # against what lane B resolved, and the fallback branch
                    # below has no such answer.
                    qualifier=site.qualifier,
                    argc=site.argc,
                )
            )
            continue
        if (site.file, site.line, site.name) in vetoed:
            continue  # ADR-111: lane B placed this outside the repo
        guess = fallback.get((site.file, site.line, site.name))
        if guess is None:
            continue  # unresolved: not an edge, ADR-007 unchanged
        if site.kind == CALL_SITE and site.file in withhold:
            continue  # ADR-113 §2: lane B compiled this file and said nothing here
        out.append(
            Resolved(
                kind=kind,
                source_file=site.file,
                line=site.line,
                scope=site.scope,
                def_file=guess[0],
                def_line=guess[1],
                tier=SYNTACTIC,
                lanes=(TREE_SITTER,),
                evidence=[{"path": site.file, "line": site.line}],
            )
        )

    # Every resolution no syntax site claimed is a real use — a type
    # annotation, an `except` clause, a value passed by name. True, useful
    # for dependency questions, and emphatically not a call.
    #
    # Typed ``uses`` rather than ``references``: ADR-010's Terraform layer
    # already spends that name on traversal chains between ``tf:`` nodes.
    # Two meanings under one type is the kind of ambiguity that only hurts
    # once a consumer filters on it.
    for (file, line), sites in sorted(buckets.items()):
        for hit in sites:
            if (hit.file, hit.line, hit.name, hit.col) in claimed:
                continue
            if (hit.file, hit.line, hit.name) in claimed_by_name:
                continue  # a columnless site claimed the name here
            in_template = _operator_call(hit, operators) if operators else None
            if in_template is False:
                # ADR-131: an operator applied by symbol, outside a
                # template. No syntax site could claim it — `a + b` names
                # no callee — so the edge belongs to neither lane alone,
                # which is the join's own case. No scope: `project` names
                # the caller by the enclosing symbol, as it does for every
                # unscoped fact.
                if counts is not None:
                    counts["drawn"] = counts.get("drawn", 0) + 1
                out.append(
                    Resolved(
                        kind="calls",
                        source_file=file,
                        line=line,
                        scope="",
                        def_file=hit.def_file,
                        def_line=hit.def_line,
                        tier=SEMANTIC,
                        lanes=(TREE_SITTER, SCIP),
                        evidence=[{"path": file, "line": line}],
                        qualifier="",
                        argc=None,
                    )
                )
                continue
            if in_template is True:
                # ADR-131's amendment: inside a template the reference is
                # withheld outright — not a call, and not the `uses` it
                # was either. At a dependent operator the index has one
                # by-name candidate and answers with it (C-153), so the
                # edge would read as a true dependency no key can
                # contradict. Counted so the cost is a number rather than
                # a silence (C-146, C-153); per hit, so another unclaimed
                # resolution on the same line still gets its `uses`.
                if counts is not None:
                    counts["in_template"] = counts.get("in_template", 0) + 1
                continue
            built = (
                _construction_call(hit, constructions, constructors)
                if constructions and constructors
                else None
            )
            if built is False:
                # ADR-132: a construction outside a template. `T x(1);`,
                # `m_(a)`, `{a, b}` — each calls the constructor lane B
                # named here and none of them writes a callee lane A could
                # record, so the edge is the join's own, unscoped as the
                # operator rule's is.
                if construction_counts is not None:
                    construction_counts["drawn"] = (
                        construction_counts.get("drawn", 0) + 1
                    )
                out.append(
                    Resolved(
                        kind="calls",
                        source_file=file,
                        line=line,
                        scope="",
                        def_file=hit.def_file,
                        def_line=hit.def_line,
                        tier=SEMANTIC,
                        lanes=(TREE_SITTER, SCIP),
                        evidence=[{"path": file, "line": line}],
                        qualifier="",
                        argc=None,
                    )
                )
                continue
            if built is True:
                # Inside a template the reference is the `uses` edge it
                # was, and true: a dependent type's construction is not
                # indexed at all, so this one's type is not dependent.
                # Counted so the rows not drawn as calls are a number.
                if construction_counts is not None:
                    construction_counts["in_template"] = (
                        construction_counts.get("in_template", 0) + 1
                    )
            made = (
                _ts_construction_call(hit, ts_constructions, ts_targets)
                if ts_constructions and ts_targets
                else None
            )
            if made is False:
                # ADR-142: the index named a class at the token, so the
                # class declares no constructor and the one that runs is
                # the base's the key names. The `uses` edge below is what
                # this reference has always been and stays; counted, so
                # the rows the rule refuses are a number rather than a
                # silence (C-168).
                if ts_construction_counts is not None:
                    ts_construction_counts["named_class"] = (
                        ts_construction_counts.get("named_class", 0) + 1
                    )
            elif made is not None:
                # A construction both lanes agree on: lane A wrote the
                # `new` and lane B named a constructor — or a constructor
                # function — at exactly its token. Unscoped as the C++
                # rules' facts are, and carrying neither qualifier nor
                # argc: `new X(1)` writes no callee for either to read.
                if ts_construction_counts is not None:
                    ts_construction_counts["drawn"] = (
                        ts_construction_counts.get("drawn", 0) + 1
                    )
                out.append(
                    Resolved(
                        kind="calls",
                        source_file=file,
                        line=line,
                        scope="",
                        def_file=made[0],
                        def_line=made[1],
                        tier=SEMANTIC,
                        lanes=(TREE_SITTER, SCIP),
                        evidence=[{"path": file, "line": line}],
                        qualifier="",
                        argc=None,
                    )
                )
                continue
            out.append(
                Resolved(
                    kind="uses",
                    source_file=file,
                    line=line,
                    scope="",
                    def_file=hit.def_file,
                    def_line=hit.def_line,
                    tier=SEMANTIC,
                    lanes=(SCIP,),
                    evidence=[{"path": file, "line": line}],
                )
            )

    # The override set (ADR-120): stated by the index between two
    # definitions, so there is no site to match and nothing to guess.
    for site in semantic:
        if site.kind != IMPLEMENTS:
            continue
        out.append(
            Resolved(
                kind="implements",
                source_file=site.file,
                line=site.line,
                scope="",
                def_file=site.def_file,
                def_line=site.def_line,
                tier=SEMANTIC,
                lanes=(SCIP,),
                evidence=[{"path": site.file, "line": site.line}],
            )
        )
    return out


def external_vetoes(
    syntax: list[Site],
    semantic: list[Site],
    fallback: dict[tuple[str, int, str], tuple[str, int]],
    external: list[dict] | None,
) -> list[tuple[Site, tuple[str, int]]]:
    """The sites :func:`join` vetoed (ADR-111), each with lane A's guess.

    Same rule as the join's veto — a call or import site with no in-repo
    semantic resolution, whose key lane B placed outside the repo, and for
    which lane A's fallback had an answer — so this count and the edges
    the join actually drops cannot drift apart. This is where
    ``hobbes lanes`` and the report meet the sites lane A would have drawn
    wrong.
    """
    buckets = index_resolutions(semantic)
    vetoed = _veto_set(external)
    out = []
    for site in syntax:
        if site.kind not in (CALL_SITE, IMPORT_SITE) or site.ambiguous:
            continue
        if match_resolution(site, buckets) is not None:
            continue
        if (site.file, site.line, site.name) not in vetoed:
            continue
        guess = fallback.get((site.file, site.line, site.name))
        if guess is None:
            continue
        out.append((site, guess))
    return out


def withheld_fallbacks(
    syntax: list[Site],
    semantic: list[Site],
    fallback: dict[tuple[str, int, str], tuple[str, int]],
    external: list[dict] | None,
    withhold: frozenset[str],
) -> list[tuple[Site, tuple[str, int]]]:
    """The sites :func:`join` withheld (ADR-113 §2), each with lane A's guess.

    Same rule as the join's, by the same predicate — a call site in a file
    lane B compiled, with no in-repo semantic resolution, not already
    vetoed as external, and for which lane A's fallback had an answer — so
    this count and the edges the join actually drops cannot drift apart.
    This is where ``lane_agreement`` and the ``cpp-fallback`` record meet
    the guesses that were wrong 74 times in 182 on fmt.
    """
    buckets = index_resolutions(semantic)
    vetoed = _veto_set(external)
    out = []
    for site in syntax:
        if site.kind != CALL_SITE or site.ambiguous:
            continue
        if site.file not in withhold:
            continue
        if match_resolution(site, buckets) is not None:
            continue
        if (site.file, site.line, site.name) in vetoed:
            continue
        guess = fallback.get((site.file, site.line, site.name))
        if guess is None:
            continue
        out.append((site, guess))
    return out


@dataclass(frozen=True)
class Disagreement:
    """One call site the two lanes resolved to different places."""

    file: str
    line: int
    name: str
    syntactic_file: str
    syntactic_line: int
    semantic_file: str
    semantic_line: int


def agreement(
    syntax: list[Site],
    semantic: list[Site],
    fallback: dict[tuple[str, int, str], tuple[str, int]],
) -> tuple[int, list[Disagreement]]:
    """Compare the two lanes wherever *both* resolved the same call site.

    Architecture v2 §3.4's self-test, in the sharper form ADR-029 made
    possible: not "do the two edge sets match" but "given the same site,
    do the two providers point at the same definition". A post-hoc set
    comparison cannot ask that — it has already lost which site produced
    which edge.

    Returns ``(sites compared, disagreements)``. Sites only one lane
    resolved are not disagreements: that is the division of labour working
    (lane B resolves what lane A cannot, and the fallback covers the
    reverse), and counting it would drown the real signal.

    A disagreement is an extractor bug in one lane or the other. It is
    free to detect and it is the only check in the system that can catch a
    resolver being confidently wrong rather than merely silent.
    """
    buckets = index_resolutions(semantic)
    compared = 0
    out: list[Disagreement] = []
    for site in syntax:
        if site.kind != CALL_SITE or site.ambiguous:
            continue  # an abstention resolves nothing to compare (ADR-104)
        guess = fallback.get((site.file, site.line, site.name))
        if guess is None:
            continue
        hit = match_resolution(site, buckets)
        if hit is None:
            continue
        compared += 1
        if (hit.def_file, hit.def_line) != guess:
            out.append(
                Disagreement(
                    file=site.file,
                    line=site.line,
                    name=site.name,
                    syntactic_file=guess[0],
                    syntactic_line=guess[1],
                    semantic_file=hit.def_file,
                    semantic_line=hit.def_line,
                )
            )
    return compared, sorted(out, key=lambda d: (d.file, d.line, d.name))


#: The shapes a registered limit gives a site disagreement (ADR-123 §1),
#: in the order :func:`disagreement_shapes` tries them.
SAME_LINE_PAIR = "same-line-pair"
CPP_WITHHELD = "cpp-withheld"


def disagreement_shapes(
    syntax: list[Site],
    semantic: list[Site],
    fallback: dict[tuple[str, int, str], tuple[str, int]],
    disagreements: list[Disagreement],
    withhold: frozenset[str] = frozenset(),
) -> list[str | None]:
    """The shape of each *disagreement*, or None where no rule explains it.

    ADR-123 §1: a disagreement a registered limit produces by construction
    is named by a rule the report can check, never by a triage. One entry
    per row, in the rows' own order, by the predicates :func:`agreement`
    used to produce them.

    - ``same-line-pair`` (C-70) — the fallback is keyed on
      ``(file, line, name)``, so two same-named calls on one line share
      lane A's one guess while lane B answers each by column. The shape
      holds only when that guess *is* lane B's answer at another of those
      sites: then lane A could not have said anything else. A same-named
      line whose guess matches no sibling's answer stays unexplained —
      shaping it by "two sites on the line" would excuse a genuine
      disagreement without evidence (ADR-123's third rejected alternative).
    - ``cpp-withheld`` (C-152) — the site sits in a C++ file lane B
      compiled, where the join draws nothing from lane A's guess anyway
      (ADR-113 §2).

    Checked in that order, so a row both rules could explain is the one
    that explains it completely.
    """
    buckets = index_resolutions(semantic)
    by_key: dict[tuple[str, int, str], list[Site]] = defaultdict(list)
    for site in syntax:
        if site.kind != CALL_SITE or site.ambiguous:
            continue
        by_key[(site.file, site.line, site.name)].append(site)

    out: list[str | None] = []
    for row in disagreements:
        key = (row.file, row.line, row.name)
        guess = fallback.get(key)
        siblings = by_key.get(key, [])
        shape: str | None = None
        if guess is not None and len(siblings) > 1:
            # A sibling whose answer *is* the guess agreed, so it is never
            # the disagreeing site itself — "another of those sites" holds
            # by construction.
            for sibling in siblings:
                hit = match_resolution(sibling, buckets)
                if hit is not None and (hit.def_file, hit.def_line) == guess:
                    shape = SAME_LINE_PAIR
                    break
        if shape is None and row.file in withhold:
            shape = CPP_WITHHELD
        out.append(shape)
    return out


@dataclass(frozen=True)
class Coverage:
    """How much of a file's syntax the semantic provider could account for.

    Tiers say how far to trust an edge that *exists*. Nothing said how much
    was missing — and on this repo 13.9% of call sites produce no edge at
    all, which was invisible. This is the denominator: it makes P6 true for
    lane B, and it is counts rather than guesses.

    Deliberately **not** a confidence score on a hypothetical edge. "This
    function probably calls something it got back" names no target, so it
    cannot be drawn, checked against an invariant, or cited — it is the
    false edge ADR-007 rules out, wearing a probability.
    """

    file: str
    sites: int
    resolved: int
    external: int
    unresolved: int

    @property
    def accounted(self) -> float:
        """Share of call sites with a known destination, in or out of repo."""
        if not self.sites:
            return 1.0
        return round((self.resolved + self.external) / self.sites, 3)


def _dispositions(
    syntax: list[Site],
    semantic: list[Site],
    external: list[dict] | None,
):
    """Each call site with its fate: ``resolved`` | ``external`` |
    ``unresolved``. The one walk both :func:`coverage` and
    :func:`unresolved_sites` derive from, so the counted set and the
    classified set (ADR-045's tail view) cannot drift apart."""
    buckets = index_resolutions(semantic)
    outside = {
        (e["file"], e["line"], e.get("name", "")) for e in (external or [])
    }
    for site in syntax:
        if site.kind != CALL_SITE:
            continue
        if site.ambiguous:
            # ADR-104: the join vetoed whatever lane B had here; the
            # site is unresolved and the tail says why (`union-member`).
            yield site, "unresolved"
        elif match_resolution(site, buckets) is not None:
            yield site, "resolved"
        elif (site.file, site.line, site.name) in outside:
            yield site, "external"
        else:
            yield site, "unresolved"


def coverage(
    syntax: list[Site],
    semantic: list[Site],
    external: list[dict] | None = None,
) -> list[Coverage]:
    """Per-file resolution coverage over the call sites in *syntax*."""
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    slot = {"resolved": 0, "external": 1, "unresolved": 2}
    for site, fate in _dispositions(syntax, semantic, external):
        counts[site.file][slot[fate]] += 1
    return [
        Coverage(file, resolved + ext + un, resolved, ext, un)
        for file, (resolved, ext, un) in sorted(counts.items())
    ]


def unresolved_sites(
    syntax: list[Site],
    semantic: list[Site],
    external: list[dict] | None = None,
) -> list[Site]:
    """The call sites :func:`coverage` counts as ``unresolved`` — the
    tail view's input (ADR-045)."""
    return [
        site
        for site, fate in _dispositions(syntax, semantic, external)
        if fate == "unresolved"
    ]
