# ADR-096 — Java: the sixth language, and what its build costs the containment story

**Date:** 2026-08-29 · **Status:** accepted — J.M0–J.M2 built this session (the spike, lane A, contained lane B); J.M4 (the oracle) and J.M5 (the evidence row) follow in `docs/java-build-plan.md`'s order · **Owner:** Max · **Source:** `docs/java-build-plan.md` (parked 2026-08-28, opened 2026-08-29 at Max's direction: "begin implementing java as an added language")

Amends the architecture's **§3.1** (a sixth syntax provider), **§3.2** (a
fifth indexer; the one index step with a network), **§3.7** (a sixth
worked example). Registers **C-66**, **C-67**, **C-68**, **C-69**
(`docs/constraints/extraction-java.md`). Adds a face to **C-29** and
**C-58**. Evidence is reproducible via `scip/spike-java.mjs`.

## Context

§3.7's checklist, as corrected by ADR-037 and proven by Rust (ADR-040):
register an indexer, write a syntax provider, record evidence. Java is
the first language whose *indexer is a build step*: scip-java is a javac
compiler plugin, and the only way to hand javac a classpath is to run
the build that resolves one. That single fact shapes every decision
below, and it is why this ADR is longer than ADR-040.

## What the spike found (`scip/spike-java.mjs`, 2026-08-29)

Run inside the image on a copy of **jhy/jsoup** (Maven, 197 files) and
**spring-projects/spring-petclinic** (Gradle 9.5.1 wrapper and Maven
both present; Gradle chosen for the spike):

1. **`syntax_kind` is unset for 104,453 of 104,453 occurrences** (jsoup)
   and 6,677 of 6,677 (petclinic). scip-python 0/8,575, scip-go
   0/18,682, rust-analyzer 0/169, scip-java 0/104,453 — four
   independent implementations, the same omission (C-6). §3.7's
   mandatory syntax provider stands confirmed a fourth time.
2. **The moniker version is the artifact's own** — `1.24.1-SNAPSHOT`
   for jsoup, the dependencies' Maven versions, `21` for the JDK — never
   the git revision. Decision 1 (ADR-027) is satisfied by default, as it
   was for rust-analyzer. A Gradle project without `maven-publish`
   coordinates gets package `.` version `.` for its own symbols (3,081
   of petclinic's occurrences): still constant, still fine.
3. **Overloads and constructors have their own descriptor shapes.** An
   overload set is `Regex#compile().`, `Regex#compile(+1).`, …; a
   constructor is `` Regex#`<init>`(+N). ``. The helper's `classify`
   read `(+1).` as a *term* and `terminalName` handed the join
   `compile(+1)` and `<init>` — names no call site spells. Both fixed
   (decision 4).
4. **Positions arrive in SCIP's typed range** — `Occurrence.single_line_range`
   (field 8) / `multi_line_range` (field 9), the `scip-code/scip` proto at
   a7b9c65a (2026-08-25) — and the deprecated `repeated int32 range` is
   left empty. The generated reader the helper borrows from
   scip-typescript 0.4.0 (the newest release, 2025-10) knows neither
   field and skips them: **every Java occurrence decoded as unplaced.**
   Decision 5.
5. **Nothing outside the repo.** 0 documents outside the stage on
   either build; no generated-source documents on these two.
6. **Wall time.** jsoup: 37 s cold (`clean verify -DskipTests`, the
   default), 13 s warm; 9 s warm with `clean test-compile`. petclinic:
   32 s (Gradle wrapper, 9.5.1 distribution downloaded into the cache).
   `podman build`: the Java layer adds **1.1 GB** (1.68 → 2.79 GB: three
   JDKs, Maven, the 86 MB scip-java launcher).
7. **Gradle refuses a JDK it did not ask for.** petclinic pins
   `languageVersion = 17`; on an image carrying only JDK 21, Gradle
   9.5.1 fails at configuration ("cannot find a Java installation …
   toolchain download repositories have not been configured"). With
   `org.gradle.java.installations.paths` naming the image's JDKs it
   builds. Decision 2.
8. **A Maven fetch phase does not reproduce the build.** `mvn
   dependency:go-offline` on jsoup fails on
   `io.netty:netty-tcnative:${os.detected.classifier}` — a property a
   *build extension* (`os-maven-plugin`) supplies only when the build
   runs — and the subsequent `--offline test-compile` fails on three
   missing test-scoped artifacts. Gradle has no fetch that does not
   evaluate `build.gradle`. Decision 3, and C-66.

## Decisions

**1. The indexer is scip-java 0.13.1, run as shipped, driven through the
repo's own build.** `INDEXERS.java` = `scip-java index
--build-tool=<derived> --output … -- <build command>`; the launcher is
the release's coursier bootstrap (`scip-java-v0.13.1`, sha256-pinned in
`sandbox/Containerfile`), self-contained after download. The build tool
is **derived** (ADR-027's rule): `maven` when a `pom.xml` roots the
unit, else `gradle`; a directory holding both is indexed with Maven (its
resolution is declarative). The build command is Hobbes's, not
scip-java's default: Maven runs `--batch-mode -DskipTests clean
test-compile` — compilation only, not `verify`, which would execute
every plugin bound to the lifecycle (jsoup's `japicmp`, `failsafe`, …);
Gradle runs `clean compileTestJava`. Kotlin sources are not indexed
(scip-java supports them under Gradle; Hobbes has no Kotlin lane A, so
they would be references without call sites — §3.7 again).

**2. The image carries the three LTS JDKs scip-java supports — 17, 21,
25 — Temurin, version- and checksum-pinned, JDK 21 the default.** A
Gradle toolchain pin refuses any other major (finding 7) and there is
no honest way to download one at index time; upstream's own image
carries the same three. The ingest planner writes a derived
`gradle.properties` under `GRADLE_USER_HOME` (in the Hobbes cache):
`org.gradle.java.installations.paths=/usr/local/java-17,…-21,…-25`,
`auto-download=false`, `daemon=false`. Maven runs on the default JDK
with whatever `<release>` the pom sets; a pom that *requires* a JDK
major via `maven-toolchains-plugin` degrades per unit (C-67). Gradle is
not installed: a Gradle repo runs its own wrapper, which downloads the
distribution it pins into the cache.

**3. Java lane B is one contained step with a network — `index-java`:
`executes_repo_code=True`, `network="default"`.** The other executing
step (Rust) has no network because a *fetch* container that runs no
repo code fills the registry first (ADR-092's phase separation). Java
has no such phase: dependency resolution *is* evaluating the build
(finding 8), and evaluating the build executes repo-authored logic —
a Gradle script literally, a pom through the plugins and extensions it
names. So the container is the boundary — rootless, the Hobbes cache
its only writable mount, the helper and the stage read-only otherwise —
and the network is not. **Registered as C-66**, disclosed on every Java
ingest (the `NOTE:` line names the network) and in `graph.json`'s
`containment` stamp (the step is listed; `all_contained` stays true —
it *is* contained; what it is not is offline). The canary
(`tests/fixtures/canary-java`, a Maven `exec` bound to
`generate-sources`) proves the build runs and reaches neither a planted
host secret nor the host filesystem. Declined: (a) lane A only for
Gradle — most modern Java is Gradle; (b) `--network none` with a
best-effort `go-offline` fetch — two code paths and a quiet 30%
failure class; (c) a route filter — rootless podman has none (ADR-092).
**This is the decision Max should ratify or reverse**; reversing it is
one field in `containment.PROFILES`.

**4. The helper learns three Java shapes.** `classify` reads
`name(+N).` as a method (an overload's disambiguator, not a parameter);
`terminalName` strips the counter and the backticks, and maps `<init>`
to the *enclosing type's* name — what the syntax provider saw at `new
T(..)` and at the constructor's declaration; `SELF_PACKAGES` gains
`jdk` (the class library resolves from the image's JDK, always) and `.`
(the repo's own package namespaces, and a Gradle project without
publish coordinates); `DUPLICATE_SHAPES.java` words the C-28 record
(`package a.b;` in every file); dependency coverage is matched **at the
Maven group** — a pom declares `junit-jupiter`, an aggregator with no
classes, and resolves `junit-jupiter-api`.

**5. The helper owns the typed-range reader.** `Occurrence.deserialize`
is replaced in `index.mjs` with the borrowed switch plus cases 8 and 9,
folded into the `[startLine, startChar, endLine, endChar]` shape every
consumer already reads; a typed range wins over a deprecated one, as
the proto says. Tested on hand-built messages for both typed shapes and
the deprecated one, so the four other indexers are unmoved. The
override is deleted the day the borrowed reader learns the fields.

**6. Lane A: `javasource.py`, on the `rustsource` contract, with three
rules Java forced.** *(a) Overloads.* Symbol ids stay unique: the first
declaration of a qualname keeps it, later ones carry `~2`, `~3` in
source order; `name` is the bare name on every one. The fallback
resolver **abstains** when the name it would bind has more than one
declaration in the scope it resolved to — an overload set, a
constructor pair — because choosing needs argument types (lane B's),
and a guess would be a false edge (ADR-007) *and* a false lane
disagreement on every overloaded call. The abstentions are reported
(`overload_sites`) and the tail names them **`overload-set`**, a new
class available to Java only — an observation, not a guess. *(b)
Nested types* are symbols with dotted qualnames; anonymous classes,
lambdas and local classes are below the floor (C-9) and their calls
attribute to the enclosing declaration — the closure rule. *(c) An
import names a type, and a type is a file* — Java's own rule — so lane A
emits in-repo `imports` edges where `import a.b.C` maps to exactly one
discovered `…/a/b/C.java` (two → unattributed, the C-28 rule at lane
A), `ext:<package>` otherwise; same-package references need no import,
so Java joins Go and Rust in the lane-agreement exclusion. Also: the
one expression receiver lane A reads is `new T(..).m()` — the type is
spelled, not inferred (the O4 rule's boundary, stated); `Foo::bar` is a
*use*, never a site; `this(..)` is a site named after the enclosing
type, `super(..)` is left to lane B; `System.getenv("X")` joins the
cross-layer `env:` nodes; `java.lang`'s public types are the pinned
builtin list (`jimage list` on the image's JDK 21) and an `import`'s
bound name — a type's or a static member's — is an `import-binding`.
Test inventory: `@Test`, `@ParameterizedTest`, `@RepeatedTest`,
`@TestFactory`, `@TestTemplate` on a method, framework `junit` — an
annotation is an attribute the way `#[test]` is (ADR-040 decision 7),
so JUnit lives in the provider, not a pack; the plan's `packs/junit.py`
is not built. Methods of anonymous class bodies — an enum constant's,
a `new Runnable() {..}` — are recorded as *local bindings* with the
body's extent (ADR-046's mechanism), because jsoup's first ingest left
exactly 44 sites unclassified and every one was a call of such a
member (`anythingElse(t, tb)` in `HtmlTreeBuilderState`'s constants),
which scip-java names `local`. A Spring route pack stays pack territory (later, if named).

**7. Units.** Files group by build root: a Maven reactor (the highest
`pom.xml` above the file) or a Gradle build (the nearest
`settings.gradle[.kts]`, else the build file's own directory). Staged
beside the sources: **every other unpruned file under the root** — the
poms and scripts at every level, the wrappers, `gradle/`, `.mvn/`,
`buildSrc/`, resources, a checkstyle config — never `target/`,
`build/` or a dot-directory the tools do not own. The first cut staged
build files only, and the first real repo (spring-petclinic) failed at
`validate` on a `src/checkstyle/nohttp-checkstyle.xml` its pom binds:
a build sees the tree it was written for, and the stage is a copy, so
the cost is bytes. Files under no build file are skipped and reported
(C-26's pattern). Wrappers get their mode back after the copy.

## Consequences

- **P7 holds narrowly, as for Rust:** zero lines in the graph builder,
  the join or the schema. What Java did touch, stated: one provider,
  one `INDEXERS` entry plus the reader override and three descriptor
  rules in the helper, one staging function, one containment profile,
  the tail's extension/class/builtin tables (and one new class), the
  I-4 roster, and the four orchestration touches every language adds.
- **The containment statement is weaker for Java than for Rust** and
  says so wherever it is read (C-66). The guarantee that survives is
  the one ADR-092 was drawn around: repo code never executes on the
  host.
- **Image:** +1.1 GB. If it starts hurting non-Java repos, ADR-092's
  slim ingest image is the recorded alternative, not a Java-less image.
- **"Supported" reaches nowhere yet** (P11): Java is *wired*.
  `verification_base` reports it verified on zero repos until J.M4's
  oracle cells license a §3.8 row.
- **Kotlin** is out of scope; a repo mixing the two gets Java edges and
  Kotlin references without sites.
