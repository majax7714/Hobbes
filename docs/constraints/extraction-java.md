# Extraction — Java

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-66 — Indexing a Java repo runs its build, in the container, with a network
- **Cannot tell you:** nothing — like C-29 this registers something
  Hobbes *does*: `hobbes ingest` on a Java repo runs that repo's own
  build (`mvn … test-compile`, or its `gradlew compileTestJava`) with
  scip-java's compiler plugin attached, inside the ingest container —
  and, unlike every other index step, **with network access**. A
  Gradle script is code; a pom names the plugins and extensions the
  build runs; either can reach the network while it runs.
- **Because:** scip-java is a javac plugin, and javac needs the
  classpath the build resolves. Neither tool separates resolving from
  evaluating the build: Gradle resolves while running the script, and
  Maven's `dependency:go-offline` does not reproduce the build's own
  resolution (the ADR-096 spike: a property supplied by a build
  extension). ADR-092's phase separation — a fetch container that runs
  no repo code, an index container with no network — has no Java form.
  What is kept: the container is rootless, the Hobbes cache root is its
  only writable mount, the helper and the stage are otherwise read-only,
  and the build never runs on the host (C-64 applies: the step refuses
  without the image).
- **Bites at:** security posture. An untrusted Java repo's build logic
  can exfiltrate what the container can see — the staged copy of the
  repo, the Hobbes cache (other repos' stages are removed after use;
  the Maven/Gradle caches persist) — over the network while indexing.
  Not the host, not the user's repo, not the user's `~/.m2`.
- **You find out:** **surfaced** — a `NOTE:` line on stderr every time
  the Java lane runs, naming the network; `graph.json`'s `containment`
  stamp lists the `index-java` step; `containment.PROFILES["index-java"]`
  is the one profile with `executes_repo_code` *and* `network="default"`,
  and the suite pins that it is the only one.
- **Provider (P9):** inherited from `scip-java` **0.13.1** and the
  build tools it drives (Maven **3.9.16** in the image; the repo's own
  Gradle wrapper). Egress narrowing (C-41's shape) or a registry mirror
  would soften this entry without Hobbes changing its rule.
- **Source:** ADR-096, decision 3 — flagged for Max's ratification.

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
  projects (scip-java dropped them at 0.13).
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
  below the floor. A named class waits on J.M4's oracle cells sizing
  it.
- **Source:** ADR-096; `docs/java-build-plan.md` §0.3.

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
