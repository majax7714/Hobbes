#!/usr/bin/env node
/**
 * Lane B's helper (architecture §3.2, ADR-027).
 *
 * Runs a SCIP indexer over a staging tree, decodes the index, filters it
 * down to what a graph can use, and emits facts JSON for the Python join.
 * Hobbes writes no provider adapters — it runs indexers and consumes their
 * output — so everything here is transport, filtering, and honesty about
 * degradation.
 *
 * Three ADR-027 decisions are implemented here rather than described:
 *
 * - **Decision 1** — `--project-version` is always passed explicitly. Its
 *   default is the git revision, which would put a new version inside every
 *   moniker on every commit.
 * - **Decision 3** — only namespace/type/method/term descriptors become
 *   graph material; parameters, locals and meta are ~86% of definitions and
 *   are dropped here, before the process boundary, not in Python.
 * - **Decision 4** — a zero exit is not a successful index, so degradation
 *   is computed from the index's own contents and reported.
 *
 * Usage:  node index.mjs --config <path-to-json>
 * Config: {stage, language, projectName, projectVersion, declaredDeps[]}
 * Output: facts JSON on stdout; diagnostics on stderr.
 */
import { spawnSync } from 'node:child_process'
import { closeSync, existsSync, mkdirSync, openSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync, writeSync } from 'node:fs'
import { availableParallelism } from 'node:os'
import { dirname, join, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

import pkg from '@sourcegraph/scip-typescript/dist/src/scip.js'
import pb from 'google-protobuf'

const { scip } = pkg
const HERE = dirname(fileURLToPath(import.meta.url))

/** Facts schema version; the Python join refuses anything else.
 *
 * v2 (V2.M3, ADR-032): facts carry `dependency_coverage` on every run,
 * replacing Decision 4's all-or-nothing degradation test.
 * v4 (ADR-116): the facts are a file of JSON lines — a header, one record
 * per document, a trailer with the counts — written where the config's
 * `facts` names, never one document on stdout. */
export const HELPER_VERSION = 5

/** The helper's exit code when the indexer it drove exited non-zero: the
 * helper ran, the indexer did not. The Python side records that as the
 * indexer's failure, not as a missing helper (C-85, C-74). */
export const INDEXER_EXIT = 3

/** What the process exits with for a thrown *err*. */
export function exitCodeFor(err) {
  return err && err.indexerExit !== undefined ? INDEXER_EXIT : 1
}

/** Indexers we know how to drive, keyed by the language they own. */
export const INDEXERS = {
  python: {
    bin: 'scip-python',
    args: (c) => [
      'index',
      '--cwd', c.stage,
      '--project-name', c.projectName,
      // Decision 1: never let this default to the git revision.
      '--project-version', c.projectVersion,
      '--output', c.output,
      '--quiet',
      // Package attribution (C-27). Without this, scip-python asks the
      // first `pip3` on PATH which environment is installed — the system
      // one, not the repo's venv (a uv venv has no pip at all), so every
      // third-party reference is attributed to the *local* project and
      // the dependency simply vanishes. The Python side pre-computes the
      // listing from the venv's own interpreter via importlib.metadata.
      ...(c.environment ? ['--environment', c.environment] : []),
    ],
  },
  typescript: {
    bin: 'scip-typescript',
    // `projects`: tsconfig paths to index instead of the cwd's — a
    // solution-style zone's referenced projects plus the generated
    // config for the files none of them claims (C-98). Absolute, so
    // scip-typescript's `-p` resolution never depends on its cwd;
    // document paths stay relative to `--cwd`, so the Python rebase
    // (`_rebase`) is unchanged.
    args: (c) => ['index', '--cwd', c.stage, '--output', c.output, '--no-progress-bar', ...(c.projects ?? [])],
  },
  go: {
    bin: 'scip-go',
    // Not an npm package: a Go binary, pinned by the version installed.
    onPath: true,
    install: 'go install github.com/scip-code/scip-go/cmd/scip-go@v0.2.7',
    // scip-go has no --cwd; it indexes the module rooted at --module-root.
    args: (c) => [
      'index',
      '--module-root', c.stage,
      '--output', c.output,
      // Decision 1 again, under a third flag name: this defaults to the
      // git revision, so every node id would change on every commit
      // (ADR-037). Two indexers made the same choice; assume the next
      // one does too.
      '--module-version', c.projectVersion,
      '--quiet',
    ],
    // scip-go runs the real Go loader, whose cwd must be inside the module.
    cwd: (c) => c.stage,
  },
  rust: {
    // rust-analyzer's native SCIP export (ADR-040) — not a scip-* wrapper,
    // the analyzer itself. Installed as a rustup component, pinned by the
    // toolchain the user has.
    bin: 'rust-analyzer',
    onPath: true,
    install: 'rustup component add rust-analyzer',
    // No version flag, and for once none is needed: the moniker version is
    // the crate's Cargo.toml version, not the git revision (measured,
    // spike-rust.mjs) — the first indexer whose default satisfies
    // Decision 1 by itself. ADR-037's "assume the next one does too"
    // was wrong in the safe direction.
    args: (c) => ['scip', c.stage, '--output', c.output],
    // Like scip-go: cargo metadata resolves relative to cwd.
    cwd: (c) => c.stage,
  },
  java: {
    // scip-java (ADR-096): a javac plugin driven through the repo's *own
    // build*, so indexing Java executes the repo's build logic (C-29's
    // Java face) and runs only inside the sandbox image, where the pinned
    // launcher lives (`sandbox/Containerfile`); `install` names that, not
    // a host command. Two routes to one plugin:
    //   Maven — scip-java's own: the launcher writes a wrapping javac and
    //   runs the build with it (`scip-java index --build-tool=maven`).
    //   Gradle — Hobbes's own (C-67): scip-java's Gradle plugin adds the
    //   javac plugin to the `compileOnly` configuration, which a build
    //   that resolves `compileOnly` at evaluation time refuses
    //   (Severed-Chains, one repo in four on the 2026-08-29 draw), so the
    //   helper attaches the same plugin through its own init script on
    //   each JavaCompile task's processor path — the oracle lane's
    //   route, which attached to that build — runs the wrapper, and
    //   aggregates the shards with `scip-java aggregate` (`gradlePlan`).
    // The build command is Hobbes's, not scip-java's default: Maven
    // compiles only — `clean test-compile` — instead of `verify`, which
    // would run every plugin bound to the lifecycle; Gradle runs
    // `clean compileTestJava`. The step runs **offline** (ADR-097): the
    // ingest resolved the build's dependencies first, in a networked
    // pass over a stage that holds no sources
    // (`containment.java_resolve_command`), so this pass has no network
    // and says so to the tool — `-o` / `--offline` — and a build that
    // still wants one fails visibly (C-66, C-67). No version flag exists
    // and none is needed: the moniker version is the artifact's own
    // (`1.24.1-SNAPSHOT` on the spike), never the git revision —
    // Decision 1 satisfied by default, as for Rust.
    bin: 'scip-java',
    onPath: true,
    install: 'build the sandbox image (sandbox/Containerfile pins scip-java)',
    args: (c) => [
      'index',
      `--build-tool=${c.buildTool}`,
      '--output', c.output,
      '--',
      '--batch-mode', '-o', '-DskipTests', 'clean', 'test-compile',
    ],
    cwd: (c) => c.stage,
    plan: (c) => (c.buildTool === 'gradle' ? gradlePlan(c) : null),
  },
  c: {
    // scip-clang (ADR-109): clang's frontend over each translation unit,
    // from a compile database. Where the database comes from is the
    // ingest's call (`compdbSource`): the repo's own, rebased into the
    // scratch build dir by the Python side; CMake's export; or bear over
    // make. The last two run the repo's build logic (C-29's C face), so
    // this runs only in the image, offline, like Java's index pass.
    // `plan` is what runs, and it runs scip-clang once per translation
    // unit (ADR-109 decision 1, amended; C-149), so `args` names the
    // whole-database invocation only for the record.
    bin: 'scip-clang',
    onPath: true,
    install: 'build the sandbox image (sandbox/Containerfile pins scip-clang)',
    args: (c) => [`--compdb-path=${cCompdb(c)}`, `--index-output-path=${c.output}`],
    cwd: (c) => c.stage,
    plan: (c) => cPlan(c),
  },
}

// C++ is C's indexer, exactly (ADR-113 §2): scip-clang is a C++ indexer
// first, and neither the compile database nor its derivation cares what
// language a translation unit is. The `cpp` language exists so the ingest
// can say which roots hold C++ — and so `decodeOptions` can add the one
// rule C++ needs (a constructor over its class).
INDEXERS.cpp = INDEXERS.c

/** Where scip-clang reads the compile database: the rebased copy of the
 * repo's own, or what CMake or bear wrote into the scratch build dir. */
export function cCompdb(c) {
  return c.compdbSource === 'repo' ? c.compdb : join(c.buildDir, 'compile_commands.json')
}

/** Where a root's one-entry compile databases and their indexes go: beside
 * the index a whole-database run used to write, never inside the stage
 * scip-clang reports its documents relative to. */
function cUnitsDir(c) {
  return `${c.output}.units`
}

/** The most translation units a root is indexed one per run (Max,
 * 2026-09-15). A header many units share is in every unit's index:
 * ScummVM's 5,958 units wrote 9.36 GB of unit indexes against 370 MB
 * whole, and took 207 s against 143 s. The merge streams them since
 * ADR-115, so the 84 GB it once projected is gone; what the per-unit
 * route still holds is every one of those repeated references until the
 * per-site rules run at the end of the decode. fmt (52), args (99) and
 * cJSON (23) lie well under the bound. A database over it is indexed in
 * one whole-database run instead, and the record says C-149 applies there;
 * running the per-site rules on arrival is what would lift the bound. */
export const PER_UNIT_MAX = 400

/** The index step's shell: one scip-clang run per one-entry database the
 * check wrote, `$1` their directory and `$2` how many may run at once.
 * `-j 1` because the parallelism is here, one process per unit. `exit 0`
 * because xargs exits 123 when any child failed, and a unit that fails
 * must not stop the others — the merge counts what is missing. When the
 * check wrote `whole.json` instead (a database over `PER_UNIT_MAX`), one
 * scip-clang run indexes it at scip-clang's own parallelism. */
const PER_UNIT_INDEX =
  'if [ -f "$1/whole.json" ]; then ' +
  'scip-clang --compdb-path="$1/whole.json" --index-output-path="$1/whole.scip"; exit 0; fi; ' +
  'ls "$1" | sed -n \'s/\\.json$//p\' | ' +
  'xargs -P "$2" -I@ scip-clang -j 1 --compdb-path="$1/@.json" --index-output-path="$1/@.scip"; ' +
  'exit 0'

/** One one-entry compile database per entry of *entries*, named by the
 * entry's zero-padded position in the database, so the units decode in
 * database order whatever order they were indexed in (ADR-109). The entry
 * is copied verbatim: it is the build's own record of how that translation
 * unit compiles, and rewriting any of it would index something else. */
export function splitCompdb(entries) {
  return entries.map((entry, i) => ({ name: String(i).padStart(4, '0'), entry }))
}

/** A check hook that writes *compdb* out as one-entry databases under
 * *unitsDir*, replacing whatever a previous run left there. It runs after
 * C-135's check, on the whole database, and before any indexing. A
 * database over `PER_UNIT_MAX` is written whole, as `whole.json`, for one
 * whole-database run. */
function splitStep(compdb, unitsDir) {
  return () => {
    const entries = JSON.parse(readFileSync(compdb, 'utf8'))
    rmSync(unitsDir, { recursive: true, force: true })
    mkdirSync(unitsDir, { recursive: true })
    if (entries.length > PER_UNIT_MAX) {
      writeFileSync(join(unitsDir, 'whole.json'), JSON.stringify(entries))
      return
    }
    for (const { name, entry } of splitCompdb(entries)) {
      writeFileSync(join(unitsDir, `${name}.json`), JSON.stringify([entry]))
    }
  }
}

/** The steps for one C build root (ADR-109): derive the compile database,
 * unless the repo carries one, then index.
 *
 * `make -k` keeps going past a target that fails (a link error, a tool the
 * image lacks), and bear records every compile it saw. So the build's own
 * exit decides nothing; the database having entries, and one of them under
 * the root, does (C-135), checked before scip-clang runs.
 *
 * The index step then runs **one translation unit per scip-clang run**
 * (ADR-109 decision 1, amended; C-149). A whole-database run indexes a
 * header many units share once, in whichever unit claims it first, and
 * that varies by run: three cJSON ingests at one commit drew 2,630, 2,615
 * and 2,621 edges. Run per unit and every unit indexes its own headers, so
 * the concatenation the decode reads is the same every time — the decode
 * itself is already order-independent (ADR-113 §2). Measured on fmt (52
 * units): 9–10 s at 6 in parallel against 8 s for one run. So the check
 * on the step that first reads the database also splits it, and the step
 * is a shell driving scip-clang over the pieces, at most
 * `availableParallelism()` at a time; `indexStage` decodes them as one. */
export function cPlan(c) {
  const compdb = cCompdb(c)
  const unitsDir = cUnitsDir(c)
  const split = splitStep(compdb, unitsDir)
  const index = {
    bin: 'sh', onPath: true, install: 'a POSIX shell (the image has one)', cwd: c.stage,
    args: ['-c', PER_UNIT_INDEX, 'sh', unitsDir, String(availableParallelism())],
  }
  // Both hooks on one step: C-135 judges the whole database, then it is
  // split. A database the check refuses is never split.
  const before = (check) => (previous) => {
    if (check) check(previous)
    split(previous)
  }
  if (c.compdbSource === 'repo') {
    return { steps: [{ ...index, check: before(null) }], unitsDir }
  }
  if (c.compdbSource === 'cmake') {
    return {
      steps: [
        {
          bin: 'cmake', onPath: true, install: INDEXERS.c.install, cwd: c.stage,
          args: ['-S', c.stage, '-B', c.buildDir, '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'],
        },
        { ...index, check: before(compdbCheck(compdb, 'CMake', c.stage)) },
      ],
      unitsDir,
    }
  }
  if (c.compdbSource === 'make') {
    return {
      steps: [
        {
          bin: 'sh', onPath: true, install: 'a POSIX shell (the image has one)', cwd: c.stage,
          args: ['-c', 'bear --output "$1" -- make -k; exit 0', 'sh', compdb],
        },
        { ...index, check: before(compdbCheck(compdb, 'bear over make', c.stage)) },
      ],
      unitsDir,
    }
  }
  throw new Error(`no compile database source for this C build root: ${c.compdbSource}`)
}

/** The longest common directory of *paths* (absolute, `path.dirname`
 * steps); the filesystem root when they share nothing below it. Where
 * C-135's message says a database's outside entries lie, when they are
 * not all under cargo's registry. */
function commonOutsideDirectory(paths) {
  let common = dirname(paths[0]).split(sep)
  for (const p of paths.slice(1)) {
    const parts = dirname(p).split(sep)
    let i = 0
    while (i < common.length && i < parts.length && common[i] === parts[i]) i++
    common = common.slice(0, i)
  }
  return common.join(sep) || sep
}

/** C-135: a compile database that has entries but none of a file under
 * the build root leaves scip-clang nothing of the root's own to index,
 * so it stops the plan first, naming where the recorded compiles do lie
 * (cargo's registry, or their common directory) and the build's own
 * words, as the empty-database case already does. */
function compdbCheck(compdb, what, stage) {
  return (previous) => {
    let entries = []
    try {
      entries = JSON.parse(readFileSync(compdb, 'utf8'))
    } catch {
      entries = []
    }
    if (!Array.isArray(entries) || entries.length === 0) {
      const said = String(previous?.stderr || previous?.stdout || '').trim().slice(-600)
      throw buildRefusal(`${what} produced no compile database entries, so scip-clang has nothing to index: ${said}`)
    }
    const root = resolve(stage)
    const outside = entries
      .map((e) => resolve(e.directory, e.file))
      .filter((path) => path !== root && !path.startsWith(root + sep))
    if (outside.length === entries.length) {
      const cargoHome = process.env.CARGO_HOME && resolve(process.env.CARGO_HOME, 'registry') + sep
      const where = cargoHome && outside.every((path) => path.startsWith(cargoHome))
        ? "cargo's registry (the dependencies' own C)"
        : commonOutsideDirectory(outside)
      const said = String(previous?.stderr || previous?.stdout || '').trim().slice(-200)
      const tail = said ? `: ${said}` : ''
      throw buildRefusal(
        `${what} recorded ${entries.length} compile(s), none of a file under this root — all under ${where}; ` +
        `the build compiled none of the root's own C (C-135)${tail}`,
      )
    }
  }
}

/** A refusal the compile-database check raises is the build's outcome,
 * not a helper that could not run: it carries `indexerExit`, so the
 * helper exits `INDEXER_EXIT` and the Python side reports the C build's
 * own words rather than "install Node and run npm install". */
function buildRefusal(message) {
  const err = new Error(message)
  err.indexerExit = 1
  return err
}

/** scip-java's javac plugin and the JVM flags it needs, extracted from
 * the pinned launcher at image build (`sandbox/Containerfile`): the one
 * provider, one version, read from one file (P13). */
export const SCIP_JAVAC_JAR = '/usr/local/lib/scip-java/scip-javac.jar'
export const SCIP_JAVAC_INTERNALS = '/usr/local/lib/scip-java/javac-internals.properties'

/** The `--add-exports` flags the plugin needs to reach javac's internals
 * on Java 9+, read from the file scip-java ships beside it
 * (`javac-internals.properties`: one property, `javac.jvmOptions`, a
 * comma-separated list continued across lines with `\`) — so a launcher
 * bump carries its own list and Hobbes spells none. */
export function javacInternals(text) {
  const line = text.replace(/\\\r?\n/g, '').split(/\r?\n/).find((l) => l.startsWith('javac.jvmOptions='))
  if (!line) throw new Error(`${SCIP_JAVAC_INTERNALS}: no javac.jvmOptions property`)
  return line.slice('javac.jvmOptions='.length).split(',').map((s) => s.trim()).filter(Boolean)
}

/** The Gradle init script that attaches scip-java's javac plugin to every
 * JavaCompile task of every project: on the task's own processor path
 * (a task property, set at configuration — never a dependency added to a
 * configuration, which is what scip-java's plugin does and what a build
 * that has already resolved `compileOnly` refuses), forked with the
 * plugin's `--add-exports`, incremental off (the plugin must see every
 * unit), `-Xplugin:scip` with the stage as sourceroot so the shards'
 * paths are stage-relative exactly as scip-java's own route wrote them.
 * A build that *replaces* `compilerArgs` after this would drop the
 * plugin; the empty targetroot is then the visible failure (`gradlePlan`). */
export function gradleAttachScript({ stage, targetroot, jar, jvmArgs }) {
  const q = (v) => `'${String(v).replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`
  return [
    "// Hobbes (C-67): attach scip-java's javac plugin to every JavaCompile",
    '// task on the task\'s processor path, the way the oracle lane attaches',
    '// its own — never through a configuration. Written by the ingest for',
    '// this one build, not by the repo.',
    'allprojects {',
    '  tasks.withType(JavaCompile).configureEach {',
    `    def jar = files(${q(jar)})`,
    '    options.fork = true',
    `    options.forkOptions.jvmArgs += [${jvmArgs.map(q).join(', ')}]`,
    '    options.incremental = false',
    `    options.compilerArgs += [${q(`-Xplugin:scip -sourceroot:${stage} -targetroot:${targetroot}`)}]`,
    '    options.annotationProcessorPath = jar + (options.annotationProcessorPath ?: files())',
    '  }',
    "  // What the build resolved, in scip-java's own dependencies.txt shape",
    '  // (group, artifact, version, jar — tab-separated), appended per',
    '  // project: the dependency-coverage line reads it, since the',
    '  // aggregator names no third-party package on its own (`gradlePlan`).',
    `  tasks.register(${q(DEPENDENCIES_TASK)}) {`,
    '    doLast {',
    `      def out = new File(${q(targetroot)}, ${q(DEPENDENCIES_FILE)})`,
    '      out.parentFile.mkdirs()',
    '      configurations.matching { it.canBeResolved }.each { c ->',
    '        try {',
    '          c.resolvedConfiguration.lenientConfiguration.artifacts.each { a ->',
    '            def id = a.moduleVersion.id',
    '            out << "${id.group}\\t${id.name}\\t${id.version}\\t${a.file}\\n"',
    '          }',
    '        } catch (Exception e) {',
    '          println("hobbes: could not list ${project.path}:${c.name}: ${e.message?.take(160)}")',
    '        }',
    '      }',
    '    }',
    '  }',
    '}',
    '',
  ].join('\n')
}

/** The init script's task that lists what the build resolved, and the
 * file it writes under the targetroot. */
export const DEPENDENCIES_TASK = 'hobbesScipDependencies'
export const DEPENDENCIES_FILE = 'dependencies.txt'

/** The packages a dependencies.txt names, as the helper keys them
 * (`maven:maven/<group>/<artifact>`), deduplicated; an absent file is no
 * packages. The SCIP index cannot carry them under this route: the
 * aggregator maps a class to its jar only through the table scip-java's
 * own `index` command builds, which `aggregate` does not take — so the
 * external symbols read package `.` and the coverage line is answered
 * from the build's own resolution instead, which is what the line asks
 * (C-23: is the environment there?). */
export function resolvedPackages(text) {
  const out = new Set()
  for (const line of String(text ?? '').split(/\r?\n/)) {
    const [group, artifact] = line.split('\t')
    if (group && artifact) out.add(`maven:maven/${group}/${artifact}`)
  }
  return [...out].sort()
}

/** The Gradle index route as steps (`runIndexer`): write the init script
 * beside the output, run the repo's wrapper offline under it, then
 * aggregate the per-source shards into the one index. Nothing of it
 * outlives the run: the script and the targetroot are removed with the
 * index file (ADR-027 clause 6). */
export function gradlePlan(c) {
  const script = `${c.output}.hobbes-scip.gradle`
  const targetroot = `${c.output}.targetroot`
  const install = 'build the sandbox image (sandbox/Containerfile pins scip-java and extracts its javac plugin)'
  return {
    prepare: () => {
      if (!existsSync(SCIP_JAVAC_JAR) || !existsSync(SCIP_JAVAC_INTERNALS)) {
        throw new Error(`${SCIP_JAVAC_JAR} is not in this image — rebuild the sandbox image (C-65): ${install}`)
      }
      rmSync(targetroot, { recursive: true, force: true })
      writeFileSync(
        script,
        gradleAttachScript({
          stage: c.stage, targetroot, jar: SCIP_JAVAC_JAR,
          jvmArgs: javacInternals(readFileSync(SCIP_JAVAC_INTERNALS, 'utf8')),
        }),
      )
    },
    steps: [
      {
        bin: 'sh', onPath: true, install: 'a POSIX shell (the image has one)', cwd: c.stage,
        args: ['./gradlew', '--no-daemon', '--offline', '--init-script', script, 'clean', 'compileTestJava', DEPENDENCIES_TASK],
      },
      {
        // The build finished but the plugin wrote nothing: it was not on
        // any JavaCompile task (a build that replaces compilerArgs after
        // configuration, or no Java source set at all). Said before the
        // aggregator's own "no documents" would, with the cause and the
        // build's own last words.
        check: (previous) => {
          if (!shardsUnder(targetroot)) {
            const said = String(previous?.stdout || '').trim().slice(-600)
            throw new Error(
              `the Gradle build succeeded but scip-java's plugin wrote no SCIP shard under ${targetroot}: ` +
              'the plugin was not attached to any JavaCompile task (the build replaces ' +
              'JavaCompile.options.compilerArgs after configuration, or compiles no Java); ' +
              `the build said: ${said}`,
            )
          }
        },
        bin: 'scip-java', onPath: true, install, cwd: c.stage,
        args: ['aggregate', '--output', c.output, '--targetroot', targetroot],
      },
    ],
    // Read before cleanup: what the build resolved, for the coverage line.
    resolved: () => {
      const f = join(targetroot, DEPENDENCIES_FILE)
      return existsSync(f) ? resolvedPackages(readFileSync(f, 'utf8')) : []
    },
    cleanup: () => {
      rmSync(script, { force: true })
      rmSync(targetroot, { recursive: true, force: true })
    },
  }
}

/** Whether any `.scip` file sits under *dir* (the plugin writes one per
 * compilation unit, in a tree that mirrors the sources). */
function shardsUnder(dir) {
  if (!existsSync(dir)) return false
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory() ? shardsUnder(p) : name.endsWith('.scip')) return true
  }
  return false
}

/**
 * A root's index, read as a stream of documents (ADR-115).
 *
 * `scip.Index.deserialize` builds the whole index as generated message
 * objects — an Occurrence object, its wrapper arrays and a fresh copy of
 * its symbol string for every one of a root's occurrences — and ScummVM's
 * 387 MB index (7.9 million occurrences) needed 8.95 GB of heap that way,
 * twice Node's default, so the root had no lane B (C-150). Nothing in the
 * decode needs the index at once: it reads one document's occurrences,
 * keeps the few fields it keys on, and moves on. So the wire format is
 * walked here directly — `Index.documents` is field 2, one
 * length-delimited message per document — and a document is materialised
 * only while `decode` is looking at it. The same file streamed this way
 * peaks at 1.4 GB, most of it the references kept.
 *
 * The fields read are the ones `decode` uses: `Document.relative_path`
 * (1), `occurrences` (2) and `symbols` (3); of an `Occurrence`, `range`
 * (1), `symbol` (2) and `symbol_roles` (3); of a `SymbolInformation`,
 * `symbol` (1) and `relationships` (4), and of a `Relationship` its
 * `symbol` (1) and `is_implementation` (3) — the override set (ADR-120). scip-java 0.13 writes an occurrence's
 * position as SCIP's *typed* range (`single_line_range` = field 8,
 * `multi_line_range` = field 9, the `scip-code/scip` proto at a7b9c65a,
 * 2026-08-25) and leaves the deprecated `repeated int32 range` empty; the
 * generated reader this helper used to borrow knew neither field, which
 * read every Java occurrence as unplaced (the J.M0 spike: 104,453 of
 * 104,453 empty). Both typed forms are folded into `range`'s
 * `[startLine, startChar, endLine, endChar]` shape here, and a typed
 * range wins over a deprecated one, as the proto says.
 */
const WIRE_VARINT = 0 // protobuf's wire type for one unpacked int

const readInts = (reader, spec) => {
  const out = {}
  reader.readMessage(undefined, () => {
    while (reader.nextField()) {
      if (reader.isEndGroup()) break
      const name = spec[reader.getFieldNumber()]
      if (name) out[name] = reader.readInt32()
      else reader.skipField()
    }
  })
  return out
}

function readOccurrence(reader) {
  const occ = { range: [], symbol: '', symbol_roles: 0 }
  let typed = null
  reader.readMessage(undefined, () => {
    while (reader.nextField()) {
      if (reader.isEndGroup()) break
      switch (reader.getFieldNumber()) {
        case 1:
          // Packed in every index met so far (proto3's default); an unpacked
          // writer sends one varint per element, and is read the same.
          if (reader.getWireType() === WIRE_VARINT) occ.range.push(reader.readInt32())
          else occ.range = reader.readPackedInt32()
          break
        case 2:
          occ.symbol = reader.readString()
          break
        case 3:
          occ.symbol_roles = reader.readInt32()
          break
        case 8: {
          const r = readInts(reader, { 1: 'line', 2: 'start', 3: 'end' })
          typed = [r.line ?? 0, r.start ?? 0, r.end ?? 0]
          break
        }
        case 9: {
          const r = readInts(reader, { 1: 'startLine', 2: 'start', 3: 'endLine', 4: 'end' })
          typed = [r.startLine ?? 0, r.start ?? 0, r.endLine ?? 0, r.end ?? 0]
          break
        }
        default:
          reader.skipField()
      }
    }
  })
  if (typed) occ.range = typed
  return occ
}

/** One `Relationship`'s target symbol when it says `is_implementation`,
 * else ''. The other flags (`is_reference`, `is_type_definition`,
 * `is_definition`) are search hints for an editor and nothing here reads
 * them (ADR-120). */
function readImplementation(reader) {
  let symbol = ''
  let implementation = false
  reader.readMessage(undefined, () => {
    while (reader.nextField()) {
      if (reader.isEndGroup()) break
      switch (reader.getFieldNumber()) {
        case 1:
          symbol = reader.readString()
          break
        case 3:
          implementation = reader.readBool()
          break
        default:
          reader.skipField()
      }
    }
  })
  return implementation ? symbol : ''
}

/** A `SymbolInformation` reduced to what the decode keeps: the symbol and
 * the symbols it implements (`relationships[].is_implementation`). Every
 * other field — documentation, kind, display name, signature — is skipped
 * unread, so a document's symbol table costs the decode nothing but its
 * override pairs (ScummVM: 411,173 symbol informations, 49,912 pairs). */
function readSymbolInformation(reader) {
  const info = { symbol: '', implements: [] }
  reader.readMessage(undefined, () => {
    while (reader.nextField()) {
      if (reader.isEndGroup()) break
      switch (reader.getFieldNumber()) {
        case 1:
          info.symbol = reader.readString()
          break
        case 4: {
          const target = readImplementation(reader)
          if (target) info.implements.push(target)
          break
        }
        default:
          reader.skipField()
      }
    }
  })
  return info
}

function readDocument(reader) {
  const doc = { relative_path: '', occurrences: [], symbols: [] }
  reader.readMessage(undefined, () => {
    while (reader.nextField()) {
      if (reader.isEndGroup()) break
      switch (reader.getFieldNumber()) {
        case 1:
          doc.relative_path = reader.readString()
          break
        case 2:
          doc.occurrences.push(readOccurrence(reader))
          break
        case 3: {
          const info = readSymbolInformation(reader)
          // Only a symbol that implements something is kept: that is the
          // one thing the table carries which an occurrence does not.
          if (info.implements.length) doc.symbols.push(info)
          break
        }
        default:
          reader.skipField()
      }
    }
  })
  return doc
}

/** Every document of the SCIP index in *bytes*, one at a time, in the
 * order the indexer wrote them. Nothing else of the index is kept. */
export function* streamDocuments(bytes) {
  const reader = new pb.BinaryReader(bytes)
  while (reader.nextField()) {
    if (reader.isEndGroup()) break
    if (reader.getFieldNumber() === 2) yield readDocument(reader)
    else reader.skipField()
  }
}

/** Whether *bytes* parse as a SCIP index at the top level: every field
 * skips cleanly to the end, and there is at least one. Cheap — a document
 * is one length-delimited field, so this jumps over each rather than
 * reading it — and it is how a unit's output is told from a scip-clang
 * run that wrote nothing usable. */
export function wellFormedIndex(bytes) {
  try {
    const reader = new pb.BinaryReader(bytes)
    let fields = 0
    while (reader.nextField()) {
      if (reader.isEndGroup()) return false
      reader.skipField()
      fields += 1
    }
    return fields > 0
  } catch {
    return false
  }
}

/** An index source over the `.scip` files at *paths*: `documents()`
 * streams every document of every file, in path order, holding one
 * file's bytes at a time; `count` is how many documents the last walk
 * yielded. This is the shape `decode` and `degradations` read, beside
 * the literal `{documents: [...]}` the tests build. */
export function indexFiles(paths) {
  const source = {
    count: 0,
    *documents() {
      source.count = 0
      for (const path of paths) {
        const bytes = readFileSync(path)
        for (const doc of streamDocuments(bytes)) {
          source.count += 1
          yield doc
        }
      }
    },
  }
  return source
}

/** The documents of *index*, whichever shape it has: a streamed source
 * (`documents` is a generator function) is walked afresh each call; a
 * literal index is its array. */
export function documentsOf(index) {
  return typeof index.documents === 'function' ? index.documents() : index.documents
}

/** How many documents *index* holds — for a streamed source, as of its
 * last walk. */
export function documentCount(index) {
  return typeof index.documents === 'function' ? index.count : index.documents.length
}

/**
 * Is this document a file of the repo we indexed?
 *
 * `relative_path` is the indexer's word, not a fact. scip-go emits
 * documents for the Go build cache — real paths like
 * `../../.cache/go-build/f1/f12bb…-d` — and a join that trusts them
 * attributes occurrences to files the user has never seen, inventing
 * nodes outside the repo (ADR-037, finding 5). One filter here protects
 * every language rather than each join separately.
 */
export function insideRepo(relativePath) {
  const p = String(relativePath ?? '')
  if (!p || p.startsWith('/')) return false
  return !p.split('/').includes('..')
}

/**
 * What a SCIP symbol denotes, from its descriptor suffix.
 *
 * `<scheme> <manager> <package> <version> <descriptors>`; the suffix of the
 * last descriptor says what kind of thing it is. Only the first four kinds
 * are graph material (Decision 3).
 */
export function classify(symbol) {
  if (!symbol || symbol.startsWith('local ')) return 'local'
  const parts = symbol.split(' ')
  if (parts.length < 5) return 'malformed'
  const desc = parts.slice(4).join(' ')
  if (/\(\w[^)]*\)$/.test(desc)) return 'parameter'
  // `foo().`, with the SCIP spec's optional disambiguator inside the parens.
  // That is scip-java's overload counter `foo(+1).` (ADR-096), or
  // scip-clang's signature hash `cJSON_Delete(6efceb6909523ce2).` for a C
  // function. Without the hash here every C function read as a `term`, and
  // its name never matched a call site (the C lane B spike).
  if (/\([\w+]*\)\.$/.test(desc)) return 'method'
  if (desc.endsWith('#')) return 'type'
  if (desc.endsWith('.')) return 'term'
  if (desc.endsWith('/')) return 'namespace'
  if (desc.endsWith(':')) return 'meta'
  // SCIP's macro descriptor (`macros/println!`). Only rust-analyzer emits
  // it today; without this a repo-defined macro_rules! is invisible to
  // the definitions map and every invocation of it lands in external_refs
  // attributed to the repo's own crate (ADR-040).
  if (desc.endsWith('!')) return 'macro'
  return 'other'
}

/** Descriptor kinds that become graph symbols. */
export const GRAPH_KINDS = new Set(['namespace', 'type', 'method', 'term', 'macro'])

/**
 * The terminal descriptor's bare name, which is what a syntax provider
 * saw at the call site (ADR-029 matches on it).
 *
 * `…\`src.a\`/Engine#run().` -> `run`;  `…/CONFIG.` -> `CONFIG`.
 */
export function terminalName(symbol) {
  const parts = String(symbol).split(' ')
  if (parts.length < 5) return ''
  const desc = parts.slice(4).join(' ')
  // Strip the descriptor suffix — a method's disambiguator with it
  // (scip-java's `(+1)`, scip-clang's signature hash) — then take the last
  // path/member segment.
  const bare = desc.replace(/(\([\w+]*\)\.|#|\.|\/|:|!)$/, '')
  const segments = bare.split(/[/#.]/).filter(Boolean)
  const seg = segments.pop() ?? ''
  // rust-analyzer scopes impl methods as `impl#[Counter]new().` — the
  // bracketed self type rides the final segment, and a name that keeps it
  // matches no call site, which silently costs Rust every method edge
  // (found by the V2.M7 rust_proj verification: `unwrap` unresolved).
  const name = seg.replace(/`/g, '').replace(/^\[.*\]/, '')
  // scip-java names a constructor `<init>` (`Foo#`<init>`(+1).`); what
  // the syntax provider saw at `new Foo(..)` — and at the declaration —
  // is the type's name, so the two lanes meet on it (ADR-096).
  if (name === '<init>') return (segments.pop() ?? '').replace(/`/g, '')
  return name
}

/**
 * The class moniker a C++ constructor moniker belongs to, or '' when
 * *symbol* is not one.
 *
 * scip-clang names a constructor after its class, as C++ does:
 * `` `shapes/Circle#Circle(9b2f…).` `` is the constructor of
 * `shapes/Circle#`. The test is the moniker's own shape — a method whose
 * name equals the last segment of the type that owns it — so no
 * language-specific name list is needed.
 */
function constructorClass(symbol) {
  const parts = String(symbol).split(' ')
  if (parts.length < 5) return ''
  const method = /^(.*#)([^#/]+)\([\w+]*\)\.$/.exec(parts.slice(4).join(' '))
  if (!method) return ''
  const [, owner, name] = method
  const segments = owner.slice(0, -1).split(/[/#]/)
  if (segments[segments.length - 1] !== name) return ''
  return `${parts.slice(0, 4).join(' ')} ${owner}`
}

/** `<manager>:<package>` for a symbol, or '' when it has no package. */
export function packageOf(symbol) {
  const p = String(symbol).split(' ')
  return p.length >= 4 ? `${p[1]}:${p[2]}` : ''
}

const isDefinition = (occ) =>
  (occ.symbol_roles & scip.SymbolRole.Definition) !== 0

/**
 * Decode an index into definitions, references, and the packages it
 * resolved against.
 *
 * Ranges are SCIP's `[startLine, startChar, endLine, endChar]` (or a
 * 3-element form when the range is single-line), zero-based; graph lines
 * are one-based, so every line is +1 here and nowhere else.
 *
 * The decode is order-independent (ADR-113 §2, amended): scip-clang gives
 * one moniker to several definitions of one file — a class template and
 * its specialisations, `enable_if` overloads its signature hash does not
 * tell apart, `#if` alternatives across units — and lists them in an
 * order that varies by run. Keeping the first one met made the answer
 * vary with it: three fmt ingests at one commit drew 3,308, 3,298 and
 * 3,293 call edges. So such a moniker's definitions are collected in
 * full, and the choice among them is made by rule, not by arrival.
 */
export function decode(index, opts = {}) {
  // `opts` carries C's two rules (ADR-109, `decodeOptions`): `nameOf`
  // reads a name the moniker does not spell, and `ownFile` resolves a
  // file-static that several files define. C++ adds three of its own,
  // `constructorOverClass`, `abstainMultiDefined` and
  // `abstainOverloadSites` (ADR-113 §2). Every other language passes
  // nothing and decodes as before.
  const nameOf = opts.nameOf ?? terminalName
  // A reference carries no moniker — the join keys on file, line and name
  // — so C++'s two rules that need one are given it here and nowhere else.
  const monikerOf = new Map()
  const keepMonikers = Boolean(opts.constructorOverClass || opts.abstainOverloadSites)
  const byFile = new Map() // `${moniker}\0${file}` -> that file's own definition, smallest line
  const definitions = new Map() // moniker -> {file, line, endLine, kind}
  const packages = new Map() // manager:package -> reference count
  const references = []
  // Occurrences that resolve *outside* this index — stdlib and third-party.
  // Not repo edges, but not failures either: recording them is what lets
  // the join tell "correctly out of scope" from "nobody could resolve it",
  // which is the difference between coverage and a silent hole (P6).
  const external = []
  // Monikers defined in more than one document. rust-analyzer emits the
  // same `crate/` and `main().` for every cargo target of a package
  // (its own "Duplicate symbol" warning), so first-wins would attribute
  // a `use mylib` in a test to whichever binary decode saw first — a
  // false edge, which is worse than a missing one (ADR-007). Ambiguous
  // monikers are kept out of the definitions map: their references fall
  // to `external`, unattributed rather than guessed, and `degradations`
  // reports the drop (ADR-040).
  const ambiguous = new Set()
  // Which files define each ambiguous moniker (ADR-091, D7): the
  // degradation record is scoped to their common directory, so a unit
  // brief whose interior lies elsewhere never carries it.
  const ambiguousFiles = new Map()
  // Every symbol with a definition occurrence in an in-repo document,
  // whatever its kind — collected before the GRAPH_KINDS filter below, so
  // it also catches a moniker of a kind the graph drops (ADR-111). This is
  // what tells "outside the repo" from "in the repo but ambiguous, or of a
  // kind we do not keep" when an external reference is recorded.
  const inRepoMonikers = new Set()
  // Monikers one file defines at more than one line, where the language
  // abstains rather than pick one (`opts.abstainMultiDefined`, C++ only —
  // ADR-113 §2). They are treated as an ambiguous moniker is: no
  // definition, no edge, and their references stay in-repo so they veto
  // no lane A fallback (ADR-111). Counted, never silent.
  const multiDefined = new Set()
  let multiDefinedRefs = 0
  // moniker -> file -> {def: its smallest-line definition, lines}. Every
  // definition line is collected, not the first met, because scip-clang's
  // order varies by run (see the doc comment above).
  const defsOf = new Map()
  const smallestLine = (a, b) => (a && a.line <= b.line ? a : b)

  for (const doc of documentsOf(index)) {
    if (!insideRepo(doc.relative_path)) continue
    for (const occ of doc.occurrences) {
      if (!occ.symbol || occ.symbol.startsWith('local ')) continue
      if (!isDefinition(occ)) continue
      inRepoMonikers.add(occ.symbol)
      const kind = classify(occ.symbol)
      if (!GRAPH_KINDS.has(kind)) continue
      const r = occ.range
      const here = {
        moniker: occ.symbol,
        file: doc.relative_path,
        line: r[0] + 1,
        end_line: (r.length >= 4 ? r[2] : r[0]) + 1,
        kind,
      }
      const own = `${occ.symbol}\u0000${doc.relative_path}`
      if (opts.ownFile) byFile.set(own, smallestLine(byFile.get(own), here))
      let files = defsOf.get(occ.symbol)
      if (!files) defsOf.set(occ.symbol, (files = new Map()))
      const seen = files.get(doc.relative_path)
      if (seen) {
        seen.def = smallestLine(seen.def, here)
        seen.lines.add(here.line)
      } else {
        files.set(doc.relative_path, { def: here, lines: new Set([here.line]) })
      }
    }
  }
  for (const [symbol, files] of defsOf) {
    if (files.size > 1) {
      ambiguous.add(symbol)
      ambiguousFiles.set(symbol, new Set(files.keys()))
      continue
    }
    const [{ def, lines }] = files.values()
    // One file, several lines. A namespace keeps its smallest line in
    // every language (lane A draws none of them anyway); anything else
    // either abstains — C++, where the shapes that share a moniker are
    // genuinely different definitions — or takes the smallest line, which
    // is ADR-109's "kept once, at the first line" made order-independent.
    if (lines.size > 1 && def.kind !== 'namespace' && opts.abstainMultiDefined) {
      multiDefined.add(symbol)
      continue
    }
    definitions.set(symbol, def)
  }
  let tuSplit = 0
  // Sites where the references name more than one overload of one name
  // (`opts.abstainOverloadSites`, C++ only — ADR-113 §2, C-151). Every
  // example is collected and sorted below, so which three are shown does
  // not depend on the order scip-clang listed the units in.
  const overloadSites = []

  for (const doc of documentsOf(index)) {
    if (!insideRepo(doc.relative_path)) continue
    for (const occ of doc.occurrences) {
      if (!occ.symbol || occ.symbol.startsWith('local ')) continue
      const pkgKey = packageOf(occ.symbol)
      if (pkgKey) packages.set(pkgKey, (packages.get(pkgKey) ?? 0) + 1)
      if (isDefinition(occ)) continue
      let target = definitions.get(occ.symbol)
      // C (ADR-109): file-statics of one signature in several files share
      // one scip-clang moniker. A reference from a file that defines it
      // means that file's own definition (C's static linkage); everywhere
      // else the moniker stays unattributed.
      if (!target && opts.ownFile && ambiguous.has(occ.symbol)) {
        target = byFile.get(`${occ.symbol}\u0000${doc.relative_path}`)
      }
      if (!target) {
        if (multiDefined.has(occ.symbol)) multiDefinedRefs += 1
        external.push({
          file: doc.relative_path,
          line: occ.range[0] + 1,
          col: occ.range[1],
          name: nameOf(occ.symbol),
          package: pkgKey,
          // Kept since v3 (ADR-049): "external" means external to *this
          // index*, and a sibling indexing unit of the same repo may
          // define exactly this moniker — the cross-unit join matches on
          // it after the per-unit indexes merge. Dropping it here was
          // what made C-33 unfixable in principle.
          moniker: occ.symbol,
          // ADR-111: this moniker has an in-repo definition after all — it
          // only missed `definitions` because it is ambiguous or of a kind
          // the graph drops. The join must not veto lane A's fallback on
          // a reference like this one.
          ...(inRepoMonikers.has(occ.symbol) ? { in_repo: true } : {}),
        })
        continue // resolves outside this index: not a repo edge
      }
      const reference = {
        file: doc.relative_path,
        line: occ.range[0] + 1,
        // Column and name are what let the join tell two same-named
        // occurrences on one line apart (ADR-029).
        col: occ.range[1],
        name: nameOf(occ.symbol),
        def_file: target.file,
        def_line: target.line,
      }
      if (keepMonikers) monikerOf.set(reference, occ.symbol)
      references.push(reference)
    }
  }

  // C++ (ADR-113 §2, measured on `minicpp`): a construction site carries
  // two references of one name — the class (`shapes/Circle#`, at the type)
  // and its constructor (`shapes/Circle#Circle(…).`, at the declared
  // variable for `Circle c(3)`, at the type for `new Circle(1)`). The
  // join's nearest-column pick and the one-target-per-site rule below both
  // land on the class, so every construction edge was drawn to the type,
  // where the oracle keys the constructor. Where both are at one
  // `(file, line, name)`, the class reference goes. A class with only an
  // implicit constructor has no constructor reference and keeps its type
  // reference alone.
  if (opts.constructorOverClass) {
    const dropped = new Set()
    const bySite = new Map()
    for (const r of references) {
      const key = JSON.stringify([r.file, r.line, r.name])
      if (!bySite.has(key)) bySite.set(key, [])
      bySite.get(key).push(r)
    }
    for (const rs of bySite.values()) {
      const classes = new Set(
        rs.map((r) => constructorClass(monikerOf.get(r))).filter(Boolean),
      )
      if (classes.size === 0) continue
      for (const r of rs) if (classes.has(monikerOf.get(r))) dropped.add(r)
    }
    if (dropped.size) {
      const kept = references.filter((r) => !dropped.has(r))
      // A loop, not `push(...kept)`: spreading hundreds of thousands of
      // references into arguments overflows the stack, and per-unit
      // indexing merges enough units to reach that (484,201 on fmt).
      references.length = 0
      for (const r of kept) references.push(r)
    }
  }

  // C (ADR-109): scip-clang merges translation units, so one site can
  // arrive once per unit, and not always with the same answer.
  // - Targets in one file, at several lines, are one definition's own
  //   `#if` alternatives (`CJSON_PUBLIC`, which the library and the tests
  //   configure differently). The edge is right in every configuration,
  //   so it is kept once, at the first line, which is where the graph
  //   keeps the symbol.
  // - Targets in different files are a real disagreement. At cJSON.c:612,
  //   `isinf` is cJSON's own macro in the C89 library build and Unity's
  //   in the test programs that #include cJSON.c. Lane B answering two
  //   ways is no answer: the site keeps lane A's floor, and the count is
  //   reported.
  // A site is a position *and a name*, as the join keys it. At a macro
  // call, scip-clang records the macro and every symbol of its expansion
  // at the call's own position (`TEST_ASSERT_TRUE` beside
  // `UNITY_TEST_ASSERT` and `UnityFail`). Those are different names, not
  // one name answered several ways.
  if (opts.oneTargetPerSite) {
    const bySite = new Map()
    for (const r of references) {
      const key = JSON.stringify([r.file, r.line, r.col, r.name])
      if (!bySite.has(key)) bySite.set(key, [])
      bySite.get(key).push(r)
    }
    const kept = []
    for (const rs of bySite.values()) {
      if (new Set(rs.map((r) => r.def_file)).size > 1) {
        tuSplit += 1
        continue
      }
      // C++ (ADR-113 §2, amended a third time, measured on the two cells):
      // one file, several lines, *several monikers* is an overload set, not
      // one definition's `#if` alternatives. scip-clang lists the candidates
      // of a call in a template it cannot resolve there — `write2` at
      // chrono.h:1348 references both `write2(d4f7…)` and `(fc4f…)` — and
      // keeping the smallest line answers whichever the call meant: 36 wrong
      // semantic edges on fmt and all 4 of args' contradictions. So the site
      // abstains. C keeps its rule: its several lines are one moniker's.
      if (opts.abstainOverloadSites && new Set(rs.map((r) => monikerOf.get(r))).size > 1) {
        overloadSites.push({ name: rs[0].name, file: rs[0].file, line: rs[0].line })
        continue
      }
      kept.push(rs.reduce((a, b) => (b.def_line < a.def_line ? b : a)))
    }
    // A loop, not `push(...kept)`, for the reason above.
    references.length = 0
    for (const r of kept) references.push(r)
  }

  overloadSites.sort((a, b) =>
    a.file.localeCompare(b.file) || a.line - b.line || a.name.localeCompare(b.name),
  )
  const overrides = implementsRows(index, definitions)
  return {
    ...overrides,
    tu_split: tuSplit,
    overload_sites: overloadSites.length,
    overload_examples: overloadSites.slice(0, 3),
    multi_defined: [...multiDefined].sort(),
    multi_defined_refs: multiDefinedRefs,
    definitions: [...definitions.values()],
    references,
    external,
    packages,
    ambiguous: [...ambiguous].sort(),
    ambiguous_files: Object.fromEntries(
      [...ambiguousFiles].sort().map(([symbol, files]) => [symbol, [...files].sort()]),
    ),
  }
}

/** The owning type of a member moniker — everything up to and including
 * its last `#` — or '' for a moniker that is not a member of a type.
 * `…/Circle#area().` → `…/Circle#`; scip-go's interface method spec
 * `…/Journal#Park.` → `…/Journal#`; a type `…/Circle#` → `…/` prefix of
 * itself is not wanted, so a type answers ''. */
function ownerOf(symbol) {
  if (symbol.endsWith('#')) return ''
  const at = symbol.lastIndexOf('#')
  return at === -1 ? '' : symbol.slice(0, at + 1)
}

/**
 * The override set (ADR-120): every `implements` pair the index states
 * between two in-repo definitions, as rows the join draws as `implements`
 * edges — `{file, line}` the implementor's definition, `{def_file,
 * def_line}` the implemented's.
 *
 * SCIP's convention (the proto's own example) puts the relationship on
 * the *implementor*: `Dog#` carries `{symbol: "Animal#",
 * is_implementation}`, and `Dog#bark().` the same toward `Animal#bark().`.
 * Measured on the six indexers (2026-09-16, this repo's fixtures and its
 * own Go and Python, ScummVM for scip-clang): scip-clang, scip-go,
 * scip-typescript and scip-python write exactly that; scip-java writes it
 * and, on an abstract or interface method, the *reverse* row too
 * (`Shape#area().` → `Circle#area().`, so that an editor's "find
 * implementations" on the interface method finds them); rust-analyzer
 * writes no relationships at all (C-157).
 *
 * So a pair whose reverse is also stated is oriented by the type level:
 * the row whose owner reaches the other's owner through the index's own
 * type-level pairs is the implementor's, and the other is dropped. A
 * chain counts (`C#m` → `A#m` where `C#` → `B#` → `A#`: scip-clang and
 * javac name the overridden method by where it is declared, and the
 * class by its direct base). A mutual pair no type-level row can orient
 * is dropped both ways and counted (`implements_undirected`), never
 * guessed. A pair whose target is outside this index — a stdlib
 * interface, a sibling unit's — is counted (`implements_outside`) and
 * draws nothing; a pair whose source is no graph definition (a local, an
 * ambiguous moniker) is counted (`implements_unplaced`).
 *
 * Rows are deduplicated — scip-clang states a class's base once per
 * translation unit that sees it — and sorted, so the facts do not depend
 * on the order the units were listed in.
 */
export function implementsRows(index, definitions) {
  const stated = new Set() // `${source}\u0000${target}` for every stated pair
  const pairs = []
  for (const doc of documentsOf(index)) {
    if (!insideRepo(doc.relative_path)) continue
    for (const info of doc.symbols ?? []) {
      if (!info.symbol || info.symbol.startsWith('local ')) continue
      for (const target of info.implements) {
        if (!target || target.startsWith('local ')) continue
        const key = `${info.symbol}\u0000${target}`
        if (stated.has(key)) continue
        stated.add(key)
        pairs.push([info.symbol, target])
      }
    }
  }
  // Type-level pairs, for orienting a mutual member pair.
  const bases = new Map() // type -> Set of the types it is stated to implement
  for (const [source, target] of pairs) {
    if (!source.endsWith('#') || !target.endsWith('#')) continue
    if (!bases.has(source)) bases.set(source, new Set())
    bases.get(source).add(target)
  }
  const reaches = (from, to) => {
    const seen = new Set()
    const stack = [from]
    while (stack.length) {
      const here = stack.pop()
      if (here === to) return true
      if (seen.has(here)) continue
      seen.add(here)
      for (const next of bases.get(here) ?? []) stack.push(next)
    }
    return false
  }
  const rows = new Map()
  let outside = 0
  let unplaced = 0
  let undirected = 0
  for (const [source, target] of pairs) {
    const from = definitions.get(source)
    if (!from) {
      unplaced += 1
      continue
    }
    const to = definitions.get(target)
    if (!to) {
      outside += 1
      continue
    }
    if (stated.has(`${target}\u0000${source}`)) {
      const forward = reaches(ownerOf(source), ownerOf(target))
      const backward = reaches(ownerOf(target), ownerOf(source))
      if (!forward) {
        // The reverse row's turn will keep it, or neither is kept.
        if (!backward) undirected += 1
        continue
      }
    }
    const row = { file: from.file, line: from.line, def_file: to.file, def_line: to.line }
    rows.set(JSON.stringify([row.file, row.line, row.def_file, row.def_line]), row)
  }
  const implementsList = [...rows.values()].sort(
    (a, b) =>
      a.file.localeCompare(b.file) ||
      a.line - b.line ||
      a.def_file.localeCompare(b.def_file) ||
      a.def_line - b.def_line,
  )
  return {
    implements: implementsList,
    implements_outside: outside,
    implements_unplaced: unplaced,
    // Counted once per mutual pair, not once per direction.
    implements_undirected: undirected / 2,
  }
}

/**
 * The deepest directory that holds every one of *files* (relative,
 * '/'-separated); '.' when they share none. Where a duplicated moniker's
 * degradation record lands, so it is read by the units it concerns.
 */
export function commonDirectory(files) {
  const dirs = files.map((f) => f.split('/').slice(0, -1))
  if (dirs.length === 0) return '.'
  let common = dirs[0]
  for (const d of dirs.slice(1)) {
    let i = 0
    while (i < common.length && i < d.length && common[i] === d[i]) i++
    common = common.slice(0, i)
  }
  return common.length ? common.join('/') : '.'
}

/**
 * Why a language's indexer emits one moniker from more than one file —
 * stated per lane (ADR-091, D7): the Rust wording on a Python decode
 * rode every sklearn brief in the ADR-085 validation run.
 */
const DUPLICATE_SHAPES = {
  rust: 'cargo targets of one package share their `crate/` and `main().` monikers',
  java: "a package's namespace is declared in every one of its files (`package a.b;`)",
  go: "a package's namespace is declared in every one of its files",
  python: 'the same module name lives under more than one directory (a tutorial\'s skeletons/ and solutions/, a vendored copy)',
  typescript: 'the same module or namespace is declared from more than one file',
  c: 'file-`static`s of one signature in several files share one scip-clang moniker (a reference from a file that defines it resolves to that file\'s own, ADR-109), and so does `main` across programs',
  cpp: 'file-`static`s of one signature in several files share one scip-clang moniker (a reference from a file that defines it resolves to that file\'s own, ADR-109), `main` does too across programs, and a namespace is declared from every file that opens it',
}

/**
 * Packages an indexer resolves from its own bundle, whatever the repo's
 * environment looks like. They must not count as evidence that the
 * environment is installed — see `dependencyCoverage`.
 */
const SELF_PACKAGES = new Set([
  'typescript',
  'python-stdlib',
  // Go's stdlib resolves from the toolchain, always, so counting it as a
  // resolved dependency would report full coverage for a repo whose real
  // dependencies were all missing (ADR-032's lesson, a language later).
  'github.com/golang/go/src',
  // Rust's stdlib crates resolve from the rustup sysroot, always (their
  // moniker versions are rust-lang/rust URLs, not crates.io versions —
  // spike-rust.mjs). Same rule, fourth language. The names are generic,
  // but the exclusion is symmetric (both declared and seen sides), so a
  // repo that really depended on a crates.io package by one of these
  // names is left uncounted, never miscounted.
  'std',
  'core',
  'alloc',
  'proc_macro',
  // scip-java's JDK: the class library resolves from the JDK the image
  // carries, always (moniker package `jdk`, version the major — spike).
  // And `.`: the package scip-java gives a Gradle project's own symbols
  // when no `maven-publish` coordinates exist, and every package
  // namespace — the repo itself, never a dependency.
  'jdk',
  '.',
])

/**
 * Decision 4's signal, as counts rather than a boolean (ADR-032).
 *
 * The original test fired only when *every* declared dependency was
 * missing. For TypeScript that can never happen: the indexer bundles
 * `typescript` and therefore always resolves it, so one always-present
 * package held the condition false forever. Measured on kbet staged
 * without `node_modules`: **1 of 23 declared dependencies resolved, and
 * nothing was reported**. A boolean that can only be true in an
 * impossible case is worse than no check, because it reads as coverage.
 *
 * So the counts are emitted on every run, degraded or not — the ADR-029
 * denominator pattern — and the threshold is secondary to them.
 */
/** PEP 503 name normalisation, Python only: distribution names are
 * case-insensitive and `-`/`_`/`.` are one character, so a manifest's
 * `pyyaml` and the moniker's `PyYAML` (or `tree-sitter` and
 * `tree_sitter`) are the same package. Without this the C-27 fix half
 * worked — the index resolved into PyYAML and the coverage report went
 * on saying `pyyaml` was missing. npm and Go names stay verbatim: their
 * ecosystems treat case and punctuation as identity. */
function canonicalName(name, language) {
  if (language === 'python') return name.toLowerCase().replace(/[-_.]+/g, '-')
  // Java: a moniker's package is `maven/<group>/<artifact>`, and a pom
  // declares artifacts a build resolves to *other* artifacts (a BOM, an
  // aggregator like `junit-jupiter` with no classes of its own) — so
  // coverage is matched at the group: some artifact of the declared
  // group resolved, or none did (ADR-096).
  if (language === 'java') return name.split('/').slice(0, 2).join('/')
  return name
}

export function dependencyCoverage(decoded, config, alsoResolved = []) {
  // Excluded from *both* sides. A bundled package resolving is not
  // evidence the environment exists, and a repo declaring it (nearly
  // every TS repo declares `typescript`) must not be marked as missing a
  // dependency it will never be credited for either.
  const declared = (config.declaredDeps ?? []).filter((d) => !SELF_PACKAGES.has(d))
  const seen = new Set()
  // *alsoResolved*: packages the build itself resolved, where the index
  // cannot name them (the Gradle route, `resolvedPackages`).
  for (const key of [...decoded.packages.keys(), ...alsoResolved]) {
    const name = key.split(':')[1]
    if (!name || SELF_PACKAGES.has(name)) continue
    seen.add(canonicalName(name, config.language))
    // `import React from "react"` resolves to @types/react, so the
    // package SCIP attributes is the types package. Crediting only the
    // literal name would report every typed dependency as missing.
    if (name.startsWith('@types/')) seen.add(name.slice('@types/'.length))
  }
  const missing = declared.filter((d) => !seen.has(canonicalName(d, config.language)))
  return {
    declared: declared.length,
    resolved: declared.length - missing.length,
    missing,
  }
}

/** Below this share of declared dependencies resolved, the index is not
 * describing the repo the user has — it is describing a subset nobody
 * asked for. Not a proof, and a *partial* environment still degrades in
 * proportion (C-23); the counts above are what stay honest. */
const RESOLVE_FLOOR = 0.5

/**
 * Decision 4: a zero exit is not a successful index.
 *
 * scip-typescript on a repo with no node_modules exits 0 in 1.5s and
 * writes a plausible 2.4MB index whose every third-party edge is missing,
 * because the declared dependencies were not there to resolve against.
 * Nothing in the process tells you. So ask the index itself.
 */
export function degradations(index, decoded, config) {
  const out = []
  if (documentCount(index) === 0) {
    out.push({
      stage: 'scip-index',
      message: 'the indexer emitted no documents; nothing was analysed',
    })
  }
  const coverage = dependencyCoverage(decoded, config)
  if (coverage.declared && coverage.resolved / coverage.declared < RESOLVE_FLOOR) {
    out.push({
      stage: 'scip-resolve',
      message:
        `only ${coverage.resolved} of ${coverage.declared} declared dependencies ` +
        `resolved (missing ${coverage.missing.slice(0, 3).join(', ')}…) — the ` +
        'environment is probably not installed, so third-party edges are absent ' +
        'rather than nonexistent',
    })
  }
  if (decoded.definitions.length === 0 && documentCount(index) > 0) {
    out.push({
      stage: 'scip-decode',
      message: 'documents were indexed but no graph-worthy definitions came out',
    })
  }
  if (decoded.units_failed) {
    out.push({
      stage: 'scip-decode',
      message:
        `${decoded.units_failed} of ${decoded.units} translation unit(s) failed to index; ` +
        "the others stand, and the failed units' sites fall to lane A's fallback (ADR-109)",
    })
  }
  if (decoded.whole_database) {
    out.push({
      stage: 'scip-decode',
      message:
        `this build root's compile database holds ${decoded.whole_database} translation units, ` +
        `over the per-unit bound (${PER_UNIT_MAX}), so it was indexed in one whole-database run: ` +
        'scip-clang indexes a header many units share once, in whichever unit claims it first, ' +
        'so a reference whose answer depends on the unit may differ from one ingest to the next (C-149)',
    })
  }
  if (decoded.tu_split) {
    out.push({
      stage: 'scip-decode',
      message:
        `${decoded.tu_split} call site(s) resolve to different definitions in different ` +
        'translation units (a macro or a static that a unit\'s includes decide); lane B\'s ' +
        "answer is dropped there and lane A's syntactic floor stands (ADR-109, C-131)",
    })
  }
  if (decoded.overload_sites) {
    const sample = (decoded.overload_examples ?? [])
      .map((e) => `\`${e.name}\` at ${e.file}:${e.line}`)
      .join(', ')
    out.push({
      stage: 'scip-decode',
      message:
        `${decoded.overload_sites} call site(s) name more than one overload of one ` +
        `name (e.g. ${sample}) — scip-clang lists the candidates of a call it cannot ` +
        "resolve there, or units answer differently; lane B's answer is dropped " +
        'rather than the first line taken (ADR-113 §2, C-151)',
    })
  }
  if ((decoded.multi_defined ?? []).length > 0) {
    const sample = decoded.multi_defined
      .slice(0, 3)
      .map((s) => s.split(' ').slice(4).join(' '))
      .join(', ')
    out.push({
      stage: 'scip-decode',
      message:
        `${decoded.multi_defined.length} symbol(s) are defined at more than one ` +
        `line of one file (e.g. ${sample}) — a class template and its ` +
        "specialisations, or overloads scip-clang's signature hash does not tell " +
        `apart, share one moniker; ${decoded.multi_defined_refs} reference(s) to ` +
        'them are left without a lane B answer rather than guessed (ADR-113)',
    })
  }
  if (config.language === 'rust') {
    // C-157 (ADR-120): rust-analyzer's SCIP export writes no
    // `relationships`, so a trait impl states no override pair and Rust
    // draws no `implements` edge. Said on every Rust run, because it is a
    // fact about the provider, not about the crate.
    out.push({
      stage: 'scip-decode',
      message:
        "rust-analyzer's SCIP export carries no `relationships`, so no `implements` " +
        'edge is drawn for Rust: which type implements which trait, and which method ' +
        'overrides which, is not in the index (C-157)',
    })
  }
  if (decoded.implements_undirected) {
    out.push({
      stage: 'scip-decode',
      message:
        `${decoded.implements_undirected} implements pair(s) are stated in both directions ` +
        'and no type-level pair orients them; both rows are dropped rather than one ' +
        'guessed (ADR-120)',
    })
  }
  if ((decoded.ambiguous ?? []).length > 0) {
    const sample = decoded.ambiguous
      .slice(0, 3)
      .map((s) => s.split(' ').slice(4).join(' '))
      .join(', ')
    const files = [...new Set(Object.values(decoded.ambiguous_files ?? {}).flat())]
    const shape = DUPLICATE_SHAPES[config.language] ?? 'more than one file declares the same symbol'
    out.push({
      stage: 'scip-decode',
      path: commonDirectory(files),
      message:
        `${decoded.ambiguous.length} symbol(s) are defined in more than one ` +
        `file (e.g. ${sample}) — ${shape}; references to them are left ` +
        'unattributed rather than guessed (C-28)',
    })
  }
  return out
}

/** The steps an indexer runs for *config*: one for every language but
 * Gradle-built Java, whose plan is Hobbes's own (`gradlePlan`). A step
 * names its binary the way it is installed and where it runs. */
export function indexerPlan(config) {
  const spec = INDEXERS[config.language]
  if (!spec) throw new Error(`no indexer configured for ${config.language}`)
  const plan = spec.plan ? spec.plan(config) : null
  if (plan) return plan
  return {
    steps: [{
      bin: spec.bin, onPath: spec.onPath, install: spec.install,
      args: spec.args(config), ...(spec.cwd ? { cwd: spec.cwd(config) } : {}),
    }],
  }
}

function runIndexer(config) {
  const plan = indexerPlan(config)
  let proc
  let resolved = []
  try {
    if (plan.prepare) plan.prepare()
    for (const step of plan.steps) {
      if (step.check) step.check(proc)
      proc = runStep(step)
    }
    if (plan.resolved) resolved = plan.resolved()
  } finally {
    if (plan.cleanup) plan.cleanup()
  }
  return { proc, resolved, unitsDir: plan.unitsDir }
}

function runStep(step) {
  // Two install shapes, because indexers are not all npm packages: the
  // Python and TypeScript ones are pinned devDependencies here, scip-go
  // is a Go binary the user installs (`go install`). Resolving the wrong
  // one fails as a bare ENOENT, so each says how *it* is installed.
  const bin = step.onPath ? step.bin : join(HERE, 'node_modules', '.bin', step.bin)
  const proc = spawnSync(bin, step.args, {
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
    timeout: 600_000,
    ...(step.cwd ? { cwd: step.cwd } : {}),
  })
  if (proc.error && proc.error.code === 'ENOENT') {
    throw new Error(
      step.onPath
        ? `${step.bin} is not on PATH — install it with \`${step.install}\``
        : `${step.bin} is not installed — run \`npm install\` in the hobbes repo's scip/`,
    )
  }
  if (proc.status !== 0) {
    const detail = String(proc.stderr || proc.stdout || '').trim().slice(-500)
    const err = new Error(`${step.bin} ${step.args[0]} exited ${proc.status}: ${detail}`)
    err.indexerExit = proc.status
    throw err
  }
  return proc
}

/** C's decode rules (ADR-109) — C++ takes all three and adds three
 * (ADR-113 §2); every other language gets none.
 *
 * scip-clang names a macro by where it is defined, not by what it is
 * called (`` cxx . . $ `cJSON.h:281:9`! ``), so no call site could ever
 * match it by name. The name is read at that location in the stage. A
 * location outside the repo (a libc macro) keeps the moniker's own form,
 * which matches nothing, and stays external. */
export function decodeOptions(config) {
  if (config.language !== 'c' && config.language !== 'cpp') return {}
  const lines = new Map()
  const nameOf = (symbol) => {
    const at = /`([^`]+):(\d+):(\d+)`!$/.exec(String(symbol))
    if (!at || !insideRepo(at[1])) return terminalName(symbol)
    const [, file, line, col] = at
    if (!lines.has(file)) {
      try {
        lines.set(file, readFileSync(join(config.stage, file), 'utf8').split('\n'))
      } catch {
        lines.set(file, null)
      }
    }
    const text = lines.get(file)?.[Number(line) - 1]
    const id = text == null ? null : /^[A-Za-z_]\w*/.exec(text.slice(Number(col) - 1))
    return id ? id[0] : terminalName(symbol)
  }
  return {
    nameOf,
    ownFile: true,
    oneTargetPerSite: true,
    // C++ alone abstains on a moniker one file defines at several lines,
    // and on a site whose references name more than one overload; C takes
    // the smallest line in both (ADR-113 §2, ADR-109 amended).
    ...(config.language === 'cpp'
      ? {
          constructorOverClass: true,
          abstainMultiDefined: true,
          abstainOverloadSites: true,
        }
      : {}),
  }
}

/**
 * The translation units' indexes, read as one (ADR-109 decision 1,
 * amended): their documents concatenated in database order, in the shape
 * `decode` reads. The same header arrives once per unit that includes it,
 * which is the point — every unit indexes its own copy, so nothing depends
 * on which unit claimed it first. `decode` already answers a site the
 * units answer differently by rule (tu-split, the smallest line, C++'s
 * abstention), so merging needs no rule of its own.
 */
export function mergeUnitIndexes(indexes) {
  const source = {
    count: 0,
    *documents() {
      source.count = 0
      for (const index of indexes) {
        for (const doc of documentsOf(index)) {
          source.count += 1
          yield doc
        }
      }
    },
  }
  return source
}

/** Every unit index under *unitsDir*, in name order, with the count of
 * units whose output is not there to read: a scip-clang run that failed or
 * wrote nothing usable. The others stand. A database over `PER_UNIT_MAX`
 * left one `whole.json` and one index; `whole` then carries its unit count.
 * The indexes are named, not read: `indexStage` streams them (ADR-115). */
function readUnitIndexes(unitsDir) {
  const names = existsSync(unitsDir)
    ? readdirSync(unitsDir).filter((f) => f.endsWith('.json')).sort()
    : []
  const readable = (path) => existsSync(path) && wellFormedIndex(readFileSync(path))
  if (names.length === 1 && names[0] === 'whole.json') {
    const units = JSON.parse(readFileSync(join(unitsDir, 'whole.json'), 'utf8')).length
    const whole = join(unitsDir, 'whole.scip')
    return readable(whole)
      ? { units, units_failed: 0, files: [whole], whole: units }
      : { units, units_failed: units, files: [], whole: units }
  }
  const files = []
  for (const name of names) {
    const out = join(unitsDir, `${name.slice(0, -'.json'.length)}.scip`)
    // Missing or unreadable: that unit did not index. Counted below.
    if (readable(out)) files.push(out)
  }
  return { units: names.length, units_failed: names.length - files.length, files }
}

/** Every one of a root's translation units failed, so there is no index to
 * decode. That is the indexer's outcome, not a helper that could not run:
 * it carries `indexerExit`, as a refused compile database does. */
function noUnitIndexed(units, proc) {
  const said = String(proc?.stderr || proc?.stdout || '').trim().slice(-500)
  const err = new Error(
    `scip-clang indexed none of the ${units} translation unit(s) — ` +
    `it is installed by \`${INDEXERS.c.install}\`: ${said}`,
  )
  err.indexerExit = 1
  return err
}

/** Run the plan, decode what it wrote, and report it.
 *
 * C and C++ index one translation unit per scip-clang run (`cPlan`), so
 * the index to decode is the units' concatenation rather than one file,
 * and the units that failed are counted and reported rather than passed
 * off as an empty result (C-149). Every other language writes the one
 * `config.output` it always did. */
export function indexStage(config) {
  const { proc, resolved, unitsDir } = runIndexer(config)
  let index
  let unitRuns = null
  let decoded
  try {
    if (unitsDir) {
      unitRuns = readUnitIndexes(unitsDir)
      if (unitRuns.units > 0 && unitRuns.files.length === 0) throw noUnitIndexed(unitRuns.units, proc)
      index = indexFiles(unitRuns.files)
    } else {
      if (!existsSync(config.output) || !wellFormedIndex(readFileSync(config.output))) {
        throw new Error('could not read the SCIP index the indexer wrote: not a SCIP index')
      }
      index = indexFiles([config.output])
    }
    // The decode streams the files (ADR-115), so they stay until it is done.
    decoded = decode(index, decodeOptions(config))
  } finally {
    // A .scip file is an intermediate, never an artifact (ADR-027 clause
    // 6): its metadata.project_root holds the absolute staging path, so
    // identical content staged elsewhere differs in bytes. Nothing about
    // it is propagated, and it is removed once decoded — the unit
    // databases and their indexes with it.
    rmSync(config.output, { force: true })
    if (unitsDir) rmSync(unitsDir, { recursive: true, force: true })
  }
  // How many units ran is the run's fact, not the decode's, but it is
  // read where every other count is: in `degradations`.
  if (unitRuns) {
    decoded.units = unitRuns.units
    decoded.units_failed = unitRuns.units_failed
    decoded.whole_database = unitRuns.whole ?? 0
  }
  return {
    helper_version: HELPER_VERSION,
    language: config.language,
    definitions: decoded.definitions,
    references: decoded.references,
    external_refs: decoded.external,
    // The override set (ADR-120): drawn by the join as `implements` edges.
    implements: decoded.implements,
    implements_outside: decoded.implements_outside,
    implements_unplaced: decoded.implements_unplaced,
    implements_undirected: decoded.implements_undirected,
    packages: Object.fromEntries(decoded.packages),
    ...(unitRuns
      ? { units: unitRuns.units, units_failed: unitRuns.units_failed, whole_database: unitRuns.whole ?? 0 }
      : {}),
    // Reported every run, not only when something is wrong: the counts
    // are the honest form of the signal and the threshold is secondary.
    dependency_coverage: dependencyCoverage(decoded, config, resolved),
    degraded: degradations(index, decoded, config),
    stderr: String(proc.stderr || '').trim().slice(-2000),
  }
}

/** The facts as JSON lines (ADR-116), one string per line and none of them
 * the whole: a header, one record per document, and a trailer.
 *
 * The whole facts document is one V8 string, and V8's longest is 536,870,888
 * characters: ScummVM's facts are 699 MB of JSON, and `JSON.stringify` threw
 * `RangeError: Invalid string length`. A line here is one document's rows
 * (ScummVM's longest: 5.3 MB).
 *
 * A document's rows drop the `file` its record states once. Documents come in
 * the order of their first row — definitions, then references, then external
 * references — and rows keep the decode's order within one, so every
 * (file, line) bucket the Python join builds holds its sites in the order it
 * did when the facts were one document. The trailer counts the documents and
 * each kind of row, so a file cut short is told from a smaller answer, and
 * carries the root-level fields. */
export function* factsLines(facts) {
  const { helper_version, language, definitions, references, external_refs, implements: overrides = [], ...rest } = facts
  yield JSON.stringify({ helper_version, language })
  const documents = new Map()
  // `implements` rows (ADR-120, helper version 5) are the fourth row kind,
  // keyed like the others by the file they sit in — the implementor's.
  for (const [key, rows] of Object.entries({ definitions, references, external_refs, implements: overrides })) {
    for (const row of rows) {
      let doc = documents.get(row.file)
      if (!doc) documents.set(row.file, (doc = { file: row.file, definitions: [], references: [], external_refs: [], implements: [] }))
      doc[key].push(row)
    }
  }
  const bare = ({ file, ...row }) => row
  for (const doc of documents.values()) {
    yield JSON.stringify({
      file: doc.file,
      definitions: doc.definitions.map(bare),
      references: doc.references.map(bare),
      external_refs: doc.external_refs.map(bare),
      implements: doc.implements.map(bare),
    })
  }
  yield JSON.stringify({
    end: true,
    documents: documents.size,
    definitions: definitions.length,
    references: references.length,
    external_refs: external_refs.length,
    implements: overrides.length,
    ...rest,
  })
}

/** Write `factsLines(facts)` to *path*, a line at a time. */
export function writeFacts(facts, path) {
  const fd = openSync(path, 'w')
  try {
    for (const line of factsLines(facts)) writeSync(fd, line + '\n')
  } finally {
    closeSync(fd)
  }
}

function main(argv) {
  const at = argv.indexOf('--config')
  if (at === -1 || !argv[at + 1]) {
    process.stderr.write('usage: index.mjs --config <path-to-json>\n')
    process.exitCode = 2
    return
  }
  const config = JSON.parse(readFileSync(argv[at + 1], 'utf8'))
  try {
    // Never stdout (ADR-116): the Python side names the file and reads it as
    // it arrives, and nothing is printed there.
    if (!config.facts) throw new Error('the config names no `facts` file to write (helper version 4, ADR-116)')
    writeFacts(indexStage(config), config.facts)
  } catch (err) {
    process.stderr.write(String(err.message ?? err) + '\n')
    // process.exitCode, not process.exit: a hard exit can truncate a large
    // stdout write that is still flushing (the M6 lesson).
    process.exitCode = exitCodeFor(err)
  }
}

if (process.argv[1] && process.argv[1].endsWith('index.mjs')) main(process.argv)
