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

Last checked 2026-10-03. pytest was re-run on the host at 0.2.101-beta and Go at
0.2.99-beta, tsextract and vitest at 0.2.83-beta; the rest were run at
0.2.74-beta.

| Suite | Size | Notes |
|---|---|---|
| pytest | 2,822 | 28 of them `lane_b`, run on the host at 0.2.101-beta |
| Go `./...` | 403 with subtests | 403 pass |
| oracle-lane Go | 131 with subtests | 119 pass, 12 skip on a host without clang++ or cmake; the C++ ones pass in the image |
| vitest | 52 | |
| tsextract | 49 | |
| scip node | 97 | |
| atlas0 | 84 | |
| lattice | 663 | 631 pass, 32 skip on a host without clang; they run in the image (2026-10-03) |

Keep them green. CI does not check these counts. Update this table when
you re-run a suite.
