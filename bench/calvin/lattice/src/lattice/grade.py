"""The graders, run end to end: punch, fill, compile, link, run the differential, and classify.

One entry is `{"id", "cell", "body"}`, where `body` is a body's text (`{` … `}`) or the word `"gold"`.
:func:`grade` returns one JSON-able result per entry, in the order they came, and never raises for a
body's fault: a body that does not balance its braces is a `compile` result with the reason, because a
truncated generation is a fact about the model, not an exception for the harness.

**The staged copy is made once and reused.** Each entry writes its filled file over the staged tree, is
graded, and the file is put back. That is not only cheaper — it is what makes the object cache work,
since the `-I` flags (and so the cache key) would differ under a per-entry directory, and five of the six
translation units are the same bytes for every entry in a run.

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
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import build, diff, feedback, holes, hsr, run
from .cells import Lattice, UnknownCell
from .cells import build as build_lattice
from .scan import ScanError, scan

__all__ = ["DIAGNOSTIC_LIMIT", "Bench", "grade", "stage"]

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
    run.require_container(allow_host=allow_host)
    bench = Bench.open(target, workdir, compiler=compiler, timeout=timeout)
    known = hsr.inventory(bench.root)
    results: list[dict] = []
    for entry in entries:
        results.append(_one(bench, entry, known))
    return results


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

    ran = diff.run(linked.product, cell.isa, list(cell.graded_via), timeout=bench.timeout)
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
