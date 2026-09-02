# ADR-097 — Java phase separation, cut the other way: resolve without sources, index without a network

**Date:** 2026-09-01 · **Status:** accepted — built, canary-tested, and re-run on two of the four Java cells this session · **Owner:** Max · **Source:** the C-66 ratification ADR-096 left open ("ratify or reverse"); Max chose the third option this ADR records ("your recommendation is good. good to proceed")

Amends **ADR-096 decision 3** and **ADR-092 §4** (network by phase
separation). Narrows **C-66** (`docs/constraints/extraction-java.md`).
Architecture **§3.2** amended in the same commit.

## Context

ADR-096 left one decision open: `index-java` was the only lane B step
that executed repo-authored code *and* kept a network, because scip-java
rides the repo's own build and the build is where the classpath gets
resolved. The ADR recorded phase separation as having "no Java form",
on two measurements: `mvn dependency:go-offline` does not reproduce a
real build's resolution (jsoup: a build extension's property, three
test-scoped artifacts), and Gradle has no fetch that does not evaluate
`build.gradle`. Reversing to `--network none` would have cost Gradle
repos lane B outright and most Maven repos on a cold cache.

Both measurements are right and the conclusion was too quick. The
question was framed as *find a fetch that runs no repo code*. There is
another cut: **run the repo's own resolution, but on a stage that holds
no sources.** Measured 2026-09-01, inside the image, on the two cells
ADR-096 built first:

| repo | pass 1 — no `.java` on the stage, network | pass 2 — full stage, `--network none`, offline flag, scip-java | wall |
|---|---|---|---|
| jsoup (Maven) | `mvn --batch-mode -DskipTests clean test-compile` into a fresh `m2`: **BUILD SUCCESS**, 149 jars | `mvn -o … test-compile` under `scip-java index`: **BUILD SUCCESS**, 197 shards | 17 s + 10 s (ADR-096's single cold pass: 37 s) |
| spring-petclinic (Gradle 9.5.1 wrapper, toolchain 17) | `./gradlew --init-script hobbes-resolve.gradle hobbesResolveAll` into a fresh `GRADLE_USER_HOME`: 24 configurations resolved | `./gradlew --offline clean compileTestJava` under `scip-java index`: **BUILD SUCCESSFUL** | 52 s + 12 s |

Why it works, per tool. **Maven** resolves a mojo's declared dependency
scope *before* running it (`requiresDependencyResolution`), so
`test-compile` over a tree with nothing to compile still fetches exactly
the set the real `test-compile` needs — including the extension-supplied
classifier and the test-scoped artifacts `go-offline` missed, because it
is the same resolution, not a reimplementation of it. **Gradle** resolves
lazily, so a source-less `compileTestJava` is `NO-SOURCE` and fetches
nothing; a Hobbes init script registers one task that resolves every
resolvable configuration of every project — a superset of what
`compileTestJava` resolves — and the wrapper downloads its distribution
in the same pass. scip-java's own additions (the semanticdb javac plugin
for Maven, its init script for Gradle) needed nothing from the network in
pass 2 on either repo: the launcher carries them.

Also measured, for the follow-up this ADR does *not* take: rootless
podman 5.8 (netavark + pasta) gives an `--internal` network no egress,
no DNS and no route to the host, while containers on it reach each
other; a container attached to that network *and* a custom egress
bridge reaches out; a CONNECT proxy on such a container served an
allowlisted host (200) and refused another (403) to a client that had
the internal network only. Attaching to the default `podman` bridge
instead of a custom one breaks DNS. So an allowlisted egress proxy is
buildable in this podman; it is recorded in `workstreams.md` W1 as the
next narrowing, not built here.

## Decision

1. **Two contained passes per Java unit.** `fetch-java`
   (`executes_repo_code=True`, `network="default"`): the build files and
   every other non-source file under the build root — `java_build_files`,
   which by construction never lists a `.java` — staged alone, and the
   build's own resolution run over them (`containment.java_resolve_command`:
   Maven's `test-compile`; the Gradle wrapper with
   `containment.GRADLE_RESOLVE_SCRIPT` and its `hobbesResolveAll` task,
   passed by `--init-script` so it never rides into the index pass).
   `index-java` (`executes_repo_code=True`, `network="none"`): the full
   stage, the same build with scip-java attached and the tool's offline
   flag (`-o` / `--offline`, spelled in `scip/index.mjs`), so a build that
   still wants the network fails visibly rather than reaching for one.
   The suite pins: every index step has no network; `fetch-java` is the
   only executing step with one; its stage holds no sources.
2. **A failed resolve is recorded, not fatal.** The index pass runs
   anyway — the caches persist across ingests — and if the build then
   fails, the unit degrades to lane A with both records in one message
   (the `_fetch` shape ADR-092 gave Go and Rust). The refusal type is not
   caught by `_fetch`: `fetch-java` executes repo code, so on a box
   without containment it refuses like an index step (P10).
3. **The property, stated:** *the pass that can reach the network never
   sees a source file; the pass that sees the sources has no route out.*
   What `fetch-java` still concedes is the narrowed C-66: repo build
   logic runs with a network over the build files it came from, the
   resources beside them, and the public artifact caches under the Hobbes
   cache root. Not the sources, not the host, not the user's `~/.m2`.
4. **The canary carries the property.** `tests/fixtures/canary-java`
   gains a fourth probe bound to `generate-sources`: if the step can see
   `Canary.java` *and* reach Maven Central in the same pass, it generates
   `Phoned.java`. The `lane_b` test asserts `Phoned#` is never indexed,
   the ledger reads `[fetch-java, index-java]` both contained, and the
   three ADR-096 probes still hold. The positive control (sources and
   network in one container) writes `Phoned.java`; measured by hand
   2026-09-01, so the negative means what it says.
5. **Declined, and why.** (a) Reversing to `network="none"` alone: loses
   Gradle lane B and cold-cache Maven, for a property this ADR reaches
   without the loss. (b) A source-less pass that also runs *no* repo
   code (a Hobbes-owned resolver over the poms): Gradle declares in code,
   and a pom's extensions supply properties only a run supplies — the
   go-offline lesson again. (c) The egress proxy first: more moving parts
   for a narrower residual; taken second (W1), on the measurements above.
   (d) The oracle lane's `java-build`/`java-javac` steps keep their single
   networked pass for now — bench tooling, not product; their C-66 note
   points here and the same two-pass shape applies when someone needs it.

## Consequences

- **C-66 narrowed**, status surfaced: the `NOTE:` line names the two
  passes; `graph.json`'s `containment` stamp lists `fetch-java` and
  `index-java`; `all_contained` unchanged in meaning.
- **ADR-092 §4 gains a second form** of phase separation: by *what the
  container holds* rather than by *what it runs*. The first form stays
  the stronger one where a tool offers it.
- **Cost:** one more container per Java unit; on jsoup the two passes
  together were faster than the old single cold pass. A build whose
  *configuration* phase needs sources or generated code fails its resolve
  pass and is recorded; on the two repos measured, none did.
- **No change to the graph.** The index pass is the ADR-096 build with an
  offline flag; the re-ingest of jsoup and spring-petclinic is recorded
  in the BUILDLOG entry for this date, tier counts against the 2026-08-29
  artifacts.
