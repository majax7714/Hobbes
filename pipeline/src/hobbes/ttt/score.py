"""Scoring a model's navigation answers against the graph (ADR-099 §4.4, §4.5).

Every evaluation record's answer was rendered by :mod:`hobbes.ttt.corpus`
from the graph, so the truth is recoverable from the record itself: the
backticked items of the assistant turn. A reply is scored by what it
*names* — the graph ids and paths it contains — never by wording:

- a set family (*callers*, *callees*, *tests*, *impact*) scores F1 over
  the truth items found in the reply against the other known ids the
  reply names; an empty truth ("none recorded") scores 1 when the reply
  names no other known id;
- *defines* scores 1 when the reply names the true path;
- *absent* scores 1 when the reply refuses — a negation cue and no
  path-shaped or known name offered — and 0 when it invents one. The
  false-acceptance rate on distractors is the abstention metric.

Deterministic and model-free, like everything else that grades.
"""

from __future__ import annotations

import re

_TICKED = re.compile(r"`([^`]+)`")
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
        hit = bool(truth) and truth[0] in text
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
