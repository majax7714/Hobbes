"""Dual-arm accounting: tokens, cost, wall time, turns (ADR-055).

H3 is decided per *solved* instance, so the same meter has to read
both arms. The source is Claude Code's ``--output-format json`` result
envelope — ``usage`` (input, output, cache creation, cache read),
``total_cost_usd``, ``duration_ms``, ``num_turns`` — which the pure
arm captures directly from the ``claude -p`` subprocess. The harness
arm's sessions run inside the sandbox; their stdout is kept per unit
in ``session.log`` (ADR-054), and an envelope found there is read the
same way. A session that emitted none is recorded **unobserved** —
the ADR-054 rule: a number the recorder did not see is never filled
in, and the H3 row says which terms are missing rather than showing a
zero that reads as cheap.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass


@dataclass
class Usage:
    """One arm's meter for one instance. ``None`` = unobserved."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_creation_tokens: int | None = None
    cache_read_tokens: int | None = None
    cost_usd: float | None = None
    wall_seconds: float | None = None
    turns: int | None = None
    envelopes: int = 0

    @property
    def total_tokens(self) -> int | None:
        if self.input_tokens is None and self.output_tokens is None:
            return None
        return (self.input_tokens or 0) + (self.output_tokens or 0) \
            + (self.cache_creation_tokens or 0) + (self.cache_read_tokens or 0)

    @property
    def unobserved(self) -> list[str]:
        return [name for name, value in (
            ("tokens", self.total_tokens), ("cost", self.cost_usd),
            ("wall_time", self.wall_seconds),
        ) if value is None]

    def add(self, other: "Usage") -> "Usage":
        """Sum two meters; a term unobserved on either side stays
        unobserved on the sum — a partial total would read as a total."""
        def both(a, b):
            return None if a is None or b is None else a + b
        if other.envelopes == 0:
            return Usage(**{**asdict(self)})
        if self.envelopes == 0:
            return Usage(**{**asdict(other)})
        return Usage(
            input_tokens=both(self.input_tokens, other.input_tokens),
            output_tokens=both(self.output_tokens, other.output_tokens),
            cache_creation_tokens=both(self.cache_creation_tokens, other.cache_creation_tokens),
            cache_read_tokens=both(self.cache_read_tokens, other.cache_read_tokens),
            cost_usd=both(self.cost_usd, other.cost_usd),
            wall_seconds=both(self.wall_seconds, other.wall_seconds),
            turns=both(self.turns, other.turns),
            envelopes=self.envelopes + other.envelopes,
        )

    def to_dict(self) -> dict:
        return {**asdict(self), "total_tokens": self.total_tokens, "unobserved": self.unobserved}


def from_envelope(envelope: dict) -> Usage:
    """A :class:`Usage` from one Claude Code result envelope. Fields the
    envelope lacks stay ``None``."""
    usage = envelope.get("usage") or {}
    def _int(v):
        return int(v) if isinstance(v, (int, float)) else None
    def _cache(key):
        # Cache counters are optional in the envelope; absent beside a
        # reported input count they mean none, not unobserved.
        return _int(usage.get(key)) if key in usage else (0 if usage else None)
    duration = envelope.get("duration_ms")
    return Usage(
        input_tokens=_int(usage.get("input_tokens")),
        output_tokens=_int(usage.get("output_tokens")),
        cache_creation_tokens=_cache("cache_creation_input_tokens"),
        cache_read_tokens=_cache("cache_read_input_tokens"),
        cost_usd=float(envelope["total_cost_usd"]) if isinstance(envelope.get("total_cost_usd"), (int, float)) else None,
        wall_seconds=duration / 1000.0 if isinstance(duration, (int, float)) else None,
        turns=_int(envelope.get("num_turns")),
        envelopes=1,
    )


def find_envelope(text: str) -> dict | None:
    """The last JSON result envelope in *text* (a ``claude -p`` stdout or
    a session log that may carry other lines around it), or ``None``."""
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            doc = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(doc, dict) and doc.get("type") == "result":
            return doc
    # A pretty-printed envelope spans lines; try the whole text last.
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return None
    return doc if isinstance(doc, dict) and doc.get("type") == "result" else None


def from_text(text: str) -> Usage:
    """The meter read from a stdout/log text; unobserved when it carries
    no envelope."""
    envelope = find_envelope(text)
    return from_envelope(envelope) if envelope else Usage()
