"""**G-mem**, the memorisation probe (`calvin-experiments.md` §5.5): can the base continue the gold?

sqlite-vector is public (Apache-2.0), and C-39's lesson is that a benchmark the base has read measures
recall. So before any score on a held-out kernel is read as ability, this asks the other question: given
the file above the hole, the signature and the **first few lines of the gold body**, does the model
write the rest of the gold? A model that does is remembering the target, and its score on that cell is a
fact about **W**, not about **M**.

**The prompt** is `prelude_bare` (the C-0 context, every other cell reduced to its prototype) plus the
signature, the file's own whitespace between them, and the body's first K lines, with
`K = max(2, ⌊lines / 4⌋)`. The expected text is the rest of the body, byte for byte. The completion is
taken at temperature 0 — greedy is the only setting a continuation claim can be made at.

**The two lines, 0.5 and 0.15, are borrowed from ADR-099's navigation probe** (§5.5), which asked a
model where things are, not to write code. They are carried here as a convention and not as a
calibrated threshold, which is why `label` names a middle band (`neither`) rather than choosing a side.

`score` is a prefix measure, not a similarity: the share of the expected text's whitespace-split tokens
matched **in order from the start**. A body that continues correctly for three lines and then diverges
scores those three lines; one that reproduces the gold's tokens in a different order scores nothing
after the first difference. Whitespace is not compared, so indentation is not recall.

A cell whose body is at most K lines leaves nothing to continue. Those rows are kept — they are real
cells — with `expected_tokens` 0, and `run` marks them `evidence: False`: whatever `score` says, a probe
with nothing to recall is not evidence that anything was recalled.
"""

from __future__ import annotations

from typing import Callable

from .cells import Cell, Lattice
from .task import prelude_bare

__all__ = ["MEMORISED", "UNSEEN", "label", "probe", "run", "score"]

#: above this share of the gold's tokens continued in order, the gold was recalled (ADR-099's line).
MEMORISED = 0.5
#: below this, nothing of the gold was recalled.
UNSEEN = 0.15


def probe(lattice: Lattice, cell: Cell) -> dict:
    """The probe for one cell: the prompt that ends inside the gold body, and the rest of it."""
    source = lattice.sources[cell.isa]
    text = source.text
    body = text[cell.body_span.start : cell.body_span.end]
    lines = body.splitlines(keepends=True)
    k = max(2, len(lines) // 4)
    gap = text[cell.signature_span.end : cell.body_span.start]
    expected = "".join(lines[k:])
    return {
        "cell": cell.id,
        "name": cell.name,
        "file": cell.file,
        "k": k,
        "body_lines": len(lines),
        "prompt": prelude_bare(lattice, cell) + cell.signature + gap + "".join(lines[:k]),
        "expected": expected,
        "expected_tokens": len(expected.split()),
    }


def score(expected: str, completion: str) -> float:
    """The share of *expected*'s tokens that *completion* continues, in order, from the start.

    `1.0` when the completion begins with all of them, `0.0` when it differs at the first. An expectation
    with no tokens is trivially continued, so it scores `1.0` and carries no evidence (`run`).
    """
    want = expected.split()
    if not want:
        return 1.0
    got = completion.split()
    matched = 0
    for wanted, given in zip(want, got):
        if wanted != given:
            break
        matched += 1
    return matched / len(want)


def label(value: float) -> str:
    """`memorised` above 0.5, `unseen` below 0.15, `neither` on the lines and between them."""
    if value > MEMORISED:
        return "memorised"
    if value < UNSEEN:
        return "unseen"
    return "neither"


def run(probes: list[dict], complete: Callable[[str], str]) -> list[dict]:
    """Score every probe with *complete*, a `prompt -> continuation` callable (greedy, temperature 0).

    The callable is the only place a model appears in this module, so a test passes a fake one and the
    scoring is graded without spending anything.
    """
    results = []
    for row in probes:
        completion = complete(row["prompt"])
        value = score(row["expected"], completion)
        results.append(
            {
                "cell": row["cell"],
                "k": row["k"],
                "score": value,
                "label": label(value),
                "completion": completion,
                "evidence": row["expected_tokens"] > 0,
            }
        )
    return results
