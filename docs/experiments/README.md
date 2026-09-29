# Experiments — two programmes, one root

Hobbes the layer is versioned and reviewed ([`../hobbes-architecture.md`](../hobbes-architecture.md)).
The experiments here are not (ADR-103): they test ideas the layer could serve. They split into two
programmes (Max, 2026-09-28).

**The shared root: reduce the room for chaos.** Hand a model less to get wrong, in a form that makes a
wrong move visible. The two programmes attack that problem at different layers, so a result in one is
not a result in the other.

| | [Mapped agents with derived context](mapped-agents/README.md) | [Calvin — a model that can only code](calvin/README.md) |
|---|---|---|
| **Thesis** | Smaller tasks with better context are easier to complete, which lets smaller models compete against bigger ones. | A model with constrained input and only the ability to code, perhaps in one language (C for now), is more efficient and better aligned per task. A deliberately looser idea. |
| **What it shrinks** | The task and the context (the planner, work units, derived briefs). | The model's input and its capability (a coder, not an agent). |
| **Where it stands** | Parked (the standing policy). No H1 claim earned. The removal A/B re-run on the 7B is first in line. | Closed on its lattice (2026-09-29, Max). The reassessment ([`calvin-reassessment.md`](calvin/calvin-reassessment.md) §11–§13) found the lattice's residual deterministic: compiler, lifter, solver, lookup. It reopens only on a target where the job is not derivable. Its floor, Shanks (the gate and the harness), is in use. |
| **Its records** | SWE-bench and DeepSWE runs, agent mapping, TTT | The keyed rounds (the lower bound), Atlas-0, the sqlite-vector lattice (E0–E4, D-11–D-16) |
| **Tooling** | `pipeline/src/hobbes/{derive,run,bench,ttt}`, `pipeline/scripts/`, `bench/ttt/` | `bench/calvin/` (`lattice/`, `e3-draw/`, `templates/`), `bench/atlas0/`, `pipeline/scripts/calvin_probe.py` |

## The rule: read the register before proposing

Each programme's README carries an **observed register**: what has been measured, scoped exactly as far
as its evidence reaches, with the source. Its purpose is to stop anyone from experimenting again on
something already observed.

- **Before proposing a run, read the register of its programme.** A proposal names the entries it
  builds on, and says why it is not a re-run of any of them. A different model, size, target or rung
  counts as a new question only where the entry's "does not show" line leaves it open.
- **A result lands in its record first** (the experiment's own page, dated, with the numbers). The
  register then gains one line pointing at it. Nothing is re-scoped after the numbers arrive (ADR-052,
  P11).
- **An entry that a later run overturns is marked, never deleted.** It gets `superseded by <entry>` or
  `retracted (<reason>)`, as the constraint register does (P8).

Numbering is per programme: `MA-n` for mapped agents and `CV-n` for Calvin.

## Not here

- **Shanks, the harness** (`hobbes dispatch`, ADR-107; named by ADR-152) is product, in
  [`../shanks/`](../shanks/README.md). It is how work is done, and it is not an experiment. The keyed rounds that
  left it are Calvin's history. Shanks is Calvin's accepted lowest floor, not Calvin's design.
- **The oracle lane and the comparative programme** grade the graph ([`../oracle/`](../oracle/),
  [`../comparative/`](../comparative/)). They are the layer's evidence, not experiments on an idea.
- **Spend:** API and Modal compute only on Max's word for a named run and its ceiling
  ([`../session-handoff.md`](../session-handoff.md), standing policy).
