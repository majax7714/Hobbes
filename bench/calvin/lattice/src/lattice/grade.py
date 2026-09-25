"""The graders, run end to end: punch, fill, compile, link, run the differential, and classify.

One entry is `{"id", "cell", "body"}`, where `body` is a body's text (`{` … `}`) or the word `"gold"`.
:func:`grade` returns one JSON-able result per entry, in the order they came, and never raises for a
body's fault: a body that does not balance its braces is a `compile` result with the reason, because a
truncated generation is a fact about the model, not an exception for the harness.

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

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import build, diff, feedback, holes, hsr, run
from .cells import Lattice, Slot, UnknownCell
from .cells import build as build_lattice
from .scan import ScanError, scan

__all__ = [
    "DIAGNOSTIC_LIMIT",
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
    :func:`_one` writes it without compiling anything.
    """
    found: dict[str, None] = {}
    for entry in entries:
        try:
            cell = lattice.get(entry.get("cell", ""))
        except UnknownCell:
            continue
        if cell.native and cell.graded_via:
            found[cell.isa] = None
    return sorted(found)


# MARK: - one entry -


def _one(bench: Bench, entry: dict, known: frozenset[str]) -> dict:
    result = {
        "id": entry.get("id"),
        "cell": entry.get("cell"),
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

    source = bench.root / cell.file
    original = source.read_text(encoding="utf-8")
    try:
        source.write_text(filled, encoding="utf-8")
        _grade_filled(bench, cell, filled, gold, known, result)
    finally:
        source.write_text(original, encoding="utf-8")
    result["feedback"] = feedback.build(result)
    return result


def _grade_filled(bench: Bench, cell, filled: str, gold: str, known: frozenset[str], result: dict) -> None:
    result["reg"] = _reg(filled, gold)

    ok, compilations, linked = bench.build_all(cell.isa)
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

    if not cell.native:
        result["class"] = "not-installed"
        result["reason"] = f"{cell.isa} is not native on this box, so no slot of it can be read"
        return
    if not cell.graded_via:
        result["class"] = "not-installed"
        result["reason"] = f"{cell.id} is reached through no table slot, so the differential cannot see it"
        return

    # Unreachable through :func:`grade_with_references`, which asks for exactly the ISAs that get here.
    # It is checked anyway because the wrong answer is a *silent* one: without the reference every case
    # would fall back to the scalar, and the gold-referenced cases would quietly fail again.
    reference = bench.references.get(cell.isa)
    if reference is None:
        raise GoldUnavailable(f"no gold reference for {cell.isa}; it is built before the first body is filled in")
    ran = diff.run(
        linked.product,
        cell.isa,
        list(cell.graded_via),
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
        result["reason"] = f"init_distance_functions_{cell.isa}() returned false: the ISA is not in this build"
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
