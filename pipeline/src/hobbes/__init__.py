"""Hobbes: the Python side of the agentic development environment.

This package holds the ingestion pipeline (deterministic extractors, from
M1), the invariant compiler (M8), and the ``hobbes`` CLI that fronts them.
Policy semantics deliberately do NOT live here: the Go engine
(``go/internal/policy``) is the single implementation, and :mod:`hobbes.policy`
shells out to its ``hobbes-policy`` binary (ADR-003).
"""

# The one version of the Hobbes layer (ADR-103): equal to the root
# VERSION file, the Go `version.Version`, and the three package.json
# versions — `tests/test_version.py` holds them together. Stamped into
# every artifact's `built_by` and printed on every knowledge answer.
__version__ = "0.1.19-beta"
