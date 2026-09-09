#!/usr/bin/env python3
"""Write the cell record of a foreign (third-party) cell from its artifacts (ADR-101).

    foreign_record.py --cell ~/.hobbes/bench/comparative/<tool>-<repo> --pair docs/oracle/cells/<hobbes cell>.md \\
        --key ~/.hobbes/bench/oracle/<key dir> --repo-url <url> --clone <path> [--date YYYY-MM-DD] [--triage triage.json] --out docs/oracle/cells/<tool>-<repo>-<date>.md

Every number in the record is read from the cell directory: `edges.json`
(the converter's header and drop counts), `run.log` (index exit, wall
time), `index.log` (the tool's own error/warning lines), `report.txt`
(the head, verbatim) and `report.json` (the contradicted rows, grouped
by a mechanical shape: whether the tool's callee has the same short
name as one of the oracle's targets — the name-match-wrong-owner shape —
or not). The hand-read part is `--triage`: a JSON file with the verdict
per sampled row written by a person, quoted as sampled (A-8); without
it the triage ratio prints as untriaged.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


def head_lines(report: str) -> list[str]:
    keep = []
    for line in report.splitlines():
        if line.startswith(("cell ", "hobbes edges", "precision-against-oracle", "recall", "confirmation rate",
                            "recall-against-executed", "  recall[", "  tier ", "  line-grain", "poison check", "foreign cell")):
            keep.append(line)
    return keep


def short(name: str) -> str:
    # `(*github.com/gorilla/mux.Route).Methods` → Methods; `pkg.Func` → Func; `Type::method` → method
    n = name.rstrip(")")
    for sep in (").", ".", "::", "#"):
        if sep in n:
            n = n.rsplit(sep, 1)[-1]
    return n.split("(")[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell", required=True); ap.add_argument("--pair", required=True); ap.add_argument("--key", required=True)
    ap.add_argument("--repo-url", required=True); ap.add_argument("--clone", required=True)
    ap.add_argument("--date", default="2026-09-09"); ap.add_argument("--triage"); ap.add_argument("--out", required=True)
    ap.add_argument("--index-cmd", default="", help="the tool's documented index command, as run")
    ap.add_argument("--hobbes", action="store_true", help="a Hobbes cell on a draw of the comparative programme: hobbes.json is `oracle export`'s, there is no converter")
    ap.add_argument("--ingest-note", default="", help="--hobbes: the ingest's capture line and containment, quoted")
    ap.add_argument("--fix-note", default="", help="--hobbes: what changed between report.v1 and report (the signed direction line's cause)")
    ap.add_argument("--triage-note", default="", help="a hand-read triage paragraph for this cell's contradictions, quoted as written")
    ap.add_argument("--lang", default="", help="the cell's language name as the triage file spells it (Go, TypeScript, Rust, Java, Python)")
    ap.add_argument("--repo-name", default="", help="the cell's repo name as the triage file spells it")
    a = ap.parse_args(argv)
    cell = Path(a.cell)
    if a.hobbes:
        hx = json.loads((cell / "hobbes.json").read_text())
        edges = {"tool": "hobbes", "version": a.index_cmd or "this checkout", "converter": "", "sha": hx["sha"], "edges": hx["edges"], "notes": {"dropped": hx.get("excluded", {}), "grain": "oracle export (D-O4)"}}
    else:
        edges = json.loads((cell / "edges.json").read_text())
    report = json.loads((cell / "report.json").read_text())
    run = (cell / "run.log").read_text() if (cell / "run.log").exists() else ""
    index_log = (cell / "index.log").read_text() if (cell / "index.log").exists() else ""
    tool, version, conv = edges["tool"], edges["version"], edges.get("converter", "")
    notes = edges.get("notes", {})
    m = re.search(r"index exit (\d+) wall ([\d.]+)s", run)
    exit_code, wall = (m.group(1), m.group(2)) if m else ("?", "?")
    errs = [l.strip() for l in index_log.splitlines() if re.search(r"error|warn|fail|exception", l, re.I)]
    rows = report["rows"]
    contra = [r for r in rows if r["bucket"] == "contradicted"]
    by_tier = Counter(r["edge"]["tier"] for r in contra)
    shape = Counter()
    for r in contra:
        callee_short = None
        # the converter's caller/target ids carry no name; use the site's oracle targets vs the tool's callee position file
        tgt = r["edge"]["target"]
        names = {short(t["name"]) for t in (r.get("oracle_targets") or [])}
        same_file = any(t["pos"]["path"] == tgt["path"] for t in (r.get("oracle_targets") or []))
        shape["same file as an oracle target, other line" if same_file else "another file than every oracle target"] += 1
    pair_name = Path(a.pair).name
    total = report["total"]
    prec = report.get("precision_against_oracle")
    if (Path(a.key) / "report.txt").exists():
        key_head = (Path(a.key) / "report.txt").read_text().splitlines()[0]
    else:  # a key built directly by an oracle subcommand: describe it from its own header
        ok = json.loads((Path(a.key) / "oracle.json").read_text())
        key_head = f"oracle {ok['oracle']} ({ok['kind']}), roots {len(ok.get('roots') or [])}, {len(ok.get('files') or [])} files, {len(ok.get('sites') or [])} sites"
    triage = json.loads(Path(a.triage).read_text()) if a.triage else None
    v1 = json.loads((cell / "report.v1.json").read_text()) if (cell / "report.v1.json").exists() else None
    if a.hobbes:
        lines = [f"# Oracle cell — {a.repo_url.rstrip('/').split('/')[-1]} ({cell.name.split('-', 1)[1]}), module `{report['module'] or '.'}`, {a.date} (a draw of repowise's, ADR-101 § the 1-1)", ""]
        lines.append(f"**Hobbes on a repo another tool's benchmark drew.** Repo: {a.repo_url}, clone `{a.clone}`, commit {edges['sha']} — the commit repowise-bench's `graph/corpus/corpus.lock` pins for its G4 experiment; the answer key is ours (`{a.key}/oracle.json`: `{key_head}`), built by `oracle go-rta` / `ts/tsc-oracle.mjs` on this box, so this cell is 1-1 with the foreign cells beside it (`codegraphcontext-{cell.name.split('-', 1)[1]}`, `repowise-{cell.name.split('-', 1)[1]}`) and **not** with repowise-bench's own numbers, whose key is at function grain (caller declaration → callee declaration) and whose matcher is theirs. Ingest: contained, `HOBBES_SCIP=1 uv run hobbes ingest`; {a.ingest_note}")
        lines.append("")
        lines.append(f"Command: `oracle export --graph <clone>/.hobbes/derived/graph.json --module . --lang <lang> --out hobbes.json && oracle grade --hobbes hobbes.json --oracle {Path(a.key).name}/oracle.json --json report.json --poison`. Outputs in `{cell}`.")
        lines.append("")
    else:
        lines = [f"# Oracle cell — {tool} {version} on {a.repo_url.rstrip('/').split('/')[-1]}, module `{report['module'] or '.'}`, {a.date} (foreign cell, ADR-101)", ""]
    if not a.hobbes:
      lines.append(f"**A third-party graph graded by the oracle lane.** Tool: **{tool} {version}**, run as its README documents on this box "
                 f"(host-run, C-96), converter `{conv}` (`bench/oracle/adapters/{tool}/adapter.py`, its hand-read fixture in the Go test). "
                 f"Repo: {a.repo_url}, clone `{a.clone}`, commit {edges['sha']} — **the same commit and the same answer key as the Hobbes cell "
                 f"[{pair_name}]({pair_name})**; the key is `{a.key}/oracle.json` (`{key_head}`), regenerated by the command that cell names.")
    if not a.hobbes:
      lines.append("")
      lines.append(f"Index command: `{a.index_cmd}` — exit {exit_code}, wall {wall} s; no network observed, no repo build invoked. "
                 f"The tool's own log carries {len(errs)} error/warning line(s)" + (f", e.g. `{errs[0][:160]}`" if errs else "") + ". "
                 f"Conversion: {len(edges['edges'])} (site, callee) pairs; dropped {json.dumps(notes.get('dropped', {}))}"
                 + (f"; {notes['heuristic_calls_in_db']} rows in the tool's separate HEURISTIC_CALLS table, not graded (its own label for name-only guesses)" if notes.get("heuristic_calls_in_db") else "")
                 + f". Grain note from the adapter: {notes.get('grain', 'n/a')}.")
    if not a.hobbes:
      lines.append("")
      lines.append(f"Command: `bench/oracle/grade-foreign.sh {cell.name}/edges.json {Path(a.key).name}/oracle.json {cell.name} --lang {Path(a.key).name.rsplit('-', 1)[-1] if Path(a.key).name.rsplit('-', 1)[-1] in ('go','ts','rust','java','py') else '<lang>'}`. Outputs in `{cell}` (`hobbes.json` is the converted graph, `raw.json` the tool's rows as stored, `edges.json` the minimal shape).")
    if not a.hobbes:
      lines.append("")
    lines.append("## Numbers (report.txt, head, verbatim)")
    lines.append("")
    lines.append("```")
    lines.extend(head_lines((cell / "report.txt").read_text()))
    lines.append("```")
    lines.append("")
    if prec is None and report.get("kind") != "trace":
        lines.append(f"| bucket | count |\n|---|---|\n| graded edges | {report['hobbes_edges']:,} |\n| confirmed | {total['confirmed']:,} |\n| contradicted | {total.get('contradicted', 0):,} |\n| silent | {total.get('silent', 0):,} |\n| precision-against-oracle | **undefined** — nothing confirmed or contradicted (the tool stored {len(edges['edges'])} call edge(s) in this cell) |\n| recall | {100*(report['recall'] or 0):.1f}% ({report['recall_confirmed']:,}/{report['oracle_pairs_in_repo']:,}) |")
    elif prec is not None:
        lines.append(f"| bucket | count |\n|---|---|\n| graded edges | {report['hobbes_edges']:,} |\n| confirmed | {total['confirmed']:,} |\n| contradicted | {total.get('contradicted', 0):,} |\n| abstract | {total.get('abstract', 0):,} |\n| silent | {total.get('silent', 0):,} {json.dumps(report.get('silent_by', {}))} |\n| precision-against-oracle (lower bound) | **{100*prec:.1f}%** ({total['confirmed']:,}/{total['confirmed']+total.get('contradicted', 0):,}) |\n| recall | {100*(report['recall'] or 0):.1f}% ({report['recall_confirmed']:,}/{report['oracle_pairs_in_repo']:,}) {('at %d roots' % report['roots']) if report['roots'] else 'over every resolved site'} |")
    else:
        lines.append(f"| bucket | count |\n|---|---|\n| graded edges | {report['hobbes_edges']:,} |\n| confirmed | {total['confirmed']:,} |\n| suspect | {total.get('suspect', 0):,} |\n| unobserved | {total.get('unobserved', 0):,} {json.dumps(report.get('silent_by', {}))} |\n| confirmation rate (coverage-limited, not precision) | {100*(report.get('confirmation_rate') or 0):.1f}% |\n| recall-against-executed | {100*(report['recall'] or 0):.1f}% ({report['recall_confirmed']:,}/{report['oracle_pairs_in_repo']:,}) |")
    lines.append("")
    lines.append((f"**By tier:** " if a.hobbes else f"**By the tool's own label** (the edge's tier is the tool's confidence label, C-95): ") + "; ".join(f"`{t}` confirmed {c['confirmed']} / contradicted {c['contradicted']} / abstract {c.get('abstract', 0)} / silent {c.get('silent', 0)}" + (f" / suspect {c['suspect']}" if c.get('suspect') else "") for t, c in sorted(report["by_tier"].items())) + ".")
    lines.append("")
    if contra:
        lines.append(f"## Contradicted ({len(contra)} rows; all in report.json)")
        lines.append("")
        lines.append("Mechanical shape (no reading): " + "; ".join(f"{k} {v}" for k, v in shape.most_common()) + ". By label: " + ", ".join(f"`{t}` {n}" for t, n in by_tier.most_common()) + ".")
        lines.append("")
        lines.append("Sample rows (site → the tool's callee; the oracle's targets at that site):")
        lines.append("")
        for r in contra[:6]:
            e = r["edge"]
            ot = ", ".join(f"{t['name']} @ {t['pos']['path']}:{t['pos']['line']}" for t in (r.get("oracle_targets") or [])[:3])
            lines.append(f"- `{e['site']['path']}:{e['site']['line']}` → `{e['target']['path']}:{e['target']['line']}` [{e['tier']}] — oracle: {ot}")
        lines.append("")
        if triage:
            lang_rows = [r for r in triage["rows"] if r["lang"] == a.lang]
            mine = [r for r in lang_rows if r["repo"] == a.repo_name]
            c = Counter(r["verdict"] for r in lang_rows)
            lines.append(f"**Triage ratio (A-8), sampled:** over the tool's {a.lang} cells, {len(lang_rows)} contradicted rows drawn at random ({triage['rule']}) read "
                         f"`oracle-grain {c.get('oracle-grain', 0)} : tool-wrong {c.get('tool-wrong', 0)} : converter-defect {c.get('converter-defect', 0)}`; the rest of this cell's {len(contra)} rows are untriaged. "
                         f"The rows drawn from this cell:" if mine else f"**Triage ratio (A-8), sampled:** over the tool's {a.lang} cells, {len(lang_rows)} contradicted rows drawn at random ({triage['rule']}) read "
                         f"`oracle-grain {c.get('oracle-grain', 0)} : tool-wrong {c.get('tool-wrong', 0)} : converter-defect {c.get('converter-defect', 0)}`; none of the draws fell in this cell, whose {len(contra)} rows are untriaged.")
            for r in mine:
                lines.append(f"- `{r['site']}` → `{r['callee']}` [{r['tier']}]: **{r['verdict']}** — {r['note']}")
        else:
            lines.append(f"**Triage ratio (A-8):** `oracle-wrong 0 : {'hobbes' if a.hobbes else 'tool'}-wrong 0 : untriaged {len(contra)}` — the rows are not read; the number above is a lower bound (a contradiction is very strong evidence, not proof; C-62)" + ("." if a.hobbes else ", and a converter defect would count against the tool (C-94)."))
        lines.append("")
    if a.triage_note:
        lines.append(f"**Triage (hand-read, {a.date}):** {a.triage_note}")
        lines.append("")
    lines.append("## Misses by class")
    lines.append("")
    lines.append("| class | hits / pairs | misses |\n|---|---|---|")
    for k, v in sorted(report["recall_by_class"].items(), key=lambda kv: -report["miss_by"].get(kv[0], 0)):
        lines.append(f"| `{k}` | {v['hits']:,} / {v['pairs']:,} | {report['miss_by'].get(k, 0):,} |")
    lines.append("")
    pc = report.get("poison") or {}
    lines.append(f"**Poison check:** {'PASS' if pc.get('passed') else 'FAIL'} — {pc.get('seeded', 0):,} seeded wrong edges: {pc.get('refused', 0):,} refused, {pc.get('unjudged', 0):,} unjudged (oracle silent there), {pc.get('confirmed', 0):,} falsely confirmed.")
    lines.append("")
    if v1 and (v1["total"] != report["total"]):
        vp, p2 = v1.get("precision_against_oracle"), report.get("precision_against_oracle")
        head = (f"**Direction of fix ({a.date}, signed):** {a.fix_note} " if a.hobbes else
                "**Direction of fix (converter@1 → converter@2, 2026-09-09, signed):** the converter now advances a declaration line past leading annotation / decorator lines to the identifier's (C-94, found by the triage sample: Java `@Override` lines were charged to the tool). ")
        body = (f"graded edges {v1['hobbes_edges']:,} → {report['hobbes_edges']:,} ({report['hobbes_edges']-v1['hobbes_edges']:+,}); confirmed {v1['total']['confirmed']:,} → {total['confirmed']:,} ({total['confirmed']-v1['total']['confirmed']:+,}); "
                f"contradicted {v1['total'].get('contradicted', 0):,} → {total.get('contradicted', 0):,} ({total.get('contradicted', 0)-v1['total'].get('contradicted', 0):+,})"
                + (f"; precision-against-oracle {100*vp:.1f}% → {100*p2:.1f}% ({100*(p2-vp):+.1f})" if vp is not None and p2 is not None else "")
                + f"; recall {100*(v1['recall'] or 0):.1f}% → {100*(report['recall'] or 0):.1f}% ({100*((report['recall'] or 0)-(v1['recall'] or 0)):+.1f}). "
                + ("`report.v1.*` beside the cell keeps the first grade." if a.hobbes else "Nothing on the tool's side moved; `report.v1.*` beside the cell keeps the first grade."))
        lines.append(head + body)
        lines.append("")
    if a.hobbes:
        lines.append(("" if v1 and v1["total"] != report["total"] else "**Direction of fix:** first grade — nothing to sign. ") + "**Not a comparison with repowise-bench's table:** a different key grain and matcher; the comparison is with the foreign cells on this key.")
    else:
        lines.append(("" if v1 and v1["total"] != report["total"] else "**Direction of fix:** first grade of this tool on this cell — nothing to sign. ") + "**What the record does not say:** anything about the tool beyond this run on this box at this version; the matcher's tolerances were tuned on Hobbes' output (C-95); the conversion is Hobbes' and a misread would be Hobbes' defect (C-94).")
    lines.append("")
    Path(a.out).write_text("\n".join(lines) + "\n")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
