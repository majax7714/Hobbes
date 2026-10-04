"""Deterministic extraction pipeline (build plan M1).

Walks a repo with tree-sitter (ADR-005) and emits the three SHA-stamped
derived artifacts (ADR-006) into ``.hobbes/derived/``:

- ``graph.json`` — module nodes + symbol layer, typed edges (``imports``,
  ``env-read`` at module level, ``calls`` at symbol level), plus whatever
  the enrichment packs contributed and a ``packs`` list naming them,
  plus two honesty fields: ``tail_classes_available`` (C-32) and
  ``verification_base`` (C-31) — what each language's tail could have
  said, and how thin the evidence behind "supported" is for it,
- ``tests.json`` — pytest inventory with static test→symbol reach,
- ``interfaces.json`` — HTTP routes and CLI entry points, all of which
  now come from packs (ADR-035) rather than from the pipeline itself.

No LLM is involved anywhere in this package (P5: deterministic first).
The public entry points are :func:`extract_repo` (pure: tree → documents)
and :func:`ingest` (extract, stamp with the repo's git SHA, write).
"""

from __future__ import annotations

import re
import subprocess

from collections import Counter, defaultdict

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from hobbes.extract import evidence as ev
from hobbes.extract import (
    aliases,
    clscalls,
    containment,
    decorators,
    fixtures,
    indexcache,
    ingestlock,
    instcalls,
    laneacache,
    minted,
    pybases,
    pystatic,
    pyunion,
    reexport,
    rustsource,
    scipsource,
    staging,
    tail,
    tssource,
    withstmt,
)
from hobbes.extract.cppsource import collect_cpp_tests, extract_cpp
from hobbes.extract.csource import collect_c_tests, extract_c
from hobbes.extract.discover import discover_modules, linked_copies, too_deep
from hobbes.extract.emit import ensure_hobbes_ignored, repo_stamp, write_artifacts
from hobbes.extract.gosource import collect_go_tests, extract_go
from hobbes.extract.javasource import collect_java_tests, extract_java
from hobbes.extract.graph import build_graph, resolve_call_sites
from hobbes.extract.packs import REGISTRY as PACK_REGISTRY
from hobbes.extract.packs import Pack, PackContext, run_packs
from hobbes.extract.pysource import FromImport, parse_source
from hobbes.extract.rustsource import collect_rust_tests, extract_rust
from hobbes.extract.schema import (
    LANE_SCIP,
    LANE_TREE_SITTER,
    SEMANTIC,
    SYNTACTIC,
    tiered_edge,
)
from hobbes.extract.testmap import collect_tests, runner_excluded_trees
from hobbes.extract.timings import Timings
from hobbes.extract.tssource import (
    collect_ts_tests,
    declared_test_frameworks,
    extract_ts,
    uninventoried_runner_manifests,
)
from hobbes.extract.verification import verification_base

#: v2 (M3): "language" became "languages" when the infra layer joined
#: (ADR-010). v3 (M6, ADR-021): tests carry a per-test "framework" field
#: (a repo now mixes pytest with JS frameworks) and the global
#: tests.json "framework" field is gone; "languages" may include
#: typescript/javascript. v4 (V2.M1, ADR-028): every edge carries a
#: ``tier`` and every evidence entry a ``lane`` (architecture §3.4) —
#: additive over v3, so a reader that ignores unknown fields still reads
#: v4 correctly. Consumers reject versions they don't know (ADR-006), and
#: as of v4 they actually do: see :mod:`hobbes.artifacts`.
SCHEMA_VERSION = 4


@dataclass(frozen=True)
class Extraction:
    """The three artifact documents, minus the provenance stamp — and the
    fixture trees `hobbes review` reads beside them (ADR-114), which are
    not emitted."""

    graph: dict
    tests: dict
    interfaces: dict
    fixture_trees: tuple = ()


def extract_repo(
    repo_root: Path,
    tf_plan: Path | None = None,
    packs: tuple[Pack, ...] = PACK_REGISTRY,
    timings: Timings | None = None,
) -> Extraction:
    """Extract the knowledge skeleton (lanes + packs) under *repo_root*.

    Pure with respect to the working tree: no git access, no writes — the
    stamp and the emission live in :func:`ingest` so tests can exercise
    extraction on unversioned fixtures. *tf_plan* optionally names a
    ``terraform show -json`` file for plan enrichment (ADR-010).

    The order is load-bearing since V2.M3. **All of lane A first**, across
    every language, so the node and symbol space is complete; **then the
    packs** (V2.M4), which read those facts and add framework knowledge on
    top; **then the range join**, which is the only producer of symbol edges
    and needs the node space to project onto; **then the test map**, whose
    reach is measured over the edges the join produced. Running lane B per
    language as each was parsed — the M2 shape — could not work for
    TypeScript, because its nodes did not exist yet when the join ran.

    *packs* is a seam for the exit criterion (ADR-035): the suite extracts
    with a pack and without it, and asserts the difference is exactly that
    pack's contribution. Callers have no reason to pass it.
    """
    containment.reset_ledger()
    indexcache.reset_ledger()
    laneacache.reset_ledger()
    # Every step below is timed (ADR-119); the record never enters an
    # artifact, and a caller that passes none gets one that is dropped.
    timings = timings if timings is not None else Timings()
    repo_root = Path(repo_root).resolve()
    with timings.step("discover [python]"):
        modules = discover_modules(repo_root)
    too_deep_python: list[dict] = []
    with timings.step("parse [python]"):
        parsed = {}
        for m in modules:
            try:
                parsed[m.id] = parse_source((repo_root / m.path).read_bytes())
            except RecursionError:
                # C-171: the module stays a node and is read as empty.
                parsed[m.id] = parse_source(b"")
                # Read as empty, never as holding no code (ADR-117's amendment).
                parsed[m.id].no_code = False
                too_deep_python.append(too_deep(m.path, "Python"))
    with timings.step("graph [python]"):
        graph = build_graph(modules, parsed)
    degraded: list[dict] = [
        # C-73: a repo-internal directory link is walked once, at its
        # target, by every language's discovery; the record says why the
        # ids a reader expects under the link are not there.
        {
            "path": link,
            "stage": "discover",
            "message": (
                f"{link} is a symlink to {target}, inside the repo; the tree is "
                f"walked once at {target} and not counted a second time under "
                f"{link} (C-73)"
            ),
        }
        for link, target in linked_copies(repo_root)
    ]
    degraded += too_deep_python
    if graph.get("dynamic_loads"):
        degraded.append(_python_loads_record(graph["dynamic_loads"]))

    # Languages reflect what the repo actually contains — a TS-only repo
    # (M6) must not claim python.
    languages = ["python"] if modules else []

    with timings.step("lane A [ts]"):
        ts = extract_ts(repo_root)
    if ts:
        languages += ts["languages"]
        degraded += list(ts["errors"])
        degraded += _merge_layer(graph, ts["nodes"], ts["module_edges"])
        graph["symbols"] = _merge_symbols(graph["symbols"], ts["symbols"])

    with timings.step("lane A [go]"):
        go = extract_go(repo_root)
    if go:
        languages += go["languages"]
        degraded += list(go["errors"])
        degraded += _merge_layer(graph, go["nodes"], go["module_edges"])
        graph["symbols"] = _merge_symbols(graph["symbols"], go["symbols"])

    with timings.step("lane A [rust]"):
        rust = extract_rust(repo_root)
    if rust:
        languages += rust["languages"]
        degraded += list(rust["errors"])
        degraded += _merge_layer(graph, rust["nodes"], rust["module_edges"])
        graph["symbols"] = _merge_symbols(graph["symbols"], rust["symbols"])

    with timings.step("lane A [java]"):
        java = extract_java(repo_root)
    if java:
        languages += java["languages"]
        degraded += list(java["errors"])
        degraded += _merge_layer(graph, java["nodes"], java["module_edges"])
        graph["symbols"] = _merge_symbols(graph["symbols"], java["symbols"])

    # C++ runs before C, and only because of the `.h` claim (ADR-113 §1):
    # a header this layer took must not also be read as C, so C is handed
    # the claimed set. Like C's first unit, C++ has no lane B yet — every
    # edge is this layer's fallback, at `syntactic` tier.
    with timings.step("lane A [cpp]"):
        cpp = extract_cpp(repo_root)
    if cpp:
        languages += cpp["languages"]
        degraded += list(cpp["errors"])
        degraded += _merge_layer(graph, cpp["nodes"], cpp["module_edges"])
        graph["symbols"] = _merge_symbols(graph["symbols"], cpp["symbols"])

    # C has no lane B in this unit (no indexer exists yet): every edge is
    # this layer's fallback, at `syntactic` tier — the join's normal
    # degraded path (P6), not a special case.
    with timings.step("lane A [c]"):
        c = extract_c(
            repo_root,
            claimed=cpp["claimed_headers"] if cpp else None,
            # ADR-138: the files C++ owns are known paths to the C walk,
            # so a C header's include of one draws its edge — to the id
            # that walk gave it, which is why the map is its nodes'.
            foreign=(
                {n["path"]: n["id"] for n in cpp["nodes"] if n.get("path")} if cpp else None
            ),
        )
    if c:
        languages += c["languages"]
        degraded += list(c["errors"])
        degraded += _merge_layer(graph, c["nodes"], c["module_edges"])
        graph["symbols"] = _merge_symbols(graph["symbols"], c["symbols"])

    # Lane A is complete. Packs read it and add framework knowledge; the
    # graph builder itself knows nothing about FastAPI, Express or HCL.
    with timings.step("packs"):
      enriched = run_packs(
        PackContext(
            repo_root=repo_root,
            modules=modules,
            parsed=parsed,
            ts=ts,
            go=go,
            rust=rust,
            java=java,
            tf_plan=tf_plan,
        ),
        packs,
    )
    languages += enriched.languages
    degraded += enriched.errors
    degraded += _merge_layer(graph, enriched.nodes, enriched.module_edges)
    graph["packs"] = enriched.ran

    # The pytest fixture injections the symbol layer drew (ADR-137), handed
    # back here so the test map can follow them: they are edges in the
    # graph, but *which* `uses` edges may widen reach is not a thing an edge
    # says about itself.
    injections: list[dict] = []
    degraded += _build_symbol_layer(
        repo_root,
        graph,
        modules,
        parsed,
        ts,
        go,
        rust,
        java,
        c,
        cpp,
        timings=timings,
        injections=injections,
    )

    timings_tests = timings.step("tests")
    timings_tests.__enter__()
    tests = collect_tests(modules, parsed, graph["symbol_edges"], injections=injections)
    if ts:
        declared_test_frameworks(repo_root, ts["files"])
        tests += collect_ts_tests(ts["files"], ts["symbols"], graph["symbol_edges"])
        uninventoried = uninventoried_runner_manifests(repo_root, ts["files"])
        if uninventoried:
            degraded.append(_uninventoried_suite_record(uninventoried))
    if go:
        tests += collect_go_tests(go["files"], graph["symbol_edges"])
    if rust:
        tests += collect_rust_tests(rust["files"], graph["symbol_edges"])
    if java:
        tests += collect_java_tests(java["files"], graph["symbol_edges"])
    if c:
        tests += collect_c_tests(c["files"], graph["symbol_edges"])
    if cpp:
        tests += collect_cpp_tests(cpp["files"], graph["symbol_edges"])
    tests = sorted(tests, key=lambda t: t["id"])
    timings_tests.__exit__(None, None, None)
    if degraded:
        # Sorted, not append-ordered: which pass reported first is an
        # accident of pipeline order, and an artifact that changes with it
        # is not reproducible in the sense P1 means (ADR-035).
        graph["extraction_errors"] = sorted(
            degraded, key=lambda d: (d["stage"], d["path"], d["message"])
        )

    # The verification base is a property of Hobbes, not of the repo: how
    # many repos each detected language's accuracy was measured on
    # (architecture §3.8, C-31). Stamped into the artifact so the summary,
    # the surface, and the proxy state it where the language list is read.
    graph["verification_base"] = verification_base(sorted(set(languages)))
    # Where lane B ran (ADR-092 phase 3): every step and whether it was
    # contained, so an artifact built with the escape hatch says so
    # wherever it is read — the summary, list_blind_spots, a cell record.
    graph["containment"] = containment.summary()
    # Which Hobbes built this (ADR-094): the checkout the running code
    # came from and its commit. A stale install on PATH once produced an
    # artifact with pre-containment code; the artifact now says who made
    # it, and the knowledge tools repeat it.
    graph["built_by"] = built_by()

    return Extraction(
        graph={"languages": sorted(languages), **graph},
        tests={"tests": tests},
        interfaces={
            "routes": sorted(
                enriched.routes, key=lambda r: (r["file"], r.get("line", 0))
            ),
            "cli_entry_points": enriched.cli_entry_points,
        },
        # The trees this tree's own test runners exclude (ADR-114): read
        # here, where the tree is on disk, so each end of a review exempts
        # by its own configuration.
        fixture_trees=_timed(
            timings,
            "fixture trees",
            lambda: runner_excluded_trees(
                repo_root,
                (n.get("path", "") for n in graph["nodes"] if n.get("kind") in ("module", "package")),
            ),
        ),
    )


def _timed(timings: Timings, name: str, thunk):
    """Run *thunk* as the timed step *name* and return its value."""
    with timings.step(name):
        return thunk()


def _syntax_sites(modules, parsed) -> list:
    """Lane A's call sites, in evidence-IR shape (ADR-029). A method call on
    a receiver that reads as a union of in-repo classes is ``union-member``
    (ADR-168, C-184): the join draws nothing there from either lane."""
    union_sites = pyunion.union_member_sites(modules, parsed)
    return [
        ev.Site(
            provider=ev.TREE_SITTER,
            kind=ev.CALL_SITE,
            file=module.path,
            line=call.line,
            name=call.callee.split(".")[-1],
            col=call.col,
            scope=f"{module.id}.{call.scope}" if call.scope else module.id,
            ambiguous=(
                tail.UNION_MEMBER if (module.path, call.line, call.col) in union_sites else ""
            ),
        )
        for module in modules
        for call in parsed[module.id].calls
    ]


def _read_static_tests(
    graph: dict, modules, parsed, fallback: dict, python_reading: dict
) -> dict[str, list]:
    """Apply ADR-154 steps 3 and 5 to lane A's symbols and fallback, in place.

    Each Python file's static tests are evaluated under the reading lane B
    indexed with (:mod:`hobbes.extract.pystatic`). A twin's record takes
    its live def's ``line`` and ``end_line``, its id unchanged; a fallback
    entry naming any def of a twin names the live def instead, the node's
    one reading (a guess at the first def would disagree with lane B, and a
    dropped one would lose a call whose name lane B spells differently —
    an aliased import's ``f()`` — since the join's column reading needs
    lane A's answer); and one whose site lies inside a dead def of a twin
    is dropped, since the projection would file it under the live node by
    its scope. Returns, per file with a dead region, ``[reading, call
    sites withheld from a dead twin def]``.
    """
    version = python_reading.get("version")
    reading = pystatic.Reading(version=(version[0], version[1]) if version else None)
    out: dict[str, list] = {}
    records = {s["id"]: s for s in graph["symbols"]}
    twin_defs: dict[tuple[str, int], tuple[str, int]] = {}
    dead_defs: dict[str, list[tuple[int, int]]] = {}
    for module in sorted(modules, key=lambda m: m.path):
        read = pystatic.read_file(parsed[module.id], reading)
        if not read.regions:
            continue
        out[module.path] = [read, 0]
        for qualname, (live, dead) in read.twins.items():
            record = records.get(f"{module.id}.{qualname}")
            if record is not None:
                record["line"], record["end_line"] = live.line, live.end_line
            twin_defs[(module.path, live.line)] = (module.path, live.line)
            for symbol in dead:
                twin_defs[(module.path, symbol.line)] = (module.path, live.line)
                dead_defs.setdefault(module.path, []).append((symbol.line, symbol.end_line))
    if not twin_defs:
        return out
    # Any file's entry can name a twin's def; only a twin's own file can
    # hold a site inside its dead def.
    for key in list(fallback):
        in_dead_def = any(a <= key[1] <= b for a, b in dead_defs.get(key[0], ()))
        if in_dead_def:
            out[key[0]][1] += 1
        if in_dead_def:
            del fallback[key]
        elif tuple(fallback[key]) in twin_defs:
            fallback[key] = twin_defs[tuple(fallback[key])]
    return out


def _later_defs(
    graph: dict, modules, parsed, python_reading: dict
) -> dict[str, list[tuple[int, int]]]:
    """The spans of each Python qualname's later live defs (ADR-155 step 1).

    scip-python gives a name one scope binds more than once one definition,
    at the first def, so the node sits there; but a lane B ``uses`` fact
    inside a later def, or at its own name token, carries no lane A scope
    and the projection files it by the enclosing lines. Keyed by symbol id,
    each qualname with two or more defs gives ``(line, end_line)`` of every
    def other than the one its record sits at (after ADR-154 has moved a
    twin's record) and outside a dead region, ascending, read under the
    reading :func:`_read_static_tests` evaluates. A qualname with no span
    left is absent.
    """
    version = python_reading.get("version")
    reading = pystatic.Reading(version=(version[0], version[1]) if version else None)
    records = {s["id"]: s for s in graph["symbols"]}
    out: dict[str, list[tuple[int, int]]] = {}
    for module in sorted(modules, key=lambda m: m.path):
        facts = parsed[module.id]
        by_qualname: dict[str, list] = {}
        for symbol in facts.symbols:
            by_qualname.setdefault(symbol.qualname, []).append(symbol)
        if all(len(defs) < 2 for defs in by_qualname.values()):
            continue
        read = pystatic.read_file(facts, reading)
        for qualname, defs in by_qualname.items():
            record = records.get(f"{module.id}.{qualname}")
            if len(defs) < 2 or record is None:
                continue
            spans = sorted(
                (symbol.line, symbol.end_line)
                for symbol in defs
                if symbol.line != record["line"] and not read.dead(symbol.line)
            )
            if spans:
                out[record["id"]] = spans
    return out


#: The decorators that make a repeated name one property, not two defs
#: (C-186 leaves the group out: its node is the property).
_ACCESSORS = frozenset({"property", "setter", "getter", "deleter"})


def _python_repeats(
    graph: dict, modules, parsed, later_defs: dict[str, list[tuple[int, int]]] | None
) -> dict[str, tuple[str, list[int]]]:
    """Each Python name one scope defines two or more times, by symbol id:
    ``(kind, every def's line)`` (ADR-172, C-186).

    The node is one, at the first def (the index makes the defs one
    definition there; lane A keeps one record), whichever def runs. Where
    lane B ran, *later_defs* is ADR-155's reading: a def ADR-154's static
    reading found dead is out, and a twin whose record moved to its live
    def is settled, so it is not named. Without lane B every repeated
    qualname is named. A property's accessors are one property and are
    left out. *kind* is ``overload`` where a def is an ``@overload`` stub,
    else ``repeated``.
    """
    records = {s["id"]: s for s in graph["symbols"]}
    out: dict[str, tuple[str, list[int]]] = {}
    for module in sorted(modules, key=lambda m: m.path):
        facts = parsed.get(module.id)
        if facts is None:
            continue
        by_qualname: dict[str, list] = {}
        for symbol in facts.symbols:
            by_qualname.setdefault(symbol.qualname, []).append(symbol)
        for qualname, defs in by_qualname.items():
            symbol_id = f"{module.id}.{qualname}"
            record = records.get(symbol_id)
            if len(defs) < 2 or record is None:
                continue
            if later_defs is not None and symbol_id not in later_defs:
                continue
            names = {(d.dotted or "").rpartition(".")[2] for symbol in defs for d in symbol.decorators}
            if names & _ACCESSORS:
                continue
            lines = [record["line"]] + (
                [line for line, _ in later_defs[symbol_id]]
                if later_defs is not None
                else sorted(symbol.line for symbol in defs if symbol.line != record["line"])
            )
            out[symbol_id] = ("overload" if "overload" in names else "repeated", lines)
    return out


def _python_repeats_record(repeats: dict[str, tuple[str, list[int]]]) -> dict:
    """The one degradation record ADR-172 writes per ingest where a Python
    scope defines a name two or more times (C-186)."""
    overloads = sum(1 for kind, _ in repeats.values() if kind == "overload")
    shown = sorted(repeats.items(), key=lambda item: (item[1][0] == "overload", item[0]))
    examples = "; ".join(
        f"{symbol_id} ({kind}, defs at line {', '.join(str(line) for line in lines)})"
        for symbol_id, (kind, lines) in shown[:5]
    )
    return {
        "path": ".",
        "stage": "python-repeats",
        "message": (
            f"{len(repeats)} Python name(s) are defined two or more times in one scope: "
            f"{len(repeats) - overloads} written again (an `if`/`else` or `try`/`except` pair "
            "the static reading does not settle, or a later def that replaces the first) and "
            f"{overloads} `@overload` stub group(s). Each is one node at its first def, "
            "whichever def runs: an edge to it is evidenced at its call, but the node's lines "
            "name the first def, which may not be the one that runs (ADR-172, C-186). "
            f"{examples}{' …' if len(repeats) > 5 else ''}"
        ),
    }


def _shared_later_defs(
    symbols: list[dict], shared: dict[str, list[tuple[int, int]]]
) -> dict[str, list[tuple[int, int]]]:
    """ADR-163: each Rust id two differently written impl headers mint
    alike, with the spans of its defs other than the one its node sits
    at. An id the symbol layer does not carry is absent. ADR-165 reads a
    cfg twin's other arms through it the same way."""
    lines = {s["id"]: s["line"] for s in symbols}
    out: dict[str, list[tuple[int, int]]] = {}
    for symbol_id, spans in sorted(shared.items()):
        line = lines.get(symbol_id)
        later = [span for span in spans if span[0] != line] if line is not None else []
        if later:
            out[symbol_id] = later
    return out


def _shared_qualname_record(
    shared_later: dict[str, list[tuple[int, int]]], refused: list[dict]
) -> dict:
    """The one degradation record ADR-163 writes per ingest with a Rust id
    two impl headers share: how many, what was refused, examples."""
    calls = sum(1 for row in refused if row["kind"] == "calls")
    examples = "; ".join(
        f"{symbol_id} (later def at line {', '.join(str(line) for line, _ in spans)})"
        for symbol_id, spans in list(shared_later.items())[:3]
    )
    return {
        "path": ".",
        "stage": "rust-qualnames",
        "message": (
            f"{len(shared_later)} Rust symbol id(s) are minted by two or more "
            "differently written impl blocks in one file (`impl Pointer for *const T` "
            "and `impl Pointer for *mut T` both name `T.distance`), or by two kinds of "
            "item (`struct B` beside `const B`); each node is the "
            "first def, and a later def has no node of its own, so what is written "
            f"inside or resolved onto one is refused: {calls} call(s), counted in the "
            f"tail as `shared-qualname`, and {len(refused) - calls} other reference(s) "
            f"(ADR-163, C-180, C-182). Later defs: {examples}"
        ),
    }


def _unstated_bases_record(pairs: list[tuple[str, str]]) -> dict:
    """The one degradation record ADR-169 writes per ingest (C-185)."""
    examples = "; ".join(f"{cls} -> {base}" for cls, base in pairs[:5])
    return {
        "path": ".",
        "stage": "python-bases",
        "message": (
            f"{len(pairs)} Python class(es) name an in-repo base the index resolved in the class header, "
            "but the index states no relationship for the class (scip-python 0.6.6 writes none for some "
            "classes), so no `implements` edge is drawn from it to the base; its methods' own pairs may "
            f"still be (ADR-169, C-185). {examples}{' …' if len(pairs) > 5 else ''}"
        ),
    }


def _python_loads_record(loads: list[dict]) -> dict:
    """The one degradation record ADR-167 writes per ingest where a Python
    file loads a module by name: how many, how many were placed (C-179)."""
    placed = [load for load in loads if load["target"]]
    unplaced = [load for load in loads if not load["target"]]
    examples = "; ".join(
        f"{load['path']}:{load['line']} ({load['via']}"
        f"{' ' + repr(load['written']) if load['written'] else ', nothing literal'})"
        for load in unplaced[:3]
    )
    return {
        "path": ".",
        "stage": "python-loads",
        "message": (
            f"{len(loads)} Python call(s) in {len({load['path'] for load in loads})} file(s) load a "
            "module by name (`importlib.import_module`, `__import__`, `spec_from_file_location`); "
            "the graph draws no import edge for a load, so reach through one is not seen "
            f"(ADR-167, C-179). {len(placed)} name an in-repo module, and tests_guarding and "
            f"the review name the load beside it; {len(unplaced)} name no module the ingest "
            "could place (outside the repo, not literal, or more than one candidate)"
            + (f": {examples}" if examples else "")
        ),
    }


#: A name spelled like a C/C++ macro: capitals and digits in two or more
#: underscore-joined parts (``GTEST_LOCK_EXCLUDED_``, ``FMT_CATCH``).
_MACRO_STYLE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]*)+$")

#: What ends a declarator's parameter list and may precede a trailing
#: annotation macro: ``)`` and the qualifiers written after it.
_AFTER_PARAMETERS = re.compile(r"(?:\)|\bconst|\bvolatile|\bnoexcept|\boverride|\bfinal|&)\s*$")

#: A member initialiser list's start: ``) :`` (C-164's second shape).
_INITIALISER_START = re.compile(r"\)\s*:\s*$")

#: A block's end, then only blank space before the name on its line: a
#: macro written where a statement goes (``} FMT_CATCH(...) {}``).
_AFTER_BLOCK = re.compile(r"\}\s*$")


def _cpp_macro_names(
    repo_root: Path, symbols: list[dict], nodes: list[dict], cpp_paths: dict
) -> list[dict]:
    """C++ functions and methods left in the graph that tree-sitter-cpp
    named for something written after the true declarator (C-164's
    remainder, ADR-135's amendment): a macro-spelled name right after a
    parameter list or a block's closing brace, or any name right after
    ``) :``, the first member initialiser. Where an index ran, ADR-135's R1 has removed most of them.
    Sorted by id."""
    path_of = {n["id"]: n.get("path") for n in nodes}
    texts: dict[str, list[str]] = {}
    named = []
    for symbol in symbols:
        path = path_of.get(symbol.get("module"))
        name = symbol.get("name") or ""
        if symbol.get("kind") not in ("function", "method") or path not in cpp_paths:
            continue
        if path not in texts:
            try:
                texts[path] = (repo_root / path).read_text(errors="replace").splitlines()
            except OSError:
                texts[path] = []
        lines = texts[path]
        row = symbol.get("line", 0) - 1
        if not 0 <= row < len(lines) or name not in lines[row]:
            continue
        before = "\n".join(lines[max(0, row - 2):row] + [lines[row][: lines[row].index(name)]])
        if _INITIALISER_START.search(before) or (
            _MACRO_STYLE.match(name)
            and (_AFTER_PARAMETERS.search(before) or _AFTER_BLOCK.search(before))
        ):
            named.append(symbol)
    return sorted(named, key=lambda symbol: symbol["id"])


def _cpp_macro_name_record(named: list[dict]) -> dict:
    """The one degradation record per ingest naming C-164's remainder: C++
    functions whose name is spelled like a macro, which may be the macro's
    name and not the function's."""
    examples = "; ".join(
        f"{symbol['name']} at {symbol['module']}:{symbol['line']}" for symbol in named[:5]
    )
    return {
        "path": ".",
        "stage": "cpp-macro-names",
        "message": (
            f"{len(named)} C++ function(s) are named for what follows their declarator: a "
            "trailing annotation macro tree-sitter-cpp read as the declarator (`void f() "
            "GTEST_LOCK_EXCLUDED_(mu) {` is a function called `GTEST_LOCK_EXCLUDED_`), a "
            "macro written as a statement after a block (`} FMT_CATCH(...) {}`), or a "
            "constructor's first member initialiser (`C(int x) : size_(x) {`). The function's "
            "calls are drawn from the misnamed symbol, and no index ran there to remove it "
            f"(ADR-135, C-164). {examples}{' …' if len(named) > 5 else ''}"
        ),
    }


def _uninventoried_suite_record(manifests: list[tuple[str, str]]) -> dict:
    """The one degradation record C-194 writes per ingest: packages that
    declare a test runner while no file under them is test-named."""
    examples = "; ".join(f"{path} ({runner})" for path, runner in manifests[:5])
    return {
        "path": ".",
        "stage": "js-tests",
        "message": (
            f"{len(manifests)} package(s) declare a test runner but no file under them is "
            "test-named (`*.test.*`, `*.spec.*`, `__tests__/`), so their suites are not "
            "inventoried and `tests_guarding` answers nothing there (C-194). "
            f"{examples}{' …' if len(manifests) > 5 else ''}"
        ),
    }


def _go_init_record(inits: dict[str, list[tuple[int, int]]]) -> dict:
    """The one degradation record ADR-166 writes per ingest where a Go file
    declares two or more ``func init()``: how many, and examples."""
    examples = "; ".join(
        f"{symbol_id} (later def at line {', '.join(str(line) for line, _ in spans)})"
        for symbol_id, spans in list(inits.items())[:3]
    )
    return {
        "path": ".",
        "stage": "go-inits",
        "message": (
            f"{len(inits)} Go file(s) declare two or more `func init()`; Go runs them "
            "all and no code can name one, so each file's are one node, `<module>.init`, "
            "at the first def, and what is written inside a later one is filed under it "
            f"(ADR-166, C-183). Read an edge's evidence line to tell them apart. {examples}"
        ),
    }


def _rust_repeat_record(repeats: dict[str, dict[str, list[tuple[int, int]]]]) -> dict:
    """The one degradation record per ingest naming C-182's residual: ids
    written two or more times with one header and one kind that are not a
    cfg twin, neither refused nor mapped (ADR-165's amendment)."""
    files = sorted(repeats)
    ids = [symbol_id for path in files for symbol_id in repeats[path]]
    examples = "; ".join(
        f"{symbol_id} (defs at line {', '.join(str(line) for line, _ in repeats[path][symbol_id])})"
        for path in files
        for symbol_id in list(repeats[path])[:3]
    )
    return {
        "path": ".",
        "stage": "rust-repeats",
        "message": (
            f"{len(ids)} Rust symbol id(s) in {len(files)} file(s) are written two or more "
            "times with one header and one kind, and some def carries no `#[cfg]`, so lane A "
            "cannot say they are one item compiled two ways (a file no crate compiles writes "
            "this freely); each is one node at its first def, a later def's facts are filed "
            "under it and a call resolved onto one is `below-floor` (ADR-165, C-182). "
            f"Files: {', '.join(files[:5])}{' …' if len(files) > 5 else ''}. {examples}"
        ),
    }


def _cfg_twin_record(
    twins: dict[str, dict[str, list[tuple[int, int]]]],
    compiled: dict[str, tuple[int, int]] | None = None,
    refused: Counter | None = None,
) -> dict:
    """The one degradation record ADR-165 writes per ingest with a Rust
    cfg twin (C-182): how many, and examples with their def lines; since
    its second amendment, how many sit at the arm lane B compiled and how
    many lane B references written in an uncompiled arm were refused."""
    compiled = compiled or {}
    refused = refused or Counter()
    ids = sorted(
        (symbol_id, spans) for by_id in twins.values() for symbol_id, spans in by_id.items()
    )
    examples = "; ".join(
        f"{symbol_id} (defs at line {', '.join(str(line) for line, _ in spans)})"
        for symbol_id, spans in ids[:3]
    )
    return {
        "path": ".",
        "stage": "rust-cfg-twins",
        "message": (
            f"{len(ids)} Rust symbol id(s) are cfg twins: one item written two or more "
            "times in one file, each def under a `#[cfg(…)]` with the same header and "
            f"kind. Each is one node: {len(compiled)} sit at the one arm lane B defined "
            "(the arm the build compiled), the rest at their first def, whichever arm "
            "the build compiles. Lane A files every arm's calls under the node "
            "(`syntactic`), and a call lane B resolves onto any arm draws to it. "
            f"{sum(refused.values())} lane B reference(s) written inside an arm the build "
            f"did not compile were refused ({len(refused)} file(s)): rust-analyzer "
            "resolves them against the compiled arm's scope, so they are not evidence "
            f"of the build (ADR-165, C-182). Twins: {examples}"
        ),
    }


def _static_reading_records(
    static_reading: dict[str, list], symbol_edges: list[dict], version
) -> list[dict]:
    """One ``scip-python`` degradation record per file with a dead region
    (ADR-154 step 4, C-173): the spans, the forms that killed them, the
    reading, lane A's edges there, the twins and the sites withheld."""
    said = f"Linux / Python {version[0]}.{version[1]}" if version else "Linux, version unread"
    in_regions: Counter = Counter()
    for edge in symbol_edges:
        paths = {
            row.get("path")
            for row in edge.get("evidence", ())
            if row.get("path") in static_reading
            and static_reading[row["path"]][0].dead(row.get("line", 0))
        }
        in_regions.update(paths)
    records = []
    for path in sorted(static_reading):
        read, withheld = static_reading[path]
        spans = ", ".join(
            str(first) if first == last else f"{first}–{last}" for first, last in read.regions
        )
        edges = in_regions[path]
        twins = (
            "twins recorded at their live def: "
            + ", ".join(f"{q} (line {live.line})" for q, (live, _) in read.twins.items())
            if read.twins
            else "no twin"
        )
        unread = "" if version else "; a version test is read as not static"
        records.append(
            {
                "path": path,
                "stage": "scip-python",
                "message": (
                    f"{'line' if len(read.regions) == 1 and read.regions[0][0] == read.regions[0][1] else 'lines'} "
                    f"{spans} read as never run under {said} "
                    f"({', '.join(read.forms)}{unread}): scip-python indexes "
                    "nothing there, so lane B is silent and lane A's edges there "
                    f"are `syntactic` only ({edges} symbol edge"
                    f"{'' if edges == 1 else 's'} with evidence in them); "
                    f"{twins}; {withheld} call site{'' if withheld == 1 else 's'} "
                    "in a dead twin def withheld (ADR-154, C-173)"
                ),
            }
        )
    return records


def _build_symbol_layer(
    repo_root: Path,
    graph: dict,
    modules,
    parsed,
    ts: dict | None,
    go: dict | None = None,
    rust: dict | None = None,
    java: dict | None = None,
    c: dict | None = None,
    cpp: dict | None = None,
    timings: Timings | None = None,
    injections: list[dict] | None = None,
) -> list[dict]:
    """Join every lane's evidence and project it onto the graph's ids.

    **The only producer of *joined* symbol edges** (ADR-031), and it runs
    whether or not lane B does: with no semantic resolutions every call site
    falls to the fallback arm and the graph is lane A's, at ``syntactic``
    tier. That is P6 satisfied by construction rather than by a second code
    path — the degraded case is the normal case with an empty input.

    The one thing appended after the projection is the pytest fixture
    injections (ADR-137): lane A facts with no call site for any occurrence
    to claim, drawn ``uses`` / ``syntactic`` / ``tree-sitter`` and re-sorted
    into the projection's own order. *injections* is the list they are
    handed back on, for the test map to follow.

    Both languages' evidence is pooled before joining. They cannot collide:
    the join buckets by ``(file, line)`` and no file belongs to two
    languages.

    Returns degradation records; never raises. A missing indexer, a crashed
    one, or an uninstalled environment must not fail an ingest.
    """
    timings = timings if timings is not None else Timings()
    degraded: list[dict] = []
    syntax: list[ev.Site] = []
    resolutions: list[ev.Site] = []
    fallback: dict[tuple, tuple] = {}
    external: list[dict] = []

    with timings.step("lane A sites"):
        if modules:
            syntax += _syntax_sites(modules, parsed)
            fallback.update(resolve_call_sites(modules, parsed))
        for layer in (ts, go, rust, java, c, cpp):
            if layer:
                syntax += layer["call_sites"]
                fallback.update(layer["call_fallback"])

    # ADR-113 §2 (amended a third time): the C++ call-site files lane B
    # compiled. An occurrence of any kind — a definition, a reference, an
    # external reference — is the proof that scip-clang indexed the file;
    # where it then answered nothing at a call site, the join withholds
    # lane A's name guess rather than drawing it (C-152). A C++ file lane B
    # did not index carries no occurrence and keeps its fallback, which is
    # C-135's C++ face: no compile database, a failed build, a file outside
    # it. Read off the C++ layer's own files rather than off a facts
    # document's language, because the C and C++ roots merge into one
    # document that carries none — and the two say the same thing here: a
    # root holding any C++ file is a `cpp` root (`extract_scip_c`), and no
    # other indexer sees a C++ file at all.
    cpp_site_files = {site.file for site in cpp["call_sites"]} if cpp else set()
    cpp_withheld_files: set[str] = set()
    implements_counts: Counter = Counter()

    # ADR-129: the C and C++ files lane A walked, and the ones whose parse
    # had ERROR nodes. A `definitions` row in a lossy file is a definition
    # the parse *lost*, and `minted.mint` decides which of them becomes a
    # symbol; rows outside these files belong to another language's lane A,
    # which has no such loss to recover.
    lane_a_c_files = {parsed.path for layer in (c, cpp) if layer for parsed in layer["files"]}
    lossy_files = frozenset().union(*(layer["lossy_files"] for layer in (c, cpp) if layer))
    lane_b_definitions: list[dict] = []
    # ADR-142, the same shape for TS/JS: the definition rows lane B raised
    # in the files lane A walked as TS/JS, collected only where lane A
    # recorded a `new` token at all — with no construction written there
    # is nothing for the reading to answer, and no reason to keep a row.
    ts_files = (
        {f["path"] for f in ts["files"]} if ts and ts.get("constructions") else set()
    )
    ts_definitions: list[dict] = []
    lane_b_ran = False
    # ADR-165's second amendment: the lines lane B defined something at, in
    # the files that hold a Rust cfg twin, to say which arm was compiled.
    rust_twin_files = set(rust.get("cfg_twins") or {}) if rust else set()
    rust_defined: dict[str, set[int]] = {}
    # ADR-154: the platform and version scip-python read Python under, set
    # only where lane B ran for Python.
    python_reading: dict | None = None

    for facts in _lane_b_facts(
        repo_root, modules, ts, go, rust, java, c, cpp, degraded, timings=timings
    ):
        # A reference arrives as a resolution site (ADR-116); definitions
        # and external references stay the helper's rows.
        references = facts.get("references") or []
        resolutions += references
        # The override set rides with the resolutions (ADR-120): the join
        # buckets only resolutions by line, and draws every implements
        # site as its own fact.
        resolutions += facts.get("implements") or []
        for key in scipsource._IMPLEMENTS_COUNTS:
            implements_counts[key] += facts.get(key) or 0
        external += facts.get("external_refs") or []
        lane_b_ran = True
        if facts.get("python_reading") is not None:
            python_reading = facts["python_reading"]
        if lane_a_c_files:
            lane_b_definitions += [
                row for row in facts.get("definitions") or [] if row["file"] in lane_a_c_files
            ]
        for row in facts.get("definitions") or [] if rust_twin_files else []:
            if row["file"] in rust_twin_files:
                rust_defined.setdefault(row["file"], set()).add(row["line"])
        if ts_files:
            ts_definitions += [
                row for row in facts.get("definitions") or [] if row["file"] in ts_files
            ]
        if cpp_site_files:
            indexed = {site.file for site in references}
            indexed.update(
                row["file"] for key in ("definitions", "external_refs") for row in facts.get(key) or []
            )
            cpp_withheld_files |= indexed & cpp_site_files
        for record in facts.get("degraded", []):
            degraded.append(
                {
                    "path": record.get("path", "."),
                    "stage": record["stage"],
                    "message": record["message"],
                }
            )
        coverage = facts.get("dependency_coverage") or {}
        if coverage.get("declared"):
            graph.setdefault("dependency_coverage", []).append(coverage)

    # ADR-154, between lane B and the join: where lane B ran for Python,
    # the code its Pyright read as never run on Linux at the read version
    # has no occurrence. A twin's record moves to its live def, so lane B's
    # references to it land, and lane A stops guessing at a twin's name or
    # filing a dead def's calls under the live node. Without lane B for
    # Python nothing is evaluated and the graph is what it was (P6).
    # ADR-155, after it so a twin's record has moved: a qualname's later
    # live defs, which the projection reads as its node's lines too.
    static_reading: dict[str, list] = {}
    later_defs: dict[str, list[tuple[int, int]]] | None = None
    if python_reading is not None and modules:
        static_reading = _read_static_tests(graph, modules, parsed, fallback, python_reading)
        later_defs = _later_defs(graph, modules, parsed, python_reading)
    # ADR-172 (C-186), read before Go's inits join the later defs: each
    # Python name a scope defines more than once is one node at its first
    # def, whichever runs, and one record names them.
    python_repeats = _python_repeats(graph, modules, parsed, later_defs) if modules else {}
    if python_reading is not None and modules:
        # ADR-161, before the join: a Python reference lane B named with
        # another symbol's name through a module the file imports is
        # scip-python's reading of a `from … import *` re-export (C-178).
        # It is refused — it reaches no edge, row or count — and counted in
        # one record; nothing is repaired. Without lane B for Python there
        # is nothing to refuse and nothing is recorded (P6).
        python_files: dict[str, tuple[list[str], frozenset[str]]] = {}
        for module in modules:
            facts_file = parsed.get(module.id)
            if facts_file is None:
                continue
            try:
                text = (repo_root / module.path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            python_files[module.path] = (
                reexport.source_lines(text),
                reexport.module_names(facts_file),
            )
        resolutions, refused_rows = reexport.refuse(resolutions, python_files)
        refusal = reexport.record(refused_rows)
        if refusal is not None:
            degraded.append(refusal)

    # ADR-165's second amendment (C-182), before the join: the arm of each
    # Rust cfg twin lane B defined is the compiled one, and a reference lane
    # B wrote inside an arm it did not compile was resolved against the
    # compiled arm's scope — it is refused and counted. Lane A's facts there
    # stay `syntactic`. Without lane B for the file nothing is named (P6).
    rust_compiled: dict[str, tuple[int, int]] = {}
    rust_dead_refused: Counter = Counter()
    if rust_defined:
        rust_compiled, dead = rustsource.compiled_arms(rust["files"], rust_defined)
        if dead:
            kept = []
            for site in resolutions:
                regions = dead.get(site.file)
                if regions and any(start <= site.line <= end for start, end in regions):
                    rust_dead_refused[site.file] += 1
                else:
                    kept.append(site)
            resolutions = kept

    withhold = frozenset(cpp_withheld_files)
    # ADR-131: lane A's operator tokens, read by the join alone and only
    # where lane B ran for C++ — with no indexer there is no reference to
    # match, so the tokens are read by nothing and the graph is what it
    # was (P6). The two counts come back in this dict rather than in the
    # join's return value, which every other caller reads unchanged.
    operator_counts: dict[str, int] = {"drawn": 0, "in_template": 0}
    # ADR-132, on the same condition and for the same reason: the tokens
    # and the constructor set are read together or not at all. The set is
    # read off the rows the mint already collected below — the C++ ones
    # among them; C has no constructors, so its rows name none.
    construction_counts: dict[str, int] = {"drawn": 0, "in_template": 0, "implicit": 0}
    constructors = (
        minted.constructor_lines(lane_b_definitions) if cpp and lane_b_ran else None
    )
    # ADR-175, rule C: lane A's body spans and the macro definitions lane B
    # names, read beside the pair above and on its condition.
    macro_definitions = (
        minted.macro_lines(lane_b_definitions) if cpp and lane_b_ran else None
    )
    # ADR-142: lane A's `new` tokens and lane B's reading of what each
    # definition would be constructed as — the TS/JS pair, read together
    # or not at all, and only where lane B ran. With no index there is no
    # reference to meet a token, so the tokens are read by nothing and the
    # graph is what it was (P6), exactly as the C++ pair above.
    ts_construction_counts: dict[str, int] = {"drawn": 0, "named_class": 0}
    ts_targets = (
        scipsource.ts_construction_targets(ts_definitions)
        if ts_definitions and lane_b_ran
        else None
    )
    with timings.step("join"):
        resolved = ev.join(
            syntax,
            resolutions,
            fallback=fallback,
            external=external,
            withhold=withhold,
            operators=cpp["operators"] if cpp and lane_b_ran else None,
            counts=operator_counts,
            constructions=cpp["constructions"] if cpp and lane_b_ran else None,
            constructors=constructors,
            construction_counts=construction_counts,
            ts_constructions=ts["constructions"] if ts_targets else None,
            ts_targets=ts_targets,
            ts_construction_counts=ts_construction_counts,
            bodies=cpp["bodies"] if cpp and lane_b_ran else None,
            macros=macro_definitions,
        )
    if operator_counts["drawn"] or operator_counts["in_template"]:
        # Additive, and absent on a repo with nothing to say — a C++
        # operator drawn as a call is a new thing in the graph, and the
        # one inside a template that was not is the cost beside it.
        graph["operators"] = dict(operator_counts)
    if (
        construction_counts["drawn"]
        or construction_counts["in_template"]
        or construction_counts["implicit"]
    ):
        # Additive too, and absent where there is nothing to say: a
        # construction drawn as a call is a new edge, and the one inside a
        # template left as a `uses` is what the rule did not draw.
        graph["constructions"] = dict(construction_counts)
    if ts_construction_counts["drawn"] or ts_construction_counts["named_class"]:
        # ADR-142's two, in the same block and absent on the same terms —
        # a repo with no TS/JS construction says nothing, as one with no
        # C++ construction says nothing. Named apart from C++'s because
        # they are different rules over different files, and a reader of
        # one number must not read it as the other's.
        graph.setdefault("constructions", {}).update(
            ts_drawn=ts_construction_counts["drawn"],
            ts_named_class=ts_construction_counts["named_class"],
        )
    # ADR-129, after the join and before the projection: where lane A's
    # parse lost a C or C++ definition, lane B's definition row becomes the
    # symbol, so `starting_at` answers for the lost line and the calls
    # scip-clang already resolved there draw instead of falling
    # `below-floor`. ADR-134 reads such a definition's extent from the
    # file's own braces and re-homes the facts written inside it, which is
    # the one thing here that touches a fact the join settled — and it
    # touches only its caller. ADR-135 runs first, and is the one rule that
    # touches lane A's **symbols**: a C++ function or method whose own name
    # token the index reads as a reference, or whose extent holds a
    # definition, is refused or clipped here, so the mint meets the line as
    # lost. ADR-136 carries the positions it emptied over: a line R1 vacated
    # is read by the mint even in a file that parsed clean, since the
    # removal is evidence against the premise `clean-file` rests on — a
    # generator macro parses without an ERROR node and lane A names the
    # function after it. Nothing else lane A decided sees any of it — the
    # fallback tables, `withhold`, the lane agreement inputs and
    # `full_specializations` are all settled above, and a fallback naming a
    # refused symbol finds nothing at the projection and draws nothing —
    # and `project` needs no change: the called-type guard, R-qual and the
    # macro handling apply to a minted target as to any other, and
    # `enclosing` answers with a minted extent as with a parsed one.
    if lane_a_c_files and lane_b_ran:
        module_of_path = {n["path"]: n["id"] for n in graph["nodes"] if n.get("path")}
        with timings.step("contradicted"):
            graph["symbols"], resolved, contradictions, vacated = minted.contradicted(
                repo_root,
                graph["symbols"],
                resolved,
                resolutions,
                lane_b_definitions,
                module_of_path,
            )
        if minted.contradicted_fired(contradictions):
            # Additive, and absent where neither rule fired, as `operators`
            # and `constructions` are.
            graph["lane_a_contradicted"] = contradictions
        with timings.step("mint"):
            minted_symbols, graph["minted"] = minted.mint(
                repo_root,
                lane_b_definitions,
                lossy_files,
                graph["symbols"],
                module_of_path,
                vacated=vacated,
            )
        if minted_symbols:
            graph["symbols"] = sorted(
                graph["symbols"] + minted_symbols, key=lambda s: s["id"]
            )
        with timings.step("rehome"):
            resolved, graph["minted"]["extents"]["rehomed"] = minted.rehome(
                resolved, minted_symbols, graph["symbols"], module_of_path
            )
    # ADR-163 (C-180), read off the settled symbols so "later" means every
    # def but the one the node sits at: lane A and lane B alike.
    shared_later = (
        _shared_later_defs(graph["symbols"], rust.get("shared_qualnames") or {})
        if rust
        else {}
    )
    # ADR-165's second amendment: a twin whose compiled arm lane B named
    # sits there, so its line is the code the build runs; its other arms,
    # read next, include the first.
    if rust_compiled:
        for symbol in graph["symbols"]:
            arm = rust_compiled.get(symbol["id"])
            if arm is not None:
                symbol["line"], symbol["end_line"] = arm
    # ADR-165 (C-182): a cfg twin's other arms, read off the settled
    # symbols the same way; they are the node's own code.
    twin_arms = (
        _shared_later_defs(
            graph["symbols"],
            {
                symbol_id: spans
                for by_id in (rust.get("cfg_twins") or {}).values()
                for symbol_id, spans in by_id.items()
            },
        )
        if rust
        else {}
    )
    # ADR-166 (C-183): a Go file's later `func init()` defs, read off the
    # settled symbols the same way; every init is the node's code, so they
    # join ADR-155's later defs and the enclosing lookup files under it.
    go_inits = _shared_later_defs(graph["symbols"], go.get("init_spans") or {}) if go else {}
    if go_inits:
        later_defs = {**(later_defs or {}), **go_inits}
    with timings.step("project"):
        projected = scipsource.project(
            resolved,
            graph["nodes"],
            graph["symbols"],
            # ADR-125: the classes C++ declares `template <>`, the one
            # owner shape whose arguments are concrete enough for a
            # written qualifier to contradict. No C++ layer, no rule.
            full_specializations=cpp["full_specializations"] if cpp else frozenset(),
            # ADR-155: a Python qualname's later live defs; None without
            # lane B for Python, and the index is what it was.
            later_defs=later_defs,
            # ADR-163: a Rust id two differently written impl headers
            # share; a fact at one of its later defs is refused.
            shared=shared_later,
            # ADR-165: a Rust cfg twin's other arms are the node's.
            twins=twin_arms,
        )
    # What the override set could not draw (ADR-120), so the summary says
    # how far the `implements` edges reach: pairs to a declaration outside
    # the repo (a stdlib interface), pairs whose source is no graph
    # definition, mutual pairs nothing oriented, and pairs whose end lane A
    # keeps no symbol for (a Go interface's method spec — C-58's floor).
    graph["implements"] = {
        "outside": implements_counts["implements_outside"],
        "unplaced": implements_counts["implements_unplaced"],
        "undirected": implements_counts["implements_undirected"],
        "below_floor": projected.get("implements_below_floor", 0),
    }
    # ADR-169 (C-185): a Python class whose base lane B resolved in its
    # header and whose `implements` edge the index never stated. Only where
    # lane B ran for Python; nothing is drawn, one record names the pairs.
    if python_reading is not None and modules:
        unstated = pybases.unstated_bases(modules, parsed, graph["symbols"], projected["symbol_edges"])
        if unstated:
            degraded.append(_unstated_bases_record(unstated))
    with timings.step("lane agreement"):
      graph["lane_agreement"] = _lane_agreement(
        syntax,
        resolutions,
        fallback,
        graph["module_edges"],
        projected["module_edges"],
        # Go and Rust both leave in-repo import edges to the join (a Go
        # import names a package, a Rust `use` names an item path), so
        # their lane-B-only module edges are exclusions, not findings.
        # Java joins them for the mirror reason: same-package references
        # need no import statement, so lane B raises module edges lane A
        # never spelled (ADR-096). C joins them too (ADR-109): lane A spells
        # a file's includes, while lane B raises the module edges calls make
        # between `.c` files, which no include names.
        lane_b_only_modules={
            n["id"]
            for layer in (go, rust, java, c)
            if layer
            for n in layer["nodes"]
            if "path" in n
        },
        external=external,
        withhold=withhold,
        cpp_site_files=cpp_site_files,
        twins=rust.get("cfg_twins") if rust else None,
    )
    degraded += _cpp_fallback_records(graph["lane_agreement"])
    graph["symbol_edges"] = projected["symbol_edges"]
    if static_reading:
        degraded += _static_reading_records(
            static_reading, graph["symbol_edges"], python_reading.get("version")
        )
    # ADR-137, after the projection and appended to it: pytest's fixture
    # lookup is syntax — the parameter, the class, the file and the conftest
    # chain are all in the tree lane A parses — and what it resolves is a
    # lane A fact no lane B occurrence can claim, because the test wrote no
    # call site there for the join to match. The edge is `uses`, never
    # `calls` (a name-matched call from a fixture parameter was wrong six
    # times of six at the oracle's first Python triage, graph._shadowed),
    # and the list is re-sorted by the projection's own key, so the join
    # stays the only producer of *joined* edges (ADR-031).
    with timings.step("fixtures"):
        drawn, fixture_counts = fixtures.injections(modules, parsed)
        _add_injection_edges(graph, drawn)
        # ADR-145, appended after the projection for the same reason and
        # one more: where a fixture's body is a single `return C(…)`, a
        # `p.m(…)` on the injected parameter is a call on `C.m` — but the
        # index emits *nothing* at `m` (scip-python does not type an
        # unannotated parameter), so there is no occurrence for the join
        # to match and no joined edge to wait for. The two hops it does
        # draw — the injection above and the `semantic` edge from the
        # fixture to the class it constructs — are read off the settled
        # graph here. A pair the graph already carries a `calls` edge for
        # is left alone: the join's edge stands, and the rule counts its
        # own abstention. Resolution coverage is deliberately not moved
        # (ADR-145, *What this leaves*): the join did not resolve the
        # site, the file's tail still counts it `attr-call`, and the
        # percentage stays a floor.
        value_rows, value_counts = fixtures.value_calls(
            modules, parsed, drawn, graph["symbols"], graph["symbol_edges"]
        )
        _add_value_call_edges(graph, value_rows)
        if value_counts:
            fixture_counts["value_calls"] = value_counts
    if fixture_counts:
        # Additive, and absent on a repo that defines no fixture and looks
        # no parameter up, as `operators` and `constructions` are.
        graph["fixtures"] = fixture_counts
    # ADR-147, ADR-148 and ADR-149, appended after the projection for the
    # same reason as the two above: `@f(…)` is two calls, and the index
    # names only the first.
    # Applying what `f(…)` returned is written nowhere — there is no token
    # for the index to name — so no occurrence exists for the join to match
    # and no joined edge to wait for. What the rule reads is the settled
    # graph's own answer at the decorator's line (the `semantic` edge
    # ADR-146 put there) plus the factory's written shape, so it runs here,
    # after the projection and before the test map, whose reach follows
    # these edges as it follows any `calls` edge. Resolution coverage is
    # deliberately not moved (ADR-147, *What this leaves*): there is no
    # site to count, so the percentage stays the floor it was.
    with timings.step("decorators"):
        factory_rows, factory_counts = decorators.factory_calls(
            modules, parsed, graph["symbols"], graph["symbol_edges"]
        )
        _add_factory_call_edges(graph, factory_rows)
        if factory_counts:
            graph["decorators"] = {"factory_calls": factory_counts}
    # ADR-156, appended after the projection for the same reason as the
    # three above: a `with` statement runs its item's `__enter__` and
    # `__exit__` and writes a call to neither, so there is no token for the
    # index to name and no joined edge to wait for. The class is read off
    # the settled graph at the item's own call (and, for a factory, at its
    # return annotation), as ADR-145 reads a construction.
    with timings.step("with"):
        with_rows, with_counts = withstmt.with_calls(
            modules, parsed, graph["symbols"], graph["symbol_edges"]
        )
        _add_with_call_edges(graph, with_rows)
        if with_counts:
            # Additive, and absent where no `with` item is a call.
            graph["with_statements"] = with_counts
    # ADR-160, after the `with` step and for the same reason: a call
    # through a local alias names the local at the site, below the symbol
    # floor (C-9), so the join has nothing to draw. The target is the
    # index's own edge at the alias's assignment, read off the settled
    # graph. Resolution coverage is not moved (ADR-160 *Not taken*).
    with timings.step("aliases"):
        alias_rows, alias_counts = aliases.alias_calls(
            modules, parsed, graph["symbols"], graph["symbol_edges"]
        )
        _add_alias_call_edges(graph, alias_rows)
        if alias_counts:
            # Additive, and absent where no file records an alias.
            graph["aliases"] = alias_counts
    # ADR-170, after the aliases and for the same reason: `cls(…)` in a
    # classmethod names the parameter at the site, below the symbol floor
    # (C-9); the class is where the `def` is written. `syntactic`.
    with timings.step("cls calls"):
        cls_rows, cls_counts = clscalls.cls_calls(
            modules, parsed, graph["symbols"], graph["symbol_edges"]
        )
        _add_alias_call_edges(graph, cls_rows, via=clscalls.CLS)
        if cls_counts:
            # Additive, and absent where no file records a classmethod.
            graph["cls_calls"] = cls_counts
    # ADR-171, after the `cls` step and for the same reason: calling an
    # instance runs its class's `__call__`, and the site names a local or
    # an expression, so the join has nothing to draw. The class is the
    # index's own edge at the construction. `syntactic`; a module-level
    # `C(…)(…)` is drawn from the module, as a module-level `with` is.
    with timings.step("instance calls"):
        instance_rows, instance_counts = instcalls.instance_calls(
            modules, parsed, graph["symbols"], graph["symbol_edges"]
        )
        _add_with_call_edges(graph, instance_rows, via=instcalls.CALL)
        if instance_counts:
            # Additive, and absent where no file records a site.
            graph["instance_calls"] = instance_counts
    if injections is not None:
        injections.extend(drawn)
    # C-153's surfacing (ADR-125 §4), read off the edges the projection has
    # just settled: which of them start in a C++ template pattern.
    degraded += _cpp_template_pattern_records(graph, cpp)
    graph["module_edges"] = _merge_module_edges(
        graph["module_edges"], projected["module_edges"]
    )
    # The tail view (ADR-045): the unresolved remainder, classified by
    # observation — checker origins for TS/JS (facts v4), pinned builtin
    # names, text shape — so "13% unaccounted" decomposes into what the
    # graph sees and does not model versus what it cannot resolve. The
    # classified set is derived from the same disposition walk as the
    # counts, so per file the tail sums to `unresolved` by construction.
    origins = tssource.call_origins(ts["files"]) if ts else {}
    # Names bound by `from x import y as z` per Python file — lane A's
    # own parse, so a bare call of a bound name classifies as
    # `import-binding` rather than falling to `unclassified` (the
    # private-repo-A/qwen finding: that residue was almost entirely imports of
    # packages dependency_coverage already reported missing).
    py_bindings = {
        module.path: frozenset(
            bound
            for imp in parsed[module.id].imports
            if isinstance(imp, FromImport)
            for _, bound in imp.names
            if bound != "*"
        )
        for module in modules
    }
    # What each Python file's imports of the standard library bind
    # (ADR-164, C-181): a call rooted there that no provider placed is
    # `stdlib-import`, not a missing environment and not an untyped
    # receiver. A repo module's own top-level name is never the stdlib's.
    repo_roots = frozenset(module.id.split(".")[0] for module in modules)
    py_stdlib = {
        module.path: names
        for module in modules
        if (names := tail.stdlib_bindings(parsed[module.id].imports, repo_roots))
    }
    # Java's static imports bind a bare name the same way (`import static
    # a.b.C.m` binds `m`) — lane A's own parse, so `assertEquals(..)`
    # classifies as `import-binding`, never `unclassified` (ADR-096).
    if java:
        py_bindings.update(java.get("import_bindings", {}))
    # Sub-module bindings with enclosing-function extents (ADR-046):
    # Python's from its parse, Go's from its layer. TS needs none — its
    # checker origins already answer, one grade stronger.
    local_bindings: dict[str, tuple] = {
        module.path: tuple(
            (b.name, b.start, b.end) for b in parsed[module.id].local_bindings
        )
        for module in modules
        if parsed[module.id].local_bindings
    }
    if go:
        local_bindings.update(go.get("local_bindings", {}))
    if java:
        local_bindings.update(java.get("local_bindings", {}))
    if c:
        local_bindings.update(c.get("local_bindings", {}))
    if cpp:
        local_bindings.update(cpp.get("local_bindings", {}))
    # The files the C++ layer owns, which is the one thing an extension
    # cannot say: a `.h` it claimed is C++, not C (ADR-113 §1). The same
    # map stamps the coverage rows below.
    cpp_languages = {parsed.path: "cpp" for parsed in cpp["files"]} if cpp else {}
    # Java abstains on an overload set and C++ on an overload of its own
    # (a name with more than one definition at a fallback rank); the tail
    # names both the same way.
    overloads = (java.get("overload_sites") if java else set()) or set()
    if cpp:
        overloads = overloads | cpp["overload_sites"]
    # The tail reads a site with a fallback entry as `fallback` — lane A
    # answered. A withheld site's answer was not drawn, so the tail is given
    # the fallback without those files' keys and classes each one as a site
    # lane A had no guess for (ADR-113 §2). `ev.agreement` above still gets
    # the whole fallback, so the lane self-test compares both lanes wherever
    # both answered.
    tail_fallback = (
        {key: guess for key, guess in fallback.items() if key[0] not in withhold}
        if withhold
        else fallback
    )
    with timings.step("tail"):
      tails = tail.classify(
        # The whole fallback, not `tail_fallback`: ADR-143's match reads it
        # as the join does, and a site it matched is resolved rather than
        # classified at all. What the tail *classifies* a site as still
        # comes from `tail_fallback` below.
        ev.unresolved_sites(syntax, resolutions, external, fallback),
        repo_root,
        origins=origins,
        fallback=tail_fallback,
        import_bindings=py_bindings,
        local_bindings=local_bindings,
        overloads=overloads,
        inherited=java.get("inherited_sites") if java else None,
        build_tags=go.get("build_tag_sites") if go else None,
        qualified=cpp["qualified_sites"] if cpp else None,
        languages=cpp_languages,
        stdlib_bindings=py_stdlib,
    )
    # C-58's surfacing: sites the semantic lane resolved to a declaration
    # below the symbol floor still count as `resolved` (the number is not
    # moved — that concession stands), but the row now carries `floored`
    # and the tail names them `below-floor`, so per file the tail sums
    # to `unresolved + floored`.
    floored = Counter(file for file, _ in projected.get("below_floor", []))
    for file, n in floored.items():
        tails.setdefault(file, Counter())[tail.BELOW_FLOOR] += n
    # ADR-125's abstention, counted the same way: lane B answered at these
    # sites and the written specialisation contradicted it, so the site is
    # resolved, draws no edge, and the tail says which rule removed it.
    for file, n in Counter(
        file for file, _ in projected.get("qualifier_mismatch", [])
    ).items():
        tails.setdefault(file, Counter())[tail.QUALIFIER_MISMATCH] += n
    # ADR-130's abstention, beside it: lane B answered, and the call was
    # written with more arguments than that answer can take.
    for file, n in Counter(
        file for file, _ in projected.get("arity_mismatch", [])
    ).items():
        tails.setdefault(file, Counter())[tail.ARITY_MISMATCH] += n
    # ADR-163's refusal, beside them: a call written inside, or resolved
    # onto, a later def of a Rust id two impl headers share. A site lane B
    # resolved is added, as the two above are; a site only lane A had
    # answered was counted `fallback-resolved`, whose edge it no longer
    # has, so it moves to this class and the per-file sum is unchanged.
    for row in projected.get("shared_qualname", []):
        if row["kind"] != "calls":
            continue
        counts = tails.setdefault(row["path"], Counter())
        if not row["lane_b"] and counts.get(tail.FALLBACK, 0) > 0:
            counts[tail.FALLBACK] -= 1
            if not counts[tail.FALLBACK]:
                del counts[tail.FALLBACK]
        counts[tail.SHARED_QUALNAME] += 1
    if shared_later:
        degraded.append(_shared_qualname_record(shared_later, projected["shared_qualname"]))
    if rust and rust.get("cfg_twins"):
        degraded.append(_cfg_twin_record(rust["cfg_twins"], rust_compiled, rust_dead_refused))
    if rust and rust.get("same_header_repeats"):
        degraded.append(_rust_repeat_record(rust["same_header_repeats"]))
    if go_inits:
        degraded.append(_go_init_record(go_inits))
    if python_repeats:
        degraded.append(_python_repeats_record(python_repeats))
    macro_named = _cpp_macro_names(repo_root, graph["symbols"], graph["nodes"], cpp_languages)
    if macro_named:
        degraded.append(_cpp_macro_name_record(macro_named))
    graph["resolution_coverage"] = [
        {
            "file": row.file,
            # Only where the extension would say otherwise (C-32's note,
            # one language over): the tail and the proxy's copies of these
            # tables prefer a row's own language.
            **({"language": cpp_languages[row.file]} if row.file in cpp_languages else {}),
            "sites": row.sites,
            "resolved": row.resolved,
            "external": row.external,
            "unresolved": row.unresolved,
            **({"floored": floored[row.file]} if floored[row.file] else {}),
            **(
                {"tail": dict(sorted(tails[row.file].items()))}
                if row.file in tails
                else {}
            ),
        }
        for row in ev.coverage(syntax, resolutions, external, fallback)
    ]
    # Which tail classes each present language's providers could have
    # reported (C-32): stated beside the counts, so an absent class reads
    # as "not reportable here" when that is what it is.
    graph["tail_classes_available"] = tail.classes_available(
        graph["resolution_coverage"]
    )
    if go:
        degraded += _one_configuration_records(
            graph["resolution_coverage"], go.get("constrained_files", {})
        )
    return degraded


def _edge_order(edge: dict) -> tuple:
    """The projection's own sort key, ``(from, to, type, tier, lane)``
    (:func:`hobbes.extract.scipsource._edges`). Every edge it produces
    carries at least one piece of evidence and all of them share the edge's
    lane, so the lane is read off the first."""
    lane = edge["evidence"][0]["lane"] if edge["evidence"] else ""
    return (edge["from"], edge["to"], edge["type"], edge["tier"], lane)


def _add_injection_edges(graph: dict, drawn: list[dict]) -> None:
    """Draw each fixture injection whose ends the graph knows as one
    ``uses`` edge (ADR-137), evidence at every parameter that names it.

    An injection onto an id the symbol layer does not carry is dropped
    rather than drawn to nothing; the abstention is already counted where
    it was made. Each evidence row says which request it saw — a parameter,
    a ``usefixtures`` mark or an autouse fixture (ADR-139).
    """
    ids = {symbol["id"] for symbol in graph["symbols"]}
    sightings: dict[tuple[str, str], set] = defaultdict(set)
    for injection in drawn:
        if injection["from"] in ids and injection["to"] in ids:
            sightings[(injection["from"], injection["to"])].add(
                (injection["path"], injection["line"], injection["via"])
            )
    if not sightings:
        return
    graph["symbol_edges"] = sorted(
        graph["symbol_edges"]
        + [
            tiered_edge(
                source,
                target,
                "uses",
                [
                    {"path": path, "line": line, "via": via}
                    for path, line, via in sorted(evidence)
                ],
                tier=SYNTACTIC,
                lane=LANE_TREE_SITTER,
            )
            for (source, target), evidence in sorted(sightings.items())
        ],
        key=_edge_order,
    )


def _add_value_call_edges(graph: dict, drawn: list[dict]) -> None:
    """Draw each call on the value a fixture constructs as one ``calls``
    edge (ADR-145), evidence at every site that made it.

    The same shape as :func:`_add_injection_edges`: an end the symbol
    layer does not carry is dropped rather than drawn to nothing, the
    sightings merge per ``(from, to)``, and the list is re-sorted by the
    projection's own key. The tier is ``syntactic`` — the chain is read
    from the tree and from one semantic edge, which is not the same as
    the index having answered at the call.
    """
    ids = {symbol["id"] for symbol in graph["symbols"]}
    sightings: dict[tuple[str, str], set] = defaultdict(set)
    for call in drawn:
        if call["from"] in ids and call["to"] in ids:
            sightings[(call["from"], call["to"])].add((call["path"], call["line"]))
    if not sightings:
        return
    graph["symbol_edges"] = sorted(
        graph["symbol_edges"]
        + [
            tiered_edge(
                source,
                target,
                "calls",
                [
                    {"path": path, "line": line, "via": fixtures.FIXTURE_VALUE}
                    for path, line in sorted(evidence)
                ],
                tier=SYNTACTIC,
                lane=LANE_TREE_SITTER,
            )
            for (source, target), evidence in sorted(sightings.items())
        ],
        key=_edge_order,
    )


def _add_with_call_edges(graph: dict, drawn: list[dict], via: str = withstmt.WITH) -> None:
    """Draw each ``__enter__`` / ``__exit__`` a ``with`` item's known class
    runs as one ``calls`` edge (ADR-156), evidence at every item that made
    it.

    The same shape as :func:`_add_value_call_edges`: an end the graph does
    not carry is dropped rather than drawn to nothing, the sightings merge
    per ``(from, to)``, and the list is re-sorted by the projection's own
    key. As at :func:`_add_factory_call_edges`, the caller may be the
    **module** — a module-level ``with`` runs at import, and the projection
    draws a module-body call from the module node (ADR-007). The tier is
    ``syntactic``: the index answered at the item's call, not at the
    methods, where it answered nothing. ADR-171 draws an instance's
    ``__call__`` through it with its own *via*, for the same reasons.
    """
    ids = {symbol["id"] for symbol in graph["symbols"]}
    callers = ids | {node["id"] for node in graph["nodes"]}
    sightings: dict[tuple[str, str], set] = defaultdict(set)
    for call in drawn:
        if call["from"] in callers and call["to"] in ids:
            sightings[(call["from"], call["to"])].add((call["path"], call["line"]))
    if not sightings:
        return
    graph["symbol_edges"] = sorted(
        graph["symbol_edges"]
        + [
            tiered_edge(
                source,
                target,
                "calls",
                [
                    {"path": path, "line": line, "via": via}
                    for path, line in sorted(evidence)
                ],
                tier=SYNTACTIC,
                lane=LANE_TREE_SITTER,
            )
            for (source, target), evidence in sorted(sightings.items())
        ],
        key=_edge_order,
    )


def _add_alias_call_edges(graph: dict, drawn: list[dict], via: str = aliases.ALIAS) -> None:
    """Draw each call through a local alias as one ``calls`` edge
    (ADR-160), evidence at every site that made it.

    The same shape as :func:`_add_with_call_edges`: an end the graph does
    not carry is dropped rather than drawn to nothing, the sightings merge
    per ``(from, to)``, and the list is re-sorted by the projection's own
    key. The caller is always a function or method — a module body records
    no alias — and the target is whatever the index named at the alias's
    right-hand side. The tier is ``syntactic``: the binding is read from
    syntax, and the index answered at the assignment, not at the call.
    """
    ids = {symbol["id"] for symbol in graph["symbols"]}
    sightings: dict[tuple[str, str], set] = defaultdict(set)
    for call in drawn:
        if call["from"] in ids and call["to"] in ids:
            sightings[(call["from"], call["to"])].add((call["path"], call["line"]))
    if not sightings:
        return
    graph["symbol_edges"] = sorted(
        graph["symbol_edges"]
        + [
            tiered_edge(
                source,
                target,
                "calls",
                [
                    {"path": path, "line": line, "via": via}
                    for path, line in sorted(evidence)
                ],
                tier=SYNTACTIC,
                lane=LANE_TREE_SITTER,
            )
            for (source, target), evidence in sorted(sightings.items())
        ],
        key=_edge_order,
    )


def _add_factory_call_edges(graph: dict, drawn: list[dict]) -> None:
    """Draw each decorator-factory application as one ``calls`` edge
    (ADR-147, ADR-148, ADR-149), evidence at every decorator that made
    it.

    Each evidence row carries the ``via`` of the row that drew it, so a
    pair reached by more than one reading — one site ADR-147 settles,
    another ADR-148 folds, a third ADR-149 reaches through a second
    factory's call — says at which line it was which.

    The same shape as :func:`_add_value_call_edges`, but for the caller: a
    target the symbol layer does not carry is dropped rather than drawn to
    nothing, the sightings merge per ``(from, to)``, and the list is
    re-sorted by the projection's own key. The tier is ``syntactic`` — the chain is read
    from the tree and from one semantic edge, which is not the same as the
    index having answered at the application, where it answered nothing.
    """
    ids = {symbol["id"] for symbol in graph["symbols"]}
    # Unlike a fixture's requester, a decorator's caller is often the
    # **module** — `@factory("a")` at the top level runs at import — and
    # the projection draws a module-body call from the module node
    # (ADR-007). The caller here is the `from` of an edge the graph
    # already carries, so a node id is as good an end as a symbol's;
    # dropping it left the block counting rows the graph did not hold.
    callers = ids | {node["id"] for node in graph["nodes"]}
    sightings: dict[tuple[str, str], set] = defaultdict(set)
    for call in drawn:
        if call["from"] in callers and call["to"] in ids:
            sightings[(call["from"], call["to"])].add(
                (call["path"], call["line"], call["via"])
            )
    if not sightings:
        return
    graph["symbol_edges"] = sorted(
        graph["symbol_edges"]
        + [
            tiered_edge(
                source,
                target,
                "calls",
                [
                    {"path": path, "line": line, "via": via}
                    for path, line, via in sorted(evidence)
                ],
                tier=SYNTACTIC,
                lane=LANE_TREE_SITTER,
            )
            for (source, target), evidence in sorted(sightings.items())
        ],
        key=_edge_order,
    )


def _cpp_fallback_records(lane_agreement: dict) -> list[dict]:
    """C-152's surfacing: the lane A guesses the join withheld (ADR-113 §2).

    Read off the count :func:`_lane_agreement` already holds, so the record
    and the report can never say two different numbers. Silent when nothing
    was withheld — which is every repo without C++, and every C++ repo lane
    B could not index.
    """
    withheld = lane_agreement["cpp_withheld"]["sites"]
    if not withheld:
        return []
    return [
        {
            "path": ".",
            "stage": "cpp-fallback",
            "message": (
                f"{withheld} lane A guess(es) withheld in C++ files scip-clang "
                "indexed, where lane B answered nothing at the site: those sites "
                "stay unresolved rather than drawn by name (ADR-113 §2, C-152)"
            ),
        }
    ]


def _cpp_template_pattern_records(graph: dict, cpp: dict | None) -> list[dict]:
    """C-153's surfacing (ADR-125 §4): the region, not the wrong edges.

    scip-clang indexes a template's pattern once, so its one answer at a
    call written inside one can name another specialisation's declaration.
    R-qual (ADR-125's decision rule) withholds the answers the source text
    contradicts; what is left cannot be told from a right edge at the site,
    so the honest response is to say where the edge comes from. This writes
    the callers a reader meets that in — ``graph["cpp_template_patterns"]``,
    which ``who_calls`` marks its lines from — and one record so
    ``list_blind_spots`` names the region too.

    Only the patterns that actually *call* something semantically are
    listed: a pattern with no such edge out of it is a region no answer is
    drawn from, and listing it would grow the artifact for nothing. The key
    is written whenever the C++ layer ran, so an empty list reads as "asked
    and none" rather than as an older artifact.
    """
    if cpp is None:
        return []
    patterns = cpp["template_patterns"]
    marked = [
        edge
        for edge in graph["symbol_edges"]
        if edge["type"] == "calls"
        and edge["tier"] == SEMANTIC
        and edge["from"] in patterns
    ]
    graph["cpp_template_patterns"] = sorted({edge["from"] for edge in marked})
    if not marked:
        return []
    return [
        {
            "path": ".",
            "stage": "cpp-template-sites",
            "message": (
                f"{len(marked)} semantic C++ call edge(s) start in a template "
                "pattern (a function template, or a member of a class template "
                "or partial specialisation): scip-clang indexes a pattern once, "
                "and its one answer there can name another specialisation's "
                "declaration (C-153); who_calls marks each"
            ),
        }
    ]


def _one_configuration_records(
    coverage_rows: list[dict], constrained_files: dict[str, str]
) -> list[dict]:
    """C-71's surfacing: the Go index is one configuration's.

    scip-go loads the module for the box it runs on (the image: linux,
    its pinned Go), so a file whose build constraint excludes it from
    that configuration gets no semantic occurrence at all and its sites
    fall to lane A's fallback — which the per-file row shows as
    ``resolved 0`` without saying why. This names the files, per
    package directory, and only when lane B answered *somewhere* in the
    Go zone (otherwise the index did not run and C-8 is the record).
    A constrained file that lane B did resolve is simply in the
    configuration, and is not listed.
    """
    go_rows = [r for r in coverage_rows if r["file"].endswith(".go")]
    if not any(r["resolved"] or r["external"] for r in go_rows):
        return []
    dark: dict[str, list[str]] = defaultdict(list)
    for row in go_rows:
        if (
            row["file"] in constrained_files
            and row["sites"]
            and not row["resolved"]
            and not row["external"]
        ):
            directory = str(PurePosixPath(row["file"]).parent)
            dark[directory if directory not in ("", ".") else "."].append(row["file"])
    out = []
    for directory, files in sorted(dark.items()):
        names = ", ".join(sorted(PurePosixPath(f).name for f in files))
        out.append(
            {
                "path": directory,
                "stage": "scip-go",
                "message": (
                    f"{len(files)} file(s) under a build constraint got no "
                    f"semantic resolution ({names}) — the index is one "
                    "configuration's (the box it ran on), so their call "
                    "edges are lane A's fallback or absent (C-71)."
                ),
            }
        )
    return out


#: Node id prefixes only lane A can produce — third-party packages,
#: environment variables, and the Terraform layer. Lane B never sees them,
#: so their absence from its edge set is not a disagreement.
_LANE_A_ONLY = ("ext:", "env:", "tf:")


def _lane_agreement(
    syntax,
    resolutions,
    fallback,
    lane_a_edges,
    lane_b_edges,
    lane_b_only_modules: set[str] | None = None,
    external: list[dict] | None = None,
    withhold: frozenset[str] = frozenset(),
    cpp_site_files: set[str] | None = None,
    twins: dict[str, dict[str, list[tuple[int, int]]]] | None = None,
) -> dict:
    """The §3.4 self-test: where both lanes can answer, they must agree.

    Two comparisons, because the lanes overlap in two places. Call sites
    both resolved (the sharp one, ADR-029) and module-level import edges
    both could produce. Only edges between two repo modules are compared —
    ``ext:``/``env:``/``tf:`` nodes are lane A's alone, and counting them
    would report hundreds of false disagreements and bury the real ones.

    *lane_b_only_modules* is the mirror of that exclusion, added for Go
    (V2.M5): a Go import names a *package*, so lane A cannot emit an
    in-repo import edge without guessing which of the package's files is
    meant, and deliberately emits none (`gosource`). Every such edge would
    otherwise land in "lane B only" — 91 of them on this repo — and a
    report whose noise floor is that high stops being read. Excluded by
    construction, and **counted**, because an exclusion nobody can see is
    how a self-test quietly stops testing.

    *lane_b_edges* is the join's projection, which raises module edges
    from lane A's own fallback too (a syntactic edge is still an edge).
    Only the edges with semantic evidence are lane B's here (C-75): on
    date-fns every one of 200 "lane B only" edges was tree-sitter's, and
    the comparison was reporting lane A's agreement with lane A. The
    count lane B actually produced is returned beside the comparison so
    a thin lane B reads as thin.

    *external* is lane B's external references, passed through to
    :func:`~hobbes.extract.evidence.external_vetoes` (ADR-111): the sites
    where the join dropped lane A's fallback because lane B placed the
    site outside the repo. Not a disagreement — the graph already took
    lane B's answer there — so it does not affect ``sites_compared`` or
    change ``hobbes lanes``' exit status; it is where a user meets the
    sites lane A would have drawn wrong.

    *withhold* is the same thing one rule over (ADR-113 §2): the C++ files
    lane B compiled, where a site it answered nothing at draws no fallback
    edge either. Reported the same way and for the same reason, and
    ``sites_compared`` is untouched by it — the comparison is fed the whole
    fallback, so wherever both lanes answered the self-test is unchanged.

    *cpp_site_files* is every file the C++ layer saw a call site in, which
    is what ADR-123 §3 needs beside the C++ rows: the denominator they are
    a share of (``cpp_sites_compared``), and the guesses of the same kind
    that *are* drawn — the ones in the C++ files lane B did not index
    (``cpp_guess_drawn``, C-135's C++ face). Neither moves
    ``sites_compared``, the rows, or their order.

    *twins* is lane A's Rust cfg twins (ADR-165), read only to shape a
    row whose two answers are two arms of one node (``cfg-twin``, C-182).
    """

    def by_site(pair):
        return (pair[0].file, pair[0].line, pair[0].name)

    compared, disagreements = ev.agreement(syntax, resolutions, fallback)
    # ADR-123 §1: a rule the report can check, per row and in the rows'
    # order, so a registered limit's disagreement is named rather than
    # triaged away.
    shapes = ev.disagreement_shapes(
        syntax, resolutions, fallback, disagreements, withhold, twins
    )
    cpp_compared, cpp_guess_drawn = _cpp_site_counts(
        syntax, resolutions, fallback, withhold, cpp_site_files or set(), external
    )
    vetoes = sorted(
        ev.external_vetoes(syntax, resolutions, fallback, external), key=by_site
    )
    withheld = sorted(
        ev.withheld_fallbacks(syntax, resolutions, fallback, external, withhold),
        key=by_site,
    )
    lane_b_only_modules = lane_b_only_modules or set()
    lane_b_edges = [
        e
        for e in lane_b_edges
        if e["type"] == "imports"
        and any(s["lane"] == LANE_SCIP for s in e["evidence"])
    ]

    def repo_imports(edges):
        return {
            (e["from"], e["to"])
            for e in edges
            if e["type"] == "imports"
            and not e["from"].startswith(_LANE_A_ONLY)
            and not e["to"].startswith(_LANE_A_ONLY)
            and not (
                e["from"] in lane_b_only_modules and e["to"] in lane_b_only_modules
            )
        }

    a, b = repo_imports(lane_a_edges), repo_imports(lane_b_edges)
    return {
        "sites_compared": compared,
        "site_disagreements": [
            {
                "file": d.file,
                "line": d.line,
                "name": d.name,
                "syntactic": f"{d.syntactic_file}:{d.syntactic_line}",
                "semantic": f"{d.semantic_file}:{d.semantic_line}",
                # The registered limit that explains this row, or None
                # (ADR-123). Nothing is removed by it.
                "shape": shape,
            }
            for d, shape in zip(disagreements, shapes)
        ],
        # Only meaningful when lane B ran at all; an empty lane B would
        # otherwise report every module edge as "lane A only".
        "module_edges_compared": len(a | b) if b else 0,
        # Import edges carrying semantic evidence — the count lane B
        # produced, before the repo-only filter (C-75).
        "module_edges_lane_b_produced": len(lane_b_edges),
        # Edges left out because only one lane can produce them at all.
        # Reported so the denominator is never quietly smaller than it
        # looks — the ADR-029 coverage habit, applied to this report.
        "module_edges_excluded_lane_b_only": sum(
            1
            for e in lane_b_edges
            if e["type"] == "imports"
            and e["from"] in lane_b_only_modules
            and e["to"] in lane_b_only_modules
        ),
        "module_edges_lane_a_only": (
            [{"from": f, "to": t} for f, t in sorted(a - b)] if b else []
        ),
        "module_edges_lane_b_only": [
            {"from": f, "to": t} for f, t in sorted(b - a)
        ],
        "external_vetoes": _withheld_report(vetoes),
        # The same shape, one rule over (ADR-113 §2, C-152): the C++ files
        # lane B compiled and said nothing in.
        "cpp_withheld": _withheld_report(withheld),
        # The C++ rows' denominator and their drawn counterpart (ADR-123
        # §3): the C++ call sites both lanes answered, and the guesses of
        # the same kind lane A does draw, where lane B never compiled.
        "cpp_sites_compared": cpp_compared,
        "cpp_disagreements": sum(
            1 for d in disagreements if d.file in (cpp_site_files or set())
        ),
        "cpp_guess_drawn": cpp_guess_drawn,
    }


def _cpp_site_counts(
    syntax,
    resolutions,
    fallback,
    withhold: frozenset[str],
    cpp_site_files: set[str],
    external: list[dict] | None = None,
) -> tuple[int, int]:
    """``(C++ sites compared, C++ guesses drawn)`` for ADR-123 §3.

    The first is :func:`~hobbes.extract.evidence.agreement`'s own predicate
    restricted to the C++ layer's files — the denominator the withheld rows
    are a share of. The second is the guess the join *does* draw: a C++ call
    site lane B never compiled (so not in *withhold*), with no in-repo
    resolution and a fallback answer, drawn at syntactic tier (C-135's C++
    face). A site the external veto dropped (ADR-111) draws nothing and is
    not counted. Zero when the C++ layer did not run.
    """
    if not cpp_site_files:
        return 0, 0
    buckets = ev.index_resolutions(resolutions)
    vetoed = ev._veto_set(external)
    compared = drawn = 0
    for site in syntax:
        if site.kind != ev.CALL_SITE or site.ambiguous:
            continue
        if site.file not in cpp_site_files:
            continue
        if fallback.get((site.file, site.line, site.name)) is None:
            continue
        if (
            ev.match_resolution(site, buckets) is not None
            # The join's second reading (ADR-143): a site it matched there
            # is compared, never drawn from lane A's guess alone.
            or ev.match_at_own_column(site, buckets, fallback) is not None
        ):
            compared += 1
        elif (
            site.file not in withhold
            and (site.file, site.line, site.name) not in vetoed
        ):
            drawn += 1
    return compared, drawn


def _withheld_report(pairs: list[tuple]) -> dict:
    """A count of dropped fallbacks with up to ten of them named — the one
    shape both drop rules report in, so a reader compares them directly."""
    return {
        "sites": len(pairs),
        "examples": [
            {
                "file": site.file,
                "line": site.line,
                "name": site.name,
                "lane_a": f"{guess[0]}:{guess[1]}",
            }
            for site, guess in pairs[:10]
        ],
    }


def _lane_b_facts(
    repo_root: Path,
    modules,
    ts: dict | None,
    go: dict | None,
    rust: dict | None,
    java: dict | None,
    c: dict | None,
    cpp: dict | None,
    degraded: list[dict],
    timings: Timings | None = None,
):
    """Every semantic provider's facts, skipping the ones that cannot run."""
    if not scipsource.enabled():
        return
    timings = timings if timings is not None else Timings()
    runs = []
    if modules:
        files = sorted({m.path for m in modules})
        roots = sorted({m.root for m in modules})
        runs.append(
            (
                "python",
                lambda: scipsource.extract_scip(
                    repo_root,
                    files,
                    roots,
                    project_name=repo_root.name,
                    sha="",
                    declared_deps=scipsource.declared_dependencies(repo_root),
                ),
            )
        )
    if ts:
        ts_files = sorted({f["path"] for f in ts["files"]})
        runs.append(
            ("typescript", lambda: scipsource.extract_scip_typescript(repo_root, ts_files))
        )
    if go:
        go_files = sorted({f.path for f in go["files"]})
        runs.append(("go", lambda: scipsource.extract_scip_go(repo_root, go_files)))
    if rust:
        rust_files = sorted({f.path for f in rust["files"]})
        runs.append(("rust", lambda: scipsource.extract_scip_rust(repo_root, rust_files)))
    if java:
        java_files = sorted({f.path for f in java["files"]})
        runs.append(("java", lambda: scipsource.extract_scip_java(repo_root, java_files)))
    if c or cpp:
        # One run for both languages (ADR-113 §2): scip-clang indexes
        # whatever the compile database names, so a build root holding C
        # and C++ must be one index, not two over overlapping trees. The
        # run is named for what the repo actually holds — `cpp` only when
        # there is no C at all, since C's records are the ones a mixed
        # repo reads.
        cpp_files = sorted({f.path for f in cpp["files"]}) if cpp else []
        c_files = sorted({f.path for f in c["files"]}) if c else []
        both = sorted(set(c_files) | set(cpp_files))
        runs.append(
            (
                "c" if c_files else "cpp",
                lambda: scipsource.extract_scip_c(repo_root, both, cpp_files=cpp_files),
            )
        )

    for language, run in runs:
        try:
            with timings.step(f"lane B [{language}]"):
                facts = run()
        except containment.ContainmentRefusal as exc:
            # P10 (ADR-036, ADR-092): the general catch below is a policy
            # about the unknown failure; this is the known one. Named and
            # handled first, so the guarantee — repo code never executes
            # on the host — is recorded as a refusal, never absorbed into
            # "lane B did not run" or retried outside the container.
            degraded.append(
                {
                    "path": ".",
                    "stage": f"scip-{language}",
                    "message": (
                        f"lane B refused for {language}: {exc} — semantics for "
                        f"{language} fall to lane A's syntactic floor (C-64)"
                    ),
                }
            )
            continue
        except (scipsource.ScipError, staging.StagingError, OSError) as exc:
            degraded.append(
                {
                    "path": ".",
                    "stage": f"scip-{language}",
                    "message": f"lane B did not run for {language}: {exc}",
                }
            )
            continue
        if facts is not None:
            degraded.extend(_coverage_gap_records(language, facts))
            yield facts


def _coverage_gap_records(language: str, facts: dict) -> list[dict]:
    """A record when the environment check ran against nothing (C-79).

    ``dependency_coverage`` is appended to the graph only when a manifest
    declared something; a Python repo declaring its dependencies in
    ``setup.py`` alone (peft, 2026-09-02) therefore had no key, no message
    and no environment line in ``list_blind_spots`` — an absence, where
    the module's own rule is that an inert check that appears to run is
    worse than no check. Python only: the TS helper reads ``package.json``
    per zone and a zone without one is C-23's shape, already recorded.
    """
    if language != "python":
        return []
    coverage = facts.get("dependency_coverage") or {}
    if coverage.get("declared"):
        return []
    return [
        {
            "path": ".",
            "stage": "scip-python",
            "message": (
                "no manifest declares Python dependencies (pyproject.toml "
                "[project] / [dependency-groups] / [tool.poetry] / [tool.pdm] "
                "/ [tool.uv], setup.cfg [options], requirements*.txt are "
                "read; setup.py is code and is not; a lock file is the "
                "resolver's closure and is not) — the environment coverage "
                "check had nothing to compare against, so a thin graph here "
                "has no environment number to rank on (C-79)"
            ),
        }
    ]


def _merge_module_edges(lane_a: list[dict], lane_b: list[dict]) -> list[dict]:
    """Keep lane A's module edges, upgrading the ones lane B also proved.

    Lane A's import statements are syntactic facts about the source — an
    ``import x`` really is an import — and they reach ``ext:``/``env:``
    nodes lane B cannot see. So lane A stays the spine here and lane B
    raises the tier where it agrees.
    """
    by_key = {(e["from"], e["to"], e["type"]): e for e in lane_a}
    for edge in lane_b:
        key = (edge["from"], edge["to"], edge["type"])
        prior = by_key.get(key)
        if prior is None:
            by_key[key] = edge
            continue
        seen = {(s["path"], s["line"], s["lane"]) for s in edge["evidence"]}
        merged = dict(edge)
        merged["evidence"] = edge["evidence"] + [
            s for s in prior["evidence"]
            if (s["path"], s["line"], s["lane"]) not in seen
        ]
        by_key[key] = merged
    return sorted(by_key.values(), key=lambda e: (e["from"], e["to"], e["type"]))


def _merge_layer(
    graph: dict, nodes: list[dict], module_edges: list[dict]
) -> list[dict]:
    """Merge another language layer's nodes and module edges into *graph*.

    Each language owns its own files (discovery is by extension, so no
    parser ever sees another's source) and its facts are merged, never
    re-derived — a second parse can't contradict the first because it
    never happens.

    Node ids can still collide *across* layers, though: a repo-root
    ``widget.py`` and ``widget.ts`` both want the id ``widget``. The
    first layer keeps it, and the loser is **reported**, not dropped in
    silence — resolution by pipeline order is an accident, and an
    accident that is invisible is a lie about the graph (P1). Returns
    one degradation record per collision.
    """
    merged = {n["id"]: n for n in graph["nodes"]}
    collisions = []
    for node in nodes:
        existing = merged.get(node["id"])
        if existing is None:
            merged[node["id"]] = node
            continue
        if existing.get("path") != node.get("path"):
            collisions.append(
                {
                    "path": node.get("path", node["id"]),
                    "stage": "layer-merge",
                    "message": (
                        f"module id {node['id']!r} is already held by "
                        f"{existing.get('path')!r}; this file is omitted from the "
                        "graph. Rename one of them, or move it out of the repo root."
                    ),
                }
            )
    graph["nodes"] = sorted(merged.values(), key=lambda n: n["id"])
    graph["module_edges"] = sorted(
        graph["module_edges"] + module_edges,
        key=lambda e: (e["from"], e["to"], e["type"]),
    )
    return collisions


def _merge_symbols(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Merge a layer's symbols, keeping ids unique.

    A colliding module id drags its symbols with it; emitting both would
    put two rows under one id in the artifact and leave one of them
    pointing at a module the node list does not contain.
    """
    merged = {s["id"]: s for s in existing}
    for symbol in incoming:
        merged.setdefault(symbol["id"], symbol)
    return sorted(merged.values(), key=lambda s: s["id"])


def built_by() -> dict:
    """The provenance of the running pipeline code: its version (ADR-103),
    the checkout that holds this package and its git commit, or ``""``
    when the package is not inside a git checkout (an installed wheel)."""
    from hobbes import __version__
    package = Path(__file__).resolve().parent.parent  # .../src/hobbes

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(package), *args], capture_output=True,
                              text=True, check=True, timeout=10).stdout.strip()

    try:
        root, sha = git("rev-parse", "--show-toplevel"), git("rev-parse", "HEAD")
        dirty = bool(git("status", "--porcelain", "--", str(package)))
    except (subprocess.SubprocessError, OSError):
        return {"version": __version__, "checkout": str(package), "sha": "", "dirty": False}
    return {"version": __version__, "checkout": root, "sha": sha, "dirty": dirty}


def ingest(
    repo_root: Path, tf_plan: Path | None = None, timings: Timings | None = None
) -> list[Path]:
    """Extract *repo_root*, stamp with its git SHA, write the artifacts.

    Returns the written paths (``.hobbes/derived/{graph,tests,interfaces}.json``).
    Requires *repo_root* to be a git repo with at least one commit — the SHA
    is the provenance every downstream claim pins to (P3). Always ensures
    git ignores Hobbes files first (ADR-012); in a git repo the line goes
    in the clone's ``info/exclude``, so the ingest leaves the tree and the
    stamp's ``dirty`` flag as it found them. An ingest of a repo
    whose ingest is already running raises
    :class:`~hobbes.extract.ingestlock.IngestBusy` before anything is
    staged, indexed or written (ADR-127).
    """
    repo_root = Path(repo_root).resolve()
    with ingestlock.hold(repo_root):
        ensure_hobbes_ignored(repo_root)
        timings = timings if timings is not None else Timings()
        extraction = extract_repo(repo_root, tf_plan=tf_plan, timings=timings)
        stamp = {"schema_version": SCHEMA_VERSION, **repo_stamp(repo_root)}
        with timings.step("write"):
            return write_artifacts(
                repo_root,
                {
                    "graph.json": {**stamp, **extraction.graph},
                    "tests.json": {**stamp, **extraction.tests},
                    "interfaces.json": {**stamp, **extraction.interfaces},
                },
            )
