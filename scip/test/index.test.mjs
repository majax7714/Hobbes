import assert from 'node:assert/strict'
import { test } from 'node:test'

import * as cfs from 'node:fs'
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
  dependencyCoverage,
  GRAPH_KINDS,
  INDEXERS,
  insideRepo,
  packageOf,
  terminalName,
  indexerPlan,
  gradleAttachScript,
  javacInternals,
  resolvedPackages,
} from '../index.mjs'

// Real monikers, pasted from scip-python 0.6.6 and scip-typescript 0.4.0
// output during the V2.M0 spike (ADR-027).
const PY = 'scip-python python hobbes 0 `src.hobbes.cli`'
const TS = 'scip-typescript npm betchat-frontend 1.0.0 src/api/`axios.ts`'
// scip-java's and scip-clang's shapes, from the Java cells (ADR-096) and
// the C lane B spike (scip-clang 0.4.0 on DaveGamble/cJSON).
const JAVA_OVERLOAD = 'scip-java maven maven/org.jsoup/jsoup 1.24.1-SNAPSHOT org/jsoup/Jsoup'
const CLANG = 'cxx . . $ '

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

test('a C build root plans CMake or bear over make, then scip-clang (ADR-109)', () => {
  const base = { language: 'c', stage: '/s/cjson', output: '/s/o.scip', buildDir: '/s/b' }
  const cmake = cPlan({ ...base, compdbSource: 'cmake' })
  assert.deepEqual(cmake.steps.map((s) => s.bin), ['cmake', 'scip-clang'])
  assert.deepEqual(cmake.steps[0].args, ['-S', '/s/cjson', '-B', '/s/b', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'])
  assert.deepEqual(cmake.steps[1].args, ['--compdb-path=/s/b/compile_commands.json', '--index-output-path=/s/o.scip'])
  assert.equal(cmake.steps[1].cwd, '/s/cjson', 'scip-clang reports documents relative to its cwd, the root')
  const make = cPlan({ ...base, compdbSource: 'make' })
  assert.deepEqual(make.steps.map((s) => s.bin), ['sh', 'scip-clang'])
  assert.equal(make.steps[0].args[1], 'bear --output "$1" -- make -k; exit 0', "make's own exit decides nothing")
  assert.equal(make.steps[0].args[3], '/s/b/compile_commands.json')
  const repo = cPlan({ ...base, compdbSource: 'repo', compdb: '/s/b/rebased.json' })
  assert.deepEqual(repo.steps.map((s) => s.bin), ['scip-clang'])
  assert.equal(cCompdb({ ...base, compdbSource: 'repo', compdb: '/s/b/rebased.json' }), '/s/b/rebased.json')
  assert.equal(indexerPlan({ ...base, compdbSource: 'cmake' }).steps.length, 2)
  assert.throws(() => cPlan({ ...base }), /no compile database source/)
})

test("an empty compile database stops the plan before scip-clang, in the build's words", () => {
  const dir = cfs.mkdtempSync(cpath.join(cos.tmpdir(), 'hobbes-c-'))
  const plan = cPlan({ language: 'c', stage: dir, output: cpath.join(dir, 'o.scip'), buildDir: dir, compdbSource: 'make' })
  cfs.writeFileSync(cpath.join(dir, 'compile_commands.json'), '[]')
  assert.throws(() => plan.steps[1].check({ stderr: 'make: *** No rule to make target' }),
    /bear over make produced no compile database entries.*No rule to make target/)
  cfs.writeFileSync(cpath.join(dir, 'compile_commands.json'), JSON.stringify([{ directory: dir, file: 'a.c', arguments: ['cc', 'a.c'] }]))
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

test('typed ranges (SCIP fields 8 and 9) are read into the range shape', async () => {
  const pb = (await import('google-protobuf')).default
  const { scip } = (await import('@sourcegraph/scip-typescript/dist/src/scip.js')).default
  const w = new pb.BinaryWriter()
  w.writeString(2, 'scip-java maven . . a/B#m().')
  w.writeInt32(3, 1)
  w.writeMessage(8, {}, () => { w.writeInt32(1, 4); w.writeInt32(2, 7); w.writeInt32(3, 11) })
  const single = scip.Occurrence.deserialize(w.getResultBuffer())
  assert.deepEqual(single.range, [4, 7, 11])
  assert.equal(single.symbol, 'scip-java maven . . a/B#m().')
  assert.equal(single.symbol_roles, 1)
  const w2 = new pb.BinaryWriter()
  w2.writeString(2, 'x')
  w2.writeMessage(9, {}, () => { w2.writeInt32(1, 4); w2.writeInt32(2, 7); w2.writeInt32(3, 6); w2.writeInt32(4, 2) })
  assert.deepEqual(scip.Occurrence.deserialize(w2.getResultBuffer()).range, [4, 7, 6, 2])
  // The deprecated field still reads, so the other four indexers are untouched.
  const w3 = new pb.BinaryWriter()
  w3.writeString(2, 'y')
  w3.writePackedInt32(1, [1, 2, 3])
  assert.deepEqual(scip.Occurrence.deserialize(w3.getResultBuffer()).range, [1, 2, 3])
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
