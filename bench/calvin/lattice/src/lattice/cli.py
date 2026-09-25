"""`lattice` — read a target's kernel lattice, and grade bodies against it, from the command line.

    lattice map        <target> [--json]        the cells per ISA: counts by kind, slots, and what did not fit
    lattice task       <target> <cell-id>       the task record for one cell, as JSON
    lattice punch      <target> <cell-id>       that cell's file with its body replaced by the hole
    lattice facts      <target> <cell-id>       the cell's callees from the ledger (C-1, §5.3)
    lattice intrinsics <include-dir>            index clang's headers for every `_mm…`/`_cvt…` signature
    lattice ages       <git-dir> <ref>          since when each cell's name and body have been what they are
    lattice mem-probes <target>                 the G-mem probes, written and not run
    lattice shadow     <target> <dest>          write one rename shadow of the target (E2)
    lattice graph-grade <target> <results.jsonl> G-graph over the bodies a grading run kept
    lattice grade      <target> <manifest.json> grade every entry in the manifest; one JSON line each
    lattice selftest   <target> [--cells …]     the gate on the instruments (§5.5)

Everything but the last three reads text — files, a git history, the derived artifacts — and runs
nowhere in particular. **`grade` and `selftest` compile and run the target's code**, so they take
`--here` (this process is already contained) or `--image NAME` (the default: build a `podman run` plan
and run this same CLI inside it, ADR-092/C-64). `--here` outside a container exits 2 with the refusal.
**`graph-grade` runs a Hobbes ingest**, which contains its own lane B (ADR-092) and so runs on the host
like `uv run hobbes ingest` does. `<target>` is a checkout's root — the directory holding
`src/distance-*.c`.

A manifest is a JSON list of `{"id", "cell", "body"}` entries, or an object with them under `entries`;
`body` is a body's text, `{` to its matching `}`, or the word `"gold"`. `graph-grade` reads the same
rows with a grading run's `class` beside them, and says which it did not carry and why.

`facts` and `task` take the ledger as `--graph derived/graph.json`, `--key derived/oracle.json` and
`--intrinsics index.json`. None of the three is required, and one left out is **named in the answer's
`missing`** rather than filled in from somewhere else: `lattice facts` with no ledger prints no callees
and says so. `mem-probes` writes the probes only — this CLI never calls a model.

`map`, `task` and `grade` take `--rename <shadow-map.json>`: the lattice is then read through that
shadow's reverse map, so the grid is the target's and the names are the shadow's.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from . import ages as ages_of
from . import facts as facts_of
from . import graphgrade as graph_of
from . import shadow as shadow_of
from . import gmem, holes, intrinsics as intrinsics_of, run, task
from .cells import ISAS, Lattice, UnknownCell, build

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns the process exit code: 0, 1 for a self-test mismatch, 2 for a refusal."""
    parser = argparse.ArgumentParser(prog="lattice", description="sqlite-vector's kernel lattice, its cells and its graders")
    verbs = parser.add_subparsers(dest="verb", required=True)

    mapper = verbs.add_parser("map", help="the cells per ISA")
    mapper.add_argument("target", type=Path)
    mapper.add_argument("--json", action="store_true", help="the map as JSON rather than a table")
    _renamed(mapper)

    tasker = verbs.add_parser("task", help="one cell's task record, as JSON")
    tasker.add_argument("target", type=Path)
    tasker.add_argument("cell", help="a cell id, <isa>/<type>/<metric>")
    _ledger(tasker)
    _renamed(tasker)

    puncher = verbs.add_parser("punch", help="one cell's file with its body punched out")
    puncher.add_argument("target", type=Path)
    puncher.add_argument("cell", help="a cell id, <isa>/<type>/<metric>")

    facter = verbs.add_parser("facts", help="one cell's callees from the graph and the clang key")
    facter.add_argument("target", type=Path)
    facter.add_argument("cell", help="a cell id, <isa>/<type>/<metric>")
    _ledger(facter)

    indexer = verbs.add_parser("intrinsics", help="index clang's headers for the intrinsic signatures")
    indexer.add_argument("include_dir", type=Path, help="clang's include dir (`clang -print-file-name=include`)")
    indexer.add_argument("--out", type=Path, help="write the index as JSON here")

    ager = verbs.add_parser("ages", help="since when each cell's name and body have been what they are")
    ager.add_argument("git_dir", type=Path, help="a clone of the target, with its history")
    ager.add_argument("ref", help="the commit to read the cells at")
    ager.add_argument("--out", type=Path, help="write the rows as JSON here; the table always prints")

    prober = verbs.add_parser("mem-probes", help="the G-mem probes for every native cell, as JSONL")
    prober.add_argument("target", type=Path)
    prober.add_argument("--out", type=Path, help="write the probes here (default: stdout)")

    shadower = verbs.add_parser("shadow", help="write one rename shadow of the target (E2)")
    shadower.add_argument("target", type=Path)
    shadower.add_argument("dest", type=Path, help="where to write the shadow; shadow-map.json goes at its root")
    shadower.add_argument("--graph", type=Path, required=True, help="the target's ingest, derived/graph.json")
    shadower.add_argument("--style", choices=shadow_of.STYLES, required=True, help="descriptive or opaque")

    graphgrader = verbs.add_parser("graph-grade", help="G-graph over the bodies a grading run kept")
    graphgrader.add_argument("target", type=Path)
    graphgrader.add_argument("results", type=Path, help="JSONL rows of {id, cell, body, class}")
    graphgrader.add_argument("--gold-graph", type=Path, help="the target's own ingest; without it, one is made")
    graphgrader.add_argument("--hobbes", type=Path, help="a Hobbes checkout, whose pipeline runs the ingest")
    graphgrader.add_argument("--out", type=Path, help="write the rows as JSONL here (default: stdout)")
    _renamed(graphgrader)

    grader = verbs.add_parser("grade", help="grade a manifest of bodies")
    grader.add_argument("target", type=Path)
    grader.add_argument("manifest", type=Path, help="a JSON list of {id, cell, body} entries")
    grader.add_argument("--out", type=Path, help="write the results as JSONL here (default: stdout)")
    _where(grader)
    _renamed(grader)

    tester = verbs.add_parser("selftest", help="the gate on the instruments: the gold and its four mutants")
    tester.add_argument("target", type=Path)
    tester.add_argument("--cells", help="a comma-separated list of cell ids (default: every native cell)")
    tester.add_argument("--out", type=Path, help="write the report as JSON here; the table always prints")
    _where(tester)

    args = parser.parse_args(argv)

    try:
        rename = shadow_of.load(args.rename) if getattr(args, "rename", None) else None
    except OSError as missing:
        print(f"lattice: the shadow map could not be read ({missing})", file=sys.stderr)
        return 2

    if args.verb in ("grade", "selftest"):
        try:
            if args.verb == "selftest":
                return _selftest(args)
            if rename is None:
                return _grade(args)
            with shadow_of.grading(rename):
                return _grade(args)
        except run.NotContained as refusal:
            print(f"lattice: {refusal}", file=sys.stderr)
            return 2
        except FileNotFoundError as missing:
            print(f"lattice: the plan could not be run ({missing}); is podman installed?", file=sys.stderr)
            return 2

    if args.verb == "intrinsics":
        return _intrinsics(args)
    if args.verb == "ages":
        return _ages(args)
    if args.verb == "shadow":
        return _shadow(args)
    if args.verb == "graph-grade":
        return _graph_grade(args, rename)

    lattice = build(args.target, rename=rename)
    if args.verb == "map":
        print(json.dumps(_map(lattice), indent=2) if args.json else _table(lattice))
        return 0
    if args.verb == "mem-probes":
        probes = [gmem.probe(lattice, cell) for cell in _native(lattice)]
        _write_lines([json.dumps(probe, sort_keys=True) for probe in probes], args.out)
        return 0

    try:
        cell = lattice.get(args.cell)
    except UnknownCell:
        print(f"lattice: no cell {args.cell!r}; try `lattice map {args.target}`", file=sys.stderr)
        return 2

    if args.verb in ("task", "facts"):
        try:
            ledger = facts_of.load(args.graph, args.key, args.intrinsics)
        except OSError as missing:
            print(f"lattice: the ledger could not be read ({missing})", file=sys.stderr)
            return 2
        if args.verb == "facts":
            rows = ledger.callees(lattice, cell)
            print(json.dumps(
                {
                    "cell": cell.id,
                    "source": ledger.source(),
                    "missing": rows.missing,
                    "dropped": rows.dropped,
                    "callees": list(rows),
                },
                indent=2,
            ))
        else:
            given = ledger if (args.graph or args.key or args.intrinsics) else None
            print(task.dumps(task.build(lattice, cell, facts=given)))
        return 0

    print(holes.punch(lattice.text(cell), cell), end="")
    return 0


def _where(verb: argparse.ArgumentParser) -> None:
    """The two ways a grading verb can run: here (contained already) or in the image."""
    verb.add_argument("--here", action="store_true", help="run in this process; refused outside a container")
    verb.add_argument("--image", default=run.IMAGE, help=f"the image to run in (default: {run.IMAGE})")
    verb.add_argument("--work", type=Path, help="the work dir (default: a fresh temporary one)")


def _renamed(verb: argparse.ArgumentParser) -> None:
    """`--rename`: read the lattice through a shadow's map, so the grid is the target's own."""
    verb.add_argument("--rename", type=Path, help="a shadow-map.json, from `lattice shadow`")


def _ledger(verb: argparse.ArgumentParser) -> None:
    """The ledger the facts come from; each part left out is named in `missing`, never filled in."""
    verb.add_argument("--graph", type=Path, help="the target's ingest, derived/graph.json")
    verb.add_argument("--key", type=Path, help="the target's clang oracle key, derived/oracle.json")
    verb.add_argument("--intrinsics", type=Path, help="an intrinsic index, from `lattice intrinsics`")


def _native(lattice: Lattice) -> list:
    """Every native cell, in the order the files define them — the cells a body can be graded on."""
    return [cell for isa in ISAS for cell in lattice.by_isa(isa) if cell.native]


# MARK: - the reading verbs -


def _intrinsics(args) -> int:
    index = intrinsics_of.load(args.include_dir)
    macros = sum(1 for entry in index.values() if entry["macro"])
    headers = len({entry["header"] for entry in index.values()})
    print(f"intrinsics: {len(index)} names ({macros} macro, {len(index) - macros} function) over {headers} header(s)")
    if args.out:
        args.out.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    return 0


def _ages(args) -> int:
    try:
        rows = ages_of.ages(args.git_dir, args.ref)
    except (ages_of.NoKernelsAtRef, ages_of.GitError) as refusal:
        print(f"lattice: {refusal}", file=sys.stderr)
        return 2
    print(_age_table(rows))
    if args.out:
        args.out.write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
    return 0


def _shadow(args) -> int:
    try:
        graph = json.loads(args.graph.read_text(encoding="utf-8"))
    except OSError as missing:
        print(f"lattice: the graph could not be read ({missing})", file=sys.stderr)
        return 2
    try:
        plan = shadow_of.plan(args.target, graph, args.style)
    except shadow_of.Collision as refusal:
        print(f"lattice: the {args.style} shadow was not written — {refusal}", file=sys.stderr)
        return 2
    shadow_of.write(plan, args.dest)
    counts = plan.counts
    leaked = shadow_of.leaks(plan, args.dest)
    print(
        f"shadow ({plan.style}): {counts['renamed']} renamed, {counts['kept']} kept, "
        f"{counts['prefixed']} sv_-prefixed, over {counts['files']} file(s) → {args.dest}"
    )
    for reason in ("external", "entry-point", "not-a-graph-symbol"):
        names = [row["name"] for row in plan.kept if row["reason"] == reason]
        if names:
            print(f"  kept, {reason}: {', '.join(names)}")
    for row in leaked:
        names = "too large to read" if row.get("unread") else f"{len(row['names'])} original name(s)"
        print(f"  leaks, not renamed: {row['file']} — {names}")
    for gap in plan.missing:
        print(f"  missing: {gap}")
    return 0


def _graph_grade(args, rename) -> int:
    rows = [json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines() if line.strip()]
    entries, skipped = graph_of.keep(rows)
    gold = json.loads(args.gold_graph.read_text(encoding="utf-8")) if args.gold_graph else None
    ingest = graph_of.hobbes_ingest(args.hobbes or Path.cwd())
    try:
        graded = graph_of.grade(args.target, entries, ingest, gold_graph=gold, rename=rename)
    except graph_of.IngestFailed as refusal:
        print(f"lattice: {refusal}", file=sys.stderr)
        return 2
    _write_lines([json.dumps(row, sort_keys=True) for row in graded + skipped], args.out)
    return 0


def _age_table(rows: dict) -> str:
    header = f"{'cell':<26}{'name since':<14}{'body since':<14}  name"
    lines = [f"ages of {len(rows)} native cell(s)", header, "-" * len(header)]
    for cell_id in sorted(rows):
        row = rows[cell_id]
        lines.append(
            f"{cell_id:<26}{row['name_since'] or '-':<14}{row['body_since'] or '-':<14}  {row['name']}"
            + (f"  ({row['reason']})" if row["reason"] else "")
        )
    dates = [row["body_since"] for row in rows.values() if row["body_since"]]
    if dates:
        lines.append("")
        lines.append("bodies already identical at the end of each quarter:")
        for end in _quarter_ends(min(dates), max(dates)):
            lines.append(f"  {end}  {ages_of.identical_at(rows, end)} of {len(rows)}")
    return "\n".join(lines)


def _quarter_ends(first: str, last: str) -> list[str]:
    """Every quarter end from the oldest body to the newest, so a cutoff can be read off the tally.

    From the first quarter end the rows reach — the first row with a non-zero count — through the one
    that holds the newest body, which is where the count is all of them.
    """
    ends = []
    for year in range(int(first[:4]), int(last[:4]) + 2):
        for end in (f"{year}-03-31", f"{year}-06-30", f"{year}-09-30", f"{year}-12-31"):
            if end < first:
                continue
            ends.append(end)
            if end >= last:
                return ends
    return ends


# MARK: - the grading verbs -


def _grade(args) -> int:
    entries = _entries(args.manifest)
    if args.here:
        from . import grade

        with _workdir(args.work) as workdir:
            results = grade.grade(args.target, entries, workdir)
        _write_lines([json.dumps(result, sort_keys=True) for result in results], args.out)
        return 0

    with _workdir(args.work) as workdir:
        (workdir / "manifest.json").write_text(json.dumps(entries), encoding="utf-8")
        inner = ["grade", "/target", "/work/manifest.json", "--out", "/work/results.jsonl", "--work", "/work/run"]
        if args.rename:
            # the map rides in the work dir, not the target: `--rename` may point anywhere on this box
            (workdir / "shadow-map.json").write_text(args.rename.read_text(encoding="utf-8"), encoding="utf-8")
            inner += ["--rename", "/work/shadow-map.json"]
        plan = run.image_plan(args.image, args.target, workdir, inner)
        done = run.run_plan(plan)
        sys.stderr.write(done.stderr)
        if done.returncode != 0:
            return done.returncode
        _write_lines((workdir / "results.jsonl").read_text(encoding="utf-8").splitlines(), args.out)
    return 0


def _selftest(args) -> int:
    cells = [c.strip() for c in args.cells.split(",") if c.strip()] if args.cells else None
    if args.here:
        from . import selftest

        with _workdir(args.work) as workdir:
            report = selftest.selftest(args.target, workdir, cells=cells)
        print(selftest.render(report))
        if args.out:
            args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 0 if report["ok"] else 1

    with _workdir(args.work) as workdir:
        inner = ["selftest", "/target", "--out", "/work/report.json", "--work", "/work/run"]
        if cells:
            inner += ["--cells", ",".join(cells)]
        done = run.run_plan(run.image_plan(args.image, args.target, workdir, inner))
        sys.stdout.write(done.stdout)
        sys.stderr.write(done.stderr)
        report_file = workdir / "report.json"
        if args.out and report_file.exists():
            args.out.write_text(report_file.read_text(encoding="utf-8"), encoding="utf-8")
        return done.returncode


def _entries(manifest: Path) -> list[dict]:
    payload = json.loads(Path(manifest).read_text(encoding="utf-8"))
    return payload["entries"] if isinstance(payload, dict) else payload


def _write_lines(lines: list[str], out: Path | None) -> None:
    text = "".join(f"{line}\n" for line in lines)
    if out is None:
        sys.stdout.write(text)
    else:
        out.write_text(text, encoding="utf-8")


class _workdir:
    """The work dir: the one given, or a temporary one removed on the way out."""

    def __init__(self, given: Path | None):
        self.given = given
        self.temporary: str | None = None

    def __enter__(self) -> Path:
        if self.given is not None:
            self.given.mkdir(parents=True, exist_ok=True)
            return self.given
        self.temporary = tempfile.mkdtemp(prefix="lattice-")
        return Path(self.temporary)

    def __exit__(self, *_) -> None:
        if self.temporary is not None:
            shutil.rmtree(self.temporary, ignore_errors=True)


# MARK: - the map -


def _map(lattice: Lattice) -> dict:
    return {
        "root": str(lattice.root),
        "isas": [_row(lattice, isa) for isa in ISAS if isa in lattice.sources],
        "unmatched": [
            {"name": u.name, "file": u.file, "line": u.line, "reason": u.reason} for u in lattice.unmatched
        ],
    }


def _row(lattice: Lattice, isa: str) -> dict:
    cells = lattice.by_isa(isa)
    return {
        "isa": isa,
        "file": lattice.sources[isa].file,
        "native": cells[0].native if cells else isa in {"sse2", "avx2", "avx512"},
        "cells": len(cells),
        "impl": sum(1 for c in cells if c.kind == "impl"),
        "wrapper": sum(1 for c in cells if c.kind == "wrapper"),
        "body": sum(1 for c in cells if c.kind == "body"),
        "slots": sum(len(c.slots) for c in cells),
    }


def _table(lattice: Lattice) -> str:
    header = f"{'isa':<8}{'native':<8}{'cells':>6}{'impl':>6}{'wrapper':>9}{'body':>6}{'slots':>7}  file"
    lines = [f"lattice of {lattice.root}", header, "-" * len(header)]
    for row in _map(lattice)["isas"]:
        lines.append(
            f"{row['isa']:<8}{'yes' if row['native'] else 'no':<8}{row['cells']:>6}{row['impl']:>6}"
            f"{row['wrapper']:>9}{row['body']:>6}{row['slots']:>7}  {row['file']}"
        )
    if lattice.unmatched:
        lines.append("")
        lines.append("unmatched:")
        lines += [f"  {u.file}:{u.line} {u.name} — {u.reason}" for u in lattice.unmatched]
    else:
        lines.append("")
        lines.append("unmatched: none")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - the console script is the entry point
    raise SystemExit(main())
