"""Pack: the Terraform layer and its cross-layer joins (ADR-035, ADR-010).

The largest port and the one with the most hand-verified behaviour behind
it — the private-repo-A ``packages`` edge checked by hand at
``infra-core/lambda.tf:5``, the ``env:VAR`` join that makes infra-to-code
environment coupling a visible edge, the tfstate refusal. So the pack is an
**adapter over the retained implementation** (:mod:`hobbes.extract.terraform`)
rather than a rewrite: same code, new and only caller. Rewriting 372 verified
lines for a structural change no user can observe is how a milestone about
removability becomes a milestone about regressions.

This is the one pack that contributes graph *nodes and edges* rather than
interface rows, and the only one that can tell the graph a language is
present — HCL has no lane of its own, so if this pack does not run, nothing
else will say the repo contains Terraform.
"""

from __future__ import annotations

from hobbes.extract.packs.base import Pack, PackContext, PackRefusal, PackResult
from hobbes.extract.schema import SYNTACTIC
from hobbes.extract.terraform import PlanError, discover_tf, extract_terraform


def _applies(ctx: PackContext) -> bool:
    """True when the repo contains any ``.tf`` file.

    Uses the extractor's own pruned discovery, so detection and extraction
    can never disagree about which files count — and so a pure-Python repo
    does not pay for an HCL parse it has no use for.
    """
    return bool(discover_tf(ctx.repo_root))


def _run(ctx: PackContext) -> PackResult:
    try:
        infra = extract_terraform(ctx.repo_root, ctx.modules, tf_plan=ctx.tf_plan)
    except PlanError as exc:
        # A refusal, not a failure — a `.tfstate` handed to --tf-plan must
        # stop the ingest, not warn and continue (I-1, ADR-011). Degrading
        # it here would have quietly reversed the guarantee.
        raise PackRefusal(str(exc)) from exc
    if not infra["tf_file_count"]:
        return PackResult()
    return PackResult(
        nodes=infra["nodes"],
        module_edges=infra["module_edges"],
        languages=["hcl"],
    )


PACK = Pack(name="terraform", tier=SYNTACTIC, applies=_applies, run=_run)
