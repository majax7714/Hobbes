# ADR-162 — Agent context hygiene: small entry docs, delegated reading, one home per fact

**Date:** 2026-10-02 · **Status:** accepted (Max, 2026-10-02: "we will also implement the policy that
exploring and reading with be done by subagents and summarized when not hobbes tools cant cover";
"its better to have a smaller set of good rules to follow when developing and ledgers and organized docs
when needed") · **Owner:** Max · **Source:** the sources below, read 2026-10-02.

## Context

Every session loads CLAUDE.md, and it used to load the handoff and the architecture in full as well. By
2026-10-02, CLAUDE.md was 376 lines, the handoff 316, and the architecture is over 2,000 lines; the
architecture's §9 told a session to read it whole. Most of that text was state, history, or items
waiting on a decision. It was paid for by every session, and it was relevant to few of them. Hobbes'
own thesis is that an agent works best under a small, derived context. The project's process did not
follow that thesis.

## Decision

1. **Two always-loaded docs, capped.** CLAUDE.md (AGENTS.md is its copy) holds rules and pointers only:
   about 200 lines, hard cap 250. `session-handoff.md` is the resume point: about 100 lines, hard cap
   150. `test_agent_docs.py` holds the caps, the copy, and the pointers. There is no status block:
   state lives in the handoff.
2. **One home per kind of fact** (CLAUDE.md §5). Open decisions and work noted but not done go in
   `currently-open.md`, procedures in `runbook.md`, and the rest in the existing ledgers and records.
   Everything else points to that home and does not copy it.
3. **Read through the graph, then through subagents.** The knowledge tools come first. Reading that they
   cannot cover (docs, records, configs, logs, the web) goes to a subagent, which returns a summary with
   `file:line` pointers. The main context reads only what it edits, what an answer pointed it at, the
   two entry docs, and a single known fact at a known path.
4. **References are read by section; ledgers are searched.** That includes the architecture. The
   architecture's opening and §9 are amended to say so.
5. **Close each unit of work the same way:** update the docs it moved, append to the BUILDLOG, and
   commit. This replaces the per-task end-of-session lists, whose specific assumptions drifted.
6. **Honesty and accuracy before recall** is CLAUDE.md's first section. It covers the extraction rules,
   and it applies the same standard to what an agent reports.

## Why: the sources

- **Context is finite, and recall degrades as it grows.** "as the number of tokens in the context window
  increases, the model's ability to accurately recall information from that context decreases"; the
  goal is "the smallest set of high-signal tokens that maximize the likelihood of some desired outcome".
  (Anthropic, *Effective context engineering for AI agents*, 29 Sep 2025,
  https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents.)
  Chroma tested 18 models and found that "model performance degrades as input length increases, often
  in surprising and non-uniform ways" (Hong, Troynikov and Huber, *Context Rot*, 14 Jul 2025,
  https://www.trychroma.com/research/context-rot). Information in the middle of a long input is used
  worst: "significantly degrades when models must access relevant information in the middle of long
  contexts" (Liu et al., *Lost in the Middle*, TACL 12, 2024, https://aclanthology.org/2024.tacl-1.9/).
- **Instruction files: short and specific.** "target under 200 lines per CLAUDE.md file. Longer files
  consume more context and reduce adherence"; imports "don't reduce its context cost"; "The more specific
  and concise your instructions, the more consistently Claude follows them" (Claude Code docs, *How
  Claude remembers your project*, https://code.claude.com/docs/en/memory, accessed 2026-10-02). And:
  "For each line, ask: 'Would removing this cause Claude to make mistakes?' If not, cut it. Bloated
  CLAUDE.md files cause Claude to ignore your actual instructions!" (*Best practices for Claude Code*,
  https://code.claude.com/docs/en/best-practices, accessed 2026-10-02; first published April 2025 at
  anthropic.com/engineering/claude-code-best-practices, which now redirects there.)
- **Subagents keep the main context clean.** A subagent "might explore extensively, using tens of
  thousands of tokens or more, but returns only a condensed, distilled summary of its work (often
  1,000-2,000 tokens)" (*Effective context engineering*). Subagents "run in separate context windows and
  report back summaries", keeping "your main conversation clean for implementation" (*Best practices*).
  Anthropic's research system uses them for "compression"
  (*How we built our multi-agent research system*, 13 Jun 2025,
  https://www.anthropic.com/engineering/multi-agent-research-system).
- **Notes outside the context are memory.** In that pattern, the agent "regularly writes notes persisted
  to memory outside of the context window", and loads data "just in time" through "lightweight
  identifiers" (*Effective context engineering*). Here, the ledgers, `currently-open.md` and the pointers
  play that part.
- **Start simple.** "finding the simplest solution possible, and only increasing complexity when needed"
  (Schluntz and Zhang, *Building effective agents*, 19 Dec 2024,
  https://www.anthropic.com/research/building-effective-agents).
- **AGENTS.md** is the cross-tool name for the same file: a "README for agents"
  (https://agents.md/, accessed 2026-10-02). It says nothing about length.

**Not from a source:** closing each unit with a commit is this repo's own convention. *Best practices*
has a commit step at the end of a task, and no source here argues for it further. Max (2026-10-02):
smaller commits are better hygiene. The one limit is the repo's same-commit rules (tests, `C-n`, the
architecture, the version bump): a commit is the smallest *complete* unit, never a red midpoint.

## Costs and limits

- **Delegation is not free.** Multi-agent systems "use about 15× more tokens than chats" (*multi-agent
  research system*). A subagent pays for itself when the reading is large and only its conclusion is
  needed. For a single known fact at a known path, read it directly; the rule says so.
- **A summary can be wrong.** A subagent's report is model output. Check any claim you will act on
  against the lines it cites (the 2026-10-02 audit of the doc split found four losses and five
  misstatements, so the check is worth making).
- **Caps can push content into the wrong home.** The test checks length and pointers; it does not check
  placement. The §5 table is the guard.
