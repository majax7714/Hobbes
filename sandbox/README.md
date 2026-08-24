# sandbox/ — the M4 session sandbox (ADR-018)

The rootless Podman image an agent session runs in, plus the M4 exit-check
harness. Built and driven by `go/cmd/hobbes-session`.

- `Containerfile` — the session image (`hobbes-session:local`): a small
  Alpine base with git + python3 and the statically-linked `hobbes-proxy`
  copied in. The agent runtime (Claude Code / Node) is mounted from the
  host at run time, not baked in.
- `hobbes-proxy` — the static proxy binary the image `COPY`s. A build
  artifact (gitignored); rebuild with
  `CGO_ENABLED=0 go build -o ../sandbox/hobbes-proxy ./cmd/hobbes-proxy`
  from `go/`.
- `driver.py` — a scripted implementer that speaks MCP to the proxy exactly
  as Claude Code would. Used by the exit check to exercise the sandbox
  without spending subscription quota.
- `exitcheck.py` — the M4 exit-check orchestrator: launches a sandboxed
  session on the hobbes repo (with fake secrets in the launching env),
  approves the parked escalation from the real `hobbes-proxy escalations`
  CLI, and prints the flight log.

## Build and run

```sh
# from go/
CGO_ENABLED=0 go build -o ../sandbox/hobbes-proxy ./cmd/hobbes-proxy
go build -o bin/hobbes-session ./cmd/hobbes-session

# build the image (from sandbox/)
podman build -t hobbes-session:local -f Containerfile .

# inspect what a session launch would do — no container run
bin/hobbes-session start --repo /path/to/repo --role implementer \
  --task "..." --dry-run

# the full M4 exit check (from repo root)
python3 sandbox/exitcheck.py
```

## Live Claude Code

`hobbes-session start` without a trailing `-- CMD` launches Claude Code as
the implementer (`--claude-cred` mounts `~/.claude` for its own auth). The
exit check substitutes `driver.py` so it stays quota-free; a live run is the
same command with `--claude-cred` and no override.
