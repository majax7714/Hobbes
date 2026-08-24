# ADR-033 — The architecture is one running document

**Status:** accepted (2026-08-15)

**Context:** Max's call, before V2.M4. Restructures `docs/`; changes no code.

## Context

Hobbes had two architecture documents: `hobbes-architecture.md` (v1, with a
"superseded in part" banner) and `hobbes-architecture-v2.md` (the extraction
rewrite, and the declared source of truth). The intent was clean — v1 is
history, v2 is now.

It did not hold, and the failure is measurable. The v2 document was written
2026-08-14 and was inaccurate about its own subject **within three
milestones**:

- **§3.3 claimed SCIP monikers are the graph's node IDs.** They are not.
  The range join (ADR-029) meant lane B never had to invent an id for
  anything lane A already named, so node ids stayed path-based. The dogfood
  graph's ids are `driver.Proxy`, `env:HOME`, `ext:react`. The document said
  otherwise for three milestones, and §4 repeated the claim.
- **§3.1 said lane A's resolver moves entirely to lane B.** ADR-031 demoted
  it to a fallback instead, because deleting it leaves any repo without a
  working indexer holding no call graph at all.
- **§3.7 said "add the indexer to `hobbes.yaml`".** That file does not
  exist; the registry is code and the per-repo config is derived.

Each drift was recorded in an ADR at the time. None of them reached the
document a session is told to read first. That is the same failure P8 was
created to name in artifacts — a confident surface concealing a known gap —
except here the artifact is the architecture itself, and its reader is the
next build session.

A versioned architecture document has a structural problem: it describes a
plan at the moment of writing, and every subsequent decision makes it more
wrong, while its title asserts it is current. "v2" reads as authoritative
long after v2 stopped being what the code does.

## Decision

**One running architecture document, amended in place, carrying no version
number.**

- `docs/hobbes-architecture.md` is the running architecture. It describes
  Hobbes as it is *now*. Where any other document disagrees, it wins.
- `docs/hobbes-architecture-v1.md` is the frozen v1 record, kept because the
  reasoning behind the carried subsystems is there and is still good.
- The former `hobbes-architecture-v2.md` **becomes** the running document
  rather than sitting beside it. There is no "v3" and there will not be one.
- `docs/adr/` remains the dated account of every change. The ADRs are the
  history; the architecture file is the present tense.

**The rule that keeps it true** (§8): a change that moves the architecture
patches this document *in the same commit as the code*, and an ADR that
amends it names the section it amends. A session that finds the file
describing something the tree does not do has found a bug in the file — fix
it and record the fix, rather than working around it.

The build programme moves out. §7 becomes a status table pointing at
`hobbes-build-plan-v2.md`, because milestone detail restated in two places
is detail that disagrees with itself — which is this ADR's whole subject.

## Consequences

- **Applied immediately, not asserted:** the three drifts above are
  corrected in the same commit as this ADR, and §3.3 now carries the
  honest note that multi-repo merge is *less* prepared than the moniker
  plan implied. Writing the rule without paying its first bill would have
  been the fake-honest version of it.
- Sessions read one file. The kickoff instruction "read the source of truth
  fully" stops requiring a judgment about which document is live.
- The v1 document loses its "superseded in part" banner in favour of a
  plainer one: it is history, and the running file is current.
- **Cost:** the ability to read the architecture *as of* a past decision is
  now the ADRs' job alone. That is acceptable — the ADRs are dated, numbered
  and complete, and nobody was reading v2's §3.3 for history. They were
  reading it for truth, and getting neither.
- No `C-n` entry: this concedes no information about a user's repo. It is a
  process decision about our own documents.
