<!-- Copied verbatim from ~/calvin/calvin-charter.md (its own repo, commit ee5ae5a, 2026-09-03) into this tree on 2026-09-04 so `docs/calvin-potential.md` links to a file that exists. The companion doc it names, `calvin-m0-socket.md`, was the M0 design's v1 title; the v2 is `docs/calvin-potential.md`. -->

# Calvin — charter

**Status:** proposed · **Type:** role definition (architecture-independent) · **Companion docs:** `calvin-m0-socket.md` (first experiment), ADR-099 (the run that motivated this), `olmo3-ttt-results.md`

This document says what Calvin is *for*, what it must and must not do, and what it needs from Hobbes. It does not say how Calvin is built. The Ledger Machine is one candidate implementation; a stock small model behind a deterministic grounder is another; a future architecture nobody has proposed yet is a third. Any of them is Calvin if it satisfies the contract in §4. None of them is Calvin if it doesn't.

---

## 1. The one-sentence job

**Calvin makes an orchestrator's intended change true against the repository at a specific commit — every reference resolved to something that exists or reported as unbound, every edit placed at an exact location, every affected site propagated — and it can prove what it read to do so.**

A compiler does not understand your program; it makes it consistent. A linker does not know what your code means; it resolves every symbol or fails loudly. Calvin is that layer for edits produced by a model that understands intent but cannot be trusted about the repo.

---

## 2. Why this role exists

The ADR-099 run measured a 7B model editing an unseen repo under three deliveries of context. The result that survives every caveat: with a manifest in the prompt, the model found the right files at precision 0.95 and still emitted symbol references that did not exist 82% of the time. Without the manifest, it invented every path it touched. With repo knowledge loaded into its weights, it stopped reading the manifest at all.

The literature says this is not a property of that model or that size. It is a property of the standard block: a transformer stores facts and routes context with the same gradient, storage is keyed by similarity so learning a fact perturbs its neighbors, and once an answer exists in the weights the optimizer prefers recalling it to reading it. A frontier model has the same block. It is better at intent and worse at the repo in exactly the way the 7B was, with more confidence.

So there are two different jobs in "write a correct change," and the same organ is bad at one of them no matter how large it gets. Calvin exists to take that job away from the organ that fails at it.

---

## 3. Position in the stack

```
  task (human, issue, orchestrator)
        │
        ▼
  ┌───────────┐   anchors, typed-hole template        ┌──────────────┐
  │  Hobbes   │ ───────────────────────────────────▶  │ Orchestrator │
  │ (truth @  │                                       │ (intent,     │
  │   SHA)    │ ◀─────────────────────────────────── │  fills)      │
  └─────┬─────┘   fills                               └──────────────┘
        │                                                     ▲
        │ template + fills + ledger (graph, tiers,            │ NULL list,
        │ testmap, co-change, partitions)                     │ questions
        ▼                                                     │
  ┌───────────┐   diff + NULL list + read-trace        ───────┘
  │  Calvin   │ ──────────────────────────────────────▶ policy / sandbox / review
  └───────────┘
```

Three parties, three kinds of knowledge:

| party | knows | is trusted about | is not trusted about |
|---|---|---|---|
| Orchestrator | the world, the language, the intent | what the change should accomplish | whether anything it names exists |
| Hobbes | the repo at this SHA, deterministically | what exists, what calls what, what tests reach what | what the change should be |
| Calvin | how to make an intent consistent with a repo | that every reference in its output is real or flagged | intent; it never decides *what*, only *whether and where* |

Calvin sits between the party that knows what and the party that knows where, and its whole value is that it refuses to guess about the second.

---

## 4. The contract

These hold for any implementation. They are testable without knowing what is inside.

### 4.1 Inputs

1. **A ledger** — Hobbes's derived layer at a SHA: symbols with spans, edges with tiers, testmap, co-change, impact, write partitions, lane-B types where present. Calvin reads only this for facts about the repo. It has no other source.
2. **A template** — Hobbes's structural expansion of the task into typed holes with spans and constraints (`calvin-m0-socket.md` §2.1). Calvin may also be handed a raw draft diff with no template; it must then treat every hunk as a `FREEFORM` hole and derive spans itself.
3. **Fills** — the orchestrator's content for holes. Assumed noisy: wrong names, near-miss names, plausible-but-absent names, edits in the wrong place, references to things at another version of the repo.
4. **A policy** — hop limits, write partitions, what may be touched. Enforced below Calvin, not by Calvin; Calvin must nonetheless never *propose* outside it.

### 4.2 Outputs

1. **A diff** that applies cleanly at the SHA.
2. **A NULL list** — every reference in the fills that Calvin could not bind to the ledger or to a symbol the diff itself declares, each with the fill it came from and, where Calvin can offer them, ranked candidates from the ledger.
3. **A read-trace** — every ledger lookup made, in order, with what it returned. This is the artifact the reviewer and the policy engine consume; it is how "did it check the callers before changing the signature" becomes a query instead of a judgment.
4. **Questions** — hole closures Calvin could not decide structurally and is routing back to the orchestrator, phrased as a narrower template.

### 4.3 Invariants

- **I1 — No unbound emission.** Every identifier in the diff resolves to a ledger entry at the SHA or to a declaration earlier in the diff. Hallucinated-symbol rate is zero by construction, and it is measured anyway. A nonzero reading is a defect in Calvin, never a finding about the task.
- **I2 — NULL is a value.** Unresolvable is reported, not approximated. Calvin never substitutes a plausible neighbor for a missing name without saying so; a substitution it does make (a ranked candidate the orchestrator accepted) is recorded as such in the trace.
- **I3 — Exact placement.** Every edit lands in a span the template gave or the trace justifies. "Somewhere in this file" is not a placement.
- **I4 — Propagation is complete relative to the ledger.** If the ledger says a change to X affects A, B, C within the policy's hop limit, the output either edits A, B, C or contains a closed hole for each with a reason. Silence on an affected site is a defect.
- **I5 — Determinism keyed to inputs.** Same ledger, same template, same fills, same Calvin version → same diff, NULL list, and trace. Calvin is a derived artifact of its inputs, regenerable, hash-keyed, like everything under `.hobbes/derived/`. If an implementation samples, the seed is part of the key.
- **I6 — Read-only about the world.** Calvin has no opinion on whether the intent is right. It does not improve the change, refactor around it, or add what the orchestrator forgot. It makes what was asked consistent and reports what could not be. (An implementation may *suggest* — a candidate list is a suggestion — but suggestions are outputs, never applied unasked.)
- **I7 — Smaller as Hobbes grows.** Any responsibility that becomes deterministically derivable moves out of Calvin into Hobbes. Calvin's scope is defined as a residual, and the residual is expected to shrink. An implementation that resists shrinking — that needs to keep a job for itself — is wrong.

---

## 5. The residual: what Calvin does that nothing else can

Everything deterministically derivable belongs to Hobbes. Everything about intent belongs to the orchestrator. Calvin owns the four things that are neither, as identified across the ADR-099 findings and the M0 design:

1. **Near-miss resolution.** The fill says `merge_ranges(a, b)`; the ledger has `range_join(left, right)`. Deciding whether these are the same thing is fuzzy matching over *structure* — same module, same arity, same call context, same test reach — not over string similarity. A rule catches case and basename; Calvin catches the rest, and says which it did.
2. **New-thing placement.** The ledger has no entry for a file that doesn't exist yet. Where a new symbol goes, what it should be named to match its neighbors, which module's conventions apply — this is the module-shape generalization that the 3,000-step adapter showed on never-seen symbols (impact 0.66, tests 0.75) and that no manifest can supply, because a manifest describes what is. C-84 says most real changes need it.
3. **Hole closure.** "Does caller A need updating?" is structural for an added optional parameter and semantic for a changed return type. Calvin closes the structural ones itself, routes the semantic ones back as questions, and knowing which is which is a judgment over the graph that neither Hobbes (no judgment) nor the orchestrator (no graph) can make alone.
4. **Placement within a span.** The template says "in `range_join`"; where in the fifty lines the edit belongs is not in the graph.

If M0 shows one of these is empty — near-misses all close with a basename rule, say — it leaves the residual and Calvin gets smaller. That is the intended direction (I7).

---

## 6. What Calvin needs from Hobbes

Calvin's ceiling is Hobbes's floor. The charter depends on Hobbes delivering, and names what "delivering" means so the dependency can be measured rather than assumed:

| Hobbes capability | Calvin's dependence | what breaks if it's missing |
|---|---|---|
| Semantic-tier symbol resolution (lane B live) for every language in the repo | I1 is only meaningful against semantic truth; a syntactic-only ledger makes "exists" a guess | Calvin degrades to a syntactic grounder and must say so per language; HSR becomes unmeasurable (ADR-099 exclusion rule) |
| Correct edges with tiers | I4 propagation and residual item 3 | wrong edges get *executed*, not hallucinated around — a frontier model will trust the ledger completely |
| Testmap and co-change | hole types `TEST_EXPECTATION`, `COCHANGE_TOUCH`; candidate ranking in item 1 | propagation is incomplete and Calvin cannot know it |
| Anchor pass and template generation | Calvin's inputs; without a template, everything is `FREEFORM` and Calvin derives spans alone | Calvin works harder and worse; measured as template coverage in M0 |
| Write partitions and policy below the model | I3 and I6 are enforced, not merely intended | Calvin's promises become promises, not properties |
| Determinism and SHA-keyed regeneration | I5 | Calvin's outputs cannot be regenerated or audited |
| Containment (sandboxed extraction, no model in the loop) | the ledger is trustworthy *because* nothing that guesses wrote it | the whole trust argument for the stack collapses one layer down |

The knowledge-only mode Hobbes committed to in August is what makes this stack possible: a user brings any orchestrator, Hobbes brings truth, Calvin brings grounded execution. Calvin is knowledge-only mode with an executor attached.

---

## 7. What Calvin is not

- **Not a general model.** It reads code, identifiers, spans, and structured fills. Prose it does not parse; it hands prose to the orchestrator. This is a constraint stated at the start of the thread and it is now a design property, not a limitation to apologize for.
- **Not a smaller LLM.** The size ladder was the wrong question. Calvin is not "a 7B that does what a 400B does, worse." It is a piece the 400B cannot be.
- **Not a competitor to the orchestrator.** The pairing is the product. A benchmark score, if one ever comes, belongs to the pair and to the repo it was measured on, and is read against the contamination note in the Hobbes README like every other number.
- **Not the place intent lives.** If Calvin starts deciding what a change should be, it has become the thing it was built to replace.
- **Not the place facts live.** If an implementation stores repo facts in weights and those facts survive a SHA change, it violates I5 and the entire reason the role exists (ADR-099 §4a, §9b: knowledge in weights overrides live context).

---

## 8. Implementation freedom, and the one thing it cannot trade away

Any implementation is acceptable that satisfies §4. Three are on the table:

- **Grounder + ranker.** Deterministic exact-match grounding with a small learned ranker for residual items 1 and 3, and a small planner for item 2. Cheapest; likely the first real Calvin (M1).
- **Pointer decoder.** A small model whose identifier vocabulary *is* the ledger plus its own declarations — identifiers copied, never generated — with a learned grammar for structure. I1 falls out of the decoding rule (M2).
- **The Ledger Machine.** Untrained orthogonal address channel; small learned relation channel; no trainable path from address to address; facts exist only in the per-session ledger. I1, I2, I5 are structural rather than enforced (M3, reached only if M2's errors are the kind the split removes).

What none of them may trade away: **Calvin must be wrong only in ways that are visible.** A wrong candidate is visible (it's in the trace, ranked, chosen). A wrong placement is visible (it's in the diff at a span). A missed propagation is visible (I4 makes silence a defect). An invented symbol is *not* visible — it looks like code — and so it is the one failure the contract forbids absolutely. Every implementation choice is judged first by whether it preserves that.

---

## 9. How to know Calvin is working

Not a benchmark. Role-level signals, each measurable per task:

- The orchestrator's NULL list shrinks across a loop and the shrink is attributable in the trace (candidate offered → candidate accepted → tests pass).
- Multi-file changes land with propagation complete (I4) at a rate the orchestrator alone does not reach on the same units.
- A reviewer can answer "why did it touch this file" from the trace without reading the code.
- On a repo neither model has seen, the pair's right-files-edited is bounded below by Hobbes's manifest precision and does not fall when the repo changes underneath (regeneration at the new SHA, no retraining).
- Calvin's scope has gotten smaller since the last release because something moved into Hobbes.

That last one is the health check for the whole idea. Calvin is doing its job when it is being replaced, one deterministic rule at a time, by the thing it depends on.
