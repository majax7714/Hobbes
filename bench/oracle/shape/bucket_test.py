"""bucket.py on a hand-built cell: one miss per bucket rule, and the
collapsed recall over a key with an overload pair; then the identity
cases of H-22 (two same-named methods in one file, an ambiguous site, a
line with records naming something else, a `new`, a confirmed row no
target explains, a collapsed pair of mixed kinds, lane A's ambiguity).
stdlib unittest — `python3 -m unittest bucket_test` here, which
`shape_test.go` runs."""
import unittest

import bucket


def _site(path, line, col=0):
    return {"path": path, "line": line, "col": col}


def _row(site, target_path, target_line, name, bucket_="confirmed"):
    return {
        "bucket": bucket_,
        "edge": {
            "site": {"path": site[0], "line": site[1]},
            "target": {"path": target_path, "line": target_line},
            "target_id": f"{target_path.rsplit('.', 1)[0]}.{name}",  # a module-qualified symbol id
        },
    }


def _miss(site, target_path, target_line, name, kind="function", cls="static→function"):
    return {
        "site": {"path": site[0], "line": site[1]},
        "target": {"name": name, "kind": kind, "pos": {"path": target_path, "line": target_line}},
        "class": cls,
    }


def _shape(path, line, name, shape, recv=None, decls=(), ccol=0, cline=None):
    return {
        "path": path, "line": line, "cline": line if cline is None else cline,
        "col": ccol, "ccol": ccol, "name": name, "shape": shape, "recv": recv,
        "decls": list(decls), "sigDecl": None, "js": False,
    }


# The key: every miss below is a pair the oracle names. `foo` is
# declared twice (an overload signature at f.ts:10 and its implementation
# at f.ts:12) — the grain the collapsed recall removes.
ORACLE = {
    "sites": [
        {"pos": _site("a.ts", 3), "col": 4, "targets": [
            {"name": "foo", "kind": "function", "pos": {"path": "f.ts", "line": 10}},
            {"name": "foo", "kind": "function", "pos": {"path": "f.ts", "line": 12}},
        ]},
        {"pos": _site("a.ts", 5), "col": 4, "targets": [
            {"name": "bar", "kind": "function", "pos": {"path": "f.ts", "line": 20}},
        ]},
        {"pos": _site("a.ts", 7), "col": 2, "targets": [
            {"name": "load", "kind": "method", "pos": {"path": "f.ts", "line": 30}},
        ]},
        {"pos": _site("a.ts", 8), "col": 2, "targets": [
            {"name": "run", "kind": "method", "pos": {"path": "f.ts", "line": 40}},
        ]},
        {"pos": _site("a.ts", 9), "col": 2, "targets": [
            {"name": "ghost", "kind": "function", "pos": {"path": "f.ts", "line": 50}},
        ]},
        {"pos": _site("a.ts", 11), "col": 28, "targets": [
            {"name": "far", "kind": "function", "pos": {"path": "f.ts", "line": 60}},
        ]},
        {"pos": _site("a.ts", 13), "col": 0, "targets": [
            {"name": "ext", "kind": "function", "external": True, "pos": {"path": "node_modules/x/i.d.ts", "line": 1}},
        ]},
    ]
}

REPORT = {
    "rows": [
        _row(("a.ts", 3), "f.ts", 12, "foo"),          # the implementation, confirmed
        _row(("a.ts", 13), "f.ts", 99, "other", "silent"),
    ],
    "misses": [
        _miss(("a.ts", 3), "f.ts", 10, "foo"),         # the signature: sibling grain
        _miss(("a.ts", 5), "f.ts", 20, "bar"),         # a const arrow: below the floor
        _miss(("a.ts", 7), "f.ts", 30, "load", "method", "static→method"),
        _miss(("a.ts", 8), "f.ts", 40, "run", "method", "static→method"),
        _miss(("a.ts", 9), "f.ts", 50, "ghost"),       # no checker record on the line
        _miss(("a.ts", 11), "f.ts", 60, "far"),        # two records; the one at the oracle's column wins
    ],
}

SHAPES = [
    _shape("a.ts", 3, "foo", "identifier", decls=[{"kind": "function-decl"}]),
    _shape("a.ts", 5, "bar", "identifier", decls=[{"kind": "var:const:top:fn-literal"}]),
    _shape("a.ts", 7, "load", "member", recv="ident:var:let:nested:none"),
    _shape("a.ts", 8, "run", "member", recv="this"),
    _shape("a.ts", 11, "near", "iife", ccol=2),
    _shape("a.ts", 11, "away", "computed", ccol=27),  # the oracle's col 28 is 1-based
]

FACTS = {"files": [{"path": "a.ts", "calls": [
    {"line": 5, "name": "bar", "callee": None, "origin": "local", "ambiguous": False},
    {"line": 8, "name": "run", "callee": "f.ts:Runner.run", "origin": "module", "ambiguous": False},
]}]}


class TestBuckets(unittest.TestCase):
    def setUp(self):
        self.out, self.detail, self.examples, self.lane_a, self.how = bucket.bucket_misses(REPORT, ORACLE, SHAPES, FACTS)

    def by_bucket(self):
        return {b: n for (cls, b), n in self.out.items()}

    def test_every_miss_lands_in_exactly_one_bucket(self):
        self.assertEqual(sum(self.out.values()), len(REPORT["misses"]))

    def test_a_confirmed_edge_to_the_same_name_at_another_line_is_the_oracles_grain(self):
        self.assertEqual(self.out[("static→function", bucket.SIBLING)], 1)
        self.assertEqual(self.detail[bucket.SIBLING], {("function", "f.ts", 10, "foo"): 1})

    def test_an_identifier_is_bucketed_by_its_declaration_kind(self):
        self.assertEqual(self.by_bucket()["identifier:const-top-fn-literal"], 1)

    def test_a_member_is_bucketed_by_its_receiver_shape(self):
        by = self.by_bucket()
        self.assertEqual(by["member:on-let-nested-none"], 1)
        self.assertEqual(by["member:on-this"], 1)

    def test_a_line_with_no_checker_record_says_so(self):
        self.assertEqual(self.by_bucket()[bucket.NO_SITE], 1)

    def test_the_record_at_the_oracles_column_is_the_one_read(self):
        by = self.by_bucket()
        self.assertEqual(by.get("computed"), 1)
        self.assertNotIn("iife", by)

    def test_the_report_says_how_each_miss_found_its_record(self):
        # foo: sibling; far: at the column; bar, load, run: by name (the
        # fixture's columns do not line up — read as such, not as exact);
        # ghost: no record on the line
        self.assertEqual(dict(self.how), {"sibling": 1, "exact": 1, "name": 3, "none": 1})

    def test_lane_as_record_at_the_site_is_carried_per_bucket(self):
        self.assertEqual(dict(self.lane_a["identifier:const-top-fn-literal"]), {("no-callee", "local", False): 1})
        self.assertEqual(dict(self.lane_a["member:on-this"]), {("callee", "module", False): 1})
        self.assertEqual(dict(self.lane_a["member:on-let-nested-none"]), {("no-lane-A-record",): 1})

    def test_examples_name_site_target_and_class(self):
        self.assertEqual(self.examples[bucket.SIBLING], ["a.ts:3 -> f.ts:10 foo [static→function]"])


class TestShapeBucket(unittest.TestCase):
    def test_an_unresolved_identifier(self):
        self.assertEqual(bucket.shape_bucket(_shape("a.ts", 1, "x", "identifier")), "identifier:unresolved")

    def test_a_non_variable_declaration_keeps_its_kind(self):
        self.assertEqual(bucket.shape_bucket(_shape("a.ts", 1, "x", "identifier", decls=[{"kind": "param"}])), "identifier:param")

    def test_a_member_on_a_call_result(self):
        self.assertEqual(bucket.shape_bucket(_shape("a.ts", 1, "x", "member", recv="call-result")), "member:on-call-result")

    def test_other_shapes_are_their_own_bucket(self):
        self.assertEqual(bucket.shape_bucket(_shape("a.ts", 1, "x", "keyword")), "keyword")


class TestCollapsedRecall(unittest.TestCase):
    def test_one_pair_per_site_and_named_target_and_no_external(self):
        pairs, hit, kind, unmatched = bucket.collapsed_recall(ORACLE, REPORT["rows"])
        # seven oracle targets: foo's two declarations collapse to one
        # pair, the external target is not counted
        self.assertEqual(len(pairs), 6)
        self.assertEqual(hit, {("a.ts", 3, "f.ts", "foo")})
        self.assertEqual(kind[("a.ts", 7, "f.ts", "load")], "method")
        self.assertEqual(unmatched, [])

    def test_only_confirmed_rows_hit(self):
        rows = [_row(("a.ts", 5), "f.ts", 20, "bar", "contradicted")]
        _, hit, _, _ = bucket.collapsed_recall(ORACLE, rows)
        self.assertEqual(hit, set())


class TestRender(unittest.TestCase):
    def test_the_report_reads_the_totals_and_the_collapsed_recall(self):
        text = bucket.render(REPORT, ORACLE, SHAPES, FACTS)
        self.assertTrue(text.startswith("TOTAL misses 6\nattribution: sibling 1, exact 1, name 3, ambiguous 0, none 1"))
        self.assertIn(f"== {bucket.SIBLING}: 1 (16.7%)", text)
        self.assertIn("COLLAPSED in-repo pairs 6 hit 1 recall 16.7%", text)
        self.assertIn("confirmed rows no target at their position explains: 0", text)
        self.assertIn("function", text.split("COLLAPSED")[1])
        self.assertIn("e.g. a.ts:9 -> f.ts:50 ghost [static→function]", text)

    def test_the_graders_collapsed_line_is_cross_checked(self):
        # an older report.json: no field, said so
        self.assertIn("grader: this report.json carries no recall-collapsed", bucket.render(REPORT, ORACLE, SHAPES, FACTS))
        # the grader's number, the same identity: agrees
        same = bucket.render({**REPORT, "collapsed_pairs": 6, "collapsed_hits": 1}, ORACLE, SHAPES, FACTS)
        self.assertIn("grader: recall-collapsed 1/6 — the same number", same)
        # a report graded against another key: the mismatch is named, not averaged
        other = bucket.render({**REPORT, "collapsed_pairs": 7, "collapsed_hits": 1}, ORACLE, SHAPES, FACTS)
        self.assertIn("grader: recall-collapsed 1/7 — DISAGREES with this join", other)


# H-22 (the 2026-09-10 review): the identity cases, on a cell of their
# own. `Runner.run` and `Other.run` are two methods of one file; the
# line-15 call reaches the first and misses the second.
ORACLE2 = {
    "sites": [
        {"pos": _site("b.ts", 15), "col": 3, "targets": [
            {"name": "Runner.run", "kind": "method", "pos": {"path": "g.ts", "line": 70}},
        ]},
        {"pos": _site("b.ts", 15), "col": 12, "targets": [
            {"name": "Other.run", "kind": "method", "pos": {"path": "g.ts", "line": 80}},
        ]},
        {"pos": _site("b.ts", 17), "col": 6, "targets": [
            {"name": "dup", "kind": "function", "pos": {"path": "g.ts", "line": 90}},
        ]},
        {"pos": _site("b.ts", 19), "col": 40, "targets": [
            {"name": "nah", "kind": "function", "pos": {"path": "g.ts", "line": 95}},
        ]},
        {"pos": _site("b.ts", 21), "col": 5, "targets": [
            {"name": "Box", "kind": "class", "pos": {"path": "g.ts", "line": 100}},
        ]},
        {"pos": _site("b.ts", 25), "col": 1, "targets": [
            {"name": "mk", "kind": "function", "pos": {"path": "g.ts", "line": 110}},
            {"name": "mk", "kind": "variable", "pos": {"path": "g.ts", "line": 111}},
        ]},
        {"pos": _site("b.ts", 27), "col": 1, "targets": [
            {"name": "amb", "kind": "function", "pos": {"path": "g.ts", "line": 120}},
        ]},
        {"pos": _site("b.ts", 29), "col": 1, "targets": [
            {"name": "x", "kind": "function", "pos": {"path": "g.ts", "line": 130}},
        ]},
    ]
}

REPORT2 = {
    "rows": [
        _row(("b.ts", 15), "g.ts", 70, "run"),            # Runner.run, confirmed
        _row(("b.ts", 23), "g.ts", 999, "nowhere"),       # confirmed, but no oracle site at b.ts:23
    ],
    "misses": [
        _miss(("b.ts", 15), "g.ts", 80, "Other.run", "method", "static→method"),
        _miss(("b.ts", 17), "g.ts", 90, "dup"),
        _miss(("b.ts", 19), "g.ts", 95, "nah"),
        _miss(("b.ts", 21), "g.ts", 100, "Box", "class", "static→class"),
        _miss(("b.ts", 27), "g.ts", 120, "amb"),
        _miss(("b.ts", 29), "g.ts", 130, "x"),
    ],
}

SHAPES2 = [
    _shape("b.ts", 15, "run", "member", recv="ident:class", ccol=2),
    _shape("b.ts", 15, "run", "member", recv="ident:class", ccol=11),
    _shape("b.ts", 17, "p", "identifier", decls=[{"kind": "param"}], ccol=5),
    _shape("b.ts", 17, "q", "identifier", decls=[{"kind": "import"}], ccol=5),
    _shape("b.ts", 19, "zzz", "identifier", decls=[{"kind": "param"}], ccol=0),
    _shape("b.ts", 21, "Box", "new", decls=[{"kind": "class"}], ccol=4),
    _shape("b.ts", 27, "amb", "identifier", decls=[{"kind": "function-decl"}], ccol=0),
    _shape("b.ts", 29, "x", "identifier", decls=[{"kind": "function-decl"}], ccol=0),
]

FACTS2 = {"files": [{"path": "b.ts", "calls": [
    {"line": 27, "name": "amb", "callee": "g.ts:amb", "origin": "module", "ambiguous": False},
    {"line": 27, "name": "amb", "callee": None, "origin": "local", "ambiguous": False},
    {"line": 29, "name": "other", "callee": None, "origin": "local", "ambiguous": False},
]}]}


class TestIdentity(unittest.TestCase):
    def setUp(self):
        self.out, self.detail, self.examples, self.lane_a, self.how = bucket.bucket_misses(REPORT2, ORACLE2, SHAPES2, FACTS2)
        self.by = {b: n for (cls, b), n in self.out.items()}

    def test_a_same_named_method_of_another_class_is_not_a_sibling(self):
        # the confirmed edge reaches Runner.run; Other.run shares the
        # bare name, not the symbol — a real miss, bucketed by its shape
        self.assertNotIn(bucket.SIBLING, self.by)
        self.assertEqual(self.by["member:on-ident:class"], 1)
        self.assertEqual(self.detail["member:on-ident:class"], {("method", "g.ts", 80, "run"): 1})

    def test_two_readings_at_the_column_are_ambiguous_not_the_first(self):
        self.assertEqual(self.by[bucket.AMBIGUOUS], 1)
        self.assertEqual(self.examples[bucket.AMBIGUOUS], ["b.ts:17 -> g.ts:90 dup [static→function]"])

    def test_records_on_the_line_naming_something_else_are_not_this_callee(self):
        self.assertEqual(self.by[bucket.NO_RECORD], 1)
        self.assertNotIn(bucket.NO_SITE, self.by)

    def test_a_new_expression_is_bucketed_by_what_the_name_declares(self):
        self.assertEqual(self.by["new:class"], 1)
        self.assertEqual(self.how["exact"], 4)  # Other.run, Box, amb and x (col 1 → 0)

    def test_lane_as_disagreeing_records_are_ambiguous_and_other_names_are_not_a_reading(self):
        self.assertEqual(dict(self.lane_a["identifier:function-decl"]),
                         {("ambiguous", 2): 1, ("lane-A-record-other-name",): 1})

    def test_the_collapse_keeps_same_named_targets_apart_and_reports_the_unexplained_row(self):
        pairs, hit, kind, unmatched = bucket.collapsed_recall(ORACLE2, REPORT2["rows"])
        self.assertIn(("b.ts", 15, "g.ts", "Runner.run"), pairs)
        self.assertIn(("b.ts", 15, "g.ts", "Other.run"), pairs)
        self.assertEqual(hit, {("b.ts", 15, "g.ts", "Runner.run")})
        self.assertEqual(kind[("b.ts", 25, "g.ts", "mk")], "mixed:function|variable")
        self.assertEqual([r["edge"]["target"]["line"] for r in unmatched], [999])

    def test_the_report_carries_the_identity_line(self):
        text = bucket.render(REPORT2, ORACLE2, SHAPES2, FACTS2)
        self.assertIn("attribution: sibling 0, exact 4, name 0, ambiguous 1, none 1", text)
        self.assertIn("confirmed rows no target at their position explains: 1", text)
        self.assertIn("mixed:function|variable", text)


if __name__ == "__main__":
    unittest.main()
