# Lessons — what earlier sessions paid for

Each line is a mistake a session made, or nearly made, and the check
that would have caught it. The run that paid for it is in the ADR or
session named, and in that date's `BUILDLOG.md` entry. Read this before
writing a brief, a probe or a pre-registration. The resume point is
[`session-handoff.md`](session-handoff.md); the driver index is
[`bench-drivers.md`](bench-drivers.md).

## Probes and pre-registration

- **A new fixture joins this repo's own graph, so run `scripts/ci-graph.sh`
  on the host before committing one.** ADR-163's fixture passed pytest
  with `lane_b` and both cells, and turned CI's `hobbes lanes` red: no cell
  regrade runs `lanes` on this repo (ADR-165).
- **Before naming a lane row "explained", read what the graph draws at
  the site.** ADR-165's first route shaped a row as "both answers are one
  node"; the probe found no edge drawn and the site tailed `below-floor`.
  Also check that a test named "still draws" covers both ends: calls
  *onto* the arm, not only calls out of it.
- **A same-header repeat is not one item.** ADR-163 excluded 161 memchr ids
  as cfg twins; 152 were different items (a std copy no crate compiles,
  and `struct B` beside `const B`). Gate a "same item" rule on the
  evidence that makes it one: here, a `#[cfg]` on every arm and one kind.
- **Read the file before classing a shape from the graph's silence.**
  ADR-159's step 0 called Preact's `html` a local without reading it; it
  was a module-level `const html = htm.bind(h)`. Lane B not indexing a
  directory is silence too, and lane A still answers there.
- **A simulation adds edges the way the build merges them.** ADR-160's probe added one row per site; the
  build leaves a pair the graph already carries alone (`already-drawn`), and 9 of rich's sites were such
  pairs. Model the pair convention, and the scope rule exactly as worded (3 nested-def sites were labelled
  same-scope).
- **A bucket regex over a site's line is for ranking, never sizing.** rich's cell bucketed 121/12/24 local
  aliases on rich/flask/click; an `ast` read found 155/0/0. Read the shape exactly before naming a
  candidate's size in a handoff.
- **A trace key grades calls only.** pyparsing's 0 contradicted sat beside 1,688 wrong `semantic` `uses`
  rows (C-178). On a new cell, also count `semantic` rows whose line does not hold the target's name.
- **scip-python counts columns in UTF-16 code units.** A character above U+FFFF is two; read a token at a
  raw column with that conversion or a line holding an emoji reads mid-word (`'gment'`, C-178's step 0).
- **A prediction about this repo includes the fixture the unit adds.** ADR-161's Q5 predicted 0 refusals
  here; the 3 were its own `minireexport`, which this repo ingests like every fixture.
- **A probe applies every condition the ADR states.** ADR-156's `sim.py`
  ignored step 2's `semantic` condition and over-predicted flask (about
  +102 against +28).
- **Model the join's claim in a probe.** A simulation that ignores the
  by-(file, line, name) claim over-predicts (ADR-132: P102 missed by 19
  rows).
- **A probe's premise can be the docs' error.** `oracle-misses.md` said
  Python nested defs are not symbols; the export said otherwise in one
  grep. Read the export's `target_id`s before sizing a "missing symbol"
  rule (ADR-146).
- **Ask what the index emits at a token before counting a shape as a
  rule's.** A ten-line fixture indexed in the image answered `super` and
  JSX in a minute (`c168-remainder/mini/`, a `dump.mjs` over
  `streamDocuments`).
- **An in-repo `external_ref` is the index speaking, not silence.** Its
  moniker says what was named; ADR-144's whole shape sat there unread.
  Run `inrepo_ext.py` on a new cell.
- **A code search's hit is not the repo's use.** `pytestmark =
  …usefixtures(` hits are mostly strings pytest's own suite writes, and
  docstrings; read the clone with `ast` (`c4-pytestmark/scan.py`).
- **Read a register entry's rows before building on it.** C-168 named the
  wrong shape and the wrong numbers; a row-by-row read of the key caught
  it. C-165 named an edge that is never drawn; checking the TS cells for
  a `node_modules` target caught it.

## Briefs and dispatched units

- **Read a brief's premises in the tree before dispatch** (ADR-134's
  brief was wrong about a site's scope), and run the real cell before
  merging. A doer may narrow a brief's wording rightly (unit `5587` kept
  H-33's row).
- **"Exactly as X does" in a brief copies X's assumptions.** ADR-145's
  callers are never modules; ADR-147's usually are. Name the caller kinds
  in the brief, and give an append step its own lane A test.
- **Put a real-source case in the brief.** ADR-148's unit tested trimmed,
  untyped signatures; click annotates every factory (`**attrs: t.Any`,
  a `typed_parameter`) and the first build folded nothing.
- **Read a doer's idiom against the grammar, not only its tests.**
  `children[-1]` passed eleven cases and lost every commented decorator.
- **A rule that drops a fallback can lose an edge the join places only at
  its own column** (ADR-143): an aliased import's site, which the two
  lanes spell differently. Ask what the join needs lane A's answer for
  before a brief drops one.
- **A write partition is a file list, at file grain.** A directory entry
  matches nothing, and every code file created under it is a `partition`
  row (unit `b444`). Spell a new fixture's files out, one path per line.
- **A fixture repo's new file can move another fixture's module id.**
  `flask-excerpt/conftest.py` made ADR-006 root-prefix `minifixval`'s
  conftest too; check the whole repo's `discover_modules` ids.
- **A deny in a session log can break the tracker** (unit `1527`: a
  multi-line command split the Policy line). If the tracker refuses a log,
  read the log's line before the parser.

- **Renaming a test: grep `.hobbes/invariants/` for it.** An invariant's
  `guarded_by` names tests by id, and only the graph job's `invariants
  compile` reads them; pytest stays green. ADR-012's amendment renamed
  I-2's guard and the host run of `scripts/ci-graph.sh` caught it.

- **Count a probe's rows at the grader's grain.** ADR-170's step 0 counted
  `cls(…)` call sites (rich 55); the grader keeps one row per line and
  target, and four lines held two calls. C5 missed by one row although the
  rule did exactly what the probe saw. Dedupe by `(path, line, target)`.

- **§3.8's rows are pinned in code.** `verification.py` holds each row of
  architecture §3.8 verbatim and `test_verification` compares them; adding a
  held-out repo to the Python row at 0.2.100-beta left `main` red because the
  full suite had run before the doc edit. Run pytest after the last edit,
  docs included.

- **A prediction from written sites must subtract the registered refusals.**
  ADR-171's P1 counted pyparsing's 310 `C(…)(…)` in source and predicted at
  least 100 rows; 196 of them are `pp.X(…)(…)`, which C-178's containment
  refuses before the join, and 55 were drawn. Before a source-count
  prediction, run it past the refusals the cell is known to trigger.

## Grading

- **Read every suspect of a new key, row by row.** A trace key never
  contradicts, so a wrong edge sits in the suspect queue: three of
  flask's 18 were Hobbes-wrong, and "suspect rate 1.6%" said nothing.
- **A provider pick contained in one language: look for its twin in the
  others.** ADR-104 contained scip-typescript's first-member pick on a
  union receiver in 2026-09; scip-python makes the same pick, and the
  first Python cell with union type aliases (icalendar, C-184) drew six
  wrong `semantic` edges no earlier key had shown.
- **Grade the nodes a rule adds, not only its edges** (ADR-129).
- **A fixture key is collected with `-v` alone.** Without it pytest
  prints no fixture whose name starts with `_`; `-v -q` cancel (missy
  read 26,474 "wrong"). flask also needs `-p no:hypothesispytest`, and
  the mounts need `--security-opt label=disable` on this box.
- **Collecting a foreign Python suite in the image:** `uv pip install
  --target deps --python-version 3.12 --only-binary :all: pytest <its
  deps>` on the host, then `podman run --network none -v
  <clone>:/work:ro -v deps:/deps:ro --env PYTHONPATH=/deps:/work/src …
  python3 -m pytest --fixtures-per-test -q tests`. pytest prints a test
  one line past its first line, a fixture at its first decorator line,
  and one row per fixture name.
- **A before arm needs copied `node_modules`, not symlinks** (ADR-157).
  Running the before arm at HEAD before editing needs no worktree, since
  the TS helper is read live at ingest.

## Facts about the tools

- scip-clang 0.4.0 emits no `enclosing_range` (checked in the image).
- **The architecture's §8 header is a version copy no test holds** —
  bump it by hand (missed at 0.2.51-beta).
