"""TS/JS extraction: invoke the tsextract helper, join its facts (ADR-021).

The Node helper (``tsextract/extract.mjs``, ts-morph) does discovery and
checker-grade resolution and emits facts JSON; this module turns those
facts into the same graph/tests/interfaces shapes the Python extractor
produces. Module ids are repo-relative paths sans extension
(``src/flow``), symbol ids ``<module-id>.<qualname>``.

Setup is explicit, never silent: a repo with TS/JS files and no usable
helper fails ingest with instructions (skipping would make graph content
depend on the environment). ``HOBBES_TSEXTRACT_CMD`` overrides the
helper invocation — the ``HOBBES_POLICY_BIN`` precedent; tests use it
for canned facts.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from collections import defaultdict
from pathlib import Path, PurePosixPath

from hobbes.extract.discover import SKIPPED_DIR_NAMES, is_linked_copy
from hobbes.extract.schema import tiered_edge

#: Environment variable holding a shell-split command prefix that replaces
#: ``node <repo>/tsextract/extract.mjs``.
TSEXTRACT_CMD_ENV = "HOBBES_TSEXTRACT_CMD"

#: The facts schema this join understands (helper HELPER_VERSION).
#: v2 (V2.M3): ``calls`` carries every call site, not only resolved ones,
#: positioned on the terminal identifier with ``col`` and ``name`` so the
#: evidence IR can join it against SCIP occurrences (ADR-029); ``callee``
#: is None where the checker resolved nothing. Test cases carry
#: ``end_line``.
#: v3 (C-5 surfacing): files carry ``routes_declined`` — registrations
#: seen and declined for a computed path, reported by the http-ts pack.
#: v4 (ADR-045): calls carry ``origin`` — where an *unresolved* callee's
#: declarations live (``local`` | ``nested`` | ``external`` | null), the
#: checker knowledge the tail view classifies instead of discarding.
HELPER_VERSION = 4

#: Extensions the helper extracts; used only for the cheap "does this repo
#: have TS/JS at all" scan that decides whether the helper must run.
_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
_TS_EXTENSIONS = {".ts", ".tsx"}


class TsExtractError(RuntimeError):
    """The helper could not run or answered garbage — with the fix."""


def has_ts_files(repo_root: Path) -> bool:
    """Cheap scan: does the repo contain any TS/JS source at all?"""
    stack = [Path(repo_root)]
    while stack:
        directory = stack.pop()
        for child in directory.iterdir():
            if child.name.startswith("."):
                continue
            if child.is_dir():
                if child.name not in SKIPPED_DIR_NAMES and not is_linked_copy(child, repo_root):
                    stack.append(child)
            elif child.suffix in _EXTENSIONS:
                return True
    return False


def _helper_cmd() -> list[str]:
    override = os.environ.get(TSEXTRACT_CMD_ENV)
    if override:
        return shlex.split(override)
    helper = Path(__file__).resolve().parents[4] / "tsextract" / "extract.mjs"
    return ["node", str(helper)]


def run_helper(repo_root: Path) -> dict:
    """Run the helper on *repo_root* and return its parsed facts."""
    cmd = _helper_cmd()
    setup = (
        "TS/JS files found but the tsextract helper is unusable — install "
        "Node and run `npm install` in the hobbes repo's tsextract/, or set "
        f"${TSEXTRACT_CMD_ENV} (ADR-021)"
    )
    try:
        proc = subprocess.run(
            [*cmd, "--repo", str(repo_root)],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError as exc:
        raise TsExtractError(f"{setup}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise TsExtractError(f"tsextract helper timed out on {repo_root}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()[-500:]
        raise TsExtractError(f"{setup}: helper exited {proc.returncode}: {detail}")
    try:
        facts = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise TsExtractError(f"tsextract helper emitted invalid JSON: {exc}") from exc
    version = facts.get("helper_version")
    if version != HELPER_VERSION:
        raise TsExtractError(
            f"tsextract facts version {version!r} unsupported (want {HELPER_VERSION})"
        )
    return facts


def module_id(path: str) -> str:
    """Repo-relative path sans extension: the ADR-021 module id."""
    pure = PurePosixPath(path)
    return str(pure.with_suffix("")) if pure.suffix in _EXTENSIONS else str(pure)


def join_facts(facts: dict) -> dict:
    """Join helper facts into graph/routes pieces (pure).

    Returns ``{"nodes", "module_edges", "symbols", "call_sites",
    "call_fallback", "files", "routes", "languages", "errors"}`` — empty
    when the repo has no TS/JS files.

    **No symbol edges (ADR-031).** ts-morph's checker resolutions are now
    the join's fallback rather than edges, symmetrically with Python's:
    lane B is the resolver of record, and what lives here is the labelled
    floor beneath it. Tests are collected after the join, by
    :func:`collect_ts_tests`, because their reach must be computed over
    the edges the join produced rather than over lane A's guesses.
    """
    files = facts.get("files", [])
    languages = set()
    for f in files:
        suffix = PurePosixPath(f["path"]).suffix
        if suffix in _TS_EXTENSIONS:
            languages.add("typescript")
        elif suffix in _EXTENSIONS:
            languages.add("javascript")

    nodes: dict[str, dict] = {}
    module_edges: dict[tuple, list] = defaultdict(list)
    symbols: list[dict] = []
    routes: list[dict] = []

    for f in files:
        mid = module_id(f["path"])
        nodes[mid] = {"id": mid, "kind": "module", "path": f["path"]}
        for imp in f["imports"]:
            if imp["resolved"]:
                target = module_id(imp["resolved"])
            elif imp["external"]:
                target = f"ext:{imp['external']}"
                nodes.setdefault(target, {"id": target, "kind": "external"})
            else:
                continue
            module_edges[(mid, target, "imports")].append(
                {"path": f["path"], "line": imp["line"]}
            )
        for read in f["env_reads"]:
            env_node = f"env:{read['var']}"
            nodes.setdefault(
                env_node, {"id": env_node, "kind": "env", "name": read["var"]}
            )
            module_edges[(mid, env_node, "env-read")].append(
                {"path": f["path"], "line": read["line"]}
            )
        for sym in f["symbols"]:
            symbols.append(
                {
                    "id": f"{mid}.{sym['qualname']}",
                    "module": mid,
                    "kind": sym["kind"],
                    "name": sym["name"],
                    "qualname": sym["qualname"],
                    "line": sym["line"],
                    "end_line": sym["end_line"],
                }
            )
        for route in f["routes"]:
            handler = route["handler"]
            if route.get("handler_path"):
                handler = f"{module_id(route['handler_path'])}.{handler}"
            routes.append(
                {
                    "file": f["path"],
                    "framework": route["framework"],
                    "handler": handler,
                    "line": route["line"],
                    "method": route["method"],
                    "path": route["path"],
                }
            )

    sorted_symbols = sorted(symbols, key=lambda s: s["id"])
    return {
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "module_edges": _edge_list(module_edges),
        "symbols": sorted_symbols,
        "call_sites": _call_sites(files),
        "call_fallback": _call_fallback(files, sorted_symbols),
        # The raw per-file facts, kept so tests can be collected once the
        # join has produced the symbol layer they measure reach over.
        "files": files,
        "routes": sorted(routes, key=lambda r: (r["file"], r["line"], r["path"])),
        "languages": sorted(languages),
        # Per-file/stage degradations the helper survived (a checker
        # crash on one expression must not zero the repo) — carried into
        # the artifact so the gap is visible, never silent (P1).
        "errors": facts.get("errors", []),
    }


def _call_sites(files: list[dict]) -> list:
    """Lane A's TS/JS call sites, in evidence-IR shape (ADR-029).

    Every site, resolved or not: the join needs them as the left-hand
    side (SCIP cannot tell a call from a reference) and coverage needs
    them as its denominator.
    """
    from hobbes.extract import evidence as ev

    return [
        ev.Site(
            provider=ev.TREE_SITTER,
            kind=ev.CALL_SITE,
            file=f["path"],
            line=call["line"],
            name=call["name"],
            col=call.get("col", -1),
            scope=(
                f"{module_id(f['path'])}.{call['scope']}"
                if call["scope"]
                else module_id(f["path"])
            ),
        )
        for f in files
        for call in f["calls"]
    ]


def call_origins(files: list[dict]) -> dict[tuple[str, int, str], str]:
    """Checker origins for unresolved TS/JS callees, keyed like the
    fallback dict (ADR-045). Only sites the checker could place — a null
    origin stays absent, so the tail view falls through to its
    text-shape classes rather than trusting an empty answer."""
    return {
        (f["path"], call["line"], call["name"]): call["origin"]
        for f in files
        for call in f["calls"]
        if call.get("origin")
    }


def _call_fallback(
    files: list[dict], symbols: list[dict]
) -> dict[tuple[str, int, str], tuple[str, int]]:
    """ts-morph's own resolutions, keyed by call site (ADR-031).

    The projection resolves a target by the line its definition *starts*
    on, so the checker's qualname has to be turned back into a line here —
    the symbol table is the only place that mapping exists.
    """
    line_of = {(s["module"], s["qualname"]): s["line"] for s in symbols}
    fallback: dict[tuple[str, int, str], tuple[str, int]] = {}
    for f in files:
        for call in f["calls"]:
            if not call["callee_path"]:
                continue
            target_module = module_id(call["callee_path"])
            line = line_of.get((target_module, call["callee"]))
            if line is None:
                continue  # resolves to something the symbol layer omits
            fallback[(f["path"], call["line"], call["name"])] = (
                call["callee_path"],
                line,
            )
    return fallback


def _edge_list(edges: dict[tuple, list]) -> list[dict]:
    """Mirror of graph._edge_list: sorted typed edges with merged evidence.

    Tier and lane come from the shared v4 vocabulary (ADR-028) rather than
    being restated here — the helper's checker-resolved edges are still
    lane A, and stay ``syntactic`` until scip-typescript replaces them at
    V2.M2/M3.
    """
    return [
        tiered_edge(
            source,
            target,
            edge_type,
            sorted(evidence, key=lambda e: (e["path"], e["line"])),
        )
        for (source, target, edge_type), evidence in sorted(edges.items())
    ]


def collect_ts_tests(
    files: list[dict], symbols: list[dict], symbol_edges: list[dict]
) -> list[dict]:
    """tests.json rows for JS/TS tests, with **per-case** static reach.

    A JS test case is an anonymous closure with no symbol to hang an edge
    on, so until V2.M3 reach was computed once per test *file* and shared
    by every case in it. That made `tests_guarding` and behavioural
    coverage *over*-report on TS repos — the only number in the system
    that was larger than the truth rather than smaller, and worse,
    indistinguishable from a precise pytest row (C-11).

    SCIP occurrences carry ranges and the helper now records each case's
    extent, so a call can be attributed to the `it()` that encloses it.
    Two kinds of call, and both are needed to stay honest:

    - inside a case's range → that case reaches it;
    - outside **every** case → shared setup (`beforeEach`, module-level
      fixtures, `describe` bodies), so every case in the file reaches it.

    Dropping the second kind would trade the old over-report for an
    under-report, which is not an improvement — setup really does run for
    each case.

    Reach is measured over the **joined** symbol edges, so it counts what
    the semantic provider proved wherever it could (ADR-031).
    """
    test_files = {f["path"] for f in files if f["test_framework"]}
    test_module_ids = {module_id(p) for p in test_files}
    symbol_module = {s["id"]: s["module"] for s in symbols}
    symbols_by_module = defaultdict(set)
    for s in symbols:
        symbols_by_module[s["module"]].add(s["qualname"])

    # `calls` only: a `uses` edge would let a test claim it guards code it
    # merely names (ADR-029), and reach is the basis of that claim.
    adjacency = defaultdict(set)
    calls_at = defaultdict(list)  # file -> [(line, target)]
    for edge in symbol_edges:
        if edge["type"] != "calls":
            continue
        adjacency[edge["from"]].add(edge["to"])
        for sighting in edge["evidence"]:
            calls_at[sighting["path"]].append((sighting["line"], edge["to"]))

    records = []
    for f in files:
        if not f["test_framework"]:
            continue
        mid = module_id(f["path"])
        cases = f["tests"]
        ranges = [(c["line"], c.get("end_line", c["line"])) for c in cases]

        # Seeded from calls only, and deliberately *not* from the file's
        # imports. Import seeding was the file-level approximation of the
        # attribution now done properly: `api.test.ts` imports fourteen
        # functions, so seeding on imports hands all fourteen to every
        # case and per-case ranges buy nothing. It also makes JS reach
        # mean what pytest reach means — the closure over calls (ADR-007)
        # — which is the whole point of C-11: a JS row must not look like
        # a precise pytest row while being computed differently.
        shared: set[str] = set()
        per_case: dict[int, set[str]] = {i: set() for i in range(len(cases))}
        for line, target in calls_at.get(f["path"], ()):
            owners = [
                i for i, (start, end) in enumerate(ranges) if start <= line <= end
            ]
            if owners:
                # Nested `it()` cannot happen, but a defensive innermost
                # pick costs nothing and keeps one call in one case.
                per_case[owners[-1]].add(target)
            else:
                shared.add(target)  # beforeEach, describe body, module level

        test_prefixes = tuple(f"{tm}." for tm in test_module_ids)
        # Module-level guarding must not depend on symbol modeling: a
        # test that imports a module guards it even when nothing it
        # names is in the symbol layer (data consts, mocked modules).
        imported_modules = {
            module_id(imp["resolved"])
            for imp in f["imports"]
            if imp["resolved"]
        } - test_module_ids

        for i, case in enumerate(cases):
            seeds = shared | per_case[i]
            reached = set(seeds)
            frontier = list(seeds)
            while frontier:
                current = frontier.pop()
                for target in adjacency.get(current, ()):
                    if target not in reached:
                        reached.add(target)
                        frontier.append(target)
            # Anything living in a test file is scaffolding, not guarded
            # code — filter by id prefix, not the symbol table, so call
            # targets the symbol layer doesn't model are excluded too.
            reached = {s for s in reached if not s.startswith(test_prefixes)}
            records.append(
                {
                    "id": f"{f['path']}::{case['qualname']}",
                    "file": f["path"],
                    "framework": f["test_framework"],
                    "line": case["line"],
                    "symbol": f"{mid}.{case['qualname']}",
                    "reaches": sorted(reached),
                    "reaches_modules": sorted(
                        {symbol_module[s] for s in reached if s in symbol_module}
                        | imported_modules
                    ),
                }
            )
    return sorted(records, key=lambda r: r["id"])


def extract_ts(repo_root: Path) -> dict | None:
    """The TS/JS layer for *repo_root*, or None when it has no TS/JS.

    Raises :class:`TsExtractError` when TS/JS files exist but the helper
    can't run — never silently skips (P1).
    """
    repo_root = Path(repo_root)
    if not has_ts_files(repo_root):
        return None
    return join_facts(run_helper(repo_root))
