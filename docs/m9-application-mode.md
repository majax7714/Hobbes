# M9 (proposed): Hobbes as an application

**Status: PARKED (2026-08-15). Not on the roadmap. No code written, and
none to be written.**

Max's call, in his words: *"the application was a thought i had wanting it
less and less but maybe one day."* **Hobbes stays local** — on the box,
against a repo on disk (architecture §9). This document is kept as the
record of the thought and the assessment it got, not as a plan. Do not
begin implementing it, and do not design other work toward it.

The three open questions below were never answered and are left as they
were. If this is ever revived it starts there, and it still has to answer
for crossing ADR-022's "the surface never runs the pipeline" line — which
would want a launch token *before* the feature, not after.

*(Original status: proposed, not decided; paused 2026-08-13 while Max moved
for college.)*

---

## What Max asked for

In his words (2026-08-13):

> move from repo style `hobbes up` to hobbes as an application (more
> actual environment), where you can open a folder and either start
> hobbes, refresh hobbes, or continue developing. the refresh should go
> through our already existing workflow of new commits since last. to
> establish hobbes status we can do two checks: does hobbes exist yet?
> and is last hobbes commit equal to last git commit. action is waited
> on by user while status is captured.

The motivation was the two papercuts recorded at the end of
`future_additions.md`: buffered `hobbes up` output, and the
cross-device clone failure.

---

## Verdict: the shape is right, and most of it already exists

Max's two checks are *already* the two checks `hobbes up` makes:

- `pipeline/src/hobbes/cli.py:440-458` — is there a `.hobbes/`, then
  does `graph.json`'s stamped `sha` equal HEAD?
- `/api/overview` already returns both, as `ingested`, `sha`, `head`,
  `behind` (plus `dirty`, `narrated`, and the counts).

So this is not new logic. It is **moving that status out of a process
that holds a terminal and into a surface that reports it.** The
computation survives intact; what changes is who waits.

## What it fixes, and what it does not

**Buffered output: fixed by deletion.** That papercut exists only
because a long-lived Python process prints while it blocks. No blocking
process, no buffer, no bug. This is the honest reason to want the
redesign.

**Cross-device clone: not fixed by this.** That is `hobbes-session`
hardlinking into `~/.hobbes/sessions/<id>/worktree`, and it stays broken
in app mode. What app mode does is make the better fix natural — if
Hobbes owns per-workspace state, session worktrees can live beside the
repo instead of under `$HOME`, and the cross-device case stops existing.
Either way it is a one-line decision (`git clone --no-hardlinks`, or
relocate the worktree), independent of everything here.

## Two dimensions the two checks would lose

Both already work today and neither is derivable from a SHA comparison:

- **Dirty tree.** Artifacts stamped at HEAD can still have been built
  from uncommitted content. Status has to be *current / behind / dirty*,
  not a boolean, or refresh looks like a no-op when it is not.
- **Doc staleness is blob-level and independent** (ADR-019). The graph
  can be current while a module doc is stale because a file it cites
  changed.

The full status object should be: **exists → graph-behind → dirty →
docs-stale → decisions-owed.** Max's two are the right primary gates;
the other three are already computed and should not be dropped on the
way over.

## What genuinely has to change

**1. The surface would run the pipeline.** ADR-022 says the surface
writes exactly three files and never invokes the extractor. A refresh
*button* means the Go daemon shells out to `hobbes ingest`. That is a
real boundary crossing and needs an ADR amending 022, carrying one
constraint over hard: **refresh re-ingests, never narrates.** Quota
stays something Max spends deliberately (ADR-026). It also needs to be a
job with state and a log, not a synchronous request.

Refresh then composes from what exists:

1. re-ingest at HEAD,
2. graph delta from the previously-stamped SHA to HEAD —
   `pipeline/src/hobbes/graphdiff.py`, already built and already exposed
   as `hobbes diff <base>..<head>` (ADR-009),
3. re-badge doc staleness,
4. route any newly inferred invariants into the decision queue
   (ADR-026).

That is Max's "new commits since last," and it is the first time
`hobbes diff` gets a natural home.

**2. Workspace binding moves from startup to runtime.** `RepoRoot` is
resolved once in `web.New` (`go/internal/web/server.go:44-67`) and read
at 22 sites across `server.go`, `artifacts.go`, `source.go`, and
`decisions.go`. Threading it is mechanical, but it is the difference
between "a server for this repo" and "an application."

**3. Blocking moves from the process to the action.** Max chose blocking
deliberately in ADR-026, and it survives — better. Instead of a terminal
he cannot reclaim, **"continue developing" is disabled until intent and
invariants are settled.** Same guarantee, no hostage.

*(Open: whether "continue developing" means "start a session here" or
"get out of my way, the environment is ready." Assumed the former.)*

## The one thing to flag hard

Today the server has **no authentication**, justified because it is
loopback and scoped to one repo named on the command line (ADR-022). If
the UI can open *any* folder, that same unauthenticated port can read
any file the user can read — and it can already approve escalations,
which execute. Any page in the browser can POST to `127.0.0.1:7777`.

The fix is cheap now and awkward later: a token minted at launch, plus
an `Origin` / `Sec-Fetch-Site` check alongside the existing `Host`
check. Build app mode with it from the start rather than bolt it on.

## What the browser cannot do

There is no native folder picker that hands a server a path — the File
System Access API gives opaque handles, not paths. In-browser, "open a
folder" is a typed or pasted path plus a recents list the daemon
maintains. A real dialog needs a desktop shell (Tauri/Electron), which
is a new dependency and a new build story.

## Size and proposed split

Milestone-sized, not an afternoon. Suggested split:

- **M9a — the app shell over today's one-repo server.** Status object,
  refresh as a job with the delta report, actions gated on decisions,
  `hobbes up`'s blocking form retired. Delivers the feel, fixes the
  buffering papercut, low risk.
- **M9b — multi-workspace.** Registry, launcher, recents, auth token.
  The part that changes the threat model.

A CLI stays either way: CI has no browser, so `hobbes review` and a
report-and-exit status check remain.

## Open questions (need Max)

1. **Workspace model** — one daemon holding many workspaces (routes
   become workspace-scoped; the single-window experience he described),
   or a launcher that supervises one `hobbes-web` per repo on its own
   port (far less code, every existing traversal guard stays intact per
   server, but N processes and N ports)?
2. **Folder open** — browser-only with typed paths plus recents, or a
   desktop shell for a real native dialog?
3. **Scope** — M9a first and stop, or the whole thing in sequence?

Recommendation: one daemon many workspaces, browser-only to start,
M9a first — with the launch token built in from the beginning rather
than deferred to M9b.
