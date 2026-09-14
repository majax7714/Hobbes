#!/usr/bin/env python3
"""repowise → the oracle lane's foreign edge file (ADR-101).

    adapter.py dump    --db <repo>/.repowise/wiki.db --out raw.json     # sqlite3, stdlib
    adapter.py convert --raw raw.json --sha <sha> --version <tool version> --out edges.json

`repowise init --no-prose -y <repo>` (the README's keyless path) writes
`.repowise/wiki.db`. `dump` copies two tables as stored: `graph_edges`
rows with `edge_type = 'calls'` — a caller symbol id, a callee symbol id,
`confidence`, `resolution_origin` (the tool's own ladder: same_package,
receiver_typed_same_file, package_alias, …) and `call_lines_json`, the
call-site lines in the caller's file — and `wiki_symbols`, which maps a
symbol id (`file.go::Type::Method`) to its `file_path`, `kind` and
`start_line`. Nothing is interpreted at this stage.

`convert` makes one (site, callee) pair per call line: the site is the
caller symbol's file at that line, the callee the target symbol's file at
its `start_line`; `resolution_origin` becomes the edge's `label` and the
symbol's `kind` its kind. A call edge whose target symbol is not in
`wiki_symbols` (an external or unresolved target) is dropped and counted.

Grain (C-94): `start_line` is the symbol's first line as the tool's parser
saw it — the annotation's line for a Java method under `@Override`, the
decorator's for decorated TS / Python. converter@2 reads the source and
advances past leading annotation lines (`declaration_line`); a cell
graded at @1 charged those rows to the tool.

Grain (C-95's C face, ADR-101's 2026-09-14 (later) amendment): the first
foreign C cells found the tool storing a function-like macro as kind
`function`, so each such edge graded against the callee clang saw in the
expansion. converter@3 reads the declared line's source and reads a
leading `#define` as kind `macro` (`declared_kind`), which the lane
already excludes for a `macro` kind; a cell graded at @2 charged those
rows to the tool.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

VERSION = "repowise-adapter@3"


def dump(db: str, out: str) -> None:
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    edges = [dict(r) for r in con.execute(
        "SELECT source_node_id, target_node_id, edge_type, confidence, hint_source, resolution_origin, call_lines_json "
        "FROM graph_edges WHERE edge_type = 'calls' ORDER BY source_node_id, target_node_id")]
    symbols = [dict(r) for r in con.execute(
        "SELECT symbol_id, file_path, name, qualified_name, kind, start_line, end_line, language FROM wiki_symbols ORDER BY symbol_id")]
    repo = [dict(r) for r in con.execute("SELECT name, local_path, head_commit FROM repositories")]
    Path(out).write_text(json.dumps({"database": db, "repositories": repo, "edges": edges, "symbols": symbols}, indent=1) + "\n")
    print(f"dumped {len(edges)} call edges, {len(symbols)} symbols → {out}", file=sys.stderr)


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


def declared_kind(repo: str, path: str, line: int, stored: str) -> str:
    """converter@3 (ADR-101's 2026-09-14 amendment, C-95's C face): the
    first foreign C cells found the tool storing a function-like macro —
    `#define can_read(buffer, size) …` — as kind `function`, so every
    such edge graded against the callee clang saw in the expansion. Read
    the source at the (already advanced) declaration line; if its
    stripped text begins with `#define`, the callee is a macro and the
    lane's existing exclusion applies as it does to Hobbes' own. A
    `#define` does not occur outside C / C++. Unreadable source → the
    kind as already read."""
    try:
        with open(os.path.join(repo, path), encoding="utf-8", errors="replace") as f:
            lines = f.read().split("\n")
    except OSError:
        return stored
    if 1 <= line <= len(lines) and lines[line - 1].strip().startswith("#define"):
        return "macro"
    return stored


def convert(raw_path: str, sha: str, version: str, out: str, repo: str = "") -> None:
    raw = json.loads(Path(raw_path).read_text())
    sym = {s["symbol_id"]: s for s in raw["symbols"]}
    edges, dropped = [], {"unknown-caller": 0, "unknown-callee": 0, "no-call-lines": 0}
    for e in raw["edges"]:
        src, dst = sym.get(e["source_node_id"]), sym.get(e["target_node_id"])
        if src is None:
            dropped["unknown-caller"] += 1
            continue
        if dst is None:
            dropped["unknown-callee"] += 1
            continue
        lines = json.loads(e.get("call_lines_json") or "[]")
        if not lines:
            dropped["no-call-lines"] += 1
            continue
        repo_path = repo or (raw["repositories"][0]["local_path"] if raw.get("repositories") else "")
        callee_line = declaration_line(repo_path, dst["file_path"], int(dst["start_line"]))
        kind = declared_kind(repo_path, dst["file_path"], callee_line, str(dst.get("kind") or ""))
        for line in lines:
            edges.append({
                "site": f"{src['file_path']}:{int(line)}",
                "callee": f"{dst['file_path']}:{callee_line}",
                "caller": src["symbol_id"],
                "kind": kind,
                "label": str(e.get("resolution_origin") or "unlabelled"),
            })
    edges.sort(key=lambda x: (x["site"], x["callee"]))
    repo = repo or (raw["repositories"][0]["local_path"] if raw.get("repositories") else "")
    doc = {"repo": repo, "sha": sha, "tool": "repowise", "version": version, "converter": VERSION,
           "notes": {"dropped": dropped, "grain": "declaration line = wiki_symbols.start_line advanced past leading annotation/decorator lines to the identifier's line (converter@2; @1 graded the annotation line)"
                     "; a callee whose declared line begins with #define is kind macro, which the lane excludes (converter@3; @2 graded it as stored)"},
           "edges": edges}
    Path(out).write_text(json.dumps(doc, indent=1) + "\n")
    print(f"{len(edges)} edges (dropped {dropped}) → {out}", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump"); d.add_argument("--db", required=True); d.add_argument("--out", required=True)
    c = sub.add_parser("convert"); c.add_argument("--raw", required=True); c.add_argument("--sha", required=True)
    c.add_argument("--version", required=True); c.add_argument("--out", required=True)
    c.add_argument("--repo", default="", help="the clone (to read declaration lines); default: the path the tool recorded")
    a = ap.parse_args(argv)
    if a.cmd == "dump":
        dump(a.db, a.out)
    else:
        convert(a.raw, a.sha, a.version, a.out, a.repo)


if __name__ == "__main__":
    main()
