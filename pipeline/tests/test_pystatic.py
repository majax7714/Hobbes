"""Tests for hobbes.extract.pystatic — what Pyright reads as never run (ADR-154).

Each case parses a small source with :func:`parse_source`, as the ingest
does, and evaluates what the walk collected under Linux at Python 3.12
(or the version a case names). The forms and contexts are exactly
ADR-154's; a case for a form it does not list asserts the test is *not*
static.
"""

import pytest

from hobbes.extract import pystatic
from hobbes.extract.pysource import parse_source

AT_312 = pystatic.Reading(version=(3, 12))
UNVERSIONED = pystatic.Reading(version=None)

PRELUDE = "import os\nimport sys\nimport typing as t\n"


def reads(test, prelude=PRELUDE, reading=AT_312):
    """What ``if <test>:`` reads as: True, False, or None (not static)."""
    source = f"{prelude}if {test}:\n    x = 1\n"
    facts = parse_source(source.encode())
    line = source.count("\n") - 1
    found = [t for t in facts.static_tests if t.line == line]
    if not found:
        return None
    return pystatic.evaluate(found[0].condition, found[0].line, facts, reading)


def regions(source, reading=AT_312):
    return pystatic.read_file(parse_source(source.encode()), reading).regions


def twins(source, reading=AT_312):
    read = pystatic.read_file(parse_source(source.encode()), reading)
    return {q: (live.line, tuple(d.line for d in dead)) for q, (live, dead) in read.twins.items()}


class TestEachForm:
    @pytest.mark.parametrize(
        "test, value",
        [
            ('sys.platform == "linux"', True),
            ('sys.platform == "darwin"', False),
            ('sys.platform != "win32"', True),
            ('sys.platform == "lin" "ux"', True),
            ('os.name == "nt"', False),
            ('os.name != "nt"', True),
            ("sys.version_info >= (3, 11)", True),
            ("sys.version_info < (3, 8)", False),
            ("sys.version_info >= (3,)", True),
            # two or more elements: the first two are read, the rest ignored
            ("sys.version_info >= (3, 11, 1)", True),
            ('sys.version_info >= (3, 13, 0, "final")', False),
            ("sys.version_info[0] == 3", True),
            ("sys.version_info[0] < 3", False),
            ("TYPE_CHECKING", True),
            ("t.TYPE_CHECKING", True),
            ("True", True),
            ("False", False),
            ('(sys.platform == "win32")', False),
        ],
    )
    def test_reads_true_or_false(self, test, value):
        assert reads(test) is value

    @pytest.mark.parametrize(
        "test",
        [
            'sys.platform.startswith("win")',
            '"win" in sys.platform',
            "sys.version_info >= (3.1,)",
            'sys.version_info >= (3, "11")',
            "x.TYPE_CHECKING",
            'sys.platform == f"win32"',
            "flag",
        ],
    )
    def test_is_not_static(self, test):
        assert reads(test) is None

    def test_from_sys_import_platform_is_not_read(self):
        assert reads('platform == "darwin"', prelude="from sys import platform\n") is None

    def test_a_sys_alias_imported_below_the_test_is_not_read(self):
        source = 'if sys.platform == "darwin":\n    x = 1\nimport sys\n'
        facts = parse_source(source.encode())
        [test] = facts.static_tests
        assert pystatic.evaluate(test.condition, test.line, facts, AT_312) is None
        assert regions(source) == ()

    def test_an_aliased_sys_is_read(self):
        assert reads('_sys.platform == "darwin"', prelude="import sys as _sys\n") is False

    def test_a_name_no_sys_import_binds_is_not_read(self):
        assert reads('os.platform == "darwin"', prelude="import os\n") is None

    @pytest.mark.parametrize(
        "test",
        ["sys.version_info >= (3, 11)", "sys.version_info < (3,)", "sys.version_info[0] == 3"],
    )
    def test_every_version_form_is_not_static_without_a_version(self, test):
        assert reads(test, reading=UNVERSIONED) is None

    def test_the_platform_still_reads_without_a_version(self):
        assert reads('sys.platform == "win32"', reading=UNVERSIONED) is False


class TestCodeFlow:
    def test_one_false_and_operand_kills_the_body_wherever_it_sits(self):
        assert regions(PRELUDE + 'if os.name == "nt" and flag:\n    x = 1\n') == ((5, 5),)
        assert regions(PRELUDE + 'if flag and sys.platform == "darwin":\n    x = 1\n') == ((5, 5),)

    def test_one_true_or_operand_kills_the_else(self):
        assert regions(
            PRELUDE + "if flag or TYPE_CHECKING:\n    x = 1\nelse:\n    y = 2\n"
        ) == ((6, 7),)

    def test_not_inverts(self):
        assert regions(PRELUDE + "if not TYPE_CHECKING:\n    x = 1\n") == ((5, 5),)

    def test_an_undecided_and_or_or_is_not_static(self):
        assert reads('flag and sys.platform == "linux"') is None
        assert reads('flag or sys.platform == "darwin"') is None
        assert reads('sys.platform == "linux" and TYPE_CHECKING') is True


class TestEachContext:
    def test_a_three_arm_platform_chain_keeps_only_the_else(self):
        source = (
            "import sys\n"  # 1
            'if sys.platform == "darwin":\n'  # 2
            "    a = 1\n"  # 3
            'elif sys.platform == "win32":\n'  # 4
            "    b = 2\n"  # 5
            "else:\n"  # 6
            "    c = 3\n"  # 7
        )
        assert regions(source) == ((3, 3), (5, 5))

    def test_a_while_false_body(self):
        assert regions("while False:\n    x = 1\n    y = 2\n") == ((2, 3),)

    def test_a_module_level_assert_kills_the_rest_of_the_module(self):
        source = (
            "import sys\n"  # 1
            'assert sys.platform == "win32"\n'  # 2
            "def f():\n"  # 3
            "    return g()\n"  # 4
            "x = f()\n"  # 5
        )
        assert regions(source) == ((3, 5),)

    def test_an_assert_in_a_function_kills_only_the_rest_of_its_body(self):
        source = (
            "import sys\n"  # 1
            "def f():\n"  # 2
            '    assert sys.platform == "win32"\n'  # 3
            "    return g()\n"  # 4
            "x = f()\n"  # 5
        )
        assert regions(source) == ((4, 4),)

    def test_an_else_that_raises_kills_the_rest_of_the_module(self):
        # rich's `_win32_console.py` (C-173's widening): Pyright reads
        # everything after the `if` as never run on Linux.
        source = (
            "import sys\n"  # 1
            'if sys.platform == "win32":\n'  # 2
            "    windll = 1\n"  # 3
            "else:\n"  # 4
            '    raise ImportError("only on Windows")\n'  # 5
            "\n"  # 6
            "def f():\n"  # 7
            "    return g()\n"  # 8
        )
        assert regions(source) == ((3, 3), (7, 8))

    def test_an_if_that_raises_kills_the_rest_of_its_block_on_true(self):
        # rich's `_windows.py` shape, inside a `try`, with the test negated.
        source = (
            "import sys\n"  # 1
            "try:\n"  # 2
            '    if sys.platform != "win32":\n'  # 3
            "        raise ImportError\n"  # 4
            "    import ctypes\n"  # 5
            "except ImportError:\n"  # 6
            "    ctypes = None\n"  # 7
        )
        assert regions(source) == ((5, 5),)

    def test_a_branch_that_does_not_end_in_raise_kills_nothing_after(self):
        source = (
            "import sys\n"  # 1
            'if sys.platform == "win32":\n'  # 2
            "    x = 1\n"  # 3
            "else:\n"  # 4
            "    if y:\n"  # 5
            "        raise ImportError\n"  # 6
            "    z = 2\n"  # 7
            "w = 3\n"  # 8
        )
        assert regions(source) == ((3, 3),)

    def test_an_else_after_an_elif_is_not_one_tests_reading(self):
        # The `else` runs only when both tests read False; one test's
        # reading cannot say so, so nothing after the `if` is killed.
        source = (
            "import os\n"  # 1
            "import sys\n"  # 2
            'if sys.platform == "win32":\n'  # 3
            "    x = 1\n"  # 4
            'elif os.name == "posix":\n'  # 5
            "    x = 2\n"  # 6
            "else:\n"  # 7
            "    raise ImportError\n"  # 8
            "y = 3\n"  # 9
        )
        assert regions(source) == ((4, 4), (7, 8))

    def test_a_raise_on_the_live_reading_kills_nothing_after(self):
        source = (
            "import sys\n"  # 1
            'if sys.platform == "linux":\n'  # 2
            "    x = 1\n"  # 3
            "else:\n"  # 4
            "    raise ImportError\n"  # 5
            "y = 3\n"  # 6
        )
        assert regions(source) == ((4, 5),)

    def test_a_deciding_operand_kills_the_operand_on_its_own_line(self):
        source = (
            "import os\n"  # 1
            'x = (os.name == "nt"\n'  # 2
            "     and f())\n"  # 3
        )
        assert regions(source) == ((3, 3),)

    def test_a_ternary_arm(self):
        source = (
            "x = (a()\n"  # 1
            "     if TYPE_CHECKING\n"  # 2
            "     else b())\n"  # 3
        )
        assert regions(source) == ((3, 3),)


class TestTwins:
    def test_a_platform_pair_is_a_twin_live_at_the_else(self):
        source = (
            "import sys\n"  # 1
            'if sys.platform == "win32":\n'  # 2
            "    def f():\n"  # 3
            "        return 1\n"  # 4
            "else:\n"  # 5
            "    def f():\n"  # 6
            "        return 2\n"  # 7
        )
        assert twins(source) == {"f": (6, (3,))}

    def test_a_type_checking_pair_is_a_twin_live_at_the_first(self):
        source = (
            "if TYPE_CHECKING:\n"  # 1
            "    def f():\n"  # 2
            "        return 1\n"  # 3
            "else:\n"  # 4
            "    def f():\n"  # 5
            "        return 2\n"  # 6
        )
        assert twins(source) == {"f": (2, (5,))}

    def test_a_try_except_pair_is_no_twin(self):
        source = (
            "try:\n"
            "    def f():\n"
            "        return 1\n"
            "except ImportError:\n"
            "    def f():\n"
            "        return 2\n"
        )
        assert twins(source) == {}

    def test_a_def_only_in_a_dead_arm_is_no_twin(self):
        source = 'import sys\nif sys.platform == "win32":\n    def f():\n        return 1\n'
        assert regions(source) == ((3, 4),)
        assert twins(source) == {}


#: click ``src/click/_termui_impl.py`` lines 880–972, verbatim, with four
#: of the file's imports above it: the shape ADR-154 was measured on.
CLICK_TWIN_EXCERPT = r'''import contextlib
import os
import sys
import typing as t


if sys.platform == "win32":
    import msvcrt

    @contextlib.contextmanager
    def raw_terminal() -> cabc.Iterator[int]:
        yield -1

    def getchar(echo: bool) -> str:
        # The function `getch` will return a bytes object corresponding to
        # the pressed character. Since Windows 10 build 1803, it will also
        # return \x00 when called a second time after pressing a regular key.
        #
        # `getwch` does not share this probably-bugged behavior. Moreover, it
        # returns a Unicode object by default, which is what we want.
        #
        # Either of these functions will return \x00 or \xe0 to indicate
        # a special key, and you need to call the same function again to get
        # the "rest" of the code. The fun part is that \u00e0 is
        # "latin small letter a with grave", so if you type that on a French
        # keyboard, you _also_ get a \xe0.
        # E.g., consider the Up arrow. This returns \xe0 and then \x48. The
        # resulting Unicode string reads as "a with grave" + "capital H".
        # This is indistinguishable from when the user actually types
        # "a with grave" and then "capital H".
        #
        # When \xe0 is returned, we assume it's part of a special-key sequence
        # and call `getwch` again, but that means that when the user types
        # the \u00e0 character, `getchar` doesn't return until a second
        # character is typed.
        # The alternative is returning immediately, but that would mess up
        # cross-platform handling of arrow keys and others that start with
        # \xe0. Another option is using `getch`, but then we can't reliably
        # read non-ASCII characters, because return values of `getch` are
        # limited to the current 8-bit codepage.
        #
        # Anyway, Click doesn't claim to do this Right(tm), and using `getwch`
        # is doing the right thing in more situations than with `getch`.

        if echo:
            func = t.cast(t.Callable[[], str], msvcrt.getwche)
        else:
            func = t.cast(t.Callable[[], str], msvcrt.getwch)

        rv = func()

        if rv in ("\x00", "\xe0"):
            # \x00 and \xe0 are control characters that indicate special key,
            # see above.
            rv += func()

        _translate_ch_to_exc(rv)
        return rv

else:
    import termios
    import tty

    @contextlib.contextmanager
    def raw_terminal() -> cabc.Iterator[int]:
        f: t.TextIO | None
        fd: int

        if not isatty(sys.stdin):
            f = open("/dev/tty")
            fd = f.fileno()
        else:
            fd = sys.stdin.fileno()
            f = None

        try:
            old_settings = termios.tcgetattr(fd)

            try:
                tty.setraw(fd)
                yield fd
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                sys.stdout.flush()

                if f is not None:
                    f.close()
        except termios.error:
            pass

    def getchar(echo: bool) -> str:
        with raw_terminal() as fd:
            ch = os.read(fd, 32).decode(get_best_encoding(sys.stdin), "replace")

            if echo and isatty(sys.stdout):
                sys.stdout.write(ch)

            _translate_ch_to_exc(ch)
            return ch
'''


def test_clicks_twin_reads_as_the_index_reads_it():
    """At 3.12 on Linux the win32 arm is dead (excerpt 8–58: `import
    msvcrt` to `return rv`), the `else` arm live, and both names it
    writes twice are twins whose node belongs at the `else` def."""
    lines = CLICK_TWIN_EXCERPT.splitlines()
    assert lines[7].strip() == "import msvcrt" and lines[57].strip() == "return rv"
    assert lines[64].strip().startswith("def raw_terminal")
    assert lines[90].strip().startswith("def getchar")
    read = pystatic.read_file(parse_source(CLICK_TWIN_EXCERPT.encode()), AT_312)
    assert read.regions == ((8, 58),)
    assert read.forms == ("sys.platform",)
    assert {q: live.line for q, (live, _) in read.twins.items()} == {
        "getchar": 91,
        "raw_terminal": 65,
    }
    assert {q: tuple(d.line for d in dead) for q, (_, dead) in read.twins.items()} == {
        "getchar": (14,),
        "raw_terminal": (11,),
    }
