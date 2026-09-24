"""Punching a hole where a kernel body was, and filling it again.

A hole is the smallest edit that leaves a compilable file with one body missing: the cell's body — `{`
to its matching `}` — replaced by `{ /* HOLE */ }`, and every other byte of the file left alone. The
signature stays, so the file still declares what the model is asked to write, and the helpers, macros
and siblings around it are the context of §5.3.

The property this module exists to keep is the round trip: `fill(punch(t, c), gold_body(t, c)) == t`
for every cell of every file. A grader that cannot put the gold back is a grader that is measuring its
own edit, which is how the keyed rounds lost their first runs.

A body that is not balanced braces is refused (`UnbalancedBody`) rather than written: the model's
output is the one thing here that is not deterministic, and a truncated generation would otherwise
produce a file whose compile failure is the harness's fault, not the model's.
"""

from __future__ import annotations

from .scan import mask

__all__ = ["HOLE", "UnbalancedBody", "NoHole", "punch", "fill", "gold_body"]

#: what a punched body reads as. Its indentation is the target's four spaces.
HOLE = "{\n    /* HOLE */\n}"


class UnbalancedBody(Exception):
    """The text offered as a body is not `{` … matching `}`, so it was not written."""


class NoHole(Exception):
    """The text is not a punched file: it carries no hole, or more than one."""


def gold_body(text: str, cell) -> str:
    """The body the target itself wrote for that cell, braces included."""
    return text[cell.body_span.start : cell.body_span.end]


def punch(text: str, cell) -> str:
    """The file with that cell's body replaced by the hole, every other byte unchanged."""
    return text[: cell.body_span.start] + HOLE + text[cell.body_span.end :]


def fill(punched: str, body: str) -> str:
    """The punched file with the hole replaced by `body` (a body is `{` … `}` inclusive)."""
    _check(body)
    count = punched.count(HOLE)
    if count != 1:
        raise NoHole(f"expected exactly one hole, found {count}")
    return punched.replace(HOLE, body, 1)


def _check(body: str) -> None:
    masked = mask(body)
    if not masked.strip().startswith("{") or not masked.strip().endswith("}"):
        raise UnbalancedBody("a body runs from '{' to its matching '}'")
    depth = 0
    for i, c in enumerate(masked):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and masked[i + 1 :].strip():
                raise UnbalancedBody("the body's first '{' closes before its text ends")
            if depth < 0:
                raise UnbalancedBody("a '}' closes what nothing opened")
    if depth != 0:
        raise UnbalancedBody(f"{depth} brace(s) left open")
