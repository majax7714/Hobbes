"""Tests for the home-screen logo data (DEC-017)."""

from __future__ import annotations

import pytest

from hobbes.watterson.serve import logo


def test_letters_spell_hobbes_in_the_theme_colour():
    rows = logo.letters()["rows"]
    assert len(rows) == 12 and len({len(r) for r in rows}) == 1
    assert len(rows[0]) == 6 * 8 + 5 * logo.GAP and set("".join(rows)) == {".", "T"}


def test_a_picture_file_parses():
    pic = logo.parse("# a comment\nO e8892b\nK #1C1816\n\n.OK\nKO\nT..\n")
    assert pic["palette"] == {"O": "#e8892b", "K": "#1c1816"}
    assert pic["rows"] == [".OK", "KO.", "T..", "..."]  # padded to a rectangle and an even height


@pytest.mark.parametrize("text, error", [
    ("O e8892b\n\nOX\n", "no colour: X"),
    ("O e8892b\n\nOO\n\nOO\n", "blank line inside"),
    ("# only\n", "no grid rows"),
])
def test_bad_pictures_are_refused(text, error):
    with pytest.raises(ValueError, match=error):
        logo.parse(text)


def test_payload_reads_the_file_or_falls_back(tmp_path):
    missing = logo.payload(tmp_path / "none.txt")
    assert missing["art"] is None and "error" not in missing and missing["letters"]["rows"]
    (tmp_path / "logo.txt").write_text("O e8892b\n\nOO\nOO\n")
    assert logo.payload(tmp_path / "logo.txt")["art"]["rows"] == ["OO", "OO"]
    (tmp_path / "bad.txt").write_text("OZ\n")
    bad = logo.payload(tmp_path / "bad.txt")
    assert bad["art"] is None and "no colour" in bad["error"]


def test_the_path_can_be_overridden(tmp_path):
    assert logo.logo_path({"HOBBES_LOGO": str(tmp_path / "x.txt")}) == tmp_path / "x.txt"
    assert logo.logo_path({}).name == "logo.txt"
