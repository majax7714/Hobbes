# 007: Two permission routes: guarded by default, manual on request

- Status: accepted; first slice built (see note). Adjustments open.
- Date: 2026-10-16
- Narrows: open question 3 in `docs/overview.md` (policy and sandbox sessions)
- Research: `docs/research/coding-agent-auto-permissions.md`

## Context
The environment replaces the web UI (the user, 2026-10-16). It drives
Claude Code, Codex and Gemini CLI over ACP, and every permission request a
harness raises reaches our client (`AgentSession(on_permission=…)`). So we
can decide per request instead of removing commands from the sandbox,
which would break the harnesses.

Two kinds of user (the user's framing; "Mac vs Linux"):
- **Most people approve almost anything** until it hurts them. The research
  agrees: Anthropic reports that 93% of permission prompts were approved
  before auto mode, and in one user study, where users wrote their own
  rules, 133 of 148 overreaching actions ran after a human approved them
  (arXiv 2608.27443). Turning on auto-approve in six harnesses raised attack success
  from 29.2% to 95.6% (arXiv 2610.07639). For these users a prompt is not a
  safety mechanism, and too many prompts push them to "approve everything".
- **Some want total control** and accept the prompts that come with it.

What the research found about our position (verified in the locked
adapters unless marked):
- Each harness decides most actions **before** asking the client: Claude's
  hooks, settings rules, mode and self-approved reads; Codex's sandbox,
  `.rules` and (in its default ACP mode, `agent`) its Auto-review model;
  Gemini's policy engine. The client sees what is left.
- ACP can only answer a request (`selected` option or `cancelled`) and set
  a mode. There is no reason text and no way to push policy.
- `allow_always` writes a rule **inside the harness** (Claude settings,
  Codex `default.rules`, Gemini `auto-saved.toml`), which later skips us.
- Our client drops each request's `kind`, `rawInput`, `content` and
  `locations` (`providers/acp_session.py:77-92`) and never sets a mode.
- No vendor resolves what a command will actually run, or treats
  repo-controlled execution (git hooks, `core.fsmonitor`, `.env`, agent
  config) as special. That is where the recorded bypasses came from, and
  where Hobbes's graph can add signal.

## Decision
1. **Never looser than the harness.** Hobbes adds checks on top of each
   harness's own; it never removes commands and never answers more loosely
   than the harness's built-in protection would. Hobbes never selects an
   `allow_always` option by itself.
2. **Two routes, chosen per session, `guarded` by default.**
   - **guarded** (default, for most people): turn on each harness's
     strongest built-in decider, so few requests reach anyone: Claude
     `auto` (falls back to `default` where the adapter does not offer it),
     Codex `agent` (Auto-review), Gemini `default`. Hobbes then:
     - **denies** a short hard list without asking: writes to an agent's
       own permission config (`.claude/settings*.json`, `.codex/` rules and
       config, `.gemini/` settings and policies), the "agent rewrites its
       own approvals" class (Copilot's CVE-2025-53773 wrote its own
       auto-approve setting);
     - **asks** the human for everything else that reaches it, with a plain
       line on what the action really touches, and a warning when it
       touches repo-controlled execution (`.git/hooks`, `.git/config`,
       `.env*`, CI workflows) or leaves the repo. Those are warned about,
       not denied: blocked users move to "approve everything" modes, which
       is worse;
     - **auto-allows nothing** in the first slice. Count how many prompts
       actually reach people first, then decide what is safe to allow.
   - **manual** (opt-in, for full control): the most-asking modes (Claude
     `default`, Codex `workspace-write`, Gemini `default`). Every request
     goes to the human with the same annotations. The hard list becomes a
     strong warning, not a denial: this user decides.
3. **Prerequisites, built first:** keep the full request (`kind`,
   `rawInput`, `content`, `locations`, option ids and kinds); set the mode
   explicitly at session start; when a human picks an "always" option,
   say where the harness will write the rule.
4. **Annotations start deterministic:** path facts (inside or outside the
   repo, repo-controlled execution, agent config, test files from
   `tests.json`). Graph resolution (what `npm run`, `make` or a script
   runs) comes later, against the snapshot graph of DEC-006.
5. **Adjustments beyond picking a route stay open** (not built): user
   rules, Hobbes-side "remember", compiling policy into harness-native
   rules or hooks, feeding graph facts to a harness classifier
   (Claude's `classifierContext`).

## Consequences
- The guarded route inherits each harness's judge, its cost (on the user's
  own subscription) and its error rates; Anthropic's are the only published
  ones (0.4% false positives, 17% missed overreach, Sonnet 4.6).
- Hobbes does not see what a harness allows by itself. Graph checks on
  those actions need compiled rules or hooks, which are open (5).
- Codex Auto-review denials never reach us; Gemini requests carry no
  `rawInput`, so its command is parsed from the title.
- A rejection over ACP carries no reason, so the agent is not told why.
- Non-interactive runs keep today's rule: deny unless the caller allows.

### Note, 2026-10-16: the user's choices
Taken from the proposal's recommendations: flagged actions are asked with a
warning, not denied ("a warning is better than yolo"); the hard-deny list
is the agents' own permission config only; the guarded route auto-allows
nothing at first.

### Note, 2026-10-16: first slice built
- `PermissionRequest` keeps the tool call's `kind`, `raw_input` and `paths`
  (locations and diff targets), merged over the call's earlier updates.
  Gemini sends the details only when the call starts.
- `AgentSession(modes=…)` sets the first preferred mode the agent offers
  (`session/set_mode`). `hobbes.permissions.ROUTE_MODES` holds the
  preferences. The claude and codex ids are checked in the locked adapters
  (claude offers `auto` only for models that support it, else `default`);
  gemini's come from its source and were not checked against an installed
  CLI. An agent Hobbes has no modes for keeps its own.
- `RoutePolicy` is the session's `on_permission`; `annotate` gives the
  plain lines a prompt shows. Commands are read as text, so the warnings
  can be fooled. Since nothing is allowed without a human (or
  `--allow-permissions`), a miss only drops a warning. The hard deny
  looks at an edit's paths, not command text: a command that merely
  names an agent config is warned about, never denied.
- "Always" options: the prompt says the harness remembers the choice
  itself and will not ask Hobbes again. It does not name the file, since
  that is unverified for the app-server paths (see the research notes).
- `hobbes ask --route guarded|manual` (default guarded). It prompts on a
  TTY; Enter rejects.
- Not built: anything in Decision 5, and graph resolution (Decision 4,
  later).
- **Kept as a note** (the user, 2026-10-16): Codex `manual` stays on
  `workspace-write`, which still runs in-workspace edits and sandboxed
  commands without asking. `read-only` would ask about every edit; revisit
  when the manual route gets real use.

### Note, 2026-10-16: live check (claude only)
Real `claude-agent-acp` 0.90.0 on the user's subscription, in a throwaway
copy of the miniapp fixture. Every request was recorded and denied.
- It offers `default, acceptEdits, plan, auto, bypassPermissions`. guarded
  set `auto` and manual set `default`, as intended.
- **guarded:** Claude's auto mode approved both actions itself (`touch` of
  a file and a write, both in the repo). **No request reached Hobbes.**
  This confirms the research: in guarded, the harness judge decides most
  actions, and Hobbes sees only what it escalates.
- **manual:** both requests reached Hobbes with full details:
  - the command: `kind=execute`, the command as the title,
    `raw_input={"command": …, "description": …}`, and the touched file as
    a path;
  - the write: `kind=edit`, `raw_input={"file_path": …, "content": …}`.

  The annotations read `runs: touch live_check_marker.txt` and
  `edits: notes.txt`. The command request offered only allow-once and
  reject; the edit also offered `allow-with-updates` (`allow_always`).
- Checked live: claude and codex (next note). gemini is not installed.

### Note, 2026-10-16: live check (codex)
Real `codex-acp` 2.2.2, same throwaway repo and the same recorder, plus a
third step (`curl -sI https://example.com`) to force a sandbox escalation.
- It offers `read-only, workspace-write, agent, agent-full-access`.
  guarded set `agent` and manual set `workspace-write`, as intended.
- **guarded:** the `touch` and the write ran in the sandbox without
  asking. The `curl` ran in the sandbox and failed (no network, exit 6).
  No escalation was requested and **no request reached Hobbes**. Whether
  Auto-review was consulted is unknown.
- **manual:** the `touch` and the write again ran without asking
  (`workspace-write`). After the sandboxed `curl` failed, Codex asked to
  escalate:
  - the request: `kind=execute`, title `Run command` (not the command),
    `raw_input={"command": "curl -sI https://example.com", "cwd": …}`;
    annotated `runs: curl -sI https://example.com`;
  - the options: `allow_once`, `accept_execpolicy_amendment`
    (`allow_always`), and `cancel` (`reject_once`).
- **Finding: on Codex, a reject can end the turn.** codex-acp maps two
  different decisions to `reject_once`:
  - `decline`: "No, continue without running it";
  - `cancel`: "No, and tell Codex what to do differently", which ends the
    turn (`codex-acp/dist/index.js:32164-32176`).

  This request offered only `cancel`, so our automatic deny stopped the
  turn (`stop_reason=cancelled`). The ACP kind alone cannot tell the two
  apart. An automatic deny should prefer `decline` when it is offered.
  Not changed yet; open.

### Note, 2026-10-16: automatic rejects prefer `decline` (3c)
Fixes the Codex finding above. Every reject Hobbes picks without a human
choosing an option (the hard deny, no terminal, Enter at the prompt,
`deny_all`) now prefers an option with id `decline` over other options of
the same kind (`providers/events.py` `option_of_kind`). The id is
codex-acp's (`ApprovalOptionId.Decline`, `codex-acp` 2.2.2
`dist/index.js:32023-32027`); ACP kinds alone cannot tell the two apart.
Limit: codex-acp offers only `cancel` for file changes
(`fileChangeDecisionOptions`, `dist/index.js:32211-32226`) and MCP tool
approvals (`:32689-32694`), and for commands whose decisions lack
`decline` (as in the live check). An automatic reject of those still ends
the turn; Hobbes cannot avoid that over ACP. Not re-checked live.
