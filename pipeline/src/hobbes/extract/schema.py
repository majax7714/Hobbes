"""Graph schema v4 vocabulary: edge tiers and evidence lanes (ADR-028).

Architecture v2 §3.4 gives every edge a **tier** — how much the edge is to
be trusted — and every piece of evidence a **lane** — which producer saw
it. The two answer different questions, and consumers use them differently:
an invariant violation proven on ``semantic`` edges is a finding, the same
violation on ``syntactic`` edges is a suspicion, and the reviewer flow says
which (§3.4).

Every layer that contributes edges (Python, HCL, TS/JS) builds them through
:func:`tiered_edge`, so the vocabulary has one definition rather than three
that drift.
"""

from __future__ import annotations

#: Trust in an edge. ``semantic`` is SCIP-proven (lane B, V2.M2);
#: ``syntactic`` is a tree-sitter-era resolution that may be approximate;
#: ``dynamic`` is reserved for coverage traces — the schema carries it,
#: nothing ingests it (§3.4, §9).
SEMANTIC = "semantic"
SYNTACTIC = "syntactic"
DYNAMIC = "dynamic"

TIERS = (SEMANTIC, SYNTACTIC, DYNAMIC)

#: Who saw a given piece of evidence. Lane A's parsers are one lane, not
#: three: the tier is a statement about resolution strength, and every
#: v1 extractor resolves the same way.
LANE_TREE_SITTER = "tree-sitter"
LANE_SCIP = "scip"


def tiered_edge(
    from_id: str,
    to_id: str,
    edge_type: str,
    evidence: list[dict],
    tier: str = SYNTACTIC,
    lane: str = LANE_TREE_SITTER,
) -> dict:
    """One graph edge in v4 shape.

    *evidence* entries are ``{path, line}`` as the extractors produce them;
    each is stamped with *lane* here rather than at every call site. The
    default is lane A, because until V2.M2 lands there is no other producer
    — an edge that does not say where it came from would be a v4 artifact
    lying about its own provenance (P3).
    """
    return {
        "from": from_id,
        "to": to_id,
        "type": edge_type,
        "tier": tier,
        "evidence": [{**item, "lane": lane} for item in evidence],
    }
