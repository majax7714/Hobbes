"""Gated reads of the derived artifacts (ADR-028).

ADR-006 has always said consumers reject schema versions they don't know.
Until v4 none did: `graph.json` was read at five call sites in the CLI with
a bare ``json.loads(path.read_text())``, so a newer artifact would have been
*half-read* rather than refused — an invariant verdict computed over edges
whose tier it could not see, or a Mermaid render missing a whole layer.
A plausible wrong answer is the failure mode this system exists to avoid,
so every read goes through here and every caller says what it needs.

Callers that only use fields present since v3 accept :data:`V3_COMPATIBLE`;
callers that read ``tier`` or evidence ``lane`` require :data:`V4_ONLY`.
"""

from __future__ import annotations

import json
from pathlib import Path

from hobbes.extract import SCHEMA_VERSION

#: Artifacts live here, relative to the repo root (ADR-006).
DERIVED = ".hobbes/derived"

#: Readers needing only the v3 field set. v4 is additive (ADR-028), so
#: they read either version correctly.
V3_COMPATIBLE = (3, 4)

#: Readers that need v4's edge ``tier`` or evidence ``lane``.
V4_ONLY = (4,)

#: What produces each artifact, quoted back when one is missing or stale —
#: an error that names its own fix (the ADR-022 hint convention).
_PRODUCER = {
    "graph.json": "hobbes ingest",
    "tests.json": "hobbes ingest",
    "interfaces.json": "hobbes ingest",
}


class ArtifactError(RuntimeError):
    """An artifact is missing, unreadable, or a version we don't accept."""


def artifact_path(repo_root: Path, name: str) -> Path:
    return Path(repo_root) / DERIVED / name


def load(
    repo_root: Path, name: str, accepts: tuple[int, ...] = V3_COMPATIBLE
) -> dict:
    """Read and version-check ``.hobbes/derived/<name>``.

    Raises :class:`ArtifactError` when the file is absent, is not JSON, or
    carries a ``schema_version`` outside *accepts* — never a partial read.
    """
    path = artifact_path(repo_root, name)
    produce = _PRODUCER.get(name, "hobbes ingest")
    if not path.is_file():
        raise ArtifactError(f"no {name} in {DERIVED}/ — run `{produce}` first")
    try:
        document = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"{name} is unreadable: {exc}") from exc
    check_version(document, name, accepts, produce)
    return document


def check_version(
    document: dict,
    name: str,
    accepts: tuple[int, ...] = V3_COMPATIBLE,
    produce: str = "hobbes ingest",
) -> None:
    """Raise unless *document*'s schema version is one we accept.

    Split out from :func:`load` because ``hobbes diff`` builds graphs in
    memory from ``git archive`` (ADR-009) rather than reading them off
    disk, and those need the same check.
    """
    found = document.get("schema_version")
    if found in accepts:
        return
    wanted = ", ".join(str(v) for v in accepts)
    if found is None:
        raise ArtifactError(
            f"{name} carries no schema_version (accepts {wanted}); it predates "
            f"the version gate — re-run `{produce}`"
        )
    if found > SCHEMA_VERSION:
        raise ArtifactError(
            f"{name} is schema v{found}, newer than this Hobbes understands "
            f"(accepts {wanted}) — upgrade Hobbes rather than downgrading it"
        )
    raise ArtifactError(
        f"{name} is schema v{found}, but this reader accepts {wanted} — "
        f"re-run `{produce}` to regenerate it"
    )


def load_graph(repo_root: Path, accepts: tuple[int, ...] = V3_COMPATIBLE) -> dict:
    """``graph.json``, version-checked."""
    return load(repo_root, "graph.json", accepts)


def load_tests(repo_root: Path, accepts: tuple[int, ...] = V3_COMPATIBLE) -> dict:
    """``tests.json``, version-checked."""
    return load(repo_root, "tests.json", accepts)


def graph_if_ingested(repo_root: Path) -> dict | None:
    """``graph.json`` or None when the repo has never been ingested.

    "Not ingested yet" is a state the caller reports, not an error; a
    *wrong version* stays an error, because that one is a real mismatch
    rather than an absence.
    """
    if not artifact_path(repo_root, "graph.json").is_file():
        return None
    return load_graph(repo_root)
