"""Cartographer prompts (ADR-020).

The skeleton is the context (§3.2): each prompt carries a work unit's
slice of the derived artifacts plus the subject file's source with line
numbers — the only lines the model may pin. Prompt text asks for bare
JSON; the runner still tolerates a stray fence, and ADR-019 validation
is what actually gates disk.
"""

from __future__ import annotations

import json
from pathlib import Path

#: Truncation guard for pathological files; every dogfood module is far
#: smaller. Pins past the cap would still validate (the file really has
#: those lines) but the model never sees them, so it is told to stop here.
MAX_SOURCE_LINES = 1500

PREAMBLE = """\
You are the Hobbes cartographer. You turn a repository's extracted skeleton
into precise, line-pinned documentation that humans review at the concept
level. Accuracy beats completeness: every sentence you write must be
supported by a specific line of the material shown to you.

Rules:
- Respond with ONLY a JSON object in the exact shape requested — no markdown
  fences, no commentary before or after.
- A pin is {"path": "<repo-relative path>", "line": <1-based integer>} and must
  point at a line, shown to you below, that supports the sentence it pins.
- Only pin lines you were shown. Never invent files, paths, or line numbers.
"""


def _numbered(path: Path, rel: str) -> str:
    lines = path.read_text(errors="replace").splitlines()
    shown = lines[:MAX_SOURCE_LINES]
    body = "\n".join(f"{i:5d}: {line}" for i, line in enumerate(shown, start=1))
    if len(lines) > MAX_SOURCE_LINES:
        body += (
            f"\n… truncated: {rel} continues to line {len(lines)}; "
            f"do not pin past line {MAX_SOURCE_LINES}."
        )
    return body


def _edge_lines(edges: list[dict], key: str) -> str:
    out = []
    for e in edges[:40]:
        cite = ", ".join(f"{ev['path']}:{ev['line']}" for ev in e["evidence"][:3])
        out.append(f"- {e[key]} [{e['type']}] ({cite})")
    return "\n".join(out) or "(none)"


def module_doc_prompt(
    repo_root: Path, unit, graph: dict, tests: dict, interfaces: dict
) -> str:
    """Prompt for one module doc: purpose, responsibilities, gotchas."""
    module_id, rel = unit.id, unit.path
    outgoing = [e for e in graph["module_edges"] if e["from"] == module_id]
    incoming = [e for e in graph["module_edges"] if e["to"] == module_id]
    symbols = [s for s in graph["symbols"] if s["module"] == module_id]
    symbol_lines = "\n".join(
        f"- {s['kind']} {s['qualname']} (line {s['line']})" for s in symbols[:60]
    ) or "(none extracted)"
    routes = [r for r in interfaces.get("routes", []) if r.get("file") == rel]
    route_lines = "\n".join(
        f"- {r['method']} {r['path']} → {r['handler']} ({r['file']}:{r['line']})"
        for r in routes[:20]
    )
    clis = [
        c
        for c in interfaces.get("cli_entry_points", [])
        if c.get("target", "").split(":")[0] == module_id
    ]
    cli_lines = "\n".join(f"- `{c['name']}` → {c['target']}" for c in clis[:10])
    interface_block = "\n".join(filter(None, [route_lines, cli_lines])) or "(none)"
    guarding = [
        t["id"] for t in tests["tests"] if module_id in t.get("reaches_modules", [])
    ]
    guarding_lines = "\n".join(f"- {t}" for t in guarding[:30]) or "(none)"

    return f"""{PREAMBLE}
Write the module doc for **{module_id}** ({rel}).

## Numbered source of {rel}
{_numbered(Path(repo_root) / rel, rel)}

## Skeleton context (from the extracted graph)
Imports / uses (outgoing edges):
{_edge_lines(outgoing, "to")}

Used by (incoming edges):
{_edge_lines(incoming, "from")}

Symbols defined here:
{symbol_lines}

Interfaces exposed here:
{interface_block}

Tests that statically reach this module:
{guarding_lines}

## Respond with exactly this JSON shape
{{
  "purpose": {{"text": "<one sentence: what this module is for>", "pins": [...]}},
  "responsibilities": [{{"text": "<one concrete duty>", "pins": [...]}}, ...],
  "gotchas": [{{"text": "<one non-obvious constraint or sharp edge>", "pins": [...]}}, ...]
}}

Guidance:
- purpose: one sentence, pinned to the line(s) that best evidence it (a doc
  comment counts as evidence only if the code around it agrees).
- responsibilities: 2–6 entries, each a duty this module actually carries,
  pinned to the code that carries it.
- gotchas: 0–4 entries, only genuinely non-obvious things — invariants the
  code relies on, ordering requirements, deliberate pins/workarounds. An
  empty list is better than a padded one.
- Pin lines from the numbered source above ({rel} or the cited
  evidence lines shown in the skeleton context)."""


def test_doc_prompt(repo_root: Path, unit) -> str:
    """Prompt for one test file's behavior index: one line per test."""
    rel = unit.path
    test_rows = "\n".join(
        f"- {t['id']} (line {t['line']}, reaches: "
        f"{', '.join(t.get('reaches_modules', [])[:6]) or 'nothing extracted'})"
        for t in unit.tests
    )
    return f"""{PREAMBLE}
Write the behavior index for the test file **{rel}**: one line per test
describing the *behavior it pins down* — what the system guarantees, not what
the test does.

## Numbered source of {rel}
{_numbered(Path(repo_root) / rel, rel)}

## Tests in this file (use these ids exactly, each exactly once)
{test_rows}

## Respond with exactly this JSON shape
{{
  "behaviors": [
    {{"test": "<pytest id exactly as listed>",
      "text": "<one line: the behavior this test guarantees>",
      "pins": [...]}},
    ...
  ]
}}

Guidance:
- text: a single line under 140 characters, present tense, stated as a
  guarantee ("rotating a refresh token invalidates the prior token") — never
  "tests that ..." and never a restatement of the test's name.
- pins: the assertion line(s) in this test's body that pin the behavior.
- Cover every listed test id exactly once; add nothing else."""


def invariants_prompt(
    repo_root: Path,
    graph: dict,
    tests: dict,
    interfaces: dict,
    module_purposes: list[tuple[str, str]],
) -> str:
    """Prompt for repo-wide inferred invariants (§3.2, §10 schema)."""
    edge_rows = "\n".join(
        f"- {e['from']} → {e['to']} [{e['type']}] "
        f"({e['evidence'][0]['path']}:{e['evidence'][0]['line']})"
        for e in graph["module_edges"]
    )
    purpose_rows = "\n".join(f"- {mid}: {text}" for mid, text in module_purposes)
    cli_rows = "\n".join(
        f"- `{c['name']}` → {c['target']}"
        for c in interfaces.get("cli_entry_points", [])
    ) or "(none)"
    test_ids = "\n".join(f"- {t['id']}" for t in tests["tests"])
    policy = Path(repo_root) / ".hobbes" / "policies" / "repo.policy"
    policy_block = (
        f"## Repo policy (.hobbes/policies/repo.policy, numbered, pinnable)\n"
        f"{_numbered(policy, '.hobbes/policies/repo.policy')}\n"
        if policy.is_file()
        else ""
    )
    return f"""{PREAMBLE}
Infer the **invariants** this repository appears to rely on: explicit rules a
change could silently break ("only auth-core may mint tokens"). They will be
flagged `inferred` and are inert until a human confirms them.

## Module dependency edges (each with a pinnable evidence line)
{edge_rows}

## Module purposes (from the generated module docs)
{purpose_rows}

## CLI entry points
{cli_rows}

{policy_block}## Test ids (for guarded_by, use exactly as listed)
{test_ids}

## Respond with exactly this JSON shape
{{
  "invariants": [
    {{"statement": "<declarative rule the code relies on>",
      "scope": "<narrowest repo path prefix the rule governs>",
      "evidence": [{{"path": "...", "line": ...}}, ...],
      "guarded_by": ["<test id from the list, only if it clearly guards this>"]}},
    ...
  ]
}}

Guidance:
- 3 to 8 invariants; prefer few and load-bearing over many and trivial.
- statement: declarative and checkable in principle, not a vague aspiration.
- evidence: pin the enforcement or reliance sites using the evidence lines
  shown above (or repo-policy lines); at least one pin each.
- guarded_by: empty list unless a listed test id clearly guards the rule."""
