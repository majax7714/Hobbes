"""The act vocabulary (design §2.5) and the scorer that reads it (§6.1, **P**).

Every answer begins with one act token and then a value: ``ANSWER v``,
``CANDIDATES v1, v2, …``, ``UNDEFINED``, ``UNKNOWN``. The scorer is
strict on purpose — §6.1's second row asks whether a hedged answer is
being read as ``UNDEFINED``, and the way to make that question
answerable is a scorer that reads ``UNDEFINED`` only when the line is
exactly that. Anything else is ``malformed``, a column of its own, never
folded into a neighbour.

``grade`` places one output in one column of the confusion matrix:
``ANSWER-correct``, ``ANSWER-wrong`` (sub-classed ``sibling`` when the
wrong value is the nearest dense-real name's answer — the strange tree —
or ``other``), ``CANDIDATES-with`` / ``CANDIDATES-without`` (the correct
value in the list or not), ``UNDEFINED``, ``UNKNOWN``, ``malformed``.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ACTS = ("ANSWER", "CANDIDATES", "UNDEFINED", "UNKNOWN")
COLUMNS = ("ANSWER-correct", "ANSWER-wrong", "CANDIDATES-with", "CANDIDATES-without",
           "UNDEFINED", "UNKNOWN", "malformed")

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Act:
    kind: str                     # one of ACTS, or "malformed"
    values: tuple[str, ...] = ()
    raw: str = ""


def parse(text: str) -> Act:
    """Read one act off the first line of a model's output.

    Exactly one act token first; ``ANSWER`` takes exactly one name,
    ``CANDIDATES`` one or more comma-separated names, and the two bare
    acts take nothing. Leading whitespace is allowed (the prompt ends in
    ``A:``); anything else — a second act, a value on a bare act, a
    value that is not a name, an empty line — is malformed.
    """
    line = text.split("\n", 1)[0].strip()
    if not line:
        return Act("malformed", (), text)
    head, _, rest = line.partition(" ")
    rest = rest.strip()
    if head not in ACTS:
        return Act("malformed", (), text)
    if head in ("UNDEFINED", "UNKNOWN"):
        return Act(head, (), text) if not rest else Act("malformed", (), text)
    if head == "ANSWER":
        return Act("ANSWER", (rest,), text) if _NAME.match(rest) else Act("malformed", (), text)
    parts = [p.strip() for p in rest.split(",")] if rest else []
    if not parts or not all(_NAME.match(p) for p in parts) or len(set(parts)) != len(parts):
        return Act("malformed", (), text)
    return Act("CANDIDATES", tuple(parts), text)


@dataclass(frozen=True)
class Grade:
    column: str                   # one of COLUMNS
    detail: str = ""              # ANSWER-wrong: "sibling" | "other"; CANDIDATES: the rank of the hit
    memorised: bool = False       # the value answered was in a training QA pair


def grade(act: Act, item: dict) -> Grade:
    """Place ``act`` in a column for the eval ``item`` (a row of an eval jsonl)."""
    gold = set(item.get("gold") or ())
    trained = set(item.get("gold_trained") or ())
    sibling = item.get("sibling")
    if act.kind == "malformed":
        return Grade("malformed")
    if act.kind in ("UNDEFINED", "UNKNOWN"):
        return Grade(act.kind)
    if act.kind == "ANSWER":
        v = act.values[0]
        if v in gold:
            return Grade("ANSWER-correct", memorised=v in trained)
        return Grade("ANSWER-wrong", "sibling" if sibling is not None and v == sibling else "other")
    hits = [i for i, v in enumerate(act.values) if v in gold]
    if hits:
        return Grade("CANDIDATES-with", str(hits[0] + 1), memorised=act.values[hits[0]] in trained)
    return Grade("CANDIDATES-without")


def row_of(item: dict) -> str:
    """The confusion-matrix row an item belongs to: the class, with the exposure
    when it carries one (absent names: trained / held-out; a real symbol's
    relation in a v1 relation-absence world: with / without)."""
    cls = item["class"]
    exp = item.get("exposure", "n/a")
    return f"{cls}/{exp}" if exp != "n/a" else cls


def confusion(items: list[dict], outputs: dict[str, str]) -> dict:
    """The act × class matrix (§6.1) over ``items`` and their ``outputs`` (id → text).

    Items with no output are counted in ``missing``. The matrix carries,
    per row, the count in each column, the sibling share of the wrong
    answers, and the memorised share of the correct ones.
    """
    rows: dict[str, Counter] = {}
    extra: dict[str, Counter] = {}
    missing = 0
    for it in items:
        if it["id"] not in outputs:
            missing += 1
            continue
        g = grade(parse(outputs[it["id"]]), it)
        r = row_of(it)
        rows.setdefault(r, Counter())[g.column] += 1
        e = extra.setdefault(r, Counter())
        e["n"] += 1
        if g.column == "ANSWER-wrong" and g.detail == "sibling":
            e["wrong-sibling"] += 1
        if g.memorised:
            e["memorised"] += 1
    return {
        "columns": list(COLUMNS),
        "rows": {r: {c: rows[r].get(c, 0) for c in COLUMNS} for r in sorted(rows)},
        "extra": {r: dict(extra[r]) for r in sorted(extra)},
        "missing": missing,
    }


def render(matrix: dict) -> str:
    cols = matrix["columns"]
    w = max(len(r) for r in matrix["rows"]) if matrix["rows"] else 10
    head = "row".ljust(w) + "  " + "  ".join(c.rjust(18) for c in cols) + "   wrong-sibling  memorised"
    lines = [head]
    for r, counts in matrix["rows"].items():
        e = matrix["extra"][r]
        lines.append(r.ljust(w) + "  " + "  ".join(str(counts[c]).rjust(18) for c in cols)
                     + f"   {e.get('wrong-sibling', 0):>13}  {e.get('memorised', 0):>9}")
    if matrix["missing"]:
        lines.append(f"missing outputs: {matrix['missing']}")
    return "\n".join(lines)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def read_outputs(path: Path) -> dict[str, str]:
    """Outputs as ``{"id": …, "output": …}`` lines → id → output."""
    return {row["id"]: row["output"] for row in read_jsonl(path)}
