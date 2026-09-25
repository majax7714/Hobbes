"""G-hsr: the names a body invented, the bucket each falls in, and the failure class of the whole body.

Atlas-0 found the standard block *inventing from sand* — an absent name built of known stems gets a
confident answer. The intrinsic namespace is exactly that kind of sand (`_mm512_reduce_add_ps` exists,
`_mm512_reduce_max_epi8` does not, and both read the same), so this programme counts invented names
rather than folding them into "it did not compile".

**Where an invented name comes from.** The compiler and the linker already know: clang's `call to
undeclared function 'X'`, `use of undeclared identifier 'X'` and `unknown type name 'X'`, and ld's
``undefined reference to `X'``. Those four messages are the whole source. A name a body used that
resolves somewhere is not invented, however wrong the call is — that is `wrong`, not `invented`, and the
distinction is the point (§12.2's taxonomy).

**The buckets.** `intrinsic` — an `_mm…`, `__m…` or `__builtin_…` name, the sand Atlas-0 measured;
`in-repo` — a name the target itself would have had to define: kernel-shaped (`<type>_distance_…`) or
one that any of the target's files defines or `#define`s; `other` — everything else, which in practice
is libc and the model's own inventions.

**The failure class** is the per-body verdict the experiments report, in the order this module tests it:
a body that did not compile is `invented` when it named something that is nowhere and `compile` when it
did not; a body that compiled but whose slot the ISA's init did not install is `not-installed` and is
never read as a pass; then `wrong` (a bulk case, a crash or a timeout), `edge` (every bulk case passes
and an edge case does not), and `pass`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .cells import TYPES
from .scan import ScanError, scan

__all__ = [
    "BUCKETS",
    "CLASSES",
    "Invented",
    "inventory",
    "bucket",
    "invented",
    "classify",
]

#: Where an invented name came from, in the order §12.2 reads them.
BUCKETS = ("intrinsic", "in-repo", "other")

#: Every failure class a body can get, worst first — the order :func:`classify` tests them in.
CLASSES = ("invented", "compile", "not-installed", "wrong", "edge", "pass")

_UNDECLARED = (
    re.compile(r"call to undeclared function '([^']+)'"),
    re.compile(r"use of undeclared identifier '([^']+)'"),
    re.compile(r"unknown type name '([^']+)'"),
)
_UNDEFINED_REFERENCE = re.compile(r"undefined reference to [`']([^'`]+)'")

_INTRINSIC_PREFIXES = ("_mm", "__m", "__builtin_")


@dataclass(frozen=True)
class Invented:
    """One name that resolves nowhere, and the bucket it falls in."""

    name: str
    bucket: str

    def as_dict(self) -> dict:
        return {"name": self.name, "bucket": self.bucket}


def inventory(root: Path | str) -> frozenset[str]:
    """Every name the target's own C files define or `#define` — headers included.

    This is what `in-repo` is measured against: a name in here is one the target has, so a body that
    could not resolve it did not invent it (it was punched out, or the build lost it). A file that does
    not scan is skipped rather than raised on — the inventory is a bucket rule, not a fact about the
    graph.
    """
    root = Path(root)
    names: set[str] = set()
    for path in sorted(root.rglob("*")):
        if path.suffix not in (".c", ".h") or not path.is_file():
            continue
        try:
            scanned = scan(path.read_text(encoding="utf-8"))
        except (ScanError, OSError, UnicodeDecodeError):
            continue
        names.update(fn.name for fn in scanned.functions)
        names.update(scanned.defines)
    return frozenset(names)


def bucket(name: str, known: frozenset[str] | set[str] = frozenset()) -> str:
    """Which of :data:`BUCKETS` *name* falls in, given the target's inventory."""
    if name.startswith(_INTRINSIC_PREFIXES):
        return "intrinsic"
    if _kernel_shaped(name) or name in known:
        return "in-repo"
    return "other"


def _kernel_shaped(name: str) -> bool:
    return any(name.startswith(f"{kind}_distance_") for kind in TYPES)


def invented(outputs: list[str] | tuple[str, ...], known: frozenset[str] | set[str] = frozenset()) -> tuple[Invented, ...]:
    """The invented names in the compiler and linker output, deduplicated, in the order they appear."""
    seen: dict[str, Invented] = {}
    for output in outputs:
        for pattern in (*_UNDECLARED, _UNDEFINED_REFERENCE):
            for name in pattern.findall(output or ""):
                if name not in seen:
                    seen[name] = Invented(name, bucket(name, known))
    return tuple(seen.values())


def classify(
    *,
    compiled: bool,
    invented_names: tuple[Invented, ...] | list[Invented] = (),
    installed: bool = True,
    crashed: bool = False,
    bulk_failed: int = 0,
    edge_failed: int = 0,
) -> str:
    """The failure class of one body. See the module docstring for the order and why it is that order."""
    if not compiled:
        return "invented" if invented_names else "compile"
    if not installed:
        return "not-installed"
    if crashed or bulk_failed:
        return "wrong"
    if edge_failed:
        return "edge"
    return "pass"
