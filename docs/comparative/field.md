# The field — code-graph tools with agent-facing surfaces, one row each, every cell sourced or *unstated*

**Read 2026-09-09** (ADR-101, Workstream A). Every cell below is what
the tool's own README, docs, paper or issue tracker says, with the link
it was read at, or the word **unstated**. Nothing is inferred from
silence; nothing is editorialised. Where a tool publishes a number on
a basis other than the oracle lane's, the basis is recorded here and
the number is **never** put in a table beside an oracle number (ADR-101
§6, C-62). The two tools graded by the lane on 2026-09-09
(CodeGraphContext, repowise) have a further column, *what our run
observed*, which is a fact about a run on this box and not a claim
about the tool.

**Draw rule.** Start from the two `how-hobbes-differs.md` named in
August (CodeGraphContext, repowise), then search for what is current —
the space moves in months. A tool qualifies with (a) a graph over a
repository, (b) MCP or agent-facing tools, (c) public source. Searches
run 2026-09-09 (WebSearch): *code graph MCP server repository call graph
agent 2026*; *"codebase knowledge graph" MCP server github 2026*; and one
per candidate name (Potpie, GitNexus, Codanna, Blar, Serena, Joern,
CocoIndex, Continue.dev, Nx/Kùzu, RepoGraph, Lynn). Each included
repo's README was then read raw (`raw.githubusercontent.com`, `main`),
and stars, licence and last push were taken from the GitHub API the
same day. Not checked: any tool's full docs subtree beyond its README
and the pages linked from it; nothing was cloned except the two tools
graded. The survey pass was made by an agent and the load-bearing
cells (edge source, export format, self-reported numbers) re-read
from the raw README by hand before this page was written.

**Excluded** (met the traction bar for a look, did not clear the rule
as documented): Blarify (a library; its README exposes no MCP surface);
Aider's repo map (no MCP); bare SCIP / Sourcegraph (a protocol and an
index, not an agent-facing repo graph); CocoIndex code (embedding
search, no call-edge graph found); bare Joern (a CPG with no
agent-facing surface of its own — its MCP packaging *codebadger* is
the row); Augment's context engine and Cursor's index (closed);
Continue.dev (no repo-graph product found); `codegraph-ai/CodeGraph`,
`domjancik/codebase-graph-mcp`, `tirth8205/code-review-graph`,
`graphify` (surfaced, plausible, not read to the same depth — left out
for row budget, not disqualified).

## 1. The rows

Columns are the brief's. *Edge source* is what builds the edges;
*model in the build* is whether an LLM runs at index time; *says what
it cannot see* is the column that carries the actual difference, and
most rows read *nothing found* — stated as exactly that.

| Tool (pin, licence, stars 2026-09-09) | Edge source | Publishes precision? | Publishes recall? | Seeds wrong edges to test its own grader? | Deterministic build? | Model in the build? | Says what it cannot see? | Executes repo code during indexing? | Languages, with evidence base | Export format — readable as (site file:line, callee file:line)? |
|---|---|---|---|---|---|---|---|---|---|---|
| **[CodeGraphContext](https://github.com/CodeGraphContext/CodeGraphContext)** 0.6.13 · MIT · 4,180★ · pushed 2026-09-06 | tree-sitter; SCIP optional for C/C++ (`compile_commands.json`) and C# via `SCIP_INDEXER=true`, falling back to tree-sitter ([README](https://github.com/CodeGraphContext/CodeGraphContext#readme)) | unstated | unstated | unstated | unstated ([what our run observed](#2-what-our-runs-observed): four indexes of the same clone stored 767 / 1,193 / 767 / 767 CALLS rows) | no (static parse; the SCIP path only when enabled) | nothing found as a limitations statement; the README points to `docs/TROUBLESHOOTING.md` ("every entry maps a real reported issue to its fix or workaround") | unstated (described as tree-sitter / SCIP parsing; no execution statement either way) | 23 named in the README (Python, JS, TS, Java, C, C++, C#, Go, Rust, Ruby, PHP, Swift, Kotlin, Dart, Perl, Lua, Scala, Haskell, Elixir, Emacs Lisp, HTML, CSS, TSX, Solidity); no per-language evidence basis stated | **yes.** Graph DB (FalkorDB Lite default on Unix, KuzuDB, LadybugDB, Neo4j). No documented export command; read directly (our adapter's Cypher): `CALLS` edges carry `line_number` (site), `confidence`, `confidence_label` (EXTRACTED / INFERRED), `resolution_tier`; the callee `Function` node carries `path` and `line_number` (declaration). A separate `HEURISTIC_CALLS` table holds name-only guesses |
| **[repowise](https://github.com/repowise-dev/repowise)** 0.49.0 · AGPL-3.0 · 6,386★ · pushed 2026-09-09 | tree-sitter AST "+ LSP-style resolution with confidence stamping" ([README](https://github.com/repowise-dev/repowise#readme)); no SCIP mentioned | **yes, two bases:** 84.8% call-edge precision, "540 rows hand-graded from source" ([BENCHMARKS §7](https://github.com/repowise-dev/repowise/blob/main/docs/BENCHMARKS.md)); and a **compiler-graded table** against Go RTA and `tsc` — five tools, seven cells, 37,853 oracle edges ([BENCHMARKS "Is the call graph correct"](https://github.com/repowise-dev/repowise/blob/main/docs/BENCHMARKS.md#is-the-call-graph-correct)); see §3 | **yes**, per cell beside precision in the same table, with the statement "Do not compare recall across rows" | unstated | claimed: "Zero LLM calls, zero cloud … Pure Python over tree-sitter and git data" for the graph layers ([what our run observed](#2-what-our-runs-observed): two indexes of the same clone stored the same edge rows) | optional — the graph, risk, health, tests and dead-code layers "no LLM"; prose pages and answers use one when a key is set | **yes, explicitly:** edge confidence "stamped 0.95 down to 0.50" by resolution origin; "Signal is correlated with file size and weakens sharply within a fixed size band, which we report rather than bury"; the benchmarks page's "Limits that apply to the whole page" | unstated (no execution statement found) | 13 "Full" (Python, TS, JS, Svelte, Vue, Java, Kotlin, Go, Rust, C++, C#, Scala, Ruby), "10 at Good tier, 2 Partial", 39 total; evidence per language: the nine-language hand-graded audit (BENCHMARKS §7) | **yes.** `.repowise/wiki.db` (SQLite): `graph_edges` rows with `edge_type='calls'`, `call_lines_json` (site lines), `confidence`, `resolution_origin` (same_file, same_package, receiver_typed_*, package_alias, …); `wiki_symbols` maps a symbol id to `file_path` and `start_line`. Also `repowise export --format structurizr` (architecture, not edges) |
| **[codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)** · MIT · 42,774★ · pushed 2026-09-09 | tree-sitter (162 vendored grammars) + "Hybrid LSP" semantic resolution for 12 languages ([README](https://github.com/DeusData/codebase-memory-mcp#readme)) | unstated as precision; "83% answer quality across 31 real-world repositories" (basis: its own question set) | unstated | unstated | unstated | no model stated for the graph build ("100% locally") | **yes, a list:** "Cypher support is read-only subset"; "Textual resolution fallback for 150 languages without Hybrid LSP"; "Zero-edge guarantee only for Perl unresolved receivers" | unstated (structural analysis described; no execution statement) | 162 via grammars; Hybrid LSP for Python, TS/JS/JSX/TSX, PHP, C#, Go, C/C++, Java, Kotlin, Rust, Perl; "benchmarked against 64 real open-source repositories", bucketed by cross-file resolution | **partly, per the README:** edges by qualified name (`<project>.<path>.<name>`) with `CALLS` / `CALL_REFERENCE` / `USAGE`; a read-only Cypher subset (`query_graph`) — whether a `CALLS` row carries the site line is not shown; SQLite backend, single binary. Not graded here |
| **[codegraph](https://github.com/colbymchenry/codegraph)** · MIT · 70,254★ · pushed 2026-09-09 | native Rust kernel over tree-sitter grammars, "automatic per-file fallback" ([README](https://github.com/colbymchenry/codegraph#readme)) | unstated as precision; per-language "cross-file coverage" percentages (TS 95.8%, Python 100%, Go 96.6%) — a coverage number, not precision against a key | see left | unstated | claimed: "graphs verified byte-for-byte identical to the reference engine" | no ("zero external dependencies … no API keys or network calls") | **yes:** "Dynamic dispatch, reflection, and runtime-determined routing cannot be statically resolved"; files > 1 MB skipped; framework coverage caps named (Django 74.1%, Spring 83.3%) | "No code execution during indexing" (README) | 30+ named; per-language cross-file coverage % as the evidence | **unclear from the README:** SQLite + FTS5 at `.codegraph/codegraph.db`; CLI `callers`, `callees`, `impact`; the schema's line grain is not shown. Its shell installer, not the npm package of the same name, is the documented path. Not graded here |
| **[GitNexus](https://github.com/abhigyanpatwari/GitNexus)** · PolyForm Noncommercial 1.0.0 · 47,176★ · pushed 2026-09-09 | tree-sitter AST ([README](https://github.com/abhigyanpatwari/GitNexus#readme)) | unstated (edges show a confidence like "[CALLS 90%]", basis not explained) | unstated | unstated | unstated (Leiden clustering, no determinism statement either way) | optional — the index needs no key; `gitnexus wiki` "requires an LLM API key" | **yes, several limits:** browser memory cap (~5k files), a 50,000-node safety cap, CFG "currently TypeScript & JavaScript", watch mode "does not pull remotes" | unstated (walks the tree and parses; a `--spring-actuator` flag reads a snapshot, not executed code) | 16 named with a per-language feature matrix (imports, exports, heritage, type annotations, …) | **not consistently:** the `impact` example shows the callee side with file:line and the caller side by name; local LadybugDB index; no JSON/DB export documented. Not graded here |
| **[code-graph-rag](https://github.com/vitali87/code-graph-rag)** · MIT · 5,113★ · pushed 2026-09-09 | tree-sitter multi-language parser ([README](https://github.com/vitali87/code-graph-rag#readme)) | unstated | unstated | unstated | unstated | optional / unstated precisely — Qdrant for semantic search; whether an LLM runs at build time is not stated | tree-sitter's "inherent static analysis constraints" named; a dynamic call-tracing overlay offered for "dispatch that static analysis cannot see" | unstated | 13 fully supported (Python, TS, TSX, JS, Rust, Go, Java, C, C++, C#, PHP, Lua, Dart), Scala in development, a "structural" tier via ast-grep | **unstated:** Memgraph + Qdrant; `cgr start --repo-path … --update-graph`; no statement of file:line on both ends found. Needs Docker. Not graded here |
| **[Serena](https://github.com/oraios/serena)** · MIT · 29,087★ · pushed 2026-09-08 | LSP (default) or a JetBrains backend; works at "symbol level" — the README does not call what it builds a graph ([README](https://github.com/oraios/serena#readme)) | unstated | unstated | unstated | unstated | unstated | nothing found | an `execute_shell_command` tool exists for the agent; whether indexing executes repo code is unstated | "over 40 languages" via language servers; evidence basis is which server is available | **not documented:** no export or edge schema found. Not graded here |
| **[Potpie](https://github.com/potpie-ai/potpie)** · Apache-2.0 · 5,715★ · pushed 2026-09-09 | unstated in the README ("knowledge graph", parser not named) | unstated | unstated | unstated | unstated | unstated | nothing found | unstated | unstated in the README read | **unstated:** a UI graph explorer; no CLI export or schema found; a native MCP server is not confirmed in the README. Not graded here |
| **[Codanna](https://github.com/bartolli/codanna)** · Apache-2.0 · 739★ · pushed 2026-08-29 | tree-sitter ([README](https://github.com/bartolli/codanna#readme)) | unstated (throughput and latency numbers only, "not an accuracy claim") | unstated | unstated | unstated | optional — a bundled local embedding model by default; remote embeddings opt-in | "Windows support experimental" is the only limitation-type statement found | unstated ("no source code leaves your machine" is a network claim) | 15 named; no per-language evidence beyond the list | **yes in the shown example:** symbol file:line, callees "called at" file:line, callers by reverse reference; index format under `.codanna/` not specified. Not graded here |
| **[codebadger](https://github.com/qcri/codebadger)** · GPL-3.0 · 167★ · pushed 2026-08-31 | Joern code property graphs ([README](https://github.com/qcri/codebadger#readme)) | unstated | unstated | unstated | unstated | unstated for the CPG build | nothing found | unstated (Joern's CPG for compiled languages may need a build; not confirmed) | Java, C/C++, JavaScript, Python, Go, Kotlin, C#, Ghidra, Jimple, PHP, Ruby, Swift (named) | **unstated:** CPGQL queries; the MCP tool catalogue (`docs/available-tools.md`) was not read. Docker-based. Not graded here |

**Hobbes 0.1.3-beta (ADR-103; every cell record names the commit, exact
where a version is a name), for the same columns, so the reader has
the row it is being compared to** — every entry points at the evidence
rather than restating it: edge source, tree-sitter (lane A) joined to the
language's own pinned SCIP indexer (lane B), architecture §3;
precision and recall, per cell against compilers and the interpreter,
`docs/oracle/cells/`; seeds wrong edges, yes — every cell's poison
line; deterministic, demonstrated (byte-identical re-ingests on peft,
date-fns, quic-go, serde, jsoup, petclinic; `extraction-evidence.md`);
model in the build, no (`hobbes narrate` sits on top and is pinned);
says what it cannot see, a per-repo statement (`list_blind_spots`, the
tail classes per file, the containment stamp) and the register
(`docs/constraints/`, 96 entries); executes repo code, yes for lane B
and the executing oracles, **contained** in the sandbox image
(ADR-092, C-64); languages, five, each with its §3.8 evidence row;
export, `oracle export` reads `graph.json` to (site, callee) pairs.

## 2. What our runs observed

Facts about running the two graded tools on this box on 2026-09-09,
as their READMEs document, on the loop repos at the commits the oracle
keys were built at. These are not claims about the tools beyond that
run.

| | CodeGraphContext 0.6.13 (`--db kuzudb`) | repowise 0.49.0 (`init --no-prose -y --no-editor-setup`) |
|---|---|---|
| Install | `uv venv && uv pip install codegraphcontext`; Python 3.14 on this box | `uv venv && uv pip install repowise` |
| Network during index | none observed; no key asked for | none observed; no key asked for (`--no-prose`) |
| Repo code executed | none observed (tree-sitter parse; no build invoked) | none observed |
| Writes into the repo | none (the database is at `--db-path`) | `.repowise/` (kept out of the tree with `--no-editor-setup`; the default also writes `.mcp.json`, `.claude/CLAUDE.md`, `.vscode/*`) |
| Determinism, the same clone indexed again | **not always the same**: four fresh indexes of mux stored 767, 1,193, 767 and 767 CALLS rows (the 1,193 a strict superset; the tool's own summary printed 2,165 each time) — both grades are in the mux cell record | **same**: the converted edge file was byte-identical across two indexes of mux |
| Wall time on mux (7.5k lines Go) | 4 s | 4 s |
| Their own errors during the loop | read from each cell's `index.log`, quoted in its record; the spring-data-elasticsearch index exited 1 on a Kuzu binder exception and was graded as stored | none |
| Declaration line of a Java method under `@Override` | the annotation's line (the tree-sitter node start) | the annotation's line |
| Our conversion of that line | converter@1 graded the annotation line and charged the edge to the tool (C-94); converter@2 advances to the identifier's line — the Java cells were regraded with signed direction-of-fix lines | same |
| Triage of a 20-row random sample of contradictions per tool (after the regrade) | tool-wrong 20 : oracle-grain 0 : converter-defect 0 | tool-wrong 19 : oracle-grain 1 : converter-defect 0 |

## 3. Numbers published on other bases — recorded here, compared nowhere

- **repowise, hand-graded:** "84.8%" call-edge precision, 540 rows
  hand-graded from source, nine languages, against CodeGraph 57.0%
  ([BENCHMARKS §7](https://github.com/repowise-dev/repowise/blob/main/docs/BENCHMARKS.md)).
  Basis: the publisher's own reading of its own sample.
- **repowise, compiler-graded ("Is the call graph correct"):** a
  precision / recall pair per cell for five tools — repowise, CodeGraph
  1.5.0, codebase-memory-mcp 0.10.8, Graphify 0.9.31, code-review-graph
  2.3.7 — on cobra (with tests), gitleaks (with and without tests),
  syft (with and without tests), zod, hono; the key is
  `golang.org/x/tools/go/callgraph/rta` for Go and `tsc`'s resolution
  for TypeScript; 37,853 oracle edges; artifacts and a graded
  pre-registration at
  [repowise-bench/graph/experiments/g4-oracle-anchored](https://github.com/repowise-dev/repowise-bench/tree/master/graph/experiments/g4-oracle-anchored).
  The page states its limits in its own words: two languages, seven
  cells; a contradicted edge is very strong evidence, not proof; edges
  the oracle cannot speak about are charged to nobody and reported at
  full size; do not compare recall across rows; two of the five arms
  are read through adapters the publisher wrote. **This is the same
  shape as the oracle lane**, published by a competitor, and it is what
  the August reading of this page said no competitor published. It is
  not a 1-1 cell with anything here: different repos, their matcher,
  their adapters. Hobbes graded on their draws by our key, with both
  tools on the same clones, is done (`README.md` § *The 1-1 on
  repowise's draws*, 2026-09-09); their artifacts under our matcher
  would need per-edge files their experiment directory does not
  publish (it holds per-cell summaries).
- **codebase-memory-mcp:** "83% answer quality" on 31 repositories;
  "99.2% reduction in tokens". Basis: its own question set and its own
  token count.
- **codegraph:** "88% fewer tool calls · 53% faster · 62% fewer tokens
  · 44% cheaper" across seven repositories; per-language cross-file
  coverage. Basis: its own agent-loop measurement; coverage is not
  precision.
- **GitNexus:** per-edge confidence percentages in examples; no
  quantified accuracy claim found.
- **Hobbes' own H1–H3, SWE-bench, DeepSWE, TTT and Calvin numbers**
  are not on this page either (ADR-101 §7): unearned as claims, and a
  skeptic replicating one would undo what the oracle numbers buy.

## 4. The 1-1 cells

A 1-1 cell exists only when both sides have the same measure on the
same repo at the same commit against the same answer key. Those made
on 2026-09-09 are in `docs/oracle/cells/` as
`codegraphcontext-<repo>-2026-09-09.md` and
`repowise-<repo>-2026-09-09.md`, one per tool × repo, beside the
Hobbes cell each pairs with; the claim page
[`README.md`](README.md) lists them in one table, and the scatter
draws them as hollow squares. Nothing on this page is a number from
those cells; that is the point of keeping this page and that one
apart.
