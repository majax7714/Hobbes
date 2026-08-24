"""Pack: JS/TS CLI entry points from ``package.json`` ``bin`` (C-14).

The second CLI source the register said was missing: a package's ``bin``
map is npm's `[project.scripts]`, and reading only pyproject.toml made a
Node CLI repo report "no CLI" — an empty list that reads as an answer
(C-14, lifted with this pack).

Every ``package.json`` in the repo, pruned like every other discovery —
a monorepo's workspaces each declare their own binaries, and
``node_modules`` holds thousands of manifests that are not this repo's.
"""

from __future__ import annotations

import json
from pathlib import Path

from hobbes.extract.discover import SKIPPED_DIR_NAMES
from hobbes.extract.packs.base import Pack, PackContext, PackResult
from hobbes.extract.schema import SYNTACTIC


def iter_package_jsons(repo_root: Path):
    """Every ``package.json`` in the repo, pruned like Python discovery."""
    stack = [Path(repo_root)]
    while stack:
        directory = stack.pop()
        try:
            children = sorted(directory.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_dir():
                if child.name not in SKIPPED_DIR_NAMES and not child.name.startswith("."):
                    stack.append(child)
            elif child.name == "package.json":
                yield child


def _entries(repo_root: Path) -> list[dict]:
    entries = []
    for manifest in iter_package_jsons(repo_root):
        try:
            data = json.loads(manifest.read_text())
        except (OSError, ValueError):
            continue  # a broken manifest is not the extractor's problem
        if not isinstance(data, dict):
            continue
        source = manifest.relative_to(repo_root).as_posix()
        base = manifest.parent.relative_to(repo_root)
        bin_field = data.get("bin")
        if isinstance(bin_field, str):
            # `"bin": "./cli.js"` names one binary after the package —
            # npm uses the name's last segment for scoped packages.
            name = str(data.get("name") or "")
            name = name.rsplit("/", 1)[-1]
            if name:
                bin_field = {name: bin_field}
            else:
                bin_field = {}
        if not isinstance(bin_field, dict):
            continue
        for name, target in sorted(bin_field.items()):
            if not isinstance(name, str) or not isinstance(target, str):
                continue
            resolved = (base / target).as_posix().removeprefix("./")
            entries.append({"name": name, "target": resolved, "source": source})
    return sorted(entries, key=lambda e: (e["source"], e["name"]))


def _applies(ctx: PackContext) -> bool:
    """True when the repo has any ``package.json`` at all.

    The cli-python posture: a repo with manifests but no ``bin`` should
    report an empty list rather than look unexamined.
    """
    return any(True for _ in iter_package_jsons(ctx.repo_root))


def _run(ctx: PackContext) -> PackResult:
    return PackResult(cli_entry_points=_entries(ctx.repo_root))


PACK = Pack(name="cli-ts", tier=SYNTACTIC, applies=_applies, run=_run)
