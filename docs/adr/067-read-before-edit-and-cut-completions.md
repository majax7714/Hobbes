# ADR-067 — Read before edit, the reworded anchor stack, cut completions, and any fence

**Date:** 2026-08-22 · **Status:** accepted · **Amends:** the owned
agent loop (ADR-056), extending ADR-064's read-before-overwrite rule
and ADR-066's repeated-edit refusal.

## Context

The 5-fresh re-run on the ADR-066 harness (both arms, 0/5; the read is
in `benchmark-hypotheses.md` Results, 2026-08-22) showed that the two
ADR-066 fixes held and that four gaps remained between what the 7B
produced and what the harness kept:

1. **Edits from memory.** In nearly every implementer session the first
   turn is a prose "Changes made", and the `edit_file` calls that follow
   the nudge carry anchors the model *recalled* rather than copied —
   xarray-3993's U2 sent nine identical pairs against
   `def integrate(self, dim=None, **kwargs):`, a signature that does not
   exist, and never called `read_file`. ADR-064 gave `write_file` a
   read-before-overwrite rule; `edit_file` had none, so a guessed anchor
   cost the model one turn and taught it nothing.
2. **The reworded stack.** django-11400's U4 applied three *different*
   wordings of one block at one anchor; each `new_text` still contained
   the anchor, so each applied and stacked. ADR-066 refuses a
   byte-identical repeat and correctly did not fire.
3. **Cut completions.** sphinx-8548's planner wrote its `reflect` as a
   fenced JSON block that `--max-tokens 1536` cut mid-list — three times,
   each time nudged as prose because the loop never looked at
   `finish_reason`. A correct-shaped handoff was lost to the cap.
4. **The fence.** `_FENCED` accepted only ```` ```json ```` or bare fences
   with strict JSON; the 7B also writes ```` ```python ```` around JSON,
   forgets the closing fence, and puts real newlines inside a handoff's
   `"text"`.

## Decision

In `agent/loop.py`, both arms:

- **`edit_file` on a path this session has not `read_file`d is refused**,
  pointing at the read. The refusal names the rule: `old_text` is copied
  from the file as it is, not recalled. Same mechanism as ADR-064
  (`read_paths`), so a read of any range unlocks the path.
- **An edit at an already-applied anchor whose `new_text` still contains
  the anchor is refused** (`ANCHOR_STACK_REFUSAL`), keyed on
  `(path, old_text)`; an edit that consumed its anchor (new_text without
  it) frees the anchor for a later edit. The byte-identical refusal
  (ADR-066) is checked first and keeps its message.
- **A completion with `finish_reason == "length"` and no structured tool
  call is retried once at `CUT_RETRY_FACTOR` (2) × `max_tokens`**; the
  window fit (C-46) still bounds the retry. The cut prefix is discarded,
  not appended. If the retry is cut too, it stands as prose. The envelope
  carries `cut_retried`.
- **`text_tool_calls` accepts any fence tag, a fence never closed
  (end of content), and `json.loads(strict=False)`** so real newlines
  inside strings parse. Still counted as `text_tool_calls`.

## Consequences

- Four existing loop tests that edited without reading gained a read
  step — the guard changed their premise, not their intent (as ADR-064's
  tests did). The pure-arm token assertion moved with the extra turn.
- Forcing reads makes the window the binding constraint sooner: a brief
  of up to 16.7k tokens plus three or four 12k-char reads overflows 32k,
  and the fit then elides the reads the guard just required (C-46,
  measured). The brief's shape — 82 % neighborhood/guarding tests/
  contracts — is a derivation decision and is put to Max, not decided
  here.
- The cut retry doubles one completion's cost when it fires (~110 s at
  28 tok/s); `cut_retried` in every envelope keeps that visible.
- No new register entry: none of the four concedes information; each
  keeps or recovers model output the harness was discarding.

**Tests:** `TestReadBeforeEditAndCutCompletions` in
`tests/test_agent_loop.py`. 847 pytest.
