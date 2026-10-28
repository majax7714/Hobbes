# Plan: move the extraction pipeline in (DEC-001)

> Status: **done** on `feat/extract-move` (2026-10-15). `uv run pytest -q`:
> **2020 passed, 2 skipped** on this machine (podman + `hobbes-session:local`
> present, `scip/` installed, so lane B runs); **1991 passed, 31 skipped** with
> podman absent (29 `lane_b` + 2 Go-proxy drift checks). See "Outcome" below.
> The facts were surveyed from `~/hobbes_public` @ `2089e22`.

## Cut line

`hobbes.extract` imports nothing else from hobbes. The one exception is a lazy
`from hobbes import __version__` in `built_by()` (`extract/__init__.py:2343`).
The slice is 46 `.py` files, about 27.8k LOC. It loads no package data.

**Moves:**
- `pipeline/src/hobbes/extract/`, the whole package. Lane B code is
  intertwined with it, so it all comes.
- `hobbes/__init__.py`, which is only `__version__`. Reset the version for this
  repo.
- `tsextract/`, a Node helper using `ts-morph ^27`. It is **required** in lane A
  for any TS/JS repo, and fails loudly if missing.
- `scip/`, the pinned SCIP helpers (lane B only). Its files are hashed into the
  index-cache key.
- Tests: the 60 pure-extract test files (about 27.6k LOC), the extract classes
  from `test_cli.py`, `conftest.py` (the `_lane_a_only` and
  `_no_ambient_commit_identity` fixtures), and about 31 fixture mini-repos
  (about 3 MB). `minijs` and `twomod` are referenced by no test; check before
  copying.
- A **new thin CLI**: `ingest` (and optionally `lanes`) rebuilt from `cli.py`
  lines 44–694 plus the ingest parser. Do not lift `cli.py` whole, because its
  top level imports `policy` and `artifacts`.

**Does not move:** `narrate/` (deferred), `derive/`, `run/`, `bench/`, `ttt/`,
`review.py`, `graphdiff.py`, `render.py`, `policy`, `go/`, `web/`, and
`sandbox/Containerfile` (shared with agent sessions, so decide separately).
Also staying behind are `test_version.py` and `test_agent_docs.py`, which are
hobbes-repo-wide.

**Dependencies** (Python ≥3.12):
- `tree-sitter>=0.25,<0.26` (0.26 segfaults)
- `tree-sitter-c>=0.24.2,<0.25`
- `tree-sitter-cpp>=0.23.4,<0.24`
- `tree-sitter-go>=0.25.0`
- `tree-sitter-hcl>=1.2.0`
- `tree-sitter-java>=0.23.5`
- `tree-sitter-python>=0.25.0`
- `tree-sitter-rust>=0.23,<0.25`
- dev: `pytest>=8`

`pyyaml` is **not** needed by extract.

## Things that break standalone

- **Path anchors.** `tssource.py:90`, `scipsource.py:384` and
  `containment.py:431` use `Path(__file__).parents[4]` to reach the
  `tsextract/` and `scip/` directories at the repo root. `__init__.py:2344` uses
  `parent.parent` to find the git checkout for provenance. Either keep the
  `<root>/pipeline/src/hobbes/extract/` depth, or replace these anchors.
- **Tests that read outside the slice:**
  - `test_verification.py:17` reads `docs/hobbes-architecture.md` §3.8.
  - `test_packs.py:654` extracts hobbes's own `go/` directory.
  - `test_helper_contracts.py`, `test_tssource.py` and `test_packs.py` locate
    the helpers at `parents[2]`.
- **Env vars** in the slice: `HOBBES_CACHE_DIR`, `HOBBES_INDEX_CACHE`,
  `HOBBES_LANEA_CACHE`, `HOBBES_SCIP`, `HOBBES_SCIP_CMD`,
  `HOBBES_TSEXTRACT_CMD`, `HOBBES_SANDBOX_IMAGE`, `HOBBES_UNCONTAINED`.
- **Lane B** needs podman and the `hobbes-session:local` image. Without them,
  about 30 `lane_b` tests skip, and runtime falls back with a degradation
  record. `HOBBES_UNCONTAINED=1` runs it on the host.

## Open choices

1. **Git history.**
   - (a) Plain copy, with the provenance SHA in the commit message. hobbes-public
     stays the historical record.
   - (b) Preserve the roughly 311 relevant commits via `git filter-repo` (not
     installed) and an unrelated-history merge. That history only goes back to
     2026-08-24.
2. **Layout and name.**
   - (a) Keep `pipeline/src/hobbes/extract/` + `tsextract/` + `scip/`. No path
     edits are needed.
   - (b) A new layout or package name. This means rewriting the 4 anchors and
     about 128 import lines.
3. **Lane B now or later.** The code comes either way. The question is whether
   we also set up the sandbox image here, or treat lane B as skip-only for now.

## Execution outline (once choices are made)

1. Create a branch `feat/extract-move`.
2. Copy the slice and add `pyproject.toml` (uv). Run `uv sync`.
3. Write the thin CLI. Fix the out-of-slice tests: vendor the §3.8 doc excerpt
   or inline it, and swap `go/` for a fixture.
4. Run `uv run pytest`. Lane A tests must pass. Lane B skips are expected and
   counted.
5. Fill in the CLAUDE.md "Commands" section, update `docs/overview.md`, and
   commit with provenance (`from hobbes_public@2089e22`).

## Outcome

- Copied verbatim from `hobbes_public@2089e22`: `extract/` (46 files, about
  27.9k LOC), `tsextract/`, `scip/`, 60 test files (about 27.8k LOC), 31
  fixtures. `minijs`, `twomod` and `decision-keys.json` were not referenced and
  were skipped. Lanes A and B both pass here; no extraction code changed.
- New: `pipeline/pyproject.toml` + `uv.lock` (same versions as the source
  lock), `hobbes/cli.py` (`ingest` only; `lanes` needs `hobbes.artifacts`, so
  it stayed behind), and `tests/test_cli.py` (the ingest classes).
- Tests changed:
  - `test_verification.py` reads §3.8 from `docs/reference/hobbes-architecture-3.8.md`.
  - `test_packs.py`: the Go dogfood test runs on the `goshapes` fixture.
  - `test_tail.py`: `TestKnowledgeToolsMirrorTail` skips when `go/` is absent.
    The plan missed this one: it reads `go/internal/knowledge/knowledge.go`.
  - `test_cli.py`: `TestProgressIsNotBuffered` runs `ingest`, not `init`.
  - `conftest.py`: trimmed to the two autouse fixtures. The `lanea_cache`
    marker moved to `pyproject.toml`.
- Lane B: with podman and the image present but `scip/` not installed, 27
  `lane_b` tests fail. They are not skipped.
