"""Requirement coverage — the planner's guarantee (ADR-084, ADR-085).

The planner is the **requirement-decomposer**: its handoff carries not
just *where* the change goes (``files:``) but *what must become true*
(``requirements:``), each requirement naming the file that owns it. This
module reads those requirements, assigns each to the unit whose interior
holds its file, and states the result as a **coverage** record:

- ``covered`` — every requirement has an owning unit (⋃ handoffs ⊇ the
  request). The implementers' briefs then carry their owned
  requirements as the task and the proposal leaves the brief.
- ``uncovered`` — a requirement names no file in any unit's interior.
  That is the sympy-13852 defect (value-eval stated in the issue, no
  owner, never implemented). The staged run re-plans once with the
  uncovered requirements in the planner's inbox, then either stops at
  plan cost (``strict``) or assigns the leftovers to the seed unit and
  says so (``assign``, C-57).
- ``no-requirements`` — the planner hand-off carried no requirements
  at all (the pre-085 shape). Coverage cannot be judged; the proposal
  stays in every brief and the record says why.

Ownership here is **by named file**, never by meaning: a requirement
whose file resolves to a unit's interior is that unit's; one that names
no file is the unit's only when the whole plan lies in a single unit (a
contained change has one possible owner). Nothing is inferred from the
requirement's prose — that is the planner's job, and the model's
opinion (C-47). The same honesty bounds :func:`imperatives_unmentioned`,
the cheap precursor ADR-084 asked for: it is a lexical diff of the
proposal's imperative sentences against everything the planner wrote,
reported as a measure of the gap, never as a verdict.
"""

from __future__ import annotations

import re

from hobbes.run.orchestrate import RunError

COVERAGE_MODES = ("strict", "assign")

#: The words that open an imperative or obligation sentence in a
#: request — a pinned list, so what counts as an imperative is a
#: checkable observation, not a judgement (C-57).
IMPERATIVE_VERBS = frozenset("""
add allow avoid change check consider convert create deprecate disable
document drop emit enable ensure expose extend fix handle implement
improve include make move prevent provide raise refactor remove rename
replace require return support throw update use validate warn
""".split())
MODALS = re.compile(r"\b(should|must|needs? to|ought to|has to|have to|shall)\b", re.IGNORECASE)
#: A repo-relative path token: has a directory or a source extension.
_PATH_SRC = (r"(?:[A-Za-z_][\w.-]*/)+[A-Za-z_][\w.-]*|[A-Za-z_][\w-]*\.(?:py|ts|tsx|js|go|rs|c|h|cfg|toml|yaml|yml|ini|rst|md)")
PATHISH = re.compile(r"(?<![\w/])(" + _PATH_SRC + r")(?![\w/])")
_ID_PREFIX = re.compile(r"^\s*(?:[-*•]\s*)?(?:(?:R|REQ|req|r)?\s*(\d+)\s*[.):\-–—]\s*)?(.*)$")
#: An explicit owner clause: a marker, then nothing but paths to the end
#: of the line. Prose after the marker is not an owner clause.
_OWNER = re.compile(r"\s*(?:(?:->|→|=>|@|\||\(?(?:owner|owned by|file|files|in)\s*:)\s*)+[`(\[]*"
                    r"((?:" + _PATH_SRC + r")(?:[`\])]*\s*(?:,|and|/)?\s*[`(\[]*(?:" + _PATH_SRC + r"))*)[`\])]*\s*$",
                    re.IGNORECASE)
_STOP = frozenset("""
the a an of to in on for and or is are be was were it this that with as by
at from into than then so not no if when which who whom whose what where
there here its it's their they them these those we you i he she his her
also should must would could can may might shall since because
""".split())


class PlanCoverageError(RunError):
    """The planner's handoffs do not cover the request (ADR-084): a
    requirement has no owning unit, or no requirements were stated.
    Raised at plan cost, like the invariant gate — never after a
    session has been spent on an unowned requirement."""

    def __init__(self, coverage: dict):
        self.coverage = coverage
        status = coverage.get("status")
        if status == "no-requirements":
            detail = "the planner stated no requirements (ADR-084: its handoff must say what must become true)"
        else:
            names = "; ".join(f"{r['id']}: {r['text'][:80]}" for r in coverage.get("uncovered", []))
            detail = f"requirement(s) with no owning unit — {names}"
        super().__init__(f"plan coverage failed ({status}): {detail}")


def _stem(token: str) -> str:
    """A crude suffix strip so `removed`/`remove`/`removes` and
    `term`/`terms` meet — the comparison is lexical either way (C-57)."""
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            token = token[: -len(suffix)]
            break
    return token[:-1] if token.endswith("e") and len(token) > 4 else token


def _tokens(text: str) -> set[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text or "")
    return {_stem(t) for t in re.split(r"[^A-Za-z0-9_]+", spaced.lower())
            if len(t) >= 3 and t not in _STOP and not t.isdigit()}


def parse_requirement(line: str, index: int) -> dict | None:
    """One handoff requirement line → ``{id, text, files}``.

    Accepts ``R1: text -> path``, ``1. text (path)``, ``- text @ path``
    and a bare sentence. *files* are the path-shaped tokens the line
    names, the owner clause's first. A line that is only a path or
    empty is not a requirement."""
    raw = (line or "").strip().strip("`*_")
    if not raw:
        return None
    m = _ID_PREFIX.match(raw)
    number, body = (m.group(1), m.group(2)) if m else (None, raw)
    body = body.strip().strip("`*_\"' ")
    owner_files: list[str] = []
    om = _OWNER.search(body)
    if om:
        owner_files = [p for p in PATHISH.findall(om.group(1))]
        body = body[: om.start()].rstrip(" ,;:-")
    files = list(dict.fromkeys(owner_files + PATHISH.findall(body)))
    files = [f.strip("`'\"()[],.;:") for f in files]
    files = [f for f in files if f and ("/" in f or re.search(r"\.\w+$", f))]
    text = body.strip().rstrip(".;,")
    # Nothing but paths and punctuation is a file list, not a requirement.
    if not re.search(r"[A-Za-z]", PATHISH.sub("", text)):
        return None
    return {"id": f"R{number or index}", "text": text, "files": files}


def requirements_from_handoff(handoff: dict) -> list[dict]:
    """The requirements a parsed handoff carries, numbered in order;
    ids the planner wrote are kept, unnumbered lines counted on."""
    out: list[dict] = []
    for i, line in enumerate(handoff.get("requirements", []) or [], start=1):
        req = parse_requirement(str(line), i)
        if req:
            if any(r["id"] == req["id"] for r in out):
                req["id"] = f"R{len(out) + 1}"
            out.append(req)
    return out


def in_interior(term: str, module: str | None, ids: set[str], paths: list[str]) -> bool:
    """A named term is a unit's when it resolved to one of the unit's
    interior module ids or path-matches one of its interior files."""
    if module in ids:
        return True
    bare = term.strip().lstrip("./")
    return any(p == bare or p.endswith("/" + bare) or bare.endswith("/" + p) for p in paths if p)


def assign_requirements(requirements: list[dict], terms: dict[str, str | None],
                        contexts: dict[str, dict], planner_files: list[str],
                        mode: str = "strict", seed_unit: str | None = None) -> dict:
    """Give each requirement its owning unit and state the coverage.

    *terms* is the plan stage's ``term → module id`` map; *contexts*
    the spec's per-unit contexts; *planner_files* the handoff's
    ``files:``. A requirement with files is owned by the unit(s) whose
    interior holds one; with no files it is owned by the one unit the
    whole plan lies in, else uncovered. In ``assign`` mode an uncovered
    requirement is given to *seed_unit* (the unit holding the planner's
    first resolved file, or the first unit), recorded as
    ``source: assigned`` — the orchestrator's fallback, not the
    planner's guarantee (C-57). Returns::

        {"status": covered|uncovered|assigned|no-requirements,
         "mode": …, "requirements": [{id, text, files, units, source}],
         "uncovered": [...], "by_unit": {unit: [ids]}}
    """
    interiors = {
        unit: ({m.get("id") for m in ctx.get("modules", [])},
               [m.get("path", "") for m in ctx.get("modules", [])])
        for unit, ctx in contexts.items()
    }

    def owners_of(files: list[str]) -> list[str]:
        found = []
        for f in files:
            for unit, (ids, paths) in interiors.items():
                if in_interior(f, terms.get(f), ids, paths) and unit not in found:
                    found.append(unit)
        return found

    plan_owners = owners_of(planner_files)
    # Every file the planner named lies in ONE unit: a requirement that
    # names no file can only be that unit's (a contained change).
    contained = plan_owners[0] if len(plan_owners) == 1 else None
    if seed_unit is None:
        seed_unit = plan_owners[0] if plan_owners else (next(iter(contexts)) if contexts else None)

    if not requirements:
        return {"status": "no-requirements", "mode": mode, "requirements": [], "uncovered": [],
                "by_unit": {}, "seed_unit": seed_unit}
    rows, uncovered, by_unit = [], [], {}
    for req in requirements:
        units = owners_of(req["files"])
        source = "named-file" if units else ""
        if not units and not req["files"] and contained:
            units, source = [contained], "contained"
        row = {**req, "units": units, "source": source}
        if not units:
            uncovered.append(row)
        rows.append(row)
    status = "uncovered" if uncovered else "covered"
    if uncovered and mode == "assign" and seed_unit:
        for row in uncovered:
            row["units"], row["source"] = [seed_unit], "assigned"
        status = "assigned"
    for row in rows:
        for unit in row["units"]:
            by_unit.setdefault(unit, []).append(row["id"])
    return {"status": status, "mode": mode, "requirements": rows,
            "uncovered": [r for r in rows if not r["units"]] if status != "assigned" else uncovered,
            "by_unit": by_unit, "seed_unit": seed_unit}


def unit_task(coverage: dict, unit: str) -> str:
    """The requirement block a unit's brief carries as its task — its
    owned requirements verbatim, each with the file that owns it and,
    for an orchestrator-assigned one, that fact stated."""
    mine = [r for r in coverage.get("requirements", []) if unit in r.get("units", [])]
    if not mine:
        return ""
    lines = []
    for r in mine:
        where = f" — in {', '.join(r['files'])}" if r.get("files") else ""
        note = ""
        if r.get("source") == "assigned":
            note = " (assigned to you by the orchestrator: the planner named no owner, C-57)"
        elif r.get("source") == "contained":
            note = " (the whole change lies in your unit)"
        lines.append(f"- {r['id']}: {r['text']}{where}{note}")
    return "\n".join(lines)


def _sentences(text: str) -> list[str]:
    """Prose sentences of a request: fenced code blocks and
    interpreter transcripts are removed first (they are evidence, not
    imperatives), then lines split at sentence punctuation."""
    text = re.sub(r"```.*?```", " ", text or "", flags=re.DOTALL)
    text = re.sub(r"^\s*(?:In \[\d+\]|Out\[\d+\]|>>>|\.\.\.|\$|#)\s.*$", " ", text, flags=re.MULTILINE)
    out = []
    for line in re.split(r"\n{2,}", text):
        flat = re.sub(r"\s+", " ", line)
        out += [s.strip() for s in re.split(r"(?<=[.!?])\s+|;\s+", flat) if s.strip()]
    return out


def imperatives(proposal: str) -> list[str]:
    """The proposal's imperative or obligation sentences — those that
    open with a pinned verb or carry a modal. Code blocks and bare
    paths are not sentences; a sentence under four words is noise."""
    out = []
    for s in _sentences(proposal):
        words = re.findall(r"[A-Za-z']+", s)
        if len(words) < 4:
            continue
        first = words[0].lower()
        if first in IMPERATIVE_VERBS or MODALS.search(s):
            out.append(s)
    return out


def imperatives_unmentioned(proposal: str, handoff_texts: list[str], share: float = 0.5) -> list[str]:
    """Imperative sentences of the proposal fewer than *share* of whose
    content tokens appear anywhere in the planner's handoff text(s) —
    the requirements the planner may have dropped (ADR-084's cheap
    precursor). Lexical, so a paraphrase can be reported as dropped and
    a token-sharing sentence as kept: a measure of the gap, not a
    verdict (C-57)."""
    said = set()
    for t in handoff_texts:
        said |= _tokens(t)
    dropped = []
    for s in imperatives(proposal):
        toks = _tokens(s)
        if not toks:
            continue
        hit = len(toks & said) / len(toks)
        if hit < share:
            dropped.append(s)
    return dropped
