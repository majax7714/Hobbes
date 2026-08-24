"""Hobbes: the Python side of the agentic development environment.

This package holds the ingestion pipeline (deterministic extractors, from
M1), the invariant compiler (M8), and the ``hobbes`` CLI that fronts them.
Policy semantics deliberately do NOT live here: the Go engine
(``go/internal/policy``) is the single implementation, and :mod:`hobbes.policy`
shells out to its ``hobbes-policy`` binary (ADR-003).
"""

__version__ = "0.0.1"
