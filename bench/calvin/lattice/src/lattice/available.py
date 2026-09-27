"""**Availability** (D-12 a): which intrinsics a kernel file can actually use, read off its own includes.

D-11's record said the helpers that did not move copy the wider sibling's shape, and the
pre-registration counted the classes: of the invented intrinsics, 56% are a width-rename of an intrinsic
in the unit's own shots, 34% are declared nowhere at all, and 9% are real but not available in the file
the student is writing. So the fact S-3h serves is not "does this name exist" but **"can *this* file use
it"**, and that question is only answerable the way the grader meets it.

**The rule, as the pre-registration words it.** An intrinsic is *available* in a file when both hold:

1. the file's own text, **preprocessed under the grader's flags**, declares it — a function definition or
   a `#define`;
2. **every feature it requires is enabled** under those flags, read from `clang -dM`.

A function's features are its `__target__("…")` entries; an entry spelled `no-…` is a statement that the
feature is *off*, not a requirement, so it is dropped. A **macro** has no attribute of its own and takes
its **header's** features: the most common feature tuple among the functions that header (by line marker)
defines. A name whose header defines no function at all — the target's own file among them — has an
**empty** tuple, which every flag set satisfies.

Why this and not the intrinsic index. :mod:`lattice.intrinsics` reads clang's headers as *text*: it sees
both arms of every `#if` and knows nothing of `-mavx2`. That is the right instrument for "what names
exist", and the wrong one here — sse2's file includes only `<emmintrin.h>`, so `_mm_shuffle_epi8` is
**undeclared** there and the index would call it real. This module asks the compiler instead, at the
flags the body will be compiled under, which is why :func:`build` runs in the image (ADR-092, C-64) and
:func:`parse` is pure over the two texts it produced.

**Rule R**, the pre-registered rename: a name not available here may still have a *form* that is. The
leading `_mm_`/`_mm256_`/`_mm512_` becomes this file's prefix, and every `128`/`256`/`512` written
directly after `si`, `ps` or `pd` becomes this file's width. The result counts only when it differs from
the name **and is itself available** — `_mm256_loadu_si256` → `_mm_loadu_si128` in sse2, while
`_mm256_extractf128_ps` has no form there and is said to have none.

**What this reads wrongly rather than refuses.** It is a line scanner over `clang -E -dD` output, not a
second front end: a declaration whose name is more than one line below its attributes is missed; a name
two headers declare keeps the **first** one's entry, in the output's own order; and a header whose
functions carry two feature tuples in equal number gives its macros the lexicographically first, which is
a tie-break and not a fact. None of the three can make an unavailable name read as available.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from . import run as sandbox
from .build import ISA_FLAGS, cc
from .cells import ISAS, NATIVE
from .e1 import head

__all__ = [
    "INCLUDES",
    "ISA_PREFIX",
    "ISA_WIDTH",
    "OPTIMISE",
    "PreprocessFailed",
    "build",
    "clang_version",
    "feature_macro",
    "kernel_file",
    "load",
    "names_for",
    "native",
    "parse",
    "preprocess_flags",
    "record_meta",
    "rename",
]

#: The grader's own optimisation level and the target's two include directories, **relative** — clang runs
#: with the target's root as its working directory, so a record carries no path of this box. This is the
#: command `tests/fixtures/preprocessed/PROVENANCE.md` cut its excerpts with, per ISA flags from
#: `build.ISA_FLAGS`, which is how `build.flags_for` compiles a body.
OPTIMISE = "-O2"
INCLUDES = ("-Isrc", "-Ilibs")

#: Rule R's two tables: the prefix each file writes, and the vector width it writes.
ISA_PREFIX = {"sse2": "_mm_", "avx2": "_mm256_", "avx512": "_mm512_"}
ISA_WIDTH = {"sse2": "128", "avx2": "256", "avx512": "512"}

#: The namespace this keeps, `intrinsics`' own: the SIMD intrinsics and the scalar conversions beside them.
_KEPT = re.compile(r"\A_(?:mm|cvt)")

#: `clang -E`'s line marker: `# 590 "/usr/lib/llvm-18/lib/clang/18/include/tmmintrin.h" 3`.
_MARKER = re.compile(r'\A#\s*\d+\s+"([^"]*)"')

#: A `#define` in `-dD` (or `-dM`) output. Function-like or not: both declare the name.
_DEFINE = re.compile(r"\A#\s*define\s+([A-Za-z_]\w*)")

#: The features a function requires, as clang's expanded attribute writes them.
_TARGET = re.compile(r'__target__\s*\(\s*"([^"]*)"\s*\)')

_ATTRIBUTE = re.compile(r"\b__attribute__\s*\(")

#: The declarator: the first identifier that a `(` follows, once the attributes are gone.
_DECLARATOR = re.compile(r"([A-Za-z_]\w*)\s*\(")

#: Rule R's width, only where `si`, `ps` or `pd` writes it — so `_mm256_extractf128_ps` keeps its `f128`,
#: which is a lane index and not the vector's width.
_WIDTH = re.compile(r"(?<=si|ps|pd)(?:128|256|512)")
_PREFIX = re.compile(r"\A_mm(?:256|512)?_")


class PreprocessFailed(Exception):
    """clang could not preprocess the file, or the file is not there.

    Its own type (P10, ADR-036) because the alternative is silence that reads as a fact: a `parse` over
    an empty text answers "nothing is declared here", which would mark every intrinsic in every shot
    unavailable and send the student a page of wrong advice.
    """


# MARK: - the rule, pure over the two texts -


def feature_macro(feature: str) -> str:
    """The predefined macro that says *feature* is on: `sse4.1` → `__SSE4_1__`, `avx512f` → `__AVX512F__`."""
    return "__" + feature.upper().replace(".", "_").replace("-", "_") + "__"


def parse(preprocessed: str, macros: str) -> dict[str, dict]:
    """Every intrinsic *preprocessed* declares, each with whether *macros* enables what it needs.

    *preprocessed* is `clang <flags> -E -dD <file>` and *macros* is `clang <flags> -dM -E -x c /dev/null`.
    Each entry is `{"available", "needs", "header"}`: the features the name requires (`no-…` entries
    dropped, a macro's taken from its header), the header the line marker in force named, and whether
    every one of those features has its macro defined. **A name this text does not declare is simply not
    in the answer** — absence is undeclared, which is the sse2 case D-12 exists for.
    """
    enabled = {found.group(1) for line in macros.splitlines() if (found := _DEFINE.match(line.strip()))}
    entries, per_header = _entries(preprocessed)

    found: dict[str, dict] = {}
    for name, needs, header in entries:
        if not _KEPT.match(name) or name in found:
            continue  # the first declaration owns the name, in the output's own order
        wanted = needs if needs is not None else _header_needs(per_header, header)
        found[name] = {
            "available": all(feature_macro(feature) in enabled for feature in wanted),
            "needs": list(wanted),
            "header": header,
        }
    return found


def _entries(preprocessed: str) -> tuple[list[tuple[str, tuple[str, ...] | None, str]], dict[str, Counter]]:
    """Every declaration in the output's own order, and each header's function feature tuples.

    A function carries its own `needs`; a macro carries `None`, because its features are its header's and
    a header's functions may be written **below** the macro (`_mm512_extracti32x4_epi32` is defined at
    `avx512fintrin.h:636` and that header's functions run from line 26 to the end of the file). So the
    header tally is finished before any macro is resolved.
    """
    lines = preprocessed.splitlines()
    entries: list[tuple[str, tuple[str, ...] | None, str]] = []
    per_header: dict[str, Counter] = {}
    header = ""
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        marker = _MARKER.match(stripped)
        if marker is not None:
            header = marker.group(1)
            index += 1
            continue
        define = _DEFINE.match(stripped)
        if define is not None:
            entries.append((define.group(1), None, header))
            index += 1
            continue
        if _is_head(stripped):
            name, used = _declarator(lines, index)
            if name is not None:
                needs = _needs(stripped)
                entries.append((name, needs, header))
                per_header.setdefault(header, Counter())[needs] += 1
            index = used + 1
            continue
        index += 1
    return entries, per_header


def _is_head(stripped: str) -> bool:
    """clang's declaration form: `static` and an `inline` spelling — `__inline__`, or the bare `__inline`."""
    return stripped.startswith("static") and "inline" in stripped


def _needs(head: str) -> tuple[str, ...]:
    """The features a head requires: its `__target__` entries, with the `no-…` statements dropped.

    `__target__("ssse3,no-evex512")` requires `ssse3` and says EVEX-512 encoding is off; reading `no-evex512`
    as a requirement would make every SSE intrinsic unavailable on the avx512 file, where `__EVEX512__` is
    defined.
    """
    features: list[str] = []
    for group in _TARGET.findall(head):
        for feature in group.split(","):
            feature = feature.strip()
            if feature and not feature.startswith("no-") and feature not in features:
                features.append(feature)
    return tuple(features)


def _declarator(lines: list[str], index: int) -> tuple[str | None, int]:
    """The declared name, from the head's own line or the one below it, and the last line read.

    Two forms, both clang's: the declarator on the same line as the attributes, and the declarator alone on
    the next. Nothing further down is tried — a name three lines below its attributes is a declaration this
    module misses, which its docstring says rather than guessing at.
    """
    same = _DECLARATOR.search(_without_attributes(lines[index]))
    if same is not None:
        return same.group(1), index
    if index + 1 < len(lines):
        below = lines[index + 1].strip()
        found = _DECLARATOR.match(below)
        if found is not None:
            return found.group(1), index + 1
    return None, index


def _without_attributes(text: str) -> str:
    """*text* with every `__attribute__((…))` removed, parens matched — what is left is the declaration."""
    while True:
        found = _ATTRIBUTE.search(text)
        if found is None:
            return text
        close = _match_paren(text, found.end() - 1)
        if close is None:
            return text[: found.start()]
        text = text[: found.start()] + " " + text[close + 1 :]


def _match_paren(text: str, open_at: int) -> int | None:
    depth = 0
    for at in range(open_at, len(text)):
        if text[at] == "(":
            depth += 1
        elif text[at] == ")":
            depth -= 1
            if depth == 0:
                return at
    return None


def _header_needs(per_header: dict[str, Counter], header: str) -> tuple[str, ...]:
    """A macro's features: the most common tuple among its header's functions, and `()` where it has none.

    The tie-break is the tuple itself, so two tuples in equal number give a deterministic answer rather
    than one that depends on a dict's order; it is a tie-break and is named as one in the module docstring.
    """
    counts = per_header.get(header)
    if not counts:
        return ()
    return sorted(counts, key=lambda needs: (-counts[needs], needs))[0]


# MARK: - rule R -


def rename(name: str, isa: str, table: dict[str, dict]) -> str | None:
    """*name*'s form in *isa*'s file under rule R, or `None` where there is none.

    *table* is that ISA's `names` map (:func:`names_for`). The renamed form counts only when it **differs**
    from the name — a name already in this file's shape has no other form to offer — and when it is itself
    **available**: a form that is declared nowhere here would be a second invented name, offered by us.
    """
    prefix, width = ISA_PREFIX.get(isa), ISA_WIDTH.get(isa)
    if prefix is None or width is None:
        return None
    renamed = _WIDTH.sub(width, _PREFIX.sub(prefix, name))
    if renamed == name:
        return None
    return renamed if (table.get(renamed) or {}).get("available") else None


def names_for(record: dict, isa: str) -> dict[str, dict]:
    """One ISA's `names` map out of a whole record, and `{}` where the record does not cover that ISA."""
    return (record.get(isa) or {}).get("names") or {}


# MARK: - the record on disk -


def load(path: Path | str) -> dict[str, dict]:
    """The record `lattice available` wrote: `{isa: {"flags", "clang", "target_sha", "names"}}`."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def record_meta(path: Path | str) -> dict:
    """A plan's `available` block: the file's own digest, and per ISA the flags and the clang line.

    The digest is over the file's bytes, so a plan names the exact availability it was built from, and the
    flags and the version are what a reader needs to know *which* compiler answered — the same shape
    `e1.meta` gives a ledger and `e4.parser_meta` gives the parser's fields.
    """
    path = Path(path)
    record = load(path)
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "isas": {
            isa: {
                "flags": list(row.get("flags") or ()),
                "clang": row.get("clang"),
                "file": row.get("file"),
                "target_sha": row.get("target_sha"),
                "names": len(row.get("names") or {}),
                "available": sum(1 for entry in (row.get("names") or {}).values() if entry.get("available")),
            }
            for isa, row in sorted(record.items())
        },
    }


# MARK: - reading the target, in the image -


def native() -> list[str]:
    """The ISAs a record covers by default: the native ones, in `ISAS` order."""
    return [isa for isa in ISAS if isa in NATIVE]


def kernel_file(isa: str) -> str:
    """The kernel file one ISA's availability is read from, relative to the target's root."""
    return f"src/distance-{isa}.c"


def preprocess_flags(isa: str) -> tuple[str, ...]:
    """The flags the file is preprocessed under: the grader's, per ISA, with relative includes."""
    return (OPTIMISE, *INCLUDES, *ISA_FLAGS.get(isa, ()))


def clang_version(root: Path | str) -> str:
    """`clang --version`'s first line — which compiler answered, on the record beside the answer."""
    done = _clang(root, ["--version"])
    return done.splitlines()[0].strip() if done.strip() else "unknown"


def build(target: Path | str, isas: list[str] | tuple[str, ...] | None = None) -> dict:
    """Preprocess each ISA's kernel file over the target's own text, and :func:`parse` the two outputs.

    It runs clang over a checkout's source, so it goes through :func:`lattice.run.require_container` and
    **refuses on the host** (ADR-092, C-64) — `lattice available` without `--here` builds a `podman run`
    plan and runs this same CLI inside the image, exactly as `lattice grade` does. clang is run from the
    target's root with relative includes, so nothing in the record names a path of this box.
    """
    sandbox.require_container()
    root = Path(target)
    version = clang_version(root)
    sha = head(root)
    record: dict[str, dict] = {}
    for isa in list(isas) if isas else native():
        source = kernel_file(isa)
        if not (root / source).exists():
            raise PreprocessFailed(f"{root} has no {source}, so {isa}'s availability cannot be read")
        flags = preprocess_flags(isa)
        record[isa] = {
            "isa": isa,
            "file": source,
            "flags": list(flags),
            "clang": version,
            "target_sha": sha,
            "names": parse(
                _clang(root, [*flags, "-E", "-dD", source]),
                _clang(root, [*flags, "-dM", "-E", "-x", "c", "/dev/null"]),
            ),
        }
    return record


def _clang(root: Path | str, args: list[str] | tuple[str, ...]) -> str:
    """One clang invocation from the target's root, its stdout — or :class:`PreprocessFailed`."""
    command = [cc(), *args]
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=600, cwd=str(root))
    except (OSError, subprocess.SubprocessError) as broken:
        raise PreprocessFailed(f"{' '.join(command)} could not be run ({broken})") from broken
    if done.returncode != 0:
        raise PreprocessFailed(
            f"{' '.join(command)} exited {done.returncode}: {(done.stderr or '').strip()[:400]}"
        )
    return done.stdout
