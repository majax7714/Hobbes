"""Repo-familiarity probe (C-56): how much of a repository does a model
already hold, with no tools? The xarray check (C-39, verbatim gold recall)
applied to the *repo* rather than the patch, so a pure score can carry a
recall caveat of its own.

    HOBBES_LLM_API_KEY=… uv run scripts/deepswe_familiarity.py <repo> <base_url> <model> [--k 8] [--symbol ID ...] [--out file.json]

Picks K functions/methods from the ingested graph (`.hobbes/derived/graph.json`
— the named `--symbol`s first, then the longest remaining functions, deterministic),
asks the model to reproduce each one's source verbatim given only the repo,
path, and qualified name, and scores the reply against the checkout: exact
match, difflib line ratio, and the fraction of the function's non-blank lines
reproduced verbatim. Prints a table and writes JSON. Computes; does not interpret.
"""
import argparse
import difflib
import json
import os
import sys
import urllib.request
from pathlib import Path

PROMPT = (
    "You are being tested on recall, not on writing code. Reproduce, verbatim and "
    "complete, the source of `{symbol}` as it appears in `{path}` of the {repo} "
    "repository (commit {commit}). Output only the code, no commentary, no fences. "
    "{escape}"
)
# Forced reconstruction is the default: with an UNKNOWN escape the 27B declined
# even `textwrap.dedent` (2026-08-22), so the escape measures refusal, not
# recall. Forced, a model that holds the text reproduces lines verbatim; one
# that holds only the API's shape produces a plausible wrong body — which the
# verbatim-line fraction separates.
ESCAPE_FORCED = "Do your best reconstruction even if unsure."
ESCAPE_ALLOWED = "If you do not know it, output exactly: UNKNOWN"


def pick(graph: dict, k: int, named: list[str]) -> list[dict]:
    syms = [s for s in graph.get("symbols", []) if s.get("kind") in ("function", "method") and s.get("line") and s.get("end_line")]
    by_id = {s["id"]: s for s in syms}
    chosen = [by_id[n] for n in named if n in by_id]
    rest = sorted((s for s in syms if s["id"] not in {c["id"] for c in chosen} and (s["end_line"] - s["line"]) >= 8),
                  key=lambda s: (-(s["end_line"] - s["line"]), s["id"]))
    return (chosen + rest)[:k]


def source_of(repo: Path, graph: dict, sym: dict) -> tuple[str, str]:
    mod = next((n for n in graph.get("nodes", []) if n["id"] == sym.get("module")), {})
    path = mod.get("path") or sym.get("path") or ""
    lines = (repo / path).read_text(errors="replace").splitlines()
    return path, "\n".join(lines[sym["line"] - 1 : sym["end_line"]])


def ask(base_url: str, model: str, key: str, prompt: str, max_tokens: int = 4096) -> str:
    # A thinking model (Qwen3.x) spends its budget on reasoning and returns an
    # empty `content` — the first probe read 0.00 everywhere for that reason.
    # Thinking is disabled for recall (vLLM's chat_template_kwargs); if a
    # server ignores it, the reasoning text is scored instead of nothing.
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0,
                       "max_tokens": max_tokens, "chat_template_kwargs": {"enable_thinking": False}}).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        msg = json.loads(r.read())["choices"][0]["message"]
    return (msg.get("content") or msg.get("reasoning_content") or "").strip()


def score(truth: str, reply: str) -> dict:
    def norm(t: str) -> list[str]:
        return [ln.rstrip() for ln in t.strip("\n").splitlines()]
    t, r = norm(truth), norm(reply.replace("```python", "").replace("```", ""))
    tl = [ln.strip() for ln in t if ln.strip()]
    rl = {ln.strip() for ln in r if ln.strip()}
    verbatim = sum(1 for ln in tl if ln in rl) / max(1, len(tl))
    return {"unknown": reply.strip() == "UNKNOWN", "exact": t == r, "line_ratio": round(difflib.SequenceMatcher(None, t, r).ratio(), 3),
            "verbatim_line_fraction": round(verbatim, 3), "truth_lines": len(tl)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", type=Path); ap.add_argument("base_url"); ap.add_argument("model")
    ap.add_argument("--k", type=int, default=8); ap.add_argument("--symbol", action="append", default=[])
    ap.add_argument("--repo-name", default=None); ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--allow-unknown", action="store_true", help="offer the UNKNOWN escape (measures refusal more than recall)")
    a = ap.parse_args(argv)
    key = os.environ.get("HOBBES_LLM_API_KEY", "")
    graph = json.loads((a.repo / ".hobbes/derived/graph.json").read_text())
    commit = graph.get("repo_sha") or graph.get("sha") or graph.get("git_sha") or "HEAD"
    name = a.repo_name or a.repo.name
    rows = []
    for sym in pick(graph, a.k, a.symbol):
        path, truth = source_of(a.repo, graph, sym)
        escape = ESCAPE_ALLOWED if a.allow_unknown else ESCAPE_FORCED
        reply = ask(a.base_url, a.model, key, PROMPT.format(symbol=sym["id"], path=path, repo=name, commit=commit, escape=escape))
        rows.append({"symbol": sym["id"], "path": path, **score(truth, reply), "reply_head": reply[:200]})
        r = rows[-1]
        print(f"{r['symbol'][:52]:52} {'UNKNOWN' if r['unknown'] else 'exact' if r['exact'] else '':8} ratio {r['line_ratio']:.2f}  verbatim {r['verbatim_line_fraction']:.2f}  ({r['truth_lines']} lines)")
    n = len(rows) or 1
    summary = {"model": a.model, "repo": name, "commit": commit, "k": len(rows), "escape": "allowed" if a.allow_unknown else "forced",
               "unknown": sum(r["unknown"] for r in rows), "exact": sum(r["exact"] for r in rows),
               "mean_line_ratio": round(sum(r["line_ratio"] for r in rows) / n, 3),
               "mean_verbatim_line_fraction": round(sum(r["verbatim_line_fraction"] for r in rows) / n, 3)}
    print("familiarity:", json.dumps(summary))
    if a.out:
        a.out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
