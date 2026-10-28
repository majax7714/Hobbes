"""Compare the locked ACP adapters against npm, and report the gap (DEC-004).

``hobbes agents --check`` runs ``check_adapters``. For each adapter in
``registry.LOCKED_ADAPTERS`` it reads the pin from ``adapters/package.json``
and the installed version from ``adapters/node_modules``, fetches the
package's npm registry document, and works out how far the pin is behind.
It never changes a pin: bumps stay manual.

A **cooldown** applies: a stable release younger than ``COOLDOWN`` is shown
as cooling down, not suggested, and the suggested bump is the newest stable
release past it. Prereleases (any ``-tag``) and deprecated versions are
never latest or suggested.

``Freshness`` is the result shape. It is generic (a subject, what is pinned,
what is current, the latest, a suggestion, a gap and a status), lives in
``hobbes.watterson.checks`` so the graph freshness check (``hobbes.watterson.freshness``,
DEC-005) reuses it without importing this layer, and is re-exported here.
``exit_code`` maps results to the CLI's exit code. Each adapter's bundled
harness version (the npm package it runs its harness from) is reported
beside it as a ``Harness``.

The network and the user's harness CLIs are reached only through
``fetch_packument`` and ``cli_version``; tests pass fakes and a fake
adapters root.
"""

from __future__ import annotations

import enum
import http.client
import json
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from hobbes.watterson.checks import Freshness  # re-exported; generic since DEC-005
from hobbes.watterson.providers import registry
from hobbes.watterson.providers.registry import LockedAdapter

#: A newer release must be at least this old before it is suggested.
COOLDOWN = timedelta(days=2)
NPM_REGISTRY = "https://registry.npmjs.org"
FETCH_TIMEOUT = 10.0
_CLI_TIMEOUT = 5.0
_STABLE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

#: ``fetch(package) -> packument``; raises ``OSError`` when offline.
Fetch = Callable[[str], dict[str, Any]]
#: ``cli_version(command) -> "--version" output``, or None when unavailable.
CliVersion = Callable[[str], "str | None"]


class Status(enum.StrEnum):
    """One check's verdict, from worst to best."""

    MISMATCH = "pin != installed"   # local state disagrees with the pin
    BUMP = "bump suggested"         # a newer release is past the cooldown
    COOLING = "cooling down"        # only releases inside the cooldown are newer
    CURRENT = "up to date"
    UNKNOWN = "unknown"             # the remote side could not be reached


@dataclass(frozen=True)
class Harness:
    """The harness an adapter bundles, beside the user's own install of it."""

    package: str
    bundled: str | None       # version installed in adapters/node_modules
    bundled_note: str | None  # e.g. the Claude Code version the SDK carries
    cli: str
    cli_version: str | None   # the user's ``<cli> --version``, if on PATH


@dataclass(frozen=True)
class AdapterCheck:
    adapter: LockedAdapter
    freshness: Freshness
    harness: Harness


def exit_code(results: Iterable[Freshness]) -> int:
    """2 if the remote was unreachable, 1 if anything needs action, else 0."""
    results = list(results)
    if any(r.error for r in results):
        return 2
    if any(r.status in (Status.MISMATCH, Status.BUMP) for r in results):
        return 1
    return 0


def fetch_packument(package: str) -> dict[str, Any]:
    """The npm registry document for *package*; ``OSError`` when unreachable."""
    url = f"{NPM_REGISTRY}/{urllib.parse.quote(package, safe='@')}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
            return json.load(response)
    except (ValueError, http.client.HTTPException) as exc:  # a garbled reply is no reply
        raise OSError(f"bad reply from {url}: {exc}") from exc


def cli_version(command: str) -> str | None:
    """First line of ``<command> --version``, or None if it is not on PATH."""
    path = shutil.which(command)
    if path is None:
        return None
    try:
        out = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=_CLI_TIMEOUT, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = out.stdout.strip().splitlines()
    return lines[0].strip() if out.returncode == 0 and lines else None


def _stable_key(version: str) -> tuple[int, int, int] | None:
    match = _STABLE.match(version)
    return tuple(int(part) for part in match.groups()) if match else None  # type: ignore[return-value]


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _read_version(package_json: Path) -> str | None:
    try:
        return json.loads(package_json.read_text()).get("version")
    except (OSError, ValueError):
        return None


def _installed(root: Path, package: str, under: str | None = None) -> str | None:
    """*package*'s installed version, nested under *under* first, then hoisted."""
    candidates = []
    if under:
        candidates.append(root / "node_modules" / under / "node_modules" / package / "package.json")
    candidates.append(root / "node_modules" / package / "package.json")
    for path in candidates:
        version = _read_version(path)
        if version:
            return version
    return None


def compare(
    subject: str,
    pinned: str | None,
    installed: str | None,
    packument: dict[str, Any] | None,
    *,
    now: datetime,
    error: str | None = None,
) -> Freshness:
    """Judge one pin against its packument (None plus *error* when offline)."""
    notes: list[str] = []
    mismatch = pinned is None or installed != pinned
    if pinned is None:
        notes.append("no pin in adapters/package.json")
    elif installed is None:
        notes.append(f"not installed; {registry.ADAPTERS_INSTALL_HINT}")
    elif installed != pinned:
        notes.append(f"installed {installed} != pinned {pinned}; {registry.ADAPTERS_INSTALL_HINT}")
    if pinned is not None and _stable_key(pinned) is None:
        notes.append(f"pin {pinned!r} is not an exact stable version")

    if packument is None:
        status = Status.MISMATCH if mismatch else Status.UNKNOWN
        return Freshness(
            subject, pinned, installed, None, None, None, status, notes=tuple(notes), error=error
        )

    times = packument.get("time", {})
    versions = packument.get("versions", {})
    stable = sorted(
        (
            (key, v, _parse_time(times[v]))
            for v in versions
            if (key := _stable_key(v)) is not None
            and v in times
            and not versions[v].get("deprecated")
        ),
        key=lambda item: item[0],
    )
    latest = stable[-1][1] if stable else None
    pin_key = _stable_key(pinned) if pinned else None
    newer = [item for item in stable if pin_key is not None and item[0] > pin_key]
    ripe = [item for item in newer if now - item[2] >= COOLDOWN]
    suggested = ripe[-1][1] if ripe else None
    for _, version, published in newer:
        if now - published < COOLDOWN:
            age = now - published
            notes.append(
                f"{version} published {published:%Y-%m-%d} is cooling down "
                f"({age.days}d {age.seconds // 3600}h old, cooldown {COOLDOWN.days}d)"
            )

    behind_by = None
    if newer and pinned in times:
        days = (newer[-1][2] - _parse_time(times[pinned])).days
        count = len(newer)
        behind_by = f"{count} stable release{'s' if count != 1 else ''}, {days} days"

    if mismatch:
        status = Status.MISMATCH
    elif suggested:
        status = Status.BUMP
    elif newer:
        status = Status.COOLING
    else:
        status = Status.CURRENT
    latest_at = stable[-1][2] if stable else None
    return Freshness(
        subject, pinned, installed, latest, suggested, behind_by, status, latest_at, tuple(notes)
    )


def _harness(adapter: LockedAdapter, root: Path, cli: CliVersion) -> Harness:
    bundled = _installed(root, adapter.harness, under=adapter.package)
    note = None
    if adapter.harness == "@anthropic-ai/claude-agent-sdk":
        nested = root / "node_modules" / adapter.package / "node_modules" / adapter.harness
        for base in (nested, root / "node_modules" / adapter.harness):
            try:
                cc = json.loads((base / "package.json").read_text()).get("claudeCodeVersion")
            except (OSError, ValueError):
                continue
            if cc:
                note = f"Claude Code {cc}"
                break
    return Harness(adapter.harness, bundled, note, adapter.cli, cli(adapter.cli))


def check_adapters(
    adapters_root: Path | None = None,
    *,
    fetch: Fetch | None = None,
    now: datetime | None = None,
    cli: CliVersion | None = None,
    adapters: Iterable[LockedAdapter] | None = None,
) -> list[AdapterCheck]:
    """Check every locked adapter under *adapters_root* (default: the repo's)."""
    root = adapters_root or registry.ADAPTERS_DIR
    fetch = fetch or fetch_packument
    cli = cli or cli_version
    now = now or datetime.now(UTC)
    try:
        pins = json.loads((root / "package.json").read_text()).get("dependencies", {})
    except (OSError, ValueError):
        pins = {}
    checks = []
    for adapter in adapters if adapters is not None else registry.LOCKED_ADAPTERS:
        try:
            packument, error = fetch(adapter.package), None
        except OSError as exc:
            reason = getattr(exc, "reason", None) or exc
            packument, error = None, f"cannot reach npm for {adapter.package}: {reason}"
        freshness = compare(
            adapter.package,
            pins.get(adapter.package),
            _installed(root, adapter.package),
            packument,
            now=now,
            error=error,
        )
        checks.append(AdapterCheck(adapter, freshness, _harness(adapter, root, cli)))
    return checks
