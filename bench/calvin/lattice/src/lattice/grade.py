"""The graders, run end to end: punch, fill, compile, link, run the differential, and classify.

One entry is `{"id", "cell", "body"}`, where `body` is a body's text (`{` … `}`) or the word `"gold"`.
:func:`grade` returns one JSON-able result per entry, in the order they came, and never raises for a
body's fault: a body that does not balance its braces is a `compile` result with the reason, because a
truncated generation is a fact about the model, not an exception for the harness.

**Two more entry forms, both E4's** (`calvin-experiments.md` §6). At rung L1 the whole file is held out, so
a hole is any of its definitions and not only a lattice cell:

| form | fills | graded over |
|---|---|---|
| `{"id", "cell", "body"}` | that cell's body | the cell's `graded_via` slots — unchanged, byte for byte |
| `{"id", "unit", "isa", "body"}` | that **definition's** body | a cell: as above. A helper: the union of the `graded_via` slots of every cell whose gold body reaches it, and :data:`UNEXERCISED` where no cell does. The init: every slot the file installs |
| `{"id", "isa", "bodies": {name: body}}` | **several** definitions at once | every slot the file installs — E4's file-level build |

Every one of them fills into the **gold** file and puts it back afterwards, so a unit's result is its own:
a wrong helper fails on its own row and the cells that call it are still graded against the target's own
(E4-d, gold substitution). The unit forms read the file's definitions and the call edges between them
through :mod:`lattice.e4`, which owns that reading; nothing here duplicates its token rule.

**The staged copy is made once and reused.** Each entry writes its filled file over the staged tree, is
graded, and the file is put back. That is not only cheaper — it is what makes the object cache work,
since the `-I` flags (and so the cache key) would differ under a per-entry directory, and five of the six
translation units are the same bytes for every entry in a run.

**The gold references come first.** Some cases are graded against the cell's own gold and not against the
scalar (`diff.reference_for`), so before any body is filled in — while the staged copy is still the
target's own bytes — :func:`grade` builds the gold once and runs its driver over every slot each ISA the
run touches installs. The records are cached for the run (:class:`GoldReference`), together with the cases
where that gold and the scalar disagree, which are a fact about the target and are reported as one.

**Containment.** :func:`grade` asks :mod:`lattice.run` before it compiles anything. `allow_host` is this
package's tests on its own fixture and nothing else.

Each result carries what the experiments read and what a retry is built from:

| field | what |
|---|---|
| `class` | one of `hsr.CLASSES` |
| `diagnostics` | the first 20 clang messages, paths relative to the target's root |
| `invented` | the names that resolve nowhere, each with its bucket |
| `bulk`, `edge` | `{"passed", "failed"}` summed over the cell's slots |
| `first_failure` | the first case that disagreed: its name, `n`, seed, expected and got |
| `slots` | per slot: installed, the counts, the worst relative error |
| `reg` | **G-reg** — the init function's slot assignments in the filled file equal the gold's |
| `seconds` | compile, link, run and total |
| `feedback` | the ≤1,500 characters a retry is shown (`feedback.py`) |

Each entry in `slots` also carries `graded`, the case counts per reference, and `first_failure` names the
`reference` the case that failed was graded against.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import build, diff, feedback, holes, hsr, run
from .cells import NATIVE, Lattice, Slot, UnknownCell
from .cells import build as build_lattice
from .scan import ScanError, scan

__all__ = [
    "DIAGNOSTIC_LIMIT",
    "UNEXERCISED",
    "Bench",
    "GoldReference",
    "GoldUnavailable",
    "grade",
    "grade_with_references",
    "installed_slots",
    "stage",
]

#: How many clang messages a result keeps. The rest are counted, never carried.
DIAGNOSTIC_LIMIT = 20

#: What a unit no table slot exercises is graded (E4-d): it compiled, and no cell's gold body reaches it,
#: so the differential has nothing to read it through. It sits beside `hsr.CLASSES` — the graders' own six
#: — as `e1.PARAM` sits beside `hsr.BUCKETS`, and is a fact about the **unit** rather than a verdict on the
#: body: reading it as `not-installed` would put it among the bodies that lost their slot, and reading it
#: as a pass would credit a body nothing ran.
UNEXERCISED = "unexercised"

#: What a grading run copies out of the target: the kernels, their headers, and fp16's. Nothing else is
#: needed, and the real target's `libs/` holds a 263k-line `sqlite3.c`.
STAGED = (("src", "src"), ("libs/fp16", "libs/fp16"))

#: Where the generated driver lands inside the staged copy — outside `src/`, so `distance-*.c` globs and
#: the `-I` paths are the target's own.
DRIVER = "driver/lattice_driver.c"

_SLOT = re.compile(
    r"dispatch_distance_table\s*\[\s*VECTOR_DISTANCE_(\w+)\s*\]\s*"
    r"\[\s*VECTOR_TYPE_(\w+)\s*\]\s*=\s*([A-Za-z_]\w*)\s*;"
)


class GoldUnavailable(Exception):
    """The gold build did not produce a reference for an ISA.

    Its own type, not an `OSError` or a `RuntimeError` (P10, ADR-036): every other failure this module
    reports is a fact about a *body*, and this one is not. The staged copy is the target's own bytes, so a
    gold that does not compile, does not link or dies in the differential is the harness's fault or the
    target's, and grading a body against it would be measuring neither.
    """


@dataclass(frozen=True)
class GoldReference:
    """One ISA's gold answers, and where they disagree with the scalar reference.

    `got` is `{(slot, case): the gold's answer}` over every slot that ISA installs — the mapping
    `diff.run` grades a candidate's gold-referenced cases against. `disagreements` is every case where the
    gold and the scalar disagree at the slot's tolerance: that is the target disagreeing with itself, it is
    reported and not smoothed away, and it is why the rule in `diff.reference_for` exists.
    """

    isa: str
    available: bool
    slots: tuple[Slot, ...]
    got: dict[tuple[str, str], object]
    disagreements: tuple[dict, ...]


def installed_slots(lattice: Lattice, isa: str) -> tuple[Slot, ...]:
    """Every `dispatch_distance_table` slot that ISA's init function assigns, in the file's order.

    The gold reference is run over all of them rather than over one cell's `graded_via`, so one gold run
    serves every entry of that ISA in a grading run.
    """
    return tuple(dict.fromkeys(slot for cell in lattice.by_isa(isa) for slot in cell.slots))


def stage(target: Path | str, dest: Path | str) -> Path:
    """Copy the target's kernels and fp16 into *dest*, and return the staged root."""
    target, dest = Path(target), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for source, into in STAGED:
        (dest / into).parent.mkdir(parents=True, exist_ok=True)
        if (dest / into).exists():
            shutil.rmtree(dest / into)
        shutil.copytree(target / source, dest / into)
    return dest


@dataclass
class Bench:
    """One grading run's staged copy, object cache and linked-in driver.

    Built once per :func:`grade` call and reused for every entry: see the module docstring on why the
    staged root has to be stable.
    """

    lattice: Lattice
    root: Path
    workdir: Path
    cache: build.ObjectCache
    compiler: str | None = None
    timeout: int = diff.TIMEOUT
    references: dict[str, GoldReference] = field(default_factory=dict)
    gold_exe: Path | None = None

    @classmethod
    def open(cls, target: Path | str, workdir: Path | str, *, compiler: str | None = None, timeout: int = diff.TIMEOUT) -> "Bench":
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        root = stage(target, workdir / "target")
        (root / DRIVER).parent.mkdir(parents=True, exist_ok=True)
        (root / DRIVER).write_text(diff.driver_source(), encoding="utf-8")
        return cls(
            lattice=build_lattice(target),
            root=root,
            workdir=workdir,
            cache=build.ObjectCache(workdir / "objects"),
            compiler=compiler,
            timeout=timeout,
        )

    def build_all(self, isa_of_changed: str) -> tuple[bool, list[build.Compilation], build.Compilation | None]:
        """Compile the six kernel files and the driver, then link. Unchanged objects come from the cache."""
        compilations: list[build.Compilation] = []
        objects: list[Path] = []
        for isa in ("cpu", "sse2", "avx2", "avx512", "neon", "rvv"):
            done = build.compile_file(
                self.root, f"src/distance-{isa}.c", isa,
                out_dir=self.cache.directory, compiler=self.compiler, cache=self.cache,
            )
            compilations.append(done)
            if not done.ok:
                # Only the file the body went into may legitimately fail; any other is the harness's.
                return False, compilations, None
            objects.append(done.product)
        driver = build.compile_file(
            self.root, DRIVER, "cpu", out_dir=self.cache.directory, compiler=self.compiler, cache=self.cache
        )
        compilations.append(driver)
        if not driver.ok:
            return False, compilations, None
        objects.append(driver.product)
        exe = self.workdir / f"driver-{isa_of_changed}.bin"
        linked = build.link(objects, exe, root=self.root, compiler=self.compiler)
        return linked.ok, compilations, linked

    def scrub(self, text: str) -> str:
        """Strip the staged root from a message, so nothing carries an absolute path."""
        return text.replace(f"{self.root}/", "").replace(str(self.root), "")

    # MARK: - the gold reference -

    def reference(self, isa: str) -> GoldReference:
        """One ISA's :class:`GoldReference`, built on the first ask and cached for the run.

        **Only callable while the staged copy is the gold.** :func:`grade` asks for every ISA it will
        touch before it fills the first body; after that the tree has been written to and put back, and
        asking again would compile whatever was last restored rather than what the target ships.
        """
        found = self.references.get(isa)
        if found is None:
            found = self._reference(isa)
            self.references[isa] = found
        return found

    def _reference(self, isa: str) -> GoldReference:
        slots = installed_slots(self.lattice, isa)
        ran = diff.run(self._gold_exe(), isa, list(slots), timeout=self.timeout)
        if ran.crashed:
            raise GoldUnavailable(
                f"the gold's differential for {isa} did not finish: "
                + (f"timed out after {self.timeout}s" if ran.timed_out else f"signal {ran.signal}" if ran.signal else f"exit {ran.returncode}")
            )
        if not ran.available:
            return GoldReference(isa, False, slots, {}, ())
        got: dict[tuple[str, str], object] = {}
        disagreements: list[dict] = []
        for record in ran.records:
            if "case" not in record:
                continue
            got[(record["slot"], record["case"])] = record["got"]
            type_, metric = diff.pair_of_slot(record["slot"])
            rtol, atol = diff.tolerance(type_, metric)
            if not diff.compare(record["ref"], record["got"], rtol, atol):
                disagreements.append(
                    {
                        "isa": isa,
                        "slot": record["slot"],
                        "case": record["case"],
                        "kind": record["kind"],
                        "n": record["n"],
                        "seed": record["seed"],
                        "scalar": record["ref"],
                        "gold": record["got"],
                        "reference": diff.reference_for(record["case"], record["ref"]),
                    }
                )
        return GoldReference(isa, True, slots, got, tuple(disagreements))

    def _gold_exe(self) -> Path:
        """The gold build's driver, linked once: the objects do not depend on which ISA is being read."""
        if self.gold_exe is not None:
            return self.gold_exe
        ok, compilations, linked = self.build_all("gold")
        if not ok or linked is None:
            output = "\n".join(self.scrub(c.output) for c in (*compilations, linked) if c is not None)
            raise GoldUnavailable(f"the target's own tree did not build:\n{output[:2000]}")
        self.gold_exe = linked.product
        return self.gold_exe


def grade(
    target: Path | str,
    entries: list[dict] | tuple[dict, ...],
    workdir: Path | str,
    *,
    allow_host: bool = False,
    compiler: str | None = None,
    timeout: int = diff.TIMEOUT,
) -> list[dict]:
    """Grade every entry against *target*, in a staged copy under *workdir*. One result per entry."""
    results, _ = grade_with_references(
        target, entries, workdir, allow_host=allow_host, compiler=compiler, timeout=timeout
    )
    return results


def grade_with_references(
    target: Path | str,
    entries: list[dict] | tuple[dict, ...],
    workdir: Path | str,
    *,
    allow_host: bool = False,
    compiler: str | None = None,
    timeout: int = diff.TIMEOUT,
) -> tuple[list[dict], dict[str, GoldReference]]:
    """:func:`grade`, and the gold references it built as well, by ISA.

    The self-test reads them for its `disagreements`: what the target disagrees with itself on is a fact
    about the target, and it belongs in the report rather than inside the grader that had to work around it.
    """
    run.require_container(allow_host=allow_host)
    bench = Bench.open(target, workdir, compiler=compiler, timeout=timeout)
    known = hsr.inventory(bench.root)
    # Before the first body is written into the staged tree, while it is still the target's own bytes.
    for isa in _isas_of(bench.lattice, entries):
        bench.reference(isa)
    results: list[dict] = []
    for entry in entries:
        results.append(_one(bench, entry, known))
    return results, dict(bench.references)


def _isas_of(lattice: Lattice, entries: list[dict] | tuple[dict, ...]) -> list[str]:
    """The ISAs a run's entries are graded on: native, reached through a slot, each once, in a fixed order.

    An entry naming a cell this lattice does not have needs no gold — it is a result with a reason, and
    :func:`_one` writes it without compiling anything. A **unit** or **file** entry names its ISA itself,
    and asks for that ISA's gold whenever the file is one this box runs: a lone unexercised helper then
    pays for a gold build it does not read, which is cheaper than working out here what it will need.
    """
    found: dict[str, None] = {}
    for entry in entries:
        if entry.get("unit") is not None or entry.get("bodies") is not None:
            isa = entry.get("isa")
            if isa in NATIVE and isa in lattice.sources and installed_slots(lattice, isa):
                found[isa] = None
            continue
        try:
            cell = lattice.get(entry.get("cell", ""))
        except UnknownCell:
            continue
        if cell.native and cell.graded_via:
            found[cell.isa] = None
    return sorted(found)


# MARK: - one entry -


def _one(bench: Bench, entry: dict, known: frozenset[str]) -> dict:
    """One entry of whichever form it is. The cell form is the one below and is unchanged."""
    if entry.get("bodies") is not None:
        return _file_entry(bench, entry, known)
    if entry.get("unit") is not None:
        return _unit_entry(bench, entry, known)
    return _cell_entry(bench, entry, known)


def _blank(entry: dict, cell: str | None) -> dict:
    """The result every form starts from: the fields the experiments read, all of them said."""
    return {
        "id": entry.get("id"),
        "cell": cell,
        "class": "compile",
        "reason": None,
        "diagnostics": [],
        "diagnostic_count": 0,
        "invented": [],
        "bulk": {"passed": 0, "failed": 0},
        "edge": {"passed": 0, "failed": 0},
        "first_failure": None,
        "slots": [],
        "reg": None,
        "seconds": {"compile": 0.0, "link": 0.0, "run": 0.0, "total": 0.0},
        "feedback": "",
    }


def _cell_entry(bench: Bench, entry: dict, known: frozenset[str]) -> dict:
    result = _blank(entry, entry.get("cell"))
    try:
        cell = bench.lattice.get(entry["cell"])
    except UnknownCell:
        result["reason"] = f"no cell {entry.get('cell')!r} in this lattice"
        result["feedback"] = feedback.build(result)
        return result

    gold = bench.lattice.text(cell)
    body = holes.gold_body(gold, cell) if entry.get("body") == "gold" else entry.get("body", "")
    try:
        filled = holes.fill(holes.punch(gold, cell), body)
    except (holes.UnbalancedBody, holes.NoHole) as refusal:
        result["reason"] = str(refusal)
        result["feedback"] = feedback.build(result)
        return result

    _in_the_staged_file(
        bench, cell.file, filled, gold, known, result,
        isa=cell.isa, native=cell.native, slots=cell.graded_via, label=cell.id,
    )
    result["feedback"] = feedback.build(result)
    return result


# MARK: - E4's two forms: a unit, and a whole file -


def _e4():
    """E4's reading of a file's definitions and the calls between them, imported on use.

    Not at the top: the unit forms are E4's (`calvin-experiments.md` §6), most grading runs carry none,
    and the token rule that orders the units is written once — there — rather than twice.
    """
    from . import e4

    return e4


def _unit_entry(bench: Bench, entry: dict, known: frozenset[str]) -> dict:
    """One definition of one file, filled into the gold and graded over the slots that exercise it."""
    isa, name = entry.get("isa"), entry.get("unit")
    found, refusal = _units_of(bench, isa)
    if refusal is not None:
        result = _blank(entry, None)
        result.update({"unit": name, "isa": isa, "reason": refusal, "feedback": refusal})
        return result

    unit = found.get(name)
    if unit is None:
        result = _blank(entry, None)
        reason = f"no definition named {name!r} in {bench.lattice.sources[isa].file}"
        result.update({"unit": name, "isa": isa, "reason": reason, "feedback": reason})
        return result

    if unit.kind == "cell":
        # a cell is graded exactly as the cell form grades it; the unit fields ride beside the result
        result = _cell_entry(bench, {"id": entry.get("id"), "cell": unit.cell, "body": entry.get("body")}, known)
        result.update(
            {
                "unit": name,
                "unit_kind": "cell",
                "isa": isa,
                "graded_over": [list(slot) for slot in bench.lattice.get(unit.cell).graded_via],
            }
        )
        return result

    source = bench.lattice.sources[isa]
    result = _blank(entry, None)
    result.update({"unit": name, "unit_kind": unit.kind, "isa": isa})
    gold = source.text
    body = holes.gold_body(gold, unit) if entry.get("body") == "gold" else entry.get("body", "")
    try:
        filled = holes.fill(holes.punch(gold, unit), body)
    except (holes.UnbalancedBody, holes.NoHole) as bad:
        result["reason"] = str(bad)
        result["feedback"] = feedback.build(result)
        return result

    slots = _unit_slots(bench.lattice, isa, unit)
    result["graded_over"] = [list(slot) for slot in slots]
    _in_the_staged_file(
        bench, source.file, filled, gold, known, result,
        isa=isa, native=isa in NATIVE, slots=slots, label=name,
        no_slots=(
            UNEXERCISED,
            f"no cell of {source.file} reaches {name}, so no table slot exercises it",
        )
        if unit.kind == "helper"
        else None,
    )
    result["feedback"] = feedback.build(result)
    return result


def _unit_slots(lattice: Lattice, isa: str, unit) -> tuple[Slot, ...]:
    """The slots a unit is graded over: its own, the union of those that reach it, or the file's all.

    A cell keeps `graded_via`, which already sends an `_impl` through its wrappers. A **helper** takes the
    union of `graded_via` over every cell whose gold body reaches it, in the file's order, so a body is
    read through every slot that runs it and through none that does not. The **init** takes every slot the
    file installs: it is the only unit whose own job is to install them.
    """
    if unit.kind == "cell":
        return lattice.get(unit.cell).graded_via
    if unit.kind == "init":
        return installed_slots(lattice, isa)
    return tuple(
        dict.fromkeys(
            slot for cell in _e4().reaching_cells(lattice, isa, unit.name) for slot in cell.graded_via
        )
    )


def _file_entry(bench: Bench, entry: dict, known: frozenset[str]) -> dict:
    """E4's file-level build: several definitions filled into the gold file at once, graded as a file."""
    isa = entry.get("isa")
    bodies = dict(entry.get("bodies") or {})
    found, refusal = _units_of(bench, isa)
    result = _blank(entry, None)
    result.update({"isa": isa, "units": sorted(bodies)})
    if refusal is not None:
        result.update({"reason": refusal, "feedback": refusal})
        return result

    unknown = sorted(name for name in bodies if name not in found)
    if unknown:
        reason = f"{bench.lattice.sources[isa].file} defines no {', '.join(unknown)}"
        result.update({"reason": reason, "feedback": reason})
        return result

    source = bench.lattice.sources[isa]
    gold = source.text
    try:
        filled = _e4().fill_units(gold, [(found[name], body) for name, body in bodies.items()])
    except (holes.UnbalancedBody, holes.NoHole) as bad:
        result["reason"] = str(bad)
        result["feedback"] = feedback.build(result)
        return result

    result["filled_sha256"] = hashlib.sha256(filled.encode("utf-8")).hexdigest()
    slots = installed_slots(bench.lattice, isa)
    result["graded_over"] = [list(slot) for slot in slots]
    _in_the_staged_file(
        bench, source.file, filled, gold, known, result,
        isa=isa, native=isa in NATIVE, slots=slots, label=source.file,
    )
    result["feedback"] = feedback.build(result)
    return result


def _units_of(bench: Bench, isa: str | None) -> tuple[dict, str | None]:
    """The file's definitions by name, or the reason there are none to read."""
    if isa not in bench.lattice.sources:
        return {}, f"no file for ISA {isa!r} in this lattice"
    try:
        return {unit.name: unit for unit in _e4().units(bench.lattice, isa)}, None
    except _e4().DuplicateDefinition as refusal:
        return {}, str(refusal)


# MARK: - the staged file, and the graders over it -


def _in_the_staged_file(
    bench: Bench,
    file: str,
    filled: str,
    gold: str,
    known: frozenset[str],
    result: dict,
    **how,
) -> None:
    """Write *filled* over the staged copy's *file*, grade it, and put the gold back whatever happened."""
    staged = bench.root / file
    original = staged.read_text(encoding="utf-8")
    try:
        staged.write_text(filled, encoding="utf-8")
        _grade_filled(bench, filled, gold, known, result, **how)
    finally:
        staged.write_text(original, encoding="utf-8")


def _grade_filled(
    bench: Bench,
    filled: str,
    gold: str,
    known: frozenset[str],
    result: dict,
    *,
    isa: str,
    native: bool,
    slots: tuple[Slot, ...],
    label: str,
    no_slots: tuple[str, str] | None = None,
) -> None:
    """G-reg, G-compile, G-hsr and G-diff over *slots*, whatever the hole was.

    *label* names the hole in the reasons — a cell id, a definition's name, a file. *no_slots* is the
    `(class, reason)` for a hole no slot reaches, and defaults to `not-installed`, which is what a cell
    with no slot has always been read as; E4 passes :data:`UNEXERCISED` for a helper, where the empty
    union is a fact about the unit and not about its body.
    """
    result["reg"] = _reg(filled, gold)

    ok, compilations, linked = bench.build_all(isa)
    outputs = [bench.scrub(c.output) for c in compilations]
    diagnostics = [d for c in compilations for d in c.diagnostics]
    if linked is not None:
        outputs.append(bench.scrub(linked.output))
        diagnostics += list(linked.diagnostics)
    result["seconds"]["compile"] = round(sum(c.seconds for c in compilations), 3)
    result["seconds"]["link"] = round(linked.seconds if linked is not None else 0.0, 3)
    result["diagnostic_count"] = len(diagnostics)
    result["diagnostics"] = [d.as_dict() for d in diagnostics[:DIAGNOSTIC_LIMIT]]
    result["invented"] = [i.as_dict() for i in hsr.invented(outputs, known)]
    result["link_errors"] = _link_errors(outputs) if not ok else []

    if not ok:
        result["class"] = hsr.classify(compiled=False, invented_names=result["invented"])
        result["reason"] = "the file did not compile" if linked is None else "the objects did not link"
        result["seconds"]["total"] = round(result["seconds"]["compile"] + result["seconds"]["link"], 3)
        return

    if not native:
        result["class"] = "not-installed"
        result["reason"] = f"{isa} is not native on this box, so no slot of it can be read"
        return
    if not slots:
        result["class"], result["reason"] = no_slots or (
            "not-installed",
            f"{label} is reached through no table slot, so the differential cannot see it",
        )
        return

    # Unreachable through :func:`grade_with_references`, which asks for exactly the ISAs that get here.
    # It is checked anyway because the wrong answer is a *silent* one: without the reference every case
    # would fall back to the scalar, and the gold-referenced cases would quietly fail again.
    reference = bench.references.get(isa)
    if reference is None:
        raise GoldUnavailable(f"no gold reference for {isa}; it is built before the first body is filled in")
    ran = diff.run(
        linked.product,
        isa,
        list(slots),
        timeout=bench.timeout,
        gold=reference.got if reference.available else None,
    )
    result["seconds"]["run"] = round(ran.seconds, 3)
    result["seconds"]["total"] = round(
        result["seconds"]["compile"] + result["seconds"]["link"] + result["seconds"]["run"], 3
    )
    result["slots"] = [
        {
            "slot": c.slot,
            "installed": c.installed,
            "bulk": {"passed": c.bulk_passed, "failed": c.bulk_failed},
            "edge": {"passed": c.edge_passed, "failed": c.edge_failed},
            "graded": {"scalar": c.scalar_cases, "gold": c.gold_cases},
            "worst": c.worst,
        }
        for c in ran.comparisons
    ]
    result["bulk"] = {
        "passed": sum(c.bulk_passed for c in ran.comparisons),
        "failed": sum(c.bulk_failed for c in ran.comparisons),
    }
    result["edge"] = {
        "passed": sum(c.edge_passed for c in ran.comparisons),
        "failed": sum(c.edge_failed for c in ran.comparisons),
    }
    result["first_failure"] = next((c.first_failure for c in ran.comparisons if c.first_failure), None)

    # A crash is read before anything else the run did or did not say: a body that dies mid-differential
    # has told us it is wrong, and the records it left behind are not evidence that its ISA was absent.
    if ran.crashed:
        result["class"] = "wrong"
        result["reason"] = (
            f"the differential did not finish inside {bench.timeout}s" if ran.timed_out
            else f"the differential died on {ran.signal}" if ran.signal is not None
            else f"the differential exited {ran.returncode}"
        )
        return

    if not ran.available:
        result["class"] = "not-installed"
        result["reason"] = f"init_distance_functions_{isa}() returned false: the ISA is not in this build"
        return

    installed = all(c.installed for c in ran.comparisons)
    if not installed:
        missing = ", ".join(c.slot for c in ran.comparisons if not c.installed)
        result["reason"] = f"the init left {missing} pointing at the scalar table"

    result["class"] = hsr.classify(
        compiled=True,
        invented_names=result["invented"],
        installed=installed,
        crashed=False,
        bulk_failed=result["bulk"]["failed"],
        edge_failed=result["edge"]["failed"],
    )


def _link_errors(outputs: list[str]) -> list[str]:
    """The linker's own lines, which carry no `file:line:col` for the diagnostics parser to read."""
    found: list[str] = []
    for output in outputs:
        for line in output.splitlines():
            if "undefined reference to" in line or "ld: " in line or "linker command failed" in line:
                found.append(line.strip()[:200])
    return found[:DIAGNOSTIC_LIMIT]


def _reg(filled: str, gold: str) -> bool:
    """**G-reg**: the filled file's init function assigns exactly the gold's table slots, in order.

    Read off the text (the cell map's own rule), not off a compile: a body that reassigns a slot, or an
    init the generation moved, shows up here and nowhere else.
    """
    try:
        return _assignments(filled) == _assignments(gold)
    except ScanError:
        return False


def _assignments(text: str) -> list[tuple[str, str, str]]:
    scanned = scan(text)
    init = next((fn for fn in scanned.functions if fn.name.startswith("init_distance_functions")), None)
    if init is None:
        return []
    body = scanned.masked[init.body_span.start : init.body_span.end]
    return _SLOT.findall(body)
