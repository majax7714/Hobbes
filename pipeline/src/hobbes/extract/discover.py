"""Repo discovery: find Python files and their import identities.

Every ``.py`` file becomes a module with a dotted import name computed by
walking its ``__init__.py`` package chain up to the import root (the
directory above the topmost package). Ids follow ADR-006: the import name,
disambiguated with the import root's repo-relative path when two roots
provide the same name (monorepos routinely have two ``tests`` packages).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

#: Directory names never descended into. Dot-directories (.git, .venv,
#: .hobbes, …) are skipped wholesale.
SKIPPED_DIR_NAMES = {
    "__pycache__",
    "node_modules",
    "venv",
    "dist",
    "build",
    "site-packages",
}


@dataclass(frozen=True)
class ModuleInfo:
    """One Python file's identity within the repo."""

    id: str
    """Graph node id: the import name, root-prefixed on collision (ADR-006)."""

    import_name: str
    """Dotted name as Python would import it (``hobbes.cli``)."""

    path: str
    """Repo-relative POSIX path of the file."""

    root: str
    """Repo-relative POSIX path of the import root (``.`` for the repo root).
    Import resolution prefers modules sharing the importer's root."""

    kind: str
    """``module`` for a plain file, ``package`` for an ``__init__.py``."""


def _skipped(name: str) -> bool:
    return name in SKIPPED_DIR_NAMES or name.startswith(".")


def iter_python_files(repo_root: Path) -> Iterator[Path]:
    """Yield every .py file under *repo_root*, pruning skipped directories."""
    stack = [repo_root]
    while stack:
        directory = stack.pop()
        for child in sorted(directory.iterdir()):
            if child.is_dir():
                if not _skipped(child.name):
                    stack.append(child)
            elif child.suffix == ".py":
                yield child


def _import_root(file: Path, repo_root: Path) -> Path:
    """The directory above the topmost package containing *file*.

    A file outside any package is its own root's direct child (scripts get
    their filename stem as import name).
    """
    directory = file.parent
    topmost = None
    while (directory / "__init__.py").is_file() and directory != repo_root:
        topmost = directory
        directory = directory.parent
    return topmost.parent if topmost is not None else file.parent


def discover_modules(repo_root: Path) -> list[ModuleInfo]:
    """Discover all Python modules under *repo_root*, sorted by id."""
    repo_root = Path(repo_root).resolve()
    found: list[tuple[str, str, str, str]] = []
    for file in iter_python_files(repo_root):
        root = _import_root(file, repo_root)
        parts = list(file.relative_to(root).with_suffix("").parts)
        kind = "module"
        if parts[-1] == "__init__":
            parts = parts[:-1]
            kind = "package"
            if not parts:  # repo root itself is a package; nothing above it
                continue
        root_rel = (
            root.relative_to(repo_root).as_posix() if root != repo_root else "."
        )
        found.append(
            (".".join(parts), file.relative_to(repo_root).as_posix(), root_rel, kind)
        )

    collisions = Counter(name for name, _, _, _ in found)
    modules = [
        ModuleInfo(
            id=name if collisions[name] == 1 else f"{root_rel}:{name}",
            import_name=name,
            path=path,
            root=root_rel,
            kind=kind,
        )
        for name, path, root_rel, kind in found
    ]
    return sorted(modules, key=lambda m: m.id)
