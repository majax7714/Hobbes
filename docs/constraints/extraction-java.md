# Extraction — Java

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-66 — Resolving a Java repo's dependencies runs its build logic, in the container, with a network — *narrowed 2026-09-01 (ADR-097)*
- **Cannot tell you:** nothing — like C-29 this registers something
  Hobbes *does*: `hobbes ingest` on a Java repo runs that repo's own
  build twice inside the ingest container. The **resolve pass**
  (`fetch-java`) runs the build's dependency resolution — Maven's
  `test-compile` over a stage with nothing to compile, or the Gradle
  wrapper with a Hobbes init script that resolves every configuration —
  **with network access**, on a stage that holds the build files and
  the other non-source files under the build root and **no source the
  build compiles** (`.java`; since C-101, `.kt` / `.scala` / `.groovy`
  too) **outside `buildSrc/`**, whose sources are the build logic and
  ride with the build files — one walk, one rule in every directory
  since 2026-09-10 (below).
  The **index pass** (`index-java`) runs the build with scip-java
  attached on the full stage, **offline** (`-o` / `--offline`). A Gradle
  script is code; a pom names the plugins and extensions the build runs;
  in the resolve pass either can reach the network while it runs.
- **Because:** scip-java is a javac plugin, and javac needs the
  classpath the build resolves. Neither tool has a fetch that evaluates
  nothing (ADR-096's spike: `dependency:go-offline` misses what a build
  extension supplies; Gradle resolves while running its script), so the
  separation ADR-092 draws by *what runs* is drawn here by *what the
  container holds*: the pass that can reach the network never sees a
  source; the pass that sees the sources has no route out. What is kept:
  the container is rootless, the Hobbes cache root is its only writable
  mount, the helper and the stage are otherwise read-only, and the build
  never runs on the host (C-64: both steps refuse without the image).
- **Bites at:** security posture, narrowly. An untrusted Java repo's
  build logic can exfiltrate what the resolve container sees — its own
  build files and resources (a private repo's `application.properties`
  is the case to know about), and the Hobbes cache (public artifacts:
  Maven, Gradle, coursier, npm, cargo, Go caches; other repos' stages
  are removed after use) — over the network while resolving. Not the
  sources, not the host, not the user's repo, not `~/.m2`. Before
  2026-09-01 the sources were in that container too.
- **You find out:** **surfaced** — a `NOTE:` line on stderr every time
  the Java lane runs, naming both passes; `graph.json`'s `containment`
  stamp lists `fetch-java` and `index-java`;
  `containment.PROFILES["fetch-java"]` is the one profile with
  `executes_repo_code` *and* `network="default"`, and the suite pins
  that it is the only one and that its stage carries no application
  source (a source planted under `.mvn/` included); the canary
  (`tests/fixtures/canary-java`) plants one under `.mvn/` and proves no
  pass saw a source and the network together — the index by `Phoned`,
  the resolve pass by a sentinel in the Maven cache.
- **Provider (P9):** inherited from `scip-java` **0.13.1** and the
  build tools it drives (Maven **3.9.16** in the image; the repo's own
  Gradle wrapper). The next narrowing is an allowlisted egress proxy on
  an internal podman network (measured feasible, ADR-097; W1), which
  would confine the residual to the registry hosts.
- **Source:** ADR-096 decision 3, as amended by ADR-097.

**Review correction, 2026-09-10 (C-66 remains active):** the source-free
statement above is the intended boundary, not a universal property of
0.1.8-beta. `java_build_files` copies `.mvn/`, `gradle/` and `buildSrc/`
recursively without the suffix filter or normal descendant pruning.
A temporary-tree reproduction retained `.mvn/Hidden.java` and
`gradle/Hidden.kt`; `buildSrc/src/Logic.java` also stays by the intended
build-logic exception. These files are available to the networked resolve
pass. The canary proves its ordinary source path, not arbitrary build-tool
directories. **Surfacing: partial** — this register and architecture §3.2
name the limit; the ingest notice still says “holds no sources” and needs
correction with the staging fix. No network exfiltration was attempted.
See [the review](../reviews/2026-09-10-baseline.md). This does not invalidate
the separate guarantee that executing Java steps require containment.

**Fixed 2026-09-10 (later; 0.1.9-beta) — the boundary is what the
entry says again:** `java_build_files` walks every directory by one
rule (lane A's pruning; `.mvn/` the one dot-directory entered; a JVM
source left out wherever it sits, `buildSrc/` the one exception, whose
sources are the build), so `.mvn/Hidden.java` and `gradle/Hidden.kt`
no longer reach the resolve stage and `buildSrc/build/` no longer
rides. The notice reads "holds no application source (build logic under
buildSrc/ excepted)". Tested at three levels: the file list, the
resolve plan's stage, and the contained canary — whose fourth probe
could never see the resolve pass (that stage is discarded before the
index runs), so it now also drops a sentinel in the Maven cache, shown
to fire under the old walk and not under the new. **Surfacing: surfaced**
again. The residual stands as registered: build logic with a network
over the build files, `buildSrc/` and public caches; a `build-logic/`
included build is not excepted and degrades visibly.

### C-67 — The Java graph is the build's default configuration
- **Cannot tell you:** what a source set the default build does not
  compile looks like — a Maven profile that is off, a Gradle source set
  or flavor the `compileTestJava` chain does not reach, a module the
  reactor excludes — nor a repo whose build does not succeed in the
  image: a JDK major the image lacks (it carries 17, 21, 25) and a pom
  that *requires* one via `maven-toolchains-plugin`, a private registry
  the container cannot reach, a build that needs a native toolchain.
  Such a unit falls to lane A's syntactic floor, whole.
- **Because:** one configuration is one classpath, and the graph is
  one graph (the C-7/C-8 shape a build system makes explicit). Running
  every profile would produce several graphs of one repo, which no
  consumer can read.
- **Bites at:** enterprise repos with private registries (the most
  common outcome, expected), multi-flavor Gradle builds, JDK 8/11
  projects (scip-java dropped them at 0.13) — **and Gradle builds whose
  compiler arguments another plugin owns.** Sighted on the second random
  draw of 2026-08-29: `scip-java` could not attach its SCIP plugin to
  **Legend-of-Dragoon-Modding/Severed-Chains** ("another Gradle plugin
  is replacing the compiler arguments we add", its own words), so all
  1,254 files fell to lane A's syntactic floor — 10,154 edges, every one
  confirmed by javac, at **23.5% recall** against 54,520 in-repo pairs.
  One repo in four, on an unfiltered sample. The oracle lane's own
  plugin *did* attach to the same build through an init script, which is
  the recorded difference between the two injection strategies.
- **You find out:** **surfaced** — the per-unit degradation record
  names the build root and the build tool's own error; lane A's files
  under no build file are reported by directory (the C-26 pattern).
- **Provider (P9):** inherited from `scip-java` **0.13.1** (JDK 17+
  only; Gradle 8+ only).
- **Source:** ADR-096, decisions 1–2, 7.

### C-68 — Generated sources are lane B's alone
- **Cannot tell you:** the call sites *inside* code an annotation
  processor, Lombok, or a protobuf/gRPC plugin generated during the
  build — and the callers of it, at lane A's grain. scip-java indexes
  generated sources the build compiled (it sees javac's view); lane A
  never sees them (they are under `target/` or `build/`, pruned by
  every walk). A reference *into* a generated declaration therefore has
  no symbol to land on and draws no edge (`below-floor`, C-58's rule);
  a call *from* generated code has no site and is not counted at all.
- **Because:** the builtin-name/pruning rule that keeps build output out
  of the graph is the same rule that keeps generated sources out; the
  alternative — indexing `target/generated-sources` as if it were
  authored — would put code nobody wrote into the review surface.
  Rust's derive/proc-macro output is the precedent (its class in
  `docs/oracle/oracle-misses.md`).
- **Bites at:** Lombok-heavy codebases (every `@Getter` call is a call
  into nothing), protobuf clients, MapStruct mappers, Dagger/Micronaut
  DI factories.
- **You find out:** **partial** — a reference into generated code
  counts in the `below-floor` tail class per file (surfaced), but the
  class does not say *which* declarations are generated versus merely
  below the floor.
- **Not yet measured, and the sample says why.** The four O8 cells of
  2026-08-29 report `excluded.generated: 0` on every one — none of
  jsoup, spring-petclinic, spring-data-elasticsearch or Severed-Chains
  runs an annotation processor that emits sources into the graded set
  (what they do have is javac's *synthetic* code, counted separately:
  411 / 50 / 1,167 / 980 inserted `super()` calls). So this entry's
  size is unknown rather than small, and the honest next step is a cell
  on a Lombok- or protobuf-heavy repo, not a number inferred from four
  repos that do not exercise it.
- **Source:** ADR-096; the O8 cells; the Java plan's §0.3 (the plan was
  removed 2026-09-09 — its observation, that annotation processors and
  Lombok emit sources lane A never sees and `scip-java` indexes only when
  the build produced them, is this entry's premise).

### C-69 — Declared Java dependencies are read, not resolved
- **Cannot tell you:** an exact dependency-coverage count for a Java
  unit. A pom's `<dependencies>` are parsed as XML, matched to the
  index **at the Maven group** (a declared aggregator resolves to its
  siblings), with `${property}` groups other than `${project.groupId}`
  skipped; a Gradle build's declarations are *text* — a
  `libs.versions.toml` catalog parsed as TOML plus `"g:a:v"` literals
  in the scripts — not what the build resolved. Transitive and
  BOM-managed dependencies are outside the count on both.
- **Because:** the count is Decision 4's honesty signal (ADR-032), and
  the only exact source for Gradle would be evaluating the build — which
  the index step already did, but whose resolution scip-java does not
  report back.
- **Bites at:** the `environment gap` line for Gradle repos, which can
  under-report what was declared (a dependency spelled through a
  variable) and never over-reports what resolved.
- **You find out:** **surfaced** — the counts print on every ingest; a
  unit with nothing readable prints `declared 0`, which is the honest
  form of "not measured".
- **Provider (P9):** none — this is Hobbes's own reading.
- **Source:** ADR-096, decision 4.

### C-101 — A Java build with Kotlin (Scala, Groovy) sources failed its resolve pass, and the unit fell to lane A — *registered and lifted 2026-09-10, the same session*
- **Was:** ADR-097's resolve stage held "every non-source file" under
  the build root, where *source* meant `.java`. A Maven build with
  `src/main/kotlin/` ran `kotlin-maven-plugin` over the `.kt` files on
  that stage, which reference the Java classes that were not there —
  `Unresolved reference` × 20, `BUILD FAILURE` — so the resolve pass
  failed, the index pass then ran offline against a Maven wrapper that
  had to download, and the unit degraded to lane A's syntactic tier
  (spring-data-elasticsearch: 16,050 semantic edges → 3,871 syntactic,
  every one confirmed, 12,179 not drawn). **Surfaced** as it happened: the
  scip-java degradation record named the failed resolve and the offline
  failure. The cell had been graded 2026-08-29, before ADR-097, and never
  re-ingested under the two passes; the 0.1.7-beta baseline regrade
  (Max, 2026-09-10) was its first.
- **And a second half, found once the first was fixed:** the index
  pass then failed alone. scip-java runs the repo's own `mvnw` when the
  build root has one, and the takari wrapper (0.5.6 here) downloads its
  Maven distribution on first use — offline, so it failed at
  `DefaultDownloader.download`. The resolve pass ran the image's `mvn`,
  which never fetched the wrapper's distribution into the cache.
  spring-petclinic (wrapper 3.3.4, the same 3.9.16 distribution) passed
  its 2026-09-01 re-ingest only because its distribution was already in
  the cache from the single-pass days: on a fresh cache every
  wrapper-shipping Maven repo would have degraded the same way.
- **Lifted by:** `_JVM_SOURCE_SUFFIXES` — `.java`, `.kt`, `.scala`,
  `.groovy` never enter the resolve stage; under `buildSrc/` they are the
  build (Gradle's convention plugins) and stay. And the resolve pass
  runs `./mvnw` when the stage has one (`java_resolve_command(...,
  wrapper=True)`), so the wrapper's distribution lands in the cache the
  index pass reads offline — the Gradle arm already did — and
  `MAVEN_USER_HOME` points both wrappers at the cache root's home (the
  Java wrapper otherwise uses the JVM's `user.home`, the passwd entry,
  not `$HOME`: the first `./mvnw` resolve pass fetched the distribution
  into the container's throwaway layer and the offline pass fetched
  again). Tests in
  `TestJavaUnits` and `test_java_resolve_commands_and_offline_flags`.
  Reproduced by hand first: the full archive builds in the image (`BUILD
  SUCCESS`); the archive minus `.java` fails in the Kotlin compile.
  spring-data-elasticsearch regraded at 0.1.8-beta: the cell record's
  2026-09-10 block.
- **Residual:** a build that compiles another language under a directory
  the rule does not know (a Gradle included build under `build-logic/`
  with Kotlin plugins) loses those files from the resolve stage and its
  resolve pass fails visibly, degrading the unit as before — registered
  here, not silent. ADR-097 amended.
- **Source:** the 0.1.7-beta baseline regrade, 2026-09-10.
