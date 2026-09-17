"""The evidence IR and the range join (ADR-029).

The join is where "is it a call" (tree-sitter) meets "where does it go"
(SCIP). These cases pin the four rows of the ADR's table, and the two
cases that motivated the whole design: a resolution nothing called is a
reference, and a call nothing resolved is not an edge.
"""

from hobbes.extract import evidence as ev
from hobbes.extract.schema import SEMANTIC, SYNTACTIC


def call(file, line, name, scope="", col=4):
    return ev.Site(ev.TREE_SITTER, ev.CALL_SITE, file, line, name, col, scope)


def imported(file, line, name):
    return ev.Site(ev.TREE_SITTER, ev.IMPORT_SITE, file, line, name, 0)


def resolution(file, line, name, def_file, def_line, col=4):
    return ev.Site(
        ev.SCIP, ev.RESOLUTION, file, line, name, col,
        def_file=def_file, def_line=def_line,
    )


def implements(file, line, def_file, def_line):
    return ev.Site(ev.SCIP, ev.IMPLEMENTS, file, line, def_file=def_file, def_line=def_line)


class TestTheTable:
    def test_a_call_scip_resolved_is_a_semantic_call(self):
        out = ev.join(
            [call("a.py", 10, "run", scope="a.main")],
            [resolution("a.py", 10, "run", "b.py", 5)],
        )
        assert len(out) == 1
        got = out[0]
        assert got.kind == "calls"
        assert got.tier == SEMANTIC
        assert (got.def_file, got.def_line) == ("b.py", 5)
        assert got.lanes == (ev.TREE_SITTER, ev.SCIP)
        assert got.scope == "a.main"

    def test_a_call_scip_missed_falls_back_to_lane_a_as_syntactic(self):
        out = ev.join(
            [call("a.py", 10, "run")],
            [],
            fallback={("a.py", 10, "run"): ("b.py", 5)},
        )
        assert out[0].kind == "calls"
        assert out[0].tier == SYNTACTIC
        assert out[0].lanes == (ev.TREE_SITTER,)

    def test_a_call_nobody_resolved_is_not_an_edge(self):
        # ADR-007 unchanged: false edges are worse than missing ones.
        assert ev.join([call("a.py", 10, "mystery")], []) == []

    def test_a_resolution_no_call_claimed_is_a_reference(self):
        # The case that forced this design: `except StampError:` and type
        # annotations resolve, and are not calls.
        out = ev.join([], [resolution("a.py", 3, "StampError", "e.py", 9)])
        assert len(out) == 1
        assert out[0].kind == "uses"
        assert out[0].tier == SEMANTIC
        assert out[0].lanes == (ev.SCIP,)

    def test_an_implements_site_is_an_implements_fact_from_lane_b_alone(self):
        # ADR-120: the index states the pair between two definitions; no
        # syntax site claims it, and no fallback stands in for it.
        out = ev.join(
            [call("a.py", 10, "run")],
            [implements("a.py", 10, "b.py", 5)],
            fallback={("a.py", 10, "run"): ("c.py", 1)},
        )
        kinds = sorted(o.kind for o in out)
        assert kinds == ["calls", "implements"]
        fact = next(o for o in out if o.kind == "implements")
        assert (fact.source_file, fact.line, fact.def_file, fact.def_line) == ("a.py", 10, "b.py", 5)
        assert fact.tier == SEMANTIC and fact.lanes == (ev.SCIP,) and fact.scope == ""
        assert fact.evidence == [{"path": "a.py", "line": 10}]
        # The call on the same line is untouched: an implements site is
        # never a resolution a call could claim.
        assert next(o for o in out if o.kind == "calls").tier == SYNTACTIC

    def test_an_implements_site_is_not_a_reference_either(self):
        out = ev.join([], [implements("a.py", 1, "b.py", 5)])
        assert [o.kind for o in out] == ["implements"]

    def test_an_import_statement_scip_resolved_is_a_semantic_import(self):
        out = ev.join(
            [imported("a.py", 1, "core")],
            [resolution("a.py", 1, "core", "core.py", 1)],
        )
        assert out[0].kind == "imports"
        assert out[0].tier == SEMANTIC


class TestDisambiguation:
    def test_a_resolution_with_a_different_name_does_not_match(self):
        # Same line, different symbol: matching on line alone would attach
        # the call to whatever else happened to sit there.
        out = ev.join(
            [call("a.py", 10, "run")],
            [resolution("a.py", 10, "other", "b.py", 5)],
        )
        assert [r.kind for r in out] == ["uses"]

    def test_columns_break_ties_between_same_named_resolutions(self):
        # `run(run(x))` — two `run` occurrences on one line.
        out = ev.join(
            [call("a.py", 10, "run", col=20)],
            [
                resolution("a.py", 10, "run", "near.py", 1, col=18),
                resolution("a.py", 10, "run", "far.py", 1, col=4),
            ],
        )
        matched = [r for r in out if r.kind == "calls"]
        assert matched[0].def_file == "near.py"

    def test_a_claimed_resolution_is_not_also_a_reference(self):
        out = ev.join(
            [call("a.py", 10, "run")],
            [resolution("a.py", 10, "run", "b.py", 5)],
        )
        assert [r.kind for r in out] == ["calls"]

    def test_an_unclaimed_resolution_on_a_call_line_still_becomes_a_reference(self):
        # `run(CONFIG)` — the call resolves, CONFIG resolves, both are real.
        out = ev.join(
            [call("a.py", 10, "run", col=0)],
            [
                resolution("a.py", 10, "run", "b.py", 5, col=0),
                resolution("a.py", 10, "CONFIG", "c.py", 2, col=8),
            ],
        )
        kinds = sorted(r.kind for r in out)
        assert kinds == ["calls", "uses"]


class TestProviderSeparation:
    def test_an_ambiguous_site_draws_nothing_and_vetoes_the_resolution(self):
        # ADR-104 / C-97: lane A abstained on a union receiver whose
        # members do not share one declaration; lane B's occurrence there
        # is the first member's — one possible dispatch, not an edge, and
        # not a `uses` reference either.
        ambiguous = ev.Site(
            ev.TREE_SITTER, ev.CALL_SITE, "a.ts", 10, "render", 4, "a.draw",
            ambiguous="union-member",
        )
        out = ev.join(
            [ambiguous],
            [resolution("a.ts", 10, "render", "b.ts", 5)],
            fallback={("a.ts", 10, "render"): ("b.ts", 5)},
        )
        assert out == []

    def test_an_ambiguous_site_does_not_claim_another_name_on_its_line(self):
        ambiguous = ev.Site(
            ev.TREE_SITTER, ev.CALL_SITE, "a.ts", 10, "render", 4, "a.draw",
            ambiguous="union-member",
        )
        out = ev.join([ambiguous], [resolution("a.ts", 10, "helper", "c.ts", 2, col=20)])
        assert [(r.kind, r.def_file) for r in out] == [("uses", "c.ts")]

    def test_a_written_qualifier_rides_only_on_the_semantic_hit(self):
        # ADR-125: the projection compares the qualifier the source spells
        # against the owner lane B resolved. A fallback edge has no index
        # answer to contradict, so the fact carries nothing there.
        site = ev.Site(
            ev.TREE_SITTER, ev.CALL_SITE, "a.cc", 10, "format", 4, "a.g",
            qualifier="S<20>",
        )
        [hit] = ev.join([site], [resolution("a.cc", 10, "format", "b.h", 5)])
        assert (hit.tier, hit.qualifier) == (SEMANTIC, "S<20>")
        [guess] = ev.join([site], [], fallback={("a.cc", 10, "format"): ("b.h", 5)})
        assert (guess.tier, guess.qualifier) == (SYNTACTIC, "")

    def test_a_written_argument_count_rides_only_on_the_semantic_hit(self):
        # ADR-130, on R-qual's condition and for its reason: the
        # projection reads the count the source spells against what the
        # declaration lane B resolved to takes, and a fallback edge is
        # lane A's own guess with no index answer to contradict.
        site = ev.Site(
            ev.TREE_SITTER, ev.CALL_SITE, "a.cc", 10, "copy", 4, "a.g", argc=3,
        )
        [hit] = ev.join([site], [resolution("a.cc", 10, "copy", "b.h", 5)])
        assert (hit.tier, hit.argc) == (SEMANTIC, 3)
        [guess] = ev.join([site], [], fallback={("a.cc", 10, "copy"): ("b.h", 5)})
        assert (guess.tier, guess.argc) == (SYNTACTIC, None)

    def test_definitions_are_not_edges(self):
        out = ev.join([ev.Site(ev.TREE_SITTER, ev.DEFINITION, "a.py", 1, "f")], [])
        assert out == []

    def test_every_result_names_the_providers_behind_it(self):
        out = ev.join(
            [call("a.py", 10, "run")],
            [
                resolution("a.py", 10, "run", "b.py", 5),
                resolution("a.py", 12, "Thing", "c.py", 1),
            ],
        )
        assert all(r.lanes for r in out)
        by_kind = {r.kind: r.lanes for r in out}
        assert by_kind["calls"] == (ev.TREE_SITTER, ev.SCIP)
        assert by_kind["uses"] == (ev.SCIP,)


class TestAnOperatorAppliedBySymbol:
    """ADR-131: lane B names an ``operator…`` at the operator token, no
    call site claims it, and the join draws the call — outside a template,
    at exactly the token lane A recorded, and nowhere else."""

    #: `os << x` at line 10: the `<<` is written at column 3, inside no
    #: template, and the `<` of some other line at 20.
    @staticmethod
    def tokens(*written):
        from array import array

        from hobbes.extract.cppsource import pack_operator

        return {"a.cc": array("Q", sorted(pack_operator(*one) for one in written))}

    @staticmethod
    def reference(name="operator<<", col=3, line=10):
        return resolution("a.cc", line, name, "fmt.h", 5, col=col)

    def counted(self, semantic, operators, syntax=()):
        counts: dict = {"drawn": 0, "in_template": 0}
        out = ev.join(list(syntax), list(semantic), operators=operators, counts=counts)
        return out, counts

    def test_outside_a_template_it_is_a_call_and_not_a_reference(self):
        out, counts = self.counted(
            [self.reference()], self.tokens((10, 3, "<<", False))
        )
        assert [fact.kind for fact in out] == ["calls"]
        [fact] = out
        assert fact.tier == SEMANTIC
        assert fact.lanes == (ev.TREE_SITTER, ev.SCIP)
        # No scope of its own: `project` names the caller by the enclosing
        # symbol, as it does for every unscoped fact.
        assert fact.scope == ""
        # Nothing for R-qual or R-arity to read: there is no written
        # callee at an operator token.
        assert (fact.qualifier, fact.argc) == ("", None)
        assert (fact.def_file, fact.def_line) == ("fmt.h", 5)
        assert counts == {"drawn": 1, "in_template": 0}

    def test_inside_a_template_it_stays_a_use_and_is_counted(self):
        # scip-clang answers a dependent operator with its single by-name
        # candidate, at the same arity, and nothing in the source
        # contradicts it (C-153): given up on purpose, counted so the cost
        # is a number rather than a silence.
        out, counts = self.counted(
            [self.reference()], self.tokens((10, 3, "<<", True))
        )
        assert [fact.kind for fact in out] == ["uses"]
        assert counts == {"drawn": 0, "in_template": 1}

    def test_one_column_off_is_not_the_token(self):
        out, counts = self.counted(
            [self.reference(col=4)], self.tokens((10, 3, "<<", False))
        )
        assert [fact.kind for fact in out] == ["uses"]
        assert counts == {"drawn": 0, "in_template": 0}

    def test_another_spelling_at_that_position_is_not_the_token(self):
        # `a < b` where the index says `operator<<`: the position agrees
        # and the source does not, so nothing is drawn.
        out, _ = self.counted([self.reference()], self.tokens((10, 3, "<", False)))
        assert [fact.kind for fact in out] == ["uses"]

    def test_a_reference_with_no_column_is_not_the_token_either(self):
        out, _ = self.counted(
            [resolution("a.cc", 10, "operator=", "fmt.h", 5, col=-1)],
            self.tokens((10, 3, "=", False)),
        )
        assert [fact.kind for fact in out] == ["uses"]

    def test_a_file_with_no_tokens_at_all_is_untouched(self):
        out, _ = self.counted([self.reference()], {"other.cc": []})
        assert [fact.kind for fact in out] == ["uses"]

    def test_an_operator_written_by_name_still_claims_its_resolution(self):
        # `ns::operator<<(a, 1)` is a call site already, and the site's own
        # claim comes first: one `calls` fact, scoped by lane A, and the
        # resolution is not also drawn by the rule above.
        site = ev.Site(ev.TREE_SITTER, ev.CALL_SITE, "a.cc", 10, "operator<<", 3, "a.g")
        out, counts = self.counted(
            [self.reference()], self.tokens((10, 3, "<<", False)), syntax=[site]
        )
        assert [fact.kind for fact in out] == ["calls"]
        assert out[0].scope == "a.g"
        assert counts == {"drawn": 0, "in_template": 0}

    def test_without_the_tokens_the_join_is_what_it_was(self):
        # P6: with lane B off, or on a repo with no C++, nothing reads the
        # tokens and the same reference is the same `uses` fact.
        assert [fact.kind for fact in ev.join([], [self.reference()])] == ["uses"]

    def test_a_plain_reference_is_never_taken_for_an_operator(self):
        out, counts = self.counted(
            [resolution("a.cc", 10, "format", "fmt.h", 5, col=3)],
            self.tokens((10, 3, "<<", False)),
        )
        assert [fact.kind for fact in out] == ["uses"]
        assert counts == {"drawn": 0, "in_template": 0}


class TestCoverage:
    """The denominator: what the semantic provider could not account for."""

    def test_a_resolved_site_counts_as_resolved(self):
        [row] = ev.coverage(
            [call("a.py", 10, "run")], [resolution("a.py", 10, "run", "b.py", 5)]
        )
        assert (row.sites, row.resolved, row.external, row.unresolved) == (1, 1, 0, 0)
        assert row.accounted == 1.0

    def test_a_site_resolving_outside_the_repo_is_accounted_not_missing(self):
        # `json.dumps(...)` is not a repo edge and not a failure either.
        [row] = ev.coverage(
            [call("a.py", 10, "dumps")],
            [],
            external=[{"file": "a.py", "line": 10, "name": "dumps", "package": "python:python-stdlib"}],
        )
        assert (row.resolved, row.external, row.unresolved) == (0, 1, 0)
        assert row.accounted == 1.0

    def test_a_site_nobody_resolved_is_counted_as_unknown(self):
        [row] = ev.coverage([call("a.py", 10, "mystery")], [])
        assert (row.resolved, row.external, row.unresolved) == (0, 0, 1)
        assert row.accounted == 0.0

    def test_coverage_is_per_file(self):
        rows = ev.coverage(
            [call("a.py", 1, "x"), call("b.py", 1, "y")],
            [resolution("a.py", 1, "x", "c.py", 2)],
        )
        assert [r.file for r in rows] == ["a.py", "b.py"]
        assert rows[0].accounted == 1.0 and rows[1].accounted == 0.0

    def test_an_ambiguous_site_is_unresolved_even_where_scip_answered(self):
        # ADR-104: the veto and the denominator agree — the site the join
        # drew nothing for is counted unresolved, so the tail can name it.
        ambiguous = ev.Site(
            ev.TREE_SITTER, ev.CALL_SITE, "a.ts", 10, "render", 4, "a.draw",
            ambiguous="union-member",
        )
        semantic = [resolution("a.ts", 10, "render", "b.ts", 5)]
        [row] = ev.coverage([ambiguous], semantic)
        assert (row.sites, row.resolved, row.unresolved) == (1, 0, 1)
        assert ev.unresolved_sites([ambiguous], semantic) == [ambiguous]

    def test_definitions_are_not_call_sites(self):
        assert ev.coverage([ev.Site(ev.TREE_SITTER, ev.DEFINITION, "a.py", 1, "f")], []) == []

    def test_a_file_with_no_calls_reports_nothing_rather_than_zero_percent(self):
        assert ev.coverage([], []) == []


class TestExternalVeto:
    """ADR-111: a site lane B resolved outside the repo vetoes lane A's
    fallback there — one case per language, each in that language's own
    external-reference shape (a moniker, a package, a column)."""

    def _check(self, name, moniker, package, col=4):
        site = call("a.src", 10, name)
        fallback = {("a.src", 10, name): ("guess.src", 1)}
        outside = [
            {"file": "a.src", "line": 10, "col": col, "name": name,
             "package": package, "moniker": moniker}
        ]

        # the fallback edge is vetoed
        assert ev.join([site], [], fallback=fallback, external=outside) == []

        # an in_repo reference at the same key does not veto
        in_repo = [{**outside[0], "in_repo": True}]
        out = ev.join([site], [], fallback=fallback, external=in_repo)
        assert len(out) == 1 and out[0].tier == SYNTACTIC
        assert (out[0].def_file, out[0].def_line) == ("guess.src", 1)

        # a site with an in-repo resolution at the same key is untouched
        semantic = [resolution("a.src", 10, name, "real.src", 2)]
        out2 = ev.join([site], semantic, fallback=fallback, external=outside)
        assert len(out2) == 1 and out2[0].tier == SEMANTIC
        assert (out2[0].def_file, out2[0].def_line) == ("real.src", 2)

        # the site's coverage fate is external
        [row] = ev.coverage([site], [], external=outside)
        assert (row.resolved, row.external, row.unresolved) == (0, 1, 0)

        # agreement's count is unchanged: nothing here is a disagreement
        compared, bad = ev.agreement([site], [], fallback)
        assert (compared, bad) == (0, [])

    def test_python(self):
        self._check(
            "dumps", "scip-python python python-stdlib 3.11 json/dumps().",
            "python:python-stdlib",
        )

    def test_typescript(self):
        self._check(
            "readFileSync",
            "scip-typescript npm @types/node 20.0.0 `fs.d.ts`/readFileSync().",
            "npm:@types/node",
        )

    def test_go(self):
        self._check(
            "Sprintf", "scip-go gomod github.com/golang/go/src go1.26 fmt/Sprintf().",
            "gomod:github.com/golang/go/src",
        )

    def test_rust(self):
        self._check(
            "println",
            "rust-analyzer cargo std https://github.com/rust-lang/rust/library/std "
            "macros/println!",
            "cargo:std",
        )

    def test_java(self):
        self._check(
            "assertEquals",
            "scip-java maven maven/org.junit.jupiter/junit-jupiter-api 5.10.0 "
            "org/junit/jupiter/api/Assertions#assertEquals().",
            "maven:org.junit.jupiter:junit-jupiter-api",
        )

    def test_c(self):
        self._check(
            "strcasestr", "cxx . . $ strcasestr(6efceb6909523ce2).", "",
        )


class TestExternalVetoes:
    """:func:`ev.external_vetoes` (ADR-111): the sites the join dropped,
    with lane A's guess — the same rule as the join's, so the count and
    the join's dropped edges cannot drift apart."""

    def test_it_returns_the_vetoed_site_and_lane_as_guess(self):
        site = call("a.py", 10, "dumps")
        fallback = {("a.py", 10, "dumps"): ("b.py", 5)}
        external = [{"file": "a.py", "line": 10, "name": "dumps",
                      "package": "python:python-stdlib"}]
        out = ev.external_vetoes([site], [], fallback, external)
        assert len(out) == 1
        got_site, guess = out[0]
        assert got_site is site
        assert guess == ("b.py", 5)

    def test_an_in_repo_reference_is_not_returned(self):
        site = call("a.py", 10, "dumps")
        fallback = {("a.py", 10, "dumps"): ("b.py", 5)}
        external = [{"file": "a.py", "line": 10, "name": "dumps", "in_repo": True}]
        assert ev.external_vetoes([site], [], fallback, external) == []

    def test_it_agrees_with_the_join_on_the_same_inputs(self):
        site = call("a.py", 10, "dumps")
        fallback = {("a.py", 10, "dumps"): ("b.py", 5)}
        external = [{"file": "a.py", "line": 10, "name": "dumps"}]
        assert ev.join([site], [], fallback=fallback, external=external) == []
        assert len(ev.external_vetoes([site], [], fallback, external)) == 1


class TestWithheldFallbacks:
    """Rule 2 of ADR-113 §2's third amendment: a C++ file lane B compiled
    draws no fallback edge. Where scip-clang indexed the file and answered
    nothing at the site, lane A's name guess was wrong 74 times in 182 on
    fmt — C's namespace-blind ranks reaching a mock, or a rank-3 "unique"
    that a parse error had made untrue (C-145)."""

    def test_a_withheld_file_s_guess_draws_no_edge_and_is_returned(self):
        site = call("fmt.cc", 10, "close")
        fallback = {("fmt.cc", 10, "close"): ("mock.h", 5)}
        assert ev.join([site], [], fallback=fallback, withhold=frozenset({"fmt.cc"})) == []
        out = ev.withheld_fallbacks([site], [], fallback, None, frozenset({"fmt.cc"}))
        assert len(out) == 1
        got_site, guess = out[0]
        assert got_site is site
        assert guess == ("mock.h", 5)

    def test_the_same_site_in_a_file_lane_b_did_not_index_keeps_its_edge(self):
        # C-135's C++ face: no compile database, a failed build, or a file
        # outside it — lane B never looked, so the floor still stands.
        site = call("tools/aux.cc", 10, "close")
        fallback = {("tools/aux.cc", 10, "close"): ("mock.h", 5)}
        out = ev.join([site], [], fallback=fallback, withhold=frozenset({"fmt.cc"}))
        assert [(e.tier, e.def_file) for e in out] == [(SYNTACTIC, "mock.h")]
        assert ev.withheld_fallbacks([site], [], fallback, None, frozenset({"fmt.cc"})) == []

    def test_a_semantic_hit_in_a_withheld_file_still_draws_its_edge(self):
        # The rule withholds lane A's guess, never lane B's answer.
        site = call("fmt.cc", 10, "write")
        out = ev.join(
            [site],
            [resolution("fmt.cc", 10, "write", "fmt.h", 22)],
            fallback={("fmt.cc", 10, "write"): ("mock.h", 5)},
            withhold=frozenset({"fmt.cc"}),
        )
        assert [(e.tier, e.def_file, e.def_line) for e in out] == [(SEMANTIC, "fmt.h", 22)]

    def test_an_import_site_in_a_withheld_file_is_untouched(self):
        # An include is lane A's fact about the source; lane B neither
        # contradicts it nor replaces it.
        site = imported("fmt.cc", 1, "fmt.h")
        fallback = {("fmt.cc", 1, "fmt.h"): ("fmt.h", 1)}
        out = ev.join([site], [], fallback=fallback, withhold=frozenset({"fmt.cc"}))
        assert [(e.kind, e.tier) for e in out] == [("imports", SYNTACTIC)]
        assert ev.withheld_fallbacks([site], [], fallback, None, frozenset({"fmt.cc"})) == []

    def test_a_site_the_external_veto_dropped_is_not_also_counted_withheld(self):
        # Both rules drop the same edge; only one of them may claim it, or
        # the two counts double-count one site.
        site = call("fmt.cc", 10, "close")
        fallback = {("fmt.cc", 10, "close"): ("mock.h", 5)}
        external = [{"file": "fmt.cc", "line": 10, "name": "close"}]
        assert ev.join(
            [site], [], fallback=fallback, external=external,
            withhold=frozenset({"fmt.cc"}),
        ) == []
        assert len(ev.external_vetoes([site], [], fallback, external)) == 1
        assert ev.withheld_fallbacks([site], [], fallback, external, frozenset({"fmt.cc"})) == []


class TestLaneAgreement:
    """§3.4's self-test, in ADR-029's sharper form.

    Not "do the two edge sets match" but "given the same site, do the two
    providers point at the same definition". Only sites *both* lanes
    resolved are compared — a site one lane alone could answer is the
    division of labour working, and counting it would bury the real
    signal under hundreds of expected differences.
    """

    def test_agreeing_sites_are_compared_and_produce_nothing(self):
        compared, bad = ev.agreement(
            [call("a.py", 1, "run")],
            [resolution("a.py", 1, "run", "b.py", 10)],
            {("a.py", 1, "run"): ("b.py", 10)},
        )
        assert compared == 1
        assert bad == []

    def test_a_site_the_lanes_resolve_differently_is_reported(self):
        compared, (row,) = ev.agreement(
            [call("a.py", 1, "run")],
            [resolution("a.py", 1, "run", "real.py", 3)],
            {("a.py", 1, "run"): ("guess.py", 7)},
        )
        assert compared == 1
        assert (row.file, row.line, row.name) == ("a.py", 1, "run")
        assert (row.syntactic_file, row.syntactic_line) == ("guess.py", 7)
        assert (row.semantic_file, row.semantic_line) == ("real.py", 3)

    def test_a_site_only_the_semantic_lane_resolved_is_not_a_disagreement(self):
        compared, bad = ev.agreement(
            [call("a.py", 1, "run")],
            [resolution("a.py", 1, "run", "b.py", 10)],
            {},
        )
        assert (compared, bad) == (0, [])

    def test_a_site_only_the_syntax_lane_resolved_is_not_a_disagreement(self):
        compared, bad = ev.agreement(
            [call("a.py", 1, "run")], [], {("a.py", 1, "run"): ("b.py", 10)}
        )
        assert (compared, bad) == (0, [])

    def test_an_ambiguous_site_is_not_compared(self):
        # An abstention resolves nothing; a stale fallback for it is not
        # a disagreement (ADR-104).
        ambiguous = ev.Site(
            ev.TREE_SITTER, ev.CALL_SITE, "a.ts", 10, "render", 4, "a.draw",
            ambiguous="union-member",
        )
        compared, out = ev.agreement(
            [ambiguous],
            [resolution("a.ts", 10, "render", "b.ts", 5)],
            {("a.ts", 10, "render"): ("c.ts", 9)},
        )
        assert (compared, out) == (0, [])

    def test_imports_are_not_compared_here(self):
        # Import sites are compared at the module-edge level, where lane
        # A's ext:/env: reach makes a set comparison meaningful.
        compared, bad = ev.agreement(
            [imported("a.py", 1, "os")],
            [resolution("a.py", 1, "os", "b.py", 1)],
            {("a.py", 1, "os"): ("c.py", 2)},
        )
        assert (compared, bad) == (0, [])

    def test_disagreements_are_ordered_for_a_stable_report(self):
        sites = [call("b.py", 5, "z"), call("a.py", 9, "y"), call("a.py", 2, "x")]
        semantic = [
            resolution("b.py", 5, "z", "r.py", 1),
            resolution("a.py", 9, "y", "r.py", 2),
            resolution("a.py", 2, "x", "r.py", 3),
        ]
        fallback = {
            ("b.py", 5, "z"): ("g.py", 1),
            ("a.py", 9, "y"): ("g.py", 2),
            ("a.py", 2, "x"): ("g.py", 3),
        }
        _, bad = ev.agreement(sites, semantic, fallback)
        assert [(d.file, d.line) for d in bad] == [("a.py", 2), ("a.py", 9), ("b.py", 5)]


class TestDisagreementShapes:
    """ADR-123 §1: the two registered limits that produce a disagreement by
    construction name themselves, by a rule the report can check."""

    def test_the_c_70_swap_is_a_same_line_pair(self):
        # One line, two `run` calls; lane A holds one guess for both keys
        # (C-70) while lane B answers each by column, so the site whose
        # answer lane A's guess is not disagrees — and could not have done
        # otherwise.
        sites = [call("a.py", 1, "run", col=4), call("a.py", 1, "run", col=20)]
        semantic = [
            resolution("a.py", 1, "run", "x.py", 1, col=4),
            resolution("a.py", 1, "run", "y.py", 2, col=20),
        ]
        fallback = {("a.py", 1, "run"): ("x.py", 1)}
        _, bad = ev.agreement(sites, semantic, fallback)
        assert [(d.semantic_file, d.semantic_line) for d in bad] == [("y.py", 2)]
        assert ev.disagreement_shapes(sites, semantic, fallback, bad) == [
            "same-line-pair"
        ]

    def test_a_same_named_line_whose_guess_matches_no_sibling_stays_unexplained(self):
        # The honesty case (ADR-123's third rejected alternative): two
        # same-named sites alone would excuse a genuine disagreement, so
        # the rule asks that lane A's guess *be* a sibling's answer.
        sites = [call("a.py", 1, "run", col=4), call("a.py", 1, "run", col=20)]
        semantic = [
            resolution("a.py", 1, "run", "x.py", 1, col=4),
            resolution("a.py", 1, "run", "y.py", 2, col=20),
        ]
        fallback = {("a.py", 1, "run"): ("elsewhere.py", 9)}
        _, bad = ev.agreement(sites, semantic, fallback)
        assert len(bad) == 2
        assert ev.disagreement_shapes(sites, semantic, fallback, bad) == [None, None]

    def test_a_site_in_a_file_lane_b_compiled_is_cpp_withheld(self):
        sites = [call("fmt.cc", 10, "close")]
        semantic = [resolution("fmt.cc", 10, "close", "real.h", 3)]
        fallback = {("fmt.cc", 10, "close"): ("guess.h", 7)}
        _, bad = ev.agreement(sites, semantic, fallback)
        assert ev.disagreement_shapes(
            sites, semantic, fallback, bad, frozenset({"fmt.cc"})
        ) == ["cpp-withheld"]

    def test_the_same_site_outside_the_withhold_set_has_no_shape(self):
        # C-152 is about the files lane B *compiled*; elsewhere lane A's
        # guess is drawn, so a disagreement there is unexplained.
        sites = [call("fmt.cc", 10, "close")]
        semantic = [resolution("fmt.cc", 10, "close", "real.h", 3)]
        fallback = {("fmt.cc", 10, "close"): ("guess.h", 7)}
        _, bad = ev.agreement(sites, semantic, fallback)
        assert ev.disagreement_shapes(sites, semantic, fallback, bad) == [None]

    def test_a_row_both_rules_explain_is_the_same_line_pair(self):
        # The order: C-70 explains the row completely, C-152 only says the
        # edge was not drawn.
        sites = [call("fmt.cc", 1, "run", col=4), call("fmt.cc", 1, "run", col=20)]
        semantic = [
            resolution("fmt.cc", 1, "run", "x.h", 1, col=4),
            resolution("fmt.cc", 1, "run", "y.h", 2, col=20),
        ]
        fallback = {("fmt.cc", 1, "run"): ("x.h", 1)}
        _, bad = ev.agreement(sites, semantic, fallback)
        assert ev.disagreement_shapes(
            sites, semantic, fallback, bad, frozenset({"fmt.cc"})
        ) == ["same-line-pair"]
