"""A reference misnamed through an imported module, refused (ADR-161, C-178).

Hand-built sites over real lines: what is refused, what is kept, the
UTF-16 column, and the record. The whole ingest is
``test_reexport_lane_b.py``.
"""

from hobbes.extract.evidence import IMPLEMENTS, RESOLUTION, SCIP, Site
from hobbes.extract.pysource import parse_source
from hobbes.extract.reexport import (
    EXAMPLES,
    module_names,
    record,
    refuse,
    refused,
    source_lines,
    token_at,
)


def names_of(source: str) -> frozenset[str]:
    return module_names(parse_source(source.encode()))


def ref(line_text: str, token: str, name: str, *, file="pkg/use.py", line=1, nth=0) -> Site:
    """A reference at the *nth* occurrence of *token* on *line_text*
    (no character above U+FFFF before it, so the index is the column)."""
    col = -1
    for _ in range(nth + 1):
        col = line_text.index(token, col + 1)
    return Site(provider=SCIP, kind=RESOLUTION, file=file, line=line, name=name, col=col)


# -- module_names -------------------------------------------------------------


def test_module_names_are_the_plain_import_bindings():
    names = names_of(
        "import os.path\nimport minireexport as mr\nimport a.b.c as abc\n"
        "from x import y\nfrom . import z\n"
    )
    assert names == frozenset({"os", "mr", "abc"})


# -- refused ------------------------------------------------------------------


def test_a_module_attribute_named_as_another_symbol_is_refused():
    names = names_of("import minireexport as mr\n")
    line = "    second = mr.Gamma()"
    assert refused(ref(line, "Gamma", "Beta"), line, names)


def test_a_chain_from_a_dotted_import_is_refused_at_its_root():
    names = names_of("import os.path\n")
    line = "    return os.path.dirname(p)"
    assert refused(ref(line, "dirname", "join"), line, names)


def test_a_token_in_the_middle_of_a_longer_chain_is_refused():
    names = names_of("import a.b\n")
    line = "x = a.b.c.Token.method()"
    assert refused(ref(line, "Token", "Other"), line, names)


def test_the_token_equal_to_its_name_is_kept():
    names = names_of("import minireexport as mr\n")
    line = "    first = mr.Beta()"
    assert not refused(ref(line, "Beta", "Beta"), line, names)


def test_a_value_receiver_is_kept():
    """rich's `rich/style.py:199`: the index names the receiver's class at
    an instance attribute it has no symbol for — a true `uses`."""
    names = names_of("import sys\nimport os\n")
    line = "        self._link = link"
    assert not refused(ref(line, "_link", "Style"), line, names)
    line = "        width = line.style"
    assert not refused(ref(line, "style", "Text"), line, names)


def test_a_receiver_bound_by_from_import_is_kept():
    names = names_of("from x import y\n")
    line = "    y.Thing()"
    assert not refused(ref(line, "Thing", "Other"), line, names)


def test_a_bare_name_is_kept():
    names = names_of("import mr\n")
    line = "    Gamma()"
    assert not refused(ref(line, "Gamma", "Beta"), line, names)


def test_a_chain_hanging_off_a_call_has_no_root_to_read():
    names = names_of("import os\n")
    line = "    f().os.Gamma"
    assert not refused(ref(line, "Gamma", "Beta"), line, names)


def test_an_implements_site_is_never_refused():
    names = names_of("import minireexport as mr\n")
    line = "    second = mr.Gamma()"
    site = Site(provider=SCIP, kind=IMPLEMENTS, file="pkg/use.py", line=1, col=line.index("Gamma"))
    assert not refused(site, line, names)


# -- UTF-16 -------------------------------------------------------------------

#: rich's `tests/test_segment.py` line 274.
RICH_LINE = '        ("💩💩", 1, (Segment(" "), Segment(" 💩"))),'


def test_token_at_reads_the_column_in_utf16_code_units():
    assert token_at(RICH_LINE, 21) == "Segment"
    assert token_at(RICH_LINE, 35) == "Segment"
    # Read as a character index, the same columns land inside the word.
    assert RICH_LINE[21:28] != "Segment"
    assert RICH_LINE[35:42] != "Segment"


def test_token_at_reads_nothing_off_an_identifier_or_past_the_line():
    assert token_at(RICH_LINE, 0) == ""
    assert token_at(RICH_LINE, 11) == ""  # inside the first emoji's pair
    assert token_at(RICH_LINE, 1000) == ""
    assert token_at(RICH_LINE, -1) == ""


def test_a_column_past_an_emoji_is_read_at_the_right_character():
    names = names_of("import mr\n")
    line = '    s = ("💩", mr.Gamma())'
    col16 = line.index("Gamma") + 1  # the emoji is two code units
    site = Site(provider=SCIP, kind=RESOLUTION, file="f.py", line=1, name="Beta", col=col16)
    assert refused(site, line, names)
    assert not refused(
        Site(provider=SCIP, kind=RESOLUTION, file="f.py", line=1, name="Gamma", col=col16),
        line,
        names,
    )


def test_source_lines_break_where_python_counts_a_line():
    assert source_lines("a\r\nb\rc\nd\x0ce") == ["a", "b", "c", "d\x0ce"]


# -- refuse -------------------------------------------------------------------


USE = [
    "import minireexport as mr",
    "",
    "def build():",
    "    first = mr.Beta()",
    "    second = mr.Gamma()",
    "    return first, second, mr.two(1), mr.CONST",
]


def test_refuse_keeps_every_other_site_in_order():
    names = names_of("\n".join(USE) + "\n")
    files = {"pkg/use.py": (USE, names)}
    beta = ref(USE[3], "Beta", "Beta", line=4)
    gamma = ref(USE[4], "Gamma", "Beta", line=5)
    two = ref(USE[5], "two", "Beta", line=6)
    first = ref(USE[5], "first", "first", line=6)
    const = ref(USE[5], "CONST", "Beta", line=6)
    other_language = Site(
        provider=SCIP, kind=RESOLUTION, file="web/a.ts", line=5, name="Beta", col=13
    )
    implements = Site(provider=SCIP, kind=IMPLEMENTS, file="pkg/use.py", line=5, col=17)
    beyond = ref(USE[4], "Gamma", "Beta", line=99)
    sites = [other_language, beta, gamma, implements, two, first, const, beyond]

    kept, rows = refuse(sites, files)

    assert kept == [other_language, beta, implements, first, beyond]
    assert rows == [
        ("pkg/use.py", 5, "Gamma", "Beta"),
        ("pkg/use.py", 6, "two", "Beta"),
        ("pkg/use.py", 6, "CONST", "Beta"),
    ]


def test_refuse_with_no_python_files_keeps_everything():
    sites = [ref(USE[4], "Gamma", "Beta", line=5)]
    assert refuse(sites, {}) == (sites, [])


# -- record -------------------------------------------------------------------


def test_record_is_none_when_nothing_was_refused():
    assert record([]) is None


def test_record_names_the_count_the_constraint_and_sorted_examples():
    rows = [
        ("pkg/z.py", 1, "Zed", "Beta"),
        ("pkg/use.py", 6, "two", "Beta"),
        ("pkg/use.py", 5, "Gamma", "Beta"),
        ("pkg/a.py", 9, "CONST", "Beta"),
    ]
    out = record(rows)
    assert out["path"] == "."
    assert out["stage"] == "scip-python"
    message = out["message"]
    assert message.startswith("4 ")
    assert "C-178" in message
    assert "import *" in message
    examples = [
        "pkg/a.py:9 `CONST` named `Beta`",
        "pkg/use.py:5 `Gamma` named `Beta`",
        "pkg/use.py:6 `two` named `Beta`",
    ]
    positions = [message.index(example) for example in examples]
    assert positions == sorted(positions)
    assert "pkg/z.py" not in message
    assert EXAMPLES == 3


def test_record_of_one_says_one():
    out = record([("pkg/use.py", 5, "Gamma", "Beta")])
    assert out["message"].startswith("1 Python reference ")
