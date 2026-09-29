# bench/ — experiment and grading tooling, never product

Nothing here is versioned with the layer (ADR-103). Each directory serves one programme. The
programmes, their theses and their observed registers are in [`../docs/experiments/`](../docs/experiments/README.md).
Read the register before proposing a run.

| directory | serves |
|---|---|
| `calvin/lattice/`, `calvin/e3-draw/` | **Calvin** — the sqlite-vector lattice programme ([`calvin-experiments.md`](../docs/experiments/calvin/calvin-experiments.md), ADR-151; closed for now) |
| `calvin/templates/` | **Calvin** — the keyed rounds' M0 template and gold fills ([`keyed-rounds/`](../docs/experiments/calvin/keyed-rounds/)) |
| `atlas0/` | **Calvin** — Atlas-0 ([`atlas-0.md`](../docs/experiments/calvin/atlas0/atlas-0.md); held) |
| `ttt/` | **Mapped agents** — the TTT proposals file ([`ttt/`](../docs/experiments/mapped-agents/ttt/), ADR-099) |
| `oracle/` | **Neither: the layer's own evidence.** The oracle lane grades the graph (ADR-089) and the foreign tools' graphs (ADR-101) |

The mapped-agents harness itself (`hobbes bench`, `hobbes plan`, `hobbes run`) is product code under
`pipeline/src/hobbes/`, and its drivers are in `pipeline/scripts/`.
