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

Grain the converter cannot repair (C-94): `start_line` is the symbol's
first line as the tool's parser saw it; for a decorated TS or Python
declaration that is the decorator's line where the oracle keys the
identifier's. Such a cell must say so.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

VERSION = "repowise-adapter@1"


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


def convert(raw_path: str, sha: str, version: str, out: str) -> None:
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
        for line in lines:
            edges.append({
                "site": f"{src['file_path']}:{int(line)}",
                "callee": f"{dst['file_path']}:{int(dst['start_line'])}",
                "caller": src["symbol_id"],
                "kind": str(dst.get("kind") or ""),
                "label": str(e.get("resolution_origin") or "unlabelled"),
            })
    edges.sort(key=lambda x: (x["site"], x["callee"]))
    repo = raw["repositories"][0]["local_path"] if raw.get("repositories") else ""
    doc = {"repo": repo, "sha": sha, "tool": "repowise", "version": version, "converter": VERSION,
           "notes": {"dropped": dropped, "grain": "declaration line = wiki_symbols.start_line (the symbol's first line as parsed)"},
           "edges": edges}
    Path(out).write_text(json.dumps(doc, indent=1) + "\n")
    print(f"{len(edges)} edges (dropped {dropped}) → {out}", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump"); d.add_argument("--db", required=True); d.add_argument("--out", required=True)
    c = sub.add_parser("convert"); c.add_argument("--raw", required=True); c.add_argument("--sha", required=True)
    c.add_argument("--version", required=True); c.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "dump":
        dump(a.db, a.out)
    else:
        convert(a.raw, a.sha, a.version, a.out)


if __name__ == "__main__":
    main()
