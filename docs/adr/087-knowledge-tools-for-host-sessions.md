# ADR-087 — Hobbes for Hobbes: the knowledge tools in a host session

**Date:** 2026-08-24 · **Status:** accepted (Max's call) · **Amends:**
`docs/hobbes-architecture.md` (§4, one paragraph).

## Context

The extraction layer has been validated most thoroughly against this
repo (3,085 sites, 0 lane disagreements at the v2 exit; hand-checked
edges in every language it has), and the session proxy already serves
six read-only knowledge tools over `.hobbes/derived/` — but only inside
a sandboxed session. The agents that actually work on Hobbes (Claude
Code sessions on the host) answer "who calls this" by grepping, which
is where the false-negative edges come from, and never see the tail
view that would scope their check.

The project is opening to collaborators, and the first thing a
collaborator's agent should have is Hobbes' *evidence*: proven, honest
help, not the agentic layer. The agentic layer (`plan`/`run`) is under
restructure from a live defect register (D1–D8) and would put its own
known defects in the path of the work meant to fix them.

## Decision

1. `hobbes-proxy serve --knowledge-only` serves **only** the six
   knowledge tools (`graph_neighborhood`, `who_calls`, `tests_guarding`,
   `get_module_doc`, `list_invariants`, `list_blind_spots`). `exec` and
   `reflect` are **absent from the tool list, not present-and-refusing**
   — the sandbox rule (a forbidden command is absent) applied to a host
   session. No policy chain is consulted: the host session keeps its own
   shell and its own permission layer, and running two policy engines
   over one shell is the P10 shape (two safety systems, the broader wins
   by default). The flight recorder is still mandatory; every answer is
   logged under the session `host-knowledge`.
2. A repo-level `.mcp.json` starts it for any MCP-speaking agent on this
   repo (`go/bin/hobbes-proxy serve --repo . --role developer
   --knowledge-only`). The binary must be built (`CGO_ENABLED=0 go build
   …`) and the repo ingested (`hobbes ingest`); until then the server
   fails loudly at start rather than serving nothing.
3. Staleness stays visible, unchanged: every answer opens with
   `knowledge from ingest @ <sha>`, adds `(dirty tree)` when the ingest
   saw uncommitted edits, and a `WARNING … artifacts are stale; rerun
   hobbes ingest` line when HEAD has moved past the ingest. An agent
   mid-change is reading the graph of the tree *before* its edits; that
   is the right question for "who calls this" and the header says which
   tree it is.

## Consequences

- Hobbes contributes evidence to its own development; the first honest
  test of whether an agent *reaches for* `who_calls`/`list_blind_spots`
  when it has them (the 7B never did — a push-only rung) is a session
  on this repo. Observed uses land in the BUILDLOG.
- Not scoped: the agentic layer on the host; a `.mcp.json` for target
  repos (ADR-012 keeps `.hobbes/` personal there; a user can copy the
  entry). No new register entry: nothing is conceded that the header
  does not already surface.
- Validation task (proposed, not yet run): a change that a grep-only
  agent gets wrong for a Hobbes-visible reason — e.g. renaming a symbol
  with callers in more than one language lane, or editing under a
  directory whose blind-spot line names an unresolved class — and
  observe whether the tools are called and whether they change the
  edit.
