"""The Calvin M0 hole language, v0 (`docs/calvin-potential.md` §2.1, step 1 of §8).

A **template** is Hobbes's structural expansion of a task at one parent
SHA into typed **holes** the orchestrator fills. This module is the
schema of that artifact and nothing more: the hole types with their
fill shapes, a validator for a template and for a fill, and a renderer
that turns a template into the prompt a reader can fill without
instructions. It derives nothing — `hobbes template` (step 2) will
*produce* templates in this shape; this module says what the shape is
and holds it still (`TEMPLATE_VERSION`), so the generator, the adapter
(§2.2) and the grounder (§2.3) meet on one contract.

Every hole carries ``id``, ``type``, ``span`` (``{path, start, end}``
at the parent SHA, or ``None`` for a hole with no site yet — an
``ANCHOR``, an ``UNRESOLVED``, a ``NEW_SYMBOL``), ``constraints`` (the
write partition, a type where known), ``provenance`` (the anchor and
edge that produced it with its tier; for a ``MODULE_REGION`` the
symbols it sits between) and ``fill_schema`` — the shape named by
``FILL_SHAPES`` below. A hole may arrive **closed** (``closed: {reason}``,
a pruning rule fired) or **filled** (``fill``, ``fill_source``) — the
round-1 holes of a round-2 template are filled, so the reader sees what
was answered. Two shapes the hand-written template (step 1) added to the
design's table: a ``NEW_SYMBOL`` may be answered ``{"covered_by": [...]}``
when the new thing is a field or a local inside another hole's fill
rather than a new top-level symbol, and ``MODULE_REGION`` accepts the
same *pattern* fill as ``CALLER_UPDATE`` (every region ``unchanged``
in one answer), because a template over two files carries a dozen
regions and one hunk. And a ``FREEFORM`` hole is answered ``"none"``
when there is nothing the template did not anticipate — the reader
must be able to say so, or the hole cannot close.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

TEMPLATE_VERSION = 0

#: hole type → what it asks for (rendered) and the fill shape's name.
HOLE_TYPES: dict[str, str] = {
    "ANCHOR": "which symbols/files this task concerns",
    "ANCHOR_CONFIRM": "is this the right site / the right existing symbol",
    "UNRESOLVED": "classify these terms: new / refers / not-code",
    "SIGNATURE": "the new signature, or unchanged",
    "BODY": "code for this symbol span, or unchanged",
    "MODULE_REGION": "code for this module-level region, or unchanged",
    "CALLER_UPDATE": "does this caller change; how",
    "TEST_EXPECTATION": "what this test should now expect",
    "COCHANGE_TOUCH": "is this co-change partner touched; why",
    "NEW_SYMBOL": "name, file, position and body for something the graph lacks",
    "FREEFORM": "anything the template did not anticipate",
}

#: The fill shape per type, as a reader sees it. ``"unchanged"`` is the
#: literal string; ``?`` marks an optional key.
FILL_SHAPES: dict[str, str] = {
    "ANCHOR": '{"names": ["<symbol or file>", ...]}',
    "ANCHOR_CONFIRM": '{"confirm": true|false, "alternative"?: "<node id>"}',
    "UNRESOLVED": '{"classes": {"<term>": "new"|"refers"|"not-code", ...}, "refers_to"?: {"<term>": "<node id>"}}',
    "SIGNATURE": '"unchanged" | {"signature": "<one line>"}',
    "BODY": '"unchanged" | {"code": "<the whole span, rewritten>"}',
    "MODULE_REGION": '"unchanged" | {"code": "<the whole region, rewritten>"}',
    "CALLER_UPDATE": '{"decision": "yes"|"no", "reason": "<why>", "body"?: "<the caller span, rewritten>"}',
    "TEST_EXPECTATION": '"unchanged" | {"expectation": "<prose>", "code"?: "<the test, rewritten>"}',
    "COCHANGE_TOUCH": '{"decision": "yes"|"no", "reason": "<why>", "body"?: "<the file, rewritten>"}',
    "NEW_SYMBOL": '{"name": "<name>", "file": "<path>", "after_symbol"?: "<node id>", "region"?: "<hole id>", "body": "<code>"} | {"covered_by": ["<hole id>", ...]}',
    "FREEFORM": '"none" | {"code": "<code>", "span": {"path": "<path>", "start": <line>, "end": <line>}}',
}

#: Types whose holes may be answered together: ``patterns: {"<TYPE>": "unchanged"}``.
PATTERN_TYPES = ("CALLER_UPDATE", "MODULE_REGION", "TEST_EXPECTATION", "COCHANGE_TOUCH")
UNRESOLVED_CLASSES = ("new", "refers", "not-code")
REGION_KINDS = ("head", "imports", "gap", "tail")
ANCHOR_MATCHERS = ("backtick", "path", "test-id", "stack-trace", "literal", "bare-identifier")


# ---------------------------------------------------------------- validation

def _span_errors(span, where: str) -> list[str]:
    if span is None:
        return []
    if not isinstance(span, dict) or set(span) < {"path", "start", "end"}:
        return [f"{where}: span must be {{path, start, end}}"]
    if not (isinstance(span["start"], int) and isinstance(span["end"], int) and 1 <= span["start"] <= span["end"]):
        return [f"{where}: span lines must satisfy 1 <= start <= end"]
    return []


def validate_template(t: dict) -> list[str]:
    """Every defect in a template, in reading order; an empty list is a valid template."""
    errs: list[str] = []
    if t.get("template_version") != TEMPLATE_VERSION:
        errs.append(f"template_version must be {TEMPLATE_VERSION}")
    key = t.get("key") or {}
    for k in ("parent_sha", "task_hash"):
        if not key.get(k):
            errs.append(f"key.{k} missing")
    if not t.get("task"):
        errs.append("task missing")
    seen: set[str] = set()
    for i, a in enumerate(t.get("anchors", [])):
        if a.get("matcher") not in ANCHOR_MATCHERS:
            errs.append(f"anchors[{i}]: matcher must be one of {ANCHOR_MATCHERS}")
        if not a.get("term") or not a.get("nodes"):
            errs.append(f"anchors[{i}]: term and nodes required")
    for i, u in enumerate(t.get("unresolved", [])):
        if not u.get("term") or not isinstance(u.get("nearest"), list):
            errs.append(f"unresolved[{i}]: term and nearest (a list, recorded not used) required")
    holes = t.get("holes")
    if not isinstance(holes, list) or not holes:
        return errs + ["holes must be a non-empty list"]
    for h in holes:
        hid = h.get("id") or "<no id>"
        if hid in seen:
            errs.append(f"{hid}: duplicate id")
        seen.add(hid)
        typ = h.get("type")
        if typ not in HOLE_TYPES:
            errs.append(f"{hid}: unknown type {typ!r}")
            continue
        errs += _span_errors(h.get("span"), hid)
        if typ in ("SIGNATURE", "BODY", "MODULE_REGION", "CALLER_UPDATE", "TEST_EXPECTATION") and h.get("span") is None:
            errs.append(f"{hid}: a {typ} hole needs a span")
        if typ == "MODULE_REGION" and (h.get("provenance") or {}).get("kind") not in REGION_KINDS:
            errs.append(f"{hid}: MODULE_REGION provenance.kind must be one of {REGION_KINDS}")
        if h.get("fill_schema") != FILL_SHAPES[typ]:
            errs.append(f"{hid}: fill_schema must be FILL_SHAPES[{typ}]")
        if "provenance" not in h or "constraints" not in h:
            errs.append(f"{hid}: provenance and constraints required (may be empty)")
        if h.get("closed") is not None and not (h["closed"] or {}).get("reason"):
            errs.append(f"{hid}: a closed hole carries a reason")
        if "fill" in h:
            if not h.get("fill_source"):
                errs.append(f"{hid}: a filled hole names its fill_source")
            errs += [f"{hid}: {e}" for e in validate_fill(h, h["fill"])]
    for h in holes:
        ref = ((h.get("fill") or {}) if isinstance(h.get("fill"), dict) else {}).get("covered_by") or []
        for r in ref:
            if r not in seen:
                errs.append(f"{h['id']}: covered_by names an unknown hole {r!r}")
    return errs


def validate_fill(hole: dict, fill) -> list[str]:
    """Defects in one fill against its hole's shape; empty means it may go to the grounder."""
    typ = hole["type"]
    e: list[str] = []

    def need(keys):
        if not isinstance(fill, dict):
            e.append(f"expected an object {FILL_SHAPES[typ]}")
            return False
        for k in keys:
            if k not in fill:
                e.append(f"missing {k!r}")
        return not e

    def yes_no():
        if need(("decision", "reason")):
            if fill["decision"] not in ("yes", "no"):
                e.append("decision must be 'yes' or 'no'")
            if fill["decision"] == "yes" and not fill.get("body"):
                e.append("a 'yes' carries a body")

    if typ == "ANCHOR":
        if need(("names",)) and not (isinstance(fill["names"], list) and fill["names"]):
            e.append("names must be a non-empty list")
    elif typ == "ANCHOR_CONFIRM":
        if need(("confirm",)) and not isinstance(fill["confirm"], bool):
            e.append("confirm must be true or false")
    elif typ == "UNRESOLVED":
        if need(("classes",)):
            terms = {u["term"] for u in hole.get("terms", [])}
            for term, cls in fill["classes"].items():
                if cls not in UNRESOLVED_CLASSES:
                    e.append(f"{term!r}: class must be one of {UNRESOLVED_CLASSES}")
                if cls == "refers" and term not in (fill.get("refers_to") or {}):
                    e.append(f"{term!r}: 'refers' names its node in refers_to")
            for term in terms - set(fill["classes"]):
                e.append(f"{term!r}: not classified")
    elif typ in ("SIGNATURE", "BODY", "MODULE_REGION"):
        key = "signature" if typ == "SIGNATURE" else "code"
        if fill != "unchanged" and not (isinstance(fill, dict) and isinstance(fill.get(key), str) and fill[key].strip()):
            e.append(f'expected "unchanged" or {{"{key}": ...}}')
    elif typ in ("CALLER_UPDATE", "COCHANGE_TOUCH"):
        yes_no()
    elif typ == "TEST_EXPECTATION":
        if fill != "unchanged" and not (isinstance(fill, dict) and fill.get("expectation")):
            e.append('expected "unchanged" or {"expectation": ...}')
    elif typ == "NEW_SYMBOL":
        if isinstance(fill, dict) and "covered_by" in fill:
            if not (isinstance(fill["covered_by"], list) and fill["covered_by"]):
                e.append("covered_by must be a non-empty list of hole ids")
        elif need(("name", "file", "body")) and not (fill.get("after_symbol") or fill.get("region")):
            e.append("a placed NEW_SYMBOL names after_symbol or region (else it lands at end of file — say so with region: 'eof')")
    elif typ == "FREEFORM":
        if fill != "none" and need(("code", "span")):
            e += _span_errors(fill["span"], "span")
    return e


def validate_fills(t: dict, doc: dict) -> dict[str, list[str]]:
    """Errors per open hole id for a fills document ``{"fills": {...}, "patterns"?: {...}}``; a hole absent from both is ``missing``."""
    out: dict[str, list[str]] = {}
    fills = doc.get("fills") or {}
    patterns = doc.get("patterns") or {}
    for p in patterns:
        if p not in PATTERN_TYPES:
            out[f"patterns.{p}"] = [f"only {PATTERN_TYPES} take a pattern fill"]
    for h in t["holes"]:
        if h.get("closed") is not None or "fill" in h:
            continue
        if h["id"] in fills:
            errs = validate_fill(h, fills[h["id"]])
        elif h["type"] in patterns:
            errs = []
        else:
            errs = ["missing"]
        if errs:
            out[h["id"]] = errs
    return out


# ------------------------------------------------------------------ rendering

def span_text(repo_root: Path, sha: str, span: dict) -> str:
    """The span's lines at ``sha`` from git, numbered; the renderer's only read of the repo."""
    src = subprocess.run(["git", "show", f"{sha}:{span['path']}"], cwd=repo_root, capture_output=True, text=True, check=True).stdout
    lines = src.splitlines()[span["start"] - 1: span["end"]]
    width = len(str(span["end"]))
    return "\n".join(f"{n:>{width}}  {l}" for n, l in zip(range(span["start"], span["end"] + 1), lines))


def render(t: dict, repo_root: Path | None = None) -> str:
    """The template as the prompt a reader fills: task, anchors, what was answered, every open hole with its current code, the answer format."""
    sha = t["key"]["parent_sha"]
    out = [f"# Template {t['key']['task_hash']} @ {sha[:12]} (v{t['template_version']})", "", "## Task", "", t["task"].strip(), ""]
    out += ["## Anchors — what in the task names repo structure, and how it was found", ""]
    for a in t.get("anchors", []):
        out.append(f"- `{a['term']}` → {', '.join(a['nodes'])}  *(matcher: {a['matcher']}{'; ' + a['note'] if a.get('note') else ''})*")
    for u in t.get("unresolved", []):
        out.append(f"- `{u['term']}` → **unresolved**; nearest names in the graph (recorded, not used): {', '.join(u['nearest'])}")
    out.append("")
    answered = [h for h in t["holes"] if "fill" in h]
    closed = [h for h in t["holes"] if h.get("closed") is not None]
    open_ = [h for h in t["holes"] if "fill" not in h and h.get("closed") is None]
    if answered:
        out += ["## Already answered (round 1)", ""]
        for h in answered:
            out.append(f"- **{h['id']}** {h['type']} — {h.get('ask', HOLE_TYPES[h['type']])}: `{json.dumps(h['fill'])}` *(by {h['fill_source']})*")
        out.append("")
    out += ["## Holes to fill", "", "Answer each hole by id, in the shape shown. `\"unchanged\"` is an answer. "
            f"Holes of a type in {list(PATTERN_TYPES)} may be answered together with `patterns: {{\"<TYPE>\": \"unchanged\"}}`.", ""]
    for h in open_:
        out.append(f"### {h['id']} · {h['type']} — {h.get('ask', HOLE_TYPES[h['type']])}")
        if h.get("span"):
            s = h["span"]
            out.append(f"Span: `{s['path']}:{s['start']}-{s['end']}`")
        prov = h.get("provenance") or {}
        if prov:
            out.append("Why this hole: " + "; ".join(f"{k} = {v}" for k, v in prov.items()))
        cons = h.get("constraints") or {}
        if cons:
            out.append("Constraints: " + "; ".join(f"{k} = {v}" for k, v in cons.items()))
        if h.get("terms"):
            for term in h["terms"]:
                out.append(f"- `{term['term']}` — nearest: {', '.join(term['nearest'])}")
        if h.get("span") and repo_root is not None and h["type"] in ("SIGNATURE", "BODY", "MODULE_REGION", "CALLER_UPDATE", "TEST_EXPECTATION"):
            out += ["", "```", span_text(repo_root, sha, h["span"]), "```"]
        out += ["", f"Answer shape: `{h['fill_schema']}`", ""]
    if closed:
        out += ["## Closed before you (a pruning rule fired)", ""]
        for h in closed:
            out.append(f"- **{h['id']}** {h['type']} — {h['closed']['reason']}")
        out.append("")
    if t.get("neighborhood"):
        out += ["## Neighborhood (one hop out — context, not holes)", ""]
        for n in t["neighborhood"]:
            out.append(f"- `{n['node']}` — {n.get('note', '')} `{n['span']['path']}:{n['span']['start']}-{n['span']['end']}`" if n.get("span") else f"- `{n['node']}` — {n.get('note', '')}")
        out.append("")
    if t.get("constraints"):
        out += ["## Constraints on the whole answer", ""]
        for k, v in t["constraints"].items():
            out.append(f"- **{k}**: {v}")
        out.append("")
    out += ["## How to answer", "", "One JSON document:", "", "```", '{"fills": {"<hole id>": <fill>, ...}, "patterns": {"<TYPE>": "unchanged", ...}}', "```", ""]
    return "\n".join(out)
