"""Tests for hobbes.extract.fixtures — pytest's fixture lookup as syntax.

ADR-137: the order is the rule (the class chain, the file, the conftest
chain upward), an injection is never a ``calls`` edge, and a parameter the
order does not end on is counted rather than guessed at.
"""

import json

from hobbes.extract import extract_repo
from hobbes.extract.discover import discover_modules
from hobbes.extract.fixtures import injections
from hobbes.extract.pysource import parse_source


def resolve(tmp_path, files: dict):
    """Write a small tree and run the lookup over it."""
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    modules = discover_modules(tmp_path)
    parsed = {m.id: parse_source((tmp_path / m.path).read_bytes()) for m in modules}
    return injections(modules, parsed)


def pairs(drawn):
    return [(i["from"], i["to"], i["name"]) for i in drawn]


def sightings(drawn):
    """The pairs with what asked for them and where it is written."""
    return [(i["from"], i["to"], i["name"], i["via"], i["line"]) for i in drawn]


class TestScopeOrder:
    def test_the_files_fixture_wins_over_the_conftests(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "conftest.py": "import pytest\n\n\n@pytest.fixture\ndef repo():\n    return 1\n",
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef repo():\n    return 2\n\n\n"
                    "def test_one(repo):\n    pass\n"
                ),
            },
        )
        assert pairs(drawn) == [("test_x.test_one", "test_x.repo", "repo")]

    def test_the_nearer_conftest_wins_over_the_farther(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "tests/__init__.py": "",
                "conftest.py": "import pytest\n\n\n@pytest.fixture\ndef repo():\n    return 1\n",
                "tests/conftest.py": "import pytest\n\n\n@pytest.fixture\ndef repo():\n    return 2\n",
                "tests/test_x.py": "def test_one(repo):\n    pass\n",
            },
        )
        assert pairs(drawn) == [
            ("tests.test_x.test_one", "tests.conftest.repo", "repo")
        ]

    def test_a_conftest_two_directories_up_is_found(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "tests/__init__.py": "",
                "tests/unit/__init__.py": "",
                "conftest.py": "import pytest\n\n\n@pytest.fixture\ndef repo():\n    return 1\n",
                "tests/unit/test_x.py": "def test_one(repo):\n    pass\n",
            },
        )
        assert pairs(drawn) == [("tests.unit.test_x.test_one", "conftest.repo", "repo")]

    def test_a_conftest_in_a_sibling_directory_is_not(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "tests/__init__.py": "",
                "other/__init__.py": "",
                "other/conftest.py": "import pytest\n\n\n@pytest.fixture\ndef repo():\n    return 1\n",
                "tests/test_x.py": "def test_one(repo):\n    pass\n",
            },
        )
        assert drawn == []
        assert counts["abstained"]["not-in-repo"] == 1


class TestClassScope:
    SOURCE = (
        "import pytest\n\n\n"
        "class TestOne:\n"
        "    @pytest.fixture\n"
        "    def repo(self):\n"
        "        return 1\n\n"
        "    def test_inside(self, repo):\n"
        "        pass\n\n\n"
        "def test_outside(repo):\n"
        "    pass\n"
    )

    def test_a_classs_own_fixture_wins_inside_it(self, tmp_path):
        drawn, _ = resolve(tmp_path, {"test_x.py": self.SOURCE})
        assert pairs(drawn) == [
            ("test_x.TestOne.test_inside", "test_x.TestOne.repo", "repo")
        ]

    def test_it_is_invisible_outside_the_class(self, tmp_path):
        _, counts = resolve(tmp_path, {"test_x.py": self.SOURCE})
        # `test_outside` sees no `repo` at all: file and conftest have none.
        assert counts["abstained"]["not-in-repo"] == 1


class TestABaseClass:
    """A base class's fixture is inherited and outranks the file's and the
    conftest's. The walk does not resolve bases, so an edge found past the
    class chain, from inside a class that names one, is left undrawn
    (the developer's addition to ADR-137's unit)."""

    SOURCE = (
        "import pytest\n\n\n"
        "@pytest.fixture\n"
        "def repo():\n"
        "    return 0\n\n\n"
        "class Base:\n"
        "    @pytest.fixture\n"
        "    def repo(self):\n"
        "        return 1\n\n\n"
        "class TestChild(Base):\n"
        "    @pytest.fixture\n"
        "    def own(self):\n"
        "        return 2\n\n"
        "    def test_inherited(self, repo, tmp_path):\n"
        "        pass\n\n"
        "    def test_own(self, own):\n"
        "        pass\n\n\n"
        "class TestPlain:\n"
        "    def test_file(self, repo):\n"
        "        pass\n\n\n"
        "class TestMeta(metaclass=type):\n"
        "    def test_file(self, repo):\n"
        "        pass\n"
    )

    def test_a_name_found_past_an_inheriting_class_is_not_drawn(self, tmp_path):
        drawn, counts = resolve(tmp_path, {"test_x.py": self.SOURCE})
        assert ("test_x.TestChild.test_inherited", "test_x.repo", "repo") not in pairs(drawn)
        assert counts["abstained"]["base-class"] == 1
        # `tmp_path` names no repo fixture, and is still counted as that.
        assert counts["abstained"]["not-in-repo"] == 1

    def test_the_classs_own_fixture_is_still_drawn(self, tmp_path):
        drawn, _ = resolve(tmp_path, {"test_x.py": self.SOURCE})
        assert ("test_x.TestChild.test_own", "test_x.TestChild.own", "own") in pairs(drawn)

    def test_a_class_with_no_base_or_only_a_metaclass_reads_the_file(self, tmp_path):
        drawn, _ = resolve(tmp_path, {"test_x.py": self.SOURCE})
        assert ("test_x.TestPlain.test_file", "test_x.repo", "repo") in pairs(drawn)
        assert ("test_x.TestMeta.test_file", "test_x.repo", "repo") in pairs(drawn)


class TestNameAlias:
    SOURCE = (
        "import pytest\n\n\n"
        '@pytest.fixture(name="alias")\n'
        "def _repo():\n"
        "    return 1\n\n\n"
        "def test_by_alias(alias):\n"
        "    pass\n\n\n"
        "def test_by_function_name(_repo):\n"
        "    pass\n"
    )

    def test_the_alias_is_the_fixtures_name(self, tmp_path):
        drawn, _ = resolve(tmp_path, {"test_x.py": self.SOURCE})
        assert pairs(drawn) == [("test_x.test_by_alias", "test_x._repo", "alias")]

    def test_the_function_name_then_resolves_to_nothing(self, tmp_path):
        _, counts = resolve(tmp_path, {"test_x.py": self.SOURCE})
        assert counts["abstained"]["not-in-repo"] == 1


class TestImportedFixtures:
    def test_a_fixture_imported_by_name_resolves_to_its_definition(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "tests/__init__.py": "",
                "tests/test_a.py": (
                    "import pytest\n\n\n@pytest.fixture\ndef repo():\n    return 1\n"
                ),
                "tests/test_b.py": (
                    "from tests.test_a import repo\n\n\n"
                    "def test_one(repo):\n    pass\n"
                ),
            },
        )
        assert ("tests.test_b.test_one", "tests.test_a.repo", "repo") in pairs(drawn)

    def test_import_as_binds_the_new_name(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "tests/__init__.py": "",
                "tests/test_a.py": (
                    "import pytest\n\n\n@pytest.fixture\ndef repo():\n    return 1\n"
                ),
                "tests/test_b.py": (
                    "from tests.test_a import repo as tree\n\n\n"
                    "def test_one(tree):\n    pass\n"
                ),
            },
        )
        assert ("tests.test_b.test_one", "tests.test_a.repo", "tree") in pairs(drawn)

    def test_a_conftests_imported_fixture_counts_as_that_conftests(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "tests/__init__.py": "",
                "tests/unit/__init__.py": "",
                "tests/test_a.py": (
                    "import pytest\n\n\n@pytest.fixture\ndef repo():\n    return 1\n"
                ),
                "tests/conftest.py": "from tests.test_a import repo\n",
                "tests/unit/test_b.py": "def test_one(repo):\n    pass\n",
            },
        )
        assert ("tests.unit.test_b.test_one", "tests.test_a.repo", "repo") in pairs(
            drawn
        )


class TestFixtureRequestingFixture:
    def test_a_fixture_requesting_a_fixture_is_an_injection(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef root():\n    return 1\n\n\n"
                    "@pytest.fixture\ndef repo(root):\n    return root\n\n\n"
                    "def test_one(repo):\n    pass\n"
                )
            },
        )
        assert pairs(drawn) == [
            ("test_x.repo", "test_x.root", "root"),
            ("test_x.test_one", "test_x.repo", "repo"),
        ]

    def test_an_override_resolves_outward_not_to_itself(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "conftest.py": "import pytest\n\n\n@pytest.fixture\ndef repo():\n    return 1\n",
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef repo(repo):\n    return repo\n\n\n"
                    "def test_one(repo):\n    pass\n"
                ),
            },
        )
        assert pairs(drawn) == [
            ("test_x.repo", "conftest.repo", "repo"),
            ("test_x.test_one", "test_x.repo", "repo"),
        ]


class TestDecoratorSpellings:
    def test_bare_fixture_yield_fixture_and_a_plugins_are_all_fixtures(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\nimport pytest_asyncio\n"
                    "from pytest import fixture\n\n\n"
                    "@fixture\ndef bare():\n    return 1\n\n\n"
                    "@pytest.yield_fixture\ndef old():\n    yield 1\n\n\n"
                    "@pytest_asyncio.fixture\ndef aio():\n    return 1\n\n\n"
                    "def test_one(bare, old, aio):\n    pass\n"
                )
            },
        )
        assert [i["to"] for i in drawn] == ["test_x.aio", "test_x.bare", "test_x.old"]


class TestAbstentions:
    def test_a_builtin_fixture_is_not_in_the_repo(self, tmp_path):
        drawn, counts = resolve(
            tmp_path, {"test_x.py": "def test_one(tmp_path, monkeypatch):\n    pass\n"}
        )
        assert drawn == []
        assert counts["abstained"]["not-in-repo"] == 2

    def test_a_name_defined_twice_in_one_file_draws_nothing(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef repo():\n    return 1\n\n\n"
                    "@pytest.fixture\ndef repo():\n    return 2\n\n\n"
                    "def test_one(repo):\n    pass\n"
                )
            },
        )
        # The two definitions share one qualname, so the symbol layer keeps
        # only the first: there is no id an injection could honestly name.
        assert drawn == []
        assert counts["abstained"]["two-definitions"] == 1

    def test_a_parametrized_name_is_not_looked_up(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef value():\n    return 1\n\n\n"
                    '@pytest.mark.parametrize("value", [1, 2])\n'
                    "def test_one(value):\n    pass\n"
                )
            },
        )
        # A fixture of that name exists; the mark fills the parameter, and
        # the mark is not an abstention either — it is not a lookup.
        assert drawn == []
        assert counts["abstained"] == {
            "not-in-repo": 0,
            "two-definitions": 0,
            "parametrize-unread": 0,
            "base-class": 0,
        }

    def test_an_unreadable_parametrize_abstains_on_every_parameter(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "conftest.py": "import pytest\n\n\n@pytest.fixture\ndef repo():\n    return 1\n",
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.mark.parametrize(CASES, [1])\n"
                    "def test_one(repo, case):\n    pass\n"
                ),
            },
        )
        assert drawn == []
        assert counts["abstained"]["parametrize-unread"] == 2


class TestWhatIsNotARequester:
    def test_a_plain_helper_draws_nothing(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef repo():\n    return 1\n\n\n"
                    "def helper(repo):\n    return repo\n"
                )
            },
        )
        # Neither a test nor a fixture: pytest injects nothing into it.
        assert drawn == []
        assert counts["abstained"]["not-in-repo"] == 0

    def test_self_is_never_looked_up(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "class TestOne:\n    def test_a(self):\n        pass\n"
                )
            },
        )
        # Nothing was defined and nothing was asked: not an abstention, no
        # block at all.
        assert (drawn, counts) == ([], {})

    def test_a_usefixtures_mark_on_a_fixture_draws_nothing(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef repo():\n    return 1\n\n\n"
                    '@pytest.mark.usefixtures("repo")\n'
                    "@pytest.fixture\ndef other():\n    return 2\n"
                )
            },
        )
        # pytest ignores a mark on a fixture; the mark is still counted.
        assert drawn == []
        assert counts["usefixtures"] == 1


class TestUsefixturesMarks:
    """ADR-139: a mark's string names a fixture exactly as a parameter
    does, and is looked up by the same order. The evidence is the mark."""

    def test_a_mark_on_the_test_draws_the_name_it_holds(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef repo():\n    return 1\n\n\n"
                    '@pytest.mark.usefixtures("repo")\n'
                    "def test_one():\n    pass\n"
                )
            },
        )
        assert sightings(drawn) == [
            ("test_x.test_one", "test_x.repo", "repo", "usefixtures", 9)
        ]

    def test_two_names_in_one_mark_draw_two(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef a():\n    return 1\n\n\n"
                    "@pytest.fixture\ndef b():\n    return 2\n\n\n"
                    '@pytest.mark.usefixtures("a", "b")\n'
                    "def test_one():\n    pass\n"
                )
            },
        )
        assert pairs(drawn) == [
            ("test_x.test_one", "test_x.a", "a"),
            ("test_x.test_one", "test_x.b", "b"),
        ]

    def test_a_mark_on_the_class_reaches_every_test_method(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef repo():\n    return 1\n\n\n"
                    '@pytest.mark.usefixtures("repo")\n'
                    "class TestOne:\n"
                    "    def test_a(self):\n        pass\n\n"
                    "    def test_b(self):\n        pass\n"
                )
            },
        )
        # Both methods, both evidenced at the class's mark.
        assert sightings(drawn) == [
            ("test_x.TestOne.test_a", "test_x.repo", "repo", "usefixtures", 9),
            ("test_x.TestOne.test_b", "test_x.repo", "repo", "usefixtures", 9),
        ]

    def test_the_name_resolves_in_pytests_order(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "conftest.py": "import pytest\n\n\n@pytest.fixture\ndef repo():\n    return 1\n",
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef repo():\n    return 2\n\n\n"
                    '@pytest.mark.usefixtures("repo")\n'
                    "def test_one():\n    pass\n"
                ),
            },
        )
        assert pairs(drawn) == [("test_x.test_one", "test_x.repo", "repo")]

    def test_an_unknown_name_is_not_in_the_repo(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef repo():\n    return 1\n\n\n"
                    '@pytest.mark.usefixtures("plugins_own")\n'
                    "def test_one():\n    pass\n"
                )
            },
        )
        assert drawn == []
        assert counts["abstained"]["not-in-repo"] == 1

    def test_a_name_defined_twice_abstains(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef repo():\n    return 1\n\n\n"
                    "@pytest.fixture\ndef repo():\n    return 2\n\n\n"
                    '@pytest.mark.usefixtures("repo")\n'
                    "def test_one():\n    pass\n"
                )
            },
        )
        assert drawn == []
        assert counts["abstained"]["two-definitions"] == 1


class TestAutouse:
    """ADR-139: an ``autouse=True`` fixture is added to every test in its
    scope, and the name is then resolved like any other. Nothing on the
    test names it, so the evidence is the test's own line."""

    def test_a_conftests_reaches_its_directory_and_below_only(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "tests/__init__.py": "",
                "tests/unit/__init__.py": "",
                "other/__init__.py": "",
                "tests/conftest.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture(autouse=True)\ndef setup():\n    return 1\n"
                ),
                "tests/test_a.py": "def test_one():\n    pass\n",
                "tests/unit/test_b.py": "def test_two():\n    pass\n",
                "other/test_c.py": "def test_three():\n    pass\n",
            },
        )
        assert sightings(drawn) == [
            ("tests.test_a.test_one", "tests.conftest.setup", "setup", "autouse", 1),
            (
                "tests.unit.test_b.test_two",
                "tests.conftest.setup",
                "setup",
                "autouse",
                1,
            ),
        ]

    def test_one_at_the_top_of_a_file_is_that_files_only(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture(autouse=True)\ndef setup():\n    return 1\n\n\n"
                    "def test_one():\n    pass\n"
                ),
                "test_y.py": "def test_two():\n    pass\n",
            },
        )
        assert sightings(drawn) == [
            ("test_x.test_one", "test_x.setup", "setup", "autouse", 9)
        ]

    def test_one_in_a_class_is_that_classs_only(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\n\n\n"
                    "class TestOne:\n"
                    "    @pytest.fixture(autouse=True)\n"
                    "    def setup(self):\n        return 1\n\n"
                    "    def test_inside(self):\n        pass\n\n\n"
                    "class TestTwo:\n"
                    "    def test_outside(self):\n        pass\n"
                )
            },
        )
        assert pairs(drawn) == [
            ("test_x.TestOne.test_inside", "test_x.TestOne.setup", "setup")
        ]

    def test_a_nearer_non_autouse_definition_of_the_name_wins(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "conftest.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture(autouse=True)\ndef setup():\n    return 1\n"
                ),
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef setup():\n    return 2\n\n\n"
                    "def test_one():\n    pass\n"
                ),
            },
        )
        # pytest adds the name, then resolves it in the ordinary order: the
        # file's override is what runs.
        assert pairs(drawn) == [("test_x.test_one", "test_x.setup", "setup")]

    def test_a_test_that_names_it_has_one_injection_by_parameter(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "conftest.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture(autouse=True)\ndef setup():\n    return 1\n"
                ),
                "test_x.py": "def test_one(setup):\n    pass\n",
            },
        )
        assert sightings(drawn) == [
            ("test_x.test_one", "conftest.setup", "setup", "parameter", 1)
        ]
        assert counts["via"] == {"parameter": 1, "usefixtures": 0, "autouse": 0}

    def test_autouse_false_injects_nothing(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "conftest.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture(autouse=False)\ndef setup():\n    return 1\n"
                ),
                "test_x.py": "def test_one():\n    pass\n",
            },
        )
        assert drawn == []
        assert counts["unread"]["autouse-value"] == 0

    def test_a_non_literal_autouse_is_counted_and_injects_nothing(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "conftest.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture(autouse=FLAG)\ndef setup():\n    return 1\n"
                ),
                "test_x.py": "def test_one():\n    pass\n",
            },
        )
        assert drawn == []
        assert counts["unread"]["autouse-value"] == 1

    def test_a_fixture_definition_is_not_given_the_autouse_name(self, tmp_path):
        drawn, _ = resolve(
            tmp_path,
            {
                "conftest.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture(autouse=True)\ndef setup():\n    return 1\n"
                ),
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture\ndef repo():\n    return 2\n\n\n"
                    "def test_one(repo):\n    pass\n"
                ),
            },
        )
        # The fixture requests through its parameters only; the test is the
        # one pytest adds the autouse name to.
        assert pairs(drawn) == [
            ("test_x.test_one", "conftest.setup", "setup"),
            ("test_x.test_one", "test_x.repo", "repo"),
        ]

    def test_an_unreadable_parametrize_abstains_on_the_autouse_name_too(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "conftest.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture(autouse=True)\ndef setup():\n    return 1\n"
                ),
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.mark.parametrize(CASES, [1])\n"
                    "def test_one(case):\n    pass\n"
                ),
            },
        )
        assert drawn == []
        assert counts["abstained"]["parametrize-unread"] == 2

    def test_a_class_that_names_a_base_abstains_on_it(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\n\n\n"
                    "@pytest.fixture(autouse=True)\ndef setup():\n    return 1\n\n\n"
                    "class Base:\n    pass\n\n\n"
                    "class TestChild(Base):\n"
                    "    def test_one(self):\n        pass\n"
                )
            },
        )
        # A base class may define `setup` itself, and its definition would
        # win over the file's.
        assert drawn == []
        assert counts["abstained"]["base-class"] == 1


class TestViaCounts:
    SOURCE = {
        "conftest.py": (
            "import pytest\n\n\n"
            "@pytest.fixture(autouse=True)\ndef setup():\n    return 1\n\n\n"
            "@pytest.fixture\ndef repo():\n    return 2\n"
        ),
        "test_x.py": (
            "import pytest\n\n\n"
            '@pytest.mark.usefixtures("repo")\n'
            "def test_one():\n    pass\n\n\n"
            "def test_two(repo):\n    pass\n"
        ),
    }

    def test_the_vias_sum_to_the_drawn(self, tmp_path):
        drawn, counts = resolve(tmp_path, self.SOURCE)
        assert counts["via"] == {"parameter": 1, "usefixtures": 1, "autouse": 2}
        assert sum(counts["via"].values()) == counts["drawn"] == len(drawn)

    def test_the_autouse_definitions_are_counted(self, tmp_path):
        _, counts = resolve(tmp_path, self.SOURCE)
        assert counts["autouse_fixtures"] == 1

    def test_a_module_level_pytestmark_is_counted_and_draws_nothing(self, tmp_path):
        drawn, counts = resolve(
            tmp_path,
            {
                "test_x.py": (
                    "import pytest\n\n\n"
                    'pytestmark = pytest.mark.usefixtures("repo")\n\n\n'
                    "@pytest.fixture\ndef repo():\n    return 1\n\n\n"
                    "def test_one():\n    pass\n"
                )
            },
        )
        assert drawn == []
        assert counts["unread"]["pytestmark"] == 1


class TestCountsBlock:
    def test_the_block_is_empty_where_nothing_was_asked(self, tmp_path):
        drawn, counts = resolve(tmp_path, {"lib.py": "def run():\n    return 1\n"})
        assert (drawn, counts) == ([], {})

    def test_a_lone_fixture_definition_is_still_something_to_say(self, tmp_path):
        _, counts = resolve(
            tmp_path,
            {"conftest.py": "import pytest\n\n\n@pytest.fixture\ndef repo():\n    return 1\n"},
        )
        assert counts["drawn"] == 0 and counts["fixtures"] == 0


class TestThroughTheIngest:
    """The edge as an ingest writes it (ADR-137): a ``uses`` edge at the
    parameter's line, no ``calls`` edge, and an artifact that does not move
    between two runs."""

    SOURCE = {
        "tests/__init__.py": "",
        "lib.py": "def build():\n    return 1\n",
        "conftest.py": (
            "import pytest\n\n"
            "from lib import build\n\n\n"
            "@pytest.fixture\n"
            "def repo():\n"
            "    return build()\n"
        ),
        "tests/test_x.py": "def test_one(repo):\n    pass\n",
    }

    @staticmethod
    def ingest(tmp_path, files):
        for name, text in files.items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return extract_repo(tmp_path)

    def test_the_injection_is_a_uses_edge_and_no_call(self, tmp_path):
        extraction = self.ingest(tmp_path, self.SOURCE)
        edges = [
            e
            for e in extraction.graph["symbol_edges"]
            if e["from"] == "tests.test_x.test_one"
        ]
        assert edges == [
            {
                "from": "tests.test_x.test_one",
                "to": "conftest.repo",
                "type": "uses",
                "tier": "syntactic",
                "evidence": [
                    {
                        "path": "tests/test_x.py",
                        "line": 1,
                        "via": "parameter",
                        "lane": "tree-sitter",
                    }
                ],
            }
        ]
        assert extraction.graph["fixtures"]["drawn"] == 1

    def test_the_edge_list_keeps_the_projections_order(self, tmp_path):
        extraction = self.ingest(tmp_path, self.SOURCE)
        edges = extraction.graph["symbol_edges"]
        key = [
            (e["from"], e["to"], e["type"], e["tier"], e["evidence"][0]["lane"])
            for e in edges
        ]
        assert key == sorted(key)

    def test_the_test_reaches_the_module_only_a_fixture_got_it_to(self, tmp_path):
        extraction = self.ingest(tmp_path, self.SOURCE)
        (record,) = [
            t for t in extraction.tests["tests"] if t["id"].endswith("::test_one")
        ]
        assert record["reaches"] == ["conftest.repo", "lib.build"]
        assert record["reaches_modules"] == ["conftest", "lib"]
        assert record["through_fixtures"] == ["conftest", "lib"]

    def test_a_second_ingest_is_identical(self, tmp_path):
        first = self.ingest(tmp_path, self.SOURCE)
        second = extract_repo(tmp_path)
        assert json.dumps(first.graph, sort_keys=True) == json.dumps(
            second.graph, sort_keys=True
        )

    def test_a_repo_with_no_python_tests_has_no_block(self, tmp_path):
        extraction = self.ingest(tmp_path, {"lib.py": "def build():\n    return 1\n"})
        assert "fixtures" not in extraction.graph


class TestTheOtherViasThroughTheIngest:
    """The same edge for the two requests a test's signature does not write
    (ADR-139): every evidence row says which one was seen, and the autouse
    fixture's own reach is answered for on its own."""

    SOURCE = {
        "tests/__init__.py": "",
        "lib.py": "def build():\n    return 1\n",
        "staging.py": "def cache():\n    return 2\n",
        "conftest.py": (
            "import pytest\n\n"
            "from lib import build\n"
            "from staging import cache\n\n\n"
            "@pytest.fixture(autouse=True)\n"
            "def setup():\n"
            "    return cache()\n\n\n"
            "@pytest.fixture\n"
            "def repo():\n"
            "    return build()\n"
        ),
        "tests/test_x.py": (
            "import pytest\n\n\n"
            '@pytest.mark.usefixtures("repo")\n'
            "def test_one():\n    pass\n"
        ),
    }

    def ingest(self, tmp_path):
        return TestThroughTheIngest.ingest(tmp_path, self.SOURCE)

    def test_the_rows_say_which_request_was_seen(self, tmp_path):
        extraction = self.ingest(tmp_path)
        rows = {
            edge["to"]: edge["evidence"]
            for edge in extraction.graph["symbol_edges"]
            if edge["from"] == "tests.test_x.test_one"
        }
        assert rows == {
            # The mark's line for the one it names, the test's own for the
            # one nothing on it names.
            "conftest.repo": [
                {
                    "path": "tests/test_x.py",
                    "line": 4,
                    "via": "usefixtures",
                    "lane": "tree-sitter",
                }
            ],
            "conftest.setup": [
                {
                    "path": "tests/test_x.py",
                    "line": 5,
                    "via": "autouse",
                    "lane": "tree-sitter",
                }
            ],
        }

    def test_the_autouse_reach_is_kept_out_of_through_fixtures(self, tmp_path):
        extraction = self.ingest(tmp_path)
        (record,) = extraction.tests["tests"]
        assert record["reaches_modules"] == ["conftest", "lib", "staging"]
        assert record["through_fixtures"] == ["conftest", "lib"]
        assert record["through_autouse"] == {"staging": ["conftest.setup"]}

    def test_a_second_ingest_is_identical(self, tmp_path):
        first = self.ingest(tmp_path)
        second = extract_repo(tmp_path)
        assert json.dumps(first.graph, sort_keys=True) == json.dumps(
            second.graph, sort_keys=True
        )
