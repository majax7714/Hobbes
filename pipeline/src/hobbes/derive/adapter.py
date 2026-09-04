"""The orchestrator adapter — Calvin M0 §2.2, step 4 of §8. Arm T's driver.

The one place a model is called. OpenAI-compatible chat completions
only (the owned loop's :class:`hobbes.agent.loop.Endpoint`, so the
window fitting and the retry discipline are the ones every run has
used): one endpoint URL, one model id, one **versioned system prompt**
(``SYSTEM_PROMPT_VERSION``), temperature 0. The adapter renders a
template to the prompt (`holes.render`), reads one JSON document back,
validates every fill against its hole's shape (`holes.validate_fills`),
returns malformed fills **once** for repair, and records every exchange
— request, response, latency, tokens, the validation verdict — so a
reader can replay the run from the record alone.

**Arm T, one pass** (`run_t`): round 1 asks only the round-1 holes
(``UNRESOLVED``, ``ANCHOR_CONFIRM``, ``ANCHOR``) on a view of the
template that holds nothing else; `template.apply_round1` rebuilds the
structure from the answers and the answers are carried into the
rebuilt template as filled holes, so the reader sees what was said;
round 2 asks the structural holes; the pruning rules and the grounder
(`ground.ground`) run on the answers. **T-loop** is exactly one more
exchange: the grounder's NULL list becomes a *narrower* template —
only the holes whose fills carried a NULL, each listing the terms that
did not bind and the nearest graph names — and the grounder runs again
on the merged fills. The loop closes a NULL or it does not; the record
says which, by §4.3 class.

What the adapter never does: resolve a name, place an edit, or improve
a fill. It carries text between the orchestrator and Hobbes and writes
down what it carried (charter §3: the orchestrator is trusted about
intent and about nothing in the repo).
"""
from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path

from hobbes.derive import ground as G
from hobbes.derive import holes as H
from hobbes.derive import template as T
from hobbes.derive.cochange import CoChange

SYSTEM_PROMPT_VERSION = 2
SYSTEM_PROMPT = """You are the orchestrator for a code change. You know the task's intent, the language and the world; you do not know this repository, and you must not pretend to.

Hobbes knows the repository at one commit exactly: it has expanded the task into a template of typed holes, each with a span (path and lines at that commit), the code currently in the span, why the hole exists, and the answer shape. A separate deterministic grounder will bind every name in your answers against the repository; a name that does not exist there is reported back to you, never silently accepted. So:

- Answer every open hole by id, in the exact shape shown. "unchanged" is a complete and welcome answer. Holes of a type listed as pattern-fillable may be answered together with `patterns`. The one exception: an ANCHOR_CONFIRM you leave unanswered counts as "no" — when a module is shown symbol by symbol, answer only the symbols the task concerns.
- Write only names you have seen in the template, names the task itself gives, or names you declare in your own answers (a new function you write). If you need something you have not seen, declare it: a NEW_SYMBOL fill, or classify the term "new" in UNRESOLVED.
- A fill for a span is the whole span rewritten, not a fragment and not a diff.
- Keep changes to what the task asks. Do not refactor, rename or "improve" around it.
- Be short where nothing changes: give `patterns` for every type you leave entirely unchanged (CALLER_UPDATE, MODULE_REGION, TEST_EXPECTATION, COCHANGE_TOUCH) and list under `fills` only the holes you change or that take no pattern. A reply that answers hundreds of holes one by one is cut off before it ends.
- A caller or a test is shown as one line first. Answer "yes" with a reason and no body when it must change; you will be shown its whole span next and asked for the rewrite.
- Something the repository lacks — a new function, a new file — is a NEW_SYMBOL fill with a name, a file (a new path is created), a position and the body; not a covered_by pointing at a hole that carries no code.
- Reply with one JSON document and nothing else: {"fills": {"<hole id>": <fill>, ...}, "patterns": {"<TYPE>": "unchanged", ...}}. No prose before or after it. A fenced ```json block is accepted."""

ROUND1_TYPES = ("UNRESOLVED", "ANCHOR_CONFIRM", "ANCHOR")
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


# ---------------------------------------------------------------- parsing

def parse_document(text: str) -> dict | None:
    """The JSON document in a reply: the whole text, else the first fenced block, else the outermost braces. None when nothing parses to an object."""
    candidates = [text.strip()]
    candidates += [m.group(1).strip() for m in _FENCE.finditer(text)]
    if "{" in text and "}" in text:
        candidates.append(text[text.index("{"): text.rindex("}") + 1])
    for c in candidates:
        try:
            doc = json.loads(c)
        except ValueError:
            continue
        if isinstance(doc, dict):
            return doc
    return None


# ---------------------------------------------------------------- adapter

class Adapter:
    """One endpoint, one model, one system prompt; every exchange recorded in ``self.exchanges``."""

    def __init__(self, endpoint, model_id: str, max_tokens: int = 16384, max_prompt_chars: int = 300_000):
        self.endpoint = endpoint
        self.model_id = model_id
        self.max_tokens = max_tokens
        #: A rendered template longer than this is asked in chunks, one group of files at a time (step 4's first pass sent a
        #: 1.5 MB prompt and got "unchanged" for everything back). A cost cap, declared.
        self.max_prompt_chars = max_prompt_chars
        self.exchanges: list[dict] = []

    def _call(self, messages: list[dict], purpose: str) -> str:
        t0 = time.monotonic()
        reply = self.endpoint.chat(messages, [], self.max_tokens)
        text = ((reply.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        usage = reply.get("usage") or {}
        self.exchanges.append({
            "n": len(self.exchanges) + 1, "purpose": purpose, "model": self.model_id, "system_prompt_version": SYSTEM_PROMPT_VERSION,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "wall_ms": int((time.monotonic() - t0) * 1000),
            "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
            "finish_reason": (reply.get("choices") or [{}])[0].get("finish_reason"),
            "request": messages, "response": text,
        })
        return text

    def ask(self, template: dict, repo_root: Path, purpose: str) -> tuple[dict | None, dict[str, list[str]]]:
        """Fills for the template's open holes: one exchange per chunk (a template over the prompt budget is split by file), and one repair exchange per chunk when its document is malformed. Returns ``(document, remaining errors)``."""
        chunks = chunk_by_file(template, repo_root, self.max_prompt_chars)
        if len(chunks) == 1:
            return self._ask_one(chunks[0], repo_root, purpose)
        doc: dict = {"fills": {}, "patterns": {}}
        errs: dict[str, list[str]] = {}
        for i, ch in enumerate(chunks, 1):
            d, e = self._ask_one(ch, repo_root, f"{purpose} [chunk {i}/{len(chunks)}]")
            if d:
                doc["fills"].update(d.get("fills") or {})
                for typ, v in (d.get("patterns") or {}).items():  # a pattern answered in one chunk covers that chunk's holes only
                    for h in ch["holes"]:
                        if h["type"] == typ and h["id"] not in doc["fills"] and h.get("closed") is None and "fill" not in h:
                            doc["fills"][h["id"]] = v if typ in ("MODULE_REGION", "TEST_EXPECTATION") else {"decision": "no", "reason": f"pattern: {v}"}
            errs.update(e)
        return doc, errs

    def _ask_one(self, template: dict, repo_root: Path, purpose: str) -> tuple[dict | None, dict[str, list[str]]]:
        prompt = H.render(template, repo_root)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        text = self._call(messages, purpose)
        cut = self.exchanges[-1].get("finish_reason") == "length"
        doc = parse_document(text)
        errs = H.validate_fills(template, doc) if doc is not None else {"document": ["the reply is not a JSON object"]}
        self.exchanges[-1]["validation"] = errs
        if not errs:
            return doc, {}
        repair = ("Your answer was cut off at the reply limit before it ended. " if cut else "Your answer did not validate. ") + \
            "Reply with the whole document again: `patterns` for every type left unchanged, and under `fills` only the holes you change or that take no pattern. Fix these:\n" + \
            "\n".join(f"- {k}: {'; '.join(v)}" for k, v in sorted(errs.items())[:40])
        messages = messages + [{"role": "assistant", "content": text}, {"role": "user", "content": repair}]
        text2 = self._call(messages, purpose + " (repair)")
        doc2 = parse_document(text2)
        errs2 = H.validate_fills(template, doc2) if doc2 is not None else {"document": ["the reply is not a JSON object"]}
        self.exchanges[-1]["validation"] = errs2
        return (doc2 if doc2 is not None else doc), errs2


# ------------------------------------------------------------------ arm T

def round1_view(template: dict) -> dict:
    """The template with only its open round-1 holes: what the orchestrator sees before any structure."""
    v = copy.deepcopy(template)
    v["holes"] = [h for h in v["holes"] if h["type"] in ROUND1_TYPES and h.get("closed") is None and "fill" not in h]
    v.pop("neighborhood", None)
    return v


def chunk_by_file(template: dict, repo_root: Path, budget: int) -> list[dict]:
    """The template as one view, or as views over groups of files whose render fits the budget; holes without a span ride the first chunk. Deterministic in the hole order."""
    if len(H.render(template, repo_root)) <= budget:
        return [template]
    open_ = [h for h in template["holes"] if h.get("closed") is None and "fill" not in h]
    by_file: dict[str | None, list[dict]] = {}
    for h in open_:
        by_file.setdefault((h.get("span") or {}).get("path"), []).append(h)
    groups: list[list[str | None]] = []
    cur: list[str | None] = []
    cur_len = 0

    def view(paths):
        v = copy.deepcopy(template)
        v["holes"] = [h for h in open_ if (h.get("span") or {}).get("path") in paths]
        v.pop("neighborhood", None)
        return v

    for path in [None] + sorted(p for p in by_file if p is not None):
        if path not in by_file:
            continue
        size = len(H.render(view([path]), repo_root))
        if cur and cur_len + size > budget:
            groups.append(cur)
            cur, cur_len = [], 0
        cur.append(path)
        cur_len += size
    if cur:
        groups.append(cur)
    return [view(g) for g in groups]


def yes_followup(t2: dict, doc: dict) -> dict | None:
    """The holes answered "yes" without a body (callers, partners) and expectations without code, each shown its whole span: the follow-up view. None when there is none."""
    ids = []
    for h in t2["holes"]:
        f = (doc.get("fills") or {}).get(h["id"])
        if h["type"] in ("CALLER_UPDATE", "COCHANGE_TOUCH") and isinstance(f, dict) and f.get("decision") == "yes" and not f.get("body"):
            ids.append(h["id"])
        elif h["type"] == "TEST_EXPECTATION" and isinstance(f, dict) and f.get("expectation") and not f.get("code"):
            ids.append(h["id"])
    if not ids:
        return None
    v = copy.deepcopy(t2)
    v["holes"] = []
    for h in t2["holes"]:
        if h["id"] in ids:
            h2 = copy.deepcopy(h)
            h2["show_span"] = True
            h2["previous_fill"] = doc["fills"][h["id"]]
            h2["ask"] = (h2.get("ask") or H.HOLE_TYPES[h2["type"]]) + " — you said this changes; here is the whole span: answer again with the rewrite in `body` (or `code`), or say no"
            v["holes"].append(h2)
    v.pop("neighborhood", None)
    return v


def carry_round1(t2: dict, base: dict, fills1: dict, source: str) -> None:
    """Every round-1 hole that was answered appears in the rebuilt template as a *filled* hole (in place), so round 2's reader sees what was said — the ones the rebuild kept, and the ones it dropped (a refused confirmation, an answered ANCHOR), prepended."""
    present = {h["id"]: h for h in t2["holes"]}
    carried = []
    for h in base["holes"]:
        if h["type"] not in ROUND1_TYPES or h["id"] not in fills1 or (isinstance(fills1[h["id"]], dict) and fills1[h["id"]].get("unanswered")):
            continue
        if h["id"] in present:
            present[h["id"]]["fill"] = fills1[h["id"]]
            present[h["id"]]["fill_source"] = source
        else:
            carried.append({**copy.deepcopy(h), "fill": fills1[h["id"]], "fill_source": source})
    t2["holes"][:0] = carried


def narrow(t2: dict, doc: dict, g: dict) -> dict | None:
    """The NULL list as a narrower template: only the holes whose fills carried a NULL, each naming the terms that did not bind and the nearest graph names. None when there is no NULL."""
    if not g["null"]:
        return None
    by_hole: dict[str, list[dict]] = {}
    for n in g["null"]:
        hid = n["hole"].split("[")[0]
        by_hole.setdefault(hid, []).append(n)
    v = copy.deepcopy(t2)
    v["holes"] = []
    for h in t2["holes"]:
        if h["id"] not in by_hole:
            continue
        h2 = copy.deepcopy(h)
        h2.pop("fill", None)
        h2.pop("fill_source", None)
        h2["provenance"] = {**h2.get("provenance", {}),
                            "NULL": "; ".join(f"`{n['term']}` at {n['path']}:{n['line']} ({n['null_class']}; nearest in the graph: {', '.join(n['nearest'])})" for n in by_hole[h["id"]])}
        h2["ask"] = (h2.get("ask") or H.HOLE_TYPES[h2["type"]]) + " — your previous answer named symbols that do not exist at this commit (see NULL); answer again using only names that exist or that you declare"
        h2["previous_fill"] = doc["fills"].get(h["id"])
        v["holes"].append(h2)
    v.pop("neighborhood", None)
    return v


def run_t(task: str, template: dict, L: T.Ledger, repo_root: Path, cochange: CoChange | None, adapter: Adapter, *, null_loop: bool = True) -> dict:
    """Arm T for one unit: round 1 → rebuild → round 2 → prune → ground, then (T-loop) one NULL round-trip. Returns the per-unit record."""
    t1 = copy.deepcopy(template)
    rec: dict = {"key": {**t1["key"], "model_id": adapter.model_id, "system_prompt_version": SYSTEM_PROMPT_VERSION}, "rounds": []}
    t2 = t1
    base = copy.deepcopy(t1)  # every round-1 hole ever asked, so a refused confirmation stays refused across passes
    fills1: dict = {}
    for pass_ in (1, 2, 3):  # another pass only when the rebuild opened new round-1 holes: an ANCHOR hole after every refusal, or a named module's symbols
        view = round1_view(t2)
        if not view["holes"]:
            break
        doc1, errs1 = adapter.ask(view, repo_root, f"round 1{'' if pass_ == 1 else 'bc'[pass_ - 2]}")
        answers = (doc1 or {}).get("fills") or {}
        fills1.update(answers)
        for h in view["holes"]:  # step 6: a confirmation left unanswered is a refusal, recorded as one, never carried as a filled hole
            if h["type"] == "ANCHOR_CONFIRM" and h["id"] not in answers:
                fills1[h["id"]] = {"confirm": False, "unanswered": True}
        row = {"round": 1 if pass_ == 1 else "1" + "bc"[pass_ - 2], "holes_asked": [h["id"] for h in view["holes"]], "fills": doc1, "errors": errs1,
               "unanswered_confirmations": sum(1 for h in view["holes"] if h["type"] == "ANCHOR_CONFIRM" and h["id"] not in answers)}
        t2 = T.apply_round1(task, L, repo_root, cochange, base, fills1)
        known = {h["id"] for h in base["holes"]}
        base["holes"] += [copy.deepcopy(h) for h in t2["holes"] if h["type"] in ROUND1_TYPES and h["id"] not in known]
        carry_round1(t2, base, fills1, f"orchestrator {adapter.model_id}, round 1")
        for h in view["holes"]:
            if h["type"] == "ANCHOR" and isinstance(answers.get(h["id"]), dict):
                bound = {a["term"] for a in t2["anchors"]}
                row["anchor_names_unbound"] = [n for n in answers[h["id"]].get("names", []) if n not in bound]
        rec["rounds"].append(row)
    rec["template_round1"] = t1
    rec["template_round2"] = copy.deepcopy(t2)
    doc2, errs2 = adapter.ask(t2, repo_root, "round 2")
    doc2 = doc2 or {"fills": {}, "patterns": {}}
    rec["rounds"].append({"round": 2, "holes_asked": [h["id"] for h in t2["holes"] if h.get("closed") is None and "fill" not in h], "fills": doc2, "errors": errs2})
    t2b = yes_followup(t2, doc2)
    if t2b is not None:  # the "yes" answers see their spans and give the rewrite
        doc2b, errs2b = adapter.ask(t2b, repo_root, "round 2b")
        for hid, fill in ((doc2b or {}).get("fills") or {}).items():
            if hid in {h["id"] for h in t2b["holes"]}:
                doc2["fills"][hid] = fill
        rec["rounds"].append({"round": "2b", "holes_asked": [h["id"] for h in t2b["holes"]], "fills": doc2b, "errors": errs2b})
    g = G.ground(copy.deepcopy(t2), doc2, L, repo_root)
    rec["ground"] = g
    if null_loop:
        t3 = narrow(t2, doc2, g)
        if t3 is not None:
            doc3, errs3 = adapter.ask(t3, repo_root, "NULL round-trip")
            merged = copy.deepcopy(doc2)
            for hid, fill in ((doc3 or {}).get("fills") or {}).items():
                merged["fills"][hid] = fill
            rec["rounds"].append({"round": 3, "holes_asked": [h["id"] for h in t3["holes"]], "fills": doc3, "errors": errs3})
            g2 = G.ground(copy.deepcopy(t2), merged, L, repo_root)
            rec["ground_after_loop"] = g2
            before = {(n["hole"], n["term"], n["null_class"]) for n in g["null"]}
            after = {(n["hole"], n["term"], n["null_class"]) for n in g2["null"]}
            rec["loop"] = {"nulls_before": len(before), "nulls_after": len(after),
                           "closed_by_class": _by_class(before - after), "opened_by_class": _by_class(after - before)}
    rec["exchanges"] = adapter.exchanges
    rec["tokens"] = {"prompt": sum(e.get("prompt_tokens") or 0 for e in adapter.exchanges), "completion": sum(e.get("completion_tokens") or 0 for e in adapter.exchanges)}
    rec["wall_ms"] = sum(e["wall_ms"] for e in adapter.exchanges)
    return rec


def _by_class(rows: set) -> dict:
    out: dict[str, int] = {}
    for _, _, cls in rows:
        out[cls] = out.get(cls, 0) + 1
    return out


# -------------------------------------------------------- §4.2 agreement

def unresolved_truth(term: str, L: T.Ledger, gold_files: set[str], gold_declared: set[str]) -> str:
    """The class the gold diff gives an unresolved term: ``new`` if the diff declares it, ``refers`` if it names a symbol in a file the diff touches, else ``not-code``."""
    t = term.strip(".,;:`'\"")
    if t in gold_declared or t.replace("-", "_") in gold_declared:
        return "new"
    for node in T._resolve_name(L, t):
        path = L.path_of(node) if node in L.symbols else L.mod_path.get(node)
        if path in gold_files:
            return "refers"
    return "not-code"


def score_unresolved(fill: dict | None, hole: dict, L: T.Ledger, gold_files: set[str], gold_declared: set[str]) -> dict:
    """§4.2: the orchestrator's class per unresolved term against the gold truth; agreement count and the confusion rows."""
    rows = []
    classes = (fill or {}).get("classes") or {}
    for term in hole.get("terms", []):
        truth = unresolved_truth(term["term"], L, gold_files, gold_declared)
        rows.append({"term": term["term"], "orchestrator": classes.get(term["term"]), "gold": truth})
    return {"n": len(rows), "agree": sum(1 for r in rows if r["orchestrator"] == r["gold"]), "rows": rows}
