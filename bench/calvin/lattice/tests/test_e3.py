"""E3's reading: two runs of one plan, one adapter apart, from two hand-written run directories.

Nothing here plans, answers, trains or serves anything — E3's comparison is a reader over rows that
already exist, so the rows are written by hand and are the whole input. The runs are tiny for the same
reason `test_compare.py`'s are: what is under test is the pairing, the two registered labels and the
refusal, not a pass rate.
"""

import json

import pytest

from lattice import e3, paired
from lattice.e1 import CALLS, GMEM, META, ROWS

MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
#: Two real bodies and one wrapper, so the two sections the report keeps apart both have rows.
CELLS = ("avx2/float32/dot", "avx2/int8/dot", "avx2/float32/l2_squared")
WRAPPERS = ("avx2/float32/l2_squared",)
ARMS = ("C-0", "C-2", "C-3")
PARAMS = {"temperature": 0.8, "top_p": 0.95, "max_tokens": 2048}
K = 2

#: The two adapters E3 trains, as `e1.adapter_meta` records them.
ADAPTER = {
    "path": "adapters/qwen-qwen2-5-coder-7b-instruct/e3-c-lattice/0123456789ab/fedcba987654",
    "model": MODEL,
    "repo": "e3-c-lattice",
    "corpus_hash": "c" * 64,
    "recipe_hash": "fedcba987654",
    "steps": 300,
}
SHUFFLED = {
    **ADAPTER,
    "path": "adapters/qwen-qwen2-5-coder-7b-instruct/e3-c-lattice-shuffled/0123456789ab/9876543210fe",
    "repo": "e3-c-lattice-shuffled",
    "recipe_hash": "9876543210fe",
}


def write_run(
    run_dir,
    passes,
    *,
    drawn=None,
    k=K,
    cells=CELLS,
    arms=ARMS,
    model=MODEL,
    params=PARAMS,
    adapter=None,
    stated_task=None,
    shadow=None,
    target_sha="a" * 40,
):
    """One run directory: its `meta.json`, and one greedy plus *k* drawn rows per (cell, arm).

    *passes* maps `(arm, cell)` to whether the greedy sample passed; *drawn* maps it to how many of the
    *k* draws passed, defaulting to all of them where the greedy one passed and none where it did not.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "model": model,
        "params": params,
        "arms": list(arms),
        "cells": list(cells),
        "k": k,
        "rounds": 0,
        "iterate": [],
        "target_sha": target_sha,
        "ledger": None,
        "shadow": shadow,
        "adapter": adapter,
        "stated_task": stated_task is not None,
        "stated_task_sha256": stated_task,
        "p12": "arm=model+prompt",
    }
    (run_dir / META).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")

    rows = []
    for arm in arms:
        for cell in cells:
            greedy = bool(passes.get((arm, cell)))
            hits = (drawn or {}).get((arm, cell), k if greedy else 0)
            for sample in range(0, k + 1):
                rows.append(
                    {
                        "id": f"{cell}|{arm}|{sample}|0",
                        "cell": cell,
                        "name": cell,
                        "kind": "wrapper" if cell in WRAPPERS else "body",
                        "isa": cell.split("/")[0],
                        "type": cell.split("/")[1],
                        "metric": cell.split("/")[2],
                        "arm": arm,
                        "sample": sample,
                        "round": 0,
                        "class": "pass" if (greedy if sample == 0 else sample <= hits) else "wrong",
                        "invented": [],
                        "reg": True,
                    }
                )
    (run_dir / ROWS).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    (run_dir / GMEM).write_text("", encoding="utf-8")
    (run_dir / CALLS).write_text(json.dumps({"round": 0, "requests": len(rows), "cost": 0.2}) + "\n", encoding="utf-8")
    return run_dir


@pytest.fixture
def runs(tmp_path):
    """The shuffled adapter against E3's own: C-2 gains a cell and C-0 stays where it was."""
    shuffled = write_run(
        tmp_path / "qwen-shuffled-300",
        {("C-2", CELLS[0]): True, ("C-0", CELLS[2]): True},
        adapter=SHUFFLED,
    )
    trained = write_run(
        tmp_path / "qwen-adapter-300",
        {("C-2", CELLS[0]): True, ("C-2", CELLS[1]): True, ("C-0", CELLS[2]): True},
        drawn={("C-3", CELLS[1]): 1},
        adapter=ADAPTER,
    )
    return shuffled, trained


def test_the_paired_rows_are_paired_dot_paired_from_a_to_b(runs):
    shuffled, trained = runs
    found = e3.compare(shuffled, trained)
    before, after = paired.cells(shuffled), paired.cells(trained)

    assert sorted(found["paired"]) == ["bodies", "wrappers"]
    for section, arms in found["paired"].items():
        assert sorted(arms) == sorted(ARMS)
        for arm, tests in arms.items():
            assert tests == paired.paired(before[section][arm], after[section][arm], K)

    # the reading itself: C-2 gained one of the two real bodies, and it is b − a
    assert found["paired"]["bodies"]["C-2"]["pass_at_1"]["gained"] == 1
    assert found["paired"]["bodies"]["C-2"]["pass_at_1"]["delta"] == 0.5
    # and a drawn sample that moved without the greedy one is read on the sampled rate alone
    assert found["paired"]["bodies"]["C-3"]["pass_at_1"]["delta"] == 0.0
    assert found["paired"]["bodies"]["C-3"]["pass_at_1_sampled"]["moved"] == 1


def test_the_two_registered_comparisons_are_marked_and_every_other_arm_described(runs):
    shuffled, trained = runs
    found = e3.compare(shuffled, trained)
    assert found["registered"] == {"C-2": "E3-use", "C-0": "E3-weights"}
    assert found["registered_section"] == "bodies" == e3.REGISTERED_SECTION
    assert found["primary"] == "pass_at_1_sampled" == e3.PRIMARY

    table = e3.render(found)
    bodies, wrappers = table.split("paired, wrappers")
    assert "C-2  E3-use (registered; primary pass_at_1_sampled)" in bodies
    assert "C-0  E3-weights (registered; primary pass_at_1_sampled)" in bodies
    assert "C-3  described, not a registered comparison" in bodies
    # a wrapper's one call is not the task a body is, so the same two arms are described there
    assert "registered" not in wrappers.replace("not a registered comparison", "")
    assert wrappers.count("described, not a registered comparison") == len(ARMS)
    # all three tests are printed under every arm; the label says which one the card reads
    assert table.count("pass_at_1_sampled") == 2 * len(ARMS) + 2


def test_each_side_names_the_weights_that_answered_and_the_plan_they_ran(runs):
    shuffled, trained = runs
    found = e3.compare(shuffled, trained)
    assert found["a"]["adapter"] == SHUFFLED and found["b"]["adapter"] == ADAPTER
    assert found["a"]["cells"] == len(CELLS) and found["a"]["arms"] == list(ARMS)

    table = e3.render(found)
    assert f"E3 qwen-shuffled-300 → qwen-adapter-300 — {MODEL} (k=2, 3 cell(s), arms C-0, C-2, C-3)" in table
    assert f"b qwen-adapter-300: {ADAPTER['path']} — repo e3-c-lattice, corpus cccccccccccc, " in table
    assert "recipe fedcba987654, 300 step(s)" in table
    assert "the target itself, stated task: no" in table


def test_the_base_model_is_a_side_like_any_other_and_says_so(tmp_path, runs):
    _, trained = runs
    base = write_run(tmp_path / "qwen-base", {("C-2", CELLS[0]): True})
    found = e3.compare(base, trained)
    assert found["a"]["adapter"] is None
    assert "a qwen-base: the base model, no adapter" in e3.render(found)


def test_a_pair_differing_in_more_than_the_adapter_is_refused(tmp_path, runs):
    shuffled, trained = runs
    cases = {
        "k": write_run(tmp_path / "other-k", {}, k=5, adapter=ADAPTER),
        "cells": write_run(tmp_path / "fewer-cells", {}, cells=CELLS[:2], adapter=ADAPTER),
        "arms": write_run(tmp_path / "fewer-arms", {}, arms=("C-0", "C-2"), adapter=ADAPTER),
        "model": write_run(tmp_path / "olmo", {}, model="allenai/Olmo-3-7B-Instruct", adapter=ADAPTER),
        "params": write_run(tmp_path / "hot", {}, params={**PARAMS, "temperature": 1.0}, adapter=ADAPTER),
        "stated_task": write_run(tmp_path / "stated", {}, stated_task="d" * 64, adapter=ADAPTER),
        "shadow": write_run(tmp_path / "opaque", {}, shadow={"style": "opaque"}, adapter=ADAPTER),
        "target_sha": write_run(tmp_path / "moved", {}, target_sha="b" * 40, adapter=ADAPTER),
    }
    for field, other in cases.items():
        with pytest.raises(e3.NotComparable) as refusal:
            e3.compare(shuffled, other)
        assert field in str(refusal.value) and "one difference" in str(refusal.value)
    # the same two runs of one plan, differing only in the adapter, are the comparison E3 exists for
    assert e3.compare(shuffled, trained)["paired"]


def test_two_stated_task_runs_of_one_table_are_comparable_and_two_tables_are_not(tmp_path):
    first = write_run(tmp_path / "stated-base", {}, stated_task="d" * 64, shadow={"style": "opaque"})
    second = write_run(tmp_path / "stated-adapter", {}, stated_task="d" * 64, shadow={"style": "opaque"},
                       adapter=ADAPTER)
    found = e3.compare(first, second)
    assert found["a"]["stated_task"] is True
    assert "opaque, stated task: yes" in e3.render(found)

    reworded = write_run(tmp_path / "reworded", {}, stated_task="e" * 64, shadow={"style": "opaque"})
    with pytest.raises(e3.NotComparable) as refusal:
        e3.compare(first, reworded)
    assert "stated_task_sha256" in str(refusal.value)


def test_the_arms_and_the_cells_are_read_as_a_set_and_not_as_an_order(tmp_path, runs):
    shuffled, _ = runs
    reordered = write_run(
        tmp_path / "reordered", {}, cells=tuple(reversed(CELLS)), arms=tuple(reversed(ARMS)), adapter=ADAPTER
    )
    assert e3.compare(shuffled, reordered)["paired"]


def test_a_run_with_no_meta_is_refused(tmp_path, runs):
    shuffled, _ = runs
    (tmp_path / "empty").mkdir()
    with pytest.raises(e3.NotComparable) as refusal:
        e3.compare(shuffled, tmp_path / "empty")
    assert "no meta.json" in str(refusal.value)


def test_a_run_whose_rows_are_not_there_is_named_missing_and_not_read_as_zero(tmp_path, runs):
    shuffled, _ = runs
    ungraded = write_run(tmp_path / "ungraded", {}, adapter=ADAPTER)
    (ungraded / ROWS).unlink()
    found = e3.compare(shuffled, ungraded)
    assert found["b"]["missing"] == [ROWS]
    assert found["paired"] == {}  # no rows on one side, so no test invented over the other's
    assert "missing, not read as zero: rows.jsonl" in e3.render(found)
