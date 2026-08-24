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
import { readFileSync, rmSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import pkg from '@sourcegraph/scip-typescript/dist/src/scip.js'

const { scip } = pkg
const HERE = dirname(fileURLToPath(import.meta.url))

/** Facts schema version; the Python join refuses anything else.
 *
 * v2 (V2.M3, ADR-032): facts carry `dependency_coverage` on every run,
 * replacing Decision 4's all-or-nothing degradation test. */
export const HELPER_VERSION = 3

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
    args: (c) => ['index', '--cwd', c.stage, '--output', c.output, '--no-progress-bar'],
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
  if (desc.endsWith('().')) return 'method'
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
  // Strip the descriptor suffix, then take the last path/member segment.
  const bare = desc.replace(/(\(\)\.|#|\.|\/|:|!)$/, '')
  const seg = bare.split(/[/#.]/).filter(Boolean).pop() ?? ''
  // rust-analyzer scopes impl methods as `impl#[Counter]new().` — the
  // bracketed self type rides the final segment, and a name that keeps it
  // matches no call site, which silently costs Rust every method edge
  // (found by the V2.M7 rust_proj verification: `unwrap` unresolved).
  return seg.replace(/`/g, '').replace(/^\[.*\]/, '')
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
 */
export function decode(index) {
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
  // monikers are dropped from the definitions map: their references fall
  // to `external`, unattributed rather than guessed, and `degradations`
  // reports the drop (ADR-040).
  const ambiguous = new Set()

  for (const doc of index.documents) {
    if (!insideRepo(doc.relative_path)) continue
    for (const occ of doc.occurrences) {
      if (!occ.symbol || occ.symbol.startsWith('local ')) continue
      if (!isDefinition(occ)) continue
      const kind = classify(occ.symbol)
      if (!GRAPH_KINDS.has(kind)) continue
      const prior = definitions.get(occ.symbol)
      if (prior) {
        if (prior.file !== doc.relative_path) ambiguous.add(occ.symbol)
        continue
      }
      const r = occ.range
      definitions.set(occ.symbol, {
        moniker: occ.symbol,
        file: doc.relative_path,
        line: r[0] + 1,
        end_line: (r.length >= 4 ? r[2] : r[0]) + 1,
        kind,
      })
    }
  }
  for (const symbol of ambiguous) definitions.delete(symbol)

  for (const doc of index.documents) {
    if (!insideRepo(doc.relative_path)) continue
    for (const occ of doc.occurrences) {
      if (!occ.symbol || occ.symbol.startsWith('local ')) continue
      const pkgKey = packageOf(occ.symbol)
      if (pkgKey) packages.set(pkgKey, (packages.get(pkgKey) ?? 0) + 1)
      if (isDefinition(occ)) continue
      const target = definitions.get(occ.symbol)
      if (!target) {
        external.push({
          file: doc.relative_path,
          line: occ.range[0] + 1,
          col: occ.range[1],
          name: terminalName(occ.symbol),
          package: pkgKey,
          // Kept since v3 (ADR-049): "external" means external to *this
          // index*, and a sibling indexing unit of the same repo may
          // define exactly this moniker — the cross-unit join matches on
          // it after the per-unit indexes merge. Dropping it here was
          // what made C-33 unfixable in principle.
          moniker: occ.symbol,
        })
        continue // resolves outside this index: not a repo edge
      }
      references.push({
        file: doc.relative_path,
        line: occ.range[0] + 1,
        // Column and name are what let the join tell two same-named
        // occurrences on one line apart (ADR-029).
        col: occ.range[1],
        name: terminalName(occ.symbol),
        def_file: target.file,
        def_line: target.line,
      })
    }
  }

  return {
    definitions: [...definitions.values()],
    references,
    external,
    packages,
    ambiguous: [...ambiguous].sort(),
  }
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
  return language === 'python' ? name.toLowerCase().replace(/[-_.]+/g, '-') : name
}

export function dependencyCoverage(decoded, config) {
  // Excluded from *both* sides. A bundled package resolving is not
  // evidence the environment exists, and a repo declaring it (nearly
  // every TS repo declares `typescript`) must not be marked as missing a
  // dependency it will never be credited for either.
  const declared = (config.declaredDeps ?? []).filter((d) => !SELF_PACKAGES.has(d))
  const seen = new Set()
  for (const key of decoded.packages.keys()) {
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
  if (index.documents.length === 0) {
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
  if (decoded.definitions.length === 0 && index.documents.length > 0) {
    out.push({
      stage: 'scip-decode',
      message: 'documents were indexed but no graph-worthy definitions came out',
    })
  }
  if ((decoded.ambiguous ?? []).length > 0) {
    const sample = decoded.ambiguous
      .slice(0, 3)
      .map((s) => s.split(' ').slice(4).join(' '))
      .join(', ')
    out.push({
      stage: 'scip-decode',
      message:
        `${decoded.ambiguous.length} symbol(s) are defined in more than one ` +
        `file (e.g. ${sample}) — cargo targets sharing a name, or a package ` +
        'namespace declared per file; references to them are left ' +
        'unattributed rather than guessed',
    })
  }
  return out
}

function runIndexer(config) {
  const spec = INDEXERS[config.language]
  if (!spec) throw new Error(`no indexer configured for ${config.language}`)
  // Two install shapes, because indexers are not all npm packages: the
  // Python and TypeScript ones are pinned devDependencies here, scip-go
  // is a Go binary the user installs (`go install`). Resolving the wrong
  // one fails as a bare ENOENT, so each says how *it* is installed.
  const bin = spec.onPath ? spec.bin : join(HERE, 'node_modules', '.bin', spec.bin)
  const proc = spawnSync(bin, spec.args(config), {
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
    timeout: 600_000,
    ...(spec.cwd ? { cwd: spec.cwd(config) } : {}),
  })
  if (proc.error && proc.error.code === 'ENOENT') {
    throw new Error(
      spec.onPath
        ? `${spec.bin} is not on PATH — install it with \`${spec.install}\``
        : `${spec.bin} is not installed — run \`npm install\` in the hobbes repo's scip/`,
    )
  }
  if (proc.status !== 0) {
    const detail = String(proc.stderr || proc.stdout || '').trim().slice(-500)
    throw new Error(`${spec.bin} exited ${proc.status}: ${detail}`)
  }
  return proc
}

export function indexStage(config) {
  const proc = runIndexer(config)
  let index
  try {
    index = scip.Index.deserialize(readFileSync(config.output))
  } catch (err) {
    throw new Error(`could not read the SCIP index the indexer wrote: ${err.message}`)
  }
  const decoded = decode(index)
  // The .scip file is an intermediate, never an artifact (ADR-027 clause
  // 6): its metadata.project_root holds the absolute staging path, so
  // identical content staged elsewhere differs in bytes. Nothing about it
  // is propagated, and it is removed once decoded.
  rmSync(config.output, { force: true })
  return {
    helper_version: HELPER_VERSION,
    language: config.language,
    definitions: decoded.definitions,
    references: decoded.references,
    external_refs: decoded.external,
    packages: Object.fromEntries(decoded.packages),
    // Reported every run, not only when something is wrong: the counts
    // are the honest form of the signal and the threshold is secondary.
    dependency_coverage: dependencyCoverage(decoded, config),
    degraded: degradations(index, decoded, config),
    stderr: String(proc.stderr || '').trim().slice(-2000),
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
    process.stdout.write(JSON.stringify(indexStage(config)))
  } catch (err) {
    process.stderr.write(String(err.message ?? err) + '\n')
    // process.exitCode, not process.exit: a hard exit can truncate a large
    // stdout write that is still flushing (the M6 lesson).
    process.exitCode = 1
  }
}

if (process.argv[1] && process.argv[1].endsWith('index.mjs')) main(process.argv)
