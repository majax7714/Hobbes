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

## Amendment — 2026-09-12 (next session): the progress hook; the doer's edits join the flight log

**Max** (closing the 2026-09-12 C-oracle session, approving the
proposal): the progress hook first, as one dispatch, so later
dispatches can be watched.

- **Found first.** The harness had no signal between "reading" and
  "stuck". `b126` wrote nothing in 53 minutes and was stopped as a
  stall, while its tunnel's close record (5.4 MB up) showed it was
  reading. `5d5f`'s doer read for about 20 minutes before its first
  edit. The developer's stopgap was a watcher on the worktree
  (`git status --porcelain`). The flight log could not help, because
  Claude Code's own Edit and Write never pass the proxy (C-125).
- **Decision.**
  1. **A PostToolUse hook reports every edit.** For a Claude Code
     session, `hobbes-session` writes a settings file into the session
     dir (`claude-settings.json`, beside `mcp.json`), and the default
     command passes it with `--settings`. Its one hook matches `Edit`,
     `Write`, `MultiEdit` and `NotebookEdit`, and runs the mounted
     static proxy as `hobbes-proxy record-edit`.
  2. **`record-edit` appends one flight line per edit:** the time, the
     session, the role, the tool's name and the path. The path is
     relative to the worktree when it lies under it. It never writes
     content: the hook's input carries the edit's text, and only the
     tool's name and the path are read from it. It always exits 0, so a
     fault in the recorder never stops the doer.
  3. **The flight line gains one field, `path`** (omitted when empty).
     ADR-015 fixed the line's fields, and ADR-016 and ADR-054 widened it
     once each; this is the third widening. An edit line has no argv, no
     rule, no decision and no exit.
  4. **The readers keep their counts.** `hobbes dispatch` counts edit
     lines apart from exec decisions, and `orchestrate.read_flight` no
     longer counts them as knowledge calls. The web Sessions card counts
     them as events, and they keep a session's card live.
  5. **The session file gains an edits line:** the count, the files, and
     the first edit's time after launch.
  6. **No kill on silence** (`b126`). While the session runs, `hobbes
     dispatch` prints one line when the first edit lands, and one note if
     none has landed by `--quiet-minutes` (default 20, 0 for off). The
     session keeps running either way, and the record keeps the note.
  7. **Checked before the decision:** Claude Code takes `--settings`, and
     hooks run under `-p` unless `--bare` is passed. The session passes
     no `--bare`.
- **Not changed:** the doer's reads are still recorded nowhere (C-125
  stays partial). The retention rule is untouched: the hook reads a
  path, and the line keeps no content.
- **Register.** C-125 is narrowed: every edit's time, tool and path is
  in the flight log.
- **Version:** 0.2.6-beta.
- **Built** through the harness, in `S-20260912T215521Z-efc8` (87 of 150
  turns). Gate clear and verify pass; merged as `7ec3fe9`, keeping the
  doer's authorship.
- **Found by use in that session:** `dispatch.reasoning_left` read the
  session's Go build cache, where compiled test packages carry the
  retention tests' own marker. It now skips `go-build` (`SCAN_SKIP`).

## Amendment — 2026-09-13: a session mounts only its own dir; `find`'s executing forms and `xargs` are questions

**Max** (reviewing the top-level docs): "the recursive delete seems
like an error more than a flag. either look to contain or prevent."

- **Found first.**
  - The box allows `find*` and `xargs*`. So `find . -delete`,
    `find . -exec rm -rf {} +` and `… | xargs rm -rf` delete
    recursively with no question, where `rm -r` escalates (0.2.7-beta).
    `-exec`, `-execdir`, `-ok` and `xargs` also run a command the
    policy never sees, because a segment is matched by its first word.
  - Tracing where a deletion can reach found a larger gap.
    `hobbes-session` mounts the whole host sessions root,
    `~/.hobbes/sessions`, read-write at `/sessions`. Every session's
    clone (`<id>/worktree`), flight log, egress log, escalation queue,
    gate and verify records and brief sit under it. So one session's
    allowed command could reach every other session's records and live
    clone: a plain `rm`, `python3 -c`, or `find /sessions -delete`. The
    box header's "only the worktree is writable" was not true.
  - The glob cannot close this. `python3 *`, `make*`, `go generate*`
    and `awk *` are allowed, and each can delete. The header already
    says an escalation is a question, not a boundary.
- **Decision.**
  1. **Contain: the boundary.** The session container mounts only its
     own session dir: host `<sessions>/<id>` at `/sessions/<id>`,
     read-write. Every in-container path stays the same: `HOME`,
     `mcp.json`, `claude-settings.json`, the flight log, the escalation
     queue, the proxy's `--log-dir /sessions`. Nothing of another
     session is mounted, so no command reaches it, however it is spelled.
     The plan is shared, so this holds for every role and for the
     benchmark's sessions. The exit check (`sandbox/exitcheck.py`) drops
     its scripted driver into the session's own dir, not the root.
  2. **Prevent: the common spellings become questions.** Both boxes
     change (`calvin.box.policy`, `bench.box.policy`):
     - `find` keeps its read-only allow. Its deleting and executing
       forms escalate: `-delete`, `-exec`, `-execdir`, `-ok` and
       `-okdir`. Escalate beats allow within a scope (ADR-002).
     - `xargs` is no longer allowed. It runs a command the policy does
       not see, so it takes the box's default, escalate.
     - The cost is small. Across the 21 sessions on record, doers ran
       `find` or `xargs` once. A dispatch's escalations expire to deny in
       5 s, so a doer reads them as refusals.
  3. **The header says what is left.** An escalation is still a
     question, and `python3 *` can still delete. What bounds a deletion
     is the mounts:
     - the session's clone, which the gate reads against the partition;
     - the session's own dir.
- **Not changed; registered as C-140.** The session's own dir stays
  writable by its doer:
  - The proxy that writes the flight log and the escalation queue runs
    in the doer's container, as the doer's user.
  - Claude Code's own Write tool reaches the dir too.

  So a doer can alter or delete its own flight log, its egress log and
  its escalation records. C-140 is surfaced in the box header and the
  harness doc. The structural fix is to give the proxy and the logs a
  container of their own, as the egress proxy has. It is named for Max,
  because a structural change is his call. **Taken: ADR-112
  (2026-09-14, 0.2.14-beta)** — the records' writers moved to a sidecar
  container; the doer's HOME is a tmpfs; C-140 narrowed.
  
- **Tests.**
  - `internal/sandbox`: the mounts name the session's own dir at
    `/sessions/<id>` and never the root.
  - **The guarantee where a user meets it (P10):** a real session lists
    `/sessions` and sees only its own dir. The test skips without
    podman or the image, like the live egress test.
  - `hobbes-policy`: against each real box, every deleting or executing
    `find` form and `xargs` escalate. That holds alone, after a `cd`,
    and as a pipe segment. `find . -name '*.go'` still runs.
- **Version:** 0.2.11-beta.


## Amendment — 2026-09-14: the doer's model is named, per checkout

- **Context.** Every one of the twenty-three sessions on record ran on
  "model the default": `hobbes dispatch --model` exists and reaches
  Claude Code's `--model` through `hobbes-session`, but nothing set
  it, and the doer's container carries no user settings (its HOME is a
  tmpfs since 0.2.14-beta), so the model was whatever Claude Code
  chose for the owner's account — unrecorded, and not the owner's
  choice. Max (2026-09-14): dispatched tasks are to run on Opus 5, and
  the checkout is to carry that so a dispatch does not have to say it
  each time. The model a dispatch spends on is the owner's call, not
  the layer's (the bench harness names its ladder per arm, ADR-055),
  so the repo names no model.
- **Decision.**
  1. **`hobbes dispatch` reads `$HOBBES_DISPATCH_MODEL` when `--model`
     is not given.** The flag beats the variable; an unset or empty
     variable leaves the choice to Claude Code, as before. The CLI's
     help names the variable. Nothing else changes: the argv already
     carries `--model`, `dispatch.json`'s doer record already stores
     it, the session log's Doer line already prints it, and the dry
     run shows the argv — so a pinned model is visible at every step a
     developer reads.
  2. **Where a checkout sets it:** the `env` block of its
     `.claude/settings.local.json`, gitignored, beside
     `HOBBES_SECRETS` — the box's setting, not the repo's. This box:
     `claude-opus-5`.
  3. The variable reaches the host process only; the session's
     environment is the launcher's allowlist as before (nothing new
     crosses into the container).
- **Tests** (`test_dispatch.py`): the variable reaches the session
  argv and the doer record; `--model` on the command line beats it;
  unset, the argv carries no `--model`.
- **Version:** 0.2.17-beta (patch: what the layer says — the log names
  the model the checkout chose).
- **Built through the harness,** the unit itself run with `--model
  claude-opus-5` said explicitly: the first session whose Doer line
  names its model.
