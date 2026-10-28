# The dev environment (watterson)

The `watterson` command puts an agent harness under Hobbes: model providers, live sessions with a fresh
graph between turns, permission routes, the knowledge tools, a TUI, level views, a review page, and agent
roles with a coordinator. It was built in watterson-environment and folded in at `a65b6b1` (ADR-181).

## Reading the imported docs

`overview.md`, `open-work.md`, `decisions/` (DEC-001…027), `research/` and `plans/` are imported verbatim
from watterson-environment@a65b6b1. Read them with these renames:

| Pre-fold (in those docs) | Now |
|---|---|
| `hobbes.<module>` for the glue (`hobbes.serve`, `hobbes.providers`, `hobbes.levels`, …) | `hobbes.watterson.<module>` |
| `cd pipeline && uv run hobbes <cmd>`, or `hobbes <cmd>` | `watterson <cmd>` (or `cd pipeline && uv run watterson <cmd>`) |
| `tests/test_<name>.py` for the glue's tests | `tests/test_watterson_<name>.py` |
| "this repo" / "hobbes-public" | this repo (the two are one) |
| `docs/reference/hobbes-architecture-3.8.md` | not imported; `test_verification.py` reads the architecture itself |

Two rules in them lapsed at the fold (ADR-181, decision 7): the extraction is no longer a verbatim copy to
leave alone (DEC-001, DEC-003), and the sandbox image is built here. `hobbes.watterson` reads the graph
through `hobbes.artifacts` and ingests through `hobbes.cli`'s handler; it imports no parser (I-4).

The open items are in `open-work.md` ("Next up" first); `docs/currently-open.md` points there.

## Rules that stay

- **Commands that reach a real harness or API spend the user's subscription or keys:** `ask`, `chat`,
  `complete`, `tui`, `dispatch`, `job` and `roles --edit`. Run them only with Max's go-ahead. The tests
  never do (a fake ACP agent, a faked any-llm).
- **Only ever launch the TUI through `watterson tui`, or with `--server URL`.** Without it, opencode starts
  its own background service. Never run its `upgrade`, `uninstall` or `service` commands.
- **Never start, stop or restart a paseo daemon on port 6767** (the user's live instance).
- `~/.watterson/` is the environment's home (ADR-181, decision 5): `cache/` (`HOBBES_CACHE_DIR`'s default
  for `watterson`), `agents.toml`, `logo.txt`, `review/`, `bun/`.

## Commands

From the repo root (`bin/watterson` is the launcher; link it into `~/.local/bin` to run it anywhere):

```sh
(cd pipeline && uv sync)                    # includes the provider libraries (DEC-004)
(cd adapters && npm ci)                     # locked claude/codex ACP adapters (DEC-004)
(cd review && npm ci && npm run build)      # review/dist/, which `watterson review` inlines (DEC-019)
(cd review && npm test)
tui/build.sh                                # tui/opencode -> tui/bin/opencode; Bun 1.4.2 into ~/.watterson/bun (DEC-025)
(cd tui/opencode/packages/tui && ~/.watterson/bun/1.4.2/bun test --timeout 30000)

watterson                                   # = watterson tui on the repo here (DEC-016)
watterson ingest --repo DIR                 # hobbes ingest, cached under ~/.watterson/cache
watterson render | levels [--view ID] [--format text|mermaid|json] [--list] | review [--no-open] --repo DIR
watterson freshness --repo DIR              # exit 0 fresh, 1 stale/missing, 2 error (DEC-005)
watterson agents [--check]                  # the registry; --check compares pins with npm, never bumps
watterson roles --repo DIR                  # list/check .hobbes/roles.toml (DEC-022)
watterson ask|chat --agent claude --repo DIR [--route guarded|manual] [--refresh|--no-refresh] [--no-knowledge]
watterson complete --model anthropic:<id> "<prompt>"
watterson dispatch --repo DIR --role NAME "<brief>"   # a role's worker, not Shanks (`hobbes dispatch`)
watterson job --repo DIR ["<job>"]

(cd pipeline && uv run pytest -q tests/test_watterson_*.py)
```

- Agent overrides: `$HOBBES_AGENTS_FILE`, else `~/.watterson/agents.toml`.
- Knowledge tools (DEC-008): `ask`/`chat` with `--repo` attach `hobbes-proxy --knowledge-only` from
  `$HOBBES_PROXY`, else `PATH` (`go/bin/hobbes-proxy` here).
- Lane B in an ingest needs podman and `hobbes-session:local`; `HOBBES_SCIP=0` turns it off.
- The graph panel (`tui/plugins/graph/tui.tsx`) is compiled by the TUI itself, with no type check here:
  after a TUI bump, look at the panel live.
- `serve/opencode.py`'s `OPENCODE_VERSION` must match `tui/build.env`'s `version`.
