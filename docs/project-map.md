# Project map

The tree in detail. `CLAUDE.md` carries a one-line-per-directory summary;
this page is the long form. For a module's purpose, ask
`get_module_doc` first. Read this page for what the graph does not hold:
the directories' roles, and the non-code trees.

- `go/` — the Go module (`github.com/majax7714/Hobbes/go`). Its only
  external deps are `yaml.v3` and `modelcontextprotocol/go-sdk`.
  - `internal/policy/` is the merge engine behind `hobbes-policy`. It
    merges builtin floor → box → repo → role → folder → agent; deny
    overrides allow; each rule is allow, deny or escalate.
  - `hobbes-proxy` is the per-session MCP daemon (`internal/proxy/`,
    `knowledge/`, `recorder/`, `escalation/`): the policy-checked `exec`,
    the read-only knowledge tools, the JSONL flight log, and the
    escalation queue.
  - `hobbes-proxy sidecar` is the session's records container (ADR-112):
    `internal/sink/`, plus `internal/egress/`, the allowlisted logging
    CONNECT proxy.
  - `hobbes-session` and `internal/sandbox/` run a session in rootless
    Podman, on its own network beside its sidecar. Its flags: `--mount`
    (ADR-100); `--egress`; `--claude-bin` plus `$CLAUDE_CODE_OAUTH_TOKEN`
    for the Claude Code doer (ADR-107). An explicit `--network` keeps the
    old file journal (C-140).
  - `hobbes-web` and `internal/web/`: the loopback-only API and the SPA.
- `pipeline/` — the Python package `hobbes` (uv, src layout; `cli.py`).
  - `extract/`: discover → syntax providers (`pysource`, `tssource`,
    `gosource`, `rustsource`, `javasource`, `csource`, `cppsource`) → the
    lane B SCIP join → graph/testmap → `packs/` → emit. `containment.py`
    runs every lane B step in the image and refuses to run without it
    (C-64, C-66).
  - `derive/`: `hobbes plan` (impact → … → changespec), plus the keyed
    rounds' pieces that Shanks runs on: `template.py`, `ground.py`,
    `gate.py` (`hobbes gate`, with `--map derive`), `adapter.py`, and
    `harness.py` (`hobbes verify`).
  - `run/`: `hobbes run`, and **`dispatch.py`, which is `hobbes dispatch`:
    Shanks, the harness** (ADR-107, ADR-152).
  - Also: `agent/loop.py`, `bench/`, `ttt/`, `narrate/`, `invariants/`,
    `review.py`, `render.py`, `graphdiff.py`.
  - Fixture repos live under `tests/fixtures/` (miniapp, minits, minigo,
    minirust, minijava, canary-rust, canary-java, goshapes, twomod, minic,
    minicpp, minifixval, minideco, mininest). They are excluded from
    collection.
- `tsextract/` — the Node helper (ts-morph) that emits facts JSON for the
  join.
- `scip/` — lane B's helper. `index.mjs` owns the SCIP decode (scip-java's
  typed ranges, and C's rules from ADR-109). The directory also holds the
  spike evidence. The pinned indexers themselves are in the image.
- `web/` — the surface (Vite + React + TS, Cytoscape.js). `src/lib/` is
  the pure layer with the vitest cases. `npm run build` bundles into the
  Go embed dir; **rebuild `hobbes-web` after** running it.
- `sandbox/` — the one image (`Containerfile`, about 3.3 GB) and the
  exit-check harness. The image serves both sessions *and* lane B ingest
  (ADR-092). It holds JDK 17/21/25 + Maven + scip-java, scip-clang + CMake
  + bear, and clang for the C and C++ oracle. It has no `claude`; a
  session mounts the host's.
- `bench/` — experiment tooling, never product. `bench/README.md` maps
  each directory to its programme.
  - `calvin/`: the lattice package, the E3 draw, the M0 templates and the
    gold fills.
  - `atlas0/`: its own uv project, with
    `bench/atlas0/scripts/modal_atlas0.py`.
  - `oracle/` (ADR-089): one `oracle` binary (`export | go-rta | py-trace
    | rust-mir | java-javac | c-clang | grade | import`; `c-clang` serves
    both C and C++), `adapters/<tool>/` for foreign graphs (ADR-101), and
    `report/render.py` with its drift test (ADR-102).
- `docs/` — the architecture and the ADRs, plus:
  - `constraints/`: the register of what Hobbes cannot tell you, one file
    per segment; `README.md` is the index.
  - `extraction-evidence.md`, `BUILDLOG.md`, `session-handoff.md`,
    `currently-open.md` (open decisions and work), `runbook.md`
    (procedures), `workstreams.md`, `future_additions.md` (the parked
    backlog), `lessons.md`, and `bench-drivers.md` (the
    `~/.hobbes/bench/` index).
  - `shanks/`: the harness, and `sessions/` with one log per dispatched
    session.
  - `experiments/`: the two programmes. `mapped-agents/` holds the
    benchmark, the agent mapping and TTT. `calvin/` holds the charter, the
    reassessment, the lattice, Atlas-0 and the keyed rounds.
- `.hobbes/` — dogfooding. `policies/` and `invariants/` are versioned;
  `derived/` and `plans/` are gitignored.
