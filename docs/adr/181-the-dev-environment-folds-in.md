# ADR-181 — The dev environment folds in from watterson-environment

**Date:** 2026-10-28 · **Status:** accepted (Max, 2026-10-28: "approved recommended good to proceed", the
seven routes below as proposed) · **Owner:** Max · **Source:** watterson-environment@a65b6b1 (its
DEC-001…027, now `docs/watterson/decisions/`), built outside this repo from 2026-10-15 to 2026-10-19.

Unparks §10's "Hobbes-as-an-application" as **the dev environment**, the 0.3.0 that ADR-103 reserved.
Amends §10, ADR-022's scope line, D3's scope, and `Potential-application-mode.md`'s status.

## What is missing

Max built the environment piece in a separate repo, watterson-environment, so that it would not shape this
one while it was being worked out. Its extraction pipeline was a verbatim copy of this repo at `2089e22`
(its DEC-001, DEC-003), and it put a harness layer on top: model providers over ACP and any-llm, live chat
sessions that re-extract between turns, permission routes and hooks, the knowledge tools, a TUI (an opencode
fork) served by a Hobbes server, level views and a review page, and agent roles with a coordinator. Max asked
for it to come home as a monorepo with its behavior exactly as watterson-environment has it, "a plug and test
against watterson-environment".

At the fold, `extract/`, `tsextract/`, `scip/`, `render.py` and `artifacts.py` were byte-identical in both
repos (`diff -rq`), and so were 60 of watterson's test files. What moves is the glue and its four root
directories.

## Decision

1. **The dev environment is unparked, as 0.3.0-beta.** The fold is the feature ADR-103 named for the next
   minor; the version moves in the fold's last commit. §10 and `Potential-application-mode.md` say so.
   - **ADR-022's line.** `hobbes-web` is unchanged: it still never runs the pipeline. The dev environment's
     server is a second surface, and it does run ingest: when the user starts Hobbes on a stale graph
     (DEC-016) and between chat turns on a snapshot (DEC-006, DEC-009). The parked document asked a revival to
     answer this with a launch token before the feature. The server binds to loopback only and takes a fresh
     per-launch password (`serve/launch.py`, `serve/http.py`, HTTP Basic, `secrets.token_urlsafe(24)`), which
     only the TUI it launches is given.
   - **A stated exception to D1's daemon split.** ADR-022 rejected a Python `hobbes serve` because it would
     reimplement the ADR-016 escalation queue and put a long-running daemon in Python. The dev environment's
     server does not touch that queue: its permission routes are its own (DEC-007), decided per tool call in
     the session. It is still a long-running Python process. That is recorded here as an exception scoped to
     `hobbes.watterson.serve`, not a change to D1.
2. **A subpackage and its own command.** The glue lives in `pipeline/src/hobbes/watterson/`, and a second
   console script, `watterson = "hobbes.watterson.cli:main"`, runs it. `hobbes` is unchanged. This settles the
   two module collisions (`hobbes.review` is ADR-025's PR review and `hobbes.watterson.review` the HTML page;
   `hobbes.cli` and `hobbes.watterson.cli`) and the two command collisions (`watterson review` and
   `watterson dispatch` keep watterson's meanings; `hobbes review` and `hobbes dispatch` keep this repo's).
   `watterson ingest` and `watterson render` call `hobbes.cli`'s own handlers, which were byte-identical, so
   there is one ingest.
3. **opencode is graphed with the rest of the repo, measured first.** CI's `graph` job ingests the whole
   repo, and discovery has no exclude list. Measured on a clone of watterson-environment@a65b6b1 (which holds
   `tui/opencode` already): opencode adds 2,628 of 3,353 module nodes and about 43 s of lane A TypeScript.
   Lane B fails in every opencode zone, disclosed per zone (`@tsconfig/bun/tsconfig.json` not found: its
   dependencies are not installed), so its calls are lane A's `syntactic` tier and it adds no lane
   disagreement. No exclude mechanism is built.
4. **D3 binds the web surface.** D3 (Cytoscape.js) is the renderer for `web/`. The review page is a
   standalone HTML file written by `watterson review`, drawn with React Flow and ELK (DEC-019), and stays so.
5. **`~/.watterson/` stays the dev environment's home.** `watterson` defaults `HOBBES_CACHE_DIR` to
   `~/.watterson/cache`, as watterson did (DEC-003). Agents file, logo, review pages and the TUI's state are
   unchanged.
6. **A plain copy with provenance.** The fold commit records `from watterson-environment@a65b6b1`; that repo
   stays the historical record of the glue, as this one stayed the record of the extraction (its DEC-003).
7. **watterson's docs are imported verbatim** under `docs/watterson/`, keeping the DEC numbers. DEC-001…027
   are accepted decisions of the dev environment; where one conflicts with an ADR, the ADR wins. Two of their
   rules lapse at the fold: the extraction is no longer a copy that must stay verbatim (DEC-001, DEC-003), and
   lane B's image is built here again. Their open items stay in `docs/watterson/open-work.md`, and
   `currently-open.md` points to it.

## What moved, and the changes it needed

- 37 modules and `review.html` into `hobbes/watterson/` (`providers/`, `serve/` inside it). Imports of the
  moved modules gain `.watterson`. Three path anchors go one level deeper: `review.py`'s `parents[3]` → `[4]`;
  `registry.py`'s and `launch.py`'s `parents[4]` → `[5]`. Two subprocess calls run
  `-m hobbes.watterson.cli ingest`. The RPC names the TUI calls (`hobbes.logo`, `hobbes.review`,
  `hobbes.mode`, …) are wire names and do not change.
- The CLI drops its 650-line copy of `hobbes.cli`'s ingest summary and imports `_cmd_ingest`, `_cmd_render`,
  `_detect_repo_root` and `_repo_root_from` instead. Its `prog` is `watterson`.
- 25 test files, prefixed `test_watterson_`, and the `fake_acp_agent.py` fixture. watterson's edited copies
  of `test_packs`, `test_tail` and `test_verification`, and the summary-printer classes of its `test_cli`,
  are not moved: this repo's originals run them.
- `tui/`, `review/`, `adapters/` and `bin/` at the root, unchanged except `bin/watterson`, which runs the
  `watterson` command. `tui/bin/` is ignored.
- `pyproject.toml` adds `agent-client-protocol==0.12.1` and `any-llm-sdk[anthropic,openai]==1.36.0`. The
  lock pins openai, jiter, httpx2 and httpcore2 to watterson's versions; anyio, idna, iniconfig, pluggy,
  pydantic(-core) and pygments keep this repo's existing (slightly older) pins.

## Parity (the acceptance test)

Recorded in the BUILDLOG entry for the fold: watterson's Python suite test by test, `review`'s tests and
bundle, the adapters' dependency tree, the TUI's build and its `tui` package suite, and the outputs of
`watterson` in both checkouts against the same targets at the same SHA. The differences expected and
accepted are the version (`0.1.0` → this repo's, in `--version`, `built_by` and the ACP client info), the
checkout path in `built_by`, and `prog` in usage text.

## Not done

- **Commands that reach a real harness** (`ask`, `chat`, `complete`, `tui`, `dispatch`, `job`,
  `roles --edit`) are covered by the fake-agent tests only; a live run is Max's.
- **CI** runs the moved Python tests and `review`'s; the TUI's Bun build and suite are not in CI (Bun is
  fetched by `tui/build.sh`).
- **The lane A defect the measurement found** (one `unexplained` disagreement in the moved CLI, where two
  functions each import a different `exit_code`) is its own unit, not this one.
