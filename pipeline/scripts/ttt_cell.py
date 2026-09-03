"""The primary cell: derived units → four arms → HSR / RFE / manifest_ignore (ADR-099 §4.1–4.2; review item 9).

    uv run scripts/ttt_cell.py units <repo-at-base> <proposals.jsonl> --out <cell-dir> [--units-nll hobbes-cond.jsonl] [--max-units 4]
    HOBBES_LLM_API_KEY=… uv run scripts/ttt_cell.py run <cell-dir> <base_url> --arm A1=allenai/Olmo-3-7B-Instruct --arm A3=hobbes-ebdf7a51 … [--workers 6] [--max-turns 30]
    uv run scripts/ttt_cell.py score <cell-dir> <repo-at-base>
    uv run scripts/ttt_cell.py report <cell-dir>

``units`` runs ``hobbes plan`` over every proposal (seeded by the files
of the commit that the base graph holds — read from the NLL units file
— or lexically) and writes ``units.jsonl``. ``run`` executes one
file-tools-only agent per (arm, unit) on a fresh checkout under
``<cell-dir>/work/``, resumable (a finished row is skipped), the
unaided arms once per proposal and shared across its units. ``score``
reads every transcript and patch against the graph; ``report`` pairs
the arms by unit. Every arm is *model + prompt* (P12). Computes; does
not interpret.
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from hobbes import artifacts
from hobbes.ttt import cell
from hobbes.ttt.units import read_units as read_nll_units

LOOP = Path(__file__).resolve().parents[1] / "src" / "hobbes" / "agent" / "loop.py"


def cmd_units(a) -> int:
    proposals = {}
    for line in Path(a.proposals).read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("commit") and row.get("task"):
                proposals[row["commit"]] = row["task"].strip()
    seeds: dict[str, list[str]] = {}
    if a.units_nll:
        graph = artifacts.load_graph(Path(a.repo))
        known = {n.get("path") for n in graph.get("nodes", []) if n.get("path")}
        for u in read_nll_units(Path(a.units_nll)):
            commit = u["id"].split(":", 1)[0]
            for f in u.get("files", []):
                if f in known and f not in seeds.setdefault(commit, []):
                    seeds[commit].append(f)
        seeds = {c: v for c, v in seeds.items() if any(c.startswith(k) or k.startswith(c) for k in proposals)}
        seeds = {k: seeds.get(k) or seeds.get(k[:12]) or [] for k in proposals}
    units, errors = cell.derive_units(Path(a.repo), proposals, seeds, max_units=a.max_units)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    cell.write_units(units, out / "units.jsonl", errors)
    graph = artifacts.load_graph(Path(a.repo))
    (out / "cell.json").write_text(json.dumps({"repo": str(Path(a.repo).resolve()), "name": a.name or Path(a.repo).resolve().name,
                                               "sha": graph.get("sha"), "built_by": graph.get("built_by"),
                                               "proposals": len(proposals), "units": len(units), "plan_errors": errors,
                                               "max_units": a.max_units}, indent=1, sort_keys=True))
    for u in units:
        print(f"{u.id:60} {len(u.paths):2d} paths {len(u.guarding_tests):3d} guards {len(u.manifest):6d} chars{'  ' + '; '.join(u.notes) if u.notes else ''}")
    for e in errors:
        print(f"plan error {e['commit'][:12]}: {e['error'][:140]}")
    print(f"{len(units)} unit(s) from {len(proposals)} proposal(s), {len(errors)} refused → {out / 'units.jsonl'}")
    return 0


def cmd_run(a) -> int:
    cd = Path(a.cell)
    meta = json.loads((cd / "cell.json").read_text())
    units, _ = cell.read_units(cd / "units.jsonl")
    arms = dict(spec.split("=", 1) for spec in a.arm)
    runs_path = cd / "runs.jsonl"
    done = set()
    if runs_path.exists():
        for line in runs_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line); done.add((r["arm"], r["unit"]))
    sha12 = (meta.get("sha") or "")[:12]
    jobs = []
    for arm, model in arms.items():
        _, aided = cell.ARMS[arm]
        seen_commit: set[str] = set()
        for u in units:
            if (arm, u["id"]) in done:
                continue
            if not aided:
                if u["commit"] in seen_commit:
                    continue
                seen_commit.add(u["commit"])
            jobs.append((arm, model, aided, u))
    print(f"{len(jobs)} session(s) to run ({len(done)} rows already recorded)", flush=True)

    def one(job):
        arm, model, aided, u = job
        key = u["commit"][:12] if not aided else u["id"].replace("/", "__")
        ws = cell.checkout(Path(meta["repo"]), meta["sha"], cd / "work" / arm / key)
        prompt = cell.brief(u, meta["name"], sha12, aided)
        res = cell.run_agent(LOOP, ws, prompt, a.base_url, model, max_turns=a.max_turns, max_tokens=a.max_tokens,
                             temperature=a.temperature, timeout=a.timeout)
        rows = []
        targets = [u] if aided else [v for v in units if v["commit"] == u["commit"]]
        for v in targets:
            rows.append({"arm": arm, "unit": v["id"], "commit": v["commit"], "aided": aided, "shared_run": not aided,
                         "workspace": str(ws), **res})
        return rows

    with ThreadPoolExecutor(max_workers=a.workers) as pool, runs_path.open("a") as fh:
        for i, rows in enumerate(pool.map(one, jobs)):
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n"); fh.flush()
            r = rows[0]
            print(f"[{i + 1}/{len(jobs)}] {r['arm']} {r['unit'][:50]:50} turns {(r['envelope'] or {}).get('num_turns')} "
                  f"patch {len(cell.patch_files(r['patch']))} files {r['wall_s']}s {('ERR ' + r['error'][:80]) if r['error'] else ''}", flush=True)
    return 0


def cmd_score(a) -> int:
    cd = Path(a.cell)
    units = {u["id"]: u for u in cell.read_units(cd / "units.jsonl")[0]}
    names = cell.graph_names(artifacts.load_graph(Path(a.repo)))
    rows = [json.loads(ln) for ln in (cd / "runs.jsonl").read_text().splitlines() if ln.strip()]
    scores = [cell.score_run(r, units[r["unit"]], names, r["aided"]) for r in rows if r["unit"] in units]
    (cd / "scores.jsonl").write_text("\n".join(json.dumps(s, sort_keys=True) for s in scores) + "\n")
    print(f"{len(scores)} row(s) scored → {cd / 'scores.jsonl'}")
    return 0


def cmd_report(a) -> int:
    cd = Path(a.cell)
    scores = [json.loads(ln) for ln in (cd / "scores.jsonl").read_text().splitlines() if ln.strip()]
    rep = cell.cell_report(scores, a.resamples, a.seed)
    rep["inputs"] = json.loads((cd / "cell.json").read_text())
    (cd / "report.json").write_text(json.dumps(rep, indent=1, sort_keys=True))
    print(cell.format_cell_report(rep))
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("units"); u.add_argument("repo"); u.add_argument("proposals"); u.add_argument("--out", required=True)
    u.add_argument("--units-nll"); u.add_argument("--max-units", type=int, default=4); u.add_argument("--name")
    r = sub.add_parser("run"); r.add_argument("cell"); r.add_argument("base_url"); r.add_argument("--arm", action="append", required=True)
    r.add_argument("--workers", type=int, default=6); r.add_argument("--max-turns", type=int, default=30)
    r.add_argument("--max-tokens", type=int, default=1536); r.add_argument("--temperature", type=float, default=0.2)
    r.add_argument("--timeout", type=float, default=1800.0)
    s = sub.add_parser("score"); s.add_argument("cell"); s.add_argument("repo")
    p = sub.add_parser("report"); p.add_argument("cell"); p.add_argument("--resamples", type=int, default=5000); p.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    return {"units": cmd_units, "run": cmd_run, "score": cmd_score, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
