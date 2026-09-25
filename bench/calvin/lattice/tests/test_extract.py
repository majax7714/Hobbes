"""E1-c's parse: the body out of a completion, or the reason there is none — written as models write."""

from pathlib import Path

import pytest

from lattice import extract, holes
from lattice.cells import build

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"

NAME = "float32_distance_dot_avx2"
BODY = """{
    const float *a = (const float *)v1;
    const float *b = (const float *)v2;
    float acc = 0.0f;
    for (int i = 0; i < n; ++i) acc += a[i] * b[i];
    return -acc;
}"""

WITH_A_HELPER = f"""Here is the kernel. It follows the file's own style, and the tail loop handles the
remainder that the vector width does not cover.

```c
static inline float hsum_local (__m256 v)
{{
    return _mm256_cvtss_f32(v);
}}

float {NAME} (const void *v1, const void *v2, int n)
{BODY}
```

Note that I negated the dot product, as the file's own kernels do.
"""

BARE_FENCE = f"""```
float {NAME} (const void *v1, const void *v2, int n)
{BODY}
```
"""

TRUNCATED = f"""Sure:

```c
float {NAME} (const void *v1, const void *v2, int n)
{{
    const float *a = (const float *)v1;
    float acc = 0.0f;
    for (int i = 0; i < n; ++i"""

SECOND_BLOCK = f"""First, the helper it needs:

```c
static inline float hsum_local (__m256 v)
{{
    return _mm256_cvtss_f32(v);
}}
```

And now the kernel itself:

```c
float {NAME} (const void *v1, const void *v2, int n)
{BODY}
```
"""

ANOTHER_NAME = f"""```c
float float32_distance_l1_avx2 (const void *v1, const void *v2, int n)
{BODY}
```
"""


@pytest.fixture(scope="module")
def lattice():
    return build(FIXTURE)


def test_the_definition_comes_out_of_the_block_past_the_prose_and_the_helper():
    found = extract.extract(WITH_A_HELPER, NAME)
    assert found == {"body": BODY, "reason": None, "block": 1}


def test_the_tag_is_not_read():
    for fenced in (BARE_FENCE, WITH_A_HELPER.replace("```c", "```C"), WITH_A_HELPER.replace("```c", "```cpp")):
        assert extract.extract(fenced, NAME)["body"] == BODY


def test_no_fence_at_all_is_its_own_reason():
    prose = f"float {NAME} (const void *v1, const void *v2, int n)\n{BODY}\n"
    assert extract.extract(prose, NAME) == {"body": None, "reason": extract.NO_BLOCK, "block": None}


def test_a_fence_cut_off_mid_body_is_read_to_the_end_and_refused():
    found = extract.extract(TRUNCATED, NAME)
    assert found["body"] is None and found["block"] == 1
    assert "does not scan" in found["reason"]
    assert "never closed" in found["reason"]  # the scanner's own words, not this module's guess


def test_the_rule_is_the_first_block_even_when_a_later_one_has_it():
    found = extract.extract(SECOND_BLOCK, NAME)
    assert found["body"] is None and found["block"] == 1
    assert found["reason"] == f"the first fenced block defines no {NAME}"
    # and the block it did read was the helper's, which it could have returned under another name
    assert extract.extract(SECOND_BLOCK, "hsum_local")["body"] is not None


def test_a_definition_of_a_different_name_is_not_the_one_asked_for():
    found = extract.extract(ANOTHER_NAME, NAME)
    assert found == {"body": None, "reason": f"the first fenced block defines no {NAME}", "block": 1}


def test_a_stray_closing_brace_is_the_scanners_refusal_and_not_a_body():
    offered = f"```c\nfloat {NAME} (const void *v1, const void *v2, int n)\n{{ return 0.0f; }} }}\n```\n"
    found = extract.extract(offered, NAME)
    assert found["body"] is None and found["block"] == 1
    assert found["reason"].startswith("the first fenced block does not scan:")


def test_a_body_holes_would_not_write_comes_back_as_a_reason(monkeypatch):
    # In every shape that could be constructed here `scan` refuses first, because its spans are balanced
    # by construction. The guard is asked anyway: `holes` is the module that will be handed this body, and
    # its refusal has to arrive as a reason rather than as an exception out of the parse.
    def refuse(punched, body):
        raise holes.UnbalancedBody("2 brace(s) left open")

    monkeypatch.setattr(extract.holes, "fill", refuse)
    found = extract.extract(BARE_FENCE, NAME)
    assert found["body"] is None and found["block"] == 1
    assert found["reason"] == f"the body of {NAME} would not be written: 2 brace(s) left open"


def test_the_first_block_runs_to_the_next_fence_whatever_follows():
    assert extract.first_block("prose\n```\nx\ny\n```\nmore\n```\nz\n```\n") == "x\ny"
    assert extract.first_block("```c\nx\n") == "x"
    assert extract.first_block("no fence here\n") is None


def test_every_fixture_golds_round_trips_through_a_fence(lattice):
    for cell in lattice.cells.values():
        gold = holes.gold_body(lattice.text(cell), cell)
        completion = f"Here it is:\n\n```c\n{cell.signature}\n{gold}\n```\n\nThat is the whole definition.\n"
        found = extract.extract(completion, cell.name)
        assert found["reason"] is None, (cell.id, found["reason"])
        assert found["body"] == gold, cell.id
