# sandbox/ — the M4 session sandbox (ADR-018)

The rootless Podman image an agent session runs in, plus the M4 exit-check
harness. Built and driven by `go/cmd/hobbes-session`.

- `Containerfile` — the one image (`hobbes-session:local`), two mount
  shapes (ADR-092): an agent session (git + python3 + the static
  `hobbes-proxy`) and an ingest container (lane B's indexers — pinned
  node, Go, scip-go, rustup 1.97.1 with rust-analyzer, Temurin JDK
  17/21/25 + Maven 3.9.16 + the scip-java 0.13.1 launcher (ADR-096;
  `jdk.sh` installs one JDK, checksum-verified); the `scip/` helper and
  its npm indexers are mounted from the hobbes checkout at run time).
  Gradle is not installed: a Gradle repo runs its own wrapper into the
  Hobbes cache. Ubuntu 24.04 base: the trees the ingest mounts from the
  host are glibc-linked. The ingest planner is
  `pipeline/src/hobbes/extract/containment.py`.
- `knowledge-serve` — the launcher this repo's `.mcp.json` names
  (ADR-094): the image's `hobbes-proxy serve --knowledge-only` on
  stdio, repo mounted ro at `/work`, `--network none`, flight log in
  `~/.hobbes/sessions`. Refuses without podman or the image;
  `HOBBES_KNOWLEDGE_HOST=1` runs `go/bin/hobbes-proxy` on the host and
  says so (C-65). Rebuild the image after rebuilding the proxy or the
  tools answer with the old build.
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
