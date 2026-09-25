"""`lattice` — read a target's kernel lattice, and grade bodies against it, from the command line.

    lattice map      <target> [--json]        the cells per ISA: counts by kind, slots, and what did not fit
    lattice task     <target> <cell-id>       the task record for one cell, as JSON
    lattice punch    <target> <cell-id>       that cell's file with its body replaced by the hole
    lattice grade    <target> <manifest.json> grade every entry in the manifest; one JSON line each
    lattice selftest <target> [--cells …]     the gate on the instruments (§5.5)

The first three read text and run nowhere in particular. **The last two compile and run the target's
code**, so they take `--here` (this process is already contained) or `--image NAME` (the default: build
a `podman run` plan and run this same CLI inside it, ADR-092/C-64). `--here` outside a container exits 2
with the refusal. `<target>` is a checkout's root — the directory holding `src/distance-*.c`.

A manifest is a JSON list of `{"id", "cell", "body"}` entries, or an object with them under `entries`;
`body` is a body's text, `{` to its matching `}`, or the word `"gold"`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from . import holes, run, task
from .cells import ISAS, Lattice, UnknownCell, build

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns the process exit code: 0, 1 for a self-test mismatch, 2 for a refusal."""
    parser = argparse.ArgumentParser(prog="lattice", description="sqlite-vector's kernel lattice, its cells and its graders")
    verbs = parser.add_subparsers(dest="verb", required=True)

    mapper = verbs.add_parser("map", help="the cells per ISA")
    mapper.add_argument("target", type=Path)
    mapper.add_argument("--json", action="store_true", help="the map as JSON rather than a table")

    tasker = verbs.add_parser("task", help="one cell's task record, as JSON")
    tasker.add_argument("target", type=Path)
    tasker.add_argument("cell", help="a cell id, <isa>/<type>/<metric>")

    puncher = verbs.add_parser("punch", help="one cell's file with its body punched out")
    puncher.add_argument("target", type=Path)
    puncher.add_argument("cell", help="a cell id, <isa>/<type>/<metric>")

    grader = verbs.add_parser("grade", help="grade a manifest of bodies")
    grader.add_argument("target", type=Path)
    grader.add_argument("manifest", type=Path, help="a JSON list of {id, cell, body} entries")
    grader.add_argument("--out", type=Path, help="write the results as JSONL here (default: stdout)")
    _where(grader)

    tester = verbs.add_parser("selftest", help="the gate on the instruments: the gold and its four mutants")
    tester.add_argument("target", type=Path)
    tester.add_argument("--cells", help="a comma-separated list of cell ids (default: every native cell)")
    tester.add_argument("--out", type=Path, help="write the report as JSON here; the table always prints")
    _where(tester)

    args = parser.parse_args(argv)

    if args.verb in ("grade", "selftest"):
        try:
            return _grade(args) if args.verb == "grade" else _selftest(args)
        except run.NotContained as refusal:
            print(f"lattice: {refusal}", file=sys.stderr)
            return 2
        except FileNotFoundError as missing:
            print(f"lattice: the plan could not be run ({missing}); is podman installed?", file=sys.stderr)
            return 2

    lattice = build(args.target)
    if args.verb == "map":
        print(json.dumps(_map(lattice), indent=2) if args.json else _table(lattice))
        return 0

    try:
        cell = lattice.get(args.cell)
    except UnknownCell:
        print(f"lattice: no cell {args.cell!r}; try `lattice map {args.target}`", file=sys.stderr)
        return 2

    if args.verb == "task":
        print(task.dumps(task.build(lattice, cell)))
    else:
        print(holes.punch(lattice.text(cell), cell), end="")
    return 0


def _where(verb: argparse.ArgumentParser) -> None:
    """The two ways a grading verb can run: here (contained already) or in the image."""
    verb.add_argument("--here", action="store_true", help="run in this process; refused outside a container")
    verb.add_argument("--image", default=run.IMAGE, help=f"the image to run in (default: {run.IMAGE})")
    verb.add_argument("--work", type=Path, help="the work dir (default: a fresh temporary one)")


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
        plan = run.image_plan(
            args.image, args.target, workdir,
            ["grade", "/target", "/work/manifest.json", "--out", "/work/results.jsonl", "--work", "/work/run"],
        )
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
