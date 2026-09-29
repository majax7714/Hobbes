# docs/shanks — Shanks, the harness (product)

This directory holds **Shanks**, the harness that does the work: `hobbes dispatch` (ADR-107, ADR-112). It runs
the doer in `hobbes-session` behind the egress allowlist, gates and verifies its diff, and writes one log per
session. It is part of the Hobbes layer, not an experiment.

| file | what it is |
|---|---|
| [`shanks-harness.md`](shanks-harness.md) | The harness: the stack under the doer (§2) and its validation rule (§4) |
| [`sessions/`](sessions/README.md) | One log per dispatched session, and the tracker (`pipeline/scripts/shanks_tracker.py render`) |

**The name** ([ADR-152](../adr/152-the-harness-is-shanks-calvin-is-the-model.md), 2026-09-28). Until then the
harness was called Calvin: "Calvin as a harness" in ADR-107, and `docs/calvin/` in the records before that date.
The name now belongs to the model programme alone.

**Shanks's standing: Calvin's accepted lowest floor, not Calvin's design.** The keyed rounds (M0, M0-Go,
M0-Gate, 2026-09-03 to 09-11) ran Calvin as an experiment, and they closed as an approach on 2026-09-12. The BUILDLOG
of 2026-09-11 and 2026-09-12 has why. The one shape that held up was a frontier agent doing the work and
`hobbes gate` judging its finished diff, and Shanks is that shape with a session and an egress allowlist around it.
It treats a symptom, an unchecked diff, and changes nothing about what writes it.
- Shanks stays the way work is done.
- A Calvin result is measured against it.
- Calvin's design is not bound to it.

The keyed rounds live with the model programme in
[`../experiments/calvin/keyed-rounds/`](../experiments/calvin/keyed-rounds/). **Calvin**, a model or tool that
can program in a language and is intentionally not general, is
[`../experiments/calvin/`](../experiments/calvin/README.md): its charter, its register and its reassessment.
