"""Enrichment packs: framework knowledge, isolated and removable (ADR-035).

The architecture's §3.5 makes packs the plugin surface symmetric with
indexers. Lane A gives structure and lane B gives resolution; neither knows
that a decorator is an HTTP route, that an HCL block is a resource, or that
a Terraform ``environment`` block and a Python ``os.environ`` read are two
ends of one fact. That knowledge is framework-shaped, it dates faster than
the parsers do, and keeping it in the graph builder is how a builder stops
being general (P7).

**Registered in code, activated by detection (ADR-035).** There is no
``hobbes.yaml``: a pack's ``applies`` reads the repo and answers for
itself, the same way the indexer config is derived rather than authored
(ADR-027's amendment). ``graph.json`` records which packs ran, so the layer
is attributable in the artifact and not only in this file.

**The contract that makes a pack a pack** is removability, and it is
V2.M4's exit criterion: dropping a pack from :data:`REGISTRY` removes
exactly its own contribution and nothing else, and putting it back
reproduces the artifact byte-for-byte. ``test_packs.py`` asserts it per
pack rather than trusting it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hobbes.extract.packs import (
    cli_go,
    cli_python,
    cli_rust,
    cli_ts,
    http_go,
    http_python,
    http_ts,
    terraform,
)
from hobbes.extract.packs.base import Pack, PackContext, PackRefusal, PackResult

#: The built-in packs, in the order they run. Order is not load-bearing —
#: contributions are merged and sorted — but it fixes ``ran`` and therefore
#: the artifact, so it stays stable. The three C-14 packs append rather
#: than slot beside cli-python, for exactly that reason.
REGISTRY: tuple[Pack, ...] = (
    http_python.PACK,
    cli_python.PACK,
    http_ts.PACK,
    http_go.PACK,
    terraform.PACK,
    cli_ts.PACK,
    cli_go.PACK,
    cli_rust.PACK,
)


@dataclass(frozen=True)
class PacksOutput:
    """The merged contribution of every pack that ran, plus who ran."""

    nodes: list[dict] = field(default_factory=list)
    module_edges: list[dict] = field(default_factory=list)
    routes: list[dict] = field(default_factory=list)
    cli_entry_points: list[dict] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    #: Names of the packs that applied and ran, in registry order.
    ran: list[str] = field(default_factory=list)


def run_packs(ctx: PackContext, packs: tuple[Pack, ...] = REGISTRY) -> PacksOutput:
    """Run every pack that applies to *ctx*, in registry order.

    A pack that raises is **degraded, not fatal**: its contribution is
    dropped and an ``extraction_errors`` record takes its place, because a
    framework pass failing on one repo must not cost that repo its whole
    graph (P6). The failure is named, since a pack that silently produced
    nothing is indistinguishable from a repo that does not use the
    framework — which is the confusion this system exists to prevent (C-1).

    :class:`PackRefusal` is the exception, and it is re-raised. A pack
    declining input the user supplied — a ``.tfstate`` handed to
    ``--tf-plan`` — is not a pass that broke, and degrading it would turn a
    refusal into a warning printed beside the thing it refused to do.
    """
    out = PacksOutput()
    for pack in packs:
        try:
            if not pack.applies(ctx):
                continue
            result = pack.run(ctx)
        except PackRefusal:
            raise
        except Exception as exc:  # noqa: BLE001 — a pack must not fail ingest
            out.errors.append(
                {
                    "path": ".",
                    "stage": f"pack:{pack.name}",
                    "message": f"enrichment pack {pack.name!r} failed: {exc}",
                }
            )
            continue
        out.nodes.extend(result.nodes)
        out.module_edges.extend(result.module_edges)
        out.routes.extend(result.routes)
        out.cli_entry_points.extend(result.cli_entry_points)
        out.languages.extend(result.languages)
        out.errors.extend(result.errors)
        out.ran.append(pack.name)
    return out


__all__ = [
    "REGISTRY",
    "Pack",
    "PackContext",
    "PackRefusal",
    "PackResult",
    "PacksOutput",
    "run_packs",
]
