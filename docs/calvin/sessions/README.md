# Harness sessions — one file per dispatched session

> **These files are evaluation rows, never model training data**
> (ADR-107's retention amendment). They record the doer's output, never
> its reasoning or transcript, which are not stored. The git unit source
> of `hobbes derive-corpus` (`ttt.units.units_from_git`) skips this
> folder and every commit a doer authored.

Each file here is written by `hobbes dispatch` (ADR-107) when a session
ends. It is named by the session id (`S-<utc>-<4 hex>.md`), so the
files sort by time. The rule these files are read by is
[`../calvin-harness.md`](../calvin-harness.md) §4.

A file has two parts:

- **The harness's record**, written by the harness. Do not edit it:
  - the task's first line and hash;
  - the parent;
  - the doer's version, model and turns;
  - the egress tunnels and refusals;
  - the policy decisions;
  - the harvested branch and its files;
  - the gate's verdict with every row;
  - verify;
  - the doer's closing words.

  The full record is `dispatch.json` in the session's directory,
  beside the flight log, the egress log and the gate and verify
  records.
- **The review block** (`## Review`), filled by the developer after
  reading the diff:
  - `gate:` one of
    - `right-clear`: nothing a blocking class covers;
    - `right-block`: the block named a real error;
    - `false-block`: the block was wrong;
    - `missed`: an error inside a blocking class got through;
  - `outcome:` `merged`, `reworked` or `discarded`;
  - `notes:` free text.

  A `missed` found after the session is added here with the date it
  was found.

Commit a session's file with the work it produced, or on its own if
the work was discarded. Merge a doer's commit; never squash it, since
its authorship is what keeps it out of any training unit.

## Tracker

<!-- tracker:begin -->

| # | session | date | area | turns | wall | cost | gate | verify | review | outcome |
|---|---------|------|------|-------|------|------|------|--------|--------|---------|
| 1 | [96df](S-20260912T151728Z-96df.md) | 2026-09-12 | — | 1/40 | 3 s | $0.00 | clear | empty | n/a | discarded |
| 2 | [417f](S-20260912T151945Z-417f.md) | 2026-09-12 | knowledge tools | 38/40 | 3 min | $0.89 | clear | pass | right-clear | merged |
| 3 | [eef8](S-20260912T164904Z-eef8.md) | 2026-09-12 | extraction | 74/200 | 19 min | $4.68 | clear | pass | right-clear | merged |
| 4 | [e6db](S-20260912T171754Z-e6db.md) | 2026-09-12 | extraction | 68/150 | 12 min | $2.84 | clear | pass | right-clear | merged |
| 5 | [404f](S-20260912T174351Z-404f.md) | 2026-09-12 | knowledge tools | 25/60 | 3 min | $0.90 | clear | pass | right-clear | merged |
| 6 | [b126](S-20260912T191410Z-b126.md) | 2026-09-12 | — | — | 55 min | — | clear | empty | right-clear | discarded |
| 7 | [5d5f](S-20260912T201059Z-5d5f.md) | 2026-09-12 | oracle lane | 79/150 | 28 min | $5.20 | clear | pass | right-clear | merged |
| 8 | [9396](S-20260912T204447Z-9396.md) | 2026-09-12 | oracle lane | 127/150 | 22 min | $6.53 | clear | pass | right-clear | merged |
| 9 | [efc8](S-20260912T215521Z-efc8.md) | 2026-09-12 | harness and sandbox | 87/150 | 14 min | $4.30 | clear | pass | right-clear | merged |
| 10 | [42d1](S-20260912T221854Z-42d1.md) | 2026-09-12 | extraction | 99/200 | 14 min | $3.33 | clear | pass | right-clear | merged |
| 11 | [3c45](S-20260913T132457Z-3c45.md) | 2026-09-13 | knowledge tools | 25/150 | 4 min | $0.89 | clear | pass | right-clear | merged |
| 12 | [a323](S-20260913T145700Z-a323.md) | 2026-09-13 | extraction | 28/150 | 3 min | $0.71 | clear | pass | right-clear | merged |
| 13 | [2aa9](S-20260913T163921Z-2aa9.md) | 2026-09-13 | harness and sandbox | 57/150 | 6 min | $1.58 | clear | pass | right-clear | merged |
| 14 | [9cad](S-20260913T200618Z-9cad.md) | 2026-09-13 | harness and sandbox | 15/80 | 60 s | $0.29 | clear | pass | right-clear | merged |
| 15 | [e537](S-20260913T203100Z-e537.md) | 2026-09-13 | extraction | 26/150 | 9 min | $1.40 | clear | pass | right-clear | merged |
| 16 | [78b7](S-20260913T203123Z-78b7.md) | 2026-09-13 | harness and sandbox | 29/100 | 9 min | $1.36 | clear | pass | right-clear | merged |
| 17 | [81df](S-20260913T210133Z-81df.md) | 2026-09-13 | — | 19/60 | 2 min | $0.37 | clear | pass | right-clear | merged |
| 18 | [3ebb](S-20260914T004830Z-3ebb.md) | 2026-09-14 | harness and sandbox | 82/150 | 16 min | $4.42 | clear | pass | right-clear | merged |

18 of 40 sessions · areas: extraction, knowledge tools, oracle lane, harness and sandbox (4; at least 3) · false blocks 0 · missed 0
refusals: egress 16, policy escalations 22, denies 0 (each read in its session's notes, §4)
reported cost $39.71 over 17 of 18 sessions (the envelope's figure, on the subscription) · turns 879 · wall 220 min
This block is rendered by `pipeline/scripts/calvin_tracker.py render` from the logs and is not edited by hand.

<!-- tracker:end -->
