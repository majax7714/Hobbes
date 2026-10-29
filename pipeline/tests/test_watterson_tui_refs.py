"""What the TUI fork's kept configs name still exists (DEC-028).

DEC-028 trimmed ``tui/opencode/`` to what the binary ships. The build alone
does not prove the rest of the workspace still holds together: a package
script, an export, a test preload or a tsconfig can name a file the trim
removed, and only the command that reads it fails. These tests walk every
kept manifest and config and fail on any name that no longer resolves.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

FORK = Path(__file__).resolve().parents[2] / "tui" / "opencode"
pytestmark = pytest.mark.skipif(not FORK.is_dir(), reason="no tui/opencode in this checkout")

#: A script argument that names a file: a relative path with an extension
#: the workspace's tools read.
_FILE_ARG = re.compile(r"(?<![\w@:/.-])((?:\.{1,2}/)?[\w.-]+(?:/[\w.-]+)*\.(?:ts|tsx|mts|js|mjs|cjs|json|ya?ml|toml))(?![\w/])")


#: The names `bun test` collects (its own rule): `.test`, `_test_`, `.spec`
#: or `_spec_` before a JS or TS extension.
_BUN_TEST = re.compile(r"(\.test|_test_|\.spec|_spec_)\.[cm]?[jt]sx?$")


def _manifests() -> list[Path]:
    return [FORK / "package.json", *sorted(FORK.glob("packages/*/package.json"))]


def _jsonc(path: Path) -> dict:
    """A tsconfig or turbo file: JSON with comments and trailing commas."""
    text = re.sub(r"(?m)^\s*//.*$", "", path.read_text())
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", text))


def _targets(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [t for v in value.values() for t in _targets(v)]
    if isinstance(value, list):
        return [t for v in value for t in _targets(v)]
    return []


def _matches(base: Path, pattern: str) -> bool:
    path = pattern.removeprefix("./")
    if "*" not in path:
        return (base / path).exists()
    return any(base.glob(path))


def test_every_file_a_package_script_names_exists():
    missing = []
    for manifest in _manifests():
        base = manifest.parent
        for name, command in json.loads(manifest.read_text()).get("scripts", {}).items():
            # `bun run --cwd <dir> <file>` reads the file from that dir.
            cwd = re.search(r"--cwd[ =](\S+)", command)
            at = base / cwd.group(1) if cwd else base
            for arg in _FILE_ARG.findall(re.sub(r"--cwd[ =]\S+", "", command)):
                if not (at / arg).exists():
                    missing.append(f"{manifest.relative_to(FORK)} scripts.{name}: {arg}")
    assert not missing, "\n".join(missing)


def test_every_declared_entry_point_resolves():
    missing = []
    for manifest in _manifests():
        data = json.loads(manifest.read_text())
        for key in ("exports", "imports", "bin", "main", "module", "types"):
            for target in _targets(data.get(key)):
                if target.startswith(("./", "../")) or key in ("main", "module", "types", "bin"):
                    if not _matches(manifest.parent, target):
                        missing.append(f"{manifest.relative_to(FORK)} {key}: {target}")
    assert not missing, "\n".join(missing)


def test_every_test_preload_exists():
    missing = []
    for bunfig in [FORK / "bunfig.toml", *sorted(FORK.glob("packages/*/bunfig.toml"))]:
        data = tomllib.loads(bunfig.read_text())
        for preload in [*_targets(data.get("preload")), *_targets(data.get("test", {}).get("preload"))]:
            if preload.startswith(("./", "../")) and not (bunfig.parent / preload).exists():
                missing.append(f"{bunfig.relative_to(FORK)}: {preload}")
    assert not missing, "\n".join(missing)


def test_every_tsconfig_has_inputs_and_its_parent():
    missing = []
    for tsconfig in sorted(FORK.glob("**/tsconfig*.json")):
        if "node_modules" in tsconfig.parts:
            continue
        data = _jsonc(tsconfig)
        base = tsconfig.parent
        parent = data.get("extends")
        if isinstance(parent, str) and parent.startswith(".") and not (base / parent).exists():
            missing.append(f"{tsconfig.relative_to(FORK)} extends: {parent}")
        for key in ("files", "include"):
            entries = data.get(key)
            if entries is not None and not any(_matches(base, e) for e in entries):
                missing.append(f"{tsconfig.relative_to(FORK)} {key}: no input among {entries}")
    assert not missing, "\n".join(missing)


def test_a_package_with_a_test_script_has_tests():
    # turbo's `test` task runs every package's test script, and `bun test`
    # with no test files exits 1.
    empty = []
    for manifest in _manifests()[1:]:
        if "test" not in json.loads(manifest.read_text()).get("scripts", {}):
            continue
        base = manifest.parent
        if not any(_BUN_TEST.search(p.name) for p in base.rglob("*") if "node_modules" not in p.parts):
            empty.append(str(manifest.relative_to(FORK)))
    assert not empty, "\n".join(empty)
