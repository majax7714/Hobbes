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

import subprocess

from collections import Counter, defaultdict

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from hobbes.extract import evidence as ev
from hobbes.extract import (
    containment,
    indexcache,
    ingestlock,
    scipsource,
    staging,
    tail,
    tssource,
)
from hobbes.extract.cppsource import collect_cpp_tests, extract_cpp
from hobbes.extract.csource import collect_c_tests, extract_c
from hobbes.extract.discover import discover_modules, linked_copies
from hobbes.extract.emit import ensure_hobbes_ignored, repo_stamp, write_artifacts
from hobbes.extract.gosource import collect_go_tests, extract_go
from hobbes.extract.javasource import collect_java_tests, extract_java
from hobbes.extract.graph import build_graph, resolve_call_sites
from hobbes.extract.packs import REGISTRY as PACK_REGISTRY
from hobbes.extract.packs import Pack, PackContext, run_packs
from hobbes.extract.pysource import FromImport, parse_source
from hobbes.extract.rustsource import collect_rust_tests, extract_rust
from hobbes.extract.schema import LANE_SCIP, SEMANTIC
from hobbes.extract.testmap import collect_tests, runner_excluded_trees
from hobbes.extract.timings import Timings
from hobbes.extract.tssource import collect_ts_tests, extract_ts
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
    # Every step below is timed (ADR-119); the record never enters an
    # artifact, and a caller that passes none gets one that is dropped.
    timings = timings if timings is not None else Timings()
    repo_root = Path(repo_root).resolve()
    with timings.step("discover [python]"):
        modules = discover_modules(repo_root)
    with timings.step("parse [python]"):
        parsed = {
            m.id: parse_source((repo_root / m.path).read_bytes()) for m in modules
        }
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
        c = extract_c(repo_root, claimed=cpp["claimed_headers"] if cpp else None)
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

    degraded += _build_symbol_layer(
        repo_root, graph, modules, parsed, ts, go, rust, java, c, cpp, timings=timings
    )

    timings_tests = timings.step("tests")
    timings_tests.__enter__()
    tests = collect_tests(modules, parsed, graph["symbol_edges"])
    if ts:
        tests += collect_ts_tests(ts["files"], ts["symbols"], graph["symbol_edges"])
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
    """Lane A's call sites, in evidence-IR shape (ADR-029)."""
    return [
        ev.Site(
            provider=ev.TREE_SITTER,
            kind=ev.CALL_SITE,
            file=module.path,
            line=call.line,
            name=call.callee.split(".")[-1],
            col=call.col,
            scope=f"{module.id}.{call.scope}" if call.scope else module.id,
        )
        for module in modules
        for call in parsed[module.id].calls
    ]


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
) -> list[dict]:
    """Join every lane's evidence and project it onto the graph's ids.

    **The only producer of symbol edges** (ADR-031), and it runs whether or
    not lane B does: with no semantic resolutions every call site falls to
    the fallback arm and the graph is lane A's, at ``syntactic`` tier. That
    is P6 satisfied by construction rather than by a second code path — the
    degraded case is the normal case with an empty input.

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

    withhold = frozenset(cpp_withheld_files)
    with timings.step("join"):
        resolved = ev.join(
            syntax, resolutions, fallback=fallback, external=external, withhold=withhold
        )
    with timings.step("project"):
        projected = scipsource.project(
            resolved,
            graph["nodes"],
            graph["symbols"],
            # ADR-125: the classes C++ declares `template <>`, the one
            # owner shape whose arguments are concrete enough for a
            # written qualifier to contradict. No C++ layer, no rule.
            full_specializations=cpp["full_specializations"] if cpp else frozenset(),
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
    )
    degraded += _cpp_fallback_records(graph["lane_agreement"])
    graph["symbol_edges"] = projected["symbol_edges"]
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
        ev.unresolved_sites(syntax, resolutions, external),
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
        for row in ev.coverage(syntax, resolutions, external)
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
    """

    def by_site(pair):
        return (pair[0].file, pair[0].line, pair[0].name)

    compared, disagreements = ev.agreement(syntax, resolutions, fallback)
    # ADR-123 §1: a rule the report can check, per row and in the rows'
    # order, so a registered limit's disagreement is named rather than
    # triaged away.
    shapes = ev.disagreement_shapes(
        syntax, resolutions, fallback, disagreements, withhold
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
        if ev.match_resolution(site, buckets) is not None:
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
    the repo gitignores Hobbes files first (ADR-012), so the stamp's
    ``dirty`` flag reflects that edit when it happens. An ingest of a repo
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
