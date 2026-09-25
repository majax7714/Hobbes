"""G-mem: the probe stops inside the gold body, and the score is a prefix of the rest of it."""

from pathlib import Path

import pytest

from lattice import gmem, task
from lattice.cells import build

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"


@pytest.fixture(scope="module")
def lattice():
    return build(FIXTURE)


def test_k_is_a_quarter_of_the_body_and_never_under_two(lattice):
    for cell in lattice.cells.values():
        row = gmem.probe(lattice, cell)
        assert row["k"] == max(2, row["body_lines"] // 4), cell.id
    assert gmem.probe(lattice, lattice.get("avx2/float32/dot"))["k"] == 6  # a 25-line body


def test_the_prompt_ends_inside_the_body_and_the_expectation_is_the_rest_of_it(lattice):
    cell = lattice.get("avx2/float32/dot")
    row = gmem.probe(lattice, cell)
    body = lattice.text(cell)[cell.body_span.start : cell.body_span.end]
    lines = body.splitlines(keepends=True)
    assert row["prompt"].endswith("".join(lines[: row["k"]]))
    assert row["expected"] == "".join(lines[row["k"] :])
    # the prompt is the C-0 context, the signature and the head of the body — and nothing below it
    assert row["prompt"].startswith("//\n//  distance-avx2.c")
    assert cell.signature in row["prompt"]
    assert row["prompt"].count("_mm256_setzero_ps()") == 1  # the head's line, the siblings' gone
    assert row["expected"].rstrip().endswith("}")
    assert row["expected_tokens"] > 0


def test_the_prompt_and_the_expectation_rebuild_the_gold_from_the_signature_on(lattice):
    cell = lattice.get("sse2/int8/dot")
    row = gmem.probe(lattice, cell)
    text = lattice.text(cell)
    assert row["prompt"] + row["expected"] == (
        task.prelude_bare(lattice, cell) + cell.signature + text[cell.signature_span.end : cell.body_span.end]
    )


def test_the_probe_names_the_cell_it_is_of(lattice):
    row = gmem.probe(lattice, lattice.get("avx512/bit1/hamming"))
    assert (row["cell"], row["name"], row["file"]) == (
        "avx512/bit1/hamming",
        "bit1_distance_hamming_avx512",
        "src/distance-avx512.c",
    )
    assert str(FIXTURE) not in row["prompt"]


# MARK: - the score and its labels -


def test_an_exact_continuation_scores_one_and_an_empty_one_scores_nothing():
    expected = "return hsum256_ps(acc);\n}\n"
    assert gmem.score(expected, expected) == 1.0
    assert gmem.score(expected, expected + "\n\nfloat other (void) {}") == 1.0  # the prefix is what is asked
    assert gmem.score(expected, "") == 0.0
    assert gmem.score(expected, "int x = 0;") == 0.0  # it differs at the first token
    assert gmem.score(expected, "return 0.0f;\n}\n") == 1 / 3  # `return` and then it diverges


def test_half_the_tokens_in_order_scores_half():
    expected = "a b c d"
    assert gmem.score(expected, "a b x d") == 0.5
    assert gmem.score(expected, "a b") == 0.5
    assert gmem.score(expected, "b a c d") == 0.0  # in order, from the start


def test_whitespace_is_not_recall():
    assert gmem.score("return  hsum256_ps(acc);", "return\n\thsum256_ps(acc);") == 1.0


def test_an_expectation_with_nothing_left_to_continue_is_trivially_continued():
    assert gmem.score("", "anything") == 1.0
    assert gmem.score("  \n ", "") == 1.0


def test_the_labels_and_their_two_lines():
    assert gmem.label(1.0) == "memorised"
    assert gmem.label(0.51) == "memorised"
    assert gmem.label(0.5) == "neither"  # ADR-099's line is "above 0.5"
    assert gmem.label(0.15) == "neither"
    assert gmem.label(0.149) == "unseen"
    assert gmem.label(0.0) == "unseen"


# MARK: - the run -


def test_run_scores_every_probe_through_the_completer(lattice):
    probes = [gmem.probe(lattice, lattice.get(cell)) for cell in ("avx2/float32/dot", "sse2/float32/l1")]
    asked = []

    def gold_back(prompt):
        asked.append(prompt)
        return next(row["expected"] for row in probes if row["prompt"] == prompt)

    results = gmem.run(probes, gold_back)
    assert len(asked) == 2
    assert [row["cell"] for row in results] == ["avx2/float32/dot", "sse2/float32/l1"]
    assert [row["score"] for row in results] == [1.0, 1.0]
    assert [row["label"] for row in results] == ["memorised", "memorised"]
    assert all(row["evidence"] for row in results)


def test_run_reads_a_completer_that_writes_something_else_as_unseen(lattice):
    probes = [gmem.probe(lattice, lattice.get("avx2/float32/dot"))]
    results = gmem.run(probes, lambda prompt: "int nothing_like_it = 0;")
    assert results[0]["score"] == 0.0
    assert results[0]["label"] == "unseen"
    assert results[0]["completion"] == "int nothing_like_it = 0;"


def test_a_probe_with_nothing_to_continue_carries_no_evidence():
    probes = [{"cell": "x/y/z", "k": 2, "prompt": "p", "expected": "", "expected_tokens": 0}]
    result = gmem.run(probes, lambda prompt: "")[0]
    assert result["score"] == 1.0
    assert result["evidence"] is False  # whatever the score says, nothing was recalled


# MARK: - the evidence floor (E1-g's record, limit 3) -


def test_the_floor_is_where_a_tail_starts_being_evidence():
    assert gmem.MIN_EXPECTED_TOKENS == 8
    assert gmem.has_evidence(8) is True
    assert gmem.has_evidence(7) is False
    assert gmem.has_evidence(1) is False  # a wrapper's `}`
    assert gmem.has_evidence(0) is False


def test_a_wrappers_expected_tail_is_one_brace_and_carries_no_evidence(lattice):
    """E1-g's ten wrappers all read `memorised` on this: K = 2 of a three-line body leaves `}` alone."""
    row = gmem.probe(lattice, lattice.get("avx2/float32/l2"))
    assert row["body_lines"] == 3 and row["k"] == 2
    assert row["expected"].strip() == "}"
    assert row["expected_tokens"] == 1

    result = gmem.run([row], lambda prompt: "}\n")[0]
    assert result["score"] == 1.0 and result["label"] == "memorised"
    assert result["evidence"] is False  # the continuation is right and says nothing


def test_a_real_bodys_probe_still_carries_evidence(lattice):
    row = gmem.probe(lattice, lattice.get("avx2/float32/dot"))
    assert row["expected_tokens"] >= gmem.MIN_EXPECTED_TOKENS
    assert gmem.run([row], lambda prompt: row["expected"])[0]["evidence"] is True
