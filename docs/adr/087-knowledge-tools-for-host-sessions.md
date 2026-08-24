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

## First observation (2026-08-24, the rename probe)

Run the same day in a fresh headless session (`claude -p`, Claude Code
2.1.241, this repo's `.mcp.json`, permission mode acceptEdits, prompt:
rename `hobbes.extract.ingest` → `ingest_repo`, update callers, run the
covering tests, report how the callers were found — **nothing in the
prompt named the tools**). Session id `host-knowledge`; the three tool
calls are in its flight log at 18:41:11–12Z.

- **The agent reached for the tools unprompted, first** — turn ~2,
  before any grep: `who_calls hobbes.extract.ingest`, then
  `tests_guarding hobbes.extract`, then `list_blind_spots
  pipeline/src/hobbes/extract`. Three calls total; none repeated.
- **`who_calls` was complete and precise**: 9 call edges + 5
  non-call references across the four caller files, including the
  two *function-local* imports in `tests/test_tssource.py`
  (`:550`, `:572`) — exactly the hits a word-grep for `ingest`
  (CLI verb, subcommand, `_cmd_ingest`, docstrings, BUILDLOG) buries.
  Verified after the run by re-issuing the call.
- **The blind-spot line changed behaviour, the way it is meant to**:
  the agent cited C-1 (dynamic dispatch / calls through values) as the
  reason it did *not* trust the graph alone and ran a cross-check grep,
  which found the same callers plus the docstring `:func:` references
  the graph does not model. Graph for callers, grep for prose — the
  division the tools' descriptions argue for, arrived at by the agent.
- **`tests_guarding` was used to scope the run**: targeted 138 tests
  first (test_emit, test_tssource, test_cli, test_bench), then the full
  suite.
- Result: 5 files, 19 lines, correct; 895/896 pass — the one failure
  (`test_scipsource … test_venv_environment_lists_the_venvs_own_distributions`)
  fails identically on clean `main` and was correctly attributed to the
  environment. 32 turns, 131 s, $1.44. The edits were discarded — the
  rename was the probe, not a wanted change.
- Honest scope of the observation: n = 1, a frontier model, a task the
  tools are built for. It says the tools are *reached for* and *change
  the work* under those conditions; it says nothing about weaker
  models (the 7B never called one) or about tasks where the graph's
  answer is wrong. `git status`/`git diff` were outside the probe's
  allowlist, so the agent's file list came from its own edits — a
  harness detail, not a Hobbes one.
