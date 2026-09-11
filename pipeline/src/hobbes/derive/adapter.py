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
exchange (`null_round_trip`): the grounder's NULL list becomes a
*narrower* template — since protocol v0.4, a **declaration hole** (a
``NEW_SYMBOL`` for one name) for every name a fill wrote at a call site
and nothing declares, and the holes whose fills carried any other NULL,
each listing the terms that did not bind and the nearest graph names —
and the grounder runs again on the merged fills with the declaration
holes placed, so a declared name binds as a gensym at the call site it
was written at. Since v0.5 the grounder holds a declaration's body to
the repository's world, and a NULL raised inside it goes back once, as
a repair of that same declaration hole — one exchange, never a loop.
The loop closes a NULL or it does not; the record says which, per site
and by §4.3 class.

What the adapter never does: resolve a name, place an edit, or improve
a fill. It carries text between the orchestrator and Hobbes and writes
down what it carried (charter §3: the orchestrator is trusted about
intent and about nothing in the repo).
"""
from __future__ import annotations

import collections
import copy
import json
import re
import time
from pathlib import Path

from hobbes.derive import ground as G
from hobbes.derive import harness as HV
from hobbes.derive import holes as H
from hobbes.derive import template as T
from hobbes.derive.cochange import CoChange

SYSTEM_PROMPT_VERSION = 2
#: The exchange protocol, recorded on every exchange and every arm-T record. v0.1 (M0 step 4): round 1 on a view, round 2b, chunks,
#: a cut reply repaired; v0.2 (step 6): candidates in the ANCHOR hole; **v0.3** (Calvin M0-Go WP-5, Max 2026-09-11): a pattern on
#: SIGNATURE, BODY or ANCHOR_CONFIRM is read per hole ("unchanged", "no") and recorded as arrived by pattern
#: (`holes.read_patterns`), and a refused pattern's holes are named in the repair (`holes.validate_fills`). The code carries no
#: switch: v0.3 supersedes v0.2. The system prompt is unchanged (v2) — the three types are accepted, not advertised.
#: **v0.4** (Calvin M0-Go WP-7a, Max 2026-09-11; WP-6's D-b and D-a): the NULL round-trip offers a declaration hole for every name
#: written at a call site and declared nowhere — the grounder's class ``new`` or ``invented``, the name in no module of the parent
#: graph nor among the post-image's declarations (`null_route`) — instead of re-asking the hole that wrote the call, which cannot
#: close it; once placed, the name binds as a gensym and the call site is grounded again. A near-miss is re-asked as in v0.3. And a
#: SIGNATURE or BODY fill carrying the render's line-number gutter is refused, a repairable error naming the hole
#: (`holes.carries_gutter`). v0.4 supersedes v0.3, no switch; the system prompt is unchanged (v2).
#: **v0.5** (Calvin M0-Go WP-9, Max 2026-09-11; WP-8's D-f, D-g, D-h): the grounding holds every Go fill to the world (grounder v2: an
#: import outside the standard library, the module and its go.mod's requires is a NULL ``import-outside``; a qualifier nothing binds a
#: NULL ``unimported``); a NULL raised inside a placed declaration's body goes back **once**, as a repair of that same declaration hole
#: (`declaration_repair`) — one exchange, no validation repair after it, never a loop; the declaration hole shows one sibling of the same
#: kind from its directory (`declaration_sibling`, ``SIBLING_RULE``); and the loop's site record reads the grounder's refused list, so a
#: refused declaration reads ``refused``, never ``placed``. v0.5 supersedes v0.4, no switch; the system prompt is unchanged (v2).
#: **v0.6** (Calvin M0-Go round 2, WP-14; WP-10's D-i, D-j, WP-12's D-l, D-n, D-o): the one declaration repair now reads *both* causes
#: at once — the grounder's world NULLs (unchanged) **and** a compile error (`harness.build_row`'s "go build ./..." step, trimmed to
#: the lines naming the declaration's file, `harness.trim_build_error`) — never a second exchange, the same one repair, its ask worded
#: for either cause or both (D-o). The sibling is shown **whole** (every line of its span), capped only by bytes (`SIBLING_BYTES`), not
#: by a line count (D-h's ``SIBLING_LINES`` is gone). Both arms share **one budget**: `Adapter.budget`, a count of exchanges (T) —
#: `run_t`'s `is_loop_exchange` still separates the loop's spend from T's own (D-i, now also true of the build-row check's own repair
#: exchange, unchanged in name from v0.5). D-i's other half: `usd_loop` (the driver's, `calvin_probe.py`) now recognizes "declaration
#: repair" as loop spend by its own purpose string rather than the ``NULL``-prefix test that missed it. D-n: `run_t` no longer hands
#: a dict it keeps mutating (round 2b's merge into round 2's fills) to its own record — the round-2 row is copied first. D-l: WP-11b/12's
#: path-explained flips are read (`docs/calvin/calvin-m0-go-r2.md`'s gate record) as a sampled earlier reply changing which path a run
#: took, not a protocol bug — no code follows from it; recorded in ``budget.md``, not here.
PROTOCOL_VERSION = "0.6"
#: How the declaration hole's sibling is chosen (unchanged since v0.5, D-h) and shown (v0.6, §2.4): whole, capped only by bytes.
#: ``SIBLING_BYTES`` is the gitleaks-rules distribution's 95th percentile (WP-14's ``budget.md``): the largest top-level function span
#: per file under ``cmd/generate/config/rules/*.go`` (non-test; n = 131), rounded up from 4380.5 to 4400.
SIBLING_BYTES = 4400
SIBLING_RULE = ("the same kind in the binding directory — a function, or a method of the same type when the hole declares a method — test files "
                "excluded: the one the fill that wrote the call also calls, called nearest the call site (ties: the earlier line, then the id); "
                "else the one with the most callers in the parent graph (ties: the id); else none. Shown whole (every line of its span), capped "
                f"only by bytes, at most {SIBLING_BYTES} characters (v0.6, D-h; the gitleaks rules/*.go 95th percentile)")
#: The NULL classes a v0.4 round-trip answers with a declaration hole rather than a re-ask.
DECLARE_CLASSES = ("new", "invented")
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

    def __init__(self, endpoint, model_id: str, max_tokens: int = 16384, max_prompt_chars: int = 300_000, budget: int | None = None):
        self.endpoint = endpoint
        self.model_id = model_id
        self.max_tokens = max_tokens
        #: A rendered template longer than this is asked in chunks, one group of files at a time (step 4's first pass sent a
        #: 1.5 MB prompt and got "unchanged" for everything back). A cost cap, declared.
        self.max_prompt_chars = max_prompt_chars
        #: v0.6 (§2.4, "one budget"): the number of model calls this adapter may make in all for one key — None is unbounded
        #: (round 1's condition). Once spent, `_ask_one` makes no further call and answers nothing for the holes it was asked:
        #: the reader's own reading (calvin-m0-go-r2 WP-14) is that an unanswered hole grounds as if it said nothing, which is
        #: exactly "unchanged" for a SIGNATURE/BODY/MODULE_REGION hole (the grounder emits no hunk for an unfilled one) — the run
        #: is not aborted, it is scored as it stands.
        self.budget = budget
        self.exchanges: list[dict] = []
        #: Asks answered as empty because the budget was already spent when they were made (counted, never called).
        self.budget_cuts = 0

    def at_budget(self) -> bool:
        return self.budget is not None and len(self.exchanges) >= self.budget

    def _call(self, messages: list[dict], purpose: str) -> str:
        t0 = time.monotonic()
        reply = self.endpoint.chat(messages, [], self.max_tokens)
        text = ((reply.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        usage = reply.get("usage") or {}
        self.exchanges.append({
            "n": len(self.exchanges) + 1, "purpose": purpose, "model": self.model_id, "system_prompt_version": SYSTEM_PROMPT_VERSION,
            "protocol_version": PROTOCOL_VERSION, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "wall_ms": int((time.monotonic() - t0) * 1000),
            "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
            "finish_reason": (reply.get("choices") or [{}])[0].get("finish_reason"),
            "request": messages, "response": text,
        })
        return text

    def ask(self, template: dict, repo_root: Path, purpose: str, *, repair: bool = True) -> tuple[dict | None, dict[str, list[str]]]:
        """Fills for the template's open holes: one exchange per chunk (a template over the prompt budget is split by file), and one repair exchange per chunk when its document is malformed — none when *repair* is False (v0.5's declaration repair is itself the one repair). Returns ``(document, remaining errors)``."""
        chunks = chunk_by_file(template, repo_root, self.max_prompt_chars)
        if len(chunks) == 1:
            return self._ask_one(chunks[0], repo_root, purpose, repair)
        doc: dict = {"fills": {}, "patterns": {}}
        errs: dict[str, list[str]] = {}
        for i, ch in enumerate(chunks, 1):
            d, e = self._ask_one(ch, repo_root, f"{purpose} [chunk {i}/{len(chunks)}]", repair)
            if d:
                doc["fills"].update(d.get("fills") or {})
                if d.get("by_pattern"):
                    doc.setdefault("by_pattern", {}).update(d["by_pattern"])
                for typ, v in (d.get("patterns") or {}).items():  # a pattern answered in one chunk covers that chunk's holes only
                    if typ not in H.PATTERN_TYPES:
                        continue  # a v0.3 pattern is already read per hole (`holes.read_patterns`); a refused one answers nothing
                    for h in ch["holes"]:
                        if h["type"] == typ and h["id"] not in doc["fills"] and h.get("closed") is None and "fill" not in h:
                            doc["fills"][h["id"]] = v if typ in ("MODULE_REGION", "TEST_EXPECTATION") else {"decision": "no", "reason": f"pattern: {v}"}
            errs.update(e)
        return doc, errs

    def _ask_one(self, template: dict, repo_root: Path, purpose: str, repair: bool = True) -> tuple[dict | None, dict[str, list[str]]]:
        if self.at_budget():  # v0.6: the budget is spent — this ask (and any repair it would need) makes no call
            self.budget_cuts += 1
            return None, {}
        prompt = H.render(template, repo_root)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        text = self._call(messages, purpose)
        cut = self.exchanges[-1].get("finish_reason") == "length"
        doc = parse_document(text)
        errs = H.validate_fills(template, doc) if doc is not None else {"document": ["the reply is not a JSON object"]}
        self.exchanges[-1]["validation"] = errs
        if not errs or not repair or self.at_budget():  # v0.6: the budget covers the repair call too
            return H.read_patterns(template, doc), errs
        repair = ("Your answer was cut off at the reply limit before it ended. " if cut else "Your answer did not validate. ") + \
            "Reply with the whole document again: `patterns` for every type left unchanged, and under `fills` only the holes you change or that take no pattern. Fix these:\n" + \
            "\n".join(f"- {k}: {'; '.join(v)}" for k, v in sorted(errs.items())[:40])
        messages = messages + [{"role": "assistant", "content": text}, {"role": "user", "content": repair}]
        text2 = self._call(messages, purpose + " (repair)")
        doc2 = parse_document(text2)
        errs2 = H.validate_fills(template, doc2) if doc2 is not None else {"document": ["the reply is not a JSON object"]}
        self.exchanges[-1]["validation"] = errs2
        return H.read_patterns(template, doc2 if doc2 is not None else doc), errs2


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
        if h["type"] not in ROUND1_TYPES or h["id"] not in fills1 or (isinstance(fills1[h["id"]], dict) and (fills1[h["id"]].get("unanswered") or fills1[h["id"]].get("by_pattern"))):
            continue
        if h["id"] in present:
            present[h["id"]]["fill"] = fills1[h["id"]]
            present[h["id"]]["fill_source"] = source
        else:
            carried.append({**copy.deepcopy(h), "fill": fills1[h["id"]], "fill_source": source})
    t2["holes"][:0] = carried


def null_route(n: dict, L: T.Ledger, g: dict) -> str:
    """Protocol v0.4: ``"declare"`` for a NULL whose name nothing declares — the grounder's class ``new`` or ``invented``, the bare
    name in no module of the parent graph and, for ``invented``, not declared anywhere in the post-image — else ``"re-ask"`` (a
    near-miss, or a name declared where the call does not reach: the hole that wrote it is asked again, as in v0.3)."""
    name = n["term"].rsplit(".", 1)[-1]
    if n["null_class"] not in DECLARE_CLASSES or name in L.by_name:
        return "re-ask"
    if n["null_class"] == "invented" and name in g.get("gensyms", ()):
        return "re-ask"
    return "declare"


def _scope_key(n: dict) -> tuple:
    sc = n.get("scope") or {}
    return n["term"].rsplit(".", 1)[-1], sc.get("dir"), sc.get("type")


def _null_text(n: dict) -> str:
    """One NULL as a narrowed template states it: the term, the site, the class — and the world check's reason, or the nearest graph names."""
    if n.get("reason"):
        return f"`{n['term']}` at {n['path']}:{n['line']} ({n['null_class']}; {n['reason']})"
    return f"`{n['term']}` at {n['path']}:{n['line']} ({n['null_class']}; nearest in the graph: {', '.join(n['nearest'])})"


def declaration_sibling(declares: dict, site: dict, g: dict, L: T.Ledger, repo_root: Path | None, degree: dict | None = None) -> dict | None:
    """v0.5 (D-h): one existing declaration of the kind a declaration hole asks for, from the directory the name binds in, chosen by
    ``SIBLING_RULE`` — its symbol, file, package clause, imports, and (v0.6) its whole declaration, byte-capped — or None (no directory,
    no repo, nothing of the kind there). *site* is the NULL the hole answers (its hole, path and line); *g* the grounding that raised it."""
    where, typ = declares.get("dir"), declares.get("type")
    if where is None or repo_root is None:
        return None
    where = "" if where in ("", ".") else where
    cands: dict[str, str] = {}
    for sid, s in L.symbols.items():
        p = L.mod_path.get(s["module"])
        if not p or not p.endswith(".go") or p.endswith("_test.go") or H.dir_of(p) != where:
            continue
        if (typ is not None and s.get("kind") == "method" and s.get("qualname", "").split(".")[0] == typ) or (typ is None and s.get("kind") == "function"):
            cands[sid] = p
    if not cands:
        return None
    near = [r for r in g.get("refs", []) if r["hole"] == site["hole"] and r["path"] == site["path"] and r["class"] == "in-graph" and r["target"] in cands]
    if near:
        sid = min(near, key=lambda r: (abs(r["line"] - site["line"]), r["line"], r["target"]))["target"]
        rule = "called nearest the call site by the same fill"
    else:
        deg = degree if degree is not None else G.density_table(L.graph)["degree"]
        sid = min(cands, key=lambda x: (-deg.get(x, 0), x))
        rule = "the most callers in the directory"
    sp = L.span(sid)
    lines = G.file_at(repo_root, L.sha, sp["path"]) or []
    body = lines[sp["start"] - 1: sp["end"]]
    head: list[str] = []  # v0.6 (D-h): the whole span, capped only by bytes — no separate line count
    for line in body:
        if head and sum(len(x) + 1 for x in head) + len(line) > SIBLING_BYTES:
            break
        head.append(line)
    from hobbes.extract import gosource
    root = gosource._PARSER.parse("\n".join(lines).encode("utf-8", "surrogateescape")).root_node
    imports = [(f"{s['alias']} " if s["alias"] else "") + f'"{s["path"]}"' for s in G._go_import_specs(root)]
    return {"symbol": sid, "path": sp["path"], "line": sp["start"], "rule": rule, "package": gosource._package_name(root),
            "imports": imports, "text": "\n".join(head), "more_lines": len(body) - len(head)}


def declaration_holes(t2: dict, g: dict, L: T.Ledger, repo_root: Path | None = None) -> list[dict]:
    """The NULL list's undeclared names (`null_route`) as ``NEW_SYMBOL`` holes, one per name and scope, in NULL order: what a v0.4
    round-trip asks to declare. Each names its call sites and the line written there, the directory the name binds in (the
    grounder's ``scope``) and the write partition's files in it — never a path the partition lacks: a new file is the answer's
    to name, and the grounder records it outside the partition. Since v0.5, with *repo_root*, each carries a ``sibling``
    (`declaration_sibling`) when its directory holds one."""
    partition = list((t2.get("constraints") or {}).get("write_partition", []))
    taken = {h["id"] for h in t2["holes"]}
    groups: dict[tuple, list[dict]] = {}
    for n in g["null"]:
        if null_route(n, L, g) == "declare":
            groups.setdefault(_scope_key(n), []).append(n)
    out: list[dict] = []
    degree: dict | None = None
    i = 0
    for (name, where, typ), ns in groups.items():
        i += 1
        while f"d{i}" in taken:
            i += 1
        post = (g.get("post") or {}).get(ns[0]["path"], "").split("\n")
        call = post[ns[0]["line"] - 1].strip() if 0 < ns[0]["line"] <= len(post) else ""
        files = [p for p in partition if where is None or H.dir_of(p) == ("" if where in ("", ".") else where)]
        there = "" if where is None else f" It binds only in the directory `{where or '.'}/`, the package the call names" + (f", as a method of `{typ}`" if typ else "") + "."
        offer = (f" Files of the write partition there: {', '.join(f'`{p}`' for p in files)}." if files else
                 " No file of the write partition is there: a new file you name is created, and is recorded outside the partition.")
        declares = {"name": name, "term": ns[0]["term"], "dir": where, "type": typ}
        sib = None
        if repo_root is not None and where is not None:
            if degree is None:
                degree = G.density_table(L.graph)["degree"]
            sib = declaration_sibling(declares, ns[0], g, L, repo_root, degree)
        hole = {"id": f"d{i}", "type": "NEW_SYMBOL", "span": None,
                "constraints": {"write_partition": partition, "declares": declares},
                "provenance": {"anchor": f"NULL round-trip: `{name}` written at a call site, declared nowhere",
                               "NULL": "; ".join(_null_text(n) for n in ns),
                               "call_site": f"{ns[0]['path']}:{ns[0]['line']}: `{call}`"},
                "fill_schema": H.FILL_SHAPES["NEW_SYMBOL"],
                "ask": (f"declare `{name}` — your answer calls it and nothing declares it, at this commit or in your answers.{there}{offer} "
                        "Answer with name, file, position (after_symbol, or region: \"eof\") and body: the whole declaration, its signature line "
                        "first (a new file: the whole file). Or covered_by another declaration hole whose body declares it too."
                        + (" Write it in this repository's world: imports only from the Go standard library, this module's packages, or a module "
                           "its go.mod requires, as the sibling below does — anything else is reported back." if sib else ""))}
        if sib:
            hole["sibling"] = sib
        out.append(hole)
    return out


def declaration_repair(tg: dict, merged: dict, g2: dict, decl: list[dict], build_errors: dict[str, str] | None = None) -> dict | None:
    """v0.5 (D-g), extended v0.6 (§2.4, D-o): the placed declarations whose bodies raised a NULL at the grounder, **or** whose file
    the build row (`harness.build_row`) reports a compile error for (*build_errors*, hole id → the error's text, already trimmed to
    the lines naming that file — `harness.trim_build_error`), each shown its previous answer and whichever of the two it carries
    (both, when it carries both) — the one repair of that same declaration hole, never a new hole and never a second round. None
    when every placed declaration grounds clean and builds clean."""
    ids = [h["id"] for h in decl]
    by: dict[str, list[dict]] = {}
    for n in g2["null"]:
        if n["hole"] in ids:
            by.setdefault(n["hole"], []).append(n)
    build_errors = build_errors or {}
    needs = {h["id"] for h in decl} & (set(by) | set(build_errors))
    if not needs:
        return None
    v = copy.deepcopy(tg)
    v["holes"] = []
    for h in decl:
        if h["id"] not in needs:
            continue
        name = h["constraints"]["declares"]["name"]
        h2 = copy.deepcopy(h)
        extra: dict[str, str] = {}
        reasons = []
        if h["id"] in by:
            extra["NULL in your declaration"] = "; ".join(_null_text(n) for n in by[h["id"]])
            reasons.append("the grounder found names in its body that this repository's world lacks (see NULL in your declaration): an import "
                            "outside the Go standard library, this module's packages and the modules its go.mod requires, or a qualifier the "
                            "file does not import")
        if h["id"] in build_errors:
            extra["build error in your declaration"] = build_errors[h["id"]]
            reasons.append("the repository failed to build with it (see build error in your declaration)")
        h2["provenance"] = {**h2.get("provenance", {}), **extra}
        h2["previous_fill"] = merged["fills"].get(h["id"])
        h2["ask"] = (f"repair your declaration of `{name}` — " + "; and ".join(reasons) + ". Answer again with the whole declaration, in the "
                     "same shape. This is the one repair: nothing is asked after it.")
        v["holes"].append(h2)
    v.pop("neighborhood", None)
    return v


def narrow(t2: dict, doc: dict, g: dict, L: T.Ledger, repo_root: Path | None = None) -> dict | None:
    """The NULL list as a narrower template (v0.4): the holes whose fills carried a NULL `null_route` re-asks, each naming the terms that
    did not bind and the nearest graph names, then a declaration hole per undeclared name (`declaration_holes`). None when there is no NULL."""
    if not g["null"]:
        return None
    by_hole: dict[str, list[dict]] = {}
    for n in g["null"]:
        if null_route(n, L, g) == "declare":
            continue
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
        h2["provenance"] = {**h2.get("provenance", {}), "NULL": "; ".join(_null_text(n) for n in by_hole[h["id"]])}
        h2["ask"] = (h2.get("ask") or H.HOLE_TYPES[h2["type"]]) + " — your previous answer named symbols that do not exist at this commit (see NULL); answer again using only names that exist or that you declare"
        h2["previous_fill"] = doc["fills"].get(h["id"])
        v["holes"].append(h2)
    v["holes"] += declaration_holes(t2, g, L, repo_root)
    v.pop("neighborhood", None)
    return v if v["holes"] else None


def _hole_files(decl: list[dict], merged: dict, refused: set[str] | None = None) -> dict[str, str]:
    """Hole id → the file its own fill named (the placement the build error, if any, names — not gold's). A refused hole (D-f:
    its edit lingers in the grounder's own edit list though it never landed) is excluded — nothing of it is in the diff the
    build row read, so no build error is its to carry."""
    out = {}
    for h in decl:
        if refused and h["id"] in refused:
            continue
        f = merged["fills"].get(h["id"])
        if isinstance(f, dict) and isinstance(f.get("file"), str):
            out[h["id"]] = f["file"]
    return out


def declaration_build_errors(diff: str, decl: list[dict], merged: dict, L: T.Ledger, repo_root: Path, *, refused: set[str] | None = None,
                              build_source: Path | None = None, timeout: int = 900) -> tuple[dict[str, str], dict]:
    """v0.6 (§2.4): verify's build row (`harness.build_row`) on *diff* — the template's current, grounded diff, declarations placed
    — contained, no baseline, no test selection; the "go build ./..." step's stderr, trimmed to the lines naming each declared
    hole's own file (`harness.trim_build_error`) when that step failed. *refused* names the hole ids the grounder already
    refused (D-f) — excluded, since nothing of theirs reached the diff the build row read. Returns ``(hole id → trimmed error
    text, a record for the loop: ran?, wall_s, whether the build failed at all)``. ``{}`` when the row applied clean, when it
    did not apply, or when no declared hole's file appears in the failure (a compile error elsewhere in the diff, not this
    repair's to carry)."""
    br = HV.build_row(build_source or repo_root, L.sha, diff, L, build_source or repo_root, timeout=timeout)
    rec = {"ran": True, "applies": br.get("applies"), "wall_s": br.get("wall_s")}
    if not br.get("applies"):
        return {}, rec
    step = next((s for s in br.get("steps", {}).values() if s.get("kind") == "build"), None)
    rec["build_failed"] = bool(step and step.get("outcome") != "pass")
    if not rec["build_failed"]:
        return {}, rec
    files = _hole_files(decl, merged, refused)
    out: dict[str, str] = {}
    for hid, path in files.items():
        err = HV.trim_build_error(step.get("stderr_tail", "") or "", Path(path).name)
        if err:
            out[hid] = err
    return out, rec


def null_round_trip(t2: dict, doc2: dict, g: dict, L: T.Ledger, repo_root: Path, adapter: Adapter, *, rta: dict | None = None,
                     verify_build: bool = False, build_source: Path | None = None) -> dict | None:
    """T-loop on a grounding with NULLs (v0.6): `narrow` → ask → the answers merged into the round-2 fills and the declaration holes
    added to the template, so the grounder places them and grounds every call site again; then, when a placed declaration's body
    raised a NULL **or** (v0.6, §2.4; *verify_build*) the diff's build row names a compile error in its file, **one** more exchange —
    `declaration_repair`, reading both causes at once, no validation repair after it — and the grounding once more with the repaired
    declarations that validate. Returns ``{"template_round3", "round", "ground_after_loop", "loop", "template_repair",
    "repair_round", "ground_before_repair"}`` (the last three None when nothing was repaired), or None when there is no NULL. The
    record's closure is per site, keyed on (hole, term), against the final grounding: a NULL still there under another class is not
    closed; a declaration the grounder refused reads ``refused`` (D-f), and each declaration site counts the NULLs left in its body."""
    t3 = narrow(t2, doc2, g, L, repo_root)
    if t3 is None:
        return None
    doc3, errs3 = adapter.ask(t3, repo_root, "NULL round-trip")
    merged = copy.deepcopy(doc2)
    for hid, fill in ((doc3 or {}).get("fills") or {}).items():
        merged["fills"][hid] = fill
    decl = [h for h in t3["holes"] if (h.get("constraints") or {}).get("declares")]
    tg = copy.deepcopy(t2)
    tg["holes"] += copy.deepcopy(decl)
    g2 = G.ground(copy.deepcopy(tg), merged, L, repo_root, rta=rta)
    gf, repair_round, repair = g2, None, None
    build_errors, build_row_rec = {}, {"ran": False}
    if verify_build and decl and not adapter.at_budget():  # the build row spends no model call; the repair it may trigger does, so honour the budget first
        already_refused = {x["hole"] for x in g2["refused"]}
        build_errors, build_row_rec = declaration_build_errors(g2["diff"], decl, merged, L, repo_root, refused=already_refused, build_source=build_source)
    t3r = declaration_repair(tg, merged, g2, decl, build_errors)
    if t3r is not None:
        asked = [h["id"] for h in t3r["holes"]]
        doc3r, errs3r = adapter.ask(t3r, repo_root, "declaration repair", repair=False)
        taken = sorted(hid for hid in ((doc3r or {}).get("fills") or {}) if hid in asked and hid not in errs3r)
        for hid in taken:
            merged["fills"][hid] = doc3r["fills"][hid]
        if taken:
            gf = G.ground(copy.deepcopy(tg), merged, L, repo_root, rta=rta)
        repair_round = {"round": "3r", "holes_asked": asked, "fills": doc3r, "errors": errs3r, "taken": taken}
        body = lambda gg: [{x: n.get(x) for x in ("hole", "line", "term", "null_class", "kind")} for n in gg["null"] if n["hole"] in asked]
        repair = {"asked": asked, "taken": taken, "exchanges": 1, "body_nulls_before": body(g2), "body_nulls_after": body(gf),
                  "build_errors_before": dict(build_errors), "build_row": build_row_rec}
    after = {(n["hole"], n["term"]) for n in gf["null"]}
    before = {(n["hole"], n["term"]) for n in g["null"]}
    decl_of = {_scope_key({"term": h["constraints"]["declares"]["term"], "scope": {"dir": h["constraints"]["declares"]["dir"],
                                                                                   "type": h["constraints"]["declares"]["type"]}}): h["id"] for h in decl}
    refused = {x["hole"] for x in gf["refused"]}
    placed = {e["hole"]: e for e in gf["edits"] if e["hole"] not in refused}  # D-f: the edit list keeps a refused overlap; the refused list says so
    sites = []
    for n in g["null"]:
        s = {"hole": n["hole"], "path": n["path"], "line": n["line"], "term": n["term"], "null_class": n["null_class"], "route": null_route(n, L, g),
             "closed": (n["hole"], n["term"]) not in after}
        if s["route"] == "declare":
            dh = decl_of[_scope_key(n)]
            f = merged["fills"].get(dh)
            via = f["covered_by"][0] if isinstance(f, dict) and isinstance(f.get("covered_by"), list) and f["covered_by"] else dh
            e = placed.get(via)
            answer = None if f is None else "refused" if via in refused else ("covered_by " + via if via != dh else "placed" if e else "not placed")
            s.update({"declaration": dh, "answer": answer, "file": e["path"] if e else None, "in_partition": e["in_partition"] if e else None,
                      "body_nulls": sum(1 for m in gf["null"] if m["hole"] == via) if e else None, "repaired": bool(repair and via in repair["asked"])})
        sites.append(s)
    loop = {"nulls_before": len(g["null"]), "nulls_after": len(gf["null"]),
            "closed_by_class": dict(collections.Counter(n["null_class"] for n in g["null"] if (n["hole"], n["term"]) not in after)),
            "opened_by_class": dict(collections.Counter(n["null_class"] for n in gf["null"] if (n["hole"], n["term"]) not in before)),
            "routes": dict(collections.Counter(s["route"] for s in sites)), "declaration_holes": [h["id"] for h in decl],
            "refused_declarations": sorted(h["id"] for h in decl if h["id"] in refused), "declaration_repair": repair, "sites": sites,
            "build_row": build_row_rec}  # v0.6 (§2.4): whether the build row ran before the repair, its wall-clock, and whether it failed
    return {"template_round3": t3, "round": {"round": 3, "holes_asked": [h["id"] for h in t3["holes"]], "fills": doc3, "errors": errs3},
            "ground_after_loop": gf, "loop": loop, "template_repair": t3r, "repair_round": repair_round,
            "ground_before_repair": g2 if t3r is not None else None}


#: v0.6 (D-i): the purposes `is_loop_exchange` reads as T-loop's own spend, base name (chunk and validation-repair suffixes stripped).
_LOOP_PURPOSES = ("NULL round-trip", "declaration repair")


def is_loop_exchange(purpose: str) -> bool:
    """D-i: whether one exchange's ``purpose`` belongs to T-loop's spend (``usd_loop``) rather than T's own (``usd_T``) — the NULL
    round-trip's ask and the declaration repair's, a chunk suffix (``" [chunk i/n]"``) and a validation-repair suffix
    (``" (repair)"``) stripped first. Round 1's driver (`calvin_probe.cmd_t_units`) tested ``purpose.startswith("NULL")`` only,
    which missed "declaration repair" — its dollars landed in ``usd_T`` though the totals (built from every exchange regardless)
    were always right."""
    base = purpose.split(" [chunk", 1)[0]
    if base.endswith(" (repair)"):
        base = base[: -len(" (repair)")]
    return base in _LOOP_PURPOSES


def run_t(task: str, template: dict, L: T.Ledger, repo_root: Path, cochange: CoChange | None, adapter: Adapter, *, null_loop: bool = True,
          rta: dict | None = None, verify_build: bool = False, build_source: Path | None = None) -> dict:
    """Arm T for one unit: round 1 → rebuild → round 2 → prune → ground, then (T-loop) one NULL round-trip. Returns the per-unit record.

    *rta* is handed to both groundings (`ground.ground`'s rule-2 implementers, recorded, never bound; M0-Go). *verify_build* (v0.6,
    §2.4) turns on the build row inside the declaration repair (`declaration_build_errors`) — off by default (round 1's condition,
    and every existing test's): it makes a real contained ``go build`` and needs `hobbes.extract.containment` wired to something
    that can run one (a fake in tests, the sandbox image live)."""
    t1 = copy.deepcopy(template)
    rec: dict = {"key": {**t1["key"], "model_id": adapter.model_id, "system_prompt_version": SYSTEM_PROMPT_VERSION, "protocol_version": PROTOCOL_VERSION}, "rounds": []}
    t2 = t1
    base = copy.deepcopy(t1)  # every round-1 hole ever asked, so a refused confirmation stays refused across passes
    fills1: dict = {}
    for pass_ in (1, 2, 3):  # another pass only when the rebuild opened new round-1 holes: an ANCHOR hole after every refusal, or a named module's symbols
        view = round1_view(t2)
        if not view["holes"]:
            break
        doc1, errs1 = adapter.ask(view, repo_root, f"round 1{'' if pass_ == 1 else 'bc'[pass_ - 2]}")
        answers = (doc1 or {}).get("fills") or {}
        by_pattern = (doc1 or {}).get("by_pattern") or {}
        fills1.update(answers)
        for h in view["holes"]:  # step 6: a confirmation left unanswered is a refusal, recorded as one, never carried as a filled hole
            if h["type"] == "ANCHOR_CONFIRM" and h["id"] not in answers:
                fills1[h["id"]] = {"confirm": False, "unanswered": True}
            elif h["type"] == "ANCHOR_CONFIRM" and h["id"] in by_pattern:  # v0.3: a refusal by pattern, recorded as one and not carried, like silence
                fills1[h["id"]] = {"confirm": False, "by_pattern": True}
        row = {"round": 1 if pass_ == 1 else "1" + "bc"[pass_ - 2], "holes_asked": [h["id"] for h in view["holes"]], "fills": doc1, "errors": errs1,
               "unanswered_confirmations": sum(1 for h in view["holes"] if h["type"] == "ANCHOR_CONFIRM" and h["id"] not in answers),
               "pattern_confirmations": sum(1 for typ in by_pattern.values() if typ == "ANCHOR_CONFIRM")}
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
    # v0.6 (D-n): the round-2 row keeps a copy of doc2 as it stood here — round 2b (below) still merges its answers into doc2
    # itself, the copy the grounder and every later reader sees, but the recorded row must not move when that happens.
    rec["rounds"].append({"round": 2, "holes_asked": [h["id"] for h in t2["holes"] if h.get("closed") is None and "fill" not in h],
                          "fills": copy.deepcopy(doc2), "errors": errs2})
    t2b = yes_followup(t2, doc2)
    if t2b is not None:  # the "yes" answers see their spans and give the rewrite
        doc2b, errs2b = adapter.ask(t2b, repo_root, "round 2b")
        for hid, fill in ((doc2b or {}).get("fills") or {}).items():
            if hid in {h["id"] for h in t2b["holes"]}:
                doc2["fills"][hid] = fill
        rec["rounds"].append({"round": "2b", "holes_asked": [h["id"] for h in t2b["holes"]], "fills": doc2b, "errors": errs2b})
    g = G.ground(copy.deepcopy(t2), doc2, L, repo_root, rta=rta)
    rec["ground"] = g
    if null_loop:
        lp = null_round_trip(t2, doc2, g, L, repo_root, adapter, rta=rta, verify_build=verify_build, build_source=build_source)
        if lp is not None:
            rec["rounds"].append(lp["round"])
            rec["template_round3"] = lp["template_round3"]
            if lp["repair_round"] is not None:  # v0.5: the one declaration repair
                rec["rounds"].append(lp["repair_round"])
                rec["template_repair"] = lp["template_repair"]
                rec["ground_before_repair"] = lp["ground_before_repair"]
            rec["ground_after_loop"] = lp["ground_after_loop"]
            rec["loop"] = lp["loop"]
    rec["exchanges"] = adapter.exchanges
    rec["tokens"] = {"prompt": sum(e.get("prompt_tokens") or 0 for e in adapter.exchanges), "completion": sum(e.get("completion_tokens") or 0 for e in adapter.exchanges)}
    rec["wall_ms"] = sum(e["wall_ms"] for e in adapter.exchanges)
    return rec


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
