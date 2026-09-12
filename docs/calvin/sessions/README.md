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
