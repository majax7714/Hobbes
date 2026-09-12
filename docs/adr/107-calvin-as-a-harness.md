# ADR-107 — Calvin as a harness: the doer dispatched into `hobbes-session` behind an egress allowlist, gated at its end, validated by use

**Date:** 2026-09-12 · **Status:** accepted — Max's direction and his four decisions, taken in session · **Owner:** Max · **Source:** the review of the top-level docs after Calvin M0-Gate (`docs/calvin/calvin-m0-gate.md` §10), and Max: *"o+gate is essentially a harness to stack on top of this environment, lacking hobbes session and egress allowlist. After the harness is set up, how we will verify is by using it through Hobbes development and appending to a log file per session."*

ADR-106 stays held for M0-Go's design, as the handoff has it. This
record amends the architecture's **§6** (a new §6.3), **§7** (the
session's secret and network) and **§8** (the status table), and it
supersedes the keyed rounds **as an approach**. Their records stand as
history.

## Context

Three keyed rounds ran Calvin as an experiment: M0 in Python, M0-Go in
two rounds, and M0-Gate. Each had keys, arms, preregistered readings
and a spend gate, and together they spent about $27. The approach did
not validate itself:

- **The floor was not established where it was sought.** M0-Go found
  none at A2. M0-Gate found one as a safety property, not a helper, on
  n = 10.
- **Each round found defects in its own instrument.** Round 2's audit
  found 19 of round 1's 31 passes vacuous. D-x showed that five O
  sessions read their answer from the clone's history. C-124 left the
  network open.

What held up was one shape: a frontier agent does the work, and
`hobbes gate` judges its finished diff. The gate cleared every gold
diff and blocked every seeded error with the right class. Two parts
were missing before that shape could run on real work:

- **The session.** Claude Code had never run under `hobbes-session`.
  The image carries no `claude` binary. `--claude-cred` mounted
  `~/.claude` at `/root/.claude`, but the session's `HOME` is its own
  directory, so the mount was never read. Had it been read, it would
  have handed the doer every host transcript and memory file.
- **A closed network.** A live session kept a whole network (C-41,
  C-124).

## Decision

1. **The harness is `hobbes dispatch`** (`pipeline/src/hobbes/run/dispatch.py`).
   The developer's own session keeps the intent. It hands one task to
   a doer that runs under the whole environment:
   - **the ingest at the parent**, refused otherwise, because the gate
     reads that graph;
   - **`hobbes-session`**: a fresh clone, exec only through the policy
     proxy, the flight log, commit-on-exit;
   - **the egress allowlist** (decision 2);
   - **Claude Code as the doer** (decision 3).

   The harvested diff then goes through `hobbes gate`, with the
   blind-spot map derived from the parent's graph, and optionally
   through `hobbes verify`. Nothing merges.
2. **The egress allowlist is `hobbes-session --egress HOST`** (`go/internal/egress`,
   `hobbes-proxy egress`). ADR-097 measured the shape:
   - **The session container** sits on its own podman `--internal`
     network, which has no route off the box.
   - **A proxy container**, on that network and on a custom bridge
     (`hobbes-egress`), tunnels CONNECT to the named hosts alone. It
     answers 403 to everything else, plain HTTP included, and writes one
     JSONL line per decision to the session's `egress.jsonl`.
   - **The launcher** waits for the proxy's listen record before it
     starts the session. It tears both down after, and prints the log's
     summary.
   - **Exclusive with `--network`:** the egress plan owns the session's
     network.
3. **The doer is Claude Code on the owner's subscription** (Max's
   decision). The host's binary is mounted read-only at
   `/usr/local/bin/claude`, never relabeled. Its long-lived token
   (`claude setup-token`) reaches the container as
   `CLAUDE_CODE_OAUTH_TOKEN`, passed by name. Podman copies it from its
   own environment, so the token is in no argv and no dry run. The
   rest of the doer's setup:
   - **Tools:** Bash is withheld and `--strict-mcp-config` is set, so
     the repo's own `.mcp.json` is not loaded.
   - **Pinned and quiet:** auto-update and nonessential traffic are off.
   - **Refusals up front:** a live run without a binary, a token or a
     route is refused before the container starts.
   - **The flag:** `--claude-cred` is withdrawn, with a refusal that
     says why.

   A dispatch spends subscription usage, not API dollars. The standing
   spend rule is untouched.
4. **One log file per session** (Max's decision). Every dispatch writes
   `docs/calvin/sessions/<session>.md`, and the full record sits beside
   the flight log. A log file has two parts:
   - **The harness's record:** the task, the doer and its turns, egress
     opened and refused, the policy decisions, the branch and its files,
     the gate verdict with each row, and verify.
   - **The review block, filled by the developer:** gate `right-clear |
     right-block | false-block | missed`; outcome `merged | reworked |
     discarded`; notes.

   The harness is validated by these files, read under
   `calvin-harness.md` §4's rule. There is no keyed metric and no arm.
5. **The gate derives its own map.** `gate.derive_map` moves WP-17's
   rule into the layer, and `hobbes gate --map derive` exposes it. The
   map covers the partition when one is given, else the diff's files.
   A created file is read at its directory's files at the parent
   (`map_files`), never as `unmapped`. The graph is named by its SHA,
   so the record holds no path of this machine and stays byte-identical
   on rerun.
6. **The keyed rounds' held steps are closed as superseded** (Max's
   decision). These are M0-Gate's widening, its repair-turn design and
   O+world, M0-Go's floor, and M0's wider run. The reviewer path
   (`review.py`) moves to `--egress api.anthropic.com`.

## Consequences

- **Register.** C-41 is narrowed: a session launched with `--egress`
  reaches its list alone, but the allowlisted endpoint is still a
  channel. C-124 is superseded, because its path, the keyed rounds' O
  driver, no longer runs. Four new entries:
  - C-125: the doer's native file tools are not in the flight log;
  - C-126: a created file in a new directory reads `unmapped`;
  - C-127: the validation is the developer's review, not an answer key;
  - C-128: a dispatch is not reproducible.
- **Version.** 0.1.21-beta (the layer's number line stays patch by
  patch). The image is rebuilt (C-65).
- **Not built:**
  - a partition derived by `hobbes plan` for a dispatch (the developer
    passes one, or none);
  - a repair turn (a blocked dispatch goes back to the developer);
  - the doer's file tools through the proxy (C-125);
  - `fetch-java` on the same proxy (C-66's next narrowing);
  - a multi-unit decomposed dispatch (P12).

## Tests

- **Go:** the allowlist's parse and match, and the proxy's tunnel,
  refusal and log (`go/internal/egress`). The plan's argv, env, mounts,
  setup and teardown, and the token never in an argv
  (`internal/sandbox`). `hobbes-proxy egress`'s refusals. The session
  launcher's dry run, the withdrawal and the live-run refusals.
- **The guarantee where a user meets it (P10):** a real session behind
  the real proxy on a real internal network. The allowed host answers
  200 through the tunnel, another port gets 403 on CONNECT, and a
  direct request finds no route (`TestEgressRouteLiveAllowsTheListAndNothingElse`;
  it skips without podman or the image).
- **Python:** `derive_map`, `map_files` and `gate --map derive`
  (`test_gate.py`). `hobbes dispatch` end to end against a stand-in
  session that commits and writes both logs: the brief, the argv, the
  harvest, the gate, one log per session, the refusals, the key file,
  the partition (`test_dispatch.py`).
- **Checked by hand, no spend:** Claude Code in the container with an
  invalid token reached `api.anthropic.com:443` through the proxy
  (three tunnels), got `401`, reached for no other host, and left no
  container or network behind.

## Amendment — 2026-09-12 (later): retention; recorded sessions are evaluation rows, never model training data

**Max:** *"make sure not to store reasoning context, also pin in docs that
recorded sessions are evaluation rows never model training … I only care
about the doer's output."*

- **Found first.** The first real dispatch stored Claude Code's own
  state in the session dir, which is the session's HOME:
  - its transcript under `.claude/`: 5 files, 564 KB, 21 lines carrying
    thinking blocks;
  - `.claude.json`;
  - its MCP logs under `.cache/claude-cli-nodejs/`.

  All of it was purged from the three harness sessions that had any.
  None of the closed rounds' Claude transcripts carries reasoning. Five
  owned-loop transcripts from 2026-08-22, the Qwen benchmark runs, do
  (`reasoning_content`); they are left for Max's call.
- **Decision.**
  1. **No transcript is written.** The doer runs with
     `--no-session-persistence`, so its transcript, reasoning included,
     never reaches disk.
  2. **Whatever state is left is removed.** When the container exits,
     `hobbes-session` removes the doer's state from its HOME
     (`sandbox.PurgeDoerState`: `.claude/`, `.claude.json*`,
     `.cache/claude-cli-nodejs/`) and prints what it removed.
     `hobbes dispatch` repeats the pass, scans the session dir for any
     stored reasoning block, and records both.
  3. **A session keeps the doer's output:** its diff and commits, the
     envelope's closing result, the flight and egress logs, the gate
     and verify records, and the brief.
  4. **Recorded sessions are evaluation rows, never model training
     data.** This is stated in every session file and every record. It
     is enforced where Hobbes itself could turn them into training data:
     `ttt.units.units_from_git` skips every commit the dispatch
     identity authored (`dispatch@hobbes.local`) and every path under
     `docs/calvin/sessions/`. A doer's commit is merged, never squashed,
     so the authorship the guard reads survives.
- **Register.**
  - C-125 amended: the transcript is no longer kept, so the doer's reads
    are recorded nowhere.
  - C-129 added: the guard's reach. Once merged, a doer's code is part
    of the tree, and a corpus rendered from the tree contains it.
- **Version:** 0.1.22-beta.
- **Tests:**
  - `PurgeDoerState` (Go);
  - the live session test, where state the session wrote in its HOME
    is gone after it and the launcher says so;
  - the default command carries `--no-session-persistence`;
  - dispatch's purge and retention record;
  - `units_from_git` over a real repo: a developer commit, a doer
    commit and a session file yield units from the developer's files
    alone.

