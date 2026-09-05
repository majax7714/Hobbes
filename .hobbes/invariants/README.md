# invariants/

Confirmed invariants for the Hobbes repo itself — one YAML record per
file, `<id>-<slug>.yaml`, following the schema in architecture §5 as
made precise by **ADR-024** and reshaped by **ADR-039** (V2.M6): `id`,
`statement` (the prose a human reads), `scope`, `status`, `check`
(how it is held — see below), and `guarded_by`.

`check` decides the rest of the shape:

- `check: graph` — carries a top-level `rule` block; the unified
  checker judges it against the graph on every review, tier-aware
  (semantic evidence proves, syntactic evidence suspects — except on
  `ext:`/`env:`/`tf:` edges, where syntactic is the only form that
  exists and counts as proof). No CI config is emitted.
- `check: emit` — carries `rule` plus `compile.target`; `hobbes
  invariants compile` writes the CI config, and the checker still
  answers in-process wherever the graph can see the rule, so the two
  verdicts can be held against each other.
- `check: soft` — no rule, no compile; a reviewer session judges it
  and must cite evidence.

Records enter as `status: inferred` from the M5 narrative pass, land in
`.hobbes/derived/docs/invariants.inferred.yaml`, and reach this
directory only when a human promotes them — that promotion is a
physical act, not a status flag (ADR-019). `retired` records stay here
as history rather than being deleted.

Only `confirmed` records compile (`hobbes invariants compile`) and
receive review verdicts (`hobbes review`).

I-7..I-11 are reworded restatements of I-1..I-6, approved through the
surface on 2026-08-15 before the queue could show neighbouring
confirmed records (C-21); where they overlap, the I-1..I-6 record is
the one of reference. **I-7, I-8 and I-11 were retired on 2026-09-05**
(W0's duplicate pairs): each added a second soft verdict for `hobbes
review` to spend a session on and a second `list_invariants` line with
nothing of its own; their files stay as history with the reason in the
header. I-9 (kept on Max's approval, its own correction recorded) and
I-10 (restates I-5) stand as confirmed.
