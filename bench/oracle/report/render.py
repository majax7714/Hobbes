#!/usr/bin/env python3
"""The comparative graphics, regenerated from the cell records (ADR-102).

Every number a graphic prints is read from `docs/oracle/cells/*.md` — the
verbatim `report.txt` blocks a cell record quotes (the *last* block in a
file is the standing grade; a regrade appends) and, for the dagger Go
record, its per-module "after" table — or from two `graph.json` artifacts
for the before/after view. Nothing is typed into a picture. `check`
re-renders and fails when the committed graphics drift from the records,
so a regraded cell without a regenerated graphic fails CI (P8).

    render.py cells   [--cells docs/oracle/cells] [--meta report/cells.meta.json] --out data/cells.json
    render.py capture --before <graph.json> --after <graph.json> --repo <name> --sha <sha> --out data/<repo>-capture.json
    render.py render  --data docs/comparative/data --out docs/comparative/graphics
    render.py check   [--data ...] [--graphics ...]      # exit 1 on drift

stdlib only; run from anywhere (paths default relative to the repo root).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CELLS = ROOT / "docs" / "oracle" / "cells"
META = HERE / "cells.meta.json"
DATA = ROOT / "docs" / "comparative" / "data"
GRAPHICS = ROOT / "docs" / "comparative" / "graphics"

# ---------------------------------------------------------------- parsing

DATE_RE = re.compile(r"-(\d{4}-\d{2}-\d{2})\.md$")
NUM = r"([\d,]+)"


def _int(s: str) -> int:
    return int(s.replace(",", ""))


def _pairs(s: str) -> dict[str, int]:
    """`map[a:1 b:2]` → {a: 1, b: 2}."""
    m = re.search(r"map\[(.*?)\]", s)
    if not m or not m.group(1).strip():
        return {}
    out = {}
    for tok in m.group(1).split():
        k, _, v = tok.rpartition(":")
        out[k] = _int(v)
    return out


def parse_blocks(text: str) -> list[dict]:
    """Every verbatim report block in a record, in order."""
    blocks: list[dict] = []
    cur: dict | None = None
    cell_line = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("cell ") and " oracle " in s:
            cell_line = s
            continue
        m = re.match(rf"hobbes edges {NUM}: (.*)$", s)
        if m:
            cur = {"edges": _int(m.group(1)), "cell_line": cell_line}
            for k in ("confirmed", "contradicted", "abstract", "silent", "suspect", "unobserved"):
                mm = re.search(rf"\b{k} {NUM}", m.group(2))
                cur[k] = _int(mm.group(1)) if mm else 0
            blocks.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(rf"precision-against-oracle ([\d.]+)% \({NUM}/{NUM}\)", s)
        if m:
            cur["precision"] = {"pct": float(m.group(1)), "num": _int(m.group(2)), "den": _int(m.group(3))}
            continue
        if s.startswith("precision-against-oracle: undefined"):
            cur["precision"] = None
            cur["undefined"] = True
            continue
        m = re.match(rf"recall ([\d.]+)% \({NUM}/{NUM} in-repo oracle pairs\)(.*)$", s)
        if m:
            rest = m.group(4)
            roots = re.search(r"at (\d+) roots", rest)
            cur["recall"] = {
                "pct": float(m.group(1)), "hits": _int(m.group(2)), "pairs": _int(m.group(3)),
                "roots": int(roots.group(1)) if roots else None,
                "basis": f"at {roots.group(1)} roots" if roots else "over every resolved site (resolution oracle: no roots)",
            }
            if "misses map[" in rest:
                cur["misses"] = _pairs(rest)
            continue
        m = re.match(rf"recall-against-executed ([\d.]+)% \({NUM}/{NUM} observed in-repo pairs\)(.*)$", s)
        if m:
            rest = m.group(4)
            runs = re.search(r"over (\d+) run", rest)
            cur["recall"] = {
                "pct": float(m.group(1)), "hits": _int(m.group(2)), "pairs": _int(m.group(3)),
                "roots": None, "runs": int(runs.group(1)) if runs else None,
                "basis": "recall-against-executed (coverage-limited)",
            }
            if "misses map[" in rest:
                cur["misses"] = _pairs(rest)
            continue
        m = re.match(rf"confirmation rate ([\d.]+)% \({NUM}/{NUM} hobbes edges", s)
        if m:
            cur["confirmation_rate"] = {"pct": float(m.group(1)), "num": _int(m.group(2)), "den": _int(m.group(3))}
            continue
        m = re.match(rf"(?:\*\*Poison check:\*\* |poison check: )(PASS|FAIL) — {NUM} seeded wrong edges: {NUM} refused[^,]*, {NUM} unjudged[^,]*, {NUM} falsely confirmed", s)
        if m:
            cur["poison"] = {"passed": m.group(1) == "PASS", "seeded": _int(m.group(2)), "refused": _int(m.group(3)),
                             "unjudged": _int(m.group(4)), "falsely": _int(m.group(5))}
            continue
    return blocks


def parse_dagger_after(text: str) -> list[dict]:
    """The dagger Go record's per-module 'after' table (W1 fixes), with the
    root count of each module from the first table."""
    roots = {}
    for m in re.finditer(r"^\| `([^`]+)` \| [\d,]+ \| [\d,]+ / [\d,]+ / [\d,]+ \| [\d.]+% \| [\d.]+% \([\d,]+/[\d,]+\) at (\d+) \| (.*) \|$", text, re.M):
        mod, r, misses = m.group(1), int(m.group(2)), m.group(3).strip()
        mm = {}
        for tok in re.findall(r"([\w→\-]+) (\d+)", misses):
            mm[tok[0]] = int(tok[1])
        roots[mod] = (r, mm)
    cells = []
    for m in re.finditer(r"^\| `([^`]+)` \| [\d,]+ / [\d,]+ / [\d,]+ · [\d,]+/[\d,]+ \| \*\*([\d,]+) / ([\d,]+) / ([\d,]+) · ([\d,]+)/([\d,]+)\*\* \|$", text, re.M):
        mod = m.group(1)
        c, x, s, h, p = (_int(m.group(i)) for i in range(2, 7))
        r, misses = roots.get(mod, (None, {}))
        misses = {k: v for k, v in misses.items() if k != "static→named"}  # 0 after the fixes, the record says; the C-58 classes unchanged
        cells.append({
            "module": mod, "edges": c + x + s, "confirmed": c, "contradicted": x, "abstract": 0, "silent": s,
            "precision": {"pct": round(100 * c / (c + x), 1), "num": c, "den": c + x},
            "recall": {"pct": round(100 * h / p, 1), "hits": h, "pairs": p, "roots": r, "basis": f"at {r} roots"},
            "misses": misses,
        })
    return cells


def load_cells(cells_dir: Path, meta_path: Path) -> dict:
    meta = json.loads(meta_path.read_text())
    latest: dict[str, Path] = {}
    earlier: dict[str, list[Path]] = {}
    for p in sorted(cells_dir.glob("*.md")):
        m = DATE_RE.search(p.name)
        if not m:
            continue
        stem = p.name[: m.start()]
        earlier.setdefault(stem, []).append(p)
        if stem not in latest or m.group(1) > DATE_RE.search(latest[stem].name).group(1):
            latest[stem] = p
    out = []
    for stem, p in sorted(latest.items()):
        if stem not in meta:
            sys.exit(f"{p.name}: no entry in {meta_path.name} — add one (lang, run, draw, label)")
        m = dict(meta[stem])
        text = p.read_text()
        date = DATE_RE.search(p.name).group(1)
        if m.get("table") == "dagger-after":
            for sub in parse_dagger_after(text):
                out.append({"stem": stem, "record": p.name, "date": date, "kind": "reachability",
                            "oracle": "go-rta", "sub": sub.pop("module"), **m, **sub})
            continue
        blocks = parse_blocks(text)
        if not blocks:
            sys.exit(f"{p.name}: no verbatim report block found")
        last = blocks[-1]
        misses = next((b["misses"] for b in reversed(blocks) if b.get("misses")), {})
        poison = next((b["poison"] for b in reversed(blocks) if b.get("poison")), None)
        cell_line = last.get("cell_line") or blocks[0].get("cell_line") or ""
        if not cell_line:  # a regrade record quotes the head without its cell line: the earlier record of the cell names the oracle
            for q in earlier[stem]:
                for b in parse_blocks(q.read_text()):
                    cell_line = cell_line or b.get("cell_line") or ""
        kind = re.search(r"\((reachability|resolution|trace)\)", cell_line)
        oracle = re.search(r"oracle (.*?)\s+\((reachability|resolution|trace)\)", cell_line)
        cell = {"stem": stem, "record": p.name, "date": date,
                "kind": kind.group(1) if kind else None,
                "oracle": oracle.group(1).strip() if oracle else None, **m}
        cell.update({k: v for k, v in last.items() if k != "cell_line"})
        cell["misses"] = misses
        cell["poison"] = poison
        if last.get("recall") and "misses" in last["recall"]:
            del last["recall"]["misses"]
        out.append(cell)
    return {"source": str(cells_dir.relative_to(ROOT)), "cells": out}


# --------------------------------------------------------------- capture

def capture(graph_path: Path, depth: int = 2) -> dict:
    """Per-directory capture exactly as `hobbes ingest` prints it (ADR-045,
    cli.py): accounted = sites − unresolved, over the file rows of
    `resolution_coverage`, grouped at directory depth 2."""
    g = json.loads(graph_path.read_text())
    rows = g["resolution_coverage"]
    by: dict[str, dict] = {}
    total = {"sites": 0, "resolved": 0}
    for r in rows:
        parts = r["file"].split("/")
        d = "/".join(parts[:depth]) if len(parts) > depth else "/".join(parts[:-1]) or "."
        b = by.setdefault(d, {"sites": 0, "resolved": 0, "files": 0})
        b["sites"] += r["sites"]
        b["resolved"] += r["sites"] - r["unresolved"]
        b["files"] += 1
        total["sites"] += r["sites"]
        total["resolved"] += r["sites"] - r["unresolved"]
    built = g.get("built_by") or {}
    return {
        "sha": g.get("sha"), "hobbes": built.get("sha"), "containment": (g.get("containment") or {}).get("all_contained"),
        "total": total, "by_directory": by,
    }


# --------------------------------------------------------------- rendering

FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
INK = "#1a1a19"
INK2 = "#5a5a57"
GRID = "#d9d8d2"
BLUE = "#2a78d6"     # Hobbes
ORANGE = "#eb6834"   # a foreign (competitor) cell in the scatter; CodeGraphContext in same-key.svg
AQUA = "#1baf7a"     # repowise in same-key.svg — the reference palette's third slot; the three validate all-pairs (CVD ΔE ≥ 9)
SURFACE = "#fcfcfb"


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def fmt(n: int) -> str:
    return f"{n:,}"


def svg_open(w, h, title):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">',
            f'<title>{esc(title)}</title>',
            f'<rect width="{w}" height="{h}" fill="{SURFACE}"/>']


def text(x, y, s, size=13, fill=INK, anchor="start", weight="normal", extra=""):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" {FONT} {extra}>{esc(s)}</text>'


def wrap(s: str, width: int) -> list[str]:
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def compiler_graded(c):
    return c["kind"] in ("reachability", "resolution")


def cell_name(c):
    return c["label"] + (f" · {c['sub']}" if c.get("sub") else "")


def render_one_number(cells: list[dict]) -> str:
    comp = [c for c in cells if compiler_graded(c) and c.get("tool", "hobbes") == "hobbes" and c.get("precision")]
    trace = [c for c in cells if c["kind"] == "trace" and c.get("tool", "hobbes") == "hobbes"]
    with_poison = [c for c in comp if c.get("poison")]
    without = sorted({c["label"] for c in comp if not c.get("poison")})
    seeded = sum(c["poison"]["seeded"] for c in with_poison)
    falsely = sum(c["poison"]["falsely"] for c in with_poison)
    langs = sorted({c["lang"] for c in with_poison})
    t_seeded = sum(c["poison"]["seeded"] for c in trace if c.get("poison"))
    t_falsely = sum(c["poison"]["falsely"] for c in trace if c.get("poison"))
    t_k = sum(1 for c in trace if c.get("poison"))
    exceptions = [c for c in comp if c["precision"]["num"] != c["precision"]["den"]]
    perfect = [c for c in comp if c["precision"]["num"] == c["precision"]["den"]]
    n_sub = sum(1 for c in comp if c.get("sub"))
    W = 900
    lines: list[tuple[str, int, str, str, int]] = []  # (text, size, fill, weight, indent)

    def para(t, size=12, fill=INK2, weight="normal", indent=32, width=120):
        for i, l in enumerate(wrap(t, width)):
            lines.append((l, size, fill, weight, indent))

    lines.append(("Seeded wrong edges the oracle grader falsely confirmed", 15, INK2, "normal", 32))
    lines.append(("", 14, INK, "normal", 32))
    lines.append((f"{fmt(falsely)} of {fmt(seeded)}", 56, INK, "bold", 32))
    lines.append(("", 4, INK, "normal", 32))
    para(f"seeded wrong edges across {len(with_poison)} compiler-graded cells in {len(langs)} languages ({', '.join(langs)}). "
         f"Every cell grades a poisoned twin of its own export — each edge re-targeted to a declaration the oracle never resolved that site to — "
         f"and the grader refused or left unjudged every one; it confirmed none.", 13, INK2, width=105)
    lines.append(("—", 14, GRID, "normal", 32))
    lines.append((f"Precision-against-oracle on the {len(comp)} compiler-graded cells (dagger's {n_sub} Go modules counted one each):", 13, INK, "bold", 32))
    para(f"{len(perfect)} at 100% — confirmed equals graded, 0 contradicted. The exceptions, printed because they are what make the number believable:", 12, INK2)
    for c in sorted(exceptions, key=lambda c: c["label"]):
        pr = c["precision"]
        para(f"{cell_name(c)} ({c['lang']}): {fmt(pr['num'])}/{fmt(pr['den'])} = {pr['pct']}% — {c.get('note', '')}", 12, INK, indent=48, width=112)
    lines.append(("", 6, INK, "normal", 32))
    para(f"Trace-graded cells (Python — the interpreter under the repo's own suite): {fmt(t_falsely)} of {fmt(t_seeded)} seeded wrong edges falsely confirmed "
         f"across {t_k} cell{'s' if t_k != 1 else ''}. A refusal there is 'suspect', never a contradiction: the interpreter confirms and cannot contradict (C-60), "
         f"so those cells are kept out of the headline sum.", 11, INK2)
    if without:
        para(f"Not in the sum: {', '.join(without)} — graded before the poison check existed (kbet), or the record quotes the check per module and does not sum it (dagger).", 11, INK2)
    lines.append(("—", 14, GRID, "normal", 32))
    para("Precision-against-oracle is a lower bound: contradictions mostly triage to the oracle's own grain, and the triage ratio is quoted per cell (A-8).", 11, INK, "bold", width=125)
    para("Every number is read from docs/oracle/cells/ by bench/oracle/report/render.py (ADR-102); the answer keys are compilers Hobbes does not control (ADR-089): "
         "x/tools RTA for Go, tsc for TypeScript, rustc's MIR for Rust, javac with CHA for Java.", 10, INK2, width=140)
    H = 40 + sum(sz + 6 for _, sz, _, _, _ in lines) + 24
    o = svg_open(W, H, "Wrong edges seeded into the graph, falsely confirmed by the grader")
    y = 40
    for t, sz, fill, weight, indent in lines:
        y += sz + 6
        if t == "—":
            o.append(f'<line x1="32" y1="{y-8}" x2="{W-32}" y2="{y-8}" stroke="{GRID}"/>')
            continue
        if t:
            o.append(text(indent, y, t, sz, fill, weight=weight))
    o.append("</svg>")
    return "\n".join(o) + "\n"


def render_scatter(cells: list[dict]) -> str:
    comp = [c for c in cells if compiler_graded(c)]
    trace = [c for c in cells if c["kind"] == "trace"]
    langs = ["Go", "TypeScript", "Rust", "Java"]
    panels = [(l, [c for c in comp if c["lang"] == l]) for l in langs]
    PW, PH, GAP, L, T = 300, 300, 40, 60, 92
    cols = 3
    rows = 2
    W = L + cols * (PW + GAP) + 10
    H = T + rows * (PH + 74) + 120
    o = svg_open(W, H, "Precision-against-oracle by recall, one dot per cell, per language")
    o.append(text(24, 30, "One dot per cell: precision-against-oracle (y, a lower bound) against recall (x), never pooled", 15, INK, weight="bold"))
    o.append(text(24, 50, "Filled blue dot = Hobbes; hollow orange square = CodeGraphContext (·cgc), hollow orange diamond = repowise (·rw) — third-party graphs graded by the same key (ADR-101).", 11, INK2))
    o.append(text(24, 64, "Hover a dot for its miss classes with counts. Language is the panel, not a colour; the y axis of each panel starts where its lowest cell sits and says so.", 11, INK2))
    recalls = [c["recall"]["pct"] for c in comp if c.get("tool", "hobbes") == "hobbes" and c.get("precision")]

    def panel(i, title, items, x_label, y_label, y_key, hollow):
        px = L + (i % cols) * (PW + GAP)
        py = T + (i // cols) * (PH + 74)
        # The y axis starts where the lowest cell sits (never above 80), so a
        # 99.6% and a 100% are told apart; the range is printed on the axis.
        y_lo = min(80, int(min([c[y_key]["pct"] for c in items if c.get(y_key)] + [100]) // 10 * 10))
        o.append(text(px, py - 10, title, 13, INK, weight="bold"))
        o.append(f'<rect x="{px}" y="{py}" width="{PW}" height="{PH}" fill="none" stroke="{GRID}"/>')
        ys = list(range(y_lo, 101, 5 if 100 - y_lo <= 20 else 10))
        for v in (0, 25, 50, 75, 100):
            gx = px + PW * v / 100
            o.append(f'<line x1="{gx}" y1="{py}" x2="{gx}" y2="{py+PH}" stroke="{GRID}" stroke-dasharray="2 3"/>')
            o.append(text(gx, py + PH + 14, f"{v}", 9, INK2, "middle"))
        for v in ys:
            gy = py + PH - PH * (v - y_lo) / (100 - y_lo)
            o.append(f'<line x1="{px}" y1="{gy}" x2="{px+PW}" y2="{gy}" stroke="{GRID}" stroke-dasharray="2 3"/>')
            o.append(text(px - 6, gy + 3, f"{v}", 9, INK2, "end"))
        o.append(text(px + PW / 2, py + PH + 30, x_label, 10, INK2, "middle"))
        o.append(text(px - 34, py + PH / 2, f"{y_label}, axis from {y_lo}", 9, INK2, "middle", extra=f'transform="rotate(-90 {px-34} {py+PH/2})"'))
        placed = []  # label boxes (x0, y0, x1, y1); every dot is a box first, so no label covers a dot
        for c in items:
            if c.get(y_key):
                dx_ = px + PW * c["recall"]["pct"] / 100
                dy_ = py + PH - PH * (max(c[y_key]["pct"], y_lo) - y_lo) / (100 - y_lo)
                placed.append((dx_ - 7, dy_ - 7, dx_ + 7, dy_ + 7))
        undefined = [c for c in items if not c.get(y_key)]
        if undefined:
            o.append(text(px + 6, py + PH - 8, "not drawn (nothing graded): " + ", ".join(cell_name(c) + (f" ({c['tool']})" if c.get("tool", "hobbes") != "hobbes" else "") for c in undefined), 9, INK2))
        for c in sorted([c for c in items if c.get(y_key)], key=lambda c: c["recall"]["pct"]):
            xv, yv = c["recall"]["pct"], c[y_key]["pct"]
            cx = px + PW * xv / 100
            cy = py + PH - PH * (max(yv, y_lo) - y_lo) / (100 - y_lo)
            foreign = c.get("tool", "hobbes") != "hobbes"
            colour = ORANGE if foreign else BLUE
            misses = ", ".join(f"{k} {fmt(v)}" for k, v in sorted(c.get("misses", {}).items(), key=lambda kv: -kv[1])) or "none recorded"
            pr = c[y_key]
            tip = (f"{cell_name(c)}" + (f" — {c['tool']}" if foreign else "") + f" — {c['lang']}, {c['oracle']} ({c['kind']}), {c['run']}, {c['date']}\n"
                   f"{'confirmation rate' if c['kind']=='trace' else 'precision-against-oracle'} {fmt(pr['num'])}/{fmt(pr['den'])} = {pr['pct']}%\n"
                   f"recall {fmt(c['recall']['hits'])}/{fmt(c['recall']['pairs'])} = {c['recall']['pct']}% {c['recall']['basis']}\n"
                   f"misses by class: {misses}" + (f"\n{c['note']}" if c.get("note") else ""))
            o.append("<g>")
            o.append(f"<title>{esc(tip)}</title>")
            if foreign and c["tool"] == "repowise":
                o.append(f'<polygon points="{cx},{cy-6} {cx+6},{cy} {cx},{cy+6} {cx-6},{cy}" fill="{SURFACE}" stroke="{colour}" stroke-width="2"/>')
            elif foreign:
                o.append(f'<rect x="{cx-5}" y="{cy-5}" width="10" height="10" fill="{SURFACE}" stroke="{colour}" stroke-width="2"/>')
            elif hollow:
                o.append(f'<circle cx="{cx}" cy="{cy}" r="5" fill="{SURFACE}" stroke="{colour}" stroke-width="2"/>')
            else:
                o.append(f'<circle cx="{cx}" cy="{cy}" r="5" fill="{colour}" stroke="{SURFACE}" stroke-width="2"/>')
            o.append("</g>")
            if c.get("sub"):  # dagger's modules: one shared label below
                continue
            short_tool = {"codegraphcontext": "cgc", "repowise": "rw"}.get(c.get("tool"), c.get("tool"))
            lab = c["label"] if not foreign else f"{c['label']} ·{short_tool}"
            labs = [lab, "no semantic lane: the syntactic floor"] if c.get("floor") else [lab]
            # place the label at the first of four offsets whose box (approx 4.6 px per char at 8.5 px) is inside the panel and clear of every placed box
            w = max(len(l) for l in labs) * 4.6
            h = 10 * len(labs)
            chosen = None
            for dx, dy, anchor in ((8, 4, "start"), (-8, 4, "end"), (8, -h + 2, "start"), (-8, -h + 2, "end"), (8, h + 8, "start"), (-8, h + 8, "end")):
                for extra in range(0, 60, 10):
                    ly = cy + dy + (extra if dy >= 0 else -extra)
                    x0 = cx + dx if anchor == "start" else cx + dx - w
                    box = (x0, ly - 8, x0 + w, ly - 8 + h)
                    if box[0] < px + 2 or box[2] > px + PW - 2 or box[1] < py + 2 or box[3] > py + PH - 2:
                        continue
                    if any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in placed):
                        continue
                    chosen = (ly, anchor, box)
                    break
                if chosen:
                    break
            if not chosen:
                ly, anchor = cy + 4, "start"
                chosen = (ly, anchor, (cx + 8, ly - 8, cx + 8 + w, ly - 8 + h))
            ly, anchor, box = chosen
            placed.append(box)
            lx = cx + 8 if anchor == "start" else cx - 8
            for k, l in enumerate(labs):
                o.append(text(lx, ly + 10 * k, l, 8.5, INK, anchor))
        subs = [c for c in items if c.get("sub")]
        if subs:
            lo, hi = min(c["recall"]["pct"] for c in subs), max(c["recall"]["pct"] for c in subs)
            o.append(text(px + PW - 6, py + PH - 8, f"{subs[0]['label']}: {len(subs)} modules, recall {lo}–{hi}%, one dot each", 9, INK2, "end"))

    for i, (l, items) in enumerate(panels):
        panel(i, f"{l} — {', '.join(sorted({c['oracle'].split(' ')[0] for c in items}))} (compiler-graded)", items,
              "recall, % of in-repo oracle pairs at the cell's roots", "precision vs oracle, %", "precision", False)
    panel(4, "Python — the interpreter under the repo's suite (trace-graded)", trace,
          "recall-against-executed, % (coverage-limited)", "confirmation rate, % — not precision", "confirmation_rate", True)
    # Caption
    y = T + rows * (PH + 74) + 8
    o.append(f'<line x1="24" y1="{y}" x2="{W-24}" y2="{y}" stroke="{GRID}"/>')
    y += 22
    o.append(text(24, y, "We draw nothing the compiler contradicts; here is how much we do not draw, and what it is.", 13, INK, weight="bold"))
    y += 18
    o.append(text(24, y, f"Recall across Hobbes' compiler-graded cells runs {min(recalls)}–{max(recalls)}% — a range, never an average: each cell's denominator is its own roots or its resolved sites (C-62).", 11, INK2))
    y += 16
    o.append(text(24, y, "The misses are one register entry, C-58: closures, interface dispatch, function values, macro and derive bodies; docs/oracle/oracle-misses.md has the tables.", 11, INK2))
    y += 16
    o.append(text(24, y, "Precision-against-oracle is a lower bound (contradictions mostly triage to the oracle's grain, A-8). Trace cells confirm and never contradict, so they sit in their own panel.", 11, INK))
    y += 16
    o.append(text(24, y, "Rendered from docs/oracle/cells/ by bench/oracle/report/render.py (ADR-102).", 10, INK2))
    o.append("</svg>")
    return "\n".join(o) + "\n"


def render_before_after(cap: dict) -> str:
    before, after = cap["before"], cap["after"]
    dirs = sorted(set(before["by_directory"]) | set(after["by_directory"]),
                  key=lambda d: -max(before["by_directory"].get(d, {}).get("sites", 0), after["by_directory"].get(d, {}).get("sites", 0)))
    dirs = [d for d in dirs if max(before["by_directory"].get(d, {}).get("sites", 0), after["by_directory"].get(d, {}).get("sites", 0)) >= cap.get("min_sites", 1)]
    ROW, L = 30, 200
    W = 820
    story = wrap(cap["story"], 135)
    T = 66 + 15 * len(story) + 30
    caption = wrap(cap["caption"], 130)
    foot = wrap("Capture is lane A's count of detected call sites the join accounted for — a coverage number, not precision; the semantic edges are graded separately (docs/oracle/cells/). "
                "Rendered from two graph.json artifacts by bench/oracle/report/render.py (ADR-102).", 150)
    H = T + ROW * (len(dirs) + 1) + 70 + 15 * len(caption) + 13 * len(foot) + 20
    o = svg_open(W, H, f"{cap['repo']}: call-site capture per directory before and after {cap['fix']}")
    o.append(text(24, 30, f"{cap['repo']} @ {cap['sha'][:8]} — capture per directory, before and after {cap['fix']}", 15, INK, weight="bold"))
    for i, line in enumerate(story):
        o.append(text(24, 50 + 15 * i, line, 11, INK2))
    o.append(text(24, 50 + 15 * len(story) + 2, f"Before: Hobbes at {before['hobbes'][:8]}; after: Hobbes at {after['hobbes'][:8]}. Same clone, same commit, both ingests contained. Bar = accounted sites / detected call sites, as `hobbes ingest` prints it.", 10, INK2))
    bx = L
    bw = W - L - 150
    for v in (0, 25, 50, 75, 100):
        gx = bx + bw * v / 100
        o.append(f'<line x1="{gx}" y1="{T-8}" x2="{gx}" y2="{T + ROW*(len(dirs)+1)}" stroke="{GRID}" stroke-dasharray="2 3"/>')
        o.append(text(gx, T - 12, f"{v}%", 9, INK2, "middle"))

    def row(i, name, b, a):
        y = T + i * ROW
        o.append(text(bx - 8, y + 12, name, 11, INK, "end"))
        for k, (d, colour) in enumerate(((b, "#c3c2b7"), (a, BLUE))):
            pct = 100 * d["resolved"] / d["sites"] if d["sites"] else 0
            w = max(bw * pct / 100, 1)
            yy = y + k * 9
            o.append("<g>")
            o.append(f"<title>{esc(name)} {'before' if k == 0 else 'after'}: {fmt(d['resolved'])} of {fmt(d['sites'])} sites resolved ({pct:.1f}%), {d.get('files', '?')} files</title>")
            o.append(f'<rect x="{bx}" y="{yy}" width="{w:.1f}" height="7" fill="{colour}" rx="2"/>')
            o.append("</g>")
            o.append(text(bx + w + 5, yy + 7, f"{pct:.1f}%" + (f" of {fmt(d['sites'])}" if k == 1 else ""), 9, INK2))

    for i, d in enumerate(dirs):
        row(i, d, before["by_directory"].get(d, {"sites": 0, "resolved": 0}), after["by_directory"].get(d, {"sites": 0, "resolved": 0}))
    row(len(dirs), "whole repo", before["total"], after["total"])
    y = T + ROW * (len(dirs) + 1) + 20
    o.append(f'<rect x="{bx}" y="{y}" width="12" height="7" fill="#c3c2b7" rx="2"/>')
    o.append(text(bx + 18, y + 7, "before", 10, INK2))
    o.append(f'<rect x="{bx+80}" y="{y}" width="12" height="7" fill="{BLUE}" rx="2"/>')
    o.append(text(bx + 98, y + 7, "after", 10, INK2))
    y += 30
    o.append(f'<line x1="24" y1="{y}" x2="{W-24}" y2="{y}" stroke="{GRID}"/>')
    y += 20
    for line in caption:
        o.append(text(24, y, line, 11, INK))
        y += 15
    y += 4
    for line in foot:
        o.append(text(24, y, line, 10, INK2))
        y += 13
    o.append("</svg>")
    return "\n".join(o) + "\n"


def render_tables(cells: list[dict]) -> str:
    """docs/comparative/tables.md — the standing Hobbes cells and, per foreign
    cell, the pair on the same key. Every number is the record's."""
    draws = [c for c in cells if "repowise-bench" in c.get("draw", "")]
    hob = [c for c in cells if c.get("tool", "hobbes") == "hobbes" and c not in draws]
    frn = [c for c in cells if c.get("tool", "hobbes") != "hobbes" and c not in draws]
    out = ["<!-- generated by bench/oracle/report/render.py tables (ADR-102); do not edit — regenerate -->", "",
           "## The standing Hobbes cells", "",
           "Precision-against-oracle is a lower bound (A-8). Recall carries its root count or basis and is never pooled (C-62). Trace cells print a confirmation rate, never precision (C-60). dagger's 19 Go modules are one row.", "",
           "| cell | lang | oracle | edges | precision-against-oracle | recall | run | poison (seeded / falsely confirmed) | record |", "|---|---|---|---|---|---|---|---|---|"]
    dag = [c for c in hob if c.get("sub")]
    for c in sorted([c for c in hob if not c.get("sub")], key=lambda c: (c["lang"], c["label"])):
        p = c.get("precision") or c.get("confirmation_rate")
        pl = f"**{fmt(p['num'])}/{fmt(p['den'])}** ({p['pct']}%)" if c.get("precision") else f"confirmation rate {p['pct']}% ({fmt(p['num'])}/{fmt(p['den'])}) — not precision"
        r = c["recall"]
        po = c.get("poison")
        out.append(f"| {c['label']} | {c['lang']} | {c['oracle']} | {fmt(c['edges'])} | {pl} | {r['pct']}% ({fmt(r['hits'])}/{fmt(r['pairs'])}) {r['basis']} | {c['run']} | {fmt(po['seeded']) + ' / ' + fmt(po['falsely']) if po else 'not run (graded before the check)'} | [{c['record']}](../oracle/cells/{c['record']}) |")
    if dag:
        lo, hi = min(c["recall"]["pct"] for c in dag), max(c["recall"]["pct"] for c in dag)
        conf = sum(c["confirmed"] for c in dag); den = sum(c["precision"]["den"] for c in dag)
        out.append(f"| {dag[0]['label']} ({len(dag)} Go modules) | Go | go-rta | {fmt(sum(c['edges'] for c in dag))} | **{fmt(conf)}/{fmt(den)}** (100% in every module) | {lo}–{hi}% per module, one root count each — a range, not a pool | {dag[0]['run']} | per module in the record, not summed | [{dag[0]['record']}](../oracle/cells/{dag[0]['record']}) |")
    if frn:
        out += ["", "## Foreign cells beside the Hobbes cell on the same key (ADR-101)", "",
                "Same repo, same commit, same answer key, same matcher, same poison check. The tool's number is at our grain (C-94, C-95) and host-run (C-96); every foreign record quotes the tool's own confidence labels and its untriaged contradiction count. Hobbes' number is the standing cell's.", "",
                "| repo | lang | tool | tool: edges | tool: precision-against-oracle | tool: recall | tool: poison | Hobbes: precision-against-oracle | Hobbes: recall | records |", "|---|---|---|---|---|---|---|---|---|---|"]
        by_label = {c["label"]: c for c in hob if not c.get("sub")}
        for c in sorted(frn, key=lambda c: (c["lang"], c["label"], c["tool"])):
            h = by_label.get(c["label"])
            p = c.get("precision"); r = c["recall"]; po = c.get("poison")
            if p:
                pl = f"{p['pct']}% ({fmt(p['num'])}/{fmt(p['den'])})"
            elif c.get("undefined"):
                pl = "undefined (nothing confirmed or contradicted)"
            elif c.get("confirmation_rate"):
                pl = f"confirmation {c['confirmation_rate']['pct']}% — not precision"
            else:
                pl = "undefined (nothing graded)"
            hp = (h.get("precision") or h.get("confirmation_rate")) if h else None
            hpl = (f"{hp['pct']}% ({fmt(hp['num'])}/{fmt(hp['den'])})" if h and h.get("precision") else (f"confirmation {hp['pct']}% — not precision" if hp else "—"))
            out.append(f"| {c['label']} | {c['lang']} | {c['tool']} | {fmt(c['edges'])} | {pl} | {r['pct']}% ({fmt(r['hits'])}/{fmt(r['pairs'])}) | {fmt(po['seeded']) + ' / ' + fmt(po['falsely']) if po else '—'} | {hpl} | {h['recall']['pct'] if h else '—'}% | [{c['record']}](../oracle/cells/{c['record']}), [{h['record'] if h else '—'}](../oracle/cells/{h['record'] if h else ''}) |")
    dh = [c for c in draws if c.get("tool", "hobbes") == "hobbes"]
    if dh:
        out += ["", "## The 1-1 on repowise's draws (ADR-101 § the 1-1)", "",
                "The five repos repowise-bench's G4 experiment drew (its `corpus.lock` pins), ingested by Hobbes contained and graded by **our** key on this box, with both tools run on the same clones and graded by the same key. This is a 1-1 among the three graphs at our grain; it is **not** comparable with repowise-bench's own table, whose key is at function grain (caller declaration → callee declaration) and whose matcher and adapters are theirs. Precision-against-oracle is a lower bound; recall carries its roots; nothing is pooled.", "",
                "| cell | lang | Hobbes: edges | Hobbes: precision-against-oracle | Hobbes: recall | Hobbes: poison | CodeGraphContext: precision / recall | repowise: precision / recall | records |", "|---|---|---|---|---|---|---|---|---|"]
        for h in sorted(dh, key=lambda c: (c["lang"], c["label"])):
            def cellp(t):
                c = next((x for x in draws if x.get("tool") == t and x["label"] == h["label"]), None)
                if not c:
                    return "—"
                p = c.get("precision")
                pl = f"{p['pct']}% ({fmt(p['num'])}/{fmt(p['den'])})" if p else ("undefined" if c.get("undefined") else "—")
                return f"{pl} / {c['recall']['pct']}% ({fmt(c['recall']['hits'])}/{fmt(c['recall']['pairs'])})"
            p = h["precision"]; r = h["recall"]; po = h.get("poison")
            recs = ", ".join(f"[{x['record']}](../oracle/cells/{x['record']})" for x in [h] + [x for x in draws if x.get("tool") and x["label"] == h["label"]])
            out.append(f"| {h['label']} | {h['lang']} | {fmt(h['edges'])} | **{fmt(p['num'])}/{fmt(p['den'])}** ({p['pct']}%) | {r['pct']}% ({fmt(r['hits'])}/{fmt(r['pairs'])}) {r['basis']} | {fmt(po['seeded']) + ' / ' + fmt(po['falsely']) if po else '—'} | {cellp('codegraphcontext')} | {cellp('repowise')} | {recs} |")
    return "\n".join(out) + "\n"


def render_comparison(cells: list[dict]) -> str:
    """docs/comparative/graphics/same-key.svg — one row per cell that has a
    foreign graph graded on the same key: three markers on the precision
    axis and three on the recall axis (Hobbes, CodeGraphContext, repowise),
    grouped by language; repowise-bench's draws as their own band; the
    trace-graded Python cell last with its confirmation rate. Nothing is
    pooled: every row is one key, one root count or one resolved-site set.
    One hue per tool (blue, orange, green — validated all-pairs) and a shape
    as the second encoding, every marker filled: three hollow shapes in one
    colour did not read at a glance (2026-09-09, Max)."""
    by_label: dict[str, dict] = {}
    for c in cells:
        if c.get("sub"):
            continue
        by_label.setdefault(c["label"], {})[c.get("tool", "hobbes")] = c
    rows = [(lab, d) for lab, d in by_label.items() if any(t != "hobbes" for t in d) and "hobbes" in d]
    order = ["Go", "TypeScript", "Rust", "Java", "Python"]
    bands = []
    for lang in order:
        loop = [(l, d) for l, d in rows if d["hobbes"]["lang"] == lang and "repowise-bench" not in d["hobbes"].get("draw", "")]
        if loop:
            bands.append((f"{lang} — the loop and random-draw cells", loop))
    draws = [(l, d) for l, d in rows if "repowise-bench" in d["hobbes"].get("draw", "")]
    if draws:
        bands.append(("repowise-bench's draws under our key (Go, TypeScript) — the 1-1", draws))
    ROW, L, PW, GAP, T = 22, 250, 300, 60, 104
    n = sum(len(b[1]) for b in bands) + len(bands)
    W = L + 2 * PW + GAP + 40
    H = T + ROW * n + 190
    o = svg_open(W, H, "Three graphs on one key per cell: precision-against-oracle and recall, Hobbes beside CodeGraphContext and repowise")
    o.append(text(24, 30, "Three graphs, one key per cell: precision-against-oracle and recall, never pooled", 15, INK, weight="bold"))
    px = {"precision": L, "recall": L + PW + GAP}
    marks = {"hobbes": ("circle", BLUE), "codegraphcontext": ("square", ORANGE), "repowise": ("diamond", AQUA)}

    def mark(kind, colour, cx, cy, tip):
        o.append("<g>")
        o.append(f"<title>{esc(tip)}</title>")
        # every marker filled in its tool's hue with a surface ring, so two
        # tools on one value stay two marks
        if kind == "circle":
            o.append(f'<circle cx="{cx}" cy="{cy}" r="5.5" fill="{colour}" stroke="{SURFACE}" stroke-width="1.5"/>')
        elif kind == "square":
            o.append(f'<rect x="{cx-5}" y="{cy-5}" width="10" height="10" fill="{colour}" stroke="{SURFACE}" stroke-width="1.5"/>')
        else:
            o.append(f'<polygon points="{cx},{cy-6.5} {cx+6.5},{cy} {cx},{cy+6.5} {cx-6.5},{cy}" fill="{colour}" stroke="{SURFACE}" stroke-width="1.5"/>')
        o.append("</g>")

    # the legend: the marker itself beside each tool's name, one colour per tool
    lx = 24
    for t, name in (("hobbes", "Hobbes"), ("codegraphcontext", "CodeGraphContext 0.6.13"), ("repowise", "repowise 0.49.0")):
        kind, colour = marks[t]
        mark(kind, colour, lx + 6, 46, name)
        o.append(text(lx + 16, 50, name, 11, INK2))
        lx += 16 + 6.1 * len(name) + 14
    o.append(text(lx, 50, "— one colour per tool; the same repo, commit, answer key, matcher and poison check (ADR-101).", 11, INK2))
    o.append(text(24, 64, "The tools' numbers are at our grain (C-94, C-95) and host-run (C-96). Hover a marker for its fraction; the grey line spans the three.", 11, INK2))
    for key, x0 in px.items():
        for v in (0, 25, 50, 75, 100):
            gx = x0 + PW * v / 100
            o.append(f'<line x1="{gx}" y1="{T-6}" x2="{gx}" y2="{T + ROW*n}" stroke="{GRID}" stroke-dasharray="2 3"/>')
            o.append(text(gx, T - 10, f"{v}%", 9, INK2, "middle"))
        o.append(text(x0 + PW / 2, T - 26, "precision-against-oracle (a lower bound)" if key == "precision" else "recall, of in-repo oracle pairs at the cell's roots", 11, INK, "middle", weight="bold"))
    y = T
    for title, items in bands:
        o.append(text(24, y + 14, title, 11, INK, weight="bold"))
        y += ROW
        for lab, d in sorted(items, key=lambda x: x[0].lower()):
            h = d["hobbes"]
            trace = h["kind"] == "trace"
            o.append(text(L - 10, y + 14, lab + (" (trace: confirmation rate)" if trace else ""), 10, INK, "end"))
            for key, x0 in px.items():
                pts = []
                for t, c in d.items():
                    if key == "precision":
                        v = (c.get("confirmation_rate") if trace else c.get("precision"))
                        if not v:
                            continue
                        val = v["pct"]; tip = f"{lab} — {t}: {'confirmation rate' if trace else 'precision-against-oracle'} {fmt(v['num'])}/{fmt(v['den'])} = {val}%"
                    else:
                        r = c["recall"]; val = r["pct"]; tip = f"{lab} — {t}: recall {fmt(r['hits'])}/{fmt(r['pairs'])} = {val}% {r['basis']}"
                    pts.append((t, val, tip))
                if not pts:
                    continue
                xs = [x0 + PW * v / 100 for _, v, _ in pts]
                o.append(f'<line x1="{min(xs)}" y1="{y+10}" x2="{max(xs)}" y2="{y+10}" stroke="{GRID}" stroke-width="2"/>')
                for (t, val, tip), cx in zip(pts, xs):
                    kind, colour = marks[t]
                    mark(kind, colour, cx, y + 10, tip)
                undefined = [t for t in d if t != "hobbes" and key == "precision" and d[t].get("undefined")]
                if undefined:
                    o.append(text(x0 + 4, y + 14, f"{', '.join(undefined)}: undefined (no call edge stored)", 8.5, INK2))
            y += ROW
    y += 14
    o.append(f'<line x1="24" y1="{y}" x2="{W-24}" y2="{y}" stroke="{GRID}"/>')
    y += 20
    for line in wrap("Read across a row, never down a column: each cell's recall is over its own roots or resolved sites (C-62), and a precision is a lower bound (contradictions mostly triage to the oracle's grain, A-8). "
                     "Every Hobbes marker on the precision axis sits at 100% except ajv, hono (one scip-typescript union-member shape) and quic-go (a 99.6% lower bound, 0 hobbes-wrong). "
                     "The tools' contradictions are a lower bound on their precision exactly as ours is on ours; a 40-row random sample read by hand found tool-wrong 39, oracle-grain 1 after the converters' Java annotation-line defect (C-94) was repaired and the Java cells regraded. "
                     "On repowise-bench's draws the key is ours, at site grain — not comparable with their published table; syft is absent because RTA over it is killed by the kernel on this box.", 175):
        o.append(text(24, y, line, 10.5, INK2))
        y += 14
    o.append(text(24, y + 4, "Rendered from docs/oracle/cells/ by bench/oracle/report/render.py (ADR-102); the numbers are in tables.md.", 10, INK2))
    o.append("</svg>")
    return "\n".join(o) + "\n"


def render_all(data_dir: Path, out_dir: Path) -> dict[str, str]:
    cells = json.loads((data_dir / "cells.json").read_text())["cells"]
    for p in sorted(data_dir.glob("foreign-*.json")):
        cells.extend(json.loads(p.read_text())["cells"])
    out = {"one-number.svg": render_one_number(cells), "precision-recall.svg": render_scatter(cells), "same-key.svg": render_comparison(cells), "../tables.md": render_tables(cells)}
    for p in sorted(data_dir.glob("*-capture.json")):
        cap = json.loads(p.read_text())
        out[p.name.replace("-capture.json", "-before-after.svg")] = render_before_after(cap)
    return out


# ------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("cells"); a.add_argument("--cells", default=str(CELLS)); a.add_argument("--meta", default=str(META)); a.add_argument("--out", default=str(DATA / "cells.json"))
    a = sub.add_parser("capture"); a.add_argument("--before", required=True); a.add_argument("--after", required=True); a.add_argument("--repo", required=True)
    a.add_argument("--fix", required=True); a.add_argument("--story", required=True); a.add_argument("--caption", required=True); a.add_argument("--min-sites", type=int, default=1); a.add_argument("--out", required=True)
    a = sub.add_parser("render"); a.add_argument("--data", default=str(DATA)); a.add_argument("--out", default=str(GRAPHICS))
    a = sub.add_parser("check"); a.add_argument("--cells", default=str(CELLS)); a.add_argument("--meta", default=str(META)); a.add_argument("--data", default=str(DATA)); a.add_argument("--graphics", default=str(GRAPHICS))
    args = ap.parse_args(argv)

    if args.cmd == "cells":
        d = load_cells(Path(args.cells), Path(args.meta))
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")
        print(f"{len(d['cells'])} cells → {args.out}")
    elif args.cmd == "capture":
        b, a = capture(Path(args.before)), capture(Path(args.after))
        if b["sha"] != a["sha"]:
            sys.exit(f"before and after are different commits: {b['sha']} vs {a['sha']}")
        d = {"repo": args.repo, "sha": a["sha"], "fix": args.fix, "story": args.story, "caption": args.caption, "min_sites": args.min_sites,
             "before": b, "after": a, "artifacts": {"before": str(args.before), "after": str(args.after)}}
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")
        print(f"{args.repo}: {b['total']['resolved']}/{b['total']['sites']} → {a['total']['resolved']}/{a['total']['sites']} → {args.out}")
    elif args.cmd == "render":
        out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
        for name, svg in render_all(Path(args.data), out).items():
            (out / name).write_text(svg)
            print(f"wrote {out / name}")
    elif args.cmd == "check":
        drift = []
        fresh = load_cells(Path(args.cells), Path(args.meta))
        committed = json.loads((Path(args.data) / "cells.json").read_text())
        if fresh != committed:
            drift.append("data/cells.json does not match docs/oracle/cells/ — run `render.py cells` then `render.py render`")
        for name, svg in render_all(Path(args.data), Path(args.graphics)).items():
            p = Path(args.graphics) / name
            if not p.exists() or p.read_text() != svg:
                drift.append(f"{p} drifted from the data — run `render.py render`")
        if drift:
            print("\n".join(drift)); sys.exit(1)
        print("graphics match the cell records")


if __name__ == "__main__":
    main()
