# Verification — the benchmark harness (ADR-055)

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-39 — Contamination is bounded, never proven

**Amended 2026-08-22 — contamination is now *demonstrated*, not only bounded, and it is *asymmetric*.** On `five-fresh-27b-adr075` the 27B pure arm reproduced `pydata__xarray-3993`'s gold patch **verbatim, including the author's forward-looking string `" `dim` will be removed in version 0.19.0."`** — a maintainer's future deprecation target that cannot be derived from the repository at the base commit. It also reproduced 100% of the gold *added* lines on xarray (29/29), scikit-learn (19/19), and sphinx (23/23); the smaller 7B produced empty patches on xarray. This is recall, not capability, and it is **size-dependent**. Crucially it is **asymmetric between the arms**: regurgitating a memorized whole-patch requires seeing the whole task, so it favors the **undivided (pure) arm** and is denied to the **partitioned harness** by construction — a confound *against* Hobbes. Any pure-vs-harness comparison on Verified is therefore contaminated in Hobbes's disfavor, and no H1 claim may rest on it. The clean test is a **post-cutoff / decontaminated set** (SWE-bench-Live, SWE-rebench, or the diversified small-model set on a model that provably did not memorize the instance) — promoted by this finding from optional (ADR-052) to necessary.
- **Cannot tell you:** whether a pure-model solve on a benchmark
  instance came from reasoning or from memory. Known benchmarks are in
  training corpora; a memorised answer needs no context, which biases
  the comparison *against* the harness, not for it. The instance
  protocol bounds the set by `created_at` against a stated cutoff and
  counts what it dropped; it cannot see inside a model's training
  data, and a post-cutoff instance can still resemble a pre-cutoff one.
- **Because:** the only honest tool is selection, and selection is a
  date. SWE-bench Verified's newest instance is 2023-08-07 — a 2025
  cutoff selects zero of 500 — so a live run on a contemporary model
  needs a continuously refreshed set (SWE-rebench, SWE-bench-Live) and
  still only *bounds* the question.
- **Bites at:** every H1–H3 rate; a pure arm that looks strong on an
  old set may be remembering, and a harness that looks weak beside it
  is being compared to recall.
- **You find out:** **surfaced** — `hobbes bench select` and `run`
  print the cutoff line first ("bounded, not proven — C-39", or "every
  instance may be in a model's training data" when none is set);
  `run.json` records the cutoff, the created range, and the drops; the
  report's notes restate it.
- **Source:** ADR-055 (2026-08-21).

### C-40 — The verdict is the evaluator's
- **Cannot tell you:** that a `resolved` verdict means the patch is
  right, or an `unresolved` one that it is wrong, beyond what the
  benchmark's own tests decide in the benchmark's own environment.
  The harness runs the pinned `swebench` evaluator as a subprocess and
  reads its report; per-repo test commands, environments, log parsers,
  and image builds are the evaluator's, and so are their failures
  (an `error` verdict is an environment that did not come up, not a
  patch that was judged).
- **Because:** reimplementing per-repo test semantics would make the
  verdict Hobbes's opinion of the benchmark rather than the benchmark;
  P9's shape — a provider we run and do not wrap.
- **Provider:** `swebench` **5.0.2** (pinned in `bench/verdict.py`;
  `HOBBES_SWEBENCH_CMD` overrides the invocation, never the meaning).
- **Bites at:** `error` and `unjudged` counts in a report; a rate is
  over *judged* records only, and the unjudged count is printed beside
  it.
- **You find out:** **surfaced** — the report's notes name the
  evaluator and version; `run.json` records it; every verdict class is
  counted in the output, none folded into another.
- **Source:** ADR-055 (2026-08-21).

### C-41 — A live session has egress, and carries the model credential
- **Cannot tell you:** that a running session could not reach the
  network. The architecture's enforcement text says a forbidden route
  is *absent*, and for every session so far it was (`--network none`).
  A session driven by a model served off-box must reach that endpoint,
  so a live session runs with a network, and the endpoint's bearer
  token rides into it as `HOBBES_LLM_API_KEY` — the one secret a
  session carries. Nothing narrows the egress to the endpoint host yet.
- **Because:** the small-model ladder is served from the owner's
  compute (ADR-056), not from a binary in the image; the model is a
  network service by construction. The shell is still only reachable
  through the policy-checked `exec`, the mounts are unchanged, and the
  loop offers no `bash` when an MCP config is present — what changed is
  one reachable host, stated rather than hidden.
- **Bites at:** a session that exfiltrates through the model endpoint
  or anywhere else reachable on the session network; a leaked endpoint
  token (scope it per run — a Modal proxy token, revocable).
- **You find out:** **surfaced** — `hobbes-session --dry-run` prints
  the network mode and the runtime line (`runtime: … → <endpoint>`)
  with the token redacted; `hobbes bench run` prints `runtime openai @
  <endpoint>`; `run.json` records the endpoint. Narrowing egress to the
  endpoint host is in `future_additions.md`.
- **Source:** ADR-056 (2026-08-21).

### C-42 — A benchmark session runs under the solo floor, not the repo's intent
- **Cannot tell you:** that a benchmark session's permissions match what
  the repo owner would allow. A benchmark checkout is a committed-only
  clone, so the repo policy and the role policies (untracked under
  `.hobbes/`, ADR-012) never reach the session's worktree — only the
  derived agent policy and the shipped **solo box policy**
  (`bench/bench.box.policy`) apply. That box grants a lone implementer
  the tests-and-commit it needs with no human to approve; it is the
  *benchmark's* floor, not the target repo's intent.
- **Because:** benchmarks run Hobbes alone (no plan-review, no
  escalation approver — ADR-054's direction), and without this a
  needed `pytest`/`git commit` escalates and expire-denies after 30
  minutes of dead time, starving the arm under test (the ADR-057
  finding). The specific guarantees still win by deny-overrides
  (`*.tfstate*`, `git push*`, `git add *.hobbes/derived*`), and the OS
  sandbox is unchanged — the real boundary is the mounts and the
  network (C-41), not this file.
- **Bites at:** reading a benchmark session's allowed commands as if
  they were the repo owner's policy; they are not, and a real
  deployment of the execution path (not the benchmark) would load the
  repo and role policies instead.
- **You find out:** **surfaced** — `hobbes-session --dry-run` prints the
  box path (the podman `-v` line) and the escalation timeout; the policy
  file is committed and commented with exactly this scope. (Corrected
  2026-08-23: `run.json` records only the *user's* session args, not the
  default box the harness adds — the dry run is where it shows.)
- **Source:** ADR-057 (2026-08-21).

### C-43 — The benchmark environment is bound, not rebuilt
- **Cannot tell you:** that a candidate patch which changes a compiled
  extension (a `.pyx`, a C source, a generated module) was tested
  against that change. Both arms run in the instance's own swebench
  image (ADR-058); the worktree at `/work` shadows the image's
  installed copy through `PYTHONPATH`, and the in-place build
  artifacts (`.so` files, generated version modules) are **copied**
  from the image's `/testbed` into the worktree before the session —
  never rebuilt. A pure-python change is tested exactly; a change that
  needs a rebuild runs the old extension under the new source.
- **Because:** rebuilding per unit session is minutes of compile per
  spawn (astropy, scikit-learn), and the evaluator (C-40) does its own
  install in the same image anyway — the verdict is unaffected, only
  the agent's in-session test signal is. Four of the 45 complex
  instances are compiled repos; the other 41 are pure python.
- **Bites at:** an agent editing a compiled module and trusting a green
  in-session test run; the evaluator then disagrees.
- **You find out:** **surfaced** — `hobbes bench run` prints the binding
  in its banner (`worktree bound by PYTHONPATH + copied build
  artifacts (ADR-058, C-43)`); every record's `detail.environment`
  names the image, digest, the `PYTHONPATH` binding and the
  pre-command; `hobbes-session --dry-run` prints all of them.
- **Source:** ADR-058 (2026-08-21).

### C-44 — The unit cap decides which units run, not which belong together
- **Cannot tell you:** that a deferred unit did not need a session, or
  that the modules in a `capped` unit belong together. The benchmark
  unit cap (`--max-units`, default 20, ADR-058; restated 2026-08-22 by
  the harness restructure) **selects**: units are ranked by the best
  impact score in their interior, then weight, and the lowest-ranked
  are **deferred** — recorded in the spec under `units_deferred` with
  their score, never spawned. A seed-bearing unit (score 1.0) is
  never deferred; when those alone exceed the cap they **merge** past
  the context budget — strongest coupling first, then lightest — and
  are flagged `capped`. Either way the number of sessions was the
  decision, not the partition.
- **Because:** one instance's plan reached 210 units on a large repo
  under lexical seeds (C-35/C-36); the first cap (merge-to-fit) then
  fused 300 modules into one 17M-token unit whose brief was cut by
  418 KB — the gold files inside it, the unit that edited nothing.
  The cap bounds the run's cost; deferring keeps the units it does
  run the partition's own. It does not improve the partition.
- **Bites at:** reading a capped plan's unit boundaries as derived
  structure; a deferred unit that the change did reach (the impact
  score ranked it low — C-35's weights deciding); measuring H2
  (per-unit context) on capped units without separating them.
- **You find out:** **surfaced** — every deferred unit is listed in
  the spec (`units_deferred`, flag `deferred: … best impact score …`)
  and every merged one carries `capped: … (C-44)`; `max_units` is
  recorded in the spec and `run.json`; the record's `detail.plan`
  counts `capped` and `deferred`; `hobbes plan` and the bench banner
  print both.
- **Source:** ADR-058 (2026-08-21).

### C-45 — A brief is held to the model's window; what was cut is named, not read
- **Cannot tell you:** that a session saw its whole standing context.
  `hobbes bench run --brief-limit` (default **sized to the endpoint's
  window** — 35 % of `max_model_len` × 3.3 chars/token, ADR-069;
  60,000 chars only when the window is unknown, said so) and `hobbes
  run --brief-limit` cut a unit's brief to fit: the unprotected
  sections (guarding tests, module docs, neighborhood, inbox) are
  filled in priority order, no one of them above 60 % of the room
  (ADR-069; before that they were trimmed to
  an equal share, each ending in a stated `… cut: N more line(s)`;
  the protected ones — the unit's own **interior** (since ADR-062:
  phase 4 cut U1's 21 KB of paths while the global planner handoff
  stayed whole, and the unit aimed at someone else's file), the
  complement (*What Hobbes cannot see*, ADR-047's contract), the
  derived policy, the contracts, the invariants — are never cut, so a
  limit below their size is not met and the brief is simply as small
  as honesty allows.
- **Because:** a capped unit (C-44) carries the context of everything
  it absorbed — one astropy unit's brief reached 488 KB, past the
  kernel's single-argument limit (the crash that surfaced this) and
  four times the 7B's whole window. The knowledge tools still answer
  for every cut line; the cut bounds what the model is *handed*, not
  what it can ask.
- **Bites at:** reading H2 (per-unit context) on a cut unit as if the
  derived context were what the model saw; it saw the protected
  sections and a prefix of the rest.
- **You find out:** **surfaced** — line 2 of a cut brief says
  `(standing context cut by N characters … C-45)`; every cut section
  ends in its cut line; the partition record carries `brief_chars`
  and `brief_cut` per unit and the bench record copies them; the run
  banner prints the limit.
- **Source:** ADR-058 (2026-08-21), the second finding; the interior
  protected by ADR-062 (2026-08-22).

### C-46 — A small model's window is fitted, and old tool results elide
- **Cannot tell you:** that a harness session's model saw every tool
  result it had gathered. The owned loop (`agent/loop.py`) runs on the
  window the endpoint reports (ADR-069 — 32k on the 7B ladder where
  this entry was written, 131k on the 27B); when a request would exceed it the loop first
  shrinks `max_tokens` to what is left, and if that leaves too little
  it **elides the oldest tool results in place** (a stated placeholder)
  until the request fits — the model then works from a summary of its
  early reads, not their text. Tool results are also clipped to
  `--max-result-chars` (default 12,000) head-first, the cut stated.
- **Because:** the ladder's rungs (7B/32B) have small windows and a
  benchmark repo's files are large; without fitting, one long read made
  the *next* call a hard 400 and killed the arm (the third finding of
  the first run — `astropy-13398` U1). The knowledge tools still answer
  for an elided result; the loss is what the model holds at once, not
  what it can re-fetch.
- **Bites at:** reading a harness result as if the model had full
  recall of its session; a long multi-file unit is working from elided
  early context by its last turns.
- **You find out:** **surfaced** — the envelope carries
  `context_fitted` and `context_elided` counts per session, and (ADR-068)
  `prompt_tokens_max`, `calls`, `calls_saturated`; every call's prompt
  size, `max_tokens` actually sent, `finish_reason`, and overflow events
  are in `calls.jsonl` beside the transcript — a 200 that a fit made
  possible is visible there, not only in a provider's log; an elided
  result is the literal placeholder in the transcript; a clipped result
  ends in its cut line. Larger windows (a rung with more context, or a
  paged-context loop) lift it — parked in `future_additions.md`.
- **Measured (2026-08-22, the 5-fresh re-run):** the brief itself is
  the window's main tenant — an implementer brief tokenized to up to
  **16,750 of 32,768 tokens**, and 82 % of it is context the unit
  cannot change (neighborhood, guarding tests, contracts; the unit's
  interior averages 171 chars). The brief is never elided, so the fit
  drops **the model's own reads first** — sympy-13852 U2 read the file
  it was about to edit, had that read elided, guessed the anchor, and
  spun. Two earlier runs the same day paid ~390 context-length 400s
  between them (the Modal log Max read); the re-run paid ~10, because
  sessions now end sooner, not because the window got roomier. The
  brief's shape is a derivation decision, not a loop fix — open.
- **Source:** ADR-058 (2026-08-21), the third finding; measured
  2026-08-22 (`benchmark-hypotheses.md` Results).

### C-47 — A staged plan's seeds are a model's opinion, not a derivation
- **Cannot tell you:** that a staged run's change-spec is reproducible.
  In the staged run (ADR-059) a `planner` session names the files the
  change touches, and its handoff — a model output — becomes the seeds
  the deterministic partition runs on. Two planner sessions may name
  different files, so `seed_source: planner` specs are not
  byte-identical between runs, unlike the lexical path (C-36) which is.
- **Because:** the whole point of the planner is to read prose the
  lexical seeds cannot (C-36 made the impact set the whole repo on the
  first live run). A generative reading is a model opinion by
  construction; P5 keeps it *above* the deterministic layer, never
  inside it — the derivation from the planner's seeds onward is still
  reproducible, and the deterministic lexical seeding is always the
  fallback.
- **Bites at:** treating a staged unit boundary as a derived fact;
  comparing two staged runs' plans as if a difference were a bug;
  auditing a spec without noticing a human never approved these seeds
  (the benchmark path runs Hobbes alone — the plan-review gate is off).
- **You find out:** **surfaced** — the record's `seed_source` says
  `planner` / `lexical-fallback` / `explicit`; the planner's handoff is
  kept verbatim in the `plan` stage and its unresolved names in
  `planner_unresolved`; the resolved seeds are in the spec as always.
- **Source:** ADR-059 (2026-08-22).
- **Amended (ADR-072, 2026-08-22):** until ADR-072 the planner's map was
  the first 60 modules alphabetically — the gold module was in front of
  the planner in 1 of 5 benchmark instances, and every planner's only
  tool call was its handoff. The hits recorded before ADR-072 measure
  the model's prior knowledge of the repository (C-39), not derived
  context. The map is now ranked by the proposal and carries the whole
  package tree.

### C-48 — The verifier's writes never reach the tree; a repro it writes is lost with the session
- **Amended 2026-08-22 (ADR-060):** the read-only roles' worktree is
  now an *overlay* mount, not `ro` — the verifier *can* write a
  scratch repro or let pytest cache inside its container view, and
  none of it reaches the host tree or the harvest. The concession
  narrows to: what the verifier wrote to reproduce is **not kept** (its
  handoff is the only thing that survives), and the `verifier-env`
  classification stays as the defensive path for a mount that still
  refuses a write.
- **Cannot tell you (as registered):** that a staged run's verifier reproduced the bug
  the way a developer would. The `verifier` session's worktree was
  mounted read-only (it owns no code, ADR-054/059), and its only shell
  is the policy-checked `exec` — so it could *run* the repo's tests but
  not write a fresh reproduction script or a fixture, and a test
  that needed to write under the tree failed on the mount, not on the
  code. Such a failure is reclassified `verifier-env`, not `fail`.
- **Because:** a role that judges the merged result must not be able to
  change it (a verifier that writes is an implementer), and the ro
  mount is the real boundary (§5.2). Bytecode writes are already
  disabled (`PYTHONDONTWRITEBYTECODE=1`, phase 1) so imports do not
  trip it; a test that writes output files still will.
- **Bites at:** a bug whose only check writes a golden file; reading a
  `verifier-env` outcome as a passing verify (it is neither pass nor
  fail — the harness could not run that check).
- **You find out:** **surfaced** — the verifier's brief states the ro
  limit and asks for `-p no:cacheprovider`; the verify stage records
  `verifier_env: true` and the verdict is `verifier-env`; the reason
  line carries what could not run.
- **Source:** ADR-059 (2026-08-22).

### C-49 — The planner hit-rate is measured against one solution
- **Cannot tell you:** that a planner which *missed* the gold files
  named the wrong place. The benchmark report's planner hit (`hobbes
  bench report`, harness restructure phase 3) is
  `planner_files ∩ gold_files` over the instance's gold patch — and a
  gold patch is one accepted solution, not the set of correct ones. A
  planner that names a different file where an equally valid fix lives
  scores a miss; a planner that names the gold file and the wrong ten
  beside it scores a hit. The recall counts the gold files named, never
  the noise around them.
- **Because:** the benchmark supplies exactly one reference patch, and
  the hit is computed post hoc from it so that no session is ever shown
  the answer; the alternative — judging a planner's files by whether
  the patch later solved — would fold the implementer's competence into
  the planner's number, which is the thing phase 4's probe must keep
  apart.
- **Bites at:** reading a hit-rate as planner accuracy; tuning the
  planner brief to the gold files of the probe instances (the two
  astropy instances are the probe and then part of the 45-set — a
  brief edited against their gold patches is contaminated by hand);
  comparing hit-rates across instances whose gold patches differ in
  size without reading the `gold` count printed beside them.
- **You find out:** **surfaced** — every report that prints the planner
  block carries the note naming this entry; the record's
  `detail.planner` states `gold`, `hits`, `named` and the file lists,
  so a miss can be read against what was actually named.
- **Also (probe, 2026-08-22):** a file the gold patch *creates* is in
  the denominator and can never be named from the graph — 13398's
  `itrs_observed_transforms.py` caps that instance's recall at 3/4
  however good the planner is. The record's `gold_files` list lets a
  reader see which gold files exist at base.
- **Source:** harness restructure phase 3 (2026-08-22), ADR-059
  amended.

### C-50 — swebench 5.0.2's Modal evaluator is broken; the verdict comes from the local engine
- **Cannot tell you (via `--eval-modal`):** any verdict. swebench
  5.0.2's Modal path calls `test_spec.setup_env_script` /
  `install_repo_script` in `get_instance_image`, attributes its own
  5.0.2 `TestSpec` does not define — the code carries a `# TODO` saying
  as much. So `--modal true` raises `AttributeError` for every instance
  and reports them all `error`, after the patches are already produced.
- **Because:** the pinned evaluator is a third party we run and do not
  wrap (P9), and this is its bug, not ours — but the user ran `hobbes
  bench … --eval-modal` and got no verdict either way. The **local**
  path (no `--modal`) works: it reads the same `image` field and runs
  the prebuilt `swebench/sweb.eval.*` container, which on this box is
  served by rootless podman's Docker-compatible API socket
  (`$XDG_RUNTIME_DIR/podman/podman.sock`). `verdict.docker_host_env`
  points docker-py at it; the ADR-055 "podman socket for the evaluator"
  open item is thereby closed.
- **Bites at:** a run launched with `--eval-modal` (the handoff's
  command carried it) — it costs the arms nothing but yields four
  `error` verdicts that are the evaluator's failure, not the model's.
  Reading those as solves-failed would be wrong; they are unjudged.
- **You find out:** **surfaced** — the evaluator's own log records the
  `AttributeError`; the local path is the default and needs no flag.
  `--eval-modal` is kept for when swebench fixes its Modal path
  upstream, and its images-lack-schema failure mode is C-49's sibling.
- **Source:** phase 4 full-stage run (2026-08-22), swebench 5.0.2.
  **Provider:** swebench 5.0.2 (`run_evaluation_modal.get_instance_image`).

### C-51 — Parallel units see only their owners' commits; the speed-up needs a batching endpoint
- **Cannot tell you:** that an implementer's clone held every commit
  that had landed before it finished. With `--parallel` > 1 (ADR-063)
  units whose contract owners are integrated run at once, each cloned
  at the integration head *as of its start*; a unit sees its owners'
  commits — the promised interface — and not those of units it has no
  contract with, which the sequential order used to deliver for free.
  The speed-up itself exists only on an endpoint that batches
  concurrent requests (vLLM); on any other engine the requests queue
  and the harness cannot tell, so `auto` falls back to sequential.
- **Because:** ~85–90 % of a unit's wall is one decode stream at ~28
  tok/s against an engine that can batch many; the harness's own
  per-unit overhead is ~1 s. Ten serial units was the whole cost.
- **Bites at:** a unit that relied on a non-contract neighbour's edit
  (a verifier failure is where it shows); reading `stage_wall` per unit
  as if the units had run alone.
- **You find out:** **surfaced** — the run banner prints `parallel
  implementers: <reason>`; the run manifest and the record carry
  `parallel` (`workers`, `waves`) and `implement_wall_seconds` beside
  `implement_units_sum`; `--parallel 1` restores the chained order.
- **Source:** ADR-063 (2026-08-22).

### C-52 — A unit the planner did not name is not tried
- **Cannot tell you:** that every unit the change truly reaches was
  attempted. On the planner path (ADR-064) a unit with no
  planner-named file in its interior is not spawned at all — the
  planner's naming is the selector, and the planner is a one-shot 7B
  opinion (C-47), so a file it failed to name is a unit that never
  runs.
- **Because:** the re-probe showed unnamed units spend a whole session
  planning edits to another unit's file; one session is alive at a time
  at ~28 tok/s, so a do-nothing session is the dominant waste.
- **Bites at:** a change whose real site the planner missed — no unit
  edits it, and the miss reads as "the model could not fix it" rather
  than "we never pointed a unit at it".
- **You find out:** **surfaced** — the record carries
  `units_not_selected` with each unit's reason and the orchestrator
  inbox gets a `not-selected` note; the lexical fallback (no planner)
  keeps every unit, and `hobbes run --from-proposal` without staging is
  the un-selected path.
- **Source:** ADR-064 (2026-08-22).

### C-53 — In a benchmark, a human-first unit may run anyway
- **Cannot tell you:** that a benchmark's harness arm honoured the
  derivation contract's human-first shape. ADR-047 parks a unit whose
  unresolved complement rivals what the graph sees (no writes, a human
  first). `hobbes bench run --human-first spawn` runs such a unit with
  its write scope kept, because a benchmark has no human to hand it to
  and a parked unit is an empty patch counted against the harness
  (ADR-071). The complement stays in the unit's brief; the contract's
  *policy* half is waived for that run.
- **Because:** sympy-13852's gold file sat in a 1,783-site unit, 87 %
  unresolved — parked in every run, so its owner never ran. Max's D2
  rule for benchmarks Hobbes runs alone (the manual gate is off) is the
  analogue.
- **Bites at:** reading a benchmark solve on a human-first unit as
  evidence the derived context was sufficient — the agent was told what
  it could not see and went ahead; a human was the contract's answer.
- **You find out:** **surfaced** — the run banner states the mode; each
  such unit's record reads `human-first: spawned anyway (--human-first
  spawn, C-53) — <reason>`; `run.json` carries `human_first`. The
  default is still `park`, and `hobbes run` has no such switch.
- **Source:** ADR-071 (2026-08-22).

### C-54 — A compound shell command is resolved per segment, and its filters must be named
- **Cannot tell you:** that every shell command a session runs will be
  judged as the model wrote it. The policy engine now splits a command
  on top-level `&&`, `||`, `;`, and `|` and resolves each segment on its
  own (ADR-075): the command is as permitted as its least-permitted
  part, and a leading `cd <dir>` or `VAR=value` prefix is handled so it
  cannot hide the command under it. The split is quote-aware but
  conservative — an unbalanced quote falls back to matching the whole
  string, never more permissively.
- **Because:** the anchored glob (ADR-001) matched a whole command
  string, so an allowed rule like `python -m pytest*` could not see past
  a `cd /work &&` prefix or an env-var assignment, and two allowed
  commands chained with `&&` matched nothing — all three fell to the
  box floor's `escalate`, which on a benchmark expire-denies with no
  approver. In `five-fresh-27b` that escalated **104 of 253** exec calls
  and starved the harness arm (implementers could not run their tests,
  verifiers could not run the suite, some could not commit). The old
  behaviour was also *unsafe*: `git status && rm -rf /` matched
  `git status*` and ran the `rm`; per-segment resolution closes that.
- **Bites at:** a pipe or chain into a tool the policy does not name —
  it now escalates rather than riding the head command's allow. The
  benchmark box policy names the common read-only filters (`tr`, `awk`,
  `wc`, `sort`, `uniq`, `cut`, `xargs`, `tee`, `grep`, `sed -n`, `head`,
  `tail`, `cat`); a repo policy that relied on the old `*`-swallow for a
  chained command must add the segment's rule.
- **You find out:** **surfaced** — the flight log records the decisive
  segment's rule per exec, `hobbes policy resolve "<compound>"` shows
  the **decisive segment's** rule (not every segment's — corrected
  2026-08-23), and the box policy carries a comment naming
  why the filters are listed.
- **Source:** ADR-075 (2026-08-22).

### C-57 — Requirement coverage is ownership by named file; the imperative diff is lexical
- **Cannot tell you:** that a plan whose coverage reads `covered` is
  *complete* — only that every requirement the planner **wrote** names a
  file some unit owns. A requirement the planner never wrote is not in
  the list to be covered (the decomposition is the planner's, a model
  opinion like its seeds — C-47); a requirement written against the
  wrong file is "covered" by the wrong unit; one that names no file is
  given to the single unit the plan lies in, by containment, not by
  reading it. Under `--coverage assign`, a leftover is handed to the seed
  unit by the orchestrator — a fallback, not the planner's guarantee —
  and a planner that names no resolvable file runs on the lexical seeds
  with no check at all (`lexical-fallback`); under `strict` both are
  plan errors after the one re-plan (ADR-093, D5).
  Nor can `imperatives_unmentioned` tell you the planner *dropped* a
  requirement: it is a token overlap between the proposal's imperative
  sentences (a pinned verb list, modals) and the handoff text, with a
  crude stem. A paraphrase reads as dropped (xarray's three "IMO it
  should be `coord`" sentences, every rung); a sentence that shares
  words with the handoff reads as kept even when its substance is gone.
- **Because:** judging whether prose requirements are *meant* by a
  handoff needs a model, and the checker is deterministic by P1 — so it
  checks the one thing it can observe (a named file resolving to an
  interior) and measures the rest lexically, saying so (ADR-085).
- **Bites at:** reading `coverage: covered` as "the plan is right"; reading
  `imperatives_unmentioned: 0` as "nothing was dropped"; reading
  `assigned` as planner work.
- **You find out:** **surfaced** — every partition record carries
  `coverage` with each requirement's `source` (`named-file` |
  `contained` | `assigned`) and the `uncovered` list; an assigned
  requirement says so in the implementer's own brief ("assigned to you
  by the orchestrator … C-57"); the verifier's brief lists the
  requirements so an unmet one is a reported id, not a silence; `hobbes
  bench report` prints the status counts and the imperative count
  labelled `lexical, C-57`; `hobbes bench run` states the mode before a
  run. The removal test (ADR-084 §3; `--proposal-in-brief` as control)
  is the only evidence that a covered plan was complete *enough*.
- **Source:** ADR-085, built 2026-08-23 on ADR-084's frame.

---

## Superseded constraints in this segment

A limit that was never lifted but whose path no longer runs. The
concession is intact — it would return with the path — so the entry keeps
its number and its full text, plus a **Was / Superseded by / Would return
if** line, and the debt summary does not count it among the active.

### C-55 — The DeepSWE aid is derived without the planner stage
*(Superseded 2026-08-23. Was: the Pier aided arm's aid came from the
lexical map only. Superseded by: P12/ADR-082 retracted the aided arm as a
Hobbes test; the decomposed run's planner is now the
requirement-decomposer (ADR-084/085). Would return if: `deepswe_aid.py`
is used for a run presented as a Hobbes arm — `deepswe_run_arm.sh`
refuses that arm name.)*
- **Cannot tell you:** the planner's *approach* — the prose read of where
  the mechanism lives and what the fix looks like — on a DeepSWE run. The
  aid Pier injects (ADR-078, `scripts/deepswe_aid.py`) is assembled
  deterministically: `hobbes plan`'s lexical seeds for the starting
  files, graph symbols whose capitalised name the instruction mentions,
  their one-hop neighborhood, and the tests that reach the seed module.
  No model reads the repo before the agent does.
- **Because:** the planner stage lives in our own harness (`run_staged`,
  ADR-059) behind `hobbes-session`; the Pier path runs nothing of ours in
  the container, and the injection seam was prototyped first with the
  pieces that need no session. Symbol selection by name match is the
  C-36 lexical-seed limit restated at the symbol grain: a symbol the
  instruction names by behaviour rather than by name is not in the aid.
- **Bites at:** a task whose instruction names no class and whose seed
  module is the wrong one — the aid then says so (`the planner resolved
  nothing specific`) and the arm is the baseline plus a disclaimer.
- **You find out:** **surfaced** — the aid block itself carries the line
  `derived without a planner pass: files from lexical seeds, symbols by
  name match (C-55)`, so the agent and anyone reading the trajectory see
  what the context is made of.
- **Source:** ADR-078 (2026-08-22).

### C-56 — The two arms do not measure the same thing: repo recall in the pure arm, an off-distribution prompt in the aided arm
- **Cannot tell you:** how much of a *pure* success on an original task is
  the model's memory of the **repository** (its layout, idioms, the
  library parsers in its corpus) rather than reasoning; DeepSWE's
  originality bounds recall of the *patch* only. Nor whether a gap
  between arms is context *quality* or prompt *shape*: every agent
  trajectory in pretraining discovers context through tools, none
  receives a derived-context block, so the aided arm is off-distribution
  and the model may under-trust or over-read it (the first 27B run took a
  bare file name as "read the file", all 1,085 lines).
- **Because:** the pure arm is a fight between memory and ability that no
  score separates (Max, 2026-08-22; the C-39 finding generalised from
  verbatim-patch recall to partial repo familiarity), while the aided arm
  more directly shows the model *using* what Hobbes hands it — so the two
  arms answer different questions, and a side-by-side reads as a
  comparison it is not.
- **Bites at:** any pure-vs-aided table read as "Hobbes helped / hurt";
  any pure success read as capability.
- **You find out:** **surfaced** — `docs/benchmark-hypotheses.md` carries
  the reading rule and every results table since 2026-08-22 notes it; the
  candidate instruments are a per-(model, repo) familiarity probe
  (reproduce a named function with no tools; verbatim-match rate beside
  every pure score), an observation-shaped aid (the context delivered as
  the agent's first tool result, in-distribution) to test the shape
  confound directly, and a solution-shape diff against known library
  implementations. None built yet.
- **Source:** Max's rethink, 2026-08-22, after the first 27B pair (ADR-080).
- **Was / Superseded by / Would return if** (moved 2026-08-23): *was* the
  reading rule for the Pier pure-vs-aided pairs; *superseded by* P12
  (ADR-082), which retracted every single-agent pair as Hobbes evidence,
  and by the instruments it asked for — `deepswe_familiarity.py`,
  `deepswe_solution_shape.py`, `deepswe_read_volume.py` (ADR-081), so
  "none built yet" above is historical; *would return* the day a
  pure-vs-aided table is read as a Hobbes comparison again.

---
