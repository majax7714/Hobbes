"""``hobbes derive-corpus`` — the derived layer rendered as a training set.

Three renderings of ``.hobbes/derived/`` at one SHA, chat-formatted for
an Instruct model, written as JSONL (ADR-099 §3.2):

- **symbol cards** — one per graph symbol: file and lines, callers,
  callees, guarding tests, every edge with its tier printed, so a model
  that learns the graph learns that a ``syntactic`` edge is a suspicion;
- **doc chunks** — the narrative module docs and test docs, verbatim,
  with their ``file:line`` pins, cut at ~2k tokens;
- **navigation QA** — six question families whose answer is exactly a
  graph query: *defines*, *callers*, *callees*, *tests*, *impact*
  (``hobbes plan``'s expansion from the symbol's module), and *absent* —
  a name mutated from a real one that resolves to nothing, answered with
  a refusal. The absent family is the abstention training; its
  distractors are checked mechanically against every name the graph
  holds before they are written.

**Held out by symbol.** A deterministic fraction of the symbols (a hash
of the id under a seed) is the evaluation set: those symbols get no card
and no training question, their ids and unique code-shaped names are
masked in the doc chunks, and they are dropped from other symbols'
answer lists — so a symbol in an evaluation pair never appears in a
training pair. A held-out symbol whose bare name is a plain word
(``token``) is left where a doc uses the word; the manifest counts
those mentions rather than hiding them.

**Paraphrases.** ``--paraphrases K`` renders every *training* question
through K phrasings of its question and its answer (template 0 is the
canonical wording; K=0 writes exactly that). Fact injection by
fine-tuning wants varied exposure, and a single template cannot tell
under-exposure from "edges do not enter weights" (review item 5,
2026-09-03). The answer variants name the same backticked items in the
same order, so the scorer reads them alike; the evaluation files are
always template 0, so held-out scores stay comparable across corpora.

**Controls.** ``--control shuffled`` deranges every training answer
within its (kind, family) group. That permuted card *bodies* whole —
each still opening with its own symbol and its own true edges — so
every true edge stayed in that control corpus under the wrong
question. ``--control shuffled-all`` additionally deranges the cards'
``called by`` / ``calls`` / ``tests`` lines across the cards of one
module: module-shaped regularities kept, every specific edge broken.

Deterministic end to end: sorted iteration, canonical JSON, no model,
no randomness beyond the seeded hash. Same artifacts in, same bytes
out — the property the test suite holds, and the reason the adapter
built from this corpus can be called a derived artifact at all.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from hobbes import artifacts
from hobbes.derive.impact import expand, module_adjacency, module_of_symbols
from hobbes.extract.emit import DERIVED_DIR

#: The question families, in the order they are generated.
FAMILIES = ("defines", "callers", "callees", "tests", "impact", "absent")
#: Symbol kinds that get a card.
CARD_KINDS = ("function", "method", "class", "type", "const", "var", "macro")
#: Symbol kinds that get questions (the callable and the named).
QA_KINDS = ("function", "method", "class", "type")
#: Kinds that carry a call relation at all.
CALLABLE_KINDS = ("function", "method")
#: The stable placeholder a held-out name becomes in a doc chunk.
HELD_OUT = "‹held-out›"
#: ~2k tokens at four characters a token; chunks cut at line boundaries.
DOC_CHUNK_CHARS = 8_000
#: Answer lists longer than this end with "and N more".
LIST_CAP = 12
#: Modules an impact answer names, by score then id.
IMPACT_CAP = 8
#: Navigation items the memorisation probe draws (ADR-099 §4.4, part 3).
PROBE_ITEMS = 30
#: The corpus recipe; bumped when a rendering changes shape (the
#: template-0 rendering is unchanged by paraphrases and controls).
RECIPE_VERSION = 1
#: Phrasings available per family (question and answer alike).
PARAPHRASES = 4
#: Default output directory, under the derived tree (regenerable, gitignored).
CORPUS_DIR = "corpus"


class CorpusError(RuntimeError):
    """The repo is not ingested, or an artifact is unusable."""


def held_out(symbol_ids: list[str], fraction: float, seed: int) -> set[str]:
    """The evaluation symbols: those whose seeded hash falls below *fraction*.

    A hash rather than a shuffle so the split is a property of the id and
    the seed alone — adding a symbol to the graph does not move any other
    symbol across the line. The set is then closed over membership (a
    held-out class's methods are held out too).
    """
    out = set()
    for sid in symbol_ids:
        digest = hashlib.sha256(f"{seed}\n{sid}".encode()).hexdigest()[:8]
        if int(digest, 16) / 2**32 < fraction:
            out.add(sid)
    # Closed over membership: a held-out class takes its methods with it,
    # because a member's id spells the class's — a card for
    # ``Router.dispatch`` would name a held-out ``Router`` in training.
    classes = sorted(out)
    for sid in symbol_ids:
        if any(sid.startswith(c + ".") for c in classes):
            out.add(sid)
    return out


@dataclass
class Index:
    """Everything the renderings look up, built once from the artifacts."""

    sha: str
    dirty: bool
    symbols: dict[str, dict]
    module_path: dict[str, str]
    #: symbol id -> [(caller id, tier)], semantic first, then by id.
    callers: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    callees: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    tests_of: dict[str, list[str]] = field(default_factory=dict)
    #: every id, name and qualname the graph holds — what a distractor must miss.
    names: set[str] = field(default_factory=set)
    #: bare names that exactly one symbol carries — safe to mask in prose.
    unique_names: set[str] = field(default_factory=set)

    @property
    def sha12(self) -> str:
        return self.sha[:12]


def build_index(graph: dict, tests: dict) -> Index:
    """Index the graph and the test map for the renderings."""
    symbols = {s["id"]: s for s in graph.get("symbols", [])}
    module_path = {n["id"]: n.get("path", "") for n in graph.get("nodes", [])}
    index = Index(graph.get("sha", ""), bool(graph.get("dirty")), symbols, module_path)
    for edge in graph.get("symbol_edges", []):
        if edge.get("type") != "calls":
            continue
        src, dst, tier = edge["from"], edge["to"], edge.get("tier", "syntactic")
        index.callers.setdefault(dst, []).append((src, tier))
        index.callees.setdefault(src, []).append((dst, tier))
    for bucket in (index.callers, index.callees):
        for key, rows in bucket.items():
            bucket[key] = sorted(set(rows), key=lambda r: (r[1] != "semantic", r[0]))
    for test in tests.get("tests", []):
        for sid in test.get("reaches", []):
            index.tests_of.setdefault(sid, []).append(test["id"])
    for sid, rows in index.tests_of.items():
        index.tests_of[sid] = sorted(set(rows))
    counts: dict[str, int] = {}
    for sid, sym in symbols.items():
        index.names.update({sid, sym.get("name", ""), sym.get("qualname", "")})
        counts[sym.get("name", "")] = counts.get(sym.get("name", ""), 0) + 1
    index.names.update(module_path)
    index.names.discard("")
    index.unique_names = {n for n, c in counts.items() if c == 1 and len(n) >= 4}
    return index


def symbol_path(index: Index, sym: dict) -> str:
    return index.module_path.get(sym.get("module", ""), "") or sym.get("module", "")


# ---------------------------------------------------------------- renderings

def _listed(rows: list[str], cap: int = LIST_CAP) -> str:
    shown = ", ".join(f"`{r}`" for r in rows[:cap])
    rest = len(rows) - cap
    return shown + (f" (and {rest} more)" if rest > 0 else "")


def _edges_line(rows: list[tuple[str, str]], hidden: set[str]) -> tuple[str, int]:
    """Render ``a (semantic), b (syntactic)``; held-out targets are dropped and counted."""
    kept = [(i, t) for i, t in rows if i not in hidden]
    dropped = len(rows) - len(kept)
    if not kept:
        return "none recorded", dropped
    text = ", ".join(f"{i} ({t})" for i, t in kept[:LIST_CAP])
    if len(kept) > LIST_CAP:
        text += f" (and {len(kept) - LIST_CAP} more)"
    return text, dropped


def symbol_card(index: Index, sym: dict, hidden: set[str]) -> tuple[str, int]:
    """The card for one symbol; returns ``(text, held-out mentions dropped)``."""
    callers, d1 = _edges_line(index.callers.get(sym["id"], []), hidden)
    callees, d2 = _edges_line(index.callees.get(sym["id"], []), hidden)
    tests = index.tests_of.get(sym["id"], [])
    tier = "syntactic" if any(
        t == "syntactic" for _, t in index.callers.get(sym["id"], []) + index.callees.get(sym["id"], [])
    ) else "semantic"
    lines = [
        f"symbol: {sym['id']}  ({sym.get('kind', 'symbol')})",
        f"file: {symbol_path(index, sym)}:{sym.get('line', '?')}–{sym.get('end_line', '?')} @ {index.sha12}",
        f"called by: {callers}",
        f"calls: {callees}",
        f"tests: {_listed(tests) if tests else 'none recorded'}",
        f"tier of this card: {tier}",
    ]
    return "\n".join(lines), d1 + d2


def _pins(pins: list[dict]) -> str:
    return ", ".join(f"{p.get('path', '?')}:{p.get('line', '?')}" for p in pins)


def render_doc(doc: dict, sha12: str) -> str:
    """One module or test doc as prose with its pins, every section in key order."""
    kind = doc.get("kind", "doc")
    head = f"{kind}: {doc.get('id', doc.get('path', '?'))} ({doc.get('path', '?')}) @ {sha12}"
    lines = [head]
    for key in sorted(doc):
        if key in ("id", "kind", "path", "dirty", "sha"):
            continue
        value = doc[key]
        if isinstance(value, dict) and "text" in value:
            lines.append(f"{key}: {value['text']}  [{_pins(value.get('pins', []))}]")
        elif isinstance(value, list) and value and isinstance(value[0], dict) and "text" in value[0]:
            lines.append(f"{key}:")
            for row in value:
                label = f"{row['test']}: " if row.get("test") else ""
                lines.append(f"- {label}{row['text']}  [{_pins(row.get('pins', []))}]")
    return "\n".join(lines)


def chunk_text(text: str, limit: int = DOC_CHUNK_CHARS) -> list[str]:
    """Cut at line boundaries so no chunk exceeds *limit* characters (a
    single over-long line stands alone rather than being split mid-pin)."""
    chunks, current, size = [], [], 0
    for line in text.splitlines():
        if current and size + len(line) + 1 > limit:
            chunks.append("\n".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def code_shaped(name: str) -> bool:
    """A bare name that reads as code rather than as a word: an underscore,
    a capital, or a digit inside it. ``render_page`` and ``Router`` are;
    ``token`` and ``usage`` are not, and masking those would erase the
    English word wherever a doc used it."""
    return "_" in name or any(c.isupper() or c.isdigit() for c in name)


def _bounded(pattern: str) -> str:
    return rf"(?<![\w.]){re.escape(pattern)}(?![\w])"


def mask_text(text: str, index: Index, hidden: set[str]) -> tuple[str, int, int]:
    """Replace held-out ids, dotted qualnames and unique code-shaped bare
    names with the placeholder. Returns ``(text, replacements, left)``,
    where *left* counts the word-bounded mentions of a held-out symbol's
    plain-word name that stay in place — the leak the manifest reports
    rather than hides (ADR-099 §7)."""
    replaced = left = 0
    patterns, plain = set(), set()
    for sid in hidden:
        sym = index.symbols[sid]
        patterns.add(sid)
        qual = sym.get("qualname", "")
        if qual and "." in qual:
            patterns.add(qual)
        name = sym.get("name", "")
        if name in index.unique_names:
            (patterns if code_shaped(name) else plain).add(name)
    for pattern in sorted(patterns, key=len, reverse=True):
        text, n = re.subn(_bounded(pattern), HELD_OUT, text)
        replaced += n
    for name in sorted(plain):
        left += len(re.findall(_bounded(name), text))
    return text, replaced, left


# ---------------------------------------------------------------- questions

#: Question phrasings per family; index 0 is the canonical wording.
_QUESTIONS: dict[str, tuple[str, ...]] = {
    "defines": ("Which file defines `{sid}` in {repo} (at {sha12})?",
                "In {repo} at {sha12}, where is `{sid}` defined?",
                "Find the file and lines that define `{sid}` ({repo}, {sha12}).",
                "`{sid}` in {repo} (at {sha12}): which file holds its definition?"),
    "callers": ("What calls `{sid}` in {repo} (at {sha12})?",
                "Which symbols call `{sid}` in {repo} at {sha12}?",
                "List the callers of `{sid}` ({repo}, {sha12}).",
                "In {repo} at {sha12}, who calls `{sid}`?"),
    "callees": ("What does `{sid}` call in {repo} (at {sha12})?",
                "Which symbols does `{sid}` call in {repo} at {sha12}?",
                "List the callees of `{sid}` ({repo}, {sha12}).",
                "In {repo} at {sha12}, what is called by `{sid}`?"),
    "tests": ("Which tests exercise `{sid}` in {repo} (at {sha12})?",
              "What tests reach `{sid}` in {repo} at {sha12}?",
              "List the tests guarding `{sid}` ({repo}, {sha12}).",
              "In {repo} at {sha12}, which tests cover `{sid}`?"),
    "impact": ("If `{sid}` changes in {repo} (at {sha12}), which modules are affected?",
               "Which modules does a change to `{sid}` reach in {repo} at {sha12}?",
               "What is the impact set of `{sid}` ({repo}, {sha12}) — the affected modules?",
               "In {repo} at {sha12}, a change to `{sid}` affects which modules?"),
    "absent": ("Where is `{sid}` defined in {repo} (at {sha12})?",
               "Which file defines `{sid}` in {repo} at {sha12}?",
               "Find the definition of `{sid}` ({repo}, {sha12}).",
               "In {repo} at {sha12}, where does `{sid}` live?"),
}

#: Answer phrasings; index 0 is canonical. Every variant names the same
#: backticked items in the same order as variant 0 — the scorer reads
#: backticks (`hobbes.ttt.score.truth_items`): *defines* wants the path
#: first after the symbol, *impact* the module first, *absent* a
#: negation cue in every phrasing.
_ANSWERS: dict[str, tuple[str, ...]] = {
    "defines": ("`{sid}` is defined in `{path}` at lines {line}–{end} ({kind}).",
                "`{sid}` lives in `{path}`, lines {line}–{end} — a {kind}.",
                "The definition of `{sid}` is in `{path}` (lines {line}–{end}, {kind}).",
                "`{sid}` — {kind} — is defined at `{path}`:{line}–{end}."),
    "callers": ("Semantic-tier callers of `{sid}`: {list}.",
                "`{sid}` is called by {list} (semantic tier).",
                "Callers of `{sid}` at the semantic tier: {list}.",
                "{list} call `{sid}` — semantic-tier edges."),
    "callers_none": ("No semantic-tier caller of `{sid}` is recorded at {sha12}.",
                     "Nothing calls `{sid}` at the semantic tier as of {sha12}; no caller is recorded.",
                     "`{sid}` has no recorded semantic-tier caller at {sha12}.",
                     "At {sha12}, no semantic-tier caller of `{sid}` is recorded."),
    "callees": ("Semantic-tier callees of `{sid}`: {list}.",
                "`{sid}` calls {list} (semantic tier).",
                "Callees of `{sid}` at the semantic tier: {list}.",
                "{list} are called by `{sid}` — semantic-tier edges."),
    "callees_none": ("No semantic-tier callee of `{sid}` is recorded at {sha12}.",
                     "`{sid}` calls nothing at the semantic tier as of {sha12}; no callee is recorded.",
                     "`{sid}` has no recorded semantic-tier callee at {sha12}.",
                     "At {sha12}, no semantic-tier callee of `{sid}` is recorded."),
    "tests": ("Tests reaching `{sid}`: {list}.",
              "`{sid}` is reached by {list}.",
              "The tests that exercise `{sid}` are {list}.",
              "{list} reach `{sid}`."),
    "tests_none": ("No test reaches `{sid}` at {sha12}.",
                   "`{sid}` is reached by no test at {sha12}.",
                   "There is no test that exercises `{sid}` at {sha12}.",
                   "At {sha12}, no test reaches `{sid}`."),
    "impact": ("Beyond `{module}` itself, a change to `{sid}` reaches: {list}.",
               "Besides `{module}`, changing `{sid}` affects {list}.",
               "Outside `{module}`, the modules a change to `{sid}` reaches are {list}.",
               "A change to `{sid}` reaches, beyond `{module}` itself, {list}."),
    "impact_none": ("A change to `{sid}` reaches no module beyond `{module}` itself at {sha12}.",
                    "Besides `{module}`, a change to `{sid}` affects no module at {sha12}.",
                    "Outside `{module}`, nothing is reached by a change to `{sid}` at {sha12}.",
                    "At {sha12}, a change to `{sid}` reaches no module beyond `{module}`."),
    "absent": ("`{sid}` is not defined in this repo at {sha12}.",
               "There is no `{sid}` in this repo at {sha12}; it is not defined.",
               "`{sid}` does not exist in this repo at {sha12} — nothing defines it.",
               "`{sid}` cannot be found in this repo at {sha12}; it is not defined."),
}
assert all(len(v) == PARAPHRASES for v in (*_QUESTIONS.values(), *_ANSWERS.values()))


def _q(family: str, sid: str, repo: str, sha12: str, variant: int = 0) -> str:
    return _QUESTIONS[family][variant].format(sid=sid, repo=repo, sha12=sha12)


def _a(key: str, variant: int = 0, **fields) -> str:
    return _ANSWERS[key][variant].format(**fields)


def impact_modules(graph: dict, module: str, adjacency: dict | None = None,
                   owners: dict[str, str] | None = None) -> list[str]:
    """The modules ``hobbes plan`` would expand to from *module*, best first.

    The expansion runs over the plan's adjacency, whose calling side is
    a symbol id (:func:`hobbes.derive.impact.module_adjacency`); every
    scored node is projected onto its module here, keeping the best
    score, so the answer names modules and only modules. *adjacency* and
    *owners* are computed once by the caller for a whole corpus.
    """
    owners = module_of_symbols(graph) if owners is None else owners
    best: dict[str, float] = {}
    for node, score in expand(graph, {module: module}, adjacency).items():
        target = owners.get(node, node)
        if target and target != module:
            best[target] = max(best.get(target, 0.0), score)
    return sorted(best, key=lambda n: (-best[n], n))[:IMPACT_CAP]


def answers(index: Index, graph: dict, sym: dict, hidden: set[str], families: tuple[str, ...],
            adjacency: dict | None = None, owners: dict[str, str] | None = None,
            variant: int = 0) -> list[tuple[str, str, int]]:
    """``(family, answer, held-out mentions dropped)`` for one symbol, in
    phrasing *variant* (0 is canonical)."""
    sid, sha12 = sym["id"], index.sha12
    out = []
    if "defines" in families:
        out.append(("defines", _a("defines", variant, sid=sid, path=symbol_path(index, sym), line=sym.get("line", "?"),
                                  end=sym.get("end_line", "?"), kind=sym.get("kind", "symbol")), 0))
    if sym.get("kind") in CALLABLE_KINDS:
        for family, bucket in (("callers", index.callers), ("callees", index.callees)):
            if family not in families:
                continue
            rows = [i for i, t in bucket.get(sid, []) if t == "semantic"]
            kept = [i for i in rows if i not in hidden]
            if kept:
                out.append((family, _a(family, variant, sid=sid, list=_listed(kept)), len(rows) - len(kept)))
            else:
                out.append((family, _a(family + "_none", variant, sid=sid, sha12=sha12), len(rows) - len(kept)))
    if "tests" in families:
        tests = index.tests_of.get(sid, [])
        out.append(("tests", _a("tests", variant, sid=sid, list=_listed(tests)) if tests
                    else _a("tests_none", variant, sid=sid, sha12=sha12), 0))
    if "impact" in families:
        module = sym.get("module", "")
        mods = impact_modules(graph, module, adjacency, owners)
        out.append(("impact", _a("impact", variant, sid=sid, module=module, list=_listed(mods, IMPACT_CAP))
                    if mods else _a("impact_none", variant, sid=sid, module=module, sha12=sha12), 0))
    return out


#: Mutations a distractor is drawn from, in order; the first that
#: resolves to nothing in the graph is used.
def _mutations(name: str) -> list[str]:
    flipped = (name[0].swapcase() + name[1:]) if name else name
    out = [flipped, name + "2", name + "_v2", "get_" + name, name + "_impl"]
    if "_" in name:
        head, _, tail = name.rpartition("_")
        out.append(f"{head}_{tail}s")
        out.append(f"{head}_new_{tail}")
    return out


def distractor(index: Index, sym: dict, taken: set[str]) -> str | None:
    """A plausible-looking id that resolves to nothing, or None."""
    module, qual = sym.get("module", ""), sym.get("qualname", sym.get("name", ""))
    head, _, name = qual.rpartition(".")
    for fake in _mutations(name):
        fake_qual = f"{head}.{fake}" if head else fake
        fake_id = f"{module}.{fake_qual}" if module else fake_qual
        if fake in index.names or fake_qual in index.names or fake_id in index.names or fake_id in taken:
            continue
        return fake_id
    return None


def resolves(index: Index, fake_id: str) -> bool:
    """Whether a distractor id, or its last segment, names anything the graph holds."""
    return fake_id in index.names or fake_id.rsplit(".", 1)[-1] in index.names


# ---------------------------------------------------------------- assembly

def _record(kind: str, family: str | None, symbol: str | None, split: str, user: str, assistant: str) -> dict:
    return {"kind": kind, "family": family, "symbol": symbol, "split": split,
            "messages": [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]}


def _dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def load_docs(repo_root: Path) -> list[dict]:
    """Every narrative doc under ``derived/docs/{modules,tests}``, sorted by path."""
    base = Path(repo_root) / DERIVED_DIR / "docs"
    docs = []
    for sub in ("modules", "tests"):
        for path in sorted((base / sub).rglob("*.json")) if (base / sub).is_dir() else []:
            try:
                docs.append(json.loads(path.read_text()))
            except (OSError, ValueError) as exc:
                raise CorpusError(f"{path}: {exc}") from exc
    return docs


#: Control corpora: ``shuffled`` keeps every training record's question
#: and permutes the answers within each (kind, family) group, so the
#: token distribution — the repo's names, paths and templates — is
#: identical and every relation is wrong *in the QA*. It permuted card
#: bodies whole, and a body opens with its own symbol and its own true
#: edges, so every true edge stayed in that control under the wrong
#: "Describe" question (the 2026-09-03 control adapter, review item 3).
#: ``shuffled-all`` also deranges the cards' edge lines within each
#: module (:func:`shuffle_card_lines`): the module's names, paths and
#: shape survive; no specific edge does. An adapter trained on either
#: separates "learned the vocabulary" from "learned the graph"; only the
#: second removes the graph from the cards too.
CONTROLS = ("none", "shuffled", "shuffled-all")
#: The card lines ``shuffled-all`` deranges; the header lines stay.
_CARD_EDGE_LINES = ("called by: ", "calls: ", "tests: ")


def _derange(indices: list[int], key: str) -> list[tuple[int, int]]:
    """``(destination, source)`` pairs: a cyclic shift of a seeded shuffle,
    so no index keeps its own value whatever the group size (≥ 2)."""
    perm = indices[:]
    random.Random(key).shuffle(perm)
    return [(perm[(k + 1) % len(perm)], src) for k, src in enumerate(perm)]


def shuffle_answers(records: list[dict], seed: int, kinds: tuple[str, ...] | None = None) -> list[dict]:
    """Permute assistant turns within each (kind, family) group, seeded;
    a group of one is left alone (nothing to permute against). *kinds*
    restricts the permutation to those record kinds (None: every kind)."""
    groups: dict[tuple, list[int]] = {}
    for i, r in enumerate(records):
        if kinds is None or r["kind"] in kinds:
            groups.setdefault((r["kind"], r.get("family")), []).append(i)
    out = [dict(r, messages=[dict(m) for m in r["messages"]]) for r in records]
    for key in sorted(groups, key=str):
        idx = groups[key]
        if len(idx) < 2:
            continue
        for dst, src in _derange(idx, f"{seed}\n{key}"):
            out[dst]["messages"][1] = records[src]["messages"][1]
    return out


def shuffle_card_lines(records: list[dict], module_of: dict[str, str], seed: int) -> tuple[list[dict], int]:
    """Derange each card's ``called by`` / ``calls`` / ``tests`` line among
    the cards of the same module, each line kind independently; the
    header lines (symbol, file, tier) stay. Returns the records and the
    count of cards left alone because their module had only one."""
    groups: dict[str, list[int]] = {}
    for i, r in enumerate(records):
        if r["kind"] == "card":
            groups.setdefault(module_of.get(r["symbol"], ""), []).append(i)
    out = [dict(r, messages=[dict(m) for m in r["messages"]]) for r in records]
    alone = 0
    for module in sorted(groups):
        idx = groups[module]
        if len(idx) < 2:
            alone += len(idx)
            continue
        lines = {i: records[i]["messages"][1]["content"].split("\n") for i in idx}
        new = {i: list(lines[i]) for i in idx}
        for prefix in _CARD_EDGE_LINES:
            for dst, src in _derange(idx, f"{seed}\n{module}\n{prefix}"):
                src_line = next((ln for ln in lines[src] if ln.startswith(prefix)), None)
                if src_line is None:
                    continue
                new[dst] = [src_line if ln.startswith(prefix) else ln for ln in new[dst]]
        for i in idx:
            out[i]["messages"][1]["content"] = "\n".join(new[i])
    return out, alone


def build_corpus(repo_root: Path, out_dir: Path, *, holdout: float = 0.1, seed: int = 0,
                 name: str | None = None, control: str = "none", paraphrases: int = 0) -> dict:
    """Render the corpus into *out_dir*; returns the manifest.

    *control* ``shuffled`` writes the answer-permuted training set
    (:func:`shuffle_answers`), ``shuffled-all`` also the card-line
    permuted one (:func:`shuffle_card_lines`); *paraphrases* K > 0
    writes every training question K times, in phrasings 0..K−1 (each
    record marked ``variant``). The evaluation files are the true,
    canonical ones either way.

    Writes ``train.jsonl`` (cards, doc chunks, training QA),
    ``eval.jsonl`` (QA on the held-out symbols), ``eval-cards.jsonl``
    (the held-out symbols' cards, for the prompted control),
    ``probe-nav.jsonl`` (thirty held-out navigation items without the
    absent family, for the memorisation probe) and ``manifest.json``.
    """
    repo_root = Path(repo_root)
    try:
        graph = artifacts.load_graph(repo_root)
        tests = artifacts.load_tests(repo_root)
    except artifacts.ArtifactError as exc:
        raise CorpusError(str(exc)) from exc
    if not graph.get("symbols"):
        raise CorpusError("graph.json holds no symbols — nothing to render")
    if control not in CONTROLS:
        raise CorpusError(f"unknown control {control!r}; one of {', '.join(CONTROLS)}")
    if not 0 <= paraphrases <= PARAPHRASES:
        raise CorpusError(f"paraphrases must be 0..{PARAPHRASES}, got {paraphrases}")
    variants = range(max(1, paraphrases))
    repo = name or repo_root.resolve().name
    index = build_index(graph, tests)
    sha12 = index.sha12

    ordered = sorted(index.symbols)
    hidden = held_out([s for s in ordered if index.symbols[s].get("kind") in QA_KINDS], holdout, seed)
    train: list[dict] = []
    eval_: list[dict] = []
    masked = {"card_mentions_dropped": 0, "qa_mentions_dropped": 0,
              "doc_replacements": 0, "doc_plain_names_left": 0}

    # (a) symbol cards — training symbols; a held-out symbol's card goes to
    # ``eval-cards.jsonl`` (never trained on: the reading-comprehension
    # control for a navigation question, ADR-099 §4.5).
    eval_cards: list[dict] = []
    for sid in ordered:
        sym = index.symbols[sid]
        if sym.get("kind") not in CARD_KINDS:
            continue
        if sid in hidden:
            text, _ = symbol_card(index, sym, set())
            eval_cards.append(_record("card", None, sid, "eval", f"Describe `{sid}` in {repo} (at {sha12}).", text))
            continue
        text, dropped = symbol_card(index, sym, hidden)
        masked["card_mentions_dropped"] += dropped
        train.append(_record("card", None, sid, "train", f"Describe `{sid}` in {repo} (at {sha12}).", text))

    # (b) doc chunks — masked.
    doc_chunks = 0
    for doc in load_docs(repo_root):
        text, n, left = mask_text(render_doc(doc, sha12), index, hidden)
        masked["doc_replacements"] += n
        masked["doc_plain_names_left"] += left
        for i, chunk in enumerate(chunk_text(text)):
            doc_chunks += 1
            label = doc.get("id", doc.get("path", "?"))
            part = f" (part {i + 1})" if i else ""
            train.append(_record("doc", None, None, "train",
                                 f"What does the {doc.get('kind', 'doc')} for `{label}` in {repo} say (at {sha12}){part}?", chunk))

    # (c) navigation QA — every family; impact once per module in train.
    first_in_module: dict[str, str] = {}
    for sid in ordered:
        if index.symbols[sid].get("kind") in QA_KINDS and sid not in hidden:
            first_in_module.setdefault(index.symbols[sid].get("module", ""), sid)
    taken: set[str] = set()
    adjacency, owners = module_adjacency(graph), module_of_symbols(graph)
    for sid in ordered:
        sym = index.symbols[sid]
        if sym.get("kind") not in QA_KINDS:
            continue
        split = "eval" if sid in hidden else "train"
        families = FAMILIES if split == "eval" or first_in_module.get(sym.get("module", "")) == sid \
            else tuple(f for f in FAMILIES if f != "impact")
        # The evaluation set is always canonical (variant 0); training
        # questions are rendered once per phrasing when paraphrasing.
        for v in (variants if split == "train" else (0,)):
            rows = answers(index, graph, sym, hidden if split == "train" else set(), families, adjacency, owners, v)
            for family, answer, dropped in rows:
                masked["qa_mentions_dropped"] += dropped if v == 0 else 0
                rec = _record("qa", family, sid, split, _q(family, sid, repo, sha12, v), answer)
                if paraphrases and split == "train":
                    rec["variant"] = v
                (train if split == "train" else eval_).append(rec)
        fake = distractor(index, sym, taken)
        if fake is not None:
            if resolves(index, fake):  # the mechanical check the doc requires
                raise CorpusError(f"distractor {fake!r} resolves in the graph — refusing to write it")
            taken.add(fake)
            for v in (variants if split == "train" else (0,)):
                rec = _record("qa", "absent", fake, split, _q("absent", fake, repo, sha12, v),
                              _a("absent", v, sid=fake, sha12=sha12))
                if paraphrases and split == "train":
                    rec["variant"] = v
                (train if split == "train" else eval_).append(rec)

    cards_unpermuted = 0
    if control == "shuffled":
        train = shuffle_answers(train, seed)
    elif control == "shuffled-all":
        # Cards stay under their own question with their own header;
        # only their edge lines move, so the card is wrong about the
        # symbol it names rather than a true card under a wrong name.
        train = shuffle_answers(train, seed, kinds=("qa", "doc"))
        train, cards_unpermuted = shuffle_card_lines(train, owners, seed)

    # The probe draws held-out navigation items, by seeded hash order.
    nav = [r for r in eval_ if r["family"] != "absent"]
    nav.sort(key=lambda r: hashlib.sha256(f"{seed}\n{r['family']}\n{r['symbol']}".encode()).hexdigest())
    probe = nav[:PROBE_ITEMS]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    blobs = {}
    for fname, rows in (("train.jsonl", train), ("eval.jsonl", eval_), ("probe-nav.jsonl", probe),
                        ("eval-cards.jsonl", eval_cards)):
        blob = ("\n".join(_dumps(r) for r in rows) + ("\n" if rows else "")).encode()
        (out_dir / fname).write_bytes(blob)
        blobs[fname] = blob
    digest = hashlib.sha256()
    for fname in sorted(blobs):
        digest.update(fname.encode()); digest.update(blobs[fname])

    def count(rows, key):
        out: dict[str, int] = {}
        for r in rows:
            k = r.get(key) or "-"
            out[k] = out.get(k, 0) + 1
        return dict(sorted(out.items()))

    manifest = {
        "recipe_version": RECIPE_VERSION,
        "control": control,
        "cards_unpermuted": cards_unpermuted,
        "paraphrases": paraphrases,
        "repo": repo,
        "sha": index.sha,
        "dirty": index.dirty,
        "built_by": graph.get("built_by"),
        "containment": graph.get("containment", {}).get("all_contained"),
        "holdout": {"fraction": holdout, "seed": seed, "symbols": len(hidden)},
        "counts": {
            "train": {"total": len(train), "by_kind": count(train, "kind"), "by_family": count(train, "family")},
            "eval": {"total": len(eval_), "by_family": count(eval_, "family"), "cards": len(eval_cards)},
            "probe_nav": len(probe),
            "doc_chunks": doc_chunks,
            "symbols": len(index.symbols),
        },
        "masked": masked,
        "chars_estimate": sum(len(m["content"]) for r in train for m in r["messages"]),
        "corpus_hash": digest.hexdigest(),
        "files": sorted(blobs),
    }
    (out_dir / "manifest.json").write_text(_dumps(manifest) + "\n")
    return manifest


def format_manifest(manifest: dict, out_dir: Path) -> str:
    """The CLI summary."""
    c = manifest["counts"]
    dirty = " (dirty)" if manifest["dirty"] else ""
    control = f", control: {manifest['control']}" if manifest.get("control", "none") != "none" else ""
    para = f", paraphrases: {manifest['paraphrases']}" if manifest.get("paraphrases") else ""
    lines = [
        f"corpus for {manifest['repo']} @ {manifest['sha'][:12]}{dirty} — recipe v{manifest['recipe_version']}{control}{para}",
        f"  train: {c['train']['total']} records — " + ", ".join(f"{k} {v}" for k, v in c["train"]["by_kind"].items()),
        f"  qa families: " + ", ".join(f"{k} {v}" for k, v in c["train"]["by_family"].items() if k != "-"),
        f"  eval: {c['eval']['total']} records over {manifest['holdout']['symbols']} held-out symbols "
        f"(fraction {manifest['holdout']['fraction']}, seed {manifest['holdout']['seed']}); probe draws {c['probe_nav']}",
        f"  masked: {manifest['masked']['doc_replacements']} doc replacements "
        f"({manifest['masked']['doc_plain_names_left']} plain-word mentions left in place), "
        f"{manifest['masked']['card_mentions_dropped']} card and {manifest['masked']['qa_mentions_dropped']} answer mentions dropped",
        f"  ~{manifest['chars_estimate'] // 4:,} tokens; corpus hash {manifest['corpus_hash'][:16]}",
        f"  written: {out_dir}",
    ]
    if manifest.get("containment") is False:
        lines.append("  note: the graph's lane B ran uncontained (C-64) — the corpus inherits that record")
    return "\n".join(lines)
