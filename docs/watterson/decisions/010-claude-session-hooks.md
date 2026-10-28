# 010: Claude sessions carry Hobbes hooks; observe first, enforce only the hard deny

- Status: accepted; built and checked live on claude (see notes)
- Date: 2026-10-16
- Narrows: open-work 3a (DEC-007 adjustments)
- Builds on: DEC-007 (routes, hard deny, "count first")
- Research: `docs/research/session-policy-injection.md`

## Context
DEC-007's live checks found that in the guarded route the harness judges
decide everything: no request reached Hobbes on claude or codex. Hobbes's
hard deny and annotations only apply to what a harness escalates, and
DEC-007 asked to count how many prompts actually reach people before
allowing anything automatically. Nothing counts that yet.

The survey found one strong session-scoped lever: claude-agent-acp passes
`_meta.claudeCode.options.settings` from `session/new` to Claude Code as an
inline settings object, and settings can carry command hooks. A
`PreToolUse` hook runs for every tool call, including ones auto mode would
allow alone, and can deny with a reason the agent sees. Nothing is written
to disk. Codex has no equivalent that writes nothing: its hooks need a
trust entry in the user's `~/.codex/config.toml`.

## Decision
1. **Claude sessions get Hobbes hooks** through `_meta.claudeCode.options.settings`,
   on both routes: `PreToolUse`, `PostToolUse` and `PermissionDenied`, as
   exec-form command hooks (no shell). The hook client is a stdlib-only
   script in this repo, run with `python -I -S`; it hands the hook's input
   to the running Hobbes process over a Unix socket in a private temp dir
   (named in the adapter's env) and prints the answer.
2. **Observe first.** Hobbes answers no opinion to every hook, except:
3. **The hard deny moves in front of the judge.** In guarded, a
   `PreToolUse` edit of an agent's own permission config (DEC-007's list,
   checked by `annotate` on the hook's paths) is denied, with the reason
   given to the agent. Manual keeps it a warning (DEC-007).
4. **Every session keeps a permission log**: each tool call, whether the
   harness ran it, denied it, or escalated it to Hobbes, and how Hobbes
   answered. JSONL under `$HOBBES_CACHE_DIR/permissions/`, one file per
   session, and a one-line count when the session ends. This is DEC-007's
   "count first".
5. **If the hook client cannot reach Hobbes it says nothing**, so a broken
   socket never blocks a session; the harness's own checks still apply.
6. **Codex: parked** (the user, 2026-10-16: Codex's behaviour is OpenAI's to
   fix, not ours). No Codex hooks while trusting them writes the user's
   config; judge guidance (`auto_review.extra_policy`, custom instructions)
   also waits. Reassess when Codex offers a session-scoped way, or when the
   guarded counts show it is needed. Gemini is unchanged (not installed).

## Consequences
- In guarded, Hobbes sees and logs everything Claude does, not only what
  its judge escalates; the counts decide later slices (allowing safe
  requests, judge facts through `classifierContext` or `autoMode`).
- Each tool call costs one small process spawn and a socket round trip.
- Unverified until the live check: that settings hooks passed this way run,
  that they run before the auto classifier, and that the hook process sees
  the adapter's env.
- The hook client lives in this repo, outside a target repo's writable
  roots, except when the target is this repo.
- Anything that can reach the socket can only log or trigger a deny;
  Hobbes never allows from a hook.
- The Codex adapter trusts every session root, so a repo's own `.codex/`
  config, rules and hooks load (open-work 3f); parked with Codex.

### Note, 2026-10-16: built
- `hobbes.hooks.SessionHooks` (socket server, answers, log, `observe`
  wrapper for escalated requests) and `hobbes/hook_client.py` (stdlib
  only). `AgentSession(meta=…)` sends the `_meta`. `ask` and `chat` use them
  for the `claude` agent and print the count when the session ends.
- The socket path is passed as the hook's last argument, not in the
  adapter's env, so the hook does not depend on Claude passing env through.
- A tool call is "decided alone" when its `PreToolUse` was seen and no
  request for it reached Hobbes (ACP tool call id = Claude `tool_use_id`).
- Tests (`tests/test_hooks.py`) run the client as Claude would and check
  that the settings reach `session/new` through the fake agent. Not yet
  checked live.

### Note, 2026-10-16: live check (claude)
Real `claude-agent-acp` 0.90.0 on the user's subscription, in a throwaway
git copy of the miniapp fixture, `ask --no-knowledge`, no terminal. One
prompt: `touch` a file, write `notes.txt`, write `.claude/settings.json`.
- **Settings hooks passed in `_meta` run**, for Bash and Write, on both
  routes; each `PreToolUse` came before the tool ran.
- **guarded** (mode `auto`): the `touch` and the `notes.txt` write ran with
  no request to Hobbes (logged `PreToolUse` then `PostToolUse`). The
  settings write was denied by the hook; Claude quoted the reason and did
  not try another way. Count: 3 calls, 2 decided alone, 0 reached Hobbes,
  1 denied by Hobbes before the judge. In DEC-007's live check none of
  this was visible to Hobbes.
- **manual** (mode `default`): all three reached Hobbes as ACP requests and
  were rejected (no terminal); their ids matched the hooks' `tool_use_id`,
  so the count joined them (3 reached Hobbes, 0 alone). Claude reported
  "User refused permission to run tool": an ACP reject still carries no
  reason, unlike the hook's deny.
- Still unverified: whether the auto classifier was consulted before or
  after the hook (the deny held either way), and when the
  `PermissionDenied` hook fires; no harness denial happened in either run.
