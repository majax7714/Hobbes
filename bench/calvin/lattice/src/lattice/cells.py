"""The lattice: sqlite-vector's kernel files read as a grid of `(type, metric, isa)` cells.

Each `src/distance-<isa>.c` hand-writes the same distance functions, named `<type>_distance_<metric>_<isa>`
and installed into `dispatch_distance_table` by the file's `init_distance_functions_<isa>`. `build()`
reads that grid off the files with `scan` and nothing else: no compiler, no preprocessor, no graph.

Three things the real source does that the grid does not say, and this module carries:

- **`_impl` has no table slot.** `l2` and `l2_squared` are one-statement wrappers that call it with
  `use_sqrt` true or false, so an `_impl` is graded through the wrappers that reach it — that is what
  `Cell.graded_via` holds, and why a wrapper is recognised by its body and not by its name.
- **AVX-512's `bit1_distance_hamming_avx512` is `static`**, and every `_impl` is `static inline`, so a
  harness that calls a kernel by name cannot reach them. `Cell.static` is recorded for that reason.
- **NEON spells its int8 helper `int8_distance_l2_neon_imp`** — no `_impl`, and the ISA before the
  abbreviation. It is mapped to `(int8, l2_impl, neon)` and the cell keeps its real name.

`cpu` is mapped like any other ISA because it is the numeric reference the differential grades against,
but it is not native and not a cell to grade; it also fills the table through a local `cpu_table`
initialiser and `memcpy` rather than by assignment, a shape this module does not read, so its cells
carry no slots. `neon` and `rvv` are mapped and marked not native: this box does not run them.

A name that starts `<type>_distance_` and does not parse into the grid is listed in `Lattice.unmatched`
with the reason, never dropped: the whole point of the map is that a cell it does not name is visible.

**A shadow's lattice is the same grid under new names** (`shadow.py`, E2). `build(target, rename=…)`
takes a map from the name as the shadow writes it back to the target's own name, and every question
about the *grid* — does this parse into `(type, metric, isa)`, is this the file's init function — is
asked of the original, while everything about the *file* — the cell's name, the wrapper's one call, the
init function's slot assignments — stays what the shadow wrote. `Cell.original` carries the other side,
so a row can name both. Without a *rename* the two are the same string and nothing changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

from .scan import FunctionDef, ScanResult, Span, scan

__all__ = [
    "TYPES",
    "METRICS",
    "ISAS",
    "NATIVE",
    "Cell",
    "Lattice",
    "Source",
    "Unmatched",
    "UnknownCell",
    "build",
    "parse_name",
]

#: the axes, in the order the target writes them — also the order `Lattice.neighbours` returns.
TYPES = ("float32", "float16", "bfloat16", "uint8", "int8", "bit1")
METRICS = ("l2_impl", "l2", "l2_squared", "l1", "dot", "cosine", "hamming")
ISAS = ("cpu", "sse2", "avx2", "avx512", "neon", "rvv")

#: the ISAs this box runs, so the ones a body can be graded on (`cpu` is the reference, not a cell).
NATIVE = frozenset({"sse2", "avx2", "avx512"})

_METRIC_ENUM = {
    "l2": "L2",
    "l2_squared": "SQUARED_L2",
    "cosine": "COSINE",
    "dot": "DOT",
    "l1": "L1",
    "hamming": "HAMMING",
}
_TYPE_ENUM = {
    "float32": "F32",
    "float16": "F16",
    "bfloat16": "BF16",
    "uint8": "U8",
    "int8": "I8",
    "bit1": "BIT",
}

_SLOT = re.compile(
    r"dispatch_distance_table\s*\[\s*VECTOR_DISTANCE_(\w+)\s*\]\s*"
    r"\[\s*VECTOR_TYPE_(\w+)\s*\]\s*=\s*([A-Za-z_]\w*)\s*;"
)
_RETURN_CALL = re.compile(r"\Areturn\s+([A-Za-z_]\w*)\s*\(")

#: one `(metric enum, type enum)` position in `dispatch_distance_table`, e.g. `("HAMMING", "BIT")`.
Slot = tuple[str, str]


class UnknownCell(KeyError):
    """No cell in this lattice has that id."""


@dataclass(frozen=True)
class Cell:
    """One `(type, metric, isa)` position: the function that fills it and how it is reached."""

    type: str
    metric: str
    isa: str
    name: str
    original: str  # the target's own name for it; equal to `name` outside a shadow
    file: str
    signature: str
    signature_span: Span
    body_span: Span
    kind: str  # "impl" | "wrapper" | "body"
    static: bool
    inline: bool
    native: bool
    slots: tuple[Slot, ...]
    graded_via: tuple[Slot, ...]

    @property
    def id(self) -> str:
        """The stable id a task record and the CLI use: `<isa>/<type>/<metric>`."""
        return f"{self.isa}/{self.type}/{self.metric}"


@dataclass(frozen=True)
class Source:
    """One kernel file, read once: its text, its scan, and the name of the init function it defines."""

    isa: str
    path: Path
    file: str
    text: str
    scanned: ScanResult
    init: str | None


@dataclass(frozen=True)
class Unmatched:
    """A kernel-shaped name the grid could not place, kept with the reason it could not."""

    name: str
    file: str
    line: int
    reason: str


@dataclass
class Lattice:
    """Every cell of a target's kernel files, the files they came from, and what did not fit."""

    root: Path
    sources: dict[str, Source]
    cells: dict[str, Cell]
    unmatched: tuple[Unmatched, ...]

    def get(self, cell_id: str) -> Cell:
        """The cell with that id, or `UnknownCell`."""
        try:
            return self.cells[cell_id]
        except KeyError:
            raise UnknownCell(cell_id) from None

    def by_isa(self, isa: str) -> tuple[Cell, ...]:
        """That ISA's cells, in the order the file defines them."""
        found = [c for c in self.cells.values() if c.isa == isa]
        return tuple(sorted(found, key=lambda c: c.signature_span.start))

    def text(self, cell: Cell) -> str:
        """The full text of the file the cell lives in."""
        return self.sources[cell.isa].text

    def neighbours(self, cell: Cell) -> tuple[Cell, ...]:
        """The cells one step along each axis that exist, in a fixed order.

        The ISA axis first (same type and metric, every other ISA), then the type axis (same metric and
        ISA), then the metric axis (same type and ISA); within each axis, the order of `ISAS`, `TYPES`
        and `METRICS` above, which is the order the target writes them. `hamming` has no type or metric
        neighbours — `bit1` has no other metric and no other type has `hamming` — so it keeps only its
        ISA siblings; an `_impl` and its two wrappers are metric neighbours of each other.
        """
        ids = [f"{isa}/{cell.type}/{cell.metric}" for isa in ISAS if isa != cell.isa]
        ids += [f"{cell.isa}/{t}/{cell.metric}" for t in TYPES if t != cell.type]
        ids += [f"{cell.isa}/{cell.type}/{m}" for m in METRICS if m != cell.metric]
        return tuple(self.cells[i] for i in ids if i in self.cells)


def parse_name(name: str) -> tuple[str, str, str] | None:
    """`<type>_distance_<metric>_<isa>` as `(type, metric, isa)`, or `None` if it is not one.

    NEON's `int8_distance_l2_neon_imp` parses as `(int8, l2_impl, neon)`: a trailing `_imp` after the
    ISA is the same helper the other files spell `_impl` before it.
    """
    for kind in TYPES:
        prefix = f"{kind}_distance_"
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix) :]
        abbreviated = rest.endswith("_imp")
        if abbreviated:
            rest = rest[: -len("_imp")]
        for isa in sorted(ISAS, key=len, reverse=True):
            if not rest.endswith(f"_{isa}"):
                continue
            metric = rest[: -(len(isa) + 1)]
            if abbreviated:
                metric = f"{metric}_impl"
            if metric in METRICS:
                return kind, metric, isa
        return None
    return None


def build(target: Path | str, rename: dict[str, str] | None = None) -> Lattice:
    """Read `<target>/src/distance-*.c` into a lattice.

    *rename* maps a name as the tree writes it back to the target's own name — the reverse of a
    `shadow.Plan`. The grid is read off the originals and the cells keep what the file says, so the
    lattice of a shadow is the same 13 cells per ISA under new names. `None` is the identity.
    """
    root = Path(target)
    back = dict(rename or {})
    sources: dict[str, Source] = {}
    unmatched: list[Unmatched] = []

    for path in sorted((root / "src").glob("distance-*.c")):
        isa = path.stem[len("distance-") :]
        rel = f"src/{path.name}"
        if isa not in ISAS:
            unmatched.append(Unmatched(path.name, rel, 0, "file name carries no known ISA"))
            continue
        text = path.read_text(encoding="utf-8")
        scanned = scan(text)
        init = f"init_distance_functions_{isa}"
        written = next((fn.name for fn in scanned.functions if back.get(fn.name, fn.name) == init), None)
        sources[isa] = Source(isa, path, rel, text, scanned, written)

    cells: dict[str, Cell] = {}
    for isa in ISAS:
        source = sources.get(isa)
        if source is None:
            continue
        for fn in source.scanned.functions:
            original = back.get(fn.name, fn.name)
            axes = parse_name(original)
            if axes is None:
                if _is_kernel_shaped(original):
                    unmatched.append(
                        Unmatched(fn.name, source.file, fn.signature_span.line, "name does not parse into (type, metric, isa)")
                    )
                continue
            kind, metric, named_isa = axes
            if named_isa != isa:
                unmatched.append(
                    Unmatched(fn.name, source.file, fn.signature_span.line, f"names ISA {named_isa} in {source.file}")
                )
                continue
            cell = _cell(fn, kind, metric, isa, source, original)
            if cell.id in cells:
                unmatched.append(
                    Unmatched(fn.name, source.file, fn.signature_span.line, f"{cell.id} is already filled by {cells[cell.id].name}")
                )
                continue
            cells[cell.id] = cell

    _classify(cells, sources)
    _install_slots(cells, sources, unmatched)
    _grade_impls(cells)
    return Lattice(root, sources, cells, tuple(unmatched))


# MARK: - the passes -


def _is_kernel_shaped(name: str) -> bool:
    return any(name.startswith(f"{kind}_distance_") for kind in TYPES)


def _cell(fn: FunctionDef, kind: str, metric: str, isa: str, source: Source, original: str) -> Cell:
    return Cell(
        type=kind,
        metric=metric,
        isa=isa,
        name=fn.name,
        original=original,
        file=source.file,
        signature=fn.signature,
        signature_span=fn.signature_span,
        body_span=fn.body_span,
        kind="body",
        static=fn.static,
        inline=fn.inline,
        native=isa in NATIVE,
        slots=(),
        graded_via=(),
    )


def _classify(cells: dict[str, Cell], sources: dict[str, Source]) -> None:
    """Set each cell's `kind`. A wrapper is one whose body is a single call to this type's `_impl`."""
    for cell_id, cell in cells.items():
        if cell.metric == "l2_impl":
            cells[cell_id] = replace(cell, kind="impl")
            continue
        impl = cells.get(f"{cell.isa}/{cell.type}/l2_impl")
        if impl is None:
            continue
        masked = sources[cell.isa].scanned.masked
        if _one_call_to(masked[cell.body_span.start : cell.body_span.end]) == impl.name:
            cells[cell_id] = replace(cell, kind="wrapper")


def _one_call_to(masked_body: str) -> str | None:
    inner = masked_body.strip()
    if not (inner.startswith("{") and inner.endswith("}")):
        return None
    inner = inner[1:-1].strip()
    if inner.count(";") != 1 or not inner.endswith(";"):
        return None
    found = _RETURN_CALL.match(inner)
    return found.group(1) if found is not None else None


def _install_slots(cells: dict[str, Cell], sources: dict[str, Source], unmatched: list[Unmatched]) -> None:
    """Read each file's init function for the `dispatch_distance_table` slots it assigns."""
    by_name = {cell.name: cell_id for cell_id, cell in cells.items()}
    for source in sources.values():
        if source.init is None:
            continue
        init = next(fn for fn in source.scanned.functions if fn.name == source.init)
        body = source.scanned.masked[init.body_span.start : init.body_span.end]
        for metric_enum, type_enum, name in _SLOT.findall(body):
            cell_id = by_name.get(name)
            if cell_id is None:
                unmatched.append(
                    Unmatched(name, source.file, init.body_span.line, "assigned a table slot but defined nowhere in this file")
                )
                continue
            cell = cells[cell_id]
            cells[cell_id] = replace(cell, slots=cell.slots + ((metric_enum, type_enum),))


def _grade_impls(cells: dict[str, Cell]) -> None:
    """`graded_via` is a cell's own slots, or for an `_impl` the slots of the wrappers that call it."""
    for cell_id, cell in cells.items():
        if cell.kind != "impl":
            cells[cell_id] = replace(cell, graded_via=cell.slots)
            continue
        wrappers = sorted(
            (c for c in cells.values() if c.kind == "wrapper" and c.isa == cell.isa and c.type == cell.type),
            key=lambda c: c.body_span.start,
        )
        through: tuple[Slot, ...] = ()
        for wrapper in wrappers:
            through += wrapper.slots
        cells[cell_id] = replace(cell, graded_via=through)


def metric_enum(metric: str) -> str | None:
    """The `VECTOR_DISTANCE_*` name a metric is installed under, or `None` for `l2_impl`, which has no slot."""
    return _METRIC_ENUM.get(metric)


def type_enum(kind: str) -> str | None:
    """The `VECTOR_TYPE_*` name an element type is installed under."""
    return _TYPE_ENUM.get(kind)
