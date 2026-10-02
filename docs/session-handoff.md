# Session handoff — the single resume point

**Reviewed 2026-10-02 (thirty-second session); Hobbes 0.2.83-beta on `main`.**
Max pushed through `3d1dda7` (Calvin closed, 2026-09-29); `main` is ahead of
`origin/main` by the commits since, unpushed. The image and the proxy are at
0.2.83-beta, and this repo was ingested at the release commit; ingest at HEAD
again if `main` has moved since. A new session's knowledge server is a new
container from the current image (`sandbox/knowledge-serve` runs `podman run
--rm`), so it is fresh.
- **Tags:** `v0.2.10-beta` is the latest tag (Max, 2026-09-13). The one
  before it is `v0.1.8-beta`. 0.1.9-beta to 0.2.9-beta and 0.2.11-beta to
  0.2.83-beta are untagged. Tags stay Max's call each time.
- **Numbering** (Max; ADR-103's fourth amendment): patch by patch on 0.2.x,
  counting past nine. A language addition or a constraint's fix is a patch,
  even when structural; a minor is for a feature added to Hobbes (the
  harness earned 0.2.0; the dev environment would earn 0.3.0 and is not
  being worked on). Ask before a minor.
- **Where work happens:** on `main`; publishing belongs to Max.

This file keeps only what the next session needs. What shipped is the
CHANGELOG's; how each session went is the BUILDLOG's. Two companions hold
what used to sit here: **[`bench-drivers.md`](bench-drivers.md)**, where
each measurement's scripts are, and **[`lessons.md`](lessons.md)**, the
checks earlier sessions paid for. Read the lessons before writing a brief
or a probe.

## ⇢ START HERE NEXT SESSION

**Max's direction (2026-09-20): extraction first — "the most annoying work to
do but the most important for hobbes"; "we never sacrifice honesty for higher
recall".** And (2026-10-01) against fitting: "if we try to 100% 100% everything
we might be defeating the point of the [poison] check by conforming to our
tested repos."

**Next — the local alias of a global** (`_Segment = Segment` … `_Segment(…)`;
rich 121, click 24, flask 12; C-9). Measure first, and grade a candidate rule
on the held-out rich cell as well as click and flask. Then `cls(…)` in a
classmethod (rich 57), C-174's remainder per language, and C/C++ lane A's
time. **Pick the next held-out repo before the next round of fitting.**

**Where the last day left things** (2026-10-01; the CHANGELOG has each):
the honesty audit (0.2.80-beta, precedent 1) widened C-174 and registered
C-175 to C-177, and all three are fixed — C-175 lifted (ADR-157, 0.2.81), C-176
narrowed to the symbol floor (ADR-158, 0.2.82), C-177 lifted (ADR-159, 0.2.83).
**Not audited:** Terraform/HCL; repo-scale counts of any implicit shape outside
Python's `__exit__`; Go's and Java's caller roll-up on real repos. The held-out
rich cell (0.2.77-beta) reads 4,748 confirmed, 0 Hobbes-wrong, recall 89.7%,
and is now in the loop.

## Open for Max (no spend)

Each is his call; nothing is built until he answers.

- **ADR-158's amendment:** nested functions file under their top-level
  symbol. It was not in the route he named; it was pre-registered and is in
  the ADR for review. C-176 keeps the floor (an object literal's method, an
  unnamed class, a property-assigned function, a namespace); lifting it moves
  the symbol set. The CJS literal member (cue 49, Express 46) is the same
  question.
- **The TS symbol floor's class-property functions** (zod 1,029 collapsed
  pairs): off the table since 2026-09-10 "with the constructor grain settled
  before `new`", which ADR-142 since settled. **Re-ask; do not start.**
- **ADR-156 and fixture values:** the `with` rule does not build on
  ADR-145's `syntactic` fixture-value edges (40 of flask's items, `with
  app.app_context():`); allowing it would stack one `syntactic` rule on
  another.
- **ADR-126 §3:** whether to build the "may reach through dispatch (not
  traced)" section in `tests_guarding` and `hobbes review` on §10.12's
  numbers. It needs a syntax exclusion for every non-dispatched call (Java
  `super.`/private/static/final, Python `super()`, C++ class-qualified) and
  would say no key confirms reach.
- **flask's `src/flask/sansio/`** has no `__init__.py` (PEP 420): lane A names
  its modules `app`, `scaffold`, and the `implements` join places `App →
  Scaffold` but not `Flask → App` (`graph["implements"]["outside"]` 79). Why is
  not read; whether it is a constraint to register is his.
- **Verify's `classify`** returns `error` for a row that errors on *both*
  trees, and `FAILING` holds `error`, so a fixture repo's own uncollectable
  test (`minifixval/tests/test_runner.py`) failed a verdict with 0
  regressions (session `54cf`). A route, not changed.
- **`npm ci` refused three of four lockfile-bearing JS repos** the draws met
  (counted under C-23 in C-165): whether "pinned or declined" falls back to
  anything. Nothing proposed.
- **The ingest's `.gitignore` edit:** register it as a constraint or change
  it.
- **Calvin's open findings, proposed and not registered:** G-diff coverage
  (the driver never puts inf/NaN in `b` alone, nor mixes inf kinds, so
  one-sided masks pass; the fix is `inf_b`/`nan_b`/mixed specials, then a
  zero-spend re-grade of the stored rows); G-hsr's macro-arity misfile; the
  ISA-split golds.
- **Parked by him:** C-150's remainder ("fine for now"); §3.8's paragraphs
  stay in the architecture ("dont split for now"); constructions inside a
  template stay `uses`; repowise's cells stay on 0.49.0 (0.53.0 is out).

## Extraction candidates (each measured first)

- **C and C++ lane A time** grows about 8× per doubling of chain depth (6 s
  and 12 s at 800 calls): a measured-fix candidate, no graph change.
- **An aliased function-local import that draws nothing** (`from .testing
  import FlaskClient as cls; cls(…)`: flask 2). click's `termui.py:980` draws
  since ADR-154; read why flask's do not. A single-repo row.
- **scip-python names no occurrence for flask's `urlsplit`**, at the import
  or the call (`app.py:15`, `:725`). Not read. A single-repo row.
- **Other languages' duplicate qualnames** (ADR-155 is Python only). TS/JS
  was read and the shape is absent; Go, Java and Rust are not measured.
- **An `extends`-chain walk (TS/JS):** 104 rows at 0 contradicted (ajv 18,
  hono 8, xmpp.js 2, zod about 76), 0 on Preact. A chain of lane B hops would
  be a new kind of rule, for under a point a cell. Measured, undecided.
- **What click still misses** (806 on r3 before ADR-153): 460 closures
  (callbacks through attributes and parameters, C-58), 215 methods (79 a
  subclass override — ADR-126 §3's question; 90 duck-typed receivers and
  test doubles), 81 lambdas, 37 classes, 13 functions. No decorator-line
  shape with more than 10 rows is left; none has a syntactic rule ready.
- **Preact's test-file misses** (closures in `it` bodies, calls through
  `.d.ts` interface members, hook setters in locals): C-58's shapes.
- **Older, none started:** C-142's remainder (the 273 headers nothing
  includes; ADR-138's route b, a content read); C's residue (W1: C-134's
  remainder, C-135's autotools, Meson and Bazel roots, C-133's unit 2 and its
  macro half); C-139's finer extent and C-133's unit 2, each only if a graded
  cell shows the cost; C-140's remainder (ADR-112's route 2). Optional and
  no-spend: a `lane_b` end-to-end case for ADR-135.
- **C++ recall's remainder** (Max's Route A, ADR-132 to ADR-136 built):
  constructions' remainder is C-162; a lost definition's refused extents are
  C-145; C-164's remainder is its own entry; operators at a macro's name are
  C-131's (parked). dagger's docs snippet zones were not re-ingested after the
  `corepack` fix.

## Held, with all spend

- **Calvin** is closed on sqlite-vector (2026-09-29; `calvin-reassessment.md`
  §11–§13): the lattice's residual is deterministic. It reopens only on a
  target where the job is not derivable; choosing one is a design question
  for Max. Before any later model run, read the registers (`CV-1…21`,
  `MA-1…18`) and the Calvin README's "Instrument lessons".
- **Atlas-0** (held from 2026-09-07; `atlas-0.md` § Addendum, $22.28 of $25).
  Max reads the B4 record, then decides: the T that carries the abstention act
  (the memorising T, or §A.7 branch 2's computed `NO_EDGE` target, about
  $3.5–4 plus B1's cells); the grid's second run (about $3.8, the programme
  to about $26 against $25); T_v2 for the v2 grid (the plateau at 3,100 is
  seed-variable); the corrected item-1 section and §6.6 as amended, and the
  ADR number on *accepted*. The drivers build paths by string
  (`Path.with_suffix` eats a dotted name's tail); the grid's B4 cells run four
  at a time, about 14 min each.
- **TTT:** the 10,000-step point (about 6 A100-hours) and the 3,000-step
  adapter under the primary cell (about 0.7 A100-hour; deploy with
  `TTT_APP=hobbes-ttt-cell … deploy`, then `ttt_cell.py run … --arm
  A2=<name> --arm A3=<name>`); the cell's defect register (D-1–D-5): which
  first; ADR-092's four embedded decisions. Records: `olmo3-ttt-results.md`
  §9–§10.
- Also held: the removal A/B re-run on the 7B; a second unseen repo through
  the cell; DeepSWE's decomposed protocol; `hobbes narrate` on this repo.

## Running a session (`shanks-harness.md` §5)

- Keep the token in the key file, and ingest at HEAD.
- The doer's model is the checkout's: `HOBBES_DISPATCH_MODEL` in
  `.claude/settings.local.json` (this box: `claude-opus-5-5`, Max
  2026-09-30); `--model` beats it.
- Decide the design in an ADR or an amendment **before** the dispatch.
- Name one small unit: `hobbes dispatch --task-file … --partition …
  --secrets "$HOBBES_SECRETS"`, with `--dry-run` first. Check that the argv
  carries `--settings` (the hook) and the model.
- **Launch a dispatch detached** (`setsid nohup sh -c '… hobbes dispatch …;
  echo "exit $?"' > log 2>&1 < /dev/null &`), never as the assistant's
  background Bash, which is capped at ten minutes. A short background waiter
  over the log (`until grep -q '^exit '`) is fine.
- Review the session file and the diff. Merge with `git merge --no-ff`, never
  squash. **After filling the review block, re-render the tracker**
  (`pipeline/scripts/shanks_tracker.py render`).
- **Run every live and `lane_b` test on the host before merging**: they skip
  in the sandbox.
- **Testing a branch on the host:** `git worktree add` it, copy
  `scip/node_modules` and `tsextract/node_modules` as real trees, `uv sync` in
  its `pipeline/`. Node 22 prints `ℹ pass N`, not `# pass N`.
- Do not rebuild `go/bin` while a dispatch runs; do not re-ingest while one
  is gating.
- Clean up a killed session with `podman rm -f -t 0 hobbes-side-<id>` and
  `podman network rm -f hobbes-int-<id>`.

## A regrade against stored keys

- For one cell: re-ingest, `oracle export`, then `oracle grade --poison`
  against the cell's saved `oracle.json`.
- For many: `~/.hobbes/bench/adr111-drivers/regrade3.sh` over a `cells.tsv`
  (ROOT=<worktree>); run a pre pass only when ingest code changed; never two
  passes over one clone at once. The TS/JS one is
  `~/.hobbes/bench/c177-tagged-template/run.sh` over its `cells.tsv`.
- A regrade after a fix carries signed direction-of-fix lines in its record.
- **Pre-register before grading a new cell.** Check `oracle-grading.md` §10
  for the language's section first.

## WHERE THINGS STAND (2026-10-02)

- **Languages:** Python, TypeScript, Go, Rust, Java, C and C++ supported,
  each as far as its §3.8 row (P11); Terraform/HCL structure. JavaScript is
  drawn through TypeScript's lanes and graded on five repos of its own
  (ADR-140, `oracle-grading.md` §10.22–§10.28), two with their dependencies
  installed (C-165).
- **Shanks, the harness** (ADR-107, ADR-112, ADR-152): each session's state is
  under `~/.hobbes/sessions/<id>/`, written by its sidecar `hobbes-side-<id>`;
  the doer mounts only `in/`, read-only, and its HOME is a tmpfs. Ninety-six
  log files under `docs/shanks/sessions/`; the tracker reads 96 of 40 (4
  areas, 4 false blocks, all closed, 0 missed; 1 deny).
- **The comparative graphics** (`docs/comparative/graphics/`): four, from 96
  cells (22 same-key rows); `render.py check` green.
- **Atlas-0** (`bench/atlas0/`, 84 tests) and **TTT** (Modal apps deployed
  and idle): held.
- **Register:** 177 entries: 129 active (100 surfaced, 25 partial, 3
  unsurfaced — C-19, C-20, C-112 — 1 n/a), 31 lifted, 11 superseded, 6
  folded. Its dated notes are `docs/constraints/HISTORY.md`.
- **Oracle defect log: nothing open** (H-37 the latest, fixed 0.2.79-beta;
  `docs/oracle/oracle-defects.md`). RC-4 still carries its price: silencing is
  indiscriminate, and it hides 6 of C-153's rows.
- **Suites** (2026-10-01; pytest, Go, tsextract and vitest re-run on the host
  at 0.2.83-beta, the rest at 0.2.74-beta): 2,605 pytest (`lane_b` 21 of
  them, run with the image rebuilt at 0.2.83-beta), Go `./...` 402 with
  subtests (402 pass), 97 scip node, 49 tsextract, 52 vitest, 84 atlas0, 656
  lattice (624 pass / 32 skip without clang); oracle-lane Go 131 with
  subtests, 119 pass / 12 skip on this host, which has no clang++ or cmake
  (the C++ fixture tests run and pass in the image).
- **Disk:** `~/.hobbes` is about 50 GB plus the C++ cells
  (`cpp-cells/scummvm-cost` is the large one; sweep it if space is needed).

## NEXT (in order; no API spend)

1. **Extraction, as under START HERE**, one unit per brief through the
   harness once named; ADR-126's surface once Max decides it; C's residue
   (W1); W1/W3's no-spend items (the decorated-declaration line convention,
   the C-15 namespacing ADR, `fetch-java` on the egress proxy); the
   comparative queue's next tools if named (the two SQLite tools in
   `field.md`, converters first; syft's keys on a bigger box).
2. **W0's remainder:** the registry-pulled image and the drift audit, when
   named.
3. **Carried, small:** `stringer` is not in the image; the Gradle attach
   route's residuals (C-67); `recall-collapsed` and H-23; ADR-105/P13; the
   C-98 residuals; `build-logic/` is recorded, not built (ADR-097); the
   tracker's area for a test-only session (row 17, `—`).

## STANDING POLICY (Max) — read before doing anything

0. **API spend and Modal compute are off the table** (Max, 2026-09-04)
   unless Max names a run and its ceiling. No remainder carries to another
   run. **A `hobbes dispatch`** spends the owner's Claude Code subscription,
   not API dollars.
1. **Experiments are PARKED** except what Max clears by name.
2. **The 7B is the instrument, by speed not capability.** GPU-hours stated
   first; ≥15 min of evaluation before any run over 30 min.
3. **P12 (ADR-082):** every TTT arm is *model + prompt* and is labelled so.
4. **The 27B is untouched** until the mapping fixes are validated on the 7B,
   and only on a decontaminated set.

## PRACTICAL NOTES

- **Two sessions may share this checkout.** Before assuming `main`'s state or
  a file's content, read `git reflog` and the file itself.
- **A session sees only its own `in/`** (0.2.14-beta, ADR-112); an explicit
  `--network` is the old file world (C-140 in full).
- **The sidecar and the route:** every session gets `hobbes-int-<id>` and
  `hobbes-side-<id>`; `hobbes-egress` is a shared bridge. Name every probe
  container before removing by name.
- **A no-spend route check:** `CLAUDE_CODE_OAUTH_TOKEN=invalid
  go/bin/hobbes-session start --repo <a tiny repo> --role implementer
  --egress api.anthropic.com --task "Reply ok." --max-turns 1`: expect a 401,
  tunnels to `api.anthropic.com:443`, no refusals.
- **After an image rebuild, restart the knowledge server** (C-65) — inside
  the session that rebuilt it, as its last step. Do not hand it on.
- **The comparative graphics** are rendered by `bench/oracle/report/render.py`
  (`cells`, `render`, `check`); a caption that names cells reads them from
  `cells.json`.
- **A model run:** state the total dollar ceiling, run a few units first,
  compare the cost to the estimate before widening.
- **Worktrees for sub-agents:** `git worktree add` from `main`; a worktree
  lacks the gitignored build outputs.
- **`pgrep -f` / `pkill -f` match your own waiting shell too.** Wait on a log
  line and kill by PID.
- **Always `uv run --project pipeline hobbes … --repo <target>` from this
  checkout** (ADR-094).
- **The oracle lane:** build `oracle` from the tree before a regrade; `go test
  -count=1 ./report/` after a record changes; send a regrade's report to a
  file; `run-cell.sh --lang cpp` runs O10.
- **Olmo 3 on vLLM has no tool-call parser:** send no `tools`.
- **The key file is off the tree.** Never write its path into repo prose. It
  holds `anthropic_key` and `claude_oauth_token` (the harness's default
  `--key-name`).

## Housekeeping

- Commit to `main`; never `git push` (Max publishes).
- One ADR per design decision; one BUILDLOG entry per session.
- Every concession gets a `C-n` in its segment file under
  `docs/constraints/`.
- Rewrite this doc; do not append to it. A driver path goes in
  `bench-drivers.md`, a lesson in `lessons.md`, history in the BUILDLOG.
