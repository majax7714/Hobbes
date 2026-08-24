"""Reading an agent's handoff (harness restructure, ADR-059).

A handoff is the one reflection an agent sends with ``kind: handoff``
— its job for the next agent, in short memory. The orchestrator asks
for a fixed, line-keyed shape (``files:``, ``symbols:``, ``tests:``,
``approach:``, ``risks:``, ``verdict:``, ``units:``, ``reason:``) and
reads it tolerantly: bullets, backticks, quotes and a JSON object are
all accepted, because a small model follows a schema loosely. What is
*not* done is inference from prose: a file that is not named is not
guessed, and a verdict that is not keyed is reported as inferred
rather than asserted.
"""

from __future__ import annotations

import json
import re

#: The keys the orchestrator reads, and the aliases a model tends to use.
LIST_FIELDS = ("files", "symbols", "tests", "units", "requirements")
#: List fields split on lines only — a requirement is a sentence and
#: carries commas of its own (ADR-085).
LINE_FIELDS = ("requirements",)
TEXT_FIELDS = ("approach", "risks", "verdict", "reason")
ALIASES = {
    "file": "files", "paths": "files", "path": "files", "modules": "files",
    "symbol": "symbols", "functions": "symbols", "function": "symbols", "classes": "symbols",
    "test": "tests", "tests_to_run": "tests", "tests to run": "tests", "run": "tests",
    "unit": "units", "rework": "units",
    "requirement": "requirements", "must become true": "requirements", "goals": "requirements",
    "acceptance": "requirements", "acceptance criteria": "requirements",
    "plan": "approach", "summary": "approach", "changes": "approach",
    "risk": "risks", "unverified": "risks", "could not verify": "risks",
    "result": "verdict", "status": "verdict", "outcome": "verdict",
    "why": "reason", "failure": "reason", "failures": "reason",
}
#: The verdicts a verifier or reviewer may return, normalised.
VERDICTS = {"pass": "pass", "passed": "pass", "passes": "pass", "ok": "pass", "green": "pass",
            "fail": "fail", "failed": "fail", "fails": "fail", "failing": "fail", "red": "fail",
            "approve": "approve", "approved": "approve", "accept": "approve", "lgtm": "approve",
            "amend": "amend", "revise": "amend", "reject": "amend", "change": "amend"}

_KEYED = re.compile(r"^\s*(?:[-*•]\s*)?(?:#+\s*)?[`*_]*([A-Za-z][A-Za-z _]{1,24}?)[`*_]*\s*[:=]\s*(.*)$")
#: A prose heading that ends in a colon — "The proposed changes touch the
#: following files:", "Tests guarding this behavior:" — opens the field a
#: word in it names. The first live 7B planner wrote exactly this shape
#: (astropy-13398) and named a gold file under it; the strict key parse
#: read `files: []`.
_HEADING = re.compile(r"^\s*(?:[-*•#]+\s*)?[`*_]*([A-Za-z][^:`]{0,80}?)[`*_]*\s*:\s*(.*)$")
#: A repo-relative path token: has a directory or an extension.
_PATHISH = re.compile(r"^[\w.-]+(?:/[\w.-]+)+(?:\.\w+)?$|^[\w-]+\.(?:py|ts|tsx|js|go|rs|c|h|cfg|toml|yaml|yml|ini|txt|rst|md)$")


#: Field keywords (canonical + single-word aliases) for splitting a
#: value that runs several fields onto ONE line — the xarray planner
#: wrote `**Handoff:** files: a.py, b.py  symbols: X  tests: t  approach:
#: …` on one line, and a line-only parser swallowed `symbols:`/`tests:`
#: into `files`. Multi-word aliases are left out; they do not appear
#: inline in practice.
_INLINE_KEYS = sorted({k for k in (*LIST_FIELDS, *TEXT_FIELDS, *ALIASES) if " " not in k},
                      key=len, reverse=True)
_INLINE = re.compile(r"\s+[`*_]*(" + "|".join(re.escape(k) for k in _INLINE_KEYS) + r")[`*_]*\s*[:=]\s*",
                     re.IGNORECASE)


def _split_inline(value: str) -> tuple[str, list[tuple[str, str]]]:
    """Split a single value that contains inline ``field:`` boundaries.

    Returns ``(head, extras)``: *head* is the part belonging to the
    field already in hand, *extras* the ``(field, value)`` pairs the
    inline keys open. No inline key → ``(value, [])`` unchanged, so a
    normal multi-line handoff is untouched."""
    matches = [m for m in _INLINE.finditer(value) if _norm_key(m.group(1))]
    if not matches:
        return value, []
    head = value[: matches[0].start()]
    extras: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        field = _norm_key(m.group(1))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(value)
        extras.append((field, value[m.end(): end]))
    return head, extras


def _clean(item: str) -> str:
    # Trailing sentence punctuation is the planner's prose, not the path
    # (ADR-071: `sympy/tests/test_zeta_functions.py.` went unresolved).
    return item.strip().strip("`'\"*-•[]() ").rstrip(".:;,").strip()


def _listify(value, lines_only: bool = False) -> list[str]:
    if isinstance(value, list):
        raw = [str(v) for v in value]
    elif lines_only:
        raw = str(value).splitlines()
    else:
        raw = re.split(r"[,\n;]+", str(value))
    out: list[str] = []
    for item in raw:
        item = _clean(item)
        if not lines_only:
            # "path (reason)" / "path — reason": keep the path
            item = re.split(r"\s+[—–-]\s+|\s+\(", item, maxsplit=1)[0].strip()
        if item and item.lower() not in ("none", "n/a", "-") and item not in out:
            out.append(item)
    return out


def _norm_key(key: str) -> str | None:
    k = key.strip().lower().replace("-", " ").replace("_", " ")
    k2 = k.replace(" ", "_")
    for candidate in (k, k2):
        if candidate in LIST_FIELDS or candidate in TEXT_FIELDS:
            return candidate
        if candidate in ALIASES:
            return ALIASES[candidate]
    return None


def _field_in_phrase(phrase: str) -> str | None:
    """The field a heading phrase names by one of its words — "Symbols
    to change", "Tests guarding this behavior", "the following files".
    The last matching word wins ("files to test" is about tests)."""
    words = re.findall(r"[a-z_]+", phrase.lower())
    found = None
    for w in words:
        f = _norm_key(w)
        if f:
            found = f
    return found


def parse_handoff(text: str) -> dict:
    """Parse a handoff into ``{field: value}`` with list fields as lists.

    Returns the fields present plus ``verdict_source`` (``keyed`` when a
    ``verdict:`` line was given, ``inferred`` when the word had to be
    found in prose, ``none`` otherwise) and ``raw`` — the text itself,
    which is what the record keeps.
    """
    out: dict = {"raw": text or "", "verdict_source": "none"}
    text = (text or "").strip()
    data = None
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
    if isinstance(data, dict):
        for key, value in data.items():
            field = _norm_key(str(key))
            if field in LIST_FIELDS:
                out[field] = _listify(value, lines_only=field in LINE_FIELDS)
            elif field in TEXT_FIELDS:
                out[field] = str(value).strip()
    else:
        current: str | None = None
        loose: list[str] = []  # path-shaped bullets under no field
        for line in text.splitlines():
            m = _KEYED.match(line)
            field = _norm_key(m.group(1)) if m else None
            rest = m.group(2).strip() if m else ""
            if not field:
                h = _HEADING.match(line)
                if h:
                    phrase, rest = h.group(1), h.group(2).strip()
                    # "Handoff: The proposed changes touch the following files:"
                    # — the field word may sit in the value's own heading.
                    tail = re.match(r"^(.*?):\s*(.*)$", rest)
                    field = _field_in_phrase(phrase)
                    if tail and not field:
                        field, rest = _field_in_phrase(tail.group(1)), tail.group(2).strip()
                    elif tail and field and _field_in_phrase(tail.group(1)):
                        field, rest = _field_in_phrase(tail.group(1)), tail.group(2).strip()
            if field:
                # A requirement line names its owner inline ("… -> file:
                # a.py"); splitting it would move the owner into `files`
                # and leave the requirement ownerless.
                head, extras = (rest, []) if field in LINE_FIELDS else _split_inline(rest)
                current = field
                out[field] = (out[field] + "\n" + head).strip() if field in out else head
                for f2, v2 in extras:
                    out[f2] = (out[f2] + "\n" + v2).strip() if f2 in out else v2
                    current = f2  # a continuation line belongs to the last inline field
            elif current and line.strip():
                out[current] = (out[current] + "\n" + line.strip()).strip()
            elif line.strip():
                item = _clean(line)
                if _PATHISH.match(item):
                    loose.append(item)
        for field in LIST_FIELDS:
            if field in out:
                out[field] = _listify(out[field], lines_only=field in LINE_FIELDS)
        if not out.get("files") and loose:
            # Named paths under no heading: kept as files, and said so —
            # they were written, not inferred from prose.
            out["files"] = _listify(loose)
            out["files_source"] = "path-shaped"
    if "verdict" in out:
        word = re.findall(r"[A-Za-z]+", str(out["verdict"]).lower())
        verdict = next((VERDICTS[w] for w in word if w in VERDICTS), "")
        if verdict:
            out["verdict"] = verdict
            out["verdict_source"] = "keyed"
        else:
            del out["verdict"]
    if "verdict" not in out:
        words = re.findall(r"[A-Za-z]+", text.lower())
        inferred = next((VERDICTS[w] for w in words if w in VERDICTS and VERDICTS[w] in ("pass", "fail")), "")
        if inferred:
            out["verdict"] = inferred
            out["verdict_source"] = "inferred"
    return out
