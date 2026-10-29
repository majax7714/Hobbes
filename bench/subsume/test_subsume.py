"""The mutation-subsumption tool's pure parts: the verdict, the faults, the mirror."""

import os
from pathlib import Path

from subsume import mirror, mutants, redundant_cases


def labels(text: str) -> list[str]:
    return [label for _, label, _ in mutants(text)]


def test_a_case_whose_faults_others_catch_is_redundant():
    redundant, kept = redundant_cases({"a": {1, 2}, "b": {2, 3}, "c": {1}, "d": set()})
    assert [r["case"] for r in redundant] == ["d", "c"]
    assert redundant[1]["also_caught_by"] == ["a"]
    assert set(kept) == {"a", "b"}


def test_of_two_cases_catching_the_same_faults_one_is_kept():
    redundant, kept = redundant_cases({"a": {1, 2}, "b": {1, 2}})
    assert [r["case"] for r in redundant] == ["a"]
    assert list(kept) == ["b"]


def test_a_case_with_a_fault_of_its_own_is_kept():
    redundant, kept = redundant_cases({"a": {1, 2, 3}, "b": {3, 4}})
    assert redundant == []
    assert set(kept) == {"a", "b"}


def test_nothing_is_planted_inside_a_string_or_a_comment():
    found = labels('const s = "a < b && c" // x === y\n')
    assert not any("'<'" in label or "'&&'" in label or "'==='" in label for label in found)
    assert any(label.startswith("string") for label in found)


def test_operators_and_literals_each_give_one_fault_per_place():
    found = labels("if (a === b && n <= 3) return x\n")
    for expected in ("'==='->'!=='", "'&&'->'||'", "'<='->'<'", "'3'->'4'", "drop guard"):
        assert expected in found, expected
    # Two faults with one label on one line stay two faults.
    assert labels("x = a && b && c\n").count("'&&'->'||'") == 2


def test_a_regex_never_matches_or_loses_an_anchor():
    found = labels("const ok = /^ab+$/.test(value)\n")
    assert "regex never '^ab+$'" in found
    assert "regex unanchored-start '^ab+$'" in found
    assert "regex unanchored-end '^ab+$'" in found


def test_a_call_gives_way_to_its_argument_and_a_clamp_to_each_bound():
    text = "const v = Math.max(0, Math.min(hi, n))\nconst s = decode(raw)\n"
    by_line = {}
    for line, label, mutated in mutants(text):
        by_line.setdefault(line, []).append((label, mutated.split("\n")[line - 1]))
    first = dict(by_line[1])
    assert first["Math.max(…)->'0'"] == "const v = 0"
    assert first["Math.min(…)->'n'"] == "const v = Math.max(0, n)"
    assert dict(by_line[2])["decode(…)->'raw'"] == "const s = raw"


def test_imports_and_type_lines_are_left_alone():
    assert labels('import { a } from "./a"\nexport type T = 1 | 2\n') == []


def test_the_mirror_copies_the_package_and_links_the_rest(tmp_path):
    workspace = tmp_path / "ws"
    (workspace / "packages" / "util" / "src").mkdir(parents=True)
    (workspace / "packages" / "util" / "src" / "a.ts").write_text("export const a = 1\n")
    (workspace / "packages" / "other").mkdir()
    (workspace / "node_modules").mkdir()
    (tmp_path / "copy").mkdir()

    copy = mirror(workspace, workspace / "packages" / "util", tmp_path / "copy")
    assert copy == tmp_path / "copy" / "packages" / "util"
    assert not (copy / "src" / "a.ts").is_symlink()
    (copy / "src" / "a.ts").write_text("export const a = 2\n")
    assert (workspace / "packages" / "util" / "src" / "a.ts").read_text() == "export const a = 1\n"
    assert os.readlink(tmp_path / "copy" / "node_modules") == str(workspace / "node_modules")
    assert Path(os.readlink(tmp_path / "copy" / "packages" / "other")) == workspace / "packages" / "other"
