"""The gate on the instruments (§5.5): the gold passes, and four mutants of it get their class.

The keyed rounds lost their first runs to their own instruments, and every round after found a defect in
one. So before any model writes anything, the graders are graded: for each native cell the gold must
read `pass`, and four deliberate damages to the gold must read exactly the class they are damage of.

| mutant | the damage | must read |
|---|---|---|
| `syntax` | the body's last `;` removed | `compile` |
| `invented` | `(void)_mm_lattice_invented_ps(0);` as the first statement | `invented`, bucket `intrinsic` |
| `wrong` | every `return EXPR;` becomes `return (EXPR) * 1.5f + 1.0f;` | `wrong` |
| `edge` | `if (n % 64 != 0) return -12345.0f;` as the first statement | `edge` |

The `edge` mutant is built on the bulk grid's sizes, every one of which is a multiple of 64: it answers
correctly on every bulk case and wrongly on the ragged ones, which is precisely the failure §12.2 calls
`edge`. A mutant of an `_impl` is graded through the wrappers that reach it, like the `_impl` itself —
`Cell.graded_via` already says which slots those are.

The report also carries **the gold's worst relative error per `(type, metric)`**, which is the margin the
tolerance table is running on: a row whose worst error is a hair under its `rtol` is a row that will
report a false failure on the next box, and reading it here is how that is caught before a run.

Mutation is textual and works on the masked text (`scan.mask`), so a `;` inside a comment or a string is
never the one removed.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import diff, grade, holes, run
from .cells import NATIVE, Cell, Lattice
from .cells import build as build_lattice
from .scan import mask

__all__ = ["MUTANTS", "EXPECTED", "mutate", "selftest", "render"]

#: The mutants, in the order the report lists them.
MUTANTS = ("syntax", "invented", "wrong", "edge")

#: What each mutant must read, and what the gold must read.
EXPECTED = {"gold": "pass", "syntax": "compile", "invented": "invented", "wrong": "wrong", "edge": "edge"}

#: The name the `invented` mutant calls. Built of known stems — `_mm`, `_ps` — exactly as Atlas-0's
#: inventions were, so it lands in the `intrinsic` bucket and nowhere else.
INVENTED_CALL = "(void)_mm_lattice_invented_ps(0);"

#: The `edge` mutant's guard. Every bulk size is a multiple of 64; most edge sizes are not.
EDGE_GUARD = "if (n % 64 != 0) return -12345.0f;"

_RETURN = re.compile(r"\breturn\s+(?P<expression>[^;]+);", re.DOTALL)


def mutate(body: str, mutant: str) -> str:
    """One mutant of a gold body. *body* runs from its `{` to the matching `}`, and so does the result."""
    if mutant == "syntax":
        return _drop_last_semicolon(body)
    if mutant == "invented":
        return _insert_first(body, INVENTED_CALL)
    if mutant == "edge":
        return _insert_first(body, EDGE_GUARD)
    if mutant == "wrong":
        return _scale_returns(body)
    raise ValueError(f"no mutant {mutant!r}; the four are {MUTANTS}")


def _drop_last_semicolon(body: str) -> str:
    masked = mask(body)
    at = masked.rfind(";")
    if at < 0:
        raise ValueError("the body has no ';' to drop")
    return body[:at] + body[at + 1 :]


def _insert_first(body: str, statement: str) -> str:
    at = mask(body).index("{")
    return f"{body[: at + 1]}\n    {statement}{body[at + 1 :]}"


def _scale_returns(body: str) -> str:
    """Every `return EXPR;` becomes `return (EXPR) * 1.5f + 1.0f;` — real C, and a real wrong answer.

    Matched on the masked text so a `return` inside a comment is not one, and rewritten on the real text
    by span, right to left, so the earlier spans stay valid.
    """
    spans = [(m.start(), m.end(), m.start("expression"), m.end("expression")) for m in _RETURN.finditer(mask(body))]
    for start, end, expression_start, expression_end in reversed(spans):
        expression = body[expression_start:expression_end].strip()
        body = body[:start] + f"return ({expression}) * 1.5f + 1.0f;" + body[end:]
    return body


def selftest(
    target: Path | str,
    workdir: Path | str,
    *,
    cells: list[str] | tuple[str, ...] | None = None,
    allow_host: bool = False,
    compiler: str | None = None,
    timeout: int = diff.TIMEOUT,
) -> dict:
    """Grade the gold and its four mutants for every named cell (default: every native one).

    Returns the report: one row per cell and mutant with expected against got, the worst relative error
    per `(type, metric)`, and `ok`, which is false when any row disagrees.
    """
    run.require_container(allow_host=allow_host)
    lattice = build_lattice(target)
    chosen = _chosen(lattice, cells)
    entries = [
        {"id": f"{cell.id}#{name}", "cell": cell.id, "body": "gold" if name == "gold" else mutate(_gold(lattice, cell), name)}
        for cell in chosen
        for name in ("gold", *MUTANTS)
    ]
    results = grade.grade(
        target, entries, workdir, allow_host=allow_host, compiler=compiler, timeout=timeout
    )
    return _report(chosen, results)


def _gold(lattice: Lattice, cell: Cell) -> str:
    return holes.gold_body(lattice.text(cell), cell)


def _chosen(lattice: Lattice, cells: list[str] | tuple[str, ...] | None) -> list[Cell]:
    if cells:
        return [lattice.get(cell_id) for cell_id in cells]
    return sorted(
        (cell for cell in lattice.cells.values() if cell.isa in NATIVE),
        key=lambda c: (c.isa, c.file, c.signature_span.start),
    )


def _report(chosen: list[Cell], results: list[dict]) -> dict:
    by_id = {result["id"]: result for result in results}
    rows: list[dict] = []
    worst: dict[str, float] = {}
    ok = True
    for cell in chosen:
        for name in ("gold", *MUTANTS):
            result = by_id[f"{cell.id}#{name}"]
            got = result["class"]
            agreed = got == EXPECTED[name]
            if name == "invented" and agreed:
                agreed = any(i["bucket"] == "intrinsic" for i in result["invented"])
            ok = ok and agreed
            rows.append(
                {
                    "cell": cell.id,
                    "mutant": name,
                    "expected": EXPECTED[name],
                    "got": got,
                    "ok": agreed,
                    "reason": result.get("reason"),
                    "buckets": sorted({i["bucket"] for i in result["invented"]}),
                    "seconds": result["seconds"]["total"],
                }
            )
            if name == "gold":
                for slot in result["slots"]:
                    key = f"{cell.type}/{diff.METRIC_OF_ENUM.get(slot['slot'].split(':')[0], slot['slot'])}"
                    worst[key] = max(worst.get(key, 0.0), slot["worst"])
    return {
        "cells": len(chosen),
        "rows": rows,
        "mismatches": [row for row in rows if not row["ok"]],
        "worst_relative_error": dict(sorted(worst.items())),
        "tolerance": {f"{t}/{m}": list(v) for (t, m), v in sorted(diff.TOLERANCE.items())},
        "ok": ok,
    }


def render(report: dict) -> str:
    """The report as a table: every cell and mutant, then the margins the tolerance table is running on."""
    lines = [f"self-test over {report['cells']} cell(s) — {'ok' if report['ok'] else 'MISMATCHED'}", ""]
    lines.append(f"{'cell':<28}{'mutant':<10}{'expected':<14}{'got':<14}{'':<4}")
    lines.append("-" * 70)
    for row in report["rows"]:
        lines.append(
            f"{row['cell']:<28}{row['mutant']:<10}{row['expected']:<14}{row['got']:<14}"
            f"{'' if row['ok'] else '  <-- ' + (row['reason'] or '')}"
        )
    lines.append("")
    lines.append("the gold's worst relative error, against the tolerance table:")
    for key, value in report["worst_relative_error"].items():
        rtol = report["tolerance"].get(key, [None, None])[0]
        lines.append(f"  {key:<24}{value:.3g}" + (f"   (rtol {rtol:g})" if rtol is not None else ""))
    if report["mismatches"]:
        lines.append("")
        lines.append(f"{len(report['mismatches'])} mismatch(es).")
    return "\n".join(lines)
