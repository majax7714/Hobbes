# docs/calvin — the Calvin harness (product)

This directory holds **Calvin as it runs today**: the harness that does the work (`hobbes dispatch`,
ADR-107, ADR-112), and the role it serves. It is part of the Hobbes layer, not an experiment.

| file | what it is |
|---|---|
| [`calvin-harness.md`](calvin-harness.md) | The harness: the stack under the doer (§2) and its validation rule (§4) |
| [`calvin-charter.md`](calvin-charter.md) | The role: what Calvin is for, independent of how it is built |
| [`sessions/`](sessions/README.md) | One log per dispatched session, and the tracker (`pipeline/scripts/calvin_tracker.py render`) |

**The keyed rounds that produced it** (M0, M0-Go, M0-Gate) are Calvin's history and the evidence for
the harness as **the accepted lower bound for Calvin as a product**. They live with the model programme
in [`../experiments/calvin/keyed-rounds/`](../experiments/calvin/keyed-rounds/). **The model programme**
("a model that can only code", closed for now on 2026-09-28) is
[`../experiments/calvin/`](../experiments/calvin/README.md). Two things share the name: the harness is
here, and the model is there.
