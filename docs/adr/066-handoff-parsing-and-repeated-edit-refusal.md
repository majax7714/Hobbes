# ADR-066 — Two harness fixes the 5-fresh set surfaced: inline handoff fields, and refusing a repeated identical edit

**Date:** 2026-08-22
**Status:** accepted — both are harness defects that discarded or
corrupted correct model output on the 5-fresh set; fixed before any
model-rung re-evaluation (the standing rule: resolve the harness's
contribution first).
**Amends:** `docs/hobbes-architecture.md` (none of substance — behaviour
of two existing mechanisms).

## Context

The 5-fresh set (django/sympy/xarray/sphinx/scikit-learn, 0/5) was read
by hand. Two of the failures were not the model:

1. **A correct planner handoff was thrown away.** The xarray planner
   named both gold files (`xarray/core/dataset.py`, `dataarray.py`) and
   the right fix (dim→coord) — but wrote every field on **one line**
   after a markdown `**Handoff:**` prefix. `parse_handoff` split fields
   only at line breaks, so `files:` swallowed `symbols:`/`tests:`/
   `approach:` into itself, producing unresolvable garbage → recorded
   `0/2`, seed fell to lexical. It should have been `2/2`.
2. **A grounded edit was corrupted into dead code.** django's U4
   repeated a **byte-identical** `edit_file` four times (its test kept
   failing, so it retried the same edit). `edit_file`'s `new_text`
   re-includes its `old_text` anchor, so the anchor still matches after
   the first edit and each repeat **stacks another copy**. The loop
   refuses repeated reads and execs but explicitly allowed repeated
   edits — four stacked blocks, everything after the first `return`
   dead.

## Decision

1. **Inline handoff fields.** `parse_handoff` splits a value at inline
   `field:` boundaries (`_split_inline`), so a single line carrying
   several fields is parsed into each. Multi-line handoffs are
   untouched (no inline key → value returned unchanged), and the
   no-prose-inference principle stands: a file not named in a
   `field:`-shaped position is still not guessed. Pure-prose handoffs
   (sympy named `polylog` in a sentence) remain unparsed by design —
   that is a planner-brief question, not a parser one.
2. **Refuse a repeated identical edit.** The loop records each
   successful non-exec mutating call and refuses a byte-identical
   repeat (`EDIT_REPEAT_REFUSAL`) — the `edit_file`/`write_file` analog
   of the exec-repeat refusal. A genuinely different edit is still
   allowed; the refusal counts toward the stall guard, so a model that
   can only repeat itself terminates instead of corrupting the file.

## Consequences

- xarray's planner handoff now resolves to both gold files (verified on
  the recorded handoff text); the recorded 2/5 planner localization on
  the set was a parser artifact, ~4/5 is the real figure.
- A retrying small model can no longer stack duplicate edits; it is
  pushed to read and try something else, or to stop.
- Neither change touches the model or the pure/harness symmetry — both
  arms run the same loop and the same parser.
- Tests: `test_inline_fields_on_one_line_are_split_not_swallowed`
  (handoff), `test_a_repeated_identical_edit_is_refused` (loop).
- Not addressed here (a separate, prompt-side lever): pushing the
  planner to emit the structured handoff shape so a pure-prose handoff
  like sympy's is not the parser's problem to begin with.
