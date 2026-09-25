"""G-diff: the numeric differential against `distance-cpu.c`, through the dispatch table.

**Through the table, never by name.** `init_distance_functions(true)` installs the scalar kernels into
`dispatch_distance_table`; the driver snapshots that as the reference, calls
`init_distance_functions_<isa>()`, and reads back the slots the cell is graded through. A slot whose
pointer is still the reference's was **not installed**, and is reported as that and never graded as a
pass. This is the only route that reaches AVX-512's `static bit1_distance_hamming_avx512` and every
`static inline` `_impl`, and it is also the route the extension itself takes.

**The driver is generated C**, not a fixture: :func:`driver_source` emits it from :data:`CASES` and the
specials below, so the case list is Python data with one C rendering. It draws inputs from splitmix64
seeded per case, calls the reference and the installed kernel on the same bytes, and prints one JSON line
per `(slot, case)`. `inf` and `nan` are printed as strings (`"inf"`, `"-inf"`, `"nan"`) because JSON has
no literal for them, and every finite value with `%.9g`.

**The comparison is in Python** (:func:`compare`), not in C, so the tolerance table is data a reader can
audit: both NaN is equal, both infinite with the same sign is equal, and otherwise
`|ref - got| <= atol + rtol*|ref|`. :data:`TOLERANCE` is per `(type, metric)` — an entry is widened only
with the gold's worst observed error named beside it, which the self-test measures and reports.

**Two references, and :func:`reference_for` says which.** `distance-cpu.c` is the reference for every case
whose answer it has: that is what it is for. It is *not* the reference where the target has no one
semantics — on a non-finite input, and where the scalar's own answer overflows — because there
sqlite-vector's SIMD kernels disagree with it and with each other, per ISA. Those cases are graded against
the **cell's own gold**, which is the only question with an answer: does this body do what the kernel it
replaces does. The reason and the evidence are in :func:`reference_for`'s docstring, the flag is on
:class:`Special`, and the disagreements themselves are reported by the self-test rather than smoothed
away.
"""

from __future__ import annotations

import json
import math
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "BULK_NS",
    "BULK_SEEDS",
    "EDGE_NS",
    "NON_FINITE_SPECIALS",
    "REFERENCES",
    "SPECIAL_NS",
    "SPECIAL_OF_CASE",
    "SPECIALS",
    "CASES",
    "TOLERANCE",
    "TIMEOUT",
    "Case",
    "Comparison",
    "DiffRun",
    "cases_for",
    "compare",
    "compare_records",
    "driver_source",
    "number",
    "pair_of_slot",
    "reference_for",
    "run",
    "slot_name",
    "tolerance",
]

#: One driver run's wall-clock ceiling. A body that does not finish inside it is `wrong`.
TIMEOUT = 300

#: The bulk grid: sizes that exercise every unrolled path, eight seeds each.
BULK_NS = (64, 256, 1024, 4096)
BULK_SEEDS = tuple(range(8))

#: The edge sizes: zero, the tails below one vector, and one either side of each unroll width.
EDGE_NS = (0, 1, 2, 3, 5, 7, 9, 15, 17, 31, 33, 63, 65, 127, 129)

#: The two sizes the special-value cases are run at: a ragged one and a whole vector's worth.
SPECIAL_NS = (17, 64)

_FLOATS = ("float32", "float16", "bfloat16")
_INTS = ("uint8", "int8")
_NUMERIC = _FLOATS + _INTS
_ALL = _NUMERIC + ("bit1",)

#: Every element type, in the order of the `vector_type` enum — the index a driver bitmask uses.
TYPE_ENUM = {"float32": "F32", "float16": "F16", "bfloat16": "BF16", "uint8": "U8", "int8": "I8", "bit1": "BIT"}
METRIC_ENUM = {"l2": "L2", "l2_squared": "SQUARED_L2", "cosine": "COSINE", "dot": "DOT", "l1": "L1", "hamming": "HAMMING"}

#: The reverse: a slot's enum spelling back to this package's.
TYPE_OF_ENUM = {v: k for k, v in TYPE_ENUM.items()}
METRIC_OF_ENUM = {v: k for k, v in METRIC_ENUM.items()}


@dataclass(frozen=True)
class Special:
    """One special-value pattern: its name, its C constant, and the types it means anything for.

    `non_finite` says whether the inputs it writes hold an inf or a NaN, which is what sends its cases to
    the gold reference (:func:`reference_for`). The flag lives here, on the case table's data, and not in
    the comparison.
    """

    name: str
    constant: str
    types: tuple[str, ...]
    non_finite: bool = False


#: The special-value patterns, applied after the random fill at each of :data:`SPECIAL_NS`. `non_finite`
#: marks the four that write an inf or a NaN into the inputs; `large` writes finite values that the
#: arithmetic then overflows, which :func:`reference_for` catches on the scalar's answer instead.
SPECIALS = (
    Special("inf_a", "SP_INF_A", _FLOATS, non_finite=True),
    Special("inf_both_same", "SP_INF_BOTH_SAME", _FLOATS, non_finite=True),
    Special("inf_both_opposite", "SP_INF_BOTH_OPPOSITE", _FLOATS, non_finite=True),
    Special("nan", "SP_NAN", _FLOATS, non_finite=True),
    Special("zeros_a", "SP_ZEROS_A", _NUMERIC),
    Special("large", "SP_LARGE", _FLOATS),
    Special("extremes_lo_hi", "SP_EXTREMES_LO_HI", _INTS),
    Special("extremes_hi_lo", "SP_EXTREMES_HI_LO", _INTS),
    Special("bit_zero_vs_ones", "SP_BIT_ZERO_ONES", ("bit1",)),
)


@dataclass(frozen=True)
class Case:
    """One input the differential draws: its name, its size, its seed, its pattern and who it is for."""

    name: str
    kind: str  # "bulk" | "edge"
    n: int
    seed: int
    special: str  # a `SPECIALS` name, or "" for a plain random fill
    types: tuple[str, ...]


def _cases() -> tuple[Case, ...]:
    built: list[Case] = []
    for n in BULK_NS:
        for seed in BULK_SEEDS:
            built.append(Case(f"bulk/n{n}/s{seed}", "bulk", n, seed, "", _ALL))
    for index, n in enumerate(EDGE_NS):
        built.append(Case(f"edge/n{n}", "edge", n, 100 + index, "", _ALL))
    for special in SPECIALS:
        for index, n in enumerate(SPECIAL_NS):
            built.append(Case(f"edge/{special.name}/n{n}", "edge", n, 200 + index, special.name, special.types))
    return tuple(built)


#: Every case, bulk then edge. A type's cases are the ones whose `types` name it.
CASES = _cases()

#: Each case's special pattern, by case name (`""` for a plain random fill). A case name is unique across
#: :data:`CASES`, so this is what turns a driver record — which carries the name and not the pattern —
#: back into the flag :func:`reference_for` reads.
SPECIAL_OF_CASE: dict[str, str] = {case.name: case.special for case in CASES}

#: The specials whose inputs hold an inf or a NaN.
NON_FINITE_SPECIALS = frozenset(special.name for special in SPECIALS if special.non_finite)

#: The two references a case can be graded against.
REFERENCES = ("scalar", "gold")

#: `(rtol, atol)` per `(type, metric)`. **Data, and only data** — an entry moves when the gold's worst
#: observed error says it must, and the comment beside it then names that error. The float rows start at
#: rtol 1e-4 / atol 1e-5 because a SIMD kernel sums in a different order from the scalar one and the
#: reassociation is the whole difference; the integer rows are exact (1e-6 / 0) because the accumulation
#: is integral, except `cosine`, which divides by a float norm; `hamming` counts bits and is exact.
TOLERANCE: dict[tuple[str, str], tuple[float, float]] = {
    ("float32", "l2"): (1e-4, 1e-5),
    ("float32", "l2_squared"): (1e-4, 1e-5),
    ("float32", "l1"): (1e-4, 1e-5),
    ("float32", "dot"): (1e-4, 1e-5),
    ("float32", "cosine"): (1e-4, 1e-5),
    ("float16", "l2"): (1e-4, 1e-5),
    ("float16", "l2_squared"): (1e-4, 1e-5),
    ("float16", "l1"): (1e-4, 1e-5),
    ("float16", "dot"): (1e-4, 1e-5),
    ("float16", "cosine"): (1e-4, 1e-5),
    ("bfloat16", "l2"): (1e-4, 1e-5),
    ("bfloat16", "l2_squared"): (1e-4, 1e-5),
    ("bfloat16", "l1"): (1e-4, 1e-5),
    ("bfloat16", "dot"): (1e-4, 1e-5),
    ("bfloat16", "cosine"): (1e-4, 1e-5),
    # Widened on the real target's first run (the 93-cell self-test at `0c2223a`, in the image; session
    # `9326`'s review), and it is int8's cause below on the rows the fixture could not measure: the scalar
    # `uint8` kernels accumulate into a `float` while the SIMD ones accumulate into int32 and convert once,
    # so past float32's exact integer range the **reference** is the imprecise side. Worst observed, on sse2,
    # avx2 and avx512 alike: **`l2_squared` 1.05e-6** (bulk/n4096/s4, 45930488 against 45930440) and
    # **`dot` 1.45e-6** (bulk/n4096/s7, −66351128 against −66351032); `l2` is `l2_squared`'s error under
    # the square root. `l1` sums absolute differences, which stay inside float32's exact range at every
    # size here, and it has not drifted. 1e-5 leaves each a margin an off-by-one tail cannot hide in.
    ("uint8", "l2"): (1e-5, 0.0),
    ("uint8", "l2_squared"): (1e-5, 0.0),
    ("uint8", "l1"): (1e-6, 0.0),
    ("uint8", "dot"): (1e-5, 0.0),
    ("uint8", "cosine"): (1e-4, 0.0),
    # Widened from 1e-6 on the gold's own disagreement, and the reference is the imprecise side:
    # `int8_distance_l2_impl_cpu` accumulates the squared differences into a `float`, while every SIMD
    # kernel accumulates into int32 and converts once at the end. Past float32's exact integer range
    # (n·255² is ~2.7e8 at n = 4096) the scalar drifts and the vector does not. Worst observed on the
    # fixture's 39 native golds: **l2_squared 1.06e-6** (sse2/avx2/avx512 alike, bulk/n4096/s4,
    # 45090808 against the exact 45090760) and **l2 5.09e-7**, which is the same error halved by the
    # square root. 1e-5 leaves both a margin; an off-by-one tail at n = 4096 moves the answer by
    # ~1e-3 of itself, so it is still caught.
    ("int8", "l2"): (1e-5, 0.0),
    ("int8", "l2_squared"): (1e-5, 0.0),
    ("int8", "l1"): (1e-6, 0.0),
    ("int8", "dot"): (1e-6, 0.0),
    ("int8", "cosine"): (1e-4, 0.0),
    ("bit1", "hamming"): (0.0, 0.0),
}

#: The pair a `(type, metric)` with no row of its own falls back to, so a slot is never ungraded.
FALLBACK = (1e-4, 1e-5)


def tolerance(type_: str, metric: str) -> tuple[float, float]:
    """The `(rtol, atol)` for one `(type, metric)`."""
    return TOLERANCE.get((type_, metric), FALLBACK)


def slot_name(slot: tuple[str, str] | list[str]) -> str:
    """A `(metric enum, type enum)` slot as the driver spells it on its command line: `L2:F32`."""
    return f"{slot[0]}:{slot[1]}"


def pair_of_slot(name: str) -> tuple[str, str]:
    """A slot the driver's way — `SQUARED_L2:I8` — back as this package's `(type, metric)`."""
    metric_enum, _, type_enum = name.partition(":")
    return TYPE_OF_ENUM.get(type_enum, type_enum), METRIC_OF_ENUM.get(metric_enum, metric_enum)


def cases_for(type_: str) -> tuple[Case, ...]:
    """The cases that mean something for one element type."""
    return tuple(case for case in CASES if type_ in case.types)


# MARK: - the comparison -


def number(value) -> float:
    """A driver field — a JSON number, or `"inf"` / `"-inf"` / `"nan"` — as a float."""
    if isinstance(value, str):
        return {"inf": math.inf, "-inf": -math.inf, "nan": math.nan}[value]
    return float(value)


def compare(ref, got, rtol: float, atol: float) -> bool:
    """Whether *got* agrees with *ref*: both NaN, both the same infinity, or inside the tolerance."""
    a, b = number(ref), number(got)
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    if math.isinf(a) or math.isinf(b):
        return math.isinf(a) and math.isinf(b) and (a > 0) == (b > 0)
    return abs(a - b) <= atol + rtol * abs(a)


def reference_for(case: str, scalar) -> str:
    """Which reference one case is graded against: `"gold"` — the cell's own gold — or `"scalar"`.

    A case goes to the gold when **its inputs hold a non-finite value** (the specials in
    :data:`NON_FINITE_SPECIALS`: `inf_a`, `inf_both_same`, `inf_both_opposite`, `nan`) **or when the
    scalar reference's own result for it is not finite** — `large`, whose finite inputs overflow, and any
    case where the scalar answers inf or NaN. Every other case is graded against the scalar, which is what
    `distance-cpu.c` is for.

    **The reason is the target, not the tolerance.** On inf and NaN inputs sqlite-vector's f16 and bf16
    SIMD kernels disagree with its scalar kernel *and with each other*. Read at `0c2223a`, in the image,
    gold against scalar: `COSINE:BF16` answers 1 on `inf_a`, `inf_both_same` and `inf_both_opposite`
    where the scalar answers NaN, on every ISA; `DOT:BF16` on `large` answers NaN on avx2 and avx512 and
    **+inf on sse2** where the scalar answers −inf; `L1:F16`, `L2:F16` and `SQUARED_L2:F16` on
    `inf_both_same` answer finite where the scalar answers NaN, on sse2 and avx2 but **not** avx512,
    which agrees with the scalar there.

    There is no one semantics for these cases to be graded against, because the target's kernels do not
    have one, and inventing one would make the graders assert something the project does not know.
    Grading them against the cell's own gold asks the only question that has an answer — *does this body
    do what the kernel it replaces does* — and it is the same question the scalar-graded cases ask,
    against the reference that is right for them. What the target disagrees with itself on is reported
    (the self-test's `disagreements`), never hidden: the rule narrows what is claimed, it does not narrow
    what is seen.
    """
    if SPECIAL_OF_CASE.get(case, "") in NON_FINITE_SPECIALS:
        return "gold"
    return "scalar" if math.isfinite(number(scalar)) else "gold"


def relative_error(ref, got) -> float:
    """`|ref - got| / |ref|`, or the absolute error when the reference is zero. NaN when either is not finite."""
    a, b = number(ref), number(got)
    if not (math.isfinite(a) and math.isfinite(b)):
        return 0.0 if compare(ref, got, 0.0, 0.0) else math.inf
    return abs(a - b) / abs(a) if a != 0.0 else abs(a - b)


@dataclass(frozen=True)
class Comparison:
    """One slot's verdict: the counts, the first case that failed, and the worst error seen.

    `scalar_cases` and `gold_cases` are how many of the slot's cases each reference graded, so a reader of
    a result never has to guess which question a count answers (:func:`reference_for`).
    """

    slot: str
    type: str
    metric: str
    installed: bool
    bulk_passed: int = 0
    bulk_failed: int = 0
    edge_passed: int = 0
    edge_failed: int = 0
    scalar_cases: int = 0
    gold_cases: int = 0
    first_failure: dict | None = None
    worst: float = 0.0


@dataclass(frozen=True)
class DiffRun:
    """What one driver process produced."""

    available: bool
    comparisons: tuple[Comparison, ...]
    records: tuple[dict, ...]
    returncode: int
    signal: str | None
    timed_out: bool
    output: str
    seconds: float

    @property
    def crashed(self) -> bool:
        return self.timed_out or self.signal is not None or self.returncode != 0


def run(
    exe: Path | str,
    isa: str,
    slots: list[tuple[str, str]] | tuple,
    *,
    timeout: int = TIMEOUT,
    gold: dict | None = None,
) -> DiffRun:
    """Run the driver for one cell: its ISA, the slots it is graded through, every case of its type.

    *gold* is the gold build's answers, `{(slot, case): got}`, for the cases :func:`reference_for` sends
    to the gold. Without it every case is graded against the scalar — which is how the gold reference is
    itself produced, and the only way its disagreements with the scalar are visible.
    """
    command = [str(exe), isa, *[slot_name(slot) for slot in slots]]
    started = time.monotonic()
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return DiffRun(False, (), (), -1, None, True, f"the driver did not finish inside {timeout}s", time.monotonic() - started)
    seconds = time.monotonic() - started
    records = tuple(json.loads(line) for line in done.stdout.splitlines() if line.startswith("{"))
    crash = _signal_name(done.returncode)
    available = any(record.get("available") is True for record in records)
    return DiffRun(
        available=available,
        comparisons=tuple(compare_records(records, slots, gold)),
        records=records,
        returncode=done.returncode,
        signal=crash,
        timed_out=False,
        output=done.stderr,
        seconds=seconds,
    )


def _signal_name(returncode: int) -> str | None:
    if returncode >= 0:
        return None
    try:
        return signal.Signals(-returncode).name
    except ValueError:  # pragma: no cover - a signal number this Python does not know
        return f"signal {-returncode}"


def compare_records(records: tuple[dict, ...] | list[dict], slots, gold: dict | None = None) -> list[Comparison]:
    """One :class:`Comparison` per slot, from the driver's records. Pure: the whole comparison is here.

    *gold* is `{(slot, case): the gold's answer}`, or `None` to grade every case against the scalar.
    """
    installed = {r["slot"]: r["installed"] for r in records if "installed" in r}
    out: list[Comparison] = []
    for slot in slots:
        name = slot_name(slot)
        metric = METRIC_OF_ENUM.get(slot[0], slot[0])
        type_ = TYPE_OF_ENUM.get(slot[1], slot[1])
        if not installed.get(name, False):
            out.append(Comparison(name, type_, metric, installed=False))
            continue
        rtol, atol = tolerance(type_, metric)
        counts = {"bulk": [0, 0], "edge": [0, 0]}
        graded = {"scalar": 0, "gold": 0}
        first: dict | None = None
        worst = 0.0
        for record in records:
            if record.get("slot") != name or "case" not in record:
                continue
            against, expected, ok = _expected(record, name, gold, rtol, atol)
            graded[against] += 1
            counts[record["kind"]][0 if ok else 1] += 1
            if expected is not None:
                worst = max(worst, min(relative_error(expected, record["got"]), 1e300))
            if not ok and first is None:
                first = {
                    "slot": name,
                    "case": record["case"],
                    "kind": record["kind"],
                    "n": record["n"],
                    "seed": record["seed"],
                    "reference": against,
                    "expected": expected,
                    "got": record["got"],
                }
                if against == "gold":
                    first["scalar"] = record["ref"]
        out.append(
            Comparison(
                slot=name,
                type=type_,
                metric=metric,
                installed=True,
                bulk_passed=counts["bulk"][0],
                bulk_failed=counts["bulk"][1],
                edge_passed=counts["edge"][0],
                edge_failed=counts["edge"][1],
                scalar_cases=graded["scalar"],
                gold_cases=graded["gold"],
                first_failure=first,
                worst=worst,
            )
        )
    return out


def _expected(record: dict, slot: str, gold: dict | None, rtol: float, atol: float):
    """One record's `(reference, expected, ok)` under :func:`reference_for`.

    A gold-referenced case the gold build has no answer for is **failed, never passed**: the graders could
    not ask the question, and a silent pass is the one answer that would be wrong. It is `expected: None`
    and the caller's `first_failure` shows it.
    """
    against = "scalar" if gold is None else reference_for(record["case"], record["ref"])
    if against == "scalar":
        return "scalar", record["ref"], compare(record["ref"], record["got"], rtol, atol)
    expected = (gold or {}).get((slot, record["case"]))
    if expected is None:
        return "gold", None, False
    return "gold", expected, compare(expected, record["got"], rtol, atol)


# MARK: - the generated driver -


def driver_source() -> str:
    """The differential driver's C, generated from :data:`CASES`. Written into the staged copy, compiled
    with the base flags and linked with all six kernel objects."""
    return _DRIVER_HEAD + _case_table() + _DRIVER_TAIL


def _case_table() -> str:
    rows = []
    for case in CASES:
        mask = " | ".join(f"T_{TYPE_ENUM[t]}" for t in case.types)
        special = next((s.constant for s in SPECIALS if s.name == case.special), "SP_NONE")
        rows.append(
            f'    {{ "{case.name}", "{case.kind}", {case.n}, {case.seed}ull, {special}, {mask} }},'
        )
    return "static const case_t CASES[] = {\n" + "\n".join(rows) + "\n};\n"


_DRIVER_HEAD = r"""/*
 * G-diff's driver — generated by lattice/diff.py. Do not edit this file: edit diff.py.
 *
 * usage: driver <isa> <METRIC:TYPE> [<METRIC:TYPE> ...]
 *
 * Installs the scalar table, snapshots it as the reference, initialises the ISA, and compares each
 * named slot against the reference on the same inputs. One JSON line per (slot, case).
 */
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "distance-cpu.h"
#include "distance-sse2.h"
#include "distance-avx2.h"
#include "distance-avx512.h"
#include "distance-neon.h"
#include "distance-rvv.h"

extern distance_function_t dispatch_distance_table[VECTOR_DISTANCE_MAX][VECTOR_TYPE_MAX];

#define SP_NONE               0
#define SP_INF_A              1
#define SP_INF_BOTH_SAME      2
#define SP_INF_BOTH_OPPOSITE  3
#define SP_NAN                4
#define SP_ZEROS_A            5
#define SP_LARGE              6
#define SP_EXTREMES_LO_HI     7
#define SP_EXTREMES_HI_LO     8
#define SP_BIT_ZERO_ONES      9

#define T_F32   (1u << VECTOR_TYPE_F32)
#define T_F16   (1u << VECTOR_TYPE_F16)
#define T_BF16  (1u << VECTOR_TYPE_BF16)
#define T_U8    (1u << VECTOR_TYPE_U8)
#define T_I8    (1u << VECTOR_TYPE_I8)
#define T_BIT   (1u << VECTOR_TYPE_BIT)

typedef struct {
    const char *name;
    const char *kind;
    int n;
    uint64_t seed;
    int special;
    unsigned types;
} case_t;

"""

_DRIVER_TAIL = r"""
#define NCASES ((int)(sizeof(CASES) / sizeof(CASES[0])))

/* splitmix64: one seed in, the same stream out, on every box. */
static uint64_t sm_state;

static void sm_seed (uint64_t s) {
    sm_state = s;
}

static uint64_t sm_next (void) {
    uint64_t z = (sm_state += 0x9E3779B97F4A7C15ull);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}

static double sm_unit (void) {
    return (double)(sm_next() >> 11) * (1.0 / 9007199254740992.0);
}

static float sm_signed (void) {
    return (float)(sm_unit() * 2.0 - 1.0);
}

static int elem_size (int type) {
    switch (type) {
        case VECTOR_TYPE_F32: return 4;
        case VECTOR_TYPE_F16: return 2;
        case VECTOR_TYPE_BF16: return 2;
        default: return 1;
    }
}

static void put_value (int type, void *buf, int i, float v) {
    switch (type) {
        case VECTOR_TYPE_F32:  ((float *)buf)[i] = v; break;
        case VECTOR_TYPE_F16:  ((uint16_t *)buf)[i] = float32_to_float16(v); break;
        case VECTOR_TYPE_BF16: ((uint16_t *)buf)[i] = float32_to_bfloat16(v); break;
        case VECTOR_TYPE_U8:   ((uint8_t *)buf)[i] = (uint8_t)v; break;
        case VECTOR_TYPE_I8:   ((int8_t *)buf)[i] = (int8_t)v; break;
        default:               ((uint8_t *)buf)[i] = (uint8_t)v; break;
    }
}

static void fill_random (int type, void *buf, int n) {
    for (int i = 0; i < n; ++i) {
        if (type == VECTOR_TYPE_U8 || type == VECTOR_TYPE_I8 || type == VECTOR_TYPE_BIT) {
            ((uint8_t *)buf)[i] = (uint8_t)(sm_next() & 0xFFull);
        } else {
            put_value(type, buf, i, sm_signed());
        }
    }
}

static float large_magnitude (int type) {
    return (type == VECTOR_TYPE_F16) ? 60000.0f : 1e30f;
}

static void apply_special (int special, int type, void *a, void *b, int n) {
    size_t bytes = (size_t)n * (size_t)elem_size(type);
    switch (special) {
        case SP_INF_A:
            for (int i = 0; i < n; i += 5) put_value(type, a, i, INFINITY);
            break;
        case SP_INF_BOTH_SAME:
            for (int i = 0; i < n; i += 5) { put_value(type, a, i, INFINITY); put_value(type, b, i, INFINITY); }
            break;
        case SP_INF_BOTH_OPPOSITE:
            for (int i = 0; i < n; i += 5) { put_value(type, a, i, INFINITY); put_value(type, b, i, -INFINITY); }
            break;
        case SP_NAN:
            for (int i = 0; i < n; i += 7) put_value(type, a, i, NAN);
            break;
        case SP_ZEROS_A:
            memset(a, 0, bytes);
            break;
        case SP_LARGE: {
            float m = large_magnitude(type);
            for (int i = 0; i < n; ++i) {
                put_value(type, a, i, sm_signed() * m);
                put_value(type, b, i, sm_signed() * m);
            }
            break;
        }
        case SP_EXTREMES_LO_HI:
            if (type == VECTOR_TYPE_U8) { memset(a, 0x00, bytes); memset(b, 0xFF, bytes); }
            else                        { memset(a, 0x80, bytes); memset(b, 0x7F, bytes); }
            break;
        case SP_EXTREMES_HI_LO:
            if (type == VECTOR_TYPE_U8) { memset(a, 0xFF, bytes); memset(b, 0x00, bytes); }
            else                        { memset(a, 0x7F, bytes); memset(b, 0x80, bytes); }
            break;
        case SP_BIT_ZERO_ONES:
            memset(a, 0x00, bytes);
            memset(b, 0xFF, bytes);
            break;
        default:
            break;
    }
}

static bool init_isa (const char *isa) {
    if (strcmp(isa, "sse2") == 0) return init_distance_functions_sse2();
    if (strcmp(isa, "avx2") == 0) return init_distance_functions_avx2();
    if (strcmp(isa, "avx512") == 0) return init_distance_functions_avx512();
    if (strcmp(isa, "neon") == 0) return init_distance_functions_neon();
    if (strcmp(isa, "rvv") == 0) return init_distance_functions_rvv();
    return false;
}

static int metric_index (const char *s) {
    if (strcmp(s, "L2") == 0) return VECTOR_DISTANCE_L2;
    if (strcmp(s, "SQUARED_L2") == 0) return VECTOR_DISTANCE_SQUARED_L2;
    if (strcmp(s, "COSINE") == 0) return VECTOR_DISTANCE_COSINE;
    if (strcmp(s, "DOT") == 0) return VECTOR_DISTANCE_DOT;
    if (strcmp(s, "L1") == 0) return VECTOR_DISTANCE_L1;
    if (strcmp(s, "HAMMING") == 0) return VECTOR_DISTANCE_HAMMING;
    return -1;
}

static int type_index (const char *s) {
    if (strcmp(s, "F32") == 0) return VECTOR_TYPE_F32;
    if (strcmp(s, "F16") == 0) return VECTOR_TYPE_F16;
    if (strcmp(s, "BF16") == 0) return VECTOR_TYPE_BF16;
    if (strcmp(s, "U8") == 0) return VECTOR_TYPE_U8;
    if (strcmp(s, "I8") == 0) return VECTOR_TYPE_I8;
    if (strcmp(s, "BIT") == 0) return VECTOR_TYPE_BIT;
    return -1;
}

/* JSON has no inf and no nan: spell them as strings and let the reader put them back. */
static void print_number (float v) {
    if (isnan(v)) { printf("\"nan\""); return; }
    if (isinf(v)) { printf(v > 0.0f ? "\"inf\"" : "\"-inf\""); return; }
    printf("%.9g", (double)v);
}

int main (int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s <isa> <METRIC:TYPE> [<METRIC:TYPE> ...]\n", argv[0]);
        return 2;
    }
    const char *isa = argv[1];

    /* Line-buffered on purpose: a body that segfaults on case 40 must leave cases 1..39 on the pipe,
     * or a crash would read as "the ISA was never available" instead of as the wrong answer it is. */
    setvbuf(stdout, NULL, _IOLBF, 0);

    distance_function_t reference[VECTOR_DISTANCE_MAX][VECTOR_TYPE_MAX];
    init_distance_functions(true);
    memcpy(reference, dispatch_distance_table, sizeof(reference));

    bool available = init_isa(isa);
    printf("{\"isa\":\"%s\",\"available\":%s}\n", isa, available ? "true" : "false");
    if (!available) { fflush(stdout); return 0; }

    for (int s = 2; s < argc; ++s) {
        char spec[64];
        snprintf(spec, sizeof(spec), "%s", argv[s]);
        char *colon = strchr(spec, ':');
        if (colon == NULL) { printf("{\"slot\":\"%s\",\"error\":\"no ':' in the slot\"}\n", argv[s]); continue; }
        *colon = '\0';
        int m = metric_index(spec);
        int t = type_index(colon + 1);
        if (m < 0 || t < 0) { printf("{\"slot\":\"%s\",\"error\":\"unknown slot\"}\n", argv[s]); continue; }

        distance_function_t got_fn = dispatch_distance_table[m][t];
        distance_function_t ref_fn = reference[m][t];
        bool installed = (got_fn != NULL) && (got_fn != ref_fn);
        printf("{\"slot\":\"%s\",\"installed\":%s}\n", argv[s], installed ? "true" : "false");
        if (!installed || ref_fn == NULL) { fflush(stdout); continue; }

        for (int c = 0; c < NCASES; ++c) {
            if ((CASES[c].types & (1u << t)) == 0) continue;
            int n = CASES[c].n;
            size_t bytes = (size_t)n * (size_t)elem_size(t);
            void *a = malloc(bytes ? bytes : 1);
            void *b = malloc(bytes ? bytes : 1);
            if (a == NULL || b == NULL) { free(a); free(b); fprintf(stderr, "out of memory\n"); return 3; }
            sm_seed(CASES[c].seed * 1000003ull + (uint64_t)n);
            fill_random(t, a, n);
            fill_random(t, b, n);
            apply_special(CASES[c].special, t, a, b, n);

            float ref = ref_fn(a, b, n);
            float got = got_fn(a, b, n);
            printf("{\"slot\":\"%s\",\"case\":\"%s\",\"kind\":\"%s\",\"n\":%d,\"seed\":%llu,\"ref\":",
                   argv[s], CASES[c].name, CASES[c].kind, n, (unsigned long long)CASES[c].seed);
            print_number(ref);
            printf(",\"got\":");
            print_number(got);
            printf("}\n");
            free(a);
            free(b);
        }
        fflush(stdout);
    }
    return 0;
}
"""
