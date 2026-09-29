# ADR-152 — The harness is Shanks; Calvin is the model

**Date:** 2026-09-28 · **Status:** accepted (Max, in session: "Full rename") · **Owner:** Max · **Source:** the
reassessment of Calvin's design ([`calvin-reassessment.md`](../experiments/calvin/calvin-reassessment.md)), and Max:
*"calvin might not be a typical llm, it could be some different form of model. the gated harness which was called
calvin we can rename shanks to keep the difference … shanks was calvins accepted lowest floor from an experiment …
however it looks to treat a symptom barely more than being anything worth pursuing or clashing with calvins
eventual, which is why the rename is warranted."*

## Context

Since ADR-107 (2026-09-12), two things have shared one name:

- **The harness.** `hobbes dispatch` hands one task to a frontier doer (Claude Code) inside `hobbes-session`,
  behind the egress allowlist. `hobbes gate` judges the finished diff at its parent, `hobbes verify` runs the
  guarding tests, and one log per session is written. ADR-107 called it "Calvin as a harness".
- **The model programme.** This is a model or tool that can program in a language and is intentionally not
  general. The charter defines its role, ADR-151 and the lattice records are its evidence, and the reassessment
  asks what form it should take.

The harness is what survived the keyed rounds (M0, M0-Go, M0-Gate, 2026-09-03 to 09-11). ADR-107 closed those as
an approach, and the BUILDLOG entries of 2026-09-11 and 2026-09-12 record why. What held up was one shape: a
frontier agent does the work, and the gate judges its diff. That is Calvin's accepted lowest floor. It is recorded
in the BUILDLOG and ADR-107, and nowhere in the docs a reader starts from.

The harness treats a symptom. It checks a frontier agent's finished work and changes nothing about what writes
it. Keeping Calvin's name on it lets the floor read as Calvin's design, and lets the design lean toward the floor.

## Decision

1. **Calvin names the model programme and its eventual artifact:** a model or tool that can program in a language
   and is intentionally not general. It is not assumed to be a typical LLM. The charter's §8 already names a
   pointer decoder and the Ledger Machine, and the reassessment adds decoder-, DSL- and search-shaped routes. The
   charter moves to `docs/experiments/calvin/calvin-charter.md`, beside the programme it defines.
2. **Shanks names the harness:** `hobbes dispatch`, the session, the egress allowlist, the gate, the verify step
   and the per-session log.
   - The docs are `docs/shanks/` (`shanks-harness.md`, `sessions/`).
   - The box policy is `shanks.box.policy`.
   - The tracker is `pipeline/scripts/shanks_tracker.py`.
   - The commands keep their names.
3. **Shanks's standing: Calvin's accepted lowest floor, and not Calvin's design.**
   - Shanks stays the way work is done.
   - A Calvin result is measured against Shanks.
   - Nothing in Calvin's design is bound to extend Shanks, keep its shape, or fit inside it.
4. **Records keep the name they were written under.** None of the following is rewritten: the BUILDLOG, the past
   CHANGELOG entries, ADR-107's text, the keyed-round records, and the bodies of the 90 session logs written before
   this. Links in current docs, ADRs and records point to where the files now are. That is a link fix, not an edit
   to what they say.
5. **The retention guarantee covers both paths.** A session record is never training data (ADR-107's retention
   amendment, C-129). `ttt.units.units_from_git` refuses `docs/shanks/sessions/` and the old
   `docs/calvin/sessions/`, because git history still holds the first 90 there. The lattice corpus refuses a root
   holding either path. Each path keeps its own test (P10).

## Consequences

- What the layer says changes: the CLI's help, and the directory the harness writes its logs to. That makes this a
  patch (0.2.72-beta, ADR-103), and the image is rebuilt (C-65).
- The tracker's area table keeps `pipeline/scripts/calvin_tracker.py` beside the new name, so past sessions keep
  their area. Its rendered block moved by one line, and no session changed area.
- "Calvin" in a current doc now means the model programme only.
