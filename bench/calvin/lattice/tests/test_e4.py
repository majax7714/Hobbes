"""E4's runner: the units and their order, the bare skeleton, the arms, the plan, and the file level.

No model appears anywhere here. The generator and the grader are injected, as in `test_e1.py`, so the
whole loop is driven by fakes over the fixture's own bytes; the one test that really compiles asks the
real grader with `allow_host=True` — this package's fixture, which is not a target checkout (`run.py`).

The property with the most riding on it is the third one down: **no held-out unit's gold body reaches any
prompt**. At L1 every definition of the file is a hole, so a single sibling body left in a skeleton would
hand the student the pattern S-2 exists to measure, and the run would read as S-2 under S-0's name.
"""

import json
import re
import shutil
from pathlib import Path

import pytest

from lattice import e1, e4, facts, grade as grade_of, holes, prompts, task
from lattice.cells import build
from lattice.scan import mask

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"
DERIVED = FIXTURE / "derived"

_IDENT = re.compile(r"[A-Za-z_]\w*")


@pytest.fixture(scope="module")
def lattice():
    return build(FIXTURE)


@pytest.fixture(scope="module")
def ledger():
    return facts.load(graph=DERIVED / "graph.json", key=DERIVED / "oracle.json")


# MARK: - the fakes -


def tokens(text):
    """The identifier tokens of a piece of C, masked: a name in a comment or a literal is not one."""
    return _IDENT.findall(mask(text))


def definition(lattice, isa, unit):
    """The unit's whole definition — signature and body — exactly as the file writes it."""
    source = lattice.sources[isa]
    return source.text[unit.signature_span.start : unit.body_span.end]


def golds(lattice, isa):
    """Each unit's gold body, by name."""
    text = lattice.sources[isa].text
    return {unit.name: holes.gold_body(text, unit) for unit in e4.units(lattice, isa)}


def replay_file(tmp_path, run_dir, lattice, isa, wrong=None):
    """A completions file answering every request with that unit's gold definition, or a planted body."""
    wrong = dict(wrong or {})
    units = {unit.name: unit for unit in e4.units(lattice, isa)}
    recorded = tmp_path / "completions.jsonl"
    rows = []
    for line in (run_dir / e1.REQUESTS).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        request = json.loads(line)
        unit = units[request["unit"]]
        body = wrong.get(unit.name)
        text = definition(lattice, isa, unit) if body is None else f"{unit.signature}\n{body}"
        rows.append({"id": request["id"], "text": f"Here you go.\n\n```c\n{text}\n```\n"})
    recorded.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return recorded


def fake_grade(lattice, isa, failing=()):
    """A grader that passes a gold body and fails everything else, as G-diff would, for both E4 forms."""
    gold = golds(lattice, isa)
    failing = set(failing)

    def grade(entries):
        results = []
        for entry in entries:
            if entry.get("bodies") is not None:
                ok = all(body == gold.get(name) for name, body in entry["bodies"].items())
                results.append({"id": entry["id"], "class": "pass" if ok else "wrong", "reg": True})
                continue
            name = entry["unit"]
            passed = entry["body"] == gold.get(name) and name not in failing
            results.append(
                {
                    "id": entry["id"],
                    "unit": name,
                    "class": "pass" if passed else "wrong",
                    "reg": True,
                    "feedback": "" if passed else "It compiled, and case bulk/0 disagrees with the scalar reference.",
                }
            )
        return results

    return grade


def real_grade(target, workdir):
    """The real graders over the fixture, one staged copy and one object cache for every call."""

    def grade(entries):
        return grade_of.grade(target, entries, workdir, allow_host=True)

    return grade


def make_run(tmp_path, lattice, arms=("S-0",), *, isa="avx2", k=0, ledger=None, model="M"):
    """`e4.plan` plus `e4.meta`, written into a fresh run directory."""
    requests = e4.plan(lattice, isa, arms, model, ledger, k=k)
    record = e4.meta(lattice, isa, requests, model, arms=arms, k=k, target=FIXTURE, facts=ledger)
    return e1.write_plan(tmp_path / "run", requests, record)


def rows_of(run_dir):
    return [json.loads(line) for line in (run_dir / e1.ROWS).read_text(encoding="utf-8").splitlines() if line.strip()]


# MARK: - the units and their order -


def test_every_definition_of_the_file_is_a_unit(lattice):
    units = e4.units(lattice, "avx2")
    assert len(units) == 27
    kinds = {kind: [u.name for u in units if u.kind == kind] for kind in e4.KINDS}
    assert len(kinds["cell"]) == 13 and len(kinds["helper"]) == 13
    assert kinds["init"] == ["init_distance_functions_avx2"]
    assert "hsum256_ps" in kinds["helper"] and "popcount_avx2" in kinds["helper"]
    # a cell carries its grid id; a helper and the init have no grid position and say so with `None`
    assert {u.cell for u in units if u.kind == "cell"} == {c.id for c in lattice.by_isa("avx2")}
    assert all(u.cell is None for u in units if u.kind != "cell")


def test_the_order_is_leaves_first(lattice):
    units = e4.units(lattice, "avx2")
    at = {unit.name: index for index, unit in enumerate(units)}
    calls = e4.calls_within(lattice, "avx2")
    for unit in units:
        for callee in calls[unit.name]:
            assert at[callee] < at[unit.name], f"{unit.name} is asked for before {callee}"
    # the two the card names: every helper a cell's gold body calls, and the init after the cells
    assert at["hsum256_ps"] < at["float32_distance_dot_avx2"]
    assert at["hsum256_epi64"] < at["hsum256_epi32"] < at["int8_distance_l2_impl_avx2"]
    installed = [c.name for c in lattice.by_isa("avx2") if c.slots]
    assert installed and all(at[name] < at["init_distance_functions_avx2"] for name in installed)
    assert e4.cycles(lattice, "avx2") == []


def test_a_cycle_is_one_group_in_file_order_and_the_plan_records_it(tmp_path):
    root = tmp_path / "cyclic"
    (root / "src").mkdir(parents=True)
    (root / "src" / "distance-avx2.c").write_text(
        "#include <stddef.h>\n"
        "extern distance_function_t dispatch_distance_table[8][8];\n"
        "static float ping(const void *a, int n);\n"
        "static float pong(const void *a, int n) { return ping(a, n); }\n"
        "static float ping(const void *a, int n) { return pong(a, n); }\n"
        "float float32_distance_dot_avx2 (const void *v1, const void *v2, int n)\n"
        "{ return ping(v1, n) + pong(v2, n); }\n"
        "int init_distance_functions_avx2 (void)\n"
        "{ dispatch_distance_table[VECTOR_DISTANCE_DOT][VECTOR_TYPE_F32] = float32_distance_dot_avx2; return 1; }\n",
        encoding="utf-8",
    )
    lattice = build(root)
    assert e4.cycles(lattice, "avx2") == [["pong", "ping"]]  # one group, in the file's own order
    ordered = [unit.name for unit in e4.units(lattice, "avx2")]
    assert ordered == ["pong", "ping", "float32_distance_dot_avx2", "init_distance_functions_avx2"]

    requests = e4.plan(lattice, "avx2", ("S-0",), "M", k=0)
    record = e4.meta(lattice, "avx2", requests, "M", arms=("S-0",), k=0)
    assert record["cycles"] == [["pong", "ping"]]


def test_a_name_the_file_defines_twice_is_not_one_unit(tmp_path):
    root = tmp_path / "twice"
    (root / "src").mkdir(parents=True)
    (root / "src" / "distance-avx2.c").write_text(
        "#if defined(__AVX2__)\n"
        "static int supported(void) { return 1; }\n"
        "#else\n"
        "static int supported(void) { return 0; }\n"
        "#endif\n",
        encoding="utf-8",
    )
    with pytest.raises(e4.DuplicateDefinition) as refused:
        e4.units(build(root), "avx2")
    assert "a unit is one definition" in str(refused.value)


def test_a_helper_no_cell_reaches_is_reached_by_nothing(lattice):
    reached = [cell.id for cell in e4.reaching_cells(lattice, "avx2", "hsum256_ps")]
    assert "avx2/float32/dot" in reached and "avx2/int8/dot" not in reached
    # the wrappers reach it through the `_impl` they call, which is a cell and not a helper
    assert "avx2/float32/l2" in reached
    assert e4.reaching_cells(lattice, "avx2", "bf16x8_to_f32x8_loadu") == ()


# MARK: - the skeleton -


def test_the_skeleton_prototypes_every_other_body_and_keeps_every_signature(lattice):
    source = lattice.sources["avx2"]
    unit = next(u for u in e4.units(lattice, "avx2") if u.name == "int8_distance_dot_avx2")
    skeleton = e4.skeleton(lattice, "avx2", unit)

    assert skeleton.endswith(unit.signature)
    above = [fn for fn in source.scanned.functions if fn.body_span.end <= unit.signature_span.start]
    assert len(above) > 15
    for fn in above:
        assert f"{fn.signature};" in skeleton, fn.name  # the signature stays, the body is a `;`
        assert holes.gold_body(source.text, fn) not in skeleton, fn.name
    # the helper this cell calls is there as a prototype, and its body is not
    assert "static inline __m256i dot_epi8 (__m256i a, __m256i b);" in skeleton
    # and what is not a definition is the file's own bytes
    assert "#include <immintrin.h>" in skeleton and "// MARK: - BIT -" not in skeleton


def test_the_skeleton_is_barer_than_c_zeros_prelude(lattice):
    """`task.prelude_bare` keeps the non-cell helpers' bodies; at L1 those helpers are holes too."""
    unit = next(u for u in e4.units(lattice, "avx2") if u.name == "float32_distance_dot_avx2")
    cell = lattice.get("avx2/float32/dot")
    body = holes.gold_body(lattice.sources["avx2"].text, next(
        fn for fn in lattice.sources["avx2"].scanned.functions if fn.name == "hsum256_ps"
    ))
    assert body in task.prelude_bare(lattice, cell)
    assert body not in e4.skeleton(lattice, "avx2", unit)


# MARK: - the arms -


def test_no_held_out_gold_reaches_any_prompt(lattice, ledger):
    units = e4.units(lattice, "avx2")
    bodies = {unit.name: tokens(holes.gold_body(lattice.sources["avx2"].text, unit)) for unit in units}
    for unit in units:
        for arm in e4.ARMS:
            written = tokens("".join(turn["content"] for turn in e4.messages(lattice, "avx2", unit, arm, ledger)))
            for other in units:
                if other.name == unit.name:
                    continue
                gold = bodies[other.name]
                run = len(gold)
                assert not any(written[at : at + run] == gold for at in range(len(written) - run + 1)), (
                    f"{arm} on {unit.name} carries {other.name}'s gold body"
                )


def test_the_arms_differ_in_one_thing_each(lattice, ledger):
    unit = next(u for u in e4.units(lattice, "avx2") if u.name == "float32_distance_dot_avx2")
    said = {
        arm: e4.messages(lattice, "avx2", unit, arm, ledger)[1]["content"] for arm in e4.ARMS
    }
    skeleton = e4.skeleton(lattice, "avx2", unit)
    assert all(skeleton in text for text in said.values())
    assert all(text.endswith(e4.INSTRUCTION) for text in said.values())
    for arm, text in said.items():
        assert ("The same function in the instruction sets that stay" in text) == (arm in e4.SHOT_ARMS)
        assert ("read from the project's graph and the compiler's own key" in text) == (arm in e4.FACTS_ARMS)
    assert [turn["role"] for turn in e4.messages(lattice, "avx2", unit, "S-0")] == ["system", "user"]


def test_a_cells_shots_are_the_same_position_in_every_other_native_file(lattice):
    unit = next(u for u in e4.units(lattice, "avx2") if u.name == "int8_distance_dot_avx2")
    shots = e4.shots(lattice, "avx2", unit)
    assert [(shot.isa, shot.source) for shot in shots] == [
        ("sse2", "sse2/int8/dot"),
        ("avx512", "avx512/int8/dot"),
    ]
    text = e4.messages(lattice, "avx2", unit, "S-2")[1]["content"]
    assert "/* sse2: sse2/int8/dot */" in text and "/* avx512: avx512/int8/dot */" in text
    assert "int8_distance_dot_sse2" in text  # another file's bytes, labelled by the ISA they came from


def test_the_init_units_shots_are_the_other_files_init_functions(lattice, ledger):
    unit = next(u for u in e4.units(lattice, "avx2") if u.kind == "init")
    assert [(shot.isa, shot.source) for shot in e4.shots(lattice, "avx2", unit)] == [
        ("sse2", "init_distance_functions_sse2"),
        ("avx512", "init_distance_functions_avx512"),
    ]
    text = e4.messages(lattice, "avx2", unit, "S-3", ledger)[1]["content"]
    assert "init_distance_functions_sse2" in text
    assert e4.NO_FACTS["init"] in text  # the ledger answers a cell's callees, and the init is not one


def test_a_helper_carries_no_shot_and_no_fact_and_says_so(lattice, ledger):
    unit = next(u for u in e4.units(lattice, "avx2") if u.name == "popcount_avx2")
    assert e4.shots(lattice, "avx2", unit) == []
    data = e4.context(lattice, "avx2", unit, "S-3", ledger)
    assert data["shots_note"] == "shots: none (helper)" and data["facts"] == []
    text = e4.messages(lattice, "avx2", unit, "S-3", ledger)[1]["content"]
    assert "shots: none (helper)" in text and "facts: none (helper)" in text
    assert e4.context(lattice, "avx2", unit, "S-0")["shots_note"] is None  # S-0 carries none by design


def test_a_facts_arm_with_no_ledger_is_refused_and_never_filled_empty(lattice):
    unit = next(u for u in e4.units(lattice, "avx2") if u.kind == "cell")
    with pytest.raises(prompts.NoLedger):
        e4.messages(lattice, "avx2", unit, "S-3")


def test_asking_for_an_arm_of_the_second_unit_is_refused_by_name(lattice, ledger):
    unit = next(u for u in e4.units(lattice, "avx2") if u.kind == "cell")
    for arm in e4.PLANNED:
        with pytest.raises(e4.NotBuilt) as refused:
            e4.context(lattice, "avx2", unit, arm, ledger)
        assert arm in str(refused.value) and "second unit" in str(refused.value)
    with pytest.raises(e4.NotBuilt):
        e4.plan(lattice, "avx2", ("S-0", "S-5"), "M", ledger, k=0)
    with pytest.raises(prompts.UnknownArm):
        e4.context(lattice, "avx2", unit, "C-2", ledger)


# MARK: - the plan -


def test_the_plan_is_every_unit_by_arm_by_sample_in_the_units_order(lattice, ledger):
    units = e4.units(lattice, "avx2")
    made = e4.plan(lattice, "avx2", ("S-0", "S-2"), "M", ledger, k=3)
    assert len(made) == 27 * 2 * 4
    assert len({request["id"] for request in made}) == len(made)
    assert all(request["mode"] == "chat" for request in made)  # no G-mem probe: those are E1's rows
    assert [request["unit"] for request in made][:8] == [units[0].name] * 8
    first = made[0]
    assert first["id"] == e1.request_id(units[0].name, "S-0", 0, 0)
    assert first["cell"] == units[0].name and first["kind"] == units[0].kind
    assert first["params"]["seed"] == e1.seed("M", units[0].name, "S-0", 0, 0)
    assert (first["params"]["temperature"], first["params"]["top_p"]) == (0.0, 1.0)
    drawn = made[1]
    assert (drawn["params"]["temperature"], drawn["params"]["top_p"]) == (e1.TEMPERATURE, e1.TOP_P)
    assert {request["params"]["max_tokens"] for request in made} == {e1.MAX_TOKENS}


def test_the_default_sampling_is_greedy_plus_ten(lattice):
    assert e4.K == 10
    made = e4.plan(lattice, "avx2", ("S-0",), "M")
    assert sorted({request["sample"] for request in made}) == list(range(0, 11))


def test_the_meta_records_the_rung_the_order_and_p12_decomposed(lattice, ledger):
    requests = e4.plan(lattice, "avx2", ("S-0", "S-3"), "M", ledger, k=1)
    record = e4.meta(lattice, "avx2", requests, "M", arms=("S-0", "S-3"), k=1, target=FIXTURE, facts=ledger)
    assert record["rung"] == "L1" and record["isa"] == "avx2" and record["file"] == "src/distance-avx2.c"
    assert record["p12"] == "decomposed" != e1.P12
    assert [row["name"] for row in record["units"]] == [u.name for u in e4.units(lattice, "avx2")]
    assert record["rounds"] == 0 and record["iterate"] == []  # E4 does not iterate
    window = record["decomposition"]
    assert window["unit_count"] == 27
    assert window["file_chars"] == len(lattice.sources["avx2"].text)
    assert window["largest_prompt_chars"] < window["file_chars"]
    assert window["every_window_smaller"] is True
    assert record["ledger"]["graph"]["version"] == "0.2.70-beta"


# MARK: - the loop, and the file level -


def test_the_loop_grades_every_unit_through_the_unit_form(tmp_path, lattice):
    run_dir = make_run(tmp_path, lattice)
    asked = []

    def grade(entries):
        asked.extend(entries)
        return fake_grade(lattice, "avx2")(entries)

    summary = e4.run(
        run_dir,
        FIXTURE,
        e1.replay_generator(replay_file(tmp_path, run_dir, lattice, "avx2")),
        grade,
        ceiling_usd=1.0,
    )
    assert summary["rows"] == 27 and summary["spent_usd"] == 0.0
    units = [entry for entry in asked if entry.get("unit")]
    assert len(units) == 27 and {entry["isa"] for entry in units} == {"avx2"}
    assert [row["class"] for row in rows_of(run_dir)] == ["pass"] * 27


def test_the_file_level_build_writes_the_patch_and_counts_the_units_that_passed(tmp_path, lattice):
    run_dir = make_run(tmp_path, lattice, ("S-0",))
    wrong = {"popcount_avx2": "{\n    (void)v;\n    return _mm256_setzero_si256();\n}"}
    summary = e4.run(
        run_dir,
        FIXTURE,
        e1.replay_generator(replay_file(tmp_path, run_dir, lattice, "avx2", wrong=wrong)),
        fake_grade(lattice, "avx2"),
        ceiling_usd=1.0,
    )
    level = summary["file_level"]
    assert [row["arm"] for row in level] == ["S-0"]
    row = level[0]
    passed = {r["cell"] for r in rows_of(run_dir) if r["class"] == "pass"}
    assert row["units"] == 27 and row["units_passed"] == len(passed) == 26
    assert "popcount_avx2" not in row["unit_names"]

    written = run_dir / row["written"]
    assert written.name == "distance-avx2.c"
    # every unit that passed wrote its gold back, so the file is the target's and the patch is empty
    assert written.read_text(encoding="utf-8") == lattice.sources["avx2"].text
    assert (written.parent / "distance-avx2.c.patch").read_text(encoding="utf-8") == ""
    assert row["diff_pass"] is True and row["reg"] is True

    # and a second pass over the same directory builds nothing again
    again = e4.file_level(run_dir, FIXTURE, fake_grade(lattice, "avx2"))
    assert len(again) == 1


def test_the_file_level_patch_names_the_lines_the_student_changed(tmp_path, lattice):
    run_dir = make_run(tmp_path, lattice, ("S-0",))
    gold = golds(lattice, "avx2")
    mine = "{\n    return (float)hsum256d(_mm256_setzero_pd());\n}"

    def grade(entries):
        """Everything passes, so the file the student wrote is every body it wrote — the wrong one too."""
        return [{"id": entry["id"], "class": "pass", "reg": True} for entry in entries]

    e4.run(
        run_dir,
        FIXTURE,
        e1.replay_generator(replay_file(tmp_path, run_dir, lattice, "avx2", wrong={"hsum256_ps": mine})),
        grade,
        ceiling_usd=1.0,
    )
    patch = (run_dir / e4.FINAL / "S-0" / "distance-avx2.c.patch").read_text(encoding="utf-8")
    assert patch.startswith("--- a/src/distance-avx2.c")
    assert "+    return (float)hsum256d(_mm256_setzero_pd());" in patch
    assert mine not in gold["hsum256_ps"]


# MARK: - gold substitution: a failed unit does not cascade -


@pytest.mark.skipif(shutil.which("clang") is None, reason="G-compile needs clang; the image has it")
def test_a_planted_wrong_unit_fails_alone_and_nothing_it_calls_cascades(tmp_path, lattice):
    """E4-d: every unit is graded against the gold file with that one definition punched."""
    run_dir = make_run(tmp_path, lattice, ("S-0",))
    flat = "{\n    (void)v;\n    return 0.0f;\n}"
    generate = e1.replay_generator(replay_file(tmp_path, run_dir, lattice, "avx2", wrong={"hsum256_ps": flat}))
    summary = e4.run(run_dir, FIXTURE, generate, real_grade(FIXTURE, tmp_path / "work"), ceiling_usd=1.0)

    by_unit = {row["cell"]: row for row in rows_of(run_dir)}
    assert summary["rows"] == 27
    assert by_unit["hsum256_ps"]["class"] == "wrong"
    assert by_unit["hsum256_ps"]["grade"]["bulk"]["failed"] > 0
    # every cell whose gold body reaches it is still graded against the target's own helper
    callers = [cell.id for cell in e4.reaching_cells(lattice, "avx2", "hsum256_ps")]
    assert len(callers) >= 5
    for cell in callers:
        name = lattice.get(cell).name
        assert by_unit[name]["class"] == "pass", (name, by_unit[name]["reason"])
    failed = sorted(name for name, row in by_unit.items() if row["class"] not in ("pass", grade_of.UNEXERCISED))
    assert failed == ["hsum256_ps"]
    # the fixture's five helpers no cell reaches: they compiled, and no slot ran them either way
    assert sorted(name for name, row in by_unit.items() if row["class"] == grade_of.UNEXERCISED) == [
        "bf16x8_to_f32x8_loadu",
        "block_has_l2_inf_mismatch_8",
        "block_has_l2_inf_mismatch_bf16_8",
        "dot_epu8",
        "hsum256d",
    ]

    # and the file the student wrote is the gold everywhere but the one unit it got wrong
    row = summary["file_level"][0]
    assert row["units_passed"] == 21 and row["diff_pass"] is True and row["reg"] is True
    assert row["graded_sha256"] == row["filled_sha256"]
