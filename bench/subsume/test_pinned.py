"""The pinned-input tool's pure parts: the changed keys, the shrink, the cover."""

from pinned import changed_keys, cover, shrink


def test_a_key_changes_when_its_value_differs_or_it_appears_or_goes():
    assert changed_keys({"a": 1, "b": 2, "c": None}, {"a": 1, "b": 3, "d": 4}) == ["b", "c", "d"]
    assert changed_keys({"a": [1, 2]}, {"a": [1, 2]}) == []


def test_shrink_deletes_lines_the_fault_does_not_need_and_keeps_the_header():
    def still_differs(candidates):
        # The fault shows while both "x" and "y" remain.
        return next((i for i, lines in enumerate(candidates) if "x" in lines and "y" in lines), None)

    assert shrink(["head", "a", "x", "b", "y", "c"], still_differs) == ["head", "x", "y"]
    assert shrink(["head"], still_differs) == ["head"]


def test_shrink_stops_when_no_deletion_still_shows_the_fault():
    assert shrink(["head", "x"], lambda candidates: None) == ["head", "x"]


def test_cover_keeps_the_fewest_inputs_that_tell_every_fault_apart():
    tells = {"long one": {1, 2}, "b": {2, 3}, "c": {3}, "d": {1, 2, 3}, "e": set()}
    assert cover(tells) == ["d"]
    assert cover({"aa": {1}, "b": {1}, "c": {2}}) == ["b", "c"]
    assert cover({}) == []


def test_the_harnesses_bun_tests_pass_where_bun_is():
    import subprocess
    from pathlib import Path

    import pytest
    import subsume

    if not Path(subsume.BUN).exists():
        pytest.skip("no Bun here: the harnesses' tests run where the TUI's workspace is installed")
    here = Path(__file__).parent
    if not (here / "../../tui/opencode/packages/merman/node_modules").exists():
        pytest.skip("the TUI's workspace is not installed (tui/install.sh)")
    proc = subprocess.run([subsume.BUN, "test", "harnesses.test.ts"], cwd=here, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
