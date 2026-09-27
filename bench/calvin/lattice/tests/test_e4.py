"""E4's runner: the units and their order, the bare skeleton, the arms, the plan, and the file level.

No model appears anywhere here. The generator and the grader are injected, as in `test_e1.py`, so the
whole loop is driven by fakes over the fixture's own bytes; the one test that really compiles asks the
real grader with `allow_host=True` — this package's fixture, which is not a target checkout (`run.py`).

Two properties have the most riding on them. **No held-out unit's gold body reaches any prompt**: at L1
every definition of the file is a hole, so a single sibling body left in a skeleton would hand the student
the pattern S-2 exists to measure, and the run would read as S-2 under S-0's name. And **S-2o carries the
student's own bodies and never gold**: its shots come off `rows.jsonl`, so the test that matters is the one
that reads a later unit's prompt back against the *replay's* text and not against the target's.
"""

import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

import pytest

from lattice import available as available_of
from lattice import e1, e4, facts, families as families_of, grade as grade_of, holes, prompts, task
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


def make_run(tmp_path, lattice, arms=("S-0",), *, isa="avx2", k=0, ledger=None, model="M", fields=None):
    """`e4.plan` plus `e4.meta`, written into a fresh run directory."""
    requests = e4.plan(lattice, isa, arms, model, ledger, k=k, fields=fields)
    record = e4.meta(
        lattice, isa, requests, model, arms=arms, k=k, target=FIXTURE, facts=ledger,
        parser=e4.parser_meta(tmp_path / "run"),
    )
    return e1.write_plan(tmp_path / "run", requests, record)


def marked(body, name):
    """A body that is the gold's text with one statement of the student's own put into it.

    It is balanced braces, so `extract` and `holes` take it; it carries a **token** the gold does not, so
    "this is the student's text" and "this is the target's" can be told apart; and it is not a comment,
    which `mask` would blank and the token check would then miss.
    """
    return body.replace("{", "{\n    /* mine */\n    (void)mine_" + name + ";", 1)


def own_replay(tmp_path, lattice, isa, arm, k, bodies):
    """A completions file for **every** (unit, sample) of one arm, whether the plan has written it yet.

    S-2o's later waves are requests `run` builds as the rows come in, so a replay cannot be made from
    `requests.jsonl`. It does not need to be: a request id is `<unit>|<arm>|<sample>|0` and the ids are
    therefore known before the waves are.
    """
    recorded = tmp_path / f"{arm}-completions.jsonl"
    rows = []
    for unit in e4.units(lattice, isa):
        text = f"```c\n{unit.signature}\n{bodies[unit.name]}\n```"
        for sample in range(0, k + 1):
            rows.append({"id": e1.request_id(unit.name, arm, sample, 0), "text": text})
    recorded.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return recorded


def pass_grade(failing=()):
    """A grader that passes every entry of either E4 form but the units named, which read `wrong`."""
    failing = set(failing)

    def grade(entries):
        return [
            {
                "id": entry["id"],
                "class": "wrong" if entry.get("unit") in failing else "pass",
                "reg": True,
            }
            for entry in entries
        ]

    return grade


def parse_replay(tmp_path, lattice, answers=None, *, isa="avx2", model="P"):
    """A completions file answering every parse request, `answers` overriding a unit's raw text."""
    answers = dict(answers or {})
    recorded = tmp_path / "parse-completions.jsonl"
    rows = []
    for request in e4.parse_requests(lattice, isa, model):
        unit = request["unit"]
        text = answers.get(
            unit,
            json.dumps({"contract": f"{unit} answers its own question.", "edge_cases": ["n is 0."]}),
        )
        rows.append({"id": request["id"], "text": text})
    recorded.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return recorded


def parse_into(tmp_path, run_dir, lattice, answers=None, *, ledger=None, ceiling=1.0, cost=None):
    """Run the parse step over a replay, and return `read_fields`'s map. Nothing is spent unless *cost*."""
    replay = e1.replay_generator(parse_replay(tmp_path, lattice, answers))
    generate = replay if cost is None else (lambda requests: {**replay(requests), "cost": cost})
    e4.parse(run_dir, lattice, "avx2", generate, "P", ceiling_usd=ceiling, facts=ledger)
    return e4.read_fields(run_dir)


def rows_of(run_dir):
    return [json.loads(line) for line in (run_dir / e1.ROWS).read_text(encoding="utf-8").splitlines() if line.strip()]


#: The prefixes each native file may **not** write, for the hand-built availability tables below.
_WIDER = {"sse2": ("_mm256_", "_mm512_"), "avx2": ("_mm512_",), "avx512": ()}


def available_for(lattice, isa="avx2"):
    """A **hand-built** availability record for one file, in `available.load`'s shape.

    Not the compiler's answer — that is `test_available.py`'s, against the three real `clang -E -dD`
    excerpts. This is the stand-in every S-3h test reads, and its rule is one line: every intrinsic any of
    the three native files writes is available in *isa*'s file **unless its prefix is wider than that
    file's**, so `_mm512_reduce_add_ps` is unavailable on avx2 and `_mm_add_ps` is available. It has the
    shape of the real answer at the grain these tests are about, and none of them depends on its edges.
    """
    names = {}
    for other in NATIVE:
        for name in re.findall(r"\b(_mm\w*|_cvt\w*)\s*\(", lattice.sources[other].text):
            names.setdefault(
                name,
                {"available": not name.startswith(_WIDER[isa] or ("\0",)), "needs": [], "header": "hand-built"},
            )
    return {
        isa: {
            "isa": isa,
            "file": f"src/distance-{isa}.c",
            "flags": ["-O2", "-Isrc", "-Ilibs"],
            "clang": "hand-built, not a compiler",
            "target_sha": None,
            "names": names,
        }
    }


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


def fields_for(lattice, isa="avx2", answers=None):
    """A parser row per unit, as `read_fields` returns them, with no run directory in the way."""
    answers = dict(answers or {})
    rows = {}
    for unit in e4.units(lattice, isa):
        if unit.name in answers:
            rows[unit.name] = {"unit": unit.name, "parsed": False, "raw": answers[unit.name],
                               "contract": None, "edge_cases": None, "reason": answers[unit.name]}
            continue
        rows[unit.name] = {
            "unit": unit.name,
            "parsed": True,
            "contract": f"{unit.name} answers its own question.",
            "edge_cases": ["n is 0.", "the pointers may be unaligned."],
            "raw": "{}",
            "reason": None,
        }
    return rows


def test_no_held_out_gold_reaches_any_prompt(lattice, ledger):
    """Every arm, with S-2o carrying what the run carries at the start: nothing written yet.

    S-2o's own shots come off `rows.jsonl`, so its own no-gold property is the one two tests below —
    the shot is read back against the *replay's* text. This one holds the skeleton and the served shots.
    """
    units = e4.units(lattice, "avx2")
    fields = fields_for(lattice)
    table = available_for(lattice)
    bodies = {unit.name: tokens(holes.gold_body(lattice.sources["avx2"].text, unit)) for unit in units}
    for unit in units:
        for arm in e4.ARMS:
            written = tokens(
                "".join(
                    turn["content"]
                    for turn in e4.messages(lattice, "avx2", unit, arm, ledger, fields, available=table)
                )
            )
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
    fields = fields_for(lattice)
    table = available_for(lattice)
    said = {
        arm: e4.messages(lattice, "avx2", unit, arm, ledger, fields, available=table)[1]["content"]
        for arm in e4.ARMS
    }
    skeleton = e4.skeleton(lattice, "avx2", unit)
    assert all(skeleton in text for text in said.values())
    assert all(text.endswith(e4.INSTRUCTION) for text in said.values())
    for arm, text in said.items():
        assert ("The same function in the instruction sets that stay" in text) == (arm in e4.SHOT_ARMS)
        assert ("read from the project's graph and the compiler's own key" in text) == (arm in e4.FACTS_ARMS)
        assert ("What this function must do:" in text) == (arm in e4.FIELD_ARMS)
        assert ("own shots" in text or "as you wrote it" in text) == (arm in e4.OWN_ARMS)
        assert ("What this file can use, of what the examples above use" in text) == (
            arm in e4.FACTS_ISA_ARMS
        )
    # S-5 is S-3 and the parser's words, and nothing else: the one is the other plus one section
    row = fields[unit.name]
    section = "What this function must do:\n\n" + "\n".join(
        [row["contract"], *(f"- {case}" for case in row["edge_cases"])]
    )
    assert said["S-5"].replace(f"{section}\n\n", "") == said["S-3"]
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


def test_an_arm_that_is_not_e4s_is_refused_as_a_typo(lattice, ledger):
    unit = next(u for u in e4.units(lattice, "avx2") if u.kind == "cell")
    assert e4.ARMS == ("S-0", "S-2", "S-2h", "S-3h", "S-2o", "S-3", "S-5")
    with pytest.raises(prompts.UnknownArm):
        e4.context(lattice, "avx2", unit, "C-2", ledger)


def test_s5_with_no_parser_fields_is_refused_and_never_filled_empty(lattice, ledger):
    """An S-5 with no fields is S-3 wearing S-5's name, exactly as an empty S-3 would be S-2's."""
    unit = next(u for u in e4.units(lattice, "avx2") if u.kind == "cell")
    with pytest.raises(e4.NoFields) as refused:
        e4.context(lattice, "avx2", unit, "S-5", ledger)
    assert "never filled empty" in str(refused.value)
    # and a set of fields that does not cover this unit is the same refusal, naming it
    without = {name: row for name, row in fields_for(lattice).items() if name != unit.name}
    with pytest.raises(e4.NoFields) as uncovered:
        e4.context(lattice, "avx2", unit, "S-5", ledger, without)
    assert unit.name in str(uncovered.value)
    with pytest.raises(e4.NoFields):
        e4.plan(lattice, "avx2", ("S-5",), "M", ledger, k=0, fields=without)


# MARK: - S-2h: the helper's name family (rule W) -

#: The native files, and the pre-registration's own figures for rule W over their helpers (D-11 a): 26 of
#: 31 helpers in 11 families with none ambiguous, and these five with no member in any other native file.
NATIVE = ("sse2", "avx2", "avx512")
UNPAIRED = {
    # `mm_abs_pd` is one of a kind, and no other file's helper loads an f16 lane pair
    "sse2": ["mm_abs_pd", "f16x4_to_f32x4_loadu"],
    # `hsum512_epu32` differs in `epu`, so neither of these two is its family
    "avx2": ["hsum256_epi64", "hsum256_epi32"],
    "avx512": ["hsum512_epu32"],
}


def helpers_of(lattice, isa):
    """That file's non-cell helper units, in the units' own order."""
    return [unit for unit in e4.units(lattice, isa) if unit.kind == "helper"]


def token_run(written, gold):
    """Whether *written*'s tokens hold *gold*'s as a contiguous run — the no-gold check, done once."""
    length = len(gold)
    return any(written[at : at + length] == gold for at in range(len(written) - length + 1))


def test_rule_w_reproduces_the_pre_registration_on_the_real_helpers(lattice):
    """The figures D-11 was taken on, recomputed from the fixture's own three native files.

    The fixture carries the three files' helpers in full, so these are the target's numbers: **26 of 31**
    with a sibling, in **11 families**, **0 ambiguous**. E3's rule as worded reaches 3 of them, which is
    why W is a rule of its own — the last two lines hold that difference, since `families` is a port and
    the reason it is not edited is that it is the draw's rule and not this one.
    """
    families = {}
    paired, ambiguous = [], []
    for isa in NATIVE:
        for unit in helpers_of(lattice, isa):
            rows = e4.helper_siblings(lattice, isa, unit)
            assert [row.isa for row in rows] == [other for other in NATIVE if other != isa]
            if any(row.reason == e4.AMBIGUOUS for row in rows):
                ambiguous.append(f"{isa}:{unit.name}")
            if any(row.shot for row in rows):
                paired.append(f"{isa}:{unit.name}")
                families.setdefault(e4.family_key(unit.name), []).append(f"{isa}:{unit.name}")
            else:
                assert unit.name in UNPAIRED[isa], f"{isa}:{unit.name} was expected to have a sibling"
                assert all(row.reason == e4.NO_SIBLING for row in rows)

    everything = [f"{isa}:{u.name}" for isa in NATIVE for u in helpers_of(lattice, isa)]
    assert len(everything) == 31 and len(paired) == 26 and ambiguous == []
    assert sorted(set(everything) - set(paired)) == sorted(
        f"{isa}:{name}" for isa, names in UNPAIRED.items() for name in names
    )
    assert len(families) == 11 and sum(len(members) for members in families.values()) == 26

    # E3's rule as worded pairs only the three `popcount_*`, which is the record D-11 corrected
    members = [{"name": unit.name} for isa in NATIVE for unit in helpers_of(lattice, isa)]
    by_isa_token = {
        name
        for family in families_of.isa_families(members)
        for name in (member["name"] for member in family["members"])
    }
    assert sorted(by_isa_token) == ["popcount_avx2", "popcount_avx512", "popcount_sse2"]


def test_the_families_are_the_pre_registrations_own_examples(lattice):
    """Four of the eleven, each named in D-11's page, read back off the fixture."""
    shots = {}
    for isa in NATIVE:
        for unit in helpers_of(lattice, isa):
            shots[f"{isa}:{unit.name}"] = [
                f"{row.isa}:{row.shot.source}" for row in e4.helper_siblings(lattice, isa, unit) if row.shot
            ]
    assert shots["avx2:hsum256_ps"] == ["sse2:hsum128_ps", "avx512:hsum512_ps"]
    assert shots["avx512:dot_epu8_512"] == ["avx2:dot_epu8"]
    assert shots["avx2:bf16x8_to_f32x8_loadu"] == [
        "sse2:bf16x4_to_f32x4_loadu",
        "avx512:bf16x16_to_f32x16_loadu",
    ]
    assert shots["avx2:block_has_l2_inf_mismatch_bf16_8"] == ["avx512:block_has_l2_inf_mismatch_bf16_16"]
    assert shots["avx2:popcount_avx2"] == ["sse2:popcount_sse2", "avx512:popcount_avx512"]


def test_the_family_key_abstracts_a_width_and_never_an_element_type():
    """Rule W, step by step — and the two pairs it must **not** join, which is what makes it a rule."""
    # 1: a trailing all-digit token goes, where the name has more than one token
    assert e4.family_key("dot_epu8_512") == e4.family_key("dot_epu8") == ("dot", "epu8")
    assert e4.family_key("block_has_l2_inf_mismatch_8") == ("block", "has", "l2", "inf", "mismatch")
    # 2: an ISA token is any ISA
    assert e4.family_key("popcount_sse2") == e4.family_key("popcount_avx512") == ("popcount", e4.ANY_ISA)
    # 3: a vector width inside a token, and a one-token name keeps its own shape around it
    assert e4.family_key("hsum256_ps") == (f"hsum{e4.WIDTH}", "ps")
    assert e4.family_key("hsum128d") == (f"hsum{e4.WIDTH}d",)
    # 4: a lane count
    assert e4.family_key("bf16x8_to_f32x8_loadu") == (f"bf16x{e4.WIDTH}", "to", f"f32x{e4.WIDTH}", "loadu")

    # an **element** width is not a vector width: `epi8` and `epi16` stay two families
    assert e4.family_key("dot_epi8") != e4.family_key("dot_epi16")
    assert e4.family_key("bf16x8_to_f32x8_loadu") != e4.family_key("f16x4_to_f32x4_loadu")
    # and neither is a different element sign or width in the same position
    assert e4.family_key("hsum256_epi32") != e4.family_key("hsum512_epu32")
    assert e4.family_key("hsum256_epi64") != e4.family_key("hsum512_epi32_signed")


def ambiguous_target(tmp_path):
    """A target whose `sse2` file holds **two** members of one family, which `avx2`'s helper matches.

    `hsum128_ps` and `hsum512_ps` are one family under rule W (`hsum# ps`), so a file defining both answers
    `hsum256_ps` with two candidates and no shot. The real target has no such file — 0 ambiguous over its
    31 helpers — so the case is built rather than waited for.
    """
    root = tmp_path / "ambiguous"
    (root / "src").mkdir(parents=True)
    for isa, helpers in (("avx2", ("hsum256_ps",)), ("sse2", ("hsum128_ps", "hsum512_ps"))):
        lines = ["#include <stddef.h>", "extern distance_function_t dispatch_distance_table[8][8];"]
        lines += [f"static inline float {name} (float v) {{ return v + 1.0f; }}" for name in helpers]
        lines.append(
            f"float float32_distance_dot_{isa} (const void *v1, const void *v2, int n)\n"
            f"{{ (void)v2; (void)n; return {helpers[0]}(*(const float *)v1); }}"
        )
        lines.append(
            f"int init_distance_functions_{isa} (void)\n"
            "{ dispatch_distance_table[VECTOR_DISTANCE_DOT][VECTOR_TYPE_F32] = "
            f"float32_distance_dot_{isa}; return 1; }}"
        )
        (root / "src" / f"distance-{isa}.c").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return build(root)


def test_an_ambiguous_family_serves_no_shot_and_the_request_names_both(tmp_path):
    lattice = ambiguous_target(tmp_path)
    unit = next(u for u in e4.units(lattice, "avx2") if u.name == "hsum256_ps")
    assert e4.family_key("hsum128_ps") == e4.family_key("hsum512_ps") == e4.family_key(unit.name)

    rows = e4.helper_siblings(lattice, "avx2", unit)
    assert rows == [e4.Sibling("sse2", None, e4.AMBIGUOUS, ("hsum128_ps", "hsum512_ps"))]
    data = e4.context(lattice, "avx2", unit, "S-2h")
    assert data["shots"] == []
    assert data["shots_note"] == "shots: none (sse2 — ambiguous: hsum128_ps, hsum512_ps)"
    text = e4.messages(lattice, "avx2", unit, "S-2h")[1]["content"]
    assert "ambiguous: hsum128_ps, hsum512_ps" in text
    assert "return v + 1.0f;" not in text  # neither candidate's body is carried; picking one is a new rule


def test_a_helpers_s2h_shots_are_its_name_family_in_the_files_that_stay(lattice):
    unit = next(u for u in e4.units(lattice, "avx2") if u.name == "hsum256_ps")
    assert e4.shots(lattice, "avx2", unit) == []  # S-2 has nothing to cross for a helper: that is the gap

    data = e4.context(lattice, "avx2", unit, "S-2h")
    assert [(row["isa"], row["from"]) for row in data["shots"]] == [
        ("sse2", "hsum128_ps"),
        ("avx512", "hsum512_ps"),
    ]
    assert data["shots_note"] is None  # every file that stays answered, so there is nothing to say
    text = e4.messages(lattice, "avx2", unit, "S-2h")[1]["content"]
    assert "matched by name, not by the grid" in text
    assert "/* sse2: hsum128_ps */" in text and "/* avx512: hsum512_ps */" in text
    sibling = next(u for u in e4.units(lattice, "sse2") if u.name == "hsum128_ps")
    assert definition(lattice, "sse2", sibling) in text  # the whole definition, as that file writes it


def test_a_helper_with_no_sibling_carries_the_pre_registered_note_and_never_s2s(lattice):
    unit = next(u for u in e4.units(lattice, "avx2") if u.name == "hsum256_epi32")
    data = e4.context(lattice, "avx2", unit, "S-2h")
    assert data["shots"] == []
    assert e4.NO_SIBLING == "no name-family sibling"  # the pre-registration's own wording
    assert data["shots_note"] == (
        "shots: none (sse2 — no name-family sibling; avx512 — no name-family sibling)"
    )
    text = e4.messages(lattice, "avx2", unit, "S-2h")[1]["content"]
    assert e4.NO_SIBLING in text
    # and it is never S-2's sentence: "none (helper)" would say the grid had nothing, which is not the fact
    assert e4.NO_SHOTS["helper"] not in text
    assert e4.NO_SHOTS["helper"] in e4.messages(lattice, "avx2", unit, "S-2")[1]["content"]


def test_s2h_is_s2_byte_for_byte_for_every_cell_and_the_init(lattice):
    """The arm differs on the helpers and nowhere else, which is why the comparison is read on them."""
    ordered = e4.units(lattice, "avx2")
    for unit in ordered:
        if unit.kind == "helper":
            continue
        one = e4.context(lattice, "avx2", unit, "S-2")
        other = e4.context(lattice, "avx2", unit, "S-2h")
        assert other == {**one, "arm": "S-2h"}  # the arm's name is the whole of the difference
        assert e4.messages(lattice, "avx2", unit, "S-2h") == e4.messages(lattice, "avx2", unit, "S-2")

    moved = {
        unit.name
        for unit in ordered
        if e4.context(lattice, "avx2", unit, "S-2")["shots"]
        != e4.context(lattice, "avx2", unit, "S-2h")["shots"]
    }
    assert moved == {u.name for u in helpers_of(lattice, "avx2")} - set(UNPAIRED["avx2"])

    # the request is the same request under another name: one id, one seed, and the same bytes
    unit = next(u for u in ordered if u.kind == "cell")
    made = {
        arm: e4.requests_for(lattice, "avx2", unit, arm, "M", 0)[0] for arm in ("S-2", "S-2h")
    }
    assert made["S-2h"]["messages"] == made["S-2"]["messages"]
    assert made["S-2h"]["shots"] == made["S-2"]["shots"]
    assert made["S-2h"]["id"] != made["S-2"]["id"]
    assert made["S-2h"]["params"]["seed"] == e1.seed("M", unit.name, "S-2h", 0, 0)
    assert made["S-2h"]["params"]["seed"] != made["S-2"]["params"]["seed"]


def test_no_gold_enters_an_s2h_helper_prompt_that_is_not_a_shot(lattice):
    """The skeleton is still bare, and of the files that stay only the family's own member is shown."""
    unit = next(u for u in e4.units(lattice, "avx2") if u.name == "hsum256_ps")
    written = tokens("".join(turn["content"] for turn in e4.messages(lattice, "avx2", unit, "S-2h")))

    for other in e4.units(lattice, "avx2"):
        if other.name == unit.name:
            continue
        gold = tokens(holes.gold_body(lattice.sources["avx2"].text, other))
        assert not token_run(written, gold), f"the held-out file's {other.name} is in the prompt"

    for isa in ("sse2", "avx512"):
        for other in e4.units(lattice, isa):
            gold = tokens(holes.gold_body(lattice.sources[isa].text, other))
            shown = other.kind == "helper" and e4.family_key(other.name) == e4.family_key(unit.name)
            assert token_run(written, gold) is shown, f"{isa}:{other.name}"


def test_the_registered_comparison_is_the_helper_units(lattice):
    assert e4.COMPARISONS == (
        ("S-0", "S-2", None),
        ("S-3", "S-5", None),
        ("S-2", "S-2h", "helper"),
        ("S-2h", "S-3h", None),
    )
    assert e4.FAMILY_ARMS == ("S-2h", "S-3h") and "S-2h" in e4.SHOT_ARMS
    # S-2h needs no ledger, no fields, no availability and no wave: it is planned whole, like S-2
    assert "S-2h" not in e4.FACTS_ARMS and "S-2h" not in e4.FIELD_ARMS and "S-2h" not in e4.OWN_ARMS
    assert "S-2h" not in e4.FACTS_ISA_ARMS
    made = e4.plan(lattice, "avx2", ("S-2h",), "M", k=0)
    assert len(made) == len(e4.units(lattice, "avx2"))
    assert {request["wave"] for request in made} == {0}


# MARK: - S-3h: what this file can use (D-12 a) -


def said(lattice, unit, arm, isa="avx2", table=None, **rest):
    """One (unit, arm)'s user turn."""
    return e4.messages(lattice, isa, unit, arm, available=table, **rest)[1]["content"]


def unit_of(lattice, name, isa="avx2"):
    return next(u for u in e4.units(lattice, isa) if u.name == name)


def block_of(lattice, name, isa="avx2", table=None):
    """One unit's S-3h block as data, and the lines the prompt carries for it."""
    unit = unit_of(lattice, name, isa)
    table = available_for(lattice, isa) if table is None else table
    data = e4.context(lattice, isa, unit, "S-3h", available=table)
    return data["available"], said(lattice, unit, "S-3h", isa, table)


def test_s3h_is_s2h_plus_one_block_and_nothing_else(lattice):
    """The arm is one variable apart: every unit's shots, note and skeleton are S-2h's byte for byte."""
    table = available_for(lattice)
    for unit in e4.units(lattice, "avx2"):
        family = e4.context(lattice, "avx2", unit, "S-2h")
        facts_isa = e4.context(lattice, "avx2", unit, "S-3h", available=table)
        assert facts_isa == {**family, "arm": "S-3h", "available": facts_isa["available"]}
        assert facts_isa["available"] is not None and family["available"] is None
        # and the prompt is S-2h's with exactly one section inserted, under the shots and their note
        block = e4._availability_section(facts_isa["available"])
        text = said(lattice, unit, "S-3h", table=table)
        assert text.replace(f"{block}\n\n", "") == said(lattice, unit, "S-2h")
        assert e4.INSTRUCTION not in block
        # and it sits after the shots and their note, and before the hole
        if facts_isa["shots"]:
            assert text.index("in the instruction sets that stay") < text.index(block)
        if facts_isa["shots_note"]:
            assert text.index(facts_isa["shots_note"]) < text.index(block)
        assert text.index(block) < text.index("The function to write:")


def test_the_blocks_intrinsics_are_the_shots_own_with_their_status_and_form(lattice):
    """`hsum256_ps`: five SSE names its sse2 sibling writes, and the one AVX-512 name that has no form."""
    found, text = block_of(lattice, "hsum256_ps")
    assert [row["name"] for row in found["intrinsics"]] == [
        "_mm_add_ps", "_mm_movehl_ps", "_mm_add_ss", "_mm_shuffle_ps", "_mm_cvtss_f32",
        "_mm512_reduce_add_ps",
    ]
    assert [row["name"] for row in found["intrinsics"] if row["available"]][-1] == "_mm_cvtss_f32"
    wider = next(row for row in found["intrinsics"] if row["name"] == "_mm512_reduce_add_ps")
    assert wider == {"name": "_mm512_reduce_add_ps", "available": False, "form": None}

    assert "available here: `_mm_add_ps`, `_mm_movehl_ps`" in text
    assert "`_mm512_reduce_add_ps` is not available in this file, and no same-named form is" in text
    assert "What this file can use, of what the examples above use" in text


def test_an_unavailable_intrinsic_with_a_form_says_what_it_is_here(lattice):
    """`sqdiff_epu8`: every `_mm512_` name of its avx512 sibling renames to one this file has (rule R)."""
    found, text = block_of(lattice, "sqdiff_epu8")
    assert [(row["name"], row["form"]) for row in found["intrinsics"]] == [
        ("_mm512_unpacklo_epi8", "_mm256_unpacklo_epi8"),
        ("_mm512_setzero_si512", "_mm256_setzero_si256"),
        ("_mm512_unpackhi_epi8", "_mm256_unpackhi_epi8"),
        ("_mm512_add_epi32", "_mm256_add_epi32"),
        ("_mm512_madd_epi16", "_mm256_madd_epi16"),
    ]
    assert not any(row["available"] for row in found["intrinsics"])
    assert "available here:" not in text  # none of them is, so the line is omitted rather than empty
    assert "`_mm512_setzero_si512` is not available in this file; its form here: `_mm256_setzero_si256`" in text


def test_a_name_the_other_file_owns_is_answered_by_rule_ws_family(lattice):
    """`sqdiff_epu8`'s avx512 shot calls `abs_diff_epu8_512`, and this file's is `abs_diff_epu8` (D-12)."""
    found, text = block_of(lattice, "sqdiff_epu8")
    theirs = {row["name"]: row for row in found["names"]}
    assert theirs["abs_diff_epu8_512"] == {
        "name": "abs_diff_epu8_512", "from": "avx512", "kind": "function",
        "mine": ["abs_diff_epu8"], "status": "one",
    }
    assert "`abs_diff_epu8_512` is the other file's own; this file's: `abs_diff_epu8`" in text
    # the shot's own name is answered the same way: this file's member of its family
    assert theirs["sqdiff_epu8_512"]["mine"] == ["sqdiff_epu8"]


def test_a_cells_block_names_the_helper_and_the_other_files_define(lattice):
    """`int8_distance_l2_impl_avx2`: its avx512 shot calls `sqdiff_epu8_512` (distance-avx512.c:281).

    `S8_TO_BIASED_U8_512` is that file's `#define` and not a function, so rule W has no family for it and
    the block says this file has no such definition — which is what the compiler would say too.
    """
    found, text = block_of(lattice, "int8_distance_l2_impl_avx2")
    theirs = {row["name"]: row for row in found["names"]}
    assert theirs["sqdiff_epu8_512"]["mine"] == ["sqdiff_epu8"]
    assert "`sqdiff_epu8_512` is the other file's own; this file's: `sqdiff_epu8`" in text

    assert theirs["S8_TO_BIASED_U8_512"]["kind"] == "define"
    assert theirs["S8_TO_BIASED_U8_512"] == {
        "name": "S8_TO_BIASED_U8_512", "from": "avx512", "kind": "define", "mine": [], "status": "none",
    }
    assert "`S8_TO_BIASED_U8_512` is the other file's own; this file has no such definition" in text


@pytest.mark.parametrize("isa", ["sse2", "avx512"])
def test_a_file_scope_static_object_of_the_other_file_is_named(lattice, isa):
    """`popcount_lut_bytes` is avx2's own array, and neither other file has one (the pre-reg's third form)."""
    assert e4.file_scope(lattice, "avx2")["popcount_lut_bytes"] == "object"
    assert "popcount_lut_bytes" not in e4.file_scope(lattice, isa)

    found, text = block_of(lattice, f"popcount_{isa}", isa)
    row = next(row for row in found["names"] if row["name"] == "popcount_lut_bytes")
    assert row == {
        "name": "popcount_lut_bytes", "from": "avx2", "kind": "object", "mine": [], "status": "none",
    }
    assert "`popcount_lut_bytes` is the other file's own; this file has no such definition" in text
    # and the sibling helper itself is answered by the family, which is this file's own popcount
    assert next(r for r in found["names"] if r["name"] == "popcount_avx2")["mine"] == [f"popcount_{isa}"]


def test_a_unit_with_no_shots_says_there_is_nothing_to_check(lattice):
    """`hsum256_epi64`'s family reaches nothing in either file that stays, so there is no block to state."""
    unit = unit_of(lattice, "hsum256_epi64")
    table = available_for(lattice)
    data = e4.context(lattice, "avx2", unit, "S-3h", available=table)
    assert data["shots"] == [] and data["available"] == {
        "shots": 0, "intrinsics": [], "names": [], "note": e4.NO_EXAMPLES,
    }
    text = said(lattice, unit, "S-3h", table=table)
    assert e4.NO_EXAMPLES in text and "What this file can use" not in text
    assert e4.NO_SIBLING in text  # S-2h's own note is still there, unchanged


def test_s3h_without_a_record_is_refused_and_never_filled_empty(lattice):
    """An empty availability table marks every intrinsic unavailable, so it is a refusal and not a default."""
    unit = unit_of(lattice, "hsum256_ps")
    with pytest.raises(e4.NoAvailability) as refused:
        e4.context(lattice, "avx2", unit, "S-3h")
    assert "never filled empty" in str(refused.value)

    # a record that covers another file is the same refusal, naming the one it does not cover
    with pytest.raises(e4.NoAvailability) as elsewhere:
        e4.context(lattice, "avx2", unit, "S-3h", available=available_for(lattice, "sse2"))
    assert "does not cover avx2" in str(elsewhere.value)
    with pytest.raises(e4.NoAvailability):
        e4.plan(lattice, "avx2", ("S-3h",), "M", k=0)


def test_the_request_records_the_blocks_data_and_not_only_its_text(lattice):
    """What the arm served is on the row: every name, its status, and the form it was offered."""
    unit = unit_of(lattice, "sqdiff_epu8")
    table = available_for(lattice)
    made = e4.requests_for(lattice, "avx2", unit, "S-3h", "M", 0, available=table)[0]
    assert made["available"] == e4.context(lattice, "avx2", unit, "S-3h", available=table)["available"]
    assert made["arm"] == "S-3h" and made["available"]["shots"] == 1
    # and S-2h's row carries none, which is how the two arms are told apart on the record
    assert e4.requests_for(lattice, "avx2", unit, "S-2h", "M", 0)[0]["available"] is None


def test_no_gold_enters_an_s3h_prompt_that_is_not_a_shot(lattice):
    """The block is names and statuses, never a body: the same property S-2h's prompt is held to."""
    table = available_for(lattice)
    for name in ("hsum256_ps", "sqdiff_epu8", "int8_distance_l2_impl_avx2"):
        unit = unit_of(lattice, name)
        shown = {row["from"] for row in e4.context(lattice, "avx2", unit, "S-3h", available=table)["shots"]}
        written = tokens(
            "".join(turn["content"] for turn in e4.messages(lattice, "avx2", unit, "S-3h", available=table))
        )
        for other in e4.units(lattice, "avx2"):
            if other.name == unit.name:
                continue
            gold = tokens(holes.gold_body(lattice.sources["avx2"].text, other))
            assert not token_run(written, gold), f"the held-out file's {other.name} is in S-3h's prompt"
        assert shown  # the shots are there; it is only the held-out file's bodies that are not


def test_the_meta_records_the_availability_the_plan_was_built_from(tmp_path, lattice):
    """A plan names the record it read: its digest, and per ISA the flags and the clang line that answered."""
    path = tmp_path / "available.json"
    path.write_text(json.dumps(available_for(lattice), indent=2), encoding="utf-8")
    table = available_of.load(path)
    requests = e4.plan(lattice, "avx2", ("S-3h",), "M", k=0, available=table)
    record = e4.meta(
        lattice, "avx2", requests, "M", arms=("S-3h",), k=0, target=FIXTURE,
        availability=available_of.record_meta(path),
    )
    block = record["available"]
    assert block["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert block["isas"]["avx2"]["flags"] == ["-O2", "-Isrc", "-Ilibs"]
    assert block["isas"]["avx2"]["clang"] == "hand-built, not a compiler"
    assert block["isas"]["avx2"]["available"] < block["isas"]["avx2"]["names"]
    # and a plan with no record says so rather than carrying an empty block
    assert e4.meta(lattice, "avx2", requests, "M", arms=("S-2h",), k=0)["available"] is None


# MARK: - the parser's fields (S-5) -


def test_the_parser_is_shown_no_body_of_any_definition_and_no_brace(lattice, ledger):
    """The one thing the parse step must never do (§5.2): the fields are words about a task, not a body.

    Two checks, one cheap and one exact. The cheap one is the brace: every C body has a `{`, and nothing
    this module writes into a parse prompt does — the JSON's shape is spelled out in words for that
    reason. The exact one is the token run: no definition of **any** of the lattice's files appears.
    """
    made = e4.parse_requests(lattice, "avx2", "P", ledger, api=None)
    assert [request["unit"] for request in made] == [u.name for u in e4.units(lattice, "avx2")]

    bodies = []
    for source in lattice.sources.values():
        for fn in source.scanned.functions:
            bodies.append((fn.name, tokens(holes.gold_body(source.text, fn))))
    for request in made:
        text = "".join(turn["content"] for turn in request["messages"])
        assert "{" not in text and "}" not in text, request["unit"]
        written = tokens(text)
        for name, gold in bodies:
            run = len(gold)
            assert not any(written[at : at + run] == gold for at in range(len(written) - run + 1)), (
                f"the parse request for {request['unit']} carries {name}'s body"
            )
    # and it is greedy, once per unit, at a limit with no room for a body in it
    assert {request["params"]["temperature"] for request in made} == {0.0}
    assert {request["params"]["max_tokens"] for request in made} == {e4.PARSE_MAX_TOKENS}


def test_the_parser_is_shown_the_api_doc_where_there_is_one_and_told_where_there_is_not(tmp_path, lattice):
    unit = next(u for u in e4.units(lattice, "avx2") if u.kind == "cell")
    assert e4.read_api(FIXTURE) is None  # the fixture is kernels only; the target carries API.md
    told = e4.parse_turns(e4.parse_context(lattice, "avx2", unit))[1]["content"]
    assert f"the project has no {e4.API_DOC} at its root, so none is shown" in told

    root = tmp_path / "with-doc"
    root.mkdir()
    (root / e4.API_DOC).write_text("vector_distance(a, b) returns the distance.\n", encoding="utf-8")
    shown = e4.parse_turns(e4.parse_context(lattice, "avx2", unit, api=e4.read_api(root)))[1]["content"]
    assert "vector_distance(a, b) returns the distance." in shown


def test_the_parser_sees_the_callees_by_name_only(lattice, ledger):
    unit = next(u for u in e4.units(lattice, "avx2") if u.name == "float32_distance_dot_avx2")
    data = e4.parse_context(lattice, "avx2", unit, ledger)
    assert "hsum256_ps" in data["callees"]
    text = e4.parse_turns(data)[1]["content"]
    assert "- what it calls, by name: " in text
    # the names, and not the ledger's signatures — those are S-3's answer to the student
    assert "__m256" not in text.split("- what it calls, by name: ")[1]
    assert "- element type: float32" in text and "- distance metric: dot" in text


def test_an_unparseable_answer_is_kept_raw_and_its_s5_prompt_says_the_parse_failed(tmp_path, lattice, ledger):
    run_dir = tmp_path / "run"
    raw = "I think it sums the lanes of a vector."
    fields = parse_into(tmp_path, run_dir, lattice, {"hsum256_ps": raw}, ledger=ledger)

    failed = fields["hsum256_ps"]
    assert failed["parsed"] is False and failed["raw"] == raw
    assert failed["contract"] is None and failed["edge_cases"] is None
    assert "not JSON" in failed["reason"]
    assert fields["popcount_avx2"]["parsed"] is True  # every other unit is untouched

    unit = next(u for u in e4.units(lattice, "avx2") if u.name == "hsum256_ps")
    data = e4.context(lattice, "avx2", unit, "S-5", ledger, fields)
    assert data["fields"] is None
    assert data["fields_note"] == e4.NO_FIELDS.format(reason=failed["reason"])
    text = e4.messages(lattice, "avx2", unit, "S-5", ledger, fields)[1]["content"]
    assert f"no parser fields (the parse failed: {failed['reason']})" in text
    assert "What this function must do:" not in text  # never filled empty, and never guessed at


def test_an_answer_that_is_not_the_two_fields_is_never_repaired(tmp_path, lattice):
    run_dir = tmp_path / "run"
    answers = {
        "hsum256_ps": '{"contract": "It sums the lanes."}',
        "popcount_avx2": '{"contract": "", "edge_cases": []}',
        "hsum256d": '["it sums the lanes"]',
        "dot_epi8": 'Sure:\n```json\n{"contract": "It multiplies.", "edge_cases": ["n is 0."]}\n```\n',
    }
    fields = parse_into(tmp_path, run_dir, lattice, answers)
    assert "edge_cases" in fields["hsum256_ps"]["reason"] and not fields["hsum256_ps"]["parsed"]
    assert "contract" in fields["popcount_avx2"]["reason"] and not fields["popcount_avx2"]["parsed"]
    assert "not an object" in fields["hsum256d"]["reason"] and not fields["hsum256d"]["parsed"]
    # a fenced answer is read, as `extract` reads a fenced body: that is a rule, not a repair
    assert fields["dot_epi8"]["parsed"] is True
    assert fields["dot_epi8"]["contract"] == "It multiplies."


def test_the_parse_step_is_priced_capped_and_resumed(tmp_path, lattice):
    run_dir = tmp_path / "run"
    with pytest.raises(e1.CeilingReached) as refused:
        parse_into(tmp_path, run_dir, lattice, ceiling=0.0)
    assert "nothing was sent" in str(refused.value)
    assert not (run_dir / e4.PARSER).exists()

    fields = parse_into(tmp_path, run_dir, lattice, cost=0.02)
    assert len(fields) == 27
    calls = [json.loads(line) for line in (run_dir / e1.CALLS).read_text().splitlines() if line.strip()]
    assert [call["stage"] for call in calls] == [e4.PARSE_STAGE]
    assert e1.spent(run_dir) == 0.02  # the parser's spend is the run's, against the run's own ceiling

    # a second parse over the same directory asks for nothing and pays for nothing
    again = parse_into(tmp_path, run_dir, lattice, cost=0.02)
    assert len(again) == 27 and e1.spent(run_dir) == 0.02
    assert len((run_dir / e4.PARSER).read_text().splitlines()) == 27


def test_a_parse_call_that_failed_is_priced_and_nothing_is_written(tmp_path, lattice):
    """A lost call read as free is how a run passes its ceiling with nobody seeing it (E1's own record)."""
    run_dir = tmp_path / "run"

    def generate(requests):
        raise e1.GenerateFailed("the parser's call did not finish", call={"cost": 0.04, "wall_seconds": 12.0})

    with pytest.raises(e1.GenerateFailed):
        e4.parse(run_dir, lattice, "avx2", generate, "P", ceiling_usd=1.0)
    assert not (run_dir / e4.PARSER).exists()
    row = json.loads((run_dir / e1.CALLS).read_text().splitlines()[0])
    assert row["stage"] == e4.PARSE_STAGE and row["answered"] == 0 and row["cost"] == 0.04
    assert e1.spent(run_dir) == 0.04


def test_the_plan_records_which_parser_filled_the_fields(tmp_path, lattice, ledger):
    run_dir = tmp_path / "run"
    fields = parse_into(tmp_path, run_dir, lattice, {"hsum256_ps": "not json"}, ledger=ledger)
    block = e4.parser_meta(run_dir)
    assert block["model"] == "P" and block["units"] == 27 and block["parsed"] == 26
    assert block["sha256"] == hashlib.sha256((run_dir / e4.PARSER).read_bytes()).hexdigest()

    requests = e4.plan(lattice, "avx2", ("S-5",), "M", ledger, k=0, fields=fields)
    record = e4.meta(
        lattice, "avx2", requests, "M", arms=("S-5",), k=0, target=FIXTURE, facts=ledger, parser=block
    )
    assert record["parser"] == block


# MARK: - D-13: the facts in the loop (S-3hd against S-3hf) -

#: The names the source rows below invent, and what each one is there to make the rule say.
NOT_HERE_FORM = "_mm512_setzero_si512"  # in the table, unavailable here, and rule R has a form
NOT_HERE_BARE = "_mm512_reduce_add_ps"  # in the table, unavailable here, and rule R has none
INDEXED = "_mm512_indexed_ps"  # in the **index** and not in the table: declared, and not here
NOWHERE_FORM = "_mm512_nope_ps"  # in neither, and its rule-R form is available here
NOWHERE_BARE = "_mm512_castps512_pd256"  # in neither, and its rule-R form is not here either
THEIR_FUNCTION = "abs_diff_epu8_512"  # avx512's own; this file's member of the family is abs_diff_epu8
THEIR_DEFINE = "S8_TO_BIASED_U8_512"  # avx512's own `#define`; this file has no such definition
AVAILABLE = "_mm256_setzero_si256"  # available here, so there is nothing to correct


def loop_table(lattice, isa="avx2"):
    """:func:`available_for`'s hand-built table, plus the two entries D-13's cases need.

    `_mm256_nope_ps` is available so that a name declared **nowhere** can still have a form here, which is
    the one case of the four that says something positive; `_mm512_indexed_ps` is deliberately *absent*,
    because the index is what makes that name read `not-here` rather than `nowhere`.
    """
    record = available_for(lattice, isa)
    record[isa]["names"]["_mm256_nope_ps"] = {"available": True, "needs": [], "header": "hand-built"}
    return record


def loop_index():
    """A hand-built intrinsic index: a JSON object keyed by name, as `facts/intrinsics-clang18.json` is."""
    return {INDEXED: {"header": "avx512vlintrinsics.h"}, NOT_HERE_FORM: {"header": "avx512fintrinsics.h"}}


def instruments(tmp_path, lattice, isa="avx2"):
    """The two instruments on disk, which is where `e4.loop` records their digests from."""
    available_path = tmp_path / "available.json"
    available_path.write_text(json.dumps(loop_table(lattice, isa), sort_keys=True), encoding="utf-8")
    index_path = tmp_path / "intrinsics.json"
    index_path.write_text(json.dumps(loop_index(), sort_keys=True), encoding="utf-8")
    return available_path, index_path


def graded(request, given):
    """One hand-written graded round-0 row for a planned request, in `e1._row` + `_merge`'s own shape."""
    invented = [{"name": name, "bucket": bucket} for name, bucket in given.get("invented", ())]
    diagnostics = [
        {"file": "distance-avx2.c", "line": 1, "col": 1, "severity": "error", "message": message}
        for message in given.get("messages", ())
    ]
    body = given.get("body", "{\n    return 0;\n}")
    return {
        "id": request["id"],
        "cell": request["cell"],
        "name": request["name"],
        "kind": request["kind"],
        "isa": request["isa"],
        "type": request["type"],
        "metric": request["metric"],
        "signature": request["signature"],
        "arm": request["arm"],
        "sample": request["sample"],
        "round": 0,
        "class": given.get("class", "pass"),
        "reason": None,
        "text": given.get("text", f"```c\n{request['signature']}\n{body}\n```"),
        "extract": {"body": body, "reason": None, "block": 1, "params": []},
        "grade": {"class": given.get("class", "pass"), "diagnostics": diagnostics, "invented": invented},
        "reg": True,
        "invented": invented,
        "feedback": given.get("feedback", "It did not compile.\nfoo.c:1:1: error: nope"),
        "tokens_in": 10,
        "tokens_out": 10,
        "finish_reason": "stop",
    }


#: The source run's rows below. Two chains are retried (`invented` and `compile`) and `popcount_avx2` is
#: `wrong`, which D-13 does not retry; every other unit passes at round 0 and is never asked again.
SOURCE_ROWS = {
    "hsum256_ps": {
        "class": "invented",
        "invented": (
            (NOT_HERE_FORM, "intrinsic"),
            (NOT_HERE_BARE, "intrinsic"),
            (INDEXED, "intrinsic"),
            (NOWHERE_FORM, "intrinsic"),
            (NOWHERE_BARE, "intrinsic"),
            (THEIR_FUNCTION, "in-repo"),
            (THEIR_DEFINE, "in-repo"),
            (AVAILABLE, "intrinsic"),
            ("v1", "param"),
            ("__m512i", "other"),
        ),
        "messages": (
            f"always_inline function '{NOT_HERE_BARE}' requires target feature 'avx512f', but would be "
            "inlined into function 'hsum256_ps'",
            "'_mm512_abs_epi32' needs target feature avx512vl",
        ),
        "feedback": "It did not compile.\nThese names resolve nowhere.",
    },
    "sqdiff_epu8": {"class": "compile", "feedback": "It did not compile.\nfoo.c:2:3: error: expected ';'"},
    "popcount_avx2": {"class": "wrong", "feedback": "It compiled, and case bulk/0 disagrees."},
}


def source_run(tmp_path, lattice, rows=None, *, isa="avx2", k=0, model="M", name="d12", arms=("S-3h",)):
    """A finished E4 run of one file's S-3h arm, with hand-written graded rows: D-13's own round 0."""
    table = loop_table(lattice, isa)
    requests = e4.plan(lattice, isa, arms, model, k=k, available=table)
    record = e4.meta(lattice, isa, requests, model, arms=arms, k=k, target=FIXTURE)
    run_dir = e1.write_plan(tmp_path / name, requests, record)
    written = [graded(request, (rows if rows is not None else SOURCE_ROWS).get(request["unit"], {}))
               for request in requests]
    (run_dir / e1.ROWS).write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in written), encoding="utf-8"
    )
    return run_dir


def loop_run(tmp_path, lattice, rows=None, **rest):
    """A D-13 run beside its source: `e4.loop` over one hand-written S-3h run, and the two instruments."""
    source = source_run(tmp_path, lattice, rows, **rest)
    available_path, index_path = instruments(tmp_path, lattice)
    run_dir = e4.loop(
        source, tmp_path / "d13", available_path=available_path, intrinsics_path=index_path
    )
    return source, run_dir


def counting_generator(lattice, isa="avx2"):
    """A generator that answers every request with its unit's gold definition and counts what it was sent."""
    units = {unit.name: unit for unit in e4.units(lattice, isa)}
    calls = []

    def generate(requests):
        calls.append([request["id"] for request in requests])
        return {
            "completions": [
                {
                    "id": request["id"],
                    "text": f"```c\n{definition(lattice, isa, units[request['unit']])}\n```",
                    "tokens_in": 10,
                    "tokens_out": 10,
                }
                for request in requests
            ],
            "cost": 0.0,
            "seconds": 0.0,
        }

    generate.calls = calls
    return generate


def later(run_dir, arm=None, unit=None):
    """The run's round-1 requests, optionally one arm's or one unit's."""
    found = [
        json.loads(line)
        for line in (run_dir / e1.REQUESTS).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [
        request
        for request in found
        if request["round"] == 1
        and (arm is None or request["arm"] == arm)
        and (unit is None or request["unit"] == unit)
    ]


def test_the_loop_copies_round_zero_exactly_and_asks_nothing(tmp_path, lattice):
    """D-13's round 0 **is** D-12's: every S-3h request and row appears twice, one arm's name apart."""
    source, run_dir = loop_run(tmp_path, lattice)
    asked = {
        request["id"]: request
        for request in [json.loads(line) for line in (source / e1.REQUESTS).read_text().splitlines()]
    }
    was = {row["id"]: row for row in [json.loads(line) for line in (source / e1.ROWS).read_text().splitlines()]}
    assert len(asked) == len(was) == 27

    requests = {r["id"]: r for r in [json.loads(line) for line in (run_dir / e1.REQUESTS).read_text().splitlines()]}
    rows = {r["id"]: r for r in rows_of(run_dir)}
    assert len(requests) == len(rows) == 27 * 2
    for arm in e4.LOOP_ARMS:
        for unit in (u.name for u in e4.units(lattice, "avx2")):
            before = asked[e1.request_id(unit, "S-3h", 0, 0)]
            now = requests[e1.request_id(unit, arm, 0, 0)]
            assert now == {**before, "arm": arm, "id": now["id"]}
            assert now["messages"] == before["messages"] and now["params"] == before["params"]
            row = rows[e1.request_id(unit, arm, 0, 0)]
            assert row == {**was[before["id"]], "arm": arm, "id": row["id"]}
            assert row["grade"] == was[before["id"]]["grade"]
            assert row["class"] == was[before["id"]]["class"] and row["text"] == was[before["id"]]["text"]

    # round 0's spend is the source's, so this run has bought nothing and says so by having no call at all
    assert not (run_dir / e1.CALLS).exists() and e1.spent(run_dir) == 0.0
    record = json.loads((run_dir / e1.META).read_text(encoding="utf-8"))
    assert record["rounds"] == 1 and record["iterate"] == list(e4.LOOP_ARMS)
    assert record["retry_classes"] == ["invented", "compile"] == list(e4.RETRY_CLASSES)
    assert record["arms"] == ["S-3hd", "S-3hf"]
    assert record["source"]["run"] == source.name and record["source"]["arm"] == "S-3h"
    for name in e4.LOOP_SOURCE_FILES:
        assert record["source"][f"{name}_sha256"] == hashlib.sha256((source / name).read_bytes()).hexdigest()
    # and the four fields it carries over are the source's own
    before = json.loads((source / e1.META).read_text(encoding="utf-8"))
    assert [record[field] for field in e4.LOOP_CARRIED] == [before[field] for field in e4.LOOP_CARRIED]


def test_the_meta_records_both_instruments_digests(tmp_path, lattice):
    _, run_dir = loop_run(tmp_path, lattice)
    block = json.loads((run_dir / e1.META).read_text(encoding="utf-8"))["loop"]
    for what, path in (("available", tmp_path / "available.json"), ("intrinsics", tmp_path / "intrinsics.json")):
        assert block[what]["path"] == str(path)
        assert block[what]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert block["seed_arm"] == "S-3h" and block["max_lines"] == e4.LOOP_MAX_LINES == 10


def test_a_source_with_no_s3h_or_an_ungraded_row_is_refused_and_nothing_is_written(tmp_path, lattice):
    available_path, index_path = instruments(tmp_path, lattice)
    plain = source_run(tmp_path, lattice, name="s2h-only", arms=("S-2h",))
    with pytest.raises(e4.LoopSource) as no_arm:
        e4.loop(plain, tmp_path / "none", available_path=available_path, intrinsics_path=index_path)
    assert "has no S-3h request" in str(no_arm.value) and "nothing was written" in str(no_arm.value)
    assert not (tmp_path / "none").exists()

    half = source_run(tmp_path, lattice, name="half")
    kept = rows_of(half)[:-3]
    (half / e1.ROWS).write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in kept), encoding="utf-8"
    )
    with pytest.raises(e4.LoopSource) as ungraded:
        e4.loop(half, tmp_path / "short", available_path=available_path, intrinsics_path=index_path)
    assert "answered no row for" in str(ungraded.value)
    assert not (tmp_path / "short").exists()

    # and a source missing one of the four fields a D-13 plan carries over unchanged
    for field in e4.LOOP_CARRIED:
        bare = source_run(tmp_path, lattice, name=f"no-{field}")
        record = json.loads((bare / e1.META).read_text(encoding="utf-8"))
        record[field] = None
        (bare / e1.META).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        with pytest.raises(e4.LoopSource) as missing:
            e4.loop(bare, tmp_path / f"x-{field}", available_path=available_path, intrinsics_path=index_path)
        assert field in str(missing.value)


def test_only_invented_and_compile_chains_are_retried_in_both_arms(tmp_path, lattice):
    """D-13's two classes, and no others: `wrong` and `pass` keep their round-0 row as their final row."""
    every = {
        "hsum256_ps": {"class": "invented", "invented": ((NOT_HERE_FORM, "intrinsic"),)},
        "sqdiff_epu8": {"class": "compile"},
        "popcount_avx2": {"class": "wrong"},
        "hsum256d": {"class": "edge"},
        "dot_epu8": {"class": "no-body"},
        "bf16x8_to_f32x8_loadu": {"class": "not-installed"},
    }
    _, run_dir = loop_run(tmp_path, lattice, every)
    generate = counting_generator(lattice)
    e4.run(run_dir, FIXTURE, generate, pass_grade(), ceiling_usd=1.0)

    retried = {(row["arm"], row["cell"]) for row in rows_of(run_dir) if row["round"] == 1}
    assert retried == {(arm, name) for arm in e4.LOOP_ARMS for name in ("hsum256_ps", "sqdiff_epu8")}
    kept = {row["cell"] for row in rows_of(run_dir) if row["round"] == 0}
    assert len(kept) == 27  # every unit still has its round-0 row, retried or not
    assert {request["arm"] for request in later(run_dir)} == set(e4.LOOP_ARMS)


def test_s3hds_retry_is_e1s_own_text_and_its_request_e1s_own_round(tmp_path, lattice):
    """S-3hd is the control: E1's `_retry`, byte for byte, and E1's `_next_round` but for the seed's arm."""
    _, run_dir = loop_run(tmp_path, lattice)
    e4.run(run_dir, FIXTURE, counting_generator(lattice), pass_grade(), ceiling_usd=1.0)

    zero = {
        request["id"]: request
        for request in [json.loads(line) for line in (run_dir / e1.REQUESTS).read_text().splitlines()]
        if request["round"] == 0
    }
    rows = {row["id"]: row for row in rows_of(run_dir) if row["round"] == 0}
    for unit in ("hsum256_ps", "sqdiff_epu8"):
        was = zero[e1.request_id(unit, "S-3hd", 0, 0)]
        row = rows[was["id"]]
        asked = later(run_dir, "S-3hd", unit)[0]
        assert asked["messages"][-1] == {"role": "user", "content": e1._retry(was, row)}
        assert asked["messages"][-1]["content"] == row["feedback"]
        assert asked["messages"][-2] == {"role": "assistant", "content": row["text"]}
        assert e4._LOOP_HEADING not in asked["messages"][-1]["content"]
        assert asked["loop_facts"] == [] and asked["unlined"] == []

        # and the whole request is E1's own round, the seed's arm aside
        mine = e1._next_round([was], {was["id"]: row}, 1, ("S-3hd",), "M")[0]
        assert {k: v for k, v in asked.items() if k not in ("params", "loop_facts", "unlined")} == {
            k: v for k, v in mine.items() if k != "params"
        }
        assert asked["params"] == {**mine["params"], "seed": e1.seed("M", unit, "S-3h", 0, 1)}
        assert mine["params"]["seed"] == e1.seed("M", unit, "S-3hd", 0, 1) != asked["params"]["seed"]


def facts_for(lattice, row, isa="avx2"):
    """One row's fact lines, read with the hand-built table and index."""
    return e4.loop_facts(lattice, isa, row, loop_table(lattice, isa), loop_index())


def test_each_line_says_what_this_file_has_of_the_name_it_names(tmp_path, lattice):
    """The four intrinsic cases, the two other-file ones, and the names the rule leaves alone."""
    unit = unit_of(lattice, "hsum256_ps")
    request = e4.requests_for(lattice, "avx2", unit, "S-3h", "M", 0, available=loop_table(lattice))[0]
    found = facts_for(lattice, graded(request, SOURCE_ROWS["hsum256_ps"]))
    lines = {fact["name"]: fact for fact in found["facts"]}

    assert lines[NOT_HERE_FORM] == {
        "name": NOT_HERE_FORM, "status": e4.NOT_HERE, "form": "_mm256_setzero_si256",
        "line": f"`{NOT_HERE_FORM}` is not available in this file; its form here: `_mm256_setzero_si256`",
    }
    assert lines[NOT_HERE_BARE] == {
        "name": NOT_HERE_BARE, "status": e4.NOT_HERE, "form": None,
        "line": f"`{NOT_HERE_BARE}` is not available in this file, and no same-named form is",
    }
    # the index is the only thing that knows this one exists at all, and it makes it `not-here` and not `nowhere`
    assert lines[INDEXED]["status"] == e4.NOT_HERE and lines[INDEXED]["form"] is None
    assert lines[NOWHERE_FORM] == {
        "name": NOWHERE_FORM, "status": e4.NOWHERE, "form": "_mm256_nope_ps",
        "line": f"`{NOWHERE_FORM}` is declared by no header of this compiler; its form here: `_mm256_nope_ps`",
    }
    assert lines[NOWHERE_BARE] == {
        "name": NOWHERE_BARE, "status": e4.NOWHERE, "form": None,
        "line": f"`{NOWHERE_BARE}` is declared by no header of this compiler, and no same-named form is",
    }
    assert lines[THEIR_FUNCTION] == {
        "name": THEIR_FUNCTION, "status": e4.OTHER_FILE, "form": "abs_diff_epu8",
        "line": f"`{THEIR_FUNCTION}` is the other file's own; this file's: `abs_diff_epu8`",
    }
    assert lines[THEIR_DEFINE] == {
        "name": THEIR_DEFINE, "status": e4.OTHER_FILE, "form": None,
        "line": f"`{THEIR_DEFINE}` is the other file's own; this file has no such definition",
    }
    # a renamed parameter is not a name the student invented, and the three below have nothing to correct
    assert "v1" not in found["names"]
    assert found["unlined"] == [AVAILABLE, "__m512i"]
    # the feature diagnostics' two names ride with the invented ones, deduplicated
    assert found["names"][-1] == "_mm512_abs_epi32"
    assert found["names"].count(NOT_HERE_BARE) == 1


def test_a_diagnostics_name_is_read_even_where_nothing_was_invented(lattice):
    """clang's `always_inline` refusal is a name the body wrote and this file cannot use, and no `invented`."""
    row = {
        "invented": [],
        "grade": {
            "diagnostics": [
                {
                    "message": f"always_inline function '{NOT_HERE_FORM}' requires target feature 'avx512f',"
                    " but would be inlined into function 'hsum256_ps' which was not compiled for it",
                    "severity": "error",
                }
            ]
        },
    }
    found = facts_for(lattice, row)
    assert found["names"] == [NOT_HERE_FORM]
    assert found["facts"][0]["status"] == e4.NOT_HERE


def test_past_ten_lines_the_section_counts_what_it_left_out(lattice):
    """Ten lines, then one sentence: a cut nobody is told about is a fact the record does not carry."""
    names = tuple((f"_mm512_made_up_{n}_ps", "intrinsic") for n in range(0, 13))
    found = facts_for(lattice, graded_names(names))
    assert len(found["facts"]) == 13 and found["unlined"] == []
    text = e4.loop_retry("It did not compile.", found)
    body = text.split(e4._LOOP_HEADING)[1].strip().splitlines()
    assert len(body) == 11
    assert body[-1] == "(3 more names.)" == e4.LOOP_MORE.format(count=3)
    assert body[0].startswith("`_mm512_made_up_0_ps` is declared by no header")
    # S-3hd's own text is never cut to make room
    assert text.startswith("It did not compile.\n\n")


def graded_names(names):
    """The least of a graded row `loop_facts` reads: the invented names, and no diagnostics."""
    return {"invented": [{"name": name, "bucket": bucket} for name, bucket in names], "grade": {}}


def test_a_retry_with_no_line_is_s3hds_byte_for_byte(lattice):
    """Where no name has a line, the two arms are one question — which is what makes the pair a tie there."""
    found = facts_for(lattice, graded_names(((AVAILABLE, "intrinsic"), ("v1", "param"))))
    assert found["facts"] == [] and found["unlined"] == [AVAILABLE]
    assert e4.loop_retry("It did not compile.", found) == "It did not compile."


def test_s3hf_carries_the_lines_under_one_heading_and_records_them_as_data(tmp_path, lattice):
    _, run_dir = loop_run(tmp_path, lattice)
    e4.run(run_dir, FIXTURE, counting_generator(lattice), pass_grade(), ceiling_usd=1.0)

    plain = later(run_dir, "S-3hd", "hsum256_ps")[0]
    facts = later(run_dir, "S-3hf", "hsum256_ps")[0]
    said, mine = plain["messages"][-1]["content"], facts["messages"][-1]["content"]
    assert mine.startswith(f"{said}\n\n")  # S-3hd's text, then the section, and nothing between
    assert e4._LOOP_HEADING in mine and "of the names above" in mine
    assert f"`{NOT_HERE_FORM}` is not available in this file; its form here: `_mm256_setzero_si256`" in mine
    # an available name is the subject of no line — it is only ever offered as another name's form here
    section = mine.split(e4._LOOP_HEADING)[1]
    assert f"`{AVAILABLE}` is" not in section and f"here: `{AVAILABLE}`" in section
    # and what it served is on the request as data, not only as prose
    zero = {found["id"]: found for found in rows_of(run_dir)}[e1.request_id("hsum256_ps", "S-3hf", 0, 0)]
    assert facts["loop_facts"] == facts_for(lattice, zero)["facts"]
    assert [fact["line"] for fact in facts["loop_facts"]] == section.strip().splitlines()
    assert {fact["status"] for fact in facts["loop_facts"]} == {e4.NOT_HERE, e4.NOWHERE, e4.OTHER_FILE}
    assert facts["unlined"] == [AVAILABLE, "__m512i"]
    # the turns before the retry are round 0's own, so the two arms differ in the one user turn
    assert plain["messages"][:-1] == facts["messages"][:-1]


def test_a_chain_with_no_line_is_one_request_and_two_graded_rows(tmp_path, lattice):
    """The shared seed, doing its work: one question, one answer, and both arms' rows written from it."""
    _, run_dir = loop_run(tmp_path, lattice)
    generate = counting_generator(lattice)
    e4.run(run_dir, FIXTURE, generate, pass_grade(), ceiling_usd=1.0)

    both = {arm: later(run_dir, arm, "sqdiff_epu8")[0] for arm in e4.LOOP_ARMS}
    assert both["S-3hd"]["messages"] == both["S-3hf"]["messages"]
    assert both["S-3hd"]["params"] == both["S-3hf"]["params"]  # the seed is "S-3h"'s for either arm

    # one call, and in it only one of the two ids: the other was answered from the same completion
    sent = [call for call in generate.calls if any("|1" in asked for asked in call)]
    assert len(sent) == 1
    asked = set(sent[0])
    assert len(asked & {both[arm]["id"] for arm in e4.LOOP_ARMS}) == 1
    # the chain with lines is two questions, because its two retries are two different texts
    assert len(asked & {e1.request_id("hsum256_ps", arm, 0, 1) for arm in e4.LOOP_ARMS}) == 2

    rows = {row["id"]: row for row in rows_of(run_dir) if row["round"] == 1}
    for arm in e4.LOOP_ARMS:
        row = rows[e1.request_id("sqdiff_epu8", arm, 0, 1)]
        assert row["class"] == "pass" and row["extract"]["body"]
    call = [json.loads(line) for line in (run_dir / e1.CALLS).read_text().splitlines()][0]
    assert call["deduplicated"] == 1 and call["requests"] == 3


def test_no_gold_reaches_a_retry_that_the_source_did_not_already_carry(tmp_path, lattice):
    """The section is names and statuses; the turns before it are the source run's own bytes."""
    _, run_dir = loop_run(tmp_path, lattice)
    e4.run(run_dir, FIXTURE, counting_generator(lattice), pass_grade(), ceiling_usd=1.0)
    gold = golds(lattice, "avx2")
    for request in later(run_dir):
        added = request["messages"][-1]["content"]
        assert not token_run(tokens(added), tokens(gold[request["unit"]]))
        for other in e4.units(lattice, "avx2"):
            assert not token_run(tokens(added), tokens(gold[other.name])), (request["id"], other.name)


def test_a_moved_instrument_is_refused_before_anything_is_sent(tmp_path, lattice):
    for what, name in (("available", "available.json"), ("intrinsics", "intrinsics.json")):
        into = tmp_path / what
        into.mkdir()
        _, run_dir = loop_run(into, lattice)
        (into / name).write_text("{}", encoding="utf-8")
        generate = counting_generator(lattice)
        with pytest.raises(e4.LoopMoved) as refused:
            e4.run(run_dir, FIXTURE, generate, pass_grade(), ceiling_usd=1.0)
        assert "now digests" in str(refused.value) and "nothing was sent" in str(refused.value)
        assert generate.calls == []
        assert not any(row["round"] == 1 for row in rows_of(run_dir))


def test_the_file_level_takes_a_round_one_pass_where_round_zero_failed(tmp_path, lattice):
    """A loop run's file is each chain's **final** row, so a rescued unit is in it and a `wrong` one is not."""
    _, run_dir = loop_run(tmp_path, lattice)
    summary = e4.run(run_dir, FIXTURE, counting_generator(lattice), pass_grade(), ceiling_usd=1.0)
    level = {row["arm"]: row for row in summary["file_level"]}
    assert sorted(level) == ["S-3hd", "S-3hf"]
    for row in level.values():
        # the two retried units passed at round 1 and are in the file; `popcount_avx2` stayed `wrong`
        assert "hsum256_ps" in row["unit_names"] and "sqdiff_epu8" in row["unit_names"]
        assert "popcount_avx2" not in row["unit_names"]
        assert row["units_passed"] == 26 and row["units"] == 27


# MARK: - S-2o: the student's own passed bodies as shots -


def test_the_designated_neighbours_break_e1s_symmetric_pairs(lattice):
    """E1's type pairing is `float32 ↔ int8` here, so "earlier in the order" is what makes a first wave."""
    ordered = e4.units(lattice, "avx2")
    at = {unit.name: index for index, unit in enumerate(ordered)}
    designated = {
        unit.name: [row for row in e4.designated(lattice, "avx2", unit, ordered) if row.reason is None]
        for unit in ordered
    }
    for name, rows in designated.items():
        for row in rows:
            assert at[row.unit] < at[name], (name, row)
            # and therefore no unit is its own neighbour's designated neighbour, on any axis
            assert name not in [other.unit for other in designated[row.unit]]
    # the pairing it comes from really is symmetric, which is the thing the order breaks
    assert prompts.TYPE_PAIR["float32"] == "float16" and prompts.TYPE_PAIR["int8"] == "uint8"
    served = e4.designated(
        lattice, "avx2", next(u for u in ordered if u.name == "int8_distance_dot_avx2"), ordered
    )
    assert served[0] == e4.Designated("type", "float32_distance_dot_avx2", None)
    assert served[1] == e4.Designated("metric", "int8_distance_cosine_avx2", e4.LATER)


def test_the_waves_are_consistent_with_the_designated_neighbours(lattice):
    ordered = e4.units(lattice, "avx2")
    waved = e4.waves(lattice, "avx2")
    assert set(waved) == {unit.name for unit in ordered}
    assert min(waved.values()) == 0
    for unit in ordered:
        rows = [row for row in e4.designated(lattice, "avx2", unit, ordered) if row.reason is None]
        assert waved[unit.name] == (1 + max(waved[row.unit] for row in rows) if rows else 0)
        for row in rows:
            assert waved[row.unit] < waved[unit.name]
    # a helper and the init have no axis at all, so they are always wave 0
    assert all(waved[unit.name] == 0 for unit in ordered if unit.kind != "cell")


def test_the_plan_writes_wave_zero_only_and_the_meta_names_every_wave(lattice):
    ordered = e4.units(lattice, "avx2")
    waved = e4.waves(lattice, "avx2")
    made = e4.plan(lattice, "avx2", ("S-2o",), "M", k=0)
    assert {request["unit"] for request in made} == {n for n, wave in waved.items() if wave == 0}
    assert {request["wave"] for request in made} == {0}

    record = e4.meta(lattice, "avx2", made, "M", arms=("S-2o",), k=0)
    assert [len(wave) for wave in record["waves"]] == [18, 5, 3, 1]
    assert sum(len(wave) for wave in record["waves"]) == len(ordered)
    assert record["waves"][0] == [n for n in (u.name for u in ordered) if waved[n] == 0]


def test_a_helper_carries_s2s_shots_only_and_says_so(lattice):
    unit = next(u for u in e4.units(lattice, "avx2") if u.name == "popcount_avx2")
    data = e4.context(lattice, "avx2", unit, "S-2o")
    assert data["own"] == [] and data["own_notes"] == [{"axis": None, "unit": None, "reason": "helper"}]
    text = e4.messages(lattice, "avx2", unit, "S-2o")[1]["content"]
    assert e4.NO_OWN["helper"] in text
    assert e4.NO_SHOTS["helper"] in text  # the ISA-axis shots are S-2's, and a helper has none of those


def test_s2o_carries_the_students_own_passed_body_and_never_the_targets(tmp_path, lattice):
    """The shot text is checked against the **replay's** bytes, never against the target's own."""
    run_dir = make_run(tmp_path, lattice, ("S-2o",))
    gold = golds(lattice, "avx2")
    mine = {name: marked(body, name) for name, body in gold.items()}
    generate = e1.replay_generator(own_replay(tmp_path, lattice, "avx2", "S-2o", 0, mine))

    summary = e4.run(run_dir, FIXTURE, generate, pass_grade(), ceiling_usd=1.0)
    assert summary["rows"] == 27 and summary["waves"] == 4

    requests = {
        request["id"]: request
        for request in [
            json.loads(line)
            for line in (run_dir / e1.REQUESTS).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    }
    later = requests[e1.request_id("int8_distance_dot_avx2", "S-2o", 0, 0)]
    assert later["wave"] == 1
    assert later["own"] == [{"axis": "type", "unit": "float32_distance_dot_avx2"}]
    text = "".join(turn["content"] for turn in later["messages"])
    # the neighbour's own body, as the replay wrote it — and the target's own body nowhere in the prompt
    assert mine["float32_distance_dot_avx2"] in text
    assert gold["float32_distance_dot_avx2"] not in text
    assert "(void)mine_float32_distance_dot_avx2;" in text
    assert "your own body, which passed" in text
    # every later wave was built from rows the earlier ones wrote, so wave 3's unit carries two shots
    deepest = requests[e1.request_id("int8_distance_l2_impl_avx2", "S-2o", 0, 0)]
    assert deepest["wave"] == 3 and len(deepest["own"]) == 2


def test_a_neighbour_that_failed_leaves_its_axis_with_no_own_shot(tmp_path, lattice):
    run_dir = make_run(tmp_path, lattice, ("S-2o",))
    mine = {name: marked(body, name) for name, body in golds(lattice, "avx2").items()}
    generate = e1.replay_generator(own_replay(tmp_path, lattice, "avx2", "S-2o", 0, mine))

    e4.run(run_dir, FIXTURE, generate, pass_grade(failing=("float32_distance_dot_avx2",)), ceiling_usd=1.0)
    requests = {
        json.loads(line)["id"]: json.loads(line)
        for line in (run_dir / e1.REQUESTS).read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    later = requests[e1.request_id("int8_distance_dot_avx2", "S-2o", 0, 0)]
    assert later["own"] == []
    assert later["own_notes"] == [
        {"axis": "type", "unit": "float32_distance_dot_avx2", "reason": e4.NEIGHBOUR_FAILED},
        {"axis": "metric", "unit": "int8_distance_cosine_avx2", "reason": e4.LATER},
    ]
    text = "".join(turn["content"] for turn in later["messages"])
    assert "own shots: none on the type axis (neighbour-failed)" in text
    assert mine["float32_distance_dot_avx2"] not in text  # an unverified body is not a pattern


def test_a_resumed_run_answers_no_request_twice(tmp_path, lattice):
    run_dir = make_run(tmp_path, lattice, ("S-0", "S-2o"))
    bodies = {name: marked(body, name) for name, body in golds(lattice, "avx2").items()}
    asked = Counter()
    both = tmp_path / "both-completions.jsonl"
    # S-0's requests are in the plan, S-2o's later waves are not: the two files' ids together answer
    # every request either call can make, and the S-2o rows come second, so they are the ones that win
    both.write_text(
        replay_file(tmp_path, run_dir, lattice, "avx2").read_text(encoding="utf-8")
        + own_replay(tmp_path, lattice, "avx2", "S-2o", 0, bodies).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    replay = e1.replay_generator(both)

    def generate(requests):
        asked.update(request["id"] for request in requests)
        return replay(requests)

    first = e4.run(run_dir, FIXTURE, generate, pass_grade(), ceiling_usd=1.0)
    assert first["rows"] == 27 * 2
    again = e4.run(run_dir, FIXTURE, generate, pass_grade(), ceiling_usd=1.0)
    assert again["rows"] == first["rows"]
    assert asked and max(asked.values()) == 1
    assert sum(asked.values()) == 27 * 2


def test_the_window_record_is_restated_as_a_wave_adds_requests(tmp_path, lattice):
    run_dir = make_run(tmp_path, lattice, ("S-2o",))
    planned = json.loads((run_dir / e1.META).read_text(encoding="utf-8"))["decomposition"]
    bodies = {name: marked(body, name) for name, body in golds(lattice, "avx2").items()}
    e4.run(
        run_dir,
        FIXTURE,
        e1.replay_generator(own_replay(tmp_path, lattice, "avx2", "S-2o", 0, bodies)),
        pass_grade(),
        ceiling_usd=1.0,
    )
    window = json.loads((run_dir / e1.META).read_text(encoding="utf-8"))["decomposition"]
    # the own shots make the later waves' prompts the largest the run sent, and the record says so
    assert window["largest_prompt_chars"] > planned["largest_prompt_chars"]
    assert window["file_chars"] == planned["file_chars"]
    assert window["every_window_smaller"] is True


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
