# ADR-055 — The benchmark harness: `hobbes bench`

**Date:** 2026-08-21
**Status:** accepted — built quota-free; **no live run** (the first one
is gated on the owner's decisions listed under Consequences)
**Amends:** `docs/hobbes-architecture.md` ("Where this is going"; §6.2
new; §8's D-table); `docs/benchmark-hypotheses.md` (the harness and
the pre-run observations); `docs/constraints/README.md` (C-39, C-40; C-36 and
C-38 amended); `docs/future_additions.md` (the harness entry shrinks
to what remains)

## Context

ADR-052 set the verification method for the derivation programme and
deliberately did not start it: Hobbes as a harness under a known
software-engineering benchmark, against the same models run pure,
with H1–H3 preregistered. D1 passed review on 2026-08-21 and the D2
base (ADR-054) passed the same day; the owner's direction for this
session was to proceed to the harness unless something blocked it.

Reading the D2 base against what a live run needs found one thing the
review could not have seen, because no session was ever spawned: **the
sandbox cannot run Claude Code today.** The image is Alpine (musl),
`claude` 2.1.238 is a glibc-linked ELF that is not mounted into the
container at all (only `~/.claude` is), and the session network is
`none`. That blocks the first *live* run, not the harness's
construction — and the fix carries a design decision that is the
owner's (a session with a route to the network contradicts
architecture text that calls the absence of one the enforcement). So
this ADR builds everything that does not depend on that decision,
exactly as D2 was built: quota-free, against stand-ins that write the
real shapes.

## Decision

### 1. `hobbes bench` is a loop, not an agent

`pipeline/src/hobbes/bench/`: `select` applies the instance protocol;
`run` checks each selected instance out at its base commit and runs
the arms per model, one record per (instance, arm, model), resumable;
`--evaluate` hands the patches to the benchmark's own evaluator;
`report` lays the records against H1–H3 and **interprets nothing** —
rates, slopes, per-solved means, sample sizes, unobserved terms named.

### 2. Instances are a local file; the protocol counts its drops

The schema is SWE-bench's (Verified, Lite, SWE-rebench and
SWE-bench-Live share the fields used). `pipeline/scripts/bench_fetch.py`
exports a Hugging Face split to JSONL under uv's inline metadata, so
the pipeline carries no dataset dependency. The protocol is a
`created_at` cutoff plus repo/id filters and a prefix limit; every
drop is counted by reason in `run.json`. **Contamination is bounded,
not proven** (C-39) — the selection says so in its first lines, with
or without a cutoff.

### 3. Two arms from one checkout

- **Harness**: `ingest` → `plan` (the issue text is the proposal) →
  `run` (ADR-054) → `git diff base..hobbes/<task>`. An instance whose
  issue seeds nothing lexically is the outcome **`no-seed`** — counted
  against the harness arm, never dropped; dropping it would inflate
  the arm under test. The plan summary (seeds, unresolved terms,
  units, contracts, gate), the partition record's per-unit terms
  (faults, rework, reflections) and the loss ride the record: the
  error stream ADR-052 asked for.
- **Pure**: Claude Code on the same checkout, its own tools, no MCP
  server, no policy, no derived context; the issue as the prompt. It
  runs where `claude` runs — the host — with shell access to the
  checkout.

The candidate patch is the working tree with everything staged (pure)
or the integration branch (harness), `.hobbes/` excluded either way.

### 4. One meter for both arms

Claude Code's JSON result envelope (`usage`, `total_cost_usd`,
`duration_ms`, `num_turns`) is the meter. The pure arm reads it from
the subprocess; the harness arm reads each unit's `session.log`. For
that, `hobbes-session`'s default command now passes
`--output-format json` and gains **`--model`**, so the harness arm
names its model the way the pure arm does (H1 is a ladder). A session
that emitted no envelope is **unobserved**, and the H3 row says how
many solved instances were — never a zero that reads as cheap. The
harness arm's wall time is observed from outside the sessions even
then.

### 5. The verdict is the benchmark's

`swebench==5.0.2`'s `run_evaluation`, pinned, run as a subprocess via
`uv run --with`, over a predictions file per (arm, model); its report
is the verdict (`resolved | unresolved | error | empty-patch`,
`unjudged` when it says nothing). Hobbes does not reimplement per-repo
test commands, environments, or log parsers. That makes the evaluator
a provider in P9's sense — **C-40**, with the version on the entry. It
speaks the Docker API; rootless podman serves it through its socket.

### 6. Depth is a declared proxy

H2 needs a depth axis the benchmark does not carry. The harness uses
the gold patch's file count, bucketed 1 / 2–3 / 4+, and says "a proxy"
on every report and selection. On SWE-bench Verified the buckets hold
429 / 61 / 10 of 500 — H2's slope will rest on thin top buckets there,
which is a reason to prefer a dataset with more spread, stated now.

## Pre-run observation (quota-free, not a result)

Eight `psf/requests` instances from Verified were checked out,
ingested (lane A only) and seed-resolved against their issue text:
**8/8 seeded** (no `no-seed`), and the seed set touches a gold-patch
file in **4/8**. The misses are C-36's real shape on real prose:
dotted `package.function` names (`requests.get`, `requests.Session`)
do not resolve because seeds match symbol *names*, not dotted
suffixes; trailing punctuation makes prose look code-shaped (`fine:`,
`it.`, `label.`); and generic words (`data`, `json`, `content`,
`session`) seed spuriously. Recorded in `benchmark-hypotheses.md` as
a pre-run observation and in `future_additions.md` as the first
candidate adjustments — **not applied**: the loop adjusts from
verdicts, and there are none yet.

## Consequences

- **What the first live run needs, and who decides** — in order:
  1. *A session image that runs Claude Code* (owner's call on the
     network): a glibc base, the host `claude` binary mounted ro, a
     credential, and a network mode that is not `none`. The
     architecture's "a route to the network is absent" is true of
     sessions today and would stop being true of live ones; the
     concession should be registered when it is taken, with what
     narrows it (an egress allow-list to the API host if podman's
     network stack permits it, else stated as full egress).
  2. *Containment of the pure arm*: it runs on the host with Bash
     over a benchmark checkout. Acceptable on a dev box by the same
     reasoning as daily use; a container is the cleaner shape and
     reuses item 1.
  3. *The evaluator's engine*: `systemctl --user enable --now
     podman.socket` and `DOCKER_HOST` pointed at it; SWE-bench's
     per-instance images are pulled on first use (large).
  4. *A post-cutoff instance set*: Verified's newest instance is
     2023-08-07, so a 2025 cutoff selects zero of 500. SWE-rebench
     or SWE-bench-Live are the candidates; the choice is recorded in
     `run.json` either way.
  5. *Quota*: every live instance spends the model's quota on both
     arms; the owner names the first instance set and model ladder.
- Metering is no longer unmetered by design (C-38 amended): it is
  observed when sessions emit the envelope, which the default command
  now requests.
- 753 pytest (+30: protocol, checkouts and patches, meters, both arms
  against stand-ins — the harness arm through a *real* ingest and
  plan on a local repo — the evaluator plumbing, records and report,
  the run loop's resume and write-back, CLI exits). Go +2 (model
  pinning, JSON envelope on the default command).
