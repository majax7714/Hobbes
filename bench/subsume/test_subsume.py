"""The mutation-subsumption tool's pure parts: the verdict, the faults, the mirror."""

import os
from pathlib import Path

from subsume import classify, mirror, mutants, redundant_cases


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


def test_a_package_at_any_depth_is_mirrored_with_its_siblings(tmp_path):
    workspace = tmp_path / "ws"
    for rel in ("util", "packages/sdk/js/src", "packages/sdk/py", "packages/other"):
        (workspace / rel).mkdir(parents=True)
    for package in (workspace / "util", workspace / "packages" / "sdk" / "js"):
        into = tmp_path / package.name
        into.mkdir()
        copy = mirror(workspace, package, into)
        assert copy.is_dir() and not copy.is_symlink()
    js = tmp_path / "js"
    assert (js / "packages" / "sdk" / "py").is_symlink()
    assert (js / "packages" / "other").is_symlink()
    assert (js / "util").is_symlink()


def test_a_fault_every_case_fails_on_tells_none_apart():
    baseline = {"a": False, "b": False}
    assert classify(baseline, {"a": False, "b": False}) == ("survived", set())
    assert classify(baseline, {"a": True, "b": False}) == ("caught", {"a"})
    assert classify(baseline, {"a": True, "b": True})[0] == "every-case"
    # A file that no longer loads reports no cases at all.
    assert classify(baseline, {})[0] == "every-case"
    assert classify({"a": False}, {"a": True}) == ("caught", {"a"})


def test_a_bun_run_is_capped_only_where_a_scope_can_be_made(monkeypatch):
    import subsume

    subsume._can_cap.cache_clear()
    monkeypatch.setattr(subsume.shutil, "which", lambda name: None)
    assert subsume.capped(["bun", "test"]) == ["bun", "test"]
    subsume._can_cap.cache_clear()
    monkeypatch.setattr(subsume.shutil, "which", lambda name: "/usr/bin/systemd-run")
    monkeypatch.setattr(subsume.subprocess, "run", lambda *a, **k: type("P", (), {"returncode": 0})())
    assert subsume.capped(["bun", "test"])[:2] == ["systemd-run", "--user"]
    assert f"MemoryMax={subsume.MEMORY_MAX}" in subsume.capped(["bun", "test"])
    subsume._can_cap.cache_clear()
