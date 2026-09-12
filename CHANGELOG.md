# Changelog — the Hobbes layer

One entry per version of the Hobbes layer (ADR-103): what changed in
the product, in plain words, with the ADRs and constraints it rests on.
The experiments under `bench/` and the records under `docs/` are
internal testing and do not appear here except where a finding became
a fix. The session-by-session history is `docs/BUILDLOG.md`; the
running architecture is `docs/hobbes-architecture.md`. The number line
is Max's: **the layer stays on 0.1.x, patch by patch** (0.1.10-beta,
0.1.11-beta, …; the earlier 0.11.0-beta statement is withdrawn — the
conservative line, ADR-103's third amendment, 2026-09-10); a minor
bump lands on 0.2.0-beta when a capability earns it; tags are his call
each time (0.1.9-beta and 0.1.10-beta untagged; the last tag is
`v0.1.8-beta`).

## 0.1.22-beta — 2026-09-12 (retention: evaluation rows, never training; ADR-107 amended)

**Patch: a dispatched doer's reasoning is never stored, and recorded
sessions can never become training units.**

- **The doer runs with `--no-session-persistence`.**
- **`hobbes-session` removes the doer's state from its HOME at exit**
  (`.claude/`, `.claude.json*`, `.cache/claude-cli-nodejs/`), and prints
  what it removed.
- **`hobbes dispatch` repeats the pass and records the result.** The
  record's `retention` field lists what dispatch removed and any
  reasoning block still found (expected none). Every session file says
  that recorded sessions are evaluation rows, never model training data.
- **`ttt.units.units_from_git` skips** every commit the dispatch
  identity authored and every path under `docs/calvin/sessions/`.
- **Register:** C-125 amended; C-129 added (the guard's reach: not the
  merged tree).
- **Tests:**
  - `PurgeDoerState`;
  - the live session test (the state is gone after, and the launcher
    says so);
  - the default command's flag;
  - dispatch's retention record;
  - `units_from_git` over a real repo.

## 0.1.21-beta — 2026-09-12 (the Calvin harness, ADR-107)

**Patch: a live session reaches only the hosts it names, and Claude Code
runs inside it.** `hobbes dispatch` then stacks the doer, the gate and
a per-session log on the environment. Checked with no spend.

- **`hobbes-session --egress HOST`.** The session runs on its own
  podman `--internal` network, which has no route off the box.
  - An egress proxy container sits beside it, on that network and on a
    custom `hobbes-egress` bridge. It tunnels CONNECT to the named
    hosts alone, answers 403 to everything else, and logs every
    decision to `<session>/egress.jsonl`.
  - The launcher waits for the proxy before the session starts, and
    removes both after it.
  - `--egress` is exclusive with `--network`.
  - The proxy is `hobbes-proxy egress` (`go/internal/egress`). C-41 is
    narrowed.
- **Claude Code as the session's doer.**
  - `--claude-bin` mounts the host's binary read-only, without a
    relabel.
  - The token (`CLAUDE_CODE_OAUTH_TOKEN`, from `claude setup-token`) is
    passed by name, so it is never in an argv or a dry run.
  - `--strict-mcp-config` keeps the repo's own `.mcp.json` out.
  - Auto-update and nonessential traffic are off.
  - A live run without a binary, a token or a route is refused before
    the container starts.
  - The implementer's default command carries `--max-turns`.
- **`--claude-cred` is withdrawn, with a refusal that says why.** It
  mounted `~/.claude` at `/root/.claude`, but the session's `HOME` is
  its own directory, so the mount was never read. Had it been read, it
  would have handed the doer every host transcript. The reviewer
  session (`hobbes review`'s soft verdicts) now passes
  `--egress api.anthropic.com`.
- **`hobbes gate --map derive`** (`gate.derive_map`, `map_files`). The
  blind-spot map is read from the parent's graph by calvin-m0-gate
  WP-17's rule, over the partition or else the diff's files.
  - A created file is read at its directory's files at the parent.
  - The graph is named by its SHA, so the record stays byte-identical
    and holds no path of this machine.
- **`hobbes dispatch`** (`hobbes.run.dispatch`). One task goes to Claude
  Code under the whole stack:
  - the ingest must be at the parent;
  - the brief states how the session works;
  - the harvested branch is gated, and verified unless `--no-verify`;
  - one log file per session goes to `docs/calvin/sessions/`, with a
    review block the developer fills;
  - the full record goes to `<session>/dispatch.json`;
  - exit 0 clear, 1 blocked or verify failing, 2 refused, 3 nothing
    harvested.
- **Register.** C-41 narrowed; C-124 superseded (the keyed rounds are
  closed); C-125–C-128 added. ADR-107.
- **Tests.**
  - The egress package: parse, tunnel, refuse, log.
  - The sandbox plan and the session launcher: dry run, withdrawal,
    refusals.
  - A **live** route test: a real session behind the real proxy gets
    200 from the allowed host, 403 for another port, and no route
    without the proxy.
  - The derived map, and dispatch end to end against a stand-in
    session.

## 0.1.20-beta — 2026-09-11 (Calvin M0-Gate, WP-18c)

**Patch: an arm-O session no longer holds the repo's future.** Calvin
M0-Gate WP-18c, found by WP-21 at key 1 (D-x); checked with no model.

- **The defect.** The local harness launched arm O's session from the
  owned clone, which holds the repo's full history. The session
  therefore held every commit past the key's parent, the key's own
  gold included, and the box policy allows `git log` and `git show`.
  - WP-21's key 1 ran `git log --all --grep=…`, then `git show` on its
    own key, and wrote gold's lines.
  - Four of rounds 1–2's ten Go O sessions had done the same.
- **The fix (`harness.session_repo`).** A session now starts from a
  repo cut at the key's parent: `git clone --no-local --single-branch
  --no-tags` from a branch at the parent, `origin` removed, reflogs
  dropped.
  - **Checked at the object level:** no commit that is not the parent
    or its ancestor, no remote, no alternates file, no path back to
    the owned clone.
  - **After the session,** its branch is fetched back into the owned
    clone and the cut repo removed. The gate, the verifier,
    `gold_tests` and recall still read the owned clone, host side.
  - **The repair turn** resumes on a repo cut at O's own commit, seeded
    with the unit's own parent graph.
  - **Sessions roots:** each session gets its own, so `/sessions` in
    the container shows no other session's transcript.
- **Registered:** C-124 (*partial*) — the container keeps the model
  endpoint's network, so upstream history is out of the repo but not
  out of reach.

## 0.1.19-beta — 2026-09-11 (Calvin M0-Gate, WP-18b)

**Patch: the gate's repair message names what a blocked name nearly
was, with signatures, not an unrelated body (gate v2).** Calvin
M0-Gate WP-18b, found by WP-20's pre-flight (D-w); checked with no
model.

- **The defect.** On a near-miss name nothing declares
  (`awkTokenizeRune`), the message showed "the form of a declaration":
  the binding directory's most-called function, an unrelated 110-line
  body (`extractColor`). That rule was built for a declaration the
  model is asked to write. At the gate it only picked a big function.
- **The fix.**
  - A blocked `invented` or `near-miss` name now lists the declared
    names nearest to it: the grounder's own nearest names, resolved
    to their symbols (same file first, then the package; five at
    most), each with its signature line.
  - A declaration's form appears only where the diff itself declares
    the blocked name, but where the reference cannot bind. It stays
    capped at 4,400 bytes.
  - The record gains `nearest_declared` and `rules.message` and
    stamps `gate_version` 2. Nothing else in the record moves: every
    verdict, class, row and site reads as before.
- **The Calvin driver** (bench tooling): `o-units` rows now carry
  - `recall` read at the unit's own repo pin (`--recall-upper`, else
    the unit's `recall_upper`, else gitleaks' as before; D-u);
  - §2.5's `gold_tests` and `turns_to_first_edit` (D-v);
  - `verdict`, which reads `empty` for a session that left no diff —
    neither pass nor blocked — with `verdict_gate` beside it, and
    `verdict_after` on repair rows.

## 0.1.18-beta — 2026-09-11 (Calvin M0-Gate, WP-18)

**Patch: `hobbes gate`, the linker on a finished diff.** Calvin
M0-Gate WP-18; built and checked with no model.

- **The command.** `hobbes gate --diff <patch> --parent <sha>` runs
  grounder v3 over any finished diff at its parent. It needs no
  template: the diff is read through a one-hole template.
  - **The split:** each name-absence NULL is looked up in the unit's
    blind-spot map (`--map`). A file-grain unresolved-site count
    never routes; it is context.
  - **The partition:** every touched file is checked against the
    unit's write partition (`--partition`, else the map's), at file
    grain, under `--partition-rule`:
    - `reach`, the default — the gate judges ingested code. A file
      that is not code (docs, man pages, build files, a language
      Hobbes does not ground) and a code file created beside a
      partition file are listed in `partition.reached`, not blocked.
      A write into an existing code file outside the partition
      blocks.
    - `exempt` — allows test-support paths only.
    - `strict` — allows nothing.
  - **The verdict** is *clear*, or *blocked* with the classes that
    fired: invented, near-miss, arity, undeclared-type,
    import-outside, unimported, malformed and partition. `malformed`
    now also covers a diff that does not apply at the parent.
  - **Not blocking:** `unknown` (a NULL in a region Hobbes cannot
    see) is reported and never blocks. `new` cannot arise from a
    finished diff; if it ever does, it is routed.
  - **The record** (`<diff>.gate.json`) is stamped with the gate,
    grounder and Hobbes versions and the sha256 of every input, and is
    byte-identical on rerun. The diff is also applied with `git apply`
    and the gate's own reading is checked against the result.
  - **Exit codes:** 0 clear, 1 blocked, 2 bad input.
- **The repair turn.**
  - `hobbes gate --message` prints a blocked record as a repair
    message: the classes, every site, the files outside the
    partition, and a declaration's form where a blocked name has one.
  - The agent loop gains `--resume-transcript`: a recorded session
    resumed with one more user message, its read tickets and repeat
    guards rebuilt from the transcript.
- **The Calvin drivers.** `calvin_probe.py o-units` and `o` gain:
  - `--gate` — post hoc (O+gate);
  - `--gate-repair` — one bounded resumed turn on each blocked row
    (O+gate+repair);
  - `--recorded DIR` — gate a prior run's sessions; O is never re-run.

  `o-units --withhold-manifest` sends O the task text alone.
- **Registered:** C-121 (`unknown` is advisory), C-122 (the partition
  at file grain), C-123 (the split's grain and classes); all
  *surfaced*.

## 0.1.17-beta — 2026-09-11 (later still, the fifth)

**Patch: the grounder checks a Go call's argument count and a
qualified name against the repo's own declarations (grounder v3).**
Calvin M0-Go round 2, WP-14b; checked by replay with no model.

- **Two new NULL classes.**
  - **`arity`:** a call bound in the graph whose argument count
    differs from the callee's own declaration.
  - **`undeclared-type`:** a qualified reference into one of the
    module's own packages that the package does not declare.

  The callee's parameters are read from lane A's own parse of its
  declaration, on demand; nothing is added to the graph, and the
  artifacts are byte-identical. On WP-10's seven declarations that did
  not build, 3 now raise one of these NULLs (arity 2, undeclared-type
  1); the unused imports stay the compiler's. Gold still grounds at
  0 NULL on 20 of 20.
- **Every doubt abstains.** The rule skips variadics, generics, method
  values, interface dispatch, a call whose sole argument is itself a
  call, callees outside the module (C-118), and a callee whose own file
  the same diff edits (C-119).
- **`malformed`.** A post-image carrying the render's line-number gutter
  reads as its own class with a reason, instead of silently grounding
  to zero references (C-120).

## 0.1.16-beta — 2026-09-11 (later still, the fourth)

**Patch: the Calvin adapter's protocol v0.6, and a benchmark no tree
runs no longer fails a diff.** Calvin M0-Go round 2, WP-14; checked by
replay with no model.

- **Adapter protocol v0.6**, superseding v0.5.
  - **The build row in the repair.** After a declaration is placed and
    grounded, the verifier's build row (`go build`, `go vet`,
    generation; contained, no tests) runs. A compile error naming the
    declaration's file goes back in the one repair, beside the
    grounder's NULLs, trimmed to the lines naming that file. WP-10's
    seven declarations that did not build now build on a scripted gold
    replay (7/7).
  - **The sibling whole.** The declaration hole shows its sibling whole,
    capped at 4,400 bytes (the gitleaks `rules/*.go` 95th percentile)
    instead of 12 lines.
  - **One budget.** A key gets at most `--budget` model calls in either
    arm: confirmations, fills and repairs in T, turns in O
    (`t-units --budget --verify-build`, `o-units --budget`). An arm at
    its budget stops and its row is scored as it stands.
  - **Record fixes.** A recorded fill is a copy, not a reference the
    loop later mutates. `usd_loop` counts the repair exchanges.
- **`not-run` no longer fails a diff.** A guard-selected test that runs
  on neither tree (a Go benchmark under plain `go test`) reads
  `not-run` and decides nothing. A test that ran without the diff and
  not with it still reads `removed`. Round 1's 20 golds are unchanged;
  one fresh gold moves from fail to pass, matching its own `gold_tests`.
- C-116 (the budget cuts a row) and C-117 (the sibling cut at 4,400
  bytes) registered; C-114 amended (the one repair reads build errors
  too).

## 0.1.15-beta — 2026-09-11 (later still, the third)

**Patch: `hobbes verify` no longer reads `pass` on a change no test
exercised.** Calvin M0-Go round 2's audit (WP-11a) re-scored round 1's
31 pass rows: 19 had reached no executed guarding test.

- **`vacuous`, a verdict of its own.** A diff that builds, selects
  tests and fails none, but where no guarding test actually executed
  (every selected id uncollected, skipped, not run, errored or
  unsupported), reads `vacuous`, never `pass`. The record carries
  `guarding_tests_executed` (count and ids); guards count by origin
  `guard` or `touched`, not `generate`. The order is `build-fail` →
  `no-tests` → `fail` → `vacuous` → `pass`, so C-93's `no-tests`
  (nothing selected) is unchanged.
- **`gold_tests`, the gold's own test changes on top of the diff.** A
  caller holding a gold diff (the Calvin driver) can apply its test-file
  hunks, with the fixtures beside them under `testdata/`,
  `__fixtures__/` or `__snapshots__/`, on top of an arm's diff and
  verify that. A `gold_tests` pass makes a row `pass` even where no
  guard executed. Its failures split into `fail`, `build-fail` (with
  Go's `undefined:` names) and `conflict`. Checked by a gold control:
  gold's own non-test hunks with `gold_tests` on top read `pass` on 7
  of 7 of round 1's keys. C-115 (fixtures only from those three
  directory names).

## 0.1.14-beta — 2026-09-11 (later still, the second)

**Patch: the grounder holds a Go fill to the repo's world (grounder
v2), and the adapter gets one bounded declaration repair (protocol
v0.5).** WP-8 found that every declaration the loop placed was written
against another project's API; these changes are its fix. Both were
checked by replay with no model.

- **Grounder v2, the world check.** A Go fill's imports must be the
  standard library (go1.26.5's `go list std` less `internal` and vendor
  paths, 176 packages, pinned as `GO_STDLIB`), a module the governing
  `go.mod` requires at the parent, or a directory of the module itself
  holding Go files. Any other import line in an edited range is an
  `import-outside` NULL. A qualifier on a call, selector or type that
  no import may bind is an `unimported` NULL, and every doubt abstains.
  The rule rides in each record's `world` block. WP-8's 9 placed
  declarations each raise at least one NULL, while gold still grounds at
  0 NULL, HSR 0, and 20/20 byte-equal.
- **Adapter protocol v0.5**, superseding v0.4. A NULL inside a placed
  declaration's body goes back once as a repair of the same declaration
  hole: one exchange, and no validation repair after it. The
  declaration hole shows a sibling's form, a function of the same kind
  from the binding directory with its file's package clause and
  imports. The loop's site record reads the grounder's refused list, so
  a refused declaration reads `refused`.
- Register: C-109 (a required module's package unchecked), C-110
  (unaliased import names read by convention), C-111 (build tags
  unread), C-112 (syntax errors unclassed — **unsurfaced**, debt), C-113
  (the world check is Go only) and C-114 (the declaration repair bounded
  to one exchange) registered; 114 entries, 88 active, 24 lifted, 2
  superseded.

## 0.1.13-beta — 2026-09-11 (later still)

**Patch: what the Calvin adapter offers after a NULL, and what it
refuses in a fill (protocol v0.4).** These came from WP-6's run on
M0-Go units and were checked by replay with no model.

- **Adapter protocol v0.4, the declaration hole**, superseding v0.3
  (v0.3's pattern reading stands). When T-loop's NULL round-trip meets
  a name that a call site writes and nothing declares (class `new` or
  `invented`, in no parent-graph module), it offers one hole per
  (name, scope). The answer must declare that name in a file of the
  binding directory with a body naming it. The declaration joins the
  template and the call site is re-grounded. A near-miss is still
  re-asked in the hole that wrote it (C-106). A declaration outside
  the write partition is placed and recorded, never refused, on Max's
  decision (C-107). Replayed on WP-6's records: 11 of 11 NULL sites
  closed with scripted gold declarations, and none opened.
- **The gutter guard.** A SIGNATURE or BODY fill carrying the render's
  line-number gutter is refused and named in the repair, and the
  grounder refuses it too; WP-6's three such fills are refused, 3 of 3.
- **The grounder's `scope` field.** Every NULL row carries the Go
  package directory it binds in, plus the type for a typed receiver.
  The declaration hole reads it; for a non-Go name or an
  `after_symbol` placement the directory is not checked (C-108).
- **Fix: loop closure keyed on (hole, term).** v0.3 keyed it on (hole,
  term, class), so a NULL whose class changed counted as closed and
  opened at once. No WP-6 row was affected.
- Register: C-106, C-107 (*surfaced*) and C-108 (*partial*) registered;
  108 entries, 82 active, 24 lifted, 2 superseded.

## 0.1.12-beta — 2026-09-11 (later)

**Patch: what the Calvin adapter accepts from an orchestrator (protocol
v0.3), and a metered arm-T driver.** Both came from the first model run
on M0-Go units (WP-5: five keys, Haiku 4.5, $1.17).

- **Adapter protocol v0.3**, superseding v0.2 (Max's decision). A
  pattern of `"unchanged"` on SIGNATURE or BODY, or `"unchanged"`/`"no"`
  on ANCHOR_CONFIRM, is accepted on the first pass. Each hole it covers
  is filled as unchanged or no and listed under `by_pattern`. A pattern
  never rewrites or confirms, an explicit fill wins, and a refusal by
  pattern counts as silence does. The validator reads a refused
  pattern's holes as `missing`, so the repair names them rather than
  losing them. `protocol_version` is stamped on every exchange and
  arm-T record. Refused patterns had cost 7 of 22 calls and 36% of the
  run's spend; replayed with no spend, 4 of the 5 such exchanges
  validate on the first pass (C-105).
- **`calvin_probe.py t-units`**: arm T over a set of units with per-key
  and total dollar caps, a usage ledger per key, `--key-name`,
  `--sampling`, `--rta-key` and `--verify`. `run_t(rta=)` hands the RTA
  key to both groundings. Rows carry `files_changed` and
  `rfe_changed`, since a body written back byte for byte is not a
  changed file.
- Register: C-105 registered (a pattern answers many holes with one
  judgement, *surfaced* by `by_pattern`); 105 entries, 79 active, 24
  lifted, 2 superseded.

## 0.1.11-beta — 2026-09-11

**Patch: Calvin's derive layer reads Go (the M0-Go round).** Three
changes in what the grounder, the verifier and the template draw. All
three were run on gitleaks' 20 M0-Go gold diffs with no model.

- **Grounder v1 on Go** (`hobbes ground`). Go's universe scope is pinned
  from go1.26.5, and a bare name binds a local, then the package, then
  the universe; it never binds a method. A member is judged when the
  syntax states its receiver's type (rule 1), and an interface method
  binds to the interface (rule 2; implementers are recorded, never
  bound). Every judged reference carries a density, `dense`, `sparse`
  or `absent`, beside its class. Four defects are fixed: a bare call
  could bind a method; builtins were checked before the package; an
  import alias beat a shadowing local; a missing method on a type over
  a basic type abstained instead of NULL. Gold run: 0 NULL, HSR 0,
  `unknown-receiver` 53 → 5, poison 50/50. C-91 amended.
- **The Go verifier** (`hobbes verify`, harness v2; ADR-100 amended).
  The repo's `//go:generate` regenerates a generated file on both
  trees rather than applying it, and is a test row where its import
  closure reaches the edit. A failing generation is retried up to
  three times, with each attempt recorded (C-103). Tests run by name
  at symbol grain and whole at package grain; `go build` and `go vet`
  are build rows (a `P2F` there is `build-fail`); `go test -list`
  gives `uncollected` and `removed`. The Go module cache is now
  mounted read-only over the cache root's rw mount
  (`containment.Plan.ro_cache`, C-92). `calvin.box.policy` allows
  `go generate*`. Gold run: 20/20 pass on two passes, `P2F` 0,
  `all_contained`.
- **Template v2** (`build_template(version=2)`, opt-in). An anchored
  symbol with more than 20 in-repo callees opens each callee as a
  signature-line confirmation instead of a body (C-104). v1 stays the
  default and rebuilds byte for byte, and the `hobbes template` CLI
  builds v1. At A2, round 2's open holes fall 6,973 → 1,866.
- Register: C-102 (lane A's Go local bindings skip a function's
  `var ( … )` group, *partial*), C-103 and C-104 registered, C-91
  amended; 104 entries, 78 active, 24 lifted, 2 superseded.

## 0.1.10-beta — 2026-09-10 (later still)

**Patch: a change in what Hobbes draws on a Gradle repo (C-67).** A
Gradle unit gets scip-java's javac plugin from Hobbes's own init script
— on each JavaCompile task's processor path, the way the oracle lane
attaches its plugin — and its shards are aggregated by `scip-java
aggregate`; scip-java's own Gradle plugin, which adds the jar to the
`compileOnly` configuration, is no longer in the path, because a build
that has resolved that configuration at evaluation time refuses the
add (Severed-Chains, one repo in four on the 2026-08-29 random draw,
had fallen to lane A whole). The image extracts the plugin jar and its
`--add-exports` list out of the pinned launcher at build. Maven is
untouched (ADR-096 amended).

- Severed-Chains re-ingested contained: capture 0.0% → **100.0%** of
  52,209 sites; regraded against its standing javac key at 100.0%
  precision, recall **23.5% → 60.8%** (29,793 edges, 0 contradicted,
  poison 0 falsely confirmed), every edge semantic. spring-petclinic's
  Gradle build through the same route beside its Maven grade.
- Under Gradle the dependency-coverage line is answered from what the
  build resolved (a task the init script registers writes scip-java's
  own `dependencies.txt`), since the aggregator alone names no
  third-party package; an external node is still named by its Java
  package. A build that replaces `compilerArgs` after configuration is
  refused with its own last words quoted. Kotlin sources are not
  compiled under the plugin (they were not indexed before either).
- Bench: `oracle grade` prints `recall-collapsed` beside the standing
  line (ADR-089 amended); the Java key's names are owner-qualified
  (H-23). Neither moves the version (ADR-103).

## 0.1.9-beta — 2026-09-10 (later still)

**Patch: a change in what Hobbes refuses to stage and what it says
(C-66).** The Java resolve pass's stage (ADR-097) was meant to hold no
source the build compiles; the walk that built it copied `.mvn/`,
`gradle/` and `buildSrc/` whole, past both the JVM-suffix filter and
the pruning, so a source hidden under `.mvn/` or `gradle/` reached the
networked pass — found by the 2026-09-10 baseline review
(`docs/reviews/2026-09-10-baseline.md`). One walk and one rule now:
lane A's pruning in every directory, `.mvn/` the one dot-directory
entered, a JVM source left out wherever it sits except below
`buildSrc/`, whose sources are the build logic itself (the one
exception, unchanged). The ingest notice says so: "a networked pass
whose stage holds no application source (build logic under buildSrc/
excepted)".

- Tested at three levels: the file list, the resolve plan's stage, and
  the contained canary, which now plants `.mvn/Hidden.java` and reports
  the resolve pass through a sentinel in the Maven cache — the fourth
  probe's `Phoned` could never see that pass, whose stage is discarded
  before the index runs. Shown to fire under the old walk.
- `buildSrc/build/` and `buildSrc/.gradle/` no longer ride either.
- Bench tooling beside it (unversioned): the callee-shape bucket's
  identity fixed (H-22) and the two cells re-measured.
- Register: C-66 surfaced again; 101 entries, 75 active, 24 lifted, 2
  superseded.

## 0.1.8-beta — 2026-09-10 (the versioned baseline)

**Patch: a change in what Hobbes draws (C-101).** The Java resolve
pass's stage (ADR-097) held "no source", where source meant `.java`; a
Maven build with Kotlin sources compiled them against Java that was not
on the stage, failed, and the unit fell to lane A's syntactic tier —
surfaced by the degradation record, found when every Hobbes cell was
regraded on one build for the comparative graphics (Max, 2026-09-10).
The stage now holds no JVM source the build compiles (`.java`, `.kt`,
`.scala`, `.groovy`; `buildSrc/` stays), and the Maven resolve pass runs
the repo's `mvnw` when it ships one — scip-java's index pass runs that
wrapper, and only the networked pass can fetch its distribution into
the cache (petclinic had passed on a warm cache alone); `MAVEN_USER_HOME`
names that cache, since the Java wrapper ignores `$HOME`.

- spring-data-elasticsearch: the resolve pass succeeds again; the cell
  is regraded semantic (its record's 2026-09-10 block).
- **Every Hobbes oracle cell regraded on this build** against its
  standing key — the comparative graphics and `docs/comparative/tables.md`
  now state the Hobbes version per cell (`bench/oracle/report/render.py`
  reads it from the record's last regrade heading).
- Register: C-101 registered and lifted; 101 entries, 75 active, 24
  lifted, 2 superseded.

## 0.1.7-beta — 2026-09-10 (later still)

**Patch: a change in what Hobbes draws (C-100).** TypeScript's ESM- and
CJS-flavoured sources, `.mts` and `.cts`, are discovered: they were on
neither lane A's extension list nor the helper's, so such a file was
not a module, its calls were not counted, and scip-typescript's index of
it (the file is in the tsconfig's program) had nothing to join to —
absent without a degradation record. Found by the callee-shape bucket
of cheerio's miss set (`docs/oracle/oracle-misses.md`), which answered
Max's question about the recall gap between a `tsc` key and a
`tsc`-based indexer: at symbol grain the indexer emits 98.8–100% of the
function declarations the key names; the gap is the key's overload
grain (one pair per signature) and targets below the symbol floor.

- cheerio (the zone's own `tsc` 6.0.3): 2,682 → 2,688 edges, 2,622 →
  2,628 confirmed, 0 contradicted; the six `scripts/fetch-sponsors.mts`
  rows recovered; every function-declaration target on the cell drawn
  (1,911/1,911 collapsed pairs). zod does not move (no such file).
- Both lanes: `tsextract/extract.mjs`, `hobbes.extract.tssource`,
  `hobbes.extract.tail`; the grounder, the agent policy's test-command
  map and the harness's vitest rule take the same two extensions.
- Register: C-100 registered and lifted; 100 entries, 75 active, 23
  lifted, 2 superseded.

## 0.1.6-beta — 2026-09-10 (later)

**Patch: a change in what Hobbes draws (the C-98 lane asymmetry
closed).** 0.1.5-beta left the two lanes reading a solution-style
`tsconfig.json` differently: lane A typed a file by the referenced
project that includes it, lane B still indexed the zone under a
generated config written over the solution file (C-90's technique).
Now lane B asks the TS helper for the same zone map (`--zones`, the
compiler's own reading) and passes scip-typescript the referenced
projects that claim the zone's files, each under its own config, plus
a generated config for the files none claims — written *beside* the
solution file, which stays intact for any project that `extends` it.
One rule, one implementation, both lanes; if the helper's map is
unavailable the zone falls back to the old shape and the ingest says
so.

- hono: 768/768 unchanged, one edge moved from the syntactic to the
  semantic tier (727 semantic confirmed), lane agreement 4,332 →
  4,336 both-resolved sites with the same one line-grain disagreement;
  lane B produces 9 fewer module edges (1,483 → 1,474): a file no
  referenced project claims is its own program now, in both lanes, so
  its references into a claimed project's files take the cross-program
  shape C-12 registers.
- **ADR-105:** a lane B provider is a pinned batch program with a
  stated version and a tier stamp, never a language server — P13,
  stated in §3.2 and in §3.7's first step for the next language. No
  code moves.



**Patch: a change in what Hobbes draws (C-98 lifted).** Under a
solution-style `tsconfig.json` — `files: []` and project `references`,
hono's root, any `tsc -b` monorepo — the TS helper built the zone's
project from the solution file, which carries no compiler options: the
checker ran at its ES5 defaults, `Array.flat` was unknown, a receiver
reached through a newer lib was `any`, and every lane-A observation that
needs the type was absent — callee, origin and ADR-104's abstention
alike. The helper now resolves a file under a solution config to the
referenced project whose inputs include it, by the compiler's own
reading of the configs (references followed transitively inside the
repo, the first named claimant wins) — the lane-A analogue of C-90's
rule. A file no referenced project claims runs under the default
options and the ingest says so (`tsconfig-unclaimed`, one degradation
line per solution config, the files sampled).

- hono regraded against its standing key: 767/768 → **768/768
  (100.0%)**, 0 contradicted; 15 sites on `src/` are typed now and
  abstained as `union-member` (C-97). The claim page's one named
  exception is quic-go.
- Found on the way and fixed in both lanes (**C-99**, registered and
  lifted): a tsconfig with `references` and *neither* `files` nor
  `include` was taken for a solution config — the compiler's default
  include is then the whole directory, so hono's six
  `runtime-tests/*/tsconfig.json` zones had been indexed under the
  generated config instead of their own options.
- Facts schema unchanged (v5); `errors` gains a stage. Lane agreement
  on hono unchanged.

## 0.1.4-beta — 2026-09-09

**Patch: a change in what Hobbes draws (ADR-104).** A member call on a
union-typed receiver whose members do not share one declaration of that
member — `n: A | B`, both overriding, `n.render()` — no longer draws an
edge to the first member's method. scip-typescript and lane A's own
checker both named that member at semantic certainty, and the compiler
names a member too; none of them is the static answer, which is "one of
these". The TS helper (facts v5) types the receiver and abstains, the
evidence join vetoes lane B's occurrence at that site, and the tail
counts the site under a new class, **`union-member`** (TS/JS only;
`list_blind_spots` and the ingest summary gloss it). Registered as
**C-97**; C-58 gains its TypeScript face.

- ajv regraded against its standing key: 1,375/1,378 → **1,410/1,410**,
  now contained; hono 767/774 → **767/768**. The row left on hono is a
  site lane A cannot type at all: its root `tsconfig.json` is a
  solution-style config that leaves the helper's checker with no
  compiler options — registered as **C-98**, not yet lifted.
- The fixture `minits/src/union.ts` holds the shape; the proxy's tail
  glossary carries the class (image rebuilt).

## 0.1.3-beta — 2026-09-09

The first stated version, so this entry says what 0.1.3-beta *is*
rather than what changed. *beta*: graded, not stable — the schema and
the tool surface still move (ADR-103 §5).

**The knowledge layer** — a complete deployment on its own (ADR-092
phase 4): `hobbes ingest` builds `.hobbes/derived/` from a repo on
disk with no model, and `hobbes-proxy serve --knowledge-only` serves
six read-only tools over it from the sandbox image (ADR-087/094).

- Six languages, each a tree-sitter syntax provider joined by one
  range join to a pinned SCIP indexer: Python, TypeScript/JavaScript,
  Go, Rust, Java, plus Terraform/HCL structure (architecture §3.8).
- Every edge carries a tier (`semantic` / `syntactic`) and its evidence
  line; every site nothing resolved is counted and classed, never
  drawn (ADR-045/047).
- Everything that executes repo-authored code runs in the one sandbox
  image; `--uncontained` is disclosed and stamped (ADR-092, C-64).
- The constraint register: 96 entries, 74 active, each naming where a
  user meets the limit (`docs/constraints/`).
- Compiler-graded by the oracle lane: 0 falsely confirmed of 99,824
  seeded wrong edges across 19 cells; every compiler-graded cell at
  100% precision-against-oracle except three named ones
  (`docs/comparative/`, ADR-089/101).
- Every artifact and every knowledge answer states which Hobbes
  built it: now version and commit (ADR-094, ADR-103).

**The agentic layer** — sessions in rootless Podman under a Go policy
chain (deny overrides allow; allow | deny | escalate), the tool proxy
and flight recorder, `hobbes plan` / `hobbes run` deriving per-unit
context and policy from the graph (ADR-051/054), `hobbes review` at
the concept level with compiled invariants, `hobbes verify` (ADR-100).
Under test; no benchmark claim earned (architecture §6.2).

**Not in the version:** the oracle lane and its foreign converters,
the benchmark harness, Calvin, the test-time-training and Atlas-0
instruments — `bench/`, internal testing.
