"""The five context arms: the shot rule, the volume control, and what each prompt carries and does not."""

import json
from pathlib import Path

import pytest

from lattice import facts, holes, prompts, task
from lattice.cells import build

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"
DERIVED = FIXTURE / "derived"

#: The fixture is the real files trimmed to float32, int8 and bit1, so most type pairings have no partner
#: on it and the fallback is what answers. That is the case the real target does not exercise.
REAL_BODY = ("body", "impl")


@pytest.fixture(scope="module")
def lattice():
    return build(FIXTURE)


@pytest.fixture(scope="module")
def ledger():
    return facts.load(graph=DERIVED / "graph.json", key=DERIVED / "oracle.json")


def native(lattice):
    return [cell for cell in lattice.cells.values() if cell.native]


# MARK: - C-2, the shots -


def test_the_shots_are_one_per_axis_by_the_pairing_or_by_the_fallback(lattice):
    found = prompts.shots(lattice, lattice.get("avx2/float32/l2_impl"))
    assert [(shot.cell.id, shot.axis, shot.rule) for shot in found] == [
        ("sse2/float32/l2_impl", "isa", "pairing"),
        ("avx2/int8/l2_impl", "type", "fallback"),  # the trimmed fixture has no float16 to pair with
        ("avx2/float32/l1", "metric", "pairing"),
    ]


def test_the_pairing_is_asked_before_the_fallback_on_the_type_axis(monkeypatch, lattice):
    # On the real target `float32` pairs with `float16` and the pairing answers; the trimmed fixture has
    # no `float16` at all, so the one way to reach that path here is to point the pairing at a type the
    # fixture does have. The cell is then the same one the fallback would have found, and the rule is not.
    monkeypatch.setitem(prompts.TYPE_PAIR, "float32", "int8")
    found = prompts.shots(lattice, lattice.get("avx2/float32/l2_impl"))
    assert [(shot.cell.id, shot.rule) for shot in found if shot.axis == "type"] == [
        ("avx2/int8/l2_impl", "pairing"),
    ]


def test_a_cell_with_no_type_and_no_metric_neighbour_keeps_its_isa_sibling_alone(lattice):
    found = prompts.shots(lattice, lattice.get("sse2/bit1/hamming"))
    assert [(shot.cell.id, shot.axis, shot.rule) for shot in found] == [
        ("avx2/bit1/hamming", "isa", "pairing"),
    ]


def test_a_wrapper_hole_takes_wrappers_and_its_sibling_wrapper_on_the_metric_axis(lattice):
    found = prompts.shots(lattice, lattice.get("avx2/float32/l2"))
    assert [(shot.cell.id, shot.rule) for shot in found] == [
        ("sse2/float32/l2", "pairing"),
        ("avx2/int8/l2", "fallback"),
        ("avx2/float32/l2_squared", "pairing"),
    ]
    assert all(shot.cell.kind == "wrapper" for shot in found)


def test_no_shot_is_a_reference_isa_the_hole_itself_or_the_wrong_kind(lattice):
    for cell in native(lattice):
        found = prompts.shots(lattice, cell)
        assert found, cell.id
        assert len(found) == len({shot.axis for shot in found}) == len({shot.cell.id for shot in found})
        for shot in found:
            assert shot.cell.isa in ("sse2", "avx2", "avx512"), (cell.id, shot.cell.id)
            assert shot.cell.id != cell.id
            assert shot.rule in ("pairing", "fallback")
            if cell.kind == "wrapper":
                assert shot.cell.kind == "wrapper", (cell.id, shot.cell.id)
            else:
                assert shot.cell.kind in REAL_BODY, (cell.id, shot.cell.id)
            if shot.axis == "isa":
                assert (shot.cell.type, shot.cell.metric) == (cell.type, cell.metric)
            elif shot.axis == "type":
                assert (shot.cell.isa, shot.cell.metric) == (cell.isa, cell.metric)
            else:
                assert (shot.cell.isa, shot.cell.type) == (cell.isa, cell.type)


# MARK: - C-4, the volume control -


def test_the_control_shares_neither_axis_with_the_hole_and_is_never_a_shot(lattice):
    for cell in native(lattice):
        taken = {shot.cell.id for shot in prompts.shots(lattice, cell)}
        rows = prompts.control(lattice, cell, 40)
        assert rows, cell.id
        for row in rows:
            assert row.cell.file == cell.file  # the hole's own file
            assert row.cell.kind in REAL_BODY
            assert row.cell.type != cell.type and row.cell.metric != cell.metric, (cell.id, row.cell.id)
            assert row.cell.id != cell.id and row.cell.id not in taken


def test_the_control_reaches_the_shots_line_count_or_the_file_ran_out(lattice):
    for cell in native(lattice):
        data = prompts.context(lattice, cell, "C-4")
        wanted, carried = data["lines"]["shots"], data["lines"]["control"]
        assert wanted == sum(
            prompts.line_count(prompts.definition(lattice, shot.cell))
            for shot in prompts.shots(lattice, cell)
        )
        if carried == wanted:
            # only the last body is ever cut, and it is cut to the line
            assert [row["cut"] for row in data["control"][:-1]] == [False] * (len(data["control"]) - 1)
        else:
            assert carried < wanted, cell.id
            assert not any(row["cut"] for row in data["control"]), cell.id


def test_when_the_file_runs_out_the_record_says_so_rather_than_repeating_a_body(lattice):
    cell = lattice.get("avx2/float32/dot")
    rows = prompts.control(lattice, cell, 10_000)
    assert len({row.cell.id for row in rows}) == len(rows)  # nothing is carried twice
    assert not any(row.cut for row in rows)
    assert sum(prompts.line_count(row.text) for row in rows) < 10_000


def test_the_same_cell_gives_the_same_choice_twice(lattice):
    for cell in native(lattice):
        first = prompts.control(lattice, cell, 60)
        second = prompts.control(lattice, cell, 60)
        assert [(row.cell.id, row.text, row.cut) for row in first] == [
            (row.cell.id, row.text, row.cut) for row in second
        ]


def test_the_control_arm_matches_the_shot_arm_and_carries_none_of_its_cells(lattice):
    for cell in native(lattice):
        shot_arm = prompts.context(lattice, cell, "C-2")
        control_arm = prompts.context(lattice, cell, "C-4")
        assert control_arm["lines"]["shots"] == shot_arm["lines"]["shots"]
        assert control_arm["lines"]["control"] <= control_arm["lines"]["shots"]
        assert control_arm["shots"] == [] and shot_arm["control"] == []
        assert {row["cell"] for row in control_arm["control"]}.isdisjoint(
            {row["cell"] for row in shot_arm["shots"]}
        )


# MARK: - the arms as prompts -


def test_every_arm_carries_the_bare_prelude_and_not_the_full_one(lattice, ledger):
    cell = lattice.get("avx2/int8/dot")
    bare = task.prelude_bare(lattice, cell)
    for arm in prompts.ARMS:
        assert prompts.context(lattice, cell, arm, ledger)["prelude"] == bare
        # fenced, so the block ends on the prelude's last line rather than on its trailing blank ones
        assert bare.rstrip() in prompts.messages(lattice, cell, arm, ledger)[1]["content"]
    assert bare != lattice.text(cell)[: cell.signature_span.start]  # the full prelude is a pattern arm


def test_c_zero_carries_no_lattice_cells_gold_body(lattice):
    bodies = {
        cell.id: holes.gold_body(lattice.text(cell), cell)
        for cell in lattice.cells.values()
        if len(holes.gold_body(lattice.text(cell), cell).splitlines()) >= 3
    }
    for cell in native(lattice):
        content = prompts.messages(lattice, cell, "C-0")[1]["content"]
        for other, body in bodies.items():
            assert body not in content, (cell.id, other)


def test_c_two_carries_each_shots_whole_definition_under_its_cell_id(lattice):
    for cell in native(lattice):
        content = prompts.messages(lattice, cell, "C-2")[1]["content"]
        for shot in prompts.shots(lattice, cell):
            assert f"/* {shot.cell.id} */" in content, (cell.id, shot.cell.id)
            assert prompts.definition(lattice, shot.cell) in content, (cell.id, shot.cell.id)


def test_c_one_names_every_callee_the_ledger_found_and_the_callers_the_lattice_knows(lattice, ledger):
    dot = lattice.get("avx2/float32/dot")
    content = prompts.messages(lattice, dot, "C-1", ledger)[1]["content"]
    rows = ledger.callees(lattice, dot)
    assert rows
    for row in rows:
        assert row["name"] in content, row["name"]
    assert "dispatch_distance_table[VECTOR_DISTANCE_DOT][VECTOR_TYPE_F32]" in content
    assert content.count("(no signature)") == sum(1 for row in rows if not row.get("signature"))
    # an `_impl` has no slot of its own: its callers are the two wrappers that reach it
    impl = lattice.get("avx2/float32/l2_impl")
    through = prompts.messages(lattice, impl, "C-1", ledger)[1]["content"]
    assert "float32_distance_l2_avx2 calls it" in through
    assert "float32_distance_l2_squared_avx2 calls it" in through
    assert "dispatch_distance_table[VECTOR_DISTANCE_SQUARED_L2][VECTOR_TYPE_F32]" in through


def test_c_three_carries_both_the_shots_and_the_facts(lattice, ledger):
    cell = lattice.get("avx2/int8/dot")
    content = prompts.messages(lattice, cell, "C-3", ledger)[1]["content"]
    for shot in prompts.shots(lattice, cell):
        assert prompts.definition(lattice, shot.cell) in content
    for row in ledger.callees(lattice, cell):
        assert row["name"] in content


def test_a_facts_arm_without_a_ledger_is_refused_by_a_type_of_its_own(lattice):
    cell = lattice.get("avx2/float32/dot")
    for arm in prompts.FACTS_ARMS:
        with pytest.raises(prompts.NoLedger):
            prompts.context(lattice, cell, arm)
        with pytest.raises(prompts.NoLedger):
            prompts.messages(lattice, cell, arm)
    # and the arms that do not claim facts are built without one
    for arm in ("C-0", "C-2", "C-4"):
        assert prompts.context(lattice, cell, arm)["facts"] is None


def test_an_unknown_arm_is_refused(lattice):
    with pytest.raises(prompts.UnknownArm):
        prompts.context(lattice, lattice.get("avx2/float32/dot"), "C-9")


def test_the_user_turn_ends_on_the_signature_and_the_instruction(lattice):
    cell = lattice.get("avx512/bit1/hamming")
    turns = prompts.messages(lattice, cell, "C-0")
    assert [turn["role"] for turn in turns] == ["system", "user"]
    assert turns[0]["content"] == prompts.SYSTEM
    assert turns[1]["content"].endswith(f"```c\n{cell.signature}\n```\n\n{prompts.INSTRUCTION}")


def test_a_section_the_arm_does_not_carry_takes_its_heading_with_it(lattice, ledger):
    cell = lattice.get("avx2/float32/dot")
    plain = prompts.messages(lattice, cell, "C-0")[1]["content"]
    assert "Related functions:" not in plain
    assert "What this function calls" not in plain and "What calls it:" not in plain
    assert "Related functions:" in prompts.messages(lattice, cell, "C-2")[1]["content"]
    assert "What this function calls" in prompts.messages(lattice, cell, "C-1", ledger)[1]["content"]


def test_the_same_inputs_give_the_same_bytes_and_none_of_them_is_the_targets_path(lattice, ledger):
    for cell in native(lattice):
        for arm in prompts.ARMS:
            first = prompts.messages(lattice, cell, arm, ledger)
            assert first == prompts.messages(lattice, cell, arm, ledger)
            dumped = json.dumps(first)
            assert str(FIXTURE) not in dumped, (cell.id, arm)
            assert str(FIXTURE.resolve()) not in dumped, (cell.id, arm)
