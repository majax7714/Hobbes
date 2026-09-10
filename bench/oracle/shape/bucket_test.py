"""bucket.py on a hand-built cell: one miss per bucket rule, and the
collapsed recall over a key with an overload pair. stdlib unittest —
`python3 -m unittest bucket_test` here, which `shape_test.go` runs."""
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
        _miss(("a.ts", 11), "f.ts", 60, "far"),        # two records; the nearest column wins
    ],
}

SHAPES = [
    _shape("a.ts", 3, "foo", "identifier", decls=[{"kind": "function-decl"}]),
    _shape("a.ts", 5, "bar", "identifier", decls=[{"kind": "var:const:top:fn-literal"}]),
    _shape("a.ts", 7, "load", "member", recv="ident:var:let:nested:none"),
    _shape("a.ts", 8, "run", "member", recv="this"),
    _shape("a.ts", 11, "near", "iife", ccol=2),
    _shape("a.ts", 11, "away", "computed", ccol=30),
]

FACTS = {"files": [{"path": "a.ts", "calls": [
    {"line": 5, "name": "bar", "callee": None, "origin": "local", "ambiguous": False},
    {"line": 8, "name": "run", "callee": "f.ts:Runner.run", "origin": "module", "ambiguous": False},
]}]}


class TestBuckets(unittest.TestCase):
    def setUp(self):
        self.out, self.detail, self.examples, self.lane_a = bucket.bucket_misses(REPORT, ORACLE, SHAPES, FACTS)

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

    def test_the_record_nearest_the_oracles_column_is_the_one_read(self):
        by = self.by_bucket()
        self.assertEqual(by.get("computed"), 1)
        self.assertNotIn("iife", by)

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
        pairs, hit, kind = bucket.collapsed_recall(ORACLE, REPORT["rows"])
        # seven oracle targets: foo's two declarations collapse to one
        # pair, the external target is not counted
        self.assertEqual(len(pairs), 6)
        self.assertEqual(hit, {("a.ts", 3, "f.ts", "foo")})
        self.assertEqual(kind[("a.ts", 7, "f.ts", "load")], "method")

    def test_only_confirmed_rows_hit(self):
        rows = [_row(("a.ts", 5), "f.ts", 20, "bar", "contradicted")]
        _, hit, _ = bucket.collapsed_recall(ORACLE, rows)
        self.assertEqual(hit, set())


class TestRender(unittest.TestCase):
    def test_the_report_reads_the_totals_and_the_collapsed_recall(self):
        text = bucket.render(REPORT, ORACLE, SHAPES, FACTS)
        self.assertTrue(text.startswith("TOTAL misses 6"))
        self.assertIn(f"== {bucket.SIBLING}: 1 (16.7%)", text)
        self.assertIn("COLLAPSED in-repo pairs 6 hit 1 recall 16.7%", text)
        self.assertIn("function", text.split("COLLAPSED")[1])
        self.assertIn("e.g. a.ts:9 -> f.ts:50 ghost [static→function]", text)


if __name__ == "__main__":
    unittest.main()
