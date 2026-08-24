# ADR-058 — The benchmark's environment bound to both arms, and the unit cap

**Date:** 2026-08-21
**Status:** accepted — built, run live on one instance's pure arm;
the first full complex-set run relaunched under it
**Amends:** `docs/hobbes-architecture.md` (§6.2); `docs/constraints.md`
(C-43, C-44); `docs/bench-run-handoff.md` *(since deleted; history in
the BUILDLOG)*; ADR-057's "consequences"

## Context

The first full run of the complex set (ADR-057's handoff) was stopped
after its first instance. Twenty minutes in, `astropy__astropy-13398`
had surfaced two structural problems, both independent of the model
under test and both in the harness's own hands:

1. **The plan exploded to 210 units.** `hobbes plan` over astropy with
   the issue as proposal produced 210 agent units (an 80k-line
   change-spec); `hobbes run` spawns one sandbox session per unit, and
   the measured session was ~7.5 minutes — about 26 hours for one
   instance's harness arm, on a 45-instance set. ADR-051's per-hop
   decay had cut the dogfood repo's 33-unit case; at astropy's scale
   with lexical seeds (C-36) it does not hold. C-35 — partition
   quality unvalidated — firing on the first large repo.
2. **Neither arm could run the target's tests.** The session image is
   a bare Alpine with python3 and git; the pure arm ran on the host.
   Every unit's flight log was the same loop: `pytest` → exit 127,
   `pip install pytest` → 127, `git commit` → exit 128 (no identity
   in the clone), then `apt-get` / `curl get-pip.py` /
   `git config --global`, each escalating and expire-denying at 5s.
   The solo policy (ADR-057) was working exactly as designed — the
   `pytest*` and `git add*` rules answered `allow` — but there was
   nothing to run. An agent that cannot run a test cannot verify a
   fix, so the arm's outcome was empty by construction.

The owner's direction: cap benchmark plans at **20 units** ("we can
adjust after with n max sizing"), and **install the environment** —
acknowledged as a benchmark practice, not an architecture change.

## Decision

1. **The benchmark's environment is the benchmark's own image, bound
   to both arms** (`pipeline/src/hobbes/bench/environment.py`). Each
   SWE-bench instance publishes an image with the repo installed at
   the base commit and its per-version environment — the same image
   the evaluator judges in (C-40). Both arms now run *in* it:
   `hobbes-session --image` for the harness arm, a bare `podman run`
   over the mounted workspace for the pure arm (which was on the
   host; this also discharges ADR-055's "pure-arm containment" item).
   The workspace at `/work` is bound to the environment by two
   mechanisms, both visible in the dry run and recorded per arm
   (image + digest):
   - `PYTHONPATH=/work` — the image's editable install points at
     `/testbed`; a path entry precedes the editable finder on
     `sys.meta_path`, so the worktree shadows the installed copy;
   - a **pre-command** that copies `/testbed`'s untracked files (the
     in-place build artifacts: `.so` extensions, generated version
     modules) into `/work`, so a compiled repo imports without a
     rebuild. Verified on astropy: the same test file gives the same
     result from `/work` as from `/testbed`.
   `hobbes-session` gained the flags this needs — `--path`, `--env
   K=V` (repeatable), `--pre CMD`, `--runtime-python P` — and the
   session command is unchanged in shape: the pre-command wraps it
   with `sh -c 'PRE && exec "$@"'`. The owned loop runs on the
   image's base python (`/opt/miniconda3/bin/python3`, 3.11) because
   the conda env carries the *target's* python, which is 3.6 on old
   django. `hobbes bench run --environment swebench` is the default;
   `none` is the old behaviour, kept so the harness can run without
   podman images (the tests use it).
2. **A commit identity for every session clone.** `hobbes-session`
   copies the canonical repo's `user.name`/`user.email` into the
   clone (falling back to `hobbes-session` / `session@hobbes.local`).
   A sandbox has no global git config, so every in-session commit
   had been exit 128. Not benchmark-specific: any session that
   commits needed this.
3. **The unit cap** (`partition.build_units(max_units=…)`). After the
   budgeted partition, while the count exceeds the cap: merge the
   strongest-coupled pair *past the budget*; when nothing couples,
   merge the two lightest units. Deterministic by the partition's own
   tie rule. Every unit the cap touched is flagged `capped` — the
   merge was for session count, not coupling — and the spec records
   `max_units`. `hobbes bench run --max-units` defaults to **20**
   (`0` = no cap); `hobbes plan --max-units` exists with no default,
   because a human-reviewed plan has a human to size it.

## The second finding (same day): the brief as argv

The relaunch ran five instances in twenty minutes — the cap held (20
units each, 1–2 `capped`), `pytest` exited 0 in the sessions, commits
went through — and **every harness arm failed with `Argument list too
long`** spawning `hobbes-session`: one astropy unit's brief was
488 KB, a `capped` unit carrying the standing context of everything
it absorbed, past the kernel's 128 KB single-argument limit. Two
fixes, both in this ADR's scope:

4. **The brief travels as a file.** `hobbes-session --task-file`
   (exclusive with `--task`); the orchestrator passes the `brief.md`
   it already writes. `spawn.txt` now shows the real argv.
5. **A brief limit** (`hobbes bench run --brief-limit`, default
   60,000 characters ≈ 15k tokens for the ladder's 32k window;
   `hobbes run --brief-limit` with no default). `agents.limit_context`
   trims the unprotected sections to an equal share with a stated cut
   line each; the complement, the policy, the contracts and the
   invariants are never cut (ADR-047's contract outranks the limit).
   The record carries `brief_chars`/`brief_cut` per unit — **C-45**.
   A 488 KB brief would otherwise have reached the endpoint as a
   context-length error, counted as a unit failure for a reason that
   is the harness's, not the model's.

## The third finding: the window, and the uncommitted work

The next relaunch reached the harness arms and ran them — 20 units,
the cap holding, `pytest` **exit 4/5** (real test outcomes, not 127),
briefs fitting — but instance 1 still produced an **empty patch**, for
two reasons this ADR also fixes:

6. **The window was a hard wall.** `astropy-13398` U1 read a large
   frame file, and its *next* completion was a 400: `maximum context
   length is 32768 tokens and your request has 28852 input tokens`.
   The loop treated a length 400 as fatal. Now `Endpoint.chat` fits
   the window — shrink `max_tokens` to what is left, and when that is
   too little **elide the oldest tool results in place** (stated) —
   and every tool result is clipped head-first to
   `--max-result-chars` (12,000). The envelope reports
   `context_fitted`/`context_elided`. **C-46.**
7. **Committed work was the only work harvested, and the 7B rarely
   committed.** Most units ended by editing a file and then `reflect`-ing
   a prose summary (U2, U4, U5) or looping on `reflect` (U3 ×42) — the
   edits were on disk but never `git commit`-ed, and the harvest takes
   only commits, so the branch diff was empty. `hobbes-session
   --commit-on-exit` (set by the solo path) commits whatever the
   session left uncommitted at exit — `.hobbes/` excluded (P1), the
   commit named as the wrapper's — so an agent that edits but forgets
   to commit still yields its patch. The orchestrator records
   `exit_commit_files` per unit, so how often this rescued a unit is
   measurable.

These are the harness meeting a small model's habits, not the model's
competence; the pure arm on the same instances did commit-free edits
too (its patch is the worktree diff, so it needed no commit — the
asymmetry the harness had to close).

## The fifth finding: a prose plan is not a patch

With the window fixed, a debug loop on one light instance
(`pytest-5787`, full harness, isolated) ran clean — 5 units, sessions
in the env, `pytest` executing — and still empty-patch, for a reason
that is the model's habit, not a harness bug: the 7B wrote a **prose
plan on turn 1 and stopped** ("Here is how I would fix it: …"), never
calling an edit tool. `commit-on-exit` correctly committed nothing,
because nothing was edited.

8. **A bounded nudge toward acting.** When the loop's model returns no
   tool calls and has edited nothing, one corrective user turn is sent
   — *a description is not a fix; call write_file/edit_file now* —
   capped at `--max-nudges` (default 2) so a model that genuinely will
   not act still terminates. The envelope reports `nudges` and
   `edited`. This is the boundary of what the harness may do: it makes
   the model *act*, it does not tell it *what* to write — that would
   coach the H1 measurement. With the nudge the same instance produced
   a real patch (2 of 5 units edited, 2 commits; the other 3 declined
   their unit after two nudges, which is allowed).

The line this holds: mechanical failures (no test env, argv limit,
window wall, commit-only harvest) are the harness's to fix; whether a
capable-enough model then solves the task is H1's to measure. The
nudge sits exactly on that line — it removes "the agent never tried to
edit" as a harness artifact without supplying the fix.

## The sixth finding: an implementer with a map still needs discipline

Watching the capped run, `astropy-13579` unit U10 — an **implementer**
whose assigned interior was `astropy/io/misc/asdf/conftest.py`, a file
unrelated to the WCS-slicing proposal — called `tests_guarding` on one
symbol **55 times** and `reflect` 54 times, editing nothing, burning
its whole turn budget (~14 min). Two things behind it:

- **A spurious unit.** The lexical seeds (C-36) produced a unit whose
  interior does not intersect the change; it had no real work, so it
  thrashed. This is the *unit-selection* case (spawn a stream of
  *selected* units, not all of them) — the bigger fix, parked in
  `future_additions.md`, named by the owner watching this run.
- **No loop discipline against repetition.** The brief carries a *map*
  (module names, one-hop signatures — "internals deliberately absent"),
  never source, so an implementer still reads; but nothing stopped it
  repeating one read-only call 55 times.

9. **The nudge becomes pipeline discipline** (the owner's direction:
   "integrate the nudge as part of the pipeline… make it stricter").
   The loop every implementer runs now: **refuses an identical
   read-only tool call** (same name+args) rather than re-running it,
   telling the model to do something new (`repeats_refused` in the
   envelope); counts a turn that changed nothing as **dry**, nudges
   toward editing at `--nudge-after` (3) dry turns while nudges remain,
   and **stops a stalled session with a reason** at `--stall-after` (6)
   dry turns instead of burning the budget. On U10's real pattern this
   stops at turn 9, not 55 calls. It disciplines *how* the model works,
   never *what* it writes — H1 stays the model's.

## What this is not

- Not a change to the sandbox boundary. The mounts, the network
  (C-41), the policy chain and the proxy are unchanged; the image is
  the benchmark's and the two bindings are host-authored, listed in
  the argv, never the agent's to set.
- Not a claim that 20 is right. It is the owner's first sizing, to
  be adjusted from the run's verdicts ("n max sizing"); the flag on
  every capped unit is what makes the adjustment measurable — a run
  can count how often the cap, not the coupling, decided a unit.
- Not a fix for C-35/C-36. The 210 units were the impact set's size
  under lexical seeds on a large repo; the cap bounds the cost of
  that, it does not improve the partition. The parked seed
  adjustments in `future_additions.md` remain the response to the
  miss rate, decided from verdicts.

## Consequences

- **C-43** registered, surfaced: the environment binding's edge — a
  change that needs a rebuild of a compiled extension is not seen by
  the tests, because the build artifacts are copied, not rebuilt.
  Four of the 45 complex instances are compiled repos (astropy ×3,
  scikit-learn ×1); 41 are pure python.
- **C-44** registered, surfaced: a capped unit's modules were merged
  for count, not coupling; the flag, the spec's `max_units`, the
  record's `capped` count and the run banner all say so.
- The run manifest records `environment`, `network`, `max_units`;
  each record's `detail.environment` carries the image and digest.
- Tests: Go +5 (env binding; no wrapper without `--pre`; clone
  identity; `--task-file`; commit-on-exit excludes `.hobbes/`),
  pytest +27 (cap ×6, environment ×8, brief limit ×3, window ×4,
  exit-commit, prose-plan nudge ×3, strict pipeline ×3). 797 pytest /
  Go green.
- **Confirmed on one instance** (`pytest-5787`, harness arm): outcome
  `patch`, a real branch diff — the harness produces a candidate end
  to end. Correctness is the evaluator's verdict, not this ADR's.
- The 20-minute poll that found this is the handoff's "watch it"
  step; it worked. The handoff doc now says what to look for first.
