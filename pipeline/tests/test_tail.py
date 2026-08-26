"""The tail view (ADR-045): the unresolved remainder, classified by
observation.

Two properties matter more than any single class: every unresolved site
lands in exactly one class (per file the tail sums to the coverage
row's ``unresolved``), and nothing here infers — a class is a checkable
observation about the site or it is ``unclassified``. The integration
case runs the real extractor on the miniapp fixture with lane B off,
which is the suite's default and the degraded path P6 cares about: the
tail view must exist there too, not only when an indexer ran.
"""

from pathlib import Path

from hobbes.extract import evidence as ev
from hobbes.extract import extract_repo, tail

FIXTURE = Path(__file__).parent / "fixtures" / "miniapp"


def site(file, line, name, col=4):
    return ev.Site(ev.TREE_SITTER, ev.CALL_SITE, file, line, name, col)


def write(tmp_path, rel, text):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return rel


class TestClasses:
    def test_a_bare_builtin_named_call_is_builtin_name(self, tmp_path):
        f = write(tmp_path, "a.py", "x = 1\nn = len(items)\n")
        tails = tail.classify([site(f, 2, "len")], tmp_path)
        assert tails[f] == {tail.BUILTIN: 1}

    def test_builtin_names_are_per_language(self, tmp_path):
        # `len` is a Go builtin too; `isinstance` is not.
        f = write(tmp_path, "a.go", "n := len(items)\nisinstance(x)\n")
        tails = tail.classify(
            [site(f, 1, "len", col=9), site(f, 2, "isinstance", col=0)], tmp_path
        )
        assert tails[f][tail.BUILTIN] == 1
        assert tails[f][tail.UNCLASSIFIED] == 1

    def test_a_scope_contained_lane_a_binding_is_local(self, tmp_path):
        # `fake_policy_bin` is a fixture parameter of the enclosing test:
        # bound at line 1, function spans 1-3, call at line 2 — local.
        f = write(tmp_path, "test_a.py",
                  "def test_x(fake_policy_bin):\n"
                  "    out = fake_policy_bin('deny')\n"
                  "    assert out\n")
        bindings = {f: (("fake_policy_bin", 1, 3),)}
        tails = tail.classify([site(f, 2, "fake_policy_bin", col=10)], tmp_path,
                              local_bindings=bindings)
        assert tails[f] == {tail.LOCAL: 1}

    def test_a_binding_outside_its_extent_does_not_match(self, tmp_path):
        # Same name, but the call sits outside the binding's function —
        # containment fails and the site falls through honestly.
        f = write(tmp_path, "a.py",
                  "def setup(helper):\n"
                  "    pass\n"
                  "helper()\n")
        bindings = {f: (("helper", 1, 2),)}
        tails = tail.classify([site(f, 3, "helper", col=0)], tmp_path,
                              local_bindings=bindings)
        assert tails[f] == {tail.UNCLASSIFIED: 1}

    def test_a_scope_contained_local_outranks_an_import_binding(self, tmp_path):
        # A parameter shadows a module-level import inside its function.
        f = write(tmp_path, "a.py",
                  "from utils import runner\n"
                  "def drive(runner):\n"
                  "    runner()\n")
        tails = tail.classify(
            [site(f, 3, "runner", col=4)], tmp_path,
            import_bindings={f: frozenset({"runner"})},
            local_bindings={f: (("runner", 2, 3),)},
        )
        assert tails[f] == {tail.LOCAL: 1}

    def test_an_attr_call_never_matches_a_local_binding(self, tmp_path):
        # A local named `helper` must not absorb `self.helper()` — the
        # attribute call's receiver is what is untyped, and the class
        # says so.
        f = write(tmp_path, "a.py",
                  "def run(helper):\n"
                  "    self.helper()\n")
        tails = tail.classify([site(f, 2, "helper", col=9)], tmp_path,
                              local_bindings={f: (("helper", 1, 2),)})
        assert tails[f] == {tail.ATTR: 1}

    def test_a_bare_call_of_an_import_bound_name_is_import_binding(self, tmp_path):
        f = write(tmp_path, "a.py",
                  "from sqlalchemy.dialects.postgresql import UUID as PG_UUID\n"
                  "col = PG_UUID(as_uuid=True)\n")
        bindings = {f: frozenset({"PG_UUID"})}
        tails = tail.classify([site(f, 2, "PG_UUID", col=6)], tmp_path,
                              import_bindings=bindings)
        assert tails[f] == {tail.IMPORT_BINDING: 1}

    def test_an_import_binding_outranks_a_builtin_match(self, tmp_path):
        # `from rich import print`: the import is the truer observation.
        f = write(tmp_path, "a.py", "from rich import print\nprint('x')\n")
        bindings = {f: frozenset({"print"})}
        tails = tail.classify([site(f, 2, "print", col=0)], tmp_path,
                              import_bindings=bindings)
        assert tails[f] == {tail.IMPORT_BINDING: 1}

    def test_an_attribute_call_stays_attr_even_when_its_receiver_is_imported(self, tmp_path):
        # `import os` binds `os`; `os.path.join()` is still an attr call —
        # the binding classifies bare calls only.
        f = write(tmp_path, "a.py", "p = os.path.join(a, b)\n")
        bindings = {f: frozenset({"os", "join"})}
        tails = tail.classify([site(f, 1, "join", col=12)], tmp_path,
                              import_bindings=bindings)
        assert tails[f] == {tail.ATTR: 1}

    def test_a_wrapped_chain_call_is_attr_call(self, tmp_path):
        # gofmt mandates the trailing dot, so dagger-style fluent chains
        # put the call opener at the line start; the previous line is the
        # observation (ADR-048).
        f = write(tmp_path, "a.go", "c.Container().\n\tFrom(\"alpine\").\n\tWithExec(nil)\n")
        tails = tail.classify(
            [site(f, 2, "From", col=1), site(f, 3, "WithExec", col=1)], tmp_path
        )
        assert tails[f] == {tail.ATTR: 2}

    def test_a_wrapped_chain_with_a_trailing_comment_still_reads(self, tmp_path):
        f = write(tmp_path, "a.ts", "builder. // fluent\n  build()\n")
        tails = tail.classify([site(f, 2, "build", col=2)], tmp_path)
        assert tails[f] == {tail.ATTR: 1}

    def test_a_comment_ending_in_a_period_is_not_a_chain(self, tmp_path):
        f = write(tmp_path, "a.go", "// see the docs.\nMiddleware()\n")
        tails = tail.classify([site(f, 2, "Middleware", col=0)], tmp_path)
        assert tails[f] == {tail.UNCLASSIFIED: 1}

    def test_python_is_not_read_across_the_wrap(self, tmp_path):
        # Python chains wrap with a *leading* dot; a trailing one is a
        # shape this classifier abstains on rather than reads.
        f = write(tmp_path, "a.py", "(x.\n  refresh())\n")
        tails = tail.classify([site(f, 2, "refresh", col=2)], tmp_path)
        assert tails[f] == {tail.UNCLASSIFIED: 1}

    def test_a_wrapped_path_call_is_path_call(self, tmp_path):
        f = write(tmp_path, "a.rs", "some::module::\n    thing()\n")
        tails = tail.classify([site(f, 2, "thing", col=4)], tmp_path)
        assert tails[f] == {tail.PATH_CALL: 1}

    def test_an_attribute_call_is_attr_call(self, tmp_path):
        f = write(tmp_path, "a.py", "out = capsys.readouterr()\n")
        tails = tail.classify([site(f, 1, "readouterr", col=13)], tmp_path)
        assert tails[f] == {tail.ATTR: 1}

    def test_optional_chaining_is_attr_call(self, tmp_path):
        f = write(tmp_path, "a.ts", "user?.refresh()\n")
        tails = tail.classify([site(f, 1, "refresh", col=6)], tmp_path)
        assert tails[f] == {tail.ATTR: 1}

    def test_a_path_qualified_call_is_path_call(self, tmp_path):
        f = write(tmp_path, "a.rs", "let x = Counter::new();\n")
        tails = tail.classify([site(f, 1, "new", col=17)], tmp_path)
        assert tails[f] == {tail.PATH_CALL: 1}

    def test_a_checker_origin_outranks_text_shape(self, tmp_path):
        # The checker knows setError is declared in this file; the text
        # shape (bare) never gets asked.
        f = write(tmp_path, "a.tsx", "setError(null)\n")
        origins = {(f, 1, "setError"): "local"}
        tails = tail.classify([site(f, 1, "setError", col=0)], tmp_path, origins=origins)
        assert tails[f] == {tail.LOCAL: 1}

    def test_each_checker_origin_maps_to_its_class(self, tmp_path):
        f = write(tmp_path, "a.ts", "a()\nb()\nc()\n")
        origins = {
            (f, 1, "a"): "local",
            (f, 2, "b"): "nested",
            (f, 3, "c"): "external",
        }
        sites = [site(f, n, x, col=0) for n, x in ((1, "a"), (2, "b"), (3, "c"))]
        tails = tail.classify(sites, tmp_path, origins=origins)
        assert tails[f] == {tail.LOCAL: 1, tail.NESTED: 1, tail.EXTERNAL_ORIGIN: 1}

    def test_a_fallback_resolved_site_outranks_everything(self, tmp_path):
        # Lane A produced a (syntactic) edge; the site is unresolved only
        # in the semantic ledger, and the class says exactly that.
        f = write(tmp_path, "a.py", "n = len(items)\n")
        fallback = {(f, 1, "len"): ("a.py", 1)}
        tails = tail.classify([site(f, 1, "len")], tmp_path, fallback=fallback)
        assert tails[f] == {tail.FALLBACK: 1}

    def test_an_unreadable_site_is_unclassified_never_guessed(self, tmp_path):
        missing = "gone.py"  # file absent: no observation, no class
        tails = tail.classify([site(missing, 1, "mystery")], tmp_path)
        assert tails[missing] == {tail.UNCLASSIFIED: 1}

    def test_a_name_absent_from_its_line_is_unclassified(self, tmp_path):
        # A wrapped chain can put the terminal on another line; without
        # the observation the site stays unclassified rather than shaped.
        f = write(tmp_path, "a.py", "something_else()\n")
        tails = tail.classify([site(f, 1, "refresh")], tmp_path)
        assert tails[f] == {tail.UNCLASSIFIED: 1}


class TestRollup:
    def test_rollup_groups_by_language_and_sums_tails(self):
        rows = [
            {"file": "a.py", "sites": 10, "unresolved": 2,
             "tail": {tail.BUILTIN: 2}},
            {"file": "b.py", "sites": 5, "unresolved": 1,
             "tail": {tail.ATTR: 1}},
            {"file": "c.go", "sites": 7, "unresolved": 0},
            {"file": "main.tf", "sites": 1, "unresolved": 1},  # no bucket
        ]
        langs = tail.rollup(rows)
        assert langs["python"]["sites"] == 15
        assert langs["python"]["tail"] == {tail.BUILTIN: 2, tail.ATTR: 1}
        assert langs["go"]["unresolved"] == 0
        assert "hcl" not in langs and None not in langs

    def test_not_modelled_covers_exactly_the_by_design_classes(self):
        assert tail.NOT_MODELLED == {tail.LOCAL, tail.NESTED, tail.BUILTIN, tail.BELOW_FLOOR}


class TestDirectoryRollup:
    ROWS = [
        {"file": "sdk/python/src/client.py", "sites": 10, "unresolved": 4,
         "tail": {tail.ATTR: 3, tail.IMPORT_BINDING: 1}},
        {"file": "sdk/python/src/gen.py", "sites": 5, "unresolved": 1,
         "tail": {tail.ATTR: 1}},
        {"file": "sdk/typescript/src/api.ts", "sites": 8, "unresolved": 2,
         "tail": {tail.EXTERNAL_ORIGIN: 2}},
        {"file": "core/schema/query.go", "sites": 7, "unresolved": 0},
        {"file": "main.go", "sites": 3, "unresolved": 1,
         "tail": {tail.BUILTIN: 1}},
        {"file": "main.tf", "sites": 1, "unresolved": 1},  # no bucket
    ]

    def test_groups_by_depth_two_directory_and_language(self):
        dirs = tail.rollup_directories(self.ROWS)
        py = dirs[("sdk/python", "python")]
        assert py["sites"] == 15 and py["unresolved"] == 5
        assert py["tail"] == {tail.ATTR: 4, tail.IMPORT_BINDING: 1}
        assert ("sdk/typescript", "ts/js") in dirs
        assert dirs[("core/schema", "go")]["unresolved"] == 0

    def test_a_root_level_file_buckets_as_dot(self):
        dirs = tail.rollup_directories(self.ROWS)
        assert dirs[(".", "go")]["sites"] == 3

    def test_unbucketed_languages_are_absent(self):
        dirs = tail.rollup_directories(self.ROWS)
        assert not [k for k in dirs if k[1] is None]

    def test_directory_sums_match_the_language_rollup(self):
        # The two rollups are views of one artifact; their totals must
        # agree per language or one of them is lying.
        langs = tail.rollup(self.ROWS)
        dirs = tail.rollup_directories(self.ROWS)
        for lang, agg in langs.items():
            per_dir = [v for (_, l), v in dirs.items() if l == lang]
            assert sum(v["sites"] for v in per_dir) == agg["sites"]
            assert sum(v["unresolved"] for v in per_dir) == agg["unresolved"]

    def test_depth_one_collapses_the_sdk_split(self):
        dirs = tail.rollup_directories(self.ROWS, depth=1)
        assert ("sdk", "python") in dirs and ("sdk", "ts/js") in dirs
        assert ("sdk/python", "python") not in dirs


class TestArtifact:
    def test_every_unresolved_site_is_classified_and_sums_match(self):
        # The degraded path (lane B off — the suite default): the tail
        # view exists, and per file its counts sum to `unresolved`.
        graph = extract_repo(FIXTURE).graph
        rows = graph["resolution_coverage"]
        assert rows, "fixture produced no coverage rows"
        for row in rows:
            expected = row["unresolved"] + row.get("floored", 0)
            if expected:
                assert sum(row["tail"].values()) == expected, row
            else:
                assert "tail" not in row

    def test_the_fixture_tail_names_its_builtins(self):
        # miniapp's Python calls include builtin-named sites; with no
        # semantic lane the tail must still say so (pinned list, not
        # the running interpreter).
        graph = extract_repo(FIXTURE).graph
        classes = set()
        for row in graph["resolution_coverage"]:
            classes |= set(row.get("tail", {}))
        assert classes <= {
            tail.FALLBACK, tail.LOCAL, tail.NESTED, tail.EXTERNAL_ORIGIN,
            tail.IMPORT_BINDING, tail.BUILTIN, tail.ATTR, tail.PATH_CALL,
            tail.UNCLASSIFIED,
        }


class TestClassesAvailable:
    """C-32's note: the table says what each language *could* report, and
    it must agree with what :func:`classify` can decide."""

    def test_the_table_covers_every_tail_language_and_only_known_classes(self):
        assert set(tail.CLASSES_AVAILABLE) == set(tail._LANG_BY_EXT.values())
        for classes in tail.CLASSES_AVAILABLE.values():
            assert classes <= set(tail.ALL_CLASSES)
            # Every language can fall back, read an attr-call, or abstain.
            assert {tail.FALLBACK, tail.ATTR, tail.UNCLASSIFIED} <= classes

    def test_builtin_name_is_available_exactly_where_a_list_is_pinned(self):
        with_list = {l for l, c in tail.CLASSES_AVAILABLE.items() if tail.BUILTIN in c}
        assert with_list == set(tail._BUILTINS)

    def test_checker_origin_classes_are_ts_only(self):
        for lang, classes in tail.CLASSES_AVAILABLE.items():
            has = {tail.NESTED, tail.EXTERNAL_ORIGIN} & classes
            assert bool(has) == (lang == "ts/js"), lang

    def test_the_fixture_tail_stays_inside_its_language_row(self):
        out = extract_repo(FIXTURE)
        rows = out.graph["resolution_coverage"]
        available = out.graph["tail_classes_available"]
        assert "python" in available
        for row in rows:
            lang = tail.language_of(row["file"])
            assert set(row.get("tail", {})) <= set(available[lang]), row

    def test_only_present_languages_are_listed_in_decision_order(self):
        rows = [{"file": "a/x.rs"}, {"file": "b/y.py"}, {"file": "c/z.tf"}]
        got = tail.classes_available(rows)
        assert list(got) == ["python", "rust"]
        assert got["rust"] == [tail.FALLBACK, tail.ATTR, tail.PATH_CALL, tail.UNCLASSIFIED, tail.BELOW_FLOOR]


class TestCaptureLineNamesMissingClasses:
    def test_the_summary_names_what_a_lane_cannot_report(self, capsys):
        from hobbes import cli

        rows = [{"file": "a.go", "sites": 4, "unresolved": 1,
                 "tail": {"attr-call": 1}}]
        cli._print_tail_view(rows, tail.classes_available(rows))
        out = capsys.readouterr().out
        assert ("classes this lane cannot report: nested-decl, external-origin, "
                "import-binding, path-call (C-32)") in out

    def test_an_older_artifact_without_the_field_prints_no_note(self, capsys):
        from hobbes import cli

        rows = [{"file": "a.go", "sites": 4, "unresolved": 1,
                 "tail": {"attr-call": 1}}]
        cli._print_tail_view(rows)
        assert "cannot report" not in capsys.readouterr().out

