# Extraction — lane B environments and staging

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-22 — Lane B links the repo's `node_modules`, and trusts it not to be written
- **Cannot tell you:** with structural certainty that indexing a TypeScript
  repo cannot modify its dependency tree. The staging tree symlinks
  `node_modules` rather than copying it (222 MB on kbet), so for the
  duration of an index there is a live handle into the user's tree.
- **Because:** copying is infeasible at that size, and the alternative that
  preserves the copy — an absolute `paths` fallback — measured a **6.4%
  loss of semantic references**, which is the lane's whole output.
- **Bites at:** nothing observed. Two properties were verified rather than
  assumed: a full index modified **0 files** under the real
  `node_modules`, and `shutil.rmtree` unlinks a symlinked directory instead
  of recursing into it, so removing a stage cannot delete the target.
- **You find out:** **surfaced by test, not by artifact** — both properties
  carry regression tests (`test_staging.py`), so a change that breaks
  either fails the suite rather than a user's machine. This is the correct
  surfacing for a constraint whose audience is a future maintainer rather
  than a reviewer.
- **Honest residue:** measured, not structurally enforced. A future indexer
  that emits, or a dependency with a build step run during indexing, would
  invalidate it and the tests are what would catch it.
- **Source:** ADR-032.

### C-23 — TypeScript semantics need an installed dependency tree — *narrowed 2026-08-18*
- **Cannot tell you:** where a call goes when its receiver's type comes
  from a package that is not installed **and cannot be provisioned**.
  Measured on kbet with no `node_modules`: **19% of internal references
  and 73% of external references disappear**, and 20 of 23 packages
  resolve to nothing.
- **Because:** the indexer's resolution is whole-program type inference,
  and an absent dependency has no types to infer from. It exits 0 and
  produces a plausible index regardless.
- **Narrowed by ADR-050:** when the repo carries a lockfile Hobbes can
  honor (`package-lock.json` → `npm ci`; v1 `yarn.lock` → pinned
  classic yarn), the tree is **provisioned into `~/.hobbes/cache`** —
  `--ignore-scripts`, never touching the repo — and symlinked into the
  stage. What remains of this entry: pnpm, Yarn Berry, and
  lockfile-less repos (each declined by name in a per-zone degradation
  record), plus the offline case, which is C-34's subject.
- **Bites at:** TS repos on pnpm/Berry or without a lockfile, ingested
  without `npm install` having been run — and partially-installed
  environments everywhere.
- **You find out:** **surfaced** — `dependency_coverage: {declared,
  resolved, missing[]}` is reported on every run, plus an
  `extraction_errors` entry and an ingest WARNING below a ratio.
  Previously **unsurfaced and actively misleading**: the old all-or-nothing
  test could never fire for TypeScript, because the indexer bundles
  `typescript` itself and that one always-resolving package kept the
  "everything missing" condition false forever. 1 of 23 resolved, and it
  said nothing.
- **Honest residue:** a *partially* installed environment still degrades in
  proportion, and the ratio is a threshold rather than a proof.
- **Provider (P9):** inherited from `@sourcegraph/scip-typescript`
  **0.4.0**. **Not liftable by an upgrade** — whole-program type inference
  cannot infer from types that are not on disk, so this is a property of
  the approach rather than of the release. The surfacing is the permanent
  answer here, not a placeholder for a fix.
- **Source:** ADR-032, found by the control variant in the V2.M3 spike;
  owned as ours under P9 (ADR-034).

### C-27 — Python third-party semantics need a discoverable venv
- **Cannot tell you:** where a call into a third-party package goes, when
  the repo's environment is not a venv Hobbes can find — a conda env,
  system-installed packages, or a venv living somewhere unconventional.
- **Because:** two mechanisms both need the environment, and both were
  quietly broken until the C-16 fix exposed it (2026-08-15). *Resolution*:
  Pyright needs `venvPath`, which was hardcoded to `<root>/.venv` — this
  repo's venv is `pipeline/.venv`, so it resolved nothing; now discovered
  (`find_venv`: `.venv`/`venv` at the root, then beside each manifest,
  `pyvenv.cfg` required). *Attribution*: scip-python maps resolved files
  to packages by asking the first `pip3` on PATH which environment is
  installed — the **system** one, and a uv venv has no pip at all — so
  every third-party reference was attributed to the local project and the
  dependency vanished; now Hobbes pre-computes the listing with the
  venv's own interpreter (stdlib `importlib.metadata`) and hands it over
  via `--environment`. Names are matched PEP-503-style (`pyyaml` ==
  `PyYAML`), Python only.
- **Bites at:** third-party `uses`/`calls` edges on any Python repo whose
  environment the discovery conventions miss. On this repo the fix took
  resolution from **0 of 5 declared packages to 5 of 5**.
- **You find out:** **surfaced** — `dependency_coverage` counts plus the
  ingest WARNING below the threshold, the same mechanism as C-23. The
  degradation had existed since lane B landed and was invisible until
  C-16's manifest walk gave the check its denominator; three days of
  "semantic" Python graphs carried no third-party edges and nothing said
  so.
- **Honest residue:** discovery is convention-bound. An environment
  without `pyvenv.cfg` under `.venv`/`venv` at the root or beside a
  manifest is not searched for, and the coverage counts are the answer
  there, not a fix.
- **Provider (P9):** inherited from `@sourcegraph/scip-python` **0.6.6**
  — its environment discovery (PATH's pip) is the part Hobbes routes
  around, and `--environment` is the indexer's own escape hatch, marked
  experimental. Re-check on any version bump: an upgrade that fixes its
  discovery could retire our listing; one that drops the flag would
  break it loudly (the helper passes it only when computed).
- **Source:** found 2026-08-15 by C-16's first real run; fixed and
  registered the same day. The Python sibling of C-23.

### C-34 — Dependency provisioning needs a fetchable npm registry and a supported lockfile
- **Cannot tell you:** anything better than C-23's degraded answer when
  the provisioning path (ADR-050) cannot run: no network to the npm
  registry, no `npm` on the box, a pnpm or Yarn Berry lockfile, or no
  lockfile at all.
- **Because:** the install is **lockfile-pinned or declined** — an
  unpinned `npm install` is the registry's answer of the day, and an
  artifact that changes between runs of the same commit breaks P1.
  Berry is declined because PnP does not produce the `node_modules`
  shape the indexer resolves against; pnpm because no pinned installer
  for it is wired. `--ignore-scripts` is unconditional, so a package
  whose type declarations are *generated by its postinstall* stays
  typeless — that residue is accepted, not excepted, because a
  lifecycle script is arbitrary code and no analyzer here requires
  execution (the C-29 contrast).
- **Bites at:** offline ingests of uninstalled TS repos, and the
  pnpm/Berry half of the ecosystem. The npm sibling of C-30 (crates)
  and cousin of C-27 (venvs): every language's third-party semantics
  need an environment from somewhere.
- **You find out:** **surfaced** — every zone that is declined or fails
  gets a degradation record naming the reason (`no lockfile`,
  `Berry (v2+)`, the installer's own error tail), and
  `dependency_coverage` still counts what resolved.
- **Source:** ADR-050 (2026-08-18).

---

### C-64 — Lane B runs in the sandbox image; without one, executing providers refuse
- **Cannot tell you:** Rust **or Java** semantics (and the
  venv-attributed Python environment) on a box with no `podman` or with
  the sandbox image not built. Since ADR-092 every lane B step runs
  inside `hobbes-session:local`; the steps that execute repo-authored
  code — rust-analyzer's `scip` export (C-29), **scip-java, which runs
  the repo's own Maven or Gradle build** (C-66, ADR-096), and the venv
  listing, which runs the venv's own `bin/python` — **refuse** on such a
  box rather than run on the host. Rust and Java fall to lane A's
  syntactic floor; the Python index runs without an environment listing
  (C-27's shape). Java is also the language whose *toolchain* the image
  supplies most of: three JDKs and Maven, with a Gradle repo pulling its
  own wrapper. A repo needing a
  newer toolchain than the image pins (`RUSTUP_TOOLCHAIN`,
  `GOTOOLCHAIN=local`) degrades per unit, visibly. The oracle lane's
  O6/O7 (bench tooling) refuse the same way — a cell does not grade on
  such a box; `report.txt` says where the oracle ran.
- **Because:** the guarantee is P10-specific — *repo code never executes
  on the host* — and a general degrade path that quietly fell back to
  host execution would hollow it out (ADR-036). The providers that
  execute no repo code (scip-python, scip-typescript, scip-go) may still
  run on the host there, because losing three languages' semantics to a
  uniformity preference would be the wrong trade; they say so.
- **Bites at:** first contact on a fresh box — build the image before
  the first semantic ingest (`docs/first-run.md`); and any box where
  rootless podman cannot run.
- **You find out:** **surfaced** — a degradation record per provider
  (`lane B refused for rust: … (C-64)` / `scip-typescript ran on the
  host, not in the sandbox image: … (C-64)`) in `extraction_errors`,
  printed by the ingest summary as a WARNING and by `list_blind_spots`
  for the directory. `hobbes ingest --uncontained` (or
  `HOBBES_UNCONTAINED=1`) runs everything on the host: the flag prints
  `UNCONTAINED:` before the ingest, every provider's facts carry the
  disclosure, `graph.json` is stamped with a `containment` record (each
  step, where it ran, whether the hatch was set — `all_contained`
  false), the summary prints a `containment:` WARNING, and
  `list_blind_spots` names the artifact as not built under the
  guarantee. An oracle cell's export and report carry the same. A named
  escape hatch, never a default.
- **Scope (P11):** the contained path is verified only on the runs made
  under it (this repo, rust_proj, the fixtures — 2026-08-27/28); every
  earlier record was a host run and says nothing about the contained
  toolchain, which already differed once (`rust-src`). A cell record
  without a `containment` field is a host-run record.
- **Provider (P9):** none — this is Hobbes's own containment; the
  toolchains inside the image are pinned in `sandbox/Containerfile`.
- **Source:** ADR-092.

## Lifted constraints in this segment

A lift is a technique, and the technique — not the celebration — is what
these entries document. Each keeps its number, states the limit as it
stood, the exact mechanism that lifted it, and the **residual edge
cases**: inputs the technique does not classify, where the old concession
quietly survives. When a residual case turns out to bite, it becomes a
new active entry and the two cross-reference. Field key: `README.md`,
"How to read a lifted entry".

### C-74 — A workspace link inside `node_modules` dangled in the container, and the record blamed the helper — *lifted 2026-09-03*
- **Was:** `containment.mount_roots` mounted each `node_modules` tree
  read-only at its host path and nothing else of the repo's *installed*
  tree; a link whose target lies outside every `node_modules` — exactly
  what a pnpm / npm / yarn **workspace** link is (`node_modules/@scope/pkg
  -> ../../../pkg`) — had no target in the container. date-fns
  (2026-09-02): `pkgs/core/tsconfig.json` extends
  `@date-fns/dev/config/tsconfig`; scip-typescript exited with `File
  '@date-fns/dev/config/tsconfig' not found … no files got indexed` on
  **every** workspace zone (6 of 6 + root): 3 semantic call edges of
  2,258, capture 0.1%, over a fully installed environment the same
  indexer handles on the host in ~10 s. The per-zone record said *"the
  SCIP helper is unusable — install Node and run npm install"* — the
  helper ran; and seven `scip-resolve` records all sat at `path: "."`.
  *Partial* while it stood.
- **Lifted by — the technique:** three pieces. (1)
  `scipsource.workspace_link_targets` reads one level of each
  `node_modules` tree a zone links (`name` and `@scope/name`) and lists
  the targets of links that resolve *outside* the tree; they join the
  tree as ro mounts (`run_helper(ro=…)`), so the link resolves in the
  container to the same host path. Third-party links (`.pnpm/…`)
  resolve inside the tree and are not listed; a dangling link is
  skipped. (2) The helper exits `INDEXER_EXIT` (3) when the indexer it
  drove exited non-zero, and `run_helper` records that as *"the
  typescript indexer exited inside the container (the helper ran; this
  is the indexer's own failure, not a missing helper): …"* with the
  indexer's stderr — the "install Node" text is reserved for a helper
  that could not start. (3) `_rebase` places a zone's whole-index
  records (`scip-index`, `scip-resolve`, the empty-decode record) at
  the zone, ADR-048's per-unit rule. **Measured** on a synthetic
  workspace (`pkgs/core/tsconfig.json` extending
  `@x/dev/tsconfig.base.json` through `node_modules/@x/dev ->
  ../../../dev`), contained: the zone indexes and `b → a` is a semantic
  `calls` edge; the control with the new mounts disabled reproduces
  date-fns exactly — `error TS6053: File '@x/dev/tsconfig.base.json'
  not found`, capture 0.0% — under the reworded record. Tests:
  `TestWorkspaceLinkTargets`, `TestHelperExitClassification`, the
  helper's `exitCodeFor` test.
- **Residual edge cases:** a link two levels deep or a link *inside* a
  linked package that points elsewhere in the repo is not followed
  (one level, by design — the targets are mounted, and what they
  contain is theirs). A workspace whose links target a directory
  *outside* the repo (a sibling checkout) mounts that directory ro —
  the C-22 trust, now spanning it. date-fns itself is not re-ingested
  here; the synthetic cell is the evidence (P11: the machinery on that
  shape, not on every workspace).
- **Source:** the four-repo extraction test of 2026-09-02 (agent B,
  date-fns/date-fns); lifted 2026-09-03.

### C-85 — A Python repo with no venv lost lane B entirely under containment, and the record blamed the helper — *lifted 2026-09-03*
- **Was:** with no venv where `find_venv` looks (C-27's conventions)
  Hobbes computed no `--environment` listing and handed scip-python
  nothing; inside the sandbox image scip-python's own discovery then
  failed and the indexer exited 1 before indexing a file — every Python
  site fell to the syntactic floor (`capture [python]: 0.0%` on httpx,
  fastapi and textual at their DeepSWE base commits, 2026-09-03;
  reproduced 2026-09-03 on a venv-less copy of the `miniapp` fixture:
  0.0% of 19 sites, the stack ending in scip-python's option parser,
  `main-impl.ts:47`). The degradation record said *"the SCIP helper is
  unusable — install Node and run `npm install`"*: the helper ran, the
  indexer died. *Partial* while it stood — loud, wrong cause, no fix
  named.
- **Lifted by — the technique:** `extract_scip` always writes the
  environment listing — the venv's when one is found, **empty** when
  none is (or when the listing was refused by containment) — so the
  indexer never runs its own discovery in the image; and it appends a
  `scip-python` record saying no venv was found, that third-party
  references attribute to the local project, and the one-command fix
  (`uv venv .venv && uv pip install -e .`). The helper-exit
  classification is C-74's piece (2), shared. **Measured:** the
  venv-less `miniapp` copy goes from 0.0% to **68.4% of 19 sites** —
  the number it reads with a venv — with the C-85 record (and the C-79
  record, which fires too: the fixture declares no dependencies)
  printed under the summary. Tests: `TestNoVenvStillIndexes`,
  `TestHelperExitClassification`.
- **Residual edge cases:** an empty listing is the true statement about
  what Hobbes can name and still the C-27 concession — third-party
  edges are absent, and `dependency_coverage` (when a manifest declares
  anything, C-79) will show them missing; the environment gap line in
  `list_blind_spots` is the surfacing. A conda or system environment is
  still not searched for (C-27 unchanged).
- **Provider (P9):** `@sourcegraph/scip-python` 0.6.6 — the discovery
  that failed is its; the crash-on-absence was ours to avoid and the
  record was ours to fix.
- **Source:** ADR-099's memorised-cell ingests, 2026-09-03; lifted the
  same day.

### C-79 — A Python repo declaring its dependencies outside `pyproject.toml [project]` got no `dependency_coverage`, silently — *lifted 2026-09-03*
- **Was:** `scipsource.declared_dependencies` walked `pyproject.toml`
  files only (C-16's lift widened it to *every* `pyproject.toml`, not
  to other manifests). peft (2026-09-02): `pyproject.toml` has no
  `[project]` table, so `declared_dependencies` read `[]`, and
  `extract/__init__.py` appends `dependency_coverage` only when
  `declared` is truthy — the key was absent from `graph.json`, no
  message said the check did not run, and `list_blind_spots` printed
  no environment line. The environment itself was found and used
  (17,284 external sites attributed); what was missing was C-27's
  surfacing. *Unsurfaced*: the absence of a key.
- **Lifted by — the technique:** two halves. (1) The reader takes every
  manifest the pruned walk finds (`iter_manifests`, the same walk as
  the CLI pack): `pyproject.toml [project]`, `setup.cfg [options]
  install_requires` + `[options.extras_require]` (configparser,
  multi-line, comments stripped), and every `requirements*.txt`
  (comments, `-r`/`-e`/`--option` lines, bare URLs and paths skipped;
  `pkg @ url` keeps `pkg`; nothing is followed — an included file is
  read on its own if its name matches). **`setup.py` is code and is
  not read.** (2) When the Python index ran and no manifest declared
  anything, `_coverage_gap_records` appends an `extraction_errors`
  record (`scip-python`, naming C-79 and the three manifests read), so
  the summary's WARNING line and `list_blind_spots`' `degraded:` line
  both say the environment check had nothing to compare against. Tests:
  `test_setup_cfg_install_requires_and_extras_are_read`,
  `test_requirements_files_are_read_and_nothing_is_followed`,
  `test_setup_py_alone_declares_nothing_and_is_not_executed`,
  `TestCoverageGapRecord`.
- **Residual edge cases:** a repo whose only declaration is
  `setup.py`'s `install_requires` still has no list — it now gets the
  record instead of silence, and the fix a user can apply is a
  `setup.cfg` or a `requirements.txt` beside it. Poetry's
  `[tool.poetry.dependencies]` and PDM/uv-only lock files are not read
  (a `pyproject.toml` without `[project]` reads as empty; the record
  fires). A `requirements` file under another name (`deps.txt`,
  `requirements/base.in`) is not matched by the `requirements*.txt`
  pattern.
- **Source:** the four-repo extraction test of 2026-09-02 (agent A,
  huggingface/peft); lifted 2026-09-03.

### C-16 — Dependency-degradation detection read only the repo root's manifest — *lifted 2026-08-15*
- **Was:** `declared_dependencies` looked only at `<repo>/pyproject.toml`,
  so a repo whose manifest lives in a subdirectory — this repo's own deps
  are in `pipeline/pyproject.toml` — ran ADR-027 Decision 4's check
  against an empty list. Worse than unsurfaced: the check *appeared* to
  run and reported nothing, on exactly the repo Hobbes dogfoods against.
- **Lifted by — the technique:** the pre-M6 register sweep — the function
  now unions every `pyproject.toml` in the repo via the same pruned walk
  the CLI pack uses (`iter_pyprojects`), with the subdirectory case
  pinned by a test written in this repo's own shape. The TS half was
  already per-zone (`declared_npm_dependencies` takes the zone's
  `package.json`) and needed nothing.
- **Residual edge cases:** the technique's boundary is the manifest
  format, not the manifest's location. A Python repo declaring
  dependencies exclusively via `setup.py` or `requirements.txt` still
  presents an empty declared list, and Decision 4's check is inert there
  exactly as it was for subdirectory manifests before the lift — with the
  same failure shape: a check that appears to run and reports nothing.
- **Source:** BUILDLOG 2026-08-14 (seventh), found via private-repo-A; lifted
  2026-08-15.

### C-33 — In-repo references across indexing units did not resolve — *lifted 2026-08-18, one session after registration*
- **Was:** a language's indexing units — Go modules, cargo roots, TS
  zones — are indexed separately and merged, so an in-repo reference
  *across* units resolved in neither index. Dagger's root-module calls
  into the `replace`d `./sdk/go` produced **zero** semantic edges — the
  dominant miss on exactly the monorepo shape where cross-unit edges
  are the architecture. Two stacked mechanisms, measured on a
  two-module fixture: per-unit staging stripped the sibling's sources
  (the loader could not type the import and mis-attributed it to the
  stdlib bucket), and `decode()` binned cross-index references into
  `external_refs`, discarding the moniker there — unfixable in
  principle at the merge.
- **Lifted by — the technique (ADR-049):** external rows keep their
  moniker (helper facts v3); `join_cross_unit` runs after each
  language's units merge and promotes external rows to references on
  **exact moniker equality** — never heuristically, so this is not the
  cross-zone reconciliation C-12 rejected (nothing interprets another
  unit's compiler config; a moniker matches byte-for-byte or the row
  stays external). Go replace targets are staged beside their consumer
  (`go_replace_targets`: the consumer's own go.mod only — Go's rule —
  path replacements only, in-repo only). Verified: the reproducing
  fixture flips 0% → 100% with the edge `semantic`/`calls`; dagger
  re-ingest numbers in `docs/extraction-evidence.md`.
- **Residual edge cases:** a moniker **two units both define** abstains
  and is reported (`scip-merge` degradation — C-28's rule across
  units; dagger's generated `internal/dagger` packages are the live
  case). **Rust** path-dependencies across *separate* workspaces are
  not staged together — members already collapse to one workspace
  unit, and no verified cross-workspace case exists to build against
  (the ADR-046/P11 rule). **TS** alias- and config-mediated cross-zone
  imports remain C-12's subject. **Version skew** would silence the
  join, not corrupt it: both sides are pinned to `0` (ADR-027
  Decision 1 is what makes monikers meet), and lane agreement is the
  watchdog if an indexer ever stamps them apart. A replace escaping
  the repo is not staged — code outside the repo is not ours to copy.
- **Source:** ADR-048 (registered), ADR-049 (lifted, same week the
  register said the fix needed its own review — Max reviewed and
  directed it).

---
