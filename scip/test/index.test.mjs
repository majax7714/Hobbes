import assert from 'node:assert/strict'
import { describe, it, test } from 'node:test'

import { spawnSync } from 'node:child_process'
import * as cfs from 'node:fs'
import pkg from '@sourcegraph/scip-typescript/dist/src/scip.js'
import * as cos from 'node:os'
import * as cpath from 'node:path'

import { INDEXER_EXIT,
  cCompdb,
  cPlan,
  decodeOptions,
  exitCodeFor,
  classify,
  commonDirectory,
  decode,
  degradations,
  implementsRows,
  dependencyCoverage,
  GRAPH_KINDS,
  INDEXERS,
  insideRepo,
  mergeUnitIndexes,
  streamDocuments,
  indexFiles,
  wellFormedIndex,
  documentCount,
  packageOf,
  PER_UNIT_MAX,
  splitCompdb,
  terminalName,
  indexerPlan,
  gradleAttachScript,
  javacInternals,
  resolvedPackages,
  HELPER_VERSION,
  factsLines,
  writeFacts,
} from '../index.mjs'

// Real monikers, pasted from scip-python 0.6.6 and scip-typescript 0.4.0
// output during the V2.M0 spike (ADR-027).
const PY = 'scip-python python hobbes 0 `src.hobbes.cli`'
const TS = 'scip-typescript npm betchat-frontend 1.0.0 src/api/`axios.ts`'
// scip-java's and scip-clang's shapes, from the Java cells (ADR-096) and
// the C lane B spike (scip-clang 0.4.0 on DaveGamble/cJSON).
const JAVA_OVERLOAD = 'scip-java maven maven/org.jsoup/jsoup 1.24.1-SNAPSHOT org/jsoup/Jsoup'
const CLANG = 'cxx . . $ '
// The bundled proto bindings, to write an index the way an indexer does.
const { scip } = pkg

test('descriptor kinds are read off real monikers', () => {
  assert.equal(classify(`${PY}/__init__:`), 'meta')
  assert.equal(classify(`${PY}/main().`), 'method')
  assert.equal(classify(`${PY}/main().(argv)`), 'parameter')
  assert.equal(classify(`${PY}/Thing#`), 'type')
  assert.equal(classify(`${PY}/CONSTANT.`), 'term')
  assert.equal(classify(`${TS}/`), 'namespace')
  assert.equal(classify('local 12'), 'local')
  // A method descriptor's disambiguator is any identifier (the SCIP spec).
  // scip-java writes an overload counter; scip-clang (0.4.0, the C lane B
  // spike on cJSON) writes a signature hash for every C function.
  assert.equal(classify(`${JAVA_OVERLOAD}#run(+1).`), 'method')
  assert.equal(classify(`${CLANG}cJSON_Delete(6efceb6909523ce2).`), 'method')
  assert.equal(classify(`${CLANG}cJSON_Delete(6efceb6909523ce2).(item)`), 'parameter')
})

test('only the four graph kinds survive the filter', () => {
  // ~86% of definitions are parameters, locals and meta (ADR-027).
  assert.ok(GRAPH_KINDS.has('method') && GRAPH_KINDS.has('type'))
  assert.ok(!GRAPH_KINDS.has('parameter'))
  assert.ok(!GRAPH_KINDS.has('local'))
  assert.ok(!GRAPH_KINDS.has('meta'))
})

test('packageOf reads manager and package, never the version', () => {
  assert.equal(packageOf(`${PY}/main().`), 'python:hobbes')
  assert.equal(packageOf(`${TS}/api.`), 'npm:betchat-frontend')
  assert.equal(packageOf('malformed'), '')
})

// A hand-built index in the shape scip.Index.deserialize produces, so the
// decode logic is testable without running an indexer.
function fakeIndex(documents) {
  return { documents, metadata: { project_root: 'file:///stage' } }
}
const DEF = 0x1 // scip.SymbolRole.Definition

test('definitions carry one-based lines and drop noise kinds', () => {
  const idx = fakeIndex([
    {
      relative_path: 'src/a.py',
      occurrences: [
        { symbol: `${PY}/run().`, symbol_roles: DEF, range: [4, 0, 8, 0] },
        { symbol: `${PY}/run().(x)`, symbol_roles: DEF, range: [4, 8, 4, 9] },
        { symbol: 'local 3', symbol_roles: DEF, range: [5, 4, 5, 5] },
      ],
    },
  ])
  const { definitions } = decode(idx)
  assert.equal(definitions.length, 1, 'parameter and local must be filtered out')
  assert.deepEqual(definitions[0], {
    moniker: `${PY}/run().`,
    file: 'src/a.py',
    line: 5, // SCIP is zero-based; the graph is one-based
    end_line: 9,
    kind: 'method',
  })
})

test('references to symbols defined outside the index are not edges', () => {
  const idx = fakeIndex([
    {
      relative_path: 'src/b.py',
      occurrences: [
        { symbol: 'scip-python python python-stdlib 3.11 os/getenv().', symbol_roles: 0, range: [1, 0, 1, 5] },
      ],
    },
  ])
  const { references, packages } = decode(idx)
  assert.equal(references.length, 0, 'stdlib is not a repo edge')
  assert.equal(packages.get('python:python-stdlib'), 1, 'but it is still counted')
})

test('an empty index is reported as degraded, not as an empty repo', () => {
  const idx = fakeIndex([])
  const out = degradations(idx, decode(idx), {})
  assert.ok(out.some((d) => d.stage === 'scip-index'))
})

test('resolving none of the declared dependencies is degradation', () => {
  // The kbet case: exit 0, a plausible index, every third-party edge gone.
  const idx = fakeIndex([
    {
      relative_path: 'src/a.ts',
      occurrences: [{ symbol: `${TS}/api.`, symbol_roles: DEF, range: [0, 0, 0, 3] }],
    },
  ])
  const out = degradations(idx, decode(idx), { declaredDeps: ['axios', 'react'] })
  assert.ok(out.some((d) => d.stage === 'scip-resolve'), 'must notice the gap')
})

test('resolving the declared dependencies is not degradation', () => {
  const idx = fakeIndex([
    {
      relative_path: 'src/a.ts',
      occurrences: [
        { symbol: `${TS}/api.`, symbol_roles: DEF, range: [0, 0, 0, 3] },
        { symbol: 'scip-typescript npm axios 1.0.0 `index.d.ts`/get().', symbol_roles: 0, range: [1, 0, 1, 3] },
      ],
    },
  ])
  const out = degradations(idx, decode(idx), { declaredDeps: ['axios'] })
  assert.equal(out.filter((d) => d.stage === 'scip-resolve').length, 0)
})

// ADR-032. The old test fired only when *every* declared dependency was
// missing, and scip-typescript bundles `typescript`, so that one
// always-resolving package held the condition false forever. Measured on
// kbet staged without node_modules: 1 of 23 resolved, nothing reported.
test("the indexer's own bundled package is not evidence of an environment", () => {
  const idx = fakeIndex([
    {
      relative_path: 'src/a.ts',
      occurrences: [
        { symbol: `${TS}/api.`, symbol_roles: DEF, range: [0, 0, 0, 3] },
        // What an index built with no node_modules is full of.
        { symbol: 'scip-typescript npm typescript 5.9.3 `lib.d.ts`/Array#', symbol_roles: 0, range: [1, 0, 1, 3] },
      ],
    },
  ])
  const declared = { declaredDeps: ['typescript', 'axios', 'react', 'zustand'] }
  const coverage = dependencyCoverage(decode(idx), declared)

  assert.equal(coverage.resolved, 0, 'typescript resolving proves nothing')
  // Excluded from the denominator too: nearly every TS repo declares
  // `typescript`, and a package that can never be credited must not be
  // reported missing either — that would be a permanent false alarm.
  assert.equal(coverage.declared, 3)
  assert.ok(!coverage.missing.includes('typescript'), 'never report the bundled package missing')
  assert.deepEqual(coverage.missing, ['axios', 'react', 'zustand'])

  const out = degradations(idx, decode(idx), declared)
  assert.ok(
    out.some((d) => d.stage === 'scip-resolve'),
    'a near-total resolution failure must be reported',
  )
})

test('dependency coverage is reported as counts, not only as a verdict', () => {
  // The ADR-029 denominator pattern: a repo half-resolved is not a
  // pass/fail, and the number is what a reviewer can act on.
  const idx = fakeIndex([
    {
      relative_path: 'src/a.ts',
      occurrences: [
        { symbol: `${TS}/api.`, symbol_roles: DEF, range: [0, 0, 0, 3] },
        { symbol: 'scip-typescript npm axios 1.0.0 `index.d.ts`/get().', symbol_roles: 0, range: [1, 0, 1, 3] },
      ],
    },
  ])
  const coverage = dependencyCoverage(decode(idx), { declaredDeps: ['axios', 'react'] })
  assert.deepEqual(coverage, { declared: 2, resolved: 1, missing: ['react'] })
})

test('python coverage matches names PEP-503-style, other languages verbatim', () => {
  // C-27's second half: the index resolved into PyYAML while the report
  // went on saying `pyyaml` was missing — distribution names are
  // case-insensitive with -/_/. equivalent, for Python only.
  const idx = fakeIndex([
    {
      relative_path: 'src/a.py',
      occurrences: [
        { symbol: `${PY}/api.`, symbol_roles: DEF, range: [0, 0, 0, 3] },
        { symbol: 'scip-python python PyYAML 6.0.1 `yaml`/load().', symbol_roles: 0, range: [1, 0, 1, 3] },
        { symbol: 'scip-python python tree_sitter 0.25.0 `tree_sitter`/Parser#', symbol_roles: 0, range: [2, 0, 2, 3] },
      ],
    },
  ])
  const py = dependencyCoverage(decode(idx), {
    language: 'python',
    declaredDeps: ['pyyaml', 'tree-sitter', 'httpx'],
  })
  assert.deepEqual(py, { declared: 3, resolved: 2, missing: ['httpx'] })
  // npm treats case and punctuation as identity: no normalisation there.
  const ts = dependencyCoverage(decode(idx), {
    language: 'typescript',
    declaredDeps: ['pyyaml'],
  })
  assert.deepEqual(ts.missing, ['pyyaml'])
})

test('python indexer args carry --environment only when one was computed', () => {
  // C-27: without it, scip-python asks the first pip3 on PATH which
  // environment exists and attributes third-party references to the
  // local project. With no listing the flag must be absent, not empty.
  const base = { stage: '/s', projectName: 'p', projectVersion: '0', output: '/o' }
  const with_ = INDEXERS.python.args({ ...base, environment: '/s.env.json' })
  assert.ok(with_.includes('--environment'))
  assert.equal(with_[with_.indexOf('--environment') + 1], '/s.env.json')
  const without = INDEXERS.python.args(base)
  assert.ok(!without.includes('--environment'))
})

test('terminalName reads the bare name a syntax provider would have seen', () => {
  assert.equal(terminalName(`${PY}/run().`), 'run')
  assert.equal(terminalName(`${PY}/Engine#run().`), 'run')
  assert.equal(terminalName(`${PY}/CONFIG.`), 'CONFIG')
  assert.equal(terminalName(`${PY}/Thing#`), 'Thing')
  assert.equal(terminalName(`${TS}/api.`), 'api')
  assert.equal(terminalName('nonsense'), '')
  // The disambiguator goes with the suffix. Kept, the name was
  // `cJSON_Delete(6efceb6909523ce2)`, and no C call site ever matched it.
  assert.equal(terminalName(`${JAVA_OVERLOAD}#run(+1).`), 'run')
  assert.equal(terminalName(`${CLANG}cJSON_Delete(6efceb6909523ce2).`), 'cJSON_Delete')
})

/** The last step of every C plan: a shell running scip-clang once per
 * one-entry database the check wrote (ADR-109 decision 1, amended). A
 * whole-database run indexes a shared header in whichever unit claims it
 * first, and that varies by run (C-149). */
function assertPerUnitIndexStep(step) {
  assert.equal(step.bin, 'sh', 'the units are driven from a shell, as bear over make is')
  assert.equal(step.cwd, '/s/cjson', 'scip-clang reports documents relative to its cwd, the root')
  assert.match(step.args[1], /xargs -P "\$2" -I@ scip-clang -j 1 /, 'one unit per run, the parallelism outside it')
  assert.match(step.args[1], /--compdb-path="\$1\/@\.json" --index-output-path="\$1\/@\.scip"/)
  assert.match(step.args[1], /exit 0$/, 'a unit that fails does not stop the others')
  assert.equal(step.args[3], '/s/o.scip.units', 'the unit databases sit beside the output, never in the stage')
  assert.ok(Number(step.args[4]) >= 1, "at most the box's parallelism at a time")
  assert.equal(typeof step.check, 'function', 'the database is checked, then split, before any indexing')
}

test('a C build root plans CMake or bear over make, then scip-clang once per unit (ADR-109)', () => {
  const base = { language: 'c', stage: '/s/cjson', output: '/s/o.scip', buildDir: '/s/b' }
  const cmake = cPlan({ ...base, compdbSource: 'cmake' })
  assert.deepEqual(cmake.steps.map((s) => s.bin), ['cmake', 'sh'])
  assert.deepEqual(cmake.steps[0].args, ['-S', '/s/cjson', '-B', '/s/b', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'])
  assertPerUnitIndexStep(cmake.steps[1])
  assert.equal(cmake.unitsDir, '/s/o.scip.units', 'the plan says where the units are, so the decode can read them')
  const make = cPlan({ ...base, compdbSource: 'make' })
  assert.deepEqual(make.steps.map((s) => s.bin), ['sh', 'sh'])
  assert.equal(make.steps[0].args[1], 'bear --output "$1" -- make -k; exit 0', "make's own exit decides nothing")
  assert.equal(make.steps[0].args[3], '/s/b/compile_commands.json')
  assert.equal(make.steps[0].check, undefined, 'the database is read by the step that indexes it, not before')
  assertPerUnitIndexStep(make.steps[1])
  const repo = cPlan({ ...base, compdbSource: 'repo', compdb: '/s/b/rebased.json' })
  assert.deepEqual(repo.steps.map((s) => s.bin), ['sh'], 'a carried database is split and indexed the same way')
  assertPerUnitIndexStep(repo.steps[0])
  assert.equal(cCompdb({ ...base, compdbSource: 'repo', compdb: '/s/b/rebased.json' }), '/s/b/rebased.json')
  assert.equal(indexerPlan({ ...base, compdbSource: 'cmake' }).steps.length, 2)
  assert.throws(() => cPlan({ ...base }), /no compile database source/)
})

test('the check writes one one-entry database per compile, numbered in database order (ADR-109)', () => {
  const dir = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-c-'))
  const entries = [
    { directory: dir, file: 'a.c', arguments: ['cc', '-c', 'a.c'] },
    { directory: dir, file: 'b.c', command: 'cc -c b.c' },
    { directory: dir, file: 'sub/c.c', arguments: ['cc', '-c', 'sub/c.c'], output: 'c.o' },
  ]
  assert.deepEqual(splitCompdb(entries).map((u) => u.name), ['0000', '0001', '0002'])
  assert.deepEqual(splitCompdb(entries).map((u) => u.entry), entries, 'each entry is the build\'s own record, verbatim')
  const plan = cPlan({ language: 'c', stage: dir, output: cpath.join(dir, 'o.scip'), buildDir: dir, compdbSource: 'make' })
  cfs.writeFileSync(cpath.join(dir, 'compile_commands.json'), JSON.stringify(entries))
  plan.steps[1].check({})
  assert.deepEqual(cfs.readdirSync(plan.unitsDir).sort(), ['0000.json', '0001.json', '0002.json'])
  assert.deepEqual(JSON.parse(cfs.readFileSync(cpath.join(plan.unitsDir, '0001.json'), 'utf8')), [entries[1]],
    'a one-entry database, holding that entry and nothing else')
})

test("the index step's shell indexes every unit and a unit that fails stops none of them (ADR-109)", () => {
  // The step run for real, against a stub that copies its one-entry
  // database to the index path it was given and fails on one unit the way
  // a scip-clang that cannot compile a translation unit does.
  const dir = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-c-'))
  const bin = cpath.join(dir, 'bin')
  cfs.mkdirSync(bin)
  cfs.writeFileSync(cpath.join(bin, 'scip-clang'), [
    '#!/bin/sh',
    'for a in "$@"; do case "$a" in',
    '  --compdb-path=*) db=${a#--compdb-path=};;',
    '  --index-output-path=*) out=${a#--index-output-path=};;',
    'esac; done',
    'case "$db" in *0001.json) echo "no rule to compile this unit" >&2; exit 1;; esac',
    'cat "$db" > "$out"',
  ].join('\n') + '\n', { mode: 0o755 })
  const plan = cPlan({ language: 'c', stage: dir, output: cpath.join(dir, 'o.scip'), buildDir: dir, compdbSource: 'repo', compdb: cpath.join(dir, 'compile_commands.json') })
  cfs.writeFileSync(cpath.join(dir, 'compile_commands.json'), JSON.stringify(
    ['a.c', 'b.c', 'c.c'].map((file) => ({ directory: dir, file, arguments: ['cc', '-c', file] }))))
  const step = plan.steps[0]
  step.check({})
  const proc = spawnSync('sh', step.args, { cwd: step.cwd, encoding: 'utf8', env: { ...process.env, PATH: `${bin}:${process.env.PATH}` } })
  assert.equal(proc.status, 0, 'the step exits 0 even though a unit failed; the merge counts what is missing')
  assert.deepEqual(cfs.readdirSync(plan.unitsDir).filter((f) => f.endsWith('.scip')).sort(), ['0000.scip', '0002.scip'])
  assert.deepEqual(JSON.parse(cfs.readFileSync(cpath.join(plan.unitsDir, '0002.scip'), 'utf8'))[0].file, 'c.c',
    'each run read its own one-entry database')
  assert.match(String(proc.stderr), /no rule to compile this unit/, "the failed unit's words reach the facts")
})

test("an empty compile database stops the plan before scip-clang, in the build's words", () => {
  const dir = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-c-'))
  const plan = cPlan({ language: 'c', stage: dir, output: cpath.join(dir, 'o.scip'), buildDir: dir, compdbSource: 'make' })
  cfs.writeFileSync(cpath.join(dir, 'compile_commands.json'), '[]')
  assert.throws(() => plan.steps[1].check({ stderr: 'make: *** No rule to make target' }),
    (err) => /bear over make produced no compile database entries.*No rule to make target/.test(err.message)
      && exitCodeFor(err) === INDEXER_EXIT)
  cfs.writeFileSync(cpath.join(dir, 'compile_commands.json'), JSON.stringify([{ directory: dir, file: 'a.c', arguments: ['cc', 'a.c'] }]))
  plan.steps[1].check({})
})

test('a compile database recorded entirely under cargo\'s registry says so, before scip-clang runs (C-135)', () => {
  const dir = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-c-'))
  const cargoHome = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-cargo-'))
  const savedCargoHome = process.env.CARGO_HOME
  process.env.CARGO_HOME = cargoHome
  try {
    const plan = cPlan({ language: 'c', stage: dir, output: cpath.join(dir, 'o.scip'), buildDir: dir, compdbSource: 'make' })
    const libbpf = cpath.join(cargoHome, 'registry', 'src', 'x', 'libbpf', 'src')
    cfs.writeFileSync(cpath.join(dir, 'compile_commands.json'), JSON.stringify([
      { directory: libbpf, file: 'btf.c', arguments: ['cc', 'btf.c'] },
      { directory: libbpf, file: 'bpf.c', arguments: ['cc', 'bpf.c'] },
    ]))
    assert.throws(() => plan.steps[1].check({ stderr: 'make: *** Error 1' }),
      (err) => /recorded 2 compile\(s\), none of a file under this root.*cargo's registry.*\(C-135\).*Error 1/s.test(err.message)
        && exitCodeFor(err) === INDEXER_EXIT, "the refusal is the build's outcome, so the helper exits INDEXER_EXIT")
  } finally {
    if (savedCargoHome === undefined) delete process.env.CARGO_HOME
    else process.env.CARGO_HOME = savedCargoHome
  }
})

test('a compile database recorded entirely elsewhere names their common directory (C-135)', () => {
  const dir = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-c-'))
  const plan = cPlan({ language: 'c', stage: dir, output: cpath.join(dir, 'o.scip'), buildDir: dir, compdbSource: 'make' })
  cfs.writeFileSync(cpath.join(dir, 'compile_commands.json'), JSON.stringify([
    { directory: '/opt/vendor/a', file: '/opt/vendor/a/x.c', arguments: ['cc', 'x.c'] },
    { directory: '/opt/vendor/b', file: '/opt/vendor/b/y.c', arguments: ['cc', 'y.c'] },
  ]))
  assert.throws(() => plan.steps[1].check({}), /recorded 2 compile\(s\), none of a file under this root.*\/opt\/vendor.*\(C-135\)/s)
})

test('a compile database with one entry under the root passes, even with another outside (C-135)', () => {
  const dir = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-c-'))
  const plan = cPlan({ language: 'c', stage: dir, output: cpath.join(dir, 'o.scip'), buildDir: dir, compdbSource: 'make' })
  cfs.writeFileSync(cpath.join(dir, 'compile_commands.json'), JSON.stringify([
    { directory: dir, file: 'a.c', arguments: ['cc', 'a.c'] },
    { directory: '/opt/vendor/a', file: '/opt/vendor/a/x.c', arguments: ['cc', 'x.c'] },
  ]))
  plan.steps[1].check({})
})

test('a compile database over the per-unit bound is written whole, and one under it one per unit (C-149)', () => {
  // The merge holds every unit's index at once: ScummVM's 5,958 units
  // projected to ~84 GB. Over the bound, one whole-database run instead.
  const dir = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-c-'))
  const plan = cPlan({ language: 'c', stage: dir, output: cpath.join(dir, 'o.scip'), buildDir: dir, compdbSource: 'make' })
  const entries = (n) => Array.from({ length: n }, (_, i) => ({ directory: dir, file: `u${i}.c`, arguments: ['cc', '-c', `u${i}.c`] }))
  cfs.writeFileSync(cpath.join(dir, 'compile_commands.json'), JSON.stringify(entries(PER_UNIT_MAX + 1)))
  plan.steps[1].check({})
  assert.deepEqual(cfs.readdirSync(plan.unitsDir), ['whole.json'], 'one database, not a split')
  assert.equal(JSON.parse(cfs.readFileSync(cpath.join(plan.unitsDir, 'whole.json'), 'utf8')).length, PER_UNIT_MAX + 1,
    'the whole database, verbatim')
  cfs.writeFileSync(cpath.join(dir, 'compile_commands.json'), JSON.stringify(entries(PER_UNIT_MAX)))
  plan.steps[1].check({})
  assert.equal(cfs.readdirSync(plan.unitsDir).length, PER_UNIT_MAX, 'at the bound itself, one database per unit')
  assert.ok(!cfs.existsSync(cpath.join(plan.unitsDir, 'whole.json')), "a previous run's whole database is gone")
})

test("the index step's shell runs one whole-database scip-clang over whole.json (C-149)", () => {
  const dir = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-c-'))
  const bin = cpath.join(dir, 'bin')
  cfs.mkdirSync(bin)
  const calls = cpath.join(dir, 'calls')
  cfs.writeFileSync(cpath.join(bin, 'scip-clang'), [
    '#!/bin/sh',
    `echo "$*" >> "${calls}"`,
    'for a in "$@"; do case "$a" in --index-output-path=*) out=${a#--index-output-path=};; esac; done',
    'echo indexed > "$out"',
  ].join('\n') + '\n', { mode: 0o755 })
  const plan = cPlan({ language: 'c', stage: dir, output: cpath.join(dir, 'o.scip'), buildDir: dir, compdbSource: 'repo', compdb: cpath.join(dir, 'compile_commands.json') })
  cfs.writeFileSync(cpath.join(dir, 'compile_commands.json'), JSON.stringify(
    Array.from({ length: PER_UNIT_MAX + 1 }, (_, i) => ({ directory: dir, file: `u${i}.c`, arguments: ['cc', '-c', `u${i}.c`] }))))
  const step = plan.steps[0]
  step.check({})
  const proc = spawnSync('sh', step.args, { cwd: step.cwd, encoding: 'utf8', env: { ...process.env, PATH: `${bin}:${process.env.PATH}` } })
  assert.equal(proc.status, 0)
  const lines = cfs.readFileSync(calls, 'utf8').trim().split('\n')
  assert.equal(lines.length, 1, 'one scip-clang run for the whole database')
  assert.doesNotMatch(lines[0], /-j 1/, "at scip-clang's own parallelism")
  assert.match(lines[0], /--compdb-path=\S*whole\.json --index-output-path=\S*whole\.scip/)
})

test('a whole-database run says so and names C-149; a per-unit run says nothing of it (C-149)', () => {
  const idx = fakeIndex([{ relative_path: 'a.c', occurrences: [] }])
  const said = (whole_database) => degradations(idx, { ...decode(idx), units: whole_database || 5, units_failed: 0, whole_database }, { language: 'cpp' })
    .filter((r) => /per-unit bound/.test(r.message))
  const [record] = said(5958)
  assert.equal(record.stage, 'scip-decode')
  assert.match(record.message, new RegExp(`holds 5958 translation units, over the per-unit bound \\(${PER_UNIT_MAX}\\)`))
  assert.match(record.message, /\(C-149\)$/)
  assert.deepEqual(said(0), [])
})

test('a relative file under the root passes the compile-database check (C-135)', () => {
  const dir = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-c-'))
  const plan = cPlan({ language: 'c', stage: dir, output: cpath.join(dir, 'o.scip'), buildDir: dir, compdbSource: 'make' })
  cfs.writeFileSync(cpath.join(dir, 'compile_commands.json'), JSON.stringify([
    { directory: dir, file: 'src/a.c', arguments: ['cc', 'src/a.c'] },
  ]))
  plan.steps[1].check({})
})

test('C decodes a macro by the name at its defining location, and a file-static in its own file (ADR-109)', () => {
  const stage = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-c-'))
  cfs.writeFileSync(cpath.join(stage, 'util.h'), '#ifndef U\n#define U\n#define TWICE(x) ((x) * 2)\n#endif\n')
  const opts = decodeOptions({ language: 'c', stage })
  assert.equal(opts.nameOf(`${CLANG}\`util.h:3:9\`!`), 'TWICE', 'scip-clang names a macro by where it is defined')
  assert.equal(opts.nameOf(`${CLANG}cJSON_Delete(6efceb6909523ce2).`), 'cJSON_Delete')
  assert.deepEqual(decodeOptions({ language: 'go', stage }), {}, 'no other language changes')
  const helper = `${CLANG}helper(1a35796978658aa4).`
  const idx = fakeIndex([
    { relative_path: 'a.c', occurrences: [
      { symbol: helper, symbol_roles: DEF, range: [2, 11, 2, 17] },
      { symbol: helper, symbol_roles: 0, range: [9, 4, 9, 10] },
    ] },
    { relative_path: 'b.c', occurrences: [
      { symbol: helper, symbol_roles: DEF, range: [5, 11, 5, 17] },
      { symbol: helper, symbol_roles: 0, range: [7, 4, 7, 10] },
    ] },
    { relative_path: 'c.c', occurrences: [{ symbol: helper, symbol_roles: 0, range: [1, 4, 1, 10] }] },
  ])
  assert.equal(decode(idx).references.length, 0, 'without the C rule, a moniker two files define is never attributed')
  const c = decode(idx, { ownFile: true })
  assert.deepEqual(c.references.map((r) => [r.file, r.line, r.def_file, r.def_line]),
    [['a.c', 10, 'a.c', 3], ['b.c', 8, 'b.c', 6]], "each file's reference resolves to its own static")
  assert.equal(c.external.filter((e) => e.file === 'c.c').length, 1, 'a file that does not define it stays unattributed')
  assert.deepEqual(c.ambiguous, [helper], 'the ambiguity is still reported (C-28)')
})

test('a C site that two translation units resolve differently keeps no lane B answer (ADR-109)', () => {
  // cJSON.c:612's `isinf`: cJSON's own macro in the library build, Unity's in
  // a test program that #includes cJSON.c. The merged index holds both.
  const own = `${CLANG}\`cJSON.c:74:9\`!`
  const unity = `${CLANG}\`unity.h:191:9\`!`
  const idx = fakeIndex([
    { relative_path: 'cJSON.c', occurrences: [
      { symbol: own, symbol_roles: DEF, range: [73, 8, 73, 13] },
      { symbol: own, symbol_roles: 0, range: [611, 20, 611, 25] },
      { symbol: unity, symbol_roles: 0, range: [611, 20, 611, 25] },
      { symbol: own, symbol_roles: 0, range: [700, 4, 700, 9] },
    ] },
    { relative_path: 'unity.h', occurrences: [{ symbol: unity, symbol_roles: DEF, range: [190, 8, 190, 13] }] },
  ])
  assert.equal(decode(idx).references.filter((r) => r.line === 612).length, 2, 'without the rule both answers stay')
  // The run reads both macros' names from the stage; here the name is given.
  const c = decode(idx, { nameOf: () => 'isinf', oneTargetPerSite: true })
  assert.deepEqual(c.references.map((r) => r.line), [701], 'the split site is dropped; a one-answer site stays')
  assert.equal(c.tu_split, 1)
  const [record] = degradations(idx, c, { language: 'c' }).filter((r) => /translation units/.test(r.message))
  assert.match(record.message, /^1 call site\(s\) resolve to different definitions in different translation units/)
})

test("one definition's own #if alternatives are one C target, kept once at the first line (ADR-109)", () => {
  // `CJSON_PUBLIC` is defined in several arms of cJSON.h, and the library
  // and the tests configure it differently. It is the same macro either way.
  const first = `${CLANG}\`cJSON.h:81:9\`!`
  const other = `${CLANG}\`cJSON.h:85:9\`!`
  const idx = fakeIndex([
    { relative_path: 'cJSON.h', occurrences: [
      { symbol: first, symbol_roles: DEF, range: [80, 8, 80, 20] },
      { symbol: other, symbol_roles: DEF, range: [84, 8, 84, 20] },
    ] },
    { relative_path: 'cJSON.c', occurrences: [
      { symbol: other, symbol_roles: 0, range: [99, 0, 99, 12] },
      { symbol: first, symbol_roles: 0, range: [99, 0, 99, 12] },
      { symbol: first, symbol_roles: 0, range: [99, 0, 99, 12] },
    ] },
  ])
  const c = decode(idx, { nameOf: () => 'CJSON_PUBLIC', oneTargetPerSite: true })
  assert.equal(c.tu_split, 0, 'one file is not a disagreement')
  assert.deepEqual(c.references.map((r) => [r.line, r.def_file, r.def_line]), [[100, 'cJSON.h', 81]])
})

test("a macro and its expansion's symbols at one position are different names, not a split (ADR-109)", () => {
  // scip-clang records `TEST_ASSERT_TRUE` and `UnityFail`, from its
  // expansion, at the call's own position. The first version of the rule
  // keyed on position alone and dropped 1,001 cJSON sites this way.
  const macro = `${CLANG}\`unity.h:121:9\`!`
  const fn = `${CLANG}UnityFail(0a1b2c3d4e5f6071).`
  const stage = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-c-'))
  cfs.writeFileSync(cpath.join(stage, 'unity.h'), '\n'.repeat(120) + '#define TEST_ASSERT_TRUE(c) UnityFail()\n')
  const { nameOf } = decodeOptions({ language: 'c', stage })
  const idx = fakeIndex([
    { relative_path: 'unity.h', occurrences: [{ symbol: macro, symbol_roles: DEF, range: [120, 8, 120, 24] }] },
    { relative_path: 'unity.c', occurrences: [{ symbol: fn, symbol_roles: DEF, range: [9, 5, 9, 14] }] },
    { relative_path: 't.c', occurrences: [
      { symbol: macro, symbol_roles: 0, range: [4, 4, 4, 20] },
      { symbol: fn, symbol_roles: 0, range: [4, 4, 4, 20] },
    ] },
  ])
  const c = decode(idx, { nameOf, oneTargetPerSite: true })
  assert.equal(c.tu_split, 0)
  assert.deepEqual(c.references.map((r) => [r.name, r.def_file]).sort(), [['TEST_ASSERT_TRUE', 'unity.h'], ['UnityFail', 'unity.c']])
})

// C++ is C's indexer with one decode rule of its own (ADR-113 §2, measured
// on the `minicpp` fixture): a construction site carries a reference to the
// class beside one to its constructor, and the constructor is the answer.
const CPP_CTOR = `${CLANG}shapes/Circle#Circle(3f1a2b3c4d5e6f70).`
const CPP_CLASS = `${CLANG}shapes/Circle#`

function constructionIndex(ctorRange, classRange) {
  return fakeIndex([
    { relative_path: 'shapes.h', occurrences: [
      { symbol: CPP_CLASS, symbol_roles: DEF, range: [15, 6, 24, 1] },
      { symbol: CPP_CTOR, symbol_roles: DEF, range: [17, 4, 17, 10] },
    ] },
    { relative_path: 'main.cpp', occurrences: [
      { symbol: CPP_CTOR, symbol_roles: 0, range: ctorRange },
      { symbol: CPP_CLASS, symbol_roles: 0, range: classRange },
    ] },
  ])
}

test('a C++ construction site keeps the constructor and drops its class (ADR-113)', () => {
  // `new Circle(1)`: scip-clang puts both references on the type name.
  const idx = constructionIndex([6, 21, 6, 27], [6, 21, 6, 27])
  assert.deepEqual(decode(idx, { oneTargetPerSite: true }).references.map((r) => r.def_line), [16],
    "without the rule the one-target reduction takes the smallest line — the class, which is what the read on `minicpp` found")
  const cpp = decode(idx, { oneTargetPerSite: true, constructorOverClass: true })
  assert.deepEqual(cpp.references.map((r) => [r.name, r.def_file, r.def_line]),
    [['Circle', 'shapes.h', 18]], 'the constructor, at its own line')
})

test('a C++ construction at two columns on one line is still one site (ADR-113)', () => {
  // `Circle c(3)`: the class at the type name, the constructor at the
  // declared variable. The site is a position *and a name*, and the join
  // keys the line — so the pair is read by line and name, not by column.
  const idx = constructionIndex([6, 20, 6, 21], [6, 12, 6, 18])
  const cpp = decode(idx, { oneTargetPerSite: true, constructorOverClass: true })
  assert.deepEqual(cpp.references.map((r) => [r.col, r.def_line]), [[20, 18]])
})

test('a C++ class referenced with no constructor beside it survives (ADR-113)', () => {
  // An implicit constructor is declared nowhere, so scip-clang writes the
  // type reference alone; dropping it would lose the site altogether.
  const idx = fakeIndex([
    { relative_path: 'shapes.h', occurrences: [
      { symbol: CPP_CLASS, symbol_roles: DEF, range: [15, 6, 24, 1] },
    ] },
    { relative_path: 'main.cpp', occurrences: [
      { symbol: CPP_CLASS, symbol_roles: 0, range: [6, 4, 6, 10] },
    ] },
  ])
  const cpp = decode(idx, { oneTargetPerSite: true, constructorOverClass: true })
  assert.deepEqual(cpp.references.map((r) => [r.name, r.def_line]), [['Circle', 16]])
})

test("a c config decodes the same construction as before: the rule is C++'s alone", () => {
  const idx = constructionIndex([6, 21, 6, 27], [6, 21, 6, 27])
  assert.equal(decode(idx).references.length, 2, 'the rule is off unless a config asks for it')
  const c = decode(idx, decodeOptions({ language: 'c', stage: '/nowhere' }))
  assert.deepEqual(c.references.map((r) => r.def_line), [16], "C's own answer, unchanged")
  assert.equal(decodeOptions({ language: 'c', stage: '/nowhere' }).constructorOverClass, undefined)
  assert.equal(decodeOptions({ language: 'cpp', stage: '/nowhere' }).constructorOverClass, true)
})

test('a cpp config plans bear or CMake exactly as a c one does (ADR-113)', () => {
  const config = { language: 'cpp', stage: '/s', output: '/s/o.scip', buildDir: '/b', compdbSource: 'make' }
  const shape = (plan) => plan.steps.map((s) => [s.bin, s.onPath, s.install, s.cwd, s.args])
  assert.deepEqual(shape(indexerPlan(config)), shape(indexerPlan({ ...config, language: 'c' })))
  assert.equal(indexerPlan(config).steps[0].bin, 'sh', 'bear over make, the C plan')
  assert.deepEqual(shape(indexerPlan({ ...config, compdbSource: 'cmake' })),
    shape(indexerPlan({ ...config, language: 'c', compdbSource: 'cmake' })))
  assert.equal(INDEXERS.cpp, INDEXERS.c, 'one indexer spec, not a copy that can drift')
})

test("the cpp duplicate-shape wording names namespaces as well as C's statics", () => {
  const idx = fakeIndex([
    { relative_path: 'a.cpp', occurrences: [{ symbol: `${CLANG}shapes/`, symbol_roles: DEF, range: [4, 10, 4, 16] }] },
    { relative_path: 'b.cpp', occurrences: [{ symbol: `${CLANG}shapes/`, symbol_roles: DEF, range: [2, 10, 2, 16] }] },
  ])
  const decoded = decode(idx, { oneTargetPerSite: true, constructorOverClass: true })
  const [record] = degradations(idx, decoded, { language: 'cpp' }).filter((r) => /defined in more than one/.test(r.message))
  assert.match(record.message, /a namespace is declared from every file that opens it/)
  assert.match(record.message, /file-`static`s of one signature/, "C's two shapes are still said")
})

// One moniker, several lines of one file (ADR-113 §2 amended, ADR-109
// decision 3): scip-clang lists those definitions in an order that varies
// by run — three fmt ingests at one commit drew three different edge
// counts — so the choice among them is made by rule here.
const CPP_OVERLOAD = `${CLANG}is_negative(ee44cd12ab34cd56).`

/** `is_negative` defined at format.h:10 and :20, listed either way, with
 * one reference to it. *order* is which line comes first. */
function multiLineIndex(order) {
  const defs = [
    { symbol: CPP_OVERLOAD, symbol_roles: DEF, range: [9, 5, 9, 16] },
    { symbol: CPP_OVERLOAD, symbol_roles: DEF, range: [19, 5, 19, 16] },
  ]
  return fakeIndex([
    { relative_path: 'format.h', occurrences: order === 'small-first' ? defs : [...defs].reverse() },
    { relative_path: 'main.cpp', occurrences: [{ symbol: CPP_OVERLOAD, symbol_roles: 0, range: [3, 8, 3, 19] }] },
  ])
}

test('a C moniker one file defines at two lines takes the smallest, in either order (ADR-109)', () => {
  const opts = decodeOptions({ language: 'c', stage: '/nowhere' })
  const small = decode(multiLineIndex('small-first'), opts)
  const large = decode(multiLineIndex('large-first'), opts)
  assert.deepEqual(small.references.map((r) => [r.def_file, r.def_line]), [['format.h', 10]],
    "ADR-109's first line, read as the smallest")
  assert.deepEqual(small, large, "the decode does not depend on scip-clang's listing order")
  assert.deepEqual(small.multi_defined, [], 'C picks; only C++ abstains')
})

test('C++ abstains on a moniker one file defines at two lines, in either order (ADR-113)', () => {
  // A class template and its specialisations, or `enable_if` overloads one
  // signature hash covers: different definitions under one moniker.
  const opts = decodeOptions({ language: 'cpp', stage: '/nowhere' })
  const small = decode(multiLineIndex('small-first'), opts)
  const large = decode(multiLineIndex('large-first'), opts)
  assert.deepEqual(small.references, [], 'no edge is guessed between them')
  assert.deepEqual(small.definitions, [], 'and the moniker keeps no definition')
  assert.deepEqual(small, large, "the decode does not depend on scip-clang's listing order")
  const [ref] = small.external.filter((e) => e.file === 'main.cpp')
  assert.equal(ref.in_repo, true, "in-repo, so it vetoes no lane A fallback (ADR-111)")
  const [record] = degradations(multiLineIndex('small-first'), small, { language: 'cpp' })
    .filter((r) => /more than one line of one file/.test(r.message))
  assert.match(record.message, /^1 symbol\(s\) are defined at more than one line of one file \(e\.g\. is_negative/)
  assert.match(record.message, /1 reference\(s\) to them are left without a lane B answer/)
})

test('a C++ namespace defined at two lines of one file is kept, at the smallest (ADR-113)', () => {
  // `namespace fmt { … }` reopened in one header. The abstention is for
  // graph kinds a call site can land on; a namespace keeps its line.
  const ns = `${CLANG}shapes/`
  const build = (order) => {
    const defs = [
      { symbol: ns, symbol_roles: DEF, range: [2, 10, 2, 16] },
      { symbol: ns, symbol_roles: DEF, range: [11, 10, 11, 16] },
    ]
    return fakeIndex([
      { relative_path: 'shapes.h', occurrences: order === 'small-first' ? defs : [...defs].reverse() },
      { relative_path: 'main.cpp', occurrences: [{ symbol: ns, symbol_roles: 0, range: [4, 0, 4, 6] }] },
    ])
  }
  const opts = decodeOptions({ language: 'cpp', stage: '/nowhere' })
  const small = decode(build('small-first'), opts)
  assert.deepEqual(small.definitions.map((d) => [d.kind, d.line]), [['namespace', 3]])
  assert.deepEqual(small.references.map((r) => r.def_line), [3])
  assert.deepEqual(small, decode(build('large-first'), opts))
})

// Python takes the same abstention for a reason of its own (ADR-150):
// scip-python names a def nested in a *method* by the class and its own
// name, dropping every function scope between them, so the `generate` two
// sibling methods each nest is one moniker over two definitions — flask's
// `TestStreaming` shape, where the smallest line answered a call in the
// other method's body.
const PY_MINI = 'scip-python python mini 0 '
const PY_NESTED = `${PY_MINI}t/T#generate().`
const PY_PLAIN = `${PY_MINI}t/T#run().`

/** `generate` defined at t.py:4 and :11 and referenced at :6, beside a
 * `run` one line defines and one line calls. *order* is which definition
 * of `generate` the document lists first. */
function pyMultiLineIndex(order) {
  const defs = [
    { symbol: PY_NESTED, symbol_roles: DEF, range: [3, 16, 3, 24] },
    { symbol: PY_NESTED, symbol_roles: DEF, range: [10, 16, 10, 24] },
  ]
  return fakeIndex([
    { relative_path: 't.py', occurrences: [
      ...(order === 'small-first' ? defs : [...defs].reverse()),
      { symbol: PY_NESTED, symbol_roles: 0, range: [5, 19, 5, 27] },
      { symbol: PY_PLAIN, symbol_roles: DEF, range: [14, 8, 14, 11] },
      { symbol: PY_PLAIN, symbol_roles: 0, range: [17, 20, 17, 23] },
    ] },
  ])
}

test('Python abstains on a moniker one file defines at two lines, in either order (ADR-150)', () => {
  const opts = decodeOptions({ language: 'python', stage: '/nowhere' })
  assert.deepEqual(opts, { abstainMultiDefined: true }, "Python takes none of C's rules")
  const small = decode(pyMultiLineIndex('small-first'), opts)
  const large = decode(pyMultiLineIndex('large-first'), opts)
  assert.deepEqual(small, large, "the decode does not depend on scip-python's listing order")
  assert.deepEqual(small.multi_defined, [PY_NESTED], 'the shared moniker is the abstained one')
  assert.equal(small.multi_defined_refs, 1, 'and the reference to it is counted')
  assert.deepEqual(small.definitions.map((d) => [d.moniker, d.line]), [[PY_PLAIN, 15]],
    'no definition is kept for the shared moniker; the single one is untouched')
  assert.deepEqual(small.references.map((r) => [r.line, r.def_line]), [[18, 15]],
    'only the single definition answers a site')
  const [ref] = small.external.filter((e) => e.moniker === PY_NESTED)
  assert.equal(ref.line, 6)
  assert.equal(ref.in_repo, true, 'in-repo, so it vetoes no lane A fallback (ADR-111)')
})

test("the Python degradation record names scip-python's shape, not scip-clang's (ADR-150)", () => {
  const idx = pyMultiLineIndex('small-first')
  const decoded = decode(idx, decodeOptions({ language: 'python', stage: '/nowhere' }))
  const [record] = degradations(idx, decoded, { language: 'python' })
    .filter((r) => /more than one line of one file/.test(r.message))
  assert.equal(record.stage, 'scip-decode')
  assert.match(record.message, /^1 symbol\(s\) are defined at more than one line of one file \(e\.g\. t\/T#generate\(\)\./)
  assert.match(record.message, /scip-python names a def nested in a method/)
  assert.match(record.message, /1 reference\(s\) to them are left without a lane B answer/)
  assert.match(record.message, /\(ADR-150, C-170\)$/)
  assert.doesNotMatch(record.message, /scip-clang/, "C++'s reason is not Python's")
  // scip-python 0.6.6 emits one definition for a property's getter and
  // setter, an @overload's stubs and an if/else def (read in the image), so
  // none of them is a multi-defined moniker and the record names none.
  assert.doesNotMatch(record.message, /overload|setter/, 'only the shapes scip-python actually merges')
})

test('a Python namespace defined at two lines of one file is kept, at the smallest (ADR-150)', () => {
  // The abstention is for the graph kinds a call site can land on; a
  // namespace keeps its line, as it does under C++.
  const ns = `${PY_MINI}t/`
  const build = (order) => {
    const defs = [
      { symbol: ns, symbol_roles: DEF, range: [1, 0, 1, 1] },
      { symbol: ns, symbol_roles: DEF, range: [8, 0, 8, 1] },
    ]
    return fakeIndex([
      { relative_path: 't.py', occurrences: order === 'small-first' ? defs : [...defs].reverse() },
      { relative_path: 'u.py', occurrences: [{ symbol: ns, symbol_roles: 0, range: [0, 7, 0, 8] }] },
    ])
  }
  const opts = decodeOptions({ language: 'python', stage: '/nowhere' })
  const small = decode(build('small-first'), opts)
  assert.deepEqual(small.definitions.map((d) => [d.kind, d.line]), [['namespace', 2]])
  assert.deepEqual(small.references.map((r) => r.def_line), [2])
  assert.deepEqual(small.multi_defined, [], 'a namespace is no abstention')
  assert.deepEqual(small, decode(build('large-first'), opts))
})

test("the own-file map takes that file's smallest line for a colliding static (ADR-109)", () => {
  // `helper` is a file-static of two files — so the reference resolves
  // through `byFile` — and its own file defines it at two lines.
  const helper = `${CLANG}helper(1a35796978658aa4).`
  const build = (order) => {
    const defs = [
      { symbol: helper, symbol_roles: DEF, range: [2, 11, 2, 17] },
      { symbol: helper, symbol_roles: DEF, range: [8, 11, 8, 17] },
    ]
    return fakeIndex([
      { relative_path: 'a.c', occurrences: [
        ...(order === 'small-first' ? defs : [...defs].reverse()),
        { symbol: helper, symbol_roles: 0, range: [20, 4, 20, 10] },
      ] },
      { relative_path: 'b.c', occurrences: [{ symbol: helper, symbol_roles: DEF, range: [5, 11, 5, 17] }] },
    ])
  }
  const opts = decodeOptions({ language: 'c', stage: '/nowhere' })
  const small = decode(build('small-first'), opts)
  assert.deepEqual(small.references.map((r) => [r.file, r.def_file, r.def_line]), [['a.c', 'a.c', 3]])
  assert.deepEqual(small, decode(build('large-first'), opts))
})

test('a moniker defined once, or in two files, decodes as it did under both C configs', () => {
  const helper = `${CLANG}helper(1a35796978658aa4).`
  const solo = `${CLANG}solo(2b46807a89769bb5).`
  const idx = fakeIndex([
    { relative_path: 'a.c', occurrences: [
      { symbol: helper, symbol_roles: DEF, range: [2, 11, 2, 17] },
      { symbol: solo, symbol_roles: DEF, range: [11, 4, 11, 8] },
      { symbol: helper, symbol_roles: 0, range: [9, 4, 9, 10] },
    ] },
    { relative_path: 'b.c', occurrences: [
      { symbol: helper, symbol_roles: DEF, range: [5, 11, 5, 17] },
      { symbol: solo, symbol_roles: 0, range: [7, 4, 7, 8] },
    ] },
  ])
  for (const language of ['c', 'cpp']) {
    const out = decode(idx, decodeOptions({ language, stage: '/nowhere' }))
    assert.deepEqual(out.definitions.map((d) => [d.file, d.line]), [['a.c', 12]],
      `${language}: the two-file moniker is dropped, the single one kept`)
    assert.deepEqual(out.references.map((r) => [r.file, r.line, r.def_file, r.def_line]),
      [['a.c', 10, 'a.c', 3], ['b.c', 8, 'a.c', 12]], `${language}: the own-file static, and the plain call`)
    assert.deepEqual(out.ambiguous, [helper], `${language}: the ambiguity is still reported (C-28)`)
    assert.deepEqual(out.multi_defined, [], `${language}: nothing abstained`)
  }
})

// One site, several monikers (ADR-113 §2 amended a third time, measured on
// the fmt and args cells): where a call sits in a template scip-clang cannot
// resolve, it references every candidate at the call's own position. The
// one-target rule read those as one definition's `#if` alternatives and kept
// the smallest line, which answered whichever overload the call meant — 36
// wrong semantic edges on fmt, all 4 of args' contradictions.
const CPP_WRITE2_A = `${CLANG}tm_writer#write2(d4f7abc123456789).`
const CPP_WRITE2_B = `${CLANG}tm_writer#write2(fc4f9876543210ab).`

/** `write2` defined at chrono.h:1133 and :1138 under *two* monikers, both
 * referenced at chrono.h:1348 — fmt's own shape. */
function overloadSiteIndex() {
  return fakeIndex([
    { relative_path: 'include/fmt/chrono.h', occurrences: [
      { symbol: CPP_WRITE2_A, symbol_roles: DEF, range: [1132, 7, 1132, 13] },
      { symbol: CPP_WRITE2_B, symbol_roles: DEF, range: [1137, 7, 1137, 13] },
      { symbol: CPP_WRITE2_A, symbol_roles: 0, range: [1347, 6, 1347, 12] },
      { symbol: CPP_WRITE2_B, symbol_roles: 0, range: [1347, 6, 1347, 12] },
    ] },
  ])
}

test('a C++ site whose references name two overloads of one name draws no reference (ADR-113)', () => {
  const cpp = decode(overloadSiteIndex(), decodeOptions({ language: 'cpp', stage: '/nowhere' }))
  assert.deepEqual(cpp.references, [], 'neither candidate is the answer, so the site abstains')
  assert.equal(cpp.overload_sites, 1)
  assert.deepEqual(cpp.overload_examples, [{ name: 'write2', file: 'include/fmt/chrono.h', line: 1348 }])
  assert.deepEqual(cpp.definitions.map((d) => d.line), [1133, 1138], 'both overloads keep their symbols')
  const [record] = degradations(overloadSiteIndex(), cpp, { language: 'cpp' })
    .filter((r) => /more than one overload/.test(r.message))
  assert.match(record.message, /^1 call site\(s\) name more than one overload of one name \(e\.g\. `write2` at include\/fmt\/chrono\.h:1348\)/)
  assert.match(record.message, /scip-clang lists the candidates of a call it cannot resolve there/)
  assert.match(record.message, /dropped rather than the first line taken \(ADR-113 §2, C-151\)/)
})

test('the same index under C keeps the smallest line: the rule is C++\'s alone (ADR-109)', () => {
  const c = decode(overloadSiteIndex(), decodeOptions({ language: 'c', stage: '/nowhere' }))
  assert.deepEqual(c.references.map((r) => [r.line, r.def_line]), [[1348, 1133]],
    "C's several lines are one moniker's `#if` alternatives, and it still picks")
  assert.equal(c.overload_sites, 0)
  assert.deepEqual(degradations(overloadSiteIndex(), c, { language: 'c' })
    .filter((r) => /more than one overload/.test(r.message)), [], 'and says nothing')
})

test('a C++ site with several references to one moniker keeps one of them (ADR-113)', () => {
  // The ordinary macro-and-expansion shape: one name, one answer, arriving
  // once per unit. Only *several monikers* is an overload set.
  const one = `${CLANG}tm_writer#write2(d4f7abc123456789).`
  const idx = fakeIndex([
    { relative_path: 'include/fmt/chrono.h', occurrences: [
      { symbol: one, symbol_roles: DEF, range: [1132, 7, 1132, 13] },
      { symbol: one, symbol_roles: 0, range: [1347, 6, 1347, 12] },
      { symbol: one, symbol_roles: 0, range: [1347, 6, 1347, 12] },
      { symbol: one, symbol_roles: 0, range: [1347, 6, 1347, 12] },
    ] },
  ])
  const cpp = decode(idx, decodeOptions({ language: 'cpp', stage: '/nowhere' }))
  assert.deepEqual(cpp.references.map((r) => [r.line, r.def_line]), [[1348, 1133]])
  assert.equal(cpp.overload_sites, 0, 'nothing abstained')
  assert.deepEqual(degradations(idx, cpp, { language: 'cpp' })
    .filter((r) => /more than one overload/.test(r.message)), [], 'no site, no record')
})

// One translation unit per scip-clang run (ADR-109 decision 1, amended):
// every unit indexes its own copy of the headers it includes, and the
// helper decodes the units' indexes as one. The shared header arrives once
// per unit, so what the merge must answer is what the units disagree
// about — which is what `decode`'s rules already answer.
const MERGED_MACRO_OPTS = { nameOf: () => 'SCALE', oneTargetPerSite: true, ownFile: true }

/** Two unit indexes of one header, `util.h`, whose `SCALE` each unit
 * resolves into its own `.c` — the real cross-unit disagreement. */
function unitPair() {
  const fromA = `${CLANG}\`a.c:5:9\`!`
  const fromB = `${CLANG}\`b.c:7:9\`!`
  return [
    fakeIndex([
      { relative_path: 'a.c', occurrences: [{ symbol: fromA, symbol_roles: DEF, range: [4, 8, 4, 13] }] },
      { relative_path: 'util.h', occurrences: [{ symbol: fromA, symbol_roles: 0, range: [9, 4, 9, 9] }] },
    ]),
    fakeIndex([
      { relative_path: 'b.c', occurrences: [{ symbol: fromB, symbol_roles: DEF, range: [6, 8, 6, 13] }] },
      { relative_path: 'util.h', occurrences: [{ symbol: fromB, symbol_roles: 0, range: [9, 4, 9, 9] }] },
    ]),
  ]
}

test('a site two units answer into different files is dropped in the merged decode, either order (ADR-109)', () => {
  const [a, b] = unitPair()
  const ab = decode(mergeUnitIndexes([a, b]), MERGED_MACRO_OPTS)
  const ba = decode(mergeUnitIndexes([b, a]), MERGED_MACRO_OPTS)
  assert.deepEqual(ab.references, [], "lane B has no one answer, so the site keeps lane A's floor")
  assert.equal(ab.tu_split, 1)
  assert.deepEqual([ba.references, ba.tu_split], [ab.references, ab.tu_split],
    'the answer does not depend on which unit the merge read first')
})

test('a header both units answer the same way is one reference row in the merged decode (ADR-109)', () => {
  // The common case per-unit indexing creates: every unit that includes a
  // header indexes it, so the same site arrives once per unit.
  const emit = `${CLANG}emit(aaaa1111bbbb2222).`
  const unit = () => fakeIndex([
    { relative_path: 'shared.h', occurrences: [{ symbol: emit, symbol_roles: DEF, range: [4, 5, 4, 9] }] },
    { relative_path: 'util.h', occurrences: [{ symbol: emit, symbol_roles: 0, range: [9, 4, 9, 8] }] },
  ])
  const merged = mergeUnitIndexes([unit(), unit()])
  assert.equal([...merged.documents()].length, 4, 'the merge concatenates, it does not deduplicate')
  const out = decode(merged, decodeOptions({ language: 'c', stage: '/nowhere' }))
  assert.deepEqual(out.references.map((r) => [r.file, r.line, r.def_file, r.def_line]), [['util.h', 10, 'shared.h', 5]])
  assert.deepEqual(out.definitions.map((d) => [d.file, d.line]), [['shared.h', 5]], 'one definition, not one per unit')
})

test('a C++ moniker two units define at two lines of one file abstains, as in one index (ADR-113)', () => {
  // `#if` alternatives of one header, each unit configured its own way.
  const sym = `${CLANG}is_negative(ee44cd12ab34cd56).`
  const unit = (line) => fakeIndex([
    { relative_path: 'format.h', occurrences: [{ symbol: sym, symbol_roles: DEF, range: [line, 5, line, 16] }] },
    { relative_path: 'main.cpp', occurrences: [{ symbol: sym, symbol_roles: 0, range: [3, 8, 3, 19] }] },
  ])
  const opts = decodeOptions({ language: 'cpp', stage: '/nowhere' })
  const out = decode(mergeUnitIndexes([unit(9), unit(19)]), opts)
  assert.deepEqual(out.multi_defined, [sym], 'two definitions under one moniker, in one file')
  assert.deepEqual(out.references, [], 'no edge is guessed between them')
  assert.equal(out.external.filter((e) => e.file === 'main.cpp')[0].in_repo, true)
})

test('a quarter of a million references decode without overflowing the stack (ADR-109)', () => {
  // The merged size a per-unit run reaches: 484,201 references on fmt.
  // `references.push(...kept)` spread them into arguments and threw.
  const emit = `${CLANG}emit(aaaa1111bbbb2222).`
  const occurrences = [{ symbol: emit, symbol_roles: DEF, range: [0, 5, 0, 9] }]
  for (let line = 1; line <= 250_000; line++) {
    occurrences.push({ symbol: emit, symbol_roles: 0, range: [line, 4, line, 8] })
  }
  const out = decode(fakeIndex([{ relative_path: 'a.c', occurrences }]), decodeOptions({ language: 'c', stage: '/nowhere' }))
  assert.equal(out.references.length, 250_000, 'and every one is kept')
})

test('a translation unit that failed to index is counted, and nothing is said when none failed (ADR-109)', () => {
  const idx = fakeIndex([{ relative_path: 'a.c', occurrences: [] }])
  const failed = (units_failed) => degradations(idx, { ...decode(idx), units: 5, units_failed }, { language: 'c' })
    .filter((r) => /translation unit\(s\) failed/.test(r.message))
  const [record] = failed(1)
  assert.equal(record.stage, 'scip-decode')
  assert.equal(record.message,
    "1 of 5 translation unit(s) failed to index; the others stand, and the failed units' " +
    "sites fall to lane A's fallback (ADR-109)")
  assert.deepEqual(failed(0), [], 'a run whose every unit indexed says nothing')
})

test('references carry the column and name the join needs', () => {
  const idx = fakeIndex([
    {
      relative_path: 'src/a.py',
      occurrences: [{ symbol: `${PY}/run().`, symbol_roles: DEF, range: [4, 0, 8, 0] }],
    },
    {
      relative_path: 'src/b.py',
      occurrences: [{ symbol: `${PY}/run().`, symbol_roles: 0, range: [2, 17, 2, 20] }],
    },
  ])
  assert.deepEqual(decode(idx).references, [
    { file: 'src/b.py', line: 3, col: 17, name: 'run', def_file: 'src/a.py', def_line: 5 },
  ])
})

// V2.M5 (ADR-037): scip-go emits documents for the Go build cache, whose
// paths escape the repo — `../../.cache/go-build/f1/f12bb…-d`. A join that
// trusts `relative_path` invents nodes for files the user has never seen.

test('insideRepo accepts an ordinary repo-relative path', () => {
  assert.equal(insideRepo('cmd/hobbes-policy/main.go'), true)
  assert.equal(insideRepo('main.go'), true)
})

test('insideRepo rejects paths that climb out of the repo', () => {
  assert.equal(insideRepo('../../.cache/go-build/f1/f12bb51-d'), false)
  assert.equal(insideRepo('go/../../elsewhere/x.go'), false)
})

test('insideRepo rejects absolute paths and nothing', () => {
  assert.equal(insideRepo('/etc/passwd'), false)
  assert.equal(insideRepo(''), false)
  assert.equal(insideRepo(undefined), false)
})

test('decode drops documents outside the repo entirely', () => {
  const GO = 'scip-go gomod example.com/x 0 `example.com/x`'
  const idx = fakeIndex([
    {
      relative_path: 'main.go',
      occurrences: [{ symbol: `${GO}/Run().`, symbol_roles: DEF, range: [4, 0, 8, 0] }],
    },
    {
      // The build cache: real occurrences, not this repo's files.
      relative_path: '../../.cache/go-build/f1/f12bb51-d',
      occurrences: [{ symbol: `${GO}/Run().`, symbol_roles: 0, range: [2, 3, 2, 6] }],
    },
  ])
  const out = decode(idx)
  assert.equal(out.definitions.length, 1)
  // The cached document's reference must not become an edge, and must not
  // be counted as external either — it is not a fact about this repo.
  assert.deepEqual(out.references, [])
  assert.deepEqual(out.external, [])
})

// --- V2.M7: Rust via rust-analyzer's native SCIP export (ADR-040) -------

// Real monikers, pasted from rust-analyzer 1.97.1 output during the
// spike-rust.mjs run on ~/rust_proj.
const RS = 'rust-analyzer cargo example_project_structure 0.1.0'
const RS_STD = 'rust-analyzer cargo std https://github.com/rust-lang/rust/library/std'

test('macro descriptors classify as macro and survive the filter', () => {
  // Without this, a repo-defined macro_rules! never enters the
  // definitions map and every invocation of it drops to external_refs.
  assert.equal(classify(`${RS_STD} macros/println!`), 'macro')
  assert.equal(classify(`${RS} twice!`), 'macro')
  assert.ok(GRAPH_KINDS.has('macro'))
})

test('terminalName strips the macro bang', () => {
  // Lane A's call site says `println`, not `println!` — the two providers
  // must speak the same name or the range join matches nothing.
  assert.equal(terminalName(`${RS_STD} macros/println!`), 'println')
  assert.equal(terminalName(`${RS} twice!`), 'twice')
})

test('the rust indexer entry runs rust-analyzer scip with no version flag', () => {
  // The moniker version is the crate's Cargo.toml version, not the git
  // revision (spike-rust.mjs) — the one indexer where Decision 1 needs
  // no pin, so the argv must not invent one.
  const argv = INDEXERS.rust.args({ stage: '/stage', output: '/out.scip' })
  assert.deepEqual(argv, ['scip', '/stage', '--output', '/out.scip'])
  assert.ok(INDEXERS.rust.onPath, 'a rustup component, not an npm dev dep')
})

test('a moniker defined in two files is ambiguous, dropped, and reported', () => {
  // rust-analyzer emits the same `crate/` and `main().` for every cargo
  // target of a package (its own "Duplicate symbol" warning). First-wins
  // would attribute a `use mylib` in a test to whichever binary decode
  // saw first — a false edge, worse than a missing one (ADR-007).
  const idx = fakeIndex([
    {
      relative_path: 'src/main.rs',
      occurrences: [
        { symbol: `${RS} crate/`, symbol_roles: DEF, range: [0, 0, 38, 0] },
      ],
    },
    {
      relative_path: 'src/lib.rs',
      occurrences: [
        { symbol: `${RS} crate/`, symbol_roles: DEF, range: [0, 0, 4, 1] },
        { symbol: `${RS} really_complicated_code().`, symbol_roles: DEF, range: [2, 7, 2, 30] },
      ],
    },
    {
      relative_path: 'tests/it.rs',
      occurrences: [
        { symbol: `${RS} crate/`, symbol_roles: 0, range: [0, 4, 0, 9] },
        { symbol: `${RS} really_complicated_code().`, symbol_roles: 0, range: [4, 22, 4, 45] },
      ],
    },
  ])
  const decoded = decode(idx)
  assert.deepEqual(decoded.ambiguous, [`${RS} crate/`])
  assert.ok(
    !decoded.definitions.some((d) => d.moniker === `${RS} crate/`),
    'the ambiguous definition must not survive under either file',
  )
  // Its reference is unattributed, not guessed.
  assert.ok(decoded.external.some((e) => e.file === 'tests/it.rs' && e.line === 1))
  // The unambiguous symbol still resolves normally.
  assert.equal(decoded.references.length, 1)
  assert.equal(decoded.references[0].def_file, 'src/lib.rs')
  // And the drop is visible, never silent (P6).
  const out = degradations(idx, decoded, {})
  assert.ok(out.some((d) => d.stage === 'scip-decode' && /more than one/.test(d.message)))
  // Which files, so the record can be scoped (ADR-091, D7).
  assert.deepEqual(decoded.ambiguous_files, { [`${RS} crate/`]: ['src/lib.rs', 'src/main.rs'] })
})

test('the duplicate-symbol record is scoped to its files and worded per lane (ADR-091, D7)', () => {
  // sklearn's doc/tutorial/text_analytics/{skeletons,solutions}/ both
  // define exercise_01_language_train_model; the record rode every unit
  // brief with `path: "."` and Rust's "cargo targets" wording.
  const PY = 'scip-python python sklearn 1.0'
  const idx = fakeIndex([
    {
      relative_path: 'doc/tutorial/text_analytics/skeletons/exercise_01_language_train_model.py',
      occurrences: [{ symbol: `${PY} exercise_01_language_train_model/cm.`, symbol_roles: DEF, range: [0, 0, 0, 2] }],
    },
    {
      relative_path: 'doc/tutorial/text_analytics/solutions/exercise_01_language_train_model.py',
      occurrences: [{ symbol: `${PY} exercise_01_language_train_model/cm.`, symbol_roles: DEF, range: [0, 0, 0, 2] }],
    },
    { relative_path: 'sklearn/base.py', occurrences: [] },
  ])
  const decoded = decode(idx)
  const dup = (out) => out.find((x) => /more than one/.test(x.message))
  const d = dup(degradations(idx, decoded, { language: 'python' }))
  assert.equal(d.stage, 'scip-decode')
  assert.equal(d.path, 'doc/tutorial/text_analytics')
  assert.match(d.message, /skeletons\/ and solutions\//)
  assert.doesNotMatch(d.message, /cargo/)
  const r = dup(degradations(idx, decoded, { language: 'rust' }))
  assert.match(r.message, /cargo targets/)
  assert.equal(commonDirectory(['a/b/x.py', 'c/y.py']), '.')
  assert.equal(commonDirectory(['a/b/x.py', 'a/b/y.py']), 'a/b')
  assert.equal(commonDirectory([]), '.')
})

test('an external ref keeps its moniker for the cross-unit join (v3, ADR-049)', () => {
  // "External" means external to this index; a sibling indexing unit of
  // the same repo may define exactly this moniker, and the join after
  // the per-unit merge matches on it. Without the field C-33 was
  // unfixable in principle.
  const OTHER = 'scip-go gomod dagger.io/dagger 0 `dagger.io/dagger`/Hello().'
  const idx = fakeIndex([
    {
      relative_path: 'main.go',
      occurrences: [{ symbol: OTHER, symbol_roles: 0, range: [5, 5, 5, 10] }],
    },
  ])
  const out = decode(idx)
  assert.equal(out.external.length, 1)
  assert.equal(out.external[0].moniker, OTHER)
})

test('an external reference is marked in_repo when the repo defines its moniker anyway (ADR-111)', () => {
  // Two shapes miss `definitions` for a reason other than "outside the
  // repo": a moniker two in-repo files define (ambiguous, C-28) and a
  // moniker of a kind the graph does not keep (here, a parameter). Both
  // must be marked so the join never vetoes lane A's fallback there —
  // only a reference genuinely outside the repo (stdlib) may.
  const idx = fakeIndex([
    {
      relative_path: 'src/main.rs',
      occurrences: [
        { symbol: `${RS} crate/`, symbol_roles: DEF, range: [0, 0, 38, 0] },
        { symbol: `${RS} run().(x)`, symbol_roles: DEF, range: [1, 4, 1, 5] },
      ],
    },
    {
      relative_path: 'src/lib.rs',
      occurrences: [{ symbol: `${RS} crate/`, symbol_roles: DEF, range: [0, 0, 4, 1] }],
    },
    {
      relative_path: 'tests/it.rs',
      occurrences: [
        { symbol: `${RS} crate/`, symbol_roles: 0, range: [0, 4, 0, 9] },
        { symbol: `${RS} run().(x)`, symbol_roles: 0, range: [2, 0, 2, 1] },
        { symbol: `${RS_STD} macros/println!`, symbol_roles: 0, range: [3, 0, 3, 7] },
      ],
    },
  ])
  const out = decode(idx)
  const byLine = (n) => out.external.find((e) => e.file === 'tests/it.rs' && e.line === n)
  assert.equal(byLine(1).in_repo, true, 'ambiguous in two in-repo files: marked')
  assert.equal(byLine(3).in_repo, true, 'a parameter: the graph drops the kind, not the repo')
  assert.equal(byLine(4).in_repo, undefined, 'stdlib: genuinely outside the repo')
})

test("rust's toolchain stdlib is not evidence of an environment", () => {
  // std/core/alloc resolve from the rustup sysroot whatever the repo's
  // dependencies look like — the scip-go lesson, a language later.
  const idx = fakeIndex([
    {
      relative_path: 'src/lib.rs',
      occurrences: [
        { symbol: `${RS} run().`, symbol_roles: DEF, range: [0, 0, 0, 3] },
        { symbol: `${RS_STD} macros/println!`, symbol_roles: 0, range: [1, 0, 1, 7] },
      ],
    },
  ])
  const coverage = dependencyCoverage(decode(idx), {
    declaredDeps: ['serde'],
    language: 'rust',
  })
  assert.equal(coverage.resolved, 0, 'std resolving proves nothing')
  assert.deepEqual(coverage.missing, ['serde'])
})

test('impl-scoped method monikers yield the bare method name', () => {
  // Found by the rust_proj verification: the bracketed self type rode the
  // final segment, so `Counter::new()` at a call site never matched the
  // resolution's name and every in-repo method edge was silently lost.
  assert.equal(terminalName(`${RS} impl#[Counter]new().`), 'new')
  assert.equal(
    terminalName(
      'rust-analyzer cargo core https://github.com/rust-lang/rust/library/core result/impl#[`Result<T, E>`]unwrap().',
    ),
    'unwrap',
  )
})

// scip-java 0.13.1 shapes, pasted from the J.M0 spike on jsoup (ADR-096).
const JAVA = 'scip-java maven maven/org.jsoup/jsoup 1.24.1-SNAPSHOT'

test('java overload descriptors classify as methods and yield the bare name', () => {
  assert.equal(classify(`${JAVA} org/jsoup/parser/ParseError#toString().`), 'method')
  assert.equal(classify(`${JAVA} org/jsoup/helper/Regex#compile(+1).`), 'method')
  assert.equal(terminalName(`${JAVA} org/jsoup/helper/Regex#compile(+1).`), 'compile')
  assert.equal(terminalName(`${JAVA} org/jsoup/nodes/Document#OutputSettings#Syntax#`), 'Syntax')
})

test('a java constructor is named after its type, as the call site spells it', () => {
  assert.equal(classify(`${JAVA} org/jsoup/helper/Regex#\`<init>\`(+2).`), 'method')
  assert.equal(terminalName(`${JAVA} org/jsoup/helper/Regex#\`<init>\`().`), 'Regex')
  assert.equal(terminalName(`${JAVA} org/jsoup/helper/Regex#JdkMatcher#\`<init>\`(+1).`), 'JdkMatcher')
})

test('the java indexer runs scip-java through the derived build tool (maven: its own route)', () => {
  const c = { stage: '/s', output: '/o.scip', buildTool: 'maven' }
  const args = INDEXERS.java.args(c)
  assert.equal(INDEXERS.java.bin, 'scip-java')
  assert.ok(INDEXERS.java.onPath)
  assert.deepEqual(args.slice(0, 4), ['index', '--build-tool=maven', '--output', '/o.scip'])
  assert.ok(args.includes('test-compile') && !args.includes('verify'))
  assert.ok(args.includes('-o'), 'the maven index pass is offline — resolution ran first (ADR-097)')
  assert.equal(INDEXERS.java.cwd(c), '/s')
  const plan = indexerPlan({ ...c, language: 'java' })
  assert.equal(plan.steps.length, 1)
  assert.equal(plan.steps[0].bin, 'scip-java')
})

// C-67: a Gradle build gets scip-java's plugin from Hobbes's own init
// script — the wrapper offline under it, then the aggregator — never
// from scip-java's Gradle plugin, which a build that has resolved
// compileOnly at evaluation time refuses.
test('a gradle unit is indexed by the wrapper under the attach script, then aggregated', () => {
  const plan = indexerPlan({ language: 'java', stage: '/s', output: '/out/u.scip', buildTool: 'gradle' })
  assert.equal(plan.steps.length, 2)
  const [build, aggregate] = plan.steps
  assert.equal(build.bin, 'sh')
  assert.equal(build.cwd, '/s')
  assert.deepEqual(build.args.slice(0, 3), ['./gradlew', '--no-daemon', '--offline'])
  assert.equal(build.args[3], '--init-script')
  assert.equal(build.args[4], '/out/u.scip.hobbes-scip.gradle', 'the script lives beside the output, never in the stage')
  assert.deepEqual(build.args.slice(5), ['clean', 'compileTestJava', 'hobbesScipDependencies'])
  assert.equal(typeof plan.resolved, 'function', 'what the build resolved is read before cleanup')
  assert.equal(aggregate.bin, 'scip-java')
  assert.deepEqual(aggregate.args, ['aggregate', '--output', '/out/u.scip', '--targetroot', '/out/u.scip.targetroot'])
  assert.equal(typeof aggregate.check, 'function', 'an empty targetroot is named before the aggregator runs')
  assert.equal(typeof plan.prepare, 'function')
  assert.equal(typeof plan.cleanup, 'function')
})

test('the attach script puts the plugin on the processor path with its add-exports, never on a configuration', () => {
  const text = gradleAttachScript({
    stage: '/s', targetroot: '/out/u.scip.targetroot', jar: '/usr/local/lib/scip-java/scip-javac.jar',
    jvmArgs: ['--add-exports=jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED', '--add-exports=jdk.compiler/com.sun.tools.javac.tree=ALL-UNNAMED'],
  })
  assert.ok(text.includes("tasks.withType(JavaCompile).configureEach"))
  assert.ok(text.includes("options.annotationProcessorPath = jar + (options.annotationProcessorPath ?: files())"))
  assert.ok(text.includes("def jar = files('/usr/local/lib/scip-java/scip-javac.jar')"))
  assert.ok(text.includes("options.compilerArgs += ['-Xplugin:scip -sourceroot:/s -targetroot:/out/u.scip.targetroot']"))
  assert.ok(text.includes("options.fork = true"))
  assert.ok(text.includes("'--add-exports=jdk.compiler/com.sun.tools.javac.tree=ALL-UNNAMED'"))
  assert.ok(text.includes('options.incremental = false'))
  assert.ok(!/compileOnly|dependencies\s*\{/.test(text), 'no configuration is touched')
  assert.ok(text.includes("tasks.register('hobbesScipDependencies')"))
  assert.ok(text.includes("new File('/out/u.scip.targetroot', 'dependencies.txt')"))
  assert.ok(text.includes('lenientConfiguration.artifacts'))
})

test('the coverage line under the gradle route is answered from what the build resolved', () => {
  const text = 'org.joml\tjoml\t1.10.8\t/cache/joml-1.10.8.jar\ncom.opencsv\topencsv\t5.9\t/cache/opencsv-5.9.jar\norg.joml\tjoml\t1.10.8\t/cache/joml-1.10.8.jar\n\nbad line\n'
  assert.deepEqual(resolvedPackages(text), ['maven:maven/com.opencsv/opencsv', 'maven:maven/org.joml/joml'])
  assert.deepEqual(resolvedPackages(''), [])
  const decoded = { packages: new Map() }
  const config = { language: 'java', declaredDeps: ['maven/org.joml', 'maven/com.opencsv', 'maven/org.json'] }
  assert.deepEqual(dependencyCoverage(decoded, config), { declared: 3, resolved: 0, missing: ['maven/org.joml', 'maven/com.opencsv', 'maven/org.json'] })
  assert.deepEqual(dependencyCoverage(decoded, config, resolvedPackages(text)), { declared: 3, resolved: 2, missing: ['maven/org.json'] })
})

test('the add-exports list is read from the file scip-java ships, continuation lines and all', () => {
  const text = '# JVM flags required by scip-javac\njavac.jvmOptions=\\\n--add-exports=jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED,\\\n--add-exports=jdk.compiler/com.sun.tools.javac.util=ALL-UNNAMED\n'
  assert.deepEqual(javacInternals(text), [
    '--add-exports=jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED',
    '--add-exports=jdk.compiler/com.sun.tools.javac.util=ALL-UNNAMED',
  ])
  assert.throws(() => javacInternals('nothing=here\n'), /javac\.jvmOptions/)
})

test("the jdk and the dot package are not evidence of an environment (java)", () => {
  const decoded = { packages: new Map([['maven:jdk', 10], ['maven:.', 5], ['maven:maven/org.junit.jupiter/junit-jupiter-api', 3]]) }
  const cov = dependencyCoverage(decoded, {
    language: 'java',
    declaredDeps: ['maven/org.junit.jupiter/junit-jupiter', 'maven/org.assertj/assertj-core'],
  })
  // Matched at the group: the aggregator artifact resolves to its siblings.
  assert.deepEqual(cov, { declared: 2, resolved: 1, missing: ['maven/org.assertj/assertj-core'] })
})

/** A SCIP index written field by field with google-protobuf's writer:
 * `Index.documents` (2), each with `relative_path` (1) and `occurrences`
 * (2). *write* fills one occurrence. */
async function writtenIndex(documents) {
  const pb = (await import('google-protobuf')).default
  const w = new pb.BinaryWriter()
  for (const [path, occurrences] of documents) {
    w.writeMessage(2, {}, () => {
      w.writeString(1, path)
      for (const write of occurrences) w.writeMessage(2, {}, () => write(w))
    })
  }
  return w.getResultBuffer()
}

test('typed ranges (SCIP fields 8 and 9) are read into the range shape', async () => {
  const bytes = await writtenIndex([
    ['a/B.java', [
      (w) => {
        w.writeString(2, 'scip-java maven . . a/B#m().')
        w.writeInt32(3, 1)
        w.writeMessage(8, {}, () => { w.writeInt32(1, 4); w.writeInt32(2, 7); w.writeInt32(3, 11) })
      },
      (w) => {
        w.writeString(2, 'x')
        w.writeMessage(9, {}, () => { w.writeInt32(1, 4); w.writeInt32(2, 7); w.writeInt32(3, 6); w.writeInt32(4, 2) })
      },
      // The deprecated field still reads, so the other indexers are untouched.
      (w) => { w.writeString(2, 'y'); w.writePackedInt32(1, [1, 2, 3]) },
      // An unpacked writer sends one varint per element.
      (w) => { w.writeString(2, 'z'); w.writeInt32(1, 5); w.writeInt32(1, 6); w.writeInt32(1, 7) },
    ]],
  ])
  const [doc] = [...streamDocuments(bytes)]
  assert.equal(doc.relative_path, 'a/B.java')
  const [single, multi, packed, unpacked] = doc.occurrences
  assert.deepEqual(single, { range: [4, 7, 11], symbol: 'scip-java maven . . a/B#m().', symbol_roles: 1 })
  assert.deepEqual(multi.range, [4, 7, 6, 2])
  assert.deepEqual(packed.range, [1, 2, 3])
  assert.deepEqual(unpacked.range, [5, 6, 7])
})

test('a streamed index decodes exactly as its literal twin, and is walked afresh each pass (ADR-115)', async () => {
  // The decode reads an index twice — definitions, then references — so
  // a streamed source must yield the same documents on every walk.
  const run = `${PY}/run().`
  const literal = fakeIndex([
    { relative_path: 'src/a.py', occurrences: [{ symbol: run, symbol_roles: DEF, range: [4, 0, 8, 0] }] },
    { relative_path: 'src/b.py', occurrences: [
      { symbol: run, symbol_roles: 0, range: [2, 4, 2, 7] },
      { symbol: 'scip-python python requests 2.0 `requests`/get().', symbol_roles: 0, range: [3, 0, 3, 3] },
      { symbol: 'local 1', symbol_roles: DEF, range: [5, 0, 5, 1] },
    ] },
  ])
  const bytes = await writtenIndex(literal.documents.map((d) => [d.relative_path, d.occurrences.map((o) => (w) => {
    w.writePackedInt32(1, o.range); w.writeString(2, o.symbol); w.writeInt32(3, o.symbol_roles)
  })]))
  const dir = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-stream-'))
  const path = cpath.join(dir, 'u.scip')
  cfs.writeFileSync(path, bytes)
  const streamed = indexFiles([path])
  const out = decode(streamed)
  assert.deepEqual(out, decode(literal))
  assert.equal(out.references.length, 1)
  assert.equal(out.external.length, 1)
  assert.equal(documentCount(streamed), 2)
  assert.deepEqual(degradations(streamed, out, {}), degradations(literal, decode(literal), {}))
})

test('indexFiles streams several unit files in order, one file at a time (ADR-115)', async () => {
  const dir = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-units-'))
  const paths = []
  for (const name of ['0000', '0001']) {
    const path = cpath.join(dir, `${name}.scip`)
    cfs.writeFileSync(path, await writtenIndex([[`${name}.c`, [(w) => { w.writeString(2, 'x'); w.writePackedInt32(1, [0, 0, 0, 1]) }]]]))
    paths.push(path)
  }
  const source = indexFiles(paths)
  assert.deepEqual([...source.documents()].map((d) => d.relative_path), ['0000.c', '0001.c'])
  assert.equal(source.count, 2)
  assert.deepEqual([...source.documents()].map((d) => d.relative_path), ['0000.c', '0001.c'], 'the second walk is the same')
  const merged = mergeUnitIndexes([source, fakeIndex([{ relative_path: 'lit.c', occurrences: [] }])])
  assert.deepEqual([...merged.documents()].map((d) => d.relative_path), ['0000.c', '0001.c', 'lit.c'])
  assert.equal(documentCount(merged), 3)
})

test('a unit whose output is not a SCIP index is told from one that is (ADR-115)', async () => {
  assert.equal(wellFormedIndex(Buffer.alloc(0)), false, 'a scip-clang run that wrote nothing')
  assert.equal(wellFormedIndex(Buffer.from('not an index at all, 0xff 0xff')), false)
  assert.equal(wellFormedIndex(Buffer.from([0xff, 0xff, 0xff])), false, 'a truncated tag')
  assert.equal(wellFormedIndex(await writtenIndex([['a.c', []]])), true)
})

test("an indexer's own exit is a distinct helper exit code", () => {
  // C-85 / C-74: the helper ran and the indexer died — recorded by the
  // Python side as the indexer's failure, never as a missing helper.
  const died = Object.assign(new Error('scip-python exited 1'), { indexerExit: 1 })
  assert.equal(exitCodeFor(died), INDEXER_EXIT)
  assert.equal(exitCodeFor(new Error('no indexer configured')), 1)
  assert.notEqual(INDEXER_EXIT, 1)
  assert.notEqual(INDEXER_EXIT, 2)
})

// ADR-116: the facts are JSON lines — a header, one record per document, a
// trailer that counts them — because the whole document is one V8 string, and
// V8's longest (536,870,888 characters) is shorter than ScummVM's facts.
const FACTS = () => ({
  helper_version: HELPER_VERSION,
  language: 'cpp',
  definitions: [{ moniker: 'm', file: 'b.h', line: 1, end_line: 2, kind: 'type' }],
  references: [
    { file: 'a.cc', line: 3, col: 1, name: 'f', def_file: 'b.h', def_line: 1 },
    { file: 'b.h', line: 5, col: 2, name: 'g', def_file: 'b.h', def_line: 1 },
    { file: 'a.cc', line: 3, col: 9, name: 'f', def_file: 'b.h', def_line: 1 },
  ],
  external_refs: [{ file: 'c.cc', line: 1, col: 0, name: 'printf', package: 'libc', moniker: 'x' }],
  implements: [{ file: 'a.cc', line: 8, def_file: 'b.h', def_line: 1 }],
  implements_outside: 2,
  implements_unplaced: 0,
  implements_undirected: 0,
  packages: { libc: 1 },
  degraded: [],
  stderr: '',
})

test('factsLines: a header, one record per document in first-row order, rows in decode order, a counting trailer', () => {
  const lines = [...factsLines(FACTS())].map((line) => JSON.parse(line))
  assert.deepEqual(lines[0], { helper_version: HELPER_VERSION, language: 'cpp' })
  // Definitions are read first, so b.h (a definition's file) leads.
  assert.deepEqual(lines.slice(1, -1).map((doc) => doc.file), ['b.h', 'a.cc', 'c.cc'])
  assert.deepEqual(lines[2], {
    file: 'a.cc',
    definitions: [],
    references: [
      { line: 3, col: 1, name: 'f', def_file: 'b.h', def_line: 1 },
      { line: 3, col: 9, name: 'f', def_file: 'b.h', def_line: 1 },
    ],
    external_refs: [],
    // ADR-120 (helper version 5): the override set is the fourth row kind.
    implements: [{ line: 8, def_file: 'b.h', def_line: 1 }],
  })
  assert.deepEqual(lines.at(-1), {
    end: true, documents: 3, definitions: 1, references: 3, external_refs: 1, implements: 1,
    implements_outside: 2, implements_unplaced: 0, implements_undirected: 0,
    packages: { libc: 1 }, degraded: [], stderr: '',
  })
})

test('factsLines: facts with no implements at all still count them as zero', () => {
  const { implements: _drop, ...older } = FACTS()
  const lines = [...factsLines(older)].map((line) => JSON.parse(line))
  assert.equal(lines.at(-1).implements, 0)
  assert.deepEqual(lines[1].implements, [])
})

// --- ADR-120: the override set, from SymbolInformation.relationships ------
//
// Measured on the six indexers (2026-09-16): scip-clang, scip-go,
// scip-typescript and scip-python state a pair on the implementor only;
// scip-java states it and its reverse on an abstract or interface method;
// rust-analyzer states none.
const JV = 'scip-java maven maven/com.example/minijava 0.1.0'
const def = (symbol, line) => ({ symbol, symbol_roles: DEF, range: [line - 1, 0, line - 1, 5] })

function implementsIndex(docs) {
  return fakeIndex(docs)
}

test('implements: a pair between two in-repo definitions is a row from the implementor to the implemented', () => {
  const idx = implementsIndex([
    {
      relative_path: 'src/union.ts',
      occurrences: [def(`${TS}/Base#`, 8), def(`${TS}/Base#render().`, 9), def(`${TS}/Alpha#`, 12), def(`${TS}/Alpha#render().`, 13)],
      symbols: [
        { symbol: `${TS}/Alpha#`, implements: [`${TS}/Base#`] },
        { symbol: `${TS}/Alpha#render().`, implements: [`${TS}/Base#render().`] },
      ],
    },
  ])
  const out = decode(idx)
  assert.deepEqual(out.implements, [
    { file: 'src/union.ts', line: 12, def_file: 'src/union.ts', def_line: 8 },
    { file: 'src/union.ts', line: 13, def_file: 'src/union.ts', def_line: 9 },
  ])
  assert.deepEqual(
    [out.implements_outside, out.implements_unplaced, out.implements_undirected],
    [0, 0, 0],
  )
})

test('implements: a target outside the index is counted, never drawn; a local source is skipped', () => {
  const GO = 'scip-go gomod github.com/x/y 0 `github.com/x/y/p`'
  const idx = implementsIndex([
    {
      relative_path: 'p/a.go',
      occurrences: [def(`${GO}/Buf#`, 3), def(`${GO}/Buf#Write().`, 5)],
      symbols: [
        { symbol: `${GO}/Buf#`, implements: ['scip-go gomod github.com/golang/go/src go1.24 io/Writer#'] },
        { symbol: `${GO}/Buf#Write().`, implements: ['scip-go gomod github.com/golang/go/src go1.24 io/Writer#Write().'] },
        { symbol: 'local 4', implements: [`${GO}/Buf#`] },
        // A parameter is no graph definition: unplaced, and said so.
        { symbol: `${GO}/Buf#Write().(p)`, implements: [`${GO}/Buf#`] },
      ],
    },
  ])
  const out = decode(idx)
  assert.deepEqual(out.implements, [])
  assert.equal(out.implements_outside, 2)
  assert.equal(out.implements_unplaced, 1)
})

test("implements: scip-java's reverse row on the interface method is oriented by the type level and dropped", () => {
  const idx = implementsIndex([
    {
      relative_path: 'Shape.java',
      occurrences: [def(`${JV} com/example/app/Shape#`, 4), def(`${JV} com/example/app/Shape#area().`, 5)],
      symbols: [{ symbol: `${JV} com/example/app/Shape#area().`, implements: [`${JV} com/example/app/Circle#area().`] }],
    },
    {
      relative_path: 'Circle.java',
      occurrences: [def(`${JV} com/example/app/Circle#`, 3), def(`${JV} com/example/app/Circle#area().`, 11)],
      symbols: [
        { symbol: `${JV} com/example/app/Circle#`, implements: [`${JV} com/example/app/Shape#`] },
        { symbol: `${JV} com/example/app/Circle#area().`, implements: [`${JV} com/example/app/Shape#area().`] },
      ],
    },
  ])
  const out = decode(idx)
  assert.deepEqual(out.implements, [
    { file: 'Circle.java', line: 3, def_file: 'Shape.java', def_line: 4 },
    { file: 'Circle.java', line: 11, def_file: 'Shape.java', def_line: 5 },
  ])
  assert.equal(out.implements_undirected, 0)
})

test('implements: a chain orients a method overridden two levels up', () => {
  // C extends B extends A; C#m overrides A#m. The class row names the
  // direct base, the method row the declaring class (javac, scip-clang).
  const rows = (name, line) => [def(`${JV} p/${name}#`, line), def(`${JV} p/${name}#m().`, line + 1)]
  const idx = implementsIndex([
    {
      relative_path: 'P.java',
      occurrences: [...rows('A', 1), ...rows('B', 10), ...rows('C', 20)],
      symbols: [
        { symbol: `${JV} p/A#m().`, implements: [`${JV} p/C#m().`] },
        { symbol: `${JV} p/B#`, implements: [`${JV} p/A#`] },
        { symbol: `${JV} p/C#`, implements: [`${JV} p/B#`] },
        { symbol: `${JV} p/C#m().`, implements: [`${JV} p/A#m().`] },
      ],
    },
  ])
  const out = decode(idx)
  assert.deepEqual(
    out.implements.map((r) => [r.line, r.def_line]),
    [[10, 1], [20, 10], [21, 2]],
  )
})

test('implements: a mutual pair nothing orients is dropped both ways and counted', () => {
  const idx = implementsIndex([
    {
      relative_path: 'P.java',
      occurrences: [def(`${JV} p/A#m().`, 1), def(`${JV} p/B#m().`, 5)],
      symbols: [
        { symbol: `${JV} p/A#m().`, implements: [`${JV} p/B#m().`] },
        { symbol: `${JV} p/B#m().`, implements: [`${JV} p/A#m().`] },
      ],
    },
  ])
  const out = decode(idx)
  assert.deepEqual(out.implements, [])
  assert.equal(out.implements_undirected, 1)
  const said = degradations(idx, out, { language: 'java' })
  assert.ok(said.some((d) => /stated in both directions/.test(d.message)))
})

test('implements: a pair scip-clang states once per translation unit is one row, in a fixed order', () => {
  const docs = [
    {
      relative_path: 'shapes.h',
      occurrences: [def(`${CLANG}shapes/Shape#`, 3), def(`${CLANG}shapes/Circle#`, 9)],
      symbols: [{ symbol: `${CLANG}shapes/Circle#`, implements: [`${CLANG}shapes/Shape#`] }],
    },
    {
      relative_path: 'shapes.h',
      occurrences: [def(`${CLANG}shapes/Shape#`, 3), def(`${CLANG}shapes/Circle#`, 9)],
      symbols: [{ symbol: `${CLANG}shapes/Circle#`, implements: [`${CLANG}shapes/Shape#`] }],
    },
  ]
  const forward = decode(implementsIndex(docs)).implements
  const backward = decode(implementsIndex([...docs].reverse())).implements
  assert.deepEqual(forward, [{ file: 'shapes.h', line: 9, def_file: 'shapes.h', def_line: 3 }])
  assert.deepEqual(backward, forward)
})

test('implements: a document from outside the repo states nothing', () => {
  const idx = implementsIndex([
    {
      relative_path: '../../.cache/go-build/x.go',
      occurrences: [def(`${TS}/A#`, 1), def(`${TS}/B#`, 2)],
      symbols: [{ symbol: `${TS}/A#`, implements: [`${TS}/B#`] }],
    },
  ])
  assert.deepEqual(implementsRows(idx, new Map()).implements, [])
})

test('implements: every Rust run says rust-analyzer states no override set (C-157)', () => {
  const idx = implementsIndex([
    { relative_path: 'src/lib.rs', occurrences: [def(`${RS} lib/Counter#`, 1)], symbols: [] },
  ])
  const rust = degradations(idx, decode(idx), { language: 'rust' })
  assert.ok(rust.some((d) => /C-157/.test(d.message) && /no `relationships`/.test(d.message)))
  const go = degradations(idx, decode(idx), { language: 'go' })
  assert.ok(!go.some((d) => /C-157/.test(d.message)))
})

test('the real proto reader decodes SymbolInformation.relationships (is_implementation only)', () => {
  // Built with the bundled proto bindings, as an indexer would write it.
  const index = new scip.Index({
    metadata: new scip.Metadata({ project_root: 'file:///stage' }),
    documents: [
      new scip.Document({
        relative_path: 'src/a.ts',
        occurrences: [
          new scip.Occurrence({ symbol: `${TS}/Base#`, symbol_roles: DEF, range: [0, 0, 4] }),
          new scip.Occurrence({ symbol: `${TS}/Alpha#`, symbol_roles: DEF, range: [5, 0, 5] }),
        ],
        symbols: [
          new scip.SymbolInformation({
            symbol: `${TS}/Alpha#`,
            relationships: [
              new scip.Relationship({ symbol: `${TS}/Base#`, is_implementation: true }),
              // A reference-only relationship is not an override.
              new scip.Relationship({ symbol: `${TS}/Other#`, is_reference: true }),
            ],
          }),
        ],
      }),
    ],
  })
  const [doc] = [...streamDocuments(index.serialize())]
  assert.deepEqual(doc.symbols, [{ symbol: `${TS}/Alpha#`, implements: [`${TS}/Base#`] }])
  const out = decode({ documents: [doc] })
  assert.deepEqual(out.implements, [{ file: 'src/a.ts', line: 6, def_file: 'src/a.ts', def_line: 1 }])
})

test('writeFacts writes one line per record, each ending in a newline', () => {
  const dir = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'facts-'))
  try {
    const path = cpath.join(dir, 's.facts.ndjson')
    writeFacts(FACTS(), path)
    const text = cfs.readFileSync(path, 'utf8')
    assert.ok(text.endsWith('\n'))
    assert.deepEqual(
      text.trimEnd().split('\n').map((line) => JSON.parse(line)),
      [...factsLines(FACTS())].map((line) => JSON.parse(line)),
    )
  } finally {
    cfs.rmSync(dir, { recursive: true, force: true })
  }
})

test('the helper prints nothing on stdout and refuses a config that names no facts file', () => {
  const dir = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'facts-'))
  try {
    const config = cpath.join(dir, 'c.json')
    cfs.writeFileSync(config, JSON.stringify({ language: 'python', stage: dir }))
    const helper = new URL('../index.mjs', import.meta.url).pathname
    const proc = spawnSync(process.execPath, [helper, '--config', config], { encoding: 'utf8' })
    assert.equal(proc.status, 1)
    assert.equal(proc.stdout, '')
    assert.match(proc.stderr, /names no `facts` file/)
  } finally {
    cfs.rmSync(dir, { recursive: true, force: true })
  }
})

// --- ADR-144: a reference to a shorthand property ----------------------
//
// `const m = require('./m'); m.f()` over `module.exports = { f }`. At the
// member token the index names the *property* of the exported literal, and
// the property's one definition occurrence sits at the shorthand's token —
// the same range that carries the reference to the function. Every shape
// but that one stays what it is today.

describe('a shorthand property is an alias of what it names (ADR-144)', () => {
  // The fixture's shape, in scip-typescript's own moniker form: the second
  // literal in the file is why the exported one is `alpha1:`.
  const JS = 'scip-typescript npm minicjs 0.0.0 lib/`tools.js`/'
  const ALPHA = `${JS}alpha().`
  const BETA = `${JS}beta().`
  const PROPERTY = `${JS}alpha1:`
  const DEFINED_AT = [2, 9, 4, 1] // `function alpha() {…}`
  const SHORTHAND = [8, 21, 8, 26] // `module.exports = { alpha }`
  const USE = [3, 8, 3, 13] // `tools.alpha()` in test/use.js
  const defined = { symbol: ALPHA, symbol_roles: DEF, range: DEFINED_AT }
  const use = (symbol) => ({
    relative_path: 'test/use.js',
    occurrences: [{ symbol, symbol_roles: 0, range: USE }],
  })

  it('emits the reference onto the function, and no external row for it', () => {
    const out = decode(fakeIndex([
      {
        relative_path: 'lib/tools.js',
        occurrences: [
          defined,
          // A shorthand is both of these, at one range.
          { symbol: PROPERTY, symbol_roles: DEF, range: SHORTHAND },
          { symbol: ALPHA, symbol_roles: 0, range: SHORTHAND },
        ],
      },
      use(PROPERTY),
    ]))
    assert.deepEqual(out.references.find((r) => r.file === 'test/use.js'), {
      file: 'test/use.js',
      line: 4,
      col: 8,
      name: 'alpha', // the function's name, never the property's `alpha1`
      def_file: 'lib/tools.js',
      def_line: 3,
    })
    assert.deepEqual(out.external, [], 'nothing of this is external any more')
    assert.equal(out.shorthand_refs, 1)
  })

  it('refuses a value property, whose value sits at another range', () => {
    // `delta: alpha` — the reference to `alpha` is at the value token, not
    // at the property's. Unmeasured, and so not taken (ADR-144).
    const DELTA = `${JS}delta0:`
    const out = decode(fakeIndex([
      {
        relative_path: 'lib/tools.js',
        occurrences: [
          defined,
          { symbol: DELTA, symbol_roles: DEF, range: [9, 2, 9, 7] },
          { symbol: ALPHA, symbol_roles: 0, range: [9, 9, 9, 14] },
        ],
      },
      use(DELTA),
    ]))
    assert.deepEqual(out.references.filter((r) => r.file === 'test/use.js'), [])
    const [external] = out.external.filter((r) => r.file === 'test/use.js')
    assert.deepEqual(external, {
      file: 'test/use.js',
      line: 4,
      col: 8,
      name: 'delta0',
      package: 'npm:minicjs',
      moniker: DELTA,
      in_repo: true, // ADR-111: it vetoes no lane A fallback
    })
    assert.equal(out.shorthand_refs, 0)
  })

  it('refuses a range that names two symbols with definitions', () => {
    const out = decode(fakeIndex([
      {
        relative_path: 'lib/tools.js',
        occurrences: [
          defined,
          { symbol: BETA, symbol_roles: DEF, range: [6, 9, 7, 1] },
          { symbol: PROPERTY, symbol_roles: DEF, range: SHORTHAND },
          { symbol: ALPHA, symbol_roles: 0, range: SHORTHAND },
          { symbol: BETA, symbol_roles: 0, range: SHORTHAND },
        ],
      },
      use(PROPERTY),
    ]))
    assert.deepEqual(out.references.filter((r) => r.file === 'test/use.js'), [])
    assert.equal(out.external.filter((r) => r.file === 'test/use.js').length, 1)
    assert.equal(out.shorthand_refs, 0)
  })

  it('refuses a property with more than one definition occurrence', () => {
    const AGAIN = [11, 4, 11, 9]
    const out = decode(fakeIndex([
      {
        relative_path: 'lib/tools.js',
        occurrences: [
          defined,
          { symbol: PROPERTY, symbol_roles: DEF, range: SHORTHAND },
          { symbol: ALPHA, symbol_roles: 0, range: SHORTHAND },
          { symbol: PROPERTY, symbol_roles: DEF, range: AGAIN },
          { symbol: ALPHA, symbol_roles: 0, range: AGAIN },
        ],
      },
      use(PROPERTY),
    ]))
    assert.deepEqual(out.references.filter((r) => r.file === 'test/use.js'), [])
    assert.equal(out.external.filter((r) => r.file === 'test/use.js').length, 1)
    assert.equal(out.shorthand_refs, 0)
  })

  it('refuses a shorthand naming something this index does not define', () => {
    // `module.exports = { map }` over an imported `map`: the range's other
    // symbol is a package's, with no definition here to point at.
    const LODASH = 'scip-typescript npm lodash 4.17.21 `index.d.ts`/map().'
    const out = decode(fakeIndex([
      {
        relative_path: 'lib/tools.js',
        occurrences: [
          { symbol: PROPERTY, symbol_roles: DEF, range: SHORTHAND },
          { symbol: LODASH, symbol_roles: 0, range: SHORTHAND },
        ],
      },
      use(PROPERTY),
    ]))
    assert.deepEqual(out.references, [])
    assert.equal(out.external.filter((r) => r.file === 'test/use.js').length, 1)
    assert.equal(out.shorthand_refs, 0)
  })

  it('reads no scheme but scip-typescript, whatever the descriptor', () => {
    // scip-python writes `:` descriptors too (`__init__:`). The rule was
    // measured on scip-typescript's literals and reaches no further.
    const out = decode(fakeIndex([
      {
        relative_path: 'src/a.py',
        occurrences: [
          { symbol: `${PY}/run().`, symbol_roles: DEF, range: [4, 0, 8, 0] },
          { symbol: `${PY}/__init__:`, symbol_roles: DEF, range: [1, 0, 1, 3] },
          { symbol: `${PY}/run().`, symbol_roles: 0, range: [1, 0, 1, 3] },
        ],
      },
      {
        relative_path: 'src/b.py',
        occurrences: [{ symbol: `${PY}/__init__:`, symbol_roles: 0, range: [2, 4, 2, 7] }],
      },
    ]))
    assert.deepEqual(out.references.filter((r) => r.file === 'src/b.py'), [])
    assert.equal(out.external.filter((r) => r.file === 'src/b.py').length, 1)
    assert.equal(out.shorthand_refs, 0)
  })

  it('leaves an ordinary reference and an ordinary external as they were', () => {
    const REACT = 'scip-typescript npm react 18.2.0 `index.d.ts`/useState().'
    const out = decode(fakeIndex([
      { relative_path: 'lib/tools.js', occurrences: [defined] },
      {
        relative_path: 'test/use.js',
        occurrences: [
          { symbol: ALPHA, symbol_roles: 0, range: USE },
          { symbol: REACT, symbol_roles: 0, range: [5, 2, 5, 10] },
        ],
      },
    ]))
    assert.deepEqual(out.references, [
      { file: 'test/use.js', line: 4, col: 8, name: 'alpha', def_file: 'lib/tools.js', def_line: 3 },
    ])
    assert.equal(out.external.length, 1)
    assert.equal(out.external[0].moniker, REACT)
    assert.equal(out.external[0].in_repo, undefined)
    assert.equal(out.shorthand_refs, 0)
  })
})
