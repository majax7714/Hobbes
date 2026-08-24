# ADR 027: Consuming SCIP — node identity, indexer config, and the reader

Date: 2026-08-14
Status: accepted

Milestone V2.M0 (the spike). Grounds architecture v2 §3.2/§3.3 in what the
indexers actually emit. Every number below was produced by
`scip/analyze.mjs` and `scip/compare.mjs` against `scip-python` 0.6.6 and
`scip-typescript` 0.4.0 on the four sanctioned repos, and is reproducible.

## Context

§3.3 says SCIP monikers "are globally unique (they encode package and
version) and become the graph's node IDs", with the consequence that "node
identity is stable across re-indexes." M1 was to freeze a moniker-keyed
schema on that basis. The spike existed to check the claim before the schema
depended on it.

## What the indexers actually emit

A moniker is `<scheme> <manager> <package> <version> <descriptors>`:

```
scip-python python hobbes 0 `src.hobbes.cli`/__init__:
scip-python python hobbes 0 `src.miniapp.api`/read_item().
scip-python python hobbes 0 `src.miniapp.api`/read_item().(item_id)
scip-python python python-stdlib 3.11 builtins/ValueError#
scip-typescript npm betchat-frontend 1.0.0 src/api/`axios.ts`/api.
```

## Decision 1 — pin `--project-version`, or node identity is not stable

**The version field is part of every symbol, and it defaults to the git
revision.** Indexing a two-commit scratch repo with no declared version:

```
commit 1:  scip-python python vertest c9b3bbd… mod/hello().
commit 2:  scip-python python vertest 5d87e72… mod/hello().
```

`hello()` did not change. Its moniker did. Left alone, **every node id in
the graph changes on every commit** — which would make `hobbes diff` report
the entire repo as removed-and-re-added at each commit, destroying the one
thing v2 is meant to sharpen.

Precedence is `--project-version` > a version declared in
`pyproject.toml`/`package.json` > the git revision. So the behaviour also
*varies by repo*: the miniapp fixture picked up `0.1.0` from its pyproject
and was stable; a repo without one was not. Uniformly bad would be better
than this.

**Hobbes always passes an explicit constant `--project-version`.** The cost
is that monikers stop carrying real version information, which trims §3.3's
multi-repo aside: a future graph merge keys on package identity, not on
package version. That is the right trade — stable ids are load-bearing
today, cross-version merging is not on any milestone.

§3.3's stability claim is therefore true only under this ADR, not inherently.

## Decision 2 — indexer config is per *repo*, and getting it wrong is silent

§3.7 frames configuration as per *language*. It is also per repo, and the
failure mode is quiet.

`scip-python` on this repo's `pipeline/`, compared against lane A's current
module edges:

| | recall vs lane A | lane-A-only | scip-only |
|---|---|---|---|
| no config | **0.500** | 48 | 3 |
| `pyrightconfig.json` → `extraPaths: ["src"]` | **0.948** | 5 | 11 |

The cause: under a src layout, `src/hobbes/cli.py` is indexed as module
`src.hobbes.cli`, while `tests/test_cli.py` imports it as `hobbes.cli`
through the editable install. Those are two different monikers for one file,
so the reference dangles — `scip-python python hobbes 0 hobbes/__init__:` is
referenced and never defined. **Every test→source edge was lost.** One line
of Pyright config unifies them.

It generalises: qwen-pathology (src layout) went **0.625 → 1.000**, zero
lane-A-only edges remaining. Two of the three Python repos needed it.

The residual 5 on this repo are fully explained and are not misses: 3 are
`minits` TS/JS fixture files that `scip-python` correctly does not index,
and 2 are the nested `miniapp` fixture, a project-inside-a-project whose own
`src/` the outer config does not cover — the multi-zone problem M6 already
solved for tsconfig, recurring for Python. private-repo-A's 0.637 is the same
language-partition effect: its JS half is lane B's typescript indexer's job.

The 11 scip-only edges are **SCIP being more precise than lane A**:
`cli.py → invariants/schema.py` where lane A says `invariants/__init__.py`,
because SCIP follows a re-export to the real definition site. These are the
first real instances of the §3.4 lane-disagreement report, and they favour
lane B.

### The config is derived, not authored (amended 2026-08-14)

Max asked whether a hand-written `extraPaths` would survive a dirtier repo,
or whether the roots should be worked out systematically. Measured, and the
answer is that **Hobbes already computes the exact set and should never ask
a human for it.**

`discover.py:_import_root` walks each file's `__init__.py` chain and returns
the directory *above* the topmost package — which is, by definition, what
has to be on `sys.path`. The distinct set of `ModuleInfo.root` **is** the
`extraPaths` list. Feeding it straight in, python-only recall against lane A:

| repo | no config | hand-written `["src"]` | **derived roots** |
|---|---|---|---|
| hobbes/`pipeline` | 0.516 | 0.978 (2 missed) | **1.000 (0 missed)** |
| qwen-pathology | 0.625 | — | **1.000 (0 missed)** |
| private-repo-A | 0.655 | — | **1.000 (0 missed)** |

The derived set beats the hand-written one on the repo it was written for:
it picks up `tests/fixtures/miniapp` and `tests/fixtures/miniapp/src`, the
nested-project roots dismissed above as explained residual. They were not
residual, only unconfigured.

private-repo-A is the dirty case and settles the question. Its eight roots are
`core`, `core/src`, `core/migrations`, `core/migrations/versions`,
`core-frontend/core-auth`, `core-frontend/core-login`,
`core-frontend/core-login-local`, `infra-core/lambda/pretoken` — not one a
top-level `src`. No hand-written guess or `src`-shaped heuristic would have
found them; the mechanical walk gets all eight and misses nothing.

**This is not a lane boundary violation.** `discover.py` imports `Counter`,
`Iterator`, `dataclass` and `Path` — no tree-sitter, no parsing. Import-root
discovery is *filesystem topology*, a shared pre-pass both lanes consume:
lane A to compute module ids, lane B to configure its indexer. Neither
consumes the other's output, so §3.2's "semantic providers never consume
tree-sitter ASTs" is intact. The same shape already exists for TypeScript —
M6's nearest-tsconfig zoning is root discovery by another name — and `go.mod`
will be the Go version of it. Root discovery per language belongs in §3.7's
checklist.

### Lane B never writes to the target repo (revised 2026-08-14)

An earlier draft of this ADR had M2 write `pyrightconfig.json` into the
target repo for the duration of the index and delete it after. **That design
is withdrawn.** Max pushed back on it before M1 — a transient write into a
tree Hobbes otherwise only reads is a footgun that has to be crash-safe,
interrupt-safe, and careful never to delete a file it did not create. The
safer design turned out to also work, so there is no trade to make.

`scip-python` indexes what is under `--cwd`. Pointing `--cwd` at a config
directory outside the repo yields zero documents (tried twice — once under
`.hobbes/derived/`, where pyright's `**/.*` auto-exclude also bites, once
from a temp dir with an absolute `include`). But `--cwd` does not have to be
the repo: it can be a **staging tree Hobbes owns outright**, holding a copy
of the source files and the generated config. Measured, python-only recall
against lane A:

| | in-repo config | **staged copy** |
|---|---|---|
| hobbes/`pipeline` | 1.000 (0 missed) | **1.000 (0 missed)** |
| private-repo-A | 1.000 (0 missed) | **1.000 (0 missed)** |

Identical results, and `git status` on both repos stayed empty throughout.
Third-party resolution survives (217 external symbols staged vs 218 in
place) because `venvPath`/`venv` in the generated config point at the real
environment by absolute path — without that, Decision 4's degradation would
fire on every staged run.

**Staging cost on private-repo-A: 9ms to copy 421KB across 144 files**, against
~5.5s to index them — a ratio of roughly 600×. (An earlier revision of this
ADR said 0.38s and 696KB. Both were wrong: the timing measured a shell loop
spawning `mkdir`+`cp` per file, so 288 process spawns dominated an operation
that is 9ms of sequential I/O, and the size was `du` block-rounding rather
than bytes. The conclusion is unchanged and stronger.)

The asymmetry is not surprising once the two are named honestly: staging is
`read()`+`write()`, while indexing is whole-program type inference. Pyright
does not read the 144 staged files, it reads those *plus their entire
transitive import closure* — typeshed's stdlib stubs plus `boto3`,
`pydantic`, `httpx`, `pytest` on this repo — and binds and type-checks all
of it to resolve every reference. That closure is what buys the semantic
tier; lane A is fast precisely because it does not do this.

**Where the time goes**, and it matters for §3.6: indexing a *one-file* repo
takes **1.19s**, all of it Node boot, Pyright init and typeshed load before
any repo code is examined. On private-repo-A's ~6s, roughly 1s is startup, ~2s is
"parse and search for dependencies", and ~3s is emitting SCIP for the 144
files. So the fixed and dependency-shaped costs together outweigh the
per-file work.

**Consequence for the cache:** §3.6 plans to cache partial indexes by
content hash and merge them. That buys less than it appears to. Changing one
source file does not let the indexer skip reloading typeshed or re-parsing
third-party packages, so a partial re-index still pays most of the fixed and
dependency cost. The win worth building first is **skipping the run entirely
when nothing changed** — a whole-index cache keyed on (file set, content
hashes, indexer version, resolved dependency versions) — with partial
merging treated as a later refinement rather than the primary mechanism.
M2 should measure a partial re-index before investing in one.

### The safety contract — M2 must satisfy all of it

Aggressively stated because it is the part that touches someone else's repo,
and because every clause below is a failure that would be quiet:

1. **Hobbes never writes to the target repo.** Not transiently, not under a
   lock, not "and deletes it after". Lane B reads the repo and writes only
   under its own cache root.
2. **Staging copies; it never hardlinks.** Verified hazard: `chmod` through
   a hardlink changes the *original* file's mode, so a staged link is a live
   handle into the user's tree. The copy is cheap (see above) and removes
   the entire class.
3. **The staging root is Hobbes-owned, outside the repo, and its path is
   derived** from (repo path, SHA) — never `mktemp`-random, or the cache in
   §3.6 cannot find it and removal cannot be idempotent.
4. **Removal deletes only a path Hobbes computed**, and refuses any path not
   under the cache root. No globs, no paths read back from the repo, no
   user-supplied paths. A stale staging dir is garbage-collected on the next
   run and its absence is never load-bearing.
5. **Stage exactly the file set lane A discovered** — `discover_modules`
   walks the filesystem and consults git not at all, so it includes
   untracked `.py` files. Staging from `git ls-files` instead would hand the
   two lanes different file sets and manufacture false disagreements in
   §3.4's report.
6. **The `.scip` file is an intermediate, never an artifact.** Measured: two
   runs over one staging tree are byte-identical, but the same content
   staged at a *different path* produces different bytes (1307039 vs
   1307050) because `metadata.project_root` holds the absolute staging path.
   The extracted facts are identical across both (2279 definitions, 920
   graph-worthy, 15330 occurrences). So the adapter drops `project_root` and
   never propagates it, and ADR-006's byte-identical guarantee is asserted
   at the artifact, which is where it is actually required.
7. **§3.6's cache keys on source content, never on `.scip` bytes** — those
   embed the staging path, so hashing them would miss on every relocation
   and silently re-index.

This is M2's code and gets built there. It is recorded here at this length
because the cost of getting it wrong lands in a repo Hobbes does not own.

**Consequences:** the indexer-config registry is needed at **M2**, not M4 —
lane B cannot land usefully without it — and it holds *derived* roots plus
whatever a human overrides, not hand-authored paths. And Hobbes must
*detect* a degraded index rather than trust the exit code (Decision 4).

## Decision 3 — a moniker is a node id only after filtering

Taking SCIP definitions as graph nodes 1:1 does not work. On kbet's
frontend:

| definitions | count |
|---|---|
| meta (`:`) | 5054 |
| term (`.`) | 601 |
| local | 532 |
| method (`()`) | 187 |
| parameter (`(x)`) | 160 |
| namespace (`/`) | 85 |
| type (`#`) | 76 |
| **total** | **6696** |
| **graph-worthy** (namespace/type/method/term) | **949 — 14%** |

For scale: the entire current dogfood graph has 834 symbols; kbet's frontend
alone offers 6,696. **The graph builder keeps namespace, type, method and
top-level term descriptors and drops the rest**, and stdlib packages stay
dropped as they are under ADR-007. Filtering happens in the helper, before
the process boundary — see Decision 5.

## Decision 4 — a successful exit is not a successful index

`scip-typescript` on kbet with **no `node_modules` installed** exited 0 in
1.5s and produced a 2.4MB index that looks entirely plausible. It declared
`external_symbols: 0`, and its most-referenced package was
`npm:typescript@5.9.3` (2,643 references) — TypeScript's own bundled lib,
because the declared dependencies were not there to resolve against. Every
third-party edge was simply absent, and nothing said so.

P6 says degrade visibly. So the SCIP adapter computes its own degradation
signal rather than trusting the process:

- declared dependencies (`package.json`, `pyproject.toml`) that the index
  references **zero** symbols from ⇒ degraded,
- `external_symbols` empty while imports of non-stdlib packages exist ⇒
  degraded,
- indexer missing, non-zero exit, or crash ⇒ degraded.

Degraded lanes record into `extraction_errors` and warn at ingest, exactly
as M6 does for the ts-morph checker crash, and the graph stands at syntactic
tier.

## Decision 5 — the reader is a Node helper, on the ADR-021 pattern

SCIP is protobuf. Three ways to read it were considered:

- **the `scip` CLI's JSON output** — no bindings, but another external
  binary to install and pin, and it emits the whole index as JSON when we
  keep 14% of it;
- **Python `protobuf` + generated bindings** — a new pipeline dependency and
  a generated-code checkin, to read a format only lane B touches;
- **a Node helper** (chosen) — `scip/` already exists and already has the
  indexers, because both install from npm. It runs them, decodes, filters
  per Decision 3, and emits facts JSON for the Python join.

The third is what ADR-003 and ADR-021 already established for `tsextract`,
and it puts the Decision-3 filter *before* the process boundary rather than
shipping seven times the data across it. The Python side's shape does not
change: it consumes facts JSON from a Node subprocess, as it already does.

Bindings come from `@sourcegraph/scip-typescript`'s bundled generated
`scip.js`, which we already depend on at an exact pin. That is an undeclared
internal path, so a test asserts the import resolves; if a future version
moves it, the fallback is vendoring the 1,896-line generated file plus a
`google-protobuf` dependency. Reuse first because it is reversible and
lighter, not because it is prettier.

## Cost

Cold, single-threaded, on this box: miniapp 1.9s · qwen-pathology 2.8s ·
hobbes/pipeline 4.5s · private-repo-A 5.5s · kbet frontend (TS) 1.5s. Well inside
what §3.6's debounced-local, per-PR-in-CI plan assumes; the content-hash
cache is an optimisation, not a rescue.

## Verdict on §3.3: go, with conditions

Monikers work as node ids **given** a pinned project version (Decision 1),
per-repo indexer config (Decision 2), and descriptor filtering (Decision 3).
None of the three is inherent to SCIP and all three are silent when wrong,
which is why they are decided here rather than discovered at M2. V2.M1 may
proceed on a moniker-keyed schema.

## Consequences

- §3.3's stability claim holds only under Decision 1; §7's V2.M1 gets the
  pinned-version rule as an explicit requirement.
- The indexer-config registry moves from M4 into **M2**. `hobbes.yaml` still
  needs its own ADR (the ADR-012 "personal files" tension is unchanged), but
  it is now on M2's critical path.
- The graph builder needs a descriptor filter before it needs anything else.
- `scip/{analyze,compare}.mjs` are spike tooling, kept because they are the
  reproducible evidence for these numbers and because `compare.mjs` is a
  working prototype of §3.4's lane-agreement report. They are replaced by
  the real helper at M2 and carry no tests until then.
