"""One ingest of a repo at a time (ADR-127).

Two ingests of one repo at one commit stage every lane B unit at the same
derived path and each deletes the tree the other is using, so units fail
with "wrote no facts file" and the graph is written anyway. An ingest
therefore holds an exclusive ``flock`` on ``.hobbes/derived/.ingest.lock``
under the *resolved* repo root — the same file for every path that resolves
there, and independent of ``HOBBES_CACHE_DIR`` or ``$HOME``, which two
processes may set differently. A second ingest is refused
(:class:`IngestBusy`), never queued: a wait would hang a CI job or a
dispatch's pre-ingest behind a run nobody knows about.

The kernel drops the lock when the holder exits, however it exits, so
there is no stale lock to clear. Where the filesystem cannot take the lock
at all the run proceeds unlocked with a warning — the residual is C-159.
"""

from __future__ import annotations

import errno
import fcntl
import os
import sys
from contextlib import contextmanager
from pathlib import Path

from hobbes.extract import emit

#: The lock file's name inside ``.hobbes/derived/``. Gitignored in both
#: postures (ADR-012), so it is never committed.
LOCK_NAME = ".ingest.lock"


class IngestBusy(RuntimeError):
    """Another ingest of this repo holds the lock (ADR-127).

    Its own type, not a generic error (P10): the caller refuses this one
    ingest rather than treating it as a failed extraction.
    """


@contextmanager
def hold(repo_root: Path):
    """Hold the exclusive ingest lock on *repo_root* for the block.

    Raises :class:`IngestBusy` when another process (or another open file
    description in this one) already holds it. Yields without the lock,
    after a warning naming C-159, when the filesystem refuses ``flock``
    for any other reason.
    """
    root = Path(repo_root).resolve()
    derived = root / emit.DERIVED_DIR
    derived.mkdir(parents=True, exist_ok=True)
    path = derived / LOCK_NAME
    # "a+": never truncate before the lock is held — the pid in the file
    # belongs to whoever holds it.
    handle = open(path, "a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        pid = _holder_pid(handle)
        handle.close()
        raise IngestBusy(
            f"another hobbes ingest of {root} is running (pid {pid}); wait for "
            "it to finish — two ingests of one repo break each other's lane B "
            "stages (ADR-127)"
        ) from None
    except OSError as exc:
        # A filesystem without flock support is not a reason to refuse
        # every ingest (ADR-127 §3); the residual is registered.
        print(
            f"hobbes ingest: WARNING: could not lock {path} ({exc}); running "
            "unlocked — a concurrent ingest of this repo would not be refused "
            "(C-159)",
            file=sys.stderr,
        )
        try:
            yield
        finally:
            handle.close()
        return
    try:
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            # The file stays: deleting it races a third process that has
            # already opened it and would then lock a path nobody sees.
            handle.close()


def _holder_pid(handle) -> str:
    """The pid the holder wrote into the lock file, or ``"unknown"``."""
    try:
        handle.seek(0)
        text = handle.read().strip()
    except OSError:
        return "unknown"
    return text.split()[0] if text.split() else "unknown"
