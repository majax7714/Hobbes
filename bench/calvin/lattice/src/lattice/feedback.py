"""The text a model is shown on a retry: what went wrong, in at most 1,500 characters, with no host path.

E1's iterate arm gives a failing body up to three rounds (§6), and this is what it gets back. Two rules
shape it. **It is built from the graded result's structured fields only** — the parsed diagnostics, the
first failing case, the invented names — never from raw compiler output, because raw output carries the
staged copy's absolute path and a path is a fact about this box, not about the target. And it is short:
a feedback message that carries the whole build log is a second prompt, and the arm would stop measuring
iteration and start measuring context length.

The order is the order a C programmer would read: it did not compile → these errors; it compiled and got
the wrong answer → this case; the slot was never installed → say so. Invented names ride along in every
case, because they are the thing §12.2's taxonomy is watching.
"""

from __future__ import annotations

__all__ = ["LIMIT", "build"]

#: The ceiling, in characters.
LIMIT = 1500

#: How many of each kind of line the message carries before it stops.
_ERRORS = 8
_LINKS = 4


def build(result: dict) -> str:
    """The feedback for one graded result. Empty for a `pass`."""
    if result.get("class") == "pass":
        return ""
    parts: list[str] = []
    errors = [d for d in result.get("diagnostics", []) if d["severity"] in ("error", "fatal error")]
    links = result.get("link_errors") or []

    if errors or links:
        parts.append("It did not compile.")
        parts += [f"{d['file']}:{d['line']}:{d['col']}: {d['severity']}: {d['message']}" for d in errors[:_ERRORS]]
        parts += list(links[:_LINKS])
        remaining = len(errors) - _ERRORS
        if remaining > 0:
            parts.append(f"({remaining} more error{'s' if remaining > 1 else ''}.)")
    elif result.get("first_failure"):
        failure = result["first_failure"]
        parts.append(
            f"It compiled, and case {failure['case']} disagrees with the scalar reference: "
            f"at n = {failure['n']} (seed {failure['seed']}) the reference gives {failure['expected']} "
            f"and this body gives {failure['got']}."
        )
        counts = result.get("bulk", {}), result.get("edge", {})
        parts.append(
            f"{counts[0].get('failed', 0)} of {counts[0].get('passed', 0) + counts[0].get('failed', 0)} bulk cases "
            f"and {counts[1].get('failed', 0)} of {counts[1].get('passed', 0) + counts[1].get('failed', 0)} edge cases fail."
        )
    elif result.get("reason"):
        parts.append(str(result["reason"]))

    invented = result.get("invented", [])
    if invented:
        named = ", ".join(f"{i['name']} ({i['bucket']})" for i in invented[:6])
        parts.append(f"These names resolve nowhere: {named}.")

    if not parts:
        parts.append(str(result.get("reason") or "It failed, and the graders said nothing about why."))
    return _trim("\n".join(parts))


def _trim(text: str) -> str:
    if len(text) <= LIMIT:
        return text
    return text[: LIMIT - 1].rstrip() + "…"
