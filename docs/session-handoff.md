# Session handoff — the single resume point

**Rewritten 2026-08-29: Java landed (ADR-096) — six milestones, four
compiler-graded cells, one decision waiting on Max.** Read this, then the recent
`docs/BUILDLOG.md` entries (2026-08-28/29) for how the current state
was reached, and `docs/workstreams.md` for the backlog by owner.
History lives in the BUILDLOG; this doc is rewritten, never appended
into a pile.

---

## ⇢ START HERE NEXT SESSION: ratify or reverse **C-66**

**The one open decision, and it is a posture decision, so it is Max's.**
`index-java` is the **only** lane B step that executes repo-authored
code *and* keeps a network. Every other index step runs
`--network none` behind a fetch container that downloads but executes
nothing (ADR-092's phase separation).

**Why Java has no such phase:** scip-java is a javac plugin, so it needs
the classpath only the build resolves — and neither build tool separates
resolving from evaluating. Gradle resolves while running `build.gradle`
(which is code); Maven's `dependency:go-offline` does not reproduce a
real build's resolution (measured on jsoup: `${os.detected.classifier}`
comes from a build extension, and the subsequent offline compile fails
on three test artifacts).

**What is still guaranteed:** the container is the boundary — rootless,
the Hobbes cache root its only writable mount, the repo staged as a
copy, and the build never runs on the host (C-64 refuses without the
image). The canary (`tests/fixtures/canary-java`) proves a Maven build
step bound to `generate-sources` runs, and reaches neither a planted
host secret nor the host filesystem.

**What is conceded:** an untrusted Java repo's build logic can reach the
network from inside that container while indexing. Registered as
**C-66**, surfaced on every Java ingest and in the `containment` stamp.

**To reverse:** one field —
`containment.PROFILES["index-java"].network = "none"`. Cost of
reversing: Gradle repos lose lane B entirely and most Maven repos lose
it on a cold cache; Java's claim shrinks to roughly the Severed-Chains
cell (lane A, 100% precision, 23.5% recall). Nothing else in the build
depends on the choice.

**Read first:** ADR-096 decision 3 → `docs/constraints/extraction-java.md`
C-66 → the four cell records in `docs/oracle-cells/*-java-2026-08-29.md`.

*(Also still open from before, unrelated: ADR-092's four embedded
decisions, listed below.)*

---

## WHERE THINGS STAND (2026-08-29)

- **Extraction:** every compiler-graded oracle cell at 100% on every
  tier it reaches (Go/TS/Rust/**Java**); Python trace-graded (C-60). The
  misses are C-58 (closures, function values, dispatch — surfaced
  *partial* as `below-floor`) and Rust's generated code. Records:
  `docs/oracle-cells/`, `oracle-misses.md`, `oracle-defects.md`
  (+ review/tally).
- **Java is the sixth language (ADR-096, this session).** Lane A
  (`javasource.py`), scip-java 0.13.1 contained, the JUnit inventory,
  a javac+CHA oracle (`bench/oracle/java`, O8), and a §3.8 row on four
  repos — jsoup, spring-petclinic, and **two drawn at random**
  (spring-data-elasticsearch, Severed-Chains). All four at **100%
  precision, 0 contradicted**; recall 66–98% where lane B runs and
  **23.5% on the one where it could not** (C-67's first sighting:
  scip-java cannot attach to every Gradle build). **One decision waits
  on Max: C-66** — `index-java` is the only index step that executes
  repo code *and* keeps a network, because in Java the build *is* the
  dependency resolution. Reversing it is one field in
  `containment.PROFILES`; the cost of reversing is Gradle repos and
  most Maven ones losing lane B.
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

0. **C-66 — see the block at the top of this file.** Then the four
   ADR-092 decisions below. Nothing blocks on either; Java works either
   way, with a much smaller claim if C-66 is reversed.
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
   `maven-toolchains-plugin` case (C-67); egress narrowing for C-66; a
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
