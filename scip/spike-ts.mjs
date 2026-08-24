#!/usr/bin/env node
/**
 * V2.M3 spike: what does `scip-typescript` resolve against a *staged* tree?
 *
 * ADR-027 settled staging for Python because `venvPath`/`venv` in the
 * generated pyrightconfig point at the real environment by absolute path,
 * so third-party resolution survives the copy. TypeScript has no such
 * knob: module resolution walks *up* from the importing file looking for
 * `node_modules`, and a stage under `~/.hobbes/cache` has none above it.
 *
 * So the question this measures is whether lane B can honour ADR-027's
 * clause 1 ("Hobbes never writes to the target repo") for TypeScript
 * without losing the semantics that make it lane B. Four variants:
 *
 *   inplace         — index the real zone directory, output to the cache.
 *                     Writes nothing, but the indexer picks its own file
 *                     set from tsconfig `include` (clause 5 softens).
 *   staged-paths    — staged copy; generated tsconfig adds a `*` fallback
 *                     into the real repo's absolute node_modules. The
 *                     nearest TS analogue of ADR-027's venvPath trick.
 *   staged-symlink  — staged copy; node_modules symlinked. Cheap, but a
 *                     live handle into the user's tree (clause 2's spirit).
 *   staged-naive    — staged copy, tsconfig verbatim, no node_modules.
 *                     The control. It must look *bad*; if it does not,
 *                     the metric cannot tell a working config from a
 *                     plausible one, and every other number here is void.
 *
 * Usage: node spike-ts.mjs <repo-root> <zone-dir-relative>
 */
import { cpSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { indexStage } from './index.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const SPIKE_ROOT = join(process.env.HOBBES_CACHE_DIR ?? join(process.env.HOME, '.hobbes', 'cache'), 'spike-ts')

/** Copy a zone's sources into a stage, never following into node_modules. */
function stageZone(zoneAbs, stageAbs) {
  rmSync(stageAbs, { recursive: true, force: true })
  mkdirSync(stageAbs, { recursive: true })
  cpSync(zoneAbs, stageAbs, {
    recursive: true,
    dereference: false,
    filter: (src) => !src.includes('/node_modules') && !src.includes('/.git'),
  })
}

/** The zone's own tsconfig, plus a `*` path fallback into real node_modules. */
function writeFallbackConfig(stageAbs, zoneAbs) {
  const original = JSON.parse(readFileSync(join(zoneAbs, 'tsconfig.json'), 'utf8'))
  const opts = original.compilerOptions ?? {}
  // Additive only: the zone's own aliases keep their meaning (they are
  // relative to the tsconfig dir, which staging preserves), and `*` is
  // appended as the last resort rather than replacing anything.
  opts.paths = {
    ...(opts.paths ?? {}),
    '*': [`${zoneAbs}/node_modules/*`, `${zoneAbs}/node_modules/@types/*`],
  }
  opts.typeRoots = [`${zoneAbs}/node_modules/@types`]
  writeFileSync(
    join(stageAbs, 'tsconfig.json'),
    JSON.stringify({ ...original, compilerOptions: opts }, null, 1),
  )
}

function measure(label, cwd) {
  const output = join(SPIKE_ROOT, `${label}.scip`)
  const started = Date.now()
  let facts
  try {
    facts = indexStage({
      stage: cwd,
      language: 'typescript',
      projectName: 'spike',
      projectVersion: '0',
      output,
      declaredDeps: DECLARED,
    })
  } catch (err) {
    return { label, error: String(err.message ?? err).slice(0, 300) }
  }
  const packages = Object.entries(facts.packages)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
  return {
    label,
    ms: Date.now() - started,
    definitions: facts.definitions.length,
    references: facts.references.length,
    external_refs: facts.external_refs.length,
    packages: Object.keys(facts.packages).length,
    top: packages.map(([k, v]) => `${k}=${v}`).join(' '),
    degraded: facts.degraded.map((d) => d.stage).join(',') || '-',
  }
}

const repoRoot = resolve(process.argv[2])
const zoneRel = process.argv[3]
const zoneAbs = join(repoRoot, zoneRel)

const pkg = JSON.parse(readFileSync(join(zoneAbs, 'package.json'), 'utf8'))
const DECLARED = Object.keys({ ...(pkg.dependencies ?? {}), ...(pkg.devDependencies ?? {}) })

mkdirSync(SPIKE_ROOT, { recursive: true })
const rows = []

rows.push(measure('inplace', zoneAbs))

const naive = join(SPIKE_ROOT, 'naive', zoneRel)
stageZone(zoneAbs, naive)
rows.push(measure('staged-naive', naive))

const paths = join(SPIKE_ROOT, 'paths', zoneRel)
stageZone(zoneAbs, paths)
writeFallbackConfig(paths, zoneAbs)
rows.push(measure('staged-paths', paths))

const link = join(SPIKE_ROOT, 'link', zoneRel)
stageZone(zoneAbs, link)
if (existsSync(join(zoneAbs, 'node_modules'))) {
  symlinkSync(join(zoneAbs, 'node_modules'), join(link, 'node_modules'), 'dir')
}
rows.push(measure('staged-symlink', link))

const head = ['variant', 'ms', 'defs', 'refs', 'external', 'pkgs', 'degraded']
console.log(head.join('\t'))
for (const r of rows) {
  if (r.error) {
    console.log(`${r.label}\tERROR: ${r.error}`)
    continue
  }
  console.log(
    [r.label, r.ms, r.definitions, r.references, r.external_refs, r.packages, r.degraded].join('\t'),
  )
}
console.log('\ntop packages by reference count:')
for (const r of rows) if (!r.error) console.log(`  ${r.label}: ${r.top}`)
console.log(`\ndeclared deps: ${DECLARED.length}`)
console.log(`stages under: ${SPIKE_ROOT}`)
