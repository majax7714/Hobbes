"""Lane B's index cache (ADR-122): the helper's facts file, kept under
the hash of everything that produced it, so an unchanged unit is read
back instead of indexed again.

The helper writes one facts file per indexing unit (ADR-116), and two
runs over the same stage write the same bytes — measured on this repo's
python stage and eight Go modules before this module existed. The
indexer's inputs are, by the staging contract (:mod:`staging`), exactly:
the stage tree, the config the helper is handed, the sidecar files that
config names under the cache (the venv listing, a rebased compile
database), the read-only mounts, the step's environment, and the
helper and image that run. The key hashes all of them; nothing else can
reach the container. A cached file is then the same answer by
construction, and it is read by the same reader (:func:`read_facts`),
which is what makes a hit byte-identical to a miss (P1).

What is **not** cached: a run on the host (the toolchain is unpinned
there), a run that failed (nothing to keep), and any run when
``HOBBES_INDEX_CACHE=0``. A stored file that no longer reads — short,
malformed, another version — is dropped and the unit indexed again; the
reader's own rule already says a short file is never a smaller answer.

The store is ``<cache>/index/<key>.facts.ndjson``. A hit touches the
file; an entry untouched for :data:`KEEP_DAYS` is swept when the next
entry is written. The residue the key does not see is registered as
C-158: a linked dependency tree is fingerprinted by its top directory
and its installer's hidden lockfile, not by its contents, and a venv by
its listing of distributions, not by their files.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from hobbes.extract.staging import cache_root

#: Set to "0" to index every unit afresh: for a measurement of the
#: uncached lane, and for a box that wants no store under its cache.
ENABLE_ENV = "HOBBES_INDEX_CACHE"

#: An entry neither written nor read for this long is swept at the next
#: write. Long enough for a branch to come back; short enough that a
#: ScummVM-sized facts file (ADR-116: 1.19 GB read) does not sit forever.
KEEP_DAYS = 30

#: What every occurrence of the stage's own path becomes in the hashed
#: config and sidecars, so two stages of one content share a key even
#: though :func:`staging.stage_path` names them by size and mtime.
STAGE_TOKEN = "<stage>"

#: Files an installer writes at the top of a dependency tree it
#: installed into — the cheap signal that the tree changed underneath a
#: link. npm ≥ 7, Yarn 1, pnpm, and Yarn Berry's state file.
_TREE_MARKERS = (
    ".package-lock.json",
    ".yarn-integrity",
    ".modules.yaml",
    ".yarn-state.yml",
)

#: Every lookup this process made, in run order — hit or miss, with the
#: seconds the key cost — for the ingest summary and the timings log
#: (ADR-119), never for an artifact. Reset per ingest.
LEDGER: list[dict] = []


def reset_ledger() -> None:
    LEDGER.clear()


def summary() -> dict | None:
    """Hits, misses and the keys' cost for the summary and the timings
    log; ``None`` when no lookup was made (lane B off, or every unit
    uncacheable)."""
    if not LEDGER:
        return None
    return {
        "hits": sum(1 for e in LEDGER if e["hit"]),
        "misses": sum(1 for e in LEDGER if not e["hit"]),
        "key_seconds": round(sum(e["key_seconds"] for e in LEDGER), 3),
        "store": str(store_root()),
    }


def enabled() -> bool:
    return os.environ.get(ENABLE_ENV, "1") not in ("0", "false", "no")


def store_root() -> Path:
    """Where the facts files live: beside ``stage/`` under the cache."""
    return cache_root() / "index"


def entry_path(key: str) -> Path:
    return store_root() / f"{key}.facts.ndjson"


def stage_root(stage: Path) -> Path | None:
    """The staging tree *stage* sits in — the directory directly under
    ``<cache>/stage/`` — or ``None`` when *stage* is not one. A unit's
    ``stage`` may be a subdirectory (a Go module, a crate, a TS zone),
    but the indexer sees the whole tree: a replaced sibling module, a
    referenced project."""
    root = cache_root() / "stage"
    try:
        rel = Path(os.path.normpath(stage)).relative_to(root)
    except ValueError:
        return None
    if not rel.parts:
        return None
    return root / rel.parts[0]


@dataclass(frozen=True)
class Key:
    """One unit's key and what it cost to compute."""

    value: str
    seconds: float


def key(
    config: dict,
    ro: tuple[str, ...] | list[str],
    env: tuple[str, ...] | list[str],
    image_id: str,
    helper_dir: Path,
) -> Key | None:
    """The hash of everything the helper's run depends on, or ``None``
    when the unit's stage is not a staging tree under the cache (a test
    handing the helper an arbitrary directory).

    In order: the helper (its source and its lockfile — the indexers
    under its ``node_modules`` are pinned by the lock, the binaries by
    the image), the image, the config with the stage's path tokenised and
    the run-local ``facts`` path dropped, every sidecar file the config
    names under the cache (the same tokenising, on its bytes), the stage
    tree file by file, the read-only mounts and the environment.
    """
    started = time.perf_counter()
    stage = Path(config["stage"])
    root = stage_root(stage)
    if root is None or not root.is_dir():
        return None
    token = str(root).encode()
    digest = hashlib.sha256()

    def part(label: str, data: bytes) -> None:
        digest.update(label.encode())
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")

    for name in ("index.mjs", "package-lock.json"):
        try:
            part(f"helper:{name}", _sha256(helper_dir / name))
        except OSError:
            part(f"helper:{name}", b"missing")
    part("image", image_id.encode())

    hashed = {k: v for k, v in config.items() if k != "facts"}
    part("config", json.dumps(hashed, sort_keys=True).encode().replace(token, STAGE_TOKEN.encode()))
    for name, value in sorted(hashed.items()):
        sidecar = _sidecar(value)
        if sidecar is not None:
            part(f"sidecar:{name}", sidecar.read_bytes().replace(token, STAGE_TOKEN.encode()))

    for rel, data in _tree(root):
        part(f"tree:{rel}", data)
    part("ro", "\n".join(sorted(ro)).encode())
    part("env", "\n".join(env).encode())
    return Key(digest.hexdigest()[:24], round(time.perf_counter() - started, 3))


def lookup(key: Key) -> Path | None:
    """The stored facts file for *key*, touched, or ``None``."""
    path = entry_path(key.value)
    if not path.is_file():
        return None
    try:
        os.utime(path)
    except OSError:
        pass
    return path


def store(key: Key, facts_path: Path) -> Path:
    """Keep *facts_path* under *key*: copied to a ``.partial`` beside the
    entry and renamed, so a killed ingest never leaves a half entry that
    reads as one. Sweeps the store's old entries once per process."""
    root = store_root()
    root.mkdir(parents=True, exist_ok=True)
    final = entry_path(key.value)
    partial = final.with_name(final.name + ".partial")
    shutil.copyfile(facts_path, partial)
    partial.rename(final)
    _sweep_once(root)
    return final


def discard(key: Key) -> None:
    """Drop an entry that no longer reads; a missing one is not an error."""
    entry_path(key.value).unlink(missing_ok=True)


def record(language: str, key: Key, hit: bool) -> None:
    LEDGER.append(
        {"language": language, "key": key.value, "hit": hit, "key_seconds": key.seconds}
    )


_swept: set[Path] = set()


def _sweep_once(root: Path) -> int:
    """Remove entries untouched for :data:`KEEP_DAYS`, and any
    ``.partial`` a killed run left; once per process per store."""
    if root in _swept:
        return 0
    _swept.add(root)
    return sweep(root)


def sweep(root: Path | None = None, now: float | None = None) -> int:
    root = root if root is not None else store_root()
    if not root.is_dir():
        return 0
    now = time.time() if now is None else now
    removed = 0
    for child in sorted(root.iterdir()):
        try:
            stale = child.name.endswith(".partial") or (
                now - child.stat().st_mtime > KEEP_DAYS * 86400
            )
            if stale:
                child.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def _sha256(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().encode()


def _sidecar(value) -> Path | None:
    """A config value naming an existing regular file under the cache —
    the venv listing, a rebased compile database — whose bytes are the
    helper's input, not its path."""
    if not isinstance(value, str) or not value.startswith("/"):
        return None
    path = Path(value)
    try:
        path.relative_to(cache_root())
    except ValueError:
        return None
    return path if path.is_file() and not path.is_symlink() else None


def _tree(root: Path):
    """Every entry of the stage in sorted order: a regular file by its
    content, a symlink by its target and the target's fingerprint."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        base = Path(dirpath)
        # A linked directory is walked by fingerprint, never descended:
        # node_modules runs to hundreds of megabytes (ADR-032).
        linked = [d for d in dirnames if (base / d).is_symlink()]
        for name in linked:
            dirnames.remove(name)
        entries = sorted([*linked, *filenames])
        for name in entries:
            path = base / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                yield rel, _link_fingerprint(path)
            else:
                yield rel, _sha256(path)


def _link_fingerprint(link: Path) -> bytes:
    """A link's target, and the target's top-level stat plus its
    installer marker's — what changes when a tree is reinstalled. C-158
    names what this does not see."""
    target = os.readlink(link)
    parts = [f"-> {target}"]
    resolved = Path(os.path.normpath(link.parent / target)) if not os.path.isabs(target) else Path(target)
    try:
        stat = resolved.stat()
        parts.append(f"dir:{stat.st_size}:{stat.st_mtime_ns}")
    except OSError:
        parts.append("dir:missing")
        return "\n".join(parts).encode()
    for marker in _TREE_MARKERS:
        try:
            stat = (resolved / marker).stat()
            parts.append(f"{marker}:{stat.st_size}:{stat.st_mtime_ns}")
        except OSError:
            continue
    return "\n".join(parts).encode()
