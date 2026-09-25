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
| 19 | [de81](S-20260914T010846Z-de81.md) | 2026-09-14 | harness and sandbox | 94/150 | 21 min | $6.69 | clear | pass | right-clear | merged |
| 20 | [47f7](S-20260914T015405Z-47f7.md) | 2026-09-14 | extraction | 25/100 | 4 min | $0.79 | clear | pass | right-clear | merged |
| 21 | [1ae3](S-20260914T022459Z-1ae3.md) | 2026-09-14 | extraction | 17/100 | 94 s | $0.45 | clear | pass | right-clear | merged |
| 22 | [d2e3](S-20260914T131039Z-d2e3.md) | 2026-09-14 | oracle lane | 40/60 | 5 min | $1.04 | clear | pass | right-clear | merged |
| 23 | [3c41](S-20260914T144539Z-3c41.md) | 2026-09-14 | oracle lane | 45/80 | 3 min | $1.10 | clear | pass | right-clear | merged |
| 24 | [cd8e](S-20260914T153042Z-cd8e.md) | 2026-09-14 | harness and sandbox | 22/60 | 76 s | $1.11 | clear | pass | right-clear | merged |
| 25 | [3d56](S-20260914T161248Z-3d56.md) | 2026-09-14 | extraction, knowledge tools | 142/200 | 28 min | $18.67 | clear | pass | right-clear | merged |
| 26 | [a848](S-20260914T161308Z-a848.md) | 2026-09-14 | oracle lane | 139/200 | 25 min | $16.08 | clear | pass | right-clear | merged |
| 27 | [be34](S-20260915T001249Z-be34.md) | 2026-09-15 | extraction | 114/150 | 14 min | $10.84 | clear | pass | right-clear | merged |
| 28 | [3d1a](S-20260915T015439Z-3d1a.md) | 2026-09-15 | extraction | 32/80 | 4 min | $2.23 | clear | pass | right-clear | merged |
| 29 | [f3c1](S-20260915T135819Z-f3c1.md) | 2026-09-15 | extraction | 59/120 | 9 min | $4.92 | blocked | pass | false-block | merged |
| 30 | [8302](S-20260915T161919Z-8302.md) | 2026-09-15 | extraction | 77/120 | 9 min | $6.48 | clear | pass | right-clear | merged |
| 31 | [2b26](S-20260915T191904Z-2b26.md) | 2026-09-15 | harness and sandbox | 27/80 | 4 min | $1.57 | clear | pass | right-clear | merged |
| 32 | [8170](S-20260916T153010Z-8170.md) | 2026-09-16 | oracle lane | 77/120 | 12 min | $7.21 | clear | pass | right-clear | merged |
| 33 | [8d48](S-20260916T155426Z-8d48.md) | 2026-09-16 | oracle lane | 36/100 | 4 min | $1.49 | clear | pass | right-clear | merged |
| 34 | [16f4](S-20260916T165315Z-16f4.md) | 2026-09-16 | oracle lane | 79/100 | 10 min | $5.11 | clear | pass | right-clear | merged |
| 35 | [d95c](S-20260916T225041Z-d95c.md) | 2026-09-16 | extraction | 32/100 | 5 min | $2.08 | clear | pass | right-clear | merged |
| 36 | [5261](S-20260916T230256Z-5261.md) | 2026-09-16 | oracle lane | 57/100 | 8 min | $4.09 | clear | pass | right-clear | merged |
| 37 | [367f](S-20260916T231525Z-367f.md) | 2026-09-16 | extraction | 29/80 | 3 min | $1.37 | clear | pass | right-clear | merged |
| 38 | [4338](S-20260917T130613Z-4338.md) | 2026-09-17 | extraction | 41/120 | 5 min | $2.37 | clear | pass | right-clear | merged |
| 39 | [145d](S-20260917T132019Z-145d.md) | 2026-09-17 | extraction, knowledge tools, harness and sandbox | 94/140 | 11 min | $7.19 | clear | pass | right-clear | merged |
| 40 | [b0ed](S-20260917T134335Z-b0ed.md) | 2026-09-17 | extraction, knowledge tools | 61/140 | 7 min | $3.27 | clear | pass | right-clear | merged |
| 41 | [d238](S-20260917T142335Z-d238.md) | 2026-09-17 | extraction | 34/80 | 4 min | $1.57 | clear | pass | right-clear | merged |
| 42 | [9943](S-20260917T153835Z-9943.md) | 2026-09-17 | extraction | 34/80 | 6 min | $2.31 | clear | fail | right-clear | merged |
| 43 | [1ef9](S-20260917T154724Z-1ef9.md) | 2026-09-17 | extraction | 66/80 | 7 min | $3.30 | clear | pass | right-clear | merged |
| 44 | [6956](S-20260917T155937Z-6956.md) | 2026-09-17 | extraction | 58/80 | 8 min | $3.61 | clear | pass | right-clear | merged |
| 45 | [77da](S-20260917T172122Z-77da.md) | 2026-09-17 | extraction | 95/140 | 16 min | $8.92 | clear | pass | right-clear | merged |
| 46 | [4048](S-20260917T174302Z-4048.md) | 2026-09-17 | extraction, knowledge tools, harness and sandbox | 125/140 | 18 min | $12.26 | clear | pass | right-clear | merged |
| 47 | [b597](S-20260917T180521Z-b597.md) | 2026-09-17 | knowledge tools | 40/100 | 4 min | $1.90 | clear | pass | right-clear | merged |
| 48 | [d1b9](S-20260917T183820Z-d1b9.md) | 2026-09-17 | extraction | 92/140 | 13 min | $8.63 | clear | pass | right-clear | merged |
| 49 | [4033](S-20260917T202723Z-4033.md) | 2026-09-17 | extraction | 36/80 | 4 min | $1.78 | clear | pass | right-clear | merged |
| 50 | [4834](S-20260917T205400Z-4834.md) | 2026-09-17 | extraction | 84/140 | 15 min | $8.57 | clear | pass | right-clear | merged |
| 51 | [3569](S-20260918T131437Z-3569.md) | 2026-09-18 | extraction | 26/80 | 4 min | $1.78 | clear | pass | right-clear | merged |
| 52 | [368a](S-20260918T160737Z-368a.md) | 2026-09-18 | extraction | 59/120 | 15 min | $5.88 | clear | pass | right-clear | merged |
| 53 | [c2cc](S-20260918T173627Z-c2cc.md) | 2026-09-18 | extraction | 68/80 | 13 min | $6.61 | clear | pass | right-clear | merged |
| 54 | [e78d](S-20260918T230941Z-e78d.md) | 2026-09-18 | extraction | 77/80 | 10 min | $6.60 | clear | pass | right-clear | merged |
| 55 | [5393](S-20260919T151056Z-5393.md) | 2026-09-19 | extraction | 89/100 | 14 min | $7.70 | clear | pass | right-clear | merged |
| 56 | [286a](S-20260919T154713Z-286a.md) | 2026-09-19 | extraction | 61/100 | 8 min | $4.55 | clear | pass | right-clear | merged |
| 57 | [6f84](S-20260919T175646Z-6f84.md) | 2026-09-19 | extraction | 68/80 | 12 min | $5.70 | clear | pass | right-clear | merged |
| 58 | [a25f](S-20260919T191744Z-a25f.md) | 2026-09-19 | oracle lane | 56/80 | 7 min | $3.15 | clear | pass | right-clear | merged |
| 59 | [9e00](S-20260919T193208Z-9e00.md) | 2026-09-19 | oracle lane | 35/80 | 3 min | $1.71 | clear | pass | right-clear | merged |
| 60 | [5587](S-20260919T202902Z-5587.md) | 2026-09-19 | oracle lane | 37/80 | 4 min | $1.82 | clear | pass | right-clear | merged |
| 61 | [9133](S-20260919T210207Z-9133.md) | 2026-09-19 | extraction | 61/80 | 5 min | $2.64 | clear | pass | right-clear | merged |
| 62 | [b444](S-20260920T012251Z-b444.md) | 2026-09-20 | extraction | 128/140 | 16 min | $13.44 | blocked | pass | right-block | merged |
| 63 | [061a](S-20260920T145034Z-061a.md) | 2026-09-20 | extraction | 71/140 | 11 min | $5.87 | clear | pass | right-clear | merged |
| 64 | [d2de](S-20260920T155830Z-d2de.md) | 2026-09-20 | extraction | 19/80 | 2 min | $0.95 | clear | pass | right-clear | merged |
| 65 | [12ad](S-20260920T180832Z-12ad.md) | 2026-09-20 | extraction | 53/140 | 8 min | $3.53 | clear | pass | right-clear | merged |
| 66 | [1527](S-20260920T191040Z-1527.md) | 2026-09-20 | extraction | 81/140 | 12 min | $6.73 | clear | pass | right-clear | merged |
| 67 | [0bf3](S-20260920T193750Z-0bf3.md) | 2026-09-20 | extraction | 39/140 | 5 min | $2.91 | clear | pass | right-clear | merged |
| 68 | [f751](S-20260920T201508Z-f751.md) | 2026-09-20 | extraction | 45/80 | 6 min | $2.49 | clear | pass | right-clear | merged |
| 69 | [db45](S-20260920T214123Z-db45.md) | 2026-09-20 | extraction | 87/140 | 12 min | $8.23 | clear | pass | right-clear | merged |
| 70 | [de0e](S-20260920T220635Z-de0e.md) | 2026-09-20 | oracle lane | 51/80 | 5 min | $2.76 | clear | pass | right-clear | merged |
| 71 | [b4d4](S-20260921T131857Z-b4d4.md) | 2026-09-21 | extraction | 131/140 | 32 min | $15.98 | clear | pass | right-clear | merged |
| 72 | [67cc](S-20260922T002232Z-67cc.md) | 2026-09-22 | extraction | 107/140 | 23 min | $13.04 | clear | pass | right-clear | merged |
| 73 | [54cf](S-20260922T155044Z-54cf.md) | 2026-09-22 | extraction | 86/140 | 16 min | $7.62 | clear | fail | right-clear | merged |
| 74 | [4732](S-20260924T212441Z-4732.md) | 2026-09-24 | extraction | 54/100 | 5 min | $3.13 | clear | pass | right-clear | merged |
| 75 | [2fd4](S-20260924T222939Z-2fd4.md) | 2026-09-24 | — | 45/80 | 11 min | $4.78 | clear | pass | right-clear | merged |
| 76 | [9326](S-20260924T233341Z-9326.md) | 2026-09-24 | — | 87/140 | 22 min | $9.72 | blocked | pass | false-block | merged |
| 77 | [f50c](S-20260925T000959Z-f50c.md) | 2026-09-25 | — | 88/100 | 18 min | $8.40 | clear | pass | right-clear | merged |
| 78 | [189e](S-20260925T004310Z-189e.md) | 2026-09-25 | — | 85/140 | 19 min | $8.58 | clear | pass | right-clear | merged |
| 79 | [c141](S-20260925T011655Z-c141.md) | 2026-09-25 | — | 141/140 | 39 min | $20.90 | blocked | pass | false-block | merged |
| 80 | [8e50](S-20260925T154507Z-8e50.md) | 2026-09-25 | — | 70/140 | 24 min | $8.49 | clear | pass | right-clear | merged |
| 81 | [66c5](S-20260925T161239Z-66c5.md) | 2026-09-25 | — | 71/140 | 19 min | $8.94 | blocked | pass | false-block | merged |
| 82 | [06e3](S-20260925T205128Z-06e3.md) | 2026-09-25 | — | 91/120 | 13 min | $8.95 | clear | pass | right-clear | merged |

82 of 40 sessions · areas: extraction, knowledge tools, oracle lane, harness and sandbox (4; at least 3) · false blocks 4 · missed 0
refusals: egress 103, policy escalations 244, denies 1 (each read in its session's notes, §4)
reported cost $412.27 over 81 of 82 sessions (the envelope's figure, on the subscription) · turns 5149 · wall 922 min
This block is rendered by `pipeline/scripts/calvin_tracker.py render` from the logs and is not edited by hand.

<!-- tracker:end -->
