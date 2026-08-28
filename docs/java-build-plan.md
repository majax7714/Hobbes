# Hobbes — Java addition, build plan (parked)

**Status: parked — a plan, not a queue.** Written 2026-08-28 at Max's
ask ("map out the Java addition with a build plan"; interest, not
intent). Nothing here is un-parked; the programme opens when Max names
it, with an ADR-096 as its first commit. Sequencing rules carry from v1
and v2: deterministic before generative, one milestone active at a
time, each milestone exits on a real repo, stop at exits for Max's
review.

This is architecture §3.7's four-step checklist, elaborated to
file-level work with exit criteria, against the code at `90e4948`. The
Rust proof (V2.M7, ADR-040) is the comparable and is cited where Java
follows it; where Java differs it says why.

---

## 0. What the code says, before planning anything

**Ingest is per language, gated on discovery — not run regardless.**
`extract/__init__.py` runs each provider only when discovery found its
files: lane A behind `if ts:` / `if go:` / `if rust:` (lines 104–118,
146–150, 238–244, 292, 318), lane B the same way in `_lane_b_facts`
(470–478); Python runs only when `discover_modules` found modules. A
language with no files in the repo costs one directory walk by
extension (its discovery) and nothing else — no grammar load, no
indexer, no container. Adding Java therefore adds ingest time **only to
repos with `.java` files**. The one cost every repo pays is the
**image**: `sandbox/Containerfile` carries every toolchain (ADR-092's
one-image decision), so a JDK makes `podman build` longer and the image
larger for everyone, once per build — a build-time cost, not an
ingest-time one. If that ever hurts, the slim-ingest-image option
ADR-092 left open is the answer, not per-language images.

**What a language touches (§3.7, verified against Rust's commit):** the
`INDEXERS` table in `scip/index.mjs`; a lane A provider module; a
containment plan shape in `extract/containment.py`; the tail view's
extension and class tables (`tail.py`); language-specific projection
guards; `VERIFICATION_BASE` in `extract/verification.py`; a fixture
under `pipeline/tests/fixtures/`; a §3.8 row. Nothing in the graph
builder, the join or the schema.

**What is new with Java, that no current language forced:**
1. **Overloads** — one terminal name, several declarations. Lane A
   emits the name; SCIP resolves the site to one symbol. The range join
   is by position and tolerates this; the *lane-agreement* check
   (`hobbes lanes`) compares resolved targets and must compare on
   symbol, not name, or every overloaded call is a false disagreement.
2. **Nested and anonymous classes** — `Outer$Inner`, `Foo$1`. Module
   identity is "one file = its top-level type(s)" by the language's
   own rule, so C-15's cross-language namespacing question is *less*
   pressing than for C; it still needs the decision written down.
3. **Generated sources** — annotation processors, Lombok, protobuf.
   `scip-java` indexes them if the build produced them; lane A never
   sees them. Rust's generated-code class (derives, proc-macro tokens)
   is the precedent and the disclosure shape.
4. **Virtual dispatch as the default.** Every non-final instance call
   is potentially polymorphic. The static edge goes to the declared
   target, tiered; the oracle grades it against CHA and RTA. This is
   C-58's dispatch face made the majority case, and the measurement is
   the point of the milestone that grades it.

---

## J.M0 — ADR-096 and the spike (1)

*See real `scip-java` output on one repo before freezing anything —
V2.M0's rule.*

- **ADR-096**: pin `scip-java`'s version and its JDK; the build-tool
  policy (Maven / Gradle wrapper detected from the repo, `--build-tool`
  never authored — ADR-027's derived-config rule); the one-configuration
  concession (the graph is the build's default profile/flavor); the
  module-identity decision for nested classes; where generated sources
  land (indexed and marked, or excluded).
- **Spike** (`scip/spike/java/`, like the v2 spike): run `scip-java`
  inside the image on one small Maven repo and one Gradle repo, decode
  with the existing `index.mjs` reader, count occurrences with
  `syntax_kind` set (expected: 0 — the ADR-037 finding, which is why
  lane A is mandatory), record overload and nested-class symbol shapes.
- **Exit:** the ADR accepted; a spike note with the symbol shapes and
  the two builds' wall time; the image grows the JDK + `scip-java`
  behind a pinned layer; `podman build` time before/after stated.

## J.M1 — Lane A: `javasource.py` (2–3)

- `tree-sitter-java` pinned in `pipeline/pyproject.toml` beside the
  four grammars; `javasource.py` at `gosource.py`'s shape (~800 lines):
  declarations (classes, interfaces, enums, records, methods,
  constructors, fields), imports (incl. static and wildcard), call
  sites (`method_invocation`, `object_creation_expression`,
  `explicit_constructor_invocation`, method references `Foo::bar` as a
  *use*, not a call), each with file, line, column, terminal name and
  the receiver recorded as expression-or-name (the O4 rule).
- Discovery by `.java` extension; `package` declaration → module id;
  the nested-class rule from ADR-096.
- Tail tables (`tail.py`): Java's builtin-name list (`java.lang` only),
  local-binding vocabulary.
- Fixture `tests/fixtures/minijava/` — a Maven project with one of each
  shape: overload pair, nested + anonymous class, static import, lambda,
  method reference, interface dispatch, generic method, a JUnit test.
- **Exit:** the provider's tests green; `hobbes ingest` on the fixture
  yields a syntactic-tier graph with every planted call site detected;
  the class table classifies every unresolved remainder (nothing
  `unclassified` on the fixture).

## J.M2 — Lane B: `scip-java` contained (2–3)

- `INDEXERS.java` in `scip/index.mjs`; `scipsource.extract_scip_java`
  deriving the build tool and JDK from the repo.
- Containment plans (`containment.py`): `fetch-java` (dependency
  download, registry network) and `index-java` (`--network none`),
  cache root rw for `~/.m2` / Gradle caches under the Hobbes cache root
  — the `fetch-rust`/`index-rust` pair verbatim. The executing step
  refuses without the image (`ContainmentRefusal`, C-64 wording).
- The join: overload-safe lane agreement (§0.1) — the projection guard
  and its test; a Java entry in the duplicate-symbol wording (D7).
- **Exit:** the fixture ingests with semantic edges for every planted
  call, `hobbes lanes` clean; a canary (a `build.gradle` / Maven plugin
  that writes a host sentinel, like `canary-rust`) proves the build ran
  in the container; contained-vs-host diff on the fixture is empty.

## J.M3 — Packs: JUnit first, Spring second (1–2)

- `packs/junit.py`: `@Test`, `@ParameterizedTest`, `@Nested`, JUnit 4
  `@Test` — without it `tests.json` is empty and `tests_guarding`
  answers nothing for Java. Test-reach closure over call edges is
  already language-neutral.
- `packs/spring.py` (optional, this milestone or later): route pack
  over `@RequestMapping`/`@GetMapping` etc. — the Flask/FastAPI shape;
  `@Autowired`/constructor injection recorded as the C-4 fixture-
  injection class.
- **Exit:** removability byte-for-byte (V2.M4's rule); the fixture's
  JUnit test reaches its callee in `tests_guarding`.

## J.M4 — The oracle: bytecode CHA/RTA (2–3)

*Bench tooling, never product (ADR-089).*

- `bench/oracle`: a `java-cha` subcommand driving **SootUp** (or WALA)
  over the compiled classes, emitting the oracle edge set at two
  precisions — CHA (every override reachable) and RTA (instantiated
  types only) — in the `export`/`grade` format; run contained
  (`bench/oracle/internal/contain`, the verifier's mount shape).
- Grade the fixture (self-test), then two real repos: one Maven
  library, one Spring service. Poison check on every cell.
- **The measurement this milestone exists for:** precision of the
  declared-target edge against CHA (expect ~100% — a declared target is
  always *a* CHA target) and recall against RTA — the size of the
  dispatch hole on a real Java codebase, as a number, per repo. C-58's
  Java entry cites it. The X-Corpus / Reif et al. call-graph suites are
  candidate answer keys Hobbes does not control.
- **Exit:** cell records in `docs/oracle-cells/`, signed direction-of-
  fix lines, `oracle-misses.md` gains Java's classes.

## J.M5 — Evidence and the claim (1)

- §3.8 row + `VERIFICATION_BASE` (the suite holds them together);
  `extraction-evidence.md` dated entry with the `Verified:` line and
  the `containment` stamp (P11 as scoped by ADR-092's review).
- Register entries in `docs/constraints/extraction-java.md` (new
  segment; index row in `README.md`): one-configuration graph;
  generated sources; dispatch (C-58's Java face, sized by J.M4);
  reflection/DI; overload-agreement residue. Each with a surfacing
  status; `list_blind_spots` names them.
- Architecture §3.8 language row, `tail.py` class table, CLAUDE.md
  status line and the `list_blind_spots` verification-base line.
- **Exit:** Max's review; "supported" reaches exactly as far as the row.

---

## Total and shape

Nine to thirteen sessions, one milestone active at a time, in the
order above — J.M1 before J.M2 because lane A is mandatory (ADR-037)
and gives a graph even where the build cannot run. Comparable to Rust
(V2.M7 was 1–2 sessions *after* the checklist existed and with a
one-crate proof); Java's extra weight is the oracle milestone and the
build-system surface, both worth it for the reasons in the comparison
below.

## Risks

- **Build time in lane B.** A Gradle project with a cold cache is
  minutes, not seconds; the cache-root mount and the W1 cache-hygiene
  item carry this. State the fixture and real-repo wall times in every
  cell record.
- **Image size.** A JDK adds ~300 MB. If the one-image decision
  starts to hurt every non-Java repo's `podman build`, ADR-092's slim
  ingest image is the recorded alternative.
- **`scip-java` needs a compiling project.** A repo that does not build
  in the image gets lane A only — disclosed (C-64 wording), and the
  most common real-world outcome for enterprise repos with private
  registries. Egress-narrowing (C-41) and registry mirrors are the
  follow-up, not this plan.
- **Overload agreement** is the one join change; get it wrong and
  `hobbes lanes` goes red on every Java repo. It has its own test in
  J.M2 before any real repo.

## Why Java before C (from the 2026-08-28 comparison)

Stronger lane B (`scip-java` is first-tier, config is derivable),
an oracle that exists off the shelf over a stable IR, packs that map to
existing shapes (routes, tests, injection), and the target audience —
large, long-lived, review-heavy codebases — is the thesis's. C is
cheaper to parse and dearer to build, with a weaker semantic story and
per-configuration graphs; it follows Java on the same checklist if
named.
