#!/usr/bin/env python3
"""CodeGraphContext → the oracle lane's foreign edge file (ADR-101).

Two stages, so the conversion is testable without the tool installed:

    adapter.py dump    --db <kuzu dir> --out raw.json        # needs the tool's own `kuzu` (run with its venv's python)
    adapter.py convert --raw raw.json --repo <clone> --sha <sha> --version <tool version> --out edges.json

`dump` runs one Cypher query over the tool's Kuzu database (the embedded
backend its README offers: `codegraphcontext --db kuzudb --db-path <dir>
index <repo>`) and writes every CALLS row as the tool stored it: the
caller node's path (a Function or, for a module-level call, a File), the
edge's `line_number` (the call-site line), `confidence`,
`confidence_label` (EXTRACTED / INFERRED / …) and `resolution_tier`, and
the callee Function node's path and `line_number` (its declaration line).
Nothing is interpreted at this stage; the raw file is the fixture a
hand-read checks the conversion against.

`convert` makes each row one (site, callee) pair at the lane's grain:
absolute paths become repo-relative; the tool's `confidence_label` is the
edge's `label` (so the report splits by the tool's own ladder); the callee
kind is the node label lowercased, `method` when the Function carries a
`class_context`. HEURISTIC_CALLS — the tool's own separate table for
name-only guesses — is dumped and counted but not converted unless
`--include-heuristic` is passed; the cell record states the count.

Grain (C-94): the tool's declaration line is the tree-sitter node's first
line — the identifier's line for Go, Rust and plain functions, but the
annotation's line for a Java method under `@Override` and the decorator's
for decorated TS / Python. converter@2 reads the source and advances past
leading annotation lines (`declaration_line`); a cell graded at @1 charged
those rows to the tool.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

VERSION = "codegraphcontext-adapter@2"

DUMP_QUERY = """
MATCH (a)-[r:{rel}]->(b:Function)
RETURN label(a) AS caller_label, a.path AS caller_path, a.name AS caller_name,
       r.line_number AS site_line, r.confidence AS confidence, r.confidence_label AS confidence_label,
       r.resolution_tier AS resolution_tier, r.full_call_name AS full_call_name,
       b.path AS callee_path, b.line_number AS callee_line, b.name AS callee_name,
       b.class_context AS callee_class, b.is_dependency AS callee_is_dependency
"""


def dump(db: str, out: str) -> None:
    import kuzu  # the tool's own dependency; run with its venv

    con = kuzu.Connection(kuzu.Database(db, read_only=True))
    raw = {"database": os.path.abspath(db), "rows": {}}
    for rel in ("CALLS", "HEURISTIC_CALLS"):
        res = con.execute(DUMP_QUERY.format(rel=rel))
        cols = res.get_column_names()
        rows = []
        while res.has_next():
            rows.append(dict(zip(cols, res.get_next())))
        raw["rows"][rel] = rows
    Path(out).write_text(json.dumps(raw, indent=1, default=str) + "\n")
    print(f"dumped {', '.join(f'{k} {len(v)}' for k, v in raw['rows'].items())} → {out}", file=sys.stderr)


def declaration_line(repo: str, path: str, line: int) -> int:
    """D-O4 keys a declaration at its identifier's line. Both tools start a
    declaration at its node's first line, which for a Java method under an
    annotation (`@Override` on its own line), or a decorated TS / Python
    declaration, is the annotation's line. Read the source and advance
    past leading annotation / decorator lines (those starting with `@`,
    including a multi-line one until its bracket closes) to the first
    line that declares something — the identifier's line for these
    shapes. A converter@1 cell graded these as contradicted (C-94, found by
    the 2026-09-09 triage: 5 of 20 sampled CodeGraphContext rows and 1 of
    20 repowise rows were annotation lines). Unreadable source → the line
    as stored."""
    try:
        with open(os.path.join(repo, path), encoding="utf-8", errors="replace") as f:
            lines = f.read().split("\n")
    except OSError:
        return line
    i = line - 1
    if i < 0 or i >= len(lines):
        return line
    depth = 0
    while i < len(lines):
        t = lines[i].strip()
        if depth == 0 and not t.startswith("@") and t != "":
            break
        if t.startswith("@") or depth > 0:
            depth += t.count("(") - t.count(")")
            if depth < 0:
                depth = 0
        i += 1
    return i + 1 if i < len(lines) else line


def rel(path: str, repo: str) -> str | None:
    p = os.path.normpath(path)
    r = os.path.normpath(repo)
    if not p.startswith(r + os.sep):
        return None
    return p[len(r) + 1:].replace(os.sep, "/")


def convert(raw_path: str, repo: str, sha: str, version: str, out: str, include_heuristic: bool) -> None:
    raw = json.loads(Path(raw_path).read_text())
    edges, dropped = [], {"outside-repo": 0, "no-line": 0, "dependency-callee": 0}
    tables = ["CALLS"] + (["HEURISTIC_CALLS"] if include_heuristic else [])
    for table in tables:
        for row in raw["rows"].get(table, []):
            site_path, callee_path = rel(row["caller_path"], repo), rel(row["callee_path"], repo)
            if site_path is None or callee_path is None:
                dropped["outside-repo"] += 1
                continue
            if row.get("callee_is_dependency"):
                dropped["dependency-callee"] += 1
                continue
            if not row.get("site_line") or not row.get("callee_line"):
                dropped["no-line"] += 1
                continue
            label = str(row.get("confidence_label") or "unlabelled")
            if table == "HEURISTIC_CALLS":
                label = "heuristic:" + label
            edges.append({
                "site": f"{site_path}:{int(row['site_line'])}",
                "callee": f"{callee_path}:{declaration_line(repo, callee_path, int(row['callee_line']))}",
                "caller": str(row.get("caller_name") or ""),
                "kind": "method" if row.get("callee_class") else "function",
                "label": label,
            })
    edges.sort(key=lambda e: (e["site"], e["callee"]))
    doc = {
        "repo": os.path.abspath(repo), "sha": sha, "tool": "codegraphcontext", "version": version,
        "converter": VERSION,
        "notes": {
            "dropped": dropped,
            "heuristic_calls_in_db": len(raw["rows"].get("HEURISTIC_CALLS", [])),
            "heuristic_included": include_heuristic,
            "grain": "declaration line = the tool's node start line, advanced past leading annotation/decorator lines to the identifier's line (converter@2; @1 graded the annotation line)",
        },
        "edges": edges,
    }
    Path(out).write_text(json.dumps(doc, indent=1) + "\n")
    print(f"{len(edges)} edges (dropped {dropped}) → {out}", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump"); d.add_argument("--db", required=True); d.add_argument("--out", required=True)
    c = sub.add_parser("convert"); c.add_argument("--raw", required=True); c.add_argument("--repo", required=True)
    c.add_argument("--sha", required=True); c.add_argument("--version", required=True); c.add_argument("--out", required=True)
    c.add_argument("--include-heuristic", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "dump":
        dump(a.db, a.out)
    else:
        convert(a.raw, a.repo, a.sha, a.version, a.out, a.include_heuristic)


if __name__ == "__main__":
    main()
