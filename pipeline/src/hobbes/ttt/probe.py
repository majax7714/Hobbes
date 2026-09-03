"""The prompt templates and the version-aware file scoring behind
``scripts/ttt_probe.py`` (ADR-099 §4.4, §4.5; review items 4 and 10).

Two things live here so they can be tested without an endpoint:

- **Templates.** The system line and the three navigation contexts —
  ``none`` (the question alone), ``card`` (the held-out symbol's own
  card, or the note that Hobbes has none), ``card-refuse`` (the card
  plus an explicit instruction to abstain). :func:`template_hash` pins
  the wording a run was made under into its record, so a later change
  of a template cannot be mistaken for a change in the model.
- **Version-aware file scoring.** A model that holds an *older* copy of
  a repo names files that existed then and reads as ignorant at the
  probe's SHA (C-83, the httpx rename). :func:`score_files` scores a
  reply's file names at the SHA, after dropping generic names, and
  against the union of trees across the repo's tagged releases, naming
  the tag that fits best. The at-SHA raw number is what the gate reads;
  the others are reported beside it.

Computes; does not interpret.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

SYSTEM = "You are answering questions about the {repo} repository at commit {sha12}. Answer briefly and precisely."

#: What precedes the question under each ``--context``; ``{card}`` is the
#: symbol's card, ``{sha12}`` the SHA, ``{symbol}`` the asked id.
CONTEXT_CARD = "Derived context for this symbol (Hobbes, {sha12}):\n{card}\n\n"
CONTEXT_NO_CARD = "Derived context: Hobbes has no card for `{symbol}` at {sha12}.\n\n"
REFUSE_INSTRUCTION = ("If the symbol is not listed in the derived context above, reply that it is not defined "
                      "in this repo at this SHA. Do not guess a file.")
CONTEXTS = ("none", "card", "card-refuse")

#: Generic basenames that say nothing about *which* repo a model recalls.
STOPLIST = re.compile(r"^(readme|license|licence|changelog|contributing)(\.\w+)?$|"
                      r"^(__init__\.py|setup\.py|pyproject\.toml|makefile|\.gitignore|package\.json|go\.mod|cargo\.toml)$", re.I)


def context_template(context: str) -> str:
    """The exact text a context prepends to the question (before formatting)."""
    if context == "none":
        return ""
    if context == "card":
        return CONTEXT_CARD + "|" + CONTEXT_NO_CARD
    if context == "card-refuse":
        return CONTEXT_CARD + "|" + CONTEXT_NO_CARD + "|" + REFUSE_INSTRUCTION + "\n\n"
    raise ValueError(f"unknown context {context!r}; one of {', '.join(CONTEXTS)}")


def template_hash(context: str) -> str:
    """Sixteen hex characters over the system line and the context's wording."""
    body = SYSTEM + "\n\n" + context_template(context)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def render_context(context: str, symbol: str, card: str | None, sha12: str) -> str:
    """The text placed before the question for *symbol* under *context*."""
    if context == "none":
        return ""
    head = (CONTEXT_CARD.format(card=card, sha12=sha12) if card
            else CONTEXT_NO_CARD.format(symbol=symbol, sha12=sha12))
    if context == "card-refuse":
        head += REFUSE_INSTRUCTION + "\n\n"
    return head


# ---------------------------------------------------------------- files

def generic(name: str) -> bool:
    """Whether a basename is on the stoplist."""
    return bool(STOPLIST.match(name.rsplit("/", 1)[-1]))


def tag_trees(repo_root: Path, cap: int = 30) -> dict[str, set[str]]:
    """``tag -> set of paths`` for the newest *cap* tags; empty when the clone has none."""
    repo_root = Path(repo_root)
    try:
        tags = subprocess.run(["git", "-C", str(repo_root), "tag", "--sort=-creatordate"],
                              check=True, capture_output=True, text=True).stdout.split()
    except (subprocess.CalledProcessError, OSError):
        return {}
    out: dict[str, set[str]] = {}
    for tag in tags[:cap]:
        try:
            listing = subprocess.run(["git", "-C", str(repo_root), "ls-tree", "-r", "--name-only", tag],
                                     check=True, capture_output=True, text=True).stdout
        except subprocess.CalledProcessError:
            continue
        out[tag] = {ln for ln in listing.splitlines() if ln}
    return out


def _prf(listed: set[str], truth: set[str]) -> tuple[float, float, int]:
    hit = listed & truth
    return (len(hit) / len(listed) if listed else 0.0, len(hit) / len(truth) if truth else 0.0, len(hit))


def score_files(listed: set[str], real_at_sha: set[str], trees: dict[str, set[str]], directory: str) -> dict:
    """Score the basenames a reply lists for *directory*.

    ``precision_at_sha`` / ``recall`` are the gate's numbers (raw);
    ``precision_at_sha_stoplisted`` drops generic names from both sides;
    ``precision_any_version`` counts a name a hit when any tagged tree
    holds ``<directory>/<name>``; ``best_tag`` is the tag whose tree hits
    most listed names (ties broken by tag order in *trees*, newest
    first), None when no tag hits.
    """
    p, r, hit = _prf(listed, real_at_sha)
    listed_s = {n for n in listed if not generic(n)}
    truth_s = {n for n in real_at_sha if not generic(n)}
    p_s, r_s, hit_s = _prf(listed_s, truth_s)
    prefix = f"{directory.rstrip('/')}/" if directory not in ("", ".") else ""
    per_tag = {tag: len({n for n in listed if f"{prefix}{n}" in tree}) for tag, tree in trees.items()}
    union: set[str] = set()
    for tree in trees.values():
        union |= {path[len(prefix):] for path in tree if path.startswith(prefix) and "/" not in path[len(prefix):]}
    p_any = len(listed & (union | real_at_sha)) / len(listed) if listed else 0.0
    best = max(per_tag, key=lambda t: per_tag[t]) if per_tag and max(per_tag.values()) > 0 else None
    return {"precision": round(p, 3), "recall": round(r, 3), "listed": len(listed), "truth": len(real_at_sha), "hit": hit,
            "precision_at_sha": round(p, 3),
            "precision_at_sha_stoplisted": round(p_s, 3), "listed_stoplisted": len(listed_s),
            "truth_stoplisted": len(truth_s), "hit_stoplisted": hit_s,
            "precision_any_version": round(p_any, 3), "best_tag": best,
            "best_tag_hits": per_tag.get(best, 0) if best else 0}


def listed_files(reply: str) -> set[str]:
    """The file basenames a reply names (the probe's own extraction)."""
    return {t.rsplit("/", 1)[-1] for t in re.findall(r"[\w.-]+\.\w+", reply)}
