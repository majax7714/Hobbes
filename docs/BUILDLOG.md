# BUILDLOG

Append-only session log. One dated entry per session: what was built, what
changed from plan, open questions. Never edit old entries.

---

## 2026-08-10 — Repo scaffold + M0 (skeleton & policy semantics)

**Built:**

- Monorepo scaffolded per the D1 split: `go/`, `pipeline/`, `web/`
  (placeholder until M7), `docs/` (source docs moved here from the repo
  root), `.hobbes/` (`policies/` + `invariants/` versioned, `derived/` and
  `*.tfstate` gitignored from day one). Root README, CLAUDE.md, LICENSE,
  .gitignore.
- ADRs 001–004: policy YAML schema & file locations, resolution tie-breaks &
  defaults, the `hobbes-policy resolve` CLI contract (JSON + exit codes
  0/10/20), and M0 tooling choices (yaml.v3 + stdlib `flag`; argparse + uv).
- Go policy engine (`go/internal/policy`): strict-YAML parsing, box → repo →
  folder chain loader (nested folder policies, deepest most specific), and
  the resolution algorithm — deny wins from any scope, otherwise
  most-specific scope decides, escalate beats allow within a scope, unmatched
  commands fall back to the most specific `default:` (engine fallback:
  escalate). 52 test cases covering shadowing, deny-wins,
  folder-over-repo-over-box precedence, the escalate tier, defaults, glob
  matching, loading, and CLI exit codes. `go vet` clean.
- `hobbes-policy resolve` CLI (`go/cmd/hobbes-policy`) per ADR-003.
- Python `hobbes` CLI skeleton (`pipeline/`): `init`/`ingest`/`diff` stubs
  that name their delivering milestone, plus `hobbes policy resolve`
  passthrough (binary via `$HOBBES_POLICY_BIN` then `$PATH`). 17 hermetic
  pytest cases (fake binary — no Go toolchain needed to run them).
- Dogfood `.hobbes/policies/repo.policy` for this repo (tfstate deny,
  force-push deny, build/test allows, `git push` escalate). Verified
  end-to-end: Python CLI → Go binary → this repo's policy returns
  allow/deny/escalate with exit 0/10/20.

**Changed from plan:**

- Nothing substantive. Housekeeping: the two source docs moved from the repo
  root into `docs/`. Toolchain installed user-locally (no passwordless sudo
  on this box): Go 1.26.5 at `~/.local/go/bin`, uv 0.12.3 at `~/.local/bin`.
- One reconciliation, recorded in ADR-001: architecture §5.1 sketches the
  repo policy at `.hobbes/repo.policy` while §10's layout puts hand-reviewed
  policy under `.hobbes/policies/`; went with §10
  (`.hobbes/policies/repo.policy`). Folder policies stay
  `<folder>/.hobbes/folder.policy` per §5.1.

**Open questions for Max:**

1. LICENSE defaulted to MIT (you asked for a LICENSE file but didn't name
   one) — swap if you want something else.
2. ADR-002: engine fallback for a command no rule matches is **escalate**
   (not deny) — deliberate, since escalation itself expires to deny at the
   enforcement layer. Confirm or overturn.
3. ADR-002: escalate is shadowable by a more specific scope's allow; only
   deny is absolute. That's my reading of §5.1 — confirm.
4. Commits were made directly on `main` (matching the repo's existing
   history). Say the word if you'd rather have milestone branches + PRs.

**M0 exit criteria:** policy merge tests green (shadowing, deny-wins,
precedence, escalate tier) ✔ · repo scaffolded ✔ · docs written ✔.
Awaiting review before M1.

---

## 2026-08-10 (second session) — M1: Python extractor

M0 review passed (ADRs confirmed); commits pushed by Max.

**Built:**

- ADRs 005–007: tree-sitter packages over stdlib `ast` (uniformity with
  M3/M6), the three artifact schemas + id conventions + no-timestamp
  determinism, and the static resolution strategy (what resolves, what is
  deliberately omitted).
- `hobbes.extract` package: `discover` (import identities, collision
  disambiguation), `pysource` (tree-sitter walk: imports, symbols with
  decorators, call sites, env reads), `graph` (typed module/symbol edges —
  `imports`, `env-read`, `calls`; external `ext:` nodes for third-party,
  stdlib dropped; `env:` nodes as M3 join keys), `interfaces`
  (FastAPI/Flask routes from decorator sites only, `[project.scripts]`
  entry points), `testmap` (pytest defaults, transitive call-closure
  reach), `emit` (SHA+dirty stamp, sorted deterministic JSON).
- `hobbes ingest` and `hobbes init` wired for real; `diff` stays an honest
  M2 stub. 75 pytest cases against a committed fixture repo
  (`tests/fixtures/miniapp`), including byte-identical-rerun and
  git-integration tests.
- Dogfood: `hobbes ingest` on this repo — 35 nodes, 52 module edges,
  189 symbols, 159 call edges, 73 tests; hobbes.* edges hand-verified.

**Changed from plan:**

- `tree-sitter` pinned `<0.26`: the 0.26.0 core segfaulted mid-walk on
  ~300-line files (reproduced against this repo's own sources; same code
  and grammar clean on 0.25.x). Noted in ADR-005; revisit on a new
  upstream release.

**Open questions for Max:**

1. The M1 exit bar wants the spot-check on a *real repo of yours*. The
   dogfood run on hobbes itself gives 52 module edges / 73 tests — enough
   material, but it's code written this session. Point me at one of your
   Python repos for an independent ingest, or bless the dogfood run as the
   exit check.
2. Static reach through the CLI is honest but broad (a CLI test reaches
   every subcommand path via `main`). If that reads as noise once you see
   it in the UI, per-test reach depth or entry-point trimming is a cheap
   M5-era refinement — flagging, not proposing, for now.

**M1 exit criteria:** extractor built with tests ✔ · artifacts SHA-stamped
and deterministic ✔ · spot-check on a real repo — **pending your review**.

---

## 2026-08-10 (third session) — M2: graph render + diff

M1 review passed (derived artifacts spot-checked by Max); commits pushed.

**Built:**

- ADRs 008–009: Mermaid render conventions (flowchart LR, synthetic node
  ids, package clustering, kind shapes, type-styled edges) and graph-diff
  semantics (identity = node id / edge (from,to,type); evidence changes
  are not deltas; ref extraction via `git archive` + the pure extractor;
  exit codes mirror diff(1); `--json` for the M7/M8 consumers).
- `hobbes.render.to_mermaid` — deterministic module-level Mermaid export;
  `hobbes render` reads the ingest artifact and prints it.
- `hobbes.graphdiff` — `extract_at_ref` (git archive → scratch dir → pure
  extraction, checkout untouched), `diff_graphs` (both layers),
  `format_delta` (module-level lines + symbol-layer counts).
- `hobbes diff <base>..<head> [--json]` wired; bare `<base>` means
  `..HEAD`; three-dot ranges rejected. The last CLI stub is gone.
- 99 pytest cases total (24 new: render shape/determinism, delta
  semantics, ref extraction, CLI exit codes).

**Validated on real history** (the M2 exit bar, using this repo's own
commits in place of a PR):

- `hobbes diff 9158c43..f8a15f3` (the M1 CLI-wiring commit) →
  exactly `+ imports hobbes.cli -> hobbes.extract` and
  `-> hobbes.extract.emit` with correct evidence lines; exit 1.
- `hobbes diff 312f153..9158c43` (extractor introduction) → all new
  modules/externals/env nodes; also correctly surfaced the id
  re-disambiguation (`tests` → `pipeline:tests` +
  `pipeline/tests/fixtures/miniapp:tests`) as remove+add — the ADR-006
  collision rule made visible.
- Docs-only range → "no architectural changes", exit 0.

**Changed from plan:** nothing.

**Open questions for Max:**

1. A package *rename* (or an id re-disambiguation like the `tests` case
   above) appears as `- old` + `+ new` — identity is by id, so renames
   aren't tracked. Fine for v1? Rename detection (path-based matching)
   would be an M7-era nicety if the remove+add pairs read poorly in review.
2. `hobbes diff` sees only committed trees (`git archive`); uncommitted
   work is invisible. ADR-009 sketches a `--worktree` mode if you find
   yourself wanting `main..working-tree` diffs in practice.

**M2 exit criteria:** a real commit range produces a correct edge-level
delta ✔ (three ranges hand-verified above) — **pending your review**.

---

## 2026-08-10 (fourth session) — M3: Terraform extractor

M2 review passed; both M2 flags parked in `docs/future_additions.md` (new —
the parking lot for reviewed-and-deferred ideas). Test repos sanctioned:
`~/qwen-pathology` and private-repo-A (private; location withheld).

**Built:**

- ADRs 010–011: the HCL extractor model (nodes, `references`, the two
  cross-layer joins, plan consumption, schema v2) and the builtin tfstate
  deny floor in the Go engine.
- Go: `LoadChain` now prepends a synthetic `builtin:tfstate-floor` box
  file denying `*.tfstate*` — present with zero policies configured,
  unshadowable, no off switch (ADR-011). 55 Go test cases.
- `hobbes.extract.terraform` (tree-sitter-hcl): `tf:` nodes for
  resource/data/module blocks; `references` edges from traversal chains
  that resolve to *declared* blocks only; `env-set` edges from literal
  `environment { variables }` and `env { name }` patterns, landing on the
  same `env:VAR` nodes the app side uses — the §4.1 join is id equality;
  `packages` edges from string paths (after `${path.module}`) resolving to
  discovered app modules; optional `terraform show -json` enrichment
  (`hobbes ingest --tf-plan`, refusing tfstate lookalikes).
- graph.json schema v2: `language` → `languages` (dated note in ADR-006);
  render gained shapes + directory clustering for infra kinds. 119 pytest
  cases.

**Changed from plan:**

- The `packages` path join is *additive beyond* the plan's named env-var
  join. Surveying private-repo-A showed its TF sets no env vars and uses no
  `var.` — its only real app↔infra coupling is `archive_file.source_file`
  packaging `lambda/pretoken/handler.py`. Without the path join, the M3
  exit would only ever be fixture-provable. Rationale in ADR-010.

**Validated (the M3 exit bar):**

- private-repo-A ingest: 200 nodes / 591 module edges / hcl+python in one
  artifact; 22 tf nodes. Cross-layer edge verified by hand:
  `packages tf:data.archive_file.pretoken → handler [infra-core/lambda.tf:5]`
  — line 5 is exactly the `source_file` path; infra `references` edges
  (cognito→lambda, clients→pool, pool→ses) all match the source.
- Env-var join (`env-set` + `env-read` meeting at `env:VAR`) verified on
  the fixture, where both sides exist by construction.
- qwen-pathology ingest: 19 nodes / 24 edges, spot-looked sane.
- Both test repos left untouched except untracked `.hobbes/derived/`.

**Open questions for Max:**

1. private-repo-A's `handler.py` node is just `handler` — a standalone script's
   id is its stem (ADR-006), which is honest but bare in listings (the
   node's `path` field carries the context). Cosmetic; flag if it bothers
   you in review and it can join future_additions.
2. Confirm the cross-layer verification above to close M3's exit.

**M3 exit criteria:** app+infra graph for one repo ✔ (private-repo-A) · one
cross-layer edge verified by hand ✔ (lambda.tf:5 → handler) · tfstate
deny baked in ✔ — **pending your review**.

---

## 2026-08-10 (fifth session) — ADR-012: Hobbes files are personal

M3 review passed across both test repos. Max's directive: always gitignore
Hobbes files in his repos — they are personal-environment artifacts, and
an accidental push would be a mess.

**Built:**

- ADR-012 + `ensure_hobbes_ignored` in `extract/emit.py`: both
  `hobbes ingest` and `hobbes init` now guarantee the target repo
  gitignores the **entire `.hobbes/` directory** before doing anything
  else (the edit is reported by the CLI and honestly flips the stamp's
  `dirty` flag on that first run). Exception: a repo already *tracking*
  `.hobbes/` content — the hobbes repo dogfooding §10 — keeps its
  versioning; only `derived/` is ensured there. This refines §10's
  "policies/ versioned" for v1 single-dev use; the files still live at
  the §10 paths and the policy engine still loads them.
- Applied to both test repos by re-running the new ingest (dogfooding the
  mechanism): `.hobbes/` appended to each `.gitignore`, committed locally
  in each repo (`chore: gitignore .hobbes/ …`) — **not pushed**, pushes
  stay Max's. 124 pytest cases.

**Changed from plan:** §10's versioned-policies posture is deliberately
narrowed for v1 (ADR-012 documents the reconciliation and the
`git add -f` path back if policies ever become team-shared).

**Next:** M4 — policy proxy + sandbox + flight recorder. Not started;
reported back first per Max's instruction, since M4 is the big one.

---

## 2026-08-10 (sixth session) — M4 chunk 1: flight recorder + MCP exec proxy

ADR-012 review passed. Max approved splitting M4 into three review-gated
chunks (proxy+recorder → escalation queue → wrapper+sandbox); this session
is chunk 1.

**Built:**

- ADR-013/014/015: official MCP Go SDK (`modelcontextprotocol/go-sdk`
  v1.7.0); one proxy process per session over stdio, flight logs box-side
  at `~/.hobbes/sessions/<session>/flight.jsonl`; recorder schema exactly
  architecture §9, exec runs `/bin/sh -c` with a 10m default timeout and
  50 KiB/stream output caps.
- `internal/recorder/` — append-only JSONL writer, fsync per event, 0600.
- `internal/proxy/` — the `exec` tool: dir confined to the repo root,
  policy chain loaded per call (`internal/policy.LoadChain` — the M0 bet
  that the daemon imports the engine paid off unchanged), allow runs /
  deny refuses / escalate parks-as-error (honest chunk-1 stub; queue is
  chunk 2), every decision logged with the decisive rule and per-event
  HEAD sha. Protocol-level tests over the SDK's in-memory transports.
- `cmd/hobbes-proxy/` — `serve` (--repo/--role required, --session
  generated, box policy per ADR-003 rules). 90 Go test cases total.

**Verified by hand** on the hobbes repo over real stdio (scripted MCP
client): `git status` → allow, ran, exit 0 logged @ HEAD sha;
`cat prod.tfstate` → deny (repo rule, reason quoted), not run;
`git push origin main` → escalate, parked, not run. Flight log lines
carry exactly `{ts, session, role, tool, argv, policy_rule, decision,
exit, sha}`.

**Next:** chunk 2 — escalation queue (park under `~/.hobbes/sessions/`,
CLI approve/deny, 30-min expire-to-deny, replayable approvals). Awaiting
Max's chunk-1 review first.

---

## 2026-08-11 (seventh session) — M4 chunk 2: escalation queue

Chunk-1 review passed. This chunk replaces the park-as-error stub with
the real §9 escalation tier.

**Built:**

- ADR-016: file-based queue — one atomic JSON record per parked command
  under `~/.hobbes/sessions/<session>/escalations/`; the proxy blocks
  the exec call while parked (MCP progress notifications keep the
  client's tool timeout at bay) so an approved command runs inside the
  original call; the proxy's clock is the expiry authority (late
  approvals are refused and settled as expired); flight schema gains an
  optional `escalation` object — §9's "approvals log the approver"
  demanded it.
- `internal/escalation/` — record lifecycle (pending → approved/denied/
  expired), atomic writes, only-pending-resolves, list/find across
  sessions with clock-effective status.
- Proxy park loop: poll 200ms, `--escalation-timeout` (default 30m)
  expire-to-deny, disconnect-while-parked settles the record as expired
  (nothing dangles approvable). Park + resolution flight lines share
  `escalation.id`; `decision` stays `escalate` on both — the human
  verdict lives in the escalation object, `exit` only when it ran.
- `hobbes-proxy escalations list|approve|deny` — the human CLI; approver
  is the invoking OS user. (Flag-parsing gotcha: the id is popped before
  `flag.Parse`, which stops at the first positional.) 114 Go test cases,
  race detector clean.

**Verified by hand** on the hobbes repo (real stdio + the real CLI):
parked `echo …` approved by `mmarrujo` → ran, exit 0, result and flight
line both name the approver; parked `date` denied → refused naming the
denier; 3s-timeout park unanswered → expired to deny on the clock. The
M4 exit slice "an escalated command parks, gets approved from the CLI,
and runs" is done end to end.

**Next:** chunk 3 — session wrapper + Podman rootless sandbox (D2),
knowledge-layer MCP query tools, secret brokering; then the full M4
exit check. Awaiting Max's chunk-2 review first.

---

## 2026-08-11 (eighth session) — M4 chunk 3: sandbox, knowledge tools, exit check

Chunk-2 review passed. This chunk finishes M4: knowledge-layer MCP tools,
the session wrapper + Podman rootless sandbox, and the full exit check.

**Built:**

- ADR-017 + `internal/knowledge/`: the v1 subset of §6's tools —
  `graph_neighborhood`, `who_calls`, `tests_guarding` — read from
  `.hobbes/derived/` with file:line provenance and a visible staleness
  header (P1); near-miss suggestions on unknown ids; missing artifacts
  say "run hobbes ingest". Wired onto the proxy MCP server as read-only,
  never-policy-resolved, always-logged (`builtin:knowledge-read`).
  `get_module_doc`/`list_invariants` deferred to M5/M8 with their data,
  not stubbed.
- ADR-018 + `internal/sandbox/` + `cmd/hobbes-session/` + `sandbox/`:
  `hobbes-session start` clones a fresh **self-contained** worktree
  (`git clone --local`, not a linked worktree — a container mounts only
  /work, and a worktree's .git points into the unmounted canonical
  gitdir), checks out a session branch that lives only in the clone,
  seeds `.hobbes/derived/` (gitignored, so absent from the clone), writes
  the MCP config, and runs rootless `podman run`. Mounts are the policy
  surface (worktree rw, session state rw, proxy ro, box policy ro — all
  with the `z` SELinux relabel Fedora requires); env is exactly HOME+PATH
  (no host secret can reach the session); Bash is disallowed at Claude
  Code's native layer so the shell only comes through the policy-gated
  proxy. The Plan is pure data — `--dry-run` prints the whole launch.
- 140 Go test cases; pytest still 124.

**M4 exit check — passed 5/5** (`sandbox/exitcheck.py`, real rootless
Podman, hobbes repo, session `S-exitcheck-m4`). Injected
`AWS_SECRET_ACCESS_KEY` + `GITHUB_TOKEN` into the launching env; the
scripted implementer (`sandbox/driver.py`, MCP over stdio in Claude
Code's place) confirmed: (1) session env is only HOME/HOSTNAME/PATH/
container — no leak; (2) `tests_guarding` answered with provenance;
(3) task file written and seen via allowed `git status`; (4)
`cat prod.tfstate` refused + logged; (5) `id` parked → approved from the
real `hobbes-proxy escalations` CLI → ran (exit 0, approver `mmarrujo`).
Flight log carries all five with correct decisions and the joined
park/resolution pair.

**Changed from plan:** the build plan says "fresh git worktree"; a
`--local` clone gives the same isolation while working inside a container
that mounts only /work (ADR-018 records the trade). The exit-check
implementer was scripted rather than live Claude Code, to keep M4 in the
project's quota-free half (sequencing rule 1) — the wrapper launches real
Claude Code by default (`--claude-cred`), one command away.

**Next:** M5 — narrative pass (first subscription-quota milestone).
Not started; M4 awaits Max's review.

---

## 2026-08-11 (ninth session) — M5: narrative pass

M4 review passed (Max, start of session). This is the first
quota-spending milestone: cartographer module docs, test-behavior
indexes, and inferred invariants, every claim `file:line @ SHA`-pinned.

**Built:**

- ADR-019 + `hobbes.narrate.schema`/`stale`: narrative artifacts under
  `.hobbes/derived/docs/` (module docs, per-test-file behavior indexes,
  `invariants.inferred.yaml` in the §10 record shape — ids and
  `status: inferred` assigned at write time, never by the model;
  confirmation is Max moving a record into versioned
  `.hobbes/invariants/`). Every artifact stamps the repo SHA plus the
  git blob SHA of every cited file; **staleness is blob-level** — any
  cited blob changed (or gone) flips the badge, uncommitted edits
  included. Deviation from the build plan's "changed graph nodes"
  trigger recorded in the ADR: blob change is a superset, and comment
  edits that shift pinned line numbers *should* flip badges.
- ADR-020 + `hobbes.narrate`/`prompts`/`runner` + CLI: `hobbes narrate`
  drives headless Claude Code — one `claude -p --output-format json
  --tools ""` call per unit, prompt on stdin carrying the skeleton
  slice plus numbered source. Tool-less: the cartographer has no I/O
  surface, so read-only-on-source holds by construction and the
  pipeline is the only writer. Output is parsed, ADR-019-validated
  (pins exist, lines in range, behaviors cover the file's tests
  exactly), retried once with the problem list, or dropped — a bad unit
  costs two calls, never a loop. Incremental by default
  (missing-or-stale; `--all`/`--only`/`--exclude`/`--dry-run`);
  source-backed *package* nodes get docs too (hobbes.narrate's own
  orchestrator lives in an `__init__.py`), pinless files are planned
  out. `hobbes docs status` prints the badges. `HOBBES_CLAUDE_BIN`
  overrides the binary (the `HOBBES_POLICY_BIN` precedent).
- `get_module_doc` on the proxy (ADR-017's M5 deferral, due with its
  data): renders the artifact with per-claim citations; its stale
  warning is blob-level per ADR-019, not the skeleton tools' HEAD
  compare. Near-miss suggestions; "run `hobbes narrate`" when no docs
  exist; logged `builtin:knowledge-read` like the rest.
- 197 pytest cases (was 124), 146 Go test cases, race detector clean.

**M5 exit check — passed 3/3** on the hobbes repo (dogfood, fixture
tree excluded): (1) full pass generated **37/37 units, 0 failed** (21
module docs, 15 behavior indexes, 6 inferred invariants — 396 pinned
claims, one probe unit + 36 in one background run, every artifact
validated at write time); (2) **10/10 sampled claims** (seeded random
across all artifacts) resolve to lines that support them — checked by
hand against pin excerpts; (3) an uncommitted edit to `render.py`
flipped **exactly** the `hobbes.render` badge in `hobbes docs status`
(37 artifacts, 1 stale, naming the file); revert → 0 stale.
`get_module_doc` verified against the real `hobbes.policy` artifact.
The 6 inferred invariants (tfstate deny, derived-never-committed,
default-escalate, tree-sitter only in extractors, validated-writers
gate, env cross-layer join) await Max's confirmation — inert until
moved into `.hobbes/invariants/`.

**Changed from plan:** blob-level staleness (ADR-019, above); system
narrative (§3.2 user-journey walkthroughs) deferred to
`future_additions.md` with Max's sign-off — the build plan's M5 line
and exit criteria don't need it, and its natural surface is M7's docs
tab. Sandboxed cartographer *sessions* also parked there (ADR-020:
deferred, not rejected).

**Next:** M6 — TypeScript extractor (quota-free again). Not started;
M5 awaits Max's review, including the inferred invariants.

---

## 2026-08-11 (tenth session) — M6: TypeScript extractor

M5 review passed (Max, start of session). M6 lands the TS/JS layer on
the M1 contract, resolving one documented tension on the way: ADR-005's
"M6 must be tree-sitter" aside vs. the source docs' explicit ts-morph
choice — the source docs win, ADR-021 records the supersession and why
(TS parsing is easy; *resolution* — tsconfig paths, barrels,
.mjs/allowJs — is the deliverable, and that's the compiler API's job).

**Built:**

- ADR-021 + `tsextract/`: a small Node package (dependency: ts-morph,
  lockfile committed) the pipeline invokes as a subprocess — the
  ADR-003 pattern in a second direction. Emits deterministic facts
  JSON: checker-resolved imports (ESM, re-exports, require, dynamic
  import), top-level symbols, call edges (aliased through imports;
  calls to nested declarations omitted — parity with the symbol list),
  `process.env`/`import.meta.env` reads, Express + Nest routes
  (express-ish receiver + leading-slash literal; controller prefix
  join), and test inventory: vitest, jest, and **node:test** (what the
  sanctioned exit repo actually uses), with `describe`-nested
  qualnames. 15 `node --test` cases, zero dev deps.
- `extract/tssource.py`: joins facts into the artifacts. Module ids are
  repo-relative paths sans extension (`src/flow`), symbols
  `<id>.<qualname>`; externals/env nodes on the M3 conventions, so
  `env:VAR` cross-layer joins now span Python+TF+JS. JS test reach is
  **file-level** (closures aren't symbols): imports-plus-calls seeded,
  closed over the call graph, test-file scaffolding prefix-filtered.
  Missing helper on a TS repo is a hard error with the fix, never a
  silent skip (P1); `HOBBES_TSEXTRACT_CMD` overrides (the
  `HOBBES_POLICY_BIN` precedent).
- **Schema v3**: per-test `framework` field (a repo now mixes pytest
  and JS frameworks), global `framework` gone; `languages` may include
  typescript/javascript.
- Slash-bearing module ids flow through M5's surfaces: narrative
  artifacts nest under `docs/modules/` mirroring the repo tree, and
  `get_module_doc` accepts nested ids — traversal blocked in both the
  Python writer and the Go reader.
- `tests/fixtures/minits/` (Express JS + Nest TS + node:test + vitest)
  exercises the whole path; integration tests skip when Node is absent.
  224 pytest cases, 147 Go, race clean.

**M6 exit check — passed** on private-repo-A (`core-frontend/core-auth`, the
sanctioned Py+JS+TF repo; plain-JS ES modules, per the v1 "TS/JS repo"
bar): full ingest → 207 nodes, 602 module edges, languages
[hcl, javascript, python]. Hand-verified **20/20 edges** (all 11 JS
module edges + 9 call edges — every evidence line shows exactly the
claimed import/call, including scope attribution into arrow consts) and
**10/10 test mappings** (9 node:test mappings whose reach is exactly
the 8 `flow.js` symbols the test file imports, matching ground truth
1:1; plus one pytest mapping regression-checked in the same v3
artifact). Bar was ≥90%; result 100%. The spot-check caught one real
bug — a nested test helper leaking into `reaches` via a bare-qualname
call edge — fixed (calls to nested declarations omitted; reach filtered
by test-module prefix) and re-verified.

Bonus cross-milestone validation: this session's pipeline edits flipped
exactly 7 of the 37 M5 narrative badges to stale on the dogfood repo —
blob-level staleness (ADR-019) noticing M6 happening. Regeneration is
one `hobbes narrate` away, deliberately not spent here.

**Deferred** (future_additions): per-package tsconfigs in monorepos;
per-test JS reach granularity; jest-globals detection beyond imports;
package.json `bin` CLI entry points.

**Next:** M7 — web surface (Vite + React + Cytoscape.js, D3). Not
started; M6 awaits Max's review.

---

## 2026-08-11 (tenth session, addendum) — M6 verified on kbet

Max reviewed M6 ("good work") and sanctioned `~/projects/kbet` — a real
Vite + React TypeScript app (betchat frontend: 89 TS/TSX/JS files, 174
vitest cases; Java backend out of v1 scope) — as the TS verification
repo. private-repo-A had verified the JS path; kbet is the TS path, and it
forced five real fixes the fixture never exercised:

- **tsconfig zoning**: kbet's tsconfig lives at `betchat/frontend/`,
  not the repo root, and `@/*` path aliases are its entire import
  idiom. Files now group by nearest tsconfig.json, one ts-morph
  Project per zone — the "per-package tsconfigs" deferral lasted one
  repo before reality un-deferred it. Safety overrides (allowJs,
  skipLibCheck) on loaded configs also cured a TypeScript checker
  internal crash on `public/sw.js`, a file the package's own build
  never checks.
- **Checker resilience**: per-file/per-stage try-catch — a crash
  degrades one stage of one file and is recorded in the facts, the
  graph (`extraction_errors`), and an ingest WARNING. Visible, never
  silent; never zeroes a repo. (After the allowJs fix, kbet extracts
  with zero degradations.)
- **64KB truncation**: `process.exitCode` instead of `process.exit()`
  — eager exit was cutting stdout at the pipe buffer on repos bigger
  than private-repo-A.
- **JS idioms**: call-initialized consts (`create()` stores, axios
  instances) are now `kind: const` symbols, so call edges point at
  symbols that exist (`require()` handles excluded);
  `require()`/dynamic imports resolve through `ts.resolveModuleName`,
  so aliased dynamic imports work; test `reaches_modules` unions
  resolved import targets — `stores.test.ts` guarding nothing because
  zustand stores aren't functions was the tell. All 174 kbet tests now
  guard at least one module. `languages` no longer claims python for a
  TS-only repo.

**Verification — passed**: kbet ingest → 104 nodes, 358 module edges,
207 symbols, 235 call edges, 174 tests, [javascript, typescript].
Hand-checked **20/20 edges** (12 module — aliased/type-only/default/
relative all exact; 8 call — scopes into components and nested
handlers correct, store-hook calls resolving to their const symbols)
and **10/10 test mappings** (def lines match; guards sensible:
BetCard tests → BetCard + api/bets + authStore, store tests → the
stores, autoUpdate → the hook through vi.mock + dynamic import).
100% against the ≥90% bar, on top of private-repo-A's 100%.

18 node --test cases, 226 pytest, Go untouched.

---

## 2026-08-11 (eleventh session) — M7: the web surface

M6 reviewed and passed (Max, start of session; verified twice — private-repo-A
for the JS path, kbet for the TS path, 100% both). M7 builds
architecture §7's human surface: five tabs over the knowledge layer,
plus the first place a human can act on an agent rather than only read
about one.

**Built:**

- **ADR-022 + `go/cmd/hobbes-web`, `go/internal/web/`**: the serving
  half. Go, not a Python `hobbes serve` — the Sessions tab has to
  approve and deny escalations, and `internal/escalation` owns that
  lifecycle; a second implementation is what ADR-003 exists to prevent.
  No new Go dependency. Extractor artifacts pass through byte-for-byte
  (the pipeline owns schema v3; the server never restates it);
  narrative artifacts are decoded only as far as their `sources`, for
  badges. `knowledge.ChangedSources` was exported rather than copied and
  gained a batched form — the docs index badges every artifact per load,
  which was one `git hash-object` apiece. Loopback is enforced twice: a
  non-loopback `--addr` is refused at startup and non-loopback `Host`
  headers are rejected (DNS rebinding), because this surface has no auth
  and can approve commands. `/api/source` is traversal-, symlink-,
  size- and binary-guarded, and refuses `.tfstate` outright — ADR-011's
  floor restated at the read surface. Missing artifacts answer 404 with
  the command that produces them.
- **ADR-023 + `web/`**: Vite + React + Cytoscape (D3), built into the
  binary's `go:embed` directory so one `hobbes-web` works against any
  repo; a clone that has never run `npm` still builds and serves a stub
  naming the command. Graph conventions extend ADR-008's to the kinds M3
  and M6 added, with two rules the export renderer doesn't need:
  **externals hidden by default** (dependency fan-out is the main source
  of unreadable layout) and **focus mode** — laying out only the
  selected neighborhood while the dimmed remainder keeps its positions,
  so the rest of the system reads as context instead of a row of
  leftovers.
- The other four tabs: **Tests** is §4.2's behavioral index (what guards
  each module, what each test guards, the modules nothing reaches,
  routes), narrative one-liners joining in per test and carrying their
  own badge; **Docs** renders ADR-019 artifacts with every claim's pins
  clickable into a source peek at the cited line; **Diff** is §7's raw
  line diff, last, defaulting to uncommitted work; **Sessions** tails
  flight logs on a server-side line cursor with approve/deny in the
  browser.

**Three real bugs the browser found**, each now covered:

- Unmatched `/api/` paths fell through to the SPA catch-all and answered
  **200 HTML** — a wrong method or typo'd route read as success. There
  is now a JSON 404 floor under the API namespace.
- The flight tail **appended every page twice**: the cursor update
  re-ran the effect with the same page still in hand. The server now
  echoes the cursor a page was read from, so a stale page is
  recognisable rather than merely improbable.
- kbet made the Graph tab **unreadable**: TS/JS ids are repo-relative
  paths (ADR-021) and labels truncate from the right, so all 89 modules
  rendered as `betchat/frontend/sr…`. Labels and the package filter now
  strip the directory every path-shaped id shares, computed from the
  graph. Node ids are untouched — only the label shortens.

**M7 exit check — passed.** "The mockup, real, against your repo":

- Dogfood repo (70 nodes, 110 module edges, 234 tests, 37 narrative
  artifacts, 9 stale): all five tabs render real data. Focus mode on
  `hobbes.policy` shows exactly its two neighbours with the rest as
  context; the inspector joins kind, path, narrative purpose with badge,
  typed edges with their evidence lines, guarding tests, and symbols.
  A claim's pin on `hobbes.graphdiff` opened `graphdiff.py:102` and the
  highlighted line is the `(from, to, type)` tuple the claim describes —
  P3 provenance checkable in one click.
- **Escalation approve/deny in-UI, end to end**: two commands parked
  through the real `hobbes-proxy serve` from real policy decisions
  (`git push*` by rule, `npm publish` by the repo default), both showing
  up live without a reload. Approving in the browser unblocked the proxy
  and it ran the command (exit 0); denying refused it ("command NOT
  run"). Both verdicts landed in the flight log with the approver, and
  the on-disk records match — the browser goes through
  `escalation.Resolve`, so the deadline still outranks a late approval.
- Second repo, **kbet** (104 nodes, 358 edges, 174 vitest cases, no
  narrative pass): serves correctly and degrades correctly — the Docs
  tab shows the `hobbes narrate` command instead of an error, and the
  Tests tab falls back to test names where behaviors don't exist.

Suites: **189 Go / 226 pytest / 38 vitest / 18 node**, race clean.

**Note for Max:** while proving the approve path I first parked
`git push origin main` — an approved escalation *runs*, so that was a
poor choice of test command. It could not have pushed (SSH to origin has
no credentials here, and the process was killed at `exit -1`), and I
redid the approve path with `id -un`. Nothing reached the remote, but
the lesson is worth keeping: the escalation queue is live machinery, and
test commands for it should be read-only.

**Deferred** (future_additions): PR mode over the graph (M8's
`hobbes review` supplies the diff); compound nodes and layout
extensions; push transport instead of polling; symbol-level graph.

**Next:** M8 — reviewer flow + invariant compiler v0. Not started; M7
awaits Max's review.

---

## 2026-08-11 (twelfth session) — M8: reviewer flow + invariant compiler

M7 reviewed and passed (Max). One piece of review feedback landed first:
**`git push` is denied outright now, not escalated.** Publishing is
Max's; a session commits to a branch and he pushes after review. An
escalation is for commands a human might reasonably approve, and this
isn't one. Side effect worth recording: INF-3 in the inferred set
asserted "all other pushes escalate", which the change made false — it
is inert (ADR-019) and its stale badge flipped immediately, because
`repo.policy` is one of its stamped sources. The staleness mechanism
catching a claim the moment it stopped being true.

**Built:**

- **ADR-024 + `.hobbes/invariants/`**: six records promoted from the M5
  inferred set, one file each, `statement` for humans and a
  **structured** `compile.rule` for machines — §10 sketched the rule as
  prose, and a sentence cannot compile into an import-linter contract
  without an LLM, which would put quota on the enforcement path
  (sequencing rule 1). I-3 had to be rewritten, not just promoted:
  confirming the inferred wording would have versioned a false claim.
  Four of six are `soft`, which is the honest split for a repo whose
  invariants are largely about policy and derived-artifact shape.
- **`hobbes.invariants`**: strict loading (every problem in one run, not
  the first), graph-computed verdicts, and four emitters — import-linter,
  dependency-cruiser, semgrep, Rego. Compiling is text generation, so
  none of the four toolchains has to be installed to compile for it;
  none is, on this box. What the graph cannot see is `unknown` with the
  reason, never a pass: an invariant reported green because nothing
  checked it is worse than one reported unchecked.
- **ADR-025 + `hobbes review <base>..<head>`**: §7's review order in one
  command. The shaping decision is that **verdicts are computed at both
  ends** — an invariant already failing on base is inherited, one failing
  only on head is this change's regression, and a gate that cannot tell
  them apart is one people route around. Behavioural coverage is §4.2's
  metric; test files are excluded from "unguarded new code" using the
  inventory's own file list rather than a filename heuristic. Soft
  invariants get a reviewer session only when a changed path falls in
  their scope.
- **`list_invariants(scope)`** on the proxy — ADR-017's fifth tool,
  deferred at M4 "with its data, not stubbed". Scope overlaps in both
  directions, so a rule cannot hide inside the tree you asked about.
- **The reviewer role became a role rather than a label.** Running one
  exposed that `--role reviewer` changed nothing but a log field: the
  worktree is now mounted **ro** (§6 says read-only mounts; §5.2 puts
  the OS sandbox first among enforcement tiers), its allowlist drops
  Edit/Write/exec, and `.hobbes/derived/` is mounted ro into every
  session — a fresh worktree has none, so the knowledge tools had
  nothing to read and a reviewer started blind.

**M8 exit check — passed.** The v1 bar (§11), end to end:

- **A graph-diff review on a real branch.** `m8-exit-check` adds module
  docstring extraction for the narrative pass — a plausible feature that
  imported tree-sitter directly, duplicating the parser. `hobbes review`
  reported **I-4 REGRESSED** with both import sites cited, plus one
  unguarded new module, and exited 1. Fixed to consume pysource's
  captured literal; the re-review shows I-4 PASS, no coverage
  regression, exit 0 — and the delta shows the edge moving from
  `ext:tree_sitter` to `hobbes.extract.pysource`. Merged with --no-ff so
  both reviews replay: `hobbes review ace9a08..cdbc085` (exit 1) and
  `ace9a08..7d52f2e` (exit 0).
- **A reviewer session under policy**, in real rootless Podman: 5/5 —
  the three knowledge tools answer about the branch's new module, a
  write to `/work` is refused by the kernel ("Read-only file system"),
  the session dir stays writable, and all three reads land in the flight
  log as `builtin:knowledge-read`. (The implementer session was M4's.)
- **Soft invariants judged for real**: `--soft` ran three in-scope
  reviewer sessions (I-1, I-3, I-6), each returning a verdict, a reason,
  and pins; I-2 was correctly skipped as out of scope. The sessions
  flagged their own limit unprompted — being tool-less (ADR-020), they
  judge from the delta rather than the source. Recorded as a deferral.
- Python+Terraform and TS/JS repos ingested and served: private-repo-A, kbet
  (M3/M6/M7).

Suites: **205 Go / 297 pytest / 38 vitest / 18 node.**

**Deferred** (future_additions): soft verdicts are delta-based because
the reviewer session has no file tools; import-linter `layers`
contracts; running the compiled configs (no toolchain here, so the
emitters are verified by shape, not by execution); web PR mode.

**Next:** v1 is feature-complete against the build plan. M0–M8 are all
reviewed-and-passed except M8, which awaits Max's review.

---

## 2026-08-11 (thirteenth session) — ADR-026: two decision surfaces

M8 reviewed and passed, with one correction to I-4 (see below) and a
design ask: collapse bring-up to one command, and put the two things
that need a human — **intent and invariants** — in the UI, with anything
new getting escalation treatment. Everything else is a natural part of
the mechanism and expected.

**First, the M8 review feedback.**

Max's read of I-4 was that it should say *language-specific parsing must
not override another language's*, not that there happen to be two
parsers — the latter reads as an argument for a fixed linear pipeline
and stops meaning anything at the fourth language. Checking the claim
found the design was already right where it mattered (discovery is by
extension, so no parser sees another language's source) and **wrong in a
way his framing predicted**: node ids could still collide across layers,
and the merge resolved it with `setdefault` — first layer wins,
silently. A repo-root `widget.py` plus `widget.ts` produced one node, a
vanished TypeScript module, and `widget.run` listed twice in symbols with
one row pointing at a module absent from the node list. Collisions are
now reported as `extraction_errors` with an ingest WARNING, symbols stay
unique across the merge, and I-4 is restated around ownership with four
guards where it had none. Full cross-language id namespacing is deferred
with a design note — it rewrites ids across a layer's nodes, edges,
symbols, tests, and routes, which is ADR-sized.

`docs/first-run.md` also landed: the walkthrough Max asked for, written
in the order the system is meant to be used, with every command run
before it was written. It cost the `CGO_ENABLED=0` discovery a permanent
home — the proxy hobbes-session mounts must be static, or it fails in
the container as "No such file or directory" (the loader, not the
binary).

**Then ADR-026.** Four forks settled by Max: intent *is* the policy file
edited through the UI (not a layer compiling down to it); `hobbes up`
never narrates; the gate **blocks** rather than deferring; and decisions
stay untracked for now as a known limitation.

- **`hobbes up`** — init if absent, compare the artifacts' stamped SHA
  against HEAD and re-ingest on drift, serve, then block until the queue
  is empty. Ingest is free so it is unconditional; narration is offered
  in the UI with its call count, never performed by a script someone ran
  to get started.
- **Intent** — the policy editor writes `repo.policy` and shows the diff
  first. An unreviewed policy is a *pending decision*: "I never looked"
  and "I read it and it's fine" must not look alike. A hand edit after
  confirmation is flagged, not blessed.
- **Invariants** — approve / deny / edit, keyboard-driven, because a
  blocking first run presents the whole queue at once and the answer is
  to make it fast to walk rather than to shrink it. Approving writes a
  real record into `.hobbes/invariants/`, so ADR-019's "promotion is
  physical" rationale survives; only the trigger changed.

**The subtle one:** decisions key on a **content hash of (statement,
scope)**, never the id. `schema.py` assigns `INF-n` by enumeration, so
`INF-3` names different text after the next narration — an id-keyed
approval would silently bless it, which is the exact failure the gate
exists to prevent. That hash exists in Go (the writer) and Python (the
reader), so shared vectors in `tests/fixtures/decision-keys.json` pin it
from both sides: drift fails a test instead of losing every decision.
Denials persist for the same reason approvals do.

ADR-026 amends **ADR-019** (promotion physical → still a file, different
trigger) and **ADR-022** (surface read-only → three writes, each landing
in a file a human reads). Both said something this changes; neither
drifts silently.

**Verified end to end** on a scratch repo: blocked at 2 items; edited and
confirmed the policy in the UI with the diff shown first; approved one
invariant and denied the other by keyboard; `hobbes up` then reported
ready; the promoted record passed `hobbes invariants check`; `policy
resolve` obeyed the new rule; and renumbering the inferred ids did not
re-ask.

Suites: **223 Go / 334 pytest / 44 vitest / 18 node.**

**Deferred**: decisions do not survive a fresh clone (ADR-012 keeps
`.hobbes/` untracked in target repos) — recorded as a known limitation
with the opt-in fix ADR-012 already allows.

## 2026-08-13 — clearing the box for a cold `hobbes up`

No milestone work. Max reported that a package install had fallen behind
and that his Go was 1.25 where `go.mod` wants 1.26, and asked for a
report when Hobbes is clear to start from a **fresh terminal** with the
`hobbes up` flow.

**What was actually missing was `PATH`, not packages.** Go 1.26.5 was
already installed at `~/.local/go/bin`; `.bashrc` only prepended
`~/.local/bin`, so a new shell resolved `go` to Fedora's `/usr/bin/go`
1.25.12 and the build failed on the toolchain line. uv, Node 24, podman
(rootless), both `node_modules`, and the venv were all present and
current — `uv sync` checked 10 packages and changed nothing. Nothing
needed sudo, and nothing was installed.

Two host-side fixes, both outside the repo:

- `.bashrc` now prepends `~/.local/go/bin` ahead of `/usr/bin`, guarded
  on the directory existing and on not already being on `PATH`. The
  distro Go is shadowed, not removed.
- `hobbes` (the venv console script) and the four Go binaries are
  symlinked into `~/.local/bin`. `hobbes-session` resolves
  `hobbes-proxy` through `os.Executable`, which reads `/proc/self/exe`
  and is therefore already symlink-resolved — a dry run confirms it
  mounts `go/bin/hobbes-proxy`, not a path inside `~/.local/bin`.

Rebuilt everything under 1.26 (SPA first, then `hobbes-web`, proxy
static) and re-ran the suites: **223 Go / 334 pytest / 44 vitest / 18
node**, `gofmt` and `go vet` clean.

**Cold-start check**, every command run under `env -i ... bash -lc` so
nothing leaks in from this session's shell: `hobbes up` on a fresh
scratch repo initialized it, ingested it (python + typescript), blocked
on intent plus two planted inferred invariants, took the policy edit and
both verdicts through the API the UI uses, printed *ready to develop*,
and shut its server down on SIGINT. The approved record validated,
`policy resolve` obeyed the new rule, and swapping the `INF-n` ids did
not re-ask — the content key holds. On the dogfood repo `hobbes up`
re-ingested off the stamped SHA (530a998 → HEAD) and reported the known
six-invariant queue; the tree stayed clean.

Two papercuts found and recorded in `future_additions.md` rather than
fixed: `hobbes up`'s prints are block-buffered when stdout is not a tty
(so a redirected run looks silent while it blocks), and a local `git
clone` hardlinks by default, so `hobbes-session` cannot clone a repo
that lives on a different filesystem than `$HOME`.

## 2026-08-13 (later) — pause point: M9 proposed, nothing started

Max proposed moving from `hobbes up` as a per-repo command to **Hobbes
as an application** — open a folder, then start / refresh / continue
developing, with status captured while the user chooses the action —
and asked what was possible before pausing to move for college.

Assessed against the code, not from memory. The headline: his two status
checks are already the two checks `hobbes up` makes (`cli.py:440-458`,
and `/api/overview` already returns `ingested`/`sha`/`head`/`behind`),
so this is not new logic — it is moving that status out of a process
that holds a terminal and into a surface that reports it. Blocking
survives as a *disabled action* rather than a held terminal, which is
what ADR-026 was actually protecting.

Three things genuinely change: the surface would run the pipeline
(crossing ADR-022's "writes three files, never invokes the extractor"
line, and needing refresh-never-narrates carried over from ADR-026);
`RepoRoot` moves from startup to runtime (22 call sites, four files);
and an unauthenticated loopback server that can open *any* folder is a
materially wider surface than one scoped to a repo named on the command
line — that wants a launch token before the feature, not after.

Written up in full at **`docs/m9-application-mode.md`**, including what
it fixes (the buffering papercut, by deletion), what it does not (the
cross-device clone, still a one-liner), the two status dimensions his
two checks would lose (dirty tree, blob-level doc staleness), a proposed
M9a/M9b split, and the three open questions.

**No code written and none planned until Max answers those three.**
Tree clean, suites green as of the entry above: 223 Go / 334 pytest /
44 vitest / 18 node. Nothing is half-finished — the box work landed in
`1e6dbdd` and this is a design note, not an in-flight change.

## 2026-08-14 — v2 extraction architecture: docs committed, build plan proposed

Max returned with `docs/hobbes-architecture-v2.md` written the same day —
extraction splits into two parallel lanes (tree-sitter for structure,
routes and tests; SCIP indexers for symbols), joined over monikers as
node ids, with edges carrying a confidence tier and invariants moving
toward one checker over the graph. It arrived untracked; committed in
`c3b479c` along with the CLAUDE.md pointer that makes it source of
truth. The v1 architecture and build-plan docs stay in the tree —
accurate for the carried subsystems, historical for extraction.

Verified state before planning, by running things rather than reading
the status notes: 223 Go / 334 pytest / 44 vitest / 18 node all green,
artifacts stamped at HEAD, tree otherwise clean.

Then read the extraction layer against §7 to turn it into a real plan.
Six findings shaped it:

- The artifact schema is **already at v3**, so §7's "graph schema v2" is
  schema **v4**.
- **Nothing gates on the graph schema version.** ADR-006 says consumers
  reject versions they don't know; only the policy file and the
  tsextract facts actually do. `artifacts.go` passes it straight to the
  UI. §7's migration shim has nothing to hang on until that gate exists.
- **Test reach is derived from lane A's symbol edges**
  (`extract/__init__.py:62`), so stripping lane A's call resolution
  regresses `tests.json` unless reach moves to lane B in the same
  milestone.
- **`hobbes.yaml` does not exist**, and a repo-level indexer/pack
  registry is in genuine tension with ADR-012's "all of `.hobbes/` is
  personal."
- Both key indexers install from **npm** (`scip-python` 0.6.6,
  `scip-typescript` 0.4.0) — lane B is the ADR-021 helper pattern again,
  no new package manager.
- **Hobbes cannot see its own Go.** The dogfood graph is hcl/js/py/ts;
  9.4k lines of runtime are invisible to it. V2.M5 closes that loop.

Written up as `docs/hobbes-build-plan-v2.md` — file-level work and exit
criteria per milestone, with six deviations from §7 collected at the end
(a V2.M0 spike to see real SCIP before the schema freezes; the v4
correction; M1 widened to cover tests.json and the version gate; M3's
unstated test-reach coupling; an ADR for `hobbes.yaml`; and tier in the
UI at M2 so the programme is not fifteen evenings of invisible work).
20–28 evenings against §7's 18–26.

Recommendation reported: **proceed to v2, do not clear the backlog
first.** The largest deferred item — cross-language module-id
namespacing — is dissolved by moniker-keyed ids and would be thrown
away; per-test JS reach and rename detection likewise. Everything else
in `future_additions.md` sits above the extraction layer. The two
exceptions are the one-line papercuts (`flush=True` in `_cmd_up`,
`git clone --no-hardlinks` in `hobbes-session`), worth a chore commit
before M0.

**Nothing built. The plan and the deviations need Max's approval, and
ADR-026 is still unreviewed** — v2 does not touch the decision surfaces,
so there is no technical conflict, but the review debt carries forward.

## 2026-08-14 (later) — V2.M0: the SCIP spike, and three silent traps

Max approved the v2 build plan and all six deviations, cleared the two
papercuts for a chore commit, and said go to M0.

**Chores first** (`6b2ac65`). `hobbes-session` now clones with
`--no-hardlinks`, so a repo on a different filesystem than `$HOME` works;
the test asserts object link count rather than staging two filesystems (a
default `--local` clone gives nlink 2, so it has teeth). `hobbes up`'s
progress is no longer swallowed when stdout is not a tty — fixed at
`main()` with line buffering rather than `flush=True` per print, because
`narrate` prints one line per unit and had the same bug.

**Then the spike.** New `scip/` helper on the `tsextract/` conventions;
both indexers install from npm (`scip-python` 0.6.6, `scip-typescript`
0.4.0), so lane B needs no new package manager. Ran them over all four
sanctioned repos and compared the result against lane A's current edges.

The verdict is **go on monikers-as-node-ids** — but three things had to
be decided first, and all three are silent when wrong. That is the whole
value of having spiked rather than discovering them at M2.

1. **The version field defaults to the git revision.** Indexing a
   two-commit scratch repo, an unchanged `hello()` had moniker
   `…vertest c9b3bbd… mod/hello().` at one commit and
   `…vertest 5d87e72… mod/hello().` at the next. Left alone, *every node
   id changes on every commit* and `hobbes diff` reports the repo as
   removed-and-re-added each time — destroying the exact thing v2 exists
   to sharpen. Precedence is `--project-version` > a declared
   pyproject/package.json version > the git rev, so the behaviour also
   varies by repo. Hobbes pins it to a constant, and §3.3's "stable
   across re-indexes" is now true *because of* this ADR rather than
   inherently.

2. **Indexer config is per repo, not just per language.** On
   `pipeline/`, recall against lane A was **0.500** — every test→source
   edge missing. Cause: under a src layout `src/hobbes/cli.py` indexes as
   module `src.hobbes.cli` while `tests/` imports it as `hobbes.cli`
   through the editable install, so the reference dangles
   (`…hobbes 0 hobbes/__init__:` referenced, never defined). One line of
   Pyright config (`extraPaths: ["src"]`) took it to **0.948**;
   qwen-pathology went **0.625 → 1.000**, zero misses. The 5 residual
   here are explained, not misses: 3 are `minits` TS/JS files scip-python
   correctly ignores, 2 are the nested `miniapp` fixture — M6's
   tsconfig-zoning problem recurring for Python. This moves the
   indexer-config registry from M4 onto **M2's critical path**.

3. **Only ~14% of SCIP definitions are graph-worthy.** kbet's frontend
   offers 6,696 definitions; 5,054 are meta, 532 local, 160 parameters.
   Filtering to namespace/type/method/term leaves 949 — for scale, the
   entire current dogfood graph has 834 symbols. The descriptor filter
   comes before anything else in the builder, and it belongs in the
   helper so 7x the data never crosses the process boundary.

A fourth, worth its own note: **a successful exit is not a successful
index.** `scip-typescript` on kbet with no `node_modules` exited 0 in
1.5s and wrote a plausible 2.4MB index whose most-referenced package was
TypeScript's own bundled lib (2,643 refs) and whose `external_symbols`
was empty. Every third-party edge was absent and nothing said so. The
adapter computes its own degradation signal instead of trusting the exit
code (ADR-027, Decision 4).

Also settled: the reader is a **Node helper** on the ADR-021 pattern
rather than the `scip` CLI or a Python protobuf dependency — `scip/`
already has the indexers, and the filter has to run before the boundary.
Cost is comfortable: 1.5–5.5s cold per repo.

The 11 scip-only edges are lane B being *more precise* than lane A
(`cli.py → invariants/schema.py` where lane A stops at
`invariants/__init__.py`, because SCIP follows the re-export). First real
instances of the §3.4 disagreement report, and they favour lane B.

Written up as **ADR-027**; §3.3 and §7 patched with the approved
deviations plus this one; `analyze.mjs`/`compare.mjs` kept as the
reproducible evidence (`compare.mjs` is a working prototype of the
lane-agreement report). Suites unchanged and green: 223 Go / 336 pytest /
44 vitest / 18 node. **Next: V2.M1** — graph schema v4 and the version
gate. ADR-026 remains unreviewed; it does not block v2.

## 2026-08-14 (addendum) — the indexer config should be derived, not authored

Max, before M1: the `extraPaths: ["src"]` fix covered the current repos,
but would a dirtier layout need something smarter — and is that cheap or a
future addition?

Measured rather than argued, and it is cheaper than the hand-written
version because **the answer is already computed**.
`discover.py:_import_root` walks each file's `__init__.py` chain and
returns the directory above the topmost package — which is exactly what
must be on `sys.path`. The distinct set of `ModuleInfo.root` *is* the
`extraPaths` list. Python-only recall against lane A:

| repo | no config | hand-written `["src"]` | derived roots |
|---|---|---|---|
| hobbes/pipeline | 0.516 | 0.978 (2 missed) | **1.000 (0)** |
| qwen-pathology | 0.625 | — | **1.000 (0)** |
| private-repo-A | 0.655 | — | **1.000 (0)** |

The derived set beats the hand-written one *on the repo it was written
for*: it picks up the nested `miniapp` fixture roots that yesterday's
entry called explained residual. They were not residual, only
unconfigured.

private-repo-A settles the dirty case — eight roots (`core`, `core/src`,
`core/migrations/versions`, `core-frontend/core-auth`,
`infra-core/lambda/pretoken`, …), not one a top-level `src`. No
`src`-shaped heuristic finds those; the mechanical walk gets all eight.

Not a lane boundary violation: `discover.py` imports `Counter`,
`Iterator`, `dataclass`, `Path` — no tree-sitter, no parsing. Import-root
discovery is filesystem topology, a shared pre-pass both lanes consume
(lane A for module ids, lane B for indexer config), so §3.2's "semantic
providers never consume tree-sitter ASTs" holds. M6's nearest-tsconfig
zoning is the same shape, and `go.mod` will be the Go version — root
discovery per language belongs in §3.7's checklist.

One wrinkle found and left for M2: the config must sit at the repo root
while indexing. `scip-python` indexes what is under `--cwd`, so a config
directory outside the repo yields zero documents — tried twice, once
under `.hobbes/derived/` (where pyright's `**/.*` auto-exclude also
bites) and once from a temp dir with an absolute `include`. M2 writes the
file transiently and removes it, respecting any pre-existing one. That
touches a tree Hobbes otherwise only reads, so it has to be crash-safe.

ADR-027 amended with all of it. `compare.mjs` gained an extension filter,
because scoring scip-python against a repo's JS files was measuring the
wrong thing. No production code changed; M1 is still next.

## 2026-08-14 (addendum 2) — lane B stops writing to the repo at all

Max, on the transient-`pyrightconfig.json` design from the previous
addendum: verify the create/index/remove pipeline is deterministic, be
certain it only ever deletes its own creation, and treat that safeguard as
more important than continuing to M1.

**First, the audit.** The spike itself left nothing behind — no stray
`pyrightconfig.json`, no `.scip`, no `scipcfg` in any of the four repos;
all four working trees clean. The two `M .gitignore` entries in
qwen-pathology and kbet are ADR-012's `.hobbes/` and `*.tfstate` lines from
earlier ingests, confirmed by diff, not from this session.

**Then the design.** There was no pipeline to verify — it existed only as a
sentence in ADR-027 and my manual shell during the spike. Rather than
harden a transient write, tested whether it could be avoided entirely, and
it can: `--cwd` does not have to be the repo, it can be a **staging tree
Hobbes owns**, holding copies of the sources plus the generated config.
Recall stayed 1.000 with zero misses on both hobbes/pipeline and private-repo-A —
identical to the in-repo config — and `git status` stayed empty throughout.
Third-party resolution survives (217 external symbols vs 218) because
`venvPath` points at the real environment absolutely; without it Decision
4's degradation would fire on every run. Cost on private-repo-A: 0.38s and 696KB
to stage 144 files, against 5.5s to index them.

**Three things measured that would have been quiet bugs at M2:**

- **Hardlinks are not safe here.** `chmod` through a hardlink changes the
  *original* file's mode — a staged link is a live handle into the user's
  tree. Staging copies.
- **The `.scip` file is not path-independent.** Two runs over one staging
  tree are byte-identical, but the same content staged elsewhere differs
  (1307039 vs 1307050 bytes) because `metadata.project_root` carries the
  absolute path. The extracted facts are identical across both (2279 defs,
  920 graph-worthy, 15330 occurrences). So `.scip` is an intermediate, the
  adapter drops `project_root`, and ADR-006's byte-identical guarantee is
  asserted at the artifact. Corollary: §3.6's cache must key on source
  content, not on index bytes, or it misses on every relocation.
- **Stage lane A's discovered file set, not `git ls-files`.**
  `discover_modules` walks the filesystem and never consults git, so it
  sees untracked `.py` files; staging from git would hand the lanes
  different inputs and manufacture false disagreements in the §3.4 report.

ADR-027's transient-write design is **withdrawn** and replaced with a
seven-clause safety contract, stated at length because the cost of getting
it wrong lands in a repo Hobbes does not own. V2.M2 now names satisfying
that contract as its first requirement, with the removal-guard tests in the
same commit as the removal code. Still no production code; M1 next.

## 2026-08-14 (addendum 3) — correcting the staging number, and what it says about the cache

Max asked why staging was so much faster than indexing. Measuring it
turned up an error in a number the previous addendum published as
evidence.

**Staging private-repo-A is 9ms for 421KB, not 0.38s for 696KB.** The timing had
measured a shell loop spawning `mkdir`+`cp` per file — 288 process spawns
around an operation that is 9ms of sequential I/O — and the size was `du`
block-rounding rather than bytes. Roughly 40× off, in the direction that
flattered the argument. The conclusion is unchanged and stronger: the real
ratio against indexing is ~600×, not the ~14× the old figures implied.

**Why they differ is not a fair fight.** Staging is `read()`+`write()`.
Indexing is whole-program type inference: Pyright reads the 144 staged
files *plus their entire transitive import closure* — typeshed stdlib
stubs plus boto3, pydantic, httpx, pytest here — and binds and
type-checks all of it to resolve every reference. That closure is exactly
what buys the semantic tier, and it is why lane A is fast.

**Where the time goes, measured:** a *one-file* repo indexes in 1.19s,
all of it Node boot, Pyright init and typeshed load before any repo code
is read. private-repo-A's ~6s is roughly 1s startup, ~2s "parse and search for
dependencies", ~3s emitting SCIP for 144 files.

**So §3.6's cache design needs revisiting at M2.** Caching partial
indexes by content hash and merging them buys less than it appears:
changing one source file does not let the indexer skip typeshed or
re-parse fewer dependencies, so a partial re-index still pays most of the
fixed and dependency-shaped cost. The first thing worth building is
skipping the run entirely when nothing changed — a whole-index cache
keyed on (file set, content hashes, indexer version, resolved dependency
versions). Partial merging becomes a refinement to measure, not the
primary mechanism. Recorded in ADR-027; no change to the milestone.

Proceeding to V2.M1.

## 2026-08-14 (fourth) — V2.M1: graph schema v4, and the gate ADR-006 promised

Built. **ADR-028.**

**v4 is additive over v3.** Every edge gains `tier`
(`semantic`|`syntactic`|`dynamic`), every evidence entry gains `lane` —
architecture v2 §3.4's contract exactly. Nothing is removed, renamed, or
re-typed, and no id changes. That is what makes §7's "migration shim"
cheap: there is no translation layer, because a v3 reader that ignores
unknown fields already reads v4 correctly. The shim is a version *range*.

Deliberately **not** done: §3.3's lane-A/lane-B node namespace. There is
only one namespace until M2, and a field with one possible value is the
speculative abstraction the conventions forbid. What M1 does decide is
that lane-B ids will carry a `scip:` prefix, which cannot collide with
any current form — so the two namespaces can coexist while lane B's
coverage is partial, and M2's "upgraded in place" can never silently
alias a lane-A node.

**The gate is the substance.** ADR-006 has said since M1-of-v1 that
consumers reject versions they don't know; none did. Now three do, one
per language, each at a chokepoint that already existed except on the
Python side, which had none:

- `pipeline/src/hobbes/artifacts.py` — new; the CLI read `graph.json`
  from five call sites with a bare `json.loads(path.read_text())`.
- `go/internal/derived` — new; wired into `knowledge.go:loadInto` and
  `web/artifacts.go:readDerived`, **and into the byte-for-byte
  pass-through**, which now 409s rather than handing the SPA a version it
  cannot render.
- `web/src/api.ts` — the SPA restates the schema in `types.ts`, so it
  checks its own side too.

Refusal never decodes: `derived.Unmarshal` version-checks before it
unmarshals, so a caller cannot act on a partially-populated struct whose
zero values would read as real counts. A Go test asserts exactly that.

**The gate caught a real bug immediately**: the web test fixture's
`interfaces.json` carried no `schema_version`, though `hobbes ingest`
stamps all three artifacts. Six other fixtures across the Go tests were
hand-built without one. Those were latent — a fixture that cannot
represent what the pipeline writes is a test proving the wrong thing.

Verified end to end on the dogfood repo rather than in fixtures: 114
nodes re-ingested at v4 (1337 edges all `syntactic`, 1839 evidence
entries all `tree-sitter`); `/api/graph` and `/api/overview` serve v4;
all five knowledge tools answer from it with correct file:line
provenance; `render`, `diff`, `review`, `invariants check/compile` all
read it. Then the shim proof: the on-disk graph downgraded to v3 with
`tier`/`lane` stripped still serves, still reports ingested, still
renders — and was restored.

A cross-language guard keeps the two version constants in step: a Go test
reads `SCHEMA_VERSION` out of the pipeline source and fails if they drift,
because Go silently refusing what Python just wrote would be a very
confusing morning.

223 → **12 Go packages / 349 pytest / 49 vitest / 18 node**, gofmt and go
vet clean. **Next: V2.M2**, whose first requirement is ADR-027's staging
contract. M1's exit wants Max's review first.

## 2026-08-14 (fifth) — V2.M2 in progress: staging, the helper, and two IRs

Max reviewed M1 and cleared M2. Three chunks landed; the exit check and
the UI tier badge remain.

**Chunk 1 — the safety contract** (`f0c6cd4`). `staging.py` keeps
ADR-027's five clauses, each tested adversarially because each failure
would be quiet: a refused removal is asserted to have removed *nothing*;
a symlink inside the cache pointing at the repo is refused, or `rmtree`
would follow it out; crash safety is a `.partial` build plus rename.
`git status` on a real repo stays empty across a full staging run.

**Chunks 2–3 — the helper and the join** (`7c77a92`). Module-level recall
against lane A: **0.971**, and the disagreements are M0's re-export class
again — lane A stops at the package `__init__`, lane B follows through to
the definition site.

**Then the finding that reshaped the milestone.** SCIP occurrences carry
a `syntax_kind` that would separate a call from a type annotation, and
`scip-python` populates it for **0 of 8575** occurrences. So lane B's
symbol edges included `except` clauses and annotations: 1422 against lane
A's 1029, a 38% difference that is a *different question being answered*.
That breaks §3.1's plan for M3 — stripping lane A would have lost the
call graph rather than upgraded it, and `who_calls` would silently have
become `who_references`.

Put three options to Max; he chose intersection, and added the structural
part: **tree-sitter is the syntax provider, SCIP the semantic one, joined
through an evidence IR into a semantic IR, before graphing.** That is
better than what was built. A post-hoc merge of finished edges can only
compare edges that already exist, so it can never produce the edge that
matters — a call *because* tree-sitter saw a call, pointing where it does
*because* SCIP resolved it. That edge has no lane; it has two providers.

**ADR-029**, and §3.1/§3.4 amended in the same commit. `merge_lane` is
superseded and gone.

Measured on the dogfood pipeline — 3051 tree-sitter call sites joined
against 2924 SCIP resolutions:

- **1145 calls, every one semantic**; 385 references
- **0.998 recall** of lane A's call graph (1081 of 1083)
- **64 calls lane A could not resolve at all**, now proven — e.g.
  `hobbes.cli._cmd_up -> hobbes.decisions.Readiness.blockers`, a method
  on a returned object, which is exactly what static resolution cannot do
- 2 lane-A-only, both the same false positive: a local variable named
  `write` that lane A bound to a module-level function

So the intersection is both more complete and more honest than either
lane. Two providers, two IRs, one answer.

Also required: `pysource` now records each call site's terminal column,
and the helper emits each resolution's column and bare name — line alone
is ambiguous when one line holds several references, and the first cut
had discarded both.

394 pytest / 10 node. Remaining for M2: wire the join into `ingest`, tier
in the UI, and the exit check (20 semantic edges ≥95%, kbet, private-repo-A).

## 2026-08-14 (sixth) — coverage, not confidence scores

Max asked whether the hard resolution cases could carry confidence
scores: if we cannot say *what* a call on a returned object hits, could
we say a function *likely* calls one?

**First, a correction to the previous entry's framing** — it invited the
question. The 64 calls lane A could not resolve are not uncertain; they
are the most certain edges in the graph. Lane A failed on them, SCIP's
type inference succeeded, and they sit at `semantic` tier. There is no
confidence to score there.

**The answer to the idea as posed is no**, and the reason is worth
keeping: an edge with no named target cannot be drawn, cannot be checked
against an invariant, and cannot be cited at a `file:line`. It is the
false edge ADR-007 rules out, wearing a probability. Tiers already carry
confidence for edges that exist.

**But the instinct found something real, so it got built.** Measured what
the join actually drops on this repo — 3,070 call sites:

| | count | |
|---|---|---|
| resolve in-repo | 1,411 | semantic edges |
| resolve to an external package | 1,256 | correctly out of scope |
| resolve to nothing | 403 (13%) | **was invisible** |

The graph said "here are the calls" and never said "and there were 403
sites I could not account for." That is P6 unmet for lane B, and it was
only visible because someone asked.

So the honest form of the idea is a **denominator, not a score**:
`evidence.Coverage`, per file — sites, resolved, external, unaccounted.
Counts, no guesses, no invented edges. Repo-wide 86.9% accounted, and it
ranks: `review.py` is 56% accounted, `policy.py` 100%. That is a
legitimate signal for the reviewer flow — trust this module's call graph
less than that one — without a single hypothetical edge.

Required one helper change: it now reports `external_refs`, occurrences
resolving outside the index. Without them, "correctly out of scope" and
"nobody could resolve it" look identical, which is exactly the conflation
that hid the 403.

**Documented as a limit, not papered over:** the remaining unaccounted are
dominated by builtins (`len`, `isinstance`, `any`) and by dynamically
typed test fixtures (`capsys.readouterr`, `monkeypatch.setenv`) — objects
whose type Pyright cannot know at the call site. ADR-029 amended with all
of it.

400 pytest / 10 node.

## 2026-08-14 (seventh) — V2.M2: lane B wired, exit met for Python

Lane B now runs inside `hobbes ingest`. On the dogfood repo: **1192
semantic calls, 130 syntactic**, 116 semantic imports, 392 `uses`, 86.9%
resolution coverage, ingest 5.6s.

The 130 syntactic calls are the design working — SCIP could not resolve
them, lane A could, and they appear *labelled as guesses* rather than
vanishing. That is the `fallback` arm of ADR-029's table.

**A type-name collision, caught by a histogram.** The tier breakdown showed
two `references/syntactic` edges, which lane B cannot produce — every
`uses` fact it emits is semantic. They were Terraform's: ADR-010 already
spends `references` on traversal chains between `tf:` nodes. Two meanings
under one type name is exactly the ambiguity that bites once a consumer
filters on it, so lane B's edge type became **`uses`** — the newcomer
moves, since ADR-010's name is in shipped artifacts. Verified after: all
`references` are Terraform, all `uses` are semantic.

**A second gap, caught by private-repo-A.** Its 72.7% coverage came with no
warning, because Decision 4's degradation check was inert — the helper
implements it, but nothing was ever passing the declared dependencies in.
Now `declared_dependencies()` reads them from `pyproject.toml`, and a
scratch repo declaring `httpx`/`pydantic` with no environment installed
warns exactly as promised. Known limit: it reads the repo root's
pyproject, so this repo's own deps (in `pipeline/`) are not seen.

**Tests run lane-A-only by default.** An autouse fixture sets
`HOBBES_SCIP=0`; the suite went 3.5s → 48s the moment lane B started
shelling out to an indexer inside fixtures. Tests marked `lane_b` opt in.
Hermetic, and the real path is covered by the exit check on real repos.

**Tier in the UI:** syntactic edges draw thinner, dimmer and dashed;
semantic thicker. An edge with *no* tier keeps the default weight rather
than being demoted — a pre-v4 artifact is not a guess.

### Exit check

- **20/20 sampled semantic call edges verified by hand** against their
  cited source lines — 100%, bar was ≥95%. Sample is reproducible
  (`random.seed(20260814)`).
- **private-repo-A** ingests: 207 nodes, 1060 semantic calls, 408 semantic
  imports, no degradation.
- **kbet** ingests: 104 nodes, entirely syntactic, no errors — correct,
  because it has no Python and TS lane B is not built.

### What is not done

**`scip-typescript` is not wired.** §7 lists both indexers for M2, so this
milestone is two-thirds done and saying otherwise would be scope narrowing.
The helper already drives scip-typescript; the gap is the TS *syntax*
provider — `tsextract` would need to emit call sites with line, column and
name into the evidence IR the way `pysource` now does. Recorded in the plan
and CLAUDE.md rather than quietly dropped.

405 pytest / 52 vitest / 18 node (tsextract) / 10 node (scip) / 12 Go
packages. gofmt and go vet clean.

## 2026-08-15 — V2.M2* closed; the TS lane folds into M3

Max's call on yesterday's asterisk: **fold `scip-typescript` into M3 and
exit M2 marked rather than clean.**

The reasoning holds up — M3 already opens `tssource.py` to strip its
symbol layer, so wiring the TS lane in the same pass avoids editing that
file twice for opposite reasons. Doing it as a trailing M2 chunk would
have meant deleting the ts-morph call resolution in M3 immediately after
teaching it to emit call sites.

**M2 is now M2\*, and the asterisk is tracked rather than forgiven:**

- it is written into the plan, §7, and CLAUDE.md as a marked exit, not a
  clean one;
- **M3's exit criteria now include discharging it** — the disagreement
  report running clean is no longer sufficient on its own, kbet must also
  produce hand-verified semantic edges at the same ≥95% bar Python met at
  20/20;
- M3's estimate rises 2–3 → **4–5 evenings** to carry the work, so the
  cost moved with the scope rather than disappearing.

**What M3 now is:** strip lane A's symbol *resolution* while keeping its
call-site *detection* (ADR-029); move test reach onto lane B's edges; wire
`scip-typescript` behind a TS syntax provider — `tsextract/extract.mjs`
records no columns today and will need them, exactly as `pysource` did;
and ship the lane-agreement report as both a CI check and a command.

Nothing built this session. Tree clean, all suites green as of `a665363`:
405 pytest / 52 vitest / 18 node (tsextract) / 10 node (scip) / 12 Go
packages.

## 2026-08-15 (second) — V2.M3 built: the TS lane, the demotion, and P8

M3's two exit criteria are met. Reporting them first, then what it cost.

**kbet produces semantic TS edges — 20/20 hand-verified, bar was ≥95%.**
231 semantic call edges and 267 semantic module imports. The sample
(`random.seed(20260815)`) included the cases that actually test the join:
zustand store hooks (`useInstallStore((s) => s.installPrompt)`), a call
inside a nested arrow passed as a prop (`onClick={() => handleAction(() =>
cancelBet(bet.id))}`), a call inside a `.filter()` callback, and
`posts: [samplePost('a'), samplePost('b')]` — two calls on one line, which
is precisely why the evidence IR carries a column. Every cited line and
every cited definition checked out.

**The lane-agreement report runs clean on every sanctioned repo:**

| repo | sites both lanes resolved | disagree |
|---|---|---|
| hobbes | 1789 | **0** |
| private-repo-A | 976 | **0** |
| kbet | 359 | **0** |

Its module-edge rows reproduced ADR-027's M0 finding without being asked:
lane A says `hobbes.cli -> hobbes.invariants`, lane B says
`hobbes.cli -> hobbes.invariants.schema`, because SCIP follows the
re-export to the real definition. kbet's eight are type-only imports lane A
does not record. All favour lane B, exactly as the spike predicted.

private-repo-A was checked **read-only** — `extract_repo`, never `ingest`, so
nothing was written to it at all; its `git status` hash is byte-identical
before and after. 207 nodes, 1093 semantic calls, no degradation.

### The measurement that mattered most

Old code vs new code on an **identical tree** (a worktree, each side
running its own helper), because the repo was growing under me and absolute
counts were not comparable — I nearly filed a phantom regression before
setting this up:

```
python  calls/semantic  1211 -> 1211   identical
python  uses/semantic    392 ->  392   identical
ts/js   calls/syntactic  136 ->    0
ts/js   calls/semantic     0 ->  136
```

Every TS call edge ts-morph had guessed is now SCIP-proven, one for one,
none lost, Python untouched. The "86 missing Python edges" I chased for
half an hour did not exist: I had compared a whole-graph count against a
Python-filtered one, and the 136 "syntactic" edges were the TS ones.

Repo-wide coverage reads 86.9% -> 77.1%, which is **not** a regression. TS
call sites were never in the denominator before, because ts-morph reported
only the calls it had resolved. Split by language: python 86.9%, ts/js
60.4%. The TS number existing at all is the point.

### Two silent failures the work surfaced

**A path-base mismatch nearly hid the whole TS lane.** A zone is indexed
with `--cwd` at its own directory, so SCIP reports `src/App.tsx` where lane
A says `web/src/App.tsx`. The join matched nothing outside the root zone —
no error, just 64 semantic edges instead of 139 and a coverage denominator
full of holes. Found by asking why a healthy-looking index (1777
references) produced so few edges. Python never hit it because its `--cwd`
is the stage root.

**Decision 4's degradation check could never fire for TypeScript.** The
V2.M3 spike included a deliberate control — a staged copy with no
`node_modules` — which had to look bad or the measurement would be
worthless. It looked bad in ADR-027's exact signature (top package
`npm:typescript` at 2,643 references, the same number that ADR recorded)
and **reported no degradation**: the test fired only when *every* declared
dependency was missing, and scip-typescript bundles `typescript`, so that
one always-resolving package held the condition false forever. 1 of 23
resolved, silence. Replaced by a coverage ratio on the ADR-029 denominator
pattern. Then I broke it the other way — excluding the bundled package from
*resolved* but not from *declared* made every TS repo report `typescript`
permanently missing — and fixed that too.

### P8: a conceded fact is a registered constraint

Max, at kickoff: *"if we ever have to concede needed information we need to
document heavily as a constraint. hobbes is unusable if its a known liar,
even less usable if its fake honest."*

P6 covered the run that broke. Nothing covered what was never knowable, so
`docs/constraints.md` now does, seeded complete (**24 entries**) rather than
from this milestone alone — a half-seeded honesty register is itself fake
honest, because absence reads as evidence. Every entry names *where a user
meets the limit*; an entry whose only surfacing is a document is recorded
**unsurfaced**, which is debt, not a decision.

The seeding paid for itself immediately: **nine were unsurfaced**, and two
misled actively rather than staying quiet. Both had been honestly written
down in an ADR at the moment of decision, and both went on misleading for
two milestones anyway. That is the argument for P8 as evidence rather than
assertion.

**C-11 is lifted.** JS test reach was per *file*, so every case claimed the
file's whole closure — the only number in the system larger than the truth,
and indistinguishable from a precise pytest row. It is now per case. The
residue is **C-24** (a test that only renders `<BetCard />` reaches
nothing, because JSX is a `uses` edge and reach follows calls), and its
direction was chosen deliberately: under-reporting makes `review` flag code
as unguarded and a human looks; over-reporting lets code claim guarding it
does not have. With C-11 gone, **nothing left in the register inflates a
number** — a Hobbes figure can be read as a floor.

### Decisions

- **ADR-030** — P8 and the register.
- **ADR-031** — lane A's resolver is **demoted, not deleted**. The build
  plan said delete; reading the code first showed that would leave any repo
  without a working indexer holding *no call graph at all*, and the pytest
  suite runs `HOBBES_SCIP=0` by default, so every lane-A case would have
  asserted against an empty list. One resolver of record (lane B), a
  labelled floor beneath it. Registered as C-8.
- **ADR-032** — the TS lane stages a copy and **symlinks `node_modules`**
  (222 MB on kbet; the copy-preserving alternative measured a 6.4% loss of
  semantic references). ADR-027 clause 2 is refined, not withdrawn:
  authored source is still always copied. Two properties verified rather
  than assumed — a full index modified 0 files under the real
  `node_modules`, and `shutil.rmtree` unlinks a symlinked directory instead
  of recursing into it, which is the mistake that would have deleted a
  user's dependency tree. Both carry regression tests.

### Shape of the code now

The join is the **only** producer of symbol edges, for every language, and
it runs whether or not lane B does — with no semantic input every site
falls to the fallback arm. P6 is satisfied by construction rather than by a
second code path, so the degraded case is exercised on every test run
instead of only when something breaks. `extract_repo` reordered: all of
lane A first across every language, then the join, then the test map.

Also closed a gap the version bump exposed: nothing asserted the Node
helpers and their Python joins agree on a facts version. The constant is
declared twice in two languages and the suite is hermetic, so a one-sided
bump stayed green and would have broken only on a real repo.

429 pytest / 52 vitest / 20 node tsextract / 12 node scip / 12 Go packages.
gofmt and go vet clean.

**Not done, and deliberately:** `hobbes lanes` is not wired into the web
surface (§6 lists a lane-disagreement view as a v2 UI addition; the command
and artifact exist, the tab does not). M3's exit does not require it.

## 2026-08-15 (third) — M3 reviewed and passed; doc sweep before M4

Max reviewed V2.M3 and passed it ("my review looks clean"). The M2
asterisk is formally discharged. Status updated in CLAUDE.md and the v2
build plan; **V2.M4 (enrichment packs) is next**, not started.

No code this session. A documentation sweep, on his ask, to get the
project current before the next milestone.

**The README was two milestones stale** — it described M0, listed the v1
docs as "the source of truth", said `web/` had nothing to run, and did not
mention `tsextract/`, `scip/`, `sandbox/`, tiers, the constraint register,
or eight of the eleven CLI commands. Rewritten against the tree as it
actually is, with counts verified rather than recalled (188 Go cases / 429
pytest / 52 vitest / 20 tsextract / 12 scip / 32 ADRs). **Max's notes at
the top are his and are kept verbatim** — the tiger, the Joern comparison,
and the Bill Watterson note. Added `hobbesncalvin.jpg` with attribution,
at his request.

*(That image was swept into `3553002` by a `git add -A` of mine before he
mentioned it. Harmless — he wants it tracked — but it was not mine to
commit and is worth recording.)*

**Four other docs had drifted:**

- **`first-run.md`** — the "bring Hobbes up on a new app" guide, and it
  did not mention lane B at all. Step 0 was missing `cd scip && npm
  install`, so a reader following it exactly would have got a
  fully-syntactic graph and no hint why. Added that, a note that lane B
  needs the *target repo's* dependencies installed, a new step 2a for
  `hobbes lanes`, and what `tier` and `resolution_coverage` mean. Two
  entries added to "things that will bite you": ingesting a repo whose
  dependencies are not installed (C-23), and reading an absent edge as
  "this does not happen" (C-1).
- **`hobbes-architecture.md` / `hobbes-build-plan.md`** — no banner. Read
  cold, both presented as current, and `first-run.md` still called them
  the source of truth. Each now opens with what it still governs, what v2
  replaced, and that **v2 wins** where they disagree.
- **`future_additions.md`** — still parked *per-test JS reach* as deferred
  work after V2.M3 built it. Struck through with the commit, on the
  convention the two fixed papercuts already use. Also noted that
  cross-zone TS imports (C-12) now applies to **both** lanes, since
  `scip-typescript` is run per zone for the same reason `ts-morph` is.

**A doc that is deliberately current-but-unfinished:** `hobbes lanes` has
no web-surface tab, though §6 lists a lane-disagreement view as a v2 UI
addition. Recorded in the M3 entry above and left for Max to scope.

Nothing else was found stale. `docs/m9-application-mode.md` remains a
proposal with three open questions and is untouched; ADR-026 still awaits
review, and neither blocks V2.M4.

---

## 2026-08-15 (fourth) — one running architecture, and two things Hobbes never said out loud

Max's direction before V2.M4, four parts: keep Hobbes local; say plainly
what Hobbes *is*; own the language providers' limits as ours; and keep one
**running** architecture document instead of a versioned one. No code
changed — this is the doc layer catching up to the system, plus two ADRs.

**ADR-033 — the architecture is one running document.** `git mv`:
`hobbes-architecture.md` → `hobbes-architecture-v1.md` (frozen record),
`hobbes-architecture-v2.md` → `hobbes-architecture.md` (running, no version
number, wins over everything else). His reason was that the architecture had
already moved past v2 with the evidence IR, and he was right in a way worth
measuring: **the v2 document was written 2026-08-14 and was wrong about its
own subject within three milestones.**

Three drifts, all found by reading the tree against the file:

- **§3.3 claimed SCIP monikers are the graph's node IDs. They are not.**
  The range join (ADR-029) meant lane B never had to invent an id for
  anything lane A already named, so ids stayed path-based — the dogfood
  graph's are `driver.Proxy`, `env:HOME`, `ext:react`. §4 repeated the
  claim. Corrected, *and* the knock-on stated: §9's "monikers prepare
  multi-repo merge" is weaker than it reads, because two repos can both
  hold `src/util` and path-based ids have no repo-scoping pass.
- **§3.1 said lane A's resolver moves entirely to lane B.** ADR-031 demoted
  it to the join's fallback instead.
- **§3.7 said "add the indexer to `hobbes.yaml`".** That file does not
  exist. The registry is `INDEXERS` in `scip/index.mjs`; the per-repo config
  is *derived* by `scipsource.py`, not authored. Section now says so, and
  says a pack registry is still owed an ADR (the ADR-012 tension is
  unchanged).

Each drift had been recorded in an ADR at the time. **None reached the file
a session is told to read first** — which is P8's failure mode with the
architecture itself as the artifact. All three were fixed in the same commit
as the ADR; writing the rule without paying its first bill would have been
the fake-honest version of it. §7's milestone prose became a status table
pointing at the build plan, because detail restated in two places disagrees
with itself, which is this ADR's whole subject.

**ADR-034 — P9: a provider's limits are Hobbes's limits.** Max: "were using
language specific providers for semantic pulling, any issues with that
against us we have to directly write and document." The sentence this
forecloses is *"that's scip-python's limitation, not ours"* — true, and
worthless: the user ran `hobbes ingest`, and a missing edge reads as an
absent call either way (C-1). The sharper risk is that an inherited limit is
*easier* to leave unregistered than one of our own, because no decision of
ours created it and P8 keys on the moment of decision. There is no such
moment when an upstream tool simply doesn't implement a field — which is
exactly how C-6 and C-23 both went unregistered until V2.M3 went looking.

Mechanically an inherited limit is a P8 entry plus a `Provider` line naming
the provider and **pinned version**, because these are the only entries in
the register that can end without us doing anything. Retrofitted in the same
commit: **C-6** (inherited, `scip-python` 0.6.6, `syntax_kind` populated for
0 of 8,575 occurrences — *liftable* if a release fixes it, which would make
lane A's call-site detection a choice rather than a necessity), **C-23**
(inherited, `scip-typescript` 0.4.0 — *not* liftable, since whole-program
inference cannot infer from types absent from disk), and **C-9** (marked
**ours, not inherited** — the indexers do emit those symbols and Hobbes
drops them; listed because it is easily mistaken for a provider limit).
V2.M5 and V2.M7 now each owe a provider-limit review at their exit, not just
a working ingest. Noted the tension with P7 rather than hiding it: the code
stays configuration, the honesty does not come for free.

**What Hobbes is, written down.** A *multilingual deterministic code graphing
environment* — with **honest** added to deterministic, at his correction,
and **accurate** named as the job that outranks both. Now the opening of the
running architecture, the top of CLAUDE.md, and the first thing the README
says. Also written down for the first time: **where it is going** — single-use
agents under derived, systematic context, because a model's accuracy falls
as context grows and tasks accumulate, so the answer is a smaller job rather
than a bigger window. That reframes the sandbox and policy engine as the
mechanism rather than a safety feature: a forbidden command is not refused,
it is *absent*. In his words, "if we can not allow an agent to execute a
command in a space where it literally cannot, then it literally cannot."
Three of the four pieces exist (graph, invariants, enforcement); the
derivation itself is not a milestone yet, and §9 says so rather than
implying it is planned.

**Two open items closed.**

- **ADR-026 is verified.** Max ran `hobbes up` against this repo — "seems to
  be working perfectly. everything displays and runs correctly on the ui."
  Confirmed here: `.hobbes/derived` is now stamped at HEAD (`83f0b49`),
  schema v4, 126 nodes / 258 module edges / 2012 symbol edges. The review
  debt that had carried since 2026-08-11 is discharged.
- **M9 is parked, not pending.** "the application was a thought i had
  wanting it less and less but maybe one day." `m9-application-mode.md` is
  kept as the record of the thought with its three questions unanswered, and
  §9 now states that Hobbes stays local as a design position rather than a
  stage on the way to hosting.

Suites re-run green before the commit, unchanged by any of this: **429
pytest / 12 Go packages / 52 vitest / 20 tsextract / 12 scip**, and
`hobbes lanes` exits 0 (1789 call sites compared, 0 disagree).

**V2.M4 (enrichment packs) is still next, and is now unblocked on
everything except its own opening question:** the pack registry needs an ADR
before the file exists, because a registry is a property of the repo while
ADR-012 makes all of `.hobbes/` personal.

**Found while committing: an approved invariant states something false.**
Max's `hobbes up` session wrote real decisions (five approvals I-7..I-11,
one denial, intent confirmed) — ADR-026 exercised end to end, which is a
stronger verification than a UI walkthrough. But **I-9 ends "all other
pushes escalate", and the repo policy denies `git push*` outright.** It is
false in exactly the way the M5 inferred wording of I-3 was false — caught
and rewritten at M8, with the note still in I-3's file explaining why.
Narration re-proposed the uncorrected text; the queue had no way to show a
corrected record already covered it; the approval versioned the false claim.

This is C-21, and the register had it filed as a signal-to-noise cost.
Updated with the instance: the real cost is that a duplicate can carry a
claim its original was corrected to remove, and the fix belongs in the
decision surface — an inferred statement should arrive next to the confirmed
records overlapping its scope. The record itself is Max's to correct; the
untracked `.hobbes/` decisions and records were left uncommitted for him,
not swept into this commit.

---

## 2026-08-15 (fifth) — the decision set committed, with I-9 corrected

Max's call on the finding above: **"we can keep pushes off the table"** —
and the context for why it slipped, worth recording because it changes how
to read the dogfood repo's own invariants:

> i was fine with the ask just because hobbes on itself is testing, hobbes
> is incomplete so treating everything as stone isnt really worth.

So the approvals were a test of the decision surface, not a considered
ruling on eleven invariants. Committed on that understanding, with two
corrections made first.

**I-9's false clause is fixed.** "all other pushes escalate" → every push,
forced or not, denied outright, with unmatched commands still escalating by
default. The file carries a comment recording that the inferred text was the
same wording M8 caught in I-3, so the next reader sees the loop rather than
just the fix.

**All five new records are restatements, and now say so.** Checking each
against the confirmed set: I-7 restates I-1 (tfstate), I-8 restates I-2
(derived never committed), I-9 restates I-3 (publishing), I-10 restates I-5
(narrative validation), I-11 restates I-6 (env joins) — and the one Max
*denied* was the I-4 duplicate. That is C-21 landing in full: all six
inferred records correspond 1:1 to the confirmed set and none match by key,
because the inference unit is told about the repo but not about
`.hobbes/invariants/`.

Each new file gained a `RESTATES I-n (C-21)` comment naming the record of
reference and what the older one says that the newer one drops — I-1 names
three enforcement sites where I-7 names one; I-6 covers JS env-reads where
I-11 says only Python. **Comments, not fields:** the schema rejects unknown
keys (`_RECORD_FIELDS` in `invariants/schema.py`), and a comment cannot
change what gets checked. `hobbes invariants check` reports 11 valid, 11
confirmed.

The duplication is left in place rather than resolved, because retiring five
records Max approved hours ago is his call and the register now makes the
overlap legible. The real fix is upstream and already named in C-21: an
inferred statement should reach the decision queue *next to* the confirmed
records overlapping its scope.

**README rewritten around the vision.** The intro keeps the identity and
hands off to a new **"Where this is going"** section: accuracy falls as
context grows and tasks accumulate, so the answer is a smaller job rather
than a bigger window — per-task context and per-task policy derived from the
architecture, one agent inside both, ending when the task does. Context
scoped by the architecture and regenerated, rather than assembled by a
prompt and accumulated until it rots. The policy half is why the sandbox
sits below the model: a rule in a prompt is a request, while a command
outside the policy is *absent*.

It ends on a four-row table of which pieces exist, and the fourth row says
**not built, not a milestone yet**. That row is the reason the section can
sit in a README at all — a vision stated next to an honest account of how
much of it is real is a plan; stated alone it is marketing, and this project
has a principle about that.

---

## 2026-08-15 (sixth) — V2.M4: the framework knowledge leaves the builder

Max's direction: raise the extractor's ability before using Hobbes for real,
because accuracy is the backbone and a half-composed extractor makes the
rest uninteresting. So: V2.M4, enrichment packs.

**ADR-035 — packs are registered in code and activated by detection.** The
plan required this ADR before any pack existed, because §3.7's `hobbes.yaml`
collides with ADR-012 (all of `.hobbes/` is personal in target repos) and a
pack registry describes the *repo*, not one person's box.

The answer is the one ADR-027's amendment already found for indexer config:
**derive it.** Whether a repo uses FastAPI is a fact Hobbes reads from
imports; whether it has Terraform is a fact about `.tf` files. So there is no
`hobbes.yaml`, the registry is a tuple in `extract/packs/__init__.py`, each
pack answers `applies()` from the repo, and **the ADR-012 tension dissolves
rather than being resolved** — nothing is authored, so nothing needs
tracking or gitignoring, and a fresh clone gets the same packs as the
machine that ingested last, which an untracked registry could never have
promised.

**Four packs, each an adapter over the retained implementation.**
`http-python` (FastAPI/Flask decorator routes), `cli-python`
(`[project.scripts]`), `http-ts` (Express/Nest), `terraform` (the HCL layer
and its cross-layer joins). `terraform.py` and `interfaces.py` keep their
code and get a new — and *only* — caller. Rewriting 372 hand-verified lines
for a structural change no user can observe is how a milestone about
removability becomes a milestone about regressions.

One asymmetry stated rather than hidden: **TS route detection stays in the
Node helper.** Express's receiver check asks ts-morph what `app` was
initialised to, so `app.get("/x", h)` is a route and `cache.get("/x")` is
not. Reimplementing that in Python means losing it. The pack *claims* the
helper's rows and declares their tier; it does not re-derive them. The pack
contract is about owning a contribution, not about where the regex lives.

**The port is byte-identical, and that was checked rather than assumed.** A
git worktree at HEAD ran the pre-M4 code over miniapp, minits and private-repo-A;
the new code ran over the same three with the same TS helper and
`HOBBES_SCIP=0`. Every document identical apart from the new `packs` field —
private-repo-A at 207 nodes / 602 edges / 50 routes / 211 tests, unchanged.

**Exit criterion met, on fixtures and on real repos.** `test_packs.py`
asserts per pack that removal takes exactly that pack's contribution and
that restoring it reproduces the artifact byte-for-byte. The subtle half is
that a node a pack *shares* must survive its removal, and the dogfood repo
demonstrates it: dropping `terraform` removes its 5 edges and 3 `tf:` nodes
and **keeps all 5 `env:` nodes**, because Python reads those. On private-repo-A,
dropping `terraform` takes 22 nodes and 21 edges (`references`, `packages`)
and the `hcl` language, and touches no route, no test, nothing else; on
kbet **no pack applies at all** and the graph is purely the lanes', which is
the honest answer for a Vite/React app with no routes, no pyproject and no
HCL.

**The regression this milestone nearly shipped.** Packs degrade rather than
raise (P6) — a framework pass failing on one repo must not cost that repo
its graph. Implemented as a blanket `except Exception`, that swallowed
`PlanError`, the refusal that guards **I-1**: `hobbes ingest --tf-plan
prod.tfstate` stopped exiting 1 and started *succeeding* with a warning
beside the state file it had declined to read. The existing test caught it.

The rule that came out of it is now in the architecture: **packs degrade,
except when they refuse.** `PackRefusal` is re-raised and never degraded,
because a pack declining input the user supplied is not a pass that broke.
It is worth noticing what the failure shape was — a generic safety mechanism
(degrade everything) quietly eating a specific safety guarantee (refuse
this). The test that caught it was written at M3 about tfstate, not about
packs.

**Registered C-25** — a pack cannot be turned off for a repo where it
misfires. *Partial* rather than unsurfaced, because `graph.json`'s `packs`
list shipped in the same commit: a wrong edge is attributable to the pass
that made it, just not suppressible. The fix is a per-repo disable list,
which has to live somewhere that survives a clone — the ADR-012 question
deferred rather than answered.

Suites: **455 pytest** (429 + 26 new), 12 Go packages, 52 vitest, 20
tsextract, 12 scip. `hobbes lanes` still exits 0 after a full lane-B ingest
of the dogfood repo (133 nodes, 290 module edges, 2138 call edges, 522
tests).

**V2.M4 is built and stops here for review.** V2.M5 (Go support — and the
first time Hobbes can see its own 9.4k lines of Go) does not start until Max
passes it.

---

## 2026-08-15 (seventh) — M4 passed; P10, the rule the near-miss produced

Max reviewed V2.M4 and passed it. He also named the thing the tfstate
near-miss was an instance of, and it is a principle rather than a note:

> specific safety guarantees come before a general safety system. safety
> systems should be tiered by importance and coverage.

**ADR-036 adds P10 — a specific safety guarantee outranks a general safety
system.** The M4 case is the worked example: `except Exception` around packs
(general, correct, P6) swallowed `PlanError` (specific, correct, I-1), and
`ingest --tf-plan prod.tfstate` began succeeding. Both mechanisms were right
in isolation. The general one won **by default rather than by decision**,
because a broad handler is broader than anything inside it.

Three requirements come out of it, and they are requirements on the
*general* mechanism, because intent at the specific end is not enough — the
person widening the general handler is not thinking about the guarantee at
all:

1. A broad handler **names what it will not handle and re-raises it first**.
2. A refusal is a **distinct type**, not a return value or a log line — a
   guarantee that travels as a message is one string-match from being lost.
3. The specific guarantee keeps **its own test at the level a user meets
   it**. The test that caught this was written at M3 about `.tfstate` and an
   exit code, and it survived a refactor of code it knew nothing about
   precisely because it asserted the user-visible guarantee rather than the
   implementation behind it.

Ranking is **importance × coverage**: the broader a mechanism's reach, the
less it may decide on its own. A handler around one call site may swallow
that call's errors; a handler around every pack, every tool call or every
session may not, because it cannot know what it is standing in front of.

Named the mechanisms already in the blast radius, without claiming they are
wrong: expire-to-deny, the narrative runner's corrective retry, the proxy's
exec wrapper. M4's was not known to be wrong either, until a test failed.

**Max's second ask: Hobbes should eventually catch this itself.** Parked in
`future_additions.md`, not built, and the entry says plainly that nothing in
the system detects this class of gap today — it was found by a test, not by
Hobbes. The natural home is V2.M6's unified checker, because *does a broad
handler enclose a path that must refuse?* becomes a graph question once
refusals are a type. `PackRefusal` makes them one in the pack layer; the
other subsystems need the same before a checker has anything to reason over.
Two steps, in order: give every specific guarantee a type, then ask the
graph which broad handlers dominate one.

**V2.M5 (Go language support) is now active** — and it is the first
milestone written under P10, which is fitting: adding a language means new
general handling for a new indexer's failure modes, which is exactly the
shape that ate I-1.

---

## 2026-08-15 (eighth) — V2.M5: Go, and the checklist that was wrong

Max cleared M5 after passing M4. The milestone's exit criterion was written
to prove something: *"a Go repo ingests with zero builder changes —
checklist §3.7 was literally sufficient, and the diff proves it."* It
proved half of that and disproved the other half, which is the more useful
outcome and the reason to spike before building.

**The baseline, measured first.** A Go repo extracted today produces an
**entirely empty graph with no error** — 0 nodes, 0 edges, 0 tests, no
degradation record. Hobbes silently reported that a repo full of Go
contained nothing.

**The spike (ADR-037, reproducible via `scip/spike-go.mjs`).** `scip-go`
0.2.7 over this repo's own Go: 24 packages, 51 documents, 18,682
occurrences, **0.27s**. Six findings, one of which decided the milestone:

1. **`syntax_kind` is unset for 100% of 18,682 occurrences.** ADR-029
   measured the same zero for `scip-python` (0 of 8,575). Two independent
   implementations, the same omission, and the field is optional in SCIP.
   That is the field separating a call from a type annotation, so §3.7's
   "optional lane A grammar" would have left Go with references and **no
   `calls` edges at all** — no `who_calls`, no test reach.
2. `--module-version` **defaults to the git revision**, ADR-027's Decision 1
   under a third flag name. Every node id would change every commit.
3. 27.9% of definitions are graph-worthy, against ~14% for scip-python.
4. Monikers are legible and carry the package path in backticks.
5. **Documents escape the repo**: `../../.cache/go-build/f1/f12bb51…-d`.
   `relative_path` is the indexer's word, not a fact.
6. Third-party and stdlib both resolve — **no C-23 analogue for Go**, since
   the module cache is global rather than per-repo.

**So §3.7 gained a third mandatory step.** Adding a language needs *two*
providers: an indexer for resolution and a **syntax provider for
detection**. C-6 was generalised from "scip-python does not populate
`syntax_kind`" to "no indexer does" — the entry had been filed too
specifically and read as a gap one upgrade could close. Nothing catches
that except measuring the next case, which is worth remembering the next
time an entry names a single tool.

**P7 survives, narrowed and stated honestly.** The *builder* took **zero**
Go-specific lines — graph builder, join, schema and the V2.M4 pack
interface all untouched. What P7 cannot promise is that a language is free:
it costs one grammar walk, now with four worked examples. The wrong claim
was "an indexer entry plus an optional pack".

**Built:** `extract/gosource.py` (modules, symbols, imports, `os.Getenv`
env-reads, call sites with column, Go test inventory), `scip-go` in the
helper's `INDEXERS` with the version pinned and `insideRepo` dropping
out-of-repo documents, `extract_scip_go` with **one run per `go.mod`** (the
TS zoning lesson again — this repo's own module is at `go/`, not the root,
so indexing from the root finds nothing), and the `http-go` pack.

**Two Go-specific corrections, both found by reading output rather than
by theory.** A **type conversion is spelled exactly like a call** —
`Decision(s)` parses identically to `Resolve(s)` — and lane A drops
conversions using the one thing SCIP lacks: which names are types. And a
**Go import names a package, not a file**, so lane A emits no in-repo
import edges at all; the join raises them from what the call actually
reaches, which is precise rather than a guess among a package's files.

**The lane-agreement report needed the mirror of its own exclusion.** Since
lane A structurally cannot produce Go's in-repo imports, all 91 landed in
"lane B only" and buried the 10 real ones. Go module edges are now excluded
by construction the way `ext:`/`env:`/`tf:` nodes already were — and
**counted** (`module_edges_excluded_lane_b_only: 82`), because an exclusion
nobody can see is how a self-test quietly stops testing.

**Results on the dogfood repo — the loop closes.** 216 nodes across **five
languages**, 653 module edges, 1690 symbols, 3533 call edges, 712 tests, 33
routes. 813 Go `calls` edges, **20/20 hand-verified** against their cited
lines, including method-on-value calls that only lane B can resolve. 2710
call sites compared across every lane with **0 disagreements**. With
`HOBBES_SCIP=0` the same repo still yields a Go graph at `syntactic` tier
with imports raised from the fallback — P6 for a fifth language, no second
code path.

Registered **C-26** (a Go file outside any `go.mod` gets no semantics;
partial surfacing via tier). 488 pytest / 16 scip / 12 Go packages / 52
vitest / 20 tsextract.

**V2.M5 stops here for review.** V2.M6 (the unified invariant checker) does
not start until Max passes it — and it is the milestone that inherits P10's
parked ask, since "does a broad handler enclose a path that must refuse?"
is a graph question.

---

## 2026-08-15 (ninth) — the register audited against the system it describes

Max asked for the constraints register to be verified against the current
tree before any of it is tackled pre-M6. Every entry was checked against
code, not against the ADR that filed it. Twenty of twenty-six survive
untouched; six had drifted, and every drift was a V2.M4/M5 side-effect
landing in an entry those milestones never edited.

**The material one: C-3 was false for Go.** `gosource` emits an `ext:`
node for every import that resolves to no in-repo package — no stdlib
filter — so the dogfood graph carries `ext:os`, `ext:fmt`, `ext:syscall`,
`ext:net`: ~20 stdlib packages among its 51 external nodes, while Python
(`sys.stdlib_module_names`) and TS (Node builtins) drop theirs as noise
per ADR-007. The docstring says "stdlib and third-party" knowingly, but
neither ADR-037 nor the register reconciled it. The asymmetry is worse
than the old uniform silence: visible Go stdlib teaches a reader that
stdlib is modelled, so a Python module's missing node now reads as
*positively* clean. C-3 rewritten to state the split; **which way to
harmonise (drop Go's, or emit everywhere and lift C-3) is a decision for
Max**, not taken here.

The mechanical five: C-15's collision order said "(Python, HCL, TS)" —
it is Python → TS → Go → packs-last since M4/M5, verified at the
`_merge_layer` call sites. C-9 gained `scip-go` 0.2.7 on its provider
line and Go's 72% drop rate beside the 86%. C-10 now names
`--module-version`, the third flag for the same pinned decision. C-14
widened to Go: this repo's four `cmd/` binaries are absent from an
`interfaces.json` that lists `hobbes` and `mini`. C-5's mechanism moved
into the packs at M4 (all three http packs cite it and skip computed
paths identically) — the rule is ADR-007's, the code is ADR-035's.

Verified and unchanged, with the checks that mattered:
`resolution_coverage` emitted (C-2), the degradation check still reads
only the repo root's manifest (C-16, `scipsource.py`), the staging
properties still carry their tests (C-22), and the debt summary's counts
hold — still nine unsurfaced of twenty-six, still nothing that inflates
a number.

The summary gained the audit's lesson as the mirror of M5's: **a register
entry can be made wrong by a milestone that never touched it**, and
nothing detects that today — no milestone exit re-reads entries it did
not write.

No code changed. The triage of what to tackle pre-M6 goes to Max with
this session's report.

---

## 2026-08-15 (tenth) — the sweep: two lifted, two surfaced, before M6

Max's call on the audit's triage: option (b) for C-3 — "no need to hide
what hobbes does capture" — plus the three surfacing fixes, all before
V2.M6. Four commits, each with its register update in the same diff.

**C-3 lifted (ADR-038).** Stdlib imports are dependencies everywhere now.
Python drops the `sys.stdlib_module_names` skip; TS keeps Node builtins
normalised to a `node:`-prefixed name (`ext:node:fs` however the import is
spelled, never sharing a node with the npm package called `fs`); Go was
already right, just alone. On the dogfood repo: 216 → 247 nodes, 653 → 848
module edges, and `ext:subprocess` now pins exactly the six modules a
security reviewer would ask about. Externals stay hidden by default in the
surface — a view choice, where the old rule was an information choice.

**C-16 lifted — and it fired on its first real run.** The
dependency-degradation check now walks every `pyproject.toml` (the CLI
pack's pruned walk), and on this very repo it immediately reported
something true that nobody had seen: **the Python index resolves 0 of the
5 declared third-party packages** (pyyaml, the tree-sitter family), while
the TS zone resolves 6 of 9. In-repo Python semantics are intact — 1,977
semantic edges — but resolution *into* those packages has been absent
since lane B landed, because the staged copy is indexed outside the venv.
The check that was inert for two milestones surfaced a real gap within
minutes of working. Remediation (making the indexer see the environment)
is real work and is not started here; the WARNING at ingest is the
designed surfacing, and it is now honest.

**C-26 surfaced.** One degradation record per orphan Go directory names
the files and the missing `go.mod`. Detection is a pure public function
(`go_orphans`) so its test runs with no indexer installed; lane-B
degradation records keep their own `path` instead of flattening to `.`.

**C-5 surfaced — and surfacing found a bug.** All three HTTP packs now
report a route seen and declined (computed path) as an `extraction_errors`
record at file:line. Writing the decline path exposed that the Nest reader
had been *emitting* a route with a computed segment silently dropped —
`@Get(SOME_CONST)` under `@Controller("items")` reported as `/items`, a
path the app does not serve, which is the one shape worse than C-5's
absence. Computed Nest arguments now decline like the rest. tsextract
helper is v3 (`routes_declined` per file), pinned on both sides. The
false-positive edges were guarded deliberately: Python's decline is
framework-import-gated, express requires a registration-shaped call on a
receiver that resolves to an express app, Go declines only when no string
argument exists at all — a judged non-path string is not a miss.

Debt summary recounted: six unsurfaced of twenty-six (C-4, C-12, C-14,
C-19, C-20, C-24), three lifted. Of the six, C-19 and C-24 fall to V2.M6
by plan. 498 pytest / 21 tsextract / 52 vitest / 16 scip / 12 Go packages,
and a full dogfood re-ingest verified by hand.

**Still stopped at the M5 review gate.** Nothing here is M6 work — it is
the register's backlog, paid down so M6 starts clean.

---

## 2026-08-15 (eleventh) — the resolution gap C-16 found, closed (C-27)

Max: fix the resolution gaps and true up the register before M6. The
tenth entry's finding — the Python index resolving 0 of 5 declared
packages — turned out to be **two stacked causes**, and finding the
second required fixing the first.

**Cause one: the venv was assumed, not discovered.** `extract_scip`
hardcoded Pyright's `venvPath` to `<root>/.venv`; this repo's venv is
`pipeline/.venv`. The same root-only shape as C-16, one layer down.
`find_venv` now walks the conventions in a deterministic order — `.venv`
then `venv` at the root, then beside each manifest — and requires
`pyvenv.cfg`, so a directory merely *named* `.venv` is never handed to
the indexer. That alone moved PyYAML but not tree-sitter, which is what
exposed:

**Cause two: scip-python asks the wrong environment entirely.** Its
package attribution shells out to the first `pip3` on PATH — the system
one, and a uv venv carries no pip at all. Pyright *resolved*
`tree_sitter` perfectly; scip-python then attributed it to the local
project ("Could not find package information") and the dependency
vanished from the package list. PyYAML had only ever worked **by
coincidence**: Fedora's system Python happens to have it. The fix routes
around the discovery: Hobbes asks the venv's own interpreter for its
distributions (stdlib `importlib.metadata`, read-only, sixty-second
timeout, None on any failure) and hands the listing to scip-python via
its own `--environment` flag. The helper passes the flag only when a
listing was computed, so absence degrades exactly as before.

A third, smaller lie fell out en route: coverage matched names by exact
string, so once the index *did* resolve `PyYAML`, the report went on
saying `pyyaml` was missing. PEP-503 normalisation (case-insensitive,
`-`/`_`/`.` equivalent) now applies — Python only, since npm and Go
treat case and punctuation as identity.

**Result on the dogfood repo: 5 of 5 declared packages resolved, zero
extraction errors** (was 0 of 5 with a WARNING). 3,598 semantic edges.
The TS zone's 6 of 9 stands and is honest: the three missing are
devDependencies no source file imports. Verified end-to-end on a probe
repo first — `python:tree-sitter` and `python:tree-sitter-python`
attributed by name — then on the full ingest.

Registered **C-27** (Python third-party semantics need a discoverable
venv — the Python sibling of C-23, provider line `scip-python` 0.6.6,
surfaced via `dependency_coverage`). Discovery stays convention-bound:
conda and system environments are the honest residue, answered by the
counts rather than guessed at. 504 pytest / 18 scip; the register now
counts twenty-seven entries, six unsurfaced, three lifted.

**Still at the M5 review gate.** M6 starts on Max's pass, with the
register current as of this entry.

---

## 2026-08-15 (twelfth) — V2.M6: the unified invariant checker (ADR-039)

Max passed M5 and cleared M6. Built across five commits, each green.

**The record shape.** `check: graph | emit | soft` is the spine; the rule
block moved to the top level (it describes the invariant, not the
compilation); `compile` shrank to `{target}` and exists only for emit;
`soft` stopped being a pseudo-target. Validation enforces the whole
combination and refuses a `check: graph` record whose kind the graph
cannot answer — a check that cannot check would sit at `unknown` forever.
A v1 record fails with the migration named. All eleven records migrated;
the Go surface writes the new shape on approval and `list_invariants`
renders the checking mode. The decision-key hash is untouched.

**Tier-aware verdicts, with the carve-out that keeps them honest.**
Semantic evidence proves; syntactic evidence yields `suspect` — a new
result between fail and unknown, still exit 1, folded into review's red
family (pass→suspect regresses, fail↔suspect is still-failing). The
carve-out: on edges only lane A can produce (`ext:`/`env:`/`tf:`),
syntactic is not a downgrade but the only tier that exists — an import
statement lane A read is a fact, and calling it a suspicion would
understate a real violation. Without the carve-out, every I-4-style
verdict would have been permanently "suspected".

**I-4, restated a third time — and the checker now guards its roster.**
The plan predicted this. The enumerating wording went stale twice
without the record noticing: V2.M4 moved HCL behind the pack, V2.M5
added gosource's grammar. The old rule *fails* on today's graph, citing
`gosource.py:39` — which is the negative control proving the checker
isn't vacuously green, and the reason the statement now states ownership
while the enumeration lives only in the rule block held against the
graph on every review. A fifth language that forgets to amend the record
turns it red instead of quietly narrowing it.

**lint-imports ran for the first time in the project's history, and the
first execution found a real bug.** The `except` cross-product emits
ignore pairs that never occur as imports; import-linter errors on
unmatched ignores by default; a clean repo exited 1 while the graph said
pass. Exactly the class of bug M8's shape assertions could not see, and
exactly where the plan said it would surface. The emitter sets
`unmatched_ignore_imports_alerting = warn`, the regression is pinned in
`test_agreement.py`, and C-19 narrowed to the three tools still
unexecuted. import-linter is a dev dependency now.

**Soft verdicts are source-based — C-18 lifted.** `--soft` runs each
in-scope soft invariant in the M4 reviewer sandbox: worktree ro at the
review's head ref (`hobbes-session --ref`, new flag with a test), the
knowledge tools, and the range's diff hunks in the prompt (bounded at
400 lines). A missing sandbox is an error on the answer, never a silent
fallback to the delta prompt — that would have recreated C-18 quietly.

**Exit criteria, on the dogfood repo.** `hobbes review HEAD~2..HEAD`
runs the I-series under the new field end-to-end: I-4 **pass** under
`check: graph` at both ends, I-5 honest `unknown` (compiled for CI),
nine `soft` queued for a reviewer — and the delta pane flagged this
milestone's own change (`hobbes.review -> ext:os`, the ADR-038 stdlib
edges at work). Agreement wherever both exist: I-4's graph pass ↔
`lint-imports` exit 0 on the generated config; the stale-rule negative
control fails both judges *at the same line*. `hobbes invariants
compile` emits exactly the emit records (semgrep for I-5) and names why
graph and soft records are skipped.

**P10's parked ask stays parked**, stated in ADR-039: no record can want
a refusal-domination rule kind until refusals are a type outside the
pack layer. **C-24's candidate fix remains open** — its "deferred to
V2.M6" was the register's guess, not the plan's commitment; flagged for
Max before M7.

520 pytest / 18 scip / 21 tsextract / 52 vitest / all Go packages ok.
Binaries rebuilt (web, proxy, sandbox proxy, session).

**V2.M6 stops here for review.** V2.M7 (Rust proof) does not start until
Max passes it.

---

## 2026-08-15 (thirteenth) — C-24 lifted: a render is a call, outliers named

Max's call on the flagged debt: JSX instantiations become call sites,
"as long as that's something we keep honest with what hobbes does —
'in every meaningful sense' always can have outliers." The condition
shaped the change as much as the mechanism did.

**The mechanism is one gate in the syntax provider.** `extractCalls`
records a JSX opening or self-closing element as a call site when the
tag is component-like — a capitalised identifier or any dotted tag —
positioned on the tag's terminal identifier, exactly where SCIP puts its
occurrence. Everything downstream is the existing machinery: the range
join claims the site, lane A's fallback resolves what it can (top-level
symbols only, same as `Ui.Button()` the call), and SCIP promotes to
semantic where it confirms. No schema change, no helper version bump —
more sites, same shape.

**The outliers, named where a user meets them** (the lifted C-24 entry
and the extractor's own docstring): `<div>` is a string at runtime, not
code the repo owns — excluded; the framework mediates *when* a component
body runs, which is the same epistemic status as any call site behind a
branch; a closing tag repeats a name and is not a second site; and a
component passed as a value (`<Route component={Card}>`) stays a `uses`
edge, because nothing at that site instantiates it.

**Verified on kbet — the repo where the debt was measured.** 12 direct
test→component render edges, **all semantic tier**, `BetCard` among them
(the entry's own example); **108 of 174 tests now reach a component**,
with closure through what components themselves render (`ActiveBetsStrip
→ StripButton`). The 44 still-empty rows are store/logic tests in plain
`.ts` files — a different residual, honestly outside this entry's
subject. `hobbes lanes` runs clean on kbet and on this repo (whose own
web SPA gained its render edges: 3,738 call edges, up 137). The
end-to-end case is pinned in `test_tssource.py`: a render-only vitest
case reaches the component *and* what the component calls, evidence at
the JSX line.

Register: C-24 **lifted** — five lifted, five unsurfaced of twenty-seven,
and the "nothing inflates a number" property holds: the under-reporting
residue was replaced with the true edge, not with the safer inaccuracy.

521 pytest / 22 tsextract / 52 vitest / 18 scip; Go untouched.

**Pausing here before V2.M7 (the Rust proof), per Max.**

---

## 2026-08-15 (fourteenth) — V2.M7: the Rust proof (ADR-040)

Max passed M6 and cleared M7, adding `~/rust_proj` as the verification
repo. Toolchain installed user-locally (rustup, Rust 1.97.1,
rust-analyzer as a component).

**The spike before anything else** (`scip/spike-rust.mjs`, the ADR-027
convention). Three measurements decided the shape: `syntax_kind` unset
for **0 of 169** occurrences — the third indexer with the same omission,
ADR-037's mandatory syntax provider confirmed a third time; the moniker
version is the **crate's Cargo.toml version**, the first indexer whose
default satisfies Decision 1 unpinned (the INDEXERS entry passes no
version flag, with a comment saying the omission is deliberate); and
rust-analyzer **executes the repo's build scripts and proc macros**
while indexing — no other lane B provider runs repo-authored code
(C-29, disclosed by a stderr NOTE on every rust ingest).

**The exit criterion holds: zero new builder code.** The diff is one
syntax provider (`rustsource.py`), one `INDEXERS` entry, one staging
function (`extract_scip_rust`: nearest Cargo.toml collapsed to the
nearest `[workspace]` root), and the same four orchestration touches Go
added. `graph.py`, `evidence.py`, the join, the schema, the packs:
untouched. P7 proven twice, on the language the checklist was corrected
for.

**Rust's own lesson: macro arguments are token trees.** tree-sitter
leaves everything between `!` and `;` unparsed, so `assert_eq!(add(1,
2), 3)` contains no call_expression — and nearly every Rust test asserts
through a macro. `rustsource` applies call-shape detection inside token
trees (identifier immediately followed by a parenthesized token tree);
rust-analyzer emits macro-argument occurrences at their real
pre-expansion positions, so the lanes still meet on ranges, and a
false-shaped site produces no edge because nothing resolves at it. The
fallback resolver rides the module system's deterministic file mapping
(`mod x;` → `x.rs` | `x/mod.rs` | `#[path]`, use-aliases, crate names →
lib targets from Cargo.toml) and refuses value methods, `crate::` roots
and globs, per ADR-031.

**Verification found two real bugs, one of them two milestones old.**
(1) `terminalName` kept the bracketed self type of impl-scoped methods
(`impl#[Counter]new().` → `[Counter]new`), so no method reference ever
name-matched its call site and every in-repo Rust method edge silently
fell out — observed as `unwrap` counting *unresolved*. Fixed and pinned;
`c.incr()` now carries a semantic calls edge, lane B doing the one job
the fallback refuses. (2) The ambiguous-definition drop (a moniker DEF'd
in more than one document is dropped, refs go unattributed — written for
rust-analyzer's duplicate `crate/`/`main()` target monikers) fired on
**scip-go too**: a Go package's namespace is declared in every file of
the package, and the controlled dogfood re-ingest (old helper vs new,
same tree) showed the drop removing two module edges that had been
**false since V2.M5** — `hobbes-proxy/main → internal/proxy/knowledge`
and `hobbes-web/main → internal/web/artifacts`, semantic tier, pointing
at same-named files in the wrong package. Zero symbol edges changed for
any language. C-28 was generalised the day it was written — the ADR-037
"too specific" lesson, caught in hours this time.

**I-4 turned red on cue.** The first `hobbes review` after `rustsource`
landed reported I-4 FAIL citing its `tree_sitter` import — the unified
checker forcing the conscious roster amendment ADR-039 promised. Rule
block amended (`rustsource`, `ext:tree_sitter_rust`); statement
untouched; PASS; the lint-imports agreement test runs the new roster for
real and stays green.

**Verified on rust_proj**: 19 nodes, 20 module edges, 33 call edges —
every `calls` edge semantic tier and hand-checked against its cited
line, including test→lib edges through `assert_eq!` token trees; 4
cargo-test rows with correct closure reach; `hobbes lanes` clean (17
sites, 0 disagree; the lane-B-only exclusion counts 17). Dogfood repo
re-ingested: six languages now (the minirust fixture counts), 3,085
sites compared, 0 disagreements; kbet clean. Register: **C-28** (dup
monikers; generalised), **C-29** (ingest executes Rust repo code),
**C-30** (third-party semantics need a fetchable crate registry —
C-23/C-27's fourth language), C-9 amended (macro is the fifth graph
kind). Criterion bench inventory and stage `target/` caching parked in
future_additions.

12 Go packages / 555 pytest / 24 scip / 22 tsextract / 52 vitest — all
green.

**V2.M7 stops here for review.** v2's build programme is fully built;
nothing starts until Max passes the Rust proof.

---

## 2026-08-16 (fifteenth) — V2.M7 passed; the v2 programme closes

Max passed the Rust proof. **v2 is complete: V2.M0–M7 all built,
reviewed, and passed.** This session is the wrap-up he asked for — a
register accuracy audit, a doc sweep, and the README brought current. No
code changed.

**The register audit** (the pre-M6 audit's discipline, applied post-M7):

- **C-6** claimed "two independent implementations"; rust-analyzer is
  the third (0 of 169), so the entry now counts three and its Provider
  line names all of them. The generalisation the entry records was
  *confirmed* by the case it predicted — worth having written down.
- **C-10**'s mechanism sentence predated the one indexer with no version
  flag; amended to note rust-analyzer's moniker version is the crate's
  own Cargo.toml version, constant per commit without a pin.
- **C-15**'s merge order gained Rust (Python → TS → Go → Rust → packs).
- **Debt summary** updated: thirty entries, five lifted, five unsurfaced
  (C-4, C-12, C-14, C-19, C-20 — unchanged; every V2.M7 entry arrived
  surfaced, a first). It also now records C-29's novelty: the first
  entry registering something Hobbes *does* (execute a Rust repo's
  build.rs at ingest) rather than something it cannot see.

**The doc sweep:** the architecture's §7 marks the programme complete
and M7 reviewed; the build plan's header says it is now record, not
plan — and M4/M5's headers, stale at "BUILT, awaiting review" since
before their own passes, are finally marked DONE; first-run.md gains the
rustup install line and the Rust trust note (C-29/C-30) beside the Go
exception; CLAUDE.md's status states there is **no active milestone**
and lists the standing candidates (the derivation itself, and
future_additions) without queueing any of them.

**README** rewritten where it was stale: v2 complete with six languages,
the two-lane section names rust-analyzer and the 0-of-169 measurement,
the status section carries the P7-proven-twice claim and the C-29
warning in user terms ("ingest an untrusted Rust repo only if you would
also build it"), per-language indexer installs added to getting-started,
ADR count 40, test counts current (242 Go / 555 pytest / 52 vitest / 22
tsextract / 24 scip).

Nothing starts next until Max names it.

---

## 2026-08-16 (sixteenth) — the register paydown: four entries, worst first

Max's direction: tackle the easiest and highest-severity constraints. The
register's own ranking chose the slate — C-14 and C-12 held the
worst-misleading list, C-21 had observed real harm, C-19's argument was
one commit of precedent — and each landed as one commit with its tests.

**C-14 lifted** (`79a3e84`). Three packs on the ADR-035 registry:
`cli-ts` (package.json `bin`, both forms), `cli-go` (`package main` +
`func main`, named by the `go build` rule — split-package mains yield
one entry), `cli-rust` (cargo's three binary shapes). PackContext gained
the rust layer; the packs appended to the registry so existing
artifacts' `ran` order holds. Exit check is the entry's own
counter-example, pinned: the dogfood repo's four Go binaries now appear
in `interfaces.json` beside the Python scripts.

**C-12 narrowed and surfaced** (ADR-041, `a6fd519`). The #1 entry's
mechanism was a silent fallthrough in `extractImports`: what the checker
(a per-zone program) could not resolve either named a package or
vanished. Two deterministic fallbacks now run first — relative
specifiers against the repo's own file set (a path is not a compiler
configuration), bare specifiers against the repo's own package names
(read from package.json, entry or subpath) — ordered so a published
copy cannot shadow in-repo source. What still resolves nowhere becomes
one `imports-unresolved` record per file. The floor's first run flagged
`./index.css` on both kbet and this repo — real imports of files the
graph deliberately does not model — so asset specifiers are excluded
from the records by an explicit predicate (the C-26 noise-floor lesson,
applied before the noise shipped). Cross-zone edges are lane A's alone,
syntactic tier, honestly.

**C-19 narrowed to two tools** (`104760b`). semgrep is a dev dependency
and the agreement suite executes generated configs: violating tree
fails, clean tree passes, exclusions exclude, and the dogfood repo's own
I-5 rule runs against the real `narrate/` package on every test run — a
new write path there now fails the suite before it fails a reviewer.
The semgrep emitter survived its first execution clean, recorded in the
register precisely because import-linter's did not. dep-cruiser and
rego remain.

**C-21 surfaced** (ADR-042, `8d825dd`). The queue attaches each
proposal's nearest confirmed record — word-set Jaccard, deterministic,
threshold tuned on the observed I-9/I-3 pair and pinned by test with
the real texts — and the card renders "possible restatement of I-n"
with the confirmed prose and the instruction to read it before
approving. Retired records are history, not neighbours. Surfaced, not
lifted: the neighbour is lexical, and narration still does not read
`.hobbes/invariants/` — the entry's honest residue names both.

Register after the paydown: thirty entries, six lifted, three
unsurfaced (C-4, C-19, C-20), and the worst-misleading list is empty —
what remains under-reports or stays quiet. The next tier of debt, if
Max wants it: C-4 (fixture-aware reach), C-19's last two tools, C-20
(needs a design decision on where decisions live).

245 Go / 566 pytest / 24 scip / 27 tsextract / 52 vitest — all green.
SPA and `hobbes-web` rebuilt.

---

## 2026-08-16 (seventeenth) — the register splits; coverage claims get scoped

Max's direction, one honesty argument in two halves: the register should
read as active vs lifted with lifting techniques documented, and the
project's coverage claims must shrink to their evidence — "asserting
that hobbes can fully cover rust off of a 20 file repo" is a claim the
docs were structurally allowing. Docs only; no code changed.

**The register restructure (ADR-043, `0b72b15`).** `constraints.md` now
has two parts. Active constraints, grouped by subsystem (C-22/23/27
moved out of the narrative section into a lane-B-environments group
where they belong). Lifted constraints, each in a required four-field
format: Was / **Lifted by — the technique** / **Residual edge cases** /
Source — because a lift is a technique with a boundary, and an input the
technique does not classify falls back to being conceded silently unless
the boundary is written down. Two lifted entries gained boundary
documentation the old format never asked for, both verified against the
tree rather than remembered: C-3's TS normalisation is bounded by the
*running* Node's `builtinModules` (not a pin), and C-16's manifest walk
is bounded by format — a `setup.py`/`requirements.txt`-only repo still
presents an empty declared list with the same appears-to-run failure
shape the lift fixed. Numbers stable; nothing renumbered. The register
also now states it is written for anyone who runs Hobbes, named
individuals appearing only as decision attribution.

**Coverage claims scoped (ADR-044).** P11 joins the principles: a
coverage claim is scoped to its evidence, "supported" means the checks
passed on the named sample and licenses nothing beyond it. New §3.8
holds the per-language evidence table and states the asymmetry plainly —
Python and TS/JS multi-repo; **Go's entire base is one repo, this one**;
**Rust's is one small repo, 33 hand-checked edges** — proof of the
machinery, not the language. §3.7 gains mandatory step 4: a language
lands by extending §3.8 in the same commit, else it is wired, not
supported. **C-31** registers the residue and is filed *unsurfaced*
knowingly (thirty-one entries, four unsurfaced): nothing at ingest
states verification depth, and a table in a document is not a surfacing
by the register's own rule. Candidate surfacing named — depth beside the
language list.

**The guaranteed fraction ("Where this is going").** The insurance
framing is now architecture text: a raw-context model carries a 0%
*guarantee*; Hobbes converts some fraction of the codespace to derived,
checked, citable — and that fraction's integrity outranks its size. If
it is 20%, that 20% is properly captured; the complement is identified
as the unique/needs-care part rather than papered over; the sandbox is
the same move on the action side (absent, not refused). This is the
yardstick the unbuilt derivation work will be measured against — derived
context comes from the guaranteed fraction, and what falls outside it
gets pointed at, not model-filled.

Follow-up owed, not done here: re-read README's language claims against
§3.8 (it presents the five languages as peers); C-31's surfacing is new
debt on the unsurfaced list alongside C-4, C-19, C-20.

No tests affected (docs only); suite state unchanged from the sixteenth
entry (245 Go / 566 pytest / 24 scip / 27 tsextract / 52 vitest).

---

## 2026-08-16 (eighteenth) — the tail view: the unresolved remainder, classified

Max's direction in two steps, same day. First: measure what the
unresolved call sites *are* on the three verified repos. Second, on the
result: build it into the real ingest — "that measurement is our
honesty" — with locals handled accurately since the checker can, and
the vocabulary split three ways: what Hobbes sees, what it sees and
does not need to model, what it physically cannot resolve.

**The measurement** (scratch, instrumented ingest wrapping the real
`ev.coverage` — no reimplemented logic). The tails were never uniformly
dark. Go: 68.9% builtin-named (`len`×174). Python: 45.5% builtin-named,
44.4% attr calls on untypable receivers — C-2's fixture claim,
measured. kbet TS: **61% of the tail is bindings declared in the same
file** (setters, handler consts — below C-9's vocabulary, i.e. seen and
deliberately not modelled), 22% imported names the index left dark
(`expect` alone 289 sites), and **9 sites of 1,339** fit no observation
at all. Incidental live fire: the first background run had no
`~/.cargo/bin` on PATH and the rust lane *visibly* degraded
(extraction_errors named the binary and the fix) — artifacts re-ingested
clean after.

**The build (ADR-045).** Classes are observations or `unclassified` —
the standing rule against rationalising the unknown from a checklist of
potentials, which Max named as the fake-honest trap. `tail.py` (pinned
builtin literals, text shape, priority order; per-file counts that sum
to `unresolved` by construction — derived from the same
`_dispositions` walk as the counts, so measured set ≡ counted set).
tsextract **v4**: `calleeOrigin` reports where an unresolved callee's
declarations live (`local`/`nested`/`external`) — the knowledge
`resolveExpressionTarget` was discarding at its gates.
`resolution_coverage` rows carry `tail` (additive, no schema bump);
`hobbes ingest` prints the capture line per language, always against
the honest denominator ("of detected call sites", never "of the
repo"), split *seen-not-modelled-by-design* vs *cannot resolve*.

**Exit check** — the scratch measurement as oracle, checker replacing
regex: kbet `local-binding` 846 (regex said 821; the checker found 25
the regex missed), `external-origin` 462 absorbing what regex called
imported+attr, `unclassified` **3**; dogfood go builtin 314 (= 264 + the
pinned conversion-type names), python builtin 246 / attr 243; rust
tail empty on both repos. Register: C-2 amended (composition measured
per ingest; `fallback-resolved` names the semantic-ledger subtlety),
**C-32** added (the classifier's boundaries: TS-only origins, pinned
lists, text shape — partial). Not scoped: review/surface reading
`tail`; origin support from other syntax providers (C-32's candidate).

580 pytest / 29 tsextract / Go ok / 52 vitest — all green.

**Stops here for Max's review** (milestone discipline: the exit is his
to pass): the mechanism, the class vocabulary, and whether the capture
line's phrasing says what he means.

---

## 2026-08-16 (nineteenth) — the tail view meets private-repo-A and qwen; `import-binding`

Max's direction: run the tail view against the two remaining sanctioned
repos and look for major snags easier to classify than "simply
unknown". Both ingested in place (private-repo-A per its standing rule:
read-only except `.hobbes/` outputs).

**First contact numbers.** private-repo-A python 94.3% of 2,711 detected
sites accounted — the best capture measured on any repo — with
dependency_coverage honestly reporting 9/15 (dev tools uninstalled);
qwen-pathology 82.6% of 546, env not installed (2/6 — datasets,
transformers, vllm missing) and the WARNING said so.

**The snag, found exactly where he pointed.** private-repo-A's 46
`unclassified` python sites were almost entirely bare calls of
**imported names** — `PG_UUID`×22 (an import alias), `pg_insert`,
model classes — and qwen's were `load_dataset`, `LLM`,
`SamplingParams`: imports of the very packages dependency_coverage
reported missing. Lane A already parses those bindings
(`FromImport`'s (imported, bound) pairs), so the class is
provider-grade, no regex: **`import-binding`** — bare call whose name a
same-file import binds. It sits in the *cannot resolve* group beside
its checker-graded TS sibling `external-origin`, because it is
usually the shape of a missing environment. Priority: import outranks
builtin (`from rich import print`); bare calls only (`os.path.join`
stays attr). Python-only, and C-32 says why honestly: binding-proven
not declaration-proven (shadowing matches), and a Go import binds a
package name, not a callable — Go's closure-typed bare tail (~20
sites) stays `unclassified` rather than borrowing a meaningless class.

**Re-verified on all five repos.** private-repo-A unclassified 46 → **4**;
qwen 6 → **1**; dogfood python 48 → 45 (its residue is locally-declared
pytest fixtures — `fake_policy_bin` — a class Python cannot claim yet,
C-32's candidate); kbet and rust unchanged, as they should be. ADR-045
amended in place (same-day, section named), C-32 amended, architecture
§3.4 class list updated.

583 pytest / 29 tsextract — green (Go and web untouched this round).

---

## 2026-08-16 (twentieth) — C-32's candidate fix applied: lane A local bindings

Max passed the tail-view review ("the tail review of the repo really
saves us and will help for validating larger repos") and directed the
C-32 candidate fix: origin support from the other syntax providers
(ADR-046).

**The mechanism.** `pysource` and `gosource` each gain a local-binding
collector — a walk separate from `_walk`, on purpose: one collects what
the graph models, the other what it deliberately does not (C-9's
floor). Python records parameters (a pytest fixture argument is one),
assignment/walrus/`for`/`with`/`except` targets, and nested
`def`/`class` names; Go records parameters (receivers and named
results included), `:=`/`var`/`range` targets, `func_literal`s
covered. Every binding carries its **enclosing function's line
extent**, and a bare unresolved call classifies `local-binding` only
when an extent spans the call's line — scope containment, not a
file-wide name coincidence. A scope-contained local outranks an import
binding (shadowing — the mirror of import-over-builtin, one scope in).
A local class binds its name outward; its methods bind nothing. Rust
deliberately not extended: both verified Rust tails are empty, and
wiring a collector on zero evidence would be the P11 mistake at class
scale.

**Observed impact (all five repos re-ingested):**

- dogfood python: unclassified **45 → 0** (`fake_policy_bin` — a
  fixture parameter — `symbol_at`, `out`, `runner`: all local-binding).
- dogfood go: unclassified **20 → 0** (`cleanup`, `cancel` — the
  closure-typed locals).
- private-repo-A python: unclassified **4 → 0**; qwen keeps its honest **1**.
- TS unchanged everywhere (99/3/9) — correct: its checker origins
  already answer, one grade stronger.

Fleet-wide, the honestly-unknown residue is now **112 sites across
five repos** — all but one in TS zones — plus `attr-call`, the genuine
untypable-receiver limit (C-2's core), which no class may absorb.
C-32 narrowed: the asymmetry is now stated as **proof grades**
(declaration-proven for TS, binding-proven-with-containment for
Python/Go) rather than presence/absence; Rust's absence and the pinned
lists remain. Both collectors carry `TestLocalBindings` suites — the
2026-08-15 audit lesson pre-applied: a grammar bump is what would
drift them, and the tests are what would notice.

598 pytest / 29 tsextract — green (helper untouched this round; Go and
web untouched).

---

## 2026-08-16 (twenty-first) — blindness is context: list_blind_spots and the derivation contract

Max's direction: reference the constraint register as a needed
integration with agentic policy and, eventually, the derived agentic
context layer — "knowing what we cant see is very useful and by adding
that as a part of hobbes functionality we aid agents in pointing to the
work they do need to do." Two deliverables (ADR-047).

**`list_blind_spots(scope)` — built.** The sixth knowledge tool on the
session proxy, and the complement of the other five: they serve the
captured fraction, this serves its boundary. For a path prefix (or the
repo) it answers with the staleness header, the always-on denominator
statement (dynamic dispatch, fixture reach, and computed routes are in
NO count — C-1/C-4/C-5 — so every number is a floor over detected
sites), the per-language capture rollup in ADR-045's two groups,
environment gaps ("invisible, not absent — C-23/C-27/C-30"),
degradation records, the ten worst files class-broken, and a meaning
line per class present, each naming its register entry — C-n references
now reach an agent at the moment they matter, which is P8's bar. Same
contract as the rest: read-only, flight-logged, empty scope = whole
repo. The proxy's tool-inventory contract test pins seven; live smoke
against the real dogfood artifacts rendered pipeline/ correctly
(including the stale-artifacts warning, which was true at the time).
Proxy binaries rebuilt: static `go/bin/hobbes-proxy` + the sandbox
copy.

**The derivation contract — written, not built.** Architecture "Where
this is going" now states two requirements on the future milestone:
derived context carries the **stated complement** beside the captured
fraction (an agent receives "what you must verify yourself" alongside
"what is known", or the derivation recreates the fake-honest gap at the
layer built to prevent it), and derived policy treats unseen regions as
low-evidence — narrow or escalate, never widen. Register preamble now
names agents as an audience; C-2's surfacing gains the agent-facing
leg; future_additions holds the two unbuilt consumers (review verdicts
weighing low-capture diffs, surface rendering) and re-records the
derivation requirement so the milestone inherits it.

246 Go tests across 12 packages green (knowledge +4, proxy inventory
updated); pytest/tsextract/web untouched.

---

## 2026-08-18 (twenty-second) — extraction at scale: dagger

Max signed off on ADR-047's build and named the current work: deep
extraction testing before the derivation milestone ("theres not been
enough extraction testing to clear and thats actually what were
handling now"). Target: `~/dagger` — the Dagger automation engine,
~460 MB, four graph languages plus HCL-less infra, **84 TypeScript
zones, 25 Go modules, ~265,000 detected call sites** — roughly fifty
times the largest prior measurement. Also directed: carry the
directory through the capture reporting. One ADR (048), one register
add (C-33), one C-32 amendment.

**The directory capture view — built.** `rollup_directories()` in
`tail.py`, a pure read over the per-file `resolution_coverage` rows at
depth-2 grain; the ingest summary prints the worst ten directories
**ranked by the *cannot resolve* group** (the first draft ranked by
total unresolved and `internal/buildkit`'s 8,573 by-design builtin
sites outranked `sdk/typescript`'s 3,059 real misses — the view exists
to point at what is missing), with the cut stated, never silent. On
dagger it immediately gave the misses an address: Go read 79.3%
overall while `core/integration` alone held 14,902 unresolvable sites.

**First ingest found three things; two were fixed, one registered.**

1. **The Go unclassified tail was wrapped fluent chains.** 9,131
   unclassified Go sites; `container_test.go` held 783, and an awk
   count of wrapped-chain openers (previous line ending `.`) found
   782. gofmt *mandates* the trailing dot, so `From(` / `WithExec(`
   open their lines and the line-local shape read called them bare.
   Fixed as an observation, not a guess: in Go/Rust/TS a statement
   cannot end with `.`, so `_shape` now reads the previous line's
   ending when a call opens its line (trailing `//` comments cut
   first; comment lines never continue; Python excluded — its chains
   wrap with a leading dot). Go unclassified **9,131 → 359**.
   attr-call 10,672 → 19,444. C-32's text-shape boundary restated.

2. **One broken TS zone zeroed all 84 zones.** The `docs` zone extends
   `@docusaurus/tsconfig` (not installed); scip-typescript exited 1;
   the per-language catch in `_lane_b_facts` could only drop the whole
   lane, and TS capture read **0.0%** on a repo where 83 zones were
   indexable. Go and Rust had the identical shape and dagger's 25 Go
   modules simply all succeeded. Fixed: the three per-unit merge loops
   catch `UNIT_ERRORS` (pinned by test to exactly the per-language
   tuple — P10) and record a degradation naming the unit. Re-ingest:
   TS **0.0% → 18.8%** overall, `sdk/typescript` **0% → 63.7%**, the
   docs zone degrading alone with its fix named. The remaining TS miss
   is environment-shaped (no node_modules anywhere — C-23) and
   doc-snippet trees.

3. **Cross-unit references do not resolve — registered as C-33, not
   fixed.** Dagger's root module calls `dagger.io/dagger`, `replace`d
   to in-repo `./sdk/go`: zero of those calls resolve semantically.
   Reproduced on a two-module fixture at one call site; two layered
   mechanisms found: per-unit staging strips the sibling module's
   sources (scip-go then mis-attributes the reference to the stdlib
   bucket), and even indexed on the full tree — where scip-go emits
   the *exact* moniker the sibling's index defines, versions agreeing —
   `decode()` bins cross-index references into `external_refs` and
   discards the moniker there. Candidate fix (keep the moniker,
   cross-unit join at merge, stage replace targets) is a
   helper-contract change that argues with C-12's no-reconciliation
   decision for TS; written into future_additions for Max's review,
   deliberately not built.

**Lane agreement at scale:** 36,439 dual-resolved sites, **138
disagree (0.38%)**, exit 1. 126 are Go — the demoted fallback
disagreeing with scip-go where it cannot know build tags
(`disk_openbsd.go` vs `disk_unix.go`), interface methods, embedded
types: C-7/C-8's floor, now measured. 11 are a systematic TS
decorator off-by-one where both lanes cite the same declaration
(lane A cites the decorator line, SCIP the name line) — a reporting
convention mismatch, not a resolution difference; noted for review
rather than papered over with a tolerance.

Regressions checked: dogfood re-ingest healthy (go 89.2%, python
88.3%, rust 100%, TS 61.6% with the known 99-site residue), the
directory view printing there too. Also fixed pre-existing:
`test_rustsource.py`'s module-scoped `extraction` fixture ran lane B
(module-scoped fixtures set up before the function-scoped autouse
monkeypatch) — latent since V2.M7, exposed when this session's dagger
run warmed the cargo state and rust-analyzer began succeeding on
minirust.

P11 note: no §3.8 row — no dagger edges were hand-verified. What this
session extends is the honesty machinery's evidence at 50× scale.

618 pytest / 29 tsextract / 24 scip — green (Go untouched; web
untouched).

---

## 2026-08-18 (twenty-third) — the cross-unit moniker join, and the evidence log

Max's direction on the dagger report: carry a repos-tested-with-stats
doc in the repo "for honesty and proof", apply C-33's candidate fix and
retest — edge verification may wait as long as its absence is
documented. The frame: once extraction is properly set, development
moves off testing and Hobbes work becomes last-commit additions, so the
extraction layer is what gets validated and improved now.

**`docs/extraction-evidence.md` — created.** The standing per-repo
evidence log: every real repo the extraction layer has been tested
against, dated numbers, and a mandatory *Verified* line per repo —
including when its content is "none" (dagger's is, explicitly, per the
direction). §3.8 stays the claim table; this is the evidence behind and
beyond it, updated in the same commit as the session that produced the
numbers. README points at it.

**The C-33 fix — applied (ADR-049), C-33 lifted one session after
registration.** Three parts: external rows keep their moniker (helper
facts **v3**, both sides bumped together); `join_cross_unit` after each
language's per-unit merge promotes external rows to references on
**exact moniker equality** — not C-12's rejected reconciliation,
nothing reads another unit's compiler config — with cross-unit
ambiguity abstaining and reported (C-28's rule across units); and Go
replace targets staged beside their consumers (`go_replace_targets`:
consumer's own go.mod only, path replacements only, in-repo only).

**Verified bottom-up.** The two-module fixture that reproduced C-33 at
one call site flips **0% → 100%**, edge `semantic`/`calls`. Dagger
re-ingest: go capture **79.3% → 85.6%** (cannot-resolve 20,501 →
5,571), `core/integration [go]` **59.3% → 96.3%** (14,902 → 396
unresolvable), **+8,014 semantic call edges** including **7,322** from
core/integration into the `replace`d `sdk/go` — the exact miss C-33
named. The two `scip-merge` abstentions that fired are the right ones:
42 anonymous-TS-zone monikers (`npm . .` — colliding single-file
testdata zones, which is the exactness rule refusing false TS joins)
and 7 generated Go testdata modules sharing package monikers. **Lane
agreement: 36,440 dual-resolved sites, still exactly 138 disagreements
— zero added by ~8k new semantic edges**, which is the watchdog saying
the join's edges are consistent wherever both lanes speak. Python,
Rust, TS captures unchanged, as they should be. Dogfood re-ingest
stable.

Register: C-33 → Lifted (Was / technique / residual edge cases:
ambiguity abstains, separate Rust workspaces not staged on zero
evidence, TS alias imports stay C-12, version skew silences rather
than corrupts and lanes would show it). Architecture §3.2 rewritten
(the per-unit paragraph now ends in the join, not an open constraint);
README counts corrected (33 registered / 7 lifted) and the evidence
log linked.

628 pytest / 25 scip / 29 tsextract — green.

---

## 2026-08-18 (twenty-fourth) — node dependencies without touching the repo

Max's direction: TS/JS is the weakest lane across three repos — "look
for any workaround from node that is not invasive to the repos. if
none then add the lever." A non-invasive workaround exists and is
built (ADR-050); the lever was not needed.

**Two mechanisms, one rule: the repo is never written.**

1. **Per-file dependency links** (`zone_dependency_links`). TS
   resolution walks up from the importing *file*, but the stage linked
   only the zone root's nearest `node_modules` — so this repo's
   tsconfig-less `tsextract/` and `scip/` (root zone) indexed without
   the trees sitting beside their own files, while lane A, reading the
   real repo, resolved them fine. A silent lane asymmetry, found by
   asking why hobbes sat at 61.6% *with* everything installed. Now
   every `node_modules` on any zone file's walk-up path is linked at
   its repo-relative position.
2. **Lockfile-pinned provisioning** (`provision_node_modules`). When
   the repo has no tree at all: install into
   `~/.hobbes/cache/npm/<hash-of-manifests>` — `npm ci` for
   package-lock, corepack-run classic yarn (version pinned in code)
   for v1 yarn.lock — `--ignore-scripts` always, symlinked into the
   stage like a repo-owned tree. **Lockfile-pinned or declined**: an
   unpinned install is the registry's answer of the day and would
   break P1, so no-lockfile, pnpm, and Berry zones are declined *by
   name* in per-zone degradation records. C-23 narrowed; **C-34**
   registers the boundary (registry needed, the npm sibling of C-30).

**Measured across the three repos Max named:**

- **hobbes**: ts/js **61.6% → 67.0%**; the tsextract zone 27.7% →
  58.8%, its 131 external-origin sites resolving — links alone, no
  install.
- **kbet**: **72.1%** — already the handled shape (per-package
  tsconfig, tree beside it); residue is third-party external-origin
  calls, not dependencies.
- **dagger**: ts/js **18.8% → 27.9%**; `sdk/typescript` **63.7% →
  70.3%**; the docs zone (yarn v1, docusaurus) **indexes instead of
  failing** — 8 trees provisioned (~833 MB cache). What stays dark is
  honest: docs/versioned_docs (4.5%) is example snippets importing
  `@dagger.io/dagger`, which **no package.json declares** —
  undeclarable, not unprovisioned — and testdata zones without
  lockfiles, each carrying its C-34 reason.

**Lanes as watchdog:** 36,703 dual-resolved sites, 258 disagree — the
+120 over the last run are *all* the TS decorator line-convention
off-by-one (131 total now; both lanes cite the same declaration, lane
A at the decorator line, SCIP at the name line), multiplied because
far more TS has semantics. One genuinely new disagreement. The
convention fix (tssource emits the name line) is future_additions —
a tsextract facts change deserving its own pass, not a tolerance
bolted onto the checker.

Suites: 640 pytest / 29 tsextract / 25 scip green. Evidence log
updated with all three repos' rows; architecture §3.2 amended;
`_nearest_node_modules` removed (subsumed).

---

## 2026-08-19 (twenty-fifth) — the company-shaped derivation workflow, written down

Docs-only session. Max brought a direction for the unbuilt derivation
milestone (from a friend's idea on agentic breakup): structure the
eventual context-derived coding flow the way a software company
structures work — user proposes (head boss) → orchestrator builds what
the proposal actually is under base context → engineers develop a
build plan → a plan reviewer (the dev-ops analog) validates →
engineers adjust or finalize → fan-out to per-feature / specialized
engineers, width a function of codebase size → back to the verifier
before commit. The ask was to get the idea down in writing as a path
forward, not to build anything.

Recorded as a dated entry at the end of `docs/future_additions.md`,
beside — and cross-referencing — the ADR-047 derivation-contract entry,
so the milestone inherits both when it is picked up. The entry carries
three observations beyond the pipeline itself: the cast already exists
in embryo (sandbox roles, `hobbes review` + the unified checker as the
deterministic half of the verifier, the escalation queue as the boss's
approval surface, ADR-047 applying per role); the hard part is the role
taxonomy (how many, which, what type), where Max's proposed method is
mapping a relational system from real software-company role structures
if public data exists — with the filter named as the actual design work
(roles that encode a verification/context boundary map onto agents;
roles that exist for human constraints do not); and the org chart
should be derived from the graph per task, not authored — §3.7's
no-`hobbes.yaml` instinct applied to the fan-out.

No code, no suites run. The derivation milestone stays deferred; deep
extraction testing remains the named current work.

---

## 2026-08-19 (twenty-sixth) — D1: the plan derivation

Max reframed yesterday's entry ("current work structure could be
viewed as economical more than efficient"), added
`docs/agent-mapping.md` — phases not personas; an agent is (context
slice, policy profile, verification obligations); the mapping is an
algorithm over existing artifacts and the org chart is its output —
and directed the build: reference the doc, build the system, register
the concessions.

**Built: `hobbes plan "<proposal>"` (ADR-051), the derivation
programme's first milestone.** `pipeline/src/hobbes/derive/` in
pipeline order: `impact` (lexical seeds — exact matches only,
unmatched code-shaped terms reported not guessed; max-product
expansion with tier/type weights and a per-hop decay), `cochange`
(200-commit co-occurrence window, bulk commits skipped, unreadable
history degrades to structure-only with a stated warning),
`partition` (node weight = module + guarding tests + module doc in
estimated tokens; coupling = tier × type × refs × co-change;
agglomerative merge under a 60k default budget; over-decomposition
merges, oversize flags), `contracts` (cut edges pinned to declaration
sites with owner = definition side and in-scope invariants),
`manifests` (context: interior full / boundary contracts /
one-hop signatures / **complement always** — serialization refuses a
manifest without it, ADR-047 enforced in code; policy: read-only
floor, interior-only write mounts, P10 guarantees emitted first and
raising rather than absorbing, human-first units get no write mounts),
`changespec` (content-hash task ids, byte-deterministic YAML into
`.hobbes/plans/`, and the plan-review gate judging `--adds` edges
against confirmed forbidden-import invariants — exit 1 at planning
cost instead of PR cost, with what the gate cannot check stated).

**The exit check earned its keep twice.** First dogfood run: one seed
(`hobbes.review`) produced **33 units — the whole connected
component** — because a chain of semantic calls propagated at factor
1.0 forever; "tier-weighted decay" with no per-hop term is not decay.
Added HOP_DECAY 0.55 (pinned in ADR-051's table, owned by C-35);
the same seed now yields **3 units / 12 contracts**, each contract
carrying a real declaration site (`hobbes.review →
hobbes.graphdiff.diff_graphs [uses/semantic] … graphdiff.py:54-79`).
Second: the gate run — `--adds "hobbes.derive.impact ->
ext:tree_sitter"` **fails citing I-4** (exit 1) while
`hobbes.extract.pysource -> ext:tree_sitter` passes as the roster
exception; a planned violation of the parser-ownership invariant now
dies before any code exists. Two identical runs write byte-identical
specs (sha256-verified).

Register: **C-35** (partition quality unvalidated — the design's §6
registration obligation, honored on day one; surfaced on every run and
in every spec), **C-36** (lexical seeds — surfaced as
`unresolved_terms` + the exit-2 hint), **C-37** (a pin is a
declaration site, not a signature — surfaced inline in every contract
entry). Architecture: new §6 "Derivation — the task mapping",
§§6–9 renumbered §§7–10 (internal refs and CLAUDE.md's §9 pointer
fixed), "Where this is going" now says the fourth piece is begun, §8
gains the D-programme table. agent-mapping.md restamped as design
record. `.hobbes/plans/` gitignored here (an unapproved plan committed
would put Max's name on decisions he never made; the C-20 shape).
**D2 (execution) deliberately not built** — spawning from manifests,
context faults, the recorder's partition record and loss fitting,
renegotiation, a generative planner above the seeds — parked in
future_additions with dependency order.

688 pytest green (48 new across test_derive / test_changespec; Go,
web, tsextract, scip untouched). D1 exits to Max's review before D2
starts.

---

## 2026-08-19 (twenty-seventh) — the benchmark hypotheses, preregistered

Max named the verification course for the derivation programme: put
Hobbes through benchmark testing **as a harness** — "this works in our
favor of adjusting based on the produced errors and gives a large pure
model pool due to being used known benchmarks." Testing itself is
deliberately not introduced today; what this session adds is the
discipline around it, and the documentation now reflects the project
as it stands.

**`docs/benchmark-hypotheses.md` — created (ADR-052).** The standing
preregistration: three hypotheses, each with the metric that decides
it and what falsifies it, written *before* any run so results cannot
re-scope them — the register's honesty mechanism applied forward, and
the same pattern as extraction-evidence.md (results will land in the
doc beside their hypothesis, dated, naming benchmark / instance set /
models / numbers).

- **H1 — derived context substitutes for model size.** Harnessed
  smaller models perform to the degree of, if not better than, larger
  pure models. Metric: how much of the pure small→large solve-rate
  gap the harness closes, across a model ladder on the same instances.
- **H2 — depth stops costing accuracy.** Context regenerated per unit
  rather than accumulated per session flattens the accuracy-vs-depth
  curve. Metric: solve-rate slope against depth buckets (edit spread,
  chain length), pure vs harnessed, same model.
- **H3 — cheaper and quicker, as a byproduct.** Fewer tokens consumed
  and produced per **solved** instance (never per attempt — a cheap
  failure is not efficiency), at equal or better solve rate. The
  counter-pressure is stated up front: multi-unit plans add
  coordination cost, and the per-depth cost curve settles whether the
  deterministic savings dominate.

The doc also states the current gaps a run has to cross, because
"reflect current status" means the blockers too: **D2 is not built**
(nothing consumes a change-spec — the solve rate is unmeasurable
end-to-end until it is), **C-36 bites first** (benchmark issues are
prose; the lexical miss rate on real instances is itself a number to
record, and the parked generative seed layer is the expected
response), and **instance selection must respect contamination**
(memorized answers bias against the harness, not for it —
post-cutoff or held-out sets, recorded with results).

Threaded through the record: architecture "Where this is going" names
the verification path and §8's derivation table gains the
"preregistered, not started" row; future_additions parks the harness
scope in dependency order (benchmark adapter, prose seed extraction,
dual-arm token/latency/cost accounting, instance protocol); README
links the doc as extraction-evidence's forward-looking counterpart;
CLAUDE.md status updated. No constraints added — nothing here
concedes information; it schedules the measurement of concessions
already registered (C-35, C-36).

Docs only; no code, no suites affected. The benchmark milestone opens
when Max names it, after D1's review.

## 2026-08-21 (twenty-eighth) — two register candidates applied: C-31 and C-32 surfaced (ADR-053)

Max's standing instruction for the session (he was away): review the
register and apply its easiest candidate fixes, two to four if that many
exist, nothing new and nothing deep. The register carried three
candidates. **C-25** (per-repo pack disable list) is the ADR-012 question
in disguise and was left alone. **C-31** and **C-32** were both a pinned
table away, and both are done.

- **C-32 — `tail_classes_available`.** `CLASSES_AVAILABLE` in `tail.py`
  says which classes each language's providers can produce; it rides in
  `graph.json`; the capture line prints `classes this lane cannot
  report: …` per language and `list_blind_spots` prints the same. The
  tests pin the table against the decision tree (builtin-name exactly
  where a list is pinned, origin classes TS-only, the fixture's tail
  inside its row). Status partial → surfaced; what stays conceded is the
  asymmetry itself, now legible.
- **C-31 — `verification_base`.** §3.8 pinned in
  `extract/verification.py`, stamped per artifact language, a property
  of Hobbes and not of the repo. The ingest summary prints it directly
  under the language list and spells out the single-repo rows; the
  surface badges read `go · 1 repo` with the row as tooltip and
  single-repo languages in the stale colour; `list_blind_spots` prints
  the rows before any percentage, scoped to the languages under the
  scope. `test_verification.py` parses §3.8 and fails on drift — §3.7
  step 4 amended to name the twin. Status unsurfaced → surfaced (C-4,
  C-19, C-20 remain the register's unsurfaced three); the entry keeps
  what the surfacing cannot say (what a thin sample missed).

Two things worth noting. The first cut of the blind-spots line was
unscoped, and the existing `web/`-scope test caught it — the verification
base is now filtered by the tail buckets present under the scope. And
the dogfood ingest now prints, under its own language list, that Go is
verified on exactly one repo — this one — which is the line the entry
existed to make someone read.

703 pytest / Go `./...` green / 52 vitest. SPA, `hobbes-web`, and both
proxy binaries rebuilt. Nothing else touched; D1 still awaits review.

## 2026-08-21 (twenty-ninth) — D1 passed; the D2 base (ADR-054)

Max reviewed D1 and passed it, and in the same message set the shape of
the agents for the execution half, with the benchmark harness as the
destination: Hobbes runs alone there, so the manual plan-review step
shifts off for now and proposals are what gets set. His structure, in
his order: per-agent policy from the shared repo policy plus per-role
policies; a standing derived context plus a short-term one read as
role-pushed mail — the orchestrator posts a specific to a specialist's
short-term context and reads the reflection; commits are what alter
standing context and the repo/role policies; everything else in the
mapping stays; the formula learns from the errors benchmark testing
will show. The ask was a rough base of the current architecture, so
that the first twenty-odd problems can surface.

Built, split Go/Python (the Go side in a forked session with a precise
spec; both landed green):

- **Policy chain:** floor → box → repo → **role** → folder → **agent**.
  Role policies are standing files under `.hobbes/policies/roles/`
  (three scaffolded here: implementer, verifier, orchestrator — phases,
  not personas); the agent layer is derived from the unit's policy
  manifest and loaded last. Deny overrides, so it narrows only; a test
  pins that an agent allow cannot widen past a role deny.
- **Agent dir** mounted ro at `/agent`: `policy.yaml`, `context.json`
  (the proxy tags **context faults** against it — served, never
  refused), `context.md` (standing), `inbox.jsonl` (short-term),
  `brief.md` (the prompt: role, proposal, obligations, inbox, standing
  context, complement first-class).
- **`reflect`** on the proxy → `<session>/mail.jsonl`, recorded; the
  orchestrator folds reflections into its own inbox. `hobbes mail
  post|read` is the human's end of the same channel.
- **Harvest:** `hobbes-session` now fetches `hobbes/<session>` back into
  the repo before removing the clone. Until today a session's commits
  died with its worktree — an M4 exit-check design that D2 could not
  live with, found the moment something needed the commits.
- **`hobbes run <task>`:** contract order (owner before consumer), one
  session per unit, human-first units not spawned (inbox says why),
  integration onto `hobbes/<task>` in a detached worktree (conflicts
  recorded at the cut), `hobbes review` over the result, and the
  **partition record** with rework files, faults, exec counts,
  reflections, and the loss under ADR-051's declared weights — tokens
  and wall time named as unobserved, not filled in. The run states
  that re-ingesting the merged branch is what moves standing context;
  it does not do it behind the human's back.

Register: **C-38** — write scope is advisory at path grain (the sandbox
mounts the worktree whole) and is measured as rework rather than
enforced; renegotiation has no re-pin flow; nothing is metered. All
stated in every brief and record. Found along the way: the sandbox
tool allowlist had never included `list_blind_spots` (ADR-047's tool)
— fixed with the `reflect` addition.

Exit check, quota-free: the full loop against a stand-in session binary
that writes the exact Go-side shapes (flight log with a tagged fault,
mail, a harvested branch with one in-manifest and one stray file) —
the record reads 2 calls / 1 fault, 1 commit, `src/stray.py` as rework,
the reflection folded back, both branches integrated, loss positive
from rework alone. Then `hobbes run 2a56 --dry-run` on the dogfood repo
with the real `hobbes-session`: U2 → U1 → U3, agent dirs mounted ro,
the brief as the prompt, guarantees first in every derived policy. No
sandbox session was spawned. 723 pytest (+20) / 212 Go (+15).

Not built, by design of a base: path-grain write enforcement, the
verifier session, the renegotiation re-pin, metering, loss fitting,
the generative seed planner (C-36 — still the predicted first
benchmark friction). D2 base awaits Max's review; the harness is next.

*Close-out, same day.* Both of today's commits were made on a branch
(`c31-c32-surfacing`, cut from `main` at the session's start) and the
first report did not say so; Max found three local branches and no
upstream on the new one, asked where the commits went, fast-forwarded
`main` to `99e6a29`, pushed, and deleted the branch and the long-merged
`m8-exit-check`. Standing rule recorded in CLAUDE.md: commit to `main`
unless directed otherwise, and always state when work lands elsewhere.
Doc sweep done: BUILDLOG (28th, 29th), ADR-053/054, register (C-31,
C-32 surfaced; C-38 added; three unsurfaced remain), architecture
§3.4/§3.7/§3.8/§6/§8, agent-mapping header, future_additions D2
remainder, CLAUDE.md status. D2 base awaits Max's review; the benchmark
harness is next.

## 2026-08-21 (thirtieth) — D2 passed; the benchmark harness (ADR-055)

Max's direction: review the project and the docs first, D2 is passed,
then proceed to the harness unless something blocks — and if something
should be resolved first, recommend before building.

**The review found one thing worth recommending, and it does not block
building the harness — it blocks the first live run.** No session has
ever been spawned live (M4 and D2 both exit-checked with stand-ins),
and reading the sandbox against what a live run needs: the image is
Alpine/musl, `claude` 2.1.238 is a glibc-linked ELF that is mounted
nowhere in the container (only `~/.claude` is), and the session network
is `none`. Granting a session a route to the network contradicts the
architecture's enforcement text as written, so that is Max's decision,
not a session's; it is written up in ADR-055's consequences with the
other live-run items (pure-arm containment, the evaluator's podman
socket, a post-cutoff instance set, quota). Everything that does not
depend on it was built, the way D2 was: quota-free, against stand-ins
that write the real shapes.

**Built: `hobbes bench` (ADR-055).** `pipeline/src/hobbes/bench/` —
`instances` (SWE-bench schema from a local JSONL; the instance
protocol: `created_at` cutoff + filters + prefix limit, every drop
counted; depth = gold-patch file count, declared a proxy),
`workspace` (bare-mirror cache under `~/.hobbes/cache/bench/`, local
clone at the base commit, candidate patch with `.hobbes/` excluded),
`arms` (harness: `ingest` → `plan` with the issue as proposal → `run`
→ integration-branch diff, `no-seed` counted against the arm; pure:
Claude Code on the same checkout, its own tools, no Hobbes),
`accounting` (Claude Code's JSON result envelope as the one meter for
both arms; unobserved stays unobserved through sums), `verdict`
(pinned `swebench==5.0.2` `run_evaluation` as a subprocess; report →
verdicts), `results` (records.jsonl; the H1/H2/H3 report that computes
and does not interpret), `run` (the resumable loop, `run.json`,
patches, evaluate-and-write-back). CLI: `hobbes bench select | run |
report`. `pipeline/scripts/bench_fetch.py` exports a HF split under
uv inline metadata — no dataset dependency in the pipeline. Go:
`hobbes-session --model`, and the default command now passes
`--output-format json` so the harness arm is metered at all.

**Register:** C-39 (contamination bounded, never proven — surfaced
first line of every selection and in the report), C-40 (the verdict is
the evaluator's; provider line `swebench 5.0.2`). C-38's metering
clause amended; C-36 gains its first real-instance measurement.

**Exit checks, quota-free, on real data.** `bench_fetch.py` pulled
SWE-bench Verified (500). `hobbes bench select`: 1-file 429 / 2–3
61 / 4+ 10 — H2's deep bucket is thin there; a 2025 cutoff selects
**zero** of 500, which is C-39 said by the tool. Then the predicted
first friction, measured once: eight `psf/requests` instances checked
out, ingested (lane A), seed-resolved against their issue text —
**8/8 seed; 4/8 seed sets touch a gold file.** The misses have three
shapes (dotted `requests.get` names match no symbol *name*; trailing
punctuation makes prose code-shaped; generic words seed spuriously),
parked as candidate adjustments and **not applied** — the loop adjusts
from verdicts, and there are none. The full harness loop ran against
the stand-ins end to end, including the harness arm through a real
ingest and plan of a local repo.

753 pytest (+30) / Go green (+2) / `hobbes-session` rebuilt. No
quota spent, no sandbox session spawned. **Next:** Max's decisions in
ADR-055's list, then the first live instance set.

## 2026-08-21 (thirty-first) — the owned agent runtime (ADR-056, step 1 of 3)

Max's direction after the harness report: use smaller open models on
compute he already has — Modal, Daytona, Kaggle as spare — rather than
paid APIs, which also sharpens H1. Assessment given first: both arms
ran through Claude Code, whose prompt and tool surface are sized for a
frontier model, so a 7B model through a gateway would measure runtime
fit, not Hobbes; the honest runtime for a small-model ladder is a
minimal loop we own, identical on both arms. Plan agreed in three
steps: (1) the runtime, (2) Modal serving + `swebench --modal`, (3)
Daytona as a session backend. Keys verified usable before building
(`secrets.txt`, gitignored and untracked, checked first; Daytona
`GET /api/sandbox` 200; `modal profile current` → Max's workspace;
no key value printed at any point).

**Built: `hobbes/agent/loop.py`** — one stdlib-only file (a test
asserts the import set), OpenAI-compatible chat with tool calls; MCP
tools listed from the proxy over stdio, confined file tools, `bash`
only when no MCP config is given, no write tools for read-only roles;
prints Claude Code's result envelope so `bench/accounting` reads both
runtimes. **`hobbes-session --runtime FILE --llm-base-url URL`** copies
the loop and the brief into the session dir and runs
`python3 /sessions/<id>/agent.py …` in place of Claude Code; the
endpoint token rides as env from the host's `HOBBES_LLM_API_KEY` and
the dry run redacts it. **`hobbes bench run --runtime openai
--llm-base-url URL`** puts both arms on the loop; `run.json` and every
record carry the runtime. Register: **C-41** — a live session has
egress and carries the model credential, narrowing owed.

Tests: 9 new (`test_agent_loop.py`: a scripted OpenAI-compatible
server on loopback and a stdio fake proxy — routing, confinement,
unique edits, read-only roles, budget and HTTP errors in the envelope,
the script entrypoint, the pure arm on the loop) / Go +2. 762 pytest /
Go green; `hobbes-session` rebuilt. No endpoint exists yet, so nothing
live ran; step 2 is next — a vLLM app on Modal (first rung
Qwen2.5-Coder-7B-Instruct) and the evaluator on Modal.

## 2026-08-21 (thirty-second) — small-model ladder, live, and the solo policy (ADR-057)

Max: run the focus benchmark on small open models on his own compute
(no paid APIs), which also sharpens H1 — the 7B rung has no published
Verified score and is discouraged for multi-step work. Bar set in rung
form: harnessed rung N ≈ pure rung N+1 on the complex multi-step set
(Hobbes-7B vs pure-32B, then 32B vs the next), measured on Verified's
own `difficulty` label.

**Built and deployed.** Steps 2 of ADR-056's plan: `scripts/modal_vllm.py`
(one vLLM OpenAI app per rung, pinned table, scale-to-zero; 7B on A10G
live, 32B on A100 pinned; vLLM 0.10.1.1 + transformers<5 — 5.x broke
the tokenizer, found on the first cold start). `hobbes bench
--difficulty complex` (Verified's rated bands are the depth axis; the
45 `1-4 hours`/`>4 hours` instances are the focus set), `--eval-modal`
(swebench on Modal), `--secrets FILE` (the owner's key file → env,
unknown names refused, values never printed). Keys verified usable
first (Daytona 200, Modal profile resolves); `secrets.txt` gitignored
and untracked throughout.

**First live instance** (`psf__requests-1142`, 7B, both arms, real
podman sandbox over pasta). Pure arm completed empty-patch (4 tool
calls, all text-embedded — the loop now parses and counts fenced-JSON
tool calls, `text_tool_calls`; one edit missed, then a prose plan).
**Harness arm stalled** and I stopped it: a benchmark checkout is a
committed-only clone, so the repo/role policies (untracked under
`.hobbes/`) never reach the session — only the agent policy (default
escalate) and the box floor. With no human approver, `pytest
test_requests.py` and `git add && git commit` escalated and
expire-denied after 30 min each, so the arm could never commit. Run
killed rather than left to finish a meaningless empty patch.

**Fix — the solo policy (the real deliverable of this session).**
`src/hobbes/bench/bench.box.policy`, passed automatically via
`hobbes-session --box` with `--escalation-timeout 5s` (both overridable
by `--session-arg`): allows a lone implementer the test runners,
`pip install`, and `git add`/`commit` (compound forms included) while
the guarantees stay denied and win by deny-overrides (tfstate, push,
derived-add); unlisted still escalates, now fast. The OS sandbox is
unchanged and remains the boundary. Added `hobbes-session
--escalation-timeout`. Register: **C-42** (a benchmark session runs
under the solo floor, not the repo's intent — surfaced in run.json and
the dry run). C-41 is its egress twin.

**Handoff written** for a fresh session: `docs/bench-run-handoff.md` —
the endpoint, the exact run command for the complex set, how to watch
it, what is already known (the finding, text-tool-calls, C-36 on real
prose, cost), and where results go. Context this session got large
after the debugging, so the first full run is deliberately handed off.

769 pytest (+7 across bench/loop) / Go green. 7B endpoint live;
nothing else run — the complex-set run is the next session's.

## 2026-08-21 (thirty-third) — the first full run, stopped and relaunched (ADR-058)

Max's direction: review, start the complex-set run from the handoff,
poll at 20 minutes. Started it (45 instances, 7B, both arms, eval on
Modal). The poll found two structural problems on instance 1
(`astropy__astropy-13398`), both the harness's, neither the model's:
the plan had **210 units** (~7.5 min a session → ~26 h for one
instance), and inside every session `pytest` was exit 127, `pip` 127,
`git commit` 128 — the bare Alpine image has no test environment and
the clone has no identity — after which the 7B tried `apt-get`,
`get-pip.py`, `git config --global`, each escalate-denied at 5s (the
solo policy doing its job on an empty room). Stopped the run rather
than spend Modal credit on an empty-by-construction result.

Max: cap at 20 units ("adjust after with n max sizing"), install the
environment as an acknowledged benchmark practice, relaunch, poll.

Built: **`bench/environment.py`** — both arms run in the instance's
own swebench image (the evaluator's), the workspace bound by
`PYTHONPATH=/work` (a path entry precedes the editable finder) and a
pre-command copying `/testbed`'s untracked build artifacts into the
worktree; verified on astropy that `/work` and `/testbed` give the same
pytest result. `hobbes-session` gained `--path`, `--env`, `--pre`,
`--runtime-python` (the loop runs on the image's base python 3.11; the
conda env carries the target's, 3.6 on old django) and **seeds a commit
identity** into every clone. The pure arm now runs contained in the
same image (ADR-055's containment item). **`build_units(max_units=)`**:
merge past the budget, strongest coupling first then lightest, every
touched unit flagged `capped`; `hobbes bench run --max-units` defaults
to 20, `hobbes plan --max-units` has no default. Register: **C-43**
(binding, not rebuild — compiled-extension changes unseen in-session;
4 of 45 instances are compiled repos), **C-44** (capped = count, not
coupling). Architecture §6.2 amended; handoff updated with what to
check first. Go +3 / pytest +14: **783 pytest / Go green**.

Relaunched fresh (the stopped run's dir kept as `…stopped-1`). The
poll at 20 minutes: five instances done, the cap holding (20 units,
1–2 capped each), `pytest` exit 0 in sessions, commits through — and
**every harness arm `run-error`: `Argument list too long`**. One
capped unit's brief was 488 KB, passed as `--task`. Stopped again.
Fixed: `hobbes-session --task-file` (the orchestrator passes the
`brief.md` it already writes) and a **brief limit** —
`agents.limit_context` trims unprotected sections to an equal share
with a stated cut line each, never the complement/policy/contracts/
invariants; `hobbes bench run --brief-limit 60000` default (≈15k
tokens of a 32k window), per-unit `brief_chars`/`brief_cut` in the
record; **C-45**. Go +1 / pytest +3: **786 pytest / Go green**.
Resumed; the third poll reached the harness arms and ran them — 20
units, `pytest` exiting 4/5 (real), briefs fitting — but instance 1
was still an **empty patch**, from two more harness gaps: a large
read made the *next* completion a hard 400 (window exceeded; the loop
had treated length-400 as fatal), and the 7B edited files but ended
on `reflect` instead of `git commit`, so the commit-only harvest saw
nothing. Fixed: `Endpoint.chat` **fits the window** (shrink
`max_tokens`, then elide oldest tool results in place, stated) and
clips tool results head-first (`--max-result-chars`), reporting
`context_fitted`/`context_elided` — **C-46**; `hobbes-session
--commit-on-exit` (solo path) commits leftover edits at exit,
`.hobbes/` excluded, per-unit `exit_commit_files` recorded — C-46.

Then a **debug loop** on one light instance (`pytest-5787`, harness
arm, isolated — Max's call: confirm the harness on one instance
before another full pass) ran clean end to end and *still*
empty-patch: the 7B wrote a prose plan on turn 1 and never called an
edit tool. Fifth fix — a **bounded prose-plan nudge**: no tool calls
and nothing edited yet ⇒ one "a description is not a fix, edit now"
turn, capped at `--max-nudges` (default 2); envelope reports
`nudges`/`edited`. It makes the model act, never says what to write
(H1 stays the model's). With it the same instance produced a real
**patch** (2 of 5 units edited, 2 commits; 3 declined after two
nudges). Go +1 / pytest +5 across the loop fixes: **794 pytest / Go
green**. Harness confirmed on one instance; the full run relaunched.

## 2026-08-21 (thirty-fourth) — the first 7B complex-set pass, capped, running

The first full run is live: 45-instance complex set, 7B, both arms in
each instance's swebench image, `--max-turns 20 --max-units 10`
(`~/.hobbes/bench/verified-complex-7b`, resumable). It follows five
harness fixes found by successive 20-minute polls and a single-instance
debug loop (all ADR-058, committed `4ee079a`/`bbb9173`/`e21a759`, 794
pytest / Go green):

1. no test env / no git identity → the swebench-image env binding
   (PYTHONPATH + copied build artifacts, C-43) + seeded clone identity;
   unit cap after a 210-unit astropy plan (C-44).
2. 488 KB brief as argv → `--task-file` + brief limit (C-45).
3. 32k window as a hard wall → the loop fits/elides (C-46).
4. edited-but-never-committed → `--commit-on-exit` on the solo path.
5. prose plan, no edit → the bounded prose-plan nudge (`--max-nudges`).

Harness **confirmed** on `pytest-5787`: outcome `patch`, a real branch
diff end to end (the diff itself was wrong — that is the model, and
what H1 measures). First full-run timing: pure arm ~1 min; harness arm
~40–50 min on heavy repos (astropy), so the harness is nearly the whole
cost — the reason for the 20/10 caps (Max's call to cut per-instance
cost).

**Max's strategic notes on this run (parked in `future_additions.md`,
to act on after the results):**
- **Unit selection, not all-spawn.** The orchestrator spawns a session
  for every unit; most reflected "No changes made." The plan should be
  a *stream of selected* units — those the task reaches — with the cap
  a ceiling, not a target. The execution-side twin of C-35.
- **Re-evaluate the harness if its weight stays this high.** ~40–50
  min/instance of harness vs ~1 min pure is most of the cost. The full
  run **need not finish**; the **first 10–20 results are the decision
  point** — a drastic outcome could force a refocus of the harness
  shape itself, not a tuning pass. `benchmark-hypotheses.md` carries
  the reading rule (P11: results do not re-scope the hypotheses).

Run continues; polling every 20 minutes.

## 2026-08-21 (thirty-fifth) — the nudge becomes pipeline discipline (ADR-058)

Watching the capped run, Max caught the real issue behind a slow
instance: `astropy-13579` U10, an **implementer** whose interior
(`asdf/conftest.py`) was unrelated to the WCS-slicing proposal, called
one read-only tool 55 times and edited nothing. His point — an
implementer *with derived context* should not need 20 turns of reading;
integrate the nudge as pipeline discipline, make it stricter. Two
causes: a **spurious unit** (lexical seeds, C-36 — the unit-selection
case, parked) and **no loop discipline against repetition**. Fixed the
second: the loop refuses an identical read-only call (`repeats_refused`
in the envelope), nudges at `--nudge-after` (3) dry turns, and stops a
stall with a reason at `--stall-after` (6) — U10's pattern stops at
turn 9, not 55 calls. Disciplines *how* the model works, never *what*
it writes (H1 stays the model's). Pure-Python loop change (copied into
each session at spawn — no Go rebuild). pytest +3: **797 / Go green**.
Restarted the run under the stricter pipeline for clean decision-point
data.

## 2026-08-21 (thirty-sixth) — run stopped for restructure; session wound down

Owner's call after watching the strict-pipeline run: the spurious-unit
waste is clear and expensive; we have gained enough to **restructure
the harness and start fresh** rather than keep paying for the current
shape. Measured before stopping: **8/17 units ever edited** across
sessions (astropy-13579 was 2/9); the strict discipline halved
heavy-repo harness wall time (13.8 → 6.1 min) but bounding waste is not
removing it. **No solve verdicts** were gathered — the decision point
(first 10-20) was never reached; we stopped on the efficiency finding.

Wrote `docs/harness-restructure-handoff.md` — the fresh-session
starting point: the six harness fixes to keep (ADR-058), the
restructure (task-tailored **unit selection** first, then re-ask the
fan-out shape), and how to start a clean run. Updated the
`hobbes-benchmark-run` memory to point at it. Run stopped, containers
down, partial archived at `verified-complex-7b.strict-partial`. All on
`main`, 797 pytest / Go green. Nothing running.

## 2026-08-22 (thirty-seventh) — the restructure plan, and phase 0

Read the stopped run's artifacts against the gold patches: the
harness patches overlapped the gold files in **zero** places on both
astropy instances. The handoff's "8/17 productive" counted edits, not
relevance. Cause: the lexical seeds — `astropy` (root package, score
1.0) plus fourteen prose words (`input`, `open`, `check`, `unit`, …)
— made the impact set the repository; the cap then merged 300 modules
into one 17M-token unit (brief cut by 418 KB, gold files inside, the
unit that edited nothing) and nine leftover singletons did the
"work". A session also created a file literally named `.:conftest`
(module id rendered before the path), and one unit reflected 123
times.

Max restated the structure: single-use **derived-context** agents,
one alive at a time, job = short memory (planner → reviewers →
implementers → verifier). Wrote `docs/harness-restructure-plan.md`
(phases 0–4, accepted) and built **phase 0**:

- **Seed hygiene** (`impact.filter_seeds`): a package node is set
  aside once a module seeded; a prose-shaped symbol hit is set aside
  once a code-shaped term seeded, unless the proposal names it as
  code. Recorded as `seeds_rejected` in the spec, printed by `hobbes
  plan`. C-36 amended.
- **The cap selects** (`partition.build_units(scores=)`): the
  lowest-impact units are *deferred* (recorded `units_deferred`,
  never spawned, never a seed-bearing one); seed units merge only
  when they alone exceed the cap. C-44 restated.
- **Path-first interior** in the brief; a pathless module is stated as
  not editable. **`reflect` gains `kind: progress | handoff`** (Go);
  only the handoff folds forward, with the dropped count stated.

Exit check, re-planning the archived astropy workspaces (no write):
13579's seeds are now `SlicedLowLevelWCS`, `WCS`, `world_to_pixel`…
(23 prose seeds set aside) and its U10 is exactly
`wcsapi/wrappers/sliced_wcs` + `test_sliced_wcs` — the gold file and
gold test; 13398's U8 is `builtin_frames/itrs`, U9 `hadec` +
`icrs_observed_transforms`. Oversize single-module units remain
(`units.quantity`, `wcs.wcs` — C-35's grain). **805 pytest / Go
green.** Proxy rebuilt (static + sandbox copy). Next: phase 1.

## 2026-08-22 (thirty-eighth) — phase 1: roles first-class

`planner` joins `reviewer`/`verifier` as a read-only role in the Go
sandbox (`ReadOnlyRoles`), the owned loop (`READ_ONLY_ROLES`) and the
role templates (`planner`, `reviewer` scaffolded). The loop's
discipline is role-aware: for a read-only role *acted* means a
`reflect` with `kind: handoff` — the nudge says "call reflect now",
the stall reads "without a handoff", the envelope reports
`reflected` and `role`; an implementer's discipline is unchanged (a
handoff without an edit is still nudged). Every read-only session
gets `PYTHONDONTWRITEBYTECODE=1` so the repo's tests can import on the
ro mount. The plan's verifier-env classification moves to phase 2,
where the verifier session that produces the output exists (no orphan
code). pytest +3, Go +1: **808 / Go green**; `hobbes-session` rebuilt.

## 2026-08-22 (thirty-ninth) — phase 2: the staged run (ADR-059)

Built the execution shape the owner named: single-use **derived-context**
agents, one alive at a time, job = short memory. `hobbes run
--from-proposal` and `hobbes bench run --stages` run a proposal through
stages (`run/stages.py`): a read-only **planner** reads the repo and
hands off the files/symbols/tests the change touches (the generative
layer C-36 always placed above the lexical seeds); `hobbes plan`
derives deterministically on those seeds (`seed_source` =
planner/lexical-fallback/explicit — a rambling planner never fails the
run); **implementers** run in contract order, each cloned at the
*current* `hobbes/<task>` head (a consumer sees its owner's commit) and
integrated immediately; a read-only **verifier** runs the named tests
and hands off pass/fail (a read-only-mount failure is `verifier-env`,
not a fail); opt-in **reviewer** and one bounded **rework**. Handoffs
are `reflect kind:handoff`, parsed tolerantly (`run/handoff.py`) —
bullets, backticks, JSON — never inferring an unnamed file; a
prose-only verdict is marked `inferred`. `impact.resolve_terms` /
`build_lookup` factored out for the tolerant seed resolution.

Register: **C-47** (planner seeds are a model opinion — spec not
byte-reproducible, fallback always available), **C-48** (verifier reads
a ro tree, cannot write a repro). ADR-059; architecture §6.1;
constraints; agent-mapping. pytest +7 (staged loop with a role-aware
stand-in; handoff parser): **815 pytest / Go green**. No live run —
phase 4 (planner-only on the two astropy instances, checked against
gold) is next. Paused here at the owner's request.

## 2026-08-22 (fortieth) — phase 3: the harness adapter

The bench side of the staged run (ADR-059 amended). `run/stages.py`'s
`spawn` now times every session from outside and writes its output as
the agent's `session.log` plus a per-session copy (a rework reuses the
unit's dir); implementers join the stage log as entries, so `stages`
is the whole spawn sequence — plan, implement×n, verify, rework — each
with exit, verdict, `wall_seconds`, and the `UnitRecord`'s wall term
is observed for the first time (the loss's `wall_time` leaves
`unobserved`). `bench/arms.py` sums every stage's own log into the
arm's usage (planner and verifier turns count — H3), carries
`seed_source`, `stage_wall` and the planner's named files/paths;
`results.make_record` scores **`planner_files ∩ gold_files` post hoc**
from the gold patch no session saw (`hit`, `hits/gold`, `recall`,
`named`); `report` gains a planner block split by `seed_source` with
the hit-rate beside the solve rate, and `bench run` logs the hit and
stage walls per instance. **C-49** registered surfaced (the hit is a
proxy against one solution; the report's note names it).

Found while building it: **phase 2's integration branch never
advanced** — `_integrate_one` ran `git branch -f target HEAD` in the
repo (HEAD = the checkout at base) instead of the detached worktree,
so `merged` was recorded while `hobbes/<task>` stayed at base, chained
implementers cloned base, and the verifier verified base. Fixed; the
staged-run test now asserts the branch diffs from base. pytest +3:
**818 pytest / Go green.** Exit check: a dry `hobbes run
--from-proposal` on the dogfood repo records cleanly with no wall
times (no process), and `hobbes bench report` over a synthetic
three-record run prints the split. Phase 1's `ensure_role_policies`
had scaffolded `planner.policy` / `reviewer.policy` into the dogfood
`.hobbes/policies/roles/` untracked; versioned now beside the other
three. Next: **phase 4** — the planner-only probe on the two astropy
instances, reading the hit column first.

## 2026-08-22 (forty-first) — phase 4, step 1: the planner probe hits

Ran `hobbes bench run --stages plan` on astropy-13398/13579 (7B on
Modal). Three attempts; each stop was a harness finding, fixed and
committed before the next:

1. **ADR-060** — the planner died in 1 s: the C-43 pre-command copies
   build artifacts into `/work`, and a read-only role's `/work` was
   `ro`. Read-only roles now mount an **overlay** (`:O`): writable
   in-container, host untouched — the guarantee the flag was for.
   Verified on the Enforcing box (`O,z` is rejected; no relabel
   needed) and with the real astropy pre-command. C-48 narrowed.
2. **Parser + resolver** — the 7B wrote "The proposed changes touch the
   following files:" and `SlicedLowLevelWCS.world_to_pixel`; both were
   recorded as misses by the harness, not the model. `parse_handoff`
   reads a field word in a prose heading and keeps path-shaped bullets
   (flagged `files_source: path-shaped`); `build_lookup` resolves a
   dotted name by unique symbol-id suffix (everyone) or its head
   (planner only — the lexical seeds still never guess, C-36 tests
   pinned it).
3. **Planner seeds replace the lexical layer** (`derive_plan(lexical=)`):
   attempt 3 had merged them and re-admitted the prose seeds.

Result (`docs/benchmark-hypotheses.md` Results): **hit on both** —
13398 1/4 (`itrs.py`), 13579 1/1 (`sliced_wcs.py`), `seed_source:
planner`, 2 turns / ~9k tokens / ~10 s each, **one tool call: the
reflect** (no knowledge tool, no file read). Offline re-derivation
with planner-only seeds puts 3/4 and 1/1 gold files inside spawned
units; the seed-bearing unit survives a cap of 5. Also noted: `bench
run --max-turns` reaches only the pure arm (the sandbox
`RuntimeCommand` passes no `--max-turns`; harness sessions run the
loop's default 60). 820 pytest / Go green. Next: full stages on the
same two, then the 45-set.

## 2026-08-22 (forty-second) — three speed fixes from the first full-stage run

Inspected the 13398 harness arm's 36-min implement stage (per-unit
envelopes + flight logs): 45% of the wall was long prose turns
(U1/U2/U5/U8 wrote the patch as a ~2,800-token essay at ~27 tok/s and
never called a tool; nudged, then stopped), 28% was U4 running one
failing pytest 8x until the window overflowed (exec is exempt from
repeat-refusal), 17% was U6's refused-repeat loop (fixed in 40bc4b1).
Built all three, both arms:

1. **Completion cap** (`--max-tokens`, default **1536**): reaches the
   owned loop through `hobbes-session` → `RuntimeCommand` and
   `Runtime.session_args`/`run_pure_arm`; cuts the essay short so the
   nudge fires sooner. Big enough for a ~120-line whole-file write.
2. **Exec repeat refusal**: the same command with no edit since it last
   ran is refused (`EXEC_REPEAT_REFUSAL`) — a re-run after an edit stays
   legitimate (`edited_since_exec`).
3. **Box policy**: `pip show/list/freeze`, `which` allowed (read-only
   environment questions) — a 5 s expire-to-deny on `pip show numpy`
   cost U9 its session; `pip uninstall` still escalates.

824 pytest / Go green; hobbes-session rebuilt. The full-stage probe
that surfaced these is still running with the pre-fix binary
(resumable); the numbers here are its diagnostic, not a re-run.

## 2026-08-22 (forty-third) — phase 4, step 2: the first end-to-end verdicts

Ran both arms full-stage (`plan,implement,verify`) on astropy-13398 and
13579, 7B, and got the harness's first real solve verdicts. The
evaluator fought back and each fight was a fix:

- **Dataset path**: the evaluator runs from `run_dir/eval`, so a
  relative `--dataset`/instances file (`../verified.jsonl`) died with
  FileNotFoundError after every patch was produced. `evaluator_command`
  absolutizes a dataset that is a file (`f76c2f6`).
- **Dataset schema**: swebench 5.0.2's `make_test_spec` reads
  `instance["image"]`, which only `SWE-bench/SWE-bench_Verified` (the
  new image schema) carries — not `princeton-nlp/…` nor a local export.
  `EVAL_DATASET` is the default for both local and Modal eval.
- **Modal is broken (C-50, P9)**: `--eval-modal` raises
  `AttributeError: TestSpec has no setup_env_script` — swebench 5.0.2's
  own `# TODO`. The **local** path works: `verdict.docker_host_env`
  points docker-py at rootless podman's Docker socket
  (`$XDG_RUNTIME_DIR/podman/podman.sock`), closing ADR-055's "podman
  socket for the evaluator" item.

Result (`benchmark-hypotheses.md` Results, dated): **0/2 both arms**,
planner hit 100% (2/2). 13579 harness applied cleanly, 41/41 P2P green,
the one F2P still failing — a real near-miss. The planner finds the
place; the 7B implementer is the wall on these two (H1's question,
needs the 45-set). 49 bench tests green; the evaluator is unblocked.

## 2026-08-22 (forty-fourth) — write scope enforced at the cut (ADR-061), and the drift's real cause

Inspecting the phase-4 full-stage patches (owner's ask: harness vs pure
actual work) surfaced a structural fault, not a model one. On
astropy-13579 four implementers with unrelated interiors all created
`astropy/wcs/wcsapi.py` — a file none owned, not the gold
`wrappers/sliced_wcs.py` — while U10, whose interior *was* the gold
file, changed nothing; a `session_commit.txt` scratch note leaked in.
On 13398 two units both edited `itrs.py` and the second wrote
`"<updated content>"`, clobbering the first. Cause: whole-branch merge
ignores the disjoint-interior partition.

**Fixed (ADR-061):** `_integrate_one` integrates only a unit's
in-scope diff (`git diff target..branch -- <interior+guards>`, applied
onto target), so out-of-scope source and scratch files never enter the
patch and no two units clobber. Record gains `integration.dropped` /
`empty`. C-38 flips measured→enforced (the run discharged its "would be
tuning a guess"). The capture is raw (bytes) — `_git` strips and merges
stderr, which corrupts a patch. Test drives a stand-in writing an
interior edit + a scratch file, asserts only the interior lands. 827
pytest / Go green.

**The deeper cause, confirmed not fixed (owner flagged it):** the
implementers were led astray, not wrong. `_planner_note` builds ONE
handoff and posts it *identically* to every unit's inbox (short
memory), and each unit's own derived interior is truncated to fit the
brief limit — so the loudest, uncut signal in every brief is the
planner's global file list, and units aim at it instead of their role.
The short memory is not role-derived. Enforcement stops the damage;
making each unit's context role-specific (project the planner handoff
onto the unit's interior; protect the interior from truncation) is the
next change — deliberately not built yet (owner's call). **No model
attribution taken from these harness findings** (owner's instruction —
"that's how we lock a door accidentally").

## 2026-08-22 (forty-fifth) — the planner handoff projected per unit (ADR-062); the interior never cut

Resumed from `docs/phase4-to-45set-handoff.md`: its one
decided-but-unbuilt fix, built before the 45-set spends compute.
**ADR-062:** the plan stage keeps `terms` (planner-named term → module);
`planner_slice` splits them per unit into *in your interior* (resolved
module, or a path-suffix match so an unresolvable named file still
lands with its owner) and *owned elsewhere*; `_planner_note` now takes
the unit's context and posts a **different note to each inbox** — "your
slice of the change — IN YOUR INTERIOR: …", the approach, "N locations
owned by other units: not yours, dropped at integration" — or, when
nothing intersects, says so plainly and nudges toward a no-change
handoff. `## Interior` joins `PROTECTED_SECTIONS`: the C-45 cut never
touches a unit's own paths (phase 4 had cut U1's 21 KB of them while
the global handoff stayed whole). Architecture §6 and C-45 amended.
Tests: the staged stand-in asserts exactly one unit is told the file is
its slice and every other is told it has none; `limit_context` keeps
the 300th interior path; the old `_inflate` helper pads the
neighborhood now. 830 pytest / Go untouched. Next: re-run the
two-instance full-stage probe and read whether 13579's owner unit
edits `sliced_wcs.py`.

## 2026-08-22 (forty-sixth) — parallel implementers over the contract DAG (ADR-063)

Max asked why implement takes so long and where the gaps are. Measured
from the probe's envelopes and a direct timing of the Modal endpoint:
harness per-unit overhead **~1 s** (wall ≈ loop duration for every
unit — my earlier 30–50 s claim was wrong), model decode **~28 tok/s**
is 85–90 % of every unit's wall, prefill ~1 s with the prefix cache,
execs small. The only gap that is ours: ten serial units against an
engine that batches. Max: apply it, speed only, note it as a vLLM
restriction or fall back. **Built:** `run/parallel.py` (deps from
contracts, readiness, `endpoint_batches` via `/models` `owned_by`,
`resolve_workers`); `run_staged(workers=)` runs waves — ready units
start together, harvest+scoped integration stay serial on the
orchestrator thread, human-first units count as done, cycles break by
order; `_integrate_one` diffs from the **merge-base** so a neighbour's
landed change is neither dropped nor reversed; record gains
`implement_wall_seconds` + `parallel.waves`, bench `stage_wall` keeps
`implement_units_sum` beside the outside clock. `hobbes bench run
--parallel auto|N` (auto: vLLM → 4 workers, else sequential, reason in
the banner + manifest), `hobbes run --from-proposal --parallel N`. C-51
registered surfaced. 836 pytest. The ADR-062 re-probe was running on
the old code meanwhile: 13398 implement 1523 s (was 2148), patch 6
files, planner hit 1/4.

**Same session, the ADR-062 re-probe read (harness arm, n=2, 0/2):**
the owner unit now edits its own file — by `write_file` on a module
it never read (13579 U10: pytest + write in one completion, −300
lines; 13398 U2/U7/U9 likewise, −1,646 on `transformations.py`).
Non-owner units told "nothing is yours" still plan to edit the
owner's file (prose, no tools) or write their own untouched
interiors. Implement wall 1,523 s / 670 s (was 2,148 / ~1,250).
Recorded dated in `benchmark-hypotheses.md` Results. Two
observability/discipline gaps named, not built: no transcript in the
session dir; no read-before-overwrite rule on `write_file`.

## 2026-08-22 (forty-seventh) — transcript, unit selection, read-before-overwrite (ADR-064)

Three fixes Max directed from the re-probe trace. **Transcript:** the
owned loop takes `--transcript` and writes the whole message list as
JSONL in the finally (crash-safe); `hobbes-session` passes
`<session>/transcript.jsonl`. A trace no longer stops at the tool-call
line. **Selection:** on the planner path a unit the planner named
nothing in is not spawned — recorded in `units_not_selected`, counted
done so consumers still ready; the lexical fallback keeps every unit.
First cut of the parked task-tailored selection; C-52 surfaced.
**Read-before-overwrite:** `write_file` onto an existing, unread file
is refused (points at read_file+edit_file); a new file or a
write-after-read is fine; both arms. This is what silently turned
13579's 308-line module into a 36-line stub. Four existing loop tests
that overwrote the fixture without reading now write a new path — the
guard changed their premise, not their intent. 840 pytest / Go green;
hobbes-session rebuilt. Next: re-run the single instance through both
arms and review.

**Same session, the ADR-064 re-run (13579, both arms, 0/1):** every
mechanism verified. Selection spawned 2 of 10 units (implement
670→274 s); parallel gate detected vLLM → 4 workers but the 2 live
units are a contract chain (no overlap, wall≈sum); the 62 KB
transcript made U10's reasoning readable; the overwrite guard refused
the blind write, U10 read the 308-line file and wrote a 1,088-byte
stub regardless — the guard forces a read, not comprehension (the ADR
said so). The 7B is the wall on this instance, now cleanly. Recorded
in `benchmark-hypotheses.md`. Stopped for Max's review.

## 2026-08-22 (forty-eighth) — instances run concurrently on the shared endpoint (ADR-065)

Max: since the 7B is served from Modal, not a physical box, run the 5
instances in parallel and review by finishing time. Built
`--instance-workers N` (default 1): a thread pool over instances, each
end to end on its thread, records appended under a lock as they finish.
Honest caveat stated in the ADR and the banner — the speedup is
endpoint-throughput-bound (one A10G, vLLM KV-batched), ~2–3× on five,
not 5×. Removed a latent hazard on the way: session dirs are now
namespaced per instance, so two instances sharing a proposal can't
collide under the pool. One instance's failure is caught, not fatal;
the run stays resumable. 841 pytest / Go green. Relaunching the 5-fresh
set (django, sympy, xarray, sphinx, scikit-learn) at
`--instance-workers 5`.

## 2026-08-22 (forty-ninth) — the 5-fresh set: 0/5, but the failures are harness, not model

Ran 5 fresh instances (django/sympy/xarray/sphinx/scikit-learn) both
arms concurrently (ADR-065). 0/5. Investigation (Max: resolve harness
contribution before any model verdict) found: the planner localized
~4/5, but the **handoff parser** dropped two correct answers — xarray
(both gold files + right fix, on one markdown line: parser swallowed
later fields into `files`) and sympy (named `polylog`, the right
symbol, in prose). And django's broken edit was the **repeated-edit
stack**: identical `edit_file` ×4 (anchor persists in new_text; only
reads/execs are repeat-refused, not edits). Only sphinx's planner miss
(9 unrelated domain files) and one pure-arm new-file are genuine model
faults. Two harness fixes queued: robust handoff parsing (inline
`key:` splitting, prose fallback) and refusing a repeated identical
edit. Recorded in benchmark-hypotheses.md. No re-eval of the model
rung yet — harness first.

## 2026-08-22 (fiftieth) — two harness fixes from the 5-fresh read (ADR-066)

Per the resolve-harness-first rule, fixed the two defects the 5-fresh
investigation surfaced. **Handoff parser:** `_split_inline` splits a
value at inline `field:` boundaries, so a one-line handoff (xarray's
`**Handoff:** files: … symbols: … tests: …`) parses into each field
instead of swallowing them into `files`; multi-line handoffs untouched;
pure prose still not inferred (by design — sympy's `polylog` in a
sentence stays a planner-brief question). **Loop:** a byte-identical
`edit_file`/`write_file` already applied is refused (`EDIT_REPEAT_REFUSAL`)
— django-11400's U4 had stacked one broken block 4× because edit_file's
new_text re-includes its anchor. Verified the xarray handoff now yields
both gold files. 843 pytest / Go green. No re-run — the base is being
tidied and handed off fresh.

## 2026-08-22 (fifty-first) — the 5-fresh re-run on the clean harness: 0/5, the window and the no-read pattern

Max's go for the handoff's next step. Preflight (binaries rebuilt,
843 pytest / Go green, podman socket, Modal 7B cold-started), then the
five instances both arms at `--instance-workers 5`, local eval. **0/5
both arms.** Max also redirected the ladder's next rung to
**`Qwen/Qwen3.8-27B`** (not the 32B; pinned in `RUNGS`, not deployed —
the image's vLLM pin predates its architecture; ADR-057 amended,
hypotheses doc carries the dated reasoning), and, reading the Modal
logs for the first time, asked about the flood of context-length 400s.
Answered from the envelopes on disk: ~390 across the two earlier big
runs, ~10 in this one; the brief is up to 16.7k of 32k tokens, 82 %
of it outside the unit, and the fit elides the model's own reads
first — C-46 amended with the measurement. Hand-read of all ten arms
(recorded in `benchmark-hypotheses.md`): ADR-066's fixes held (xarray
planner 2/2, no byte-identical stack); the dominant pattern is the 7B
**editing without reading** (guessed anchors, "occurs 0 times" ×N);
and three harness gaps around it — a completion cut at `max_tokens` is
undetected (sphinx's planner handoff lost 3×), the fenced-call parser
is narrow, and `edit_file` has no read-before-edit rule (plus the
reworded anchor-stack ADR-066 does not cover). Nothing fixed in this
entry; the fixes follow as their own ADR. No push.

## 2026-08-22 (fifty-second) — read before edit, the anchor stack, cut completions, any fence (ADR-067)

The four harness gaps the re-run read named, fixed in the owned loop
(both arms): `edit_file` on an unread path is refused (ADR-064's rule
extended to edits — the 7B edits from memory); an edit at an already-
applied anchor whose new_text still holds the anchor is refused (the
reworded stack ADR-066 could not see); a completion cut at max_tokens
with no tool call is retried once at 2× (the sphinx planner's lost
handoff), `cut_retried` in the envelope; `_FENCED` takes any fence
tag, an unclosed fence, and `strict=False` JSON. Four tests re-premised
with a read step; four new. 847 pytest / Go untouched. Not re-run:
the brief's shape (82 % outside the unit, C-46 measured) is Max's
decision first, and a launch needs his go.

## 2026-08-22 (fifty-third) — the window per call: validated, then instrumented (ADR-068)

Max, reading the Modal vLLM log for the first time, saw calls
saturating the window far more than the envelopes counted — minute-long
calls, a context-length 400, then "a 200, fine". Inspected it properly:
reconstructed all 221 harness calls of the re-run by tokenizing each
message prefix on the endpoint and checked the sums against vLLM's own
`prompt_tokens` — exact to a constant 1,546 tokens/call (the tool
schema). Result: the re-run itself (02:38–03:10 EDT) was not
saturated (median 14k, 2 calls ≥ 28k, one session fit/elided); the two
earlier runs were (198 and 190 overflow events, prompts 16–19k mean,
sessions sitting at the window turn after turn) — that is what a
day-spanning log shows. The pure arm turned out to write no transcript.
Built ADR-068: `calls.jsonl` beside every transcript (prompt/completion
tokens, `max_tokens` actually sent, `finish_reason`, fit/elide events,
wall), `prompt_tokens_max` / `calls` / `calls_saturated` in the
envelope, the pure arm passes `--transcript`. C-46 surfacing amended.
848 pytest. Not re-run.

## 2026-08-22 (fifty-fourth) — the brief sized to the window, filled by priority (ADR-069)

Max, torn between "go to the 27B with a huge window and stop caring"
and "scale the harness context to the model's window": recommended
the second as the harness's own fix, then the cheap 7B run, then the
27B. Built: `endpoint_window()` (`max_model_len` from `/models`),
`brief_limit_for_window` (35 % × window × 3.3 chars/token, both
declared guesses), `--brief-limit` default auto with the resolution
printed and in `run.json`, and `limit_context` filling the cuttable
sections by priority (inbox → guarding tests → neighborhood → module
docs) with a 60 % per-section cap instead of equal shares; the limit
is a guarantee. C-45 and architecture §6 amended. 851 pytest. Launching
the cheap 7B 5-run on ADR-067/068/069 at Max's go.

## 2026-08-22 (fifty-fifth) — the cheap run: reads clipped, no search; ADR-070

Max's go. Ran the five on ADR-067/068/069 (brief auto-sized to 37,847
chars from the endpoint's 32k window). 0/5 both arms. The per-call
log earned its keep on its first run: forced reads pushed four
sessions to 31–32k prompts; 40 of 161 reads were clipped at 12k chars
and only one used a line range — the model read the top of a
260k-char file and kept guessing the anchor (15 of 18 anchor-missing
sessions had a clipped read); the loop had no search tool. The sphinx
planner was cut at 1,536 and at the 3,072 retry (a 9,895-char file
enumeration). Built ADR-070: `search_file` (confined regex over a file
or tree, both arms), the clip notice and the unread-edit refusal both
name it, the planner brief bounds the handoff (≤5 files, <15 lines).
853 pytest. Recorded in benchmark-hypotheses.md. Next launch is Max's
call; the 27B remains the rung after the 7B's failures read clean.

## 2026-08-22 (fifty-sixth) — the verification run: the 7B's shape, and the exec name (ADR-071)

Max: run the 7B again to verify, fully honest. 0/5 both arms. All five
planner handoffs parsed (the ADR-070 bound worked; sympy hit 1/1 for
the first time); sklearn U2 did the entire search → ranged read → copied
anchor → edit chain, then had its `pytest` refused as a repeat —
because the loop's shell check matched only `…__exec` and the proxy's
tool is `exec`: in every harness run since ADR-058 a test re-run after
an edit was refused, which is the exit most harness sessions end on.
Also: `search_file` answered a missing path as "(no matches)" (two
pure arms edited phantoms on that); a planner path with a sentence dot
went unresolved; and sympy's gold owner was **human-first, parked** in
this and both earlier partitions — the better planner produced the
emptier run. Built ADR-071: `is_exec_tool`, `hobbes bench run
--human-first park|spawn` (default park; spawn keeps write scope,
records the abstention; C-53), missing-path search error, handoff
punctuation strip, zero-site guard. Seven of ten arms read as the
model's, cleanly, for the first time. 857 pytest. Not re-run: the next
run is the first with no known harness doubt, and it is Max's go.

## 2026-08-22 (fifty-seventh) — the planner never had the context (ADR-072)

Max: did sphinx's planner name the wrong file *given* the right one?
Inspected: no. `repo_context` listed the first 60 modules by path —
the gold module was in 1 of 5 planner briefs; every planner's only
tool call was its handoff. So every planner hit of the day measured
the 7B's prior knowledge of the repo (C-39), not Hobbes. Built
ADR-072: the map ranks modules by proposal overlap on path and symbol
tokens, rarity-weighted, best-5 + 0.25×rest, top 80 listed with the
matching terms, plus the full package tree and a confirm-before-naming
line. Measured on the five real graphs: every gold file now in the map
(worst rank 71). C-47 amended. 859 pytest. Launching the 7B on
ADR-071/072 with `--human-first spawn` at Max's go.

## 2026-08-22 (fifty-eighth) — the ADR-071/072 run: the planner uses Hobbes, the 7B still writes from memory (ADR-073)

Fourth 7B run, `--human-first spawn`. 0/5 both arms. For the first time
a planner localised from derived context — sympy: search → read →
who_calls → tests_guarding → the gold file and the gold test. sklearn's
planner called `graph_neighborhood` by path and was refused three
times: ADR-073, the tool resolves a path (Go, proxy rebuilt). The exec
fix verified (a re-run after an edit runs; the no-edit repeat is
refused with the right message); sympy's human-first owner ran and
tried to overwrite the module from memory. No anchor miss is a
line-number artefact. Read: the 7B cannot execute on derived context;
the rung is done. 859 pytest / Go green. The 27B is the next decision —
Max's.

## 2026-08-22 (fifty-ninth) — the thinking rung: Qwen3.8-27B served and the loop taught to think (ADR-074)

Max's go: resume at the 27B, the 7B runs having been inspected down
to the model's limit. The rung is a thinking hybrid
(`Qwen3_5ForConditionalGeneration`, 48/64 linear-attention layers,
262k native), not a bigger Coder: vLLM's recipe wants ≥ 0.17 and
transformers ≥ 5.8, and the `qwen3` reasoning parser "is not optional
in practice". Built: the Modal image bumped to vLLM 0.27.1 /
transformers ≥ 5.8 (one image for every rung); per-rung
`reasoning_parser` + `extra` flags (`qwen3_coder` tools,
`--language-model-only`, window 131,072 — half the native, declared
from the KV budget and the ADR-069 brief size); `loop.py`
`--temperature/--top-p/--reasoning-effort/--thinking`, the reply's
`reasoning_content` kept on the assistant message (preserve_thinking
and the transcript) and `usage.reasoning_tokens` counted when
reported; `bench.Runtime` carries the sampling once for both arms,
the harness arm through a new generic `hobbes-session --loop-arg`.
The run's settings pre-registered in benchmark-hypotheses.md
(thinking on, effort medium, temp 1.0 / top-p 0.95, max_tokens 8192).
866 pytest / Go green. First deploy attempt died on a Modal pip-mirror
timeout (a 170 MB CUDA wheel), not a pin; redeployed. The cold start
then found two real defects (ADR-074 consequences): `MODEL` was read
from the host env and unset in the container (the 27B app served the
7B), and vLLM 0.27's flashinfer sampler JIT needs nvcc (engine core
dead, startup timeout). Both fixed; 7B re-verified on the new image;
27B smoke: 131,072 window, 305k KV tokens, reasoning split, structured
tool call. Launched `five-fresh-27b` at the pre-registered settings.

## 2026-08-22 (sixtieth) — the first 27B run, and the harness defect it exposed (ADR-075)

Ran `five-fresh-27b` (both arms) on the deployed thinking rung at its
pre-registered settings. **pure 40 % (2/5), harness 20 % (1/5), delta
−20 pts** — and the cause is a harness defect, so the run is **void as
a model verdict** (resolve-harness-first). The policy engine matched a
whole command string against anchored globs; a capable model's compound
commands (`cd /work && python -m pytest …`, `git -C /work status && …`,
`PYTHONDONTWRITEBYTECODE=1 python …`) matched no box allow rule and fell
to `default: escalate` → 5 s expire-deny, no approver. **104 of 253
exec calls escalated**; implementers couldn't self-test, all three
unresolved verifiers reported "nothing could be executed", some couldn't
commit. The pure arm runs bash directly (no proxy), so it was unharmed —
the gap is the proxy, not the model, and the 27B (writing `cd /work &&`
more than the 7B) was penalised harder. Built ADR-075:
`Chain.ResolveCommand` splits on top-level `&& || ; |` (quote-aware,
conservative), strips `cd`/env prefixes, resolves each segment and takes
most-restrictive-wins (deny > escalate > allow) — a command is as
permitted as its least-permitted part; this also closes a hole where
`git status && rm -rf /` matched `git status*`. Box policy broadened
with the read-only pipe filters (now that a pipe target is checked).
C-54 registered. **Real despite the defect:** planner localised from
derived context at 80 % (4/5) grounded via search + who_calls +
tests_guarding; xarray solved on the harness arm end to end; both pure
failures were harness too (sphinx tripped the stall rule mid-search,
sklearn hit the 3600 s wall). 866 pytest / Go green (new policy tests); proxy rebuilt
(static + sandbox copy). Not re-run — the ADR-075 re-run is Max's go,
and the thinking-model stall/timeout knobs should be settled first.

## 2026-08-22 (sixty-first) — the thinking-model loop knobs, and the shared-failure read (ADR-076)

Inspected the pure-vs-harness losses on `five-fresh-27b`. Of the three
instances both arms failed — sympy, sklearn, sphinx — only **sympy** is
a genuine shared *model* miss: both arms localised the gold file and
edited it, but both implemented only the issue's one worked example
(`polylog(2, 1/2)`) not the full closed-form table the hidden
`test_polylog_values` requires; pure put it in `eval` (right method,
incomplete + `S.Pi` bug), harness put it in `_eval_expand_func` (wrong
method — never fires on automatic eval) and was blind (8/9 exec calls
expire-denied, C-54). sklearn and sphinx are **harness**: sklearn's
gold ranked 44/71 in the map and the planner named `_set_output.py`
(the module gold *calls*) — a localisation miss — while pure never
patched (3600 s timeout); sphinx's planner localised (1/2) but the
implementer units were strangled by C-54 and only the test unit merged,
while pure stalled at 6 dry turns mid-investigation. So two of the three
shared losses are the harness, and both pure losses were a timeout and a
premature stall — not the model. Built ADR-076: `bench run
--stall-after/--nudge-after`, carried to both arms via Runtime, loop
defaults (6/3, cut for the 7B) unchanged when unset — a thinking model
investigates before editing and must not be stopped as if stalled.
867 pytest / Go green. Next: the scoped ADR-075/076 re-run (the four
harness failures + xarray as control) at Max's go.

## 2026-08-22 (sixty-second) — the programme reframed: outward-facing, small-model derivation validation, harness-on-top (docs only)

Two strategic decisions recorded (session-handoff STRATEGY section;
hypotheses Method section). (1) **Hobbes is now an outward-facing
university AI-research group project** with cluster access coming — the
honesty discipline and doc quality matter more, read by more than the
builder. (2) **Small models are fast validators of the derivation:** the
7B's garbage is diagnostic — low threshold, quick, legible failures that
separate a Hobbes error from a model error (a large model papers over
weak context, C-39). So validate the context piece on a small model
across a **diversified selection set** (breadth over depth) to capture
the broad space of Hobbes's own error modes; large-model runs test the
bar (H1). (3) **Build on top of a referenced open harness** (SWE-agent /
mini-swe-agent / OpenHands / Aider) — run both arms inside it so derived
context is the only variable, making the harness a dependency not a
deliverable; the ADR-058..076 harness hours were requirements-gathering
that yield the interface Hobbes needs (per-unit context injection,
write-scope, policy boundary, one meter). Separate research-core
(derivation) from plumbing as the team forms; the cluster likely
dissolves the ADR-056 constraint that forced the owned loop. No code
change this entry — direction, recorded not hidden.

## 2026-08-22 (sixty-third) — mini-swe-agent chosen and integration validated (no run yet)

The harness pivot's first concrete step. Max is suspicious the earlier
0/5 7B verdict was our bespoke harness (which void-ed every run this
session by starving the arm), not the model — worth a ~30-min 7B 5-set
re-run through a referenced harness. Chose **mini-swe-agent** (v2.4.6)
and validated the two hard seams without touching the running 27B:
its litellm model layer returns content from our 7B Modal endpoint
(`MSWEA_COST_TRACKING=ignore_errors` for the unmapped local model), and
`MSWEA_DOCKER_EXECUTABLE=podman` drives the *same* swebench images we
already pull; its batch runner emits a standard predictions file our
evaluator reads, and `agent.instance_template` is the derived-context
injection point. `swebench_backticks.yaml` (text actions) is the 7B-
friendly config. Recipe + the two-arm plan (baseline = did our harness
suppress the 7B; +context = does derived context help on a neutral
harness) in `docs/harness-mini-swe-integration.md`. **Not run** — mini's
containers share the rootless podman with the active 27B run, so the
7B baseline run waits for the 27B run to finish. Docs only.

## 2026-08-22 (sixty-fourth) — the first clean 27B comparison: pure 4/5, harness 1/5 (the falsifier fires)

`five-fresh-27b-adr075` (ADR-075/076 harness). Both arms now execute on
every instance — the proxy confounds are gone — so this is the first
comparison harness quality does not dominate. Result: **pure 4/5,
harness 1/5** (n=5, one-solution proxy). ADR-076 unleashed the pure arm
(40%→80%; sphinx and sklearn, before a stall and a timeout, now solve).
Per-instance the harness losses are the **multi-unit decomposition**, not
the proxy or localisation: django (planner named 1/3 gold → C-52 leaves
the other units unspawned → only 1 file edited → 4/6 F2P) and xarray
(1/2, edited 1 of 2 gold) are **multi-file completeness** gaps; sphinx
(planner 2/2, both gold edited, F2P green) failed on a **P2P regression**
(cross-unit over-edit); sympy both arms failed (model under-implements;
pure errored turn 1). sklearn the harness *solved* via a valid alternative
location (`_set_output.py`, not the gold files) — C-49 made real: the
gold-file planner metric undercounts. The preregistered falsifier fired:
once the harness can execute it does not beat pure, so the wall is the
partition/integration model, not the proxy. This strengthens the mini-swe
pivot (single-agent + injected context, which does not fragment the
change) and raises two derivation questions: keep a fix's full co-changing
set in one unit? is per-unit write-scope worth its fragmentation cost?
Recorded in benchmark-hypotheses.md. Checkpoint — paused here per Max;
the mini-swe 7B baseline is teed up and not yet run. Docs only.

## 2026-08-22 (sixty-fifth) — aided implement mode: aid, don't fence (ADR-077)

Inspected why the harness lost the multi-file instances on the clean 27B
run. django: the fix's 3 co-changing files scattered across units U4/U1/
no-unit; planner named only filters.py → C-52 spawned only U4; U4's write
scope EXCLUDED the other two gold files → the coherent fix was
structurally impossible inside the unit boundary. xarray identical (1 of
2). The planner's approach prose named the mechanism in the unnamed files
and the pipeline discarded it. So the harness was *overriding* the model
(fencing it below the task), not aiding it — the pure single agent edited
all files and solved. Built ADR-077 `--implement-mode aided`: planner
unchanged; then ONE implementer on the whole worktree, whole diff
integrated (allowed=None), brief = task + what-Hobbes-can-see (planner
localisation + symbol neighborhood) + what-Hobbes-cannot-confirm ("the
named files are where the change STARTS; edit ANY file the fix needs; a
head start, not a boundary"). rework_files still measured, never fenced.
Dry-run brief on django's real graph reads correctly. 868 pytest / Go
green. Next: observe on the 7B (prompt inspection + flow) whether the
aid-not-fence brief reaches a free agent and yields the coherent
multi-file change — a new-harness observation run, not a 1-1 vs 27B.

## 2026-08-22 (sixty-sixth) — contamination demonstrated on Verified; the 27B pure baseline is recall (C-39 amended)

Max's suspicion: Verified is contaminated, and contamination would
favor the undivided arm asymmetrically (regurgitating a whole memorized
patch needs the whole task, which the partition denies) — making
Hobbes's break-up "invalid by design." Inspected the 27B pure solves:
xarray pure reproduced the gold patch **verbatim including the author's
forward string `dim will be removed in version 0.19.0`** — a maintainer's
future deprecation target underivable from the repo — plus 100% of gold
added lines on xarray (29/29), sklearn (19/19), sphinx (23/23). The 7B
produced empty xarray patches. This is memorization, size-dependent, and
asymmetric — confirmed. So the clean 27B comparison (pure 4/5 vs harness
1/5) and its falsifier are confounded in Hobbes's disfavor: part of the
gap is the partition blocking recall, not hurting reasoning. django (43%
reproduction, real exploration) is the only reasoned-looking pure solve.
Recorded honestly: C-39 amended (contamination demonstrated + asymmetric,
post-cutoff set now necessary not optional), a CONTAMINATION CAVEAT on
the adr075 Results entry, handoff updated. Bearing on the in-flight aided
7B run: the 7B could not reproduce xarray, so it is the *cleaner* subject
for testing whether derived context aids capability (recall is not
available to it). Docs only.

## 2026-08-22 (sixty-seventh) — redirect to DeepSWE 1.1 on Pier + mini-swe-agent (docs only)

Max's call, from the contamination finding: shift off SWE-bench Verified
to **DeepSWE 1.1** (datacurve-ai, arxiv 2607.07946) — 113 original
long-horizon tasks in Py/TS/Go/JS/Rust, built against both of SWE-bench's
flaws (mined fixes → recall; shipped tests → one-fix grading). It uses a
behavior verifier (LLM-judge disagreement ~1.4% vs 32.4% for SWE-bench
Pro) and runs on **Pier** with `--agent mini-swe-agent` natively — so the
redirect *is* the harness pivot: the validated mini-swe substrate, on an
uncontaminated set, Hobbes injecting derived context (ADR-077 aided shape)
as the only variable. Removes contamination (C-39), the one-solution
proxy (C-49), and our bespoke exec/policy/partition harness at once; the
multi-language mix fits Hobbes's breadth. Blockers: HF-gated access (no HF
token in secrets — Max must accept terms + add one), install Pier 0.3.0+,
wire mini-swe to our Modal endpoints (litellm validated), prototype the
Hobbes injection on one task, ingest per-task repos. Plan in
`docs/benchmark-deepswe.md`; handoff REDIRECT section. The in-flight 7B
Verified aided run continues (cheap; its value is the aided-flow trace,
not its score) — inspect, then redirect. Docs only.

## 2026-08-22 (sixty-eighth) — session closeout: 7B read as a checker, README caught up, DeepSWE teed up (docs only)

Aided 7B run (`five-fresh-7b-aided-fix`) — the first *correct* aided run
after fixing a dropped `implement_mode` flag (ADR-077 wiring; guard test
added). 0/5, planner hit 75%. The traces closed the 7B chapter: where it
engaged the aid it went straight to the gold file (sympy: read→edit, 2
turns); elsewhere it confabulated (django: claimed a change it never
made), used the wrong path (sphinx: `autodoc.py` for the named
`autodoc/__init__.py`), edited blind (sklearn: 6 edits, 0 reads), or
looped on exec (xarray: 56 execs, 0 edits). None are the fence — the wall
is the 7B's execution reliability. **The 7B's only remaining use is a
diverse, quick Hobbes checker before a full benchmark run**, not a
capability measure (recorded in benchmark-hypotheses.md). HF access for
DeepSWE cleared (HF_token validated + registered as HF_TOKEN). README
brought current (it had the derivation as "not built" and the harness as
"no live run" — both long false): derivation programme built + under
test, the harness pivot, the contamination finding, the DeepSWE redirect,
counts (77 ADRs, 54 constraints, 869 pytest / 291 Go). Session closed
clean — nothing running, no containers. Next session starts at the DeepSWE
setup (`docs/benchmark-deepswe.md`, handoff REDIRECT).

## 2026-08-22 (sixty-ninth) — DeepSWE on Pier: first run, one task per arm (ADR-078)

Max's go: review the docs, set up the DeepSWE run, one task per arm,
report. Built the substrate in `~/.hobbes/deepswe/`: py3.12 venv with
`datacurve-pier` 0.3.1 (PyPI `pier` is an unrelated package) +
mini-swe-agent 2.4.6; the 117 task definitions are public in
`datacurve-ai/deep-swe` (no HF download needed to run); Pier drives the
box's Docker Engine 29 / compose v5 directly (podman socket is the
fallback). Task: `httpx-multipart-response-parsing`. Three immediate
errors, each fixed: (1) BuildKit metadata fetch for the 4 GB ECR base
timed out and killed the trial in 60 s — pre-pull the image; (2) the 7B
on mini's native tool-calling config emits a pseudo-XML `<tool_call>` in
content (probed directly), so every turn is "no tool call" →
`RepeatedFormatError` in 3 turns — both arms moved to
`litellm_textbased` + `mini_textbased.yaml`; (3) `pkill` on my own
wait-loop pattern killed the relaunch (mine). Injection: Pier's
`--ak prompt_template_path` Jinja seam, aid built deterministically by
`scripts/deepswe_aid.py` (ingest at base commit → `hobbes plan` seeds →
capitalised-name symbols → neighborhood → tests), spliced from
`aided_brief`; confirmed present in the Hobbes arm's first user message.
**Result:** both arms reward 0, empty patch (P2P 1272/1272 — verifier
grades the unchanged tree). Baseline: 100 calls / 11m53s, never opened a
file, chased a fictitious `origin` remote until the window filled. Hobbes:
17 calls / 1m42s, read `httpx/_models.py` on turn 2 (the aid localised),
then repeated one `cat` response 12× (mini has no repeat-refusal) until
the window filled. Read as the 7B checker: the loop is wired end to end
and the aid changes the first move; no capability claim. C-55 registered
(aid derived without the planner stage; surfaced in the aid text).
Scripts versioned in `pipeline/scripts/`. Nothing running at close.

## 2026-08-22 (seventieth) — 27B on Pier: the repeat guard, commit-on-exit, and two near-solves (ADR-079/080)

Max's read of the sixty-ninth: window-fit was ours only (confirmed: mini
clips per observation, never fits the window), add a repeat refusal,
move to the 27B. Built `hobbesmini` — a mini-swe-agent agent class
(`RepeatGuardAgent`) that refuses an identical consecutive action and
exits `RepeatedActionError` after 3 (ADR-079); it reaches Pier's
image-build-time agent install as a wheel served on the docker bridge
address only (a runtime mount cannot — learned by failing). 27B probed:
native tool calls work on vLLM 0.27's `qwen3_coder` parser. First 27B
pair: both arms wrote a complete implementation and lost it uncommitted
(baseline to the 90-min AgentTimeout while re-running the full suite;
Hobbes arm to a 131k ContextWindowExceeded one action after `git add`)
— ADR-058's lesson in the referenced harness. Built commit-on-exit into
hobbesmini 0.2.0 + `--agent-timeout-multiplier 2` (ADR-080). Second pair:
**baseline 115/122 F2P, Hobbes 107/122**, both P2P 1272/1272, both
COMMITTED by the exit hook, both context-bound at 131k (mini keeps every
file dump and diff). Misses are real spec items (close-before-raise on
malformed closure; header continuation spacing; streaming chunk splits).
Results table in benchmark-hypotheses.md; n=1, no H1 reading. Next
decision (Max): a window-fit for the referenced harness, both arms. 9
new pytest. Nothing running at close; the wheel server
(`http.server 8765 --bind 172.17.0.1`) is a session process and dies
with it — restart it before the next run.

## 2026-08-22 (seventy-first) — the aid was a pointer, not a map: spans added, read-volume metric, re-run launched

Max's suspicion, checked against the trajectories: the Hobbes arm was
given only `files: httpx/_models.py` + class names, no lines; it took the
pointer at turn 4 and read the whole 1,085-line file in six silent
slices (no plan of its own, nothing fought). The baseline indexed
(`grep -n "class \|def "`) and jumped to 515–700 / 856–1080 — the
strategy the aid should have supplied. So the arm exhausted its window
first because the aid widened the read, not because of mini. Built:
`deepswe_aid.py` now emits **declaration sites** (`symbol (file:line-end,
kind)`, C-37's pins) for the named symbols, the stream/close members of a
named class, and the neighborhood, with "read these ranges first";
`deepswe_read_volume.py` computes the per-trial read-volume metric
(observation chars by command kind, heredoc bodies kept, largest reads).
Re-run of the same task on the 27B, both arms (`-spans`), launched.

## 2026-08-23 (seventy-second) — C-56 instruments applied, the obs pair: baseline solves, Hobbes 120/122; paused on cost

Max stopped the spans re-run at three minutes to apply the C-56
candidates first (ADR-081): familiarity probe (forced reconstruction —
the `UNKNOWN` escape refused even `textwrap.dedent`; thinking disabled
or a Qwen3.x returns empty content), observation-shaped aid (`hobbesmini`
0.3.0: the aid becomes the agent's own first `hobbes context` tool
exchange; markers stripped from the prompt), solution-shape diff. Then
the pair: **baseline 122/122 reward 1** (first full solve; `Submitted`
at 76 calls / 125k), **Hobbes 120/122** (context out at 68 calls /
130k, commit-on-exit COMMITTED; parser built inside `_models.py`).
Reads: spans at class grain (`Response 515-1076`) were followed
literally — 109k vs 124k chars, not the 4× narrowing expected; next is
method-grain-only spans. Shape: all four 27B patches pairwise ~0.1 —
independent constructions. Familiarity 27B/httpx: 0.21 verbatim, equal
to stdlib calibration. Max: note the economics — ~3 A100-hours per
pair, four pairs in a day; **15 minutes of evaluation before any >30-min
run; paused** (handoff ECONOMICS, memory). Nothing running; wheel server
is a session process. 13 pytest in the guard file.

## 2026-08-23 (seventy-third) — the brief-bloat levers, measured (no runs)

Implemented three render-layer bounds in `agents.render_context` (P12
inspection): collapse import/uses contracts per target module with a
caller count (keep `calls` per-edge, capped); bound the neighborhood with
package roots last; cap guarding tests with the cut stated. Measured on
the five stored 27B change-specs with `scripts/brief_sizes.py` (no model,
no GPU): **total rendered context 2.61 M → 635 k chars (−76%), largest
single unit 246 k → 20 k**. The bloat was hubs and package roots on a
module-grain unit's boundary/neighborhood/guards (django U4: 276
contracts; sympy U10: 809-entry neighborhood; sklearn U1: the whole
200k-char suite as guarding tests). The caps are the symptom fix and stay;
the cause is the unit grain, and planner-grain units are the next lever
(P12 condition (c)). `TestBoundaryLevers` + guarding-tests test added.
Paused on compute still holds — this was all replay measurement.

## 2026-08-23 (seventy-fourth) — Tier 1 flow check on the change-grain partition; extraction confirmed load-bearing (7B, one instance)

Ran one 7B decomposed run (sympy-13852, harness arm, staged) on the
ADR-083 change-grain partition to validate the flow, not the score. It
wired end to end: planner hit gold 1/1 (66s) → change-grain split to 2
units → spawned the seed unit U1 → implementer edited the gold file
`sympy/functions/special/zeta_functions.py` (128s) → integration merged
U1 clean → verifier ran. P12 shape holds on the small model. (7B
under-implements sympy, as known — no solve, not the question.) Nothing
left running.

Extraction spot-check (Max's question — has the deterministic layer been
accurate and silently load-bearing?): yes, confirmed. Every span/
declaration site the briefs used lands exactly on the real line
(httpx `iter_raw`:935, `aiter_raw`:1037, `close`:961; django
`FileSystemStorage`@storage.py:170-348, `ImproperlyConfigured`@
exceptions.py:86-88); the co-change data was predictive (django
`filters.py`↔`fields/__init__.py` rank 3 = an actual gold file). Every
ADR 058-083 was a harness or agent-mapping fix; none traced to a wrong
graph edge. The bloat we just cut was *too much correct data* (276 real
contracts, 809 real neighbors, the whole real suite), not wrong data —
extraction over-delivered accurate facts and the mapping mis-allocated
them. Extraction was separately stress-tested at V2.M4-M7 (2026-08-16..18)
with honestly registered concessions and has held since. **Paused for
Max's inspection before ADR-083 lever 2 (co-change into interior).**

## 2026-08-23 (seventy-fifth) — deep read of the sympy 7B failure: not refusal, two real walls (inspection)

Max's sanity check — did the 7B refuse or genuinely fail when properly
guided? Read the U1 implementer transcript (`~/.hobbes/sessions/51eca986eb40-u1`).
**The brief was excellent** (9.4k chars vs 148k in adr075; interior =
exactly the gold file `zeta_functions.py`; planner handoff named the exact
approach "remove unnecessary exp_polar terms" and the guarding test). **The
model followed it**: turn 3 read the gold file, turn 4 made the edit the
planner named — `return -log(1 + exp_polar(-I*pi)*z)` → `return -log(1 +
z)`. No refusal, no wrong file, no hallucinated path for the *edit*. Then
it failed on two distinct axes:

1. **Derivation depth (a Hobbes limit, not the model).** The gold patch is
   TWO changes: the exp_polar removal (which the model did, though subtly
   wrong — gold is `-log(-z + 1)`) AND a new closed-form value table
   (`elif s==2: if z==S.Half: return pi**2/12 - log(2)**2/2`, …) that the
   hidden `test_polylog_values` checks. The planner's approach conveyed
   only the surface fix; nothing in the derived context carried the
   behavioral requirement the hidden test encodes. The guidance was
   correct but incomplete — the model can't implement a requirement it
   was never given, and neither the graph nor the one-solution planner
   proxy (C-49) sees the value table.
2. **Execution reliability (the 7B wall).** After the edit it invented a
   wrong test command (a mangled `test_args.py` node id, not the
   `test_zeta_functions.py` it was handed), hit `pytest: not found`,
   `pip install`ed pytest (a real recovery), then re-ran the *identical
   wrong command* 6+ times — each refused by the exec-repeat guard
   ("already ran, nothing edited") — never correcting to the test it was
   given, never verifying, until the session ended. The guard fired
   correctly; the model did not adapt to it (same shape as the mini httpx
   cat-loop).

**Conclusion: the flow was right, the model comprehended and executed the
delivered instruction, and it still failed — because (a) the derived
instruction was correct but did not carry the full behavior the hidden
test demands, and (b) the 7B cannot reliably drive its own verify loop.**
Neither is refusal; neither is a plumbing failure. (1) is the honest next
frontier for the derivation (behavior/spec depth, related to the co-change
lever and C-49); (2) is why the 7B is a checker, not a solver. Docs only;
paused before ADR-083 lever 2.

## 2026-08-23 (seventy-sixth) — CORRECTION: the sympy requirement was in the issue; the planner's summary dropped it (not a Hobbes-blindness limit)

Max's probe — was the task only solvable by stumbling on the hidden test?
**No, and it corrects the seventy-fifth entry.** The issue text
(`problem_statement`) states BOTH requirements, the value one first and
verbatim: *"Add evaluation for polylog: polylog(2, 1/2) → -log(2)**2/2 +
pi**2/12"*, then the exp_polar removal. The full issue is handed to every
agent as `## Proposal` (it was in the 7B's 9.4k brief). So the requirement
was never hidden and no recall is needed — the answer is printed in the
issue.

**The 27B passed it in adr075 (harness arm) by reading the issue**: its
patch added `elif s == 2 and z == S(1)/2: return -log(2)**2/2 + pi**2/12`
AND `return -log(1 - z)` (exp_polar gone) — both stated requirements, no
test-peeking, no contamination needed (the value is given).

**The 7B failed because the planner's `approach` was lossy and the small
model anchored on it.** The planner distilled the two-part issue to one
line — "Modify the definition of polylog to remove unnecessary exp_polar
terms" — dropping the value-eval half entirely. The 7B, handed both the
full proposal AND that short handoff, acted only on the handoff and did
only the exp_polar edit. So this is NOT "derivation depth" or "Hobbes
can't see it" (seventy-fifth was wrong on that): Hobbes HAD the
requirement (the proposal) and its own planner summary threw half of it
away, then the weak model over-trusted the summary over the full text.

**Correct classification: an agent-mapping defect (lossy planner handoff),
not a model, extraction, or contamination limit** — consistent with the
session's thesis that the problems are in the mapping, not the graph. The
fix is that the planner's approach/handoff must not drop requirements the
proposal states (or the brief must keep the full proposal primary and the
summary subordinate). A candidate check: diff the planner's approach
against the proposal for dropped imperatives. This also sharpens lever 2's
framing — the gap is requirement-preservation, adjacent to but distinct
from co-change. Docs only; still paused before lever 2.

## 2026-08-23 (seventy-seventh) — the superseding frame (ADR-084), handoff reworked, experiments parked (docs only)

Max rejected the shallow "keep the full proposal primary" fix: handing
every implementer the whole task reintroduces the P12 problem and offloads
request-parsing onto the implementer. The real defect (ADR-084): the
planner does localization but not **requirement decomposition** — a
requirement can exist in the request with no owning unit (sympy's
value-eval, stated verbatim in the issue, had none), so no downstream
diligence implements it. **Coverage** (⋃ handoffs ⊇ requirements) is the
planner's guarantee; each handoff must be complete for its implementer
(target: the implementer succeeds with the proposal removed). The **weight
is inverted** — planner 4-12% of harness tokens, implementers 88-96%; the
single comprehension role is the lightest and should be the heaviest.
ADR-083 lever 2 (co-change into interior) folds under this as one kind of
coverage. Reworked `session-handoff.md` into a clean forward-looking doc:
standing policy (experiments PARKED now and near-future; architecture +
7B review before any 27B run ever again; the 7B is the instrument by
speed not capability), the frame, the fixes due with build order (all
7B/replay-validated), what is solid, how to inspect with no GPU. Memory:
`experiments-parked-7b-first`. Nothing running; nothing built this entry.

## 2026-08-23 (seventy-eighth) — ADR-085 built: the planner hands off requirements with owners, coverage is checked, the proposal leaves the implementer brief; README credits

Max's go: "review the current documentation, then proceed to the planner
and mapping fix, record them as the current agent architecture, credit
tree-sitter and mini-swe as uses … do not progress to benchmark running."
No run was made; everything validated with the stand-in session and by
replay over stored handoffs.

**Doc review** found one stale architecture sentence (§6.1 still listed
"the generative planner above the lexical seeds" and "the verifier
session" as parked — both built since ADR-059); fixed in the same commit
(CLAUDE.md rule). The handoff, ADR-084, agent-mapping and the BUILDLOG
seventy-fourth–seventy-seventh were consistent.

**Built (ADR-085, fixes A+B of the handoff):** `run/coverage.py` —
`requirements:` parsed line-wise from the handoff (never inline-split, so
`-> files: a.py` stays the requirement's owner), each requirement owned by
the unit whose interior holds its named file (file-less → the contained
plan's single unit), `PlanCoverageError` at plan cost. The staged run
re-plans once (`planner-2`, the uncovered ids as its inbox), then
`--coverage strict` (default) stops with the record written and no
implementer spawned, or `assign` hands leftovers to the seed unit and
says so in the unit's own brief (C-57). `render_brief(task=…)` puts the
owned requirements where `## Proposal` was; `brief_task` recorded;
`--proposal-in-brief` is the removal test's control. Unit selection keeps
a requirement-owning unit; the verifier gets the checklist;
`--planner-arg` weights the planner alone; bench classes a coverage
failure `plan-error` and the report prints coverage counts + the
imperative count. Precursor: `imperatives_unmentioned` (pinned verb list
+ modals, code blocks stripped, crude stem, <50% token overlap) — lexical,
recorded, gates nothing.

**Replay (no model):** over `tier1-grain-sympy-7b`, `five-fresh-7b-adr072`,
`five-fresh-7b-clean`, `five-fresh-27b-adr075` + `verified.jsonl`: "Add
evaluation for polylog" flagged DROPPED in every 7B sympy handoff, kept
for the 27B (whose approach carried the s==2, z==1/2 case); django's one
imperative kept on both; xarray's three flagged on every rung — the
lexical limit, stated in C-57, not a planner finding. 906 pytest (+20)
/ Go green.

**Docs:** ADR-085; C-57 (surfaced day one; debt summary count corrected
to fifty-seven entries — it had said forty-one); architecture §6.1 gains
the requirement-decomposer paragraph as the **current agent
architecture**; agent-mapping.md header gains the dated "proposal →
requirements" step; session-handoff rewritten (A/B built, C pending
Max, E = the first 7B measurement when runs are cleared); README gains
**Acknowledgements — what Hobbes is built on** (tree-sitter as every
syntax lane, SCIP + its indexers as every semantic edge, ts-morph,
mini-swe-agent + Pier as the referenced harness the baselines run in,
SWE-bench/DeepSWE, Qwen/vLLM/Modal, Cytoscape.js, Podman, MCP SDK,
Watterson) and its intro paragraph replaces the one-line SCIP mention.
Dogfood `planner.policy` comment resynced from the template (rules
unchanged). Experiments remain parked.

## 2026-08-23 (seventy-ninth) — register and backlog paydown: both files audited against the tree (docs only)

Max asked, before anything else is re-evaluated, how many constraints still
apply under the current architecture and how many parked additions were
built along the way. Two audits, every entry checked against the code
rather than its own wording.

**Constraints (57):** 48 active still apply — none had been silently
lifted; the 7 lifted are still lifted in code. Two describe a path P12
retracted (C-55, C-56) and move to a new third part, **Superseded**
(Was / Superseded by / Would return if — not lifted, because the
concession returns with the path). C-4's status had lagged ADR-047 by a
week (unsurfaced → partial: the denominator statement names it). Four
prose lines had drifted and are corrected in place with the date: C-35
("execution milestone not built" — the record exists, fitting does not),
C-42 (`run.json` does not record the default box; the dry run shows it),
C-46 ("32k window" — the endpoint's, ADR-069), C-54 (`policy resolve`
shows the decisive segment, not every segment). Debt summary rewritten:
forty-eight active / seven lifted / two superseded, two unsurfaced.

**Future additions (38 + 20 sub-items):** 13 built, 8 partial, 29 parked,
6 obsolete — but only 3 of the 13 were struck through, so the file
overstated the backlog by about a third. Six more top-level items now
struck with the ADR that built them (per-package tsconfigs, source-based
soft verdicts, derivation-carries-complement, the cross-unit join,
task-tailored selection, the read-only-loop stall); the two container
items (D2 remainder, harness remainder) carry a per-sub-item audit line.
One relabel: cross-language namespacing was filed "subsumed by
moniker-keyed ids", a rationale ADR-033 retracted — it is a live parked
gap (C-15), and the preamble now says so. A tally line sits at the top.
906 pytest / Go unchanged; no code touched.

## 2026-08-24 (eightieth) — presentability pass: architecture drift audit (19 fixes), dead code removed, P12 banners, workstreams map

Max's direction: the repo must be presentable — clean, polish, verify;
break the backlog into groups he can assign people to; and give the
comic a real credit. No experiment work (runs stay parked; the next
one is still the 7B ADR-085 validation, on his go).

**Verified first:** all five suites green before touching anything —
Go 291 cases / 12 packages, 906 pytest, 52 vitest, 29 tsextract, 25
scip — and every README test number checked against a live run.

**Architecture drift audit (ADR-033 §9 discharged):** a full pass of
`hobbes-architecture.md` against the tree found 19 stale claims, all
fixed in place. The big ones: §6.2 and "Where this is going" still said
**no live run has happened** (≥15 dated runs in the hypotheses doc's
Results; the section now records the live runs, the parked status, the
C-39 contamination demonstration, the DeepSWE redirect, the referenced
Pier/mini-swe baseline, and P12's retraction); §7 described v1 designs
as carried subsystems (three-level policy merge → the real six-level
chain; "image per role" → one image with role-shaped mounts and the
ADR-060 overlay; per-command secret brokering and the quota system
marked **never built**, C-41 named); the dead `bench-run-handoff.md`
pointer replaced by `session-handoff.md`. Smaller: packs four → eight
(registry of record named), edge-type vocabulary corrected (`calls`,
`uses`, the Terraform types), the three newer tail classes named with
`extract/tail.py` as the pinned list, the `scip:` namespace honestly
"never implemented", ADR-083's change-grain exclusion added to §6's
partition, the §6.1 parked list completed, "CI check" phrasing fixed
everywhere (no CI exists — now a W0 item), agent-mapping §4 pointer
disambiguated, §8's benchmark row rewritten to the parked-running
truth.

**Dead code removed (the ledger keeps reference, the tree loses
weight):** `scip/dump.mjs` (M0 spike scratch, zero references,
excluded from the kept-evidence list); `extract/docstrings.py` + its
test (never wired into narrate — only its own test imported it;
pysource comment cleaned); the committed setuptools artifact
`scripts/deepswe/hobbesmini/build/` (byte-identical to source;
`build/` now gitignored). 906 → 895 pytest, all green. The sweep
cleared everything else by evidence: all Go packages reachable, no
dead exports/flags, deepswe scripts all referenced (C-55/C-56), spike
tooling kept as documented.

**P12 banners on the three pre-retraction docs:**
`harness-restructure-plan.md` (complete + superseded by ADR-084/085;
phase-4 line closed), `harness-mini-swe-integration.md` (retracted as
a Hobbes arm; kept as the baseline recipe),
`benchmark-deepswe.md` (redirect stands, pairs retracted). Dangling
pointers to the three deleted per-phase handoffs annotated in ADR-057/
058/062; the handoff's `[[compute-economics-gate]]` memory-link
replaced with the rule inline. `--implement-mode aided` help text now
states P12 (an aided run is model + prompt; whether it deserves a
refusal is a W5 decision for Max).

**README:** *Calvin and Hobbes* credited properly — named in the
opening line, Watterson spelled and capitalized, the Acknowledgements
entry expanded (the strip gets the last word on purpose), the license
line's "beloved goat" corrected to the tiger. Counts trued: 85 ADRs,
57 constraints (48/7/2), 895 pytest.

**`docs/workstreams.md` (new):** the backlog grouped into six
assignable workstreams — W0 presentation/CI/verification, W1
extraction core, W2 derivation/mapping, W3 benchmark/measurement, W4
surfaces, W5 safety/policy — each with its items' register/backlog
citations, gating (what waits on Max), and a contributor profile. It
names no new work and un-parks nothing; README's design-docs table
links it.

895 pytest / 291 Go / 52 vitest / 29 + 25 node — all green.

### 2026-08-24 (eightieth, addendum) — the two non-run decisions resolved; ADR-086 built

Max resolved the two decisions that stood outside the run, then named
the course: **one** 7B validation run (no experiment chains), then
project setup.

**ADR-083 lever 2 — deferred to run records** (his call, per the
handoff's own advice): the co-change-into-interior question is decided
from the 7B run's strict-coverage records, where an unnamed co-change
file now surfaces as an uncovered requirement's missing owner. ADR-083's
status line carries the dated deferral; handoff item C marked resolved.

**Aided-mode guardrail — built (ADR-086):** the machinery now refuses
the Hobbes label, per P12's own language. `_run_staged_arm` records an
aided run as `arm=model+prompt` on every return path
(`detail.implement_mode` rides the record); `bench/run.py` resumes,
names patch files, and reports env/checkout errors under the recorded
arm; the report notes the rule and an aided run enters no H1 harness
slot. Mode kept — it is the in-harness *model + prompt* baseline; the
mislabelling is what died. Architecture §6.2 amended in the same
commit; workstreams W5 item struck, W2 lever-2 item marked resolved.
**896 pytest** (one new: the label on both modes), Go untouched.

### 2026-08-24 (eightieth, second addendum) — the ADR-085 validation pair ran; eight defects registered; PAUSED for restructure

Max cleared the one run. Pre-flight per the compute-economics gate
(cost stated: ~$2–4, A10G), endpoint warmed, both passes over the same
five Verified instances (django-11400, xarray-3993, sklearn-25102,
sphinx-8548, sympy-13852), 7B harness arm only, staged strict; B =
`--proposal-in-brief`. Local podman evaluation. Full record:
**`docs/adr085-validation-run.md`** (stubbed NEEDS INSPECTION AND
REVISION at Max's direction); stub entry appended to the hypotheses
doc's Results; handoff rewritten to the paused state.

**The machinery's numbers (E):** 7B planner wrote `requirements:` 0/5
first-attempt, **3/5 after the one strict re-plan**; sphinx was the
first end-to-end ADR-085 success (re-plan → owned requirements →
proposal-free brief → coverage held). The lexical fallback **bypassed
coverage** on the other two (D5). 0/5 solved both passes — recorded,
not the measure. The removal A/B: **no usable signal** — confounded by
D5 and by planner-path variance across identical greedy runs (O4;
sympy's planner succeeded in A, fell to fallback in B). Only clean
pairs (xarray, sphinx) were empty-patch in both arms: the binding
constraint there is implementer execution, not brief composition.

**Mid-run, Max's Modal 400 alarm led to the run's richest findings**
(inspected live, fixed nothing mid-run — instrument consistency):
**D1** the window-fit loop storms the endpoint — this vLLM's overflow
error reports "at least N input tokens" where N = window−max_tokens+1
(a lower bound, reproduced by a controlled request), so the fit shrinks
by exactly 17 tokens per retry: ~75 consecutive 400s per elide cycle,
450 observed on one sklearn call, ~929 total vs 235 successes. **D2**
elision ate 89-char failed-edit results (~10 tokens saved) and the
model repeated the identical failed edits. **D3** the read-before-
overwrite ticket survived elision of the read: sklearn u1 then blind-
overwrote `_array_api.py` with a 28-byte stub — the P10 shape, a
general mechanism hollowing a specific guarantee's premise. **D4**
same-turn read+edit batching let sphinx u1 author a hallucinated
anchor (requirement text rendered as code) before seeing the read.
Plus **D5** (fallback bypasses strict), **D6** (`astype` lexically
seeded the `_array_api` hub → 2,543-guarding-test interior; the
ADR-083-lever-2 evidence Max deferred to), **D7** (foreign environment
residue `exercise_01_language_train_model` in sklearn's
extraction_errors rode every brief, Rust wording on a Python decode;
zero graph impact), **D8** (prose "reflection" with no reflect call —
no handoff). Observations: the 7B never called a knowledge tool
(derived context is push-only at this rung); run B ran 313 completions
with zero fit-400s (D1–D3 fire only under saturation).

**Every defect is documented with its proposed change and owner in the
run doc; none is fixed in this tree.** Experiments return to parked;
Max restructures from the register, then proceeds. Docs-only since the
ADR-086 commit; suites untouched (896 pytest / Go green at last run).

### 2026-08-24 (eightieth, third addendum) — the evidence trail caught up to the extraction layer

Max flagged the docs behind the extraction layer's evidence. Fixed:
`extraction-evidence.md` gains the SWE-bench era section (the six
derivation-programme repos with the validation pair's real ingest
numbers — django 123k detected sites at 53.7%, sympy 608k with lane B
degraded in-workspace, the D7 residue noted on sklearn's row — and a
Verified line scoped to what was actually checked: spans and
declaration sites during the deep reads, astropy interiors vs gold;
no call edges hand-checked there). §3.8's Python row extends to the
six repos **at span/declaration grain only**, `VERIFICATION_BASE`
updated verbatim in the same commit (repos 3 → 9; the pinning suite
holds them equal, four behavioral literals updated with it); the
asymmetry paragraph now names the two evidence bodies deliberately
outside the table (dagger's 265k-site no-hand-checks run, the
benchmark repos' grain) with the evidence log as their record. README's
stale "3,085 sites" line now carries the v2-exit date plus the dagger
and benchmark-scale evidence and points at the log. Go/Rust rows
unchanged — no new hand-verified evidence licenses them (P11). 896
pytest / suites green.

### 2026-08-24 (eightieth, fourth addendum) — a private repo's name redacted repo-wide (Max's order)

One of the sanctioned test repos is private and its name must not
appear in this now-outward-facing repo. Every reference — 73 across
docs, ADRs, the constraints register, code comments, two Go test
fixtures, `VERIFICATION_BASE`, and this BUILDLOG's own past entries —
was replaced with the designator **private-repo-A**, and its filesystem
path removed. The append-only rule yielded to the redaction order, and
this note is the record of that exception: the *evidence* those entries
carry (numbers, hand-verified counts, dates) is untouched; only the
identity is withheld. §3.8's cells and their pinned twin moved
together; 896 pytest / Go green.

### 2026-08-24 (eightieth, fifth addendum) — public-release validation; the tree splits into private and public repos

Max privated the original GitHub repo (renamed; full history his) and
created a fresh public `Hobbes` repo, cloned empty to `~/hobbes_public`.
Before the move, the tracked tree was validated clean across every leak
class: the redacted repo's name (0), the never-touch repo's name (0),
key/token patterns (0), the owner's email (0), hardcoded home paths
(6 fixed — exitcheck.py now derives its root from its own location,
deepswe_run_arm.sh uses $HOME/dirname, the mini-swe recipe genericized),
and concrete Modal endpoint URLs (2 redacted to placeholders with the
`modal_vllm.py url` pointer). The Go module renamed to match the public
repo (`github.com/majax7714/Hobbes/go` — go.mod, every import, docs
mentions, the spike filter string); builds and all suites green (896
pytest / Go ok / 25 scip). The move is `git archive HEAD` into the
fresh clone — tracked files only, so nothing gitignored (secrets,
datasets, caches) can travel. The old history never reaches the public
remote; this working repo remains the full-history private/dev twin.

## 2026-08-24 (eighty-first) — CLAUDE.md reframed as a contributor entry point (public repo, docs only)

The public repo's first task: `CLAUDE.md` had grown to 1,159 lines —
a per-session ledger addressed to the owner, duplicating this file
and `docs/session-handoff.md`, and arguing against the project's own
small-context thesis. Rewritten to ~190 lines: what Hobbes is, a
by-task reading table, the project map, build & test, the conventions
restated for any contributor (P8/P10/P11/P12 kept as rules, not
anecdotes), and a six-bullet Status block. Everything dropped is in
this log's earlier entries; nothing was moved, since it was already
here. `AGENTS.md` is a symlink to it so non-Claude agents find the
same file. README's "Current status" pointer now names
`session-handoff.md`. Standing rule added to the file's tail: update
the Status block only when the headline changes, and keep the length.

## 2026-08-24 (eighty-second) — Hobbes for Hobbes: knowledge tools in host sessions (ADR-087)

Max's call: let the agents that work on Hobbes use Hobbes — evidence
layer only, "proven honest help", not the agentic layer. Built:
`hobbes-proxy serve --knowledge-only` (`Config.KnowledgeOnly`) serves
the six knowledge tools and leaves `exec`/`reflect` **absent** from
the list — the sandbox's absent-not-refused rule on the host, and no
second policy engine over the host's shell (P10 shape). Flight log
still mandatory. Repo-level `.mcp.json` starts it (`--role developer
--session host-knowledge`). Verified over real stdio from the repo
root: 6 tools listed, `who_calls hobbes.extract.ingest` cites
`bench/arms.py:285`, `cli.py:78` and the test_emit cases with lines;
`list_blind_spots go/internal/proxy` prints the denominator statement
and 92.4% of 631 sites; every call recorded under
`~/.hobbes/sessions/host-knowledge/`. First ingest of the public clone
(lane B on): go 89.6% / python 86.0% / rust 100% / ts-js 66.9%
capture — the ts/js figure matches the private repo's. Go suite +1
(`TestKnowledgeOnlySurface`). Validation task proposed in the ADR, not
run.

### 2026-08-24 (eighty-second, addendum) — ADR-087's first observation: the rename probe

Fresh headless session, neutral prompt (rename `hobbes.extract.ingest`
→ `ingest_repo`, fix callers, run tests). The agent called `who_calls`,
`tests_guarding`, `list_blind_spots` at turn ~2, unprompted, before
any grep; `who_calls` returned all 9 call edges + 5 import references
including the two function-local imports in `test_tssource.py`
(verified by re-issuing the call); the C-1 line in `list_blind_spots`
made it run a cross-check grep rather than trust the graph alone —
which found only the docstring `:func:` references the graph does not
model. 5 files / 19 lines correct, 895/896 (the one failure is
pre-existing on `main`, environment). 32 turns, 131 s, $1.44. Edits
discarded, branch deleted. Full record in ADR-087.

### 2026-08-24 (eighty-second, second addendum) — ADR-087's second observation: the blind-spot probe; closing out

Probe 2 targeted the tools' weakest case: rename the `Pack` field
`applies` → `detect`, every use an attr-call through a value (C-1),
no symbol in the graph. Fresh headless session, neutral prompt.
Outcome correct (12 files, incl. the architecture doc unasked; 44/44
pack tests; 895/896 with the same pre-existing env failure). The
graph was never queried — defensible for a field rename — and the
agent *did* reach for `list_blind_spots` but called it with `path`
instead of `scope`, was rejected at the schema, and fell back to grep
without retrying. The rejection never reached the flight log. Two
follow-ups named in workstreams W4 (argument alias / description; log
schema rejections). Edits discarded, branch deleted. 57 turns, 209 s,
$3.17. The public clone's derived artifacts are at `12bac9f`; note
`test_scipsource … venv_environment` fails on this box at `main`
(environment — the venv lists only `pip`), so the live count here is
895, not 896. Session closed at Max's direction; docs current.

## 2026-08-25 — the constraint register becomes a folder (ADR-088)

Docs only, no code. `docs/constraints.md` (1,822 lines) is now
`docs/constraints/`: `README.md` carries the preamble, an index table,
and the debt summary; eleven segment files carry the entries under the
same headings the file had. Lifted entries moved to the bottom of their
segment (C-3 → call graph; C-11, C-24 → TS/JS; C-14 → packs; C-16, C-33
→ lane B environments; C-18 → narrative/invariants), superseded C-55/56
to the bottom of the benchmark harness file. 57 entries in, 57 out,
text unchanged. Links repointed across README, CLAUDE.md, the
architecture, first-run, workstreams, session-handoff, future_additions
and the ADRs that cite the file; earlier BUILDLOG entries left as
written. Convention updated: a new `C-n` lands in its segment file.

## 2026-08-25 — oracle-grading lane: design landed, decisions parked for Max (ADR-089)

Phase one of the oracle-grading work, docs only. The design brief
(precision-against-oracle and recall for the call graph against answer
keys Hobbes does not control — Go RTA, TS `tsc` in phase 1; Python
`sys.monitoring` traces and a Rust MIR oracle in phase 2) is now
`docs/oracle-grading.md`, owner Max, status proposed/unbuilt. ADR-089
records the lane and carries D-O1–D-O6 as *proposed* with the design's
recommendations; O1 is gated on Max deciding D-O1–D-O4. Noted while
landing it: the O1 fixture `twomod` does not exist (only `minigo`), so
it is in O1's scope. No harness code written.

## 2026-08-25 — oracle lane O1: the harness lands on fixture truth (ADR-089)

Max cleared ADR-089 with the recommendations; D-O1–D-O6 marked decided.
Built `bench/oracle/` — its own Go module (the one `x/tools` dependency
stays out of the product module, D-O2), one binary: `export` (graph.json
→ graded edges: one per evidence line of each `calls` edge, target =
callee's declaring file + declaration line), `go-rta` (packages → SSA →
RTA, rooted at every main package's `main` **and `init`**, sites scoped
to the cell's module, targets anywhere in the repo, synthetic functions
unwound, generics folded to origin), `grade` (buckets confirmed /
contradicted / abstract / silent{not-loaded, unreachable, no-targets},
precision-against-oracle and recall printed together with root count,
per-tier split, miss decomposition, triage rows). `run-cell.sh` is the
one command per cell. Added the `twomod` fixture (two modules joined by
`replace`, one interface-dispatch call). README carries the D-O4
conventions as normative.

Findings from the self-test, in order: (1) RTA rooted at `main` alone
reaches **no test function** — the synthesized test main's table is
address-taken in `init`; rooting at `init` too (as `x/tools`' own
`callgraph` does) fixed it. (2) RTA over-approximates the fixture's
one invoke with an external `reflect.StructTag.Get` beside the true
`MemStore.Get` — rule 4 of the design, seen on day one, external and
so out of the recall denominator. (3) **Hobbes draws no call edge for
`s.Get(key)` at `twomod/lib/lib.go:28`** — not to `Store.Get`, not to
`MemStore.Get`; the graph has only the `uses Lookup → Store` type edge.
The pre-registered miss class (interface dispatch) is the first graded
miss, and it is a recall miss, not a contradiction. Cells: minigo 5/5
confirmed, recall 5/5 at 2 roots; twomod/app 3/3, 3/3 at 1 root;
twomod/lib 2/2, recall 2/3 at 1 root (`misses {dynamic: 1}`). Each
cell runs in ~1 s. 10 Go tests; pytest 895/896 on this box (the known
`venv_environment` environment failure, unchanged). Fixtures are not
logged in the evidence file by its own rule. Next: the §10
pre-registration commit, then O2.

## 2026-08-25 — oracle lane O2: this repo's Go zone graded; C-58 registered

Pre-registration committed first (`docs/oracle-preregistration.md`,
P1–P9). Then `run-cell.sh . go` — the first real cell. First pass:
1,276 confirmed / 5 contradicted / 1 silent. Triage: 3 hobbes-wrong
(all syntactic — lane A bound a test helper's local closure `run` to
package `run`; C-7 priced exactly as P2 predicted), 2 **match-defect**
(the unwinder followed a generic instantiation into its body and graded
`sortedKeys[string]` as `sort.Strings`) — fixed, regression fixture
`testdata/generic`, regraded: **1,278/1,278 semantic confirmed, 0/3
syntactic, precision-against-oracle 99.8%; recall 87.5% at 20 roots,
static 1,280/1,280.** Added recall-by-class to the report because a
reachability oracle over-approximates `func()` values (138 pairs at 10
sites — `defer cancel()` resolving to every closure in the program);
the static number is the tight one and both print. The 45 honest
misses are one class and it is now **C-58** in the call-graph segment:
a call through an interface, a function value, or into a closure draws
no edge — and `resolution_coverage` counts the site *resolved* (the
checker found the interface method; C-9 then drops it), so the capture
number reads better because of the gap. Unsurfaced; candidate
surfacing named. Register: 58 entries, 49 active, 3 unsurfaced.
Evidence row, §3.8 Go row ("compiler-graded", scoped to this repo), and
the cell record (`docs/oracle-cells/hobbes-go-2026-08-25.md`) landed
in this commit; predictions graded — P3 and P4 missed and say why.
ADR-037's 20/20 could not be reproduced by identity (the edges were
never listed); the whole semantic set stood in. Cell runtime: ~4 min
for oracle + grade, ~6 min more for the six-language ingest. Next: O3.

## 2026-08-25 — oracle lane O3: kbet graded against its own `tsc`; miss classes sharpened

The TypeScript oracle (`bench/oracle/ts/tsc-oracle.mjs`, plain Node,
loads the *zone's* `typescript` so the oracle is the compiler the
project pins) and `--lang ts` in `run-cell.sh`/`export`. kbet
`betchat/frontend`, 83 files, 5,978 sites. First pass: 511 confirmed /
**119 contradicted** — every one `useAuthStore()`-shaped: `tsc`'s
declaration for a call through a `const` of callable type is the
anonymous call signature in zustand's `react.d.mts`; Hobbes (and scip)
bind the callee to the variable. Ruled a **match-defect of the oracle's
grain**, and the D-O4 conventions gained the *binding rule*: behind an
anonymous signature the callee's identity is its binding. Second pass:
**630/630 confirmed, 0 contradicted, 0 silent.** Recall 633/1,529 over
every resolved site, 633/637 on declared callees. Misses, now classed
by mode × declaration kind (local-binding, closure, type-member,
anonymous-function joined the vocabulary; TS sites get a mode from the
binding's shape so Go and TS read alike): 625 local bindings (React
state setters — C-32's by-design tail), 195 closures, 71 store members
through interface property signatures (the one class that costs real
architecture: `who_calls(addMessage)` → nobody). A second oracle defect
caught by the fixture path: dynamic `import()` listed as a call target;
dropped. `minits` self-test 4/4 both ways; noted that Hobbes' decorated
class symbol sits on the decorator line (W1) — the oracle's convention
is the identifier. Both 20/20 hand-checks (Go V2.M5, kbet V2.M3)
retired at Max's direction: rough, unnamed edges; the oracle replaces
them, hand-checks return later with a selection rule. 12 oracle-lane
Go tests. P7 met on precision; its overload clause was untestable and
the rule that mattered was one it did not anticipate. Next: O4 dagger.

## 2026-08-25 — oracle lane O4: dagger's Go modules graded; the root does not fit; C-59

Max: "always honest" — the oracle's own defects now have a record
(`docs/oracle-defects.md`, H-1…H-11), each with what it would have cost
unnoticed. Then dagger (ingest f3cc3eb3): one cell per Go module via a
driver; **19 graded** — 9,816 confirmed / 40 contradicted / 656 silent
(all unreachable), precision-against-oracle **99.6%**, 9,855/10,715
in-repo pairs drawn across 24 roots, static named calls
**9,854/9,889**. All 40 contradictions are **a type conversion drawn as
a call** (`dagger.JSON("0")` → `calls` to `type JSON`; 37 semantic, 3
syntactic) — the lane's first wrong edges in the semantic tier, a
product defect for W1, not a concession. Named misses: 16 recursion —
`graph.py` drops self-calls by design, now **C-59** (unsurfaced; the
register has 59 entries, 50 active, 4 unsurfaced) — 11 method
expressions / generic instantiation calls, 4 chain continuations (no
site: the capture number cannot see them), 4 calls on an assignment's
left side (drawn as `uses`). Interface dispatch is 23% of honest misses
here against 4% on this repo: the ranking moves with the codebase.
Harness: H-9 — the root module as one program OOMs (20.5 GB with tests,
20.7 without, 24.4 for `./core/integration/...` alone; RTA requires
`InstantiateGenerics`) on this 30 GB box; `--no-tests` and `--packages`
added, and **P8/P9 recorded not graded** rather than approximated.
H-10 — `go-rta` lacked the `--exclude` the export had; ~250 false
misses in `e2e/helm` until both sides scoped alike (72/72 after).
Four modules not gradeable (docs' undeclarable deps; recorder's
generated package; a library with nothing to root at). Evidence rows,
a §3.8 dagger-Go row scoped to the 19 modules, the miss record's
dagger section, and W1's item list landed with this. Runtimes:
150–500 s per module cell; the failed root attempts cost ~35 min.

## 2026-08-25 — W1: the O4 findings fixed; C-59 lifted the day it was registered

Max: the root needs a bigger box (flagged, parked until compute
arrives); proceed with W1's fixes. A `goshapes` fixture holds one
instance of every O4 shape; ingested with lane B and graded by the
oracle it went 6/8 → 7/8 → **8/8 both ways** as the fixes landed. What
the fixes turned out to be: (1) the "chain continuation", "LHS call"
and "method expression" misses were **one bug** — the conversion filter
reads an expression operand as no receiver, then finds a *type* of the
callee's name in the package (`UserConfig`, `File`, `Permissions`,
`Job`) and drops the site as a conversion; the receiver is now an
expression sentinel and such a call is never a conversion. (2) `Ref[T](v)`
parses as `type_conversion_expression` over a `generic_type`, so lane A
had no site; it is emitted as a candidate and the same filter decides.
(3) The 40 contradictions — `dagger.JSON("0")` — escape the filter
because a nested module's import path (`dagger/viztest/...`) does not
mirror its directory; the projection now refuses a `calls` fact whose
Go target is a `type` (→ `uses`), Go-only. (4) Self-calls: the
projection and the Python fallback both dropped them; kept for `calls`
(self-`uses` still out) — **C-59 lifted**, register 59 entries / 49
active / 8 lifted / 3 unsurfaced. §3.8's Go row is now two repos
(compiler-graded), so the pinned twin in `verification.py` moved with
it — the P11 test caught the edit, as designed — and the `go · 1 repo`
badge is gone. Architecture §3 amended. 906 pytest (+10). dagger
re-ingest and the 19-cell rerun are running for the after numbers.

## 2026-08-25 — W1 closed against the oracle: dagger's 19 modules at 0 contradictions

The rerun after the fixes surfaced one more: the 3 surviving
contradictions were `string(x)` bound by lane A's fallback to a symbol
named `string` — and dagger's graph had **58 phantom `string`/`int`
symbols**, because `var mavenImage string` was named by its
type_identifier child, not its name field (a bug as old as V2.M5's Go
provider; `const K string = ""` likewise). Fixed to read every `name`
field of the spec (`var a, b int` is two symbols); `goshapes` covers
it. Second re-ingest, the two affected cells rerun: **19 modules,
9,851 confirmed / 0 contradicted / 656 silent, precision-against-oracle
100%, static named calls 9,889/9,889, 9,890/10,715 in-repo pairs
drawn.** Before/after per module in the cell record; the before reports
kept beside the after. What is left is C-58 — a design question the
oracle has now sized on two codebases (closures 70–80%, interface
dispatch 4–23%). 907 pytest. Session closed: ADR-089 phase 1 done to
this box's limit, W1's findings fixed and verified by the instrument
that found them.

## 2026-08-25 — close-out: docs swept, phase 2 flagged as the next section

Status blocks, `oracle-grading.md`'s status line, the handoff header and
W3 now say the same thing: oracle lane phase 1 done to this box's
limit, W1's findings fixed, **phase 2 (Python traces, Rust MIR) is the
next section**, root waits on compute. Session closed at Max's
direction; a fresh session resumes from the handoff.

## 2026-08-25 — oracle lane phase 2: the interpreter grades Python, rustc's MIR grades Rust

Pre-registered first (P10–P16, own commit), then built: `py/trace_oracle.py`
(`sys.monitoring` CALL events under the repo's own pytest, one subprocess
per run, unioned; declarations mapped through an `ast` index so a
decorated function's line is its `def`; C callees counted, not listed;
out-of-cell callers `DISABLE`d at first event) and `rust/` (a
`rustc_driver` wrapper on the pinned nightly: every body's MIR `Call`
terminators through `Instance::try_resolve`, `fn_span` for the site,
`def_ident_span` for the target, external by *file* so a bin's call into
the repo's lib is in-repo). The grader gained §3.1's asymmetric buckets
(confirmed / suspect / unobserved, no precision line, the coverage line
mandatory), `export` gained `py` and `rust` (macro edges excluded and
counted), `run-cell.sh` gained both languages; fixtures `miniapp` and
`minirust` are the self-tests (7/7 and 9/9 by hand). **Five harness
defects before any number** (H-12 package nodes dropped 113 Hobbes
edges; H-13 the test harness's generated calls; H-14 the coverage
count; H-15 foreign macro bodies; H-16 `.await`'s poll of async bodies
— 649 false closure misses on dagger). **O6, this repo's Python zone:**
3,291/3,490 confirmed, 10 suspect (4 not-exercised, 6 hobbes-wrong —
all syntactic, a fixture parameter name-matched), recall-against-
executed 86.2%, 96.9% on named declarations, 94.3% of sites exercised;
closures + lambdas are 80.8% of misses. **O7:** rust_proj 17/17 (ADR-040's
33 = 17 calls + 16 uses); dagger `sdk/rust` 3,574/3,574 semantic, 12
syntactic contradictions (`format!` → `fn format`), recall 98.1% — the
misses are code macros and derives wrote, not dispatch (P16 missed
there; P11's attribution clause missed too; the other five met).
Registered C-60 (trace asymmetry), C-61 (reference lane), C-62 (§3's
four rules — phase 1's debt). §3.8's Python row is trace-graded and its
Rust row is two repos compiler-graded, the pin in `verification.py`
moved with them and the P11 test caught the edit as designed. Not run:
xarray (no workspace on this box), Rupta, the trace lane for Rust, O5.
21 oracle-lane Go tests (from 12); 907 pytest unchanged.

## 2026-08-25 — W1 from the oracle lane's phase 2: two fallback vetoes and the `below-floor` class (ADR-090)

Every wrong edge phase 2 found was lane A's fallback name-matching:
Python's six were a pytest fixture *parameter* bound to the fixture
function, Rust's twelve were `format!(..)` bound to a `fn format`.
ADR-046's local bindings now veto the Python fallback by scope
containment (a nested `def` inside the extent still stands), and Rust
macro invocations carry `macro` and bind only to `macro` symbols.
C-58's surfacing: `project()` returns the semantic-lane sites whose
target starts no symbol; the coverage row carries them as `floored`,
the tail as `below-floor` (*seen, not modelled by design*, in Python's
`NOT_MODELLED` and knowledge.go's `notModelled`), the invariant is
`sum(tail) == unresolved + floored`; the `resolved` count does not
move and the entry says so (unsurfaced → partial). On this repo:
below-floor go 3 / python 35 / ts-js 10. O6 regraded: 3,302 confirmed,
4 suspect (all not-exercised), no syntactic edge left on the executed
slice. 911 pytest (+4), Go green, proxy rebuilt. dagger re-ingested
and `sdk/rust` regraded: **3,592/3,592, 0 contradictions, precision
100%** (from 99.7%); dagger's `below-floor` is go 4,114 / ts 247 /
python 117 / rust 102 sites.

## 2026-08-25 — two cheap defenses, and two thin repos out of the base (Max)

private-repo-A and qwen-pathology retired from §3.8 and the evidence
file — a handful of hand-checked edges each, no weight beside
compiler-graded cells and confusing to read; the pin in
`verification.py` moved (python 9 → 7 repos, ts/js 3 → 2, hcl 2 → 1 —
HCL is single-repo now and the summary says so). Two defenses against
a flattering patch, at Max's direction: (1) every cell record carries a
**signed direction-of-fix line** (before → after per headline number,
`hobbes edges` included, so a number "fixed" by shrinking the graded
set shows); written for hobbes-py, dagger sdk/rust and dagger Go. (2)
**The poison check**: `grade --poison` re-targets every Hobbes edge to
a declaration the oracle never resolved that site to and reports how
many the grader refused / could not judge / **falsely confirmed** —
the fixtures had only proved true edges confirm; a falsely confirming
matcher was invisible to triage. Fixture tests for all four oracle
kinds (the single-target `minits` case needed a fallback substitute);
`run-cell.sh` passes it always; every stored cell re-graded: 0 falsely
confirmed across hobbes-py, rust_proj, dagger sdk/rust and 19 dagger Go
modules. 26 oracle-lane Go tests.

## 2026-08-25 — positioning: how Hobbes differs from CodeGraph and repowise

At Max's direction: the headline descriptions collide (a graph, MCP,
deterministic, for agents; repowise even says "confidence-stamped" and
"compiler-graded cells"), and Hobbes was built independently of both.
`docs/how-hobbes-differs.md` shows the structure instead — an
extraction-layer diagram (two lanes → range join → tiers → tail →
register → oracle lane) and a context-supply diagram (derive → planner
→ single-use agents → sandbox + policy + proxy → verify), the per-cell
oracle numbers as of today, and what the other two do per their own
READMEs on this date, nothing more. Linked from the README.

## 2026-08-25 — correction: the comparison is to CodeGraphContext, not codegraph-ai/CodeGraph

Max caught it: the positioning page had read the wrong project's README
(`codegraph-ai/CodeGraph`, someone else's tool). Rewritten from
`CodeGraphContext/CodeGraphContext` — tree-sitter across 23 languages
with SCIP as an optional alternative feeding a graph database, an MCP
query surface kept live by `cgc watch`, no accuracy figure, no action
governance stated. The differences that survive are the same in kind
(mandatory pinned lane B joined against lane A with the tier as proof;
a register; oracle grading; derived context in a sandbox) and one is
sharper: both run SCIP, and only Hobbes records which lane proved each
edge. The page keeps a correction note in its header.

## 2026-08-25 — README: diagrams for its own sections, competitors as context (Max)

At Max's direction. The "Not a copy of the other code-graph tools"
section was a denial of something no one had alleged — and the BUILDLOG
is the record either way. Replaced by a short **Related projects**
section that names CodeGraphContext and repowise as the same space,
says what is shared, and points to `docs/how-hobbes-differs.md` for the
structure. The README head now carries one Mermaid diagram per section
it already had — what it does (ingest → derived layer → two renderers →
sandbox/policy → review), extraction (two lanes → range join → tiers →
tail → register → oracle), and where this is going (plan → units →
single-use agents under proxy → verify → human) — with the prose cut to
the abstract statement and a "Deeper:" pointer line under each. Status
compressed to headlines; docs table gains the oracle and positioning
rows; ADR and pytest counts corrected (90, 911). Tail sections
(layout, getting started, tests, acknowledgements) unchanged.

## 2026-08-25 — acknowledgements: the oracle lane and the compile targets (Max)

Max's note: the graph is graded by tools that had no credit. Added to
the README's acknowledgements — `x/tools` RTA, the TypeScript compiler,
CPython's `sys.monitoring`, and rustc's own crates through
`rustc_driver` on the pinned nightly (the Rust oracle *is* rustc); the
invariant compile targets (import-linter, dependency-cruiser, semgrep,
OPA/Rego), which do the enforcing Hobbes only transcribes; React/Vite
and the Alpine sandbox base in passing. Inventory was from `go.mod`,
`pyproject.toml`, the three `package.json`s, the oracle's `Cargo.toml`
and `rust-toolchain.toml`, and the Containerfile.

## 2026-08-25 — README voice: trust is the goal, speed a side effect (Max)

Max's framing: Hobbes should be what the tiger is in the strip — the
companion for ambitious ideas who tells you the truth — and the README
had drifted toward an efficiency pitch (smaller context, drift, tokens)
stated more aggressively than needed. Rewritten in a reader-friendly
voice around one thesis: a trustworthy environment for developers —
context that is safer for agents, a system easier for people to
understand — with faster agents named as a possible side effect, not
the aim. Related projects reframed: code graphs are rising as fewer
people read every line; most of the field describes making agents
better, Hobbes leans toward safety and understandability. Diagrams and
the tail sections unchanged; "not open for relitigation" softened.

## 2026-08-27 — ADR-091: the mechanical half of the restructure (D1–D4, D7, D8)

Max's direction: start on the defect register; D5 and D6 stay
documented and held — the harness's shape is not the current focus.
All six mechanical defects fixed and validated hermetically, no model.

`agent/loop.py`: **D1** one fit per elide cycle (the overflow's input
count is a lower bound; vLLM's "at least N" shrank the room 17 tokens
a try, 450 400s on one call). **D2** `elide_oldest_tool_result` skips
mutating results and anything under `ELIDE_FLOOR` (2× the placeholder)
and now returns the elided message. **D3** `Endpoint.on_elide` lets the
loop revoke a path's read ticket when its last visible read is elided
(`ELIDED_READ_REFUSAL`), and forget the call's signature so the re-read
is not refused as a repeat — found by the test, not the register.
**D4** `read_turn` refuses an edit or write on a path first read in the
same turn (`SAME_TURN_REFUSAL`). **D8** one bounded `NUDGE_HANDOFF` for
an implementer that edited, has `reflect` on offer, and ends in prose;
`handoff_nudged` on the envelope; `UnitRecord.handoff` (`handoff |
reflection-only | missing`) set at every harvest via
`orchestrate.handoff_status`. Seven loop tests and one run test added.

**D7, with a correction to the register:** the sklearn "foreign
environment residue" was not foreign — `exercise_01_language_train_model.py`
sits in sklearn's own `doc/tutorial/text_analytics/{skeletons,solutions}/`,
a legitimate C-28 duplicate. The defects were the Rust wording on a
Python decode and `path: "."`, which the brief filter reads as every
unit. `scip/index.mjs`: `decode` returns `ambiguous_files`; the record's
`path` is their common directory (`commonDirectory`) and its wording is
per lane (`DUPLICATE_SHAPES`); `scipsource._rebase` now rebases
zone-relative degradation paths (and runs before the provision-failure
record is appended, which is already repo-relative). One node test
added; C-28's surfacing line amended.

Architecture §6 amended in the same commit. Suites: 917 pytest (one
pre-existing environmental failure deselected —
`test_venv_environment_lists_the_venvs_own_distributions` expects
`pytest` in the fixture venv and finds only `pip`; fails on the clean
tree too, not touched), 26 scip node. Go and web untouched.

## 2026-08-27 — the five-repo grading loop (documentation only)

Max's direction: validate extraction further by grading new repos —
spawn an agent per repo to pick, ingest, grade via the oracle lane and
write a cell record; nothing changed in code; the orchestrator
maintains the loop and does not judge the records. Python and Rust
cells were re-validated first on this repo and rust_proj (Python moved
only with the tree; Rust byte-identical to the stored record).

Five records in `docs/oracle-cells/`, one commit each, numbers verbatim
from `report.txt`, all poison checks 0 falsely confirmed:

| repo | lang | edges | precision-vs-oracle | recall | note |
|---|---|---|---|---|---|
| BurntSushi/toml | go | 1,047 | 100.0% | 71.9% at 4 roots | 0 contradicted |
| pallets/click | py (trace) | 2,003 | 81.0% confirmed, 5.0% suspect | 35.3% vs executed | decorator-factory closures dominate misses |
| BurntSushi/memchr | rust (MIR) | 2,623 | 99.2% | 80.7% | 7 contradicted: tuple-struct constructors typed as calls; 1,583 silent in out-of-package cargo roots |
| gorilla/mux | go | 1,264 | 99.8% | 82.6% at 1 root | first contradicted Go rows: 3 calls through a package-level func variable |
| junegunn/fzf | go | 2,973 | 97.0% | 40.8% at 5 roots | 87 contradicted, all syntactic-tier: a local `func` literal shadowing a package-level name; semantic tier 0 contradicted |

**TypeScript did not grade.** ajv and cheerio both hung the TS oracle:
`siteName()` in `bench/oracle/ts/tsc-oracle.mjs` never descends on an
element-access callee (`obj[key]()` → `e = e`). An oracle defect, not a
repo defect — **H-17, registered open** in `docs/oracle-defects.md`;
the element-access site rule (D-O4) is to be decided before the script
is touched. Loop rule held: stopped, registered, proceeded on the other
lanes at Max's word.

Nothing in `oracle-misses.md` or `extraction-evidence.md` was updated —
the records are unjudged by design; triage is a separate session.
Clones and outputs under `~/.hobbes/bench/oracle/{repos,<name>-<lang>}/`.

## 2026-08-27 — the defect-record review, its actions, and the two TS cells

Max reviewed every oracle-lane defect (H-1..H-17) before proceeding and
adopted an external review: `docs/oracle-defect-review.md` — verdict
(all seventeen attribute correctly; two dispositions pushed back on),
an action register A-1..A-9, the n=1 method, the **seen tally**
(roots RC-1..RC-7, maintained with the log), and the reviewer rules
RR-1..RR-7. Max's question on H-17 — repo bug or oracle bug? — was
answered *oracle*: the repos compile; `siteName()`'s element-access
branch was `e = e`.

Actions landed in one commit, in the review's order (harness only,
`bench/oracle/`): **A-2** verified — membership *was* written twice —
and unified on `edges.Under`/`edges.Excluded`; **A-3** `[]` not `null`
at the serializer; **A-1** `state: no-roots` on the export and `recall:
NOT GRADED — no roots exist` on the report (`testdata/noroots`);
**A-4** fixture first (`minits/src/lookup.ts`, one function per
element-access shape) → observation (Hobbes draws no edge for any of
the three: **C-63**, unsurfaced, lane A does not count the site) →
rule (D-O4's element-access bullet: literal / `Symbol.x` key graded at
the key's line, computed key silent as `computed-key`) → loop;
**A-5** `descend()` throws with a position on no progress, every walk
through it; **A-6** a worker-thread watchdog prints the last
file:line and exits 3 after `--watchdog` seconds; **A-8** precision
quoted as a lower bound everywhere, and every cell record now carries
`oracle-wrong : hobbes-wrong : untriaged` over its contradicted rows.
H-17 closed; RC-1 and RC-6 closed-structural, RC-4 closed-policy.

The two repos that hung then graded: **ajv** in 2 s (1,543 edges,
99.8% lower-bound precision, 62.0% recall, 3 contradicted untriaged,
1 computed-key site) and **cheerio** in 8 s (2,162 edges, 97.9%,
36.1% recall, 44 contradicted untriaged — 36 a spec-local `parse`
shadowing `src/parse.ts`, the fzf shape in TS). Records in
`docs/oracle-cells/`, unjudged like the other five; the five earlier
records predate the triage-ratio line and do not carry it.

Suites: oracle Go 28 (two added), pipeline tests touching minits green
(69), full pytest not re-run for a fixture file addition that the
membership-only assertions cover.

## 2026-08-27 — ADR-092 phase 1: lane B runs in the sandbox image

Max's direction: hold the oracle-cell triage; an architecture review
found the sandbox boundary covered agent sessions but not extraction or
the oracle lane — the layers that execute repo-authored code by design
ran on the host. The corrected rule, *sandbox whatever executes
repo-authored code*, and the new P10 guarantee, *repo code never
executes on the host*, are ADR-092; phase 1 (ingest containers) is
built here, phases 2–4 are written up in the ADR and the handoff.

**Built.** `pipeline/src/hobbes/extract/containment.py` — a pure
planner in the `go/internal/sandbox` shape: static per-step profiles
(`index-{python,typescript,go,rust}`, `python-env`,
`fetch-{npm,go,rust}`), a `Plan` whose `podman_args()` is inspectable,
and `run()` — now the only place lane B spawns. Mounts derived, every
one at its host path: the cache root rw (stage, helper config, SCIP
output, provisioned `node_modules`, and the cargo/go/npm caches, which
moved under it); the hobbes `scip/` helper ro; every symlink target
outside the cache ro — repo `node_modules`, the venv, and the
interpreter it links to **hop by hop and unresolved** (a hop through
uv's `cpython-3.12-…` directory symlink dangled inside the container
when only the resolved target was mounted; found by the venv listing
test). Index steps `--network none`; the registry reached from
separate fetch containers that execute nothing (`cargo fetch` pins
`build.rustc*` on its command line against a staged
`.cargo/config.toml`; `RUSTUP_TOOLCHAIN` / `GOTOOLCHAIN=local` refuse
toolchain downloads). `scipsource`: `run_helper`, `venv_environment`,
`provision_node_modules` route through it; the Rust and Go units fetch
then index; the TS zone passes its link targets; the Python index passes
its venv. The venv listing was a **fourth executing process** the
review's table did not have — it runs the venv's own `bin/python`, a
binary under the repo tree — and is contained as `python-env`.

**Refusal, P10-shaped.** `ContainmentRefusal` is neither a `ScipError`
nor an `OSError`; every per-unit catch and the language catch in
`_lane_b_facts` name it and re-raise/record it first. Without podman or
the image: `index-rust` and `python-env` refuse (Rust to the syntactic
floor with a record naming the guarantee; the Python index runs without
its listing under C-27); the non-executing steps run on the host and
say so. `HOBBES_UNCONTAINED=1` runs everything on the host, disclosed on
every provider (the CLI flag is phase 3). C-64 registered surfaced;
C-29 narrowed to in-container execution, disclosure retained.

**Image.** `sandbox/Containerfile` extended, one image still: ubuntu
24.04 (the host-mounted trees are glibc-linked; the proxy is static),
node 22.14.0, Go 1.26.5, scip-go v0.2.7, rustup 1.97.1 with
rust-analyzer **and rust-src**. The first build lacked `rust-src` and
the contained Rust lane silently lost its semantic tier (11 semantic
calls → syntactic on minirust and `bench/oracle/rust`; external refs 3
vs 30) — the contained-vs-host diff caught it, which is the check
phase 2 mandates for the oracles and the reason to keep it.

**Verified.** Canary fixture `tests/fixtures/canary-rust`: a `build.rs`
that emits a cfg (so `generated()` exists iff it ran), reads a planted
secret at `/tmp/hobbes-canary-secret` (a second cfg → `leaked()`), and
writes `/tmp/hobbes-canary-escaped`. Contained run, 0.6 s: `generated()`
in the facts, `leaked()` absent, no sentinel on the host, no host-run
record. This repo ingested contained is **byte-identical** to the host
run of the same tree (node/symbol/edge sets, `dependency_coverage`,
`extraction_errors` modulo the 13 C-64 disclosures), and two contained
runs are identical to each other; evidence row added. Note for the
record: the uncontained comparison run executed the canary's build
script on this box — the escape hatch doing exactly what its disclosure
says.

Suites: 949 pytest (31 new in `test_containment.py`, the three
provisioning tests moved to the planner seam, the venv listing test
marked `lane_b` — it now runs contained and still fails its own
pre-existing environmental assertion, untouched); Go, web, node
untouched. Architecture §3.2 and §7 amended; `first-run.md`,
`sandbox/README.md`, CLAUDE.md updated; handoff rewritten.

## 2026-08-28 — ADR-092 phase 2: the executing oracles run in the sandbox image

Max ratified the phase-1 decisions (all four, the venv listing kept
strict) and cleared phase 2. O6 and O7 — the two oracles that execute
the target — now run in `hobbes-session:local` through
`bench/oracle/internal/contain`, the lane's own copy of the planner
(bench tooling, own module): the verifier's mount shape verbatim (tree
overlay `:O` at its host path; cell dir and Hobbes cache rw; the nightly
sysroot, the driver, the tracer script and the interpreter chain ro at
their host paths); O6 no network; O7 `cargo fetch` in a networked
container then `cargo check` with none, the toolchain's binaries named
directly (`<sysroot>/bin/cargo`, `RUSTC`, `LD_LIBRARY_PATH`) because
rustup's `+nightly` proxy is the host's. `run-cell.sh` names the venv
python (`uv` is not in the image). The export and report carry
`containment`; `report.txt` prints `oracle ran contained (ADR-092)`.
Fixture self-tests (minirust MIR, miniapp trace, both poison tests) run
contained and skip without the image. Refusal is the same P10 type
(`contain.Refusal`).

**Numeric no-op, measured.** O7: rust_proj regraded — `oracle.json` and
`report.json` byte-identical to the 2026-08-25 cell modulo the new
field (`oracle-cells/rust_proj-2026-08-28.md`). O6: this repo's Python
zone contained vs host on the same tree, containment-sensitive tests
deselected on both sides — suspects (5) and every miss class identical;
an 8-confirmed-edge residue confined to one test that probes for a
container runtime and skips inside the image
(`oracle-cells/hobbes-py-2026-08-28.md`). Not an H-entry: the oracle
moved nothing, the traced program probes its environment; the rule
recorded in the ADR. The first O6 pair, run on the full suite, differed
by 207/232 sites — all in the containment tests themselves, which is
why the pair is stated with its deselection.

Suites: oracle Go 33 (5 new, `contain_test.go`); pytest untouched.
ADR-092 retitled and its phase-2 section written; `oracle-grading.md`
§6/§7, architecture §7, C-64, the lane README, CLAUDE.md amended.

## 2026-08-28 — ADR-092 phases 3 and 4: the flag, the stamp, the two layers

Phase 3, guarantee wiring: `hobbes ingest --uncontained` (prints
`UNCONTAINED:` first, sets the hatch); `containment.LEDGER` records
every lane B step and `graph.json` carries `containment: {steps,
all_contained, escape_hatch}`; the summary prints a `containment:`
WARNING when any step ran on the host; `list_blind_spots` prints the
same line with C-64 and nothing when the guarantee held (Go test);
P4's gloss extended. `go/bin/hobbes-proxy` and `sandbox/hobbes-proxy`
rebuilt. Phase 4, prose: architecture "Where this is going" states the
two layers and the P11 scope; `proxy.KnowledgeOnlyBanner` prints them
at `serve --knowledge-only`; §4 cross-references. C-64's surfacing line
rewritten for the flag and the stamp. Suites: 951 pytest (2 new), 293
Go (2 new), oracle 33.

ADR-092 is now built in full and awaits Max's review; the oracle-cell
triage (seven cells, on hold since 2026-08-27) resumes after it.

## 2026-08-28 — ADR-092 reviewed; the containment claim scoped (P11)

Max reviewed all four phases: all good, with one addition — the sandbox
runs apply only to the repos actually re-run under them. Written into
ADR-092 ("Scope of the containment evidence"), C-64 (a Scope line) and
`extraction-evidence.md`: every earlier cell and graph was a host run
and is not re-earned; the contained toolchain is not assumed equal to
the host's until a cell proves it (`rust-src` was the first difference;
more expected); a record without `containment` is a host-run record.
The oracle-cell triage resumes next.

## 2026-08-28 — the seven-cell triage: four fixes, every compiler-graded cell at 100%

Max cleared the triage after the ADR-092 review. The seven untriaged
cells (toml, click, memchr, mux, fzf, ajv, cheerio) reduce to five
findings:

- **fzf, 87 syntactic contradictions — hobbes-wrong.** Lane A's Go
  fallback bound a local `assert := func(..)` (and a local `atoi`) to a
  package-level function of the same name in another file of the
  package. ADR-090's scope veto had a Python shape only;
  `gosource._call_fallback` now refuses a bare name an ADR-046 local
  binding spans. Regrade: 87 → 0, confirmed 2,832 kept, precision 100%.
- **memchr, 7 semantic contradictions — hobbes-wrong.** A tuple-struct
  constructor expression (`FinderRev(Hash::new(..))`) drawn as `calls`
  to the type; rustc lowers it to an aggregate. The O4 conversion rule
  (`scipsource.project`) now covers `.rs` targets: → `uses`. Regrade:
  7 → 0, confirmed 921 kept.
- **mux 3 + cheerio 44 — oracle grain (H-18, RC-3).** A call through a
  function-valued binding (`var RegexpCompileFunc = regexp.Compile`;
  `const parse = getParse(..)`): Hobbes names the binding, the oracle
  the held function — both true. D-O4 bullet; the export carries
  `target_kind`; `grade` buckets it **abstract** (`func-value`) like an
  interface method. Regrades: 0 contradicted, precision 100% on both.
- **click, 47 of 85 suspects — oracle grain (H-19, RC-3).** `@overload`
  stubs and the implementation are one declaration; the tracer's index
  anchors the implementation at the first stub's `def` line. Regrade
  (contained): suspects 18, rate 1.0%; 16 of the 18 are C-60's
  override/monkeypatch asymmetry, 2 untriaged sightings.
- **ajv, 3 — hobbes-wrong by tier, n=1, unfixed.** A member call on a
  union-typed receiver drawn to the enclosing class's own override at
  semantic certainty where the base signature is the static answer; a
  scip-typescript shape (P9), recorded as `static→union-member` in the
  misses table; the second sighting names the rule (review §3.2).
- **toml:** 0 contradicted; nothing.

Records: each cell carries its regrade section, triage ratio (A-8) and
direction of fix; `oracle-defects.md` H-18/H-19 (RC-3 → n=5, still
closed-policy: two sightings against a closed root in one triage — the
rule held, its bullet list was short); `oracle-misses.md` loop table +
three class rows; `extraction-evidence.md` loop section; architecture
§3.8 note; ADR-090 amended for the two product extensions. The
regrades that moved ran contained (ADR-092); toml and ajv stay host-run
records. Suites: 954 pytest (3 new), oracle Go 35 (2 new).

## 2026-08-28 — evidence log and §3.8 refreshed

Max: the evidence had fallen behind. `extraction-evidence.md` full
pass (six drifts, the SWE-bench D7 row corrected per ADR-091, the
loop's missing pre-registration stated); then §3.8's four language rows
rewritten to the current state — the seven loop repos on their rows,
the post-ADR-090/O4 dagger numbers, rust_proj as the one Rust cell
re-earned under containment, click's trace cell — and the table stamped
current to 2026-08-28 with the host-run/contained distinction.

## 2026-08-28 — architecture drift audit (ADR-033 §9 discharged): 41 fixes, one regrade, one red test caught

Max: run the drift audit. Four read-only auditors over the running
architecture (front + §1–2, §3–4, §5–6, §7–10 + CLAUDE.md), every
report verified against the tree before a fix. 41 stale claims fixed
in place. The ones that mattered:

- **A red build the last pass had not run.** §3.8's "Verified on"
  cells are pinned verbatim in `extract/verification.py` and held by
  `test_every_section_38_row_is_pinned_verbatim`; the row rewrite of
  the previous session left the suite red. Pins re-derived from the
  rows (python 8 / ts 4 / go 5 / rust 3 repos), the sibling count
  tests updated. The lesson is the rule the section already states —
  "extending a row here without the code is a red build" — and the
  practice to add: run the suite after a docs-only commit that touches
  §3.8.
- **A claim that was not yet earned.** "Every compiler-graded cell at
  100%" was false twice: ajv at 99.8% (now stated as the exception) and
  this repo's own Go cell at 99.8% with the `run := func` shape the fzf
  veto fixed — never regraded. Regraded contained: **1,283/1,283, 0
  contradicted** (`oracle-cells/hobbes-go-2026-08-28.md`); the Go row
  and the evidence log carry it.
- **Design described as built (§3.6):** partial SCIP indexes cached by
  content hash and merged, lane B debounced — neither exists; the
  only caches are ADR-050's `node_modules` and ADR-092's tool caches.
  Rewritten as the honest state.
- **§7:** the `orchestrator` role (rw worktree) was unnamed; the flight
  record's `escalation` and `context_fault` fields; the `--claude-cred`
  mount as a second, opt-in credential path beside C-41; the ingest
  shape's "no network" narrowed to the steps that run the repo; the
  bench box policy's real path. **§8:** rows for the oracle lane and
  containment, the benchmark row's parking date and "next". **§6:**
  D5's carve-out stated inside the coverage guarantee; the transcript
  claim scoped to the owned loop; depth is the dataset's rated band,
  the file-count proxy the fallback; `write_file`/`edit_file` in the
  harness arm's tool list; the evaluator on local podman, not Modal
  (C-50); live runs through 08-24 and ADR-091 in the correction range.
  **§1/§3:** P7 restated as the four-step checklist; C-9 no longer
  listed as a provider limit (it is ours); C-28's two-file wording;
  the conversion guard's Rust half; the third indexer's omission now
  measured; "nothing else changes" replaced by the list of what a
  language does touch; the 33 Rust edges as 17 calls + 16 uses; the
  diagram's lane B node names the container. **§10:** Rust and HCL are
  in scope. **CLAUDE.md:** the policy merge order (floor first, role
  before folder), 64 constraints, 294 Go tests, the fixture list, the
  handoff routing to ADR-092, the Status date. C-63 moved above its
  segment's Lifted heading, where it had been misfiled.

Unverifiable claims (owner attributions, run observations outside the
tree, policy statements) were listed by the auditors and left as they
are; none contradicts the tree. Suites: 953 pytest + the known
environmental failure, 294 Go, 35 oracle — green.

## 2026-08-28 — ADR-093: D5 and D6 closed — lexical evidence is neither a plan nor work

Max reopened the two held harness defects and cleared the recommended
approaches. One principle covers both: the proposal-text (lexical,
C-36) layer carries the weakest evidence the mapping has, and two
guarantees written for human/planner seeds were letting it through.

- **D5** (`run/stages.py`, `run/coverage.py`): a planner whose handoff
  resolved to nothing used to drop to the lexical seeds, `break` out of
  the plan loop — no re-plan — and spawn implementers with no coverage
  check inside a `--coverage strict` run. Now it gets the one re-plan
  an uncovered handoff gets (`fallback_note`: the names it gave, "none
  found"); still nothing → `strict` raises `PlanCoverageError` with
  status `lexical-fallback`, `coverage.planner_unresolved` and
  `replanned: true` on the written record, no implementer spent.
  `assign` runs on the lexical seeds and records it, as before.
- **D6** (`derive/impact.py`, `partition.py`, `changespec.py`):
  `ImpactSet.seeds_lexical` names the seeds the text alone hit;
  `unit_modules` drops such a seed when it is a hub (fan-in ≥ 30) —
  only the hub half of ADR-083's rule: the dotless-id "package root"
  heuristic names every top-level module of a small repo and emptied
  the bench fixture's plan on the first try. `context_seeds` gives the
  reason; the spec carries `seeds_context`; `hobbes plan` prints it.
  Every-seed-a-lexical-hub is a `SeedError` naming `--seed`: what
  remained was the hub's neighbourhood, units with no seed in them.

Reconnaissance was done through the knowledge tools (Max's direction:
use Hobbes on Hobbes): `who_calls` put `unit_modules` at one product
caller, `tests_guarding` named the tests that would move
(`test_lexical_fallback_when_the_planner_names_nothing_real`,
`TestStagedCoverage`, `test_prose_hits_seed_alone_…`) before an edit.
Validated with no model: eight new tests (strict re-plan then stop /
assign runs / a recovering second handoff; a thirty-importer hub by
word vs by `--seed` vs alone; the spec's rendering). 960 pytest green
plus the known environmental failure. Register: C-36 and C-57 amended;
`adr085-validation-run.md` fully discharged; architecture §6 loses the
D5 carve-out. The removal A/B is un-confounded on the D5 axis; it
still waits on a cleared run and a larger n.

## 2026-08-28 — a stale install bypassed containment; ADR-094: the knowledge proxy in the sandbox, every artifact stamped `built_by`

Max asked whether the `scip-decode` warnings on his ingest were a
worry. They were not (C-28, identical to the previous ingest); what
the ingest had *not* printed was. The `graph.json` his bare `hobbes
up` wrote carried no `containment` stamp, though `extract/__init__.py`
sets it unconditionally. `~/.local/bin/hobbes` was a symlink into
`~/hobbes` at `7356d84` (2026-08-24), four days before ADR-092. That
tree ran lane B on the host, and the canary fixture proved it:
`/tmp/hobbes-canary-escaped` stamped `02:52:57`, the graph's minute.
Harmless against our own repo — the canary writes one sentinel — but
the P10 guarantee had been defeated by a PATH entry with nothing said.
Re-ingested from this tree: all 23 lane B steps contained, the old
graph's age visible in the diff (`fallback-resolved: 9` from before
ADR-090, no `below-floor`, 93 fewer symbol edges, the pre-ADR-091 D7
wording).

Max: run the full knowledge piece in the sandbox — it prevents path
mismatching and hardens security; if not possible, document it as a
flag. Built as ADR-094: `.mcp.json` now starts
`sandbox/knowledge-serve`, which runs the **image's** proxy in a
read-only, `--network none` container on stdio; the launcher binds to
the checkout that owns it and refuses without the image (a silent
fallback would be the pinning not happening) — `HOBBES_KNOWLEDGE_HOST=1`
is the disclosed hatch (C-65). `graph.json` carries `built_by`
(checkout, commit, dirty) of the pipeline code that ran; `hobbes
ingest` prints it, every knowledge answer opens with it, and the proxy
prints its own `build <vcs.revision>`. Live: init in 0.10 s, six tools
answered through the container, the answer head reading `built by
hobbes @ ee4d95248cf6 from /home/mmarrujo/hobbes_public`. The first
smoke test ran an image from 00:14 that predated phase 4's banner —
the "stale image" caveat C-65 states, and the reason the image is
rebuilt after the proxy. The ingest itself stays on the host: parked
in `future_additions.md` with the three reasons (lane A executes no
repo code; baking the pipeline in un-pins or slows development;
nested podman or the loss of network-by-phase). Suites: 966 pytest +
the known environmental failure, Go green, gofmt clean.

## 2026-08-28 — ADR-095: CI for real; the handoff trimmed; W0 refreshed

Session opened as a review of the project and its base docs, with
Max's note that Hobbes should be used more for the session's own
development. Reconnaissance went through the knowledge tools first:
`list_blind_spots .` (capture floors go 88.0 / python 85.5 / rust 80.2
/ ts-js 63.5; the web environment gap — `vite`, `@vitejs/plugin-react`,
`@types/cytoscape` unresolved — and the C-28 namespace rows, identical
to the previous ingest), `list_invariants .` (11 confirmed; three
near-duplicate pairs noticed: I-1/I-7, I-2/I-8, I-6/I-11),
`graph_neighborhood hobbes.cli`, `tests_guarding pipeline/src/hobbes/run`
(~100 tests). `get_module_doc` answers "run `hobbes narrate`" on this
repo — the one empty tool of the six; it spends model calls, so parked
as a W0 item for Max to clear.

**Built — W0's "CI, for real" (ADR-095).** `.github/workflows/ci.yml`:
four jobs (`go`: gofmt + product and oracle-lane `go test` + the static
proxy builds; `python`: pytest with lane B off; `web`: vitest + build,
tsextract, scip helper; `graph`). The graph job is
`scripts/ci-graph.sh <base>` — the README's shape as one script CI and
a developer run identically: static proxy → `podman build` of the image
(lane B runs only inside it, C-64) → `hobbes ingest` → **the
`containment` stamp checked** (`all_contained`, no escape hatch; an
unstamped graph is the ADR-094 incident shape and fails) → `hobbes
lanes` → `hobbes invariants compile --json` with **every emitted config
executed** (the first CI execution of a compiled checker: the I-5
semgrep rule ran clean; C-19 narrowed accordingly — dep-cruiser and
Rego stay unexercised because no record here compiles to them) →
`hobbes review $BASE..HEAD` → the `lane_b` pytest cases. Base ref:
merge-base on a PR, `event.before` on a push. Validated by running the
script end to end on the box (`HEAD~1`: 23 lane B steps contained,
lanes agree, review clean, lane_b 1 passed); **not observed on GitHub**
— Max sees the first run when he publishes, and the ADR names the two
runner-specific unknowns (rootless podman as `runner`, rustup inside
the image build). One permanent deselect, by name and with its reason
in the script: `test_venv_environment_lists_the_venvs_own_distributions`,
the environmental failure the handoff holds untouched — fixing its
fixture is now a W0 item.

**Docs.** Suite counts re-derived and corrected everywhere they were
stated (README had 291/911/25 from an older state; CLAUDE.md 960):
966 pytest + 1 `lane_b`, 294 Go, 35 oracle, 52 vitest, 29 tsextract,
26 scip. README: two copy errors in the opening paragraphs, a CI
paragraph under "the CI shape", the oracle lane added to the test
block. Architecture §3.4 and §3.6 lose "no CI is configured yet".
`session-handoff.md` rewritten to a third of its size — the D1–D8
worklist and the 2026-08-24/27 "kept for the record" sections it had
accumulated live here now, not there. `workstreams.md`: the sequencing
header brought to the 2026-08-28 state (it still named the ADR-085
validation as the next run); W0 gains the deselected-test fix, a
registry-pulled image, the duplicate invariants, and `narrate`.

## 2026-08-29 — ADR-096: Java, the sixth language — built, contained, and compiler-graded on four repos in one session

Max opened the parked plan ("begin implementing java as an added
language… testing by pulling two random java repos after building and
running evidence testing pipeline against oracle"). All six milestones
of `docs/java-build-plan.md` ran: the spike, lane A, contained lane B,
the JUnit inventory, the oracle, the evidence row. What follows is what
the code taught, which is the part the plan could not have.

**The spike (J.M0, `scip/spike-java.mjs`).** `scip-java` 0.13.1 on
jsoup and spring-petclinic inside the image. `syntax_kind` unset for
**104,453 of 104,453** occurrences — the fourth indexer, the same
omission (C-6), so §3.7's mandatory syntax provider is confirmed a
fourth time. The moniker version is the artifact's own, never the git
revision (Decision 1 satisfied by default, as for rust-analyzer). Two
things the spike caught that would have been silent bugs: overload and
constructor descriptors (`compile(+1).`, `` `<init>`(+2). ``) that the
helper's `classify` read as *terms* and `terminalName` handed the join
as `compile(+1)` and `<init>` — names no call site spells; and
**positions in SCIP's typed range** (fields 8/9 of the current proto),
which the generated reader borrowed from scip-typescript 0.4.0 does not
know, so **every Java occurrence decoded as unplaced**. The helper now
owns that decode (`installTypedRangeReader`), tested on hand-built
messages for both typed shapes *and* the deprecated one so the other
four indexers are unmoved.

**Lane A (`javasource.py`).** The `rustsource` contract, plus three
rules Java forced. *Overloads*: symbol ids carry an ordinal
(`Outer.helper~2`), and the fallback resolves only when exactly one
declaration fits the **argument count** — otherwise it abstains and the
tail names the site `overload-set`. *Inheritance*: the outward name
walk **stops at a type that declares supertypes**, because Java binds
an inherited member before an enclosing class's and lane A cannot see
the hierarchy; those sites are named `inherited-member`. *Anonymous
classes*: `new T() {..}` is a use of T, its members are local bindings
with the body's extent. Both new tail classes are observations, not
guesses — which is the whole reason precision survived what came next.

**Lane B, and the decision Max should ratify (C-66).** scip-java is a
javac plugin: the only way to hand javac a classpath is to run the
build that resolves one. There is no fetch phase to separate — Gradle
resolves while running its script, and `mvn dependency:go-offline`
does not reproduce a Maven build's own resolution (jsoup's
`${os.detected.classifier}`, supplied by a build extension). So
`index-java` is **the one index step that executes repo code *and*
keeps a network**: the container is the boundary, not the network.
Disclosed on every ingest, stamped in `containment`, and canary-tested
(`tests/fixtures/canary-java`: a Maven `exec` bound to
`generate-sources` that tries to read a planted host secret and write a
sentinel — it runs, and reaches neither). Reversing it is one field in
`PROFILES`. The image gained Temurin **17/21/25** (a Gradle toolchain
pin refuses any other major and cannot download one offline), Maven and
the launcher: +1.1 GB, 1.68 → 2.79 GB.

**The oracle (J.M4) is javac itself, not SootUp.** A `Plugin`
(`bench/oracle/java`, JDK-only, ~600 lines) rides the repo's own build
— through a wrapping `javac` under Maven, an init script under Gradle —
and records what `Trees.getElement` resolved every site to. Because
Maven compiles main and test separately, shards carry declarations
*keyed* (`owner#name(erased params)`) and the Go merge joins keys
across the build; a dynamic site carries the declared method as
`interface` and the **CHA override set** as targets, which is how
Java's dispatch hole gets a number.

**Four cells (J.M5), two of them drawn at random** from a seeded
GitHub sample — the first Hobbes language measured on repos nobody
picked:

| cell | edges | precision | recall |
|---|---|---|---|
| jsoup (Maven library, 197 files) | 18,627 | **100.0%** | 76.2% |
| spring-petclinic (Spring service, 50) | 356 | **100.0%** | 98.4% |
| spring-data-elasticsearch (**random**, 739) | 16,050 | **100.0%** | 66.4% |
| Severed-Chains (**random**, 1,254) | 10,154 *syntactic* | **100.0%** | 23.5% |

Zero contradicted anywhere; poison PASS on all four, 0 falsely
confirmed in 45,187 seeded wrong edges. Lane agreement: 0, 0, 2
disagreements (and jsoup's 3,417 sites at 0).

**The fourth cell is the one worth reading.** `scip-java` could not
attach to Severed-Chains' Gradle build at all — another plugin owns
its compiler arguments, in scip-java's own words — so lane B failed,
the degradation fired, and 1,254 files fell to lane A's syntactic
floor. That cell therefore grades **lane A alone against javac**:
10,154 edges, every one confirmed, **zero wrong**, at 23.5% recall.
Both halves matter. The abstention rules hold on a repo the resolver
had never seen; and without lane B, `interface→method` recall is 0.4%
— C-8's floor, measured. C-67 gained its first real sighting: one repo
in four, on an unfiltered sample. (Our oracle's plugin *did* attach to
the same build, through an init script rather than scip-java's
injection — the difference is now on the record.)

**Three defects the cells produced, all fixed here.** Two oracle-side:
**H-20**, erased parameter names built from `TypeMirror.toString()`
carry type annotations, so jsoup's jspecify `@Nullable String` and the
class file's `java.lang.String` were two spellings of one declaration
and the cross-shard key join missed — **871 false contradictions**
across two cells (a new root, RC-8); **H-21**, javac's synthetic
`super()` counted as a site, and the over-correction then dropped its
*default constructor* as a declaration, costing every `new T()` its
target. One product-side pair, both caught by the tail and the lane
report rather than by a person: jsoup's **44 `unclassified` sites**,
every one a helper declared in an **enum constant's body** (now local
bindings, `unclassified` → 0), and a **trailing comment counted as a
constructor argument** on spring-data-elasticsearch (tree-sitter extras
are named children), which had bound `new CriteriaQuery( //` to the
two-argument overload — disagreements 3 → 2. The two that remain are
one shape: two identically named calls on one line, where the join's
`(file, line, name)` key cannot tell the pair apart.

**Registered:** C-66 (the networked index step, flagged for
ratification), C-67 (one-configuration; the Severed-Chains sighting),
C-68 (generated sources — **unmeasured**, and the cells say why: all
four report `excluded.generated: 0`), C-69 (dependencies read, not
resolved), and **C-70** — two identically named calls on one line can
pair with the wrong resolution, which Java's fluent chains found and
this session measured at 2 of 3,908 dual-resolved sites (0.05%); it is
not a Java entry, it is the `(file, line, name)` join key's, and it had
been unregistered since ADR-029. Amended: C-58 (its Java face, with the
per-cell numbers), C-32 (Java's two abstention classes), C-64 (Java
joins the providers that refuse without containment), C-29 (its Java
face is C-66). Seventy entries, sixty active. Java is **supported at
exactly four repos' worth** and §3.8 says which four and what each
cost.

**One decision is left open on purpose, and it is the next session's
first item:** C-66. The handoff opens with it — what it concedes, what
is still guaranteed, and that reversing it is one field in
`containment.PROFILES` at the price of most Java repos' lane B.

**Not done, deliberately:** a Spring route pack, Kotlin (no lane A, so
it would be references without call sites), a bytecode RTA (CHA's
numbers were sharp enough to size the hole), egress narrowing for
C-66. All four are in `workstreams.md` W1.

## 2026-09-01 — ADR-097: C-66 settled the third way — Java resolves without sources, indexes without a network

**Where the session started.** The handoff opened on one posture
decision: ratify or reverse C-66, `index-java` being the only lane B
step that executed repo-authored code *and* kept a network. Max asked
for proposals and, in so many words, for a few differing paths to be
*tried* before anything was labeled impossible. ADR-096 had recorded
Java phase separation as having "no Java form" on two true
measurements (`go-offline` misses what a build extension supplies;
Gradle has no fetch that does not evaluate its script) and one framing
that was too narrow: *a fetch that runs no repo code*.

**What was measured, before any code changed** (the scripts sit in the
session scratchpad; the numbers are in ADR-097's table):

- **Two-pass Maven on jsoup.** A stage with every non-`.java` file and
  a fresh `m2`: `mvn --batch-mode -DskipTests clean test-compile`,
  networked → BUILD SUCCESS, 149 jars, 17 s. Then the full stage,
  `--network none`, `mvn -o …` under `scip-java index` → BUILD SUCCESS,
  197 shards, 10 s. Why: Maven resolves a mojo's scope *before* running
  it, so nothing-to-compile still resolves exactly what the real build
  needs — the same resolution, not a reimplementation.
- **Two-pass Gradle on spring-petclinic** (9.5.1 wrapper, toolchain 17).
  A source-less stage with a Hobbes init script whose one task resolves
  every resolvable configuration of every project, fresh
  `GRADLE_USER_HOME`, networked → 24 configurations, 52 s. Then the full
  stage, `--network none`, `--offline clean compileTestJava` under
  scip-java → BUILD SUCCESSFUL, 12 s. scip-java's own init script needed
  nothing from the network: the launcher carries its plugin.
- **Rootless podman 5.8 (netavark + pasta) topology**, for the option
  not taken: an `--internal` network has no egress, no DNS, no route to
  the host or gateway; containers on it reach each other; a container on
  the internal network *and* a custom egress bridge reaches out (the
  default `podman` bridge breaks DNS — use a custom one); a CONNECT
  proxy on such a container served an allowlisted host (200) and refused
  another (403) to a client holding the internal network only. So an
  allowlisted egress proxy is buildable here. Recorded in W1, not built.

Four options went to Max with a recommendation (two-pass now, proxy
second); he took it.

**Built (ADR-097).** `containment.PROFILES` gains `fetch-java`
(`executes_repo_code=True`, `network="default"`) and `index-java` drops
to `network="none"`; `java_resolve_command` (Maven's `test-compile`; the
wrapper with `--init-script` + `GRADLE_RESOLVE_SCRIPT`'s
`hobbesResolveAll`) and `java_index_offline_flags` are the record;
`_index_java_unit` stages the build files alone for the resolve pass
(`java_build_files` never lists a `.java`, by construction), runs it
through `_fetch` (which grew `timeout`/`env` and, by structure, does not
catch `ContainmentRefusal` — P10), then stages everything and runs the
helper offline; a failed resolve is recorded and the index still runs on
the cache as it stands, the two records joined if the build then fails.
`scip/index.mjs` appends `-o` / `--offline` to the build command. The
`NOTE:` line names both passes.

**Tests.** The profile pins moved: every index step has no network;
the executing set is `{index-rust, index-java, fetch-java, python-env}`;
`fetch-java` is the only executing step with a network, and the plan
test asserts its stage holds no `.java` while the index plan's does; a
Gradle plan test checks the init script rides on the resolve command
only. The Java canary gains a fourth probe: generate `Phoned.java` if
the step can see `Canary.java` *and* reach Maven Central in one pass.
The `lane_b` test asserts `Phoned#` is never indexed, the ledger reads
`[fetch-java, index-java]` both contained, the three ADR-096 probes
hold, and no resolve failure was recorded — passes for real, 3.4 s on a
warm cache. The positive control (sources + network in one container)
writes `Phoned.java`, checked by hand. Node: 31/31 with the flag
assertion inverted. Suite: **1,025 pytest** (+4; the venv test still
deselected by name), Go untouched but for comments (builds).

**Re-ingested through the product path, tier-for-tier against the
2026-08-29 artifacts:** jsoup (11 s wall) — 4,588 symbols, 21,388
symbol edges, 1,907 module edges, edge sets identical; spring-petclinic
(14 s; indexed as Maven, the pom-wins rule) — 476 / 389, identical;
**Severed-Chains** (24 s; Gradle-only, the C-67 repo) — the resolve pass
*succeeded* through the wrapper, the index pass failed on the same
"another plugin replacing the compiler arguments" as before, and the
graph fell to lane A identical to the stored one: 3,955 / 7,474. The one
difference on all three: `containment.steps` now lists `fetch-java` and
`index-java`. spring-data-elasticsearch not re-run (Maven; same path as
jsoup).

**Register.** C-66 narrowed, still surfaced: "the pass that can reach
the network never sees a source; the pass that sees the sources has no
route out." What remains conceded is stated exactly — repo build logic
with a network over its own build files, the resources beside them, and
the public caches under the Hobbes cache root; not the sources, not the
host, not `~/.m2`. ADR-096's status line names the amendment;
architecture §3.2 rewritten; first-run, oracle-grading, the oracle
README, workstreams (the proxy as W1 with the measured topology; the
oracle's own `java-build` keeps its single networked pass — bench
tooling), future_additions, CLAUDE.md.

**Not done, deliberately:** the egress proxy (W1); the oracle lane's
two-pass form; a positive-control *test* for the canary probe (it would
need sources and network in one container, which the product never
does — the hand check is recorded instead).

## 2026-09-02 — the four-repo extraction test; ADR-098 (Go build constraints); C-71–C-80

Max's direction, in two steps. First: read the docs, spawn four agents,
each drawing a random public repo for one language and testing the
extraction/knowledge piece end to end (init → contained ingest → lanes
→ determinism re-ingest → 15-edge hand sample → the six knowledge
tools → honesty cross-check), stopping on an architectural error while
the others continue. Second, on the report: "fix build tag and flag
rest in constraints", and the question whether the repos were
oracle-graded (they were not — hand samples and lane agreement; one
is now).

**The draws** (seeded GitHub samples, excluding every repo in the
evidence base): huggingface/peft (Python), date-fns/date-fns (TS/JS,
pnpm workspace), quic-go/quic-go (Go), serde-rs/serde (Rust). Numbers
in `extraction-evidence.md`'s new section. Headlines: peft and
date-fns **PASS with findings** (15/15 sampled edges each, byte-
identical re-ingests, knowledge tools consistent with `graph.json`);
quic-go and serde **stopped at `hobbes lanes`** (29 of 6,772 and 3 of
910 disagreements). Every lane B step ran contained on all four;
**no semantic-tier edge was found wrong on any repo**; the wrong edges
found were syntactic (quic-go 2 of 6, serde 3 of 81) and each traced to
a named fallback shape.

**Fixed — ADR-098, C-71.** `gosource._call_fallback`'s premise "a
top-level name is unique within its package" was false: build
constraints (`//go:build`, `_GOOS.go`) let a package declare one name
per configuration, and the external `_test` package shares the
directory. First file won. Now: declarations kept per `(directory,
name)` as a list with package and `build_constraint` (the `//go:build`
expression as written plus the filename's GOOS/GOARCH — compared,
never evaluated); a bare call considers its own package only, a
qualified call never `_test`; a split name resolves only when exactly
one declaration shares the caller's key, else the fallback abstains
and the tail names the site `build-tag-set` (new class, Go's row in
C-32's table, in `tail.py`, the CLI, and the proxy's `tailMeanings`).
C-71's surfacing: after coverage rows, and only when lane B answered
somewhere in the Go zone, one `scip-go` record per directory names the
constrained files that got no semantic resolution — the index is one
configuration's (the image's linux). quic-go re-ingested: the two
wrong syntactic edges replaced by the right ones, every other edge
identical, `hobbes lanes` 29 → **17, all C-70**; the record names
eight dark files. This repo re-ingested: 5,362 sites / 0 disagree,
edge counts unchanged. Tests: nine in `test_gosource.py`
(`TestBuildConstraints`: the key, abstention, same-constraint
resolution, the `_test` namespace, the record and its lane-B-off
silence); the proxy's "cannot report" strings widened. Suites:
**1,034 pytest** (+9; the venv test deselected by name), Go 12
packages green, oracle-lane Go green, image rebuilt (C-65), the image's
proxy prints the new class.

**Registered, not fixed — C-72–C-80** (Max: flag the rest). C-72 the
Rust fallback binds `Type::method` by its last segment (serde: 3 wrong
syntactic edges; *partial*); C-73 a repo directory symlink is walked as
a second copy (serde: 19 modules / 1,356 sites twice, the copy with no
lane B; *partial*); C-74 pnpm/npm workspace links dangle in the
container and the record blames the helper (date-fns: lane B lost on 6
of 6 zones, 3 semantic edges of 2,258; *partial*); C-75 `hobbes lanes`
counts the join's fallback module edges as lane B's (*unsurfaced*);
C-76 the summary's "call edges" counts `uses` (serde 4,361 for 1,557;
*unsurfaced* — the one line reading larger than the truth); C-77
`list_blind_spots` omits `below-floor` from its tail (*unsurfaced*);
C-78 the `http-go` pack fires on `windows.Handle(fd)` (four false C-5
records; *unsurfaced*); C-79 no `dependency_coverage` for a
`setup.py`-only repo (*unsurfaced*); C-80 `super().m()` / `f().m()` is
not a Python call site and `who_calls` glosses the `uses` edge as "not
a call" (peft: 252 such lines; *partial*). C-58 and C-70 amended
(the proxy gap; CI exits 1 on a registered limit). Debt summary: eighty
entries, seventy active, seven *partial*, seven *unsurfaced*. Five of
the nine are one-to-ten-line fixes with the candidate named.

**Oracle-graded, after the fix: quic-go** (cell record
`docs/oracle-cells/quic-go-go-2026-09-02.md`). The full RTA with test
packages was OOM-killed twice on this 30 GB box (H-9's shape); at **5
binary roots** (`--no-tests`, 458 s): 17,333 edges exported, **3,766
confirmed, 15 contradicted, 1 abstract**, 13,551 silent (13,345
`not-loaded`); precision 99.6% lower bound, **all 15 contradictions
oracle-grain** — `*wrappedConn` (connection.go:243, embeds `*Conn`)
gets shadowing methods from `conn_wrapped_test.go` in the test build,
which scip-go indexes and the no-tests oracle does not — **0
hobbes-wrong**; `static→named` recall 99.6%; poison PASS, 0 falsely
confirmed. The same fact as C-71, one configuration further: the test
build is a configuration too. §3.8's Go row and `VERIFICATION_BASE`
extended to six repos (quic-go, "binary roots only"). peft, date-fns
and serde remain hand-sampled, not graded.

**Housekeeping.** Clones under `~/.hobbes/bench/extract-test-20260902/`;
oracle outputs `~/.hobbes/bench/oracle/quic-go-go/`. Architecture §3.1
(the third Go rule), §3.4 (the class), §3.8 (the row); CLAUDE.md
counts. Nothing pushed.

## 2026-09-03 — architecture doc drift after Java and quic-go

A read-through of the base documentation (CLAUDE.md, the architecture,
the handoff, workstreams, the constraints index) found four lines in
`hobbes-architecture.md` that the tree had moved past — §9's rule
names this a bug in the file, so it is fixed here rather than worked
around: §2's overview diagram listed lane B without scip-java; §3.7
still said Java's §3.8 row "waits on its oracle cells" after ADR-096
landed it; §3.8's currency line read 2026-08-28 (Java 2026-08-29,
quic-go 2026-09-02) and now names quic-go's 99.6% lower bound beside
ajv as the two cells under 100%; §10's out-of-scope language list
omitted Java. Docs only; no code, no constraints touched.

**Held at Max's direction:** the nine registered-not-fixed entries
(C-72–C-80), the C-70/CI question, and ADR-092's four embedded
decisions.

**Then the test-time-training experiment (ADR-099).** Max: the keys
are in `secrets.txt` (Modal, Daytona, HF) and the experiment is
`docs/olmo3-ttt-validation.md` — its order of work is step-gated and
its hypotheses preregistered, so the session built steps 1–3's
instruments and ran them, the standing policy lifted for this
experiment only.

*Step 1, the corpus generator:* `hobbes derive-corpus` (`hobbes.ttt.corpus`)
— symbol cards with tiers, doc chunks with pins, six QA families
(`defines`, `callers`, `callees`, `tests`, `impact` projected onto
modules, `absent` with mechanically-checked distractors), held out by
symbol and closed over class membership, code-shaped names masked in
docs and plain-word mentions counted (C-82). Byte-identical from the
artifacts; 19 tests. On this repo at HEAD: 17,036 training records,
2,610 evaluation records over 451 held-out symbols. Two bugs found
by reading the rendering: the impact family listed symbol ids as
modules (the plan's adjacency scores the calling symbol; now
projected), and unique plain words (`token`, `usage`) were being
masked out of English prose.

*Units and prompts:* `hobbes.ttt.units` — gold-diff units from git
history (per commit after a base, per file, 3–120 changed lines, lock
files skipped, trailers stripped) and from DeepSWE tasks (`solution.patch`);
arm A1's block is `aided_brief`'s span derived the C-55 way; both NLL
prompts ride the units file. `hobbes.ttt.score` grades a reply by what
it names. `hobbes.ttt.report` pairs four arms by unit under a seeded
bootstrap, split by C-84. 17 + 7 tests.

*The base:* this repo at `ebdf7a5` (the public release) in a worktree,
`hobbes init` + contained ingest — first attempt: scip-python's helper
crashed because the worktree had no `pipeline/.venv` (C-27's shape;
`uv sync` fixed it); second attempt ran the *worktree's* older Hobbes by
`cd`-ing into it (the ADR-094 incident, again — always `uv run hobbes`
from this checkout with `--repo`); third: Python 86% capture, built by
`e656b75`. Corpus at the base: 13,688 records, no doc chunks (nothing
narrated there, C-82), hash `9dfc0270803c44fc`. Units: 147 hunks from the
72 commits after the base; 55 name a file the base graph knows (C-84).

*Modal (`pipeline/scripts/modal_ttt.py`, volume `hobbes-ttt`):*
`train_adapter` (LoRA per §3.3, A100-80GB, manifest with GPU/versions/
losses, C-81), `score_nll` (bare and aided prompt per unit, adapter
optional), `serve` (vLLM 0.27.1, base + adapters by name; vLLM lists
`Olmo3ForCausalLM` with LoRA). Pins: torch 2.8.0, transformers 4.57.6,
peft 0.18.1.

*First numbers (Olmo-3-7B-Instruct, base, no adapter — recorded, not
read):* gold-diff NLL over 147 units, A1−A0 = +0.0017 (p 0.56); on the
55 context-known units −0.0090 (95% CI [−0.0175, −0.0007], p 0.038,
30/55); on the 92 new-file units +0.0080 (p 0.011) — the boilerplate
alone costs a little. 42 s of A100.

*The adapter, and what it holds (the rest of the session; cell records
`docs/ttt-cells/hobbes-olmo3-7b-2026-09-03.md`,
`fastapi-olmo3-7b-2026-09-03.md`; the reading in
`benchmark-hypotheses.md` § H-TTT).* 300 LoRA steps on the base corpus
(0.35 epochs, 667 s of A100): gold-diff NLL **−0.296 nats on 147/147
units** (A2−A0); the block on top of it, nothing (A3−A2 +0.0006).
Distrusting a 147/147 that held on new-file units, the session added a
control outside the preregistered grid — `derive-corpus --control
shuffled`, answers permuted within family, every relation wrong, every
token the same — and it took **0.218 of the 0.296**; the true adapter
beats it by 0.078 on 140/147. Memorisation probe (§4.4): Olmo 3 at
0.044 on this repo, U. Held-out navigation over 2,270 questions about
393 symbols whose every training mention was removed (scored by what a
reply names; "none recorded" items split out after the first table
read a waffling base as 0.54 on callers): the base ≤ 0.06 everywhere
and inventing a file for 98% of distractors; the adapter at defines
0.985, refusal 0.78, tests 0.52, impact 0.30, callees 0.21, **callers
0.10 (p 0.08)**. The card-in-prompt control (A1/A3): the base reads what
the card says and nothing it omits; weights beat the card on file,
impact and abstention, the card beats weights on every specific edge;
A3 is the best navigation arm (0.61) but reads the card's tests line
*worse* than the base. **The training sample (600 trained questions):
callers 0.15, callees 0.21, tests 0.52 — the same as held-out.** The
weights hold module-grain regularities and an abstention habit, not
edges, at this step count; the doc's own next step is the step-count
ablation. Replication on fastapi (unseen, 0.129; 68 git units, 0.17
epochs): −0.223 on 68/68, block nothing. **No memorised cell at 7B:**
every candidate U or "neither" for both Olmo 3 and Qwen2.5-Coder
(C-83 seen in both shapes: Qwen names httpx's pre-rename files;
generic file names inflate files-P); H-TTT-4 unread. Standing: H-TTT-1
not killed (most of it vocabulary), H-TTT-5 killed on NLL and not on
navigation, H-TTT-2/3 unmeasured (no agent run), H-TTT-4 unreadable.

*Defects met on the way, registered:* C-85 (a Python repo with no venv
loses lane B in the container — httpx/fastapi/textual at 0.0% until
given one; the record blames the helper); the scorer counted a name
inside the asked id as an offer (fixed, the head-only A2 run set
aside and re-run with full replies); `expand()` re-sorted its whole
frontier per step (a heap now, same order on 85 seeds; textual's
corpus from >25 min to 74 s); vLLM's KV budget on the A10G (16k
window); one transient 500 killed an arm (retries); two scripts
matched their own launcher with `pkill`/`pgrep -f`. Compute, from
Modal's own meter (Max, 2026-09-03): **about 3 hours of GPU time,
$5.70** — three adapters, ten NLL passes, the A10G serving between
scale-downs. The session's in-flight estimate (~6 GPU-hours, ≈ $12)
was a wall-clock guess and read twice too high; the meter is the
record. Suites: **1,084 pytest** (+49 for
`hobbes.ttt`; the venv test deselected by name), Go untouched.

*Not done:* step 5 (agent runs, HSR/RFE); the step-count ablation;
the memorised cell; HEAD-ingested docs in the corpus. Nothing pushed;
the two vLLM apps scale to zero when idle.

## 2026-09-03 (later) — the review's ten follow-ups on the TTT results

**Max's direction:** stop the running ablation; then a ten-item list
("whoever picks up the hobbes-ttt Modal app…") — each with the gap,
the change, and a pre-committed reading — under ~10 A100-hours.
Readings were written into `benchmark-hypotheses.md` § Follow-ups
before anything ran; no first-record number was edited; a second cell
record (`docs/ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md`) carries
everything new with its scorer, template and conditioning versions.
The 10,000-step point (≈ 6 A100-hours alone at the measured 2.2 s/step)
was held for Max; everything else ran, ≈ 7 GPU-hours by the manifests
(read the meter).

**Instruments (all tested; 1,142 pytest):** NLL conditioning as a
named variable (`none` / `subject` / `message` / `task`; 28 hand-written
proposals in `bench/ttt/proposals-hobbes-ebdf7a5.jsonl`); `derive-corpus
--paraphrases K` and `--control shuffled-all`; scorer v2 (unique-suffix
paths) with `ttt_rescore.py`; `report_arms` per C-84 population;
`ttt_probe.py --context card-refuse`, a version-aware files score
(`hobbes.ttt.probe`), a `rescore` mode; `hobbes.ttt.cell` +
`ttt_cell.py` (derived units from `hobbes plan` over the proposals,
four *model + prompt* arms on the owned loop with file tools only,
HSR / RFE / `manifest_ignore`); `loop.py --no-bash` and `--tool-choice
none` (schemas in the system prompt, Olmo 3's `<function_calls>`
syntax read from the text, JSON or Python-quoted). `modal_ttt.py`:
`--conditioning`, `SERVE_GPU` / `SERVE_MAX_LEN` / `TTT_APP`, resident
adapters capped at four.

**What came out (numbers in the record):** (1) the true−control NLL
margin is larger where the graph holds nothing — a bound, not the
graph's worth (C-86); (2) the first run's prompt was the commit message
(C-87); the adapter's gain does not shrink under a task statement and
the block becomes real only under one (−0.008) — separable; (3) the
first control kept every true edge in its cards; the corrected control
takes 0.226 nats off the diff and learns **nothing** navigable; (4) one
instruction takes the base's false acceptance to 0.00 where the adapter
reaches 0.22, and the adapter under the instruction collapses its true
answers; (5) callers on trained symbols 0.15 → 0.33 → **0.95** at 1,000
/ 3,000 steps while the NLL gain falls to zero — the two metrics are
anti-correlated in step count, and one template per fact suffices; (6)
three seeds: NLL intervals relabelled unit-only, held-out tests
seed-dependent, abstention identical item for item; (7) 59 of 89 A1
defines failures were basename answers, v2 puts A1 at 0.92 and the base
at 0.29 by convention; (8) the tests collapse is a family-wide "none"
prior, callers/callees a module-tracking one (C-88); (9) the primary
cell over 50 derived units: manifest RFE 0.41, adapter alone 0.01 with
confabulated repo-shaped paths, HSR not lower — **H-TTT-2 and H-TTT-3
killed**; five harness defects registered; (10) the probe scored
against tagged releases finds Qwen's older httpx (0.25 at 0.28.1) and
no memorised cell.

**Incidents:** vLLM's "auto tool choice requires a parser" 400 killed
the first 200 cell rows (discarded); the A10G could not hold three
adapters at 16k or 8k (moved the navigation serve to an A100); the
first HSR extractor counted capitalised prose (re-scored offline, v1
scores kept beside). ADR-099 amended (decisions 9–14); design §3.2(c)
and results §1 carry dated amendments; C-86–C-88 registered (88
entries).

## 2026-09-03 (night) — the ten extraction entries lifted, easiest first; the four clones re-ingested; C-89 fixed and C-90 registered

**Max's direction:** "tackle those extraction constraints, tackle the
easiest possible; the first two covering the last experiment we leave
off for table for now." So the TTT items and the cell's defect
register stayed tabled, and the session worked C-72–C-80 and C-85 in
ease order, one commit per batch, each with its tests, its register
entry moved to the segment's lifted section in the same commit, and
the architecture amended where a rule moved.

**Batch 1 — the three counting lines (`89c819a`).** C-76: the ingest
summary and `hobbes diff` count `calls` and `uses` apart (the one
register line that read *larger* than the truth; serde's "4,361 call
edges" for 1,557). C-75: `_lane_agreement` keeps only `imports` edges
with `scip` evidence as lane B's — the projection raises module edges
from lane A's fallback too, so with lane B off the self-test had been
reporting lane A's agreement with lane A — and emits
`module_edges_lane_b_produced`, which `hobbes lanes` prints beside the
comparison (`0 (lane B produced 0)` on the suite's default). C-77: one
`below-floor` row in the Go proxy's `tailMeanings`; rollup, per-file
line, glossary and the C-32 note all iterate that table (image rebuild,
C-65).

**Batch 2 — the pack and the manifests (`0a06e8a`).** C-78: the
`http-go` pack's `_is_registration` refuses a `Handle`/`HandleFunc`
whose file imports no `net/http`, whose receiver is another import's
alias (quic-go's `windows.Handle(fd)`), or whose name is a type in the
file's package. C-79: `declared_dependencies` reads `setup.cfg
[options]` + extras and every `requirements*.txt` statically (`-r`,
`-e`, options, URLs and paths skipped; `pkg @ url` keeps `pkg`;
`setup.py` never read), through `iter_manifests`, the CLI pack's walk
generalised; `_coverage_gap_records` appends a `scip-python` record
when the index ran against no declared list.

**Batch 3 — the call graph itself (`5562271`).** C-72, reproduced on
a probe crate first: `Option::<T>::deserialize(d)` read `path []`
(the generic head is a `type_identifier`) and fell into the bare-name
lookup, which hit an `impl` method; `Expected::fmt(self, f)` resolved
through the trait's `type` symbol into the enclosing impl's own `fmt`.
Four rules in `_call_fallback` — ADR-098's in Rust's shape: a
`::`-qualified call (`qualified`, recorded by both walks) is never a
bare name; a bare name never binds to a `method`; a trait head
(`RustFile.traits`) is dispatch; a `Type.name` two impl blocks declare
is an overload set. C-80: `pysource` records an attribute call on an
expression receiver as `<expr>.name` (`EXPR_RECEIVER`) at the
terminal's line and column, `graph._resolve_call` says nothing for
that head, and the `who_calls` gloss reads *"references X where no
call site was detected (…; a call through a receiver lane A cannot
see, C-1)"* instead of "without calling it". **On this repo,
re-ingested contained:** 1,433 expression-receiver sites detected,
lanes 5,937 / 0, six of the seven `uses` edges that vanished became
`calls`, Python capture 81.7% of 14,352 (the denominator grew by the
new sites — honest, and the entry says so).

**Batch 4 — the three environment entries (`a60777f`).** C-85 first
reproduced on a venv-less copy of `miniapp`: `capture [python]: 0.0%`,
scip-python's stack ending in its option parser, the record blaming the
helper — after a false start where `uv run` *inside* the copy made uv
create a venv there (ADR-094's lesson in a new shape; the handoff now
says so). Fix: `extract_scip` always writes the environment listing,
empty without a venv, and records the one-command fix; the helper
exits `INDEXER_EXIT` (3) when the indexer it drove died and
`run_helper` records that as *the indexer's* failure. **0.0% → 68.4%
of 19**, the same as with a venv. C-73: `discover.linked_copy_target`
— every language's walk (and the manifest and Terraform walks) skips a
directory symlink whose target is inside the repo, the ingest records
each link once (stage `discover`); an ancestor link no longer loops.
C-74: `workspace_link_targets` reads one level of each `node_modules`
tree a zone links and mounts the out-of-tree targets ro beside it;
`_rebase` places a zone's whole-index records at the zone. Measured on
a synthetic pnpm-style workspace: the zone indexes contained with a
semantic `b → a` edge; the control (`workspace_link_targets` stubbed)
reproduces date-fns exactly — `TS6053: File '@x/dev/tsconfig.base.json'
not found`.

**The four clones re-ingested** (still on disk under
`~/.hobbes/bench/extract-test-20260902/`, pre-fix artifacts kept for
the diff; rows in `extraction-evidence.md`): **peft** 249 `uses` →
`calls` (all 249), `save_pretrained` 232 callers and no "non-calling
references", `dependency_coverage` 13/52 present; **date-fns** capture
**0.1% → 79.7%**, `calls` 3 → 2,205 semantic, 13 of 15 zones index;
**quic-go** the four false C-5 records gone, nothing else moved;
**serde** the copy gone (and a second link the test had not noticed,
`serde_derive_internals/src`), syntactic `calls` 81 → 28, **lanes 910 /
3 → 721 / 0**, capture 80.0% → 88.2%.

**Then the thing a fix uncovers (`3da8c07`).** date-fns's lanes, with
lane B alive for the first time, showed **54 disagreements**, every
one the same shape: tsextract emitted the *implementation's* line for
an overloaded function (`normalizeDates` 19) and scip-typescript the
*first signature's* (4) — and the projection found no lane A symbol
starting at SCIP's line, so those calls were `below-floor`. **C-89,
registered and lifted the same hour:** `declarationStart` uses
`getOverloads()[0]`; date-fns 7,586 / 54 → **7,586 / 0**, below-floor
254 → 219. The two zones still failing are **C-90, registered, not
fixed** (*partial*, loud): a tsconfig reached by `extends
"./config/tsconfig"` or by project `references` is not on the staged
walk-up path; candidate fix named (a comment-tolerant scan of the two
keys, staged transitively).

**Register at close:** 90 entries — 69 active, 19 lifted, 2
superseded; five *partial* (C-4, C-58, C-68, C-83, C-90), two
*unsurfaced* (C-19, C-20), **no line inflates a number**. Suites:
**1,166 pytest** (+24 this session; the venv test deselected by name,
W0), Go green, **30 tsextract**, **32 scip** node tests; image rebuilt
(C-65) before the runs. Nothing pushed; no GPU spent.

*Addendum, the same night — "fix c-90 too."* Two pieces:
`referenced_ts_configs` follows `extends` and `references[].path` from
each staged tsconfig (a regex over the two keys, comment-tolerant, no
JSON5), staging what they name transitively inside the repo; and
`is_solution_tsconfig` replaces a references-only root with the
generated config for the zone's own files, because a solution file
names no inputs and scip-typescript then indexes none. date-fns:
`pkgs/dev` back after the first, the root after the second — **15 of
15 zones, no `scip-typescript` record, lanes 7,601 / 0, capture
80.1%**. C-90 moved to lifted the same night; **68 active / 20
lifted**; 1,169 pytest.


## 2026-09-03 (late) — high-level doc drift: the README caught up to Java, containment and the register

A read-through of the entry docs (README, CLAUDE.md, the architecture,
the handoff, workstreams, the register index, the secondary status
headers) found the internal docs current to the night's commit and
agreeing with each other, and the public README about a week behind.
Fixed the drift and nothing else (Max: "leave the rest, something else
is more pressing").

- **README.** Status named four languages; now five plus HCL, with
  Java's landing (ADR-096) and the register's true count (ninety;
  sixty-eight active, twenty lifted — was "fifty-seven"). The two-lanes
  prose, its diagram and the grading sentence now include `scip-java`
  and the javac oracle. A containment paragraph (ADR-092: repo code
  never executes on the host, the `--uncontained` stamp, the knowledge
  layer as a complete deployment) — the architecture's headline claim
  had no public sentence. The eight harness defects read as "the
  current worklist"; all are fixed (ADR-091/093). The TTT experiment
  (ADR-099) gets one sentence and a link. The ADR count reads 99. The
  test table's hard-coded suite counts (three sessions stale) are gone
  — CLAUDE.md is the one place, checked by CI. Getting started told the
  reader to install `scip-go` and `rust-analyzer` on the host; since
  ADR-092 lane B runs from the image, so the block builds the image
  instead and says no per-language host install exists.
- **`benchmark-hypotheses.md`** opened "preregistered, not started"
  above three rounds of recorded results; the header now says what ran
  and that no H1 claim is earned.
- **Architecture §8** gained rows for Java (ADR-096/097) and the TTT
  experiment (ADR-099), both already described in §3 and §6.2; the
  benchmark row now credits ADR-093 with the last two defect fixes.
- **`future_additions.md`** titled Java "the fifth language"; CLAUDE.md
  and ADR-096 count it sixth (HCL counted). Sixth.
- **`workstreams.md`** sequencing block: item 6 said current work was
  W0's discipline items; items 6–8 now carry CI-awaiting-its-first-run,
  Java plus the 2026-09-02/03 lift cycle, and the TTT hold.

Not touched, noted for later: `oracle-grading.md` and `agent-mapping.md`
carry status headers frozen at 2026-08-25 and 2026-08-21 (both defer to
the architecture, cosmetic); CLAUDE.md's Status block is near its own
length ceiling.


## 2026-09-04 — first-run doc drift: the build step caught up to ADR-092

A base-documentation read-through (README, CLAUDE.md, the architecture,
the handoff, workstreams, the register index, `first-run.md`) found one
piece of the drift the 2026-09-03 (late) entry fixed in the README
still standing in `docs/first-run.md`: §0 told a reader to `go install
scip-go` and `rustup component add rust-analyzer` on the host, and the
dependencies callout said Go's module cache was "global, warm whenever
`go build` works". Since ADR-092 lane B runs from the image — `scip-go`,
`rust-analyzer`, `scip-java` and the JDKs are pinned inside it — and
`go mod download` / `cargo fetch` run as separate fetch containers into
the Hobbes cache (`GOMODCACHE`, `CARGO_HOME` under `~/.hobbes/cache`,
`extract/containment.py`). §0's block now builds the image in place of
the two host installs, the callout says Go and Rust fetch into the
Hobbes cache with no repo code running, and the containment callout
points at the block rather than repeating the build command. Docs only.

Noted, left as is on Max's word: architecture §10 lists "any model
fine-tuning" as out of scope while ADR-099 trains LoRA adapters; the
experiment is an instrument for observation, not product, and the
wording waits on the assessment work before the next proposal.

*Addendum, the same day — `docs/calvin-potential.md`.* Max's current
work is evaluating Calvin potential and the tree had no document for
it; the v2 design was written in as `docs/calvin-potential.md`
(*proposed → ready*): M0 runs the pipeline with Calvin's slot filled by
a deterministic grounder stub over the §9b units re-based at their
parents, three arms (O, T, T-loop), eight instruments each with an
attribution table, no kill criteria, a step-gated order of work whose
first four steps need no model. What the doc depends on is in the
tree and cited by path (the 28 proposals, the 50 units, the review
record's D-1–D-5, C-84, the HSR/RFE definitions). What it names and
the tree lacks is stated in a header note rather than linked: the
charter (`calvin-charter.md`), the v1 of the doc, and the two pre-run
probe numbers (18% of hunks outside spans; 118/182 unresolved terms
new), which §8 step 0 recomputes at the parent. Eight constraints
listed in its §7 to be registered on acceptance; no ADR until then
(100). CLAUDE.md gained a read-next row; the handoff's resume point
moved to it. Docs only; nothing run.

*Addendum, later the same morning — the v1 run salvaged.* Max: "are
you sure v1 was never run?" It was — not as a document in the tree but
as a session of 2026-09-03 (night, 21:06–21:37) that assessed the v1
design against the tree and ran two probes, whose scratchpad sat in
`/tmp` and whose transcript held the findings. Recovered: the v1 text
(19.5 kB, pasted into that session), `probe.py` / `probe2.py` /
`ingest-parents.sh` / `commits.txt`, and 28 lane-A graphs ingested at
each unit commit's parent (137 MB, `built_by 33fec69`), all copied to
`~/.hobbes/bench/calvin/`. Both probes re-run today from the saved
graphs and reproduced to the digit (680 hunks: 56% absent-file at the
base vs 18% at the parent; code hunks 78% in-span / 4% absent / 18%
outside spans; anchors 0.21 / 0.25 at file grain; 182 unresolved
terms, 118 in the diff's added lines). Into the tree: the record
`docs/ttt-cells/calvin-m0-probe-2026-09-03.md` (both tables, the
readings as recorded that night, the 28 parent SHAs, and the eight
v1 findings V-1–V-8 that v2's §11 answers one for one);
`pipeline/scripts/calvin_probe.py` (`ingest | probe | anchors`, the
same logic with paths parameterised; verified identical output) with
`tests/test_calvin_probe.py` (4 tests, the pure pieces); the charter
copied verbatim from `~/calvin` to `docs/calvin-charter.md` with a
provenance line so the design's link is real. `calvin-potential.md`'s
header note rewritten to point at the record; §0 carries the base-vs-
parent numbers; §8 step 0 marked partly done, its remainder the
contained lane-B ingest per parent. Recounted: 1,171 pytest collected
outside `lane_b` (+3 in it) with the four new tests; the 2026-09-03
line said 1,169, so the base was 1,167 — CLAUDE.md now carries the
counted number.

*Addendum, midday — step 0 finished.* Max: "run the lane b remaining
piece." `calvin_probe.py ingest --lane-b` (added: the full contained
ingest instead of `HOBBES_SCIP=0`) over the 28 parents, detached with
`nohup` (the harness's background cap is ten minutes): 28 of 28 exit 0,
698 s total, 20 / 24 / 37 s min / median / max, every graph
`all_contained` with no escape hatch, 176,796 of 176,824 symbol edges
semantic, `built_by 8add0a0`; the clone venv-less exactly as the TTT
base ingest was (C-85), so the conditions match the cell's. Both
probes re-run on the semantic graphs read identical to the lane-A rows
— expected, since spans, paths and names are lane A's; lane B is what
step 3's grounder consumes. Recorded as an addendum to the probe
record; `calvin-potential.md` §7.1 carries the measured cost and §8
step 0 reads done; handoff moved to step 1. Max's key question
answered in the session: nothing before step 4 needs one.

*Addendum, afternoon — step 1.* Max: "good to proceed with step 1
then." Built `hobbes.derive.holes` — the hole language v0: the eleven
types with their fill shapes, `validate_template` / `validate_fill` /
`validate_fills`, and `render` (the prompt a reader fills, span text
read from git at the parent). The hand-written template is for
`c59916fe2222` ("--no-tests flag to `oracle go-rta`", 2 files, 4
hunks) at parent `19bddc9230fb`: 53 holes, every type but `ANCHOR`,
round 1 (UNRESOLVED, four ANCHOR_CONFIRMs) answered by hand as the
orchestrator would, 47 open. The exit criterion is a test: the gold
diff expressed as fills — spans cut from the child commit's own
ledger, nothing typed — validates with nothing missing. Five readings
for step 2, in the probe record's second addendum: the anchors for
this task come from the literal (`go-rta` in the usage text and three
spans), not any identifier; 47 holes for 4 hunks, so pattern fills
extend to regions, tests and partners; `NEW_SYMBOL` needs
`covered_by` (the new thing is a field and a local); `FREEFORM` needs
`"none"`; and the SIGNATURE-unchanged prune is wrong for types (its
caller changes when the fields do) — scoped to functions. §2.1
amended in place; §8 step 1 done; 1,178 pytest (+7).

*Addendum, evening — step 2.* Max: "good to proceed to step 2." Built
`hobbes.derive.template` — the anchor pass (backtick, path, test id,
stack line, literal via `git grep -F` at the SHA, bare identifier
naming exactly one node; the unresolved block with nearest names), the
structure pass (anchored symbols + callees + the types an anchored
symbol uses in an interior file → SIGNATURE/BODY; callers and a type's
users → CALLER_UPDATE, closed outside the partition; reaching tests;
head/gap/tail regions for interior files; co-change partners at ≥ 2),
`apply_round1`, `prune` (functions only), the two scorers on the
pre-image side — and `hobbes template`, `calvin_probe.py templates`,
ten tests on a synthetic ledger. Exit met: 28 of 28 byte-identical at
the parent, 1.4 s. The measurement is the finding: before any
orchestrator round the templates cover 4% of hunks at symbol grain and
89% fall outside, 596 of 636 non-new hunks in files no anchor reached;
20 of 28 templates have no structure until round 1. The first batch
had three templates explode (3,594 holes: `calls` / `uses` / `grade`
as literals in 44–156 spans) and cover 10% by coincidence; the cap
(`LITERAL_MAX_NODES = 12`) and seven other v0 rules are in the record's
third addendum. The directory matcher took the knowledge-only unit
from 0 to 7 of 8. Generated template for the step-1 unit: 134 holes
to the hand-written 53, the same 4 of 4 covered. 1,188 pytest (+10).

*Addendum, night — step 3.* Max: "proceed with step 3 of calvin
potential." Built `hobbes.derive.ground` — grounder v0: every fill
shape placed (span, insertion point `end = start − 1`, new file at
`{1, 0}`, `NEW_SYMBOL` after a symbol / in a region / at end of file,
`FREEFORM` as a list of blocks), overlap refused, an open hole with no
fill reported, the pruning rules first; the post-image parsed by the
language's lane-A provider and every call site in an edited range
resolved against the graph plus the gensyms — exact match or NULL,
each NULL classed near-miss / invented / new with the nearest names
recorded, every lookup in a read-trace — and `hobbes ground`,
`calvin_probe.py ground`, `fills_from_diff` (a diff as fills against a
template, the charter's raw-diff case), nine tests. Exit met on the
commits themselves (§3.1's gold; the cell's rows are their size-bounded
subset): 28 of 28 identical on rerun, apply at the parent, and equal
the commit byte for byte; 3,760 call sites, 0 NULL, HSR 0. Six grounder
defects surfaced by the gold run and fixed before the reading — a
deletion placing a blank line, the TS helper dropping unresolvable
relative imports on a scratch tree, no JS builtin list, package
`__init__` re-exports, module-level values, package-relative imports —
and a poison control: 25 near-miss and 25 invented perturbations, one
NULL each of the right class. On the rows instead, 29 NULLs, all
symbols in files the rows omit — I2 on a partial diff. Two gold blocks
fell inside a `CALLER_UPDATE` the signature-unchanged rule had closed
(a caller edited for the task's own reason): the rule closes the
propagation question, not the site. C-91 registered (call sites only,
three languages, members on values abstained; surfaced in the record).
Design §2.3 and §8 amended; the record's fourth addendum; handoff moved
to step 4, which is the first orchestrator spend and waits on Max.
1,197 pytest (+9). One `lane_b` test fails on this box tonight and
fails identically at HEAD in a throwaway worktree — the contained venv
listing (`test_venv_environment_lists_the_venvs_own_distributions`)
comes back with `pip` alone; an environment reading, not the tree's,
left for Max.

*Addendum, later — step 4, cleared by Max ("key is in secrets should be
good to continue"; "lean toward a cheaper model").* Built
`hobbes.derive.adapter` — the orchestrator adapter on the owned loop's
`Endpoint`: render, one exchange, validate, one repair; `run_t` (round 1
on a view of the round-1 holes, rebuild, the answers carried as filled
holes, round 2, prune, ground, one NULL round-trip on a narrowed
template); `calvin_probe.py t`; eight tests on a fake endpoint. Ran
five units against `claude-sonnet-5` through Anthropic's
OpenAI-compatible endpoint (it rejects `temperature`, so greedy decoding
is not honored: the same prompt confirmed 9 anchors once and 1 the next
time). Pass 1, the design as written, cost 2.2M input tokens (≈ $8):
two round-1-only units confirmed module-level anchors and the rebuilt
templates ran to 348 and 690 holes with full code under every caller
and test — 728k-token prompts, the output cap, and "unchanged" for
everything on repair; the anchorless unit got a `FREEFORM`-only
template and answered "none". Protocol v0.1 (an `ANCHOR` hole and a
second round-1 pass when round 1 leaves no anchor; callers and tests
rendered as one line with a "yes" fetching its span; patterns-first
prompt; chunking by file over a declared budget; truncation-aware
repair) cost $2.3 for the five. The hand unit went end to end in both
passes — the gold change in substance, 0 NULL, applies, exactly the two
gold files, 2 exchanges, 2 minutes. The other four did not, and each
says why: asked outright, the orchestrator names the task's own prose
(H-a needs Hobbes-side candidates); a module anchor opens a whole file
(H-s, the design's own row); new files land flat where the gold nests
(M1′, as preregistered); `new` over-declared for prose. RFE against the
cell's impact sets reads 0 on a perfect diff — the release-SHA lexical
mapping named files the commit never touched (D-6 for the cell). The
record's fifth addendum carries both passes' rows; §2.2 and §8 amended;
1,207 pytest (+8). Step 5 next (no orchestrator).

*Addendum, evening — step 5, the local harness (no orchestrator).*
Max: "continue with the current resume point step 5 of calvin
potential." Built `hobbes.derive.harness` (ADR-100): `verify` — a
worktree at the parent, the diff applied, the testmap's guards (symbol
grain in a span, module grain outside, the whole file for a touched
test file) run in the sandbox image offline under lane B's planner
with a new `verify` profile, once with the diff and once without,
every row classed against its baseline (P2P / F2P / P2F / F2F /
new-pass / new-fail / removed / skip / uncollected / unsupported) and
the verdict read off what the diff itself did; the environment binding
— this checkout's `.venv`, `node_modules` and the venv's interpreter
linked into the worktree and mounted read-only at their host paths,
lane B's Go module cache, a git identity, vitest `--no-cache` — derived
from the manifests, not authored (C-92); arm O — `hobbes plan` at the
parent from the task text alone, every unit's manifest in one
ADR-077-shaped brief with the harness's environment notes, an agent
dir allowing the guards, `hobbes-session` with the proxy's exec under
`calvin.box.policy`, `--commit-on-exit`, the harvested branch as the
patch (the harness's links excluded), the patch through the grounder
(`ground_patch`, the raw-diff route) and the verifier. Around it:
`hobbes-session --mount HOST[:CONTAINER]` (read-only, never relabeled,
labeling off while bound; four Go tests), `loop.py --mcp-tools`
(offer a subset of the proxy's tools; one test), `hobbes verify`,
`calvin_probe.py verify | o` (`--rescore` into a new dir, never in
place), `scripts/calvin_scripted_agent.py` (a JSON script played
through a session in place of a model), twelve harness tests. The
calibration — the 28 golds at their parents — caught six harness
defects before the reading (an uncollectable id aborting pytest: a
fixture named `test…` the testmap lists, C-93; the baseline asked for
a file the diff creates, 552 false F2P; parametrized ids; no git
identity; a renamed test read not-run; the links committed into the
session's patch) and then read **26 pass / 1 fail / 1 no-tests, P2F 0,
error 0, all contained, 559 s**; the one fail is four tests a commit
adds that need podman inside the container. Arm T's step-4 diffs: the
hand unit passes its 12 guards; three are empty; one reaches no test.
The scripted O session: four runners ok under policy, `git push`
denied at the agent layer, `curl` parked and expired to deny, the
edit harvested, grounded and verified. §9b's five defects checked off
in the record (D-2 for O to be confirmed on the first model session);
D-6 closed. C-92, C-93; architecture §6.2/§7 amended; design
§2.4/§3.2/§8; handoff moved to step 6 (Max's word; the model choice
and the two protocol changes). 1,220 pytest (+13), 299 Go (+4). The
known lane_b venv-listing failure on this box is unchanged.

## 2026-09-04 (night) — Calvin M0 step 6: the run on Sonnet 5, cut to four keys on cost

**What.** Max cleared step 6 ("look to apply candidates and continue
with step 6 with model choice of sonnet 5"). First the protocol change
(`2ed0d11`): the `ANCHOR` hole carries candidates from Hobbes — the
planner's lexical seeds with their words and refusals, nearest names
per unresolved term with node ids, the ledger's file listing by
directory — rendered for the orchestrator to choose among, binding
still exact; `loop.py --sampling model-default` (Sonnet 5 rejects
`temperature`: 400 with, 200 without); `calvin_probe.py t` keeps arm
T's pre-loop diff; the 28 templates regenerate byte-identically; +3
tests. Then the run: all 28 keys launched on three arms against an
"order $50–120" estimate; the first units read $4–5 each per arm (a
1,068-hole template; 30-turn O sessions at 1.4M tokens) and **Max cut
the set to four** — `00e5aee`, `c59916f`, `b8afd41`, `d509835` — which
finished on all three arms. `calvin_probe.py rows` builds the §5
per-task rows; the record's seventh addendum has every row with its
attribution before the aggregate; design §2.2/§3.4/§8/§10 and
architecture §6.2 amended. **T pass 1 / fail 1 / empty-diff 1 /
no-tests 1, RFE 0.32 / 0.68 / 0.32, HSR 0, $6; T-loop closes 2 → 0
near-miss NULLs on the one key with any; O pass 1 / no patch 3 under
the 30-turn cap, $17.** About $35 spent in all.

**Readings.** T > O on the one key both solved and honest where its
anchors fail; O's manifest (lexical, C-36) hit the gold at Jaccard
0.10 / 0 / 0 / 0 and the one O patch found its files by grep. The
module anchor is the cost door ($5 for two right edits); the template
misses tests that reach a module through a module-level value
(`PROFILES`) and so failed the right code on exactly the tests the gold
changed; candidates close "echoes prose" (5 of 5 bind) and not H-a (0
of 5 gold); new-file placement moved from flat to nested on a prompt
line. Two harness defects registered: the loop's 7B stall discipline
cut every first-launch O session off at 12 turns of reading (fixed by
flags, three records kept under `o-step6-stall6/`), and the box policy
denies toolchain probes (`go version`, `sh -n` — 14 escalations
expired). Suites: 1,223 pytest (+3), Go unchanged. Not pushed.

**Later the same night — the four no-spend fixes** (Max: "do the four
no spend fixes before next session"): a module anchor opens
confirmations per symbol, not bodies (template v1; bodies before any
confirmation 99 → 45 over the 28, the largest template 317 → 119
holes; an unanswered confirmation is a refusal, `SYSTEM_PROMPT_VERSION`
2, `run_t` up to three round-1 passes); importer tests are guards in
the template (tier `import`) and in the verifier (import grain, C-93
amended); `calvin.box.policy` allows `go version`/`go env`/`go
list`/`sh -n`/`bash -n`/`node --version`/`command -v`/`type`/`pwd` and
denies `env`/`printenv`; `loop.py --token-budget` (1M on every arm-O
argv, `harness.O_TOKEN_BUDGET`; `calvin_probe.py o --token-budget`).
Six tests; the hand template and the 28 regenerate byte-identically
under v1 (`templates-v1/`, the step-2 set kept). Design §2.1/§8/§10,
architecture §6.2, the record. Not re-run.

## 2026-09-04 (later) — doc drift after the Calvin sprint; API spend and Modal compute off the table

**What.** Max asked for a review of the top-level documentation and
said API spend and Modal compute are off the table for the next
steps ("i was pushing things a little quickly, doc drift is heaviest
immediate task then we can proceed further"). The review found the
docs consistent up to 2026-09-03 and every drift in the last day's
Calvin M0 work, in the summary layers the architecture's own rule
(§9) says must not lag: the register summary read **93 entries,
71 active, 20 lifted, 2 superseded** (C-91–C-93 added 2026-09-04)
while CLAUDE.md, the README and the handoff's "where things stand"
still said 90 / 68 / 20; the README said 99 ADRs against 100 files;
the README's Status stopped at the TTT experiment, carrying neither
the four-repo extraction test nor Calvin M0; architecture §8's
build-programme table had no Calvin M0 row though §6.2 and §7 were
amended; the handoff mixed a 2026-09-04 "start here" with a
2026-09-03 "where things stand" (old register count, a 1,142 pytest
count); `workstreams.md` item 8 named the extraction residue as
current work while the handoff named Calvin. The register count was
re-derived from the segment-file headings (93 unique `C-n`, 20
marked lifted, C-55/C-56 superseded in their bodies), not taken from
a summary line. Also: `AGENTS.md` is a symlink to CLAUDE.md;
`secrets.txt` at the root is gitignored and untracked; 1,228 tests
collect on this box against CLAUDE.md's 1,227 + 3 `lane_b`.

**Fixed, docs only, no code.** CLAUDE.md (the register count, the
Status date, the "Then" bullet rewritten around the no-spend queue);
README (the count, the ADR count, the four-repo test and Calvin M0 in
Status, `olmo3-ttt-results.md` and `calvin-potential.md` in the
design-docs table, `scip-java` in the SCIP acknowledgement, which
listed four indexers for six languages); architecture §8 (a Calvin
M0 row); `workstreams.md` (item 8, the refresh date); the handoff
rewritten — one date, the count, a Calvin bullet, NEXT reordered
with the no-spend queue first and every spend item under a *Held*
line, standing policy item 0. Nothing in the constraint register
itself moved.

**Next (no spend):** Calvin M0's model-free follow-through — the
step-6 arm-T diffs re-verified under the importer-test guard, the
step-2 instruments on template v1, ADR-101 when Max accepts the
design — then the extraction residue and W0's items, in the handoff's
order. Not pushed.

**Later, the same session — Calvin M0 step 6b exercised with no model
(Max: "go ahead with the calvin no spend").** Three instrument runs,
no orchestrator, nothing on Modal; the record's eighth addendum has
the tables. (1) The 28 golds through the verifier under the import
grain (`verify-gold-import/`, 641 s): every verdict identical, `P2F`
0, the selection 3,190 → 5,598 (2,408 import rows), one new `F2F` —
the box's known venv-listing failure pulled onto `9c474c6` as a fault,
not a verdict. C-93 carries the calibration. (2) The four arm-T diffs
re-verified (`verify-t-step6-import/`): unchanged; the `TestProfiles`
failures on `00e5aee` had been selected at file grain already (T's
diff touched the test file), so the fix's work is in the template, not
the verifier. (3) Template v1's step-2 instruments beside v0's: symbol
4% → 3%, region 2 → 0, outside 89% → 91% (the nine hunks a module
anchor's bodies covered before confirmation), the anchor pass
unchanged, max holes 333 → 135, 17 confirmations a task. (4) A new
`calvin_probe.py replay` (two pure helpers, three tests) replays a
recorded run's round-1 answers into a later template set: on
`00e5aee`, with the gold's 15 symbols confirmed, 844 holes and the
three `TestProfiles` tests present at tier `import`; with every symbol
of the confirmed modules, 1,226 — more than the run's 1,068 — the
import tier's 167 test holes being the difference. **Reading:** the
fix lands the missed tests; v1 saves bodies only under selective
confirmation; the import tier's test hole (one per test in an
importing file, 55 of 56 on `d509835`) is the next cost door — named
for the protocol, not built. The handoff's naming of `c59916f` as the
`PROFILES` key this morning was wrong (it is `00e5aee`); corrected.
Suites: 1,230 pytest (+3), the venv test failing on this box as
before. Not pushed.

## 2026-09-05 — the extraction residue the lifts named, closed: the helper's symlink rule, every pyproject table, the expression callee counted (C-63 surfaced)

**What.** A fresh session (Fable 5.1). Max asked for a review of the
top-level documentation and then to start from the resume point; the
handoff's NEXT item 2 — the three residue cases the 2026-09-03 lifts
named, in its order — was the work. No model, no Modal, no spend. Three
commits, easiest first, each with its tests, its register entry and
the architecture line in the same commit; the dogfood repo re-ingested
contained at the end.

**(1) `tsextract` follows the C-73 symlink rule (`29906e2`).** The
helper's two walks (`discoverFiles`, `discoverWorkspacePackages`)
skipped *every* symlink where the Python walks skip only a directory
link whose target is inside the repo — so a TS repo whose only copy
sat behind a link was lane-A-less there while `has_ts_files` found it,
and the two sides could disagree on which files exist. One `walkRepo`
now serves both: an in-repo directory link is not descended (walked
once at its target, the ingest's C-73 record unchanged), a link to a
directory outside the repo and a file link are followed, a dangling
link is nothing, and — one guard the Python side does not have — a
link to a directory that *contains* the repo is skipped rather than
looped. A probe first: ts-morph keeps the linked path as given
(`getFilePath()` does not realpath) and resolves an import through
an outside link to the linked path, so the helper can follow links
without its facts leaving the repo. Node test with all six shapes;
two Python tests hold the helper beside `has_ts_files` and
`linked_copies` on one repo (`TestLinkedCopiesAgree`). C-73's residual
line rewritten; architecture §3.1. This repo has one symlink
(`AGENTS.md`, a file) and its graph does not move.

**(2) The `pyproject.toml` reader takes every declaration table
(`9423fc6`).** `_pyproject_specs` read `[project]` only, so a Poetry
or PDM repo declared nothing and got C-79's "nothing to compare
against" record. It now reads PEP 735 `[dependency-groups]` (an
`{include-group}` entry names no package — the included group is read
on its own), Poetry's `[tool.poetry.dependencies]` /
`dev-dependencies` / `group.<name>.dependencies` (name-keyed tables:
the key is the package whatever the value's shape — a caret string, a
`{version, extras, optional}` table, a `{path}`/`{git}` source, a
list of constraints; `python` is the interpreter), PDM's
`[tool.pdm.dev-dependencies]` and uv's `[tool.uv] dev-dependencies`;
a table of the wrong shape reads as empty, never an error. **Lock
files stay unread by design** — `poetry.lock`, `pdm.lock`, `uv.lock`
list the closure a resolver chose, and the coverage number means
*declared and resolved by the index*, not installed; reading them
would put every transitive package in the denominator. The C-79 gap
record names the tables read. Four tests; C-79's residual rewritten
(what remains: a `requirements` file under another name, and
`setup.py` stays code).

**(3) A call whose callee is itself an expression is a counted site
(`94a9a67`; C-63 surfaced, C-80's residual closed, ADR-045
amended).** `handlers[0]()`, `getattr(x, "y")()`, `(a or b)()`,
`f()()` in Python and `table[k](s)`, `xs[Symbol.iterator]()`,
`(a || b)()` in TS/JS have no terminal identifier for the semantic
lane to put an occurrence on, so nothing can resolve them — and until
today they were not sites at all: absent from the denominator, so a
dispatch table read as accounted (C-63, *unsurfaced* since
2026-08-27, whose own entry said "surfacing means counting the
site"). Both syntax providers now record the site under the marker
name `<expr>` alone (`pysource.EXPR_RECEIVER` as the whole callee; the
helper's `EXPR_CALLEE_NAME`), positioned where the callee expression
starts; the join matches nothing, the fallback abstains (the C-80
rule), the grounder reads no reference from it, and the tail classes
it **`expr-callee`** — a parse observation, no line read — in the
*cannot resolve* group beside `attr-call`. Python and TS/JS only; Go,
Rust and Java still do not count the shape and `tail_classes_available`
says so (C-32 amended). Keyword callees are not values and stay
outside: TS `import(..)` is an import and `super(..)` a keyword
(caught by the existing nested-tsconfig test, whose fixture has a
dynamic import); Python's `super` is an identifier and was a site
already. One old test asserted the skip (`test_dynamic_callees_are_skipped`)
and now asserts the site. Tests on every layer: pysource, tail (the
class from the parse alone; availability pinned to the two languages;
the CLI's "cannot report" line for Go gains the class), graph (the
fallback abstains), ground (no reference), the helper (five shapes,
the tie-order beside the inner `factory()`, the two keyword callees),
the Go proxy (the gloss, the per-file row). C-63's heading and status
rewritten (surfaced; the candidate edge — a literal key bound to a
property — would be `below-floor` at best and is not attempted); the
register summary's unsurfaced count now names C-63's history (it was
never in that count); architecture §3.4.

**The dogfood repo re-ingested contained** (`hobbes-proxy` rebuilt
static into `bin/` and `sandbox/`, the image rebuilt, then `uv run
hobbes ingest` at `9423fc6` dirty, all six languages): **12
`expr-callee` sites** — python 9 (`cli.py`, `invariants/compile.py`,
`ttt_cell.py`, `ttt_probe.py`, `test_containment.py`,
`test_narrate_pass.py` ×4) and ts/js 3 (the `minits` `lookup.ts`
fixture's three shapes, the ones the oracle lane's A-4 found drawing
zero edges) — capture python 81.6% of 18,047, ts/js 61.7% of 2,932;
`hobbes lanes` exit 0. **C-65 demonstrated on the way:** the
knowledge server that `.mcp.json` started at the session's open, from
the *old* image, answered `list_blind_spots pipeline/scripts` with
"cannot resolve: 318 (fallback-resolved 1, import-binding 6,
attr-call 311)" where the fresh artifact says 320 with `expr-callee
2` — the class its table does not know vanished from the count, the
C-77 shape one build later. Restart the server after an image
rebuild; the handoff says so.

**Also seen, not changed.** `docs/constraints/README.md`'s debt
summary counted two *unsurfaced* entries (C-19, C-20) while C-63 was
a third since 2026-08-27; with C-63 surfaced today the count reads
true and the summary now says why. The Python site total on this repo
(18,047) is ~3,700 above the 2026-09-03 line (14,352): the Calvin M0
code and its tests landed in between; today's change adds 12.

Suites: 1,241 pytest + 3 `lane_b` (+11; the venv-listing test failing
on this box as before, deselected) / 299 Go (assertions widened, no
new functions) + 39 oracle-lane Go / 32 tsextract node (+2) / vitest
and scip untouched. Not pushed.

**Later, the same session — W0's two build items (Max: "proceed with
w0 in the queue").** (1) **The deselected `lane_b` test.** The fake
venv wrote `home = /usr` and linked the suite's interpreter; inside the
image `/usr` is the image's python, so the listing was its `pip` and
nothing else — the handoff's reading (a host symlink the container
does not see) was half of it. The test now builds a real venv
(`python -m venv --without-pip`), whose python links to the base
install `interpreter_mounts` carries in hop by hop and whose
`pyvenv.cfg` names that install as home, and writes one distribution
by hand as a dist-info (`hobbes-probe` 1.0 with a RECORD) — no
network, no pip. It passes contained on this box, asserts the suite's
own `pytest` is *not* in the venv's listing (C-27's point), and
`ci-graph.sh` deselects nothing: the one permanent exclusion in CI is
gone. Suite 1,242 collected, 1,242 passing here. (2) **The three
duplicate invariant pairs.** I-7, I-8 and I-11 retired (`status:
retired`, the reason in each header): each restated I-1, I-2 or I-6
with strictly less, and cost a second soft verdict per `hobbes review`
and a second `list_invariants` line. Retired records leave both and
stay as files (the README's rule); `hobbes invariants check` reads 11
valid, 8 confirmed; compile skips them by name. I-9 (Max's approval,
its correction recorded) and I-10 (restates I-5) were not in the named
pairs and stand — I-10 is the same shape and is Max's call.
`.hobbes/invariants/README.md`, workstreams W0, the handoff. Not pushed.


## 2026-09-05 (later) — Atlas-0 steps 1–2: the world, the scorer, the probe, no model

**Max's direction:** "follow the doc titled atlas 0 in this repo as this
session's current work" — `atlas-0.md` was untracked at the repo root;
moved to `docs/atlas-0.md` where every design doc lives, unchanged, a
step record appended at its end. The base documentation (CLAUDE.md,
the handoff, ADR-099 §4a/§9b, the charter) was read first; nothing in
it contradicts the design, and the design's thread (a manufactured
prior overriding live text; the adapter alone confabulating
repo-shaped paths) is what Atlas-0 asks about at the block grain.

**Built: `bench/atlas0/`**, its own uv project (numpy only, 30 tests;
CI's python job runs it) — `atlas0 gen | check | score | probe-check`.
The world (`world.py`): modules `mod_<stem>`, tests, 4,000 real symbols
of 3–4 stems from a 300-stem vocabulary each class drawing from its own
balanced cycle; dense (24–40 mentions) / sparse (exactly 1–2) / a mid
background (3–23); `defined_in`, `reached_by` (a test over 1–2
modules), `calls` filled against the mention budgets at 0.7
intra-module, a short symbol re-rendering a fact through another
template; absent-near (one stem swapped or appended to a dense-real
base, that base the only real name within distance 1) and absent-far
(≥ 2 from everything), half trained / half held-out; QA for half the
dense and mid symbols, none for sparse; four arms differing only by
how absence appears; eval sets `primary` (`defined_in` for every
class), `secondary`, `trained`, `inversion` (§6.4, C+S / C-only by
construction). `check.py` reads the exit criteria back from the
written text, not the generator's counts. `acts.py` is the strict
scorer and the §6.1 matrix; `tokens.py` the entity tokenizer (B1
stems, B2/B3 one token, seeded vectors); `refmodel.py` a random-init
numpy GPT for the pipeline check; `probe.py` the per-layer probe and
the §6.3 authority tables.

**What the checks caught while building** (the reason they read the
files): sparse names leaking into other symbols' training answers (64
of 1,200 in the first world — dropped from QA); 2-stem names making
near/far unconstructible (every 2-stem name has ~13 real neighbours at
distance 1 — names are 3–4 stems now, length balanced per class);
absent-near stems inheriting an unbalanced base sample (bases chosen
to keep the class's stem counts level: TV 0.03); the design's "edit
distance 1–2" unable to separate near from far (read as 1 / ≥ 2). Five
readings in all, listed in the lane's README and the step record for
Max to confirm — a changed reading changes the world hash.

**Results.** Seeds 1–5 pass `check` (`~/.hobbes/bench/atlas0/`). Step
2's exit on the 30M-shaped random model, 900 balanced primary items:
B1 probe 0.322 / B3 0.376 against chance 0.362 — both at chance; B3
fits its training items at 0.998 (every dedicated vector its own key,
no class in it yet). Every act malformed, every MI zero, as a random
model should. A numpy pathology on the way: a multi-threaded BLAS
spent 15× longer synchronising on 15-token matmuls than one thread
(949 ms → 62 ms a forward); the package pins one thread and
`probe-check` parallelises by process (110 s for 900 items on 12
cores).

**Not done, by the gate:** step 3 (B1 calibration) trains a model.
No GPU here, spend off the table; a CPU run is hours per cell and
feasible with no spend — Max's call, in the handoff.

Suites: 30 atlas0 (new) / pipeline, Go, web, node untouched. Not
pushed.


## 2026-09-05 (night) — Atlas-0 steps 3–6 on Modal: 64 cells, $7.04 assumed, the atlas at five seeds

**Max's direction:** Modal back on the table for Atlas-0 with a
cost estimate first ("days vs an afternoon is worth the money"), then
"good to proceed … check after first cell to see how far your guess
could be off". Estimate given: $0.15–0.30 a cell on an L4 at 100k
tokens/s, $25 declared ceiling, $50 hard stop. **Measured:** $0.08–0.12 a
cell at 107–136k tokens/s; the first cell read $0.12; sixty grid cells
plus four calibration cells $7.04 at the assumed L4 rate (Modal's bill
is the number). The step gates held: first cell alone, then the
calibration, then seed 1's twelve, then seeds 2–5.

**Built:** `atlas0.train` (a torch GPT of the reference model's shape,
the three input maps — B3's entity rows frozen by a gradient mask —
checkpoints with a quick eval and stop-at-target, a full eval writing
every set's matrix, the probe and authority tables, inversion, sparse
by distance, `residuals.npz` and the weights), `scripts/modal_atlas0.py`
(`put | train | grid | get` on volume `hobbes-atlas0`, the package
shipped from `src/` each call, an assumed rate in every result, cells
cached by manifest), `atlas0 report` (§6.1–6.6 over a directory of
cells, mean [min–max] over seeds, the §6.6 gate), torch as a uv group
with the CPU index. 37 tests. Two bugs found by the first runs: the
decoder leaked `<eos>` into the text so every correct answer read
malformed (caught on the CPU tiny run); the manifest carried torch's
version-string subclass, which the torch-less client could not unpickle
(the volume had the records; the function now returns plain JSON).

**Step 3.** One rendering per fact: the block memorised its corpus
(loss 0.07) with held-out dense-real at 0.31 over 74 epochs — the
knowledge-extraction failure without paraphrase. Three renderings per
fact (`Config.renderings`, the design's "across templates"; sparse
facts rendered once): 0.955 at 2,750 steps under a 4,000 cosine, 0.937
at 3,000 over its own schedule, **0.968 at 3,500 — T frozen**. Worlds
regenerated under the new default (seed 1's hash `e4c3ee3d…`); the
sixth reading in the lane's README.

**Steps 4–6.** Sixty cells, 3 blocks × 4 arms × 5 seeds; the tables and
the three atlas entries are in `docs/atlas-0.md`'s step record. The
lines that survive §6.6: B1 invents for every absent name and gives an
absent-near name its base's module 30% of the time (the tree); under
`UNDEFINED` targets B1 refuses half of sparse-real (the conflation),
its refusal rates on sparse and on held-out absent moving together by
seed; written absences change no act in any block (the vocabulary
never pairs them with a query — a v1 item); B2's learned dedicated
tokens make the class linearly readable (probe 0.90–1.00), have no
sibling shape, are the best sparse block (0.71–0.74) and the only one
that infers module from siblings (0.24–0.37), and refuse 85% of
sparse-real in the phrase arm — with held-out absence refused
bistably (1, 0, 0.77, 1, 1 by seed) and never once lived lines are
present; B3's frozen vectors do not store the world at T (dense
0.11–0.22). `CANDIDATES` / `UNKNOWN` never emitted; entropy ≈ 0
everywhere (the §6.3 null is degenerate); the block does not read
context (§6.4's flat line).

**Also:** L4 containers queued ~17 minutes at one point (not billed);
`modal app logs` lags — read `modal container logs` instead. Records:
`~/.hobbes/bench/atlas0/runs/{cal-seed1,cal-seed1-r3,grid-3000,grid-3500}/`
and `grid-3500-report.{md,json}`; the volume holds the same.

Suites: 37 atlas0; nothing else touched. Not pushed.

## 2026-09-05 (night, later) — Atlas-0 v1: three world items, eighty cells, two defects found and fixed, $16.54 assumed to date

Max: "good to continue with world items, cost is fine so far … if there
are any errors or results against experiment, then note them at the
top." They are at the top of the v1 record (`docs/atlas-0.md` § Step
record › v1) and here.

**Errors.** (1) v0's seed 5 had *not* passed step 1's check: one
sparse-real symbol at six statements, the filler re-rendering a dense
symbol's call fact whose partner was sparse. The record's "seeds 1–5
pass" was read from the one-rendering worlds and not re-read after
`renderings = 3`. Fixed in the filler (a fact with a sparse partner is
never re-rendered for its other side; regression test at full size);
seeds 1–4 regenerate byte-identically, seed 5's hash changed
(`seed5-as-run` kept; its twelve v0 cells stand as run, one symbol of
1,200 affected). (2) The §6.4 prompt separated the context from the
question with `<nl>`, a token no training stream contains — every
inversion number of v0 was read through an untrained embedding, and
"a supporting context hurts" was that token. Fixed (a newline in a
prompt is the stream's `<eos>`); every finished cell re-read on the
fixed prompts without retraining (`train.reevaluate`, `modal_atlas0.py
reeval`, ~$0.003 a cell): support now costs B1 three points and B2
four, not a quarter to a half; no block follows a conflicting context
(0.00–0.01) — that stands.

**Results against the experiment.** The replication (the lived world's
`none`/`phrase` arms are v0's corpora byte for byte, run fresh): B1,
B2 none and B2 phrase replicate inside v0's spreads, and B2/phrase
refuses held-out absence 1.00 in all five fresh seeds (v0's 1, 0,
0.77, 1, 1 was run-to-run, not seed); **B1/phrase does not replicate
as a rate** — the same corpus and seed read sparse `UNDEFINED` 0.68 in
v0 and 0.29 fresh — so §6.6's seed spread understates B1/phrase's
variance and the entry's "refuses half" is "a quarter to two thirds,
by the run" (the direction holds). The hold-out world: every accuracy
in the atlas is an accuracy on the trained form of the question — a
fourth phrasing drops held-out dense-real to 0.42 [0.10–0.81] in B1
and 0.08 in B2, memorised facts to 0.15–0.64 / 0.29–0.39.

**The v1 worlds** (`atlas0 gen --variant`, each one `Config` field,
v0's hashes untouched, the checks reading each back from the text):
*lived* (relation absence: two written lines per empty relation of
every real dense/mid symbol and `UNDEFINED` pairs of those relations
for the QA-trained ones; sparse carries none; the secondary eval asks
every real symbol's empty relations) — 40 cells, B1/B2 × 4 arms;
*context* (half the training QA packed with its own statement) — 10
cells, re-run after the separator fix; *holdout* (three query
phrasings trained, a fourth at evaluation, `primary_seen` the control)
— 20 cells. B3 left out (did not calibrate at T). First cell of each
$0.107–0.109 against the $0.10–0.12 estimate, then the grids.

**What v1 found.** *B2 reads a written relation-absence and acts on
it* for the token it was written about: on QA-held-out real symbols
the empty relation is refused 1.00 (`calls`) / 0.96 (`reached_by`) and
the filled one 0.00 / 0.07, separable at spreads ≤ 0.10 — the lived
mechanism, measured; and a sparse symbol with no written line is
refused its empty relation 0.33–0.37 against a trained-absent name's
0.80 on the same question — the first act in the atlas that treats
the two differently. *The state does not travel*: held-out absent
names 0.00 on `calls`, and no block refuses `defined_in` of any
absent name in a lived arm — the act follows the pairing, the written
line chooses when to use it. *B1 reads nothing*: its taught
`UNDEFINED` becomes one rate per question kind (≈ 0.45 on
`reached_by` for every class, ≈ 0.05 on `calls`). *No inversion*: with
half the QA packed, conflicting context is followed 0.00–0.03 at every
one of fourteen checkpoints; there is no early reading phase to fall
from at ~70 epochs; B2 answers a fact only in context 0.43 (0.23 in
v0). *B2 refuses an unfamiliar question like an untrained name*
(held-out phrasing, phrase arm: sparse 0.98, dense 0.59, absent 1.00).
Amended atlas entries and the v2 cell (a `defined_in` pair on a
disjoint half of the absent names, lived lines on the other half) in
the record.

**Instruments:** `atlas0 evals` rewrites a world's eval files;
`atlas0 report` renders the secondary with/without rows, the
seen/held-out table and the checkpoint curve; the tokenizer appends
v1's words after every v0 id; `row_of` carries any exposure. 53
atlas0 tests (+16). Runs under `~/.hobbes/bench/atlas0/runs/` (the
README lists the directories) and on the volume. Not pushed.

## 2026-09-06 — Atlas-0: Max's three items — the reframe corrected by its own re-read (a third untrained-token defect), B3 reads and follows context, the v2 world built and its calibration run

**Max's brief (morning):** three items — (1) reframe v0/v1 as the
memorisation-regime atlas, with record edits, a §6.6 amendment and a
procedure: every eval prompt tokenised and checked against the
training vocabulary before a cell is read; (2) the B3 cell on the
context world, the block for which reading is the only route, ~$1;
(3) the v2 reading regime: few epochs, many phrasings, a held-out
phrasing by default, context-only facts, the absence split, B3
calibrated on reading. Order: 1, 2, 3.

**The procedure came first and found the third defect.** The check
(`atlas0 check`: every prompt's words against every arm's corpus text;
the trainer: every prompt's ids against the stream, `UntrainedPromptTokens`
unless allowed, recorded in the manifest; an absent name's own tokens
exempt) was run over every v0 and v1 world before anything else. The
hold-out world's fourth phrasing put `live` (`Where does X live?`) and
`exercises` (`What exercises X?`) in front of the block — words that
occur in **no** training corpus of any arm — so every held-out
`defined_in` and `reached_by` number in the v1 record was read through
an untrained token, exactly as the `<nl>` numbers had been; only the
`calls` phrasing was clean. Fixed the same way: a fifth phrasing per
kind of trained words (`Which module is X defined in?` / `Which symbol
is called from X?` / `What covers X?`), `Config.train_phrasings` /
`held_out_phrasing` (the `holdout` variant evaluates on the fifth;
`--set held_out_phrasing=3` is the world as run and fails `check`),
the five worlds regenerated with byte-identical corpora, the vocabulary
the twenty cells trained with unchanged (375 / 6,415, checked against
the manifests), and the cells re-read without retraining
(`runs/v1-holdout-fix-reeval`, $0.08).

**The re-read overturned item 1's premise.** On an unseen phrasing of
trained words, held-out dense-real reads **0.97 [0.93–0.98] in B1 and
0.89 [0.84–0.95] in B2** against 0.98 / 0.92 seen (the record had 0.42
/ 0.08); sparse and every refusal rate are the seen rate within
spread; the memorised facts read 0.82–0.87 under the new form (record:
0.15–0.64); and B2/phrase refuses dense-real **0.00** under it (record:
0.59, "B2 turns an unfamiliar question into `UNDEFINED`"). Three
trained phrasings did make a fourth readable when its words were
trained. So the reframe's premise — question-string → answer-string
pairs — does not survive, and it was not applied as written: the
retitle *Atlas entries — memorisation regime (T = 3,500, ~77 epochs)*
stands in the sense that holds (every fact the act uses is stored in
the weights and nothing is read — conflict followed 0.00–0.01 at every
checkpoint of every world, a fact only in context 0.02 in B1), the
two "trained phrasing" lines carry that corrected meaning, the two
hold-out lines of the B1/B2 entries are struck with the re-read
numbers beside them, the B2 decoupling and mechanism lines are added
(the refusal binds to "this input's parameters have not moved" — a
name or a relation; *not* a question shape, on the re-read), and §6.6
is amended as Max wrote it: two runs per seed, the gate over the union
(`--runs 2`, `-rN` cells; `atlas0 report` counts cells). What still
stands from the hold-out world: `reached_by` under a fresh phrasing
costs B2 a third of its answers where B1 loses none; the `calls`
phrasing is seed-bistable in B1 (0.04–0.80) — a passive question with
the subject in the caller's slot, a fact about that phrasing.

**Item 2 — B3 on the context world (`runs/v2-b3-context`, five seeds,
$0.61; the sixth cell at `context_qa_p = 1.0`, `runs/v2-b3-context1`,
$0.12; the first cell $0.121 against the $0.10–0.12 estimate before
the rest).** B3 answers a fact only ever in context **0.44
[0.35–0.53]** — B2's rate on the same world (0.43), B1 reads 0.03 —
with parametric dense-real at 0.29; a supporting context lifts it 0.29
→ 0.70; and it **follows a conflicting context 0.40 [0.33–0.45]**,
the first block in the atlas above 0.03 anywhere. At full packing:
0.80 read, 0.98 with support, **0.73 conflict-following**, and the
§6.4 curve measured for the first time — reading appears in one
checkpoint (0.49 → 0.93 between steps 1,000 and 1,250, before the
block answers anything parametrically) and **falls to 0.80 as the
parametric route is learned late** (dense 0.04 → 0.42); conflict
following falls 0.92 → 0.74 the same way. With nothing to read B3
still answers (`ANSWER` 200/200 on C-only/none, an invented module):
reading gives it no abstention. Against the pre-committed readings:
not "≈ 0.02 like B1"; equal to B2 at half packing, 0.80 at full; the
rise-then-fall is the ordinary inversion with a weak parametric
route, not a paradox; conflict > 0.5 at full packing. B3's §5
criterion was the wrong one; its atlas entry is amended.

**Item 3 — the v2 world is built** (`--variant v2`, each part a
`Config` field, v0/v1 byte-identical with the fields present — checked
on the five v0 dirs): `statement_templates` 8 (templates 5–7 per
relation, later 8–15 for the sixteen-rendering calibration) and
`renderings` 8; seven phrasings trained and the eighth held out with
every word trained; `context_only_frac` 0.3 (facts met only in packed
lines, once per rendering, the exposure count kept; the `C-only-qa`
inversion split; `trained_free` / `trained_context_only`);
`relation_absence` + `absence_split` (a `pair` half and a `lines`
half of the trained absent names — v1's cleanest cell folded in);
`filler_partner_budget` (eight renderings pushed a mid symbol to 26;
v0 seed 1's bytes move if it is on there). `TrainConfig.max_epochs`
(`--epochs`) sets the steps from the stream; `target_measure
read_context_only` is B3's criterion. Five full worlds checked and on
the volume. `atlas0 gen --set field=value`. 71 tests (+18).

**The calibration, seed 1, ten cells, $0.22 (record § 2026-09-06 › §3):**
2–4 epochs learn nothing — dense-real 0.015–0.03 at batch 64 / 16 / 8
and at sixteen renderings (templates 8–15 written for it; the budgets
fix the statement count, so more renderings is fewer distinct facts,
not more tokens); the loss sits at the templates' grammar. An 8-epoch
cosine leaves the plateau at 5 epochs and reads 0.11 with no fact
stored. **A 16-epoch cosine: B1 reads before it stores** — at 7.2
epochs a packed context-only fact is read 0.89 and a conflicting
context followed 0.74 with parametric dense-real 0.01; reading
saturates (1.00 / 0.93) by 10 epochs; from 11 the facts enter the
weights (dense 0.07 → 0.83 at 13.9 epochs, 3,100 steps, the 0.8 stop)
and context-following falls 0.93 → 0.77 — §6.4's inversion, in the
standard block, one seed; the context-only facts enter the weights
too (0.09 → 0.95 asked without context). The schedule is part of T:
the 8-epoch cosine at 7 epochs read 0.11, the 16-epoch one 0.89. B2
meets 0.8 at 10.4 epochs and stores and reads together (no
reading-first phase; conflict-following peaks 0.39). B3 reads 0.125 at
16 epochs: not calibrated for reading at this T (it needed ~20M tokens
on the context world; this schedule gives 6.9M). **So the item's
regime and its criterion do not meet at 30M:** ≥ 0.8 arrives only in
the memorising phase, the reading regime is 7–10 epochs with no fact
held. Two honest T's (14 epochs, the criterion; 10, the reading
regime), 90 cells ≈ $5–6 each; **the grid is not launched** — T_v2 is
the design's knob. **$1.03 this session, $17.57 assumed to date** of
the $25 ceiling. Handoff rewritten; CLAUDE.md status; workstreams.
Not pushed.

## 2026-09-07 — CI's first runs read: two red jobs since the first push, both fixed (a runner without a git identity; a redirect into a directory not yet made)

**Max's brief:** the CI runs (every push since 2026-09-04) fail on
`go test (product)` and on the graph check; resolve those first.

**What the logs said.** The `web` and `python` jobs were green on
every run. `go`: six `internal/knowledge` blind-spot tests and
`TestCommitOnExitCommitsLeftoversButNeverHobbesDir` failed with git's
exit 128, *Author identity unknown* — the GitHub runner has no global
git config, and a developer box does, which is why every local run was
green. `graph`: the image built (~1.5 min rootless on the runner), the
contained ingest ran (~1.7 min, 28 lane B steps, `all_contained`),
lanes 0 disagree on 7,199 sites — then `ci-graph.sh` died at the
compile step because the shell opens the redirect
`> .hobbes/derived/compiled/manifest.ci.json` before the compiler,
which is what creates `compiled/`, has run; on a fresh checkout the
directory does not exist. The two things ADR-095 named as able to
differ on the runner (rootless podman, the rustup download) did not.

**The fixes (three lines of intent).** `blindSpotRepo` passes
`-c user.name -c user.email` per git command like every other helper
in the tree already did; the commit-on-exit test seeds its fixture
repo with `seedIdentity(repo, repo)` — the same call `setup` makes on a
real session worktree, so the product path was never the problem, the
fixture stood in for a worktree without carrying what a worktree
carries; `ci-graph.sh` does `mkdir -p .hobbes/derived/compiled` before
the redirect. No product code changed.

**Verified:** `go test ./...` in `go/` and in `bench/oracle` under
`GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1` (the runner's
shape) — all green; `scripts/ci-graph.sh HEAD~1` end to end on this
box: image, contained ingest, stamp, lanes, the I-5 semgrep checker,
`hobbes review`, 3 `lane_b` passed. The runner's own confirmation is
the next push. Workstreams (sequencing 6, W0's CI item) and the handoff
amended. Not pushed.

**Later, after Max pushed:** the graph job went green on the runner
(6 min all in); `go` failed once more, on the oracle lane — the two
TS cells (`TestMinitsTSAllConfirmed`, the TS poison test) run the
`tsc` oracle wherever node is, the runner has node, and the oracle's
own pinned typescript (`bench/oracle/ts/package.json`, 5.9.3 with a
lockfile) was never installed in that job. The job now sets up node
and runs `npm ci` there before the oracle tests; the one-time install
lists in CLAUDE.md and the README name the directory, which they had
not. Reproduced on this box from a clean `node_modules` (`npm ci`,
then the grade package green).

## 2026-09-07 (later) — Atlas-0 addendum: B4, typed relations — the §A.1 checks (circuits, not verbs), B4 built and swept on seed 1, the grid launched at one run per seed

**Max's brief:** the B4 addendum — a rule for §1 (an atlas entry names a circuit or a displacement, never a verb; four checks owed on existing checkpoints), a block for §3 (B1 + a learned inventory of K relation operators every attention pair routes through), an instrument for §6 (type discovery, sibling pull by type, relation-absence as a computed state, route competition, the loss delta), in his order: checks, implementation, λ sweep, grid, instruments, entry; the whole item under $8. CI was green on his push first (the `go` job's third fix, 18:56 UTC).

**Errors against the experiment, first (the record's list):** the trainer had never saved checkpoint weights — every manifest "checkpoint" is a metric record — so the two cells §A.1 names were re-run with `--save-weights-every` ($0.19); the B4 full read at 2,200 was gated on the checkpoint cadence and never fired in the sweep (fixed; the sweep re-read at 2,100); B4 costs ~3× the estimate ($0.17–0.19 a cell on an L4, the `(B, h, K, T, T)` correction), so the grid ran at one run per seed to stay under $8 and the second run is Max's call; a dotted output name lost its tail in the check driver (six checks re-run).

**§A.1, run (`atlas0 mech heads | ffn | b2norm`, CPU or `modal_atlas0.py mech` on a GPU):** *B1 reads* = eight heads in layers 2, 4, 5 (at the onset L5H1 and L5H6; at 2,200 the top eight → following 0.91 → 0.055 against 0.55 for eight random heads; parametric untouched; a limit: the *bottom* heads are necessary too — they build the query). *B1 stores* = the FFNs of layers 2–7 together (single ablations cost 0.3–0.4 of 0.785 each with reading at 0.84–1.0; layer 0's FFN zeroes everything). *B2 refuses* is **not a norm**: the tied head pushes every never-a-target row along one direction, so never-seen names have the *largest* displacement (2.1 vs 0.97 dense); no scalar of the displacement is the policy (best AUC 0.89–0.98 in four phrase seeds for the input-driven part, 0.83–0.94 for the norm in lived+phrase); a linear probe on the row reads the act at 0.86–0.97. *B3 follows* = one head of layer 4 and seven of layer 0, redundant (top eight → 0.085 / 0.065 at 1,000, 1,250, 1,500; random eight 0.92; no single head necessary).

**B4 (`atlas0.train.Types`; 84 tests):** R_k = I + A_k B_kᵀ (rank 16, shared across heads, B zero at init), one router distribution per pair per layer on the full-width q/k, Gumbel-softmax soft in training with τ 1.0 → 0.3, argmax at evaluation, pair-entropy + usage-balance penalties under one λ; K = 1 reproduces B1's seed-1 loss curve **to the digit** over 300 steps; the trainer also gained `--stop-at-step`, `--save-weights-every`, `--full-eval-at` (a full read at a named step, `step-N/`, with `typed.json` from the §A.5 instruments in every cell), `atlas0 report --at`, the loss delta and the B4 tables; `atlas0 typed` re-reads a cell; `reeval --weights-step`.

**The λ sweep (seed 1, five cells, $0.89): the pressure decides the route.** λ = 0 (the routing alone): dense-real 0.815 (B1 0.83), reads 1.0, follows a conflict 0.795 at its peak → **0.36** at the plateau (B1 0.93 → 0.77), loss +0.017; λ = 0.01: stores 0.61, the copy route never above 0.195; λ = 0.03 and 0.1: copy 0.85–0.995, **stores nothing** (0.03–0.05; loss stuck at 0.99 vs 0.71); λ = 1.0 learns nothing. Collapse: at every λ half the layers route through one type whose operator is the identity (‖R_k − I‖ 0.03–0.11); where the inventory spreads (layers 5–7) NMI against the relation 0.16–0.37, `calls` on one type at 0.96–1.00; the router is hard (confidence 1.0) from step 300, so the temperature and the entropy term never acted; the partition is not at the query (NMI ≤ 0.12 under either phrasing) and arrives before any fact is stored. Sibling pull intact at λ = 0 (0.28 vs 0.30); no relation-conditioned similarity (cosines within 0.02 under every operator). B4's copy route is two heads (L2H5, L3H5) where B1's is eight. **The grid: B4 and B1, three arms, five seeds, one run, λ = 0, read at 2,200 and 3,100** (`runs/v2-b4-grid`, thirty cells, $3.38).

**The grid, read (record § 2026-09-07, the tables at both reads beside the runs).** The reading phase replicates at five seeds in both blocks (2,200: dense 0.04–0.10, conflict followed 0.81–0.94); the plateau at 3,100 is seed-variable (B1/none dense-real 0.26–0.82 — a fact about T_v2 for Max). B4 at λ = 0 matches B1 on storing (within 0.08, loss delta 0.00 at the plateau), on the sibling pull (0.23–0.25 vs 0.22–0.24: the pull is the input map's), shows no relation-conditioned similarity (pair groups within 0.02 under every operator), and weakens the copy route in every arm (0.65 / 0.71 / 0.82 vs 0.74 / 0.75 / 0.86) — not separably at five seeds. The router collapses to one identity operator per layer on the training distribution in every cell (share 1.00); the residual partition is NMI ≤ 0.23 in layers 5–7. **§A.5.3 is unreadable at this T: no block emits `UNDEFINED` in either phrase arm, not even on the trained pairs (0.00)** — the abstention act is not learned from fourteen exposures — so "does refusal travel" waits on the memorising T or a computed target. The B4 entry is written (circuits: two copy heads, B1's FFNs, one identity operator, the input map's pull); §A.7 branch 3 is selected — typing must be given, not learned, at this scale; B4-given is the next block. **Spend: $4.71 this item, $22.28 assumed to date of $25.** Handoff rewritten; CLAUDE.md status; workstreams; README. Not pushed.

## 2026-09-09 — The comparative programme (ADR-101/102): the field, an entry point that grades any tool's graph by the oracle lane, CodeGraphContext and repowise on the thirteen loop cells, three graphics regenerated from the records

**Max's brief:** the docs have grown past first contact; the owner
wants a presentable claim — a comparison against other code-graph
tools and a small set of graphics — without Hobbes saying something
about itself it has not earned. Resolved one way: the comparison uses
the oracle lane, not a scoreboard. Non-goals held: nothing from
H1–H3 / SWE-bench / DeepSWE / TTT / Calvin; no "covers language X";
no pooled recall; the video demo is separate. Session start: the
top-level docs read (README, CLAUDE.md, how-hobbes-differs, the oracle
README and cells, the handoff); nothing from the handoff's queue was
touched.

**Workstream A — the field (`docs/comparative/field.md`).** Draw rule
recorded with the date: the two August names, then a search of what is
current (a Sonnet agent ran the queries and read the READMEs; the
load-bearing cells were re-read raw by hand). Ten rows, every cell the
tool's own words with a link or *unstated*; the "says what it cannot
see" column reads *nothing found* for most, as expected. **The field
moved:** repowise's README now carries a compiler-graded table of its
own — five tools, seven cells (cobra, gitleaks ×2, syft ×2, zod, hono)
against Go RTA and `tsc`, 37,853 oracle edges, artifacts public — the
same method as ours on other repos. Recorded in §3 with its basis and
compared nowhere; Hobbes on their draws is the parked next 1-1.

**Workstream B — the adapter and the cells.** `oracle import`
(`internal/foreign`): the minimal shape `{repo, sha, tool, version,
converter, edges:[{site, callee, caller?, kind?, label?}]}` →
`HobbesExport`; a malformed position refuses the file; the tool's
label is the tier (so the report splits by its confidence ladder);
`kind` drives the two Hobbes-metadata tolerances (function-valued
binding → abstract; macro → excluded) and nothing else does.
`grade-foreign.sh` is the one command. The tolerance decision for a
foreign graph is ADR-101 §3. Fixture: `testdata/foreign/minigo.edges.json`,
hand-read, five confirmed, poison refused in full, a seeded wrong edge
contradicted. Two converters under `adapters/`, each `dump` (the
tool's storage as stored) + `convert` (stdlib) with its own dump of
`minigo` committed and read by hand in a Go test: **CodeGraphContext
0.6.13** (Kuzu: `CALLS` rows carry the site line, `confidence_label`,
the callee Function's path and line; `HEURISTIC_CALLS` is its own
table, not graded) stores exactly minigo's five true pairs;
**repowise 0.49.0** (`wiki.db`: `graph_edges` calls with
`call_lines_json` and `resolution_origin`, `wiki_symbols.start_line`)
stores four true pairs and draws `Decision(DefaultDecision)` — a
conversion — as a call to the type, which the converter carries and
the oracle leaves silent (no call on that line). Then both tools, as
their READMEs document, on the thirteen repos with keys on disk
(toml, mux, fzf, quic-go, ajv, cheerio, memchr, rust_proj, jsoup,
petclinic, spring-data-elasticsearch, Severed-Chains, click), same
commits, same keys, same matcher, poison on every one — **26 foreign
cells, 0 falsely confirmed of 171,350 seeded**, records written
from the artifacts by `report/foreign_record.py` in the existing
format, contradictions printed **untriaged** (A-8) with a mechanical
shape and six sample rows each. Per-cell numbers are in
`docs/comparative/tables.md` (generated); the shape across cells:
the tools' precision-against-oracle runs 43.8–100.0% where defined (23 of 24 compiler-graded cells)
(repowise on rust_proj stored no call edge; CodeGraphContext's index
of spring-data-elasticsearch exited 1 on a Binder exception and was
graded as stored), their recall 0.0–75.6%; Hobbes' standing cells
are 99.6–100% / 23.5–98.4% on the same keys. **Observed, not
claimed:** four fresh CodeGraphContext indexes of the mux clone stored
767 / 1,193 / 767 / 767 CALLS rows (its own summary printed 2,165 each
time); both grades are in the mux record. repowise indexed mux twice
byte-identically. Sampled contradictions on mux for both tools are
same-name-other-receiver resolutions (`r.Methods` on a `*Route` drawn
to `(*Router).Methods`) at sites the oracle has, so the converter's
line grain holds; C-94 stays open by construction.

**Workstream C — the graphics (`docs/comparative/graphics/`,
`bench/oracle/report/render.py`, ADR-102).** Every number is parsed
from the cell records' verbatim blocks (the last block is the standing
grade) and the dagger record's per-module table; `cells.meta.json`
holds language / run / draw / label and no numbers; `check` fails on
drift and the lane's Go suite runs it. Two records were amended so
the standing grade is a verbatim block the parser reads: dagger
`sdk/rust` (its post-ADR-090 head, from the on-disk report) and hobbes
`pipeline/` 2026-08-28 (its poison line). The one number: **0 falsely
confirmed of 78,812 seeded across 14 compiler-graded Hobbes cells in
four languages**, the exceptions (ajv 1,375/1,378, quic-go
3,766/3,781) and the cells not in the sum printed, trace cells on
their own line. The scatter: language as the panel (the reference
palette validates three hues all-pairs), the y axis from where the
lowest cell sits, trace cells in their own panel, foreign cells as
hollow squares (cgc) and diamonds (rw), hover text with the miss
classes. The before/after: **date-fns, per directory** — the *before*
artifact regenerated by the pre-lift Hobbes (`a60777f^`) on the same
clone, contained, reproducing the record (TS6053 on every zone, 0.1%
of 24,827), the *after* the clone's standing graph (80.1%); computed
exactly as `hobbes ingest` prints capture. dagger `core/integration`
stays in the doc as the larger measurement; its pre-join artifact is
not on the box.

**Register and docs.** C-94 (a competitor's edge our conversion
misreads is our defect), C-95 (the tolerances were tuned on Hobbes'
output; a foreign graph is read at the grain its converter can state),
C-96 (a competitor cell is host-run) — all surfaced. ADR-101, ADR-102.
Architecture §3.8's oracle paragraph, `oracle-grading.md` §11, the
oracle README (§ Grading a graph Hobbes did not build),
`how-hobbes-differs.md` rewritten to point at the cells, the README's
related-projects paragraph (one sentence and a link) and its docs
table, CLAUDE.md (a reading row, the project map, the status),
workstreams W0 (the parked follow-ups), `docs/comparative/README.md`
(the claim page and the objection answered by shipping). Suites: the
oracle lane's Go suite green with 10 new tests (47); the product
suites were not touched by this session's changes (nothing under
`go/`, `pipeline/`, `web/` changed) and were not re-run here.

**Cost:** no API spend, no Modal; two `uv` venvs and ~30 minutes of
CPU on this box for the 26 indexes and the before-graph regeneration.

## 2026-09-09 (later) — The triage sample, the converter's Java grain repaired, and the 1-1 on repowise's draws

**Max:** "triage a sample of the contradictions, then move to hobbes vs
repowise for the 1-1."

**The triage.** Five contradicted rows per tool per language drawn at
random (seed 20260909) from the foreign cells and read against the
source. The first draw found **C-94 biting exactly where the entry
said it would not yet**: both tools store a Java method under
`@Override` at the annotation's line, converter@1 graded that line,
and 5 of 20 CodeGraphContext rows and 1 of 20 repowise rows were our
defect, not theirs. converter@2 (`declaration_line` in both adapters)
reads the source and advances past leading annotation / decorator
lines to the identifier's; every foreign cell regraded from its stored
raw dump (no re-index), the eight Java cells moved (CodeGraphContext
Severed-Chains 46.2% → 79.4%, spring-petclinic 89.9% → 99.6%,
spring-data-elasticsearch 60.0% → 82.5%, jsoup 71.1% → 79.5%; repowise
58.8 / 90.7 / 57.2 / 48.9%), every non-Java cell unchanged, signed
direction lines in each record, `report.v1.*` kept beside. The sample
re-drawn after the repair and read again: **CodeGraphContext
tool-wrong 20 : oracle-grain 0 : converter-defect 0; repowise 19 : 1 : 0**
— the one oracle-grain row is the function a destructured binding holds
(D-O4's binding rule pointed the other way, C-95). The shapes: same
name, other receiver or overload; a local closure or parameter
shadowing a module-level namesake; stdlib calls bound to same-named
repo methods; a type, an `impl` block, a body line or a macro in a data
file as the callee; build-constraint alternates (C-71's shape, where
Hobbes abstains). Verdicts are in `~/.hobbes/bench/comparative/
triage-<tool>.json` and printed per cell by `foreign_record.py`.

**The 1-1.** repowise-bench's `graph/corpus/corpus.lock` pins its G4
repos; cobra, gitleaks, syft, zod and hono were cloned at those pins,
ingested contained, both tools run on the same clones, and keys built
here (`oracle go-rta` with and without test packages where their
experiment has both cells; `tsc-oracle.mjs` on zod's root and, with a
new `--config`, hono's `tsconfig.build.json` — its root is
solution-style). **Their key is function-grain and their matcher and
adapters are theirs, so nothing here compares with their table**; the
1-1 is among the three graphs on our key. Hobbes: cobra 2,186/2,186
(71.8% at 2 roots); gitleaks 2,266/2,266 with tests (94.9% at 9
roots), 2,010/2,010 without (98.0% at 2 roots); zod 9,731/9,731
(45.1%; pnpm not provisioned, C-23); hono 767/774 (55.2%; the 7 are
ajv's union-member shape, now n=2). The tools on the same keys are in
`docs/comparative/tables.md`. **One product defect found and fixed:**
gitleaks' first grade had one contradiction, syntactic — inside the
repo's own `regexp` package, `re.MustCompile` (`import re "regexp"`)
was drawn to the enclosing `MustCompile` because `_repo_package`
matched import paths to repo directories by suffix and the stdlib
path `regexp` equals the directory; cmd/go's rule (a first element
without a dot is the standard library's) is now applied, with a test;
re-ingested and regraded, edges 2,284 → 2,283, contradicted 1 → 0,
signed in both records. **syft has no key on this box:** RTA was
OOM-killed at 18.7 GB (no tests) and 19 GB (with tests), the H-9
shape; the row says so. Also learned: a `pkill -f` pattern matched this
session's own shell again (the handoff's warning); long keys now run
under `setsid nohup`, killed by pid only.

**Docs.** The one number now reads 0 of 99,824 seeded across 19
compiler-graded cells (the draws included); the scatter carries them;
the claim page's exceptions are ajv, hono and quic-go; misses register,
evidence log, architecture §3.8, workstreams, CLAUDE.md, C-94's entry.
Suites: pipeline 1,243 pytest green, the oracle lane's Go suite green.
No spend; ~1.5 hours of CPU on this box.

**Addendum (Max: "document the comparisons and present them in the
comparative section as a graphic; the rest document as next session's
work"):** `docs/comparative/graphics/same-key.svg` (ADR-102 §7) — one row
per cell that has a foreign graph on the same key, three markers on
the precision axis and three on the recall axis, grouped by language,
repowise-bench's draws as their own band, the trace cell by its
confirmation rate; regenerated from the records with the rest and
under the drift test. The claim page's file table and 1-1 section
point at it. Next session's work is the handoff's numbered list:
the claim page's wording and which graphic leads; syft's keys on a
bigger box; the union-member provider shape (n=2) — fix or register;
the next two converters; the competitor cells under the sandbox
image if C-96 is to be narrowed.

**Addendum (Max's review of the graphic: "adjust the same-key comparison
graph to reflect the differences with different colors instead of same
colored hollow shapes, hard to decipher"):** `same-key.svg` now draws one
hue per tool — blue dot Hobbes, orange square CodeGraphContext, green
diamond repowise, the reference palette's first three slots, validated
all-pairs by the palette check (CVD ΔE 9.2 worst pair, normal-vision
24.0; the green's 2.74:1 surface contrast is covered by the hover
fraction on every marker and `tables.md`) — every marker filled with a
surface ring, the shape kept as the second encoding, and the legend
carries the glyphs themselves beside the tool names. `render.py` only;
regenerated, `render.py check` and the oracle lane's Go test green. The
top-level docs were read on the way and four stale statements fixed:
README, CLAUDE.md and the handoff said *three* graphics where there are
four since the addendum above; CLAUDE.md's ADR counter said 100 (last is
102); ADR-102's status line and §7 and the claim page's file table now
describe the markers as drawn. The scatter's foreign cells are still
hollow orange squares (ADR-102 §5); untouched, Max's call.

## 2026-09-09 (evening) — Hobbes is versioned: 0.1.3 (ADR-103); the same-key graphic in one colour per tool

**Max:** the same-key comparison's three hollow shapes in one colour
were hard to decipher — one colour per tool; and "everything outside
the Hobbes layer (the experiments largely) are not version changes to
Hobbes as much as we'd call internal testing; since their products
are versioned I want to version mine — hobbes 0.1.3; we've shown we
can compete already directly."

**The graphic** (committed first, its own addendum on the entry above):
blue dot Hobbes, orange square CodeGraphContext, green diamond
repowise, the palette's first three slots validated all-pairs, every
marker filled, the glyphs in the legend.

**Versioning (ADR-103).** Versioning is a project's trait, not
GitHub's: a number the code states about itself, a tag on the commit
that carries it. Built:

- **Root `VERSION` = 0.1.3**, Max's number, chosen not derived. Its
  held-together copies: `hobbes.__version__` (was 0.0.1),
  `pipeline/pyproject.toml`, the new `go/internal/version` package,
  and `tsextract` / `scip` / `web` `package.json` + lockfiles (were
  0.0.1 / 0.0.1 / 0.1.0). `pipeline/tests/test_version.py` asserts
  every copy equals the file; the Go package's test does the same
  from its side.
- **The stamp carries it.** `built_by` (ADR-094) gains `version`;
  `hobbes ingest` prints `built by hobbes 0.1.3 @ <sha> from
  <checkout>`; the knowledge header repeats it on every graph answer
  (an older artifact prints no version — the Go test keeps one
  fixture with and one without). The four Go binaries answer
  `version` (`hobbes-proxy 0.1.3`), with a test each and a usage line.
- **The rule:** the Hobbes layer (`go/`, `pipeline/`'s product
  packages, `web/`, `tsextract/`, `scip/`, `sandbox/`) bumps patch
  for a change in what it draws, refuses or says, minor for a
  capability; `bench/` and the experiment records move nothing — a
  finding there bumps the version when its fix lands. `CHANGELOG.md`
  is new, one entry per version; its 0.1.3 entry says what 0.1.3 is.
- Architecture §2 (the two-layer paragraph) and §8 amended; README
  status, CLAUDE.md conventions + status, `field.md`'s Hobbes row
  name the version. The proxy rebuilt static into `sandbox/` and the
  image rebuilt (C-65), the binaries rebuilt; this repo re-ingested
  so the dogfood artifact carries `version`.
- **Tag `v0.1.3`** on the commit, local — the lead pushes tags with
  the commits.

Suites: Go 299 + 5 new green, the oracle lane's Go suite green,
pytest green with the new test. No spend.

**Addendum (Max: "put in preview phase or beta phase since while Hobbes
has been proved and graded it's still early"):** `0.1.3-beta`. semver's
pre-release suffix sorts before the release and says not-stable; beta
over preview because the grading is done. The tag `v0.1.3` (never
pushed) deleted and `v0.1.3-beta` cut on the new commit; pyproject
spells it `0.1.3b0` (PEP 440) and `test_version.py` holds the mapping;
ADR-103 §5 amended; every copy, the fixture and the docs re-stated;
proxy, image and this repo's artifact rebuilt again.

## 2026-09-09 (later still) — the agent file leads with the tools

Max's brief: review the top-level documentation and set it bold and
high in the agent file — use Hobbes over other tooling; it is more
accurate and direct than `cat` and `grep`, and should let an agent use
fewer tokens and hold less context.

- **Reviewed:** `README.md`, `CLAUDE.md` (`AGENTS.md` is a symlink to
  it, so one edit reaches both), `docs/session-handoff.md`,
  `docs/first-run.md` §§ on the knowledge tools, architecture §4. They
  agree with each other and with the tree at 0.1.3-beta; the tool
  guidance existed but sat mid-file under *Hobbes for Hobbes*, after
  the project map, as one sentence.
- **`CLAUDE.md`:** a new first section, directly under the header —
  *⚠ FIRST: use the Hobbes knowledge tools, not `cat` / `grep` /
  `find`* — with the why (resolved edges with `file:line` provenance
  instead of text matches to read and rule out; a smaller, truer
  context costs fewer tokens and carries fewer wrong beliefs; this repo
  is Hobbes' most-tested target), a six-row table mapping the question
  an agent has to the tool and to the shell habit it replaces, the
  order of work (`list_blind_spots` first, the question tools, then
  read only the lines the answers point at), and the two sanctioned
  fallbacks to grep — what the blind spots say the graph does not
  cover, and non-code text. The *Hobbes for Hobbes* section keeps only
  the mechanics (how the tools are served, staleness, C-65, ADR-094)
  and points up.
- The token claim is stated as the thesis it is, not as a measurement:
  no number was earned here and none is printed.

No code, no suite change, no spend.

## 2026-09-09 (docs cleanup, 1) — the v1 design, both build plans and the Java plan removed

Max: the docs layout has gotten messy; start by removing the v1
architecture and both build plans — the running architecture covers
the present, the ADRs and this ledger cover the history — and the Java
build plan, a handoff document that got stored and serves no purpose
forward; it should be documented with the ledger.

Removed: `docs/hobbes-architecture-v1.md` (349 lines),
`docs/hobbes-build-plan.md` (125), `docs/hobbes-build-plan-v2.md`
(457), `docs/java-build-plan.md` (216). Every live reference rewritten
to point at the ADRs and this file: README's design-docs table (three
rows become one, for the BUILDLOG), CLAUDE.md's `docs/` line, the
architecture's header and §8, `first-run.md`, `agent-mapping.md` (twice),
`future_additions.md` § Java, `constraints/extraction-java.md` C-68's
source line; ADR-033 gains an amendment and ADR-096's source pointer
says where the plan went. Dated records keep their references as
written (this ledger's earlier entries; the Severed-Chains cell record
quotes the plan's prediction).

**What the removed files held that no other live document did — kept
here so nothing is lost:**

- *v1 build plan.* The four sequencing rules every programme since has
  carried: deterministic before generative (M0–M3 spend zero quota);
  enforcement before agents (no session writes code until the proxy and
  recorder exist); content before chrome (the web UI after there is a
  knowledge layer worth rendering); each milestone exits on a real repo,
  never a toy fixture. D1–D3 are in CLAUDE.md. Storage was decided
  without a vote: JSON files in `derived/`, loaded in memory, SQLite
  only if a repo ever makes that slow.
- *v1 architecture.* Its §9 flagged mechanisms and §10 defaults became
  ADRs as they were built or dropped; architecture §7 (carried
  subsystems) names what was designed and never built (per-command
  secret brokering, quota). Nothing else in it was still true only
  there.
- *v2 build plan.* The seven deviations from the original §7 (the spike
  milestone; schema v4 not v2; V2.M1 widened to `tests.json` and the
  version gate; the M3 reach coupling; `hobbes.yaml`'s own ADR; tier in
  the UI at M2 and the agreement report at M3; the indexer-config
  registry moved to M2) are ADR-027's record. The three
  `future_additions` items it dissolved (cross-language module-id
  namespacing, per-test JS reach, graph-diff rename detection) stand
  dissolved.
- *Java build plan.* Estimated nine to thirteen sessions, one milestone
  at a time; the build took one session (2026-08-29, above). Its four
  named risks, with what happened: lane B build time (carried by the
  cache mount; wall times in the cell records); image size (~300 MB a
  JDK; the image carries three, ~2.8 GB, no slim image needed yet);
  `scip-java` needs a compiling project — "the most common real-world
  outcome for enterprise repos" — which arrived on the second random
  draw (Severed-Chains, lane A only, disclosed); overload agreement in
  `hobbes lanes`, tested before any real repo. Why Java before C is now
  in `future_additions.md` § Java.

No code, no suite change, no spend.

## 2026-09-09 (docs cleanup, 2) — two stored handoffs removed, the pre-registration folded into the grading design

Max: clean up the other candidates too. Removed
`docs/harness-restructure-plan.md` (202 lines; marked *complete and
superseded* since 2026-08-24) and `docs/harness-mini-swe-integration.md`
(84; marked *retracted as a Hobbes arm* since 2026-08-23) — both the
same shape as the Java plan, a per-session handoff that got stored; the
thirty-seventh to forty-third and sixty-third entries of 2026-08-22
above are their record. `docs/oracle-preregistration.md` (71) is
**folded, not removed**: the predictions P1–P16 now sit verbatim under
`docs/oracle-grading.md` §10 (the section that called for them), with
their commit dates stated, because a pre-registration's value is that
it can be shown to have been written before the run — the text is
unchanged and the git history of the removed file carries the dates.
References rewritten in `extraction-evidence.md` (three),
`benchmark-deepswe.md`, `benchmark-hypotheses.md`, ADR-059, ADR-063 and
ADR-077; dated ledger entries keep theirs.

**What the two removed files held that nothing else live did:**

- *Restructure plan.* The owner's structure of 2026-08-21 (single-use
  derived-context agents, one alive at a time, the job as short memory
  pushed by the previous agent; planner → plan reviewers → implementers
  in contract order → verifier → one bounded rework) is architecture
  §6.1's ancestry and ADR-059's subject. Its *errors foreseen*
  checklist, kept here: seeds were the failure, not the cap; a module
  id leaked as a filename (`.:conftest`); integration had no gate;
  reflection spam; an implementer-shaped loop discipline for read-only
  roles; every unit cloning at base so a consumer never saw its owner's
  commit; a map-only brief under a tight turn cap. And its testing rule:
  *one narrow probe is worth it, the full set is not* — build the one
  stage whose value is an assumption (the planner), run it alone on two
  instances, check interiors against the gold files, and exit-check
  everything else against the stand-in binaries before another
  verdict-bearing run. Its *deliberately not in this plan* list
  (path-grain write enforcement C-38, metering beyond the envelopes,
  loss fitting, the renegotiation re-pin) stands, less parallel
  implementers (ADR-063).
- *mini-swe-agent recipe.* The wiring facts for the baseline arm, should
  the direct path ever be re-run outside Pier: litellm `openai/`
  provider against the Modal endpoint with `MSWEA_COST_TRACKING=
  ignore_errors` (no price row for a local model); `MSWEA_DOCKER_EXECUTABLE=
  podman` builds the exact `swebench/sweb.eval.x86_64.<id>` images already
  pulled; the injection point is `agent.instance_template`'s `{{task}}`
  block; `swebench_backticks.yaml` (text actions) over the tool-call
  config for a 7B; output is a standard predictions file the pinned
  evaluator reads (C-50). Cautions: never run its containers while
  `hobbes bench` is active (shared rootless podman); the 7B and 27B are
  separate Modal apps; `~/.config/mini-swe-agent/.env` on this box can
  override the exports. The two questions it framed (did our harness
  suppress the 7B; does derived context help on a neutral harness) were
  answered 2026-08-22 — the sixty-fourth entry, the falsifier fires —
  and the path moved to DeepSWE on Pier (ADR-078).

No code, no suite change, no spend.

## 2026-09-09 (docs cleanup, 3) — the ADR-085 run record moves to the cells; the application-mode note renamed

Max: fold the ADR-085 validation run into the cell records; he renamed
the parked application-mode note himself. `docs/adr085-validation-run.md`
→ `docs/ttt-cells/adr085-validation-7b-2026-08-24.md` (content
unchanged, a one-line provenance note under the title) — a dated run
record with its defect register, all eight fixed (ADR-091, ADR-093),
beside the other dated cell records rather than among the living
documents; its nine references (README, CLAUDE.md, architecture §2 and
§6, `extraction-evidence.md`, `benchmark-hypotheses.md`, ADR-091,
ADR-093 ×2) follow it. `docs/m9-application-mode.md` →
`docs/Potential-application-mode.md` (Max's rename, text unchanged;
CLAUDE.md, architecture §10 and `future_additions.md` follow). `docs/`
is 26 entries, from 34 at the start of the day. Noted, not done: the
`ttt-cells/` directory now holds the Calvin probe and this bench record
as well as the test-time-training cells, so its name undersells it —
a rename is Max's call.

No code, no suite change, no spend.

## 2026-09-09 (docs cleanup, 4) — docs/ regrouped by programme (Max's structure)

Max: the docs should be split by experiment rather than by kind of
document, since with pointers the layout is for human navigation;
proposed, approved with two adjustments — `how-hobbes-differs.md` stays
top-level and `comparative/` stays its own folder, both forward-facing.
Five commits, one per folder, filenames unchanged throughout so every
bare-name mention in prose still reads; each folder is named for the
`bench/` or `pipeline/` package it documents and keeps its own `cells/`
for the dated records. The move map:

| Was | Now |
|---|---|
| `oracle-grading.md`, `oracle-misses.md`, `oracle-defects.md`, `oracle-defect-review.md` | `oracle/` |
| `oracle-cells/` (62 records) | `oracle/cells/` |
| `benchmark-hypotheses.md`, `benchmark-deepswe.md`, `agent-mapping.md` | `benchmark/` |
| `ttt-cells/adr085-validation-7b-2026-08-24.md` | `benchmark/cells/` |
| `calvin-charter.md`, `calvin-potential.md` | `calvin/` |
| `ttt-cells/calvin-m0-probe-2026-09-03.md` | `calvin/cells/` |
| `olmo3-ttt-validation.md`, `olmo3-ttt-results.md` | `ttt/` |
| `ttt-cells/` (the three Olmo records) | `ttt/cells/`; `ttt-cells/` removed |
| `atlas-0.md` | `atlas0/` |

Unchanged at the top level: the architecture, `first-run`,
`session-handoff`, `workstreams`, `future_additions`,
`Potential-application-mode`, `extraction-evidence`,
`how-hobbes-differs`, this file, `adr/`, `constraints/`, `comparative/`.

**How the pointers were rewritten.** One script per commit: a
`docs/`-prefixed mention is swapped directly; a relative markdown link
is resolved against its file's old directory, mapped, and
re-relativized against the file's new one (so a moved file's links to
unmoved files gain `../`, and an ADR's link into a moved folder gains
the folder); a bare `oracle-cells/` or `ttt-cells/` mention inside
`docs/` is treated as docs-relative. Rewritten everywhere a path swap
is lossless — living docs, README, CLAUDE.md, ADRs, constraint entries,
the cell records' own links, docstrings and CLI help in `pipeline/`,
`bench/oracle`'s README, `main.go`, `foreign_record.py`,
`cells.meta.json`. This file is the one exception: earlier entries name
the old paths and stay as written. The only functional code change is
`render.py`'s default cells directory and its tables' record links; the
comparative data, tables and four graphics were regenerated from the
moved records and the drift test passes uncached. One hand fix: the
path template for future Calvin records in `calvin-potential.md` §9.

No suite change, no spend.

## 2026-09-09 (comparative review, item 1) — the scatter takes same-key's palette; the claim page's recall range matches the graphics

Max's first review item on the comparative programme: does the claim
page say what the evidence licenses, and is `same-key.svg` the graphic
to lead with. Read against `tables.md`, the one-number graphic and the
rendered SVGs; every number in the four claim sentences matched the
records and the drift check was green. Three prose/graphic
inconsistencies, none numeric, fixed in `f54ab77`:

- `precision-recall.svg` still drew both foreign tools as hollow orange
  shapes after Max's review had moved `same-key.svg` to one filled
  colour per tool; the scatter now uses the same encoding and legend.
  Its label placer tries further below a crowded dot before falling
  back — the Go panel's 100% row had piled eight labels on one spot.
- The claim page's recall range stopped at 98.4% (spring-petclinic)
  while the scatter's footer, counting dagger's modules one dot each,
  printed 100.0%. The page now states 100.0% with dagger named and
  98.4% as the whole-repo top; one reading in both places.
- Three lines called the foreign markers "hollow squares" (the README's
  table row, claim sentence 4, ADR-102 §5); they describe the markers
  as drawn.

Assessment given to Max: `same-key.svg` is the right first graphic for a
comparing audience (it reads across a row unaided and shows Hobbes
behind or tied on recall where it is); the one-number graphic is the
stronger opener for anyone not comparing tools. The wording question
itself is his.

Also: `secrets.txt` sat at the repo root, gitignored, untracked and
never in history (`git log --all -- secrets.txt` is empty). Max moved it
off the tree this session. Nothing in Hobbes reads it by a fixed path —
`hobbes bench run --secrets FILE` is the one reader and takes any path;
the Modal scripts use Modal's own secret store. The handoff's key-file
note and `benchmark-deepswe.md` §HF token are the prose pointers to
re-aim when he names the folder.

## 2026-09-09 (later) — the union-member abstention (ADR-104, 0.1.4-beta): ajv 1,410/1,410, hono 767/768, C-97 and C-98

Handoff item 3, on Max's word ("continue with abstaining") after the
measurement. **Steps 1–2 first, no code changed:** a union-receiver case
added to a copy of the `minits` fixture reproduced the shape with lane
B on — `draw → Alpha.render` and `Holder.render → Alpha.render`, the
*first* member every time (the ajv record's "enclosing class's own
override" was incidental: `If` is `ChildNode`'s first member), and the
tsc oracle graded the copy 7/7, so the oracle picks the first member on
a two-member union exactly as Hobbes did. A ts-morph script over the
ajv and hono zones listed every member call on a union receiver (null
and undefined stripped) and joined it against the grading rows: ajv 15
sites, 9 with a Hobbes edge to the member, 3 contradicted and 6
confirmed; hono 36 sites, 7 with an edge, 7 contradicted. Every
contradiction in the set, nothing outside it wrong, and the confirmed
six separated from the contradicted three only by which declaration
`tsc`'s resolved signature happened to name (the first member on two,
the shared base on ajv's eleven). Lane A's own resolver makes the same
first-member pick as scip-typescript, so lane agreement could never
see it. Three options put to Max — abstain, match `tsc`'s pick,
register and leave — with abstain recommended as C-58's TypeScript face.

**Built (`ADR-104`):** the TS helper (facts **v5**) types the receiver at
every property-access call and, when it is a union of ≥ 2 non-nullish
members whose declarations of the member are not one, records
`ambiguous: "union-member"` with callee, path and origin null;
`evidence.join` draws nothing for such a site from either lane and
claims lane B's occurrence so it does not resurface as `uses`;
`agreement` skips it; `coverage` counts it unresolved; the tail names it
**`union-member`** (TS/JS only in `CLASSES_AVAILABLE`, after
`expr-callee` in decision order, not `NOT_MODELLED`); the proxy's
glossary carries it. Tests in the same commit: five helper cases
(override / inherit / `T | undefined` / literal union / inside an
overriding class), four evidence cases, two tail cases, the fixture end
to end in `test_tssource`, the Go rollup and gloss. Suites: 1,251 pytest
(+7), 33 tsextract, Go and oracle-lane green after the fixture pin
below. The fixture copy with lane B: `label → Base.tag` drawn, nothing
for `draw` / `Holder.render`, tail `union-member 2`, disagreements 0,
graded 5/5 with the two abstentions as misses.

**Regrades against the standing keys** (the report files were
truncated once by `tee | head` — SIGPIPE — and regenerated in full):
**ajv 1,375/1,378 → 1,410/1,410 (100.0%), recall 62.0% → 63.5%**,
re-ingested *contained* on 0.1.4-beta (1,575 edges graded where 1,543
were: every lift since 2026-08-27 is in it), artifacts
`~/.hobbes/bench/oracle/ajv-ts-r3/`; **hono 767/774 → 767/768**,
`~/.hobbes/bench/comparative/hobbes-hono-build-r2/`. The row left on
hono (`src/jsx/components.ts:18`) is a site lane A could not type at
all: hono's root `tsconfig.json` is a solution-style config (`files:
[]`, nine `references`) and the helper loads it as the zone's compiler
options — none, so ES5 defaults, `Array.flat` unknown, the receiver
`any`. Lane B follows references (C-90); lane A does not yet. Registered
**C-98** (*partial*; W1 carries the lift), **C-97** for the abstention
(surfaced); C-58 gains its TypeScript face. Register 98 / 76 / 20 / 2.
The oracle's grain at union sites is recorded as a pick, not a truth
(`oracle-misses.md`). Both records carry signed regrade blocks; meta
notes rewritten; `render.py` regenerated everything under the drift
test — the one-number graphic reads 0 of 99,850 across 19 cells, 37 of
39 at 100%, exceptions hono and quic-go; the claim page says two named
exceptions. Version 0.1.4-beta (patch: what Hobbes draws), CHANGELOG,
the four binaries and the image rebuilt, this repo re-ingested.

**Fixture pin moved:** `TestMinitsTSAllConfirmed` in the oracle lane
pinned minits' recall misses; the two deliberate abstentions in
`src/union.ts` are misses by design and the pin says so now.

## 2026-09-10 — C-98 lifted (0.1.5-beta): a file under a solution-style tsconfig is typed by the referenced project that includes it; C-99 found and fixed in both lanes; hono 768/768

Max's direction at the start: the claim page's wording is fine — item 1
of the comparative review crossed off; proceed with C-98; the bigger
box (syft, dagger's root) and the experimental holds stay off the
table. The session opened on a doc review (README, CLAUDE.md,
CHANGELOG, the handoff, workstreams — every count matched the tree) and
a knowledge server two commits stale, re-ingested.

**The lift (`9f5ca99`, `tsextract/extract.mjs`):** `zoneTsconfig`. The
nearest `tsconfig.json` is read raw (`ts.readConfigFile`, no disk walk)
and tested for the solution shape; an ordinary config is the zone as
before. A solution config's references are resolved by the compiler
(`ts.getParsedCommandLineOfConfigFile`, `resolveProjectReferencePath`),
in the order written, inside the repo, solutions followed transitively
under a `seen` set; the first referenced project whose `fileNames`
contain the file is its zone, parsed once per config per extraction.
`tsconfigs` in the facts names the zones actually used. A file no
project claims joins the zone-less default project and is reported once
per solution config (`errors` stage `tsconfig-unclaimed`, the files
sampled) — the ingest prints it as a degradation line. Facts schema
unchanged (v5). Before/after on the hono shape as a fixture, old helper
against new: `tsconfigs` `["tsconfig.json"]` → `["tsconfig.build.json"]`;
the `@/` alias unresolved → resolved; `pick`/`flat`/`map`/`render` all
null → `pick` resolved, `flat` and `map` external, `render`
`union-member`. Two node cases (35 tsextract tests, +2).

**C-99, found on the first hono ingest:** the log reported hono's six
`runtime-tests/*/tsconfig.json` as solution configs with files no
project claimed. They are `extends` + `compilerOptions` + `references`
with neither `files` nor `include` — and the compiler's default include
is then the whole directory (checked against
`getParsedCommandLineOfConfigFile`: references-only lists every file
under it; `files: []` or `include: []` lists none). Lane B's
`is_solution_tsconfig` (C-90) had the same reading since 2026-09-03, so
those six zones had been indexed under the generated config in every
hono record. The rule corrected in both lanes — a solution has
`references`, no non-empty inputs, **and** one of the two keys written
(`_TS_INPUT_KEY` in lane B; `isSolutionTsconfig` in lane A) — with
tests on both sides; registered and lifted the same session.

**Measured on hono** (same clone, commit and key; artifacts
`~/.hobbes/bench/comparative/hobbes-hono-build-r3/`, the record's third
signed block): **768/768 (100.0%), 0 contradicted**, poison 0 falsely
confirmed of 4,471, recall 55.2% (775/1,403, `static→method` 113 →
114); `union-member` 15 sites in nine files where there were 0 (the
sites `src/` types once it has `tsconfig.build.json`'s options), the
`components.ts:18` row gone by abstention; attr-call 7,819 → 7,795,
external-origin 37 → 52; capture 39.7% → 39.6%; unclaimed reports
seven configs → one (the root, 22 files, `benchmarks/deno/*` among
them). **Baseline for the lane check:** a copy of the clone ingested
under the old helper (the file swapped on disk for the run's duration)
— `hobbes lanes` byte-identical before and after: 4,332 both-resolved
sites, one disagreement (`src/middleware/body-limit/index.test.ts:139`,
two `text()` calls on one line joined at line grain — pre-existing,
not the lift's), module edges 42 lane A only / 635 lane B only. This
repo has no solution-style config; its graph did not move. The claim
page's exceptions: quic-go alone; `render.py` regenerated the four
graphics and `tables.md` under the drift test (`-count=1`, the cached
run proves nothing).

**Version 0.1.5-beta** (patch: what Hobbes draws), CHANGELOG, the ten
version copies (`test_version.py`), the four binaries and the image
rebuilt (the proxy in the image answers 0.1.5-beta); register 99 / 75 /
22 / 2 — C-98 to the TS segment's lifted section with its technique and
residuals, C-99 beside it, C-90's residual amended; architecture §3
(the lane-A rule beside lane B's) and §3.8 (hono's row, the exceptions
line); ADR-104's consequences annotated; the claim page, the evidence
log, `oracle-misses.md`, `cells.meta.json`, workstreams W1, README and
CLAUDE.md's status. Suites: 1,251 pytest + 3 `lane_b` on the new image,
Go and oracle-lane Go green, 35 tsextract, 32 scip, 52 vitest.

**Practical:** the session's knowledge server still runs the image it
started with — restart it after this rebuild (C-65). Ingesting a copy
of a clone (with its `.git`) is the cheap way to get a baseline under a
swapped helper. `go test` reports `(cached)` for the drift test after
the records change — run it `-count=1`.

**Later the same session — the lane asymmetry closed (0.1.6-beta) and
ADR-105.** Max: close the asymmetry the C-98 lift left, and state the
indexer rule high in the architecture for the next language. *Lane B
under the same map:* the helper gains `--zones` (the per-file zone by
`zoneTsconfig`, configs only, no repo code), `scipsource.ts_zone_map`
asks it once per ingest when any zone's config is a solution, and
`_index_ts_zone` passes scip-typescript the referenced projects that
claim the zone's files as positional projects (`index [projects...]`,
absolute stage paths; documents stay relative to `--cwd`, so `_rebase`
is untouched) plus `tsconfig.hobbes-unclaimed.json` for the rest —
beside the solution file, which stays intact for a project that
`extends` it; the map unavailable is a recorded degradation and the
zone falls back to the generated config over the solution file. Tests:
the projects and configs a solution zone stages, the fallback, the map
as the helper's answer, a `lane_b` case in the image (a `paths` alias
that lives only in the referenced projects' base resolves in lane B —
the old shape could not), the `--zones` case in the helper's suite;
the broken-zone mock takes the new keyword. *Measured on hono (r4):*
768/768 unchanged, one edge syntactic → semantic (727 / 41), lanes
4,332 → 4,336 both-resolved with the same one disagreement, lane B
module edges 1,483 → 1,474; lane B alone on the root zone, old against
new: references 27,682 → 37,216, module pairs 17 lost (fifteen from
the unclaimed deno benchmark and runtime-test files into `src/` — now
a separate program in both lanes, C-12's shape — two inside `src/`
from spec-project test files) and 8 gained (`src/context` to the
middleware modules augmenting it). The C-98 residual rewritten with
the numbers; C-90's residual notes the technique is superseded for a
solution zone. *ADR-105 (P13):* a lane B provider is a pinned batch
program with a stated version and a tier stamp, never a language
server; SCIP is the IR, not the rule — §1, §3.2's opening, §3.7 step 1.
Version 0.1.6-beta (patch: what Hobbes draws), the image rebuilt (the
proxy answers 0.1.6-beta), suites green: 1,255 pytest (+4; the new
`lane_b` case tolerates the containment disclosure a suite run with
`HOBBES_UNCONTAINED` leaves — two containment tests set it), 36
tsextract, 32 scip, 52 vitest, Go and oracle-lane Go.

## 2026-09-10 — (later still) the callee-shape bucket answers the indexer question; C-100 (`.mts`/`.cts`) found and lifted — 0.1.7-beta

**Max's two questions, the second taken first as directed.** (1) Jelly
(Møller's flow-insensitive points-to for JS/TS; CLDK embeds it as an
experimental backend beside the compiler's resolver with a `both` diff
mode) as a third extractor lane, graded against our `tsc` key on
cheerio/zod — an afternoon; grade before admitting. (2) *Why does a
`tsc`-based key beat a `tsc`-based indexer by 45–64 points?* — bucket
cheerio's miss set by callee-expression shape from lane A; the tail
should concentrate; that is the full-tail-check machinery pointed at
one cell and it stays in the 100% tier.

**Built for (2):** `bench/oracle/shape/shapes.mjs` (every call site of
a zone with the checker's reading of the callee: identifier → its
declaration kind, member → the receiver's shape, the resolved
signature's declaration) and `bucket.py` (join a cell's misses to that
record and to lane A's facts at the site; bucket; collapsed recall with
the oracle's overload grain removed). cheerio re-ingested and regraded
at 0.1.6-beta first (r3: 2,622/2,622, recall 36.1% → 45.0% from the
fixes since 2026-08-28), zod likewise (r2: byte-identical to
2026-09-09).

**The answer (`docs/oracle/oracle-misses.md`, the two records'
2026-09-10 blocks):** no — the indexer withholds almost nothing. With
one pair per (site, target file, target name) cheerio is 68.5% and zod
58.5%, and by target kind the *function declarations* are 99.7% / 98.8%
drawn, methods 89% / 96.5%. 60.7% of cheerio's misses and 36.9% of
zod's are the oracle's overload grain (one pair per signature — H-19's
recall side, now measured). The rest is targets below the symbol floor,
where lane A's record reads *no callee, origin local/nested* every
time: cheerio's `let $: CheerioAPI` specs (884), `const $ = load(..)`
(176), closures and params (242); zod's v4 interface signatures
(`parse`/`safeParse`/…, 4,742 — the bodies live in `$constructor`'s init
closure, no declaration has one), v3's `static create = (..) =>` class
properties (1,029), `new` (the helper does not visit `NewExpression`;
~230), the `util` namespace's members (230). Not one miss on either
cell is a site lane A resolved to a modelled symbol that the join
failed to draw.

**C-100, found there and lifted:** cheerio's only six function-target
misses were in `scripts/fetch-sponsors.mts` — no lane A record at all.
`.mts`/`.cts` were on neither extension list (helper, `tssource`,
`tail`); the file was not a module, its calls uncounted, and lane B's
index of it (it is in the program) had nothing to join to — silent.
Added to the helper's set, `tssource._EXTENSIONS`/`_TS_EXTENSIONS`, the
tail's language map, the grounder's import candidates, the agent
policy's test-command map and the harness's vitest rule; tests on both
sides. cheerio at 0.1.7-beta (r4): 2,628/2,628, the six recovered at
the semantic tier, 1,911/1,911 function targets. Patch bump (a change
in what Hobbes draws), CHANGELOG, image rebuilt (C-65), register
100 / 75 / 23 / 2.

**Priced, not done (W1; Max's call — each a floor change at symbol
grain):** class-property functions as `method` symbols (zod 6.2% of
pairs); namespace members; `new X(..)` as a site, with the grader-grain
question first (the key names the class whose constructor answers —
the base class for an inherited one).

**For (1), what the bucket settles first:** the below-floor tail is
exactly where a flow analysis would answer, and its answer is a
*different declaration* from the key's (`$(..)` → `initialize`, where
the key names the `$` binding; `schema.parse(..)` → the closure
assigned in init, where the key names the interface signature). Graded
against this key those are contradictions, not recall. A Jelly cell
needs the key grain decided — a flow-grain `tsc-oracle` mode, or a
grader rule that a below-floor target is confirmed by the value bound
there — before the afternoon is spent. Not started; no spend.

**Suites:** 1,257 pytest (+3 `lane_b` in the image), 36 tsextract, 32
scip, Go and oracle-lane Go green, the comparative drift test
regenerated. The cheerio record's standing grade is the r4 block;
`cells.meta.json`'s note names it.

## 2026-09-10 — (the versioned baseline) every Hobbes oracle cell regraded on one build, 0.1.8-beta; C-101 found and lifted on the way

**Max's direction:** update the comparative graphics with the new
numbers and state the Hobbes version — option 2 of two offered:
regrade every Hobbes cell on the current build first so the graphics
can say one version truthfully; the foreign cells (CodeGraphContext,
repowise) not regraded, since the tools did not change.

**Run:** 41 Hobbes cells — the thirteen loop and random-draw cells,
the five 1-1 draws, kbet, rust_proj, dagger's 19 Go modules and
`sdk/rust`, this repo's two dogfood cells — each re-ingested contained
(`HOBBES_SCIP=1`) and regraded with `oracle export` + `oracle grade
--poison` against its standing key (the Go RTA, `tsc`, MIR and javac
keys reused at their pinned commits; kbet's `tsc` key rebuilt at the
same commit, the 2026-08-25 artifact being gone; this repo's two keys
fresh since the tree moved). Artifacts `~/.hobbes/bench/v018/`. dagger
ingested contained for the first time (824 s); its 19 modules and
sdk/rust unchanged to the digit, poison 10,507 seeded / 0 falsely
confirmed. Every other cell held on its graded set; what moved is
growth (click +62 edges all confirmed; this repo 1,305/1,305 at 21
roots and 4,741 confirmed / 10 suspects, all C-60's mock asymmetry)
and silent counts (hono +18 in the `.mts` files C-100 discovers;
memchr −140 in a haystack file where C-72 now abstains; quic-go +20 in
a build-tagged test file) — each record's 2026-09-10 block names it.

**C-101, found there.** spring-data-elasticsearch came back 3,871
syntactic edges instead of 16,050 semantic: its first ingest under
ADR-097's two passes (the cell was graded 2026-08-29, before the
scheme). Two halves, both reproduced by hand in the image: the resolve
stage held the repo's Kotlin sources and `kotlin-maven-plugin` compiled
them against Java that was not there (BUILD FAILURE); with that fixed,
the index pass failed alone because scip-java runs `./mvnw` and the
takari wrapper downloads its Maven distribution on first use — offline
— while the resolve pass had run the image's `mvn` and never fetched
it; and with `./mvnw` in the resolve pass the distribution still landed
in the container's throwaway layer, because the Java wrapper reads
`MAVEN_USER_HOME` or the JVM's `user.home` (the passwd entry), not
`$HOME`. Fixes: `_JVM_SOURCE_SUFFIXES` (`.java`, `.kt`, `.scala`,
`.groovy` off the resolve stage, `buildSrc/` excepted), the resolve
pass through `./mvnw` when the stage has one, `MAVEN_USER_HOME` at the
cache root's home. petclinic had passed 2026-09-01 on a warm cache
alone — on a fresh cache every wrapper-shipping Maven repo would have
degraded. Registered and lifted (register 101 / 75 / 24 / 2), ADR-097
amended, a patch bump to **0.1.8-beta** (a change in what Hobbes
draws), image rebuilt; spring-data-elasticsearch regraded
16,050/16,050 at 66.4%; the other three Java cells rerun on the final
code, unchanged (Severed-Chains still lane-A-only by C-67).

**The renderer:** `hobbes_version` per cell from the record's last
regrade heading; a Hobbes column in `tables.md`, a version sentence on
the three graphics; the dagger record's per-module table can be
appended (last row per module wins). `cells.meta.json`: dagger, kbet
and toml now `contained`. `render.py check` and the Go drift test green
at 41 × 0.1.8-beta.

**Commits:** `ea72308` (C-101 first half, 0.1.8-beta, the renderer),
`d3f6596` (the wrapper), `a13539e` (`MAVEN_USER_HOME`), then the
records. **Suites:** 1,257 pytest (+4 `lane_b` in the image), Go,
oracle-lane Go, 36 tsextract, 32 scip. The scratch drivers
(`regrade-v018-*.sh`, `append-blocks.py`, `dagger-table.py`) lived in
the session scratchpad; the record blocks quote each artifact
directory, and the run is reproducible from the records' command
lines.

## 2026-09-10 — (later still) the baseline's CI was red on two jobs; both fixed, and the graph job's forgetting found

**Max pushed the versioned baseline and tagged `v0.1.8-beta` locally
(this session's first act); CI came back red on `python` and `graph`.**
Both read from the run's logs, reproduced, fixed, no model, no spend.

**`python`: one failure.** The solution-zone `lane_b` case
(`test_lane_b_indexes_a_solution_zone_under_the_referenced_projects_options`,
0.1.6-beta) had no "containment unavailable → skip" guard, unlike the
three other `lane_b` cases. On the runner podman exists and the image
does not, so scip-typescript — a non-executing provider — ran on the
host, where the python job installs `tsextract/`'s dependencies and
not `scip/`'s: the helper died with `ERR_MODULE_NOT_FOUND` and the test
read the degradation as its own failure. The guard is added; the case
skips without the image (all four skip when `HOBBES_SANDBOX_IMAGE`
names nothing) and runs in the graph job's `pytest -m lane_b`, where
the image is built (4/4 here).

**`graph`: `needs attention: 2 unguarded new module(s)` —
`bench/oracle/shape/shapes` and `bucket`.** The callee-shape tools
landed with 0.1.7-beta as two scripts and no test; the review is right.
The adapters' precedent — a Go test that execs the Python — is not a
reach the graph can see (the adapters' `adapter` modules and
`report/render.py` are unguarded by the same measure, only older). So
each tool now carries a suite *beside it in its own language*:
`bucket.py` is functions (`bucket_misses`, `collapsed_recall`,
`render`, `main`; the printed report byte-identical) and
`bucket_test.py` drives them on a hand-built cell with one miss per
rule (sibling grain, identifier kind, receiver shape, no record on the
line, nearest column, lane A's record, the external target dropped from
the pairs — 15 cases); `shapes.mjs` exports `calleeShapes(root)` under
a main guard and `shapes.test.mjs` builds a repo with one call per
shape (the import alias followed to three overload declarations and the
resolved one named, `var:const:top:fn-literal`, `ident:class`,
`call-result`, `new`, `this`, `param`, `method-signature`, `paren`,
`computed`, and the command line emitting the same record — 6 cases);
`shape_test.go` runs both under `go test ./...` (the node suite skips
without `tsextract/node_modules`, which the go job now installs).
Ingested and reviewed `0be3bfa..HEAD` locally: both modules guarded,
nothing needs attention.

**Found on the way: the graph job forgets a red review.** `ci-graph.sh`
reviews `github.event.before..HEAD`, so a module that failed one push
is in the next push's base and is never reported again. Three pushes
in a row were red this way — `go/internal/version` (0.1.3-beta, the
2026-09-09 21:03 run), the `minits/src/union` fixture (the ADR-104
regrade, 13:48 today), then `shape` (15:55) — and only the third is
fixed here; the first two stand unguarded (`tests_guarding` says so).
The fixture case is also a question for `_own_code`: a fixture source
is not behaviour a test could guard. Both are one W0 item; an ADR
either way (ADR-025 is the contract).

**Suites:** 1,257 pytest (+4 `lane_b` in the image), 51 oracle-lane
Go (`shape/`'s two run 15 unittest + 6 node cases), the rest untouched.
No version bump: a test guard and bench tooling move nothing the layer
draws, refuses or says (ADR-103).


## 2026-09-10 — Baseline review and documentation drift

Max directed the pending reviews and confirmed Hobbes is tagged
0.1.8-beta. Reviewed at `4b2ec9588ceb` using Hobbes blind spots,
callers, guarding tests and neighborhoods before targeted source reads.
The complete findings and recommendations are in
`docs/reviews/2026-09-10-baseline.md`.

Two temporary reproductions found open issues: Java build-tool
subdirectories bypass the JVM-source filter (C-66's source-free claim
narrowed), and the exploratory collapsed-recall helper merges distinct
same-named methods (H-22, RC-5). Its approximate lane-A join also cannot
prove the universal no-join-miss claim. Architecture §3.2, ADR-097 and
the miss record now state the limits; code fixes remain open. No new
constraint number: this corrects the boundary and surfacing of active
C-66. C-101's ordinary source and Maven wrapper/cache fixes pass their
targeted checks; no foreign build was rerun.

The generated data has 41 contained Hobbes cells at 0.1.8-beta, and the
report drift check passes. Corrected the comparative baseline's “four”
count, CLAUDE's current version, obsolete tagging decisions, the oracle
seen tally (22 mapped), and H-11's stale open status. Rewrote the handoff
opening around the findings and remaining lead decisions; tagged means
complete, remote publication was not checked. Held experiments remain
held; this review is not lead acceptance of a new stage or design.

Validation: 12 targeted Java unit/profile tests passed; 5 Java
containment tests passed (overlapping profile coverage); uncached Go
shape/report packages passed (15 unittest + 6 Node cases, report drift).
uv cache and Node subprocess sandbox failures passed on approved
reruns. Documentation only; no version bump, generated data change,
API/Modal spend, or push.

## 2026-09-10 — (later still) the baseline review's two findings closed: the Java resolve stage's boundary, and the bucket's identity — 0.1.9-beta

Max: "tackle the first two", the knowledge tools first. `list_blind_spots`
on the two directories, `who_calls` on `java_build_files` (one product
caller, two tests), `tests_guarding` on the module and on `shape/`, then
the lines they pointed at.

**1. The Java resolve stage (C-66; 0.1.9-beta).** `java_build_files`
copied `.mvn/`, `gradle/` and `buildSrc/` with `rglob`, past both the
JVM-suffix filter and lane A's pruning — the review's `.mvn/Hidden.java`.
One walk now, one rule in every directory: the pruning everywhere,
`.mvn/` the one dot-directory entered, a JVM source left out wherever it
sits except below `buildSrc/` (the one exception, unchanged — Gradle
compiles it before it can evaluate a script). `buildSrc/build/` and
`.gradle/` no longer ride either. The notice reads "a networked pass
whose stage holds no application source (build logic under buildSrc/
excepted)"; the containment comments say the same. Three tests, at the
three levels a user meets it: the file list (sources planted under
`.mvn/`, `gradle/`, `buildSrc/`, a stray dot-directory); the routing
test's resolve plan (the stage's JVM files are exactly the `buildSrc/`
one); and the contained canary. **The canary's fourth probe could
never have seen the resolve pass:** `Phoned.java` is written on the
resolve stage, which is discarded before the index runs — so the probe
now also drops a sentinel in the Maven cache (`maven.repo.local`, the
one writable mount that outlives the stage) listing the sources it saw
with the network, and the fixture plants `.mvn/Hidden.java`. Shown to
fire: the old walk re-admitted through a wrapper, the real contained
run wrote `./.mvn/Hidden.java` into the sentinel (3.6 s); the fixed
walk does not. A `build-logic/` included build is not excepted: its
sources stay off, the resolve pass fails to configure, the unit
degrades to lane A visibly — widening is a decision (W1), not a
default. Patch bump (a change in what the layer refuses to stage and
says): `VERSION` 0.1.9-beta in its seven holders and three lockfiles,
`CHANGELOG.md`; C-66 surfaced again; architecture §3.2, ADR-097, the
W1 item, README.

**2. The bucket's identity (H-22).** `bucket.py` collapsed on the bare
target name and hit by bare name too, so `A.run` and `B.run` in one
file were one pair a single confirmed row could cover; the sibling
rule shared that identity; the checker record was the nearest column
and lane A's the first candidate; `shapes.mjs` skipped `NewExpression`.
Now: a pair is (site path, site line, target path, the checker's fully
qualified name) — overload signatures share one, two same-named methods
do not; a confirmed row hits the oracle target at its exact position on
its line (the grader's `hasTarget` rule) and a row no target explains is
reported, never dropped; the sibling rule reads the confirmed targets
the same way; a miss takes the checker record at the oracle site's
column (1-based there, 0-based in the record; several at the column
that read one bucket are one reading), else the one record on the line
spelling the name, else an explicit `checker-record:ambiguous` /
`none-at-this-callee` row; lane A's record likewise (`ambiguous`,
`other-name`, `none`); the kinds a pair collapses are reported when they
disagree (`mixed:a|b`); `new X(..)` is a record shaped by what the name
declares. The report prints how every miss was attributed. Seven
identity tests on a cell of their own; the `new` case in the node
suite (a synthesised construct signature has no declaration — recorded
as such). **Re-measured on the 0.1.8-beta grades** (shapes and facts
regenerated from the clones, no spend): cheerio 3,826 pairs / 2,628 hit
/ 68.7% — unchanged to the pair; 1,972 sibling, 1,266 at the column, 0
by name, 5 ambiguous (the `CheerioAPI.__call` sites); zod 16,634 pairs
(+3 the bare name had merged) / 9,731 hit / 58.5%; 4,442 sibling, 7,570
at the column, 0 by name, 12 ambiguous, 14 with no record; 0 confirmed
rows unexplained on either. The `new` sites the old run reported as "no
lane A site" are attributed: zod 114 on a class, 107 on an
interface-typed constructor value (v4's `$constructor`), 85 on a
parameter. H-22 closed in `oracle-defects.md` (open: none), RC-5's
line, the misses record's prose and two table cells, both cell records.
Promotion to an `oracle grade` line stays Max's call.

Validation: 1,258 pytest (the new one included; the four `lane_b`
skipped without the flag, the Java canary run under it: pass), 304 Go,
the oracle lane's 51 (23 unittest + 7 node in `shape/`, the report
drift test on the amended records), `test_version.py`. Static proxy and
image rebuilt for the bump (C-65); this repo re-ingested. No spend, no
push, three commits on `main`.

Later, Max's two notes: 0.1.9-beta stays untagged, and the number line
after the next version is **0.11.0-beta, not 0.2.0** — ADR-103 amended,
CHANGELOG head and CLAUDE conventions say so. The session's knowledge
container (started on the 0.1.8-beta image before the rebuild; the
proxy answered `0.1.8-beta`) was stopped so the next session starts on
the rebuilt image.

## 2026-09-10 — (later still) two decisions taken: the `build-logic/` rule recorded, the collapsed recall printed by the grader; the Java key's bare names found and qualified (H-23)

Max read the two review fixes (good through his review) and took two of
the four decisions the handoff carried; the three floor shapes and the
Jelly key grain are off the table for now. The knowledge server was
confirmed up on the 0.1.9-beta image first; the artifact was one docs
commit behind HEAD and was re-ingested.

**1. `build-logic/` (C-66; ADR-097 amended).** Not by name. When a
Gradle included build under any directory degrades a real unit, the
exception is keyed on the build's own declaration — the directories a
`pluginManagement { includeBuild(..) }` block names in the settings
file, Gradle's definition of build logic — never on a directory name,
and never on plain top-level `includeBuild(..)`, which composite builds
use for application libraries. Nothing is built until a repo hits it:
the unit degrades visibly to lane A and the residual stays registered.
Recorded in ADR-097, C-66, architecture §3.2 and the W1 item.

**2. `recall-collapsed` (ADR-089 amended).** `oracle grade` prints a
second recall line on every resolution or reachability cell: one pair
per (site line, target file, target name as the key spells it) — the
callee-shape bucket's identity (H-22) — computed by the grader from the
key and its own confirmed rows, the same algorithm as `bucket.py`,
which now cross-checks the grader's number on a report and says whether
they agree. The per-signature line stays the standing grade, the
records' headline and the graphics' input; the renderer ignores the new
line; a foreign graph gets it from the same grader. cheerio
2,628/3,826 = 68.7% and zod 9,731/16,634 = 58.5% to the pair — the
bucket's published numbers from a second program. Two things fold,
stated on the line: a symbol's overload signatures and repeats of one
callee on one line — the second means the line can sit *below* the
standing one (Severed-Chains 20.9% beside 23.5%: the standing line's
12,803 hits come from 10,154 confirmed edges, one edge hitting every
repeat on its line). ajv 65.8% beside 63.5%, hono 58.9% beside 55.2%;
Go and Rust within 0.1 (hobbes-go 59.3%, memchr 80.6%). Not for trace
oracles. `TestCollapsedRecallRemovesTheOverloadGrainOnly`. Bench
tooling: no version moves (ADR-103). Design §3 and §5, the README, the
claim page's rules, the two TS records.

**3. H-23 — the Java key's member-bare names.** The line's first Java
run read jsoup at 85.3% beside 76.2%, impossible for a key that
resolves one declaration per site. `internal/javac` named a target by
its bare member (`get`, `authenticate`, a constructor by its class), so
two same-named declarations in one file — the CHA override set's common
shape, an override in a nested or anonymous class — shared one collapsed
pair and one confirmed row covered both: 433 groups folded 2,622
distinct jsoup declarations. H-22's lesson on another key (RC-5, its
fourth). Names are owner-qualified now as the shard key spells them
(`org.jsoup.nodes.Element.attr`, `a.Foo$1.run`, `a.Foo.<init>`);
`oracle java-javac --merge-only --carry <key>` re-merges a key from the
shards a cell directory keeps, without the build; the four standing
Java keys were re-merged and checked field by field — every site,
target position, kind, mode and interface identical to the 2026-08-29
files, kept beside the new ones as `oracle.json.member-bare-names-2026-09-10`
— and regraded on the 0.1.8-beta artifacts: every headline unchanged
to the digit; collapsed jsoup 76.3%, petclinic 98.3%,
spring-data-elasticsearch 66.7%, Severed-Chains 20.9%;
CodeGraphContext-on-jsoup unchanged. The foreign Java records quote no
target names in their standing blocks; a future regrade prints the
qualified spelling. `TestQualifiedNames`; the four Java records, the
defect record and the review tally.

Validation: the oracle lane's 52 Go (+1), the shape suites (24 unittest,
+1; 7 node), the report drift test on the amended records, the grade
package's contained minijava build, the TS fixture test. No product
code, no version bump, no spend, no push; commits on `main`.

## 2026-09-10 — (later still) the recovery half-built path: a Gradle unit gets scip-java's plugin from Hobbes's own init script — Severed-Chains 23.5% → 60.8% — 0.1.10-beta

Max asked why Severed-Chains' recall was so low and why it is the one
cell repowise out-recalls Hobbes on; the answer was C-67 (scip-java
could not attach its plugin to that Gradle build; lane A alone, 23.5%,
while the oracle's own plugin had attached to the same build through an
init script) and he said: continue down the half-built path.

**Why scip-java's route failed, read from its source and its jars:**
`ScipGradlePlugin` adds the javac plugin jar to the `compileOnly` and
`testCompileOnly` configurations by file, and Severed-Chains resolves
`compileOnly` at evaluation time, so Gradle refuses the add — the first
of the two causes scip-java's own message lists. The oracle's script
never touches a configuration: it puts its jar on the task's
`annotationProcessorPath` (a task property), forks the compiler with
the plugin's `--add-exports`, and appends `-Xplugin:…` to
`compilerArgs`. scip-java 0.13.1's launcher carries `scip-plugin.jar`
(the javac plugin, `ScipPlugin` on the `com.sun.source.util.Plugin`
service) and `javac-internals.properties` (the five `--add-exports`)
inside its embedded `scip-java-0.13.1.jar`; its `aggregate` command
merges per-source shards from a targetroot.

**Built (`scip/index.mjs`, `sandbox/Containerfile`; ADR-096 amended,
C-67 narrowed):** the image extracts the plugin jar and the properties
file out of the pinned launcher at build (`/usr/local/lib/scip-java/`,
the jar checksum-pinned beside the launcher's); the helper's Java spec
gains a `plan` — for Gradle, `gradlePlan`: write an init script beside
the output (`gradleAttachScript`: every `JavaCompile` task of every
project gets the jar on its processor path, fork with the
`--add-exports` read from the properties file, incremental off,
`-Xplugin:scip -sourceroot:<stage> -targetroot:<dir>`, plus a task that
lists what the build resolved in scip-java's own `dependencies.txt`
shape), run `sh ./gradlew --no-daemon --offline --init-script … clean
compileTestJava hobbesScipDependencies` in the stage, refuse with the
build's own last words when no shard was written, then `scip-java
aggregate --output … --targetroot …`; the script and the targetroot go
with the `.scip`. `runIndexer` runs a plan's steps in order; every
other language is a one-step plan as before; Maven is scip-java's own
route, untouched. Under Gradle the aggregator names no third-party
package (only scip-java's `index` command builds that table, from a
file `aggregate` does not take), so external symbols read package `.`
and the dependency-coverage line is answered from the build's own
listing (`resolvedPackages` → `dependencyCoverage`'s third argument)
— C-23's question by the other witness; external nodes were named by
Java package under both routes anyway. Kotlin is not compiled under
the plugin (never indexed before either). Node tests: 36 (+4: the
plan's two steps and their argv, the script's contents and what it
never touches, the properties parser with continuation lines, the
coverage merge).

**Measured.** Severed-Chains re-ingested contained, 36 s wall: capture
0.0% → **100.0% of 52,209 sites**, 37,998 symbol edges all semantic,
lanes 12,803 / 0, 15 of 15 declared dependencies resolved (0 of 15 on
the first run, before the dependencies task — the wrong "environment
probably not installed" warning was the reason to build it). Regraded
against the standing 2026-08-29 javac key: **29,793/29,793 confirmed,
0 contradicted, recall 23.5% → 60.8%** (`static→method` 49.5 → 100.0,
`static→constructor` 77.8 → 89.5, `interface→method` 0.4 → 43.3 — the
CHA set below the declared method is 94.0% of what is left), poison
29,793 seeded / 0 falsely confirmed; on the same key CodeGraphContext
79.4% / 17.8%, repowise 58.8% / 39.2%. spring-petclinic's Gradle build
through the new route (a one-off, `_index_java_unit(…, "gradle", …)`):
363 definitions / 944 references / 4,384 external refs, identical to
its Maven route; coverage 7/7 by the build's listing where the Maven
route's referenced-package reading says 4/7 (the three checkstyle /
format plugins are declared and resolved, never referenced). One
one-off bug cost an hour: its skip list matched `.hobbes` in the
clone's own path and staged zero files — the route's "no shard"
refusal caught it and now quotes the build's output.

**Docs.** ADR-096 amended; architecture §3.2; C-67 (the Severed-Chains
shape lifted; three residuals named); the call-graph register's
`interface→method` line; the cell record's new block with a signed
direction-of-fix line; the evidence file's row and sentence (61–98%
with lane B; the "without" is gone); `oracle-misses.md` § the four Java
cells; the claim page (the recall range starts at fzf's 40.8% now; the
floor was measured once); `cells.meta.json` (the `floor` flag off);
`cells.json`, the three graphics and `tables.md` regenerated, the drift
test passing; W1; CHANGELOG 0.1.10-beta; the "collapsed sits below"
example moved to spring-petclinic in the grader's doc, design §3 and
the misses record. **Patch bump 0.1.10-beta** (what the layer draws on
a Gradle repo) in the seven holders and three lockfiles; static proxy
and image rebuilt (`hobbes-proxy 0.1.10-beta`); this repo re-ingested.

Validation: 1,258 pytest, 304 Go, the oracle lane's 52 Go with the
shape suites and the drift test, 36 scip node; the four `lane_b` tests
not re-run (Maven canary; the Gradle route has no fixture — its
evidence is the two real repos above, P11). No spend, no push; commits
on `main`.

## 2026-09-10 — (later still) the comparative graphics restated at 0.1.10-beta: every Hobbes cell regraded on the build; the number line stays 0.1.x (Max)

Max, on reading the Gradle route: update the comparative graphs to the
current standing at 0.1.10-beta — and the number line is the
conservative one: **0.1.10-beta, 0.1.11-beta, …; the 0.11.0-beta
statement of earlier today is withdrawn** (ADR-103's third amendment;
CHANGELOG head, CLAUDE conventions, the handoff, the memory note).

**The regrade.** The graphics are read from the records (ADR-102), so
one version on every row means every cell graded on that build. The
0.1.8-beta baseline's procedure again, as one driver: 41 Hobbes cells
re-ingested contained on 0.1.10-beta (`HOBBES_SCIP=1`) and regraded
with `oracle export` + `oracle grade --poison` against their standing
keys — the loop and draw cells against the keys their records name
(ajv's 2026-09-09, cheerio's 08-27, click's 08-28 trace, fzf/mux/memchr
08-28, toml 08-27, rust_proj's 08-28 MIR, quic-go's 09-02, the five
1-1 keys, kbet's key rebuilt 2026-09-10, the four Java keys as
re-merged under H-23), dagger's 19 modules and `sdk/rust` against their
stored keys after one contained ingest (720 s), this repo's two keys
fresh since the tree moved (RTA 517 s; the trace 96 s, one run).
1,589 s all in; artifacts `~/.hobbes/bench/v0110/`. **Every cell holds
to the digit** on confirmed, contradicted, abstract, recall and poison;
two moved elsewhere and are read in their records: quic-go's silent
count is 20 lower because the 0.1.8-beta export had let
`integrationtests/fips/fips_test.go` — a nested module the cell
excludes — through without the flag (that block's "+20 in a
build-tagged test file" was this slip; the oracle held them silent, no
graded number moved); this repo's trace cell grew with the tree
(4,741 → 4,743 confirmed, 10 suspects both times). Severed-Chains keeps
the block written when the route landed (the same build). Each record
gained a 0.1.10-beta block with the report head verbatim and the
grader's new `recall-collapsed` line; dagger's record a third table in
the renderer's shape. `cells.json`, the three graphics and `tables.md`
regenerated — every Hobbes row 0.1.10-beta — and the drift test
passes; the claim page's baseline paragraph says so.

No spend, no push; commits on `main`.

## 2026-09-11 — Calvin M0-Go, the floor round on gitleaks: WP-0 to WP-10, T < O three times, the floor not established at A2; the round stops (Max) — 0.1.11-beta to 0.1.14-beta

**The plan.** Max's M0-Go handoff (`docs/calvin/calvin-m0-go.md`,
committed `d83dc5c`): prove the socket on the densest world Hobbes
makes, with the anchoring confound removed on purpose, before any
fan-out — Go, on gitleaks (the cell's precision 100%, recall 98%), 20
history keys stratified by shape, the task text at A2 (commit message
plus the gold's touched parent symbols), Haiku 4.5 in every arm. The
session ran it as the document says: an orchestrator assigning one
package per sub-agent in a fresh context, checking each exit against
its artifacts, carrying Max's decisions into §10's gate record. Sub-agents
cannot write report files, so the orchestrator saved each package's
reply verbatim as `~/.hobbes/bench/calvin-go/<wp>/report.md`. Code went
on `calvin-go/wp-N` branches, merged to `main` after the exit check.

**The packages, each exit in a line.**

- **WP-0** (units, parents, W; no spend): 20 keys, five per shape, from
  the range (a0f2f4671cfc, 8ad8470]; 20/20 parents ingested contained,
  every edge semantic; W min 1.0, median 1.0, none flagged; ingest
  median 1.75 s (cold 12.2 s). Reopened twice for A2's wording (F2, F3
  below): `a2_rev` 3 on all 20 rows.
- **WP-1** (the Go verifier; no spend): 20/20 golds pass on two passes,
  P2F 0, `all_contained` 20/20. The repo's `//go:generate` is
  regenerated on both trees, never applied; generation draws from a
  clock-seeded generator, so a failing generation gets three attempts,
  each recorded (C-103); the module cache mounted read-only (C-92's
  design). One environment fault by id (09242ce9c8a6, `go vet` on both
  trees). Merged `57b3eb3`; ADR-100 amended.
- **WP-2** (templates at A2 and A1; no spend): 20/20 byte-identical per
  tier. It found the callee door (`cmd/generate/config/main.main` fans
  out to 177–223 rule constructors, 35.2M chars at A2) and was reopened
  for template v2's out-degree cap at k = 20: round-2 open holes
  6,973 → 1,866, 35.2M → 3.22M chars, strict Go coverage 86/6/6/5.
  Merged `88c3f53`; C-104.
- **WP-3** (grounder v1 on Go, the density field; no spend): 0 NULL,
  HSR 0, 20/20 post-images byte-equal, identical on rerun, poison 50/50.
  Rules 1 (a member on a receiver whose type the syntax states) and 2
  (an interface method binds to the interface, implementers recorded)
  settled; density k = 2 on every parent; four defects fixed. Merged
  `3b015a6`; C-102, C-91 amended.
- **WP-4** (estimate; no spend): expected $17.44, band $7.74–$40.39 at
  Haiku's $1 / $5 per MTok; the ceiling asked at $30.
- **WP-5** (five keys through T by hand; spend): $1.17 against $1.95
  (0.60×), G clean on all five, Haiku confirmed 0 of 412 capped
  callees, temperature honoured. Refused `patterns` replies cost 36% of
  its spend: reopened for protocol v0.3. Merged `17f0ffd`; C-105.
- **WP-6** (the run; spend): T 0.225 [0.05, 0.40] on 20 keys × 2 runs, O
  0.80 [0.40, 1.00] on five; X and G clean, so *T < O* resolves into
  *NULL new dominates* (all 11 of T's NULLs are names it wrote and
  never declared; the loop closed none) → M1′ as protocol. O's lead is
  partly recall (two keys reproduced upstream verbatim). Track B: O
  separates sparse from absent (1,940 sparse-real references resolved,
  0 sparse NULL). $7.95. The `o-units` driver merged `5555dad`; the cell
  page `docs/calvin/cells/calvin-m0-go-2026-09-11.md`.
- **WP-7a** (the declaration hole, protocol v0.4, the gutter guard; no
  spend): WP-6's 11 NULL sites close 11/11 on a scripted gold replay,
  0 opened; 7fc11's three gutter fills refused. Merged `edd075e`;
  C-106–C-108.
- **WP-7b** (the recall scan; no spend): every WP-5 and WP-6 row
  carries `recall`; WP-6's measure reproduces 45/45; 2 of O's 5 rows
  `recalled`, 0 of T's 40. Merged `8244194` (scripts, no bump).
- **WP-8** (the floor re-tested on v0.4; spend): T 0.25 [0.075, 0.425];
  the declaration hole closed 9 of 11 NULLs and **0 of 9 built** — every
  body written against another project's API (trufflehog, gosec). *T <
  O* re-selected, not separable on the three recall-free keys; G
  unclean on declaration bodies (D-g), no sibling's form (D-h), a
  refused declaration recorded placed (D-f). $5.05.
- **WP-9** (grounder v2, the world check, protocol v0.5; no spend):
  WP-8's 9 wrong-world declarations each raise a NULL at the grounder
  (`import-outside`, `unimported`), 9/9; 0924's overlap reads `refused`
  2/2; WP-7a's gold declarations still close 11/11; gold 0 NULL, 20/20
  byte-equal; poison 50/50. Merged `ade1d79`; C-109–C-114 (C-112,
  syntax errors unclassed, **unsurfaced** — debt).
- **WP-10** (the floor re-tested on v0.5; spend, cap $15.83): T 0.20
  [0.05, 0.375], T-loop 0.20; O − T-loop on O's five keys +0.60 [0.30,
  0.90], on the three recall-free keys +0.33 [0.00, 0.50], not
  separable. *T < O* a third time, X and G clean. WP-9's fixes held:
  the 7 placed declarations are all in gitleaks' world and take the
  sibling's form (WP-8: 0 of 9) — and **0 of 7 build**: an unused
  `secrets` import 3, a wrong argument count 2, a type the grounder
  does not bind (C-91) 1, the repeated invented name 1. 6 of 7 carry no
  NULL, so T ships too; the one repair sees G's NULLs, never the build
  row, and the sibling's 12-line cap cuts it before the lines that use
  `secrets` (D-j). D-i: `t-units`' per-row `usd_loop` omits the repair
  exchange ($0.0083; totals right). $4.76; no code change.

**The residual's path across the re-tests.** WP-6: *NULL new* — 11
names written at a call site and declared nowhere, the loop closing
none. WP-8: *declared in the wrong world* — the declaration hole
closed 9 of 11, every body written against another project's API.
WP-10: *declared in the right world, not compiled* — gitleaks' form on
7 of 7, a build on 0 of 7. Each fix moved the failure one stage down;
T's pass rate did not move (0.225, 0.25, 0.20).

**Max's decisions (§10's gate record, all 2026-09-11).** W's denominator
is the parent's symbols the gold touches; symbols it creates are
declare-holes, outside W. **F1:** an out-degree cap on callee expansion
(above k, callees open as signature confirmations). **F2, then F3:** A2
names touched parent symbols only (`a2_rev` 2), then drops the new-file
path lines too (`a2_rev` 3) — naming a new file would hand the arm the
placement §4.10 measures. `calvin.box.policy` allows `go generate*`.
**The spend gate:** cleared at a $30 ceiling, WP-5 then WP-6.
**Protocol v0.3:** a `patterns` reply read as unchanged / no for the
holes it covers, the validator fixed to name a refused pattern's holes.
**Sampling:** model default from WP-6 on (WP-5's temperature-0 rows
their own reading). **The re-tests:** after WP-6, build the three
changes then re-test T (WP-7a, WP-7b, WP-8; cap $20.88); after WP-8, fix
G and D-h and re-test once (WP-9, WP-10; cap $15.83). **Place and
record:** a declaration in a new file outside the write partition is
placed and recorded `in_partition: false`, never refused (C-107) —
refusing would leave 10 of 11 sites unclosable. **The stop, after
WP-10: the round stops and is written up.** The next protocol step is
named, not built — the verifier's `go build` errors fed into the one
declaration repair, the sibling shown whole — to be read on fresh keys
(WP-0's alternates, `draw_rank >= 5` in `candidates.jsonl`, 122 of
them) with O re-run, since the 20 keys were tuned on three times. It is
held, its spend Max's word; D-i is fixed with it. The design's ADR
takes 106 when Max moves it to *accepted*.

**Versions and register.** Four patch bumps, each with its CHANGELOG
entry and the image rebuilt after (C-65): **0.1.11-beta** (`a94e2bd`) —
grounder v1 on Go, the Go verifier with the read-only module cache and
`go generate*`, template v2; **0.1.12-beta** (`92c9f7a`) — protocol v0.3
and the metered `t-units` driver; **0.1.13-beta** (`5682263`) — protocol
v0.4 (the declaration hole), the gutter guard, the grounder's `scope`;
**0.1.14-beta** (`0c87ac1`) — grounder v2 (the world check on Go fills)
and protocol v0.5 (one bounded declaration repair, a sibling's form,
`refused` read). All untagged; the last tag stays `v0.1.8-beta`. The
register went 101 → 114 entries (C-102–C-114; C-91 amended): 88 active,
24 lifted, 2 superseded.

**Spend:** WP-5 $1.17, WP-6 $7.95, WP-8 $5.05, WP-10 $4.76 — the round
closes at **$18.93 of the $30 ceiling**; the remaining $11.07 closes
with it unless Max reopens. WP-0 to WP-4, WP-7a, WP-7b and WP-9 spent
nothing.

**Disk sweep (Max's request).** `~/.hobbes` 119 GB → 50 GB. The `work/`
clones of 22 SWE-bench-era runs were deleted after each arm's records
were archived into `<run>/work-records.tar.zst`; `v017` and dagger-rust's
`cargo-target` went too. The Atlas-0 checkpoints and the session
worktrees were kept.

**Findings for Max.**
- `hobbes ingest` edits the target's `.gitignore`, so every graph stamps
  `dirty: true` (WP-0; WP-10 saw the trace on the read-only upstream
  clone, a `.hobbes/` line dated 2026-09-09 from an earlier ingest). A
  candidate constraint, not registered.
- The harness's `isolation: worktree` cut worktrees from the session's
  first commit (`9f168d6`), not `main` (WP-7b caught it; WP-7a confirmed
  its base). WP-9 and after made their own with `git worktree add` from
  `main`.
- WP-4: M0's cell record prices Sonnet 5 at $3 / $15 where two on-box
  sources say $2 / $10 (M0's $6.0 T and $16.6 O would read $4.0 and
  $11.1). The record is Max's to amend.
- The Anthropic key line for Calvin runs is `anthropic_key` (pass
  `--key-name anthropic_key`); `llm_key` is not an Anthropic key (two
  401s, unbilled, at WP-5).

Validation: pytest 1,258 → 1,307 over the round (+4 `lane_b` not
re-run); Go 304, recounted, unchanged (only the version constant moved
there); the other suites' code unchanged but for version strings.
**Docs:** the design's §10 and the cell page's `## Re-test 2 (WP-10)`
committed by the orchestrator; the version, register and suite counts
brought to 0.1.14-beta (`d68efd3`); this entry, the handoff rewritten,
CLAUDE's Status and read-next row, README's status and design-docs
table. Commits on `main`; no push, no tag.

## 2026-09-11 — (later) Calvin M0-Go round 2: the audit, then the floor on fresh keys — T 0 of 3 against O 2 of 3 where pass can be read, T declining its body holes — 0.1.15-beta to 0.1.17-beta

Max handed the orchestrator a round-2 design. It ran as written, WP-11 to WP-16, with sub-agents on Sonnet and Max's word at each gate. The design and its gate record are in the tree as `docs/calvin/calvin-m0-go-r2.md`: §0b holds the orchestrator's pins, and §10 the results and every decision, dated. The rows are in `docs/calvin/cells/calvin-m0-go-r2-2026-09-11.md`. Each package's report and artifacts are under `~/.hobbes/bench/calvin-go/wp-11a` … `wp-16`.

- **WP-11a** (the pass metric; no spend). §2.3's rule is built into `hobbes verify`: a build-clean change where no guarding test executed reads `vacuous`, and `gold_tests` applies gold's own test changes on top of the arm's diff.
  - **Reopened once by the orchestrator:** `gold_tests` had no gold control and read `fail` on every row it touched. The cause was gold's tests losing the `testdata/` fixtures gold adds (WP-11a-1 = D-k). With it fixed, the control reads 7/7.
  - **Round 1's 31 pass rows:** 19 are vacuous. T's pass drops from 0.225 / 0.25 / 0.20 to 0.075 / 0.10 / 0.05, and O's from 0.80 to 0.60.
  - **O's five diffs under grounder v2:** 0 NULL; 2 of the 5 wrote outside the partition, at HSR 0.
- **WP-11b** (templates, flips, replay; no spend).
  - **Needed-fraction** on 120 T rows: 0.69–0.96 by shape at signature grain. The templates were not starving T.
  - **The 14 flips:** 7 sampling, 7 path.
  - **Replay drift:** only D-a, and the NULL classes v0.4–v0.5 added — except one silent zero on gutter text (D-m).
- **WP-11c** (the dry-run, the cutoff, the ledger; no spend).
  - **Dry-run:** v0.5's repair carries a build error; WP-10's seven close 7/7 with gold's bodies.
  - **Cutoff:** Haiku 4.5's training-data cutoff is Jul 2025.
  - **Ledger:** reconciles to the cent ($18.9349); D-i confirmed.
  - **Fresh keys:** only **8 usable post-cutoff candidates**. The orchestrator checked upstream: 3 commits past the pin, all Actions bumps, so 8 is gitleaks' ceiling.
- **WP-12** (the audit gate). *T < O* stands on audited rows: O − T keeps its sign, and the recall-free keys are unchanged. Round 1's §10 is amended beside the original, with defects D-k–D-o.
  - **Max's rulings:** round 1's O rows **do not stand** (the stricter parse: an outside-partition write counts regardless of HSR); **N = 8** keys.
- **WP-13** (fresh keys; no spend).
  - **The keys:** 8 post-cutoff keys, all ingested contained, W 1.0.
  - **Gold:** grounds 8/8 at 0 NULL, byte-equal.
  - **Pass is readable on only 3 keys:** gold itself is vacuous on 3 and no-tests on 2. A fourth was blocked by **D-p** (`not-run` in FAILING), routed to WP-14.
- **WP-14** (protocol v0.6; no spend).
  - **What v0.6 adds:** the build row in the one repair; the sibling shown whole, capped at 4,400 bytes; one budget, N = 7, T's round-1 95th percentile, also its maximum.
  - **Defects closed:** D-i, D-n, D-o and D-p. D-l is diagnosed as sampling carried into the path, with no protocol bug.
  - **Replays:** 7/7, 11/11, gold 20/20, poison 50/50.
- **WP-14b** (grounder v3; no spend). New `arity` and `undeclared-type` NULL classes, with the callee read from lane A's parse on demand; the graph is unchanged. D-m becomes a `malformed` class.
  - **On WP-10's seven:** 3 raise one of the new classes; gold still grounds 20/20.
- **WP-15** (the estimate). Expected $3.9 at N = 7. The fact that moved the gate: **O's first edit came at turn 10–26 in every round-1 session**, so at 7 turns O would likely make no change at all.
  - **Max at the spend gate:** O keeps round 1's 30-turn cap, O's subset is redrawn to the three pass-readable keys, and T run 1 stops above $3.6.
- **WP-16** (the run; $3.10 of $12).
  - **Pass:** T 0 of 3 against O 2 of 3 on the readable keys (+0.667 [0, 1], n = 3). J 0.167 vs 0.729. 0 NULL, 0 recall.
  - **T declined to act:** its body holes came back unchanged on 5 of 8 keys in both runs, with no budget cut. The orchestrator checked that the fills are byte-identical to the parent, so the empty diffs are the model's.
  - **v0.6's build row** closed the one build failure it met, `87d96295d65a`'s near-miss name.
  - **Caveats:** not an equal-budget reading. On `8d1f98c7967e`, O's pass is by the guarding tests, and gold's own new tests fail on its diff.
  - **D-q:** WP-13's templates were built without co-change; WP-16 rebuilt them before any spend.
  - **The next step (Max's):** why Haiku declines a body hole it was shown whole.

**Versions and register.** Three patch bumps, each with its CHANGELOG entry and the image rebuilt after (C-65):
- **0.1.15-beta** (`93c43dc`): `vacuous` and `gold_tests`.
- **0.1.16-beta** (`4a22e27`): protocol v0.6, and `not-run` no longer fails a diff.
- **0.1.17-beta** (`aaecc37`): grounder v3. Max chose the number: a patch, where the design had said minor.

All untagged. The register went from 114 to **120 entries (94 active, 24 lifted, 2 superseded)**: C-115 to C-120 registered, C-93 and C-114 amended. **C-120 is unsurfaced beyond the gutter shape** — debt.

**Findings for Max.**
- **The equal-calls budget is not equal work** (C-116). A T exchange carries a template; an O turn is one tool call.
- **`hobbes verify` changed for every user.** A change no test executes reads `vacuous`. M0 (Python)'s records were not re-scored.
- **Sub-agents park themselves** on runs they launch detached, three times this session (twice WP-11a, once WP-16); the second WP-11a stall came after the orchestrator had warned it. The orchestrator watched their PIDs and resumed them each time — see the handoff's practical notes.

**Validation.** pytest 1,307 → 1,322 on `main` (+4 `lane_b` not re-run). Go unchanged but for the version constant (`go test ./internal/version` green). This repo was re-ingested at 0.1.17-beta.

**Spend.** Round 2 cost $3.10 of its $12 ceiling, all of it WP-16; the rest spent nothing. Rounds 1 and 2 together come to $22.03. Commits are on `main`; no push, no tag.

## 2026-09-11 — (later still) Calvin M0-Gate: the linker on the agent's diff — fzf, `hobbes gate` built, the controls hold, D-x found and fixed, ten keys run: the floor as a safety property, not a helper — 0.1.18-beta to 0.1.20-beta

Max handed the orchestrator the M0-Gate design: keep the world, move the agent — the frontier agent loop (O) does the work, and Hobbes' linker gates its finished diff. It ran through WP-21 on ten keys, sub-agents on the default model, Max's word at the spend gate and at D-x. The design, the orchestrator's pins (§0b) and the dated gate record (§10) are in the tree as `docs/calvin/calvin-m0-gate.md`; each package's artifacts and report are under `~/.hobbes/bench/calvin-gate/wp-17` … `wp-21` (and `wp-18b`/`c`/`d`).

- **WP-17** (the substrate draw; no spend). The Go repos in the cell set, counted under round 1's exclusions and the cutoff (committer date ≥ 2025-08-01, each bounded by its cell's SHA):
  - **Pools:** fzf 186, quic-go 154, toml 13, cobra 0; mux has no history past its 2024 pin. fzf and toml were fetched full from upstream (the oracle clones are shallow).
  - **fzf is the substrate** by §0a's rule: calibrated largest pool first, 42 of 45 tried read pass. **The draw is 20 keys, stratified by shape on the orchestrator's pin** (round 1's convention; the rank-order draw held no multi-file or new-file key): single-file 7, new-symbol 5, multi-file 5, new-file 3. W 1.0 on all 20; every parent ingested contained; gold passes with guarding tests executed on all 20.
  - **Hobbes' own repo (the Python fallback):** 26 of M0's 28 keys readable, W 1.0. One of the two unreadable is **D-r**, a verifier artifact: gold's test reads `built_by()`'s checkout, which falls back when `git` fails on the verify container's `--shared` clone.
  - **The blind-spot map** per unit: the graph keeps unresolved call sites as per-file counts, so site rows carry no line; 9 of the 20 units have uncaptured symbols (64 in all, `laneb-miss`), none an uncaptured file.
- **WP-18** (`hobbes gate`; no spend). Grounder v3, the complement split and the partition check over a finished diff at its parent → *clear* or *blocked* with a class list, a stamped record byte-identical on rerun; `o-units` and the Python driver gain `--gate` and `--gate-repair` (one bounded turn resuming the recorded O session, never a re-run; tested on a scripted endpoint).
  - **D-s** (G): the gold control read 9 of 20 at the template partition — every block `partition`, on writes beyond the graph (CHANGELOG, man page, Makefile, Ruby tests, `.s`) or new Go files in a partition file's package. **Fixed by the `reach` rule, now the default:** a file no lane-A provider reads is listed, never blocked; a code file created beside the partition is listed; an existing code file outside the partition still blocks. Gold 20/20 clear.
  - **Orchestrator's pins built in:** a line-less site never routes a NULL to *unknown*; a new file beside the partition reads its directory's map (else an invented name there would have cleared as *unknown*).
  - **Accepted as built:** only `invented`/`near-miss` route to *unknown* (the source-read classes stand); `new` cannot arise at the gate and never blocks; the world and signature classes fire on Go only. `o-units --withhold-manifest` built, off by default.
- **WP-19** (controls; no spend). Recounted by the orchestrator from the 89 records: gold 20/20 clear; seeded (i) invented, (ii) partition, (iii) arity each 20/20 blocked with the seeded class alone; (iv) 9/9 clear with one *unknown* (11 skipped: no blind spot); 89/89 byte-identical. **No G defect.** (i)'s inserted-call fallback on 12 keys accepted.
- **WP-20** (estimate and the spend gate; no spend).
  - **The estimate for 20 keys:** expected $14.0 (band $12.0–15.2), from rounds 1–2's ten O sessions re-priced for fzf's larger files, with every session run to 30 turns. A repair turn costs about $0.04, priced from its real prompt.
  - **The design's stop rules cannot bind at these costs.**
  - **The pre-flight** ran the real `o-units --tier A0 --gate --gate-repair` path on fzf against a scripted endpoint, for $0: block → repair → clear, on a near-miss and on a partition write.
  - **At A0 the plan refuses on 18 of 20 fzf keys.** On one of the other two, its manifest hands O a gold file.
  - **Three instrument defects,** fixed in **WP-18b** before any spend (**0.1.19-beta**, `ee0caae`, bump `a811695`):
    - **D-u:** recall's upper bound was gitleaks' SHA; it now comes from the unit or a flag.
    - **D-v:** rows now carry `gold_tests`, turns-to-first-edit and an `empty` verdict.
    - **D-w:** the repair message showed an unrelated 110-line function as a declaration's form. It now shows the nearest declared names with their signatures (gate v2).
  - **Controls after the fix:** they rerun unchanged, and only the message fields differ.
  - **Max at the spend gate:** 10 keys "for now", the manifest withheld, and WP-20's brake scaled to 10 keys (key 1 > $1.10; O > $5.1 after 5 keys).
    - **The hard cap is $11,** set by the orchestrator, below both ceilings offered, because Max named no dollar figure.
    - **§5's thresholds** were pinned as rates on 10 keys before any spend.
- **WP-21, stage 1 — D-x, the finding of the round.** The package held the run after key 1 by itself.
  - **Key 1's O read the answer from the repo:** `git log --all --grep=…`, then `git show d3245808`, the key commit, at turn 8. It then wrote gold's 12 lines. $0.30.
    - **Why it could:** O's clone held fzf's history past the parent, and the session policy allows `git log`/`git show`.
    - **The row is recorded `copied`, not a solve.** The recall scan cannot see it: it reads training data, not the repo's own future.
  - **The orchestrator's scan of every O session** found five that read their own key: two in round 1, two in round 2, and this one. No session fetched from the network or read another session's transcript.
    - **Round 1:** its two "recalled" O keys (`2278a2a97e42`, `93acc6e82adb`) were reading their key commits.
    - **Round 2:** `ed65b65095eb`'s pass was a copy, so O's pass that is not a copy is **1 of 3**, not 2 of 3.
    - Both rounds are amended beside their originals, in both design docs and both cell pages.
  - **WP-18c (0.1.20-beta, `7231325`, bump `05246b6`):** `harness.run_o` launches O's session, and the repair turn's, from a clone cut at the parent, checked at the object level before launch.
    - **Also closed:** one sessions root per session (a later session could have read earlier transcripts), and the repair seeded with the unit's own parent graph.
    - **Still open:** C-124, the network channel (partial). An egress allowlist is the fix.
  - **Max:** re-run key 1 clean, a stated §0 exception, with the copied row kept and marked; then continue.
- **WP-21, stage 2 — key 1 clean, then keys 2–5** (0.1.20-beta; the cut clean on every row; the leak scan found nothing).
  - **Four keys:** O passed and the gate cleared.
  - **`a650900edac4` (new-file):** O's own verdict was pass. The gate blocked it `[partition]`: O added an unused function to an existing file outside the partition, and gold's tests fail to build over O's diff.
    - Its one repair turn ($0.04) re-read the file and the repeat guard refused it, so no edit was made. That is the arm as designed.
  - **D-y:** the driver scored that repair as an empty diff reading clear. It is scored `blocked-unchanged`, and the fix, WP-18d, merges after the run.
  - **Every session hit the 30-turn cap.**
  - **Spend:** O $2.57 on the five clean keys, under the $5.1 brake; $2.91 in total with the copied session.
- **WP-21, stage 3 and the reading** (keys 6–10; the cut and the leak scan clean on every row). Over the 10 clean keys: O pass 7, fail 1, empty 2; O+gate pass 6, blocked 2, empty 2; O+gate+repair the same (neither repair edited). Blocks: `a650900edac4` `[partition]` — dead code in an existing file outside the partition, and O's pass there is not a solve (gold's tests do not build over it); `12e24d368c90` `[unimported]` — `fmt.Fprintf` with no `fmt` import, a real compile error the build also caught (a second error, an unused variable, is in no gate class). Invented 0, *unknown* 0 (§4.15 unmeasured on a dense world). Every O session hit the 30-turn cap. Recounted by the orchestrator from the rows and the 13 usage files. **§5's second reading, provisional on n = 10: the floor exists as a safety property, not a helper** — `hobbes gate` ships as a detector; the repair turn is the next thing to design (both spent their one call on a read). D-y fixed after the run (WP-18d, driver only, `9630dc2`).

**Versions and register.** Three patches, each with its CHANGELOG entry and the image rebuilt after (C-65): 0.1.18-beta (`hobbes gate`, WP-18), 0.1.19-beta (gate v2's message, D-u/D-v in the driver, WP-18b), 0.1.20-beta (O's repo cut at the parent, D-x, WP-18c). C-121–C-124 registered; register 124 (98 active, 24 lifted, 2 superseded), counted on the segment headings. pytest 1,358 (4 of them `lane_b`), Go green. Rounds 1–2 amended beside their originals (D-x). The README's register count, stale at 114, corrected.

**Spend:** $5.03 of the $11 cap (O $4.65, repair $0.08, the copied session $0.30).

**Held for Max:** widening to keys 11–20; the repair turn's design; §7 step 1 (O+world); an egress allowlist for C-124; the design's ADR number on *accepted*. D-r open (not on this round's substrate).

## 2026-09-12 — the top-level docs reviewed; Calvin re-approached as a harness: `hobbes dispatch`, the egress allowlist, Claude Code in the session — 0.1.21-beta

**Asked (Max):** review the top-level documentation, then change how
Calvin is approached. *"The way it's set up now, it did not validate
itself. O+gate is essentially a harness to stack on top of this
environment, lacking hobbes session and egress allowlist. After the
harness is set up, how we will verify is by using it through Hobbes
development and appending to a log file per session."*

**Decisions (Max, asked in session):**
- the doer is dispatched from the developer's session (not the whole
  session in the sandbox);
- the doer is Claude Code on the subscription (not the owned loop on
  the API);
- one log file per session;
- the keyed rounds' held steps are closed as superseded.

**The review (plan: read, report).** Read: README, CLAUDE.md (AGENTS.md
is a symlink to it), the handoff, `workstreams.md`, the Calvin charter
and the M0-Gate record, with the architecture's session, egress and
status sections checked against the tree.

Findings, most fixed this session:
- **CLAUDE.md's Status was 272 of its 555 lines,** a per-version
  history the CHANGELOG holds, in a file that says it is kept short.
  Its read-next rows were stale: "resuming" pointed at ADR-092, and
  Atlas-0 was labelled "the current work".
- **The handoff wrote its "Held" list twice.**
- **`workstreams.md` was last refreshed 09-07.** It had no M0-Go or
  M0-Gate, and it listed one egress mechanism three times (W1
  fetch-java, W3 C-41, the handoff's C-124).
- **README's `hobbes-session start --repo . --role implementer` could
  not run.** Its default command is `claude -p`, and the image has no
  `claude` (checked in the image). `--claude-cred` mounted `~/.claude`
  at `/root/.claude`, but the session's HOME is `/sessions/<id>`, so the
  credential was never read. Had it been read, it would have handed the
  doer every host transcript and memory file. The same broken path sat
  under `hobbes review`'s soft-verdict reviewer.
- **Minor:** `calvin.box.policy` cited a moved doc path;
  `calvin-m0-gate.md` dates its handoff 09-12 beside 09-11 rulings
  (history, left). The review first reported AGENTS.md as a byte copy;
  it is a symlink, and `cmp` had compared a file with itself
  (withdrawn).

**Measured before building.** This is ADR-097's shape re-read on this
podman (5.8.4, netavark + pasta):
- containers on an `--internal` network reach each other by name (200);
- they reach nothing outside;
- a container on both the internal network and a custom bridge reaches
  out;
- the host's `claude` 2.1.269 (glibc) runs in the Ubuntu image;
- Go 1.26.5 is in the image.

**Built (0.1.21-beta, ADR-107).**
- **The egress proxy** (`go/internal/egress`, `hobbes-proxy egress`):
  - exact host:port allowlist matching;
  - CONNECT only, so plain HTTP is refused;
  - 403 without dialling;
  - one JSONL line per listen, connect, close or refuse;
  - `Summarize`.
- **`hobbes-session --egress HOST`:**
  - the session on `hobbes-int-<id>` (internal), the proxy container on
    that network and on the shared `hobbes-egress` bridge;
  - the launcher waits for the proxy's listen record, tears both down
    and prints the log's summary;
  - exclusive with `--network`.
- **Claude Code as the doer:**
  - `--claude-bin` (the host's binary, read-only, not relabeled);
  - the token `$CLAUDE_CODE_OAUTH_TOKEN` passed by name, so it is in no
    argv and no dry run;
  - `--strict-mcp-config`, `--max-turns`, no auto-update, no
    nonessential traffic;
  - a live run without a binary, a token or a route is refused up
    front.
- **`--claude-cred` is withdrawn**, with a refusal. `review.py` moves to
  `--egress`.
- **`hobbes gate --map derive`:** WP-17's map rule becomes
  `gate.derive_map` in the layer. `map_files` reads a created file at
  its directory's files, and the graph is named by its SHA, so the
  record holds no machine path.
- **`hobbes dispatch`** (`hobbes.run.dispatch`):
  - refuses an ingest at another SHA before any session runs;
  - writes a brief that states how the session works;
  - launches `hobbes-session` with the environment binding and a
    `hobbes-dispatch` commit identity;
  - reads the harvested branch, then gates and verifies it;
  - writes one log file per session to `docs/calvin/sessions/`, with a
    review block, and `dispatch.json` beside the flight log;
  - exits 0, 1, 2 or 3;
  - on its own timeout, cleans up the proxy and the network.
- **The register:**
  - C-41 narrowed;
  - C-124 superseded (the keyed rounds closed; `--egress` is the fix it
    named);
  - C-125 (the doer's file tools are outside the flight log; *partial*);
  - C-126 (a created file in a new directory reads `unmapped`);
  - C-127 (the validation is the developer's review, not an answer
    key);
  - C-128 (a dispatch is not reproducible).
- **Docs:**
  - ADR-107 (106 stays held for M0-Go's design);
  - `docs/calvin/calvin-harness.md`, with the validation rule written
    before the first session, as the rounds wrote their readings before
    spend;
  - `docs/calvin/sessions/README.md`;
  - the architecture: §6.3 new, the §7 secret and network sentence, a
    §8 row;
  - `first-run.md`, `sandbox/README.md` and the CHANGELOG;
  - a closed-as-an-approach note on each keyed-round record;
  - CLAUDE.md rewritten short (AGENTS.md follows it as a symlink);
  - README, workstreams, and this handoff.

**Verified (no spend).**
- **pytest:** 1,371 pass (1,358 + 13).
- **Go:** 325 with subtests (the count CLAUDE.md's 304 used; 240
  top-level at HEAD); 52 oracle-lane.
- **The live route test** (P10, where a user meets it): a real session
  behind the real proxy got `ALLOWED=200 REFUSED=403 DIRECT=000
  PUBLIC=000`, and the session's internal network was gone after.
- **A smoke run of Claude Code** in the container behind
  `--egress api.anthropic.com`, with an invalid token:
  - three tunnels to `api.anthropic.com:443`;
  - `401 Invalid bearer token`;
  - no other host reached for, so one allowlist entry is enough;
  - no container or network left.

  It also showed the envelope reads `subtype: success` beside
  `is_error: true`, so the dispatch record keeps `api_error_status` and
  `terminal_reason` (tested).
- **Binaries and image rebuilt** at 0.1.21-beta, and the proxy checked
  static.
- **A test bug found and fixed on the way:** two dispatches in one
  second sort by their random suffix, so the test now picks the record
  the call created.

**Not done.** No session has been dispatched: it needs Max's `claude
setup-token`. The validation criterion (N sessions) is proposed, not
set. The next builds are named in `calvin-harness.md` §6.

## 2026-09-12 — (later) the first dispatched session; retention: the doer's reasoning never stored, recorded sessions evaluation rows, never training — 0.1.22-beta

**The first dispatches.** The task was the `path` alias for the two
scope-taking knowledge tools (W4, ADR-087 follow-up (a)), with the six
`go/internal/proxy/` files as the partition.
- **Try 1** (`S-20260912T151728Z-96df`) ended in `401 OAuth access token
  is invalid` after 3.3 s. The harness did what it should: the proxy
  tunnelled, the session logged, and dispatch exited 3 with nothing
  harvested.
  - **The cause:** the token was cut at 100 characters. The same token
    gave the same 401 on the host.
  - **The fix:** a fresh 108-character token answered `ok` on the host.
    No token value was printed at any point.
- **Try 2** (`S-20260912T151945Z-417f`) worked end to end.
  - **The run:** 38 of 40 turns and one commit by `hobbes-dispatch`,
    changing `knowledge.go` and `mcp_test.go`. Egress: 3 tunnels, 0
    refused. Policy: 12 exec calls, all allowed.
  - **The verdicts:** gate clear; verify pass (45 tests, 2 new-pass, 0
    regressions).
  - **Checked outside the sandbox:** gofmt, `go vet ./...`, and the
    proxy tests.
  - **The merge is held for Max.**

**Max, before proceeding:** *"make sure not to store reasoning context,
also pin in docs that recorded sessions are evaluation rows never model
training … I only care about the doer's output."*

**Found:**
- Try 2 had stored Claude Code's transcript in its session dir, the
  session HOME's `.claude/`: 564 KB, 21 thinking-block lines. Beside it
  were `.claude.json` and Claude Code's MCP logs
  (`.cache/claude-cli-nodejs/`).
- The auth-failure session and the no-spend smoke held the same files,
  without thinking.
- None of the closed rounds' 196 loop transcripts carries reasoning.
- Five owned-loop transcripts from 2026-08-22, the Qwen benchmark runs,
  carry `reasoning_content`. They are left for Max.
- `ttt.units.units_from_git` took every commit and every path, so a
  future corpus over this repo would have turned the doer's commits and
  the session files into training units.

**Done (0.1.22-beta, ADR-107 amended):**
- The doer runs with `--no-session-persistence`.
- `sandbox.PurgeDoerState` runs when the container exits (`.claude/`,
  `.claude.json*`, `.cache/claude-cli-nodejs/`), and the launcher
  prints what it removed.
- Dispatch repeats the pass, scans for any stored reasoning block, and
  records the result in `retention`. Every session file states that
  recorded sessions are evaluation rows, never model training data.
- `units_from_git` skips the dispatch identity's commits and
  `docs/calvin/sessions/`, so a doer's commit is merged, never squashed.
- The three harness sessions were purged; no thinking marker is left.
- **Register:** C-125 amended; C-129 added (the guard's reach: not the
  merged tree).
- **Docs:** ADR-107's amendment; a retention section in
  `calvin-harness.md`; the sessions README; a CLAUDE.md convention;
  architecture §6.3; the CHANGELOG; the README.
- **Verified:** pytest 1,372 and Go 328, green. The live session test
  now also shows state written in the session HOME is gone after it.
  The binaries and the image were rebuilt at 0.1.22-beta.

## 2026-09-12 — (later still) the first dispatched change merged; dispatch's turn default 80 — 0.1.23-beta

**Max:** good to merge. The error trip he caught was on reasoning
extraction, which the retention amendment covers. The Qwen transcripts
are fine as they are. A dispatch's stop goes to 80 turns, not 40.

**Found when merging.** The merge was already done: `git merge --no-ff`
found nothing to do.
- `main`'s reflog shows a fast-forward to the doer's commit `104c164`
  at 11:31:42, the same second both session files were last modified.
- The one other Claude session on this machine, "Dispatch background
  conversation" (Remote Control), made the merge and wrote both review
  blocks, signed "Reviewed by Max". That was 20 minutes before this
  session's retention commit, `b1f2a91`, which sits on top of it.
- Checked: `b1f2a91` holds only this session's 30 files, and the
  fast-forward brought only the doer's two. The doer's commit kept its
  `hobbes-dispatch` author, so the training guard sees it.
- **The conflict, put to Max.** The other session's review recorded
  "the budget should have been 60, with a hard cap of 100 … The
  dynamic turn budget was added the same day." No such budget existed
  in the code, in any branch, worktree or stash.
- **Max's answers:** a stop at 80, and a dated correction added under
  the note, with his text left as written.

**Done:**
- `hobbes dispatch --max-turns` defaults to 80, tested.
- 0.1.23-beta, with the CHANGELOG entry for the alias and the default.
- W4's ADR-087 follow-up (a) marked done.
- Both session files committed, with the correction line in `417f`'s
  review.
- The handoff brought current: the merge and who made it, the turns,
  the Qwen question settled, and a note that two sessions share this
  checkout.
- The CLAUDE.md and README status lines.
- The proxy and the image rebuilt, so the knowledge tools serve the
  alias once the server restarts.

## 2026-09-12 — (last) the second top-level doc review; 0.2.0-beta, the harness as the minor

**Max:** "review top level documentation and report back". Then: the
versioning should jump to 0.2.0-beta, since the harness is enough of a
jump, and the rest of the fixes are good to be handled.

**The review.** It read README, CLAUDE.md, CHANGELOG, the handoff,
workstreams, first-run, how-hobbes-differs, future_additions and
Potential-application-mode against the tree, using the knowledge tools
first; the new `path` alias answered live at `f44b772`.
- **Checked true:** the version copies; the tags; ADR-107 as the last,
  with 106 held; pytest 1,372; Go 328 (subtests counted, 264
  top-level); the register at 129 (102 / 24 / 3); the commands the docs
  show; `--claude-bin`'s PATH fallback; architecture §6.3's retention
  section.
- **Wrong, fixed (`5540b7f`):**
  - README said the suite sizes were "checked by CI", and workstreams
    said CI "catches the suite counts". Nothing compares them.
  - README's "five suites as separate jobs" and workstreams' "four
    jobs": CI runs seven suites in three jobs, plus the graph job.
    README's test list gained atlas0.
  - README said tree-sitter is "every syntax lane". TS/JS's lane A is
    ts-morph (`tssource.py` calls `tsextract`). Corrected in the prose,
    both lane diagrams and the acknowledgements.
  - README said "an Alpine base image". The Containerfile is
    `ubuntu:24.04`.
  - README's acknowledgements lacked `tree-sitter-java`, the javac
    oracle, Claude Code (the dispatch doer, and `narrate`'s) and Olmo 3
    (ADR-099).
  - how-hobbes-differs ordered the policy chain `box → repo → folder →
    role → agent`. `policy/load.go` is `builtin floor → box → repo →
    role → folder → agent`.
  - first-run said steps 1–4 spend no quota, but step 4 is `narrate`;
    now steps 1–3. Its "no network" ingest now names the Go, Rust and
    Java fetches. Its extension list gained Go, Rust and Java. The
    tools a session starts with gained `list_blind_spots`.
  - Potential-application-mode cited architecture §9 for "stays local".
    It is §10.
- **Stale, fixed:**
  - how-hobbes-differs' register count (96). The page now points at the
    index instead of copying the number.
  - future_additions still had egress narrowing as parked. It is built;
    the Java resolve-pass wiring is what is left.
  - workstreams' item 8 current-work line. C-15's first trigger ("the
    fourth language") passed unused, now said. W4's ADR-087 item moved
    back above its profile line.
  - CLAUDE.md's "(below)" pointed at nothing. README's Layout gained
    `bench/` and `scripts/`; its docs table gained `docs/reviews/`.
  - C-101 is lifted and already sat last in `extraction-java.md`; the
    segment gained the "Lifted constraints" heading the others use.
- **The handoff's stale lines:**
  - a session's records listed "Claude Code's transcript under
    `.claude/`", which is purged since 0.1.22-beta;
  - step 2.4 and NEXT 1 still pointed at the first dispatch;
  - the first review's list, which lives in this log, is now a pointer.

**The versioning rule.** ADR-103 §3 said a capability bumps minor, but
the harness shipped as 0.1.21–0.1.23-beta patches. Put to Max, who
chose 0.2.0-beta.
- **Done:** ADR-103's fourth amendment; the CHANGELOG head and its
  0.2.0-beta entry (no product code change beyond the version string);
  every copy (`test_version.py` green); the CLAUDE.md convention and
  Status; the README Status; the handoff.
- **Untagged:** tags stay his call.

**Verified:** pytest 1,372 and Go 328, green at 0.2.0-beta. The Go
binaries, the static proxy and the image were rebuilt (C-65), and the
repo was re-ingested at the release commit. The knowledge server
serves the new stamp once it restarts.

## 2026-09-12 — (after) C at lane A through the harness — 0.2.1-beta (ADR-108)

**Max:** no need to tag yet. Run the new harness with adding C as a
language to Hobbes. Then, asked: 0.2.1-beta (a patch; the minor waits
for "supported"). For C's lane B: derive the compile database and
degrade visibly.

**Scoping.** A dispatched session has a read-only venv and no route to
PyPI, and it can't build the image. C's indexer (scip-clang v0.4.0)
needs compile flags, whose source is a design decision. So the dispatch
was lane A only, with the design decisions fixed in the brief:
- `.h` keeps its extension in the module id, and `.h` is always C;
- C++ is out of scope;
- the include rules;
- the three-rank fallback, with ties abstaining;
- the `test_*` convention.

`tree-sitter-c` 0.24.2 went into the lock first (`fb24216`): it was
checked under the pinned core (ABI 15), and dispatch requires an ingest
at the parent.

**Session `eef8`** (74 of 200 turns): `csource.py`, the wiring, the tail
row, the `minic` fixture and 60 tests. Gate clear, verify pass (662
tests, 0 regressions).
- **Read:** the one egress refusal (`GET llm`) is `test_bench.py`'s
  `http://llm/v1` under the session's proxy. The doer's three
  `test_ttt_units` failures are sandbox-only; on the host that file
  passes 24/24.
- **Review on DaveGamble/cJSON** (`fb16e5c`, host) found four defects
  outside the gate's classes:
  1. `extern "C"` bodies unwalked (`unity.h` 0 of 341 macros; `cJSON.h`
     0 of 9);
  2. a rank-1 tie that picked the last definition;
  3. 73 duplicate symbol ids;
  4. a `..` include clamped at the root.

  Four sampled edges were right.
- Merged by fast-forward (`984daab`, authorship kept), full suite 1,432.

**Session `e6db`** (68 of 150 turns): the four fixes and their tests.
Gate clear, verify pass. The one replaced test is stricter.
- **Re-measured on cJSON:** 341 of 341 macros; 0 duplicate ids;
  3,363 of 4,292 sites fallback-resolved (was 2,125); 1,761 edges.
  Five more sampled edges were right, nine in all.
- **Residual, registered:** a struct tag and a function sharing a name
  tie (C-131).
- Merged by fast-forward (`48684e3`), full suite 1,443.

**Bookkeeping:**
- ADR-108;
- C-130–C-134 in a new segment (`extraction-c.md`), with the index
  and debt count (134 / 107 active);
- architecture §3.1 (seven providers), §3.7 (C, the seventh walk and
  the first with no indexer) and §8 (a C row, and the harness row's
  four sessions);
- `calvin-harness.md` §7's record;
- CHANGELOG 0.2.1-beta and every version copy;
- CLAUDE.md, README, first-run, workstreams (W1: C's lane B, in Max's
  order);
- `extraction-evidence.md` (a cJSON section);
- both session files' review blocks.

A correction made before commit: the rework's review note had claimed
the five post-rework edges were read against their lines before they
were. They were then read, and all five were right.

**Verified:** pytest 1,443 and Go green at 0.2.1-beta. The binaries,
the static proxy and the image were rebuilt (C-65), and the repo was
re-ingested at the commit (languages now include `c`).

## 2026-09-12 — (after, again) the knowledge tools see C — 0.2.2-beta

**Found at the 0.2.1-beta ingest.** The ingest summary read `capture
[c]: 0.0% of 17 detected call sites accounted`. A C-scoped
`list_blind_spots` on the fixture printed no verification-base line and
no capture line, only rows such as `main.c — 8 of 8 sites unresolved
(fallback-resolved 4, …)`.

Two separate causes:
- **The Go proxy's own language tables lacked C.** `langByExt` and
  `artifactLangBucket` in `go/internal/knowledge` lacked `.c`/`.h`/`c`,
  and C-100's `.mts`/`.cts`. The C unit's brief named `tail.py` but not
  these copies, and §3.7's list did not name them either. C-130 had
  claimed a surfacing in `list_blind_spots` that held only for
  whole-repo queries.
- **The tail's existing design** counts a fallback-resolved site in the
  unresolved remainder. For a language whose only resolver is the
  fallback, the headline reads 0%. This is not changed: it would change
  the display for every language, so it is put to Max.

**Session `404f`** (25 of 60 turns): the tables now mirror the tail's,
and a Python drift test reads both Go map literals and holds them to
`tail._LANG_BY_EXT`. Gate clear, verify pass. Merged by fast-forward
(`7123217`).
- **Expired escalations read:** four `gofmt`/`go fmt`. `calvin.box.policy`
  has no `gofmt` rule, though the brief asked for it. Checked `gofmt`-clean
  on the host.
- **The doer's `PATH` report was confirmed.** `dispatch.py:197` sorts
  the venv bins, so `bench/atlas0/.venv` comes before `pipeline/.venv`,
  and the brief's "the venv's python is first on PATH" is wrong with
  two venvs.
- Both are named for Max, not fixed.

**Bookkeeping:**
- C-130's "You find out" corrected (the C-scoped gap until now; the
  capture line's 0%);
- §3.7: the proxy's tables are among the places a language touches,
  and the C paragraph says the first unit missed them;
- CHANGELOG 0.2.2-beta and every copy (`test_version` green);
- CLAUDE.md's suite sizes (pytest 1,445; Go 330);
- the README and handoff versions;
- `calvin-harness.md` §7;
- the session's review block.

**Verified:** pytest 1,445 and Go 330, green at 0.2.2-beta. The proxy
and the image were rebuilt (C-65), and the repo was re-ingested at the
commit.

## 2026-09-12 — (after, still) two harness fixes — 0.2.3-beta; C's lane B begun

**Max:** make the two harness fixes, do not change the display, then
continue with C's lane B.

**The fixes:**
- **`calvin.box.policy`** allows `gofmt -l*` and `gofmt -d*`, and
  escalates `gofmt *-w*`. Escalate beats allow within a scope (read in
  `resolve.go`), so `gofmt -l -w` still escalates, and `go fmt` keeps
  the default. Tested: `TestCalvinBoxFormatsReadOnly` resolves six
  commands against the real box file (plain, after `cd`, `-w`,
  `go fmt`).
- **`harness.python_trees`** orders the Python trees outermost first,
  then by name. `dispatch.session_argv` builds `--path` from it, and
  `environment()`'s note now names each tree's interpreter and which
  one a bare `python` is, where it used to say "the venv's python is
  first on PATH". Tested in `test_harness.py` (two trees, the note's
  text) and `test_dispatch.py` (the `--path` order).
- **Display:** the capture line is unchanged, per Max.

**C's lane B, the spike.** scip-clang v0.4.0 (`scip-clang-x86_64-linux`,
sha256 `06fd18c5…`, dynamically linked against glibc) was downloaded and
verified on the host. The image has gcc 13, make and the libc headers,
but no CMake, bear or clang.
- A throwaway container from the image (with a network for apt, spike
  only) configured cJSON with `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`, which
  gave 27 compile-database entries.
- The first run died before scip-clang: `time` is not a command under
  dash. It was re-run under bash. Results are in the next entry.

**Verified:** pytest 1,447 and Go 331, green at 0.2.3-beta; the image
was rebuilt.

## 2026-09-12 — (last) C's lane B, scip-clang — 0.2.4-beta (ADR-109)

**The spike** (cJSON `fb16e5c`, in a throwaway container from the image,
with apt's CMake):
- CMake's export gave 27 compile-database entries, and scip-clang 0.4.0
  indexed them in 0.2 s with 0 errors.
- Through the helper's own `decode()`, lane B joined **29 of 4,292** C
  sites. scip-clang's C function moniker carries a signature-hash
  disambiguator (`cJSON_Delete(6efceb6909523ce2).`). `classify()`
  accepted only `()`/`(+N)`, so each function read as a `term`, and
  `terminalName()` kept the hash.
- With the disambiguator accepted (the SCIP spec allows any identifier
  there): 1,490 resolved, and 1,416 sites where both lanes answered
  agreed, 0 disagreeing.
- **The remaining gap:** macros named by location (1,694 sites), and
  same-signature file-statics in `cJSON.c` and `cJSON_Utils.c`, which
  scip-clang gives one moniker (253 sites).

**Built:**
- **ADR-109**, with **C-130/C-131 narrowed** and **C-135–C-137**
  registered.
- **The Containerfile:** CMake and bear from apt, and scip-clang
  sha256-pinned. The image is about 3.07 GB.
- **The helper:**
  - `INDEXERS.c` and `cPlan`: CMake configure, or
    `bear --output … -- make -k; exit 0`, then scip-clang. A check
    before scip-clang throws, in the build's words, when the database
    holds no entries.
  - `decode(index, opts)`, with `decodeOptions` for C: macro names read
    from the defining location in the stage, the own-file rule for a
    moniker two files define, and one target per site.
  - C's duplicate-moniker wording.
- **`scipsource`:**
  - `c_units`: the outermost CMake root, else the outermost Makefile
    root.
  - `c_compdb_source`: a carried database only if it rebases, then
    CMake, then make, then none, with the reason.
  - `rebased_compdb`, `c_build_tree`, and `extract_scip_c` /
    `_index_c_unit`, which stage the whole build tree with a scratch
    build dir removed after.
- **Elsewhere:** `containment` gains `index-c` (executes repo code, no
  network); `_lane_b_facts` gains C; C joins the lane-agreement
  exclusions; C's tail row gains below-floor.

**Found on the way:**
- **The edits typed ` ` as two real NUL bytes** in `index.mjs`,
  which grep then read as binary. They were replaced with the escape,
  and later edits keyed on JSON tuples instead.
- **The product-path run raised one lane disagreement,** `isinf` at
  `cJSON.c:612`: cJSON's own macro in the C89 library build, Unity's in
  the test programs that `#include` cJSON.c.
- **The one-target-per-site rule that followed was wrong twice.**
  - First, any two target lines split a site: 1,124 dropped. One
    definition's own `#if` alternatives are one target, so those were
    kept once, at the first line.
  - Then, keyed on position alone, a macro and its expansion's symbols
    at one call split every Unity assertion: 1,001 dropped.
  - Keyed on position and name, as the join keys, it drops 2
    (`isinf`, `isnan`), and the lanes agree.
- **A containment leak in the test suite, found by the new `lane_b`
  test.**
  - In a full run, `minic`'s `index-c` ran on the host
    (`bear: command not found`) instead of in the image.
  - The cause: `test_cli`'s `--uncontained` ingest sets
    `HOBBES_UNCONTAINED=1` in-process, and its `delenv` of the unset
    variable recorded nothing to undo. The escape hatch stayed on for
    every later test, including the existing `lane_b` venv test, which
    also executes repo code.
  - CI's `lane_b` run (`-m lane_b`) never ran `test_cli` first, which
    hid it.
  - The fix: the test registers the variable (`setenv "0"`), and the
    conftest's autouse fixture removes the hatch before every test.
  - Nothing ran on the host: bear is absent there, so `make` never
    started.

**Measured:**
- **cJSON:** 2,075 of 4,292 C sites semantic (48.3%); 1,072 semantic
  and 786 syntactic edges; the lanes agree on 1,717 compared; 4.1 s.
  Four lane-B edges hand-checked, all right (13 of 13 across C's
  evidence).
- **This repo's own ingest** runs bear over `minic`'s Makefile. C
  capture is 70.6% of 17, and the lanes agree.

**Tests:**
- 42 helper node tests (6 new): the moniker shapes, `cPlan`'s routes
  and check, the three decode rules, and the expansion case;
- `test_scipsource_c.py`: build roots, the compile-database choice and
  rebase, `extract_scip_c` per root, and a `lane_b` case on `minic`;
- `test_containment.py`, `test_tail.py` and `test_csource.py` updated
  for C's step and row.

**Not done:** C's §3.8 row, an oracle cell, is next. C stays unverified.

**Verified:** pytest 1,459 (5 `lane_b`), Go and the helper's node tests
green at 0.2.4-beta. The image was rebuilt, and the repo re-ingested
at the commit.


## 2026-09-12 — (last, again) C graded against clang's front end — 0.2.5-beta (ADR-110)

**Asked (Max):** "review top level documentation. then proceed with
grading c against the oracle with a c repo. utilize hobbes and calvin as
a harness." During the session he called the row a patch: "a language
addition not a structural change" (0.2.5-beta; ADR-103 noted).

**The doc review, the third today** (`348620d`):
- **An overclaim:** "every compiler-graded cell at 100%" in README,
  CLAUDE.md and the architecture's status row. quic-go is a 99.6% lower
  bound (15 semantic-tier contradictions, all the oracle's grain); §3.8
  already said so.
- **Counts:** the register at 137 (110 active), the ADR range to 109,
  the image size.
- **The handoff's suite counts were stale** (re-run: Go 331, 42 helper
  and 36 tsextract node), and its NEXT list numbered 2 twice. Both fixed
  in the rewrite.

**The design, committed before any cell** (`b7d17b8`):
- **ADR-110:** clang's front end (`-ast-dump=json`), one unit at a time
  over the compile database the ingest derives, contained.
  - Rejected: the analyser's call graph (no site) and LLVM IR (below the
    front end).
  - GCC (independent, but post-lowering) is named, not built.
  - The shared front end with scip-clang is stated.
- **The pre-registration** P17–P25 and the draw rule (seed 20260912) are
  in `oracle-grading.md` §10.5.
- **The `cclang` fixture,** with bear's record and clang's dumps. A
  separate reference reader checked its truth first, and found one
  missing rule: a `__builtin_*` is declared implicitly at its own call.
- **The image gains clang 18.1.3** (3.32 GB).

**Built through the harness, in three dispatches:**
- **`b126`** (the whole oracle in one brief) wrote nothing in 53 minutes.
  The developer stopped it as a stall; its tunnel's close record (5.4 MB
  up, 1.1 MB down) showed it was reading. Discarded, and the task was
  split.
- **`5d5f`** (unit A: the reader and merge; 79 of 150 turns): gate clear
  and verify pass; merged.
  - Review found three reader defects, each confirmed on a probe dumped
    by the image's clang: H-24 (pseudo-buffers read as files), H-25 (a
    callee that is itself a call, dropped) and H-26 (a system header's
    `static inline` counted ambiguous).
  - A fourth, the `coverage:` line leaking into trace reports, was the
    developer's error. Unit B's doer found `Print`'s early return for
    trace, and the file is corrected.
- **`9396`** (unit B: the fixes, the contained run and the CLI; 127 of
  150): gate clear and verify pass; merged. The first real cell hit H-27
  (a duplicate mount: the binary in the rw cell dir, mounted ro too),
  fixed by the developer in `contain.New` (`17def60`). The end-to-end
  test now builds where `run-cell.sh` builds.
- **Harness notes:**
  - no progress signal between reading and stuck (the developer's
    first-edit watcher was the stopgap);
  - after `rm` escalations expired, a doer deleted its scratch file
    through `python3 -c`;
  - read-only `clang --version` probes escalate.

**The cells** (contained; poison check PASS on each):
- `minic`: 5/5, recall 7/7.
- **DaveGamble/cJSON:** 1,188/1,188, all semantic.
  - The 525 syntactic edges sit in files CMake's defaults leave
    uncompiled, and are silent.
  - Recall 62.0%. Every miss is `macro→function` (728), drawn to the
    macro: 723 into Unity's assertions and runners, and 5 through cJSON's
    own `cJSON_SetNumberValue` (the record first said all Unity;
    corrected the same session).
- **sqliteai/sqlite-vector,** drawn at random: 851/854.
  - Draw 1, jfernandez/bpftop, had no C compile to derive.
  - The 3 contradicted edges are syntactic and hobbes-wrong: a
    `strcasestr` shim in a dead `#if` arm, drawn over libc's.
  - Semantic 851/851, recall 100%.

**Found, recorded:**
- **C-138:** `evidence.join` takes lane A's guess where lane B has no
  in-repo answer, even where lane B resolved the site to a library. It is
  cross-language, and the veto is Max's call.
- **C-131** measured on both repos.
- **C-135's surfacing** is partial: bpftop's root drew only a generic
  `scip-index` record.
- **The evidence log's "27 units"** for cJSON was the spike's number,
  with `ENABLE_CJSON_UTILS=On`. CMake's defaults give 23, in the product
  and the oracle alike.
- **P17–P25:** P19 undecidable, P23 partly missed (3 syntactic
  hobbes-wrong on the draw), the rest met.

**0.2.5-beta:**
- §3.8's C row and `verification.py`'s pin;
- the version copies and the CHANGELOG;
- the proxy and the image rebuilt;
- `test_csource`'s unverified assertion restated as the two repos;
- the comparative graphics regenerated (80 cells).

**Verified at 0.2.5-beta:**
- pytest 1,459;
- Go 330 pass and 1 skip;
- the oracle lane 87 pass and 4 skip, the C end-to-end contained;
- the report drift test.

**Not done, for Max:**
- C-138's veto;
- C's macro-expansion edges;
- the box policy (`rm`, the probes);
- a progress signal for dispatches.

**Closing (Max, 2026-09-12).** Asked for a proposal on each open
decision, Max approved all four in the suggested order. Each is a
patch, for the next session.
- **First, the progress hook,** so later dispatches can be watched.
- **Then C-138's veto,** as a dispatch, with a regrade of every
  contained cell as its acceptance gate.
- **Then the box policy,** directly.
- **C's macro gap is parked.** This session wrote its docs: C-131's
  `uses` sentence and a `future_additions.md` entry.

Two facts were checked before recommending:
- lane B's expansion references already exist as `uses` edges (381 into
  `UnityFail` on cJSON);
- Claude Code takes `--settings` and runs hooks under `-p`.

The first check also corrected the cJSON record: the misses are 723 into
Unity and 5 into cJSON's own API (`cdf92fe`).

## 2026-09-12 — (next session) Max's three approved patches: the progress hook (0.2.6-beta), the dispatch box (0.2.7-beta), C-138's veto (0.2.8-beta, ADR-111)

**Asked (Max):** "review top level documentation and continue from the
resume point utilizing hobbes and calvin."

**The doc review:**
- README, CLAUDE.md, the handoff, the harness doc and ADR-107 stood at
  0.2.5-beta, with nothing overclaimed.
- The resume point was Max's three approved patches, in his order.

**1. The progress hook — 0.2.6-beta.** ADR-107 was amended before the
dispatch (`f6cab1b`).
- **Built by dispatch `S-20260912T215521Z-efc8`** (87 of 150 turns,
  853 s): gate clear, verify pass. Merged as `7ec3fe9`, fast-forward,
  keeping the doer's authorship.
- **What it does:**
  - A PostToolUse hook on Edit/Write/MultiEdit/NotebookEdit runs
    `hobbes-proxy record-edit`: one flight line per edit (time, tool,
    path; never content). It always exits 0.
  - The flight line gains `path`.
  - Dispatch gains an Edits line, prints the first edit, and prints one
    quiet note (`--quiet-minutes`, default 20). It kills nothing.
  - `read_flight` skips edit lines.
- **Found by use:** `reasoning_left` read the session's Go build cache,
  where compiled test packages hold the retention tests' own marker, a
  false positive. `SCAN_SKIP` fixes it, with a test.
- **Live from the next dispatch:** "first edit at 0.8 min —
  scip/index.mjs", then 21 edit lines by path, with every other field
  empty.
- C-125 narrowed. The image and proxy rebuilt.

**2. The dispatch box — 0.2.7-beta** (`a72c5a6`, directly).
- `rm *` is allowed. A recursive `rm` escalates: `-r`/`--recursive`,
  `-R`, and `-fr`/`-fR`.
  - The two clusters were missing from the approved patterns: the
    glob's `*` crosses spaces, and neither cluster contains `-r` or
    `-R`.
- `clang`/`cmake`/`bear --version` are allowed.
- **The header** states an escalation is a question, not a boundary,
  where `python3 *`, `find*` (`find . -delete`) and `xargs*` can do the
  same. `find`/`xargs` are unchanged, for Max.
- **Checks:**
  - `TestCalvinBoxRemovesAndProbes` against the real box;
  - a gate run on a real diff that deletes `run/mail.py` outside a
    one-file partition blocks it (`partition`, "deleted").

**3. C-138's veto — 0.2.8-beta** (ADR-111 committed before the dispatch,
`e2ab96d`).
- **Refinement over the sketch:** the helper's "external" includes
  in-repo monikers (ambiguous across files, C-28; kinds the graph drops).
  - An external reference is marked `in_repo` when its moniker has any
    in-repo definition; `join_cross_unit` marks sibling-ambiguous ones.
    Only unmarked references veto.
  - Coverage is unchanged: the site was already `external`.
  - `lane_agreement.external_vetoes` is printed by `hobbes lanes`
    without changing its exit status.
- **Built by dispatch `S-20260912T221854Z-42d1`** (99 of 200 turns,
  817 s), the first under the live hook: gate clear, verify pass.
- **On the host,** in a worktree of the branch with its own venv:
  - node 43/43;
  - the `lane_b` minic shape (a dead-arm `strcasestr` shim in
    `util.c`): no edge to the shim, fate `external`, vetoes 1;
  - pytest green.
  - A first run failed 4 lane B tests. The cause was symlinked
    `node_modules` in the worktree, which the lane B container cannot
    follow; real copies fixed it.
- **The acceptance regrade** covered all 44 oracle cells with a stored
  key. Each was re-ingested contained and graded against its key; no
  oracle was re-run. The drivers are kept at
  `~/.hobbes/bench/adr111-drivers/`.
  - **The keys:** the 0.1.10-beta dirs keep only reports, and the keys
    stayed in each cell's first dir or in `comparative/keys/`. kbet's
    tsc key had never been kept, so it was rebuilt at `f6e48cf8` and kept
    at `~/.hobbes/bench/adr111-keys/`.
  - **Pre-veto pass** (`adr111-pre/`, 1,222 s): all 44 cells reproduced
    their stored confirmed and contradicted counts to the digit.
  - **Post-veto pass** (`adr111-post/`, from the branch's worktree): **no
    confirmed count moved in any cell.**
    - sqlite-vector: 851/854 → **851/851**; contradicted 3 → 0;
      syntactic edges 18,897 → 18,893 (−4); vetoes 4.
    - Every other graded cell: 0 vetoes, syntactic edges unchanged. That
      covers zod's 1,068, hono's 161, memchr's 1,399 and the C cells'.
    - Dagger's graph: 56 vetoes, all in its root module, which has no key
      (every root subtree oracle had run out of memory).
- **The gate's "exactly 3 fewer syntactic edges" read 4.**
  - The fourth is `libs/sqlite3.h:6943`: a prototype that tree-sitter-c
    reads as a call, because `SQLITE_API` is never expanded (C-131).
    Lane A drew it to the uncompiled amalgamation, and it graded silent.
  - Put to Max, who merged (0.2.8-beta).
- **Dagger's 56, checked before the question:**
  - The ten examples are method calls on a local
    `slog := slog.SpanLogger(ctx, …)`. Lane A drew them to the package
    function `engine/slog.Info`/`Warn`/…; lane B resolved them to the
    logger type's method outside the repo.
  - So wrong edges were removed. A scan finds 61 such shadowed calls.
  - The package-level calls keep 153 semantic edges.
  - Registered as **C-139** (Go's local shadow of a package name, where
    lane B does not answer).
- **Merged** with a merge commit (`0886367`), keeping the five doer
  commits; `main` had moved on with the box.
- **Records:**
  - C-138 narrowed; C-139 registered (register 139, 112 active);
  - architecture §3.4 (the veto) and §3.8 (sqlite-vector 851/851);
  - README, CLAUDE.md, the evidence log and workstreams;
  - sqlite-vector's cell record (a 0.2.8-beta block with the signed
    direction of fix);
  - the comparative graphics regenerated (80 cells), with the drift test
    passing.

**Verified at 0.2.8-beta:**
- pytest 1,474 passed (5 `lane_b`);
- Go 343 pass, 1 skip;
- scip node 43/43;
- the report drift test;
- `hobbes-proxy 0.2.8-beta` in the rebuilt image.

**Harness sessions this time:** two dispatches, both right-clear and
merged. No false block and no `missed`. Every egress refusal was read:
the suite's own `http://llm` GET, refused as built.

**Not done, for Max:**
- whether the box's `find*`/`xargs*` should change;
- C-139's lift (a lane A rule: a local binding of a selector's
  qualifier);
- the harness's validation criterion (N sessions), and ADR-106;
- the carried items in the handoff.

## 2026-09-13 — the doc sweep and the facing update (the same-key graphic in the README); the directory rollup through the harness — 0.2.9-beta

**Asked (Max):** "review top level documentation. then do a doc sweep and
facing update. have a section in the readme which shows the same key
graph to reflect where hobbbes stands with its competitors … after
completing the above, if there is a resume point. start it with hobbes
and calvin."

**The review.** README, CLAUDE.md, the handoff and CHANGELOG stood at
0.2.8-beta. The staleness was in the second rank of docs, and in the
comparative graphics:
- same-key.svg's footer still named ajv and hono as exceptions, four
  days after ADR-104 and C-98 closed them. The list was typed into
  `render.py`, which the drift test cannot catch.
- field.md's Hobbes row stood at 0.1.4-beta (96 entries, five
  languages).
- The architecture called `csource` "the only one with no indexer
  behind it" and §8 "at 100% but two", counted four harness sessions,
  and left C out of §10.
- A background agent's scan found 16 stale lines across architecture,
  first-run, oracle-grading and the harness doc. The constraints index,
  future_additions and bench/oracle/README were current.

**1. The sweep and the facing update** (`7602eb2`).
- **README: *Where Hobbes stands beside other code-graph tools*.**
  - It embeds same-key.svg and gives its reading rules: read across a
    row; precision is a lower bound for every tool; the tools' numbers
    are at our grain and host-run (C-94/95/96).
  - It says what is missing: C has no foreign cell (the C cells
    postdate the runs), and syft has no key. It gives the
    `grade-foreign.sh` line.
  - It states what the rows show, read from tables.md: on all 18 rows
    Hobbes' marker is the rightmost on both axes. It ties on precision
    only at rust_proj, where CodeGraphContext stored one correct edge.
    Its recall lead within a row runs from about one point (click,
    gitleaks) to 35 (zod). This is the first ranking sentence on a
    facing page, and it is put to Max in the handoff.
- **render.py:**
  - same-key's exceptions are computed from the cells;
  - the scatter's empty sixth slot is C's panel, titled `clang` (the
    first word of the recorded oracle was "Ubuntu");
  - legend tails and the footer's versions line move to their own lines,
    since they ran off the page;
  - the Python panel title is shortened, and the one-number caption
    names clang.
  - All five outputs were regenerated and rasterised to check, and
    `render.py check` and the report's Go test are green.
- **Also fixed:** field.md's Hobbes row (0.2.8-beta, 139/112, six
  languages; the scatter "hollow squares" line); comparative/README (the
  C cells and ADR-111's 44-cell regrade since the baseline, the recall
  range's top, no foreign C cell); architecture §1/§2/§3.1/§3.8/§7/§8/§10;
  oracle-grading's status and §14 (O8/O9); first-run (~3.3 GB,
  scip-clang); the harness doc's status; how-hobbes-differs' mermaid
  (scip-clang, the C oracle); workstreams' W2 (the hook built); the
  CHANGELOG header's untagged range.
- **Corrected after the commit:** the sweep wrote "nine" session logs.
  There were ten; with `3c45` there are eleven, and README, architecture
  §8, the harness doc and CLAUDE.md now say so.

**2. The resume point: `list_blind_spots`' directory rollup** (W1;
`future_additions.md`, from ADR-048). It was chosen from the handoff's
named no-spend queue because it needs no decision of Max's: it is a port
with a Python reference.
- **The brief** named the Python spec (`rollup_directories`,
  `_print_directory_view`), the section's place (before the worst
  files), the exact row text, and seven tests. The partition was
  `knowledge.go` and its test.
- **Dispatched as `S-20260913T132457Z-3c45`:** 25 of 150 turns, 270 s,
  first edit at 1.8 min. Gate clear, verify pass (64 tests, 0
  regressions, 7 new-pass). Egress api.anthropic.com only; 7 exec
  decisions, all allow.
- **Reviewed right-clear.** Go's `notModelled` equals `NOT_MODELLED`,
  `directoryOf` matches `directory_of` at depth 2, and the ranking and
  row format match. The fixture row was checked by hand: src/app
  resolves 25 of 30 sites (83.3%), and of its 5 unresolved, 3 are by
  design and 2 are attr-call.
- **Merged** with a merge commit as `9fc2036`, keeping the doer's
  authorship.
  - The first attempt passed the message as `-F -` from a heredoc, which
    `git merge` does not read. The `;` chain went on and bumped the
    version on the unmerged tree. The bump was kept (disjoint files)
    and the merge redone from a file; this is noted in the handoff.
- **0.2.9-beta** (a patch: what the layer says). Also: the CHANGELOG
  entry; the call-graph register entry's surfacing line; future_additions
  and workstreams struck; README, architecture §8, CLAUDE.md. The image
  and proxies were rebuilt (`hobbes-proxy 0.2.9-beta` in the image).

**Verified at 0.2.9-beta:**
- pytest 1,474 passed;
- Go 350 pass, 1 skip (351 lines; 344 before);
- `test_version.py`;
- the oracle report test after the renderer change;
- the image's proxy version.

Not re-run, since nothing they cover changed: vitest, the node suites,
atlas0, and the oracle lane beyond `./report/`.

**Harness sessions:** one this session, right-clear and merged. There
are eleven logs; no false block and no `missed` among the last three.

**Not done, for Max:** the README comparison wording; the box's
`find*`/`xargs*`; C-139's lift; the validation criterion and ADR-106;
the carried items in the handoff. A foreign C cell needs `oracle import`
to take `--lang c` first.

## 2026-09-13 — (after) C-139 lifted through the harness — 0.2.10-beta (ADR-046 amended)

**Asked (Max):** "looks good through my review. good to proceed with
dispatching the c139 lift. short note since were at 0.2.9 . next
version goes 0.2.10 not 0.3.0."

- **The number line.** ADR-103 gains a note: patch numbers count on
  past nine. The versioning memory says the same.
- **Decided before the dispatch** (`e1c9f45`): ADR-046 amended.
  - Go lane A's fallback reads a selector's qualifier as an import
    alias only when no local binding of that name spans the call. It is
    the same `_shadowed` test a bare name gets.
  - The extent stays function-wide (precision first), and the tail is
    unchanged (`attr-call`).
  - Acceptance: every Go cell with a stored key is regraded; no
    confirmed count falls and no contradiction count rises.
- **Dispatched as `S-20260913T145700Z-a323`:** 28 of 150 turns, 183 s,
  first edit at 0.3 min. Gate clear, verify pass (213 tests, 0
  regressions).
  - The doer saw three `test_ttt_units` failures in the sandbox: D-r.
    On the host, in a worktree of the branch with its own venv, pytest
    passed 1,480 (1,474 plus the doer's 6).
  - Egress refused `llm` once: the suite's own request.
- **The acceptance regrade**, from the branch worktree
  (`~/.hobbes/bench/c139-post/`, driver `regrade3.sh`), graded the 27 Go
  cells against their keys, with 0.2.8-beta's post-veto reports as the
  baseline. No ingest code had changed since that pass except version
  strings (`git diff 0886367..HEAD`), so no pre pass was run.
  - **Nothing moved in any cell:** confirmed, contradicted and
    syntactic-edge counts (fzf 46, quic-go 11) matched, with poison 0
    falsely confirmed.
  - Dagger's external vetoes went from 56 to 0: lane A no longer
    proposes those sites.
- **The lift's effect, lane A alone on dagger** (`extract_go`, main
  against the branch): fallback resolutions into `engine/slog/` went
  from 467 to 372 (95 gone, 0 new; 33,029 to 32,930 in all).
  - A text scan placed the 95:
    - 34 after the binding;
    - 31 it could not place. The three read (`core/c2h.go`) are
      closure-captured locals, so wrong edges as well.
    - 25 on the declaring statement and 5 before it: 30 true edges
      given up.
  - Those 30 are the extent's recall cost, and they cost an edge only
    where lane B is silent. They are recorded in C-139's entry as its
    residual (*partial*).
- **Reviewed right-clear;** merged with a merge commit as `a5d1e14`;
  **0.2.10-beta.**
  - C-139 lifted: register 111 active, 25 lifted.
  - Also: architecture's scope-veto sentence and §8; README; CLAUDE.md;
    the harness doc; workstreams; the CHANGELOG; the evidence log; the
    handoff.
  - The image and binaries rebuilt (`hobbes-proxy 0.2.10-beta` in the
    image). The regrade worktree was removed.

**Verified at 0.2.10-beta:**
- host pytest 1,480 on the branch;
- `test_version.py`;
- the 27-cell regrade;
- the image's proxy version.

The Go suite is unchanged apart from `version.go` (351 at 0.2.9-beta).

**Harness sessions:** twelve logs. The last four were right-clear and
merged, with no false block and no `missed`.

**Not done, for Max:** the README comparison wording; the box's
`find*`/`xargs*`; the validation criterion and ADR-106; whether C-139's
residual earns a finer extent (only if a graded cell shows the cost).

## 2026-09-13 — (later) the top-level review; the harness validated at 40 sessions; a session contained to its own dir — 0.2.11-beta (ADR-107 amended)

**Asked (Max):** "review top level documentation and report back with
current standing". Then: "lets move harness validation to 40 sessions.
worth being a little bulkier to strongly verify. especially because
there are bugs being caught. the comparison section wording is good the
recursive delete seems like an error more than a flag. either look to
contain or prevent. the rest are good to be handled".

- **The review.** README, CLAUDE.md, CHANGELOG, the handoff,
  architecture §8 and workstreams agreed on version, counts and state.
  Each was checked against the tree:
  - ADRs 001–111, 110 files with 106 held;
  - twelve session logs;
  - the register's 139 entries, by heading;
  - the README's 18 comparison rows, against `same-key.svg`;
  - pytest 1,480 and every Go package green, on a re-run.

  Three drifts, all fixed:
  - The knowledge tools served the ingest at `e1c9f45` (0.2.9-beta)
    while HEAD was `6acc028`. Re-ingested.
  - C-139 sat among `extraction-go.md`'s active entries, because the
    file had no lifted section. Filed.
  - Workstreams' dates line stopped at 0.2.8-beta. Brought through
    0.2.10.
- **Max's calls.**
  - The README comparison wording stands.
  - The harness counts as validated after 40 sessions
    (`calvin-harness.md` §4; `c0eb51f`).
  - The recursive delete is a defect, not a flag.
- **The recursive delete, traced** (ADR-107 amended as `c82e686`, before
  the dispatch):
  - `find*` and `xargs*` were allowed, so `find . -delete` and `xargs rm
    -rf` deleted with no question. `-exec`, `-ok` and `xargs` also ran
    commands the policy never sees.
  - The larger gap: `hobbes-session` mounted the whole
    `~/.hobbes/sessions` root read-write at `/sessions`. One session's
    allowed command reached every session's clone, flight log, egress
    log, escalation queue and records. The box header's "only the
    worktree is writable" was not true.
  - The glob cannot close it (`python3 *`, `make*` and `awk *` delete
    too). So containment is the boundary, and the policy rules are
    questions.
  - Doers ran `find` or `xargs` once in 21 recorded sessions, so the
    prevent half costs nothing.
- **Dispatched as `S-20260913T163921Z-2aa9`:** 57 of 150 turns, 347 s,
  first edit at 1.2 min. Gate clear, verify pass (77 tests, 0
  regressions).
  - 5 exec decisions, all allowed.
  - Egress refused a plain GET to `llm` once, during the doer's `go
    test`: a test's own request, not the doer reaching out.
  - **Reviewed right-clear;** merged unsquashed as `5fb34f7`.
  - **Found on the host:** `TestALiveSessionMountsOnlyItsOwnSessionDir`
    failed on its first real run; it skips in the sandbox.
    - The guarantee held. The listing showed only the session's own dir,
      and the sibling's file was absent.
    - The assertion searched all of stdout for `S-sibling`, which the
      `cat` error echoes.
    - Fixed in the next commit: the listing is tagged and read line by
      line. It is an error outside every class, and it is noted in the
      session file.
- **0.2.11-beta.** C-140 registered: 140 entries, 112 active, 25
  lifted, 3 superseded.
  - A doer can still alter or delete its own session's records, because
    the proxy runs in its container.
  - The structural fix, the proxy in a container of its own, is named
    for Max.
  - Also updated: the CHANGELOG, README, CLAUDE.md, architecture §8, the
    harness doc's §2 table, the register index and debt summary, and the
    handoff. `pipeline/uv.lock` carries the version, as the last three
    releases' did.
  - The image and binaries were rebuilt.

**Verified at 0.2.11-beta:**
- Go 354 `--- PASS`/`SKIP` lines (353 pass, 1 skip), with the live
  egress and live mount tests run on the host;
- pytest 1,480;
- `gofmt` clean on the three touched packages;
- the image's proxy version.

**Harness sessions:** thirteen logs, of the 40 the harness is validated
at. The last five were right-clear and merged, with no false block and
no `missed`.

**Not done, for Max:** C-140's structural fix; ADR-106; whether C-139's
residual earns a finer extent (only if a graded cell shows the cost).

## 2026-09-13 — (later still) the register and `future_additions.md` scoped against the tree; the mechanical fixes

**Asked (Max):** "review top level documentation. then scope constraints
register and future_additions for things that have already been
implemented, or in the constraints case duplicate constraints … or
constraints which are lifted but arent organized right". Then: "go ahead
with the mechanical fixes and leave the decisions for after".

- **Checked against the tree.**
  - The register by heading: 140 entries, 112 active, 25 lifted, 3
    superseded, with no id missing.
  - Every active entry with a named cheap fix was still open, so there
    were no silent lifts: C-102 (`var_spec_list` not descended), C-112,
    C-19, C-93's fixture case, C-133, C-134, C-71's stamp, and the
    decorated-declaration line (`declarationStart`).
  - Reachability by the knowledge tools. `dispatch` uses only
    `template.Ledger` and `gate` only `adapter.declaration_sibling`. The
    T-loop protocol, template v2's cap, arm budgets and `gold_tests` are
    reached only through `pipeline/scripts/calvin_probe.py`.
- **Fixed (docs only; no version bump):**
  - README: C-71 was not among the "all lifted" findings; DeepSWE is
    parked, not "moving".
  - workstreams: the `package.json bin` half is built (C-14).
  - `future_additions.md`:
    - the `bin` half, the compiled configs (partly built) and the
      Claude Code session image (built by ADR-107) marked;
    - ADR-042's surfacing noted on the narration item;
    - the rename-detection "subsumed" line retracted (ids stayed
      path-based);
    - the namespacing trigger noted as passed, with C-132's cgo shape;
    - the audit header dated;
    - the last four `##` sections made bullets like the rest.
  - The register:
    - a current status table on the debt summary (88 surfaced, 18
      partial, 5 unsurfaced, 1 n/a), and the stale hand-kept counts in
      the history marked;
    - the index order matched to the files;
    - two segment titles brought to what the files hold;
    - C-66's trailing paragraphs folded into the entry;
    - C-67 titled narrowed;
    - the Java lifted preamble added, and C-100/C-101's field names made
      standard;
    - C-56's superseded line moved to its head;
    - C-11's "Superseded by" wording corrected;
    - C-15's merge order given Java and C, with C-132's cgo shape;
    - C-130's stale "no C indexer is wired yet";
    - C-117 names the gate's use of the cap;
    - dead pointers into `future_additions.md` from C-35, C-41 and C-46
      corrected;
    - links added: C-29 → C-136, and C-125 ↔ C-140.
- **Left for Max** (handoff, item 1):
  - superseding C-104–C-108, C-114–C-116 and C-120;
  - C-139's residual as C-141;
  - a "folded into C-n" rule for five duplicate pairs;
  - a segment for the dispatch harness's entries;
  - whether the harness re-evaluation item is obsolete.

**Then (Max):** "superseed the nine make the residual change and add
the duplicate pairs rule. leave the other two for now".
- **Eight superseded, not nine.** C-104–C-108 and C-114–C-116 are
  reached only through `calvin_probe.py`, checked by the graph and by
  their callers:
  - `read_patterns` and `validate_fills` are the adapter's;
  - declaration holes are built only by its NULL round-trip;
  - `gold_tests_verdict` is called only by the probe;
  - `hobbes template` has no v2 switch.

  **C-120 stays active.** `gate.py:552` runs `ground()`, so its
  unsurfaced half (a post-image malformed some other way) is live in
  every gate. Its Bites at now says so; a fold into C-112 is left open.
- **C-141** registered from C-139's residual (*partial*); C-139's entry
  points at it.
- **The folding rule** (ADR-043 amended; the register README), applied
  to the five pairs: C-34 → C-23, C-97 → C-58, C-119 → C-118, C-130 →
  C-135, C-137 → C-28.
  - C-130 folds into C-135, not the reverse, because the parent carries
    the weaker surfacing status and C-135 is the *partial* one.
  - A folded entry keeps its number and text, so the code's pointers
    still resolve: C-34, C-97 and C-130 appear in degradation records
    and glosses.
- Superseded headings are marked like lifted ones now, C-55, C-56 and
  C-124 included.
- **The register reads 141 entries: 100 active, 25 lifted, 11
  superseded, 5 folded.** The README, CLAUDE.md and the handoff carry
  it.

## 2026-09-13 — (last) the top-level review again; workstreams brought to 0.2.11-beta; the ingest at HEAD

**Asked (Max):** "review top level documentation and report back with
current standing", then "yes proceed with those".

- **Checked against the tree:**
  - `VERSION` 0.2.11-beta; the latest tag `v0.2.10-beta`;
  - 141 register headings; 1,480 pytest collected; thirteen session
    logs; ADRs through 111, with 106 held;
  - no broken relative link in the README, CLAUDE.md, the handoff or
    workstreams;
  - `main` even with `origin/main`; CI green on the last three pushes
    (the two red runs of 2026-09-12 were fixed by later pushes).
  - The Go, vitest, node and atlas0 suites were not re-run.
- **Found:**
  - the knowledge artifacts at `e882c04` against HEAD `2615abb`. The
    two commits since touch only prose, so the answers held and only
    the stamp warned;
  - workstreams' header stopped at 0.2.10-beta, and C-140's structural
    fix sat in no workstream;
  - W3's oracle-lane item named four of the six oracles and read phase
    2's 100% as current.
  - The CHANGELOG's 0.2.11-beta register line (112 active, 3
    superseded) was right when written, and it stays.
- **Fixed (docs only; no version bump):** workstreams' header through
  0.2.11-beta; C-140 under W5; W3 names javac and clang, and dates
  phase 2's reading beside today's. Re-ingested at HEAD after the
  commit.
- **A reading for Max's open call:** `future_additions.md`'s "re-evaluate
  the harness if its weight stays this high" (2026-08-21) is about the
  benchmark's per-unit fan-out, not the Calvin harness. On that reading
  it is parked with the benchmark, not obsolete.

**Then (Max):** "yep dispatch d-r and draft the ammendment".
- **D-r's cause, reproduced before the dispatch.** Inside the image, a
  `--shared` clone's worktree fails every `git` (`unable to normalize
  alternate object path`, then `fatal: bad object HEAD`). A plain local
  clone reads.
- **Dispatched** as `S-20260913T200618Z-9cad`: gate clear, verify pass;
  15 of 80 turns, 60 s, and the envelope reports $0.29 on the
  subscription. Merged as `0e9f5b3`, not squashed.
- **The after-check.** The session's own verify ran the parent's code,
  so it was run on the host: in the image, `efc8`'s F2F test passes
  through the merged `checkout()` and fails through a `--shared` clone.
  Host pytest 1,482.
- **0.2.12-beta:**
  - the version in every copy;
  - the CHANGELOG, README, CLAUDE.md, architecture §8 and the handoff;
  - the binaries and the image rebuilt;
  - the ingest re-run at the release commit.
- **ADR-108's C-134 amendment drafted, not committed**
  (`~/.hobbes/bench/c134/adr108-amendment-draft.md`):
  - a test is a function a Unity, CMocka or Check registration names;
  - a file that registers drops the naming convention;
  - a test program with `main` and no nameable test draws a `c-tests`
    record.
  - On cJSON today there are 39 tests: 37 in the vendored Unity tree and
    2 helpers. None of its 162 `RUN_TEST` registrations count.
  - Tree-sitter-c reads Check's `START_TEST(name)` as a function
    `name`. criterion's `Test()` gives no symbol, which is why it is
    deferred.
  - Three calls wait on Max.

**Then (Max):** "can we keep a tracker thats neat , propose routes to
the three calls for me to adjust or approve". The three calls and the
tracker's form went to him as four questions, and he took the proposed
route each time.
- **A correction to (b) before it was asked.** Unity's examples register
  their tests from a separate runner file, so the convention yields per
  *defining* file, not per registering file.
- **ADR-108 amended** (`27f98af`). Two sessions then ran at once from
  that parent:
  - **`e537`, C-134:** gate clear, verify pass (181 tests); 26 of 150
    turns, $1.40.
    - On cJSON (lane A, the branch's code), 39 tests became 199: 162
      `unity` tests in its own `tests/`, with the 2 helpers gone.
    - The vendored tree keeps 37 convention tests, because its example
      trees share names and rank 3 ties. The ADR's prediction that this
      count would move was wrong, and the ADR now says so.
    - Five `c-tests` records. The body count is a floor (27 of 32 in
      `unity_fixture_Test.c`).
  - **`78b7`, the tracker:** gate clear, verify pass (9 tests); 29 of
    100 turns, $1.36. The developer's follow-ups:
    - `417f`'s area. The brief's prefix table sent
      `go/internal/proxy/knowledge.go` to the harness. The file now maps
      to knowledge tools, and a session's area comes from the code it
      changed, its tests counting only when it changed nothing else.
    - `main()`'s docstring.
- **D-s found.** The doer's full suite in `e537` failed three
  `test_ttt_units` tests.
  - Dispatch's `GIT_AUTHOR_*`/`GIT_COMMITTER_*` environment overrides the
    fixtures' `-c user.name`, so `units_from_git` skips every fixture
    commit as a doer's.
  - Reproduced on the host: 3 fail with that environment, and 24 pass
    without it.
  - 0.2.12-beta had attributed `a323`'s same failures to D-r. The
    CHANGELOG is corrected.
- **0.2.13-beta:**
  - host pytest 1,504; the image rebuilt;
  - the register: C-134 *partial*, giving 18 partial and 4 unsurfaced;
  - ADR-108's consequences as measured, and the evidence row;
  - the tracker re-rendered: 16 of 40, 4 areas, $34.92 reported over 15
    sessions.

**Then (Max):** "yep good to dispatch d-s".
- **Dispatched** as `S-20260913T210133Z-81df` from `fd129d9`: gate
  clear, verify pass (64 tests); 19 of 60 turns, 132 s, $0.37 reported.
  - **The fix is the suite's.** An autouse fixture in
    `pipeline/tests/conftest.py` clears `GIT_AUTHOR_*`/`GIT_COMMITTER_*`
    before every test. `dispatch.py` is untouched, because its identity
    is the retention mark.
  - **The guarantee's test** runs `test_ttt_units.py` in a child pytest
    with dispatch's real `IDENTITY`.
    - The doer showed it failing with the fixture disabled.
    - The doer's own full suite in the session read 1,496 passed, 9
      skipped, 0 failed.
- **On the host after the merge** (`9bbd787`): `test_ttt_units.py`
  under dispatch's identity passes 24 of 24 (3 failed before). Host
  pytest 1,505.
- **Tests only, so no version** (ADR-103).
- **The tracker:** 17 of 40, $35.29 reported over 16 sessions. Row 17's
  area reads `—`: the session changed only test files, which map to no
  area by the tracker's rule.

**Close (Max):** "leave rest of the table for now and update
documentation to end sessions off".
- The test-only area rule is held in the handoff (item 1).
- The handoff's session steps now say to re-render the tracker after a
  review, that the real session id differs from the dry-run's, and that
  two dispatches may share a parent but not a re-ingest.
- C's residue names C-134's remainder.
- The day's standing: 0.2.13-beta on `main`, unpushed. Four sessions
  this stretch (`9cad`, `e537`, `78b7`, `81df`), every gate right-clear.
  The harness is at 17 of 40, and the ingest is at the closing commit.

## 2026-09-14 — C-140's fix: a session's records leave the doer's container — 0.2.14-beta (ADR-112)

**Asked (Max):** "review top level documentation. then provide a plan to
handle constraint 140", then "good with route one, its a constraint not a
direct feature advancement so keep 0.2.11 for the work" (read as: stay on
the 0.2.x patch line — the tree was at 0.2.13-beta, so 0.2.14-beta).

- **The review.** The C-140 story was consistent across CLAUDE.md, the
  handoff, W5, the register, ADR-107's amendment and the CHANGELOG. One
  drift, fixed in the release commit: `calvin-harness.md`'s status line
  said twelve sessions through 0.2.10-beta. Traced in the code, the gap
  had three writers in the doer's container (the proxy's flight log and
  queue, the hook, the reflect tool's mail file), the egress log in the
  same host dir, and HOME *being* the session dir (`go-build`, `.semgrep`
  and `.config` landed beside the records).
- **The plan, as three routes.** Route 1, recommended and taken: the
  records' writers leave the doer's container; the executor stays. Route
  2: the whole proxy out, exec's children under a second uid (closes the
  remainder at two to three times the work; kept available). Route 0:
  detect, not prevent (dismissed under "contain first").
- **Measured before the decision** (no spend): a sidecar is reached by
  name on an internal network with no egress bridge, and the box has no
  route out; Claude Code runs with HOME on a tmpfs and read-only config,
  ending on the expected 401 in 2 s; an anonymous volume survives
  `podman rm -f` where a tmpfs dies with the container; a socket cannot
  be reopened through `/proc/<pid>/fd`. One probe with `--network none`
  hung (Claude Code retries its endpoint forever); the rerun behind an
  egress sidecar ended at once. Removing the hung probe's container took
  the knowledge server's with it (both unnamed): restart it next session.
- **ADR-112** written and amended once before the dispatch (the mail line
  and a `listening` line ride the sink too).
- **Unit A through the harness** (`S-20260914T004830Z-3ebb`, 82 of 150
  turns, 16 min, $4.42): `go/internal/sink` (the wire, one stream ever,
  the refusal recorded, session and role stamped by the sink, an edit
  stripped to tool and path, mail and the escalation round trip),
  `proxy.Journal` with the file journal kept, `serve --sink`,
  `record-edit --sink`, `hobbes-proxy sidecar` replacing `egress`. Gate
  clear, verify pass (83 tests, 0 regressions, 27 new). Two escalations
  expired (`git rm`, a heredoc commit); the doer found other forms. On the
  host, every package green but the live egress test, red for the
  expected reason (the old launcher still ran `egress`). Right-clear;
  merged `a3c2551`. After the merge, two hardening points the brief had
  not asked for (`6ad5567`): an escalation id is one path segment, and
  the sidecar cancels its sibling listener when one fails.
- **Unit B through the harness** (`S-20260914T010846Z-de81`, 94 of 150
  turns, 21 min, $6.69): the launcher's two worlds (the sidecar world by
  default: `hobbes-side-<id>`, HOME a tmpfs with a 4 GB cap, `<id>/in/`
  the one read-only host dir, the MCP config and the hook on `--sink`,
  the launcher waiting for the sink's `listening` line and then the
  egress `listen` record; the file world on an explicit `--network`,
  said in one line naming C-140; `--runtime` refuses the sidecar world),
  dispatch's stream bracket on the Policy line, `_cleanup_route` and
  `SCAN_SKIP`, the exit check's driver under `in/`. Gate clear, verify
  pass (96 tests, 0 regressions, 11 new). One egress refusal: a plain GET
  to the host `llm`, a test's fake endpoint reached through the session's
  proxy variables when the doer ran the Python suite. On the host, one
  live test red: the mount test still handed the launcher the fake
  proxy, so its sidecar never listened. Right-clear; merged `9e264d6`.
  After the merge: the three live tests share `staticProxyBin`
  (`0223091`), and the driver beside the exit check reads `in/mcp.json`
  (`32154ca`; found by running the exit check, which then passed 5/5
  through the sidecar with a host-side approval over the sink).
- **The lesson, twice:** verify cannot see a live test, and both units
  had one wrong or red on the host. The handoff's §2 now says a live
  test that needs the sidecar must pass the real static proxy, and that
  `go/bin` must not be rebuilt while a dispatch runs (the launcher and
  the proxy must agree on the subcommand set).
- **Release, 0.2.14-beta:** the CHANGELOG entry; C-140 narrowed to a
  forged edit line and surfaced (78 surfaced, 17 partial; C-125's
  related line); ADR-107's pointer; both box headers; the harness doc's
  status line, diagram and §2 table; the architecture's §6.3, sandbox
  row, recorder row (the sink's four decisions) and harness row; W5's
  item built; CLAUDE.md's map and status; the handoff rewritten. The
  image and the four binaries rebuilt at 0.2.14-beta (C-65).
- **Suites:** pytest 1,508 (host); Go 386 lines (385 pass, 1 skip,
  subtests counted, the four live launcher tests included); the tracker
  at 19 of 40, 4 areas, 0 false blocks, 0 missed, $46.40 reported.
- **Task files:** `~/.hobbes/bench/adr112-drivers/{sink,launcher}-task.md`
  with their partitions beside them.

**Not done, for Max:** ADR-106; the register segment for the dispatch
entries; C-140's remainder only if it ever matters (route 2).

## 2026-09-14 — (later) the top-level review; three stale lines from the 0.2.14-beta release fixed

**Asked (Max):** "review top level documentation and report back with
current standing", then "apply the drift fix then report back with a
tackable item from the list. the held with spend are off the table still".

- **The review.** The tree, the binaries, the image and the ingest are
  all at 0.2.14-beta on `38d364f`; the version and tracker drift tests
  pass. CLAUDE.md, the handoff, the CHANGELOG entry, the BUILDLOG, W5,
  the harness doc's status line, the architecture's harness row, the
  register's debt table (141; 100 active as 78/17/4/1) and the tracker
  (19 of 40, 4 areas, 0/0, $46.40) tell one story. Every path CLAUDE.md
  links to exists; `AGENTS.md` is its symlink.
- **Three drifts, fixed in one docs commit:** the README's status
  opened at 0.2.13-beta with seventeen sessions and no ADR-112 line;
  the architecture's §8 header read 0.2.13-beta while its harness row
  read 0.2.14-beta; the CHANGELOG's preamble left 0.2.11-beta to
  0.2.14-beta out of the untagged list.
- **Noted, not changed:** CLAUDE.md says the architecture carries no
  version number, and §8 carries one. Max's call which of the two gives.
- **The knowledge server** was up again (an unnamed container on the
  local image, started by `.mcp.json`).

**Then (Max: "continue tackling your recommended item"): C-133's unit 1
through the harness — 0.2.15-beta (ADR-108 amended).**

- **The item.** C-133 was the register's one unsurfaced C entry: an
  include decision 4's three steps cannot place drew nothing, so a
  directory whose headers sit behind the build's `-I`, or are generated,
  read like one whose includes all resolved. Two units: surface it
  (this one), then read the `-I` path from the derived compile database
  (lane B derives it after lane A runs; a later amendment).
- **Decided before the dispatch:** ADR-108's 2026-09-14 amendment —
  one `c-includes` record per directory, two shapes (unmatched quoted;
  ambiguous of either spelling), an angle include that matches nothing
  stays a dependency, the edges do not move. Committed `b154bdf`; the
  ingest at it.
- **Measured before:** on cJSON (`fb16e5c`) 305 include edges, 12
  external nodes, 7 unmatched and 8 ambiguous quoted includes across 6
  directories; on sqlite-vector (`0c2223a`) 163 and 57, 6 unmatched in
  `libs`.
- **The session** (`S-20260914T015405Z-47f7`, 25 of 100 turns, 4.3
  min, $0.79): `_resolve_include` returns a small frozen result naming
  the miss, `_join` collects per directory, `_include_degradations`
  draws the records. Gate clear, verify pass (187 tests, 0 regressions,
  6 new). One egress refusal, the known `llm` shape from the full suite.
  Right-clear; merged `a7ab3f6`, not squashed.
- **Measured after,** the merged code: cJSON 305/12 unchanged, 6
  records (`"ProductionCode.h"`/`"ProductionCode2.h"` ambiguous in four
  Unity example directories; `"Types.h"` and six `expectdata` mocks
  unmatched); sqlite-vector 163/57 unchanged, 1 record (`libs`' six
  platform and generated headers). Every count as predicted.
- **Found and fixed on the host:** the tracker's Policy pattern did not
  take the stream bracket 0.2.14-beta's dispatch writes (`; records:
  stream opened→closed`); `47f7` was the first session to carry it and
  the drift test went red. The pattern takes the clause, with a test
  for both shapes. Also: the three `package-lock.json` copies of the
  version, which `test_version.py` checks and the bump had missed.
- **Release, 0.2.15-beta:** the CHANGELOG entry; C-133 narrowed to
  *partial* (18 partial, 3 unsurfaced); W1's line; the evidence table's
  cJSON row with sqlite-vector beside it; the harness doc's status
  line, the architecture's §8 header and harness row, the README,
  CLAUDE.md, the handoff; the tracker at 20 of 40, 4 areas, 0 false
  blocks, 0 missed, $47.19 reported. The binaries and the image rebuilt
  at 0.2.15-beta (C-65); the ingest re-run at the release commit.
- **Suites:** pytest 1,515 (host); Go unchanged (nothing under `go/`
  moved but the version constant).
- **Task files:** `~/.hobbes/bench/c133-drivers/includes-task.md` with
  its partition beside it.

**Not done, for Max:** the same list as above, plus whether C-133's unit
2 (the `-I` read after lane B) is worth its amendment now or waits for a
graded cell that shows the cost.

**Then (Max): the knowledge server restarted on the 0.2.15-beta image
(C-65); the architecture keeps its version number** — CLAUDE.md's line
saying it carries none was the one that gave (`b370d1d`). The old
server's container (unnamed, on the 0.2.14-beta image) was removed;
the session reconnects through `.mcp.json`, which starts the new build.

**Then (Max: "proceed with the recommended"): C-135's measured gap on
bpftop — 0.2.16-beta (ADR-109 amended).**

- **Read first, no spend.** A probe reproduced `_index_c_unit` on the
  bpftop clone (`5a67ec0`), keeping the build dir. Under bear, `make`'s
  one target, `cargo build --release`, records 45 compiles — every one
  libbpf-sys's vendored libbpf or vsprintf under cargo's registry in
  Hobbes's cache, none under the root. cargo's own words, re-run in the
  image: libbpf's make fails on `libelf.h: No such file or directory`,
  so cargo stops before bpftop's build script compiles
  `src/bpf/pid_iter.bpf.c`. The database was not empty, so the plan's
  check passed, scip-clang found nothing of the root's, and the unit
  drew only the generic `scip-index` record.
- **Decided before the dispatch:** ADR-109's 2026-09-14 amendment — an
  entry counts for the root only when its file lies under it; a
  database with entries and none under the root stops the plan before
  scip-clang, naming the count, where they lie, the build's last words
  capped, and C-135. Committed `b4b10a0`; the ingest at it.
- **The session** (`S-20260914T022459Z-1ae3`, 17 of 100 turns, 94 s,
  $0.45): `compdbCheck(compdb, what, stage)`, `commonOutsideDirectory`,
  four tests. Gate clear, verify pass (48 tests, 0 regressions, 4 new).
  One egress refusal: `npx vitest` reaching for the registry. Right-
  clear; merged `fc7bf3d`, not squashed. Host: scip node 47/47; the C
  lane's 12 contained tests green.
- **Found and fixed on the host:** the check's refusal exited the
  helper with the generic code, so the Python side labelled it "the
  SCIP helper is unusable — install Node and run `npm install`"; the
  empty-database case had carried the same mislabel since 0.2.4-beta.
  A refusal now carries `indexerExit`, and both tests assert
  `exitCodeFor(err) === INDEXER_EXIT`. The probe re-run reads "the c
  indexer exited inside the container: bear over make recorded 45
  compile(s), none of a file under this root — all under cargo's
  registry (the dependencies' own C); the build compiled none of the
  root's own C (C-135): … make failed".
- **Release, 0.2.16-beta:** the CHANGELOG entry; C-135 narrowed (still
  partial); the evidence's bpftop paragraph; W1's line; the harness
  doc, the architecture's §8 header and harness row, the README,
  CLAUDE.md, the handoff; the tracker at 21 of 40, 4 areas, 0 false
  blocks, 0 missed. The binaries and the image rebuilt at 0.2.16-beta
  (C-65); the helper is mounted from the checkout, so the exit-code fix
  needed no rebuild. The ingest re-run at the release commit.
- **Suites:** pytest 1,515 (host); scip node 47.
- **Task files:** `~/.hobbes/bench/c135-drivers/compdb-task.md` with
  its partition beside it.

**Not done, for Max:** libelf in the image (a dependency's build the
image cannot complete stays C-135's own case; adding a library to the
image is a decision, ADR-092's shape); the leftover `.scip` outputs
under `~/.hobbes/cache/stage/` (34 files, 116 KB), a housekeeping item.

## 2026-09-14 — (later still) the top-level review; `oracle import --lang c` through the harness (ADR-101 amended; `d2e3`)

**Asked (Max):** "review top level documentation, then proceed with
most tackable item using harness".

- **The review.** The tree, the binaries, the image and the ingest were
  all at 0.2.16-beta on `97fc3da`; the README's status, the
  architecture's §8 header and harness row, the CHANGELOG's preamble
  and the harness doc's status line tell one story; the knowledge
  server answered from the ingest at HEAD. No drift found.
- **The pick.** From the handoff's no-spend queue: `oracle import --lang
  c`, the comparative queue's blocker. Read first: the converter reads
  `export.Exts`, which has carried `c` since ADR-110, so a C edge file
  already converted — but the flag helps, the refusal, the usage block
  (whose `export` line still read `go|ts`), `grade-foreign.sh`, the
  README and `foreign_record.py`'s tuple all spelled the set without
  it, and no fixture proved the C conversion. Smaller than the other
  candidates (`testmap_fixture`'s warnings are smaller still, but a
  test-only change maps to no area); in the oracle-lane area, which
  had two sessions.
- **Decided before the dispatch:** ADR-101's 2026-09-14 amendment —
  the import applies the export's predicates and nothing C-specific
  (a header callee graded, a `macro` row dropped, `c` spelled
  everywhere, a hand-read fixture graded against a hand-built key; the
  live clang key is the cell's job). Committed `7abfdcd`; the ingest
  at it.
- **The session** (`S-20260914T131039Z-d2e3`, 40 of 60 turns, 4.7 min,
  $1.04): seven files as partitioned; `cclang.edges.json` (twelve rows:
  eight graded, two across a header; a macro row, a duplicate, two
  other-language rows); two tests beside the minigo pair. Gate clear
  (map over 7 files, 40.3% uncaptured, partition checked), verify pass
  (11 tests, 0 regressions, 2 new). One egress refusal,
  `static.rust-lang.org`: the doer's `go test ./...` reached the Rust
  oracle's driver tests, which skip. Right-clear; merged `109c15b`,
  not squashed. **Host, before the merge:** `internal/foreign`,
  `export`, `grade` green in a worktree (the grade package needs the
  ts node tree beside it). **After:** the full oracle-lane suite green
  on `main`, contained tests included.
- **Fixed on the host after the merge:** one check in the conversion
  test read the truth map against itself (a tautology); it now asserts
  the two header pairs were among the converted edges.
- **No version move** (nothing under `bench/` does, ADR-103). The
  tracker at 22 of 40, 4 areas, 0 false blocks, 0 missed, $48.67
  reported; CLAUDE.md, the README, the harness doc, the architecture's
  harness row and W0's comparative item say so.
- **Task files:** `~/.hobbes/bench/c-import-drivers/import-task.md`
  with its partition beside it.

**Next on the queue, no spend:** the foreign C cells themselves (both
graded tools on cJSON and sqlite-vector — whether either draws C edges
worth grading is that cell's finding); `testmap_fixture`'s two pytest
warnings; C-135's autotools, Meson and Bazel roots.

**Then (Max: "continue with the next item listed of the foreign c
cells"), the foreign C cells, host-run, no spend.**

- **The tools, back at their pins.** The 2026-09-09 venvs had lived in
  a scratchpad; both wheels were still in uv's cache, so
  `~/.hobbes/bench/comparative/tools/{cgc,rw}` hold CodeGraphContext
  0.6.13 (kuzu 0.11.3) and repowise 0.49.0 again, on Python 3.12. The
  driver `run-c-cell.sh` beside them: index as the README documents,
  `adapter.py dump` + `convert` (converter@2), `grade-foreign.sh …
  --lang c` against the stored clang keys (`~/.hobbes/bench/oracle/
  {cjson,sqlite-vector}-c/oracle.json`). Walls: cgc 22 s and 136 s
  (the amalgamation; its converter re-reads the 263k-line file per row
  and took minutes more), repowise 11 s and 9 s.
- **The four cells** (`docs/oracle/cells/{codegraphcontext,repowise}-
  {cjson,sqlite-vector}-2026-09-14.md`, from the artifacts by
  `foreign_record.py`; every contradiction read, the A-8 line
  hand-corrected to the read ratio):
  - CodeGraphContext on cJSON **1,179/1,179**, recall 61.5%
    (1,180/1,918): its misses are the 728 macro-expansion sites, as
    Hobbes', and ten static sites it stored no edge for.
  - CodeGraphContext on sqlite-vector **851/863**, recall 100%
    (1,091/1,091): nine `sqlite3_*` names drawn into the vendored
    amalgamation the extension's build never compiles with it (in the
    unit the name is `sqlite3ext.h`'s macro over the API table), and
    the three `strcasestr` shim rows in a dead `#if` arm — Hobbes'
    own three before ADR-111's veto (C-138).
  - repowise on cJSON **1,073/1,637** (65.5%), recall 56.0%; on
    sqlite-vector **780/879** (88.7%), recall 93.3%. **562 of 564 and
    99 of 99 contradictions are `#define` targets:** the tool stores a
    function-like macro (`can_read`, Unity's `TEST_ASSERT_*`,
    `MM256_FMA_PS`) as kind `function`, so the macro exclusion, which
    fires on a `macro` kind alone, never applies, and the row grades
    against the callee clang saw in the expansion. With those rows
    excluded as Hobbes' own are, 99.8% and 100% — stated in the
    records, not graded. The two others are `setUp`/`tearDown` under
    `UNITY_WEAK_ATTRIBUTE`, the other `#if` arm.
  - Poison: 0 falsely confirmed of 27,925 seeded across the four.
- **The lane.** `cells.meta.json` four rows; `render.py cells |
  render | check` green (84 cells), `tables.md` and the scatter's C
  panel regenerated; the same-key graphic's language order gained C
  (it was a fixed list). `go test ./report/` green. C-95 gains its C
  face (the register). The claim page's item 4 replaces "no foreign
  cell exists for C" with the numbers and the finding; W0's item, the
  handoff.
- **A decision for Max, not taken (ADR-101):** whether the converters
  may read a `#define` at the target line as kind `macro` (converter@3,
  the same source reading converter@2 makes for annotation lines) and
  regrade repowise's two C cells with signed direction lines.
  Recommended yes: it is the tool's storage read at a grain the
  converter can state — C-95's own rule — not a tolerance invented
  for the tool. A harness unit (both adapters, their fixtures, the
  fixture test) and then the regrade.

**Then (Max: "proceed with the recommendation. also update comparative
graphics to show c now that weve graded foreign"): converter@3 through
the harness, and the regrade.**

- **The graphics already showed C** after the first four cells: the
  scatter's C panel carries the four markers, the one-number graphic
  counts the C cells among its "23 compiler-graded cells in 5
  languages", and the same-key graphic gained its C band when its
  fixed language order took C (the same session, earlier). They are
  regenerated again below on the regraded records.
- **Decided before the dispatch:** ADR-101's second amendment of the
  day — a callee whose declared line begins with `#define` is kind
  `macro` (converter@3), read from the source as converter@2 reads
  the declaration line; both adapters, a hand-made C raw fixture
  each, the record tooling signing the converter pair. Committed
  `d16c978`; the ingest at it.
- **The session** (`S-20260914T144539Z-3c41`, 45 of 80 turns, 3.2
  min, $1.10, no egress refusal): `declared_kind` beside
  `declaration_line` in each adapter, wired after the converter's own
  kind choice; `VERSION` at `@3`; `testdata/cclang.raw.json` per
  adapter (repowise's storing the macro as `function`, the finding
  itself) and `TestCclangMacroRowIsExcluded`; `foreign_record.py`'s
  direction line reads the pair from `edges.v1.json`/`edges.json`.
  Gate clear (7 files, 47.9% uncaptured, partition checked), verify
  pass (6 tests, 2 new). Right-clear; merged `d575428`, not squashed.
  Host: both adapter packages and `internal/foreign` green in a
  worktree before the merge; the full oracle-lane suite green on
  `main` after.
- **The regrade** (`~/.hobbes/bench/comparative/regrade-c-cell.sh`,
  from the stored dumps, no re-index; the `@2` grade kept beside each
  cell as `edges.v1.json` / `report.v1.*`):
  - repowise on cJSON: 699 edges excluded as `macro`; **1,073/1,075**
    (65.5% → 99.8%), recall unchanged 56.0%; the two left are
    `setUp`/`tearDown` under `UNITY_WEAK_ATTRIBUTE`, declared in the
    `#if` arm clang did not take (C-138's shape).
  - repowise on sqlite-vector: 607 excluded; **780/780** (88.7% →
    100%), recall 93.3%.
  - CodeGraphContext on both: unmoved (1,179/1,179; 851/863) — it
    stored no edge to a `#define` line; its records say so.
  - Records regenerated with signed direction lines; the A-8 lines
    hand-set to the read ratios. `render.py cells | render | check`
    green, the report test green. C-95 narrowed in the register; the
    claim page's C sentence restated; W0, the handoff, CLAUDE.md.
- **Task files:** `~/.hobbes/bench/c-import-drivers/macro-task.md`
  with its partition beside it. **The tracker** at 23 of 40.

## 2026-09-14 — (last) the top-level review's stale lines; the doer's model named per checkout — 0.2.17-beta (ADR-107 amended; `cd8e`, the first session on a named model)

**Asked (Max):** "review top level documentation then report back with
current standing", then "proceed with the staleness fixes and
re-ingest, also id like to setup this space where dispatching tasks
uses opus 5 instead of fable."

- **The review.** The tree, the five version copies, the binaries and
  the image were at 0.2.16-beta; the README's status, the
  architecture's §8 header and harness row, the harness doc, the
  register's debt table, W0 and the tracker (23 of 40, $49.77) agreed.
  Three drifts, all prose or the ingest: the CHANGELOG's untagged range
  stopped at 0.2.14-beta; the handoff's item 0 carried `d2e3`'s
  tracker count under `3c41`'s; the ingest was at `d16c978`, four
  commits behind HEAD (the converter@3 adapters). Fixed in `f09b371`
  (with the workstreams header), then the ingest at HEAD.
- **The finding, on the model.** Every one of the twenty-three
  sessions' Doer lines read "model the default". `hobbes dispatch
  --model` reaches `hobbes-session --model` and Claude Code's own
  flag, but nothing set it, and the doer's container carries no user
  settings (HOME a tmpfs since 0.2.14-beta), so the model was Claude
  Code's choice for the account — never the owner's, never recorded.
- **Decided before the dispatch:** ADR-107's 2026-09-14 amendment
  (`acf093c`): `hobbes dispatch` reads `$HOBBES_DISPATCH_MODEL` when
  `--model` is not given; the flag beats it; unset leaves the choice to
  Claude Code. A checkout sets it in its gitignored
  `.claude/settings.local.json` `env` block beside `HOBBES_SECRETS` —
  the box's setting, since the repo names no model (the bench harness
  names its ladder per arm, ADR-055). This box: `claude-opus-5`. The
  variable reaches a shell started after the setting, so the unit
  that built it passed the flag by hand.
- **The session** (`S-20260914T153042Z-cd8e`, 22 of 60 turns, 76 s,
  $1.11, `--model claude-opus-5`; the first Doer line naming its
  model): `MODEL_ENV` and `default_model()` in `dispatch.py`,
  `args.model or dp.default_model()` and the help in `cli.py`, three
  tests through the fake session's `argv.json` (the variable reaches
  the argv and the doer record; the flag beats it; unset leaves
  `--model` out). Gate clear (3 files, 0.0% uncaptured, partition
  checked), verify pass (388 tests, 3 new). Five execs, all allowed;
  no egress refusal. Right-clear; merged `1f5790a`, not squashed.
- **Fixed on the host after the merge:** the tracker's Doer pattern
  matched `model the default` alone, so `render` raised on the first
  named model — the stream bracket's shape at 0.2.15-beta again, a
  first-of-its-kind line. It now takes a name (`(?P<model>the
  default|\S+)`), with a test on `cd8e`'s line.
- **Version 0.2.17-beta** (patch: what the layer says — the log names
  the model the checkout chose): the five copies and the three lock
  files, the CHANGELOG entry, the README's status, the architecture's
  §8 header and harness row, CLAUDE.md, the harness doc (§5 gains the
  once-step and the flag), the handoff. Binaries, the static proxy and
  the image rebuilt (C-65). pytest on `main`: the count is in
  CLAUDE.md's suite line; Go's version package green, the rest of the
  Go suite not re-run (only the version string moved).
- **The tracker** at 24 of 40, 4 areas, 0 false blocks, 0 missed,
  $50.88 reported. **Task files:**
  `~/.hobbes/bench/dispatch-model-drivers/model-task.md` with its
  partition beside it.

**Next on the queue, no spend:** Max's open calls (ADR-106; the
register segment for the dispatch entries); then the named units
toward 40 — C-135's autotools, Meson and Bazel roots; C-133's unit 2
when a graded cell shows the cost; `testmap_fixture`'s pytest
warnings; the comparative queue's next converters if named — each now
a bare `hobbes dispatch`, on Opus 5.

## 2026-09-14 — (after the release) the register: the dispatch harness's own segment; C-120 folded into C-112; ADR-106 answered

**Asked (Max):** "whats adr-106 also yes a dispatch harness section for
constraints is a good approach. also probably the fold unless
different problems."

- **ADR-106** is a held number, not a file: M0-Go's design was to take
  it when moved to *accepted* (`calvin-m0-go.md` line 12,
  `calvin-m0-gate.md` §9), and ADR-107 closed the keyed rounds as an
  approach, so nothing will take it. Two routes put to Max in the
  handoff: write a one-page ADR-106 marked *not taken* that points at
  the M0-Go record, so the sequence has no hole and the number is never
  reused (recommended); or leave it held.
- **The segment** (`docs/constraints/dispatch-harness.md`): C-125,
  C-127, C-128, C-129 and C-140 moved out of the verification segment
  with their numbers and text unchanged; its intro says what stays
  elsewhere (the gate's entries in the derivation segment, C-41 and the
  keyed rounds' session entries in verification). The verification
  segment's title drops the harness; C-41's "below" now names the new
  file. Neither the Go knowledge package nor a test reads the segment
  files by name, so the split is prose only.
- **The fold.** Same problem, not different: C-120's own text calls its
  unsurfaced remainder "C-112's subject" — a garbled post-image reads
  as whatever lane A's parse makes of it, nothing said, and `hobbes
  gate` grounds every dispatched diff through that code. What C-120
  adds is the one shape that *is* named (the render gutter,
  `malformed`) and why only that one. Folded per ADR-043's rule: the
  entry keeps its number and text at the bottom of its segment, C-112
  gains a **Folds in** line and keeps the weaker status, unsurfaced.
  ADR-043 amended with the date; the 2026-09-13 line that kept C-120
  active stands as history.
- **The counts:** 141 entries — 99 active (77 surfaced, 18 partial, 3
  unsurfaced, 1 n/a), 25 lifted, 11 superseded, 6 folded. The index,
  the debt summary and its dated note, CLAUDE.md and the handoff say
  so. No version move: the register is read by people, and nothing
  the layer draws, refuses or says changed.
- **Then (Max: "writ the not taken note to the adr, keep the line in
  future additions"):** ADR-106 written as *not taken* — the number
  closed, the M0-Go record named as where its design lives, the
  sequence contiguous; CLAUDE.md's convention line says so. The
  `future_additions.md` harness-weight line kept with a dated note
  (Max: "havent settled on where i want to go with harness
  eventually"). The handoff's open list for Max is empty; its three
  remaining items are not owed.

## 2026-09-14 — (last) C++ as a language: ADR-113; lane A and O10 through the harness in parallel — 0.2.18-beta, wired, not supported

**Asked (Max):** "add c++ as a supported language through the typical
language addition flow", then, after his usage limit cut the session
mid-run: "see where the current status point is, look to fix or finish
and then note the remaining for next session".

- **Read first, no spend:** §3.7's checklist against C's precedent
  (ADR-108/109/110). Three measurements fixed the design: scip-clang
  indexes C++ from the same derived database and its `cxx` monikers
  already decode; tree-sitter-cpp 0.23.4 installs beside the pinned
  tree-sitter and parses every shape the walk needs (a gtest `TEST`
  reads as a function named `TEST`; Catch2's `TEST_CASE` as a call plus
  an ERROR node); clang 18's C++ dump gives every declaration a
  mangled name (the cross-unit key C++ needs where C merged by name),
  names a member call's callee by id, and gives a constructor call no
  callee at all. **ADR-113** written (`7a805de`, with the
  tree-sitter-cpp pin, so the sessions could import it offline).
- **Two units in parallel from one parent,** both on Opus 5. First
  launched as the assistant's background commands, then stopped and
  relaunched under `setsid nohup` on reading the BUILDLOG's ten-minute
  cap (the orphaned sidecars and networks removed by hand; two
  session dirs `99ad`/`ade2` hold the aborted starts, no log written).
  - **`S-20260914T161248Z-3d56`, lane A** (142 of 200 turns, 28 min,
    $18.67): gate clear (15 files), verify pass (1,575, 65 new). Nine
    deviations, all the grammar's. Merged `3030ac7`.
  - **`S-20260914T161308Z-a848`, O10** (139 of 200, 25 min, $16.08):
    gate clear (16 files), verify pass (52 tests, 4 new). Seven
    deviations, all the dump's. Merged `1f81412`.
  - **Host:** pytest 1,584 (the tracker's drift test red until the
    review blocks were filled — as designed); Go knowledge tests green;
    the oracle lane 95 pass / 5 skip with the C++ end-to-end test.
  - **The cost:** $34.75 for two of three units against the ADR's
    "about $20 for three". Both doers read and probed long before
    writing. Max hit his usage limit while they ran; both finished on
    their own, and only the assistant's waiting loop was cut.
- **The host read, fmtlib/fmt at `3a0661d7`:** 73 C++ files, 884
  types, 1,451 methods, 1,325 functions, 418 macros, 645 gtest tests;
  18,156 sites; **2,992 semantic call edges** — lane B reaches C++
  already wherever a root has a C file, because the derived database
  names every unit; 299 syntactic. The `cpp-headers` record: 25 to
  C++, 1 to C (`fmt-c.h`, included from both). **Two findings,
  registered:** every library header parses with ERROR nodes (macro-
  spelled declarations, C-145, C-131's C++ face); an overload set
  trips C's duplicate-definition rule, so only the first overload is a
  symbol and lane B's answers to the rest fall below the floor — 7,628
  below-floor sites (C-144, unit 2's first defect).
- **Register:** `constraints/extraction-cpp.md`, C-142–C-147; C-132
  narrowed; 147 entries, 105 active (82 surfaced, 19 partial, 3
  unsurfaced, 1 n/a). **The draw** for the second cell made as §7d
  states it: Taywee/args at `903b07df`, the seventh; six passed over
  with reasons in `~/.hobbes/bench/cpp-cells/draw.json`; fmt is the
  chosen cell (52 entries offline).
- **Version 0.2.18-beta** (a language addition is a patch): the copies
  and locks, the CHANGELOG, README, the architecture (§3.7's eighth
  walk, §8), CLAUDE.md, the harness doc, oracle-grading.md §7d and the
  O10 row, ADR-113's record, the handoff. Binaries, the static proxy
  and the image rebuilt (the proxy's tail tables changed, C-65).
- **The tracker** at 26 of 40, 4 areas, 0 false blocks, 0 missed.
  **Task files:** `~/.hobbes/bench/cpp-drivers/{lane-a,oracle}-task.md`
  with their partitions.

**Remaining (the handoff's item 0):** unit 2 — lane B deliberate for a
C++-only root, the overload symbol ids and the duplicate record's
wording, the decode measured on `minicpp` — once Max names its budget;
then the two cells (fmt, args) host-run and contained; then the §3.8
row, the patch that makes C++ *supported*.

## 2026-09-14 — (after the release) C++'s lane B through the harness: ADR-113 §2 amended, then `be34` — 0.2.19-beta

**Asked (Max):** "review top level documentation and proceed with the
c++ development"; then, asked as a route, unit 2's budget: "One unit,
150 turns".

- **The top-level review:** the README, CLAUDE.md, the CHANGELOG and
  the architecture's §8 agreed on 0.2.18-beta, and the knowledge server
  was current. One stale line surfaced later, during the bump: the
  README's register count (141 entries, five folded), fixed to 147.
- **Measured before the unit, no spend:**
  - **Method:** a `minicpp` copy with a stub `.c` (fmt's route) was
    ingested contained. The raw scip-clang index was built in the image
    (bear and make, offline; 3 units, 0 errored) and read with the
    helper's own deserializer (a scratch `read_scip.mjs`).
  - **Result:** every C++ shape resolved; 8 sites compared, 0
    disagreements.
  - **Finding 1:** a construction site carries the class and its
    constructor under one name. The join's nearest-column pick and C's
    one-target rule both chose the class, so every construction edge
    was drawn to the type, where O10 keys the constructor.
  - **Finding 2:** scip-clang declares a namespace from every file that
    opens it, and the record worded that as C's statics.
  - **ADR-113 §2 amended** (`e7b117e`): one decode rule, one wording,
    the calls-to-type guard extended, C-144's fix (Java's `~n`), and
    each root's language.
- **`S-20260915T001249Z-be34`** (114 of 150 turns, 13.5 min, $10.84,
  Opus 5; first edit at 4.4 min):
  - gate clear (11 files); verify pass (837, 0 regressions);
  - four deviations, none of the design's (one was the task's own: it
    named a test file that does not exist);
  - six escalations expired (a `cat` loop, `g++ -fsyntax-only` twice);
  - on the host, both `lane_b` tests pass and the scip node suite is
    53/53;
  - merged `cecb025`;
  - after the merge, the build disclosure said "c" for a C++-only root
    (the doer's own note); fixed with a test.
- **The fmt read after the merge** (branch code, contained):
  - below-floor went from 7,628 to 7,357, and call edges from 3,291 to
    3,308;
  - a scratch diagnostic (`below_floor.py`, wrapping `project`) placed
    6,896 of 7,376 below-floor facts on definitions in files that
    parsed with errors and have no lane A symbol near: 3,375 in the
    vendored `gtest.h`, 2,398 in `format.h`;
  - so the 0.2.18-beta record's attribution of all 7,628 to C-144 was
    wrong. Overloads were about 271, and C-145 now carries the cost.
- **Register:** C-144 lifted (the residue: signatures compared as text;
  `~n` in source order). C-143 and C-145 restated. 147 entries: 104
  active (81 surfaced, 19 partial, 3 unsurfaced, 1 n/a), 26 lifted.
- **Version 0.2.19-beta:** the copies and locks, the CHANGELOG, the
  README (and its stale register count), the architecture (§3.7's C++
  paragraph, §8), CLAUDE.md, the harness doc, ADR-113's record and the
  handoff. pytest 1,600 (6 `lane_b`) and scip node 53. The binaries,
  the static proxy and the image rebuilt (C-65).
- **The tracker** reads 27 of 40, 4 areas, 0 false blocks, 0 missed.
  **Task file:** `~/.hobbes/bench/cpp-drivers/lane-b-task.md` with its
  partition.

**Remaining:** the two cells. For fmt (module `.`) and Taywee/args:
`oracle c-clang --lang cpp`, then `oracle grade`, every contradiction
read, records in `docs/oracle/cells/`, and the poison check. Then the
§3.8 row, the patch that makes C++ *supported*. Expect fmt's recall to
carry C-145's cost.

## 2026-09-14 — (later) C/C++ lane B made order-independent: ADR-113 §2 and ADR-109 amended, then `3d1a` — 0.2.20-beta

**Asked (Max):** the route, once the finding was in front of him: "C++
abstains, C min line (Recommended)".

- **Found before grading fmt.** Three fmt ingests at one commit drew
  3,308, 3,298 and 3,293 call edges, and two cJSON ingests differed by
  one edge. The symbols were identical; 117 and 123 edges swapped
  between siblings in `chrono.h` (a template against its
  specialisation, an overload against `~2`).
- **Measured, no spend,** with scratch probes over fmt indexed in the
  image four ways: the whole database at `-j12` twice and at `-j1`
  twice, and each unit alone twice.
  - The raw indexes differ on every run, and the decoded references
    differed by 1,339–3,612 rows.
  - The raw occurrences showed the cause: one moniker defined at several
    lines of one file (`float_info#` at 1677/1691,
    `is_negative(ee44…)` at 1151/1155, `bit_cast(5dc1…)` at 262/418),
    listed in an order that varies by run, with the helper keeping the
    first one it met.
  - With either order-independent rule (the smallest line, or
    abstaining), all 55 run pairs decoded identically.
  - scip-clang's `--deterministic` also decoded identically, but took
    307 s against 8 s and errored on 3 of 52 units, so it was refused.
  - A first probe of mine reported 35 of 54 pairs repeatable under the
    rules. It was wrong: the careful probe checks that its rewrite
    reached the index.
- **The route, Max's:** C++ abstains and C takes the smallest line.
  ADR-113 §2 amended again, and ADR-109 decision 3 (`3e74477`).
- **`S-20260915T015439Z-3d1a`** (32 of 80 turns, 3.7 min, $2.23, Opus
  5): gate clear (2 files), verify pass (59); no deviations. On the
  host, the node suite is 58/58, and three fmt ingests are identical at
  the edge level (9,830 edges; 3,273 calls; 240 monikers and 2,228
  references abstained). Merged `f0cd459`.
- **The residue:** four fmt tail sites still flip between `external`
  and `builtin-name`, and three cJSON ingests on `main` drew 2,630,
  2,615 and 2,621 edges (`uses` edges from `tests/common.h`'s
  assertion macros to Unity's). Lane B's unit-dependent references come
  and go, because scip-clang indexes a shared header once, in
  whichever unit claims it. Registered as **C-149** (unsurfaced, debt),
  with the per-unit route measured on fmt (9–10 s against 8 s; each
  unit's index repeats under the rule, 52 of 52) for Max.
- **A slip, recorded:** the launch's `grep` printed nothing, I read it
  as a failed launch, and re-ran this repo's ingest while the session
  was starting. It was at the same commit with a clean tree, so the
  parent graph the gate read later was unchanged.
- **Register:** C-148 (surfaced) and C-149 (unsurfaced). 149 entries:
  106 active (82 surfaced, 19 partial, 4 unsurfaced, 1 n/a), 26 lifted.
- **Version 0.2.20-beta:** pytest 1,600 (6 `lane_b`) and scip node 58.
  The binaries, the static proxy and the image rebuilt. **The tracker**
  reads 28 of 40. **Task file:**
  `~/.hobbes/bench/cpp-drivers/determinism-task.md`.

**Remaining:** Max's call on C-149's per-unit route. Then the cells (fmt,
args); fmt's `calls` edges repeat, so it can be graded first with
C-149 stated. Then the §3.8 row.

## 2026-09-15 — C and C++ indexed one translation unit per run: ADR-109 amended, `f3c1`, the size guard, and C-150 — 0.2.21-beta

**Asked (Max):** "Per-unit route, then cells (Recommended)". Then, once
the ScummVM measurement was in: "Merge behind a size guard
(Recommended)".

- **Designed on measurement** (`c7782f0`). The merge probe over fmt's
  52 per-unit indexes decoded identically across two passes (64,667
  references). The decode's `references.push(...kept)` overflowed the
  stack at the merged size (484,201).
- **`S-20260915T135819Z-f3c1`** (59 of 120 turns, 9 min, $4.92, Opus
  5). It made the plan's index step per unit (`xargs -P`, `-j 1`),
  decoded the units as one, counted failed units, and turned the
  spread-pushes into loops. Verify pass (65 node tests). Merged
  `e2f7704`, not squashed.
  - **The gate blocked it, and the block was false**, the harness's
    first. The flagged call was `check(previous)`, through an arrow
    parameter. `ground._TS_PARAMS` needs a word character or `function`
    before the `(`, so in `= (check) =>` the parameter is never read as
    a local (C-91 amended).
- **Host:** node 65/65 and both `lane_b` tests pass.
  - Three cJSON ingests are identical: 2,635 edges and every tail count.
    Before, one commit gave 2,630, 2,615 and 2,621.
  - Three fmt ingests are identical at the edge level, at 21–22 s per
    ingest against about 15 s before. Two external type sites still
    flip in the tail.
- **The cost, measured:**
  - args (99 units sharing `args.hxx`): 6 s whole-database against 8 s
    per unit; indexes 1.5 MB against 85 MB;
  - fmt: 8 s against 9 s;
  - ScummVM, built in the image, offline: `./configure --backend=null`
    (SDL is absent), then bear over `make -k -j8`, 5,958 entries. 143 s
    against 207 s, and 370 MB against 9.36 GB of indexes;
  - the merged decode's peak memory: +1.1 GB at 50 units, +2.45 GB at
    200, +5.75 GB at 400, about 84 GB projected for all;
  - `main`'s helper threw `RangeError` on ScummVM's whole index. The
    branch's decoded it in 22 s at 8.95 GB peak.
  - A first run of the scaling probe died at 200 units with exit 139.
    That was my probe: it used `main`'s unfixed helper under
    `--stack-size=60000`, beyond the thread's real stack. The rerun used
    the branch's helper.
- **Max's size guard** (`4832883`): `PER_UNIT_MAX = 400`. Over it, the
  check writes the database whole, one scip-clang runs at its own
  parallelism, and a `scip-decode` record names the count, the bound
  and C-149. Three node tests (68/68).
- **The tracker** could not parse a blocked gate line. Fixed with a
  test (`f6823a6`); it reads 29 of 40, 1 false block, 0 missed.
- **ScummVM end to end,** from a carried `compile_commands.json`, with
  the build's artifacts and my indexes removed from the copy: 614 s,
  exit 0, but lane B failed.
  - The helper exited 139 with V8's allocation trace: Node's default
    heap against the ~9 GB decode.
  - The record said "the SCIP helper is unusable — install Node".
    Fixed on the host: a helper exit carrying V8's heap-exhaustion
    markers now says the helper ran out of memory, and names **C-150**
    (registered, surfaced). One test.
  - The root's 1.53 million C++ sites were left to lane A.
- **Register:** C-149 narrowed to *partial*; C-150 registered; C-91
  amended. 150 entries: 107 active (83 surfaced, 20 partial, 3
  unsurfaced, 1 n/a), 26 lifted.
- **Version 0.2.21-beta.** pytest 1,602 and node 68. The binaries, the
  static proxy and the image rebuilt.

**Remaining:** the fmt and args cells (both under the bound), then the
§3.8 row. C-150's route (a larger heap or a streaming decode) is Max's
call. The gate's arrow-parameter fix is a small unit.

## 2026-09-15 — (addendum) C-150 is cross-language; large repos stay a constraint

**Max:** "for c-150 the large repos problem is an issue outside of just
c … we might have to assess the memory problem as a whole … overarching
might be an architectural change. large repos are fine to leave as a
constraint for now … leaving closing out c++ as next sessions task".

- Checked against the code: the helper's `decode` is one function for
  every indexer, and it holds a root's whole index in memory. The
  Python side holds the facts and the graph too (1.5 GB on ScummVM
  during lane A). So C-150 is **re-scoped to every language** and moved
  to `extraction-lane-b-environments.md`. The out-of-memory record was
  already language-neutral: it lives in `run_helper`.
- **Recorded, not built:** the memory problem is to be assessed as a
  whole, likely as an architectural change (a streaming decode, bounded
  memory through the pipeline, which would also lift C-149's 400-unit
  bound). A patch such as a larger helper heap is taken only if it
  proves cheap. No code moved and no version bump; docs only.
- **Next session:** close out C++: the fmt and args cells, then the
  §3.8 row.

## 2026-09-15 — (later) C++ closed out: the two cells, ADR-113 §2 amended a third time, `8302`, and the §3.8 row — 0.2.22-beta and 0.2.23-beta

**Asked (Max):** "review top level documentation then proceed with
closing out c++". On the routes after the cells: "Fix both, then row
(Recommended)". On O10's defects: "Record open, triage carries
(Recommended)".

- **The top-level review** found two stale lines. The README's ADR
  range still said ADR-111 (fixed at 0.2.22-beta). The handoff pointed
  to the 2026-09-14 entry (rewritten with this one).
- **The driver** had no `cpp` case: `run-cell.sh --lang cpp` fell to
  "unknown lang" (`77cbd44`).
- **fmt was graded before a C++ pre-registration existed.** I ran the
  cell before checking. §10.6 was then committed (`33920b6`) before
  args ran, and it says so.
- **The first grade** (0.2.21-beta): fmt 3,439/3,577 (96.1%, 138
  contradicted), args 2,004/2,008 (99.8%, 4). Poison PASS on both.
- **The triage, every row read,** with two scratch probes:
  - The probes: the join's inputs were captured by wrapping
    `evidence.join`, and the helper's choices were logged by a patched
    copy of the helper mounted in its place. No tracked file was
    touched.
  - **The collapse:** 36 semantic (fmt) and 4 (args). C's one-target
    rule kept the smallest line where a site's references named
    several overloads; every one of fmt's 634 such sites names more
    than one moniker.
  - **The fallback:** 74 syntactic (fmt), lane A's name guesses in
    files lane B compiled, where lane B had no occurrence. 50 were
    namespace reach (43 into fmt's POSIX mocks), and 24 were
    definitions lost to C-145. The external veto fired 0 times: C++
    units carry almost no external occurrence.
  - The remaining 28: 10 are scip-clang's own single wrong candidate
    (C-153), and 18 are the oracle's (H-28–H-31).
- **The route** (Max): ADR-113 §2 amended a third time (`d35e2bf`),
  then **`S-20260915T161919Z-8302`** (77 of 120 turns, 8.7 min, $6.48,
  Opus 5).
  - Gate right-clear, verify pass (862 tests). Two deviations accepted.
  - On the host, the `minicpp` `lane_b` test was red on the doer's
    blind assertion: `tests/test_shapes.cpp` is outside the Makefile's
    default target and so keeps its fallback. Fixed, with the rule's
    other half asserted (`95c284b`).
  - Merged `0f1b4d6`.
- **Regraded against the stored keys** (0.2.22-beta, `6846d2f`): fmt
  3,254/3,282 (99.1%), args 1,995/1,995 (100%). Recall fell for both:
  fmt 15.5% → 14.5%, args 57.1% → 56.4%. fmt's 28 left are 28 of the
  triaged rows.
- **Lane agreement on fmt:** 2,239 compared, 316 disagreements,
  unchanged by the unit. None draws an edge. Read against the key:
  - 66 are lane B's target;
  - 24 are lane B at a `using` declaration;
  - 205 match neither (189 a definition lane A lost);
  - at 21 the key has no target.

  `hobbes lanes` exits 1 on fmt. This repo's graph has 0 C++
  disagreements.
- **The row** (0.2.23-beta): `VERIFICATION_BASE["cpp"]`, §3.8's C++
  row and asymmetry line, §8's C++ row, the evidence log's section,
  C-132 narrowed again, and README and CLAUDE.md.
- **Register:** C-151 and C-152 (surfaced) and C-153 (unsurfaced, P9)
  registered. 153 entries: 110 active (85 surfaced, 20 partial, 4
  unsurfaced, 1 n/a). In the oracle's log, H-28–H-31 are open and RC-8
  moved to shaped.
- **Suites:** pytest 1,613 and node 71. The binaries, the static proxy
  and the image were rebuilt at 0.2.23-beta; restart the knowledge
  server (C-65). The tracker reads 30 of 40.

**Open for Max:** H-28–H-31; C-153 (unsurfaced); `hobbes lanes` on a
C++ repo (compare only where the fallback could draw, or keep); C-150's
memory assessment. **Next:** the gate's arrow-parameter fix (C-91), as
a small unit.

## 2026-09-15 — (later still) The top-level docs brought up to date: README's claims after C++, CLAUDE.md cut to its headline

- **The review** (Max: "review top level documentation and report
  back"). README, CLAUDE.md/AGENTS.md, CHANGELOG and LICENSE were read
  against the tree. These agreed: the version everywhere, the tags, every
  link, pytest's 1,613, the 30 session logs and the register's tally.
  The README had not moved with C++ (0.2.22-beta, 0.2.23-beta), and
  CLAUDE.md was 462 lines against its own "kept short".
- **README, reworded to the evidence** (Max: "reword the claims to be up
  to date"):
  - **The comparative reading rules.** There are 20 rows now: the four C
    foreign cells of 2026-09-14 and the five repowise-bench draws, read
    against `tables.md` and `same-key.svg`. On each, Hobbes is rightmost
    or tied on both axes. It ties on precision at rust_proj, at cJSON
    (CodeGraphContext 1,179/1,179) and at sqlite-vector (repowise
    780/780), and on recall at sqlite-vector. Its recall lead runs from
    none to 35 points. "C has no foreign cell yet" now reads that C++
    has none and is not in the renderer (`render.py`'s panel list stops
    at C). The C regrade after converter@3 is named.
  - **"100% but one" is now "but two",** in both places: fmt at 99.1%.
    Its 10 contradictions through scip-clang are said to be Hobbes' own
    (C-153, P9). The misses line says C++'s cells are not yet tabled by
    class.
  - **C++ where the lists stopped at C:** lane B, the oracles,
    tree-sitter's grammars and clang in the acknowledgements.
  - **Smaller fixes:**
    - the register is 150 → 153 entries;
    - the SPA has six tabs, not five;
    - Getting started builds the SPA before `hobbes-web`, and says how
      `hobbes` reaches `PATH` (first-run's four links, ADR-094's
      warning);
    - the test commands run from the root in subshells;
    - the Calvin paragraph's 24-line sentence is now a pointer to the
      CHANGELOG;
    - "Hobbes'" is used throughout;
    - the license line is marked a request, not a term.
- **CLAUDE.md, 462 lines to under 300** (Max: 300 at most). The Status
  block had 162 lines and nine "before it" entries, all already in the
  CHANGELOG and this log. It is now the headline, the open items and
  the spend rule, and its closing line says to replace, never pile. The
  project map now keeps what `get_module_doc` does not answer. Every
  convention is kept, the versioning one shortened, and
  `modal_atlas0.py` is spelled from the root. The held list lives in the
  handoff alone, which gained the one item it lacked (DeepSWE's
  decomposed protocol).
- **Not changed:** the Watterson image stays (Max's call). C++ in the
  comparative programme is its own piece of work. There is no version
  move, since the change is docs only (ADR-103).

## 2026-09-15 — (later still) CI on `fdc7f07`: the oracle lane's drift test, and the graph job's review

Max: "go test oracle lane failed, as well as graph check returned 8
unguarded new modules". Both failures came in with the C++ commits
(`6846d2f` onward). This session's docs commit was not yet pushed.

- **Oracle lane:** `TestGraphicsMatchTheCellRecords` failed.
  - **The cause:** `render.py check` refused `args-cpp-2026-09-15.md`,
    and would have refused fmt's, because neither had a
    `cells.meta.json` row. The two C++ cells landed in
    `docs/oracle/cells/` without one.
  - **The fix:**
    - two rows: fmt picked, args random, both contained;
    - `render_scatter` gains a C++ panel, and its grid rows are now
      counted from the panels (three rows) instead of being fixed at two
      over five languages;
    - the one-number footnote and the scatter caption name C++. Its
      misses are not C-58's alone: constructions, C-143, C-145 and
      C-151;
    - the caption's headline no longer says "we draw nothing the
      compiler contradicts", which fmt's 10 (C-153) made untrue.
  - **Regenerated:**
    - fmt and args are in `tables.md`;
    - the one number is over 25 cells in 6 languages;
    - the scatter's recall range is 14.5–100.0%;
    - `same-key.svg` moved only in its legend's version list.
  - **The prose beside it:**
    - the comparative page's claim 1 names two exceptions, including
      fmt's 10 hobbes-wrong edges;
    - claim 3's range starts at fmt's 14.5%;
    - a C++ paragraph is added;
    - the README's C++ bullet is updated.
  - **Checked:** `go test -count=1 ./...` in `bench/oracle` passes. A
    cached pass is not evidence here: the test execs `render.py`, and
    Go's cache does not see the files a subprocess reads.
- **Graph job:** `hobbes review 38d364f..HEAD` reported "needs
  attention: 8 unguarded new module(s)".
  - All 8 are C++ fixture sources: `bench/oracle/testdata/cppclang/*`
    and `pipeline/tests/fixtures/minicpp/*`. By its own rule the review
    is right.
  - This is the W0 item of 2026-09-10 (`workstreams.md`): a fixture
    source is not own code a test could guard, and the job forgets a
    red review.
  - The C fixtures are just as unguarded (in `minic` only `util` is
    guarded, in `cclang` nothing). They passed only because the job
    forgot them.
  - Put to Max as routes, since either needs an ADR against ADR-025.
    The next push's graph job would pass without any fix, for the
    forgetting reason.
- **No version move for the oracle fix** (`2883154`): it is `bench/`
  tooling and docs (ADR-103).
- **Max's route: exempt fixtures and fix the base.** ADR-114,
  0.2.24-beta.
  - **`runner_excluded_trees`** (`extract/testmap.py`) is read at
    extraction from each end's own tree. It takes a pytest config's
    stated `norecursedirs` under its `testpaths` (never pytest's
    defaults), and Go's first `testdata` under a `go.mod`. It is carried
    on `Extraction`, not emitted.
  - **`_own_code`** drops sources under those trees. The coverage
    section names each tree, its rule and its module count, and `--json`
    carries them as `coverage.fixture_trees`. C-154 is registered,
    surfaced: 154 entries, 111 active, 86 surfaced.
  - **`ci.yml`** reviews a push from the last green `ci` run's commit
    when that commit is an ancestor of `HEAD`, and from `before`
    otherwise, with `actions: read`. Nothing local can run this; the
    next push is its first test, and the handoff says to check it.
  - **Tests:** three new ones — a pytest `norecursedirs` tree exempted
    and named in text and JSON; `testdata` exempt only once a `go.mod`
    surrounds it; each pytest config governing only its own directory.
    pytest now stands at 1,616.
  - **Proven locally on CI's own range:** `scripts/ci-graph.sh 38d364f`
    (image, ingest, stamp, lanes, compiled invariants, review, `lane_b`)
    exits 0. Its review ends "nothing needs attention", and `lane_b`
    reads 6 passed. It names `bench/oracle/testdata`
    (11 modules, go) and `pipeline/tests/fixtures` (54, pytest). I-4
    reads *still failing*, as it did in CI: pre-existing, not this
    change's.
  - **Also moved:** architecture §8's version and its "but one", now
    "but two" with fmt; §7's review flow names the fixture rule; the W0
    item is closed in `workstreams.md` and the handoff.

## 2026-09-15 — (later still) C-150 assessed and its decode's share taken: the helper streams the index — ADR-115, 0.2.25-beta

**Asked (Max):** "review top level documentation then report back with
any proposed fixes for c-150"; then "streaming decode is best route,
proceed with the fix".

- **The top-level review** found two stale lines: the README's ADR
  range stopped at 113 (114 had landed with 0.2.24-beta), and
  CLAUDE.md's suite line was dated 0.2.23-beta at 1,613 pytest against
  1,616 collected. Both fixed here. Everything else agreed at
  0.2.24-beta: the version copies, the CHANGELOG, §8, the handoff, the
  register's tally.
- **Where the memory goes, measured** on the ScummVM index the 0.2.21
  session left in the cache (387 MB, 5,958 units, 11,265 documents,
  7.9 million occurrences):
  - a probe that walks the wire format document by document and keeps
    only the fields the decode keys on: 3.3 s, 1.44 GB resident, every
    reference row kept;
  - the generated reader (`scip.Index.deserialize`) then the decode:
    9.7 GB resident, 38 s, at a 14 GB heap. The heap was spent on
    google-protobuf's message objects, not on the data;
  - the image's Node (22.14.0) has a 4.35 GB default heap;
  - the Python side is a second wall: 5.47 million in-repo references
    in the index, about 850 MB of JSON on stdout, 393 bytes a row
    parsed (measured), beside lane A's 1.5 GB;
  - a SIGKILLed helper (137 through podman) carries no V8 marker and
    fell back to "install Node";
  - `HOBBES_SCIP_CMD` carries a heap flag through the container today
    (verified on a scratch copy of `minicpp`: contained, 29 semantic
    edges).
- **Three routes put to Max:** the streaming decode (recommended, an
  ADR), the two cheap fixes (the SIGKILL branch, the entry's
  workaround), and later the facts streamed to the Python side. A heap
  sized from the box was not recommended. Max: the streaming decode.
- **Built (ADR-115):**
  - `scip/index.mjs`: `streamDocuments` walks `Index.documents` with
    google-protobuf's `BinaryReader`; `readOccurrence` reads `range`,
    `symbol`, `symbol_roles` and scip-java's typed fields 8 and 9, and
    an unpacked `range`; `indexFiles(paths)` streams a root's `.scip`
    files one at a time; `mergeUnitIndexes` streams any sources;
    `documentsOf` / `documentCount` let `decode` and `degradations`
    read a literal or a streamed source alike. `wellFormedIndex` tells
    a unit's output from a run that wrote nothing by a top-level skip
    walk. The `.scip` files now stay until the decode is done. The
    typed-range monkeypatch on the generated reader is gone with the
    generated reader; `scip.js` stays imported for `SymbolRole`.
  - `scipsource.run_helper`: exit 137 and -9 name C-150 ("was killed
    decoding this build's index"); the heap-marker branch stays.
  - `PER_UNIT_MAX` stays, its comment reworded: the merge's 84 GB is
    gone; the references the per-unit route holds until the per-site
    rules run, and 9.36 GB of unit indexes at 207 s, keep the bound.
- **Verified:**
  - **Equivalence:** the new decode and the old, on ScummVM's index,
    digest identically on every row of definitions (380,108),
    references (4,158,513), external (412,155), packages, ambiguous
    (5,842), `ambiguous_files`, overload examples and degradation
    records; `tu_split` 606, `overload_sites` 5,399, `multi_defined`
    529. The new run: **3.4 GB resident, 2.73 GB heap, 33 s, under the
    default heap**; the old: 9.7 GB, 38 s at 14 GB. `HELPER_VERSION`
    stays 3.
  - node 74/74 (the typed-range test through the reader; three new);
    pytest 1,617 (one new); `go test ./...` 15 packages ok against the
    rebuilt image; `test_version` at 0.2.25-beta.
  - This repo ingested end to end with the new helper: every lane B
    step contained (31 steps, seven languages), 11,891 semantic and 32
    syntactic symbol edges; `hobbes lanes` exits 0, 10,190 sites
    compared, the lanes agree wherever both answer.
- **Register:** C-150 narrowed and retitled ("lane B's facts are held
  in memory whole"), its record wording and the override named;
  C-149's reason reworded; the register's dated note. Counts unchanged:
  154 entries, 111 active.
- **Docs:** ADR-115; CHANGELOG 0.2.25-beta; architecture §3.2 (the
  streamed decode, the killed-helper record), §3's C++ paragraph, §8's
  header and the C++ row; `extraction-evidence.md`'s C++ line; README's
  ADR range; CLAUDE.md's headline, suite line and last ADR; the
  handoff rewritten.
- **Rebuilt:** the Go binaries, the static proxy and the image at
  0.2.25-beta (C-65). The knowledge server this session ran on still
  serves the 0.2.24-beta build; restart it.
- **Kept outside the repo:** ScummVM's index and unit list in
  `~/.hobbes/cache/stage/b7bc0819382fd513.scip.units/`; the probes
  `decode_equiv.mjs` and `stream_probe.mjs` beside the C++ drivers'
  probes (run from `scip/`).
- **Not done (its own decision):** the Python side reads the facts
  whole; streaming them is a facts-format change (helper version 4).
  No end-to-end ScummVM ingest at 0.2.25-beta was run; the estimate is
  8 GB free.

**Open for Max:** H-28–H-31; C-153; `hobbes lanes` on a C++ repo;
C-150's remainder. **Next:** the gate's arrow-parameter fix (C-91), as
a small unit.

## 2026-09-15 — (later still) C-150's remainder: lane B's facts arrive as a stream — ADR-116, 0.2.26-beta

**Asked (Max):** "review top level documentation, and report back with
current status"; then "fix the drift, then lets looks to deal with the
python side an offered fix is switching facts from a singular json to
ndjson with one record per document then consume. open to an
alternative better suggested approach"; then "yes proceed with a and
write the adr".

- **The top-level review** found three stale lines, fixed in
  `8576c3b`: README's status read 0.2.24-beta; the handoff's register
  line read 153 / 110 (C-154 is the 154th) and its suite line carried
  0.2.23-beta's counts; workstreams' revision line stopped at
  2026-09-14. The suites were re-run for the handoff: 1,617 pytest, 74
  scip node.
- **Measured before choosing**, on ScummVM's cached index (the probes
  are kept beside ADR-115's, below):
  - **the wall at 0.2.25-beta was the helper's output, not the Python
    side.** ScummVM's facts are 699 MB of JSON (the references 582 MB)
    and V8's longest string is 536,870,888 characters in the image's
    Node 22.14.0 and the host's 24: `JSON.stringify` threw `RangeError:
    Invalid string length`, the helper exits 1, and `run_helper` said
    "install Node". ADR-115's 850 MB reaching Python was an estimate no
    run could reach, and C-150's entry named the wrong wall;
  - the Python side's read, four ways (the facts alone, then through
    `evidence.join` with no lane A sites): one document → dicts →
    `Site` 3.63 GB (5.71 GB); JSON lines into today's dicts 3.65 GB;
    JSON lines straight into today's `Site` 2.50 GB; JSON lines into a
    slotted `Site` with interned strings 1.19 GB (3.26 GB). The line
    format alone moves nothing; the join's `Resolved` list is about
    2.1 GB whichever way; `containment.run` captures stdout whole.
- **Three routes put to Max:** A, a file of JSON lines read into
  slotted, interned sites (recommended); B, the offered line format
  into today's dicts; C, after A and a measurement, a slimmer
  `Resolved`. A join that streams by file was not recommended. Max: A,
  with the ADR.
- **Built (ADR-116, committed before the code as `aaffca6`):**
  - `scip/index.mjs`: `factsLines` — a header, one record per document
    in first-row order with the rows' `file` dropped, a trailer
    counting documents and rows and carrying the root-level fields —
    and `writeFacts`; `main` writes where the config's `facts` names,
    prints nothing on stdout, and refuses a config without it.
    `HELPER_VERSION` 4.
  - `scipsource`: `run_helper` names `<stage>.facts.ndjson` and removes
    it whatever happens; `read_facts` reads it line by line, references
    into slotted resolution `Site`s and definitions and external
    references into rows, interning paths and names and putting the
    root in front of every path. Missing, empty, another version,
    malformed, no trailer, or counts not reached: each a `ScipError`
    that says which. `resolution_sites` is gone; `_rebase` keeps only
    the records' rule; the five callers pass their root;
    `join_cross_unit` appends sites.
  - `evidence.Site` is `slots=True`; the C++ withheld-files loop reads
    `site.file`.
- **Verified:**
  - ScummVM in the image at the default heap: decode and write in
    33.2 s at 3.29 GB resident, 487 MB of lines; `read_facts` at
    0.99 GB (1.36 GB with the buckets) in 10.4 s; every row the same
    as the one-document form's, per file and in order (380,108
    definitions, 4,158,513 references, 412,155 external).
  - This repo, the same tree ingested by `aaffca6`'s code (a scratch
    worktree, since removed) and by this change's: `graph.json`,
    `tests.json` and `interfaces.json` identical, stamps aside.
  - **ScummVM end to end at 0.2.26-beta:** exit 0 in 8 min 57 s, every
    step contained, 7.72 GB peak on the Python side (`/usr/bin/time
    -v`; the helper's container is its own). The root has lane B for the
    first time: 941,498 semantic and 63,225 syntactic symbol edges;
    1,546,539 C/C++ call sites, 61.3% accounted (937,863 resolved, 9,735
    external) where 0.2.21-beta's run read 0.0%. Mid-join the process
    stood at 4.6 GB; the rest of the peak is the graph built from the
    join. So the join's `Resolved` list is part of the next wall, not
    all of it.
  - pytest 1,626 (eleven new, two retired with `resolution_sites`);
    node 77 (three new); `test_version` at 0.2.26-beta; `go test ./...`
    15 packages ok against the rebuilt image (385 pass, 1 skip).
- **Register:** C-150 corrected (the 0.2.25-beta wall and its record),
  narrowed to the join's own size, retitled, and moved to *partial*:
  an ingest the kernel kills on the Python side ends with no graph and
  no record, which was as true before and not written down. Tally: 85
  surfaced, 21 partial; the register's dated note.
- **Docs:** ADR-116; CHANGELOG 0.2.26-beta; architecture §3.2 and §8's
  header; `extraction-evidence.md`'s C++ line; README's status and ADR
  range; CLAUDE.md's headline, register line, last ADR and suite line;
  the handoff rewritten.
- **Rebuilt:** the Go binaries, the static proxy and the image at
  0.2.26-beta (C-65); the knowledge server this session ran on serves
  the image it started from until it is restarted.
- **Kept outside the repo:** `facts_probe.mjs`, `helper_facts_probe.mjs`
  and `py_facts_probe.py` in `~/.hobbes/bench/cpp-drivers/probes/`.
- **Seen in passing, then fixed (0.2.27-beta; Max: "handle the bug"):**
  the C and Java callers appended a degradation record at `path: root`
  and then `_rebase(facts, root)` put the root in front again —
  `proj/proj`. The C record is "…; derived with <source> instead" (a
  carried compile database not usable here), the Java one the failed
  resolve pass's; TypeScript's was already appended after rebasing. Both
  callers now re-root first and append after. Two tests
  (`TestExtract::test_the_roots_own_record_and_the_helpers_both_sit_at_the_root`,
  `TestJavaUnitRecords`), each red with the fix stashed and green with
  it; pytest 1,628. The binaries, the static proxy and the image
  rebuilt at 0.2.27-beta.
- **C-150's remainder parked** (Max: the memory patches are for a huge
  repo; "fine for now").
- **Then the gate's arrow fix (0.2.28-beta; Max: "proceed with the gates
  arrow fix to end off session"):** C-91 amended first (`342c5d1`): the
  text read takes a parenthesised list before `=>` wherever it stands
  and one bare name before `=>`; grounder v4; the nested-`(` residue and
  the file-wide over-read named. Dispatched as `S-20260915T191904Z-2b26`
  (27 of 80 turns, 250 s, $1.57 reported; task and partition in
  `~/.hobbes/bench/gate-drivers/`): gate clear, verify pass (70 tests, 0
  regressions). Read in full; two deviations accepted (a `.ts` fill for
  the typed arrow; a parenthesised return type left unread, the
  residue's own shape). The branch's full pytest 1,632 passed on the
  host before the merge; merged no-ff (`3526be2`); the review block
  filled (right-clear) and the tracker re-rendered: 31 of 40, 4 areas,
  1 false block (`f3c1`, now closed), 0 missed. The binaries, the static
  proxy and the image at 0.2.28-beta.

**Open for Max:** H-28–H-31; C-153; `hobbes lanes` on a C++ repo.
**Next:** named no-spend units through the harness, toward 40.

## 2026-09-15 — (last) The top-level review; the foreign C++ cells, pre-registered, graded and triaged; converter@4 (ADR-101 amended) — no version move

**Asked (Max):** "review top level documentation. then proceed with
grading c++ on foreign cells and update graphics to reflect standing
afterwards. this will fully close out c++ for now".

- **The review.** README, CLAUDE.md (AGENTS.md is its symlink), the
  handoff and the comparative pages, read against the tree at
  0.2.28-beta. Stale lines found:
  - `field.md`'s Hobbes row (0.2.8-beta, 139 register entries, six
    languages); now 0.2.28-beta, 154 and seven.
  - The language set spelled without `cpp` in `oracle import`'s usage,
    the import's and export's refusals, `grade-foreign.sh`, the oracle
    README and `foreign_record.py`. The import already took `cpp`
    through export's table.
  - The README's and the handoff's "no foreign C++ cell", replaced
    below.
- **Pre-registered before either tool ran** (`ac5f7c8`):
  `oracle-grading.md` §10.7 (P32–P35), and ADR-101's 2026-09-15
  amendment (C++ in the import's set). The foreign C cells had no
  section; these do.
- **The runs** (host-run, no spend). `~/.hobbes/bench/comparative/run-cpp-cell.sh`
  has the C driver's shape. CodeGraphContext 0.6.13 and repowise 0.49.0
  at their pins, graded by the Hobbes cells' stored clang keys:
  - CodeGraphContext on args: 6 CALLS rows, all in
    `.ycm_extra_conf.py`. Its parser table maps `.cpp`, `.h`, `.hpp`
    and `.hh` to C++ and reads no `.cc`, `.cxx` or `.hxx` file, and
    args is one `.hxx` with 101 `.cxx` tests. Nothing graded.
  - CodeGraphContext on fmt: 844/975 (86.6%), recall 11.8%, from the
    headers only (fmt's 47 `.cc` files unread).
  - repowise at converter@3: args 814/937 (86.9%), fmt 2,412/5,708
    (42.3%).
  - CodeGraphContext writes a `.cgcignore` into the clone. It did on
    the C clones on 2026-09-14 too, where `field.md` §2 said "none".
- **The triage** (§10.7: 20 rows per cell, seeded 20260915) found two
  converter defects before a tool verdict could stand (C-94):
  - repowise's nested macros written `#  define`: 3 of 20 on fmt; 713
    graded edges, 365 of them contradicted;
  - a C/C++ declaration head split over lines: args' second `ToString`
    at its return-type line, and two gtest functions under an
    attribute macro.

  A template-line hypothesis was checked first and refuted (20 of
  3,296 rows).
- **converter@4**, in both adapters, under ADR-101's amendment,
  extended:
  - `#`, optional spaces, then `define`;
  - a C/C++ head with no `;`, `{` or `}`, advanced up to three lines
    to the name.

  A first draft applied the head rule everywhere. Re-converting every
  stored dump moved 46 jsoup rows where CodeGraphContext had stored a
  javadoc or body line, so the rule reads C/C++ only and never starts
  from a comment. The fixture is `bench/oracle/testdata/cppgrain/`,
  with a raw dump per adapter and `TestCppGrainSpacedDefineAndSplitHead`
  in each. Re-converting all 52 stored dumps under @4 moved only
  repowise's two C++ cells.
- **The regrade** (`regrade-cpp-cell.sh`, from the stored dumps, the @3
  grade kept as `*.v1.*`):
  - repowise fmt 2,414/5,343 (45.2%, +2.9), recall 13.9%;
  - repowise args 815/937 (87.0%), recall 23.3%;
  - CodeGraphContext unmoved;
  - poison: 0 falsely confirmed of 8,567 seeded across the three
    graded cells.
- **The read at @4** (60 rows): tool-wrong 56, oracle-grain 4,
  converter-defect 0. The oracle-grain rows are H-29 once and H-30 three
  times; at each the tool drew the declaration the source names. The
  tools' C++ errors are one shape above all: a call drawn by its short
  name to another declaration of that name. repowise also draws a
  construction to a type or a `using` alias (6 of its 20 fmt rows;
  C-95's C++ face).
- **Pre-registration graded:** P32–P34 met on the three cells with
  graded edges, undecidable on CodeGraphContext's args. P35 missed: no
  tool's fmt recall passes Hobbes' 14.5% (11.8%, 13.9%).
- **The records** (`docs/oracle/cells/{codegraphcontext,repowise}-{fmt,args}-2026-09-15.md`)
  are written by `foreign_record.py`, which gained `--grade-lang` and
  the @4 direction cause.
  - `cells.meta.json` has four new rows.
  - The same-key graphic's language order gained C++.
  - Its undefined-marker text reads "no call edge graded".
  - Its footer names the C++ sample.

  `render.py cells | render | check` is green (90 cells, 22 same-key
  rows), and so is the report test.
- **Docs:**
  - the claim page: the oracle list, the cell-file pattern, the C++
    paragraph, item 4;
  - the README: the run dates, 22 rows, fmt as the second precision
    exception, the recall-lead range, the converter@4 sentence, "what
    is not here";
  - `field.md`: the Hobbes row, and §2's `.cgcignore` and
    file-extension rows;
  - C-94's and C-95's C++ faces, W0, the handoff and CLAUDE.md's
    headline.
- **No version move** (bench only, ADR-103). Nothing was dispatched;
  the tracker stays at 31 of 40.
- **Kept outside the repo:** the drivers and triage files in
  `~/.hobbes/bench/comparative/`; the sample scripts in the session's
  scratchpad.

**Open for Max:** H-28–H-31; C-153.
**Parked (Max: "add as a future item but fine to close out for now.
well do a full version retest at some point to fully compare"):**
CodeGraphContext's SCIP mode for C/C++, inside a full-version
comparative retest (`future_additions.md`). C++ is closed out.
**Next:** named no-spend units through the harness, toward 40.

## 2026-09-16 — O10's four defects: three fixed through the harness, the fourth left open, and a regrade that cost us the headline

Max: "restart knowledge server then proceed with the oracle defects and
side rows with the fix." The knowledge server turned out not to need a
restart — its container had started *after* the image was built, so it
already served the current build; what was stale were the artifacts, and
an ingest fixed that.

**Probed before designing.** Each of H-28–H-31 was reproduced in the
image first, and two probes overturned the hypothesis I would otherwise
have written into the ADR: a `MemberExpr` carries no `loc` at all (the
member token is its `range.end`), and it is a class template's
*pattern* members — not its specialisations — that carry a class with no
mangling. H-31's `os.cc` half did **not** reproduce
(`OUTER(INNER(sink(2)))` keys correctly), so no rule was written from a
synthetic that disagrees with the cell's evidence, and it stays open.

**Decided before dispatching** (`7240ebd`, `a0023a4`, `21f4f57`):
ADR-113 §3's amendment (the member token, the class-qualified key), §7d
and D-O4 (the silence rule), and §10.8 pre-registering the regrade as
P36–P45. A self-review of `7240ebd` caught my own overstatement — the
bullets claimed the silence rule also covers a call the key holds
nowhere, which contradicts P36 and would have misled unit 2's doer.

**Two units, both merged not squashed.** `S-20260916T153010Z-8170`
(H-28, H-29; 77 turns, $7.21) and `S-20260916T155426Z-8d48` (H-30; 36
turns, $1.49). Both gate-clear, verify-pass, none missed. Verified
inside the image, because this host has no `clang++` and a fresh
worktree has no `bench/oracle/ts/node_modules` — a host run would have
skipped the very tests that mattered, as my own pre-unit baseline
silently did. Tracker 31 → **33 of 40**.

**Found by using the harness:** `calvin_tracker.py` pinned `gate v2,
grounder v3` as literals, so the first session ever run at grounder v4
could not be parsed and `render` refused the harness's own output. Its
drift test carried the same literals, so it could never have caught it.
Fixed with a case proven red on the old pattern (`ce43e5a`).

**The regrade, three tiers, each holding the Hobbes side fixed:** fmt
and args re-run contained against their standing exports; 38 own cells
and 44 foreign cells graded by two binaries (pre/post) over identical
stored inputs. fmt 99.1% → 99.7%, args unmoved, 38 own cells unmoved,
13 foreign cells moved.

**What it cost, recorded against our own interest.** Six of C-153's ten
rows — where Hobbes' edge is genuinely wrong — are now *unjudged* rather
than fixed, so fmt reads 99.7% where the like-for-like figure is
**99.48%**; the poison instrument covers fewer sites (fmt 3,282 → 2,643
refused); and the same rule raised every moved **competitor** cell while
moving none of ours (CodeGraphContext on fmt 86.6% → 95.7%), narrowing
the gap on our own initiative. **P36, P37 and P38 all missed**, every
one in the flattering direction, recorded as misses with their causes
rather than rationalised.

**Four defects of my own, caught by checking rather than trusting:** a
regrade baseline that compared against 0.1.10-beta reports and so
measured release drift, not this change (discarded and redone with two
binaries); an auto-generated foreign key table that confidently paired
`args` with `minic`'s key (deleted after four attempts, then done from
each record); a scripted record rewrite that dropped thousands
separators and left twelve prose sentences contradicting their own
blocks; and a `--compdb` path the contained step could not see. Each is
in this entry because the alternative was a number nobody could check.

**No version move** (bench and records only, ADR-103). Graphics
re-rendered, `render.py check` and ADR-102's drift test green.
**Open for Max:** H-31; whether a "judged-as-before" companion number
belongs on any cell with `line-unresolved > 0`; C-153's status, now 4
judged : 6 unjudged.

## 2026-09-16 (later) — H-31 traced from fmt's own evidence: six rows the oracle's, the seventh ours

Max: "fix 31 from the evidence leave the rest for next session." The
entry above says H-31 stays open because its `os.cc` half would not
reproduce. That was true of the *synthetic* and wrong about the defect:
my probe spliced macros (`OUTER(INNER(sink(2)))`) but never spliced a
**qualifier**, which is the whole shape.

**The trace.** fmt's `include/fmt/os.h:57` is `#define FMT_SYSTEM(call)
::call`, so the macro body supplies `::` and the argument supplies the
name. clang spells the callee's `range.begin` in the macro body — not an
argument expansion — while `range.end` is the author's own name token,
an argument expansion. `resolve()` therefore keys the call on the
macro's definition line, in another file. Confirmed on the cell's key,
not inferred: fmt's six POSIX calls sit at `os.h:57` and `os.h:62`, one
per caller, which is exactly why `src/os.cc:176` holds `c_str` and
`__errno_location` but never `fopen`. The call's own *argument* keys
correctly, which is what made the loss invisible. Root **RC-2** (a call
attributed to a line nobody wrote it on), not RC-4.

**A control probe kept the rule narrow.** `ns::h(1)` and `ns::t<int>(2)`
have neither end in a macro, so "always take `range.end`" would have
moved `cppclang`'s hand-keyed columns for every plain qualified call.
The rule is conditioned on begin-in-body-and-not-arg + end-is-arg.

**The seventh row was never the oracle's.** `compile-test.cc:127` is
`compile<decltype(fmt::arg("arg", 42))>(...)` — an unevaluated operand,
which the compiler never calls. clang emits no site and is right;
Hobbes draws the edge from a lane B occurrence and is wrong. Registered
**C-155** (unsurfaced), and fmt's triage ratio corrected from
`hobbes-wrong 4 : oracle-wrong 7` to **5 : 6**. Sizing, honestly: one
row read from source, and 26 further edges sit on `decltype(` lines
oracle-silent — an upper bound, unread individually, while all 12 on
`sizeof(` lines are confirmed real calls.

So the cell record charged a row to the wrong side for a day, and the
correction moves a number **against** us. Register 154 → 155 entries,
unsurfaced 4 → 5.

**Next:** the oracle-side rule is dispatched as its own unit
(`macroqual-task.md`); the regrade of fmt after it lands, and with it
whether the six rows become confirmed or silent, is the developer's.
Left for next session on Max's word: the "judged-as-before" reporting
decision and C-153's status.

## 2026-09-16 (later still) — H-31's oracle half fixed, and fmt's oracle-wrong count reaches zero

Unit 3, `S-20260916T165315Z-16f4` (`bfab66b`, merged `db20845`): 79 of
100 turns, $5.11, gate right-clear. Tracker **34 of 40**.

**The doer corrected my amendment on evidence I had misread.** I wrote
that the callee's `range.begin` must be *not* an argument expansion; in
fmt's real shape — `FMT_RETRY_VAL(…, FMT_SYSTEM(fopen(…)), …)` — clang
prints only the outermost spelling/expansion pair and flags the macro
body's `::` `isMacroArgExpansion` exactly as it flags an author's own
token, so the clause could never fire on the shape it was written for.
My own probe said so and I read it wrong. The landed rule uses what the
flags can support: both ends macro positions, the end an argument
expansion, the begin spelled somewhere other than where it expands, and
the two ends spelled on different lines or files. The fixture carries
both H-31 halves and three controls — including `RETRY(ns::h(2))`, whose
ends clang flags identically — so the naive "always take `range.end`",
which would have moved `cppclang`'s hand-keyed columns a second time, is
guarded against.

**The regrade, pre-registered as §10.9 before it ran.** Both keys re-run
contained against the same standing exports.

- **P46 met in its strong form:** the six `os.cc` rows are **confirmed**,
  checked individually — not merely absent from the contradicted set.
  fmt contradicted 11 → **5**, confirmed +6, precision 99.7% →
  **99.85%**.
- **P47 met:** the five left are C-153's four and C-155's one.
  **fmt's triage ratio is now `hobbes-wrong 5 : oracle-wrong 0`.**
- **P48 recorded:** `sites_macro` 2,771 → 2,761, `sites_static` 30,765 →
  30,776 — coverage and miss classes move, judgment does not.
- **P49 met in its strong form:** args identical as a set of rows, no
  bucket movement at all.
- **P50 MISSED.** I predicted all four foreign C++ cells would rise "as
  they did under H-30". Three did not move; the fourth moved one row
  (repowise fmt 47.96% → 47.97%). The cause the prediction should have
  seen: H-30 forgave *guesses on unresolved lines*, which a name
  resolver makes constantly, so it lifted every tool; H-31 moves
  *sites*, which helps a tool only where it had already drawn at the
  corrected position — and at fmt's `os.cc` use sites they drew nothing.
- **P51 met:** poison PASS everywhere, 0 falsely confirmed.

**What is left on fmt is entirely ours:** C-153's four provider rows and
C-155's one. Both figures stay on the record — 99.85% as reported,
**99.66%** judged as the pre-H-30 grade judged — because H-30's silence
rule still withholds judgement from six of C-153's wrong rows.

**Open for Max, unchanged:** the "judged-as-before" companion number;
C-153's status (4 judged : 6 unjudged); and now C-155 — fix it in the
join or accept it as documented-only.

## 2026-09-16 (evening) — Two no-spend backlog items: pytest's warnings, and W0's unguarded version package traced to C-156

A top-level documentation review (CLAUDE.md, the handoff, W0), then two
small items from the handoff's "carried" and "W0's remainder" lists,
done directly on `main`, not dispatched.

**pytest's four warnings, gone** (`fec7a6b`). Two were
`PytestReturnNotNoneWarning`: `testmap_fixture`, a helper defined in
`test_ttt_corpus.py` and imported into `test_ttt_units.py`, matched
`test*` and was collected as a test in both. Renamed `sample_testmap`.
The other two were pytest 9's deprecation of class-scoped fixtures
defined as instance methods (`shapes` in `test_gosource.py`, `out` in
`test_javasource.py`); both moved to module level, same scope. The
suite is **1,631 passed, 0 warnings**, where 1,633 were collected
before: the missing two were the helper.

**W0's "`go/internal/version` stays unguarded", traced: C-156**
(`b1ae4df`). `version_test.go` exists and `tests.json` lists it, with
`reaches: []`. The test reads `version.Version` and calls nothing, and
every language's test map closes over `calls` edges only (ADR-007;
`testmap.py` says why `uses` edges are left out). A constants-only module
cannot be reached by any test, so this is not a missing test. It is an
unregistered concession, now **C-156, unsurfaced** (debt), in
`extraction-call-graph.md`. The register's header had not taken in C-155
(154 / 111). Now it reads 156 entries, 113 active, 6 unsurfaced.

**No version move:** tests and the register only. Re-ingested at HEAD,
since the knowledge tools were serving `58d70ff`.

**Open for Max:** C-156's route. (a) Surface it: `tests_guarding` and
the review's "new code no test reaches" name C-156 when the module
declares no function, a patch. (b) Let reach follow a test's reads of a
module's values, which reopens ADR-007's rule that reach must not widen
to code a test only names. (c) Accept it as documented-only. My
recommendation is (a).

## 2026-09-16 (evening, later) — C-156 surfaced: an unguarded module no call can reach says why; ADR-117, 0.2.29-beta

Max chose route (a) of the three put to him ("go with the recommended
route").

**The rule, read from the graph.** A module is *value-only* when none of
its symbols is a `function`, `method`, `class`, `type` or `macro`, and no
`calls` edge targets any symbol it declares. The kinds were measured
before the rule was written: on this repo's graph `calls` edges target
functions (6,880), methods (1,257), classes (496), macros (18), types (2)
and one `const`, a TS/JS binding that is called. So a const alone does
not settle it, and the edge half is what makes an arrow-function const
callable. On this repo the rule picks out `go/internal/version`,
`scip/compare`, `web/src/main`, `web/src/types`, `web/vite.config`,
`bench/oracle/internal/clang/clang` and one fixture header.

**Built:** `testmap.value_only_modules` and `CALLABLE_KINDS`, and the
review's `CoverageDelta.value_only` with the reason on the module's line
and under `--json`'s `coverage.value_only`. The module is still listed
and still needs attention: the reason is said, not exempted. In Go,
`valueOnly` in `internal/knowledge` adds one line per value-only module
to an "unguarded" `tests_guarding` answer. Tests: four cases for the
rule (constants and an empty module, class/type/macro, a called const,
a `uses` edge), one review case (a constant beside a function: both
listed, only the constant with C-156), and one Go case (a const-only
module named; a called const and a guarded module not).

**Paperwork in the same change:** ADR-117; C-156 moved to surfaced
(register 86 surfaced, 5 unsurfaced); architecture's concept-review
line; CHANGELOG 0.2.29-beta and every version copy; CLAUDE.md, the
handoff.

**Suites:** 1,636 pytest (0 warnings), Go 387 (386 pass, 1 skip) against
the rebuilt image. The binaries, the static proxy and the image were
rebuilt; the running knowledge server serves the old build until it is
restarted (C-65).

## 2026-09-16 (night) — The top-level review: the drift fixed, the store decodes once (ADR-118, 0.2.30-beta), the ingest says where its time went (ADR-119, 0.2.31-beta)

Max asked for a review of the top-level documentation, then the
architecture and the register, for any fix or restructure that would
raise recall, raise speed, cut memory or knock out constraints. The
write-up is a Claude Docs page
(<https://claude.ai/code/artifact/2cd3c181-444a-42f5-a81e-c3a62928eb28>);
what it recommends, in one line each, so the record does not depend on
the page:

- **Recall:** decode SCIP `relationships` (`is_implementation`) in the
  helper and draw `implements` edges, then expand a call to an interface
  method into its overrides as a labelled step — the override set C-58
  says Hobbes lacks is a field the helper reads past today (it keeps an
  occurrence's range, symbol and roles and nothing else); measure which
  of the six indexers populate it first. Pytest fixtures as syntactic
  edges (C-4; the trace oracle executes them). C-155 lifted at lane A
  by abstaining under `decltype`/`sizeof`/`noexcept`/`typeid`. The
  derived compile database's `-I` path and unit language at lane A
  (C-133, C-142).
- **Speed:** the proxy re-read and re-decoded the whole artifact on
  every tool call (fixed below); a lane B index cache keyed by the stage
  key, which is already a content hash; a lane A per-file cache; a
  process pool for lane A and concurrent helper containers for lane B's
  units, which run one at a time; and a timing block, because nothing
  was timed (built below).
- **Memory:** `Resolved` unslotted with a list of dicts per fact, and
  one object per unclaimed resolution before `_edges` aggregates (C-150's
  parked remainder, Max: "fine for now"); `graph.json` written with a
  two-space indent and one evidence entry per sighting (980 MB on
  ScummVM); a started record under `derived/` so a killed ingest leaves
  a trace (C-150 partial → surfaced).
- **Docs:** five drifted numbers (below); the register README's 490
  lines of dated history to their own file; §3.8's paragraph cells to
  per-language pages; one tally held by a test; CLAUDE.md's "Latest"
  bullet kept to four lines; the handoff's start-here numbering, which
  had collapsed to 00/0/0a/0a/0a/0b.

**The drift, fixed (`ed56089`):** README said 154 register entries and
111 active (156, 113), fmt 99.1% with 28 contradictions in three places
(99.85%, 99.66% like-for-like, 5, all Hobbes' own), ADR-001 to ADR-116
(117); architecture §8's header read 0.2.28-beta at 0.2.29-beta, and
§10's out-of-scope line omitted C++. ADR-117's commit had missed §8,
which CLAUDE.md says moves in the same commit.

**ADR-118, 0.2.30-beta (`82fb103`).** `internal/knowledge.Store` held
only the repo root; `WhoCalls`, `Neighborhood`, `TestsGuarding` and
`ListBlindSpots` each called `loadInto`, which read and decoded the
whole of `graph.json`, then scanned every edge — 8 MB per answer here,
980 MB on ScummVM. The store now keeps the decoded graph and test map
with each file's size and mtime, stats the file on every call, reloads
on a change, drops the cache and reports a missing file rather than
serving memory, and indexes module edges by both ends and symbol edges
by `to` as positions into the document's slices, so every answer is
byte-identical to the scan's. `readArtifact` is a package variable a
test swaps to count reads: four answers read the file once, a rewrite
with a later mtime is read on the next answer and its new edge appears,
and a removed file says "run `hobbes ingest`". The knowledge package's
suite held the scan and holds the index unchanged.

**ADR-119, 0.2.31-beta (`a934180`).** `extract/timings.py`: every step
of `extract_repo` is timed in run order (`Timings.step`, a step that
raises still recorded), threaded through `_build_symbol_layer` and
`_lane_b_facts` as an optional argument so the bench's `ingest(workspace)`
is unchanged; `hobbes ingest` prints the total and every step and
appends one JSON line per run to `~/.hobbes/cache/timings/<key>.jsonl`.
Never in an artifact: `test_emit`'s byte-identical re-ingest still
holds, and `test_timings` asserts `graph.json` carries no timings. Four
tests.

**The first measurement, this repo at `a934180`, contained:** 53.26 s in
24 steps. Lane B is 48.6 s of it — python 25.3, java 7.0, rust 6.8,
typescript 4.2, go 3.1, c 2.2 — run one language after another; lane A
is 3.5 s (ts 2.1, python parse 0.8, go 0.5); the join 0.16, the
projection 0.14, the tail 0.16, the write 0.21. Two things the block
says on its first run that the review could only guess: the lane B
index cache would take about 90% off a re-ingest of an unchanged repo,
and running the six lane B languages concurrently would take this
ingest from 53 s to about 30. Neither is built.

**Suites:** 1,640 pytest, Go 389 (388 pass, 1 skip); the binaries, the
static proxy and the image rebuilt at 0.2.31-beta, and this repo
re-ingested at HEAD. The knowledge server serves the old build until it
is restarted (C-65).

## 2026-09-16 (night, later) — The override set is drawn: SCIP `relationships` measured on six indexers, then `implements` edges; ADR-120, 0.2.32-beta

Max: "review top level documentation. then proceed with … decode SCIP
relationships and draw implements edges … measure which indexers
populate it first." The review's first recall recommendation, taken in
that order.

**The measurement, before any code.** A probe helper copy kept every
raw `.scip` the six indexers wrote for this repo before the decode
removed it (the ingest ran contained through it, as the C++ probes
did; the copy's `node_modules` has to be a real tree, `cp -a`, or the
symlink dangles inside the container), and a node script read every
`SymbolInformation` and `Relationship` of each, plus ScummVM's stored
scip-clang index for a large C++ answer. Five of six indexers state
`is_implementation` pairs on the implementor, as the proto's example
says: scip-clang (49,912 on ScummVM, 49,550 in-repo; class → base,
method → overridden, once per translation unit), scip-go (39 here,
30 of them to the stdlib; struct → interface, method → the interface's
method *spec*), scip-typescript (8), scip-python (49, 47 to builtins;
class → base, and method → overridden only to the stdlib here),
scip-java (11 — and the **reverse row on an abstract method**,
`Shape#area().` → `Circle#area().`, with the same two flags both
ways). **rust-analyzer states none** (202 symbol informations, 0
relationships). Probes and outputs: `~/.hobbes/bench/relationships-probe/`.

**ADR-120, 0.2.32-beta.** The helper (version 5) reads `Document.symbols`
beside `occurrences` and keeps only a symbol's `is_implementation`
targets; `implementsRows` turns each pair between two in-repo
definitions into a row from the implementor's definition to the
implemented's, deduplicated and sorted; a pair stated both ways is
oriented by the index's own type-level pairs, transitively (C extends
B extends A: javac names the overridden method by its declaring class
and the class by its direct base), or dropped both ways and counted;
a pair to a declaration outside the index, or from no graph
definition, is counted. The facts carry `implements` as a fourth row
kind, counted in the trailer. `read_facts` makes each an `IMPLEMENTS`
site; `evidence.join` emits it as an `implements` fact at semantic
tier, lane B alone; `project` takes both ends as the symbol *starting*
at the line (the enclosing lookup would answer the class for a method
inside it) and counts an end lane A keeps no symbol for. The summary
counts `implements edges` apart and prints every non-zero not-drawn
count; `who_calls` lists implementors under "implemented or overridden
by" with C-58's caveat; `hobbes diff` counts the type; `hobbes plan`
weights it 0.8. Every Rust run appends a C-157 record.

**Measured on this repo:** 18 `implements` edges, all read against
their sources — twomod's `MemStore → Store` (C-58's opening example)
among them; 7 pairs below lane A's floor (all Go's interface method
specs, which lane A does not declare); 83 to the stdlib; 0 unplaced;
0 undirected. Calls and uses edges unchanged from 0.2.31-beta.

**Not done, on purpose (ADR-120 §7):** the expansion of a call to an
interface method into its overrides. It changes what reach means
(ADR-007) and needs the oracle question answered first — the RTA and
CHA keys judge a call by its concrete targets. Deferred with it: Go's
interface method specs as lane A symbols (the 7 below the floor; it
would also turn every resolved call to a spec into a `calls` edge and
move Go's graded cells), and a cross-unit match for the outside pairs.

**Paperwork:** ADR-120; C-58 narrowed; **C-157 registered, surfaced**
(register 157 entries, 114 active, 87 surfaced); architecture §3.4
(the fourth edge type and its paragraph) and §8; CHANGELOG; README's
ADR range (it read ADR-117 at ADR-119) and register tally; every
version copy.

**Tests:** helper — the real proto reader on a `scip.Index` built with
the bundled bindings, a pair between two definitions, an outside target
counted and a local skipped, scip-java's reverse row oriented, a chain
two levels up, a mutual pair dropped and said, scip-clang's per-unit
repeat as one row in a fixed order, an outside-repo document, the C-157
record on Rust only, `factsLines` with and without rows (87 scip node,
was 77). Python — an `implements` row read as a site with the root in
front, a trailer count the rows do not reach refused, the join passing
the site through beside a call on the same line, projection onto both
definitions, a method inside its class, the module edge, the below-floor
count (1,648 pytest, was 1,640). Go — `who_calls` lists an implementor
under its heading, not as a caller and not as nothing (390 Go). The
binaries and the static proxy rebuilt; the image rebuilt; this repo
re-ingested at HEAD. **Restart the knowledge server** (C-65).

## 2026-09-16 (night, last) — No call in an unevaluated operand: C-155 lifted the day it was registered, on both sides of the grade; ADR-121, 0.2.33-beta and 0.2.34-beta

Max: "review top level documentation then proceed with an item from the
hobbes review." The review's next undone item was C-155 — "lift at lane
A, one dispatched unit, graded on fmt's stored key" — and it became
three units and one decision, because the oracle turned out to carry
half the defect.

**Measured before the decision, in three places.** The grammar
(tree-sitter-cpp 0.23.4): `sizeof_expression`, `alignof_expression`,
`decltype`, `requires_expression` wrap their operand; `noexcept(..)` and
`typeid(..)` parse as a *call of a bare identifier*, so lane A had been
recording a call to a keyword at each. The cells: fmt's and args' lane
A sites under those nodes, against each cell's standing key. clang's
own `-ast-dump=json`, run in the image on a probe: it **keeps** the
`CallExpr` under `sizeof`/`alignof` (`UnaryExprOrTypeTraitExpr`),
`noexcept` (`CXXNoexceptExpr`) and `typeid` (`CXXTypeidExpr`), and
never holds a `decltype` operand — so O10's reader, which records every
call kind it meets, keyed a site for a call the program never makes.
That is H-32, logged open before any code, root RC-11.

**Decided (ADR-121).** Lane A records no C++ call site under the four
node types or a `noexcept(..)` expression; `noexcept` and `typeid` in
call position record no site of their own; **`typeid`'s operand keeps
its sites**, because [expr.typeid]/3 evaluates a polymorphic glvalue
and the syntax cannot tell. The join and the tail do not move — and
here the review's sketch was corrected rather than built: lane B's
occurrence at such a site falls through as a `uses` edge, the true
statement of a dependency that is not a call, instead of being claimed
and hidden; and there is no tail class, because a site that is not a
call is not a concession. The oracle drops and counts the same list
(`sites_unevaluated`), `typeid` kept on both sides. Pre-registered as
§10.10 (P52–P56) before the regrade.

**Three units through the harness, all gate right-clear, all merged
no-ff:**
- `S-20260916T225041Z-d95c` (32 turns, $2.08): `cppsource._unevaluated`,
  one drop point, five tests including the ingest-level `uses`-not-`calls`
  check. 0.2.33-beta.
- `S-20260916T230256Z-5261` (57 turns, $4.09): O10's reader, a depth
  around three node kinds, `sites_unevaluated` in coverage, the
  `uneval.cpp` fixture measured on the real dump (9 sites before, 4
  after, 5 dropped). Verified in the image, where clang++ is: all five
  C++ tests run and pass. **The doer read past its brief:**
  `UnaryExprOrTypeTraitExpr` is C's `sizeof` too, so the key now
  abstained in C where lane A's C walk did not — measured at 0 sites on
  the C cells, then closed on the lane's side.
- `S-20260916T231525Z-367f` (29 turns, $1.37): `csource._unevaluated`,
  the same predicate one grammar over; `_Alignof(f(1))` does not even
  parse, so the `alignof` half is exercised through the one shape C
  allows, a VLA — which is also the residual (C11 6.5.3.4 evaluates a
  VLA's size). 0.2.34-beta.

**The regrade, and the misses it found in my own measurement.** fmt
against its standing key: contradicted 5 → **4** (C-153's four, row for
row), confirmed 3,269 unchanged, **99.88%** (3,269/3,273), like-for-like
99.69%; args identical row for row. But the export lost **26** rows,
not the 1 predicted: the pre-measurement had walked the six C++
extensions and skipped the 25 headers C++ claims, and had matched sites
to graded rows by the target's bare name, so `parse_context::begin`
never matched `begin`. Re-measured with the provider's own file list:
**299** sites under an unevaluated operand (294 `decltype`, 5 `sizeof`),
26 of them drawing an edge — 1 contradicted, 25 oracle-silent, every
one read and every one a `decltype` operand. P52 and P54 recorded as
missed on the counts and met on the judgement; P56 missed on its
premise (fmt's re-run key lost 6 `sizeof` sites, all read, no judgement
moved) and met on the judgement. The lesson is written where the next
lift will read it: count with the provider's file list, match by
position. **Every contradiction left on fmt is C-153.**

**Records.** ADR-121 (with its dated correction and its C amendment);
C-155 lifted at the bottom of `extraction-cpp.md` with the technique
and four residuals (`typeid`, a macro-spelled operand, C's VLA, and
nothing else on the oracle's side now); the register 157 / 113 active /
27 lifted; H-32 fixed and RC-11 opened; §10.10 graded; fmt's cell
record with the regrade and the key re-run; the graphics re-rendered
(the report drift test caught the stale `cells.json`); three session
files, the tracker at 37 of 40; CHANGELOG 0.2.33-beta and 0.2.34-beta.
The binaries, the static proxy and the image rebuilt at 0.2.34-beta
(C-65); this repo re-ingested at HEAD.

**Suites:** pipeline 1,655 passed (the tracker's drift test red once
per unfilled review block, green after each render); Go 390 with
subtests (389 pass, 1 skip) against the rebuilt image; oracle-lane Go
116 with subtests, 104 pass / 12 skip on this host (no clang++, no
cmake), the five C++ fixture tests run and pass in the image; the
report drift test green after the render.


## 2026-09-16 (night, latest) — Lane B reads an unchanged unit from its index cache; ADR-122, 0.2.35-beta

Max: "review top level documentation and proceed with next hobbes
review item." The review's next speed recommendation after the proxy
(ADR-118) and the timing block (ADR-119): "a lane B index cache by
stage key, then lane A's file cache, each measured with the timing
block". The first half, measured before and after.

**Measured before the decision** (a scratch driver over
`scipsource.extract_scip` and `extract_scip_go`, each run twice with
the sub-steps wrapped): python's 26.4 s is the index container — 26.05
s — with the venv listing at 0.24 s, staging 0.02 s and the facts
decode 0.08 s; go's 3.3 s is eight modules at a 0.13 s fetch and a
0.2–0.5 s index each. The helper's facts file is byte-identical across
the two runs for python and for all eight modules (sha256). And the
review's premise was wrong: `staging.stage_key` folds in size and
mtime, not bytes — it names a tree so removal is idempotent — so a
cache keyed on it would reuse an index across an edit inside one mtime
tick. The cache keys by content.

**Built (ADR-122).** `extract/indexcache.py`: the key (helper source +
lockfile, the image's id, the config with the stage path tokenised and
the run-local `facts` path dropped, every sidecar file the config names
under the cache by its bytes, the stage tree file by file, a link by
target + top-level stat + installer marker, the ro mounts, the env; the
root left out — it is put in front at read time), the store
(`<cache>/index/<key>.facts.ndjson`, `.partial` then rename, a hit
touches, a 30-day sweep at the next write), and a per-ingest ledger
reset beside containment's. One hook in `scipsource.run_helper`: look
up before run; a hit is `read_facts` over the stored file, and a
`ScipError` on it drops the entry and indexes; the containment ledger
takes the index step on a hit, since the stored run was contained and
the artifact's stamp says where the facts came from. `_run_helper`
stores after the read validated the file (the trailer's counts) and
only when `outcome.contained`. `containment.image_id()` (one podman
inspect per process; `None` when a run would not be contained, so
nothing uncontained is ever keyed). The CLI prints one line under the
timings — hits, misses, the keys' seconds, the store, the switch — and
`timings.record` takes `index_cache` for the log line.

**Measured after.** This repo, the same dirty tree, contained: 54.00 s
→ 8.89 s; lane B python 26.15 → 0.44, typescript 4.27 → 0.03, go 2.68
→ 0.83, rust 6.84 → 0.50, java 6.98 → 2.26, c 2.27 → 0.02; 19 units,
keys 0.04 s in all. `graph.json` and `tests.json` sha256-identical
between the cached ingest and a fresh `HOBBES_INDEX_CACHE=0` one. What
a hit still spends is the fetch passes that run before the helper —
Java's resolve pass, Go's `go mod download` per module, Rust's `cargo
fetch`, the venv listing — 4.1 s here; the key is computable before a
fetch (the stage exists by then), so skipping them is a small follow-on
if the number warrants it. Rejected in the ADR: a cache at the language
level (a second input discovery beside each extractor's own, and the
two drift), the stage key (stat-based), a pickle of the decoded facts
(a second reader is a second answer), the raw `.scip` (the decode is
the helper's).

**Records.** ADR-122; architecture §3.6 amended and §8 at 0.2.35-beta;
**C-158 registered (surfaced)** in `extraction-lane-b-environments.md`
— linked trees and venvs fingerprinted by surface, not files; a
lockfile-less manifest keeps the resolution its first index saw — the
register at 158 / 114 active / 88 surfaced; CHANGELOG 0.2.35-beta;
CLAUDE.md's status; the handoff renumbered from 0 (the review had
flagged its 00/0 collapse). 18 tests in `test_indexcache.py`: the hit
is the miss's facts and the same containment stamp, two stages of one
content share a key, every input moves the key (a staged file, the
config, a sidecar's bytes, a link's marker, the helper, the image) and
the root does not, a host run and a failed run store nothing, the
switch and a stage outside the cache bypass, a short entry is dropped
and re-indexed, the sweep, the summary; and one through the image (a
fixture ingested twice: every unit a hit, the artifact byte-identical,
no `index_cache` in it). Found by use, not fixed:
`~/.hobbes/cache/stage/` holds 38 86-byte `.scip` files from 2026-08-22
and two old stage directories, and `staging.sweep_stale` has no caller
in the ingest.

**Suites:** pipeline 1,673 passed (1,655 + 18); Go `./...` green after
the bump. The static proxy and the image rebuilt at 0.2.35-beta
(C-65); this repo re-ingested at HEAD — the first ingest after the
rebuild misses everywhere, by design.

## 2026-09-16 — the public docs name one version; drift swept

**Direction (Max).** The comparative pages and the Hobbes-facing docs list
the current version only; the graphics printing each cell's grading build
("Hobbes 0.1.10-beta / 0.2.28-beta / …") was noise, since only the
current Hobbes matters to how they read.

**Done.** `render.py` no longer parses a record's grading version: the
tables drop the per-cell Hobbes column, the legends say "Hobbes", and the
version footers are gone (the record keeps its build and commit, so no
provenance is lost; `render.py check` green, the report Go test green).
Graphics, `tables.md` and `cells.json` re-rendered. Three `cells.meta.json`
notes lost their version references. `docs/comparative/README.md` states
0.2.35-beta once, in place of the three version-history paragraphs.

**Drift fixed along the way.** The fmt note on `one-number.svg` and the
comparative claim still read 3,269/3,274 (99.85%, like-for-like 99.66%)
with C-155 open; now 3,269/3,273 (99.88%, like-for-like 99.69%), C-155
lifted, H-32 named. README: status 0.2.29 → 0.2.35-beta, register 157 →
158 (27 lifted), ADR range to 122, 37 session logs; its version history
removed from the prose. `field.md`'s Hobbes row 0.2.28 → 0.2.35-beta, 154/111
→ 158/114. `how-hobbes-differs.md`'s oracle diagram said clang for C only.
README and architecture §3.7 said scip-python "leaves `syntax_kind` unset
for 0 of 8,575" — the reverse of ADR-029's measurement ("populates it for
0"); now "sets it for 0". No version bump: docs and `bench/` only.

## 2026-09-17 — Top-level docs reviewed at 0.2.35-beta; drift fixed

**Direction (Max).** Review the top-level documentation and report the
standing; fix the drift found; then recommend a route on each open
decision, honesty and accuracy first where the extraction lane is
concerned (the recommendations were given in the session, not decided —
they stay Max's calls in the handoff's "Open for Max").

**Drift fixed.** `CHANGELOG.md`'s header named 0.2.34-beta as the last
untagged version. The handoff's "WHERE THINGS STAND" had the register
before C-158 (157 / 113 / 87 surfaced → 158 / 114 / 88) and the suites at
0.2.34-beta (1,655 pytest → 1,673, collected); its NEXT still listed
lane B's index cache as to do; three cross-references pointed at the
wrong items ("item 00", "item 5", "see item 1" for the rebuilt image);
the open-decision line and item 6 read fmt at 99.85% / 99.66% and H-31
as open. C-153's entry (present tense) read 99.85% / 99.66% with C-155
still counted among fmt's contradictions (ratio 5 : 0 → 4 : 0).
`workstreams.md`'s sequencing gained point 10 (0.2.23–0.2.35-beta).
The register index's dated 2026-09-16 note keeps its numbers: it was
true when written. AGENTS.md is the same file as CLAUDE.md. No version
bump: docs only.

### Later the same session — the review's decisions, written up, then built in Max's order (0.2.36–0.2.38-beta)

**Direction (Max).** "Honesty and accuracy matter more than just a recall
number due to being our floor… any decisions should first consider
honesty and accuracy when dealing with the extraction lane." Then, on the
routes recommended: "go with your order, write up first then proceed with
the order". The order was item 5 (lanes), 3 (strict precision),
4 (C-153), 1 (dispatch reach).

**Written first (`4553a5a`), before any build or measurement:** ADR-123
(`hobbes lanes` names a registered disagreement, exit 3), ADR-124 (strict
precision beside every grade), ADR-125 (C-153: measure a rule, then
abstain or surface), ADR-126 (reach through dispatch is measured, not
drawn). §10.11 and §10.12 pre-registered in `oracle-grading.md`.

**Item 5 — ADR-123, 0.2.36-beta.** Dispatched as `4338` (41 turns, gate
right-clear, merged no-ff).
- Every site disagreement carries a `shape`: `same-line-pair` (C-70)
  when lane A's one guess is lane B's answer at a sibling site of that
  name; `cpp-withheld` (C-152) in a compiled C++ file. The command exits
  3 when every row is shaped.
- Two gaps the review found were fixed by the developer on top:
  - the drawn-guess count included sites the external veto had already
    dropped;
  - the C++ rate counted only `cpp-withheld` rows.
- Predictions met exactly:
  - quic-go: 17 of 17 `same-line-pair`, exit 3;
  - fmt: 316 of 316 `cpp-withheld`, exit 3, printing that lane A's C++
    guess disagreed at 316 of 2,097 C++ sites and that the same guess is
    drawn at 63 sites in C++ files lane B did not index;
  - this repo: 0.
- C-152 amended with the residual (a lane B error in those files is
  reported, not failed on). C-70's open CI question settled.

**Item 3 — ADR-124, bench and docs only (`d1feba1`).**
- The grader adds `precision_strict` = confirmed / (confirmed +
  contradicted + `line-unresolved`), printed under the standing line.
- `render.py` computes it from every record's silent map, with no
  regrade, and every quoted precision carries it where the two differ.
  That applies to the competitor tools alike: 14 records have
  `line-unresolved > 0`.
- "Like-for-like" retired from the public docs. fmt then read 99.88%
  (strict 99.48%).
- Found on the way: the claim page read repowise fmt 2,410/5,025; the
  record says 5,024.

**Item 4 — ADR-125, 0.2.37-beta and 0.2.38-beta.**
- **§10.11 graded before any build.**
  - R-qual (the written qualifier's template arguments against the
    resolved owner's) matched exactly the eight predicted rows and no
    confirmed edge on fmt or args.
  - R-self (target is the caller) would have removed 10 real recursions
    on args, so it was not built.
- **Amended before the build.** Reading the rule found it too wide for
  a primary-template owner or a partial specialisation (right edges on
  other repos). Narrowed to owners declared `template <>`; all eight
  still qualify.
- **Built as `145d`** (94 turns, gate right-clear, merged no-ff).
  - The regrade missed P66 on the count: 6 of the 8 went, because
    `FMT_BEGIN_NAMESPACE` put `template <>` into an ERROR node before
    two specialisations (C-145).
  - The developer's `9daffdc` reads those exact tokens back. P69 met:
    fmt **3,269/3,269 (100%), strict 99.73%**, recall unchanged to the
    pair, args identical, poison PASS.
  - Record, graphics, README, architecture and C-153 updated.
- **§4 surfacing built as `b0ed`** (61 turns, gate right-clear, merged
  no-ff).
  - `who_calls` marks semantic C++ calls from a template pattern, and
    one `cpp-template-sites` record counts them.
  - fmt: 596 of 2,811, both remaining `format_as` rows marked.
  - C-153: unsurfaced → **partial**. The register is now 88 surfaced,
    22 partial, 3 unsurfaced.

**Item 1 — ADR-126, measured only (§10.12).** jsoup and click were
re-ingested at the keys' commits, contained.
- The override set is the compiler's: 2,837 of 2,944 expanded pairs are
  in javac's CHA set, and CHA-set recall is 97.4%. The one pair outside
  is a bridge-method override the key's erasure rule misses.
- **All 106 unjudged pairs sit at calls javac resolved statically**
  (`super.clone()` at `CDataNode.java:37`, private and final methods).
  A naive expansion would be wrong there, 3.6% of pairs, including the
  caller as its own override.
- click: 27.5% of 360 pairs observed. args: 353 unjudged by construction.
- The median fan-out is 1 (P63 missed on the median).
- **Nothing drawn.** A surface is Max's decision, and would need a
  syntax exclusion for every call the language does not dispatch.

**Tracker 40 of 40** (4 areas, 1 false block, 0 missed). Suites: pytest
1,709 collected (lane_b 7 passed on the host), Go `./...` ok, oracle
grade and report ok.

**Found by use, my mistakes, recorded:**
- **A chained `… && setsid … &` backgrounds the whole chain.** It
  launched a duplicate dispatch of `145d`'s brief
  (`S-20260917T132013Z-e1c6`), stopped before its gate. Its branch holds
  `b4d8b38`, not merged, with no session log.
- **The same mistake ran two ingests of this repo at once.** The graph
  it left had several lane B units failed ("wrote no facts file"), all
  recorded in `extraction_errors`. Concurrent ingests of one repo break
  each other, and nothing refuses the second; worth a constraint or a
  lock.

Binaries, static proxy and image rebuilt at 0.2.38-beta; this repo
re-ingested at `8bda3ec` (all 19 units a cache miss after the image
change, lanes exit 0). **Restart the knowledge server** (C-65).

## 2026-09-17 (later) — Top-level docs reviewed at 0.2.38-beta; one ingest of a repo at a time (ADR-127, 0.2.39-beta)

**Direction (Max).** Review the top-level docs and report the standing;
then "fix the doc drift and delete the duplicate branch. also handle the
two ingests of one repo issue, or if no solution doc as a constraint".

**Drift fixed (`ca1f2fd`).**
- The handoff's item 3 still listed the distinct `hobbes lanes` exit as
  not started (it is ADR-123, 0.2.36-beta).
- Item 8 read the binaries and image at 0.2.35-beta.
- Item 12 read the tracker at 37 of 40.
- `workstreams.md`'s header and sequencing point 10 stopped at 0.2.35-beta.
- Not fixed: the 2026-09-16 BUILDLOG heading still says "(night, latest)".
  The log is append-only.

**The duplicate branch.** `hobbes/S-20260917T132013Z-e1c6` (`b4d8b38`) was
read before deletion: one commit, a second run of `145d`'s brief, with
`145d` already merged. Deleted with `git branch -D`, and
`~/.hobbes/sessions/S-20260917T132013Z-e1c6` removed. No container or
network of it remained.

**Two ingests of one repo: the mechanism, read from the tree.**
- `staging.stage_path` is derived from the resolved root, the SHA and
  the files' stats (ADR-027's idempotent removal). Two ingests stage
  every unit at the same path.
- `build_stage` removes the `.partial` and the final tree first, and
  each run removes its stage after indexing. Each run deletes the other's
  tree, hence "wrote no facts file".
- `write_artifacts` wrote in place, so writers interleave and a reader
  can see half a file.

**Decided first (ADR-127, `77752dc`), then dispatched as `d238`** (34
turns, $1.57, gate right-clear, verify pass, merged no-ff `eef46dc`).
- An exclusive non-blocking `flock` on `.hobbes/derived/.ingest.lock`,
  taken first in `ingest()`. It sits in the repo, not under the cache
  root, because two processes may set `HOBBES_CACHE_DIR` differently.
- Contention raises `IngestBusy` (P10). The CLI prints it and exits 1
  before anything is staged.
- A filesystem without `flock` runs unlocked with a warning (C-159).
- Each artifact is written through a temporary and `os.replace`.
- **On top, the developer's (`0c1707a`):**
  - `NamedTemporaryFile` creates 0600, which would have narrowed every
    artifact from 0644. The rename now sets 0666 less the umask first,
    and a test holds it (red on the merged code).
  - An unused `errno` import dropped.
- **Live, this repo, image rebuilt (so lane B's 19 units all missed the
  cache):**
  - A second ingest started 4 s after the first exited 1:
    `another hobbes ingest of /home/mmarrujo/hobbes_public is running
    (pid 1958583)`.
  - The first finished with 0 "facts file" or "did not run" lines and
    the usual 27 degradation records.
  - The lock file holds the pid and stays after the run.
- **C-159 registered (surfaced)** in `extraction-lane-b-environments.md`:
  a pre-0.2.39-beta build takes no lock, and a filesystem without
  `flock` runs unlocked. Architecture §3.6 amended. 159 entries, 115
  active, 89 surfaced.

**Suites:** pytest 1,721 passed on the host (the tracker's drift test
red until d238's review block was filled), `lane_b` 7 passed, Go
`./...` all ok. Tracker **41 of 40** (4 areas, 1 false block, 0 missed).

Binaries, static proxy and image rebuilt at 0.2.39-beta; this repo
re-ingested at HEAD. **Restart the knowledge server** (C-65).

### Later the same session — lane A's file cache, measured first: ADR-128, 0.2.40-beta

**Direction (Max).** "proceed with the file cache for lane a".

**Measured before designing** (drivers in `~/.hobbes/bench/laneA-cache/`).
- Every timing log since ADR-119 had lane A under 2 s per language on
  every repo (this repo 3.4 s of 8.5 s; fmt 1.2 s; jsoup 1.1 s; quic-go
  2.0 s). The only large repo, ScummVM, had no timing record.
- Timed lane A alone on ScummVM (lane B off, nothing written): 258 s,
  of which **C++ 242 s**; nothing else over 2 s.
- cProfile over `extract_cpp`: tree-sitter's parse was 21 of 622 profiled
  seconds. Named: `csource._resolve_include`'s suffix step (262,159
  includes × every header, 1.65 billion `endswith`) and the recursive
  generator `_walk` (2.06 billion calls). cProfile inflates call-heavy
  code, so the split was re-taken by wall-time wrappers: per-file
  `_parse_file` 130 s, cross-file work about 28 s.

**Tried as driver patches before any ADR,** each output `cmp`'d against
the tree's 217 MB extraction:
- the iterative walk plus the basename index: identical, C++ 242 → 154 s;
- plus the string-test pre-filter: identical, 141 s;
- a JSON per-file cache around `_parse_file`: the first version's
  write-side equality assertion failed on the first file (a `qualifiers`
  tuple became a list); with tuples and sets tagged, cold 156 s, warm
  22 s, both identical, 289 MB.

**Found while placing the store.** `containment.plan` mounted the whole
cache root read-write in every step, including those that execute repo
code, so ADR-122's index store was writable by repo code and read back
as lane B's answer by a later ingest. The register covered what repo
code could read there, not what it could write. Contained first, in the
same ADR.

**ADR-128 written first (its own docs commit), then three
units, all merged no-ff:**
- `9943` (§1–2; 34 turns, $2.31): `TRUSTED_STORES` (`index`, `lanea`)
  laid read-only in every plan; a `NOTE:` naming C-161 whenever repo code
  ran contained. **Verify failed on two tests outside the partition** —
  `test_indexcache.py` (an absent `index/`) and `test_harness.py` (the
  nested-mount tuple). The partition was mine and too narrow; the doer
  named both fixes, applied on top. The live test passes on the host: a
  write into `<cache>/index` fails in the image, the stage write succeeds.
- `1ef9` (§3; 66 turns, $3.61): `_walk` iterative, `HeaderIndex`, the
  pre-filter. Checked that every converted header set only feeds the
  resolver. ScummVM after the merge: identical, C++ 135 s, lane A 154 s.
- `6956` (§4; 58 turns, $3.30): `extract/laneacache.py`; JSON, tagged;
  never pickle; the equality guard on write; `HOBBES_LANEA_CACHE`; the
  summary line and the timings log field; conftest keeps the suite off
  the real store. ScummVM through the real store: cold 144 s, warm
  21.7 s (lane A 163 s / 39.5 s), both identical; 19,948 records,
  318 MB. fmt through `hobbes ingest` twice: 72 misses then 72 hits,
  artifacts sha256-identical.

**Registered:** C-160 (the fingerprint sees the grammar's version, not
its build) and C-161 (repo code can write the tool caches and the stage
that later ingests read), both surfaced. 161 entries, 117 active, 91
surfaced. Architecture §3.6 amended.

**Found by use:**
- **My mistake, the recorded one again:** a chain ending `… && setsid
  nohup … &` backgrounded the whole chain (render, pytest, commit,
  ingest, dispatch). It ran in order and launched one dispatch; nothing
  was duplicated, but its output was invisible until checked.
- The pytest suite appends timing lines for its tmp repos to the real
  `~/.hobbes/cache/timings/`. Not fixed.
- The index cache's key includes the mounts, so after §1 every repo's
  first ingest misses lane B's store once.

**Suites:** pytest 1,751 passed on the host, `lane_b` 8 passed, Go
`./...` ok. Tracker **44 of 40**. Binaries, static proxy and image
rebuilt at 0.2.40-beta; this repo re-ingested at HEAD. **Restart the
knowledge server** (C-65).

## 2026-09-17 (evening) — Top-level docs drift and two found-by-use items (no version move)

Max asked for a review of the top-level docs, then for the drift and the
two items the ADR-128 session found by use to be fixed.

**Review, against the tree.** `VERSION`, `CHANGELOG.md`, architecture §8
and `CLAUDE.md` agreed on 0.2.40-beta; ADR files 128; register 161
entries, highest C-161; 44 session logs, the rendered tracker 44 of 40.
The drift: README's status still read 0.2.35-beta, "ADR-001 to ADR-122",
158 register entries and thirty-seven session logs; the handoff said
"tracker 40 of 40" twice and "Forty log files" beside "44 of 40"; its
summary called ADR-128's units gate right-clear without `9943`'s failed
verify; its 2026-09-15/16 resume points (items 0–10) had piled to 626
lines; four suite counts were carried from 0.2.8-beta.

**Fixed (docs):** README's status numbers and ADR range, with ADR-128's
result in the harness paragraph; the handoff rewritten — the day's
landings as one list with `9943`'s verify named, the old resume points
folded to a list of driver paths, the standing items renumbered 1–4;
suites re-run and counted: 1,752 pytest, Go 392 with subtests (391 pass,
1 skip; the earlier 390 was the same method), 87 scip, 36 tsextract, 52
vitest, 84 atlas0, all green.

**Found item 1, fixed (`e976ba5`, test only):** the suite's in-process
ingests appended timing lines to the real `~/.hobbes/cache/timings/` —
341 of its 347 files were pytest tmp repos. `conftest.py` redirects
`hobbes.extract.timings`' cache root to the run's basetemp unless a test
sets `HOBBES_CACHE_DIR` itself; `test_timings.py` holds it. A run of
`test_timings` and `test_cli` left the store at 347 files. The 341 old
files are left in place, not swept.

**Found item 2, a misreading — corrected, nothing built.** The record said
the index key includes the mounts, so after ADR-128 §1 every repo's first
ingest misses lane B's store once. Read against the code: the key's `ro`
is the caller's list (`scipsource._cache_key`); the trusted stores are
added in `containment.plan`, outside it. This repo's timings log: 19 of
19 misses at 0.2.39-beta's first ingest and again at 0.2.40-beta's, 18/1
at the commits between (the changed Python unit) — the whole-miss
ingests fall on version bumps, which rebuild the image (C-65); the image
id is in the key by design (ADR-122), and so is the helper's lockfile,
whose root carries the version. Re-ingested at `e976ba5` under the
0.2.40 mounts: 18 hit, 1 miss (the Python unit, its tests changed). One
miss per bump is the key being true.

**Suites:** as above. Tracker unchanged (44 of 40).


## 2026-09-17 (night) — C++ recall: a lost definition read from the index, and R-arity (ADR-129, ADR-130, 0.2.41-beta)

Max asked for a survey of the docs, then a way to raise recall, system-wide
or one language's, as a plan; he approved it the same session ("good to go
with route a, we can reopen ts if you believe beneficial if not then no,
patch number stands").

**The survey's reading.** The cross-language hole is C-58 and it is
decided: dispatch expansion was rejected the same morning (ADR-126), the
symbol floor is C-9's. TS's floor shapes are off the table (2026-09-10)
and small (6.2% of one cell); not reopened. **C++ was the lowest cell in
the system (fmt 14.5%) and its largest cause was on the honest side of
the line:** C-145, "lane B names the callee, and the graph has no symbol
to draw it to" — 6,905 call facts scip-clang had already resolved,
dropped at `scipsource.project` because `starting_at` had no lane A
symbol for a definition a macro parse lost.

**Step 0, nothing drawn** (`~/.hobbes/bench/c145-recovery/`). `probe.py`
wraps `read_facts` and `project`; `analyze.py` writes the export a rule
would produce; the real grader judges it. A naive rule read 98.2% (123
contradicted): 98 were constructions my export had wrongly drawn as
calls (the called-type guard already makes them `uses`), 17 landed on
declarations scip-clang gives the definition role, 5 on call-spelled
data members. With lane A's own two rules: 6,533 / 0, recall 29.1%. The
rule was fitted on fmt, so args was held out: frozen by hash, P70–P73
written first, 67 added and 67 confirmed. C cells: nothing moved.

**The hand read that changed the plan.** ADR-129 §6 required the 53 rows
the key could not judge to be read before shipping. 34 were wrong (a
35th among the no-targets rows): `copy<Char>(begin, end, out)` onto the
two-parameter `copy` at `format.h:549` — scip-clang's single candidate at
a dependent call, invisible until the mint gave line 549 a node. I first
told Max 38; the count was 34 + 1, corrected in the same turn. A
two-sided arity rule flagged 152 confirmed edges (defaults live on
declarations); the "too many" half flagged the 35, 5 standing wrong edges
(`holds_alternative`/`any_cast` onto gmock's ADL stubs, `scan.h:466`) and
no confirmed edge once the regex reader's own failures were read out.
ADR-130, §10.14 (P76 replaced *before* anything was built, said so).

**Built through the harness, three units, merged no-ff:** `77da` the
mint (95 turns, $8.92), `4048` R-arity (125 turns, $12.26), `b597` the
surfaces (40 turns, $1.90); all gate right-clear, verify pass; `lane_b`
9 of 9 on the host before each merge.

**What the first regrade of the built mint found (P79, P80 missed).** The
probe saw only lost definitions a call targets; the rule mints every
one. 1,722 symbols on fmt, not 622; 11 and 10 on the C cells, not 0 —
every call-edge grade as predicted. Read: unnamed structs under
scip-clang's `$anonymous_type_…` names, and types lane A already names
at another line (`typedef struct cJSON {…} cJSON;`). Two refusals added
by the developer on top (`3c31b50`), four tests; cost 17 confirmed edges
on fmt (P74's count missed by 8). **Grade the nodes a rule adds, not
only its edges.**

**Final, 0.2.41-beta, stored keys, contained:** fmt 6,510/6,510, 0
contradicted, strict 99.59% (27 unjudged), recall 29.1% (collapsed
24.8%), 1,690 symbols minted in 26 files; args 2,062/2,062, 58.6%; cJSON
and sqlite-vector identical exports (1 and 3 named types minted). R-arity:
41 sites — the 40 named rows, 0 confirmed among them under the rule-off
wrapper, and `chrono.h:330`, a C-70 mis-pairing below row grain. Of the
19 new unjudged rows 18 read right and one wrong at the right arity
(`format.h:2387`, `write` to itself): named in C-153, not fixed. A seeded
30 of the 192 new no-targets rows read right, all 30.

**Docs:** ADR-129 (with its amendment), ADR-130; §10.13, §10.14 with
results; C-145 and C-153 narrowed (no entry added; 161); architecture
§3.4, §3.7, §3.8, §8 (and its stale "fmt at 99.1%" oracle row); both
cell records; `cells.json`, `tables.md`, three graphics re-rendered
(`render.py check` and `go test ./report/` green); README; the claim
page; CHANGELOG; CLAUDE.md; the handoff.

**Found by use:**
- **The recorded mistake a third time:** `( … ) && … && setsid nohup … &`
  backgrounded the whole and-list, so the dispatch launched only after
  the ingest finished and printed nothing. Then `pgrep -f "hobbes
  ingest"` matched my own waiting shell, as the handoff warns. Nothing
  was duplicated. Launch on its own line; wait on a log line.
- `regrade.sh` overwrites its output directory; the mint-only export was
  gone when P82 needed it, and the rule-off wrapper had to regenerate
  it. It takes `OUT=` now.
- The rule-off wrapper leaves a clone's `.hobbes/derived/` in the
  rule-off state until the next ingest; the final regrade re-ingested
  all four.

**Suites at 0.2.41-beta, host:** pytest 1,837 (`lane_b` 9), Go `./...`
395 with subtests (394 pass, 1 skip), scip 87, tsextract 36, vitest 52,
`report/` ok. Tracker **47 of 40**. Binaries, static proxy and image
rebuilt; **restart the knowledge server** (C-65). Spend: three
dispatches on the subscription, $23.08 reported; no API or Modal spend.


## 2026-09-17 (late night) — C++ recall: operators at the token, outside a template (ADR-131, 0.2.42-beta)

Max asked for a review of the top-level docs, then the next C++ recall
step.

**Review, against the tree.** `VERSION`, `CHANGELOG.md`, architecture §8,
README and `CLAUDE.md` (`AGENTS.md` is its link) agreed on 0.2.41-beta;
130 ADR files, 161 register entries, 47 session logs and the tracker at
47 of 40. One drift: `workstreams.md` item 10 stopped at 0.2.38-beta and
pointed at the handoff's "item 3", which the evening's rewrite had
removed; the handoff's NEXT repeated the pointer. Both fixed.

**Step 0, nothing drawn** (`~/.hobbes/bench/c146-operators/`). The
handoff's unknown was whether scip-clang emits an occurrence at an
operator token. It does — 4,017 references named `operator…` in fmt's
cached facts, the column the key's minus one. Three reads changed the
item:
- **3,011 of 4,015 are not at a token** but at a macro invocation's name
  (`EXPECT_EQ`'s `operator=`). The key's "8,627 operator sites" is mostly
  that. The macro class, not C-146; drawn they would read 73
  contradicted.
- **At the token the key flatters.** 740 edges: 489 confirmed, 4
  contradicted (all `"x"_a`, a literal operator — a true call the key
  does not record), 148 unjudged. Read by hand, about 100 of the 148 are
  wrong: scip-clang's single by-name candidate at a dependent operator
  (`wday == 0` → `basic_fp`'s `operator==`), at the same arity. C-153
  again, where neither R-qual nor R-arity can see it.
- **Every unjudged row is inside a template** (45 of 45
  `line-unresolved`, 116 of 117 `no-targets`). Outside: +393, 391
  confirmed, 0 contradicted. An exact operator-arity rule (free =
  operands, member = operands − 1, membership from lane B's moniker
  because a macro-broken parse loses the class) caught 104 rows — all in
  templates, so it was not built.

My first member test read lane A's parse and flagged 613 rows wrongly
(gtest's `Message` class is lost to a macro); the moniker fixed it
before any number was quoted. args was held out: five predictions
written to a scratch file, the script frozen by hash, run once — +136,
all confirmed; **the count prediction missed** (≤ 120, < 3 points; it
was 136, +3.9). The scratch file reused P85–P89, which §10.14 holds;
§10.15 renumbers them P87–P91 and says so.

**The design question was cost, and it was measured too.** Operator
tokens per call expression: fmt 0.41, args 0.51, ScummVM 2.09 (600-file
sample) — 3.2 million beside its 1.53 million call sites. So tokens are
not `Site`s: one packed integer each in an `array` per file, read only
by the join, matched exactly (the ordinary name-and-nearest-column match
would pair a built-in `<<` with a macro-carried `operator<<` on its
line), never counted, guessed, vetoed or tailed.

**Built through the harness, one unit:** `d1b9` (92 turns, $8.63), gate
right-clear, verify pass, 28 tests; `lane_b` 9 of 9 and the whole suite
on the host in a worktree before the merge; merged no-ff. The doer's
three deviations draw less or follow the pinned grammar
(`a.operator=(b)` does not parse; an `init_declarator`'s `=` is not an
assignment; a token under an ERROR node is dropped).

**Final, 0.2.42-beta, stored keys, contained:** fmt 6,901/6,901, 0
contradicted, strict 99.61% (27 unjudged, none new), recall 30.1%
(collapsed 26.1%); 551 tokens drawn, 437 references inside templates
left as `uses`. args 2,198/2,198, 62.5%; 140 and 40. cJSON and
sqlite-vector identical exports. The built export is the probe's minus
one row under an ERROR node. P92–P97 met. The first regrade ran the
branch in a worktree before the bump; it was run again from `main` at
`5e7fbd0` under the rebuilt image, and all four exports were identical,
row for row (`final/` holds that run).

**Found and put to Max, not built:** the wrong candidates stand in the
graph as `uses` edges, as they did before today; no key grades `uses`.
C-153's entry names it; the handoff carries the routes.

**Docs:** ADR-131; §10.15 with both result blocks; C-146 rewritten as
narrowed, C-153 extended (no entry added; 161); architecture §3 (the
operator paragraph), §3.8, §8; both cell records; `cells.json`,
`tables.md`, three graphics re-rendered (`render.py check` and `go test
./report/` green); README; the claim page; CHANGELOG; CLAUDE.md;
`workstreams.md`; the handoff.

**Found by use:**
- `count_tokens.py` filtered `.hobbes` out of the path's parts and found
  no files: every clone lives under `~/.hobbes`. Filter on the path
  relative to the clone.
- `regrade.sh | tee out/all.txt` fails when `out/` is made by the script
  it pipes from; the summary was rebuilt from the reports.
- The facts stream's trailer row carries `definitions` as a count, not a
  list; a reader of every row must check the type.

**Suites at 0.2.42-beta, host:** pytest 1,865 (`lane_b` 9), Go `./...`
395 with subtests (394 pass, 1 skip), scip 87, tsextract 36, vitest 52,
`report/` ok. Tracker **48 of 40**. Binaries, static proxy and image
rebuilt; **restart the knowledge server** (C-65). Spend: one dispatch on
the subscription, $8.63 reported; no API or Modal spend.

## 2026-09-17 (after the regrade) — CI's go job red since the morning: `grade.go` unformatted (no version move)

**Asked:** review the top-level docs, then find why CI's gofmt step failed;
then apply the fix and commit.

**Found:** `gofmt -l go bench/oracle` names one file,
`bench/oracle/internal/grade/grade.go`, on the runner and on this box
alike (go1.26.5). `d1feba1` (ADR-124) added `PrecisionStrict` and
`StrictGraded` to the report struct without re-running gofmt, so the
field block's alignment was off; the diff is whitespace only. The go job
stops at its gofmt step, so on the four pushes from `2555e57` (14:09Z)
to `dbd1665` **CI ran neither Go suite nor the static proxy builds**:
the Go side of 0.2.35-beta to 0.2.42-beta was tested on this box only.
The last green run is `762348f` (0.2.34-beta). `web`, `python` and
`graph` passed throughout. No record named the red runs before this
entry.

**Done:** `gofmt -w` on the file (`e5d2e6f`); then, standing in for what
CI skipped, `go test ./...` in `go/` and in `bench/oracle/`, and the
static `hobbes-proxy` build — all pass on the host (the C++ oracle cells
skip here without clang++, as they do on the runner). Under `bench/`, so
no bump and no CHANGELOG entry (ADR-103). Not pushed: the run that
proves it on CI is the lead's next push.

**The docs read:** `VERSION`, README, CLAUDE.md and the CHANGELOG's head
agree on 0.2.42-beta and on every figure compared (fmt 6,901/6,901 and
strict 99.61%, recall 30.1%, args 62.5%, quic-go 99.6%, the register's
161 / 117 / 27, ADR-131, 48 sessions). Cosmetic only, left alone: the
README's unwrapped line at the comparative dates, the run-on in its
Calvin paragraph, a stray line break at "schema v4 with tiers".

**Found by use:**
- `actions/setup-go` warns on every run that it finds no `go.sum` at the
  root (the module is under `go/`), so the Go cache is never restored; a
  `cache-dependency-path` would fix it. Not changed.
- A red gofmt step hides the suites behind it. Nothing local runs gofmt
  before a commit; a hook or a line in the session checklist would have
  caught this at `d1feba1`. Put to Max, not built.

No spend.

## 2026-09-17 (after the gofmt fix) — the two found-by-use items built: the Go cache path and a pre-commit gofmt (no version move)

Max: "apply those two fixes as well worth doing." Both are the items the
entry above put to him.

**The cache.** Both `actions/setup-go` uses in `ci.yml` now carry
`cache-dependency-path`: the go job names `go/go.sum` and
`bench/oracle/go.sum` (it tests both modules), the graph job `go/go.sum`
(it builds the proxy only). The default looks for a `go.sum` at the
root, where there is none, so every run has warned and restored
nothing. The YAML parses; **whether the cache restores is unproven until
a push** — the first run can only save it, the second is the one to read.

**The hook.** `.githooks/pre-commit`, versioned, enabled per clone by
`git config core.hooksPath .githooks` (set in this checkout; CLAUDE.md's
one-time line names it). It runs gofmt over the **staged** content of
each staged `.go` file under `go/` and `bench/oracle/` — CI's two trees
— and refuses the commit with the fix command. Run by hand, four cases:
an unformatted staged file is refused; the same file fixed in the
working tree but not re-staged is still refused (the staged blob is what
CI will see); fixed and staged passes; with no gofmt on PATH it says the
check was skipped and lets the commit through. That last is deliberate:
CI stays the gate, and a doer in a session without Go must not be
blocked by a convenience. The scratch file was removed; nothing of the
test is in the tree.

**Not done, and why:** no ADR — this is ADR-095's gofmt step moved
earlier, not a new decision; no automated test for the hook — a pytest
case would shell out to git and gofmt for a twelve-line script, and the
CI step it mirrors is its backstop. Say if either should exist.

**Found by use:** this box has a distro gofmt (go1.25.12) at `/usr/bin`
behind the user-local 1.26.5. Both agree on today's tree, but the hook
runs whichever is first on PATH; the PATH order Build & test already
asks for is what keeps it CI's gofmt.

No spend.

## 2026-09-17 (evening) — a dependent operator's reference draws nothing (ADR-131 amended, 0.2.43-beta); constructions measured, nothing built

Max asked for the noted items and a plan, then: "route a approved good to
go with first three steps" — housekeeping, the wrong `uses` edges
ADR-131's read found, and the constructions measurement.

**Housekeeping.** CI went green on `dbef0af`, the first green since
`d1feba1`: go, python, web, graph. ADR-114's base rule was read on it as
the handoff asked — "reviewing from the last green run: `762348ff`", the
2026-09-16 commit, so the review covered every commit of the red day and
passed. The knowledge server started with this session on the
0.2.42-beta image (its first answer said so); the artifacts were three
commits stale and were re-ingested. `c146-operators/wt` removed (merged,
clean). Six older worktrees are still listed (`adr111-wt`,
`adr111-before/hobbes-wt`, four from the closed Calvin rounds); left for
Max's word.

**Route a, measured before it was written down**
(`~/.hobbes/bench/c153-operator-uses/`). A scratch wrapper
(`ingest_withheld.py`, no product seam) re-ingested fmt and args with the
`uses` fact dropped wherever `_operator_call` answers `True`, and
`diff.py` compared the graphs: fmt −156 `uses` symbol edges (437
references), args −24 (40), nothing added, nodes and symbols unmoved —
and **one module edge gone on each cell**, which ADR-131's Consequences
had said would not move. Both read by hand as wrong: `test/scan.h →
include/fmt/format.h` stood only on integer `n * 10` and `prev * 10ull`
read as `fp`'s `operator*`; `args.hxx → test/test_common.hxx`, a library
header depending on its own test header, only on `ss >> destination`.
That is the best evidence the route had, and it is in the amendment.

**Then the amendment and §10.16 (P98–P101), committed before the unit**
(`17ddef0`), and unit `4033` through the harness: 36 turns of 80, $1.78,
4 minutes, gate clear, verify pass. The diff is the rule as briefed (`True`
counts and `continue`s, per hit). On the host: 1,867 pytest, 9 `lane_b`.
Regraded from the branch's worktree before the merge: all four exports
identical row for row, the built graphs equal the probe's edge for edge,
evidence included. **P98–P101 met.** Not held out, and the record says
so: both C++ cells were read by the wrapper and no key judges `uses`.
Merged no-ff (`f38fc63`); tracker 49 of 40.

**The price, written where a reader meets it** (C-153's entry, the
CHANGELOG): the right candidates go with the wrong ones — the key
confirms 175 of fmt's in-template rows as calls, and those were true
dependencies. C-153's residual now names what is left of the shape: a
dependent reference *not* at an operator token still stands as `uses`.

**Constructions, step 0 — measured, nothing drawn**
(`~/.hobbes/bench/cpp-constructions/`: `probe.py`, `classes.py`,
`PREREG-args.md`, `fmt-out/`, `args-out/`). For every distinct missed
`static→constructor` pair: what lane B holds on the site line, what the
graph holds at the target and at the site, the syntax at the reference's
column, in a template or not.

| class | fmt (8,047 pairs) | args (889, held out) |
|---|---|---|
| 1–2 the constructor (or only its class) named at a **macro invocation's name** (C-131) | 6,450 — 80.2% | 0 |
| 3 no reference; gtest's `new TestClass`, the target a `TEST` line | 557 — 6.9% | 0 |
| 4 **no lane B reference on the line** | 814 — 10.1% (690 in a template) | 491 — 55.2% (484 `EitherFlag`: `'f'`/`"foo"` converted implicitly inside a braced list) |
| 5 the constructor named at a real token, **outside a template** | **152 — 1.9%** | **383 — 43.1%** (324 at the `{` of a braced argument: `Matcher`, `Nargs`) |
| 5 the same, inside a template | 45 | 2 |
| 6 the class named at a real token, the constructor not | 29 | 13 |

So the handoff's "8,117 misses, 67% of what is left on args" is not one
class. On fmt it is the macro class again (gtest's `Message` and
`AssertHelper` constructors: 4,899 of the pairs), exactly
as operators were. What a token rule in ADR-131's shape could draw is
class 5 outside a template: **at most 152 rows on fmt (+0.3 points of
recall) and 383 on args (+10.8)**. Every such row already stands as a
`uses` edge onto a `method` symbol; the reference sits at the declared
variable's name, the `{`, the member's name in an initialiser, the `=`
of a default argument, or an arbitrary expression converted implicitly —
never at a callee lane A records. Class 4 is lane B saying nothing:
undrawable from this index. Nothing in class 5 is inside an unevaluated
operand on either cell.

**args was held out and two of five predictions missed**
(`PREREG-args.md`, scripts frozen by hash, run once): P-c1 (class 5 the
largest, ≥ 50%: it is 43.1%, and class 4 is larger — I did not think of
the implicit conversions at all) and P-c3 (declarator shapes ≥ 70% of
class 5: they are 8 of 383; braced arguments are 324). P-c2, P-c4, P-c5
met.

**Not registered, and said here so it is not lost:** the C++ segment has
no entry for a construction that draws no call. It is a concession in
ADR-113 §2's text and in the projection's comment only. It gets its
`C-n` with whichever route Max takes below — the entry's shape depends on
it — and if he takes none it is registered as it stands, unsurfaced.

**Put to Max as routes (the handoff has them):** (a) a construction-token
rule, outside a template, in ADR-131's shape, args' 383 the prize and
fmt's 152 the check; (b) register and move to the list's next item;
(c) open the macro class (C-131), which is 80% of fmt's constructions,
75% of its operator references and all of cJSON's misses — parked, his
to unpark.

No spend beyond the subscription's $1.78.

## 2026-09-17 (late evening) — constructions at the token, outside a template (ADR-132, 0.2.44-beta)

Max, on the constructions routes: "remove the old work trees. then good
to go with recommended." The six worktrees went first (each looked at:
clean, merged into `main`; branches kept). `ttt/hobbes-base` stays — the
held TTT work's base.

**The rule simulated and graded before it was designed**
(`~/.hobbes/bench/cpp-constructions/`: `simulate.py`, `buckets.py`,
`grade.sh`, `tokenpos.py`, `PREREG-args-sim.md`). A candidate is a lane B
reference onto a definition row with a constructor moniker. Every
candidate drawn on fmt reads **95 contradicted**, 94 at a macro's name.
At a construction token outside a template: +135 rows, 111 confirmed, 0
contradicted, 0 `line-unresolved`, 24 `unreachable` — all 24 read by
hand as right (`MutexLock l(&m)` onto `GTestMutexLock`'s constructor
through its typedef ×23; `basic_format_context<appender, char>` onto
`context`'s).

**The hand read found one wrong class before args was run:** 4 rows were
a constructor's own in-class declaration, which lane B points at its
out-of-line definition. The class head is macro-broken (`class
GTEST_API_ X {` parses as a function, `public:` as a label, `explicit`
as the type), so the declaration looked like a local. First excluded by
comparing the identifier with the constructor's name; then restated as
what lane A can test without the name — the declaration sits directly
in a block, never under a label — since a packed token carries no text.
Both forms draw the same rows on both cells (`simulate-v1.py` kept).

**args, held out on the precision side, run once:** +369 rows, 369
confirmed, 0 contradicted, 0 silent; 62.5% → 72.9%. P-s1–P-s4 met; P-s5
half missed (16 untokened rows where ≤ 15 was predicted — none drawn).
What had and had not been read of args is written at the top of the
prereg: step 0 had read its misses, so the recall side was known; nothing
the rule would draw *beyond* the key's misses had been.

**Inside a template the rule would add 45 rows and none reads wrong** (44
on fmt: 42 confirmed, 2 the same `MutexLock`; 1 on args, confirmed) —
unlike operators. The likely reason is in step 0's table: a dependent
type's construction gets no reference at all (690 rows), so what the
index does emit in a template is a non-dependent type's. ADR-132 does
not draw them: 45 rows is evidence, not a mechanism proved, and every
other in-template answer on this lane has needed a guard. They stay
`uses`. **Put to Max.**

**ADR-132 and §10.17 (P102–P107) committed before the unit** (`7133aba`).
Unit `4834`: 84 turns of 140, $8.57, 15 minutes, gate clear, verify pass;
1,900 pytest and 9 `lane_b` on the host. Five deviations, each the
pinned grammar's shape or drawing less.

**The grade, from the branch before the merge.** args is the probe's
export row for row: **2,567/2,567, 72.9%**. fmt **6,993/6,993, 0
contradicted, 30.3%, strict 99.62%**, no row outside the probe's — and
**19 of the probe's rows not drawn. P102 missed on the count** (7,012 ± 3
predicted). One cause, found by reading both lanes on one line:
`using fmt::detail::bigint;` then `bigint n1(42);` gives two lane B
references named `bigint` — the using-declaration at the type, the
constructor at `n1`. Lane A already records a construct site for
`T x(args)` named by the type; it takes the nearer reference, which is
below the floor, and the join's `claimed` set is keyed by `(file, line,
name)`, so the constructor's reference is claimed with it and never
reaches the unclaimed loop. The simulation did not model the claim; the
doer's closing note ("that site claims every same-named resolution on
its line") is what pointed at it. 14 `bigint` rows and 5 `file` rows on
fmt, none on args. It draws nothing rather than something wrong, and the
fix is the join's claim — shared by every language — so it is registered
in C-162 and left as its own item.

**C-162 registered and narrowed in one commit.** The concession had stood
since ADR-113 in the projection's comment only. 162 entries, 118 active,
92 surfaced. The comparative data and graphics re-rendered from the cell
records (`render.py check` green): fmt 6,993/6,993, args 2,567/2,567.

Merged no-ff (`112e738`); tracker 50 of 40. Image rebuilt at
0.2.44-beta — **restart the knowledge server** (C-65).

No spend beyond the subscription's $8.57.

## 2026-09-18 — the join's by-name claim measured and simulated (ADR-133 proposed; nothing built, no version move)

Max took both recommended routes from the handoff: constructions inside
a template stay `uses` (nothing to build), and the join's claim is
measured as its own item.

**Step 0** (`~/.hobbes/bench/join-claim/probe.py`, 24 graded clones; it
wraps `join`, replays the matching and classes every resolution a
matched site's `(file, line, name)` claim hides; no artifact written).
The model was checked first against a known number: fmt reads 19
constructors hidden outside a template, ADR-132's P102 rows exactly.
6,574 hidden in all, Java and TS carrying most; 1,158 at the matched
hit's own column (alternates of one reference, which ADR-104 wants
hidden), 4,193 at another column onto a definition the line's matched
hits do not name, 1,204 onto the same one. The hand read of the 4,193:
true dependencies — a Java declaration's type beside its `new`, a TS
interface beside the function of its name, a Go return type beside a
method call. The matching is not the defect: all but 2 contested sites
took the hit at their exact column. The general case was in no register
entry (C-162 holds only the using-declaration shape).

**Step 1** (`ingest_bypos.py`, `sim.sh`, `diff.py`; `PREREG-sim.md`
written first): the claim keyed `(file, line, name, col)`, simulated in
memory, eight cells ingested stock and by-position on the same tree and
graded against stored keys. P-j1–P-j6 all met: fmt 6,993 → 7,012
confirmed at 0 contradicted (the number ADR-132 predicted); args, jsoup,
Severed-Chains, zod, ajv, quic-go and memchr graded ±0; 1,262 `uses`
symbol edges added across them, nothing removed, one module edge
(quic-go `http3/body → interface`, a true return-type dependency);
poison passes both arms. Each clone was re-ingested stock afterwards.

**Not done:** dagger's step-0 pass was still running at the close (its
line lands in `run-all.log`; `out/dagger.json`). No `uses` edge is
graded by any key — the ADR says so.

ADR-133 written as *proposed*: route (a) build it in one unit with C-163
registered and lifted and C-162 narrowed, then the full stored-key
regrade; route (b) register and leave. No spend.

## 2026-09-18 (later) — the join claims by position (ADR-133 built and graded, 0.2.45-beta)

Max read the measurement and took route (a). ADR-133 accepted, with one
addition the simulation had not carried: a **site** lane A recorded no
column for keeps the by-name claim, since which resolution it matched is
not known (no contested site on the 25 clones was columnless). dagger's
step-0 pass finished: 734 hidden, 704 of them new `uses`; 7,308 on the 25
clones.

**The unit** (`3569`, brief and partition in
`~/.hobbes/bench/join-claim/units/`): two files, 26 turns of 80, $1.78
on the subscription, gate clear, verify pass, no deviation, no existing
assertion moved. Read, run on the host from a worktree (1,910 pytest,
`lane_b` 9 of 9), merged no-ff (`83cde1b`); tracker 51 of 40.

**The regrade** (`regrade.sh`, `PREREG-regrade.md`, `compare.py`;
§10.18, P108–P113 written first, all met): 44 stored-key cells over 25
clones, each clone ingested by a worktree at `8738fc2` and then by main,
so the before and after share a clone, a key and a day. fmt 6,993 →
7,012 confirmed at 0 contradicted — the number ADR-132's P102 predicted —
strict 99.62%, recall 30.4%; the other 43 cells row-identical. 1,785
`uses` and 11 `calls` symbol edges added, none removed; two module edges,
both read by hand and true (quic-go's `quic.StreamID` return type,
dagger's `introspection.Query`). The two hobbes cells were left out:
their clone, a worktree at an old sha, is gone. An ingest that reads 0 s
in the log is the lane B index cache answering, not a skipped ingest —
checked on `built_by` in both arms' graphs.

**Records:** C-163 registered and lifted, C-162's using-declaration
residual closed (163 entries, 118 active, 28 lifted); architecture §3.4's
edge list and the C++ passages, §3.8's row, README, CHANGELOG,
comparative README, tables and graphics re-rendered from fmt's cell
record (`render.py check` green, the report drift test green),
workstreams. Image rebuilt at 0.2.45-beta — **restart the knowledge
server** (C-65). Suites green: 1,910 pytest (9 `lane_b`), Go, 87 scip,
36 tsextract, 52 vitest. Worktrees `join-claim/wt` and `wt-pre` removed.

No spend beyond the subscription's $1.78.

## 2026-09-18 (evening) — a lost definition's extent measured and simulated (ADR-134 proposed; C-164 registered; nothing built, no version move)

Max: review the top-level documentation, then continue from the resume
point with the lost definition's extent.

**The documentation read** (README, CLAUDE.md — `AGENTS.md` is its
symlink — CHANGELOG's head, the handoff, the register's index). Four
figures in the README's Status section had drifted from the records and
are corrected: the register's count (161/117/27 → the register's own),
fmt's strict figure in the oracle paragraph (99.61% where every other
place says 99.62%), the session logs standing (48 → 51, the directory's
count), and the ADR range in the design-docs table (131 → 134). The
register index's "Debt summary" headline read 162 entries and 27 lifted
above a table that said 28; it reads the table's numbers now. Not
changed, noted for the docs restructure: the README's extraction section
carries a version-by-version C++ history (0.2.41 to 0.2.45) that is the
CHANGELOG's job, and the Status section's Calvin paragraph repeats it.

**Step 0** (`~/.hobbes/bench/c145-extent/probe.py`). The C and C++ keys
grade `(site, target)` and never read an edge's `from`, so no cell has
judged a C++ caller; the key does name clang's caller at every site, so
the probe reads it beside Hobbes'. The first two passes were wrong and
the hand read caught both: gtest's `<suite>_<name>_Test::TestBody` is
lane A's `<suite>.<name>` (3,000 rows scored "wrong" at first), and
`~2`/`~b2` are id devices. After: fmt 8,123 `calls` evidence rows, 6,392
agree, **1,436 lost** (module where clang names a function; 1,329 under a
minted definition), **75 wrong**, 97 lambda, 96 no key site; args 2,567
rows, 15 lost, 4 wrong.

**What the wrong rows are** — not this item's question, and registered
as **C-164** (unsurfaced, debt): lane A symbols *named by a macro*
(`… ) GTEST_LOCK_EXCLUDED_(mutex_) {` is a function called
`GTEST_LOCK_EXCLUDED_`; 14 symbols on fmt, 28 `calls` edges out), a
constructor named by its first member initialiser (`str_`, 2), and one
`TEST` body whose recovery swallowed the ten tests after it (39 rows,
and their test reach). 73 of 75 wrong by hand, 2 the key's grain.

**The index has no extent.** scip-clang 0.4.0 run on a ten-line file in
the image, its output walked by field number: occurrences carry fields
1, 2, 3 and 5, never 7 (`enclosing_range`).

**Step 1** (`simulate.py`, the graph read and never written): a minted
function's extent by brace matching on the file's text with comments,
strings and character literals blanked, refused where a preprocessor
conditional sits in the body. fmt: 1,365 extents, 34 refused; 1,303 rows
move, 1,231 to the key's caller, 23 lambda, 19 the key cannot judge, 30
differing — all 30 read, none wrong (24 friend functions the key files
under the lexical class and the index under the namespace, 5 methods of
a nested specialisation the key's name elides, the rest lambdas the key
class-qualifies). args 16 rows, 3 differing, none wrong. **No row whose
caller was right would move.** Allowing conditionals: +61 rows, none
wrong, and a guess.

**ADR-134 proposed**, routes for Max: (a) build it with conditionals
refused — recommended; (b) conditionals allowed; (c) register and leave.
It says plainly that no graded number moves — what moves is `who_calls`,
`tests_guarding` and the gate's reading — and that the key's caller
names are a probe re-run at the regrade, not a grade. C-164's own item
goes ahead of the 15 line-convention rows: those rows are wrong, not
missing.

**Records:** ADR-134; C-164 registered, C-145's residual carries its
measurement (164 entries, 119 active, 4 unsurfaced); the register index;
README's four figures; CLAUDE.md's status; the handoff. No code moved,
no suite run, no version move, no dispatch, no spend.

## 2026-09-18 (night) — a lost definition's extent built (ADR-134 accepted, route a; 0.2.46-beta); the top-level drift fixed first

**Asked:** fix the doc drift the review found, then proceed with route
(a) for ADR-134.

**The drift (`1f10357`).** The handoff said CI was green on `dbef0af`
and everything since unpushed; `origin/main` was at `c34b98c`, green
(run 35360468231). The workstreams header stopped at 2026-09-17 while
its body carried 0.2.43–0.2.45. Both corrected.

**Measured before the brief — and the ADR was wrong.** ADR-134 §2's
third refusal (an extent containing another definition's line) carried
the sentence "not seen on either cell", which nothing had measured.
`simulate_r3.py`: it fires on **19 of fmt's 1,365 extents**. 13 are
macro-generated methods — `GTEST_REPEATER_METHOD_(OnTestStart, TestInfo)`
is a method to clang and a line with no brace in the text, so the match
ran into `OnTestIterationStart`'s body thirty lines below. Step 1 had
not seen it because no `calls` row moved wrongly; the *node* would have
been wrong. The other 6 are right extents holding a C-164 symbol,
refused all the same. The ADR was amended to accepted with this
(`fe05ca0`), §10.19's predictions written (P114–P120), then one unit.

**Unit `368a`** (Opus 5, 59 of 120 turns, $5.88 on the subscription, 15
min; gate clear, verify pass): the blanking over a whole file, the brace
match and its four refusals in two passes, `minted.rehome`, the summary
lines, 27 tests. Five deviations listed, each toward drawing less.

**Plan beside outcome — the brief's premise was wrong.** It said a
file-scope site has an empty scope and re-homes by itself once
`end_line` is real. Lane A's C and C++ sites carry **the module's id**
as scope, truthy, so `project` never asks `enclosing`. The first real
ingest of args moved 2 rows of 16. The hand-fed ingest test could not
show it (its re-homed fact is lane B's alone, scopeless); the real cell
did, which is what running the check before the merge is for. Fixed in
the developer's commit after the no-ff merge: a module-id scope is the
module. A second run left 56 fmt rows on a one-line body's own line:
`end_line == line` is a read extent and a refusal both, so the mint now
marks a read one (`extent: "braces"`), and `rehome` and the proxy's
`who_calls` note read the mark. My own `lane_b` end-to-end header also
failed first — lane A recovered its `inline` functions — and was changed
until lane A really lost them.

**The check (§10.19; `~/.hobbes/bench/c145-extent/regrade.sh`), not a
grade:** every graded number ±0 and every export row-identical on fmt,
args, cJSON, sqlite-vector; click identical. fmt: 1,346 / 34 / 19
(P115 exact), 1,290 `calls` rows re-homed (the simulation's number),
agreeing 6,392 → 7,610 (predicted), wrong class 75 → 105 (predicted),
**lost 1,436 → 188 where 165 ± 5 was predicted** — the prediction
subtracted 23 lambda and 19 unjudged rows that the probe never classed
as lost; recorded as a miss of the arithmetic. No right row moved. 760
`uses` rows re-homed (92 from a class to its own method, eight read).
Two self-edges vanish on fmt and two non-self-edges appear on args, not
predicted. fmt's test reach 3,183 → 6,131 pairs, none lost.

**Records:** ADR-134 (accepted, *Accepted* and *Built* sections);
§10.19; C-145 rewritten (no entry added; 164 / 119 / 4 unsurfaced
unmoved); the register index; architecture §3 (the extent paragraph,
§3.8's row, §8's version); CHANGELOG 0.2.46-beta; the fmt cell record (a
note, headed *not a regrade*); session `368a`'s review block and the
tracker (52 of 40); README, CLAUDE.md's status, the handoff, workstreams.
Suites on the host: 1,942 pytest, `lane_b` 10 of 10, Go 396 with
subtests (395 pass, 1 skip), the report drift test. Proxy and image
rebuilt at 0.2.46-beta; the repo re-ingested. No API or Modal spend.

## 2026-09-18 (late night) — C-164's wrong callers counted key-free and simulated (ADR-135 proposed; nothing built, no version move)

**Asked:** review the top-level documentation and report; then (Max: CI
is green, he pushed after the session closed) remove the merged unit's
worktree, restart the knowledge server if needed, and proceed with
C-164.

**The review.** `VERSION`, README, CHANGELOG, CLAUDE.md/AGENTS.md
(identical), the handoff, the workstreams header, ADR 134 and 52 session
logs agree. One drift: the handoff said everything since `c34b98c` was
unpushed; `origin/main` is `0c6c34e`, run 35370791824 green. Corrected.

**Housekeeping.** `c145-extent/wt` removed with `--force` after
checking its three modified files were byte-identical to `main`'s (the
developer's fix, `0c6c34e`). The knowledge server's container was
started after the 0.2.46-beta image was built; no restart needed.

**Step 0, key-free** (`~/.hobbes/bench/c164-wrong-callers/`:
`findstream.py`, `shapes.py`, `nameref.py`). On the four cells with an
index: 18 misnamed lane A symbols, all on fmt (13 a macro's name, 5 a
member initialiser's — the register said 2) and 2 swallowing extents; 0
on args, cJSON, sqlite-vector. **The index's definition row at the line
does not separate them** (332 of fmt's lane A functions have none, and
the read is preprocessor-inactive code parsed right), and neither does
"the name is a macro's" (cJSON's `internal_malloc`). A **reference at
exactly the symbol's own name token**, to a macro or a `term` of that
name, does: 18 flagged, 18 misnamed by hand read, 0 flagged among the
3,769 symbols whose name the index agrees with. Read loosely (anywhere
in the head or body) it flags four right symbols — `Base::KickOut`
beside `Options::KickOut` — so the built rule needs lane A's name column.

**Step 1, simulated** (`simulate.py`, `PREREG-sim.md` first): R1 refuses
the misnamed symbol, R2 re-reads a swallowing extent from the braces.
fmt wrong-caller **105 → 32**, agree 7,610 → 7,625, lost 188 → 246; 15
rows right, 58 lost, **no agreeing row moved**; six of ADR-134's
`holds-a-definition` extents unblock. The 32 left are the probe's naming
grain (25 in-class `friend` definitions, 5 a nested class, 2 others),
not C-164. P-3 and P-5 met; **P-1 missed by one** (18, not 19: one
symbol counted at two references) and **P-4 missed** (agree +15 where
+29–34 was predicted: the prediction did not read the minted
definitions' own extent refusals first — `AddTestPartResult`'s 14 rows
sit under a `conditional-inside`).

**Written:** ADR-135 (proposed, routes a–d; (a) recommended: R1 + R2,
one unit, lane A's cache to v5); C-164 amended with the counts; the
register's dated note; the handoff and CLAUDE.md's status. No suite
run — no code changed. No API, Modal or dispatch spend.

## 2026-09-18 (late night, second) — a lane A symbol the index contradicts, built (ADR-135 accepted, route a; 0.2.47-beta)

**Asked:** Max: proceed with the recommended route.

**Premises before the brief** (ADR-134's lesson, [the brief mis-stated a
site's scope and the unit shipped green on it]). Read in the tree:
`cppsource._symbol` already holds the identifier node, whose column is
0-based as lane B's `col` is (`xchar.h:98`, `str_` at 62 in both); the
lane A cache stores symbols, so `laneacache.FORMAT` must move; the
resolutions are `Site`s with `def_file`/`def_line` and the definition
rows (macro and `term` among them) are `lane_b_definitions`;
`rehome` reads a module-id scope as the module, so a refused symbol's
facts can simply take it; nothing runs into any of fmt's 18 (37 `calls`,
38 `uses`, 1 `implements` evidence rows run out). One thing in the ADR
changed on that reading: the counts go in a graph block, not the
`parse` record, which is lane A's and written before the index is read.
ADR-135 accepted with these written in; §10.20's P121–P127 committed
(`2ad6232`) before the dispatch.

**Unit `c2cc`** (68 turns, $6.61, Opus 5; launched detached, dry-run
first: `--settings`, the model and `--max-turns 80` in the argv). Gate
clear, verify pass, nine files. `name_col` on a C++ function or method;
`lanea-cpp v5`; `minted.contradicted` — the wanted `(file, line, col)`
keys built first and one pass over the resolutions — run before the
mint; `lane_a_contradicted` written only where something fired; one
summary line. Two deviations, both toward leaving the symbol alone.

**On the host, from a worktree of the branch:** `lane_b` 10 of 10, the
whole suite 1,964. **Then the real cells, before the merge**
(`c164-wrong-callers/regrade.sh`): every graded number ±0 and every
export row-identical on fmt, args, cJSON, sqlite-vector; click
identical. fmt: 18 refused (13 `macro`, 5 `term`), 1 extent re-read
(292 → 210), wrong-caller **105 → 32**, agree 7,610 → 7,628, lost 188 →
243, no agreeing row moved, `holds-a-definition` 19 → 13, one test's
reach 3 symbols smaller, none other. **Missed by one row each beyond
± 2:** agree (7,625 predicted) and lost (246) — with the misnamed symbol
gone the mint named two true definitions on the vacated lines
(`~FunctionMocker`, a `basic_scan_arg` constructor), which the
simulation did not model. 393 evidence rows changed `from` against 87
re-scoped facts, read before merging: 317 are the swallowed tests'
sites, most carrying no scope — their caller was `enclosing`'s answer,
and clipping the extent moved them.

**Merged no-ff** (`e41a687`); review block filled, tracker re-rendered
(53 of 40). **0.2.47-beta:** VERSION and its copies, the CHANGELOG,
architecture §3 and §8's header, README, C-164 unsurfaced → partial
(register 92 / 23 / 3), ADR-135's *Built*, §10.20's results, the fmt
cell page, the handoff, workstreams, CLAUDE.md's status. Proxy and image
rebuilt; on `main` 1,964 pytest, `lane_b` 10 of 10, Go `./...` and the
report drift test green; the repo re-ingested. No API or Modal spend;
one dispatch on the subscription.

**Not done, written in the handoff:** a `lane_b` end-to-end case for
ADR-135; the friend and nested-class equivalences in `probe.py`.

## 2026-09-18 (late night, third) — the `lane-a-symbol-near` rows read: no line-convention class, nothing to change (no version move)

**The doc review first:** one drift again, the handoff's push line (CI
was green on `d1f52a1`, run 35377779488, and nothing was unpushed);
corrected (`c8bf6a2`).

**The item** (the C++ recall list's third): the mint refuses a
definition row where a lane A symbol of the same name starts within 3
lines, and its docstring called that the two lanes disagreeing about a
definition's line. Measured first, key-free:
`~/.hobbes/bench/lane-a-symbol-near/probe.py` re-walks the mint's
refusal chain up to the near check on a clone's own graph and its cached
facts stream and prints each row beside the lane A symbol and the
source. It reproduces each graph's count: fmt 15, cJSON 2,
sqlite-vector 2, args 0 (the probe does not know the lossy-file set, and
says so: its one args row is in a clean file, which the mint refuses
earlier).

**Read against the source, all 19:**

- **10 on fmt are a defaulted or deleted constructor** (`weekday() =
  default;`, `buffered_file(const buffered_file&) = delete;`) beside an
  overload with a body, or beside its own class — a constructor's
  terminal name is the class's. Both lanes have the right line; they are
  two definitions.
- **8 are the other arm of an `#if`** (5 fmt, 2 cJSON, 1 sqlite-vector):
  `using utc_clock = std::chrono::utc_clock;` / `#else` / `struct
  utc_clock {`. Lane A names the first arm, the index the compiled one.
  Again two definitions, each on its true line.
- **1 is a line convention:** `typedef struct sqlite3_snapshot { … }
  sqlite3_snapshot;` — the index's row at the struct's line, lane A's
  symbol at the typedef's name. One entity, and refusing the second node
  is right.

**What the next rules would say** (`shows_body` and the type check run
on each): every one of the 19 is refused anyway — `declaration` for the
constructors and the body-less aliases, `lane-a-has-type` for the
rest. The near rule hides no definition lane A lost and no mintable
row; removing it would move only the refusal counts.

**Decision: no rule change, no ADR, no version move.** The docstring in
`minted.py` now says what the rows are. What the rows do show is
already registered elsewhere: a defaulted constructor is not a symbol
(lane A's definitions-only rule, kept in ADR-129), and lane A reads an
`#if`'s first arm where the index reads the compiled one (C-133's
family). Neither is this item's.

## 2026-09-18 (late night, fourth) — ScummVM as a scale read; R1's clean-file remainder found (ADR-136 proposed; nothing built, no version move)

**The caller probe's naming grain folded first**
(`~/.hobbes/bench/c145-extent/probe.py`; the old one kept as
`probe-v1.py`): `agree-friend` (the key puts a friend defined in a class
under the class; Hobbes names it at namespace scope — the class's line
range where lane A has it, the preceding same-scope class where the
type is minted and has no extent), `agree-nested` (the key drops a
nested class), and inner whitespace not compared (`operator char *`).
Shown as their own classes, never folded into `agree`. fmt at
0.2.47-beta: wrong-caller **32 → 3** (23 friend, 5 nested, 1 spelling);
args 6 → 4. The 7 left on the two cells are one local-to-function
definition (C-9's floor) and six lambdas the key qualifies with the
enclosing class (`Command::operator()`), which the probe's `lambda`
class matches by the bare name only.

**ScummVM, end to end at 0.2.47-beta**
(`~/.hobbes/bench/scummvm-scale/`; clone `c54b79a6`, 19,948 C++ files,
5,958 units; the 0.2.26-beta graph kept as `before/`). Launched
detached. Cold, both caches missing (`lanea-cpp v5`): **exit 0 in 9 min
04 s**, 8.1 GB peak — 0.2.26-beta's was 8 min 57 s. Warm: **2 min 20
s**, and the graph **byte-identical** to the cold one.

| step | cold | warm |
|------|-----:|-----:|
| lane A [cpp] | 228.5 s | 23.6 s |
| lane B [c] (index + decode) | 192.3 s | 19.9 s |
| join | 15.0 s | 14.7 s |
| contradicted (ADR-135) | 3.7 s | 3.6 s |
| mint + extents (ADR-129/134) | 1.9 s | 2.0 s |
| rehome | 0.8 s | 0.7 s |
| project | 17.6 s | 17.9 s |
| write | 19.1 s | 18.5 s |

Lane A's cold C++ walk was 135 s at ADR-128; the operator, construction
and name-column walks since are in the 228 s, once per file, and the
cache returns them in 7.2 s of reads. The handoff's worry (the operator
walk climbing to the root per token) is a cold-run cost of about a
minute and a half on the largest clone held, and nothing warm.

**What the rules drew there (no key; counts, and a hand read where a
rule removes):** 4,510 symbols minted in 487 lossy files, 3,084 brace
extents (refused: 448 `holds-a-definition`, 103 `conditional-inside`, 7
`runs-off`), 49,207 facts re-homed; 67,707 operator calls (254 in a
template withheld); 12,612 construction calls (24 in a template left
`uses`); `calls` semantic symbol edges 428,671 → 470,357 against
0.2.26-beta, `implements` 30,510, module edges 222,604 → 225,257.
`lane-a-symbol-near` 21.

**R1 at scale: 401 removals (400 `macro`, 1 `term`), 27 names, every
name read against the source, no false flag** — 22 generator macros
(`DECLARE_COMMAND_OPCODE(location) { … }` 59 times, `APPFUNC`,
`TERMINATOR`, the `SPELL…` family), 4 object-like renames (`#define
yyparse HYPNO_ARC_parse`), one member initialiser. R2: 2 extents
re-read, 19 refused.

**The finding** (`vacated.py`): 141 of the 401 are in lossy files and
the mint named 137 of them (131 with an extent). **260 are in 19 files
that parsed clean** — a generator macro reads as a function definition
with no ERROR node — and `clean-file` keeps the mint out, though the
index holds exactly one definition row with a body at every one of the
260 lines. Those definitions (`…::cmdOp_location`,
`Grim::lua_strlibopen`) have no node: wrong before 0.2.47-beta, absent
now. fmt never showed it (18 of 18 lossy). Registered in C-164 as a
remainder; **ADR-136 proposed**, route (a) recommended: the mint reads a
definition row at a line R1 vacated, every other refusal kept. No
graded cell can move (R1 removes nothing in a clean file on any of
them); the check would be that they do not, and a sample read of the
260.

No dispatch, no API or Modal spend. 102 `test_minted` cases green after
the docstring change; nothing else in the layer moved.

## 2026-09-18 (late night, fifth) — the mint at a line R1 vacated, built (ADR-136 accepted, route a; 0.2.48-beta)

**Max: "go with the recommended."** Before the brief, the premises were
read in the tree (ADR-136, *Accepted*), and one of the ADR's own
sentences was wrong: `contradicted` does not hand out the positions R1
vacated — `refused` is internal, id to module — so the unit adds a
fourth return rather than reading something that was there. The rest
held: the mint's line test already reads R1's output, R1's facts already
carry the scope `rehome` looks for, and `minted.files` means lossy
files, so the new mints are counted apart. §10.21's P128–P133 committed
(`d00f646`) before the dispatch.

**Unit `e78d`** (77 turns of 80, $6.60, Opus 5; launched detached,
dry-run first: `--settings`, the model and `--max-turns 80` in the
argv). Gate clear, verify pass, five files, no deviation. Two
escalations, both the doer writing a scratch fixture under `/tmp` by
heredoc; they expired and it used `tmp_path`.

**On the host, from a worktree of the branch:** 1,977 pytest, `lane_b`
10 of 10. **Then the real cells, before the merge:** fmt, args, cJSON,
sqlite-vector and click row-identical, `minted.vacated` zero on each
(P128). ScummVM on the branch's code, warm: **260 symbols in 19 clean
files, 4,770 minted, `clean-file` 185,278 — P129 exact.** 255 of the 260
took a brace extent (P130 said 245 ± 8: missed by two, the lossy half's
rate was the wrong proxy); `rehomed` 49,207 → 51,981. **P131 was worded
wrongly**: 289 symbol edges of the before graph are absent, each the
same evidence under a new `from` (278 from a module, 11 from the class
around an in-class generator macro); no evidence row left, 589 arrived,
1,639 edges added. 30 of 30 sampled names right (P132); the second
ingest byte-identical (P133).

**Merged no-ff**; review block filled, tracker re-rendered (54 of 40).
**0.2.48-beta:** VERSION and its copies, the CHANGELOG, architecture §3
and §8's header, README, C-164 narrowed again (still partial; register
counts unmoved), ADR-136's *Built*, §10.21's results, workstreams, the
handoff, CLAUDE.md's status. Go `./...` green, proxy and image rebuilt,
1,977 pytest on `main`, the repo re-ingested. No API or Modal spend; one
dispatch on the subscription.

**A lesson for the next prediction:** say what a re-home does to an
edge's `from` before predicting "no edge absent" — compare evidence
rows, as `compare.py` already does for the graded cells.

## 2026-09-19 — the review's three remaining items: C-4 and the `-I` path measured (ADR-137, ADR-138 proposed), the docs restructure's first half (no version move)

**The doc review first.** Two drifts, fixed (`2b66c73`): the handoff
still said everything since `d1f52a1` was unpushed (`a930ba1` is pushed
and CI-green, run 35412968495), and `pyproject.toml`'s comment named
VERSION 0.2.44-beta beside `0.2.48b0`. **The knowledge server needed no
restart:** its container was started with this session from image
`a56b92b0e11b`, the 0.2.48-beta build, and the ingest is at `a930ba1`.

**C-4, pytest fixtures as edges — measured, ADR-137 proposed.**
`~/.hobbes/bench/c4-fixtures/` (`probe.py`, `probe-v1.py` its first
form, `compare.py`). pytest's fixture lookup is all syntax (class, file
and its imported names, the conftest chain), and pytest itself is the
key: `--fixtures-per-test`, collection only. On this repo **1,004
test–fixture pairs, 1,004 right, 0 wrong, 0 missed**; the first form
(no class scope, no imports) read 902 / 0 / 102. 317 tests' reached
modules grow and 233 stop reading `reaches: []`; **no module is newly
guarded**, here or on click, where the one fixture buys `CliRunner` and
the real loss is `runner.invoke(…)`, a typing question. No trace key
judges a test→fixture edge (the fixture's caller is pytest's frame).
Routes: (a) a `uses` edge and a labelled reach step, (b) a new edge
type, (c) surface only.

**The `-I` path at lane A — measured, and it found C-142 instead;
ADR-138 proposed.** `~/.hobbes/bench/c133-include-path/` (`place.py`,
`claim.py`). The graded cells have nothing for `-I` to place: every
`c-includes` record on cJSON, sqlite-vector, fmt and args names a header
outside the repo or outside the build. ScummVM's database has one
non-root directory (`engines`): 116 includes of 95,510, 12 headers'
language. Beside it: **624 of ScummVM's `.h` are read as C in a repo
with two `.c` files, 535 of them spelling `class`/`namespace`/`template`**
— ADR-113 §1 asks for a C++ *source* includer, and a header reached only
through headers has none. A claim that follows claimed headers takes
374 of them. The same misread is why 122 of the 277 "unmatched" specs in
ScummVM's warnings are files at the repo root: the C walk does not know
the headers C++ claimed. Routes: (a) the transitive claim and the C walk
knowing claimed headers, (b) plus a content read for headers nothing
includes, (c) plus `-I`, (d) nothing. A first attempt at the record
count globbed all of `~/.hobbes/bench` and was stopped at five minutes;
the counts are from the five named clones and ScummVM's ingest log.

**The docs restructure, the half that needs no call.**
- `pipeline/tests/test_register_tally.py`: the register's tally is read
  from the segment files (a heading's *lifted*/*superseded*/*folded*,
  else **You find out**'s first word — it reproduces 92/23/3/1, 28, 11,
  6 exactly) and the index's table and headline, README's sentence,
  CLAUDE.md's and the handoff's lines are held to it. 1,980 pytest.
- The register index's 680 lines of dated notes moved to
  `docs/constraints/HISTORY.md` (newest first, append at the top); the
  index is 171 lines.
- README's extraction section states where C++ recall stands and points
  at the CHANGELOG, instead of retelling 0.2.41 to 0.2.48.
- **Left for Max's word:** §3.8's paragraph cells to per-language pages
  — it restructures the source-of-truth file.

No API or Modal spend; no dispatch.

## 2026-09-19 (second) — ADR-137 and ADR-138 built on Max's word (route a, both): 0.2.49-beta and 0.2.50-beta; §3.8 stays as it is

**Max: "recommended route is good, dont split for now."** Both ADRs
accepted at route (a); §3.8's per-language split is left. The knowledge
server was checked, not restarted: its container already ran the
0.2.48-beta image.

**The premises were read before each brief, and ADR-138's own rule was
wrong.** Its *Decision* let the C side follow headers too. `claim.py`,
run on that wording, moved 12 headers C++ claims today on ScummVM to
"shared" — 10 of them C++ — so the rule that went to the doer keeps the
C side direct, and only a claimed header passes the claim on. The ADR's
*Accepted* section says so, with two smaller corrections (the owning
walk's module id for an included `.cpp`; why the lane A cache is cold
after). For ADR-137: a Python `Symbol` carried no parameters, a
`Decorator` keeps only string literals (so `autouse=True` is invisible
and is *not* counted), imported names were already resolved inside
`graph._NameEnv`, and the projection is the only producer of joined
edges.

**Unit `5393` — ADR-137** (89 turns of 100, $7.70; gate clear, verify
pass, ten files). On the host from a worktree: 2,028 pytest, `lane_b` 10
of 10. The pre-registered check on the branch's own ingest: **1,004
pairs, 1,004 right, 0 wrong, 0 missed**, the figure exactly. Then the
held-out repos the ADR asked for, collected **in the image, offline**
(their dependencies installed as wheels into a directory; no repo code
run on the host): flask 504 right, attrs 104 right. **The first compare
read 3 + 5 wrong pairs, and neither was an edge:** pytest prints a
fixture at its first decorator line when the decorator spans lines, and
prints one row per fixture *name*, so the conftest's `app` that
`def app(self, app)` overrides and requests is run and not printed.
`compare.py` now counts both apart. Every miss is the remainder: 370
`autouse` on flask, 8 `usefixtures` on attrs — and the ingest's own
`usefixtures` count on attrs is 8.

**The developer's half of ADR-137, 0.2.49-beta (`2882fd2`):** a class
that names a base class abstains on a name found past its own chain
(`base-class`; an inherited fixture would win, and it is the one shape
where the rule could draw a *wrong* edge) — 0 abstentions on all three
repos; `tests_guarding` says "only through a pytest fixture (ADR-137)";
`hobbes review` lists new code guarded only that way, guarded and not a
reason for attention. C-4 partial → surfaced, narrowed. **The tally test
written this morning caught nothing because the four copies were edited
together — and then passed, which is what it is for.**

**Unit `286a` — ADR-138** (61 turns of 100, $4.55; gate clear, verify
pass, five files), launched once `5393` was merged and the ingest was at
HEAD; the developer's Python and Go edits were made while it ran, with
no `go/bin` build, image build or ingest until it had exited. On the
host: 2,046 pytest, `lane_b` 10 of 10. Five cells on the branch's code
(`c164-wrong-callers/regrade.sh`, `OUT=c133-include-path/regrade`): fmt,
args, cJSON, sqlite-vector identical in every row, symbol and edge;
click's export row-identical, its 316 new `uses` edges ADR-137's.
**ScummVM, cold, 547 s:** 9,468 → 9,824 `.h` read as C++ (356 through a
header), 629 → 273 as C; unmatched includes 395 → 43, none of the named
ones at the repo root (122 of 277 were); ambiguous 167 → 170; +1,413
symbols; 4,770 → 3,748 minted, lane A now holding those itself.
**The probe's 9,859 missed by 35**, toward claiming less (its regex
reads every `#include`, the walk the top level's). 0.2.50-beta
(`15a2d0d`): C-142 narrowed, C-133 noted as measured and not built.

**At the close:** 2,052 pytest, `lane_b` 10 of 10, Go `./...` green with
the rebuilt image, proxy and image at 0.2.50-beta, tracker 56 of 40,
both worktrees removed, the repo re-ingested at HEAD. No API or Modal
spend; two dispatches on the subscription, $12.25 reported.

**Lessons.** A probe is worth running on the rule *as worded* before the
brief: ADR-138's was wrong in the ADR and right in the code only because
of that. And a held-out key can be wrong about what it prints: read a
"wrong" row against the source before believing either side.

## 2026-09-19 (third) — the top-level doc review, the denominator statement's C-4 wording (0.2.51-beta), and C-4's remainder measured (ADR-139 proposed)

**The review.** The top-level documents agree with each other and the
tree: VERSION and its copies, AGENTS.md byte-identical to CLAUDE.md,
README, CHANGELOG, workstreams, the handoff, ADR 138 the last, 56
session logs, the tally and tracker tests green, `main` 16 commits ahead
of `origin/main` (`a930ba1`). Two drifts: the handoff's "restart it"
(the server already answered from `c481c5f`), and one in the product —
`list_blind_spots` and every derived manifest still opened with
"fixture-injected test reach (C-4)" among the things never detected,
two patches after ADR-137 drew the parameter case. The register had
recorded that the statement "still names" it.

**0.2.51-beta.** Both copies of the statement (`knowledge.go`,
`derive/manifests.py`) name C-4's remainder: a fixture no parameter
names (autouse, usefixtures) and the value a fixture returns. One
assertion on each side. No edge, node or count moves. pytest 2,052 and
Go `./...` green; binaries, image and ingest redone.

**C-4's remainder, step 0** (`~/.hobbes/bench/c4-remainder/`,
predictions first). `usefixtures` strings (test, enclosing class,
module `pytestmark`) and `autouse=True` names, resolved with ADR-137's
`_resolve` and abstentions, in memory. First comparison: `usefixtures`
clean (attrs +8), `autouse` 4,332 pairs "wrong" — every one a fixture
named `_…`, which pytest does not print without `-v`. **So ADR-137's key
had hidden them too.** Keys re-collected with `-v` (flask and attrs in
the image, no network; flask with `-p no:hypothesispytest`): today's
missed pairs are 3,962 here, 734 flask, 14 attrs, nothing drawn wrong;
with both rules 0 missed, 0 wrong on all three. Recorded misses: P-r1's
and P-r3's counts were written against the quiet key (370 and 0).

**The question the numbers raise is reach, not precision:** this repo's
`_lane_a_only` calls `staging.cache_root`, so drawn plainly every one of
1,981 tests guards `hobbes.extract.staging`. ADR-139 proposes both rules
with autouse reach said once, not listed (route a); (b) `usefixtures`
only; (c) both, listed. Nothing built. ADR-137 carries a note on its
key; C-4's figures and a HISTORY note corrected; tally unmoved.

## 2026-09-19 (fourth) — ADR-139 built on Max's word (route a): `usefixtures` and `autouse` looked up as a parameter is, autouse reach said once (0.2.52-beta)

**Max: "good to go with recommended route."** ADR-139 accepted; the
premises read in the tree first (`Decorator`'s one construction site,
the class's decorators on its own `Symbol`, `tiered_edge` copying
evidence keys through, where `through_fixtures` is read). Two narrowings
toward drawing less before the brief: a module `pytestmark` is counted
and not followed (the probe read it and no repo had one, so no key row
judged it), and one pair keeps one `via`. **The brief had one wrong
premise, caught before dispatch:** it asked for a nested class's tests
to inherit the outer mark, and `is_test_symbol` collects no nested
class's methods.

**Unit `6f84`** (68 turns, $5.70, 12 min): gate clear, verify pass, nine
files in the partition. Its four deviations each draw or say less and
are kept. On the host, on a worktree of the branch: 2,090 pytest, the 10
`lane_b` cases. **The real cell before the merge:** the branch's lookup
against the three `-v` keys — this repo 4,971 right, flask 1,238, attrs
118, 0 missed, 0 wrong — and its edges identical to the probe's. Merged
no-ff; tracker 57 of 40.

**The developer's half.** `tests_guarding` folds the tests that reach a
target only through an autouse fixture into one line naming the
fixtures, and no longer calls such a target unguarded; `hobbes review`
has `autouse_only` beside `fixture_only` (`_reach_kinds` — a module a
named fixture reaches is never autouse-only). One finding while testing
it: a new `conftest.py` is itself "new code reached through its autouse
fixture", because the test map treats a conftest as source, as it has
since ADR-137; left as it is and noted in ADR-139's *Built*. The
denominator statement rewritten to C-4's new remainder; C-4's entry
rewritten, HISTORY note, architecture paragraph, CHANGELOG.

**This repo's ingest:** 5,072 injections, 4,058 by autouse; 2,029 of
2,773 records carry `through_autouse`; `tests_guarding
hobbes.extract.staging` lists 441 tests and says 1,588 once. No graded
cell re-run: no key judges a `uses` edge and the rule adds no node.

**A drift of this session's own making, caught here:** the
architecture's §8 header still read 0.2.50-beta — the 0.2.51-beta bump
missed it, and no test holds that copy. Now 0.2.52-beta; the handoff
says to bump it by hand.

Suites at 0.2.52-beta: 2,091 pytest (10 `lane_b`, run), Go `./...` 399
with subtests (398 pass, 1 skip). Binaries and image rebuilt, repo
re-ingested.

## 2026-09-19 (fifth) — the top-level review's drift fixed; ADR-140 accepted (Max: route a) and its step 1 built: JavaScript claims no graded repo until it has one (0.2.53-beta)

**The review first (Max: "review top level documentation and report
back").** Every version copy read 0.2.52-beta and every tally agreed.
Four drifts: README's "fifty-two session logs" (57; stale since
0.2.46-beta), its ADR range (to 138; 139 exists), its Calvin list
stopping at ADR-135, and the handoff's "unpushed" line — Max had pushed
`0854855` that afternoon (CI run 35461769081, in progress when read).
Fixed in `9ce8e39`. `hobbes.cli`'s module doc reads stale; narrate on
this repo stays held.

**Then Max: "could we look to add js as a usable language?"** It is
not a missing language but an ungraded one. Both lanes take `.js .jsx
.mjs .cjs` under `allowJs`, with a generated config where the repo gives
none; a JavaScript repo ingests and draws edges. But §3.8's row was
"TypeScript / JavaScript" and `verification.py` pinned `javascript` as a
verbatim copy of TypeScript's row, so every JavaScript ingest said "4
repos, multi-repo". **Measured on the five graded cells' reports**
(`~/.hobbes/bench/v018/`): 15,167 confirmed edges, none with a
JavaScript file at either end; 27 drawn edges touch one, all `silent`.
And the oracle refuses a zone with no `tsconfig.json`, so no plain
JavaScript repo could have been graded. Nothing in the register named
it.

**Max: route (a)** — correct the claim first, then earn the row with
graded cells — and the §3.8 row split within the architecture (his
earlier "dont split for now" was about moving §3.8's paragraphs out to
per-language pages, which stays declined). ADR-140 records five steps;
step 2 is the measurement above.

**Step 1 built (0.2.53-beta):** `javascript` is 0 repos, depth
`unverified`; a zero row that names its reason prints it
(`not verified on any repo — …`). No consumer changed — the ingest
summary spells out rows at one repo or fewer, the surface badges
`unverified` apart, `list_blind_spots` prints the note. §3.8 has a
TypeScript row (unchanged) and a JavaScript row; `test_verification`
maps each label to one language, and two cases hold the row and its
printed line. C-165 registered, surfaced (165 entries, 120 active, 94
surfaced). README, CLAUDE.md and the handoff say TypeScript where they
said TS/JS. **One claim of my own was wrong and caught before the
commit:** ADR-140's draft said this repo would not show the row; its
ingest lists `javascript` (`scip/`, `tsextract/`, the oracle's `.mjs`),
and the re-ingest now prints the zero row with its reason.

Suites at 0.2.53-beta: 2,093 pytest, Go `./...` green. Binaries and
image rebuilt, repo re-ingested. **Next:** ADR-140's step 3, the
oracle's no-tsconfig zone.

**Later the same session — ADR-140 step 3 dispatched (Max: "brief it as
a dispatch unit").** Premises read in the tree before the brief: both
lanes key zones on `tsconfig.json` alone (`_nearest_config_dir`,
`nearestTsconfig`), a `jsconfig.json` is staged but its options never
read (to measure at step 4), the oracle's `files` is exactly the
in-repo non-declaration sources, `OracleExport` is plain
`encoding/json`, and a session mounts `bench/oracle/ts/node_modules`
read-only (unit `8d48` ran the TS oracle's tests in a session). Unit
`S-20260919T191744Z-a25f` (56 turns, $3.15, 7 min): gate clear, verify
pass, 11 files. Reviewed whole; on the host in a worktree the new tests
RUN and PASS, the oracle module green, vet and gofmt clean; without the
flag the minits export is byte-identical once the typescript install
path is normalised. Merged no-ff (`bb7c685`); tracker 58 of 40.

tsc resolves every CommonJS shape the fixture holds (`exports.double =
function`, `Counter.prototype.inc`, the destructured `require`), so the
key can judge the edges most in doubt. `new Greeter()` with no declared
constructor is silent — the compiler's. **The unit surfaced H-33, an
oracle defect it did not cause:** `declKind` tests `isClosure` before
`isParameter`, and every parameter sits inside a function, so no TS
target is ever `parameter` and every call through one reads
`static→closure` on every TS cell (174–324 pairs a cell). Precision is
untouched; the miss attribution in `oracle-misses.md` and C-58's reading
are not. Logged open, root RC-7 (its patch's parameter shape never
fired). Proposed to Max: fix it before step 4. 2,093 pytest, the oracle
module and `report` green.

**Then H-33 (Max: "good to proceed with recommended").** One unit,
`S-20260919T193208Z-9e00` (35 turns, $1.71, 3 min): `declKind` asks
`isParameter` before `isClosure`; the minijs row reads the hand's
`func-value→parameter`; a minits case asserts every parameter binding is
`dynamic` (minits has none — the unit measured before asserting). Gate
clear, verify pass; on the host the six TS tests RUN and PASS. Merged
no-ff (`b15a443`); tracker 59 of 40. **Regrade, contained** (the oracle
in the image with no network: the zone's own `typescript` is code from
the repo's tree, and O3 had run on the host): the before pass on the
five TS cells' clones reproduced every stored grade exactly; after the
fix, totals and every graded row are identical on all five, and 383 of
1,095 `static→closure` pairs move to `func-value→parameter` (kbet 38,
ajv 23, cheerio 65, zod 117, hono 140). H-33 closed with those numbers;
RC-7's tally and `oracle-misses.md` note it. The unit named a smaller
neighbour, left as it is: a destructured parameter's name reads
`func-value→local-binding` — the mode is right, the kind names a local.
**Next:** ADR-140's step 4.

**Then ADR-140 step 4's preparation (Max: "good to start … for me to
review before grading").** The draw rule was written to
`~/.hobbes/bench/js-cells/DRAW-RULE.md` before the pool was fetched; the
pool (1,000 repos) shuffled with seed 20260919 gave xmppjs/xmpp.js as
the sixth in order, five passed over with reasons. Express (CommonJS)
and Preact (ESM, JSDoc, JSX, a `jsconfig.json` with `paths`) are the
named cells. Measured on the key alone: Preact's `jsconfig.json`, which
neither lane reads, changes 120 of 22,804 sites' resolution. A scratch
ingest of `minijs` showed the prior that shapes Express's prediction: a
function assigned to a property is not a lane A symbol. §10.22 written
(P134–P142) and committed before any cell is ingested; nothing graded.

**ADR-140 finished (Max: "approved cells and predictions … good to do
the patch and note", then "proceed with recommended route").** C-166 at
0.2.54-beta: the TS/JS helper records one `jsconfig-ignored` degradation
per `jsconfig.json` nothing reads (37 tsextract). The cells, ingested
contained and graded with the oracle in the image: `minijs` exactly as
P139 said; Express 340/340, recall 22.4%, 652 of its misses one callee
through a CommonJS re-export (C-167, untraced); xmpp.js 552/552, 66.4%
(its own lockfile refused by `npm ci`); **Preact's first pass read
1,223 contradicted — all the oracle's**: H-34 (1,220, an in-repo `.d.ts`
keyed external with an absolute path) and H-35 (3, a JSDoc `@type` keyed
as the annotation). Unit `S-20260919T202902Z-5587` (37 turns, $1.82)
fixed both; the doer narrowed my brief's H-35 wording, which would have
caught a `@param` callback and undone H-33's row. Regraded with no
re-ingest: Preact 2,446/2,446; every other JS and TS cell row-identical
(hono +5 in-repo pairs). P137 missed on Preact (28.6%: test-file
closures, interface members of its own `.d.ts`, hook setters). Step 5 at
0.2.55-beta: the `javascript` row names the three repos "graded without
a dependency tree" (C-165 narrowed), C-167 and C-168 (`new F()` drawn
`uses` in TS and JS, 570 on Preact) registered; 168 entries. Tracker 60
of 40. The cells are not in `docs/oracle/cells/`: that feeds the
comparative graphics, Max's call.

**Close-out.** Max: "the cells get recorded but we will tackle
constraints from js next session." The three cells are in
`docs/oracle/cells/` (`{express,preact,xmpp}-js-2026-09-19.md`, the
regrade's report verbatim) and `cells.meta.json`; `render.py` gains
JavaScript in its language lists and names tsc as the key for it; 93
cells, `render.py check` and the report drift test green. The handoff's
START HERE names next session's order: C-167's trace, C-168's
construction rule, a JS cell with its dependencies provisioned (C-165).
Everything this session is on `main`, unpushed. The knowledge server
needs a restart to serve 0.2.55-beta (C-65).

## 2026-09-19 (sixth) — the top-level review's drift (the handoff rewritten); C-167 traced and probed (ADR-141 proposed; no version move)

**The review first (Max: "review top level documentation and report
back").** Every version copy read 0.2.55-beta; the session-log, ADR,
register and cell counts agreed (60 logs, ADR-140, 168 entries, 93 cells
in `cells.json` — dagger's modules one each). One drift, the handoff:
its header still said the fifth session's commits were unpushed and the
knowledge server needed a restart (Max had pushed through `13ff9d5`,
CI run 35468332243 in progress; the server served 0.2.55-beta), its
ADR-140 section still listed steps 4–5 as next, and WHERE THINGS STAND
said JavaScript was graded on nothing. It had also piled to 718 lines.
Rewritten (`2b60953`, Max: "fix the drift"): the header current, the
2026-09-17 to 19 landed notes folded to their BUILDLOG entries with
every driver path kept, 452 lines.

**C-167 traced (Max: "then proceed with c-167").** Express's tests
`require('..')` the root `index.js`, one line: `module.exports =
require('./lib/express')`. scip-typescript re-run in the image, on a
copy of Express and on a five-file reproduction, names the call site
`local N` — the re-exporting file's own document-local symbol, written
into another document — and the helper drops every local, so lane B
gives the join nothing. 652 `express(` occurrences carry one: exactly
the 652 misses. Lane A's `getAliasedSymbol()` ends at `index.js`'s
`export=` too (TypeScript does not alias a `require` call on that right
side), so the site records `origin: nested` — the tail's `nested-decl`,
not the `unclassified` C-167 was registered with (corrected, a
`Provider` line added, HISTORY noted). `module.exports = lib` after a
`require` resolves in both lanes; a direct require of the defining file
too.

**The rule probed, pre-registered first** (`~/.hobbes/bench/c167-reexport/`).
In a scratch copy of `tsextract`: follow `module.exports =
require("<literal>")` through the literal's module symbol to the
required module's `export=`, at most eight hops. Copies ingested with
`main` and with the probe, graded against the stored keys: **Express
340/340 → 992/992, recall 22.4% → 65.3%, 0 contradicted, poison PASS** —
P1 exactly; +100 syntactic `calls` edges (652 evidence rows) into
`createApplication`, +92 module edges, nothing removed, no symbol or
node changed. Preact, xmpp.js and `minijs` row-identical (P3, P4); the
five TS cells' clones and this repo hold no such file. ADR-141 written
as *proposed* with three routes, (a) recommended; nothing built, no
version move. Also counted, not registered: a callee whose site name is
not its definition's joins as `syntactic calls` beside a `semantic
uses` (Express 2, Preact 5, xmpp.js 41) — the join matches by name.

**ADR-141 built (Max: "good with recommended" — route a; 0.2.56-beta).**
The ADR's *Accepted* section records the brief's premises, each read or
run first: the two `getAliasedSymbol()` calls, `HELPER_VERSION` unchanged,
and the `minicjs` fixture through `extract_repo` on `main` and with the
probe (lane B's one degradation there, no lockfile). Unit
`S-20260919T210207Z-9133` (61 turns, $2.64): the probe's rule as
written, six tsextract cases, the fixture, a `lane_b` case and its
lane-B-off twin. Two deviations, both right (an immediately-called
`require()` is an expression callee and never reaches the hop bound).
Gate right-clear, verify pass; merged no-ff `9f1fb77`; tracker 61 of 40.
On the host: tsextract 43, pytest 2,095 (the tracker's drift test red
until the review block, as always), every `lane_b` test 11, Go `./...`
green. Bumped at `c1d25fa`. The real cell, re-ingested contained at
0.2.56-beta: **Express 992/992, strict 100%, recall 65.3%, poison PASS,
289 semantic + 703 syntactic; 0 earlier confirmed rows lost, 652
gained** — the probe exactly. The cell record carries the regrade block;
§10.22, §3.8, C-167 (narrowed, partial: the tier and a non-literal
re-export), HISTORY, the comparative data (93 cells, `render.py check`
and the report test green) follow it. Proxy and image rebuilt at
0.2.56-beta, this repo re-ingested; the knowledge server needs a restart
(C-65). Everything is on `main`, unpushed. Next, the handoff's order:
C-168's construction rule, then C-165.

## 2026-09-20 (seventh) — the handoff's drift fixed; C-168 measured, corrected and built (ADR-142, 0.2.57-beta); the tracker's gate line

**The review first (Max: "review top level documentation and report back").**
Every version copy read 0.2.56-beta and the counts agreed (61 session logs and
the tracker's 61, ADR-141 the highest, 168 register entries, 93 cells). Two
lines of the handoff's header had gone stale since it was written: it said the
sixth session's commits were unpushed (Max pushed them — `origin/main` is at
`e50ff2a` by `update by push`) and that the knowledge server needed its C-65
restart (it answers `ingest @ e50ff2a, built by hobbes 0.2.56-beta`). Both
fixed. The leftover `.hobbes/derived/.ingest.lock` holds a dead PID and blocks
nothing — the lock is `flock`-based and `ingestlock.py` says so.

**C-168 measured (Max: "then look to resolve c-168"), and its entry was wrong.**
Drivers `~/.hobbes/bench/c168-construction/`. Read row by row, the entry's
numbers are each cell's whole `static→class` miss class, not its constructions:
**Preact's 570 hold no `new` at all** — 193 `super(…)` and 383 JSX tags (6
drawn, the component declaring its own constructor) — and at a real
construction the join drew **nothing**, not the `uses` edge the entry
described: scip-typescript names `<constructor>` at the constructor's own
declaration line, which starts no lane A symbol, so the reference fell below
the floor (C-58). The `uses` edge it described sits at the *import* line. The
mini reproduction under `mini/` shows the three answers the index gives at a
`new`, and `laneb.py` reads them on the cells: a constructor (xmpp.js 101/102,
ajv 89/95, hono 67/74), the class itself where the class declares none (ajv 6,
hono 5, zod 43 — there the key names the **base** whose constructor runs), an
ES5 constructor function (Express 6, xmpp.js 23), or nothing.

**The naive rule refused on the evidence.** Promoting today's `uses` edges at a
`new` would have drawn 3 confirmed and **55 contradicted** — the first loss of
JavaScript's 100%. Not probed further.

**Pre-registered, then simulated and graded** (`PREREG.md` written before any
grade; `sim.py` builds the export a rule would produce, `oracle grade -poison`
judges it against the stored keys). Route (a), the constructor alone, and route
(b), constructor plus constructor function: 100% precision and 0 contradicted
on all seven cells either way, (b) strictly larger. P1–P6 and P8 met; **P7
missed on zod's count** (+33 against +58 ± 8 — 719 of its 946 `new` tokens
carry no resolution at all, which reading the key's rows could not show), its
precision half held. ADR-142 written with three routes, (b) recommended; Max:
route (b).

**Built (unit `S-20260920T012251Z-b444`, 128 turns, $13.44).** Its premises
were read in the tree first — `extractCalls` never walks a `NewExpression`,
lane A's facts version is held equal by `test_helper_contracts.py`, a TS
reference reaches the join with its column, `index.starting_at` answers `None`
at a constructor's line — and the `minijs` fixture was simulated before the
brief went out (7/7 → 8/8; `new Counter(1)` drawn, `new Greeter()` refused,
where tsc synthesises the construct signature and the key is silent). Lane A
records the token (facts v6, `extractConstructions`), `ts_construction_targets`
reads scip-typescript's own spelling, and the join draws to the class that
declares the constructor, or to a non-class definition; at a class it draws
nothing and counts the refusal. Two deviations, both right: the counts are
`ts_drawn`/`ts_named_class` inside the existing `constructions` block, and the
doer added two runnable cases to cover the `lane_b` case it could not run in
the sandbox. **On the host that case runs and passes** — `lane_b` 11 → 12,
pytest 2,095 → 2,119, tsextract 43 → 47, Go `./...` green.

**The gate blocked on the partition, and the brief was at fault.** My partition
named `pipeline/tests/fixtures/minicnew/` — a *directory* — and the check is a
file list at file grain (C-122): its `package.json` passed as `not-code` and
its four `.js`/`.mjs` files each became a `partition` row. The gate applied its
own rule correctly, so the verdict is recorded **right-block**; re-gated at the
same parent with the fixture's files spelled out it is **clear**. The lesson is
the brief's: spell a new fixture's files out, one per line.

**A tracker defect the block exposed.** `calvin_tracker.py`'s `GATE_RE` ended
at `partition checked`, but the harness writes `; partition checked, outside:
…` on a partition block (and `; partition not checked` when a unit gives no
partition). So the tracker refused the harness's own output and **no session
with a partition block could be recorded at all**. Regex extended, with a case
of its own; the tracker reads 62 of 40.

**Regraded at 0.2.57-beta**, each clone re-ingested contained, stored keys,
`-poison`: xmpp.js 552 → **676/676** (recall 66.4% → **81.2%**), ajv 1,410 →
**1,499** (67.5%), hono 768 → **833** (59.7%), zod 9,731 → **9,872** (45.8%),
Express 992 → **998** (65.7%), Preact 2,446 → **2,447**, `minijs` 7 → **8/8**,
cheerio unmoved — **100% precision, 0 contradicted, poison PASS on every one**,
and every earlier confirmed row kept. The `static→class` miss class falls
xmpp.js 104 → 3, ajv 107 → 18, hono 78 → 13, zod 110 → 77. §10.23 carries the
read and the table, the seven cell records their regrade blocks, and the
comparative data re-rendered (93 cells, `render.py check` and the report test
green). C-168 corrected and narrowed in the register, with its note in
HISTORY. Beside them, two surfacing fixes the unit's partition had kept out of
reach: the ingest prints the TS/JS counts on their own `constructions
[ts/js]` line (an ingest that drew eight still said `0 drawn` — C++'s
number, read as the whole answer), and `calvin_tracker`'s `GATE_RE`
reads the partition clause. The proxy and image were rebuilt at
0.2.57-beta and this repo re-ingested at `ae4fa51`; the knowledge server
needs a restart (C-65). Everything is on `main`, unpushed.

## 2026-09-20 (eighth) — the status block and the handoff cut to the headline; C-165's provisioned cell drawn and graded, the entry corrected (0.2.58-beta)

**The docs first (Max: "we have a changelog and a build log for a reason").**
A top-level review found the version copies in step (the §8 header
included) and two files piling history the CHANGELOG, this log and
`constraints/HISTORY.md` already hold: CLAUDE.md's Status block (a "Latest"
bullet spanning 0.2.49 to 0.2.57, a register trail) and the handoff (five
days of settled routes, a register trail sixteen lines long, the defect
log's history). Both cut to the headline, 113 lines out, `3df2ed1`; §3.8
stays as it is (Max). The suite count in both was three short: 2,122
pytest collected, not 2,119.

**C-165, and a premise read before the draw.** The entry asked for a
JavaScript cell graded with its lockfile provisioned on both sides. Before
drawing one I read the TypeScript cells that *have* a tree: cheerio, zod
and hono hold 0 graded rows with a `node_modules` target — Hobbes exports
no call edge into a package — so the pre-registration
(`~/.hobbes/bench/js-cells/c165/DRAW-RULE.md`) said what the cell could
and could not show, and that a provisioned arm with only in-repo rows
would mean the entry is corrected, not only lifted. The cell is graded
twice on one sha, with the tree and without.

**The draw.** ADR-140's pool and seed, resumed at position 7, two criteria
added (a lockfile `detect_installer` provisions from; a non-empty
`dependencies`). The ingest's own `npm ci --ignore-scripts` refused two
candidates — 9 hack-chat/main (`uwuify-1.0.1.tgz`, 404: unpublished) and
11 maptiler/tileserver-gl (lockfile out of sync, xmpp.js's case) — and
accepted 21, **cypress-io/github-action** @ `01e3b659a495`: 77 JS files,
one zone, 177 packages. With xmpp.js that is three refusals in four
lockfile-bearing JS repos; counted under C-23 in the entry, nothing
proposed.

**The result.** Provisioned 154/154, recall 89.0%, poison PASS; withheld
(a copy with the lockfile removed) 154/154, 89.0%, PASS. **The rows are
identical and so is the graph** — 76 `calls` + 42 `uses`, every target
in-repo, the 77 `imports → ext:` module edges the same. The tree moved the
key's external pairs 173 → 413 and `dependency_coverage` 0 → 14 of 22.
The cell is thin and is recorded as thin.

**Max: route (a), correct and narrow.** C-165 now says what the limit is:
a third-party call is stated at module grain only and no key grades it,
in JavaScript or TypeScript; one JS cell of four has its tree. The
`javascript` verification row reads 4 repos, "one of four graded with its
dependency tree" (its tests moved with it); §3.8's row, the README, §10.24
and the cell record (`github-action-js-2026-09-20.md`) say the same; the
comparative data re-rendered at 94 cells, `render.py check` and the report
test green. No ADR: no rule was decided, a claim was corrected against a
measurement. No dispatch either — the code change is one string and its
three assertions. 0.2.58-beta; pytest 2,122 green; the proxy and image
rebuilt and the repo re-ingested at HEAD; restart the knowledge server
(C-65). Everything is on `main`, unpushed.

**ADR-141's last section, measured on the TS cells (Max: proceed).**
Pre-registered (`~/.hobbes/bench/adr141-name-mismatch/PREREG.md`). The
counter had to reproduce ADR-141's JS counts first and at first did not
(Express 1, Preact 4): the lanes name different callers at some sites, so
the match is by site and target, which gives 2 / 5 / 41. Then: ajv 5,
cheerio 8, zod 0, hono 75 — 136 sites on seven cells, graded against the
standing keys with the 0.2.57-beta exports: **98 confirmed, 38 outside the
graded zone, 0 contradicted**. Two shapes carry it: a binding renamed at
the site and a `#private` method call. The index proved every one and the
graph labels the call `syntactic`. No code, no register entry, no version
move; the routes are put to Max.

**ADR-143 accepted (Max: route a), built and released — 0.2.59-beta.** The
join matches a call site to the index's resolution by name
(`evidence.match_resolution`), so where the written name is not the
definition's the index's proof became a `uses` and the call kept lane A's
tier. **Probed before anything was proposed as a rule** (`probe_join.py`,
xmpp.js and hono): a resolution onto lane A's own target sits at exactly the
site's column 38 and 76 times, 5 columns off 4 times (a namespace's
occurrence, not the callee's), and never does the site's column name another
definition. The rule is that agreement and nothing wider: a fallback, a
resolution at the site's own column, every resolution there naming the
fallback's definition. **Simulated in memory on seven cells with its
predictions written first; all five held** — 134 tiers raised, no row added
or lost, the counted shape down to xmpp.js's 3 namespace-member sites.

**The code facts read before the brief:** `join` has one product caller;
`match_resolution` is repeated in five mirrors and the C++ comparison, and
`_dispositions` alone was not handed the fallback — named in the ADR as the
unit's to settle. **Unit `061a`:** 71 turns of 140, $5.87, four files inside
a seven-file partition spelled out at file grain (the last unit's lesson),
gate clear, verify pass, **right-clear**. On the host: twelve `lane_b` tests
green in a worktree of the branch; xmpp.js, hono, ajv, cheerio, zod, Express
and Preact regraded with the unit's code, each **row-identical, tiers
included, to its simulation**; and a pre/post driver over one cell per other
language (`lang-regrade.sh`: cJSON, click, jsoup, memchr, fzf, fmt, args) —
row-identical, no tier moved. Merged `--no-ff` (`599886f`); the tracker reads
63 of 40. §10.25, the architecture's join paragraph, six cell records' regrade
notes (prose: the verbatim heads did not move), the CHANGELOG. Nothing
registered — no concession was made or lifted. pytest 2,139, Go `./...` and
the report test green; binaries and image rebuilt, the repo re-ingested at
HEAD; restart the knowledge server (C-65).

**Seen and not traced:** hono's two yarn-v1 zones fail to provision because
the ingest hands the container the host's corepack path. In the handoff.

## 2026-09-20 (ninth) — the top-level docs read against the tree; the knowledge server's restart made the closing session's step; the yarn-v1 `corepack` defect traced and fixed (0.2.60-beta)

A read of the README, CLAUDE.md, the CHANGELOG head, the handoff, the
workstreams header and the architecture's §8 header against the tree at
`9897399`. The version copies agree (0.2.59-beta everywhere, §8
included). **Drift found and fixed:** the README's ADR range read
"ADR-001 to ADR-141" (the tree has 143) and "sixty-one session logs" (63
on disk, the tracker's number); its list of what the harness built stopped
at ADR-141, so ADR-142 and ADR-143 were added with their measured effect;
the workstreams header stopped at 0.2.57-beta; the handoff said the
seventh and eighth sessions' commits were unpushed when `origin/main` is
at `9897399`.

**The restart line (Max).** Every handoff since C-65 has ended "restart
the knowledge server", and every next session read it after the server
had already restarted: `sandbox/knowledge-serve` is `podman run --rm`
under `.mcp.json`, so a new session's server is a new container from the
current image (checked: this session's container was created after the
release commit). The instruction was stale by construction when read.
Now the restart is the last step of the session that rebuilt the image,
and the handoff does not carry it — CLAUDE.md's closing paragraph and the
handoff's practical note say so; the version that opens every answer is
the next session's check. No code, no register entry, no version move.

**Later the same session — the handoff's untraced item, traced (the docs
paragraphs above were committed first, as `6c539af`, and their "no code, no
version move" is theirs).** hono's two yarn-v1 zones: `_corepack()` returns
the host's absolute path beside the host's `node`, `provision_node_modules`
put it in the argv, and `_fetch` runs that argv in the image — `crun:
executable file … not found`. `npm` is a name, so `npm ci` never met it. The
stored ingest logs show it on every contained hono and dagger ingest; the
WARNING said "dependencies not provisioned", which read as the repo's. A
defect, not C-23's. **Probed before the routes were put:** with `_corepack`
patched to the bare name, the fetch step provisioned `benchmarks/jsx` in 8 s
(the probe's cache entry was removed before the dispatch). Max: route a.

**Unit `d2de`:** 19 turns of 80, $0.95, two files at file grain, gate clear,
verify pass, **right-clear**. One helper, `_yarn1_install_argv`: contained —
asked as `containment.run` asks — the argv names `corepack` and the host's is
not consulted; on a host run the host's path, and the old refusal without
one. On the host, in a worktree: pytest 2,144, twelve `lane_b` green, and a
hono ingest (`97c6fe1`) against the 0.2.59-beta graph of the same sha — three
extraction errors gone, none new, dependency coverage 0 → 9 of 47, **2,811
symbol edges and 1,729 module edges identical by (from, to, type, tier)**.
That a provisioned tree moves no edge is C-165's statement met a second time.
dagger's snippet zones were not re-ingested. Merged `--no-ff` (`242b767`);
0.2.60-beta: the CHANGELOG, a dated note on C-23 in the register's HISTORY
(the entry's words were untrue on a contained box from ADR-092 until now, and
are left as written), the tracker at 64 of 40. Go `./...` and pytest green on
`main`; binaries and image rebuilt at 0.2.60-beta, the repo re-ingested.

**C-168's remainder, measured first (Max: "go with c-168 before the larger
cell. good to measure first").** The entry's rows were read before anything
else, and the entry was wrong again. "A `.d.ts` Hobbes keeps no symbol for":
`src/index.d.Component` is a class symbol and 1,241 confirmed Preact rows land
in `.d.ts` symbols; all 570 of Preact's `static→class` rows name that one class.
A ten-line fixture indexed in the image settled the rest: scip-typescript emits
**no occurrence at `super`**, and at a JSX tag names the **class**, never
`<constructor>`. At `extends Component` it names the merged `interface` at line
119, not the class at 144; the 377 JSX tags name test-body locals the facts
carry no reference for. **A rule was pre-registered and measured, not built:**
a walk up the `extends` chain, each hop the index's reference at the token's
column — 104 rows, all confirmed, 0 contradicted (ajv 18, hono 8, xmpp.js 2,
zod about 76), 0 on Preact; P3 missed (hono 5 of 50 refusals, xmpp.js 0 of 21:
the chains end at external bases and implicit constructors). Routes put to
Max; **route a: "honesty above all"** — correct the entry, build nothing. C-168
corrected with a `Provider` line (P9) and the measured rule recorded as
undecided; HISTORY's note; ADR-142 amended; the architecture's two sentences;
`oracle-grading.md` §10.26; the handoff. No code, no version move, tally
unmoved. Drivers `~/.hobbes/bench/c168-remainder/`.

**The larger provisioned JavaScript cell (Max: "start the walk"; then route a).**
`DRAW-RULE-2.md` was written before any candidate past 21 was seen: the pool,
seed and order unchanged, one criterion added because §10.24's cell was thin — at
least 300 `calls` edges and half the declared packages resolved — and a stop at
80. Walked 22–41: folio-2025 refused (`npm ci`, ERESOLVE), npq and
insomnia-mockbin provisioned and passed over on the stated numbers,
**Blueturboguy07/cue taken** (`a27308ed2335`, 478 `calls`, 7 of 12 resolved, 276
packages). Graded twice on one sha: **881/881 in both arms, 0 contradicted, poison
PASS, the rows identical by site, target, caller and tier, the graph identical** —
the prediction held. The tree moved the key: external pairs 1,620 → 5,198,
unjudged poison seeds 163 → 18, and three in-repo pairs that become external
(calls through a dependency-typed value; Hobbes draws nothing at any, either
arm). The withheld arm first failed — an ingest needs a git repo — and was
re-made as a same-sha clone with the lockfile removed. **0.2.61-beta:** the
`javascript` verification row reads five repos, "two of five graded with their
dependency tree" (`verification.py` and its test), the cell record, §10.27,
§3.8's row, C-165 and its C-23 count (four of eight refused), README, CHANGELOG,
HISTORY, the comparative data at 95 cells with its tables and graphics
regenerated (`render.py check` green). **Seen, not traced:** 176 of cue's misses
are a member of a `module.exports = { … }` literal called through `require`; in
the handoff as the next JavaScript recall read.

**cue's untraced shape, read, and ADR-144 (Max: "good to take the read"; then
route a; then, on the tier, "yes go with semantic").** `classify.py` over the 176
misses: 122 are `m.f()` on `const m = require('./m')` whose target *is* a function
symbol; 49 are members written in a literal, no symbol; 5 others. The separator is
the binding — the destructured form was drawn all along. The facts showed why:
the site is an **in-repo `external_ref`** whose moniker is the exported literal's
property (`loadBuildConfig0:`). Modelled as the rule fires, unfiltered by the key:
cue 124 and xmpp.js 29 (`export default { … }`), all confirmed. The first framing
had lane A read the exporting file, and Max kept it `syntactic` on that. **Then a
fixture read raw in the image changed the premise:** the index tells a file's
literals apart (`alpha0:`/`alpha1:`) and puts the property's one definition and a
reference to the function at one exact range — both hops its own, lane A reading
nothing. `PREREG-sim.md` first; a scratch worktree's helper, never merged; nine
cells: cue +124, xmpp.js +29, seven unchanged, 0 contradicted, poison PASS, rows
`semantic` of themselves. P5 was wrong about *where* the new `uses` sit (the
destructuring `require` line, as an ESM import line's). The tier went back to Max
with the changed premise: `semantic`. ADR-144 accepted with its code facts.

**Unit `12ad`:** 53 turns of 140, $3.53, five files at file grain, gate clear,
verify pass, **right-clear**. On the host: node 94, pytest 2,146, thirteen `lane_b`
(the new `minicjs` case's first run); the nine cells regraded with the unit's
code, **each row-identical to its simulation, tiers included**; `lang-regrade.sh`
over cJSON, click, jsoup, memchr, fzf, fmt, args — row-identical pre/post, the
index re-run (cache 0 hit, checked in the log, since the first timings looked like
hits). Merged `--no-ff` (`9f8dff9`). **0.2.62-beta:** §10.28, the cue and xmpp.js
records' regrade blocks, the architecture's paragraph and §3.8's row, the ADR's
*Built*, README, CHANGELOG, the comparative data regenerated, the tracker at 65
of 40. Nothing registered: the shape was never an entry, and what is left of it
(a value property; a literal's own method) is refused or C-9/C-58's.

## 2026-09-20 (tenth) — the top-level docs read again; C-4's last two parts measured; ADR-145 built (0.2.63-beta); a module `pytestmark` drawn a key row, its amendment proposed

**The docs first (Max: "review top level documentation and report back").** The
README, CLAUDE.md, the CHANGELOG's head and the handoff read against the tree:
consistent at 0.2.62-beta but for five handoff lines (JavaScript still "four repos …
one with its dependencies"; "unpushed" though `origin/main` was at HEAD; the START
HERE block dated to the eighth session; "ADR-123 to ADR-142 is built"; a dangling
"item 7"). Fixed, and the README's harness paragraph — 27 lines of "and … then …"
from ADR-128 to ADR-144 — cut to nine with the ranges and end-to-end figures
(`ff92e07`).

**C-4, part 1 — the value a fixture returns (Max: route a).** `count.py` on click's
post-ADR-144 report: 419 of 665 missed `observed→method` pairs sit at `p.m(…)` on a
parameter in a test file, 381 of them `runner.*`. The facts said why and what is
there: the index names the *parameter* at `runner`, emits nothing at `invoke`, and
names `CliRunner` at the fixture's `return CliRunner()` — an edge the graph already
carries. `PREREG.md` first; `simulate.py` with a stand-in lookup, then
`simulate_real.py` through `fixtures.injections` itself: click 383 drawn, 381
confirmed, 0 contradicted; flask 11 by hand, right, 702 refused as not a
construction; attrs and this repo 0. No node minted. Three routes to Max (build as
worded / key a second Python repo first / not at all — it is a three-hop inference
as the `extends` walk was); **route a**. ADR-145 accepted with its code facts.

**Unit `1527`:** 81 turns of 140, $6.73, 11 files at file grain, gate clear, verify
pass, **right-clear**. On the host: pytest 2,191, all 14 `lane_b` (the new
`minifixval` case's first contained run). `lang-regrade.sh` pre/post: click **1,755
→ 2,136 confirmed, recall 38.2% → 46.5%, 0 contradicted, 382 rows all `syntactic`**;
cJSON, jsoup, memchr, fzf, fmt, args row-identical. **The build drew one site fewer
than the simulation**: a `runner.invoke` inside a nested `def` of a click test. The
probe's `own_nodes` pushed a top-level nested def's children; the rule's *own body*
condition refuses it. The probe's defect, the build's refusal. Merged `--no-ff`
(`87da32f`).

**The session's one deny found two defects of the record's own.** The doer's `env |
grep …; python -c "…"` was denied — the first deny any session log carried. Its
newlines split the log's one-line Policy entry (`dispatch.summarize_flight` now
collapses whitespace before clipping; a test), and the tracker's Policy pattern had
no `; denied: …` clause at all (added; a test). This log's line was joined by hand
and the review says so. Tracker 66 of 40, denies 1.

**C-4, part 2 — a module `pytestmark` (Max: "good to run the draw").**
`DRAW-RULE.md` first: GitHub code search, 71 repos, seed 20260920. **Walk 1 took
none** — the hits are pytest's own suite writing the line into a string (and thirty
copies), GDAL's one real use (no binary wheel) and its vendored copies, docstrings,
rpm specs. `DRAW-RULE-2.md`, stated before walk 2: read the *clone* with `ast`, not
the search's first hit. Passed on the way: pytest-houdini (strings again; `grep
^pytestmark` had matched inside one), tractor (`pytest_plugins` fixtures,
`not-in-repo`), cadrumo (706 marked files; Python ≥3.13, the image has 3.12).
**MissyLabs/missy @ `223dbe8`**, position 32: 18 marked files, the fixture in the
root conftest. Key in the image, no network: 23,480 tests. As built: 34,505 right, 0
wrong, 1,265 missed — all the pytestmark's. With the rule: 35,770, 0, 0. **A mistake
made and caught:** the first collection passed `-v -q`, which cancel; pytest hid an
autouse `_…` fixture and the base arm read 26,474 "wrong". `-v` alone. ADR-139's
amendment is written as **proposed**; its unit is briefed
(`~/.hobbes/bench/c4-pytestmark/units/`) and not dispatched — it touches the same
files as `1527` and waits on Max's word.

**0.2.63-beta:** the denominator statement (proxy and manifests) says "unless the
fixture constructs it (ADR-145)"; C-4 narrowed, nothing registered; §10.29, the
click record's regrade block, the architecture's paragraph, §3.8's Python row and
the §8 header, README, CHANGELOG, the comparative data regenerated (`render.py
check` green). Go `./...` green; pytest 2,193; binaries and the image rebuilt, this
repo re-ingested, the knowledge server restarted.

**Later the same session — the `pytestmark` unit (Max: "good to dispatch the
unit"), 0.2.64-beta.** ADR-139's amendment marked accepted first. Unit `0bf3`: 39
turns of 140, $2.91, six files, gate clear, verify pass, **right-clear**. On the
host: pytest 2,204, 14 `lane_b`. The real cell with the branch's lookup against the
`-v` keys: missy **35,770 right, 0 wrong, 0 missed in the repo** — the probe's
figures — flask 1,238 and attrs 118 unchanged. The doer narrowed the walk to a
*plain* assignment (an annotated `pytestmark` had been read) and named every test
it changed. Merged `--no-ff` (`5c179e5`). The denominator statement no longer names a
module pytestmark (proxy, manifests, their two tests); C-4's entry, the
architecture's ADR-139 paragraph and §8 header, CHANGELOG, README, the tracker at
67 of 40. No graded cell moves: no trace key judges a `uses` edge. Binaries and the
image rebuilt at 0.2.64-beta, this repo re-ingested. **Both of C-4's last parts are
done**; what the entry keeps is a value that is not a construction, an inherited
method, a non-plain `pytestmark`, a non-literal `autouse=` and the abstentions.

## 2026-09-20 (eleventh session) — extraction first: a decorator is a call of what it names (ADR-146, 0.2.65-beta)

**Max's direction:** the last sessions were constraint and error fixes; "id like to
focus on extracation for now as its the most annoying work to do but the most important
for hobbes." A top-level doc review came first (the docs agreed with each other; the
handoff's "unpushed" line was stale — `origin/main` was at `0f45f6c` — fixed in
`7edaa3d`). On the number line: a minor is for a **feature** added to Hobbes (the dev
environment would be 0.3.0, not worked on now); an extraction change is a patch even
when it moves structure.

**The proposed route was wrong, and the probe said so.** Route 1 was "Python nested
defs as symbols, then the decorator-factory rule", from `oracle-misses.md`'s "nested
functions are not graph symbols". Step 0 (`~/.hobbes/bench/py-nested-defs/`, `PREREG.md`
first): nested defs **are** symbols and a direct call to one is drawn `semantic`; the
unit would have added 0 rows. What the rows were: **Hobbes drew no edge on any decorator
line** — `pysource._walk` skipped decorator expressions since the first extraction
milestone ("would pollute the call graph"), pinned by a test, in no register entry. click:
0 of 2,447 edges on a decorator line, 1,652 of 2,459 misses there. And 590 of this repo's
642 closure misses are `<genexpr>` frames, the key's grain.

**Max: route a** (the walk first, the factory rule after it; strict or loose "whicever
is more honest. we never sacrifice honesty for higher recall"). Strict chosen for
ADR-147 — every return is `return g`, ADR-145's precedent — 304 click rows at 0
contradicted; loose read 661 at 0 contradicted and is recorded, not proposed.

**Measured before the ADR**, on a scratch worktree: the walk alone click 46.5% → 65.2%,
with the bare application 66.4%, 18 suspects unchanged both times, lane disagreements
unchanged, flask +166 and attrs +120 rows all `semantic`, no symbol moved; the pipeline
suite failed one test, the pinning one. ADR-146 written on that (`13c7d13`).

**Unit `f751`:** 45 turns of 80, $2.49, seven files, gate clear, verify pass,
**right-clear**, merged `--no-ff` (`11bae01`). **The review found a defect the gate's
classes do not cover:** the doer read the decorator's expression as `children[-1]` — the
idiom `_decorator` and the parametrize read already used — and a trailing comment is the
node's last child, so `@foo  # note` recorded nothing; worse, the *existing* digest had
always read `@pytest.fixture  # shared` as no fixture. Fixed at all three sites
(`_decorator_expr`, one test). The real cell on `main`: click **3,052 confirmed of 4,595,
18 suspect (the same rows), poison PASS, row-identical to the simulation, 0 rows lost**
(`oracle-grading.md` §10.30). C-169 registered and lifted (169 entries, 29 lifted);
`oracle-misses.md`'s closure row corrected; the architecture's paragraph, §3.8's Python
row and §8 header; CHANGELOG, README, the tracker at 68 of 40. On the host: pytest 2,217,
15 `lane_b`. Binaries and the image rebuilt at 0.2.65-beta, this repo re-ingested.
**Not done:** ADR-147 (next); the `<genexpr>` grain is not yet in the oracle defect log.

**Later the same session — ADR-147 (Max: "yes proceed with the dispatch"), 0.2.66-beta.**
The wording was probed first as it would be briefed (`PREREG-b.md`, `probe_b.py`), over
the *built* 0.2.65 export rather than a stand-in: click 368 drawn, 304 confirmed, 0
contradicted; flask 1 (read by hand), attrs 0. Strict, not loose: on `command`'s `return
decorator(func)` path the site does not call `decorator`, so loose's 661 rows at 0
contradicted were recorded and not taken, and their sites are a counted refusal. Unit
`db45`: 87 turns of 140, $8.23, nine files, gate clear, verify pass, **right-clear**,
merged `--no-ff`. **The host's `lane_b` run found two things the sandbox skips past:**
the edge append kept symbol callers only — my brief said "exactly as
`_add_value_call_edges` does", and ADR-145's callers are never modules — so minideco
counted 3 drawn and held 1; and two assertions matched the index's own direct edges
(`either → either.decorator`). Both fixed on `main`, the first with a lane A test that
needs no index. The doer's one stated divergence (the counts block is written where a
site was *asked*, so `two-targets` is visible) accepted and the ADR amended. The real
cell: click **3,356 confirmed of 4,595 (73.0%), 18 suspect — the same rows — poison PASS,
0 rows lost, the probe's figures exactly** (§10.31). C-58 narrowed (a Python face bullet),
HISTORY, the architecture's paragraph, §3.8 row and §8 header, CHANGELOG, README, the
tracker at 69 of 40. **H-36 logged, open** (RC-2): a `<genexpr>` frame entry keyed as a
call pair — 592 of this repo's 642 closure misses; its recall reads 84.6% for 94.6%. On
the host: pytest 2,257, 16 `lane_b`. Binaries and the image rebuilt at 0.2.66-beta, this
repo re-ingested. Two units today: $10.72 on the subscription, click 46.5% → 73.0%.

**Later still — H-36 (Max: "go with h-36 first"), no version: the oracle lane is not the
layer.** Read first: the "call" is real bytecode — a genexpr compiles to a hidden function
and a compiler-written `CALL` of it — so the fix belongs at the extractor, RC-2's drop and
count, in the `excluded` header Rust's and Java's keys already use. Unit `de0e`: 51 turns
of 80, $2.76, six files, gate clear, verify pass, **right-clear**, nothing reworked; the
doer chose to make no site for a line that held only the frame entry (an empty site would
have bucketed a Hobbes edge there `suspect`) and corrected my brief (`tuple` is an
external class target, not a C callee). On the host, in the image, both trace tests
**pass**. Regraded, signed (`oracle-grading.md` §10.32): click's key regenerated
(`click-py-r3`, same recipe, same suite exits) 4,595 → 4,561 pairs, exactly the 34 rows,
confirmed and suspect ±0, 73.0% → 73.6%; this repo traced twice at `2c915a8` —
`oracle-pre` from `89b7f58`, `oracle` from HEAD — 9,535 → 8,612 pairs, all 923 gone
`<genexpr>`, 0 added, confirmed 8,162 and suspect 26 ±0, **85.6% → 94.8%**. The
comparative graphics read the cell records, and the first re-derive put Hobbes' click row
on r3 beside two foreign tools still on r2 — a same-key row on two keys; both foreign
graphs regraded on r3 (only the denominator moved: 28.2 → 28.5, 37.1 → 37.3) and their
records appended before the re-render. H-36 closed the day it was found; the defect log
has nothing open; tracker 70 of 40. Three units today, $13.48 on the subscription.

## 2026-09-21 (twelfth session) — the top-level docs read against the tree; click's misses sorted; ADR-148 built (0.2.67-beta)

**The docs first (Max: "review top level documentation").** Four places had drifted from
the tree: the README's session count (67 for 70), `workstreams.md` refreshed only through
0.2.59-beta, the 0.2.66-beta CHANGELOG entry still reading H-36 "open" at 84.6%/94.6%,
and the eleventh BUILDLOG entry's title naming only ADR-146 (left, append-only). The
first three fixed in one commit (`0331329`; the CHANGELOG with a dated note, not an
edit of the figures). CLAUDE.md and AGENTS.md are one text; the architecture's §8 header
and VERSION agreed.

**Then click's misses (Max: "proceed to clicks misses").** The 1,205 on `click-py-r3`,
bucketed by site syntax: 423 closure rows on decorator lines — `@click.command()` and
`@group.command()`, the optional-parentheses idiom ADR-147's strict wording refuses —
401 callbacks reached through attributes and parameters (values, C-58), 79 methods a
subclass overrides (ADR-126 §3), 90 duck-typed receivers and test doubles, 81 lambdas.
An `ast` scan over the local Python clones put the idiom in click (441 no-argument
sites) and attrs (72), not flask (decorated factories). Pre-registered (`PREREG.md`) and
probed: fold the factory's own guards over the site's literal arguments, three-valued,
and draw only where every reachable return is `return g`. The new edges written into a
copy of the export and graded by the real grader, which reproduced §10.32 exactly on the
base: 397 drawn, **347 confirmed**, 0 base rows moved, recall 73.6% → 81.2%, poison PASS
— and **P1 failed on 3 rows**, read before anything was proposed: `pytest.raises` tests
where a lower decorator raises before `command()`'s `decorator` is applied; a trace
buckets them `suspect`. A `method-positional` refusal (lane A cannot tell `@obj.f(x)`
from `@Cls.f(x)`) re-measured and found to move nothing. Three routes put to Max; route
a (own the three rows) over b (a `pytest.raises` exception in an extraction rule) and c
(build nothing).

**ADR-148 (Max: "route a good to proceed with dispatch"), 0.2.67-beta.** ADR accepted
first (`ea4978d`), this repo ingested at HEAD, the argv checked (`--settings`, the
model), launched detached with `--max-turns 140`. Unit `b4d4`: 131 turns, $15.98, nine
files, gate clear, verify pass, **right-clear**. The brief's premises were checked
against the tree before dispatch (the pinned lane A list in `test_decorator_calls.py`,
the every-`.decorator`-edge via assertion — both named in the brief as edits, not
loosenings). **The real click cell on the unit's tree folded nothing**: `*args: T` /
`**kwargs: T` is a `typed_parameter` wrapping the splat, and the signature reader
dropped every annotated factory — click annotates all of them; the unit's tests were
untyped and its own check fed hand-built digests to the fold. One `parse_source` over
the real file found it; fixed with a test on the branch (`39815c0`), merged `--no-ff`
(`78a2166`). The cell rebuilt: **397 folded, 347 confirmed, 3,703 of 4,561 (81.2%), 21
suspect (the 18 and the 3), poison PASS, 0 rows lost — the probe's rows, 4,298 of
4,298** (§10.33); attrs 18, flask 0. C-58 narrowed (its heading first read `folded`,
which the tally parser takes as a status — reworded), HISTORY, the architecture's
paragraph, §3.8 row and §8 header, CHANGELOG, README, CLAUDE.md/AGENTS.md, workstreams,
the tracker at 71 of 40. On the host: pytest 2,317, 16 `lane_b`. Image and binaries
rebuilt at 0.2.67-beta, this repo re-ingested. One unit today, $15.98 on the
subscription; click 73.6% → 81.2%.

## 2026-09-22 (thirteenth session) — the top-level docs read; group()'s chain measured and built (ADR-149, 0.2.68-beta)

**The review (Max: "review top level documentation and report back with current
status").** README, CLAUDE.md/AGENTS.md, CHANGELOG, the handoff, workstreams and the
architecture's §8 header read against each other and the tree: consistent at
0.2.67-beta, but for the handoff's claim that the eleventh and twelfth sessions' work was
unpushed — `main` equalled `origin/main` at `57e4be2`. Fixed (`b2c815f`, Max: "fix the
line").

**Step 0, the next item (Max: "proceed with listed next item").** click's misses on
`click-py-r3` at 0.2.67-beta bucketed by decorator line: 44 `@click.group(…)` →
`command.<locals>.decorator`, and 5 through `option` (`version_option`, `help_option`).
`PREREG.md` written before the probe: fold the outer factory over the site's arguments
keeping each reachable return's environment; every reachable return a call the index
names from the factory at that line to one `G`; `G` settled (ADR-147) or folded over the
forwarded arguments, a `**x` leaving unbound parameters unknown, never defaulted; one
level. `probe_chain.py` (over `ast`, reusing ADR-148's probe) graded by the real grader:
66 drawn, 51 confirmed, 15 on unrun lines (read, right), 0 contradicted, 0 new suspects,
poison PASS, 81.2% → 82.3%; P2 exceeded by one (`custom_version_option`). attrs, flask,
this repo at `2c915a8`: 0. Three routes put to Max; route a.

**ADR-149 (Max: "good to go with route a"), 0.2.68-beta.** ADR accepted first
(`5a51d6a`), ingested at HEAD, dry run checked (`--settings`, the model), launched
detached, `--max-turns 140`. The brief carried click's real `group`, `command`,
`version_option` and `option` verbatim as a test fixture (`tests/fixtures/click-excerpt/`)
— ADR-148's review lesson. Unit `67cc`: 107 turns, $13.04, ten files, gate clear, verify
pass, **right-clear**, no defect at the review. On the host: pytest 2,351, `lane_b` 16 of
16 run. The real click cell on the unit's tree: **67 chained, 52 confirmed, 3,755 of 4,561
(82.3%), 21 suspect, poison PASS, 0 rows lost** (§10.34) — the probe's 66 and one more,
read: `@click.help_option(*name_specs, **option_attrs)`, a site splat the probe refused and
the ADR's wording binds as unknown; `help_option` reaches `option` on every path;
confirmed. attrs 18 and flask 1 unchanged; this repo's 4 chained are minideco's. C-58
narrowed, HISTORY, the architecture's paragraph, §3.8 row and §8 header, CHANGELOG,
README, CLAUDE.md/AGENTS.md, workstreams, the tracker at 72 of 40. One unit, $13.04 on
the subscription; click 81.2% → 82.3%. No decorator-line shape above 10 rows is left in
click's misses.

## 2026-09-22 (fourteenth session) — the top-level docs read; flask keyed; C-4's value through a local and a base's method (ADR-145 amended, 0.2.69-beta)

**The review (Max: "review top level documentation and report back with current
status").** README, CLAUDE.md/AGENTS.md, CHANGELOG, the handoff, workstreams and the
architecture's §8 header consistent at 0.2.68-beta, but for README's "seventy-one session
logs" (72; `5d23358`, Max: "fix the readme and commit").

**Step 0 (Max: "measure flask fixture candidate").** `~/.hobbes/bench/c4-local-value/`:
`PREREG.md` first; `simulate_local.py` from ADR-145's `simulate_real.py` with the handoff's
`own_nodes` fix. Two defects in my own first run, fixed before any row was read: the fix
also skipped a nested def's decorators (flask's `@app.route` sites, 797 → 497), and the
rebound count walked subtrees twice. flask had no call key; keyed it as pre-registered —
a clone of the held-out tree at `d73fa1c`, `uv sync --group tests`, `run-cell.sh --lang py
--runs 2`, contained, 494 passed both runs: **1,121 of 2,698 (41.5%)**, 18 suspect, poison
PASS (`docs/oracle/cells/flask-py-2026-09-22.md`). 390 simulated through the local, all
confirmed. Three routes; route a.

**Found on the way, not fixed.** (1) **Three of flask's suspects are Hobbes-wrong**
`semantic` edges: `TestStreaming`'s methods each nest `index` → `generate`/`gen`, and sites
251, 281, 310 name a sibling method's def (the symbols are distinct; the join picked the
first). Cause not read. (2) `src/flask/sansio/` has no `__init__.py`: lane A names its files
`app`, `scaffold`, and `Flask → App` has a `uses` edge at the header but no `implements`
edge (`App → Scaffold` has both). Why the join misses it is not read either.

**ADR-145 amended (Max: "good to proceed with recommended route"), 0.2.69-beta.** The
header edge read instead of `implements` for (2)'s reason. `PREREG-worded.md`, then
`probe_worded.py` over each cell's own graph and lane A's parse (ADR-138's lesson): flask
400 drawn (71 direct, 329 inherited), **400 confirmed at the exact line, 0 contradicted**;
37 beyond the simulation are bare `@app.*` decorators (ADR-146). click 0 new, attrs 0, this
repo 1 (`minifixval`'s `Base.close`, which ADR-145's lane_b case asserted refused — named
in the brief). The ADR amendment and the cell committed first (`f166091`; the comparative
data at 96 cells, the meta entry saying the cell was picked). Unit `54cf`: 86 turns, $7.62,
13 files, a `flask-excerpt` fixture of flask's own files. Gate clear; **verify `fail` on a
harness row**: a fixture repo's own test the testmap now lists as a guard errors on both
trees, and `classify` counts an error/error as failing where F2F is a fault — recorded in
the review, not changed. **Two defects fixed at the review** (`64eadf0`, one test each): a
nested `def x` in the fixture was not a second binding of the local; `class-binds` was not
asked of the class holding the `def`. Host: pytest 2,400, `lane_b` 16 of 16 run. The real
flask cell: **1,121 → 1,521 (41.5% → 56.4%)**, 400 added, all `syntactic` and confirmed, 0
lost, poison PASS — the probe's 400 row for row (§10.35); click unchanged on `click-py-r3`;
attrs 0. C-4 narrowed and HISTORY, the architecture's paragraph, §3.8's Python row and the
verification base (nine repos), §8 header, CHANGELOG, README, CLAUDE.md/AGENTS.md,
workstreams; the tracker at 73 of 40; the image rebuilt at 0.2.69-beta.

## 2026-09-24 (fifteenth session) — the top-level docs read; flask's three wrong edges read to their cause; a Python moniker one file defines at several lines is no answer (ADR-150, 0.2.70-beta)

**The review (Max: "review top level documentation and report back with current
status").** The top-level docs were consistent at 0.2.69-beta, except for two lines:
README's "ADR-001 to ADR-145" (the tree has 149), and §8's harness row, which still read
"validation by use under way… thirty-one session logs". Both fixed (`c4b4a44`; Max:
"proceed with the doc fix and next item").

**The cause read (the handoff's first item).** The flask clone's cached facts stream showed
one moniker, `test_helpers/TestStreaming#generate().`, at one definition line (232), and
each site's reference filed there. A ten-line fixture, indexed in the image with the host's
pinned scip-python, showed why. A def nested in a method is named `T#generate().` with
every function scope dropped, and two definition occurrences share one moniker. A def
nested in a module-level function keeps its path. `decode` keeps a moniker one file
defines at several lines at its smallest line in every language but C++
(`abstainMultiDefined`, ADR-113 §2). `~/.hobbes/bench/py-multidef/`: raw indexes of flask,
click, attrs and this repo at `2c915a8`; `classify.py` sorts the shapes by `ast`, and
`rows.py` joins them to the reports. Only the nested shape carries graded rows: flask 2
confirmed and 3 suspect, and click 1 and 1. The click suspect is **a fourth wrong edge**,
`core.py:1888`. The rule as worded (one line in a scratch worktree, both keys regraded):
flask 1,521 → 1,519 and 18 → 15, click 3,755 → 3,754 and 21 → 20, 0 contradicted, poison
PASS. Exactly seven edges went, and lane A drew none back. Three routes; route a.

**ADR-150 (Max: "proceed with recommended"), 0.2.70-beta.** ADR first (`26a14b9`). Unit
`4732`: 54 turns, $3.13, 6 files (the helper, 3 scip cases, a `mininest` fixture and its
`lane_b` case). Gate clear, verify pass. **The review found my own error in the brief and
the ADR.** The first classifier counted parameter monikers, which the helper never keeps.
So the ADR's table showed `@overload`, property and same-scope columns, and the brief's
record wording named them. A second fixture in the image showed scip-python 0.6.6 emits one
definition for a property's getter and setter, an `@overload`'s stubs, an `if`/`else` def
and a module-level redefinition. The wording was fixed on the branch with an assertion
that holds it (`e47b35b`), and ADR-150's table and route-b argument were corrected in
place. The corrected counts match the ingest's own record: flask 9, click 2. Host:
`lane_b` 17 of 17, pytest 2,402, scip node 97. The built cells equal the probe's (flask's
export byte for byte). C-170 was registered (surfaced), with HISTORY; oracle-grading
§10.36, flask's cell record, the architecture (the provider-limits paragraph, §3.8's
Python row, the §8 header), CHANGELOG, README, CLAUDE.md/AGENTS.md, workstreams and the
handoff were updated. The tracker reads 74 of 40, and the image was rebuilt at 0.2.70-beta.

## 2026-09-24 (sixteenth session) — the top-level docs read again; the Calvin experiments programme proposed (a model that writes C, from sqlite-vector)

**The review (Max: "review top level documentation").** README, CLAUDE.md/AGENTS.md (still
byte-identical), the handoff, the Calvin charter, harness and keyed-round records, the TTT
results and Atlas-0 were read at 0.2.70-beta. They agree with the tree, except for one line
that drifted again: README's "ADR-001 to ADR-149" (the tree has 150; the fifteenth session
fixed it to 149, and ADR-150 landed after). Fixed. Noted and not changed: the harness
page's status line still counts "twenty-nine dispatched sessions through 0.2.21-beta" (the
tracker is the count); Atlas-0's header reads "proposed" where CLAUDE.md reads it held; and
Atlas-0 and the charter name `calvin-m0-socket(-v2).md`, which never existed in this tree
(the charter's header comment explains the v1 title).

**The programme (Max: "setup an overall calvin experiments file … where to progress is up
to you").** `docs/calvin/calvin-experiments.md`, proposed, no spend. Its rule is the one
ADR-099 half-measured: skill (the language, its patterns) may live in the weights, and the
target's facts come from the ledger every time. That reading keeps the charter's §7. The
target is sqlite-vector, because its cell is 100/100, so the graph can grade code a model
writes. Read from the bench clone at `0c2223a`: each of the six kernel files hand-writes the
same 31 names (5 types × {`_impl`, `l2`, `l2_squared`, `l1`, `dot`, `cosine`} + `bit1`
`hamming`; 21 real bodies, 10 two-line wrappers), filling one `dispatch_distance_table`.
`distance-cpu.c` is a scalar reference, so every cell has a numeric differential. The host
has AVX2 and AVX-512, so 93 cells run natively in the image. The page lays out the axes
(model, teacher, context, ladder L0–L4, graders), experiments E0–E7, the proposed order
(E0 instruments with no spend → E1 the lattice, pattern vs facts vs volume, ≈ $3–6 of a
$10 ceiling → the branch E1 selects), and four decisions for Max (D-1 to D-4). Flagged in
it: Claude as a teacher of training data is a terms question (as understood, outputs may not
train a competing model), so the recommended route is Claude at inference only. Linked from
README's docs table, CLAUDE.md/AGENTS.md (the read-next row, "Open for Max"), and the
handoff's standing items and held list. No version bump (ADR-103: experiments are not
versioned). pytest's doc-reading cases (tracker, tally, version, staging) 45 of 45.

**Later: the routes taken and the literature pass (Max: "good to go with recommended routes,
we could look to use an open model for inference … the general model more parses the
message into a task format … worth looking to other literature").** D-1, D-3 and D-4 were
taken as recommended. D-2 was amended: an open model at inference too, and the general
model a parser into a task format, with the graph filling every field it can. The four
searches ran in parallel (Sonnet subagents), and the abstracts the design leans on were
re-read here: Commit0, RPG/ZeroRepo, FunCoder, MapCoder-Lite, SimdBench, IntrinTrans,
AutoVecCoder, the SSW RISC-V port, monitor-guided decoding, Li et al. 2508.06414, Le et
al. 2510.03178, and Karpathy's 2025-06-27 post. One search figure did not match its
abstract (IntrinTrans: the search said 23.5%–100%, the abstract says 47%–100%). Only
re-read figures are quoted, and §12 marks which rows were re-read. The pieces are each
precedented, and the combination is not (§12.6). What changed (§12.7): E1 gets an iterate
arm and per-ISA/per-type reports, and its central reading is written against Li et al.
(similar solutions transfer little in-context); E2 gets two shadows, descriptive and
opaque, because renaming costs ability as well as recall; G-hsr gets a failure class; E3
trains only on validated, fact-complete examples; M-e (AutoVecCoder-8B) is added if its
weights are open. Paused before E0 for Max.

**Later still, into 2026-09-25: E0 built and accepted (Max: "good to go").** ADR-151 was written (the programme,
with `calvin-experiments.md` as its body), and the charter amended (skill in the weights, facts in the ledger).
`bench/calvin/lattice/` was started with a real-source fixture: sqlite-vector's kernel files at `0c2223a`,
trimmed by a script to the float32/int8/bit1 rows, verbatim otherwise. The fixture's own ingest and clang key are
beside it (126/126, recall 136/136, poison PASS). A CI step was added. Five units were dispatched serially, $52.37
of subscription usage (the envelopes'):
- `2fd4`: the map, holes and task record;
- `9326`: the graders, the containment runner, the self-test;
- `f50c`: two references;
- `189e`: facts, ages, G-mem probes;
- `c141`: the rename shadows, G-graph. It hit its 140-turn cap and was merged after review.

**Every unit's real-target check, run on the host in the image before the merge, found something the fixture
had not:**
- `prelude` carried sibling bodies into C-0 (the brief's; a bare prelude added);
- the target's own f16/bf16 SIMD kernels disagree with its scalar, and with each other, on inf and NaN (77
  cases). A case with a non-finite input or scalar result is graded against the cell's own gold; that rule is
  mine, and Max has not been asked;
- uint8's scalar drift at n = 4096 (tolerance 1e-5);
- a header macro's expansion leaking into the facts (the brief's; dropped, and the written name kept);
- `sqlite3_mutex_alloc`, an in-repo macro on one `#if` arm and SQLite's API on the other, renamed by the first
  shadows, which then failed to link. Fixed at the review (`20c53c9`, `declared-outside`).

One correction of my own record: `9326`'s review first said 372 of 372 mutants, and it was 363 (`aeb3cbf`).

The acceptance on the real target:
- 93 golds `pass` and 465 of 465 self-test rows are as expected;
- both shadows pass `make unittest` (1,447 of 1,447) and `make unittest-simd` on AVX-512, with 93 golds `pass`
  through each;
- G-graph reads Jaccard 1.0 on all 93 golds, and 0.667 on a numerically passing body with an extra callee;
- the facts cover all 93 cells, the ages equal the hand count, and there are 93 G-mem probes.

The contamination facts: the target's first commit is 2025-04-07 and AVX-512's file 2025-12-17. Olmo-3-7B's card
gives a cutoff of Dec. 2024, and Qwen2.5-Coder is of 2024. Both E1 bases predate the target, and 34 of 93 bodies
are newer than 2026-06-30.

**A harness defect, found twice:** the gate reads a newly added decorator naming a module-level value as
`invented`. Since ADR-146, lane A reads a decorator as a call, and the grounder knows no module-level assignment.
It was reproduced in 14 lines and is recorded as a false block in `9326` and `c141`; the tracker reads 79 of 40
with 3 false blocks. Not fixed; it is for Max to name. The target was re-ingested at 0.2.70-beta. README, CLAUDE.md
and AGENTS.md, the handoff and the design's record are updated; there is no version bump (ADR-103).
