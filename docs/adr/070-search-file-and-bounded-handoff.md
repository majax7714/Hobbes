# ADR-070 — A search tool for the loop; the planner's handoff is bounded

**Date:** 2026-08-22 · **Status:** accepted · **Amends:** ADR-056
(the owned loop's tool set), ADR-059 (the planner brief), ADR-067.

## Context

The cheap 7B run on ADR-067/068/069 (`five-fresh-7b-adr069`, 0/5 both
arms; the read is in `benchmark-hypotheses.md`) showed the
read-before-edit rule doing exactly what it was built to do and not
being enough: the refusal fired, the model read the file, and it still
edited with a recalled anchor that does not exist. The per-call data
says why. **161 `read_file` calls, 40 clipped at 12k chars, one with a
line range.** xarray's `dataset.py` is 260,900 characters; `def
integrate` is at line 5,966; a whole-file read shows the imports. The
model never narrows a range on its own, and the loop gave it nothing to
find a line with — the pure arm has `bash` (and never grepped), the
harness arm has neither. 15 of the 18 sessions with anchor misses had a
clipped read.

Separately, the sphinx planner's fenced handoff was cut at 1,536 tokens
*and* at ADR-067's 3,072 retry: it enumerates every `sphinx/domains/*`
file (9,895 chars and still going). The retry is not the fix; a
60-file list is not a plan.

## Decision

- **`search_file`** joins the loop's native read-only tools, both arms:
  a Python regular expression over one file or every file under a
  directory of the working tree (confined like `read_file`; `.git`,
  `node_modules`, `__pycache__`, `.hobbes` skipped), returning
  `path:line: text`, capped (default 50 matches; 2,000 files). Its
  description says what it is for: find the line, then `read_file` that
  range and copy `old_text` from what you see.
- The clip notice (C-46) no longer says "read a narrower range"; it says
  **this is NOT the whole file** and names the search; the unread-edit
  refusal (ADR-067) names it too.
- **The planner handoff is bounded in its brief**: at most 5 files, 5
  symbols, 5 tests, under 15 lines, with the reason stated (a long
  handoff is cut and lost).

## Consequences

- A small model that reads the top of a file and guesses is now
  measurably its own fault: the search exists and the refusal points
  at it. `calls.jsonl` (ADR-068) shows whether it was used.
- The bound on the handoff is prompt-side; the parser is unchanged
  (no prose inference). If the planner still overflows, that is the
  model's.
- No new register entry: nothing is conceded; a tool and a bound are
  added.

**Tests:** `TestSearchFile`, `test_planner_brief_bounds_the_handoff`.
853 pytest.
