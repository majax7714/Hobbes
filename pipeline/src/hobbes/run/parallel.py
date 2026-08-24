"""Parallel implementers — a wave scheduler over the contract DAG (ADR-063).

The staged run spawned implementers one at a time, and the measurement
behind this module (2026-08-22) showed why that was the whole cost:
~85–90 % of every unit's wall was the model *decoding* at ~28 tok/s
for one request while the serving engine could have been batching ten.
Ten units at a ≥2-turn floor is a 5–8 minute stage even when nine say
"nothing named is mine".

Parallelism here keeps the one guarantee sequential order gave that
matters: **a consumer starts after its owner is integrated**, so it
sees the owner's commit. Units with no contract between them were
never promised each other's commits — contracts are the only interface
(architecture §6) — and now they may run at once. Integration stays
serial on the caller's thread; ADR-061's scoped cut makes concurrent
units unable to clobber each other even if they try.

Speed-up depends on the endpoint actually batching requests — vLLM
does; a single-stream local server or a per-request-serial proxy would
just queue them and the harness could not tell. :func:`endpoint_batches`
asks the endpoint what it is (``/models`` → ``owned_by``), and the
bench falls back to sequential when it is not vLLM or cannot be asked,
saying why (C-51).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

#: Workers when ``--parallel auto`` finds a batching endpoint. The 7B
#: rung serves from one A10G (24 GB): the KV budget for 32k-token
#: contexts bounds how many sequences really decode at once; past it
#: vLLM preempts and recomputes — slower, never wrong. Four is a stated
#: guess to be measured, not a tuned value.
DEFAULT_WORKERS = 4

#: ``owned_by`` values that name an engine known to batch concurrent
#: requests. Anything else (or no answer) falls back to sequential.
BATCHING_ENGINES = ("vllm",)


def unit_dependencies(spec: dict) -> dict[str, set[str]]:
    """``unit -> owners it consumes from`` — the edges :func:`order_units`
    sorts by, kept as a DAG so the scheduler can start every unit whose
    owners are integrated. A cycle (a mutual dependency the partition
    cut) is broken by the caller the way order_units breaks it: the
    first pending unit by order runs."""
    names = [u["name"] for u in spec.get("units", [])]
    after: dict[str, set[str]] = {n: set() for n in names}
    for c in spec.get("contracts", []):
        owner = c["owner"]
        other = c["from_unit"] if c["to_unit"] == owner else c["to_unit"]
        if other != owner and other in after and owner in after:
            after[other].add(owner)
    return after


def ready_units(pending: list[str], done: set[str], deps: dict[str, set[str]]) -> list[str]:
    """The pending units whose owners are all integrated, in plan
    order. Empty with a non-empty *pending* means a cycle: the caller
    forces ``pending[0]``, matching order_units."""
    return [u for u in pending if deps.get(u, set()) <= done]


def endpoint_batches(base_url: str, api_key: str | None = None, timeout: float = 120.0) -> tuple[bool, str]:
    """Does the OpenAI-compatible endpoint at *base_url* batch concurrent
    requests? Answered from ``GET /models`` → ``owned_by``; returns
    ``(yes, reason)``. A cold Modal container takes ~80 s to answer, so
    the timeout is generous; no answer is a *no* with the error named,
    never an assumption."""
    if not base_url:
        return False, "no endpoint: the runtime is not an OpenAI-compatible server"
    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"} if api_key else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            doc = json.load(resp)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return False, f"endpoint did not answer /models ({type(exc).__name__}: {str(exc)[:80]})"
    owners = sorted({str(m.get("owned_by", "")) for m in doc.get("data", []) if isinstance(m, dict)})
    for owner in owners:
        if owner.lower() in BATCHING_ENGINES:
            return True, f"endpoint reports owned_by={owner} (batches concurrent requests)"
    return False, f"endpoint reports owned_by={', '.join(owners) or 'unknown'} — not a known batching engine"


def endpoint_window(base_url: str, api_key: str | None = None, timeout: float = 120.0) -> tuple[int | None, str]:
    """The model's context window in tokens, from ``GET /models`` →
    ``max_model_len`` (vLLM reports it; a server that does not answers
    ``None`` with the reason, never a guess). ADR-069: the brief is
    sized to this."""
    if not base_url:
        return None, "no endpoint: the runtime is not an OpenAI-compatible server"
    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"} if api_key else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            doc = json.load(resp)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return None, f"endpoint did not answer /models ({type(exc).__name__}: {str(exc)[:80]})"
    for m in doc.get("data", []):
        if isinstance(m, dict) and isinstance(m.get("max_model_len"), int) and m["max_model_len"] > 0:
            return m["max_model_len"], f"endpoint reports max_model_len={m['max_model_len']} for {m.get('id', '?')}"
    return None, "endpoint reports no max_model_len — the window is not known"


def resolve_workers(setting: str | int | None, base_url: str, api_key: str | None = None) -> tuple[int, str]:
    """``--parallel`` → ``(workers, reason)``. ``auto`` asks the endpoint;
    an integer is the owner's call and is not second-guessed (1 or 0 =
    sequential)."""
    if setting is None or str(setting).lower() == "auto":
        ok, reason = endpoint_batches(base_url, api_key)
        return (DEFAULT_WORKERS if ok else 1), reason + (f"; {DEFAULT_WORKERS} workers" if ok else "; sequential")
    n = int(setting)
    if n <= 1:
        return 1, "sequential by --parallel"
    return n, f"{n} workers by --parallel (endpoint not asked)"
