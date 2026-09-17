"""Lane A's C++ file cache (ADR-128 §4): one unchanged file's parse, kept
under the hash of everything that produced it, so a re-ingest of a large
C++ repo skips the per-file walk.

:func:`hobbes.extract.cppsource._parse_file` reads nothing but its two
arguments — the repo-relative path and the file's bytes — and the
pipeline's own code, and returns plain data. It is therefore a pure
function of those three, and the key hashes exactly them: a format tag,
the **code fingerprint** (the name and bytes of every
``hobbes/extract/*.py``, and the installed versions of ``tree-sitter``
and ``tree-sitter-cpp``), the path and the bytes. Any change to the
extraction code misses everywhere, which is what makes a hit the same
answer as a parse rather than merely a fast one. Only C++ is cached:
every other language's lane A is under 2 s on every timed repo (ADR-128's
numbers), so a store there is a cost with nothing to buy.

**JSON, never pickle.** The store sits under the Hobbes cache, a
directory other processes can reach, so it holds data and not code — an
unpickle is a call into whatever wrote the file. The cost is that JSON
has no tuple, no set and no ``array``, which ``_parse_file``'s result
uses (a symbol's ``qualifiers``, a file's ``duplicate_names``, its packed
``operators``); the first prototype's
plain JSON turned a ``qualifiers`` tuple into a list, so
:func:`encode` tags both and every record written is decoded back and
compared to the object it came from before it is kept.

**When in doubt, parse.** A missing version, a record that will not read,
a value the encoding refuses, a store that will not be written: each
falls back to the parse, and no failure of this module can fail an
extraction. The store is ``<cache>/lanea/cpp/<2 hex>/<key>.json``,
written ``.partial`` then renamed; a hit touches it, and an entry
untouched for :data:`KEEP_DAYS` is swept once per process at the first
write. ``HOBBES_LANEA_CACHE=0`` parses every file afresh.

The residue the key does not see is **C-160**: a native grammar rebuilt
at the same version, and code outside ``hobbes/extract/`` that
``_parse_file`` would come to reach (none today). The ingest's summary
line surfaces it.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.metadata
import json
import os
import time
from array import array
from pathlib import Path
from typing import Callable

from hobbes.extract.staging import cache_root

#: Set to "0" to parse every C++ file afresh: for a measurement of the
#: uncached lane, and for a box that wants no store under its cache.
ENABLE_ENV = "HOBBES_LANEA_CACHE"

#: An entry neither written nor read for this long is swept at the next
#: write. Long enough for a branch to come back; short enough that a
#: ScummVM-sized store (ADR-128: 289 MB) does not sit forever.
KEEP_DAYS = 30

#: Hashed into every key, so a change to the record's shape invalidates
#: the store rather than meeting it as a decode failure per file. v2: a
#: call carries its written argument count and a symbol its parameter
#: count (ADR-130), and an entry written without them would read back as
#: a parse that never counted. v3: a file carries its operator tokens
#: (ADR-131), and an entry written without them would read back as a
#: parse that saw no operator at all.
FORMAT = "lanea-cpp v3"

#: The tags the encoding gives the three types JSON has not. None can
#: collide with a field name: a NUL is not in any identifier, and the
#: encoder refuses a dict key that is one of these anyway.
TUPLE_TAG = "\0tuple"
SET_TAG = "\0set"
#: An ``array`` of packed operator tokens (ADR-131) — a list of ints on
#: disk, the ``array`` in memory, so a record read back is the object
#: ``_parse_file`` returned and not a list that merely compares equal.
ARRAY_TAG = "\0array"

#: The leaf types a record may hold. Anything else is a refusal, not a
#: best effort: a record that is not what ``_parse_file`` returned is
#: worse than no record.
_LEAVES = (str, int, float, bool)

#: The distributions whose version the fingerprint carries — the parser
#: core and the grammar that together decide what a walk sees.
_PINNED = ("tree-sitter", "tree-sitter-cpp")

#: Every lookup this process made, in run order — hit or miss, with the
#: seconds it cost — for the ingest summary and the timings log
#: (ADR-119), never for an artifact. Reset per ingest.
LEDGER: list[dict] = []


def reset_ledger() -> None:
    LEDGER.clear()


def summary() -> dict | None:
    """Hits, misses and their cost for the summary and the timings log;
    ``None`` when no lookup was made (no C++ in the repo, the cache off,
    or no fingerprint to key on)."""
    if not LEDGER:
        return None
    return {
        "hits": sum(1 for e in LEDGER if e["hit"]),
        "misses": sum(1 for e in LEDGER if not e["hit"]),
        "read_seconds": round(sum(e["read_seconds"] for e in LEDGER), 3),
        "store_seconds": round(sum(e["store_seconds"] for e in LEDGER), 3),
        "store": str(store_root()),
    }


def enabled() -> bool:
    return os.environ.get(ENABLE_ENV, "1") not in ("0", "false", "no")


def store_root() -> Path:
    """Where the records live: beside lane B's ``index`` store under the
    cache, and read-only in every contained step (ADR-128 §1)."""
    return cache_root() / "lanea" / "cpp"


def entry_path(key: str) -> Path:
    """One record's path, fanned out by the key's first byte so a
    ScummVM-sized store is not one directory of 20,000 files."""
    return store_root() / key[:2] / f"{key}.json"


_UNSET = object()
_FINGERPRINT: object = _UNSET


def code_fingerprint() -> str | None:
    """The hash of the code a parse depends on, computed once per
    process, or ``None`` when it cannot be — in which case caching is off
    for the process and every file is parsed.

    Every ``hobbes/extract/*.py`` by name and bytes, sorted by name (the
    walk, what it calls, and what they call, all in this one directory),
    then the pinned distributions' installed versions. C-160 names what
    this does not see.
    """
    global _FINGERPRINT
    if _FINGERPRINT is _UNSET:
        _FINGERPRINT = _compute_fingerprint()
    return _FINGERPRINT  # type: ignore[return-value]


def _compute_fingerprint() -> str | None:
    digest = hashlib.sha256()
    directory = Path(__file__).resolve().parent
    try:
        for path in sorted(directory.glob("*.py"), key=lambda p: p.name):
            _part(digest, path.name, path.read_bytes())
    except OSError:
        return None
    for dist in _PINNED:
        try:
            version = importlib.metadata.version(dist)
        except Exception:
            return None
        _part(digest, dist, f"{dist}={version}".encode())
    return digest.hexdigest()


def key(rel: str, source: bytes) -> str:
    """The hash of the format, the fingerprint, the path and the bytes —
    the whole of what :func:`_parse_file` reads."""
    digest = hashlib.sha256()
    for part in (FORMAT.encode(), str(code_fingerprint()).encode(), rel.encode(), source):
        digest.update(part)
        digest.update(b"\0")
    return digest.hexdigest()


def cached_parse(rel: str, source: bytes, parse: Callable) -> tuple:
    """*parse*'s answer for (*rel*, *source*), from the store when it is
    there and from *parse* otherwise.

    Returns exactly what *parse* returns, decoded into a new object each
    time so a caller's later in-place edit cannot reach the store. Every
    failure — a store that will not read, a record that will not decode, a
    value the encoding refuses, a store that will not be written — parses
    or keeps nothing, and none of them raises.
    """
    if not enabled() or code_fingerprint() is None:
        return parse(rel, source)
    path = entry_path(key(rel, source))

    started = time.perf_counter()
    hit = _load(path)
    read_seconds = time.perf_counter() - started
    if hit is not None:
        LEDGER.append({"hit": True, "read_seconds": read_seconds, "store_seconds": 0.0})
        return hit

    result = parse(rel, source)
    started = time.perf_counter()
    _store(path, result)
    LEDGER.append(
        {
            "hit": False,
            "read_seconds": read_seconds,
            "store_seconds": time.perf_counter() - started,
        }
    )
    return result


def _load(path: Path) -> tuple | None:
    """The stored answer at *path*, touched, or ``None``. An entry that
    exists and does not read — truncated by a killed run, written by
    another format — is dropped, and the caller parses."""
    if not path.is_file():
        return None
    try:
        result = decode_record(json.loads(path.read_text()))
    except (OSError, ValueError, TypeError, KeyError):
        try:
            path.unlink()
        except OSError:
            pass
        return None
    try:
        os.utime(path)
    except OSError:
        pass
    return result


def _store(path: Path, result: tuple) -> None:
    """Keep *result* at *path*, or keep nothing.

    The record is decoded back and compared to the object it came from
    before it is written: a lost tuple is a wrong answer at every later
    ingest, and the prototype lost one on its first file. A read-only
    store or a full disk is not an error here either — the parse already
    produced the answer.
    """
    try:
        text = json.dumps(encode_record(result), sort_keys=True)
        if decode_record(json.loads(text)) != result:
            return
    except (TypeError, ValueError):
        return
    partial = path.with_name(path.name + ".partial")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(text)
        partial.rename(path)
    except OSError:
        return
    _sweep_once(store_root())


# ---------------------------------------------------------------- the record


def encode_record(result: tuple) -> dict:
    """``(CppFile, had_error, duplicated)`` as JSON-able data: the
    dataclass by its fields, in declaration order."""
    parsed, had_error, duplicated = result
    return {
        "file": {f.name: encode(getattr(parsed, f.name)) for f in dataclasses.fields(parsed)},
        "had_error": bool(had_error),
        "duplicated": encode(list(duplicated)),
    }


def decode_record(record: dict) -> tuple:
    """The triple :func:`encode_record` was given. A record missing a
    field, or carrying one ``CppFile`` has not, raises — and the caller
    drops it."""
    from hobbes.extract.cppsource import CppFile

    return (
        CppFile(**{name: decode(value) for name, value in record["file"].items()}),
        record["had_error"],
        decode(record["duplicated"]),
    )


def encode(value):
    """*value* as JSON-able data, with a tuple tagged :data:`TUPLE_TAG`
    and a set tagged :data:`SET_TAG` (sorted, so one set has one
    encoding). Anything else — an object, a dict keyed by something that
    is not a plain name — raises, and the record is not stored."""
    if value is None or isinstance(value, _LEAVES):
        return value
    if isinstance(value, tuple):
        return {TUPLE_TAG: [encode(item) for item in value]}
    if isinstance(value, (set, frozenset)):
        return {SET_TAG: [encode(item) for item in sorted(value)]}
    if isinstance(value, array):
        # ADR-131's operator tokens: the typecode rides with them, so the
        # array read back is the one that was packed.
        return {ARRAY_TAG: [value.typecode, list(value)]}
    if isinstance(value, list):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        for name in value:
            if not isinstance(name, str) or name in (TUPLE_TAG, SET_TAG, ARRAY_TAG):
                raise ValueError(f"lane A cache: unencodable field name {name!r}")
        return {name: encode(item) for name, item in value.items()}
    raise TypeError(f"lane A cache: unencodable value of type {type(value).__name__}")


def decode(value):
    """:func:`encode`'s inverse: the tags become a tuple, a set and an
    array again, everything else is itself."""
    if isinstance(value, list):
        return [decode(item) for item in value]
    if isinstance(value, dict):
        if len(value) == 1:
            if TUPLE_TAG in value:
                return tuple(decode(item) for item in value[TUPLE_TAG])
            if SET_TAG in value:
                return {decode(item) for item in value[SET_TAG]}
            if ARRAY_TAG in value:
                typecode, items = value[ARRAY_TAG]
                return array(typecode, items)
        return {name: decode(item) for name, item in value.items()}
    return value


# ---------------------------------------------------------------- the sweep


_swept: set[Path] = set()


def _sweep_once(root: Path) -> int:
    """Remove entries untouched for :data:`KEEP_DAYS`, and any
    ``.partial`` a killed run left; once per process per store."""
    if root in _swept:
        return 0
    _swept.add(root)
    return sweep(root)


def sweep(root: Path | None = None, now: float | None = None) -> int:
    """Sweep the store one level down — the records live in the two-hex
    subdirectories, not at the root — and return how many went."""
    root = root if root is not None else store_root()
    if not root.is_dir():
        return 0
    now = time.time() if now is None else now
    removed = 0
    try:
        children = sorted(root.iterdir())
    except OSError:
        return 0
    for child in children:
        if not child.is_dir():
            continue
        try:
            entries = sorted(child.iterdir())
        except OSError:
            continue
        for entry in entries:
            try:
                stale = entry.name.endswith(".partial") or (
                    entry.name.endswith(".json")
                    and now - entry.stat().st_mtime > KEEP_DAYS * 86400
                )
                if stale:
                    entry.unlink()
                    removed += 1
            except OSError:
                continue
    return removed


def _part(digest, label: str, data: bytes) -> None:
    digest.update(label.encode())
    digest.update(b"\0")
    digest.update(data)
    digest.update(b"\0")
