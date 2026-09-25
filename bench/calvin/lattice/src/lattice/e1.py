"""**E1's run loop** (`calvin-experiments.md` §6, "E1's runner — the design", routes E1-d to E1-g).

`prompts` says what a model is given and `extract` reads what it gives back; this module is what runs
between them, and it is written so that **no model appears in it**. The generator and the grader are
injected callables, so this package's tests drive the whole loop with fakes and nothing is spent, and the
one real generator — `scripts/modal_e1.py`, which this module never imports — is reached through
:func:`modal_generator`.

**A run is a directory, and the directory is the state.** Five files, all append-only JSONL but the first:

| file | one row per |
|---|---|
| `meta.json` | the run: the model, the params, the arms, the cells, `k`, the rounds, the target's SHA, the ledger's provenance, and `p12` |
| `requests.jsonl` | request, round 0's from :func:`plan` and each later round's appended as it is made |
| `rows.jsonl` | request answered and graded |
| `gmem.jsonl` | G-mem probe scored |
| `calls.jsonl` | generator call: its round, its size, its tokens, its seconds and its cost |

**Resume is `rows.jsonl`.** A request whose id already has a row is never sent again, so a second
:func:`run` over a finished directory sends nothing and costs nothing. That is also why a row is written
only after its body has been graded: a row is the record of a finished request, not of a started one.

**The ceiling is checked before every call, never after** (§8: spend is held until Max names the run and
its ceiling). The estimate is deliberately crude and deliberately high — prompt characters over
:data:`CHARS_PER_TOKEN`, plus `max_tokens` for every request, at a per-model throughput and price that are
guesses written down as guesses (:data:`PRICING`). If the spend already in `calls.jsonl` plus that estimate
passes the ceiling, :class:`CeilingReached` is raised **before** the generator is called and nothing is
sent. A generator that reports no cost has its estimate recorded as the cost, with `cost_source` saying
so: a run whose generator is silent must not read as free.

**The iterate arm** (E1-e) applies to `C-0` and `C-3`. Every chain — one (cell, arm, sample) — whose last
row is not `pass` gets its conversation so far, plus the model's whole text as an assistant turn, plus one
user turn: the last result's `feedback` (≤1,500 characters, from the graded result's structured fields), or,
for a `no-body`, the one fixed sentence in :data:`NO_BODY`. A chain stops at its first `pass`, and at
`rounds`.

**P12.** This is `arm=model+prompt` (ADR-082): one single-use agent per cell, not a decomposed Hobbes test.
`meta.json` records it, so no report of this run can be read as a Hobbes-test result.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Iterable, Sequence

from . import extract, feedback, gmem, prompts
from . import run as sandbox
from .cells import Cell, Lattice
from .facts import Facts

__all__ = [
    "CALLS",
    "CHARS_PER_TOKEN",
    "COMPLETIONS",
    "GMEM",
    "GMEM_MAX_TOKENS",
    "ITERATE",
    "META",
    "NO_BODY",
    "PRICING",
    "REQUESTS",
    "ROUNDS",
    "ROWS",
    "CeilingReached",
    "GenerateFailed",
    "GradeFailed",
    "MissingCompletion",
    "TargetMoved",
    "default_grade",
    "estimate",
    "head",
    "meta",
    "modal_generator",
    "plan",
    "replay_generator",
    "request_id",
    "run",
    "seed",
    "spent",
    "write_plan",
]

#: The run directory's five files.
META, REQUESTS, ROWS, GMEM, CALLS = "meta.json", "requests.jsonl", "rows.jsonl", "gmem.jsonl", "calls.jsonl"

#: The sixth: every completion a generator returned, written **before** anything is graded. A completion
#: is what a run pays for, and grading runs in a container that can fail; a resume answers from this file
#: first and sends only what it does not hold, so a failed grade never buys the same round twice
#: (session `66c5`'s review).
COMPLETIONS = "completions.jsonl"

#: E1-d's sampling: greedy plus k samples at these settings, and 1,024 tokens to answer in.
K = 5
TEMPERATURE = 0.8
TOP_P = 0.95
MAX_TOKENS = 1024

#: E1-e: the arms that get feedback rounds, and how many.
ITERATE = ("C-0", "C-3")
ROUNDS = 3

#: G-mem is a raw continuation, not a chat, and it is short: the tail of one body (§5.5).
GMEM_MAX_TOKENS = 512

#: The one sentence a `no-body` chain is sent back with. It is fixed, so that "the model wrote nothing
#: usable" is the same input every time and never a paraphrase of the graders, who never saw a body.
NO_BODY = "Your reply had no C code block defining `{name}`."

#: What a chain is told when the graders failed it and said nothing about why. `feedback.build` writes its
#: own version of this; the fall-back is here for a grader injected by a caller that does not.
FAILED = "It failed, and the graders said nothing about why."

#: The P12 record (ADR-082): one agent per cell, so this run is a model+prompt arm and not a Hobbes test.
P12 = "arm=model+prompt"

#: Characters per token, for the ceiling's estimate only. Code tokenises nearer 3 than 4; 3.5 is the
#: middle, and the estimate is a guard rather than a measurement.
CHARS_PER_TOKEN = 3.5

#: **Estimates, not measurements** (E1-f). Both 7Bs run under batched vLLM on one A10G, whose price is
#: about $1.10/h; the throughputs are the order of magnitude a 7B reaches there, prefill being the faster
#: side. The first unit (E1-g) is priced against what Modal actually bills and these are replaced by it.
#: A model this table does not name falls back to :data:`DEFAULT_PRICE`, which is the same numbers.
PRICING = {
    "Qwen/Qwen2.5-Coder-7B-Instruct": {"prompt_tps": 5000.0, "completion_tps": 500.0, "usd_per_second": 1.10 / 3600},
    "allenai/Olmo-3-7B-Instruct": {"prompt_tps": 5000.0, "completion_tps": 500.0, "usd_per_second": 1.10 / 3600},
}
DEFAULT_PRICE = {"prompt_tps": 5000.0, "completion_tps": 500.0, "usd_per_second": 1.10 / 3600}


class CeilingReached(Exception):
    """The next generator call would carry the run past its ceiling, so nothing was sent.

    Its own type (P10, ADR-036): a general "the run failed" handler must not absorb a spend refusal, and
    the caller has to be able to tell "the model answered badly" from "the model was never asked".
    """


class MissingCompletion(Exception):
    """The generator answered a call without answering one of its requests, by id."""


class GradeFailed(Exception):
    """The image's `lattice grade` did not finish. A fact about the harness, never about a body."""


class GenerateFailed(Exception):
    """The generator did not finish. A fact about the harness or the provider, never about a body."""


class TargetMoved(Exception):
    """The target is not at the commit the run was planned against, so nothing was answered or graded.

    Its own type, and a refusal rather than a warning: the prompts in `requests.jsonl` are one tree's
    bytes, and grading a body written for them against another tree's would put two targets under one
    run's readings without either of them saying so.
    """


# MARK: - the plan -


def request_id(cell: str, arm: str, sample: int, round_: int) -> str:
    """`<cell>|<arm>|<sample>|<round>`. A cell id holds `/` and never `|`, so this parses back."""
    return f"{cell}|{arm}|{sample}|{round_}"


def seed(model: str, cell: str, arm: str, sample: int, round_: int) -> int:
    """A stable per-request seed: the same run planned twice asks for the same sample.

    `hashlib`, not Python's `hash()`, which is salted per process — a run whose seeds changed between two
    planning passes could not be resumed, and its samples could not be compared with anyone else's.
    """
    body = "|".join((model, cell, arm, str(sample), str(round_)))
    return int(hashlib.sha256(body.encode("utf-8")).hexdigest()[:8], 16)


def plan(
    lattice: Lattice,
    cells: Sequence[Cell | str],
    arms: Sequence[str],
    model: str,
    facts: Facts | None = None,
    k: int = K,
    temperature: float = TEMPERATURE,
    top_p: float = TOP_P,
    max_tokens: int = MAX_TOKENS,
) -> list[dict]:
    """Round 0's requests: one chat request per (cell, arm, sample), and one G-mem probe per cell.

    Sample 0 is greedy and samples 1 to *k* are drawn at *temperature* and *top_p*. A facts arm with no
    ledger raises `prompts.NoLedger` from `prompts.messages` rather than being filled empty.

    Each request carries the cell's grid position and kind, so the runner and the report can do their work
    from the rows alone and never re-read the target.
    """
    chosen = [cell if isinstance(cell, Cell) else lattice.get(cell) for cell in cells]
    made: list[dict] = []
    for cell in chosen:
        for arm in arms:
            messages = prompts.messages(lattice, cell, arm, facts)
            for sample in range(0, k + 1):
                greedy = sample == 0
                made.append(
                    {
                        **_position(cell),
                        "id": request_id(cell.id, arm, sample, 0),
                        "arm": arm,
                        "sample": sample,
                        "round": 0,
                        "mode": "chat",
                        "messages": messages,
                        "params": {
                            # at temperature 0 the sampler is an argmax and top_p does not apply; 1.0 says
                            # so rather than carrying a number that does nothing
                            "temperature": 0.0 if greedy else temperature,
                            "top_p": 1.0 if greedy else top_p,
                            "max_tokens": max_tokens,
                            "seed": seed(model, cell.id, arm, sample, 0),
                        },
                    }
                )
    for cell in chosen:
        probe = gmem.probe(lattice, cell)
        made.append(
            {
                **_position(cell),
                "id": f"{cell.id}|gmem",
                "arm": None,
                "sample": 0,
                "round": 0,
                "mode": "complete",
                "prompt": probe["prompt"],
                "expected": probe["expected"],
                "k": probe["k"],
                "evidence": probe["expected_tokens"] > 0,
                "params": {
                    "temperature": 0.0,
                    "top_p": 1.0,
                    "max_tokens": GMEM_MAX_TOKENS,
                    "seed": seed(model, cell.id, "gmem", 0, 0),
                },
            }
        )
    return made


def _position(cell: Cell) -> dict:
    """The grid facts a row needs so that the report never reopens the target."""
    return {
        "cell": cell.id,
        "name": cell.name,
        "kind": cell.kind,
        "isa": cell.isa,
        "type": cell.type,
        "metric": cell.metric,
    }


def meta(
    model: str,
    *,
    arms: Sequence[str],
    cells: Sequence[Cell | str],
    k: int = K,
    rounds: int = ROUNDS,
    iterate: Sequence[str] = ITERATE,
    temperature: float = TEMPERATURE,
    top_p: float = TOP_P,
    max_tokens: int = MAX_TOKENS,
    target: Path | str | None = None,
    facts: Facts | None = None,
) -> dict:
    """The run's `meta.json`: what was asked for, at which SHA, from which ledger, under which P12 arm.

    The target is named by its commit and **never by its path** — a path is a fact about this box, and the
    same run planned on another box has to read as the same run.
    """
    return {
        "model": model,
        "params": {"temperature": temperature, "top_p": top_p, "max_tokens": max_tokens},
        "arms": list(arms),
        "cells": [cell.id if isinstance(cell, Cell) else str(cell) for cell in cells],
        "k": k,
        "rounds": rounds,
        "iterate": list(iterate),
        "target_sha": None if target is None else head(target),
        "ledger": None if facts is None else facts.source(),
        "p12": P12,
    }


def head(target: Path | str) -> str | None:
    """The target's `git rev-parse HEAD`, or `None` where it is not a checkout with a commit."""
    try:
        done = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() or None if done.returncode == 0 else None


def write_plan(run_dir: Path | str, requests: list[dict], record: dict) -> Path:
    """Write `meta.json` and `requests.jsonl` into a fresh run directory, and return it."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / META).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    (run_dir / REQUESTS).write_text(
        "".join(f"{json.dumps(request, sort_keys=True)}\n" for request in requests), encoding="utf-8"
    )
    return run_dir


# MARK: - the ceiling -


def prompt_chars(request: dict) -> int:
    """The characters this request sends, whichever mode it is in."""
    if request.get("mode") == "chat":
        return sum(len(turn["content"]) for turn in request["messages"])
    return len(request.get("prompt", ""))


def estimate(model: str, requests: Sequence[dict]) -> dict:
    """What one call would cost, at :data:`PRICING`'s guesses: tokens, seconds and dollars.

    Every request is assumed to answer to its full `max_tokens`, which it will not, so the figure runs
    high. A ceiling wants the high side.
    """
    price = PRICING.get(model, DEFAULT_PRICE)
    tokens_in = sum(prompt_chars(request) for request in requests) / CHARS_PER_TOKEN
    tokens_out = sum(request["params"]["max_tokens"] for request in requests)
    seconds = tokens_in / price["prompt_tps"] + tokens_out / price["completion_tps"]
    return {
        "tokens_in": int(tokens_in),
        "tokens_out": int(tokens_out),
        "seconds": round(seconds, 3),
        "usd": round(seconds * price["usd_per_second"], 6),
    }


def spent(run_dir: Path | str) -> float:
    """The dollars `calls.jsonl` already records for this run."""
    return round(sum(float(call.get("cost") or 0.0) for call in _read(Path(run_dir) / CALLS)), 6)


# MARK: - the loop -


def run(
    run_dir: Path | str,
    target: Path | str,
    generate: Callable[[list[dict]], object],
    grade: Callable[[list[dict]], list[dict]],
    *,
    ceiling_usd: float,
    rounds: int = ROUNDS,
    iterate: Sequence[str] = ITERATE,
) -> dict:
    """Answer and grade every request in *run_dir*, round by round, and return what the run now holds.

    *generate* takes the round's requests and answers them in one call; *grade* takes that round's
    extracted bodies (`{"id", "cell", "body"}`) and grades them in one call. *target* is checked against
    the commit the plan was written at and otherwise belongs to the grader: the prompts were built from one
    tree's bytes, and answering them against another tree is :class:`TargetMoved`, not a resume.
    """
    run_dir = Path(run_dir)
    record = json.loads((run_dir / META).read_text(encoding="utf-8"))
    model = record["model"]
    _same_target(record, target)
    requests = _read(run_dir / REQUESTS)
    known = {request["id"] for request in requests}
    rows = {row["id"]: row for row in _read(run_dir / ROWS)}
    probed = {row["id"] for row in _read(run_dir / GMEM)}

    pending = [r for r in requests if r["id"] not in rows and r["id"] not in probed]
    if pending:
        _call(run_dir, model, pending, generate, grade, ceiling_usd, 0, rows)

    for round_ in range(1, rounds + 1):
        made = _next_round(requests, rows, round_, iterate, model)
        fresh = [request for request in made if request["id"] not in known]
        if fresh:
            _append(run_dir / REQUESTS, fresh)
            requests += fresh
            known |= {request["id"] for request in fresh}
        pending = [request for request in made if request["id"] not in rows]
        if not pending:
            continue
        _call(run_dir, model, pending, generate, grade, ceiling_usd, round_, rows)

    return {
        "rows": len(rows),
        "gmem": len(_read(run_dir / GMEM)),
        "calls": len(_read(run_dir / CALLS)),
        "spent_usd": spent(run_dir),
    }


def _same_target(record: dict, target: Path | str) -> None:
    """Refuse a run whose target has moved since its plan. A plan with no SHA has nothing to check."""
    planned = record.get("target_sha")
    if planned is None:
        return
    now = head(target)
    if now is not None and now != planned:
        raise TargetMoved(
            f"the run was planned at {planned[:12]} and the target is at {now[:12]}; "
            "its prompts are the other tree's bytes, so nothing was sent"
        )


def _call(
    run_dir: Path,
    model: str,
    pending: list[dict],
    generate: Callable[[list[dict]], object],
    grade: Callable[[list[dict]], list[dict]],
    ceiling_usd: float,
    round_: int,
    rows: dict[str, dict],
) -> None:
    """One round: check the ceiling, generate once, extract, grade once, and write what came back.

    A request already answered in :data:`COMPLETIONS` (a paid call whose grading failed) is answered from
    there and is neither sent nor priced again.
    """
    held = {row["id"]: row for row in _read(run_dir / COMPLETIONS)}
    to_send = [request for request in pending if request["id"] not in held]
    completions = {request["id"]: held[request["id"]] for request in pending if request["id"] in held}
    if to_send:
        guess = estimate(model, to_send)
        already = spent(run_dir)
        if already + guess["usd"] > ceiling_usd:
            raise CeilingReached(
                f"round {round_}: ${already:.4f} already spent plus an estimated ${guess['usd']:.4f} for "
                f"{len(to_send)} request(s) passes the ${ceiling_usd:.4f} ceiling; nothing was sent"
            )

        started = time.time()
        answer = generate(to_send)
        wall = round(time.time() - started, 3)
        answered = _completions(answer)
        reported = answer if isinstance(answer, dict) else {}
        # the paid part is on disk before anything else can fail: the completions, then the call's cost
        _append(run_dir / COMPLETIONS, [answered[request["id"]] for request in to_send if request["id"] in answered])
        _append(run_dir / CALLS, [_call_row(round_, to_send, answered, reported, guess, wall)])
        completions.update(answered)

    new_rows: list[dict] = []
    probes: list[dict] = []
    entries: list[dict] = []
    for request in pending:
        got = completions.get(request["id"])
        if got is None:
            raise MissingCompletion(f"the generator returned no completion for {request['id']!r}")
        if request["mode"] == "complete":
            probes.append(_probe_row(request, got))
            continue
        row = _row(request, got)
        new_rows.append(row)
        if row["extract"]["body"] is not None:
            entries.append({"id": row["id"], "cell": row["cell"], "body": row["extract"]["body"]})

    results = {result.get("id"): result for result in (grade(entries) if entries else [])}
    for row in new_rows:
        if row["extract"]["body"] is None:
            continue
        result = results.get(row["id"])
        if result is None:
            # a body the grader did not answer has no class, and a chain with no class would be retried
            # as a failure; nothing of this round is written, and a resume grades it again for nothing
            raise GradeFailed(f"the grader returned no result for {row['id']!r}")
        _merge(row, result)

    for row in new_rows:
        rows[row["id"]] = row
    if new_rows:
        _append(run_dir / ROWS, new_rows)
    if probes:
        _append(run_dir / GMEM, probes)


def _row(request: dict, got: dict) -> dict:
    """One answered chat request, before grading: the whole text, and what `extract` made of it."""
    text = got.get("text") or ""
    parsed = extract.extract(text, request["name"])
    return {
        "id": request["id"],
        "cell": request["cell"],
        "name": request["name"],
        "kind": request["kind"],
        "isa": request["isa"],
        "type": request["type"],
        "metric": request["metric"],
        "arm": request["arm"],
        "sample": request["sample"],
        "round": request["round"],
        # `no-body` is a class of its own beside `compile`, never folded into it (E1-c)
        "class": "no-body" if parsed["body"] is None else None,
        "reason": parsed["reason"],
        "text": text,
        "extract": parsed,
        "grade": None,
        "reg": None,
        "invented": [],
        "feedback": "",
        "tokens_in": got.get("tokens_in"),
        "tokens_out": got.get("tokens_out"),
        "finish_reason": got.get("finish_reason"),
    }


def _merge(row: dict, result: dict) -> None:
    """Put a graded result on its row, with the diagnostics cut to what a result carries."""
    kept = dict(result)
    kept["diagnostics"] = list(result.get("diagnostics") or [])[: _DIAGNOSTICS]
    row["grade"] = kept
    row["class"] = kept.get("class")
    row["reason"] = kept.get("reason")
    row["reg"] = kept.get("reg")
    row["invented"] = list(kept.get("invented") or [])
    row["feedback"] = kept.get("feedback") or feedback.build(kept)


#: What a graded result keeps (`grade.DIAGNOSTIC_LIMIT`). Repeated rather than imported, because `grade`
#: pulls in the compiler and the differential and this module must import in a session that has neither.
_DIAGNOSTICS = 20


def _probe_row(request: dict, got: dict) -> dict:
    """One scored G-mem probe. The expectation rode in the request, so nothing is re-read here."""
    completion = got.get("text") or ""
    value = gmem.score(request["expected"], completion)
    return {
        "id": request["id"],
        "cell": request["cell"],
        "k": request.get("k"),
        "score": value,
        "label": gmem.label(value),
        "completion": completion,
        "evidence": bool(request.get("evidence")),
        "tokens_in": got.get("tokens_in"),
        "tokens_out": got.get("tokens_out"),
        "finish_reason": got.get("finish_reason"),
    }


def _next_round(requests: list[dict], rows: dict[str, dict], round_: int, iterate: Sequence[str], model: str) -> list[dict]:
    """The iterate arms' requests for *round_*: the conversation so far, the model's text, the feedback.

    A chain is one (cell, arm, sample). It is carried forward only from the round before, and only when
    that round's row is not a `pass` — which is what makes a chain stop at its first pass.
    """
    made: list[dict] = []
    for request in requests:
        if request["round"] != round_ - 1 or request["mode"] != "chat" or request["arm"] not in iterate:
            continue
        row = rows.get(request["id"])
        if row is None or row.get("class") == "pass":
            continue
        messages = list(request["messages"]) + [
            {"role": "assistant", "content": row["text"]},
            {"role": "user", "content": _retry(request, row)},
        ]
        made.append(
            {
                **request,
                "id": request_id(request["cell"], request["arm"], request["sample"], round_),
                "round": round_,
                "messages": messages,
                "params": {
                    **request["params"],
                    "seed": seed(model, request["cell"], request["arm"], request["sample"], round_),
                },
            }
        )
    return made


def _retry(request: dict, row: dict) -> str:
    """What the chain is sent back with: the fixed sentence for a `no-body`, else the graders' feedback."""
    if row.get("class") == "no-body":
        return NO_BODY.format(name=request["name"])
    return row.get("feedback") or FAILED


def _call_row(round_: int, pending: list[dict], completions: dict[str, dict], reported: dict, guess: dict, wall: float) -> dict:
    """The call's record. A generator that reports no cost has its estimate recorded, and `cost_source`
    says which of the two the number is: a silent generator must not make a run read as free."""
    tokens_in = sum(int(c.get("tokens_in") or 0) for c in completions.values())
    tokens_out = sum(int(c.get("tokens_out") or 0) for c in completions.values())
    cost = reported.get("cost")
    return {
        "round": round_,
        "requests": len(pending),
        "tokens_in": tokens_in or reported.get("tokens_in") or guess["tokens_in"],
        "tokens_out": tokens_out or reported.get("tokens_out") or guess["tokens_out"],
        "seconds": reported.get("seconds", wall),
        "cost": guess["usd"] if cost is None else float(cost),
        "cost_source": "estimated" if cost is None else "reported",
        "estimate": guess,
    }


def _completions(answer: object) -> dict[str, dict]:
    """A generator's answer as `{id: completion}`.

    Two shapes are taken: the list of completions, and a mapping carrying them under `completions` with
    the call's own `cost`, `seconds` and token totals beside them. The second is what a generator that
    knows what it spent returns, and `modal_e1.py` is one.
    """
    rows = answer.get("completions", []) if isinstance(answer, dict) else answer
    return {row["id"]: row for row in rows or []}


# MARK: - the graders and the generators a caller can inject -


def default_grade(target: Path | str, image: str = sandbox.IMAGE) -> Callable[[list[dict]], list[dict]]:
    """The grader the runner uses: one round's bodies through `lattice grade` **in the image**.

    Grading compiles and runs the target's code, so it never happens on the host (ADR-092, C-64). This is
    `cli._grade`'s own plan, once per round rather than once per body.
    """

    def grade(entries: list[dict]) -> list[dict]:
        if not entries:
            return []
        workdir = Path(tempfile.mkdtemp(prefix="lattice-e1-"))
        try:
            (workdir / "manifest.json").write_text(json.dumps(entries), encoding="utf-8")
            plan_argv = sandbox.image_plan(
                image,
                target,
                workdir,
                ["grade", "/target", "/work/manifest.json", "--out", "/work/results.jsonl", "--work", "/work/run"],
            )
            done = sandbox.run_plan(plan_argv)
            if done.returncode != 0:
                raise GradeFailed(f"`lattice grade` in {image} exited {done.returncode}: {done.stderr[-2000:]}")
            return _read(workdir / "results.jsonl")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    return grade


def replay_generator(path: Path | str) -> Callable[[list[dict]], dict]:
    """A generator that answers from a completions JSONL: a rerun with no model, and this package's tests.

    A request the file does not answer is :class:`MissingCompletion`, not a silent gap — replaying half a
    run and reporting it as a run is the one thing this must not do.
    """
    recorded = {row["id"]: row for row in _read(path)}

    def generate(requests: list[dict]) -> dict:
        answers = []
        for request in requests:
            got = recorded.get(request["id"])
            if got is None:
                raise MissingCompletion(f"{Path(path).name} has no completion for {request['id']!r}")
            answers.append(got)
        # a replay spends nothing, and says so rather than leaving the cost to be estimated
        return {"completions": answers, "cost": 0.0, "seconds": 0.0}

    return generate


def modal_generator(model: str, script: Path | str) -> Callable[[list[dict]], dict]:
    """The host side of E1-f: shell out to `scripts/modal_e1.py` and read the batch back.

    This package never imports `modal` — the script is a `uv run` script with its own dependencies, and a
    dispatched session has neither `modal` nor a route to it. The seam is a subprocess and a pair of JSONL
    files, which is also what makes a call replayable afterwards with :func:`replay_generator`.
    """
    script = Path(script)

    def generate(requests: list[dict]) -> dict:
        workdir = Path(tempfile.mkdtemp(prefix="lattice-modal-"))
        try:
            requests_file, out_file = workdir / "requests.jsonl", workdir / "completions.jsonl"
            call_file = workdir / "call.json"
            _append(requests_file, requests)
            done = subprocess.run(
                [
                    "uv", "run", str(script),
                    "--model", model,
                    "--requests", str(requests_file),
                    "--out", str(out_file),
                    "--call", str(call_file),
                ],
                capture_output=True,
                text=True,
            )
            if done.returncode != 0:
                raise GenerateFailed(f"{script.name} exited {done.returncode}: {done.stderr[-2000:]}")
            call = json.loads(call_file.read_text(encoding="utf-8")) if call_file.exists() else {}
            return {"completions": _read(out_file), **call}
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    return generate


# MARK: - JSONL -


def _read(path: Path | str) -> list[dict]:
    """Every row of a JSONL file, or none at all when it is not there yet."""
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append(path: Path | str, rows: Iterable[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(f"{json.dumps(row, sort_keys=True)}\n")
