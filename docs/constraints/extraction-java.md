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
  the other non-source files under the build root and **no `.java`**.
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
  that it is the only one and that its stage carries no sources; the
  canary (`tests/fixtures/canary-java`) proves no pass saw sources and
  network together.
- **Provider (P9):** inherited from `scip-java` **0.13.1** and the
  build tools it drives (Maven **3.9.16** in the image; the repo's own
  Gradle wrapper). The next narrowing is an allowlisted egress proxy on
  an internal podman network (measured feasible, ADR-097; W1), which
  would confine the residual to the registry hosts.
- **Source:** ADR-096 decision 3, as amended by ADR-097.

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
  `docs/oracle-misses.md`).
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
- **Source:** ADR-096; `docs/java-build-plan.md` §0.3; the O8 cells.

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
