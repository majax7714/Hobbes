"""E2's reading: an original run against its shadows, from two hand-written run directories.

Nothing here plans, answers or grades anything — a comparison is a reader over rows that already exist,
so the rows are written by hand and are the whole input. That is also why the runs are tiny: what is
under test is the delta, the flip and the refusal, not a pass rate.

**E4's cross-run readings are held the same way** at the end: `e4_compare`, one file's two runs one *model*
apart; `e4_pool`, one arm pair over several files' runs keyed `<isa>/<unit>`, read through as many rounds as
it is asked for; and `e4_rounds`, D-13's one arm against its own earlier round. What each of them refuses is
the point of it, so every refusal has a case here beside its one number — and so is **what is registered**:
D-13's pair is a reading at `through=1` and a tie at round 0, and the difference between those two is the
whole reason the `through` argument exists.
"""

import json
from pathlib import Path

import pytest

from lattice import compare, e4
from lattice.e1 import CALLS, GMEM, META, ROWS

MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
CELLS = ("avx2/float32/dot", "avx2/int8/dot")
PARAMS = {"temperature": 0.8, "top_p": 0.95, "max_tokens": 2048}


def write_run(run_dir, passes, *, k=1, cells=CELLS, model=MODEL, params=PARAMS, style=None, arms=("C-2", "C-3")):
    """One run directory: its `meta.json` and one greedy plus one drawn row per (cell, arm).

    *passes* maps `(arm, cell)` to whether the greedy sample passed; the drawn sample passes with it,
    so pass@1 and pass@k move together and a flip is visible in both.
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
        "target_sha": None if style else "a" * 40,
        "ledger": None,
        "shadow": None if style is None else {"style": style, "map_sha256": "d" * 64, "tree_sha256": "t" * 64},
        "p12": "arm=model+prompt",
    }
    (run_dir / META).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    rows = []
    for arm in arms:
        for cell in cells:
            for sample in (0, 1):
                rows.append(
                    {
                        "id": f"{cell}|{arm}|{sample}|0",
                        "cell": cell,
                        "name": cell,
                        "kind": "body",
                        "isa": cell.split("/")[0],
                        "type": cell.split("/")[1],
                        "metric": cell.split("/")[2],
                        "arm": arm,
                        "sample": sample,
                        "round": 0,
                        "class": "pass" if passes.get((arm, cell)) else "wrong",
                        "invented": [],
                        "reg": True,
                    }
                )
    (run_dir / ROWS).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    (run_dir / GMEM).write_text("", encoding="utf-8")
    (run_dir / CALLS).write_text(json.dumps({"round": 0, "requests": len(rows), "cost": 0.1}) + "\n", encoding="utf-8")
    return run_dir


@pytest.fixture
def runs(tmp_path):
    """The original passes both cells on C-2 and one on C-3; the shadow loses one and gains another."""
    original = write_run(
        tmp_path / "qwen-target",
        {("C-2", CELLS[0]): True, ("C-2", CELLS[1]): True, ("C-3", CELLS[0]): True},
    )
    shadowed = write_run(
        tmp_path / "qwen-descriptive",
        {("C-2", CELLS[0]): True, ("C-3", CELLS[1]): True},
        style="descriptive",
    )
    return original, shadowed


def test_each_arm_carries_both_runs_figures_and_the_shadows_delta(runs):
    original, shadowed = runs
    found = compare.compare(original, [shadowed])
    arms = found["shadows"][0]["sections"]["bodies"]

    assert found["original"]["model"] == MODEL and found["original"]["cells"] == list(CELLS)
    assert found["shadows"][0]["style"] == "descriptive"
    assert arms["C-2"]["original"]["pass_at_1"] == 1.0
    assert arms["C-2"]["shadow"]["pass_at_1"] == 0.5
    assert arms["C-2"]["delta"]["pass_at_1"] == -0.5
    assert arms["C-3"]["delta"]["pass_at_1"] == 0.0  # one cell each way is no change in the rate
    # the drawn sample moves with the greedy one here, so pass@k carries the same reading
    assert arms["C-2"]["delta"]["pass_at_k"] == -0.5


def test_the_flips_name_the_cells_each_way(runs):
    original, shadowed = runs
    flips = compare.compare(original, [shadowed])["shadows"][0]["flips"]
    assert flips["C-2"] == {"cells": 2, "lost": ["avx2/int8/dot"], "gained": []}
    assert flips["C-3"] == {"cells": 2, "lost": ["avx2/float32/dot"], "gained": ["avx2/int8/dot"]}


def test_a_run_at_another_k_is_refused_rather_than_differenced(tmp_path, runs):
    original, _ = runs
    other = write_run(tmp_path / "qwen-k5", {}, k=5, style="descriptive")
    with pytest.raises(compare.NotComparable) as refusal:
        compare.compare(original, [other])
    assert "k" in str(refusal.value) and "one variable" in str(refusal.value)


def test_another_model_other_params_or_other_cells_are_refused_too(tmp_path, runs):
    original, _ = runs
    cases = {
        "model": write_run(tmp_path / "olmo", {}, model="allenai/Olmo-3-7B-Instruct", style="descriptive"),
        "params": write_run(tmp_path / "hot", {}, params={**PARAMS, "temperature": 1.0}, style="descriptive"),
        "cells": write_run(tmp_path / "fewer", {}, cells=CELLS[:1], style="descriptive"),
    }
    for field, run_dir in cases.items():
        with pytest.raises(compare.NotComparable) as refusal:
            compare.compare(original, [run_dir])
        assert field in str(refusal.value) or "different cells" in str(refusal.value)


def test_a_run_with_no_meta_is_refused(tmp_path, runs):
    original, _ = runs
    (tmp_path / "empty").mkdir()
    with pytest.raises(compare.NotComparable) as refusal:
        compare.compare(original, [tmp_path / "empty"])
    assert "no meta.json" in str(refusal.value)


def test_arms_the_two_runs_do_not_share_are_left_out_rather_than_guessed(tmp_path, runs):
    original, _ = runs
    two_arms = write_run(tmp_path / "one-arm", {("C-2", CELLS[0]): True}, style="opaque", arms=("C-2",))
    found = compare.compare(original, [two_arms])
    assert sorted(found["shadows"][0]["sections"]["bodies"]) == ["C-2"]
    assert sorted(found["original"]["sections"]["bodies"]) == ["C-2", "C-3"]


def test_both_shadows_are_compared_in_one_reading(tmp_path, runs):
    original, descriptive = runs
    opaque = write_run(tmp_path / "qwen-opaque", {}, style="opaque")
    found = compare.compare(original, [descriptive, opaque])
    assert [row["style"] for row in found["shadows"]] == ["descriptive", "opaque"]
    assert found["shadows"][1]["sections"]["bodies"]["C-2"]["delta"]["pass_at_1"] == -1.0
    assert found["shadows"][1]["flips"]["C-2"]["lost"] == list(CELLS)


def test_the_table_names_each_shadow_by_its_style_and_its_flips(runs):
    original, shadowed = runs
    table = compare.render(compare.compare(original, [shadowed]))
    assert f"E2 {Path(original).name}" in table
    assert "descriptive (qwen-descriptive)" in table
    assert "-0.50" in table  # the delta carries its sign
    assert "lost   avx2/int8/dot" in table


def test_a_run_whose_rows_are_not_there_is_named_missing_and_not_read_as_zero(tmp_path, runs):
    original, _ = runs
    bare = write_run(tmp_path / "ungraded", {}, style="descriptive")
    (bare / ROWS).unlink()
    found = compare.compare(original, [bare])
    assert ROWS in found["shadows"][0]["missing"]
    assert found["shadows"][0]["sections"]["bodies"] == {}  # no arm to read, so no delta invented
    assert found["shadows"][0]["flips"] == {}


# MARK: - E4: one file's two runs one model apart, and one comparison pooled over files -

#: One helper a file, and the three of them are one name family (rule W) — which is what S-2h serves and
#: what a pool keyed `<isa>/<unit>` must keep apart: `hsum128_ps` and `hsum512_ps` are two units.
FAMILY = {"avx2": "hsum256_ps", "sse2": "hsum128_ps", "avx512": "hsum512_ps"}


def units_of(isa):
    """One held-out file's units, named as that file's own definitions are: two cells, a helper, the init."""
    return (
        (f"float32_distance_dot_{isa}", "cell"),
        (f"int8_distance_dot_{isa}", "cell"),
        (FAMILY[isa], "helper"),
        (f"init_distance_functions_{isa}", "init"),
    )


def write_e4_run(
    run_dir,
    passes,
    *,
    isa="avx2",
    model=MODEL,
    k=1,
    units=None,
    params=PARAMS,
    arms=("S-2", "S-2h"),
    target_sha="a" * 40,
):
    """One E4 run directory: `meta.json` and one greedy plus *k* drawn rows per (unit, arm).

    *passes* maps `(arm, unit)` to whether the unit passed; the drawn samples pass with the greedy one, so
    a move is visible in all three tests. *units* defaults to that ISA's own (:func:`units_of`).
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    named = list(units if units is not None else units_of(isa))
    record = {
        "model": model,
        "params": params,
        "arms": list(arms),
        "cells": [name for name, _ in named],
        "units": [{"name": name, "kind": kind, "cell": None} for name, kind in named],
        "k": k,
        "rounds": 0,
        "iterate": [],
        "rung": "L1",
        "isa": isa,
        "file": f"src/distance-{isa}.c",
        "target_sha": target_sha,
        "p12": "decomposed",
    }
    (run_dir / META).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    rows = []
    for arm in arms:
        for name, kind in named:
            for sample in range(0, k + 1):
                rows.append(
                    {
                        "id": f"{name}|{arm}|{sample}|0",
                        "cell": name,
                        "name": name,
                        "kind": kind,
                        "isa": isa,
                        "type": None,
                        "metric": None,
                        "arm": arm,
                        "sample": sample,
                        "round": 0,
                        "class": "pass" if passes.get((arm, name)) else "wrong",
                        "invented": [],
                        "reg": True,
                    }
                )
    (run_dir / ROWS).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return run_dir


def e4_runs(tmp_path, isa="avx2", **rest):
    """One file's run on the 7B and on the 32B: the helper passes on the larger model and nothing else."""
    small = write_e4_run(
        tmp_path / f"qwen-7b-{isa}",
        {("S-2", f"float32_distance_dot_{isa}"): True, ("S-2h", f"float32_distance_dot_{isa}"): True},
        isa=isa,
        **rest,
    )
    large = write_e4_run(
        tmp_path / f"qwen-32b-{isa}",
        {
            ("S-2", f"float32_distance_dot_{isa}"): True,
            ("S-2h", f"float32_distance_dot_{isa}"): True,
            ("S-2h", FAMILY[isa]): True,
        },
        isa=isa,
        model="Qwen/Qwen2.5-Coder-32B-Instruct",
        **rest,
    )
    return small, large


def test_e4_compare_pairs_each_shared_arm_by_unit_and_by_kind(tmp_path):
    small, large = e4_runs(tmp_path)
    found = compare.e4_compare(small, large)

    assert found["a"]["model"] == MODEL
    assert found["b"]["model"] == "Qwen/Qwen2.5-Coder-32B-Instruct"
    assert found["isa"] == "avx2" and found["file"] == "src/distance-avx2.c"
    assert found["arms"] == ["S-2", "S-2h"] and found["described"] is True
    # per arm, per kind: the 32B's one gained helper is on S-2h's helper line and on no other
    assert sorted(found["paired"]["S-2h"]) == ["cell", "helper", "init"]
    assert found["paired"]["S-2h"]["helper"]["pass_at_1"]["gained"] == 1
    assert found["paired"]["S-2h"]["helper"]["pass_at_1"]["delta"] == 1.0
    assert found["paired"]["S-2h"]["cell"]["pass_at_1"]["delta"] == 0.0
    assert found["paired"]["S-2"]["helper"]["pass_at_1"]["gained"] == 0
    # the drawn samples moved with it, so the sampled test reads the same one unit
    assert found["paired"]["S-2h"]["helper"]["pass_at_1_sampled"]["moved"] == 1

    table = compare.render_e4_compare(found)
    assert "E4 qwen-7b-avx2 → qwen-32b-avx2 — src/distance-avx2.c" in table
    assert "described: a second model is a price, not a registered comparison" in table
    assert "helper units  described" in table


def test_e4_compare_refuses_two_runs_that_differ_in_more_than_the_model(tmp_path):
    small, _ = e4_runs(tmp_path)
    cases = {
        "isa": write_e4_run(tmp_path / "other-isa", {}, isa="sse2"),
        "k": write_e4_run(tmp_path / "other-k", {}, k=5),
        "params": write_e4_run(tmp_path / "hot", {}, params={**PARAMS, "temperature": 1.0}),
        "units": write_e4_run(tmp_path / "fewer", {}, units=units_of("avx2")[:2]),
        "target_sha": write_e4_run(tmp_path / "moved", {}, target_sha="b" * 40),
    }
    for field, run_dir in cases.items():
        with pytest.raises(compare.NotComparable) as refusal:
            compare.e4_compare(small, run_dir)
        assert field in str(refusal.value) and "nothing was compared" in str(refusal.value)
    # and the model alone differing is exactly what it is for
    assert compare.e4_compare(small, e4_runs(tmp_path)[1])["described"] is True
    assert compare.E4_SAME == ("isa", "file", "target_sha", "units", "k", "params")


def test_e4_compare_reads_only_the_arms_the_two_share_and_names_missing_rows(tmp_path):
    small, _ = e4_runs(tmp_path)
    one_arm = write_e4_run(
        tmp_path / "qwen-32b-one-arm",
        {("S-2", "float32_distance_dot_avx2"): True},
        model="Qwen/Qwen2.5-Coder-32B-Instruct",
        arms=("S-2",),
    )
    found = compare.e4_compare(small, one_arm)
    assert found["arms"] == ["S-2"] and list(found["paired"]) == ["S-2"]

    (one_arm / ROWS).unlink()
    bare = compare.e4_compare(small, one_arm)
    assert bare["b"]["missing"] == [ROWS]
    assert bare["paired"] == {}  # no arm both runs answered, so no delta is invented for one
    assert "(no arm both runs answered)" in compare.render_e4_compare(bare)


def pooled_runs(tmp_path, arms=("S-2", "S-2h"), **rest):
    """One run per native file, each with its own units, on one model: what a pool is made of."""
    made = []
    for isa in ("avx2", "sse2", "avx512"):
        made.append(
            write_e4_run(tmp_path / f"pool-{isa}", {("S-2h", FAMILY[isa]): True}, isa=isa, arms=arms, **rest)
        )
    return made


def test_e4_pool_keys_every_unit_by_its_isa_and_counts_each_run(tmp_path):
    found = compare.e4_pool(pooled_runs(tmp_path), "S-2", "S-2h", "helper")

    assert found["pair"] == ["S-2", "S-2h"] and found["kind"] == "helper"
    assert found["registered"] is True  # the pair and the kind are on `e4.COMPARISONS`
    assert found["model"] == MODEL
    assert [row["isa"] for row in found["runs"]] == ["avx2", "sse2", "avx512"]
    assert all(row["units"] == {"S-2": 1, "S-2h": 1} and row["missing"] == [] for row in found["runs"])
    # one helper per file, each keyed by its own ISA, and each of the three gained on S-2h
    tests = found["paired"]["pass_at_1"]
    assert tests == {"cells": 3, "both": 0, "neither": 0, "lost": 0, "gained": 3, "delta": 1.0, "p": 0.25}
    assert found["paired"]["unpaired"] == 0

    table = compare.render_e4_pool(found)
    assert "E4 pooled S-2h − S-2 over 3 run(s)" in table and "helper unit(s); registered" in table
    assert "avx512  pool-avx512" in table  # every run is named, with the ISA its units are keyed by
    assert "S-2 1, S-2h 1" in table


def test_e4_pool_keeps_two_files_units_of_one_name_apart(tmp_path):
    """The `<isa>/` in the key. Two files can define one name, and pooling them as one unit would both
    halve the reading and pair each file's answer with the other's."""
    same = [
        write_e4_run(
            tmp_path / "pool-a", {("S-2h", "hsum256_ps"): True}, isa="avx2", units=(("hsum256_ps", "helper"),)
        ),
        write_e4_run(tmp_path / "pool-b", {}, isa="sse2", units=(("hsum256_ps", "helper"),)),
    ]
    found = compare.e4_pool(same, "S-2", "S-2h", "helper")
    assert [row["units"] for row in found["runs"]] == [{"S-2": 1, "S-2h": 1}] * 2
    # two units, not one: `avx2/hsum256_ps` moved and `sse2/hsum256_ps` did not
    assert found["paired"]["pass_at_1"]["cells"] == 2
    assert found["paired"]["pass_at_1"]["gained"] == 1 and found["paired"]["unpaired"] == 0


def test_e4_pool_over_every_kind_is_described_where_the_pair_is_not_registered(tmp_path):
    found = compare.e4_pool(pooled_runs(tmp_path), "S-2", "S-2h")
    assert found["kind"] is None and found["registered"] is False
    assert found["paired"]["pass_at_1"]["cells"] == 12  # four units a file, three files
    assert "described, not a registered comparison" in compare.render_e4_pool(found)


def test_e4_pool_reads_d12s_pair_over_every_unit_as_registered(tmp_path):
    """D-12 a's `S-3h − S-2h` is registered with **no kind**: the block is stated for every unit."""
    runs = [
        write_e4_run(
            tmp_path / f"pool-{isa}",
            {("S-3h", FAMILY[isa]): True, ("S-3h", f"int8_distance_dot_{isa}"): True},
            isa=isa,
            arms=("S-2h", "S-3h"),
        )
        for isa in ("avx2", "sse2", "avx512")
    ]
    found = compare.e4_pool(runs, "S-2h", "S-3h")
    assert found["kind"] is None and found["registered"] is True
    assert all(row["units"] == {"S-2h": 4, "S-3h": 4} for row in found["runs"])
    # every unit of every file, and the two the block moved in each of the three
    assert found["paired"]["pass_at_1"] == {
        "cells": 12, "both": 0, "neither": 6, "lost": 0, "gained": 6,
        "delta": 0.5, "p": 0.03125,
    }
    assert "every unit(s); registered" in compare.render_e4_pool(found)
    # asked for one kind it is a description, because that narrowing is not what was registered
    assert compare.e4_pool(runs, "S-2h", "S-3h", "helper")["registered"] is False


def test_e4_pool_refuses_one_isa_twice_or_runs_that_are_not_one_model(tmp_path):
    runs = pooled_runs(tmp_path)
    with pytest.raises(compare.NotComparable) as repeated:
        compare.e4_pool([runs[0], runs[1], runs[0]], "S-2", "S-2h", "helper")
    assert "both over avx2" in str(repeated.value) and "nothing was pooled" in str(repeated.value)

    other = write_e4_run(tmp_path / "pool-32b", {}, isa="sse2", model="Qwen/Qwen2.5-Coder-32B-Instruct")
    with pytest.raises(compare.NotComparable) as mixed:
        compare.e4_pool([runs[0], other], "S-2", "S-2h", "helper")
    assert "model" in str(mixed.value) and "about neither" in str(mixed.value)

    with pytest.raises(compare.NotComparable) as nothing:
        compare.e4_pool([], "S-2", "S-2h", "helper")
    assert "nothing to pool" in str(nothing.value)
    assert compare.E4_POOL_SAME == ("model", "k", "params")


#: D-13's chains, per file: one rescued by the facts arm alone, one rescued in both arms.
def write_loop_run(run_dir, *, isa="avx2", model=MODEL, k=0, rescued=("S-3hf",)):
    """One D-13 run: a copied round 0 that failed in both arms, and one retry round that moved *rescued*.

    The units are that file's own, so a pool over three of them is keyed apart; `FAMILY[isa]`'s chain is
    the one the retry is read on and every other unit keeps its round-0 row.
    """
    made = write_e4_run(run_dir, {}, isa=isa, model=model, k=k, arms=e4.LOOP_ARMS)
    record = json.loads((made / META).read_text(encoding="utf-8"))
    record.update({"rounds": 1, "iterate": list(e4.LOOP_ARMS), "retry_classes": list(e4.RETRY_CLASSES)})
    (made / META).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    later = [
        {
            "id": f"{FAMILY[isa]}|{arm}|{sample}|1",
            "cell": FAMILY[isa],
            "name": FAMILY[isa],
            "kind": "helper",
            "isa": isa,
            "arm": arm,
            "sample": sample,
            "round": 1,
            "class": "pass" if arm in rescued else "invented",
            "invented": [],
            "reg": True,
        }
        for arm in e4.LOOP_ARMS
        for sample in range(0, k + 1)
    ]
    with (made / ROWS).open("a", encoding="utf-8") as handle:
        for row in later:
            handle.write(f"{json.dumps(row, sort_keys=True)}\n")
    return made


def loop_pool(tmp_path, **rest):
    return [write_loop_run(tmp_path / f"d13-{isa}", isa=isa, **rest) for isa in ("avx2", "sse2", "avx512")]


def test_e4_pool_reads_d13s_pair_through_round_one_as_registered(tmp_path):
    """D-13's first registered reading: the same two arms at round 0 is a tie, and through round 1 is the pair."""
    runs = loop_pool(tmp_path)
    at_zero = compare.e4_pool(runs, "S-3hd", "S-3hf")
    assert at_zero["through"] == 0 and at_zero["registered"] is False
    # round 0 is one row copied twice, so nothing moved and nothing could have
    assert at_zero["paired"]["pass_at_1"]["lost"] == at_zero["paired"]["pass_at_1"]["gained"] == 0

    found = compare.e4_pool(runs, "S-3hd", "S-3hf", None, 1)
    assert found["through"] == 1 and found["registered"] is True
    # one chain a file, rescued by the facts arm and not by the control
    assert found["paired"]["pass_at_1"] == {
        "cells": 12, "both": 0, "neither": 9, "lost": 0, "gained": 3, "delta": 0.25, "p": 0.25,
    }
    table = compare.render_e4_pool(found)
    assert "through round 1" in table and "registered" in table
    # and narrowed to a kind it is a description: that narrowing is not what D-13 registered
    assert compare.e4_pool(runs, "S-3hd", "S-3hf", "helper", 1)["registered"] is False


def test_e4_rounds_reads_one_arms_two_rounds_and_says_it_cannot_go_down(tmp_path):
    """D-13's second registered reading, and the sentence that has to ride with it."""
    runs = loop_pool(tmp_path, rescued=e4.LOOP_ARMS)
    found = compare.e4_rounds(runs, "S-3hf")
    assert found["arm"] == "S-3hf" and found["rounds"] == [0, 1] and found["registered"] is True
    assert found["paired"]["pass_at_1"] == {
        "cells": 12, "both": 0, "neither": 9, "lost": 0, "gained": 3, "delta": 0.25, "p": 0.25,
    }
    assert found["paired"]["pass_at_1"]["lost"] == 0  # it cannot be anything else
    assert [row["retried"] for row in found["runs"]] == [1, 1, 1]
    assert all(row["units"] == {"round 0": 4, "round 1": 4} for row in found["runs"])

    table = compare.render_e4_rounds(found)
    assert "E4 S-3hf round 1 − round 0 over 3 run(s)" in table and "registered" in table
    assert "cannot be negative by construction" in table
    assert "retried 1" in table

    # the control arm's own rounds are the same reading and are **not** what D-13 registered
    assert compare.e4_rounds(runs, "S-3hd")["registered"] is False
    assert e4.registered_rounds("S-3hf", (0, 1)) and not e4.registered_rounds("S-3hf", (0, 2))


def test_e4_rounds_refuses_two_rounds_that_are_not_a_pair_and_a_pool_it_cannot_read(tmp_path):
    runs = loop_pool(tmp_path)
    for asked in ((1, 0), (1,), (0, 1, 2)):
        with pytest.raises(compare.NotComparable) as refusal:
            compare.e4_rounds(runs, "S-3hf", asked)
        assert "--rounds takes two rounds" in str(refusal.value)
    with pytest.raises(compare.NotComparable) as repeated:
        compare.e4_rounds([runs[0], runs[0]], "S-3hf")
    assert "both over avx2" in str(repeated.value)
    with pytest.raises(compare.NotComparable) as nothing:
        compare.e4_rounds([], "S-3hf")
    assert "nothing to pool" in str(nothing.value)


def test_e4_pool_names_a_run_that_has_no_rows_for_an_arm_rather_than_failing_it(tmp_path):
    runs = pooled_runs(tmp_path)
    (runs[1] / ROWS).unlink()
    found = compare.e4_pool(runs, "S-2", "S-2h", "helper")
    assert found["runs"][1]["missing"] == ["S-2", "S-2h"]
    assert found["runs"][1]["units"] == {"S-2": 0, "S-2h": 0}
    # the two files that answered are still paired, and the one that did not is in neither side
    assert found["paired"]["pass_at_1"]["cells"] == 2 and found["paired"]["unpaired"] == 0
