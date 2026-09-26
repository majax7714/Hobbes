"""E3's corpus: what trains, what is refused, what is dropped and why, and the shuffled control.

The clones are `test_families`' — the port's own fixtures — with four more written here, one per drop:
a callee whose definition the clone cannot be read for, a K&R definition the evaluator's parser cannot
read back, two bodies too long to train without cutting, and a copy of one of the target's own gold
kernels.
"""

import hashlib
import json

import pytest
import test_families
from test_families import DOT_AVX2, DOT_SSE2, FINISH, HASH_AVX2, HASH_NEON, alpha, beta, write_clone

from lattice import corpus, extract, holes
from lattice.cells import build as build_lattice
from lattice.prompts import INSTRUCTION, SYSTEM

FIXTURE = test_families.Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"
HOBBES = test_families.Path(__file__).resolve().parents[4]

# MARK: - the clones written for the drops -

GHOST_SSE2 = """
int scale_block_sse2(const int *a, int n) {
    int total = 7;
    for (int i = 0; i < n; i++) {
        total += ghost_helper(a[i]);
    }
    return total;
}
"""

GHOST_AVX2 = """
int scale_block_avx2(const int *a, int n) {
    int total = 9;
    for (int i = 0; i < n; i += 8) {
        total += a[i] * 3;
    }
    return total;
}
"""

KNR_AVX2 = """
int old_style_avx2(a, n)
    const float *a;
    int n;
{
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += (int)a[i];
    }
    return total;
}
"""

OLD_SSE2 = """
int old_style_sse2(const float *a, int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += (int)a[i] * 2;
    }
    return total;
}
"""

PLANTED_SSE2 = """
float float32_distance_dot_sse2(const void *v1, const void *v2, int n) {
    const float *a = (const float *)v1;
    const float *b = (const float *)v2;
    float total = 0.0f;
    int i = 0;
    while (i < n) {
        total += a[i] * b[i];
        i = i + 1;
    }
    return total;
}
"""


def long_body(isa: str, factor: str) -> str:
    """One member whose body alone is past `MAX_CHARS`, so its example cannot be shown whole."""
    lines = [f"float wide_block_{isa}(const float *a, int n) {{", "    float total = 0.0f;"]
    lines += [f"    total += a[{at}] * {factor}f;" for at in range(300)]
    return "\n".join(lines + ["    return total;", "}"])


def gamma(root):
    """A repo whose `sse2` member calls a symbol the graph names and the clone cannot be read for."""
    return write_clone(
        root,
        {"src/scale.c": [("scale_block_sse2", GHOST_SSE2), ("scale_block_avx2", GHOST_AVX2)]},
        edges=[("src/scale.c.scale_block_sse2", "src/gone.c.ghost_helper")],
        ghosts=[("src/gone.c", "ghost_helper", 3, 5)],
        sha="c" * 40,
    )


def eta(root):
    """A repo one of whose members is a K&R definition, which `scan` reads wrongly rather than refuses."""
    return write_clone(
        root,
        {"src/old.c": [("old_style_avx2", KNR_AVX2), ("old_style_sse2", OLD_SSE2)]},
        sha="e" * 40,
    )


def zeta(root):
    """A repo whose family is two 300-line bodies: an example over `MAX_CHARS` either way round."""
    return write_clone(
        root,
        {"src/wide.c": [("wide_block_sse2", long_body("sse2", "1.0")),
                        ("wide_block_avx2", long_body("avx2", "2.0"))]},
        sha="f" * 40,
    )


def planted_gold() -> tuple[str, str]:
    """`(definition, gold body)` — one of the target's own native kernels, to plant in a clone."""
    lattice = build_lattice(FIXTURE)
    cell = lattice.get("avx2/float32/dot")
    gold = holes.gold_body(lattice.text(cell), cell)
    return f"{cell.signature} {gold}", gold


def delta(root):
    """A repo holding a copy of one of the target's golds, and one sibling that is not a copy."""
    definition, _ = planted_gold()
    return write_clone(
        root,
        {"src/planted.c": [("float32_distance_dot_avx2", definition),
                           ("float32_distance_dot_sse2", PLANTED_SSE2)]},
        sha="d" * 40,
    )


def only_hash(root):
    """A repo with one family and nothing else: a corpus with no derangement to be a control."""
    return write_clone(
        root,
        {"src/hash.c": [("hash_block_neon", HASH_NEON), ("hash_block_avx2", HASH_AVX2)]},
        sha="1" * 40,
    )


@pytest.fixture
def two(tmp_path):
    """The two clones of the port's tests, in the taken order."""
    return [("alpha", alpha(tmp_path / "alpha")), ("beta", beta(tmp_path / "beta"))]


@pytest.fixture
def built(two):
    return corpus.build_corpus(two, FIXTURE)


def rows(where):
    return [json.loads(line) for line in (where / "train.jsonl").read_text(encoding="utf-8").splitlines()]


# MARK: - the refusals -


def test_hobbes_itself_is_refused(tmp_path):
    assert (HOBBES / "pipeline" / "src" / "hobbes").is_dir(), HOBBES
    with pytest.raises(corpus.SessionText) as refusal:
        corpus.build_corpus([("hobbes", HOBBES)], FIXTURE)
    assert "docs/calvin/sessions" in str(refusal.value)
    assert "ADR-107" in str(refusal.value)
    # and either marker alone is enough: a checkout with no session log is still this package's tree
    checkout = tmp_path / "checkout"
    (checkout / "pipeline" / "src" / "hobbes").mkdir(parents=True)
    with pytest.raises(corpus.SessionText) as refusal:
        corpus.refuse_session_text(checkout)
    assert "pipeline/src/hobbes" in str(refusal.value)


def test_a_root_holding_a_dispatched_sessions_text_is_refused(tmp_path):
    root = tmp_path / "sessions-repo"
    (root / "docs" / "calvin" / "sessions").mkdir(parents=True)
    with pytest.raises(corpus.SessionText) as refusal:
        corpus.refuse_session_text(root)
    assert "docs/calvin/sessions" in str(refusal.value)


def test_the_target_is_refused_on_the_same_rule(two):
    with pytest.raises(corpus.SessionText):
        corpus.build_corpus(two, HOBBES)


def test_a_corpus_one_family_holds_half_of_has_no_control(tmp_path):
    with pytest.raises(corpus.NoDerangement) as refusal:
        corpus.build_corpus([("one", only_hash(tmp_path / "one"))], FIXTURE)
    assert "2 of 2" in str(refusal.value)


# MARK: - the records -


def test_one_example_per_kept_member_in_e1s_shape(built):
    assert len(built.records) == 6
    for record in built.records:
        turns = record.messages()
        assert [turn["role"] for turn in turns] == ["system", "user", "assistant"]
        assert turns[0]["content"] == SYSTEM
        assert turns[1]["content"].endswith(INSTRUCTION)
        assert "Related functions:" in turns[1]["content"]
        assert turns[1]["content"].index("Related functions:") < turns[1]["content"].index("The function to write:")
        assert record.chars <= corpus.MAX_CHARS


def test_every_records_answer_is_read_back_by_extract_as_its_own_definition(built):
    for record in built.records:
        read = extract.extract(record.answer, record.name)
        assert read["reason"] is None, record.source
        assert read["body"].startswith("{") and read["body"].endswith("}")
        assert f'{record.name}' in record.answer.splitlines()[1]


def test_the_prompt_carries_the_neighbours_and_the_callees_prototypes(built):
    record = next(r for r in built.records if r.name == "sum_float32_scalar")
    assert record.family == "alpha body:sum * scalar"
    assert record.neighbours == ("src/sums.c:15",)
    assert "sum_float16_scalar" in record.prompt
    assert "static int float32_weight(float v);" in record.prompt
    assert "{ return (int)(v * 2.0f); }" not in record.prompt  # a prototype, not the helper's body


def test_a_members_own_family_gives_its_neighbours_up_to_three(tmp_path, two):
    root = write_clone(
        tmp_path / "wide",
        {"src/k.c": [(f"step_kernel_{isa}", f"""
int step_kernel_{isa}(const int *a, int n) {{
    int total = {at};
    for (int i = 0; i < n; i++) {{
        total += a[i] * {at};
    }}
    return total;
}}
""") for at, isa in enumerate(("sse2", "avx2", "avx512", "neon", "rvv"))]},
    )
    built = corpus.build_corpus(two + [("wide", root)], FIXTURE)
    wide = [record for record in built.records if record.repo == "wide"]
    assert len(wide) == 5
    for record in wide:
        assert len(record.neighbours) == corpus.NEIGHBOURS
        assert record.source not in record.neighbours
    # a five-member family shows five different threes, because the start is derived from the member
    assert len({record.neighbours for record in wide}) == 5


# MARK: - the drops -


def test_a_member_near_the_target_is_dropped_and_leaves_its_sibling_alone(tmp_path, two):
    built = corpus.build_corpus(two + [("delta", delta(tmp_path / "delta"))], FIXTURE)
    row = next(row for row in built.report["repos"] if row["repo"] == "delta")
    assert row["dropped"] == {"near-target": 1, "unreadable": 0, "alone": 1, "unstated-callee": 0, "too-long": 0}
    assert row["kept"] == 0
    assert row["near_target"][0]["name"] == "float32_distance_dot_avx2"
    assert row["near_target"][0]["ratio"] == 1.0
    assert row["dropped_members"]["alone"] == ["src/planted.c:29 float32_distance_dot_sse2"]
    # and the gold body is in no prompt either: the target's code is not in this corpus in any column
    _, gold = planted_gold()
    written = json.dumps([record.messages() for record in built.records])
    assert "_mm256_setzero_ps" not in written
    assert max(gold.split("\n"), key=len).strip() not in written


def test_an_unstated_callee_drops_the_member_that_calls_it(tmp_path, two):
    built = corpus.build_corpus(two + [("gamma", gamma(tmp_path / "gamma"))], FIXTURE)
    row = next(row for row in built.report["repos"] if row["repo"] == "gamma")
    assert row["dropped"]["unstated-callee"] == 1
    assert row["dropped_members"]["unstated-callee"] == [
        "src/scale.c:3 scale_block_sse2 calls ghost_helper (no signature read)"
    ]
    assert row["kept"] == 1
    assert [record.name for record in built.records if record.repo == "gamma"] == ["scale_block_avx2"]


def test_an_answer_the_evaluator_cannot_read_back_is_dropped(tmp_path, two):
    built = corpus.build_corpus(two + [("eta", eta(tmp_path / "eta"))], FIXTURE)
    row = next(row for row in built.report["repos"] if row["repo"] == "eta")
    assert row["dropped"]["unreadable"] == 1
    assert "old_style_avx2 (extract does not read its own answer back)" in row["dropped_members"]["unreadable"][0]
    assert [record.name for record in built.records if record.repo == "eta"] == ["old_style_sse2"]


def test_an_example_over_the_limit_is_dropped_and_nothing_is_cut(tmp_path, two):
    built = corpus.build_corpus(two + [("zeta", zeta(tmp_path / "zeta"))], FIXTURE)
    row = next(row for row in built.report["repos"] if row["repo"] == "zeta")
    assert row["dropped"]["too-long"] == 2
    assert row["kept"] == 0
    assert all("chars)" in dropped for dropped in row["dropped_members"]["too-long"])
    assert all("wide_block" not in json.dumps(record.messages()) for record in built.records)
    assert max(record.chars for record in built.records) <= corpus.MAX_CHARS


def test_every_reason_is_counted_in_one_run(tmp_path, two):
    repos = two + [("gamma", gamma(tmp_path / "gamma")), ("eta", eta(tmp_path / "eta")),
                   ("zeta", zeta(tmp_path / "zeta")), ("delta", delta(tmp_path / "delta"))]
    built = corpus.build_corpus(repos, FIXTURE)
    assert built.report["totals"]["dropped"] == {
        "near-target": 1, "unreadable": 1, "alone": 1, "unstated-callee": 1, "too-long": 2
    }
    assert built.report["totals"]["kept"] == len(built.records) == 8


# MARK: - the control -


def test_the_shuffled_control_keeps_no_answer_of_its_own_or_of_its_family(built):
    for at, record in enumerate(built.records):
        answer = built.records[built.shuffled[at]]
        assert answer.source != record.source
        assert answer.family != record.family


def test_the_controls_answers_are_the_same_multiset_and_its_prompts_the_same_bytes(built, tmp_path):
    corpus.write(built, tmp_path / "out")
    pattern = rows(tmp_path / "out" / "e3-pattern")
    shuffled = rows(tmp_path / "out" / "e3-shuffled")
    assert len(pattern) == len(shuffled) == len(built.records)
    assert [row["messages"][:2] for row in pattern] == [row["messages"][:2] for row in shuffled]
    assert sorted(row["messages"][2]["content"] for row in pattern) == sorted(
        row["messages"][2]["content"] for row in shuffled
    )
    assert [row["messages"][2]["content"] for row in pattern] != [
        row["messages"][2]["content"] for row in shuffled
    ]


def test_the_derangement_is_seeded_and_moves_with_the_seed(built, two):
    again = corpus.build_corpus(two, FIXTURE)
    assert again.shuffled == built.shuffled
    other = corpus.build_corpus(two, FIXTURE, seed=1)
    assert other.shuffled != built.shuffled or other.records != built.records


# MARK: - what is written -


def test_both_manifests_carry_what_train_adapter_reads(built, tmp_path):
    found = corpus.write(built, tmp_path / "out")
    for where, manifest in (("e3-pattern", found["pattern"]), ("e3-shuffled", found["shuffled"])):
        on_disk = json.loads((tmp_path / "out" / where / "manifest.json").read_text(encoding="utf-8"))
        assert on_disk == manifest
        # train_adapter reads exactly these three, and keys the adapter on them
        assert manifest["corpus_hash"] and manifest["repo"] and manifest["sha"]
        payload = (tmp_path / "out" / where / "train.jsonl").read_bytes()
        assert manifest["corpus_hash"] == hashlib.sha256(payload).hexdigest()
        assert manifest["records"] == len(built.records) == len(payload.decode().splitlines())
        assert manifest["sha"] == built.sha
        assert [row["family"] for row in manifest["rows"]] == [r.family for r in built.records]
        assert [row["source"] for row in manifest["rows"]] == [r.source for r in built.records]
    assert found["pattern"]["repo"] == "e3-c-lattice"
    assert found["shuffled"]["repo"] == "e3-c-lattice-shuffled"
    assert found["pattern"]["corpus_hash"] != found["shuffled"]["corpus_hash"]
    assert found["shuffled"]["control"] is True


def test_the_report_names_every_repo_and_measures_the_lengths(built, tmp_path):
    corpus.write(built, tmp_path / "out")
    report = json.loads((tmp_path / "out" / "corpus-report.json").read_text(encoding="utf-8"))
    assert [row["repo"] for row in report["repos"]] == ["alpha", "beta"]
    assert [row["union"] for row in report["repos"]] == [4, 4]
    assert [row["unique"] for row in report["repos"]] == [4, 2]
    assert [row["duplicate"] for row in report["repos"]] == [0, 2]
    assert report["totals"]["kept"] == 6
    lengths = report["lengths"]["example_chars"]
    assert lengths["n"] == 6
    assert lengths["min"] <= lengths["q1"] <= lengths["median"] <= lengths["q3"] <= lengths["max"]
    assert lengths["max"] <= corpus.MAX_CHARS
    assert report["lengths"]["example_tokens_at_4_chars"]["max"] == round(lengths["max"] / 4, 1)
    assert report["target"]["gold_bodies"] == 39
    assert report["repos"][0]["validated"] == {"scalar_ref": 0, "reached_by_tests": 1}


def test_the_same_inputs_and_seed_give_byte_identical_output(two, tmp_path):
    for where in ("first", "second"):
        corpus.write(corpus.build_corpus(two, FIXTURE), tmp_path / where)
    for name in ("e3-pattern/train.jsonl", "e3-pattern/manifest.json", "e3-shuffled/train.jsonl",
                 "e3-shuffled/manifest.json", "corpus-report.json"):
        first = (tmp_path / "first" / name).read_bytes()
        assert first == (tmp_path / "second" / name).read_bytes(), name


# MARK: - the list -


def test_the_repos_list_is_read_in_order_and_a_bad_line_is_named(tmp_path):
    listed = tmp_path / "repos.txt"
    listed.write_text("# the taken order\nalpha=/tmp/a\n\nbeta=/tmp/b\n", encoding="utf-8")
    assert corpus.read_list(listed) == [("alpha", test_families.Path("/tmp/a")),
                                        ("beta", test_families.Path("/tmp/b"))]
    listed.write_text("alpha /tmp/a\n", encoding="utf-8")
    with pytest.raises(ValueError) as refusal:
        corpus.read_list(listed)
    assert "is not <name>=<root>" in str(refusal.value)
