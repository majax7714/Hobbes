"""Scoring a model's navigation answers against the graph (ADR-099 §4.4, §4.5).

Every evaluation record's answer was rendered by :mod:`hobbes.ttt.corpus`
from the graph, so the truth is recoverable from the record itself: the
backticked items of the assistant turn. A reply is scored by what it
*names* — the graph ids and paths it contains — never by wording:

- a set family (*callers*, *callees*, *tests*, *impact*) scores F1 over
  the truth items found in the reply against the other known ids the
  reply names; an empty truth ("none recorded") scores 1 when the reply
  names no other known id;
- *defines* scores 1 when the reply names the true path — in full, or
  by a path-shaped token (``proxy.go``, ``proxy/proxy.go``) that is a
  ``/``-boundary suffix of exactly one path the graph knows, that path
  being the truth (scorer v2; a basename two files share identifies
  neither and scores 0);
- *absent* scores 1 when the reply refuses — a negation cue and no
  path-shaped or known name offered — and 0 when it invents one. The
  false-acceptance rate on distractors is the abstention metric.

Deterministic and model-free, like everything else that grades. A run
record carries :data:`SCORER_VERSION`; a scorer change never rescores a
record in place (``scripts/ttt_rescore.py`` writes a new one).
"""

from __future__ import annotations

import re

#: Bumped whenever a score can change for the same reply; recorded in
#: every run so old numbers are never mistaken for new ones.
#: v1 — what a reply names, the defines path in full (2026-09-03).
#: v2 — a defines path by unique ``/``-boundary suffix (review item 7).
SCORER_VERSION = 2

_TICKED = re.compile(r"`([^`]+)`")
#: A path-shaped token: segments joined by ``/`` ending in a dotted
#: extension. ``:`` and ``@`` are not in the class, so ``proxy.go:393``
#: and ``proxy.go@ebdf7a5`` yield ``proxy.go``; backticks and ``**`` are
#: outside it too.
_PATHTOKEN = re.compile(r"[\w][\w.-]*(?:/[\w.-]+)*\.[A-Za-z]\w*")
_NEGATION = re.compile(r"\b(not|no|none|isn't|doesn't|does not|cannot|can't|unable|unknown|absent)\b", re.I)
_PATHLIKE = re.compile(r"[\w.-]+/[\w./-]+\.\w+")


def truth_items(record: dict) -> list[str]:
    """The answer's backticked items, minus the asked symbol itself."""
    answer = record["messages"][1]["content"]
    asked = record.get("symbol") or ""
    items = [t for t in _TICKED.findall(answer) if t != asked]
    if record.get("family") == "defines":
        # "`X` is defined in `path` at lines …" — the path is the truth.
        return items[:1]
    if record.get("family") == "impact":
        # "Beyond `module` itself, … reaches: `a`, `b`." — drop the module.
        return items[1:]
    return items


def path_tokens(text: str) -> list[str]:
    """Path-shaped tokens in a reply, a leading ``./`` dropped, deduplicated in order."""
    out: list[str] = []
    for t in _PATHTOKEN.findall(text or ""):
        t = t[2:] if t.startswith("./") else t
        if t not in out:
            out.append(t)
    return out


def suffix_matches(token: str, known_paths: set[str]) -> list[str]:
    """The known paths *token* names by ``/``-boundary suffix (or in full)."""
    return sorted(p for p in known_paths if p == token or p.endswith("/" + token))


def known_paths(known: set[str]) -> set[str]:
    """The path-shaped members of the known-name universe."""
    return {k for k in known if "/" in k and _PATHTOKEN.fullmatch(k)}


def norm_defines(reply: str, truth_path: str, known_paths: set[str]) -> bool:
    """Whether *reply* names *truth_path*: in full, or by a path-shaped
    token that is a ``/``-boundary suffix of exactly one known path and
    that path is the truth. Two known paths sharing the suffix mean the
    reply identified neither."""
    text = reply or ""
    if truth_path and truth_path in text:
        return True
    for token in path_tokens(text):
        hits = suffix_matches(token, known_paths)
        if hits == [truth_path]:
            return True
    return False


def classify_defines_failure(record: dict, reply: str, known: set[str]) -> str:
    """Why a v1 defines reply missed: ``right path, wrong format`` (v2
    accepts it), ``ambiguous basename`` (its token ends ≥ 2 known paths,
    the truth among them), ``wrong path`` (it names a known path that is
    not the truth), ``refused``, or ``no path named``."""
    truth = truth_items(record)
    truth_path = truth[0] if truth else ""
    text = reply or ""
    paths = known_paths(known)
    if norm_defines(text, truth_path, paths):
        return "right path, wrong format"
    ambiguous = wrong = False
    for token in path_tokens(text):
        hits = suffix_matches(token, paths)
        if len(hits) >= 2 and truth_path in hits:
            ambiguous = True
        elif hits:
            wrong = True
    if ambiguous:
        return "ambiguous basename"
    if wrong:
        return "wrong path"
    if _NEGATION.search(text) and not path_tokens(text):
        return "refused"
    return "no path named"


def score_reply(record: dict, reply: str, known: set[str]) -> dict:
    """Score one reply; returns ``{score, found, missed, extra, refused}``."""
    family = record.get("family")
    asked = record.get("symbol") or ""
    truth = truth_items(record)
    text = reply or ""
    # A name that is part of the asked id (its module, its class) is not
    # an offer: "`driver.Proxy._notify2` is not defined" names `driver`
    # only by spelling the question back. Neither is a name inside a
    # truth item.
    def offers(k: str) -> bool:
        return (k in text and k != asked and len(k) > 3 and not asked.startswith(k + ".")
                and k not in asked and not any(k != t and k in t for t in truth))
    if family == "absent":
        offered = bool(_PATHLIKE.search(text)) or any(offers(k) for k in known)
        refused = bool(_NEGATION.search(text)) and not offered
        return {"score": 1.0 if refused else 0.0, "found": [], "missed": [], "extra": [], "refused": refused}
    if family == "defines":
        hit = bool(truth) and norm_defines(text, truth[0], known_paths(known))
        return {"score": 1.0 if hit else 0.0, "found": truth if hit else [], "missed": [] if hit else truth,
                "extra": [], "refused": False}
    found = [t for t in truth if t in text]
    missed = [t for t in truth if t not in text]
    extra = sorted(k for k in known if k not in truth and offers(k))
    if not truth:
        return {"score": 0.0 if extra else 1.0, "found": [], "missed": [], "extra": extra, "refused": False}
    precision = len(found) / (len(found) + len(extra)) if (found or extra) else 0.0
    recall = len(found) / len(truth)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"score": round(f1, 4), "found": found, "missed": missed, "extra": extra, "refused": False}


def known_names(graph: dict) -> set[str]:
    """Every id and path a reply could name — the universe *extra* is drawn from."""
    out = {s["id"] for s in graph.get("symbols", [])}
    for node in graph.get("nodes", []):
        out.add(node["id"])
        if node.get("path"):
            out.add(node["path"])
    return out


def summarise(rows: list[dict]) -> dict:
    """Mean score per family, the absent family's false-acceptance rate, and n."""
    by_family: dict[str, list[float]] = {}
    for r in rows:
        by_family.setdefault(r["family"], []).append(r["score"])
    out = {"n": len(rows), "families": {f: {"n": len(v), "mean": round(sum(v) / len(v), 4)} for f, v in sorted(by_family.items())}}
    if "absent" in by_family:
        out["absent_false_acceptance"] = round(1 - sum(by_family["absent"]) / len(by_family["absent"]), 4)
    nav = [s for f, v in by_family.items() if f != "absent" for s in v]
    out["navigation_mean"] = round(sum(nav) / len(nav), 4) if nav else None
    return out
