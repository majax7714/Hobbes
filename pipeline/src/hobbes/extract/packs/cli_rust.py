"""Pack: Rust CLI entry points from cargo's binary targets (C-14).

The fourth CLI source. Cargo names binaries three ways, all deterministic:
``src/main.rs`` is a binary named after the package, files under
``src/bin/`` are each a binary named after their stem (or their directory,
for the ``src/bin/<name>/main.rs`` form), and explicit ``[[bin]]`` tables
override or add. All three are read here — the manifests directly, the
file set from the lane's facts, never a re-parse (ADR-035).
"""

from __future__ import annotations

import tomllib
from pathlib import Path, PurePosixPath

from hobbes.extract.packs.base import Pack, PackContext, PackResult
from hobbes.extract.rustsource import iter_cargo_manifests
from hobbes.extract.schema import SYNTACTIC


def _entries(repo_root: Path, rust: dict) -> list[dict]:
    known_files = {parsed.path for parsed in rust["files"]}
    entries: dict[tuple[str, str], dict] = {}

    for manifest in iter_cargo_manifests(Path(repo_root)):
        try:
            data = tomllib.loads(manifest.read_text())
        except (OSError, ValueError):
            continue  # a broken manifest is not the extractor's problem
        source = manifest.relative_to(repo_root).as_posix()
        base = manifest.parent.relative_to(repo_root)
        package = (data.get("package") or {}).get("name")

        def rel(path: str) -> str:
            return (PurePosixPath(base) / path).as_posix().removeprefix("./")

        def add(name: str, target: str):
            entries.setdefault((source, name), {"name": name, "target": target, "source": source})

        # Explicit [[bin]] tables first: an explicit name wins over the
        # convention for the same target.
        for table in data.get("bin") or []:
            if not isinstance(table, dict):
                continue
            name = table.get("name")
            if not isinstance(name, str) or not name:
                continue
            path = table.get("path")
            target = rel(path) if isinstance(path, str) else rel(f"src/bin/{name}.rs")
            add(name, target)

        # Convention: src/main.rs is a binary named after the package.
        main_rs = rel("src/main.rs")
        if isinstance(package, str) and package and main_rs in known_files:
            add(package, main_rs)

        # Convention: src/bin/<stem>.rs and src/bin/<dir>/main.rs.
        claimed = {e["target"] for e in entries.values()}
        bin_prefix = rel("src/bin") + "/"
        for path in sorted(known_files):
            if not path.startswith(bin_prefix) or path in claimed:
                continue
            remainder = PurePosixPath(path[len(bin_prefix):])
            if len(remainder.parts) == 1 and remainder.suffix == ".rs":
                add(remainder.stem, path)
            elif len(remainder.parts) == 2 and remainder.name == "main.rs":
                add(remainder.parts[0], path)

    return sorted(entries.values(), key=lambda e: (e["source"], e["name"]))


def _applies(ctx: PackContext) -> bool:
    return ctx.rust is not None


def _run(ctx: PackContext) -> PackResult:
    return PackResult(cli_entry_points=_entries(ctx.repo_root, ctx.rust))


PACK = Pack(name="cli-rust", tier=SYNTACTIC, applies=_applies, run=_run)
