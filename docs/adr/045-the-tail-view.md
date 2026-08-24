# ADR-045 — The tail view: the unresolved remainder, classified by observation

**Status:** accepted (2026-08-16)

**Scope:** amends the architecture §3.4 (resolution coverage rows carry a
classified ``tail``; the ingest summary prints the per-language capture
line). Amends **C-2** (the count now decomposes), registers **C-32** (the
classifier's own boundaries). tsextract facts move to **v4** (calls carry
``origin``). Follows ADR-044: this is the guaranteed fraction's boundary,
made legible per repo.

## Context

Resolution coverage (ADR-029) gave the unresolved call sites a count and
deliberately nothing more — a probability on a nameless edge is C-1's
false edge in disguise. But a count alone leaves the remainder reading as
uniformly unknown, and a 2026-08-16 measurement across the three
verified repos showed it is nothing of the sort. Classified **by
observation only**, the tails decomposed almost completely:

- Go: 68.9% of the tail is bare calls whose names match Go builtins.
- Python: 45.5% builtin-named; 44.4% attribute calls on receivers no
  static index can type — C-2's claim, now measured.
- TS/JS (kbet): **61% of the tail is calls to bindings declared in the
  same file** — state setters, handler consts — i.e. declarations C-9
  deliberately keeps below the graph's vocabulary. Another 22% resolve
  (per the checker) to declarations outside the repo. The bare residue
  that fit no observation: **9 sites of 1,339**.

Two conclusions drove the decision. First, the largest single class is
not a blind spot but the graph's own abstraction floor: those sites are
*seen and deliberately not modelled*, which is a different honesty
category from *cannot see* — and the checker already knew it, in
`resolveExpressionTarget`, where the knowledge was being discarded at
the gate. Second, per Max's directive: the measurement is the honesty,
so it must run as part of every ingest ("a full hobbes proceed"), not
live in a scratch script — and the concentrated residue it leaves is
the project's real "need to see", to be tracked in the register rather
than absorbed into an undifferentiated percentage.

## Decision

**Classes are observations or they are `unclassified`.** No class may
infer intent ("probably a store call"); each states a checkable fact,
and the class names say exactly what was checked (`builtin-name` means
*matches* — a shadowing local would match too, and the name owns that).
This is the standing rule for any future class, P5 applied to
classification: we only care about *what is*; a checklist of potentials
rationalising the unknown is the fake-honest shape and is forbidden.

The classes, in decision order (first observation wins; every
unresolved site lands in exactly one, so per file the tail sums to the
coverage row's `unresolved` — a tested invariant):

| class | the observation | source |
|---|---|---|
| `fallback-resolved` | lane A's resolver produced a syntactic edge; only semantics came up empty | join fallback |
| `local-binding` | checker: declared in this file, below the modelled vocabulary (C-9) | tsextract v4 |
| `nested-decl` | checker: declared in another repo file, below the vocabulary | tsextract v4 |
| `external-origin` | checker: every declaration lives outside the repo | tsextract v4 |
| `import-binding` | bare call, name bound by a same-file import (added same day, see amendment) | lane A parse |
| `builtin-name` | bare call, name in the language's **pinned** builtin list | tail.py |
| `attr-call` | attribute call — a receiver nothing could type | source text |
| `path-call` | `::`-qualified call | source text |
| `unclassified` | no observation applies | — |

**The rollup is the vocabulary Max named:** `local-binding` +
`nested-decl` + `builtin-name` are *seen, not modelled by design* — the
graph knows what they are and abstains, which is knowledge, not
ignorance. Everything else (bar `fallback-resolved`, which has an edge)
is *cannot resolve* — the concentrated remainder. The ingest summary
prints both groups per language, always phrased against the honest
denominator: "N% **of detected call sites**" — never "of the repo"
(the undetectable classes stay where they are, C-1/C-4/C-5).

**Where it lives.** `resolution_coverage` rows gain a `tail` object
(additive; no schema bump — the ADR-035 precedent: it changes how no
existing field is read). The rollup is derived at read time
(`tail.rollup`), never stored twice. The tsextract helper computes
`origin` only for callees it could not resolve, in `calleeOrigin` — the
same declaration walk `resolveExpressionTarget` does, reporting which
gate failed instead of discarding the answer. The classified set is
derived from the same disposition walk as the counts
(`ev._dispositions`), so the two cannot drift.

## Amended same day: `import-binding` (the private-repo-A/qwen run)

Running the tail view against the two remaining sanctioned repos —
Max's ask: catch major snags easier to classify than "simply unknown" —
cracked the `unclassified` bucket open. private-repo-A's 46 unclassified
Python sites were almost entirely **bare calls of imported names**
(`PG_UUID`×22 — an import alias — `pg_insert`, model classes);
qwen-pathology's were `load_dataset`, `LLM`, `SamplingParams` —
imports of the very packages its `dependency_coverage` reported
missing (2/6 resolved).

New class, same rules: **`import-binding`** — a bare call whose name an
import statement in the same file binds. The observation is lane A's
own parse (`FromImport`'s (imported, bound) pairs — no regex, no
guess); what stays open is only where the call would land, which is
typically C-23/C-27/C-30 territory — so this class is the *shape* of a
missing environment, sitting in the **cannot resolve** group beside
`external-origin`, its checker-graded TS sibling. Priority: an import
binding outranks a builtin match, because `from rich import print`
makes the import the truer fact about `print(...)`; bare calls only —
`os.path.join()` stays `attr-call` however `os` arrived. Python-only
today (C-32 amended): a Go import binds a package name, not a callable,
so the class has no Go meaning, and Go's remaining bare tail
(`cleanup`, `run` — closure-typed locals, ~20 sites on the dogfood
repo) stays honestly `unclassified` until a provider can prove it.

## The classifier's own boundaries (C-32)

- **Checker-origin classes are TS/JS-only** in this version. The other
  syntax providers do not resolve, so a Python local's call lands in
  `unclassified` (or `attr-call`), not `local-binding` — an absent
  `local-binding` count for Python means *not asked*, never "no
  locals". The measured tails say this costs little today (Python's
  declared-in-file share was 6.8%); the entry keeps the asymmetry from
  being read as a fact about the languages.
- **Builtin lists are pinned literals**, not the running interpreter's
  (`dir(builtins)` varies by Python version; the C-3 lift documented
  what a runtime-bound list costs). The pin can go stale by omission —
  a builtin added to the language classifies as `unclassified` until
  the list moves.
- **Shape is read from the terminal's source line.** A wrapped chain
  whose terminal the recorded line does not contain is `unclassified`
  rather than guessed — the same decline-over-invent rule as C-5.

## Consequences

- Every ingest now states, per language: the accounted share of
  detected sites, what the graph deliberately abstains from, and what
  it genuinely cannot resolve. The third number is the yardstick's
  denominator for the derivation work (ADR-044): derived context comes
  from the captured fraction, and this line names the boundary per repo.
- `hobbes review` / the surface do not yet read `tail` — candidate
  work, not scoped here.
- Exit check: the three verified repos re-ingested; the tail totals
  reconcile against the 2026-08-16 scratch measurement (checker-graded
  origins replacing its regex approximations).
