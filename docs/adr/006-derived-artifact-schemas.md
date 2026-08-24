# ADR 006: Derived artifact schemas (graph.json, tests.json, interfaces.json)

Date: 2026-08-10
Status: accepted

## Context

Architecture §3.1/§10 name the three derived artifacts, require SHA
stamping, and require both a symbol layer and a module layer in the graph
file, but leave the concrete JSON shapes and identifier conventions open.

## Decision

> **Note (2026-08-10, M3):** schema_version is now **2** — graph.json's
> `"language": "python"` became `"languages": ["hcl", "python"]` (sorted)
> when the infra layer joined (ADR-010), and node kinds grew `resource`,
> `data`, `tf-module`, with module-edge types `references`, `env-set`,
> `packages`. Everything else below is unchanged.

All three files share a stamp: `schema_version` (integer, starts at 1),
`sha` (the repo HEAD the extraction read), and `dirty` (true when the
working tree had uncommitted changes — provenance stays honest instead of
silently pinning to a SHA the tree doesn't match). **No timestamps**: the
same tree must produce byte-identical artifacts (P1 — regenerable), so all
lists are emitted in sorted order and wall-clock time never enters the file.

**Identifier conventions.**

- Module id = the dotted import name as Python would import it
  (`hobbes.cli`), computed by walking `__init__.py` packages up from the
  file; files outside any package use their repo-relative path with `/` → `.`
  and `.py` stripped. If two import roots yield the same import name, ids are
  disambiguated by prefixing the root's repo-relative path (`pipeline:tests`).
- Symbol id = `<module id>.<qualname>` (`hobbes.cli.main`,
  `tests.test_cli.TestStubs.test_stub`).
- External dependency node id = `ext:<top-level package>` (`ext:yaml`);
  environment variable node id = `env:<NAME>` — the join key M3 uses for
  cross-layer app↔infra edges.

**graph.json** — both layers of §10's granularity decision:

```json
{ "schema_version": 1, "sha": "…", "dirty": false, "language": "python",
  "nodes":   [ {"id": "hobbes.cli", "kind": "module", "path": "pipeline/src/hobbes/cli.py"} ],
  "symbols": [ {"id": "hobbes.cli.main", "module": "hobbes.cli", "name": "main",
                 "qualname": "main", "kind": "function", "line": 10, "end_line": 42} ],
  "module_edges": [ {"from": "hobbes.cli", "to": "hobbes.policy", "type": "imports",
                      "evidence": [{"path": "…", "line": 18}]} ],
  "symbol_edges": [ {"from": "hobbes.cli.main", "to": "hobbes.policy.resolve",
                      "type": "calls", "evidence": [{"path": "…", "line": 61}]} ] }
```

Node kinds: `module` (a .py file), `package` (an `__init__.py`), `external`
(third-party import), `env` (environment variable). Module edge types in M1:
`imports`, `env-read` (the §3.1 vocabulary — `http-call`, `queue`,
`db-read/write` — joins as extractors learn to see them). Symbol edge type:
`calls`. Edges are deduplicated on (from, to, type) with every occurrence
kept in `evidence`.

**tests.json** — pytest inventory:

```json
{ "schema_version": 1, "sha": "…", "dirty": false, "framework": "pytest",
  "tests": [ {"id": "pipeline/tests/test_cli.py::TestStubs::test_stub",
               "file": "pipeline/tests/test_cli.py", "line": 14,
               "symbol": "tests.test_cli.TestStubs.test_stub",
               "reaches": ["hobbes.cli.main"], "reaches_modules": ["hobbes.cli"]} ] }
```

Test ids are pytest node ids, so they join directly against coverage data
later (§3.1's optional coverage trace).

**interfaces.json** — routes and CLI entry points (event topics and DB
schema join when their extractors exist):

```json
{ "schema_version": 1, "sha": "…", "dirty": false,
  "routes": [ {"framework": "flask", "method": "GET", "path": "/health",
                "handler": "miniapp.web.health", "file": "src/miniapp/web.py", "line": 7} ],
  "cli_entry_points": [ {"name": "hobbes", "target": "hobbes.cli:main",
                          "source": "pipeline/pyproject.toml"} ] }
```

One route entry per HTTP method: a Flask `methods=["GET", "POST"]` becomes
two entries, so M2's diff works edge-wise without unpacking lists.

## Alternatives considered

- **Timestamps in the stamp** — breaks byte-for-byte reproducibility; the
  SHA *is* the provenance.
- **Path-derived ids everywhere** — unambiguous but useless for resolving
  `import hobbes.cli` to a node; import names are what the code actually
  says.
- **One combined artifact** — three files mirror three consumers (graph
  render/diff, test map, interface inventory) and keep M2's graph diff from
  reparsing test data.

## Consequences

- Artifacts are diffable text; M2's graph diff is a set difference over
  `module_edges`/`symbol_edges`.
- `schema_version` gates evolution; consumers reject versions they don't
  know.
- The `dirty` flag means a dirty-tree ingest is visibly approximate.
