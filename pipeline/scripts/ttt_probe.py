"""The memorisation probe and the held-out navigation evaluation (ADR-099 §4.4, §4.5).

    HOBBES_LLM_API_KEY=… uv run scripts/ttt_probe.py probe <repo> <corpus-dir> <base_url> <model> [--dirs 5] [--files 5] [--out f.json]
    HOBBES_LLM_API_KEY=… uv run scripts/ttt_probe.py nav <repo> <corpus-dir> <base_url> <model> [--context none|card] [--limit N] [--out f.json]

``probe`` is unaided, temperature 0, given only the repo's name and a
path: (1) list the files under a directory, precision and recall
against the real tree; (2) the functions defined in a file, against the
graph; (3) the thirty navigation items ``derive-corpus`` drew. The score
gates a repo into the memorised or the unseen cell (>0.5 / <0.15).

``nav`` asks every ``eval.jsonl`` item — the held-out symbols' questions
and the absent family's distractors — and scores what each reply names
(`hobbes.ttt.score`). ``--context card`` puts the symbol's own card in
the prompt (the reading-comprehension control); ``--context none`` is
the weights-only arm. The *model* is the arm: the base name or an
adapter's name on the same endpoint.

Computes; does not interpret.
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from hobbes import artifacts
from hobbes.ttt.score import known_names, score_reply, summarise

SYSTEM = "You are answering questions about the {repo} repository at commit {sha12}. Answer briefly and precisely."


def ask(base_url: str, model: str, key: str, system: str, user: str, max_tokens: int = 512) -> str:
    body = json.dumps({"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                       "temperature": 0, "max_tokens": max_tokens,
                       "chat_template_kwargs": {"enable_thinking": False}}).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    # A 5xx or a dropped connection is retried with backoff (the shape
    # loop.py's Endpoint uses); a 4xx is the caller's and raises. One
    # transient 500 killed a whole arm on 2026-09-03 before this.
    last: Exception | None = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                msg = json.loads(r.read())["choices"][0]["message"]
            return (msg.get("content") or msg.get("reasoning_content") or "").strip()
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429:
                raise
            last = exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last = exc
        time.sleep(2 ** attempt)
    raise RuntimeError(f"endpoint failed after 5 attempts: {last}")


def spaced(items: list, k: int) -> list:
    """*k* items spread evenly over a sorted list — deterministic, not the first k."""
    if len(items) <= k:
        return items
    step = len(items) / k
    return [items[int(i * step)] for i in range(k)]


def pick_dirs(graph: dict, k: int) -> list[str]:
    counts: dict[str, int] = {}
    for n in graph.get("nodes", []):
        if n.get("path") and "/" in n["path"]:
            counts[n["path"].rsplit("/", 1)[0]] = counts.get(n["path"].rsplit("/", 1)[0], 0) + 1
    return spaced(sorted(d for d, c in counts.items() if c >= 3), k)


def pick_files(graph: dict, k: int) -> list[tuple[str, list[str]]]:
    by_module: dict[str, list[str]] = {}
    for s in graph.get("symbols", []):
        if s.get("kind") in ("function", "method", "class"):
            by_module.setdefault(s.get("module", ""), []).append(s["name"])
    path_of = {n["id"]: n.get("path") for n in graph.get("nodes", [])}
    rows = sorted((path_of[m], sorted(set(names))) for m, names in by_module.items() if path_of.get(m) and len(set(names)) >= 5)
    return spaced(rows, k)


_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def prf(listed: set[str], truth: set[str]) -> dict:
    hit = listed & truth
    p = len(hit) / len(listed) if listed else 0.0
    r = len(hit) / len(truth) if truth else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "listed": len(listed), "truth": len(truth), "hit": len(hit)}


def probe(a, graph, corpus_dir, key) -> dict:
    repo_root = Path(a.repo)
    sha12 = graph.get("sha", "")[:12]
    system = SYSTEM.format(repo=a.name, sha12=sha12)
    out = {"model": a.model, "repo": a.name, "sha": graph.get("sha"), "parts": {}}
    # (1) files under a directory.
    rows = []
    for d in pick_dirs(graph, a.dirs):
        real = {p.name for p in (repo_root / d).iterdir() if p.is_file()} if (repo_root / d).is_dir() else set()
        reply = ask(a.base_url, a.model, key, system, f"List the files directly under `{d}/` in {a.name} (at {sha12}), one file name per line.")
        listed = {t for t in re.findall(r"[\w.-]+\.\w+", reply)}
        listed = {t.rsplit("/", 1)[-1] for t in listed}
        rows.append({"dir": d, **prf(listed, real), "reply_head": reply[:160]})
        print(f"files {d:40} P {rows[-1]['precision']:.2f} R {rows[-1]['recall']:.2f} ({rows[-1]['hit']}/{rows[-1]['truth']})")
    out["parts"]["files"] = rows
    # (2) functions in a file.
    rows = []
    for path, names in pick_files(graph, a.files):
        reply = ask(a.base_url, a.model, key, system, f"What functions, methods and classes are defined in `{path}` in {a.name} (at {sha12})? Names only, one per line.")
        listed = set(_TOKEN.findall(reply)) & {n for n in names} | {t for t in _TOKEN.findall(reply) if t in names}
        rows.append({"file": path, **prf(set(_TOKEN.findall(reply)), set(names)), "reply_head": reply[:160]})
        print(f"defs  {path:40} P {rows[-1]['precision']:.2f} R {rows[-1]['recall']:.2f} ({rows[-1]['hit']}/{rows[-1]['truth']})")
    out["parts"]["definitions"] = rows
    # (3) navigation items, no context.
    known = known_names(graph)
    rows = []
    for rec in (json.loads(ln) for ln in (corpus_dir / "probe-nav.jsonl").read_text().splitlines() if ln.strip()):
        reply = ask(a.base_url, a.model, key, system, rec["messages"][0]["content"])
        rows.append({"family": rec["family"], "symbol": rec["symbol"], **score_reply(rec, reply, known), "reply": reply})
    out["parts"]["navigation"] = {"rows": rows, **summarise(rows)}
    means = [sum(r["precision"] for r in out["parts"]["files"]) / max(1, len(out["parts"]["files"])),
             sum(r["recall"] for r in out["parts"]["definitions"]) / max(1, len(out["parts"]["definitions"])),
             out["parts"]["navigation"]["navigation_mean"] or 0.0]
    out["score"] = round(sum(means) / 3, 3)
    out["cell"] = "M" if out["score"] > 0.5 else "U" if out["score"] < 0.15 else "neither"
    print(f"probe: files-P {means[0]:.2f}  defs-R {means[1]:.2f}  nav {means[2]:.2f}  → score {out['score']}  cell {out['cell']}")
    return out


def nav(a, graph, corpus_dir, key) -> dict:
    sha12 = graph.get("sha", "")[:12]
    system = SYSTEM.format(repo=a.name, sha12=sha12)
    cards = {}
    if a.context == "card":
        for ln in (corpus_dir / "eval-cards.jsonl").read_text().splitlines():
            if ln.strip():
                c = json.loads(ln); cards[c["symbol"]] = c["messages"][1]["content"]
    known = known_names(graph)
    items = [json.loads(ln) for ln in (corpus_dir / "eval.jsonl").read_text().splitlines() if ln.strip()]
    items = items[:a.limit] if a.limit else items

    def one(rec: dict) -> dict:
        user = rec["messages"][0]["content"]
        if a.context == "card":
            card = cards.get(rec["symbol"])
            user = (f"Derived context for this symbol (Hobbes, {sha12}):\n{card}\n\n" if card else
                    f"Derived context: Hobbes has no card for `{rec['symbol']}` at {sha12}.\n\n") + user
        reply = ask(a.base_url, a.model, key, system, user)
        # The whole reply is kept so a scorer fix can rescore a run without re-asking.
        return {"family": rec["family"], "symbol": rec["symbol"], **score_reply(rec, reply, known), "reply": reply}

    # Order is the file's regardless of which request answers first.
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        rows = []
        for i, row in enumerate(pool.map(one, items)):
            rows.append(row)
            if i % 200 == 0:
                print(f"{i}/{len(items)} …", flush=True)
    out = {"model": a.model, "repo": a.name, "sha": graph.get("sha"), "context": a.context, "rows": rows, **summarise(rows)}
    print("nav:", json.dumps({k: v for k, v in out.items() if k != "rows"}))
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("probe", "nav")); ap.add_argument("repo"); ap.add_argument("corpus")
    ap.add_argument("base_url"); ap.add_argument("model")
    ap.add_argument("--name"); ap.add_argument("--dirs", type=int, default=5); ap.add_argument("--files", type=int, default=5)
    ap.add_argument("--context", choices=("none", "card"), default="none"); ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=8, help="concurrent requests for `nav` (vLLM batches them)")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    a.name = a.name or Path(a.repo).resolve().name
    key = os.environ.get("HOBBES_LLM_API_KEY", "")
    graph = artifacts.load_graph(Path(a.repo))
    result = (probe if a.mode == "probe" else nav)(a, graph, Path(a.corpus), key)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
