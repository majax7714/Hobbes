"""The Node helpers and their Python joins must agree on a facts version.

Both lane helpers (`tsextract/extract.mjs`, ADR-021, and `scip/index.mjs`,
ADR-027 Decision 5) stamp a ``helper_version`` into their output, and the
Python join refuses anything else. That is the right contract and it has a
blind spot: the constant is declared **twice, in two languages**, and the
pytest suite is hermetic — it feeds canned facts built from the *Python*
constant, so a bump on one side alone leaves every test green and breaks
only when someone ingests a real repo.

These tests read the version out of the JavaScript source and compare. No
subprocess, no Node required, so they run everywhere the suite does. The
precedent is ADR-027's test that the bundled `scip.js` import path still
resolves: a cross-language assumption gets an assertion, not a comment.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hobbes.extract import scipsource, tssource

_REPO = Path(__file__).resolve().parents[2]


def _declared_version(helper: Path) -> int:
    """The ``HELPER_VERSION = N`` a Node helper exports."""
    source = helper.read_text()
    match = re.search(r"HELPER_VERSION\s*=\s*(\d+)", source)
    assert match, f"no HELPER_VERSION declared in {helper}"
    return int(match.group(1))


@pytest.mark.parametrize(
    ("helper_path", "python_constant", "adr"),
    [
        ("tsextract/extract.mjs", tssource.HELPER_VERSION, "ADR-021"),
        ("scip/index.mjs", scipsource.HELPER_VERSION, "ADR-027"),
    ],
)
def test_facts_version_agrees_across_the_process_boundary(
    helper_path, python_constant, adr
):
    helper = _REPO / helper_path
    if not helper.is_file():  # pragma: no cover - only if the tree is partial
        pytest.skip(f"{helper_path} not present")
    assert _declared_version(helper) == python_constant, (
        f"{helper_path} and its Python join disagree on the facts version "
        f"({adr}). Bump both in the same commit, or ingest fails on a real "
        "repo while the whole suite stays green."
    )
