"""The pack contract: context in, contribution out (ADR-035).

Separate from the package's ``__init__`` so a pack module can import the
types without importing the registry that lists it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from hobbes.extract.discover import ModuleInfo
from hobbes.extract.pysource import ParsedFile


class PackRefusal(RuntimeError):
    """A pack refusing input the user supplied. **Never degraded.**

    Packs degrade by default (P6): a framework pass that fails on one repo
    must not cost that repo its graph. But some failures are refusals, not
    breakages — the Terraform pack handed a ``.tfstate`` is not failing to
    read state, it is *declining* to, and that is the guard behind I-1.

    Degrading a refusal turns "Hobbes refused to read your state file" into
    "Hobbes read your state file, with a warning", which is the opposite
    outcome. :func:`hobbes.extract.packs.run_packs` re-raises this and
    catches everything else.
    """


@dataclass(frozen=True)
class PackContext:
    """Everything the lanes know, handed to a pack read-only.

    A pack never re-parses source: it reads the facts the lanes already
    produced. Re-deriving them would give two answers to one question, and
    the second one would be wrong eventually (P1).
    """

    repo_root: Path
    #: Python modules from discovery, and their parsed facts.
    modules: list[ModuleInfo]
    parsed: dict[str, ParsedFile]
    #: The TS/JS layer's facts bundle, or ``None`` when the repo has no
    #: TypeScript (or the helper could not run).
    ts: dict | None = None
    #: The Go layer's facts bundle, or ``None`` when the repo has no Go.
    go: dict | None = None
    #: The Rust layer's facts bundle, or ``None`` when the repo has no Rust.
    rust: dict | None = None
    #: ``terraform show -json`` document, when ``ingest --tf-plan`` gave one.
    tf_plan: Path | None = None


@dataclass(frozen=True)
class PackResult:
    """What a pack contributes. Every field is optional and additive."""

    nodes: list[dict] = field(default_factory=list)
    module_edges: list[dict] = field(default_factory=list)
    routes: list[dict] = field(default_factory=list)
    cli_entry_points: list[dict] = field(default_factory=list)
    #: Languages this pack proves the repo contains. Only for languages no
    #: lane owns — HCL has no lane A parser of its own, so the Terraform
    #: pack is the only thing that can say the repo has any.
    languages: list[str] = field(default_factory=list)
    #: Degradation records, in ``extraction_errors`` shape. A pack reports
    #: rather than raises: one framework's absence must not fail an ingest.
    errors: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Pack:
    """A registered enrichment pass.

    *tier* is the trust its edges carry (§3.5). All four built-in packs
    declare ``syntactic``: each reads structure — a decorator, an HCL
    block, a string literal — with no semantic provider behind it. A pack
    that promoted edges on SCIP-proven evidence would declare ``semantic``,
    and none does today.
    """

    name: str
    tier: str
    applies: Callable[[PackContext], bool]
    run: Callable[[PackContext], PackResult]
