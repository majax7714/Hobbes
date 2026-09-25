"""E1's runner: the plan, the rounds, resume, the ceiling, and the Modal script's pins.

No model appears anywhere here. The generator and the grader are injected, so every round of every arm is
driven by a fake that answers from the fixture's own bytes, and the one test that really compiles asks the
real grader with `allow_host=True` — this package's fixture, which is not a target checkout (`run.py`).
"""

import ast
import json
import subprocess
import shutil
from pathlib import Path

import pytest

from lattice import e1, facts, holes, prompts
from lattice.cells import build

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"
DERIVED = FIXTURE / "derived"
MODAL = Path(__file__).parents[1] / "scripts" / "modal_e1.py"

needs_clang = pytest.mark.skipif(shutil.which("clang") is None, reason="G-compile needs clang; the image has it")


@pytest.fixture(scope="module")
def lattice():
    return build(FIXTURE)


@pytest.fixture(scope="module")
def ledger():
    return facts.load(graph=DERIVED / "graph.json", key=DERIVED / "oracle.json")


# MARK: - the fakes -


class FakeGenerator:
    """Answers every request from a `request -> text` rule, and records what it was asked."""

    def __init__(self, answer, cost=0.0):
        self.answer = answer
        self.cost = cost
        self.calls = []

    def __call__(self, requests):
        self.calls.append([request["id"] for request in requests])
        return {
            "completions": [
                {
                    "id": request["id"],
                    "text": self.answer(request),
                    "tokens_in": 100,
                    "tokens_out": 20,
                    "finish_reason": "stop",
                }
                for request in requests
            ],
            "cost": self.cost,
            "seconds": 1.0,
        }


def fake_grade(gold_bodies):
    """A grader that passes exactly the gold bodies and fails everything else, as G-diff would."""

    def grade(entries):
        results = []
        for entry in entries:
            passed = entry["body"] == gold_bodies.get(entry["cell"])
            results.append(
                {
                    "id": entry["id"],
                    "cell": entry["cell"],
                    "class": "pass" if passed else "wrong",
                    "reg": True,
                    "diagnostics": [{"file": "src/x.c", "line": n, "col": 1, "severity": "error", "message": "boom"} for n in range(30)],
                    "invented": [] if passed else [{"name": "_mm256_nope_ps", "bucket": "intrinsic"}],
                    "feedback": "" if passed else "It compiled, and case bulk/0 disagrees with the scalar reference.",
                }
            )
        return results

    return grade


def fenced(text):
    return f"Here you go.\n\n```c\n{text}\n```\n"


def golds(lattice):
    return {cell.id: holes.gold_body(lattice.text(cell), cell) for cell in lattice.cells.values()}


def make_run(tmp_path, lattice, cells, arms, model="Qwen/Qwen2.5-Coder-7B-Instruct", k=1, ledger=None, rounds=3):
    requests = e1.plan(lattice, cells, arms, model, ledger, k=k)
    record = e1.meta(model, arms=arms, cells=cells, k=k, rounds=rounds, target=FIXTURE)
    return e1.write_plan(tmp_path / "run", requests, record)


def rows(run_dir):
    return [json.loads(line) for line in (run_dir / e1.ROWS).read_text(encoding="utf-8").splitlines() if line.strip()]


def requests_of(run_dir):
    return [json.loads(line) for line in (run_dir / e1.REQUESTS).read_text(encoding="utf-8").splitlines() if line.strip()]


# MARK: - the plan -


def test_the_plan_is_every_cell_by_arm_by_sample_plus_one_probe_each(lattice, ledger):
    cells = list(lattice.by_isa("avx2"))
    made = e1.plan(lattice, cells, prompts.ARMS, "M", ledger, k=5)
    chat = [request for request in made if request["mode"] == "chat"]
    probes = [request for request in made if request["mode"] == "complete"]
    assert len(cells) == 13
    assert len(chat) == 13 * 5 * 6
    assert len(probes) == 13
    assert {request["id"] for request in probes} == {f"{cell.id}|gmem" for cell in cells}
    assert len({request["id"] for request in made}) == len(made)


def test_a_chat_request_carries_its_turns_its_grid_position_and_its_id(lattice):
    cell = lattice.get("avx2/int8/dot")
    made = e1.plan(lattice, [cell], ("C-2",), "M", k=2)
    first = made[0]
    assert first["id"] == "avx2/int8/dot|C-2|0|0"
    assert first["messages"] == prompts.messages(lattice, cell, "C-2")
    assert (first["kind"], first["isa"], first["type"], first["metric"]) == (cell.kind, "avx2", "int8", "dot")
    assert first["name"] == cell.name


def test_the_probe_is_a_raw_continuation_and_carries_what_it_expects(lattice):
    cell = lattice.get("avx2/float32/dot")
    probe = [r for r in e1.plan(lattice, [cell], ("C-0",), "M", k=1) if r["mode"] == "complete"][0]
    assert probe["params"]["max_tokens"] == e1.GMEM_MAX_TOKENS
    assert probe["params"]["temperature"] == 0.0
    assert "messages" not in probe
    assert probe["expected"] and probe["expected"] in lattice.text(cell)


def test_sample_zero_is_greedy_and_the_rest_are_drawn(lattice):
    made = [r for r in e1.plan(lattice, ["avx2/float32/dot"], ("C-0",), "M", k=3) if r["mode"] == "chat"]
    assert [r["sample"] for r in made] == [0, 1, 2, 3]
    assert made[0]["params"]["temperature"] == 0.0 and made[0]["params"]["top_p"] == 1.0
    for drawn in made[1:]:
        assert (drawn["params"]["temperature"], drawn["params"]["top_p"]) == (e1.TEMPERATURE, e1.TOP_P)


def test_the_seeds_are_distinct_and_the_same_two_calls_running(lattice, ledger):
    cells = list(lattice.by_isa("avx2"))
    first = e1.plan(lattice, cells, prompts.ARMS, "M", ledger, k=5)
    second = e1.plan(lattice, cells, prompts.ARMS, "M", ledger, k=5)
    seeds = [request["params"]["seed"] for request in first]
    assert len(set(seeds)) == len(seeds)
    assert seeds == [request["params"]["seed"] for request in second]
    # and the model is in the seed, so two models do not draw the same samples
    assert seeds != [r["params"]["seed"] for r in e1.plan(lattice, cells, prompts.ARMS, "N", ledger, k=5)]


def test_a_facts_arm_without_a_ledger_is_refused_by_prompts_own_type(lattice):
    with pytest.raises(prompts.NoLedger):
        e1.plan(lattice, ["avx2/float32/dot"], ("C-1",), "M")


def test_the_meta_records_p12_the_sha_and_never_the_targets_path(lattice, ledger):
    record = e1.meta("M", arms=prompts.ARMS, cells=list(lattice.by_isa("avx2")), facts=ledger, target=FIXTURE)
    assert record["p12"] == "arm=model+prompt"
    assert record["ledger"]["graph"]["sha"]
    dumped = json.dumps(record)
    assert str(FIXTURE) not in dumped and str(FIXTURE.resolve()) not in dumped


# MARK: - the loop -


def test_a_chain_that_passes_at_round_zero_stops_there(tmp_path, lattice):
    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-0",))
    generate = FakeGenerator(lambda request: fenced(prompts.definition(lattice, cell)))
    e1.run(run_dir, FIXTURE, generate, fake_grade(golds(lattice)), ceiling_usd=10.0)

    chat = [row for row in rows(run_dir)]
    assert {row["round"] for row in chat} == {0}
    assert [row["class"] for row in chat] == ["pass", "pass"]
    assert len(generate.calls) == 1


def test_a_chain_that_fails_then_writes_the_gold_passes_at_round_one(tmp_path, lattice):
    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-0",))
    generate = FakeGenerator(
        lambda request: fenced(prompts.definition(lattice, cell))
        if request["round"] == 1
        else fenced(_wrong(lattice, cell))
    )
    e1.run(run_dir, FIXTURE, generate, fake_grade(golds(lattice)), ceiling_usd=10.0)

    by_round = {}
    for row in rows(run_dir):
        by_round.setdefault(row["round"], []).append(row["class"])
    assert by_round == {0: ["wrong", "wrong"], 1: ["pass", "pass"]}

    later = [request for request in requests_of(run_dir) if request["round"] == 1]
    assert len(later) == 2
    for request in later:
        assert request["messages"][-2]["role"] == "assistant"
        assert request["messages"][-2]["content"] == fenced(_wrong(lattice, cell))
        assert request["messages"][-1] == {
            "role": "user",
            "content": "It compiled, and case bulk/0 disagrees with the scalar reference.",
        }
        # the seed moves with the round, so round 1 is not a re-draw of round 0
        assert request["params"]["seed"] != e1.seed(
            "Qwen/Qwen2.5-Coder-7B-Instruct", cell.id, "C-0", request["sample"], 0
        )


def test_a_chain_that_never_passes_stops_after_the_last_round(tmp_path, lattice):
    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-0",))
    generate = FakeGenerator(lambda request: fenced(_wrong(lattice, cell)))
    e1.run(run_dir, FIXTURE, generate, fake_grade(golds(lattice)), ceiling_usd=10.0)

    assert sorted({row["round"] for row in rows(run_dir)}) == [0, 1, 2, 3]
    assert len(rows(run_dir)) == 2 * 4
    assert len(generate.calls) == 4


def test_a_non_iterate_arm_has_round_zero_only(tmp_path, lattice):
    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-2",))
    generate = FakeGenerator(lambda request: fenced(_wrong(lattice, cell)))
    e1.run(run_dir, FIXTURE, generate, fake_grade(golds(lattice)), ceiling_usd=10.0)

    assert {row["round"] for row in rows(run_dir)} == {0}
    assert len(generate.calls) == 1


def test_a_completion_with_no_fence_is_no_body_is_not_graded_and_is_told_the_fixed_sentence(tmp_path, lattice):
    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-0",))
    graded = []

    def grade(entries):
        graded.extend(entry["id"] for entry in entries)
        return []

    generate = FakeGenerator(lambda request: "I would rather describe the algorithm in prose.")
    e1.run(run_dir, FIXTURE, generate, grade, ceiling_usd=10.0, rounds=1)

    first = [row for row in rows(run_dir) if row["round"] == 0]
    assert [row["class"] for row in first] == ["no-body", "no-body"]
    assert all(row["reason"] == "no fenced code block" for row in first)
    assert all(row["text"] for row in first)  # the model's text is kept whole
    assert graded == []

    later = [request for request in requests_of(run_dir) if request["round"] == 1]
    assert later and all(
        request["messages"][-1]["content"] == f"Your reply had no C code block defining `{cell.name}`."
        for request in later
    )


def test_the_probe_is_scored_into_its_own_file_and_never_into_the_rows(tmp_path, lattice):
    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-2",))
    expected = [r for r in requests_of(run_dir) if r["mode"] == "complete"][0]["expected"]
    generate = FakeGenerator(lambda request: expected if request["mode"] == "complete" else fenced(_wrong(lattice, cell)))
    e1.run(run_dir, FIXTURE, generate, fake_grade(golds(lattice)), ceiling_usd=10.0)

    probes = [json.loads(line) for line in (run_dir / e1.GMEM).read_text(encoding="utf-8").splitlines()]
    assert [(probe["cell"], probe["score"], probe["label"]) for probe in probes] == [(cell.id, 1.0, "memorised")]
    assert all(row["cell"] == cell.id and "gmem" not in row["id"] for row in rows(run_dir))


def test_a_row_keeps_the_text_the_extract_and_the_result_with_the_diagnostics_cut(tmp_path, lattice):
    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-2",))
    generate = FakeGenerator(lambda request: fenced(_wrong(lattice, cell)))
    e1.run(run_dir, FIXTURE, generate, fake_grade(golds(lattice)), ceiling_usd=10.0)

    row = rows(run_dir)[0]
    assert row["text"] == fenced(_wrong(lattice, cell))  # the model's whole text, prose and fences included
    assert row["extract"] == {"body": WRONG_BODY, "reason": None, "block": 1}
    assert len(row["grade"]["diagnostics"]) == 20  # the grader offered thirty
    assert row["invented"] == [{"name": "_mm256_nope_ps", "bucket": "intrinsic"}]
    assert row["reg"] is True
    assert (row["tokens_in"], row["tokens_out"], row["finish_reason"]) == (100, 20, "stop")


def test_a_second_run_sends_nothing(tmp_path, lattice):
    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-0", "C-2"))
    generate = FakeGenerator(lambda request: fenced(prompts.definition(lattice, cell)))
    first = e1.run(run_dir, FIXTURE, generate, fake_grade(golds(lattice)), ceiling_usd=10.0)
    made = len(generate.calls)

    again = e1.run(run_dir, FIXTURE, generate, fake_grade(golds(lattice)), ceiling_usd=10.0)
    assert len(generate.calls) == made
    assert again == first


def test_a_paid_round_whose_grading_fails_is_answered_from_disk_on_resume(tmp_path, lattice):
    """Session `66c5`'s review: the completions are written before grading, so a failed grade costs one call."""
    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-2",))
    generate = FakeGenerator(lambda request: fenced(prompts.definition(lattice, cell)), cost=0.25)

    def broken(entries):
        raise e1.GradeFailed("the image exited 125")

    with pytest.raises(e1.GradeFailed):
        e1.run(run_dir, FIXTURE, generate, broken, ceiling_usd=10.0)
    assert len(generate.calls) == 1
    assert e1.spent(run_dir) == 0.25
    assert len((run_dir / e1.COMPLETIONS).read_text(encoding="utf-8").splitlines()) == 3  # greedy, a sample, the probe
    assert not (run_dir / e1.ROWS).exists()

    e1.run(run_dir, FIXTURE, generate, fake_grade(golds(lattice)), ceiling_usd=10.0)
    assert len(generate.calls) == 1
    assert e1.spent(run_dir) == 0.25
    assert [row["class"] for row in rows(run_dir)] == ["pass", "pass"]


def test_a_body_the_grader_does_not_answer_is_refused_and_no_row_is_written(tmp_path, lattice):
    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-0",))
    generate = FakeGenerator(lambda request: fenced(prompts.definition(lattice, cell)))
    graded = fake_grade(golds(lattice))

    with pytest.raises(e1.GradeFailed):
        e1.run(run_dir, FIXTURE, generate, lambda entries: graded(entries)[1:], ceiling_usd=10.0)
    assert not (run_dir / e1.ROWS).exists()


def test_the_modal_generator_keeps_its_files_and_the_call_record_never_overwrites_the_completions(tmp_path, monkeypatch):
    """E1-g's first paid call was lost: the record's `completions` count overwrote the list, and the files were
    in a temporary directory. The script is stood in for by a fake `subprocess.run` that writes what it would."""

    def fake_run(argv, capture_output, text):
        out = Path(argv[argv.index("--out") + 1])
        out.write_text(json.dumps({"id": "a|C-0|0|0", "text": "x", "tokens_in": 1, "tokens_out": 1}) + "\n")
        Path(argv[argv.index("--call") + 1]).write_text(json.dumps({"completions": 1, "cost": 0.5, "seconds": 3.0}))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(e1.subprocess, "run", fake_run)
    generate = e1.modal_generator("Qwen/Qwen2.5-Coder-7B-Instruct", tmp_path / "modal_e1.py", keep=tmp_path / "calls")
    answer = generate([{"id": "a|C-0|0|0"}])
    assert [row["id"] for row in answer["completions"]] == ["a|C-0|0|0"]
    assert answer["cost"] == 0.5
    generate([{"id": "a|C-0|0|0"}])
    kept = sorted(p.name for p in (tmp_path / "calls").iterdir())
    assert kept == ["call-0001", "call-0002"]
    assert (tmp_path / "calls" / "call-0001" / "completions.jsonl").exists()


def test_a_target_that_moved_since_the_plan_is_refused_before_anything_is_sent(tmp_path, lattice, monkeypatch):
    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-2",))
    assert json.loads((run_dir / e1.META).read_text())["target_sha"]  # the fixture rides in a checkout

    generate = FakeGenerator(lambda request: fenced(prompts.definition(lattice, cell)))
    monkeypatch.setattr(e1, "head", lambda target: "0" * 40)
    with pytest.raises(e1.TargetMoved):
        e1.run(run_dir, FIXTURE, generate, fake_grade(golds(lattice)), ceiling_usd=10.0)
    assert generate.calls == []


def test_a_plan_with_no_sha_has_nothing_to_check(tmp_path, lattice):
    cell = lattice.get("avx2/int8/dot")
    requests = e1.plan(lattice, [cell], ("C-2",), "M", k=1)
    run_dir = e1.write_plan(tmp_path / "run", requests, e1.meta("M", arms=("C-2",), cells=[cell], k=1))
    assert json.loads((run_dir / e1.META).read_text())["target_sha"] is None
    generate = FakeGenerator(lambda request: fenced(prompts.definition(lattice, cell)))
    e1.run(run_dir, FIXTURE, generate, fake_grade(golds(lattice)), ceiling_usd=10.0)
    assert [row["class"] for row in rows(run_dir)] == ["pass", "pass"]


# MARK: - the ceiling -


def test_the_first_call_is_refused_when_its_estimate_alone_passes_the_ceiling(tmp_path, lattice):
    run_dir = make_run(tmp_path, lattice, ["avx2/int8/dot"], ("C-0",))
    generate = FakeGenerator(lambda request: "")
    with pytest.raises(e1.CeilingReached):
        e1.run(run_dir, FIXTURE, generate, fake_grade({}), ceiling_usd=0.0)
    assert generate.calls == []
    assert not (run_dir / e1.ROWS).exists()


def test_a_later_call_is_refused_against_the_spend_already_recorded(tmp_path, lattice):
    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-0",))
    generate = FakeGenerator(lambda request: fenced(_wrong(lattice, cell)), cost=1.0)
    with pytest.raises(e1.CeilingReached):
        e1.run(run_dir, FIXTURE, generate, fake_grade(golds(lattice)), ceiling_usd=1.0)
    assert len(generate.calls) == 1  # round 0 ran; round 1 was never sent
    assert e1.spent(run_dir) == 1.0
    assert {row["round"] for row in rows(run_dir)} == {0}


def test_a_generator_that_reports_no_cost_has_its_estimate_recorded_as_one(tmp_path, lattice):
    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-2",))

    def generate(requests):
        return [{"id": request["id"], "text": fenced(_wrong(lattice, cell)), "finish_reason": "stop"} for request in requests]

    e1.run(run_dir, FIXTURE, generate, fake_grade(golds(lattice)), ceiling_usd=10.0)
    call = [json.loads(line) for line in (run_dir / e1.CALLS).read_text(encoding="utf-8").splitlines()][0]
    assert call["cost_source"] == "estimated"
    assert call["cost"] == call["estimate"]["usd"] > 0
    assert e1.spent(run_dir) > 0


def test_the_estimate_runs_high_on_every_requests_whole_max_tokens(lattice):
    made = e1.plan(lattice, ["avx2/int8/dot"], ("C-0",), "Qwen/Qwen2.5-Coder-7B-Instruct", k=1)
    guess = e1.estimate("Qwen/Qwen2.5-Coder-7B-Instruct", made)
    assert guess["tokens_out"] == 2 * e1.MAX_TOKENS + e1.GMEM_MAX_TOKENS
    assert guess["tokens_in"] == int(sum(e1.prompt_chars(request) for request in made) / e1.CHARS_PER_TOKEN)
    assert guess["usd"] > 0
    # a model the table does not name still gets an estimate rather than a free pass
    assert e1.estimate("nobody/nothing", made)["usd"] > 0


# MARK: - the generators a caller can inject -


def test_a_replay_answers_from_the_file_and_refuses_a_request_it_has_no_row_for(tmp_path, lattice):
    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-2",))
    recorded = tmp_path / "completions.jsonl"
    recorded.write_text(
        "".join(
            json.dumps({"id": request["id"], "text": fenced(prompts.definition(lattice, cell))}) + "\n"
            for request in requests_of(run_dir)
        ),
        encoding="utf-8",
    )
    e1.run(run_dir, FIXTURE, e1.replay_generator(recorded), fake_grade(golds(lattice)), ceiling_usd=10.0)
    assert [row["class"] for row in rows(run_dir)] == ["pass", "pass"]
    assert e1.spent(run_dir) == 0.0

    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(e1.MissingCompletion):
        e1.replay_generator(empty)([{"id": "x"}])


def test_the_default_grader_is_the_images_plan_and_not_a_host_compile(monkeypatch):
    from lattice import run as sandbox

    seen = {}

    def fake_run_plan(plan, **kwargs):
        seen["plan"] = plan
        raise e1.GradeFailed("stopped before podman")

    monkeypatch.setattr(sandbox, "run_plan", fake_run_plan)
    with pytest.raises(e1.GradeFailed):
        e1.default_grade(FIXTURE, "hobbes-session:local")([{"id": "x", "cell": "avx2/int8/dot", "body": "{}"}])

    assert seen["plan"][:2] == ["podman", "run"]
    assert "hobbes-session:local" in seen["plan"]
    assert seen["plan"][-8:] == [
        "grade", "/target", "/work/manifest.json", "--out", "/work/results.jsonl", "--work", "/work/run", "--here",
    ]
    assert e1.default_grade(FIXTURE)([]) == []  # an empty round spawns nothing


# MARK: - end to end, with the real graders -


@needs_clang
def test_a_fenced_gold_grades_pass_end_to_end(tmp_path, lattice):
    from lattice import grade as grade_of

    cell = lattice.get("avx2/int8/dot")
    run_dir = make_run(tmp_path, lattice, [cell], ("C-0",), k=1)
    generate = FakeGenerator(lambda request: fenced(prompts.definition(lattice, cell)))

    def grade(entries):
        return grade_of.grade(FIXTURE, entries, tmp_path / "work", allow_host=True)

    e1.run(run_dir, FIXTURE, generate, grade, ceiling_usd=10.0)
    graded = rows(run_dir)
    assert [row["class"] for row in graded] == ["pass", "pass"]
    assert all(row["reg"] is True for row in graded)
    assert {row["round"] for row in graded} == {0}


# MARK: - the Modal script, read and never imported -


def test_the_modal_script_pins_both_models_and_the_vllm_version():
    tree = ast.parse(MODAL.read_text(encoding="utf-8"))
    values = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    models = ast.literal_eval(values["MODELS"])
    assert sorted(models) == ["Qwen/Qwen2.5-Coder-7B-Instruct", "allenai/Olmo-3-7B-Instruct"]
    assert all(row["gpu"] == "A10G" and row["max_model_len"] == 16384 for row in models.values())
    assert ast.literal_eval(values["VLLM"]) == "0.27.1"
    assert ast.literal_eval(values["APP"]) == "hobbes-e1"


def test_the_package_never_imports_modal():
    source = (Path(__file__).parents[1] / "src" / "lattice").glob("*.py")
    for module in source:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(name.name != "modal" for name in node.names), module.name
            if isinstance(node, ast.ImportFrom):
                assert node.module != "modal", module.name


#: A body `holes` would write and G-diff would fail: balanced braces, and not this cell's gold.
WRONG_BODY = "{\n    return -1.0f;\n}"


def _wrong(lattice, cell):
    """A whole definition with the wrong body — `extract` wants a definition, not a bare body."""
    return f"{cell.signature}\n{WRONG_BODY}"
