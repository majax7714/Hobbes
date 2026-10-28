"""Every wall-clock cap the ingest puts on a step, in one table (ADR-183).

A cap that fires makes the graph depend on the box it ran on, so each one
is registered (C-196) and says the same four things where it bites: what
ran out of time, the cap in seconds, the register entry, and the knob.
``HOBBES_TIMEOUT_SCALE`` multiplies every cap; nothing about it is
stamped, because it moves the graph only where a cap fires, and a cap that
fires is recorded.
"""

from __future__ import annotations

import os

SCALE_ENV = "HOBBES_TIMEOUT_SCALE"

#: Seconds at scale 1, by the step each cap bounds.
CAPS: dict[str, int] = {
    # Lane A's TS/JS helper, the whole run: a backstop for a hung helper,
    # since each zone has its own cap below (ADR-184 lever 2).
    "tsextract": 3600,
    # One tsconfig zone of lane A's TS/JS helper, on its worker thread: a
    # zone past it is stopped and recorded, and the others stand.
    "tsextract-zone": 300,
    # The helper's tsconfig zone map, read for lane B (scipsource).
    "tsextract-zones": 300,
    # One lane B unit's container (containment.run via scipsource).
    "lane-b-unit": 900,
    # A Java unit's container, resolve and index alike: the build runs.
    "lane-b-java": 1800,
    # A registry fetch's container (scipsource._fetch).
    "registry-fetch": 600,
    # The venv's own interpreter listing its distributions.
    "python-env": 60,
    # scip-clang's wait for one translation unit's worker (its own
    # ``--receive-timeout-seconds``, whose default this is).
    "clang-unit": 300,
}

#: The helper's step cap sits this far under its unit's, so the helper's
#: named error fires before podman stops the container.
STEP_MARGIN = 30


def scale() -> float:
    """``HOBBES_TIMEOUT_SCALE`` as a positive number; 1 when unset.

    A value that is not a positive number is refused, not ignored: a cap
    the user thinks they raised and did not would fire unexplained."""
    raw = os.environ.get(SCALE_ENV, "").strip()
    if not raw:
        return 1.0
    try:
        value = float(raw)
    except ValueError:
        value = 0.0
    if not value > 0 or value != value or value == float("inf"):
        raise ValueError(f"{SCALE_ENV}={raw!r} is not a positive number (ADR-183)")
    return value


def seconds(name: str) -> int:
    """The cap on *name*, in whole seconds, at the current scale."""
    return max(1, round(CAPS[name] * scale()))


def step_seconds(unit_seconds: int) -> int:
    """The helper's per-step cap inside a unit whose container has
    *unit_seconds*."""
    return max(1, unit_seconds - STEP_MARGIN)


def timed_out(what: str, cap: int) -> str:
    """The words every timeout says (ADR-183 decision 2)."""
    return (
        f"{what} did not finish within its {cap} s cap (C-196; "
        f"{SCALE_ENV} raises every cap)"
    )
