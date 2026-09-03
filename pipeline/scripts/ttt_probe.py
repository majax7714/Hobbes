"""The memorisation probe and the held-out navigation evaluation (ADR-099 §4.4, §4.5).

    HOBBES_LLM_API_KEY=… uv run scripts/ttt_probe.py probe <repo> <corpus-dir> <base_url> <model> [--dirs 5] [--files 5] [--out f.json]
    HOBBES_LLM_API_KEY=… uv run scripts/ttt_probe.py nav <repo> <corpus-dir> <base_url> <model> [--context none|card|card-refuse] [--limit N] [--out f.json]
    uv run scripts/ttt_probe.py rescore <repo> <corpus-dir> <old-probe.json> --out <new.json>

``probe`` is unaided, temperature 0, given only the repo's name and a
path: (1) list the files under a directory, precision and recall
against the real tree; (2) the functions defined in a file, against the
graph; (3) the thirty navigation items ``derive-corpus`` drew. The score
gates a repo into the memorised or the unseen cell (>0.5 / <0.15). The
files part is also scored with generic names dropped and against the
union of trees across the repo's tagged releases, naming the tag that
fits best (``score_stoplisted``, ``score_any_version``, ``best_tags``):
a model holding an older copy of the repo reads as ignorant at the SHA
otherwise (C-83). ``rescore`` recomputes that part for an old probe
record from its stored replies (the first runs kept only a 160-char
head; a row is marked ``truncated`` when the head may have cut names).

``nav`` asks every ``eval.jsonl`` item — the held-out symbols' questions
and the absent family's distractors — and scores what each reply names
(`hobbes.ttt.score`). ``--context card`` puts the symbol's own card in
the prompt (the reading-comprehension control); ``--context card-refuse``
adds an explicit instruction to abstain when the symbol is not listed
(the abstention control, review item 4); ``--context none`` is the
weights-only arm. The *model* is the arm: the base name or an adapter's
name on the same endpoint. Every record carries the ``template_hash``
of the wording it was asked under and the ``scorer_version`` it was
scored with.

Computes; does not interpret.
"""
import argparse
import hashlib
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
from hobbes.ttt import score as scoring
from hobbes.ttt.probe import (CONTEXTS, SYSTEM, listed_files, render_context, score_files, tag_trees,
                              template_hash)
from hobbes.ttt.score import known_names, score_reply, summarise

SCORER_VERSION = getattr(scoring, "SCORER_VERSION", 1)


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
    out = {"model": a.model, "repo": a.name, "sha": graph.get("sha"), "parts": {},
           "template_hash": template_hash("none"), "scorer_version": SCORER_VERSION}
    trees = tag_trees(repo_root, a.tags)
    # (1) files under a directory — at the SHA, stoplisted, and against any tagged release.
    rows = []
    for d in pick_dirs(graph, a.dirs):
        real = {p.name for p in (repo_root / d).iterdir() if p.is_file()} if (repo_root / d).is_dir() else set()
        reply = ask(a.base_url, a.model, key, system, f"List the files directly under `{d}/` in {a.name} (at {sha12}), one file name per line.")
        rows.append({"dir": d, **score_files(listed_files(reply), real, trees, d), "reply": reply, "reply_head": reply[:160]})
        print(f"files {d:40} P {rows[-1]['precision']:.2f} R {rows[-1]['recall']:.2f} ({rows[-1]['hit']}/{rows[-1]['truth']})"
              f"  any-version {rows[-1]['precision_any_version']:.2f} {rows[-1]['best_tag'] or '-'}")
    out["parts"]["files"] = rows
    out["tags_considered"] = len(trees)
    # (2) functions in a file.
    rows = []
    for path, names in pick_files(graph, a.files):
        reply = ask(a.base_url, a.model, key, system, f"What functions, methods and classes are defined in `{path}` in {a.name} (at {sha12})? Names only, one per line.")
        listed = set(_TOKEN.findall(reply)) & {n for n in names} | {t for t in _TOKEN.findall(reply) if t in names}
        rows.append({"file": path, **prf(set(_TOKEN.findall(reply)), set(names)), "reply": reply, "reply_head": reply[:160]})
        print(f"defs  {path:40} P {rows[-1]['precision']:.2f} R {rows[-1]['recall']:.2f} ({rows[-1]['hit']}/{rows[-1]['truth']})")
    out["parts"]["definitions"] = rows
    # (3) navigation items, no context.
    known = known_names(graph)
    rows = []
    for rec in (json.loads(ln) for ln in (corpus_dir / "probe-nav.jsonl").read_text().splitlines() if ln.strip()):
        reply = ask(a.base_url, a.model, key, system, rec["messages"][0]["content"])
        rows.append({"family": rec["family"], "symbol": rec["symbol"], **score_reply(rec, reply, known), "reply": reply})
    out["parts"]["navigation"] = {"rows": rows, **summarise(rows)}
    finish(out)
    print(f"probe: files-P {out['means'][0]:.2f}  defs-R {out['means'][1]:.2f}  nav {out['means'][2]:.2f}  → score {out['score']}  "
          f"cell {out['cell']}  (stoplisted {out['score_stoplisted']}, any-version {out['score_any_version']}, best tags {out['best_tags']})")
    return out


def finish(out: dict) -> dict:
    """The probe's scores from its parts: ``score``/``cell`` at the SHA, raw
    (the gate, unchanged); beside them the stoplisted and any-version
    variants and the tags that fit best."""
    files, defs = out["parts"]["files"], out["parts"]["definitions"]
    nav = out["parts"]["navigation"]["navigation_mean"] or 0.0
    defs_r = sum(r["recall"] for r in defs) / max(1, len(defs))

    def files_mean(key: str) -> float:
        return sum(r.get(key, r["precision"]) for r in files) / max(1, len(files))

    means = [files_mean("precision_at_sha"), defs_r, nav]
    out["means"] = [round(m, 3) for m in means]
    out["score"] = round(sum(means) / 3, 3)
    out["cell"] = "M" if out["score"] > 0.5 else "U" if out["score"] < 0.15 else "neither"
    out["score_at_sha"] = out["score"]
    out["score_stoplisted"] = round((files_mean("precision_at_sha_stoplisted") + defs_r + nav) / 3, 3)
    out["score_any_version"] = round((files_mean("precision_any_version") + defs_r + nav) / 3, 3)
    tags: dict[str, int] = {}
    for r in files:
        if r.get("best_tag"):
            tags[r["best_tag"]] = tags.get(r["best_tag"], 0) + 1
    out["best_tags"] = dict(sorted(tags.items(), key=lambda kv: (-kv[1], kv[0])))
    return out


def rescore(a, graph, corpus_dir, key) -> dict:
    """Recompute the files part of an old probe record from its stored
    replies (``reply`` when kept, else the 160-char ``reply_head``)."""
    old = json.loads(Path(a.old).read_text())
    repo_root = Path(a.repo)
    trees = tag_trees(repo_root, a.tags)
    rows = []
    for r in old["parts"]["files"]:
        d = r["dir"]
        real = {p.name for p in (repo_root / d).iterdir() if p.is_file()} if (repo_root / d).is_dir() else set()
        text = r.get("reply") if r.get("reply") is not None else r.get("reply_head", "")
        row = {"dir": d, **score_files(listed_files(text), real, trees, d)}
        row["truncated"] = r.get("reply") is None and len(r.get("reply_head", "")) >= 160
        row["reply_head"] = r.get("reply_head", "")
        if r.get("reply") is not None:
            row["reply"] = r["reply"]
        rows.append(row)
    out = dict(old)
    out["parts"] = dict(old["parts"], files=rows)
    out["tags_considered"] = len(trees)
    out["rescored_from"] = str(a.old)
    out["scorer_version"] = SCORER_VERSION
    out.setdefault("template_hash", template_hash("none"))
    finish(out)
    print(f"rescore: score {out['score']} cell {out['cell']}  stoplisted {out['score_stoplisted']}  "
          f"any-version {out['score_any_version']}  best tags {out['best_tags']}  "
          f"truncated rows {sum(1 for r in rows if r['truncated'])}/{len(rows)}")
    return out


def nav(a, graph, corpus_dir, key) -> dict:
    sha12 = graph.get("sha", "")[:12]
    system = SYSTEM.format(repo=a.name, sha12=sha12)
    cards = {}
    if a.context != "none":
        for ln in (corpus_dir / "eval-cards.jsonl").read_text().splitlines():
            if ln.strip():
                c = json.loads(ln); cards[c["symbol"]] = c["messages"][1]["content"]
    known = known_names(graph)
    if a.items == "train":
        # A seeded sample of the *training* questions: does the adapter hold
        # the symbol-grain edges it was shown? (The held-out set cannot ask
        # that — a held-out symbol's edges were removed from training.)
        items = [json.loads(ln) for ln in (corpus_dir / "train.jsonl").read_text().splitlines() if ln.strip()]
        items = [r for r in items if r["kind"] == "qa"]
        items.sort(key=lambda r: hashlib.sha256(f"{a.seed}\n{r['family']}\n{r['symbol']}".encode()).hexdigest())
    else:
        items = [json.loads(ln) for ln in (corpus_dir / "eval.jsonl").read_text().splitlines() if ln.strip()]
    items = items[:a.limit] if a.limit else items

    def one(rec: dict) -> dict:
        user = render_context(a.context, rec["symbol"], cards.get(rec["symbol"]), sha12) + rec["messages"][0]["content"]
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
    out = {"model": a.model, "repo": a.name, "sha": graph.get("sha"), "context": a.context, "items": a.items,
           "template_hash": template_hash(a.context), "scorer_version": SCORER_VERSION,
           "rows": rows, **summarise(rows)}
    print("nav:", json.dumps({k: v for k, v in out.items() if k != "rows"}))
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("probe", "nav", "rescore")); ap.add_argument("repo"); ap.add_argument("corpus")
    ap.add_argument("base_url", help="the endpoint; for `rescore`, the old probe record to rescore")
    ap.add_argument("model", nargs="?", default="")
    ap.add_argument("--tags", type=int, default=30, help="tagged releases considered for the any-version file score")
    ap.add_argument("--name"); ap.add_argument("--dirs", type=int, default=5); ap.add_argument("--files", type=int, default=5)
    ap.add_argument("--context", choices=CONTEXTS, default="none"); ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=8, help="concurrent requests for `nav` (vLLM batches them)")
    ap.add_argument("--items", choices=("eval", "train"), default="eval",
                    help="`nav` over the held-out questions (default) or a seeded sample of the training questions")
    ap.add_argument("--seed", type=int, default=0, help="the training-sample seed")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    a.name = a.name or Path(a.repo).resolve().name
    key = os.environ.get("HOBBES_LLM_API_KEY", "")
    graph = artifacts.load_graph(Path(a.repo))
    if a.mode == "rescore":
        a.old = a.base_url
    result = {"probe": probe, "nav": nav, "rescore": rescore}[a.mode](a, graph, Path(a.corpus), key)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
