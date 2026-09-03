# Session handoff — the single resume point

**Rewritten 2026-09-02: the four-repo extraction test ran; ADR-098
fixed Go build constraints (C-71); nine findings registered, not fixed
(C-72–C-80); quic-go oracle-graded at binary roots.** Read this, then
the recent `docs/BUILDLOG.md` entries (2026-09-01, 2026-09-02) for how
the current state was reached, and `docs/workstreams.md` for the
backlog by owner. History lives in the BUILDLOG; this doc is rewritten,
never appended into a pile.

---

## ⇢ START HERE NEXT SESSION: the nine registered-not-fixed entries, then the ADR-092 decisions

**What happened 2026-09-02.** Four random public repos, one per
language, each run through the knowledge piece by an agent under a
stop rule (BUILDLOG). No semantic edge wrong anywhere; two repos
stopped on lane disagreements. Max: "fix build tag and flag rest in
constraints." The build-tag one is fixed (ADR-098, C-71: lane A's Go
fallback resolves a constraint-split name by the caller's own
`build_constraint` or abstains into `build-tag-set`; a `scip-go`
record names the files the one-configuration index left dark). The
other nine are **registered with their candidate fix named** and wait
on Max's call, worst first:

| C-n | what | size of the fix |
|---|---|---|
| C-76 | the summary's "call edges" counts `uses` — reads *larger* than the truth | one line, `cli.py` |
| C-77 | `list_blind_spots` omits `below-floor` | one row in `knowledge.go` `tailMeanings` + image rebuild |
| C-78 | `http-go` fires on any `Handle` (`windows.Handle(fd)` → false C-5 records) | receiver check + `_is_conversion` |
| C-75 | `hobbes lanes` counts the join's fallback module edges as lane B | filter by semantic evidence |
| C-79 | no `dependency_coverage` for `setup.py`-only Python repos, silently | read `setup.cfg`/`requirements*.txt`; record when nothing declares |
| C-74 | pnpm/npm workspace links dangle in the container; record blames the helper | follow links inside `node_modules` when collecting mounts |
| C-72 | Rust fallback binds `Type::method` by last segment | filter by the path head's `impl`, else abstain (`path-call`) |
| C-73 | a repo directory symlink is walked as a second copy | record at discovery; alias or mark the copy |
| C-80 | `super().m()` / `f().m()` not a Python site; `who_calls` glosses it "not a call" | detect the receiver shape; reword the `uses` gloss |

Also open from the same test: `hobbes lanes` (and CI) exits 1 on
C-70's registered shape (quic-go: 17 sites of 6,743) — decide whether
a registered limit should fail the self-test.

**Still open, unrelated:** ADR-092's four embedded decisions (below).
Nothing blocks on them.

**C-66 is settled** (ADR-097, 2026-09-01). **Measured and parked
(W1):** the allowlisted egress proxy for `fetch-java` (topology in the
2026-09-01 BUILDLOG entry).

## WHERE THINGS STAND (2026-09-02)

- **Extraction:** every compiler-graded oracle cell at 100% on every
  tier it reaches (Go/TS/Rust/**Java**) — **quic-go (2026-09-02) at
  99.6% lower bound, 15 contradicted, all oracle-grain** (the test build
  vs. the binary build; graded at binary roots because the full RTA
  OOMs on this box, H-9); Python trace-graded (C-60). The
  misses are C-58 (closures, function values, dispatch — surfaced
  *partial* as `below-floor`) and Rust's generated code. Records:
  `docs/oracle-cells/`, `oracle-misses.md`, `oracle-defects.md`
  (+ review/tally).
- **The four-repo test (2026-09-02):** peft and date-fns pass with
  findings; quic-go and serde stopped on lane disagreements; findings
  are ADR-098 + C-71 (fixed) and C-72–C-80 (registered). Clones under
  `~/.hobbes/bench/extract-test-20260902/`. Register: 80 entries, 70
  active, 7 partial, 7 unsurfaced.
- **Java is the sixth language (ADR-096, 2026-08-29; ADR-097,
  2026-09-01).** Lane A (`javasource.py`), scip-java 0.13.1 contained,
  the JUnit inventory, a javac+CHA oracle (`bench/oracle/java`, O8), and
  a §3.8 row on four repos — jsoup, spring-petclinic, and **two drawn at
  random** (spring-data-elasticsearch, Severed-Chains). All four at
  **100% precision, 0 contradicted**; recall 66–98% where lane B runs and
  **23.5% on the one where it could not** (C-67: scip-java cannot attach
  to every Gradle build). **Lane B is two passes since ADR-097** — resolve
  with a network and no sources, index offline; the only executing step
  with a network is `fetch-java`, and the suite pins that its stage holds
  no `.java`. The oracle lane's own `java-build` keeps a single networked
  pass (bench tooling; the same shape applies when wanted).
- **Containment (ADR-092): built, all four phases, reviewed by Max.**
  Lane B and the O6/O7 oracles run only in `hobbes-session:local`;
  executing steps refuse on the host (C-64); `graph.json` carries the
  `containment` stamp and `built_by` (ADR-094); the knowledge proxy runs
  from the image via `sandbox/knowledge-serve` (C-65: rebuild the image
  after the proxy). Scope (P11): verified only on the runs made under
  it — this repo, rust_proj, the fixtures; every earlier cell is a
  host-run record. **Four embedded decisions still wait on Max's
  ratification** (ADR-092 §Decisions): contain-all vs executing-only;
  symlink targets at identical paths vs rewriting; one image vs a slim
  ingest image; network-by-phase (fetch containers) vs route filtering.
- **The harness worklist is empty.** D1–D4/D7/D8 (ADR-091) and D5/D6
  (ADR-093) fixed and validated with no model. Findings that are not
  defects (knowledge tools unused at the 7B rung; requirement text
  rendered as code; O4 planner variance) stay in
  `docs/adr085-validation-run.md`.
- **CI (ADR-095, this session):** `.github/workflows/ci.yml` — four
  suite jobs plus `scripts/ci-graph.sh <base>` (image → ingest → stamp
  check → lanes → every compiled checker → review → `lane_b` pytest).
  Validated on the box; **not yet observed on GitHub** — Max sees the
  first run when he publishes. One test deselected by name (below).
- **Max still holds the PATH fix** on his box (`~/.local/bin/hobbes` →
  `~/hobbes/...`, the ADR-094 incident). Always `uv run hobbes` from
  this checkout.

## NEXT (in order, none cleared to spend compute)

0. **The nine registered-not-fixed entries** above, on Max's call —
   five are one-to-ten-line fixes; and the C-70/CI question.
0b. **The four ADR-092 decisions** (§Decisions there): contain-all vs
   executing-only; symlink targets at identical paths vs rewriting; one
   image vs a slim ingest image; network by phase separation vs route
   filtering — the last now has two forms (ADR-092 §4 by what runs,
   ADR-097 by what the container holds). Nothing blocks on them.
1. **Watch the first CI run** when Max pushes; anything runner-specific
   (rootless podman as `runner`, rustup inside `podman build`) is fixed
   in `ci-graph.sh` / the workflow, not worked around.
2. **W0 residue** (`workstreams.md`): fix the deselected venv test with
   a real fixture venv; merge the three duplicate invariant pairs;
   `hobbes narrate` on this repo when Max clears the model spend.
3. **The removal A/B re-run** on a cleared 7B run — now un-confounded on
   D5; needs n large enough to split O4's planner variance. GPU-hours
   stated first (the compute-economics gate).
4. **Java follow-ups (W1), none urgent:** a Spring route pack; the
   `maven-toolchains-plugin` case (C-67); the allowlisted egress proxy
   for `fetch-java` (C-66's residual; topology measured, see the top of
   this file); the oracle lane's two-pass form; a
   Lombok/protobuf cell to size C-68, which the four cells left
   **unmeasured** (`excluded.generated: 0` on every one); a bytecode
   RTA only if CHA proves too coarse.
5. Collaborator onboarding per `workstreams.md`.

## STANDING POLICY (Max) — read before doing anything

1. **Experiments are PARKED** (2026-08-24). No run of any size without a
   fresh, explicit go from Max.
2. **The 7B is the instrument, by speed not capability.** Validate every
   mapping/architecture change on the 7B or with no model first.
   Compute-economics gate: ≥15 min of evaluation before any run over
   30 min; GPU-hours stated first.
3. **P12 (ADR-082): a Hobbes test decomposes, or it is not a Hobbes
   test.** The machinery enforces the label (ADR-086).
4. **The 27B is untouched** until the mapping fixes are validated on the
   7B, and only on a decontaminated set.

## PRACTICAL NOTES

- The image is **2.79 GB** since ADR-096 (three Temurin JDKs, Maven,
  the scip-java launcher: +1.1 GB) and must be built on the box
  (`sandbox/README.md`, ~5 min);
  `lane_b` tests skip without it. `scripts/ci-graph.sh HEAD~1` is the
  full local check.
- **The one deselected test:**
  `test_venv_environment_lists_the_venvs_own_distributions` fails under
  containment on its own assertion (the fake venv answers `{pip}`);
  `ci-graph.sh` names it. Untouched in the suite on purpose.
- `hobbes ingest --uncontained` on this repo executes the canary
  fixture's build script on the host — the disclosure working, not a
  bug.
- No-GPU instruments: `hobbes.run.coverage.imperatives_unmentioned` over
  stored handoffs, `pipeline/scripts/brief_sizes.py`, `derive_plan(...,
  lexical=False)`; the ADR-085 pair's records under
  `~/.hobbes/bench/adr085-validate-7b{,-control}/`.
- If a run is cleared (reference only — parked): warm the endpoint
  (short-timeout `/models` loop; Modal cold start ~10 min), then
  `hobbes bench run verified.jsonl --secrets secrets.txt --id <ids> --arm
  harness --runtime openai --llm-base-url <7B URL> --model
  Qwen/Qwen2.5-Coder-7B-Instruct --session-bin go/bin/hobbes-session
  --out ~/.hobbes/bench/<name> --stages plan,implement,verify --coverage
  strict --max-units 10 --max-turns 40 --max-tokens 1536 --parallel auto
  --evaluate --human-first spawn` (+ `--proposal-in-brief` for the
  control arm only). Evaluator on the local rootless-podman socket
  (`systemctl --user start podman.socket`); never `--eval-modal` (C-50).
  State GPU-hours first.

## Housekeeping

Commit to `main`; never `git push` (Max publishes). One ADR per design
decision; one BUILDLOG entry per session; every concession a `C-n` in
its segment file under `docs/constraints/`. Rewrite this doc; do not
append to it.
