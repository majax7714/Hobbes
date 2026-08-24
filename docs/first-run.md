# First run: bringing Hobbes up on an app

A walkthrough for pointing Hobbes at a repo for the first time, in the
order the system is meant to be used. Every step says what it is *for*,
because the order is the design: **deterministic before generative,
enforcement before agents, content before chrome** (build plan,
sequencing rules).

You can stop after any step and still have something useful. Steps 1–4
spend no quota and involve no agents at all.

> **The short version.** After step 0, `cd` to the repo and run
> **`hobbes up`**. It does steps 1–3 for you — initialize if needed,
> re-ingest when the artifacts are not stamped at HEAD, and serve the
> surface — then holds until you have settled the two things only you can
> answer: **intent** and **invariants** (ADR-026). It never narrates,
> because that spends quota and the graph should be checked first.
>
> The steps below are what `hobbes up` is doing, and what to do when you
> want to drive them yourself.

---

## 0. Build the tools (once)

```sh
cd go
go build -o bin/hobbes-policy  ./cmd/hobbes-policy
go build -o bin/hobbes-web     ./cmd/hobbes-web
go build -o bin/hobbes-session ./cmd/hobbes-session
CGO_ENABLED=0 go build -o bin/hobbes-proxy ./cmd/hobbes-proxy

cd ../web      && npm install && npm run build   # then rebuild hobbes-web
cd ../tsextract && npm install                   # only if the repo has TS/JS
cd ../scip     && npm install                    # lane B: the SCIP indexers
cd ../pipeline && uv sync

# Go repos only — scip-go is a Go binary, not an npm package, so it is
# installed rather than vendored. Pin it: its --module-version defaults
# to the git revision, and the version is what a provider limit is filed
# against (P9).
go install github.com/scip-code/scip-go/cmd/scip-go@v0.2.7

# Rust repos only — rust-analyzer is a rustup component, pinned by the
# toolchain (the version is what C-28/29/30 are filed against).
rustup component add rust-analyzer
```

> **`scip/` is what makes edges *proven* rather than guessed.** Without
> it, ingest still works and the whole graph sits at `syntactic` tier —
> lane A's static resolution, honestly labelled (ADR-031). With it, the
> two lanes join and most edges become `semantic`. `HOBBES_SCIP=0` turns
> it off deliberately.
>
> Lane B needs the target repo's **dependencies installed** to resolve
> third-party types — `npm install` for TS/JS, the virtualenv for Python.
> Without them the index still succeeds and quietly loses edges, so
> ingest reports `dependency_coverage` and warns when too little
> resolved (ADR-032, C-23). **Go is the exception**: its module cache is
> global rather than per-repo, so it is warm whenever `go build` works,
> and `scip-go` fails loudly rather than thinning out when it is not.
> **Rust fetches for itself**: cargo pulls crate sources into the
> user-global registry at index time, so the first ingest needs the
> network (C-30) — and **indexing a Rust repo executes its `build.rs`
> and proc macros** (C-29; ingest discloses this on stderr every time).
> Ingest an untrusted Rust repo only if you would also build it.

> **The proxy must be static.** `hobbes-session` mounts the
> `hobbes-proxy` sitting next to it into the sandbox. A dynamically
> linked one fails in the container as `No such file or directory` —
> which is the missing *loader*, not the missing binary, and reads like
> nonsense the first time. `CGO_ENABLED=0` fixes it, and a static binary
> works host-side too.

`go.mod` requires **Go ≥ 1.26**. Distro packages are usually behind, so
a user-local toolchain has to sit *ahead* of `/usr/bin` on `PATH` —
otherwise `go build` fails on the toolchain line and it reads like the
module is broken.

Four commands have to be findable, because they find each other by
name: `hobbes` (the `pipeline/.venv/bin/hobbes` console script — its
shebang is absolute, so a symlink works from anywhere), and
`hobbes-policy`, `hobbes-web`, `hobbes-session` from `go/bin`. `hobbes
up` looks for `hobbes-web` on `PATH`; the policy wrapper looks for
`hobbes-policy` there or in `HOBBES_POLICY_BIN`. `hobbes-session` finds
`hobbes-proxy` next to *itself*, resolving symlinks first, so linking
the four into one directory on `PATH` is enough.

Everything below assumes you are inside the target repo.

---

## 1. `hobbes init` — claim the repo, decide the rules

```sh
hobbes init
```

Scaffolds `.hobbes/` and **gitignores the whole directory** (ADR-012):
in your repos, Hobbes files are personal, not something collaborators
inherit. (This repo is the exception — it versions its own `.hobbes/`
for dogfooding.)

Then open `.hobbes/policies/repo.policy`. This is the one file you
should read before running an agent, because it decides what a session
may do:

```yaml
version: 1
scope: repo
default: escalate          # the default is a question, never a yes

rules:
  - pattern: "*.tfstate*"
    decision: deny
    reason: "tfstate carries secrets"
  - pattern: "git push*"
    decision: deny
    reason: "publishing is the human's — sessions commit, you push"
  - pattern: "pytest*"
    decision: allow
```

**Intent:** `default: escalate` means an unlisted command parks and waits
for you rather than running or failing. Allow the loop you want an agent
to run unattended (tests, builds, formatters). Deny what should never
happen regardless of who asks. Leave everything else to escalate — the
escalation queue is the point, not a failure mode.

Check your reading of it before trusting it:

```sh
hobbes policy resolve "pytest -q"          # -> allow
hobbes policy resolve "git push origin main"  # -> deny, with the reason
hobbes policy resolve "curl https://example.com"  # -> escalate
```

---

## 2. `hobbes ingest` — build the skeleton

```sh
hobbes ingest
```

Runs the deterministic extractors and writes
`.hobbes/derived/{graph,tests,interfaces}.json`, each stamped with the
repo SHA. No LLM, no network, seconds.

Each language is dispatched to its own parser by file extension — `.py`
to the Python extractor, `.tf` to the Terraform one, `.ts/.tsx/.js/.jsx/
.mjs/.cjs` to the ts-morph helper — and the layers merge facts rather
than re-deriving each other's (I-4). If the repo has Terraform and you
have a plan handy, `--tf-plan plan.json` enriches the infra layer;
`.tfstate` is refused outright and always will be.

**Read the output.** It tells you what Hobbes thinks your repo is:

```
ingested /path/to/app @ 9611f8865548 [javascript, typescript]
  graph.json:      104 nodes, 358 module edges, 207 symbols, 235 call edges
  tests.json:      174 tests
  interfaces.json: 12 routes, 0 CLI entry points
```

Anything on stderr starting `WARNING:` is a degradation — a file whose
extraction partly failed, a module id two languages both wanted, or an
indexer that resolved too few of the repo's declared dependencies. It is
never silent, and it is worth reading before you trust the graph.

### 2a. `hobbes lanes` — make the two lanes check each other

```sh
hobbes lanes          # exits 1 if they disagree
```

Extraction runs two providers: tree-sitter knows a call site *is* a call,
SCIP knows what it *resolves to*, and they meet before the graph exists
(ADR-029). Wherever both resolved the same site, they must point at the
same definition — a disagreement is an extractor bug in one of them, and
this is the only check in the system that catches a resolver being
confidently **wrong** rather than merely silent.

It costs nothing to run and belongs in CI next to `hobbes review`.
Module-edge differences are reported but do not fail it: lane B following
a re-export past the package is not a bug, it is lane B being more precise.

Two numbers in `graph.json` are worth knowing about here, because they are
how the graph admits what it missed rather than presenting a confident
surface (P8):

- **`resolution_coverage`**, per file — call sites, how many resolved in
  repo, how many resolved to an external package, and how many resolved to
  nothing. A module at 56% accounted deserves less trust than one at 100%.
- **`tier`** on every edge — `semantic` is SCIP-proven, `syntactic` is
  lane A's own resolution kept as a labelled floor. The graph draws
  syntactic edges thinner and dashed.

---

## 3. `hobbes-web serve` — check the map is *true*

```sh
hobbes-web serve --repo .      # http://127.0.0.1:7777
```

This is the step people skip and shouldn't. The whole system rests on
the derived layer being right about *your* code, and you are the only
one who can tell. It binds loopback only and has no authentication by
design.

Walk the five tabs in the order they're laid out — that order is the
review order:

- **Graph** — pick a module you know cold. Does the inspector's
  "depends on" list match your mental model? Click an edge's `:line`
  citation; it should land on the exact import. Externals are hidden by
  default (a dependency fan-out drowns the layout); toggle them on when
  you want them. Select a node and tick **focus** for anything larger
  than a hundred modules.
- **Tests** — "guarded modules" is the inverse index: what would break
  if you changed this. **"unguarded"** is the number that matters, and
  it is usually uncomfortable the first time.
- **Docs** — empty until step 4. It will tell you so.
- **Diff** — the raw line diff, deliberately last.
- **Sessions** — empty until step 6.

If the graph is wrong here, fix the extractor before spending anything
on step 4. Narrating a wrong skeleton produces confident wrong prose.

`hobbes render` prints the same module graph as Mermaid if you want it
in a markdown file instead.

---

## 4. `hobbes narrate` — the only step that costs quota

```sh
hobbes narrate --dry-run    # what it would do, and how many calls
hobbes narrate
```

Runs a headless, **tool-less** `claude -p` per unit: one module doc per
module node, one behavior index per test file, and one repo-wide
invariant inference pass. Every claim is validated before it is written,
and a claim whose `file:line` pin doesn't resolve is rejected rather
than saved — an unverifiable claim never becomes an artifact.

Start small on a big repo:

```sh
hobbes narrate --only 'app.billing*'
```

It is incremental by default: re-running only regenerates artifacts that
are **missing or stale**, so the second run is cheap.

```sh
hobbes docs status
```

Staleness is blob-level — an artifact is stale when a file it cites has
changed, including uncommitted edits. Badges show up in the Docs tab
immediately; there is no discipline required and no way to forget.

---

## 5. Confirm invariants — the one step Hobbes cannot do for you

Narration wrote `.hobbes/derived/docs/invariants.inferred.yaml`:
statements your code appears to rely on. They are **inert**. Nothing
enforces them, and nothing will, until you decide.

Open the **Intent** tab. Every inferred invariant is a card with its
evidence, and every card is **approve / deny / edit** (keys `a`, `d`,
`e`). Approving writes a real record into `.hobbes/invariants/`; denying
records the denial so the same claim never asks again; editing lets you
fix the wording or narrow the scope before it becomes a rule. A verdict
holds until you change it, and decisions key on the invariant's *text*,
so a re-narration that renumbers `INF-n` does not re-ask — only new
wording does.

You can still do it by hand if you prefer; the UI writes the same files.

**Read every word before deciding.** An inferred statement is a
guess about intent, and confirming a wrong one versions a false claim
that everything downstream then enforces. Use **edit** when the prose is
nearly right — that is normal, not a failure.

Each record gets a `compile.target`:

| target | for | checked by |
|---|---|---|
| `import-linter` | Python import boundaries | CI **and** `hobbes review` |
| `dep-cruiser` | TS/JS import boundaries | CI **and** `hobbes review` |
| `semgrep` | source patterns that must not appear | CI |
| `rego` | Terraform resource attributes | CI, against `plan -json` |
| `soft` | anything a machine cannot check | a reviewer session |

`soft` is not a cop-out; it is most of them on a real repo, and a soft
invariant with good `guarded_by` tests is stronger than a structured
rule that checks the wrong facet.

```sh
hobbes invariants check      # validates every record; exits 1 with all problems
hobbes invariants compile    # -> .hobbes/derived/compiled/ + a manifest
```

Compiling needs none of those four tools installed — it generates
configs; CI runs them. The manifest tells you the command for each.

---

## 6. `hobbes-session start` — let an agent work, under policy

```sh
hobbes-session start --repo . --role implementer \
  --task "Add a rate limiter to the login route" --claude-cred
```

The session gets a fresh git worktree, a rootless Podman container with
**no network**, an empty environment (no host secrets reach it), and no
raw shell — it reaches commands only through the policy-checked `exec`
tool. It starts oriented: `graph_neighborhood`, `who_calls`,
`tests_guarding`, `get_module_doc`, and `list_invariants` are all
available, so it reads the constraints instead of grepping for them.

Try `--dry-run` first; it prints the exact `podman` argv and MCP config
without running anything.

Watch it in the **Sessions** tab, or from the CLI:

```sh
hobbes-proxy escalations list
hobbes-proxy escalations approve E-20260811T151842Z-776b
hobbes-proxy escalations deny    E-20260811T151842Z-1e38
```

Every call — allowed, refused, or parked — lands in
`~/.hobbes/sessions/<id>/flight.jsonl`. **An approved escalation really
runs**, so read the command before approving it.

For review instead of implementation:

```sh
hobbes-session start --repo . --role reviewer --claude-cred
```

The reviewer's worktree is mounted **read-only** at the kernel level and
its tool list has no Edit, Write, or exec. That is a mount flag, not a
promise.

---

## 7. `hobbes review` — the concept-level gate

```sh
hobbes review main..my-branch
```

The §7 review order in one command:

1. **architecture delta** — added/removed typed edges, with citations
2. **invariants** — judged at *both* ends, so a regression this branch
   introduced is distinguishable from breakage it inherited
3. **behavioral coverage** — new code no test reaches, modules that lost
   every guard, invariants whose guarding tests vanished

Exits **1** when something needs attention, so CI can gate on it alone.
It spends no quota and needs none of the four toolchains. Add `--soft`
to have a reviewer session judge the soft invariants whose scope your
branch actually touched; `--json` gives the whole review for a bot.

The intended reading order is top-down, and the point of the first three
sections is that you rarely reach the line diff.

---

## 8. The refresh loop

```sh
hobbes up          # re-ingests if HEAD moved, then holds for any new decisions
hobbes narrate     # only regenerates what went stale
hobbes docs status # what moved
```

A re-narration may infer new invariants. Those arrive in the Intent tab
with the same approve / deny / edit treatment, and `hobbes up` blocks on
them — but only on the *new* ones. A verdict holds until you change it,
and decisions key on the invariant's text rather than its `INF-n` id,
which is positional and means something different every run.

Put `hobbes ingest && hobbes review $BASE..HEAD` in CI and let the exit
code do the gating.

---

## Things that will bite you

- **Narrating before checking the graph.** Confident prose about a wrong
  skeleton is worse than no prose.
- **Promoting an inferred invariant you skimmed.** It becomes a rule
  everything downstream enforces.
- **Approving an escalation without reading it.** Approval executes.
- **A dynamically linked `hobbes-proxy`.** See step 0.
- **Forgetting to rebuild `hobbes-web` after `npm run build`.** The app
  is embedded in the binary; the old bundle keeps serving.
- **Expecting `soft` invariants to be checked by CI.** They are checked
  by a reviewer session, or by you.
- **Expecting decisions to survive a fresh clone.** `.hobbes/` is
  gitignored in your repos (ADR-012), so approvals, denials, and the
  intent confirmation live in *this* clone on *this* machine. A known
  limitation, with the opt-in fix in `future_additions.md`.
- **Ingesting a repo whose dependencies are not installed.** The indexer
  exits 0 and produces a plausible index with the third-party edges
  simply missing. Ingest now warns, but check `dependency_coverage` if
  the graph looks thin (C-23).
- **Reading an absent edge as "this does not happen".** It means "not
  statically visible" and never more than that (C-1). The call graph
  under-approximates on purpose — a false edge is worse than a missing
  one — so every number Hobbes reports is a floor.

---

## Where the design is written down

`docs/hobbes-architecture.md` is the source of truth, and it is a
**running** document — it describes Hobbes as it is now rather than as of a
version, and it is amended in the same commit as any change that moves it
(ADR-033). `docs/hobbes-architecture-v1.md` and `docs/hobbes-build-plan.md`
are the frozen v1 record: history, kept for the reasoning behind the
carried subsystems.

Every decision those don't make has a numbered ADR in `docs/adr/`.
`docs/BUILDLOG.md` is what actually happened, session by session,
`docs/future_additions.md` is what was deliberately left undone and why,
and **`docs/constraints.md` is what Hobbes cannot tell you** — every
place it concedes information, and where you meet that limit (P8).
Read that one before you trust a number.
