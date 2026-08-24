"""Pack: Go CLI entry points from ``package main`` (C-14).

The third CLI source, and the one the register's own example named: this
repo's four binaries are ``package main`` directories under ``go/cmd/``,
and until this pack they were absent from ``interfaces.json`` while two
Python console scripts were listed — an inventory that read as complete
and was not (C-14, lifted with this pack).

A Go binary is a directory whose package is ``main`` and whose files
declare ``func main``; ``go build`` names the binary after the
directory. Read from the lane's facts, never re-parsed (ADR-035): the
Go layer already records each file's package clause and symbols.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from hobbes.extract.packs.base import Pack, PackContext, PackResult
from hobbes.extract.schema import SYNTACTIC


def _entries(go: dict) -> list[dict]:
    entries = []
    for parsed in go["files"]:
        if parsed.package != "main":
            continue
        if not any(
            s["kind"] == "function" and s["name"] == "main" for s in parsed.symbols
        ):
            continue
        parent = PurePosixPath(parsed.path).parent
        # `go build` names the binary after the package directory. A
        # main.go at the repo root has no directory to take a name from;
        # the file stem is the honest constant (the repo's checkout
        # directory name would vary per clone, which P1 forbids).
        name = parent.name if str(parent) not in ("", ".") else PurePosixPath(parsed.path).stem
        entries.append({"name": name, "target": parsed.path, "source": parsed.path})
    return sorted(entries, key=lambda e: (e["source"], e["name"]))


def _applies(ctx: PackContext) -> bool:
    return ctx.go is not None


def _run(ctx: PackContext) -> PackResult:
    return PackResult(cli_entry_points=_entries(ctx.go))


PACK = Pack(name="cli-go", tier=SYNTACTIC, applies=_applies, run=_run)
