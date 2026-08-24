"""Pack: Python CLI entry points from ``[project.scripts]`` (ADR-035).

Every ``pyproject.toml`` in the repo, not just the root one — a monorepo
with three packages has three sets of console scripts, and reading only the
root would report the repo as having no CLI at all.

Console scripts are the only source (**C-14**): a ``setup.py``
``entry_points``, a bare ``if __name__ == "__main__"``, or a Typer app
mounted somewhere else are all invisible here.
"""

from __future__ import annotations

from hobbes.extract.interfaces import extract_cli_entry_points, iter_pyprojects
from hobbes.extract.packs.base import Pack, PackContext, PackResult
from hobbes.extract.schema import SYNTACTIC


def _applies(ctx: PackContext) -> bool:
    """True when the repo has any ``pyproject.toml`` at all.

    Deliberately loose: a repo with a pyproject but no scripts should report
    an empty list rather than look unexamined. Uses the same pruned walk the
    extraction does — ``rglob`` here would descend into ``node_modules``.
    """
    return any(True for _ in iter_pyprojects(ctx.repo_root))


def _run(ctx: PackContext) -> PackResult:
    return PackResult(cli_entry_points=extract_cli_entry_points(ctx.repo_root))


PACK = Pack(name="cli-python", tier=SYNTACTIC, applies=_applies, run=_run)
