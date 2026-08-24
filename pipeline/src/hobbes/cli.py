"""The ``hobbes`` command-line interface.

``ingest`` runs the deterministic extractors into ``.hobbes/derived/``;
``init`` scaffolds the ``.hobbes/`` layout; ``render`` prints the module
graph as Mermaid (ADR-008); ``diff <base>..<head>`` prints the
architecture delta between two refs (ADR-009 — exit 0 no delta / 1
delta / 2 trouble, mirroring diff(1)); ``narrate`` runs the
quota-spending cartographer pass into ``.hobbes/derived/docs/``
(ADR-019/020); ``docs status`` prints stale badges; ``policy resolve``
passes through to the Go ``hobbes-policy`` binary (ADR-003). argparse
per ADR-004.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hobbes import __version__, artifacts, policy

#: Starter repo policy written by `hobbes init` (format per ADR-001).
_STARTER_POLICY = """\
# Repo policy for this repository — see hobbes docs/adr/001 for the format,
# 002 for merge semantics (box -> repo -> folder, deny overrides allow).
version: 1
scope: repo
default: escalate
rules:
  # Terraform state carries secrets: never read, written, or shipped.
  - pattern: "*.tfstate*"
    decision: deny
    reason: "tfstate carries secrets"
"""

#: Lines `hobbes init` guarantees are present in the repo's .gitignore,
#: in addition to the .hobbes/ protection from ADR-012.
_GITIGNORE_LINES = ["*.tfstate", "*.tfstate.*"]


def _detect_repo_root(start: Path) -> Path | None:
    """Walk up from *start* looking for a .git entry (mirrors ADR-003)."""
    current = start.resolve()
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            return None
        current = current.parent


def _repo_root_from(args: argparse.Namespace) -> Path:
    if args.repo:
        return Path(args.repo).resolve()
    detected = _detect_repo_root(Path.cwd())
    if detected is None:
        raise SystemExit(
            "hobbes: no repo root found (no .git upward from here); pass --repo"
        )
    return detected


def _cmd_ingest(args: argparse.Namespace) -> int:
    """Run the extractors and write the derived artifacts."""
    from hobbes.extract import ingest
    from hobbes.extract.emit import StampError
    from hobbes.extract.packs import PackRefusal
    from hobbes.extract.terraform import PlanError

    from hobbes.extract.emit import ensure_hobbes_ignored

    repo_root = _repo_root_from(args)
    ignored = ensure_hobbes_ignored(repo_root)
    if ignored:
        print(f"{ignored} (Hobbes files stay out of version control, ADR-012)")
    try:
        paths = ingest(repo_root, tf_plan=Path(args.tf_plan) if args.tf_plan else None)
    # PackRefusal is how a pack declines user-supplied input (ADR-035); it
    # reaches here rather than degrading, so `--tf-plan some.tfstate` still
    # exits 1 rather than warning and ingesting (I-1).
    except (StampError, PlanError, PackRefusal) as exc:
        print(f"hobbes ingest: {exc}", file=sys.stderr)
        return 1
    docs = {p.name: json.loads(p.read_text()) for p in paths}
    graph, tests, interfaces = (
        docs["graph.json"],
        docs["tests.json"],
        docs["interfaces.json"],
    )
    dirty = " (dirty tree)" if graph["dirty"] else ""
    languages = ", ".join(graph["languages"])
    print(f"ingested {repo_root} @ {graph['sha'][:12]}{dirty} [{languages}]")
    _print_verification_base(graph.get("verification_base", {}))
    for degraded in graph.get("extraction_errors", []):
        print(
            f"  WARNING: {degraded['path']}: {degraded['stage']} extraction "
            f"degraded ({degraded['message']})",
            file=sys.stderr,
        )
    print(
        f"  graph.json:      {len(graph['nodes'])} nodes, "
        f"{len(graph['module_edges'])} module edges, "
        f"{len(graph['symbols'])} symbols, "
        f"{len(graph['symbol_edges'])} call edges"
    )
    print(f"  tests.json:      {len(tests['tests'])} tests")
    print(
        f"  interfaces.json: {len(interfaces['routes'])} routes, "
        f"{len(interfaces['cli_entry_points'])} CLI entry points"
    )
    _print_tail_view(
        graph.get("resolution_coverage", []),
        graph.get("tail_classes_available", {}),
    )
    for path in sorted(paths):
        print(f"  wrote {path}")
    return 0


def _print_verification_base(base: dict[str, dict]) -> None:
    """The verification-depth line (C-31): how many repos each detected
    language's accuracy was measured on, printed directly under the
    language list so it cannot be read as a capability list. The
    single-repo and unverified rows are spelled out — those are the
    ones a reader would otherwise assume are peers of the rest."""
    if not base:
        return
    from hobbes.extract.verification import summary_line

    print(
        f"  verification base: {summary_line(base)} — a sample, not the "
        f"language (C-31, architecture §3.8)"
    )
    for lang, row in base.items():
        if row["repos"] <= 1:
            print(f"    {lang}: {row['note']}")


def _print_tail_view(
    coverage_rows: list[dict], classes_available: dict[str, list[str]] | None = None
) -> None:
    """The per-language capture line (ADR-045): accounted share of the
    *detected* call sites — always stated with that denominator — and
    the unresolved tail split into what the graph sees and does not
    model versus what it cannot resolve. This is the honesty line: it
    runs on every ingest, not only during development. When the artifact
    carries ``tail_classes_available`` (C-32), each language's line also
    names the classes its providers could not have reported, so a
    missing class reads as a boundary rather than an absence."""
    from hobbes.extract.tail import ALL_CLASSES, NOT_MODELLED, rollup

    classes_available = classes_available or {}
    for lang, agg in sorted(rollup(coverage_rows).items()):
        sites, unresolved = agg["sites"], agg["unresolved"]
        if not sites:
            continue
        accounted = (sites - unresolved) / sites * 100
        not_modelled = {
            c: n for c, n in agg["tail"].items() if c in NOT_MODELLED
        }
        cannot = {
            c: n for c, n in agg["tail"].items() if c not in NOT_MODELLED
        }
        print(
            f"  capture [{lang}]: {accounted:.1f}% of {sites} detected "
            f"call sites accounted"
        )
        if not_modelled:
            named = ", ".join(f"{c} {n}" for c, n in sorted(not_modelled.items()))
            print(f"    seen, not modelled by design: "
                  f"{sum(not_modelled.values())} ({named})")
        if cannot:
            named = ", ".join(f"{c} {n}" for c, n in sorted(cannot.items()))
            print(f"    cannot resolve: {sum(cannot.values())} ({named})")
        if lang in classes_available:
            missing = [c for c in ALL_CLASSES if c not in classes_available[lang]]
            if missing:
                print(
                    f"    classes this lane cannot report: {', '.join(missing)}"
                    f" (C-32)"
                )
    _print_directory_view(coverage_rows)


#: How many directory rows the ingest summary prints. The cut is stated,
#: never silent: the remainder line counts what it holds back, and the
#: per-file rows in graph.json remain the full-resolution record.
_DIR_ROWS_SHOWN = 10


def _print_directory_view(coverage_rows: list[dict]) -> None:
    """The per-directory capture breakdown: the same statement as the
    per-language line, one directory at a time, worst first — so on a
    large repo the misses have an address, not just a total. Directories
    where everything resolved are summarised, not listed: the view
    exists to point at what is missing."""
    from hobbes.extract.tail import NOT_MODELLED, rollup_directories

    def cannot(agg) -> dict:
        return {c: n for c, n in agg["tail"].items() if c not in NOT_MODELLED}

    dirs = rollup_directories(coverage_rows)
    misses = {k: v for k, v in dirs.items() if cannot(v)}
    if not misses:
        return
    # Ranked by the *cannot resolve* group, not total unresolved: a
    # directory full of builtin-named calls is accounted for by design,
    # and letting it outrank real misses would bury the point of the view.
    ranked = sorted(
        misses.items(), key=lambda kv: (-sum(cannot(kv[1]).values()), kv[0])
    )
    print(
        f"  by directory (depth 2, worst {min(len(ranked), _DIR_ROWS_SHOWN)}"
        f" of {len(misses)} with unresolvable sites; "
        f"{len(dirs) - len(misses)} without)"
    )
    for (directory, lang), agg in ranked[:_DIR_ROWS_SHOWN]:
        sites, unresolved = agg["sites"], agg["unresolved"]
        accounted = (sites - unresolved) / sites * 100
        classes = cannot(agg)
        named = ", ".join(f"{c} {n}" for c, n in sorted(classes.items()))
        by_design = unresolved - sum(classes.values())
        print(
            f"    {directory} [{lang}]: {accounted:.1f}% of {sites} sites"
            + (f", {by_design} by design" if by_design else "")
            + f" — cannot resolve {sum(classes.values())} ({named})"
        )
    rest = ranked[_DIR_ROWS_SHOWN:]
    if rest:
        held = sum(sum(cannot(v).values()) for _, v in rest)
        print(
            f"    … and {len(rest)} more directories ({held} unresolvable) — "
            f"per-file rows in graph.json resolution_coverage"
        )


def _cmd_init(args: argparse.Namespace) -> int:
    """Scaffold the .hobbes/ layout (architecture §10). Idempotent."""
    from hobbes.extract.emit import ensure_hobbes_ignored

    root = Path(args.repo).resolve() if args.repo else Path.cwd()
    actions: list[str] = []
    ignored = ensure_hobbes_ignored(root)
    if ignored:
        actions.append(f"{ignored} (ADR-012)")

    for sub in ("policies", "invariants"):
        directory = root / ".hobbes" / sub
        if not directory.is_dir():
            directory.mkdir(parents=True)
            actions.append(f"created {directory.relative_to(root)}/")

    repo_policy = root / ".hobbes" / "policies" / "repo.policy"
    if not repo_policy.exists():
        repo_policy.write_text(_STARTER_POLICY)
        actions.append(f"created {repo_policy.relative_to(root)} (starter policy)")

    gitignore = root / ".gitignore"
    existing_text = gitignore.read_text() if gitignore.exists() else ""
    missing = [
        line for line in _GITIGNORE_LINES if line not in existing_text.splitlines()
    ]
    if missing:
        if existing_text and not existing_text.endswith("\n"):
            existing_text += "\n"
        gitignore.write_text(existing_text + "\n".join(missing) + "\n")
        actions.append(f".gitignore: added {', '.join(missing)}")

    if not actions:
        print(f"{root}: .hobbes/ layout already in place, nothing to do")
    else:
        print(f"initialized .hobbes/ in {root}")
        for action in actions:
            print(f"  {action}")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    """Print the ingested module graph as Mermaid (ADR-008)."""
    from hobbes.render import to_mermaid

    repo_root = _repo_root_from(args)
    try:
        graph = artifacts.load_graph(repo_root)
    except artifacts.ArtifactError as exc:
        print(f"hobbes render: {exc}", file=sys.stderr)
        return 1
    print(to_mermaid(graph), end="")
    return 0


def _parse_range(spec: str) -> tuple[str, str]:
    """``base..head`` (bare ``base`` means ``base..HEAD``); rejects ``...``."""
    if "..." in spec:
        raise SystemExit(
            "hobbes diff: three-dot ranges are not supported; use <base>..<head>"
        )
    base, sep, head = spec.partition("..")
    if not base:
        raise SystemExit(f"hobbes diff: invalid range {spec!r}; use <base>..<head>")
    return base, (head if sep and head else "HEAD")


def _cmd_diff(args: argparse.Namespace) -> int:
    """Print the architecture delta between two refs (ADR-009)."""
    from hobbes.graphdiff import (
        RefError,
        diff_graphs,
        extract_at_ref,
        format_delta,
        has_changes,
    )

    repo_root = _repo_root_from(args)
    base_ref, head_ref = _parse_range(args.range)
    try:
        base = extract_at_ref(repo_root, base_ref)
        head = extract_at_ref(repo_root, head_ref)
    except RefError as exc:
        print(f"hobbes diff: {exc}", file=sys.stderr)
        return 2
    delta = diff_graphs(base, head)
    if args.json:
        print(json.dumps(delta, indent=2, sort_keys=True))
    else:
        print(format_delta(delta, base_ref, head_ref), end="")
    return 1 if has_changes(delta) else 0


def _cmd_lanes(args: argparse.Namespace) -> int:
    """Report where the two extraction lanes disagree (§3.4)."""
    from hobbes.artifacts import ArtifactError, load_graph

    repo_root = _repo_root_from(args)
    try:
        graph = load_graph(repo_root)
    except ArtifactError as exc:
        print(f"hobbes lanes: {exc}", file=sys.stderr)
        return 2

    report = graph.get("lane_agreement")
    if report is None:
        print(
            "hobbes lanes: this graph predates the lane-agreement report — "
            "re-run `hobbes ingest`",
            file=sys.stderr,
        )
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if _has_disagreement(report) else 0

    sites = report["sites_compared"]
    site_bad = report["site_disagreements"]
    print(f"lane agreement @ {graph['sha'][:12]}")
    print(
        f"  call sites both lanes resolved: {sites}"
        f" — {len(site_bad)} disagree"
    )
    for row in site_bad[:20]:
        print(f"    {row['file']}:{row['line']} {row['name']}()")
        print(f"      syntactic -> {row['syntactic']}")
        print(f"      semantic  -> {row['semantic']}")
    if len(site_bad) > 20:
        print(f"    ... and {len(site_bad) - 20} more")

    only_a = report["module_edges_lane_a_only"]
    only_b = report["module_edges_lane_b_only"]
    print(
        f"  module edges compared: {report['module_edges_compared']}"
        f" — {len(only_a)} lane A only, {len(only_b)} lane B only"
    )
    for row in only_a[:10]:
        print(f"    lane A only: {row['from']} -> {row['to']}")
    for row in only_b[:10]:
        print(f"    lane B only: {row['from']} -> {row['to']}")
    if not _has_disagreement(report):
        print("  the lanes agree wherever both can answer")
    return 1 if _has_disagreement(report) else 0


def _has_disagreement(report: dict) -> bool:
    """Whether the report contains anything a human must look at.

    Site disagreements only. A module edge one lane alone produced is
    usually the division of labour working — lane B follows a re-export
    to the real definition where lane A stops at the package (ADR-027) —
    so it is reported and does not fail the check.
    """
    return bool(report["site_disagreements"])


def _cmd_narrate(args: argparse.Namespace) -> int:
    """Run the cartographer narrative pass (ADR-019/020). Spends quota."""
    from hobbes.extract.emit import StampError
    from hobbes.narrate import NarrateError, plan_status, run_pass
    from hobbes.narrate.runner import ClaudeRunner

    repo_root = _repo_root_from(args)
    only, exclude = args.only or [], args.exclude or []
    try:
        if args.dry_run:
            rows = plan_status(
                repo_root,
                only=only,
                exclude=exclude,
                invariants=not args.no_invariants,
                force_all=args.all,
            )
            for unit, due, reason in rows:
                marker = "due " if due else "skip"
                print(f"  {marker} {unit.kind:<10} {unit.id} ({reason})")
            due_count = sum(1 for _, due, _ in rows if due)
            print(
                f"narrate --dry-run: {due_count} cartographer calls would run, "
                f"{len(rows) - due_count} fresh"
            )
            return 0
        summary = run_pass(
            repo_root,
            ClaudeRunner(model=args.model),
            only=only,
            exclude=exclude,
            invariants=not args.no_invariants,
            force_all=args.all,
        )
    except (NarrateError, StampError) as exc:
        print(f"hobbes narrate: {exc}", file=sys.stderr)
        return 1
    return 1 if summary["failed"] else 0


def _cmd_docs_status(args: argparse.Namespace) -> int:
    """Print each narrative artifact with its stale badge (§3.3)."""
    from hobbes.narrate import artifact_status

    repo_root = _repo_root_from(args)
    rows = artifact_status(repo_root)
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0
    if not rows:
        print("no narrative artifacts — run `hobbes narrate`")
        return 0
    badges = {"fresh": "fresh", "stale": "STALE", "broken": "BROKEN"}
    for row in rows:
        extra = f" ({', '.join(row['changed'])})" if row["changed"] else ""
        print(f"  {badges[row['status']]:<6} {row['kind']:<19} {row['id']}{extra}")
    stale = sum(1 for row in rows if row["status"] != "fresh")
    print(f"docs: {len(rows)} artifacts, {stale} stale")
    return 0


def _cmd_policy_resolve(args: argparse.Namespace) -> int:
    """Pass through to `hobbes-policy resolve`, propagating its exit code."""
    try:
        resolution = policy.resolve(
            args.command_string, dir=args.dir, repo=args.repo, box=args.box
        )
    except policy.PolicyBinaryNotFound as exc:
        print(f"hobbes policy resolve: {exc}", file=sys.stderr)
        return 1
    except policy.PolicyResolveError as exc:
        print(f"hobbes policy resolve: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(resolution.raw, indent=2))
    return resolution.exit_code


def _load_invariants(repo_root, strict_guards: bool = True):
    """Load records, checking guarded_by against tests.json when present.

    A guard naming a test that no longer exists is a false reassurance,
    so the check is on by default — but a repo that has not been ingested
    has no inventory to check against, and that is not the record's fault.
    """
    from hobbes.invariants import load_all

    known = None
    if strict_guards:
        if artifacts.artifact_path(repo_root, "tests.json").is_file():
            known = {t["id"] for t in artifacts.load_tests(repo_root)["tests"]}
    return load_all(repo_root, known_tests=known)


def _read_graph(repo_root):
    """Load graph.json, or None when the repo has not been ingested.

    A *wrong version* is not an absence and does not become None — it
    raises, so the caller cannot mistake "refused" for "never ingested"
    (ADR-028).
    """
    return artifacts.graph_if_ingested(repo_root)


def _cmd_invariants(args: argparse.Namespace) -> int:
    """`hobbes invariants list | check | compile` (ADR-024)."""
    from hobbes.invariants import ValidationError

    repo_root = _repo_root_from(args)
    try:
        records = _load_invariants(repo_root)
    except ValidationError as exc:
        print(f"hobbes invariants: {len(exc.problems)} problem(s)", file=sys.stderr)
        for problem in exc.problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    for record in records:
        for warning in record.warnings:
            print(f"WARNING: {warning}", file=sys.stderr)

    if args.invariants_command == "check":
        # Loading is the check; getting here means every record is valid.
        if args.json:
            print(json.dumps({"records": len(records), "ok": True}, indent=2))
        else:
            confirmed = sum(1 for r in records if r.confirmed)
            print(f"invariants: {len(records)} record(s) valid, {confirmed} confirmed")
        return 0

    if args.invariants_command == "list":
        rows = [
            {
                "id": r.id,
                "status": r.status,
                "check": r.check,
                "target": r.target,
                "scope": r.scope,
                "statement": r.statement,
                "guarded_by": r.guarded_by,
                "source": r.source,
            }
            for r in records
            if args.all or r.confirmed
        ]
        if args.json:
            print(json.dumps(rows, indent=2, sort_keys=True))
            return 0
        if not rows:
            print("no confirmed invariants — see .hobbes/invariants/README.md")
            return 0
        for row in rows:
            how = row["check"] + (f":{row['target']}" if row["target"] else "")
            print(f"  {row['id']:<6} {row['status']:<9} {how:<13} {row['scope']}")
            print(f"         {row['statement']}")
            if row["guarded_by"]:
                print(f"         guarded by {len(row['guarded_by'])} test(s)")
        print(f"invariants: {len(rows)} shown")
        return 0

    # compile
    from hobbes.invariants.compile import compile_all

    graph = _read_graph(repo_root)
    if graph is None:
        print(
            "hobbes invariants compile: no graph.json — run `hobbes ingest` first "
            "(wildcards expand over the module graph)",
            file=sys.stderr,
        )
        return 1
    manifest = compile_all(repo_root, records, graph)
    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0
    if not manifest["outputs"]:
        print("nothing to compile — every confirmed record is soft")
    for output in manifest["outputs"]:
        ids = ", ".join(output["invariants"])
        print(f"  wrote {output['path']}  ({ids})")
        print(f"        run: {output['run']}")
    for skip in manifest["skipped"]:
        print(f"  skipped {skip['id']}: {skip['why']}")
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    """Concept-level review of a range: delta, invariants, coverage (ADR-025)."""
    from hobbes.graphdiff import RefError
    from hobbes.invariants import ValidationError
    from hobbes.review import build_review, format_review, review_to_dict

    repo_root = _repo_root_from(args)
    base_ref, head_ref = _parse_range(args.range)
    try:
        review = build_review(
            repo_root, base_ref, head_ref, with_soft=args.soft
        )
    except RefError as exc:
        print(f"hobbes review: {exc}", file=sys.stderr)
        return 2
    except ValidationError as exc:
        print(f"hobbes review: invalid invariant records", file=sys.stderr)
        for problem in exc.problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(review_to_dict(review), indent=2, sort_keys=True))
    else:
        print(format_review(review), end="")
    return 1 if review.needs_attention else 0


def _cmd_plan(args: argparse.Namespace) -> int:
    """`hobbes plan`: proposal → change-spec (ADR-051, D1).

    Deterministic and quota-free: the mapping from agent-mapping.md's
    §3–§5 over the ingested artifacts. Writes
    .hobbes/plans/<task>/change-spec.yaml and prints the summary a
    human reviews. Exit 0 gate pass, 1 gate fail, 2 trouble.
    """
    from hobbes.derive import DeriveError, derive_plan, format_spec, spec_to_dict, write_spec
    from hobbes.derive.impact import SeedError
    from hobbes.derive.manifests import GuaranteeError
    from hobbes.invariants import ValidationError

    repo_root = _repo_root_from(args)
    try:
        spec = derive_plan(
            repo_root,
            args.proposal,
            seeds=args.seed or [],
            adds=args.adds or [],
            budget=args.budget,
            max_units=args.max_units,
        )
    except (artifacts.ArtifactError, SeedError, DeriveError, GuaranteeError) as exc:
        print(f"hobbes plan: {exc}", file=sys.stderr)
        return 2
    except ValidationError as exc:
        print("hobbes plan: invalid invariant records", file=sys.stderr)
        for problem in exc.problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    path = write_spec(repo_root, spec)
    if args.json:
        print(json.dumps(spec_to_dict(spec), indent=2, sort_keys=True))
    else:
        print(format_spec(spec), end="")
        print(f"\nchange-spec: {path.relative_to(repo_root)}")
    return 1 if spec.gate.result == "fail" else 0


def _cmd_run(args: argparse.Namespace) -> int:
    """`hobbes run`: execute a change-spec (ADR-054, D2 base).

    The orchestrator loop: materialize each unit's agent (layered
    policy, standing context, inbox), spawn one single-use session per
    unit in contract order, harvest, integrate, review, and write the
    partition record. `--dry-run` writes everything and spawns nothing.
    Exit 0 when every spawned unit exited 0, integration merged, and the
    review is clean; 1 when any of those needs attention; 2 on trouble.
    """
    from hobbes.run import RunError, SpecError, run_task
    from hobbes.run.orchestrate import format_record

    repo_root = _repo_root_from(args)
    if args.from_proposal:
        from hobbes.run.stages import ALL_STAGES, run_staged
        stages = tuple(s.strip() for s in args.stages.split(",") if s.strip())
        bad = [s for s in stages if s not in ALL_STAGES]
        if bad:
            print(f"hobbes run: unknown stage(s) {', '.join(bad)}; choose from {', '.join(ALL_STAGES)}",
                  file=sys.stderr)
            return 2
        try:
            record = run_staged(
                repo_root, args.from_proposal, stages=stages, dry_run=args.dry_run,
                session_bin=args.session_bin, sessions_root=Path(args.sessions) if args.sessions else None,
                extra_args=args.session_arg or [], brief_limit=args.brief_limit, max_units=args.max_units,
                workers=args.parallel, coverage_mode=args.coverage, proposal_in_brief=args.proposal_in_brief,
                planner_args=args.planner_arg or [],
            )
        except (RunError, artifacts.ArtifactError) as exc:
            print(f"hobbes run: {exc}", file=sys.stderr)
            if getattr(exc, "coverage", None):
                print("hobbes run: stopped at plan cost — no implementer spawned; the coverage is in "
                      "the plan's partition-record.json (ADR-085; --coverage assign runs anyway, C-57)",
                      file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(record, indent=2, sort_keys=True))
        else:
            cov = record.get("coverage", {})
            print(f"staged run {record['task']}: seed_source={record['seed_source']}, "
                  f"{len(record['units'])} unit(s), integration {record['integration'].get('merged')}, "
                  f"verify {record.get('verify', {}).get('verdict', 'n/a')}")
            if cov.get("status"):
                print(f"  coverage: {cov['status']} — {len(cov.get('requirements', []))} requirement(s)"
                      + (", re-planned once" if cov.get("replanned") else "")
                      + f"; implementer briefs carry the {record.get('brief_task', 'proposal')}"
                      + (" (ADR-085; ownership is by named file, C-57)" if cov.get("requirements") else ""))
        verify = record.get("verify", {})
        return 1 if (record["integration"].get("failed") or verify.get("verdict") == "fail") else 0
    if not args.task:
        print("hobbes run: give a plan id, or --from-proposal to plan and run in one pass",
              file=sys.stderr)
        return 2
    try:
        record = run_task(
            repo_root,
            args.task,
            dry_run=args.dry_run,
            only_units=args.unit or None,
            session_bin=args.session_bin,
            sessions_root=Path(args.sessions) if args.sessions else None,
            extra_args=args.session_arg or [],
            brief_limit=args.brief_limit,
        )
    except (SpecError, RunError, artifacts.ArtifactError) as exc:
        print(f"hobbes run: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(record, indent=2, sort_keys=True))
    else:
        print(format_record(record))
    bad_exit = any(u["spawned"] and u["exit"] not in (0, None) for u in record["units"])
    failed = bool(record["integration"].get("failed")) or bool(record["integration"].get("error"))
    attention = bool(record["review"].get("needs_attention"))
    return 1 if (bad_exit or failed or attention) else 0


def _cmd_mail(args: argparse.Namespace) -> int:
    """`hobbes mail post|read`: the short-term channel (ADR-054).

    `post` appends a message to a unit's inbox (it rides the next
    brief); `read` prints an inbox. The orchestrator's own inbox is
    unit `orchestrator` — reflections and human-first notices land
    there.
    """
    from hobbes.run import SpecError, mail
    from hobbes.run.agents import agent_dir
    from hobbes.run.spec import plan_dir, resolve_task

    repo_root = _repo_root_from(args)
    try:
        task = resolve_task(repo_root, args.task)
    except SpecError as exc:
        print(f"hobbes mail: {exc}", file=sys.stderr)
        return 2
    directory = agent_dir(plan_dir(repo_root, task), args.unit)
    if args.mail_command == "post":
        message = mail.post(directory, args.sender, args.text, kind=args.kind)
        print(f"posted [{message['seq']}] to {args.unit} ({task})")
        return 0
    messages = mail.read(directory)
    if not messages:
        print(f"{args.unit} ({task}): inbox empty")
        return 0
    for message in messages:
        print(f"[{message['seq']}] from {message['from']} ({message['kind']}): {message['text']}")
    return 0


def _cmd_bench(args: argparse.Namespace) -> int:
    """`hobbes bench select|run|report`: the benchmark harness (ADR-055).

    `select` applies the instance protocol and prints what would run;
    `run` checks each selected instance out at its base commit and runs
    the pure arm (Claude Code, raw) and/or the harness arm (ingest →
    plan → run), one record per (instance, arm, model), then judges
    the patches through the benchmark's own evaluator when
    `--evaluate` is given; `report` lays the records against H1–H3.
    Exit 0 when the command completed, 1 when an evaluator call failed
    or a run left records in error, 2 on trouble.
    """
    from hobbes.bench import instances as inst
    from hobbes.bench import results
    from hobbes.bench import run as bench_run

    if args.bench_command == "report":
        records = results.load(Path(args.run_dir))
        if not records:
            print(f"hobbes bench report: no records under {args.run_dir}", file=sys.stderr)
            return 2
        doc = results.report(records)
        print(json.dumps(doc, indent=2, sort_keys=True) if args.json else results.format_report(doc))
        return 0

    try:
        loaded = inst.load_instances(Path(args.instances))
    except (inst.InstanceError, json.JSONDecodeError) as exc:
        print(f"hobbes bench: {exc}", file=sys.stderr)
        return 2
    selection = inst.select(
        loaded, source=str(args.instances), cutoff=args.cutoff,
        repos=args.repo or [], ids=args.id or [], limit=args.limit,
        difficulty=args.difficulty or [],
    )
    if args.bench_command == "select":
        if args.json:
            print(json.dumps(selection.to_dict(), indent=2, sort_keys=True))
        else:
            print(inst.format_selection(selection))
            for i in selection.selected:
                print(f"  {i.instance_id}  {i.created_at[:10] or 'undated':10}  {i.depth_bucket}")
        return 0

    from hobbes.bench import secrets
    from hobbes.bench.arms import Runtime

    if args.secrets:
        try:
            names = secrets.export(Path(args.secrets))
        except secrets.SecretsError as exc:
            print(f"hobbes bench run: {exc}", file=sys.stderr)
            return 2
        print(f"secrets: exported {', '.join(names) if names else 'nothing new'} from {args.secrets}")

    which = ["pure", "harness"] if args.arm == "both" else [args.arm]
    models = args.model or [""]
    try:
        runtime = Runtime(kind=args.runtime, base_url=args.llm_base_url or "",
                          api_key_env=args.llm_key_env, max_turns=args.max_turns,
                          max_tokens=args.max_tokens, temperature=args.temperature, top_p=args.top_p,
                          reasoning_effort=args.reasoning_effort, thinking=args.thinking,
                          stall_after=args.stall_after, nudge_after=args.nudge_after)
    except ValueError as exc:
        print(f"hobbes bench run: {exc}", file=sys.stderr)
        return 2
    run_dir = Path(args.out) if args.out else Path.home() / ".hobbes" / "bench" / args.name
    print(inst.format_selection(selection))
    print(f"run: {run_dir} — arms {', '.join(which)}; models {', '.join(m or 'default' for m in models)}; "
          f"runtime {runtime.kind}" + (f" @ {runtime.base_url}" if runtime.base_url else ""))
    print(f"  environment: {args.environment}"
          + (" — both arms run in the instance's swebench image, worktree bound by PYTHONPATH + copied "
             "build artifacts (ADR-058, C-43)" if args.environment == "swebench" else
             " — the pure arm on the host, the harness arm in the bare session image; tests need the "
             "target's dependencies, which neither has")
          + f"; network {args.network}")
    print(f"  unit cap: {args.max_units if args.max_units else 'none'}"
          + (" — the lowest-impact units are deferred (never a seed-bearing one); seed units merged to fit are flagged `capped` (C-44)" if args.max_units else "")
          + f"; brief limit: {f'{args.brief_limit:,} chars (C-45)' if args.brief_limit else ('none' if args.brief_limit == 0 else 'sized to the window at run start (ADR-069)')}")
    print(f"  harness arm: {'staged — ' + args.stages + ' (ADR-059)' if args.stages else 'per-unit (ADR-054)'}")
    if args.stages:
        print(f"  coverage: {args.coverage} — a requirement with no owning unit after one re-plan is "
              + ("a plan-error (ADR-085)" if args.coverage == "strict" else "assigned to the seed unit, recorded (C-57)")
              + ("; full issue kept in every brief (removal-test control)" if args.proposal_in_brief
                 else "; implementers get their owned requirements, not the issue (ADR-084 §3)")
              + (f"; planner args: {' '.join(args.planner_arg)}" if args.planner_arg else ""))
    if args.instance_workers > 1:
        print(f"  instance workers: {args.instance_workers} — instances overlap on the shared endpoint "
              "(ADR-065); speedup is endpoint-throughput-bound")
    if not selection.selected:
        print("hobbes bench run: nothing selected", file=sys.stderr)
        return 2
    records = bench_run.run(
        run_dir, selection, models, which,
        session_bin=args.session_bin,
        sessions_root=Path(args.sessions) if args.sessions else None,
        session_args=args.session_arg or [], budget=args.budget,
        clean=args.clean, timeout=args.timeout, runtime=runtime,
        environment_kind=args.environment, network=args.network, max_units=args.max_units,
        brief_limit=args.brief_limit, brief_window_share=args.brief_window_share, human_first=args.human_first,
        stages=tuple(s.strip() for s in args.stages.split(",") if s.strip()) if args.stages else None,
        implement_mode=args.implement_mode,
        parallel_setting=args.parallel,
        instance_workers=args.instance_workers,
        coverage_mode=args.coverage, proposal_in_brief=args.proposal_in_brief,
        planner_args=args.planner_arg or [],
    )
    failed = False
    if args.evaluate:
        # The evaluator (local or Modal) needs the image-schema dataset
        # (see verdict.EVAL_DATASET); a local instances export lacks the
        # image/eval_script fields make_test_spec reads.
        from hobbes.bench import verdict as _verdict
        dataset = args.dataset or _verdict.EVAL_DATASET
        before = sum(1 for r in records if r.solved is None)
        records = bench_run.evaluate(run_dir, dataset, max_workers=args.workers, modal=args.eval_modal)
        failed = sum(1 for r in records if r.solved is None) == before and before > 0
    print()
    print(results.format_report(results.report(records)))
    print(f"\nrecords: {run_dir / results.RECORDS}")
    return 1 if failed else 0


def _cmd_up(args: argparse.Namespace) -> int:
    """`hobbes up`: bring Hobbes up on a repo and hold for decisions (ADR-026).

    Does the mechanical steps — init if needed, re-ingest when the
    artifacts are not stamped at HEAD — then serves the UI and blocks
    until intent and every new invariant have a human verdict. It never
    narrates: that spends quota, and the graph should be checked before
    anything is paid for prose about it.
    """
    import shutil
    import subprocess
    import time

    from hobbes import decisions

    repo_root = _repo_root_from(args)

    # 1. Is Hobbes here at all?
    policy_path = repo_root / ".hobbes" / "policies" / "repo.policy"
    if not policy_path.is_file():
        print(f"hobbes up: no .hobbes/ in {repo_root} — initializing")
        rc = _cmd_init(argparse.Namespace(repo=str(repo_root)))
        if rc != 0:
            return rc

    # 2. Which commit was Hobbes last linked to?
    graph_path = repo_root / ".hobbes" / "derived" / "graph.json"
    head = _git_head(repo_root)
    stamped = ""
    if graph_path.is_file():
        try:
            stamped = json.loads(graph_path.read_text()).get("sha", "")
        except (ValueError, OSError):
            stamped = ""
    if not stamped:
        print("hobbes up: no skeleton yet — ingesting")
    elif stamped != head:
        print(f"hobbes up: artifacts stamped at {stamped[:12]}, HEAD is "
              f"{head[:12]} — re-ingesting")
    else:
        print(f"hobbes up: artifacts current at {stamped[:12]}")
    if not stamped or stamped != head:
        rc = _cmd_ingest(argparse.Namespace(repo=str(repo_root), tf_plan=None))
        if rc != 0:
            return rc

    # 3. What is still owed a human?
    state = decisions.readiness(repo_root)
    print()
    if state.ready:
        print("hobbes up: nothing awaiting a decision")
    else:
        print("hobbes up: decisions needed before this repo is ready:")
        for blocker in state.blockers():
            print(f"  - {blocker}")

    if args.no_serve:
        _print_ready(state, repo_root, served=False)
        return 0 if state.ready else 1

    binary = args.web_bin or shutil.which("hobbes-web")
    if not binary:
        print(
            "hobbes up: hobbes-web not found on PATH — build it "
            "(`cd go && go build -o bin/hobbes-web ./cmd/hobbes-web`) or pass "
            "--web-bin",
            file=sys.stderr,
        )
        return 1

    server = subprocess.Popen(
        [binary, "serve", "--repo", str(repo_root), "--addr", args.addr]
    )
    try:
        # 4. Block until the queue is empty (ADR-026: a queue you can walk
        # past is a queue you never empty).
        announced = state.ready
        if announced:
            _print_ready(state, repo_root, served=True, addr=args.addr)
        while True:
            if server.poll() is not None:
                print("hobbes up: the web surface exited", file=sys.stderr)
                return 1
            time.sleep(_UP_POLL_SECONDS)
            state = decisions.readiness(repo_root)
            if state.ready and not announced:
                announced = True
                _print_ready(state, repo_root, served=True, addr=args.addr)
    except KeyboardInterrupt:
        print("\nhobbes up: shutting down")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


#: How often `hobbes up` re-reads the decision ledger while blocking.
_UP_POLL_SECONDS = 2.0


def _git_head(repo_root: Path) -> str:
    """The repo's HEAD sha, or "" when git cannot answer."""
    import subprocess

    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _print_ready(state, repo_root: Path, served: bool, addr: str = "") -> None:
    """The banner that says a session can start."""
    print()
    if not state.ready:
        print("hobbes up: still waiting on:")
        for blocker in state.blockers():
            print(f"  - {blocker}")
        if served:
            print(f"  decide them at http://{addr}")
        return
    print("hobbes up: ready to develop.")
    print(f"  hobbes-session start --repo {repo_root} --role implementer --task '...'")
    if served:
        print(f"  surface: http://{addr}   (ctrl-c to stop)")


def build_parser() -> argparse.ArgumentParser:
    """Construct the hobbes argument parser (exposed for tests)."""
    parser = argparse.ArgumentParser(
        prog="hobbes",
        description="Hobbes: policy-governed agentic development environment.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser(
        "init", help="scaffold the .hobbes/ layout in a repo"
    )
    init_parser.add_argument(
        "--repo", help="repo root to initialize (default: current directory)"
    )

    ingest_parser = sub.add_parser(
        "ingest",
        help="run the deterministic extractors, write .hobbes/derived/",
        description=(
            "Extract the repo's knowledge skeleton (module graph, symbols, "
            "routes, test map) into SHA-stamped JSON artifacts under "
            ".hobbes/derived/."
        ),
    )
    ingest_parser.add_argument(
        "--repo", help="repo root (default: auto-detected via .git)"
    )
    ingest_parser.add_argument(
        "--tf-plan",
        help="a `terraform show -json` file to enrich the infra graph "
        "(never .tfstate)",
    )

    render_parser = sub.add_parser(
        "render",
        help="print the ingested module graph as Mermaid",
        description=(
            "Reads .hobbes/derived/graph.json (run `hobbes ingest` first) and "
            "prints a module-level Mermaid flowchart to stdout."
        ),
    )
    render_parser.add_argument(
        "--repo", help="repo root (default: auto-detected via .git)"
    )

    diff_parser = sub.add_parser(
        "diff",
        help="architecture delta between two refs",
        description=(
            "Extracts the graph at <base> and <head> and prints the typed "
            "edge-level delta. Exit codes mirror diff(1): 0 no differences, "
            "1 differences, 2 trouble."
        ),
    )
    diff_parser.add_argument(
        "range",
        metavar="<base>..<head>",
        help="refs to compare; a bare <base> compares against HEAD",
    )
    diff_parser.add_argument(
        "--json", action="store_true", help="emit the full delta as JSON"
    )
    diff_parser.add_argument(
        "--repo", help="repo root (default: auto-detected via .git)"
    )

    lanes_parser = sub.add_parser(
        "lanes",
        help="where the two extraction lanes disagree",
        description=(
            "Architecture v2 §3.4's self-test. Wherever both the syntax "
            "lane and the semantic lane resolved the same call site, they "
            "must point at the same definition; a disagreement is an "
            "extractor bug in one of them. Exit 1 when any site disagrees, "
            "so this runs as a CI check as well as a command."
        ),
    )
    lanes_parser.add_argument(
        "--json", action="store_true", help="emit the full report as JSON"
    )
    lanes_parser.add_argument(
        "--repo", help="repo root (default: auto-detected via .git)"
    )

    narrate_parser = sub.add_parser(
        "narrate",
        help="cartographer narrative pass — module docs, test behaviors, "
        "inferred invariants (spends Claude quota)",
        description=(
            "Walks the derived skeleton (run `hobbes ingest` first) and has "
            "headless Claude Code write pinned narrative artifacts into "
            ".hobbes/derived/docs/ (ADR-019/020). Only missing or stale "
            "units run; each unit is one quota-spending call."
        ),
    )
    narrate_parser.add_argument(
        "--repo", help="repo root (default: auto-detected via .git)"
    )
    narrate_parser.add_argument(
        "--all", action="store_true", help="regenerate even fresh artifacts"
    )
    narrate_parser.add_argument(
        "--only",
        action="append",
        metavar="PATTERN",
        help="only units whose id or path matches (repeatable, fnmatch)",
    )
    narrate_parser.add_argument(
        "--exclude",
        action="append",
        metavar="PATTERN",
        help="skip units whose id or path matches (repeatable, fnmatch)",
    )
    narrate_parser.add_argument(
        "--no-invariants",
        action="store_true",
        help="skip the repo-wide invariant inference unit",
    )
    narrate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the work plan without spending any quota",
    )
    narrate_parser.add_argument(
        "--model", help="model override passed to claude -p"
    )

    docs_parser = sub.add_parser("docs", help="narrative artifacts front-end")
    docs_sub = docs_parser.add_subparsers(dest="docs_command", required=True)
    status_parser = docs_sub.add_parser(
        "status",
        help="freshness of narrative artifacts (stale badges)",
        description=(
            "Reads .hobbes/derived/docs/ and reports each artifact fresh or "
            "STALE with the changed source files (blob-level, ADR-019)."
        ),
    )
    status_parser.add_argument(
        "--repo", help="repo root (default: auto-detected via .git)"
    )
    status_parser.add_argument(
        "--json", action="store_true", help="emit the rows as JSON"
    )

    up_parser = sub.add_parser(
        "up",
        help="bring Hobbes up on this repo and hold for your decisions",
        description=(
            "One command for a bring-up (ADR-026): initialize if needed, "
            "re-ingest when the artifacts are not stamped at HEAD, serve the "
            "surface, and block until intent and every new invariant have a "
            "verdict. Never narrates — that spends quota, and is offered in "
            "the UI instead."
        ),
    )
    up_parser.add_argument("--repo", help="repo root (default: auto-detected via .git)")
    up_parser.add_argument(
        "--addr", default="127.0.0.1:7777", help="surface bind address (loopback only)"
    )
    up_parser.add_argument("--web-bin", help="hobbes-web binary (default: from PATH)")
    up_parser.add_argument(
        "--no-serve",
        action="store_true",
        help="report what is owed and exit instead of serving (exit 1 if not ready)",
    )

    plan_parser = sub.add_parser(
        "plan",
        help="derive a change-spec from a proposal: units, contracts, manifests",
        description=(
            "The plan derivation (ADR-051): proposal → impact set → partition "
            "→ contracts → per-unit context and policy manifests, each carrying "
            "its stated complement (ADR-047). Writes "
            ".hobbes/plans/<task>/change-spec.yaml. The plan-review gate judges "
            "declared edges (--adds) against confirmed forbidden-import "
            "invariants before any code exists; exit 1 on a violation. "
            "Deterministic and quota-free."
        ),
    )
    plan_parser.add_argument("proposal", help="the proposed change, free text")
    plan_parser.add_argument(
        "--seed",
        action="append",
        help="a node id, symbol, or file the change starts from (repeatable)",
    )
    plan_parser.add_argument(
        "--adds",
        action="append",
        help="a dependency the plan will introduce, as 'from -> to' (repeatable);"
        " checked against the invariants at plan time",
    )
    plan_parser.add_argument(
        "--budget",
        type=int,
        default=60_000,
        help="per-unit context budget in estimated tokens (default: 60000)",
    )
    plan_parser.add_argument(
        "--max-units", type=int, default=None,
        help="cap on the number of units; units merged past the budget to fit are flagged "
        "`capped` (ADR-058, C-44). Default: no cap",
    )
    plan_parser.add_argument(
        "--repo", help="repo root (default: auto-detected via .git)"
    )
    plan_parser.add_argument(
        "--json", action="store_true", help="machine-readable output"
    )

    run_parser = sub.add_parser(
        "run",
        help="execute a change-spec: one single-use session per unit, then "
        "harvest, integrate, review, record",
        description=(
            "The orchestrator loop (ADR-054, D2 base). Per unit, in contract "
            "order: write the brief (standing context + inbox), spawn "
            "`hobbes-session start --agent-dir`, read back the flight log, "
            "the reflections, and the harvested branch. Then integrate the "
            "unit branches onto hobbes/<task>, run the review, and write "
            ".hobbes/plans/<task>/partition-record.json. Human-first units "
            "are not spawned. --dry-run writes everything and spawns nothing."
        ),
    )
    run_parser.add_argument("task", nargs="?",
                            help="a plan id from .hobbes/plans/ (a unique prefix will do); "
                            "omit with --from-proposal, which plans and runs in one staged pass")
    run_parser.add_argument("--from-proposal", metavar="TEXT",
                            help="staged run (ADR-059): a planner names the change, `hobbes plan` derives on "
                            "its seeds, implementers run chained, a verifier checks — no pre-written spec")
    run_parser.add_argument("--parallel", type=int, default=1,
                            help="implementer sessions alive at once in a staged run (ADR-063): units whose "
                                 "contract owners are integrated run together; default 1 = the chained order")
    run_parser.add_argument("--stages", default="plan,implement,verify",
                            help="staged run: comma-separated from plan,review,implement,verify,rework "
                            "(default plan,implement,verify)")
    run_parser.add_argument("--max-units", type=int, default=None,
                            help="staged run: unit cap (C-44); the lowest-impact units are deferred")
    run_parser.add_argument("--dry-run", action="store_true",
                            help="materialize agents and briefs; spawn nothing")
    run_parser.add_argument("--unit", action="append",
                            help="run only this unit (repeatable)")
    run_parser.add_argument("--session-bin",
                            help="hobbes-session binary (default: $HOBBES_SESSION_BIN or PATH)")
    run_parser.add_argument("--sessions",
                            help="session-state root (default: $HOBBES_SESSIONS or ~/.hobbes/sessions)")
    run_parser.add_argument("--brief-limit", type=int, default=None,
                            help="hold each unit's brief to this many characters (unprotected standing-context "
                            "sections cut with a stated cut, C-45); default: no limit")
    run_parser.add_argument("--session-arg", action="append",
                            help="extra flag passed through to hobbes-session start (repeatable), "
                            "e.g. --session-arg=--claude-cred")
    run_parser.add_argument("--coverage", choices=("strict", "assign"), default="strict",
                            help="staged run (ADR-085): when a planner requirement has no owning unit after "
                                 "the one re-plan, 'strict' (default) stops at plan cost (exit 2, record "
                                 "written); 'assign' gives it to the seed unit and says so (C-57)")
    run_parser.add_argument("--proposal-in-brief", action="store_true",
                            help="staged run: keep the full proposal in every implementer brief even when "
                                 "its requirements are covered (the pre-ADR-085 shape, for the removal test)")
    run_parser.add_argument("--planner-arg", action="append",
                            help="extra hobbes-session flag for the PLANNER session only (repeatable), after "
                                 "the run's --session-arg so it overrides — e.g. --planner-arg=--max-turns=80; "
                                 "the weight belongs to the planner (ADR-084)")
    run_parser.add_argument("--repo", help="repo root (default: auto-detected via .git)")
    run_parser.add_argument("--json", action="store_true", help="machine-readable output")

    mail_parser = sub.add_parser(
        "mail",
        help="the short-term channel: post to or read a unit's inbox",
        description=(
            "Short-term context (ADR-054): the orchestrator pushes specifics "
            "to a unit's inbox, the agent reflects back through the proxy, "
            "and reflections land in the `orchestrator` inbox."
        ),
    )
    mail_sub = mail_parser.add_subparsers(dest="mail_command", required=True)
    post_parser = mail_sub.add_parser("post", help="append a message to a unit's inbox")
    post_parser.add_argument("task")
    post_parser.add_argument("unit", help="a unit name (U1) or `orchestrator`")
    post_parser.add_argument("text")
    post_parser.add_argument("--from", dest="sender", default="human",
                             help="sender (default: human)")
    post_parser.add_argument("--kind", default="request",
                             help="request | reply | warning (default: request)")
    post_parser.add_argument("--repo", help="repo root (default: auto-detected via .git)")
    read_parser = mail_sub.add_parser("read", help="print a unit's inbox")
    read_parser.add_argument("task")
    read_parser.add_argument("unit")
    read_parser.add_argument("--repo", help="repo root (default: auto-detected via .git)")

    bench_parser = sub.add_parser(
        "bench",
        help="the benchmark harness: Hobbes vs the pure model on known instances",
        description=(
            "ADR-055. Instances come from a local JSONL export "
            "(pipeline/scripts/bench_fetch.py). `select` applies the instance "
            "protocol (contamination cutoff, filters — every drop counted); "
            "`run` checks each instance out at its base commit and runs the "
            "pure arm and/or the harness arm per model, recording one line per "
            "(instance, arm, model); `--evaluate` judges the patches through the "
            "benchmark's own evaluator; `report` lays the records against the "
            "preregistered hypotheses H1–H3 and interprets nothing."
        ),
    )
    bench_sub = bench_parser.add_subparsers(dest="bench_command", required=True)

    def _selection_flags(p):
        p.add_argument("instances", help="instances JSONL (or JSON array) in SWE-bench shape")
        p.add_argument("--cutoff", help="drop instances created on or before this ISO date (contamination bound, C-39)")
        p.add_argument("--repo", action="append", help="keep only this owner/name (repeatable)")
        p.add_argument("--id", action="append", help="keep only this instance id (repeatable)")
        p.add_argument("--difficulty", action="append",
                       help="keep only this rated band (repeatable): '<15 min fix', '15 min - 1 hour', "
                       "'1-4 hours', '>4 hours', or 'complex' for the last two")
        p.add_argument("--limit", type=int, help="keep at most N (a prefix of the dataset order, not a sample)")
        p.add_argument("--json", action="store_true", help="machine-readable output")

    select_parser = bench_sub.add_parser("select", help="apply the instance protocol and list what would run")
    _selection_flags(select_parser)

    brun_parser = bench_sub.add_parser("run", help="run the arms over the selection; optionally evaluate")
    _selection_flags(brun_parser)
    brun_parser.add_argument("--arm", choices=["both", "pure", "harness"], default="both")
    brun_parser.add_argument("--model", action="append",
                             help="model for both arms (repeatable — the H1 ladder)")
    brun_parser.add_argument("--runtime", choices=["claude", "openai"], default="claude",
                             help="the loop both arms run on: Claude Code, or the owned loop against an "
                             "OpenAI-compatible endpoint (ADR-056)")
    brun_parser.add_argument("--llm-base-url", help="the endpoint for --runtime openai, e.g. https://host/v1")
    brun_parser.add_argument("--llm-key-env", default="HOBBES_LLM_API_KEY",
                             help="env var holding the endpoint's bearer token (default HOBBES_LLM_API_KEY)")
    brun_parser.add_argument("--max-turns", type=int, default=60, help="turn budget per session for the owned loop")
    brun_parser.add_argument("--max-tokens", type=int, default=1536,
                             help="completion cap per turn for the owned loop, both arms (default 1536: cuts the "
                                  "7B's prose-essay turns short so the nudge fires sooner)")
    brun_parser.add_argument("--temperature", type=float, default=0.0,
                             help="sampling temperature for the owned loop, both arms (default 0 = greedy; "
                                  "a thinking rung runs at its card's own — ADR-074)")
    brun_parser.add_argument("--top-p", type=float, default=None, help="nucleus sampling, sent only when given")
    brun_parser.add_argument("--reasoning-effort", default=None,
                             help="a thinking model's reasoning depth (its own levels, e.g. low|medium|xhigh); "
                                  "sent only when given")
    brun_parser.add_argument("--thinking", choices=("server", "on", "off"), default="server",
                             help="a thinking model's mode: the server's default, on, or off; a model without "
                                  "the switch ignores it")
    brun_parser.add_argument("--stall-after", type=int, default=None,
                             help="dry (no-edit) turns before a stalled session is stopped, both arms "
                                  "(ADR-076); default: the loop's own 6, cut for the 7B — raise it for a "
                                  "thinking model that investigates before editing")
    brun_parser.add_argument("--nudge-after", type=int, default=None,
                             help="dry turns before a mid-stream nudge, both arms (ADR-076); default: the "
                                  "loop's own 3")
    brun_parser.add_argument("--name", default="run", help="run name under ~/.hobbes/bench/ (default: run)")
    brun_parser.add_argument("--out", help="run directory (default: ~/.hobbes/bench/<name>)")
    brun_parser.add_argument("--evaluate", action="store_true",
                             help="judge the patches with the pinned swebench evaluator (needs a container engine)")
    brun_parser.add_argument("--dataset", help="dataset name or file for the evaluator (default: the instances file)")
    brun_parser.add_argument("--workers", type=int, default=1, help="evaluator parallelism (default 1)")
    brun_parser.add_argument("--eval-modal", action="store_true",
                             help="run the evaluator's instance images on Modal (swebench --modal) instead of a local engine")
    brun_parser.add_argument("--secrets", help="the owner's name=value key file; known names are exported to the "
                             "environment the tools read (values never printed)")
    brun_parser.add_argument("--timeout", type=float, default=3600.0, help="per-arm wall clock in seconds (default 3600)")
    brun_parser.add_argument("--budget", type=int, help="per-unit context budget for the harness arm's plan")
    brun_parser.add_argument("--brief-limit", type=int, default=None,
                             help="hold each unit's brief to this many characters, cutting unprotected "
                             "standing-context sections with a stated cut (C-45). Default: sized to the "
                             "endpoint's window — --brief-window-share × max_model_len (ADR-069); 60000 "
                             "when the window is unknown; 0 = no limit")
    brun_parser.add_argument("--human-first", choices=("park", "spawn"), default="park",
                             help="a human-first unit (ADR-047: its unresolved complement rivals what the graph "
                             "sees) is parked (default) or spawned anyway with its write scope kept — a benchmark "
                             "has no human to hand it to (C-53); recorded per unit either way")
    brun_parser.add_argument("--brief-window-share", type=float, default=None,
                             help="share of the model's window a brief may take when --brief-limit is not "
                             "given (default 0.35, ADR-069)")
    brun_parser.add_argument("--max-units", type=int, default=20,
                             help="cap on units per harness plan — the number of sessions an instance may "
                             "spawn; 0 = no cap (default 20, ADR-058; capped units flagged, C-44)")
    brun_parser.add_argument("--environment", choices=["swebench", "none"], default="swebench",
                             help="bind both arms to the instance's own swebench image (default) or run "
                             "without the target's environment (tests cannot run)")
    brun_parser.add_argument("--parallel", default="auto",
                             help="implementers alive at once in the staged harness arm (ADR-063): 'auto' "
                                  "(default) asks the endpoint and uses 4 workers when it is vLLM, else runs "
                                  "sequentially and says why (C-51); an integer is the owner's call; 1 = chained")
    brun_parser.add_argument("--instance-workers", type=int, default=1,
                             help="instances run concurrently on the shared endpoint (ADR-065): the served "
                                  "model batches their requests, so N>1 overlaps I/O-bound sessions; the "
                                  "speedup is endpoint-throughput-bound, not N× (default 1 = sequential)")
    brun_parser.add_argument("--implement-mode", choices=("unit", "aided"), default="unit",
                             help="staged harness implement stage (ADR-077): 'unit' spawns write-scoped "
                                  "per-partition sessions (default); 'aided' spawns one implementer on the "
                                  "planner's task, free on the whole worktree, given what Hobbes can and "
                                  "cannot see — Hobbes aids, does not fence. By P12 (ADR-082) an aided "
                                  "run is model + prompt, never a Hobbes test; report it under that label")
    brun_parser.add_argument("--coverage", choices=("strict", "assign"), default="strict",
                             help="staged harness arm (ADR-085): a planner requirement with no owning unit "
                                  "after the one re-plan is a plan-error (default 'strict') or is assigned "
                                  "to the seed unit and recorded (C-57)")
    brun_parser.add_argument("--proposal-in-brief", action="store_true",
                             help="staged harness arm: keep the full issue in every implementer brief even "
                                  "when its requirements are covered — the removal test's control (ADR-084 §3)")
    brun_parser.add_argument("--planner-arg", action="append",
                             help="extra hobbes-session flag for the planner session only (repeatable; after "
                                  "the runtime's flags, so --planner-arg=--max-turns=80 overrides for it alone)")
    brun_parser.add_argument("--stages", default=None,
                             help="staged harness arm (ADR-059): comma-separated from "
                                  "plan,review,implement,verify,rework — a planner names the change and a "
                                  "verifier checks it, instead of lexical seeds and one session per unit. "
                                  "Default: the per-unit path")
    brun_parser.add_argument("--network", default="pasta",
                             help="podman network for both arms (default pasta: the model endpoint needs egress, C-41)")
    brun_parser.add_argument("--session-bin", help="hobbes-session binary for the harness arm")
    brun_parser.add_argument("--sessions", help="session-state root for the harness arm")
    brun_parser.add_argument("--session-arg", action="append",
                             help="extra flag for hobbes-session (repeatable), e.g. --session-arg=--claude-cred")
    brun_parser.add_argument("--clean", action="store_true", help="remove each workspace after its record is written")

    report_parser = bench_sub.add_parser("report", help="lay a run's records against H1–H3")
    report_parser.add_argument("run_dir")
    report_parser.add_argument("--json", action="store_true", help="machine-readable output")

    review_parser = sub.add_parser(
        "review",
        help="concept-level review of a range: delta, invariants, coverage",
        description=(
            "The §7 review order in one command (ADR-025): architecture delta, "
            "invariant verdicts computed at BOTH ends so a regression is "
            "distinguishable from inherited breakage, and the behavioural-coverage "
            "delta. Exits 1 when something needs attention. Spends no quota unless "
            "--soft is given."
        ),
    )
    review_parser.add_argument(
        "range", help="commit range, base..head (as `hobbes diff`)"
    )
    review_parser.add_argument(
        "--repo", help="repo root (default: auto-detected via .git)"
    )
    review_parser.add_argument(
        "--json", action="store_true", help="machine-readable output"
    )
    review_parser.add_argument(
        "--soft",
        action="store_true",
        help="run a reviewer session for in-scope soft invariants (spends quota)",
    )

    invariants_parser = sub.add_parser(
        "invariants",
        help="confirmed invariant records: list, validate, compile to CI configs",
        description=(
            "Records live in .hobbes/invariants/ (ADR-024). `check` validates "
            "them, `list` shows them, and `compile` emits one CI config per "
            "target into .hobbes/derived/compiled/ — no target's toolchain "
            "needs to be installed to compile for it."
        ),
    )
    invariants_sub = invariants_parser.add_subparsers(
        dest="invariants_command", required=True
    )
    for name, help_text in (
        ("list", "show records"),
        ("check", "validate every record and exit non-zero on any problem"),
        ("compile", "emit CI configs into .hobbes/derived/compiled/"),
    ):
        p = invariants_sub.add_parser(name, help=help_text)
        p.add_argument("--repo", help="repo root (default: auto-detected via .git)")
        p.add_argument("--json", action="store_true", help="machine-readable output")
        if name == "list":
            p.add_argument(
                "--all",
                action="store_true",
                help="include inferred and retired records, not just confirmed",
            )

    policy_parser = sub.add_parser("policy", help="policy engine front-end")
    policy_sub = policy_parser.add_subparsers(dest="policy_command", required=True)
    resolve_parser = policy_sub.add_parser(
        "resolve",
        help="resolve a command against the merged policy chain",
        description=(
            "Shells out to the Go hobbes-policy binary. Prints the JSON "
            "resolution; exit code encodes the decision "
            "(0 allow, 10 deny, 20 escalate)."
        ),
    )
    # dest must not collide with the top-level subparser dest ("command").
    resolve_parser.add_argument(
        "command_string",
        metavar="command",
        help="the command to resolve, as one quoted string, "
        'e.g. "git push --force origin main"',
    )
    resolve_parser.add_argument(
        "--dir", help="directory context the command runs in (default: cwd)"
    )
    resolve_parser.add_argument(
        "--repo", help="repo root (default: auto-detected via .git)"
    )
    resolve_parser.add_argument(
        "--box", help="box policy path (default: ~/.hobbes/box.policy if present)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the process exit code."""
    # Report progress as it happens, not at exit. Python block-buffers
    # stdout when it is not a tty, and the two commands that take real time
    # print while they work: `up` lists the decisions it is blocking on and
    # then holds, `narrate` prints one line per unit. Redirected or
    # supervised (`hobbes up > up.log &`), both looked silent for exactly as
    # long as they were doing their job. A tty is line-buffered already, so
    # this changes nothing about interactive use.
    #
    # Guarded because a captured stdout (pytest's capsys, a StringIO) has no
    # reconfigure, and buffering is not its problem anyway.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args = build_parser().parse_args(argv)
    handlers = {
        "init": _cmd_init,
        "ingest": _cmd_ingest,
        "render": _cmd_render,
        "diff": _cmd_diff,
        "lanes": _cmd_lanes,
        "narrate": _cmd_narrate,
        "docs": _cmd_docs_status,
        "invariants": _cmd_invariants,
        "review": _cmd_review,
        "plan": _cmd_plan,
        "run": _cmd_run,
        "mail": _cmd_mail,
        "bench": _cmd_bench,
        "up": _cmd_up,
        "policy": _cmd_policy_resolve,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
