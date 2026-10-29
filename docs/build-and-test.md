# Build and test — the long form

`CLAUDE.md` carries the everyday commands. This page holds the setup,
the full build, and the suite sizes. **The suite sizes are kept here and
nowhere else.**

## Prerequisites and one-time setup

You need Go ≥ 1.26, uv, and Node. If the distro's Go is older, put a
user-local Go first on `PATH`, or `go build` fails on the toolchain line.

Run these once:

- `cd tsextract && npm install`
- `cd web && npm install`
- `cd scip && npm install`
- `cd bench/oracle/ts && npm install` (the oracle lane's `tsc`; its Go
  tests run it wherever node is)
- For the dev environment (ADR-181): `cd adapters && npm ci`, `cd review &&
  npm ci && npm run build`, and `tui/build.sh` (fetches Bun 1.4.2 into
  `~/.watterson/bun`, writes `tui/bin/opencode`). `docs/watterson/README.md`
  has its commands.
- `git config core.hooksPath .githooks`. The pre-commit hook runs CI's
  gofmt step on the staged Go files. Without it, a red gofmt step hides
  both Go suites behind it.

## Build

```sh
cd go && go test ./...
go build -o bin/hobbes-policy  ./cmd/hobbes-policy
go build -o bin/hobbes-session ./cmd/hobbes-session
go build -o bin/hobbes-web     ./cmd/hobbes-web      # after `cd web && npm run build`
CGO_ENABLED=0 go build -o bin/hobbes-proxy ./cmd/hobbes-proxy   # MUST be static:
CGO_ENABLED=0 go build -o ../sandbox/hobbes-proxy ./cmd/hobbes-proxy  # it is mounted into the sandbox
(cd ../sandbox && podman build -t hobbes-session:local -f Containerfile .)  # lane B and the knowledge tools need it (ADR-092/094)
```

Rebuild the image after you rebuild the proxy, or after a version bump.
Otherwise the knowledge tools answer with the old build (C-65).

## Test

```sh
cd bench/oracle && go test ./...          # fixture self-test: Python via uv, Rust via the nightly driver
cd web && npm test && npm run build
cd pipeline && uv sync && uv run pytest   # HOBBES_SCIP=0 by default; `lane_b`-marked tests opt in
cd review && npm test                     # the dev environment's review page
(cd tui/opencode/packages/tui && ~/.watterson/bun/1.4.2/bun test --timeout 30000)  # the TUI; not in CI
(cd tui/opencode/packages/util && ~/.watterson/bun/1.4.2/bun test --timeout 30000)  # our util tests; not in CI
(cd tui/opencode/packages/latex && ~/.watterson/bun/1.4.2/bun test --timeout 30000)  # our latex tests; not in CI
```

CI (`.github/workflows/ci.yml`, ADR-095) runs every suite on every push.
`scripts/ci-graph.sh <base>` is the graph job: image build → ingest →
stamp check → lanes → compiled invariants → review → `lane_b` pytest. It
runs the same way on a box.

The Go suite's live tests run wherever podman and the image are present.
Inside a dispatch they skip, so their first run is the developer's. The
host has no clang++: the C/C++ oracle tests skip there,
so a bare `ok` proves nothing. Verify them in the image with `-v`.

## Suite sizes

Last checked 2026-10-29. pytest at 0.3.6-beta, tsextract and scip node at 0.3.4-beta, on the host; Go, vitest, review and the TUI at 0.3.0-beta; the rest were run at
0.2.74-beta.

| Suite | Size | Notes |
|---|---|---|
| pytest | 3,411 | 29 of them `lane_b`; 458 are the dev environment's (`test_watterson_*`) |
| Go `./...` | 405 with subtests | 405 pass |
| oracle-lane Go | 131 with subtests | 119 pass, 12 skip on a host without clang++ or cmake; the C++ ones pass in the image |
| vitest | 52 | |
| tsextract | 56 | |
| scip node | 105 | |
| review (node) | 13 | the dev environment's review page |
| TUI (bun) | 1,494 | 1,492 pass, 2 skip (2026-10-29, after DEC-028's trim); `tui/opencode/packages/tui`, not in CI; with Bun's default 5 s timeout two shell-output cases time out, so use `--timeout 30000` |
| util (bun) | 49 | 49 pass (2026-10-29); `tui/opencode/packages/util`, ours since DEC-028, not in CI; `turbo test` runs it with the TUI |
| latex (bun) | 86 | 86 pass (2026-10-29); `tui/opencode/packages/latex`, ours, not in CI; `turbo test` runs it |
| atlas0 | 84 | |
| identity gate | 5 | `bench/identity/test_compare.py`, run by CI with the pipeline's environment |
| lattice | 663 | 631 pass, 32 skip on a host without clang; they run in the image (2026-10-03) |

Keep them green. CI does not check these counts. Update this table when
you re-run a suite.
