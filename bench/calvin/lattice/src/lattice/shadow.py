"""**The two rename shadows** (`calvin-experiments.md` §6, the E0 and E2 cards): the target's own code
under names the base model has never read.

E2 asks whether E1's score was memory or skill. The control is a copy of the target in which every
in-repo name is different and nothing else is: same bytes, same structure, same intrinsics, same SQL.
There are **two** shadows because renaming costs a model real ability as well as recall (§12.4, and
Le et al. on obfuscated identifiers). The **descriptive** shadow renames to names that still mean
something — `float32_distance_dot_avx2` reads `f32_dist_inner_x86v2` — so the gap from the original is
the memorised share. The **opaque** shadow renames to `fn_0001`, and the further gap is how much the
model reads names at all.

**What is renamed** is every symbol the graph names under `src/` or `test/`, and nothing else. At the
target's 100/100 oracle cell the graph knows every definition and every in-repo reference, so that set
is a fact and not a guess. Four things are held back, each because changing them would change what the
program *is* rather than what it is called:

- **a name the build resolves outside the repo**, of which there are two kinds and both are read, not
  guessed. `graph["lane_agreement"]["external_vetoes"]` names the first (ADR-111): sqlite-vector defines
  `strcasestr` under an `#if` that is dead on glibc, and the calls go to libc. The second is a
  **self-referential macro** — `distance-avx512.c` writes `#define _mm512_abs_ps(x) _mm512_abs_ps(x)`,
  and C11 6.10.3.4p2 says the name in its own replacement list is not expanded again, so the call lands
  on clang's intrinsic. The graph names it as an in-repo macro, and it is; renaming it would send its
  calls to a definition that does not exist. :func:`self_referential` finds those off the `#define`
  itself, and they are `kept` as `external` because that is what they are.
- **a name another file of the tree also declares**, outside the renamed files. `src/sqlite-vector.c`
  writes `#define sqlite3_mutex_alloc(_type) NULL` under one `#if` arm; under `-DSQLITE_CORE` (the
  target's `make unittest`) the same name is SQLite's own API, declared in `libs/sqlite3.h`. The ingest
  built the other arm, so no external veto names it. :func:`declared_outside` reads every C file the
  rename does not touch, and a name one of them writes in code or `#define`s is `kept` as
  `declared-outside` (added at session `c141`'s review, where the first shadows failed to link on it).
- **the extension's entry point**, `sqlite3_vector_init`, which SQLite looks up by name.
- **`main`.**
- **strings.** The SQL-visible names are string literals and the tests call through SQL, so a literal
  is never rewritten — which is also why an identifier *in a comment* is: a comment that still names
  the original leaks exactly what the shadow removes.

**What the shadow still leaks is on the record.** Every in-repo identifier the plan leaves unchanged is
in `Plan.kept` with its reason — `external`, `entry-point`, or `not-a-graph-symbol` for the enum
constants (`VECTOR_TYPE_F32`) and file-scope declarations (`dispatch_distance_table`, `VECTOR_TYPE_MAX`)
that are not graph symbols and so are not in the set to rename. :func:`declarations` finds those with
this package's own scanner; what it reads wrongly rather than refuses is in its docstring. A descriptive
name that fell back to the `sv_` prefix carries its original whole, and those are listed in
`Plan.prefixed`: a signal to extend :data:`SYNONYMS`, not a silent leak.

**A plan is a bijection or it is nothing.** Two originals may not land on one name, and a new name may
not already be an identifier token anywhere in the tree unless it is itself being renamed away. Either
one raises :class:`Collision` — its own type (P10, ADR-036) — and the plan is not built; nothing is
written, because a shadow that merges two names is a different program.

**What `grade` does not yet know.** `diff.py`'s generated driver names the target's scaffolding
(`distance_function_t`, `init_distance_functions_<isa>`) in its own C, and a shadow renames those like
any other graph symbol. :func:`grading` is the one named seam that lets the existing graders read a
shadow — the lattice through the reverse map, the driver through :func:`apply` — and it is a seam
rather than a parameter because `grade.py` and `diff.py` are not this unit's to change. It is one
function to delete when they take a rename of their own.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from .scan import ScanError, scan

__all__ = [
    "ENTRY_POINTS",
    "OPAQUE_PREFIX",
    "RENAMED",
    "STYLES",
    "SYNONYMS",
    "Collision",
    "Plan",
    "apply",
    "declarations",
    "descriptive",
    "grading",
    "identifiers",
    "leaks",
    "load",
    "map_digest",
    "plan",
    "read_map",
    "self_referential",
    "tree_digest",
    "write",
]

#: The two styles of §6's E0 card. `descriptive` keeps meaning; `opaque` removes it.
STYLES = ("descriptive", "opaque")

#: Looked up by name and never renamed: the program would stop being itself.
ENTRY_POINTS = ("sqlite3_vector_init", "main")

#: The globs a rename is applied to. Everything else the target's root holds is copied unchanged.
RENAMED = ("src/*.c", "src/*.h", "test/*.c")

#: `opaque`'s prefix per graph kind. Anything else the graph one day names gets `sy`.
OPAQUE_PREFIX = {"function": "fn", "macro": "MC", "type": "ty"}

#: The descriptive shadow's word table, written for the stems sqlite-vector's kernels use.
#:
#: A name is split on `_` and each word looked up in lower case; a word the table does not hold whole
#: is tried again as an alphabetic stem with a digit tail (`hsum256` → `hadd` + `256`), which is how the
#: target spells its horizontal sums and its lane widths. The replacement takes the word's own case, so
#: a macro stays upper case. Every entry is a synonym, not a code: the point of this shadow is that the
#: names still *mean* the same thing (§12.4) — only the model has not read them.
SYNONYMS = {
    # element types
    "float32": "f32", "float16": "f16", "bfloat16": "bf16", "float64": "f64",
    "int8": "i8", "int16": "i16", "int32": "i32", "int64": "i64",
    "uint8": "u8", "uint16": "u16", "uint32": "u32", "uint64": "u64",
    "bit1": "b1", "bit": "b", "half": "semi",
    # metrics
    "distance": "dist", "l2": "euclid", "l1": "manhattan", "squared": "sq",
    "dot": "inner", "cosine": "angular", "hamming": "bitdiff", "norm": "length",
    # the shape of a kernel
    "impl": "core", "imp": "core", "wrapper": "shell", "table": "grid",
    "dispatch": "route", "init": "setup", "function": "fn", "functions": "fns",
    "vector": "vec", "backend": "engine", "name": "label",
    # the ISAs
    "cpu": "scalar", "sse2": "x86v1", "avx2": "x86v2", "avx512": "x86v4",
    "neon": "armv8", "rvv": "rv64v", "x86": "intel", "arm": "aarch",
    "supports": "provides", "cpuid": "chipid", "xgetbv": "xctrl", "run": "invoke",
    # lane arithmetic
    "hsum": "hadd", "sum": "total", "sums": "totals", "acc": "tally",
    "accumulate": "tally", "popcount": "bitcount", "vpopcnt": "vbitcount",
    "lassq": "sumsq", "update": "refresh", "scale": "gain",
    "abs": "magnitude", "diff": "delta", "sqdiff": "sqdelta", "mul": "times",
    "add": "plus", "sub": "minus", "min": "floor", "max": "ceil", "vmaxv": "vceil",
    "shuffle": "permute", "load": "fetch", "loadu": "fetchu", "store": "keep",
    "extend": "widen", "sign": "signbit", "signed": "signedint", "biased": "offset",
    # lane spellings
    "mm": "vecop", "ps": "f32lane", "pd": "f64lane", "epi": "sint", "epu": "uint",
    "si": "ilane", "fma": "fusedmul", "vfma": "vfusedmul", "lut": "codebook",
    "lut3": "codebook3", "index": "slot", "turbo": "boost", "packed": "bundled",
    # the special values
    "inf": "unbounded", "nan": "notnum", "zero": "null", "is": "check",
    "has": "holds", "not": "non", "both": "pair", "block": "chunk",
    "mismatch": "clash", "compat": "fallback", "bits": "rawbits", "to": "into",
    "as": "into", "from": "outof", "f": "flt", "d": "dbl",
}

_IDENT = re.compile(r"[A-Za-z_]\w*")
_DEFINE = re.compile(r"#\s*define\s+([A-Za-z_]\w*)")
_TRAILING_IDENT = re.compile(r"[A-Za-z_]\w*\Z")
_LEADING_IDENT = re.compile(r"\s*([A-Za-z_]\w*)")
_STEM = re.compile(r"([A-Za-z]+)(\d\w*)\Z")
_ARRAY = re.compile(r"(\[[^\[\]]*\])+\Z")
_ENUM = re.compile(r"\benum\b")

#: Never a declared name, so never mistaken for one by :func:`declarations`.
_KEYWORDS = frozenset(
    """auto break case char const continue default do double else enum extern float for goto if inline
    int long register restrict return short signed sizeof static struct switch typedef union unsigned
    void volatile while _Bool _Atomic _Alignas _Noreturn _Thread_local""".split()
)

#: Never copied into a shadow: a history, a build tree, and an ingest of the *original* names.
_NOT_COPIED = frozenset({".git", ".hobbes", "build", "derived"})

#: How large a copied file :func:`write` will read looking for a leaked name. Bigger ones are listed
#: as unread rather than scanned: `libs/sqlite3.c` is 8 MB of a vendored amalgamation.
_LEAK_LIMIT = 8 * 1024 * 1024


class Collision(Exception):
    """A rename would merge two names, so no plan was built and nothing was written.

    Its own type, not a `ValueError` (P10, ADR-036): every other refusal in this package is a fact
    about one file or one body, and this one says the whole shadow would be a different program.
    """


@dataclass(frozen=True)
class Plan:
    """One shadow's rename, and everything it did not rename.

    `renames` is the original-to-new map in the order the plan built it; `kept` is one
    `{"name", "reason"}` row per in-repo identifier left alone; `prefixed` names the descriptive
    fall-backs, which still carry their original; `missing` is what the plan could not read.
    """

    style: str
    root: Path
    renames: dict[str, str]
    kept: tuple[dict, ...] = ()
    prefixed: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    counts: dict = field(default_factory=dict)

    def reverse(self) -> dict[str, str]:
        """The new-to-original map — what `cells.build(shadow, rename=…)` reads the grid through."""
        return {new: old for old, new in self.renames.items()}

    def as_map(self) -> dict:
        """`shadow-map.json` without its `leaks`, which only a written shadow has: the style, the
        original-to-new map, `kept`, the `sv_` fall-backs, the files renamed, the gaps and the counts."""
        return {
            "style": self.style,
            "renames": dict(self.renames),
            "kept": [dict(row) for row in self.kept],
            "prefixed": list(self.prefixed),
            "files": list(self.files),
            "missing": list(self.missing),
            "counts": dict(self.counts),
        }


# MARK: - planning -


def plan(target: Path | str, graph: dict, style: str) -> Plan:
    """The rename for one shadow of *target*, from its Hobbes ingest *graph*.

    Raises :class:`Collision` rather than returning a plan that would merge two names, and
    `ValueError` for a style that is not one of :data:`STYLES`.
    """
    if style not in STYLES:
        raise ValueError(f"style must be one of {', '.join(STYLES)}, not {style!r}")
    root = Path(target)
    missing: list[str] = []

    external = sorted(set(_external(graph, missing)) | _self_referential_in(root))
    symbols = _symbols(graph)
    outside = sorted({symbol["name"] for symbol in symbols} & declared_outside(root))
    held = set(external) | set(ENTRY_POINTS) | set(outside)
    renameable = [symbol for symbol in symbols if symbol["name"] not in held]

    if style == "descriptive":
        renames = {symbol["name"]: descriptive(symbol["name"]) for symbol in renameable}
    else:
        renames = _opaque(renameable)

    files = tuple(_files(root))
    tokens = identifiers(root)
    _check(renames, tokens)

    kept = _kept(root, symbols, held, external, tokens, outside)
    prefixed = tuple(old for old, new in renames.items() if new == f"sv_{old}")
    return Plan(
        style=style,
        root=root,
        renames=renames,
        kept=kept,
        prefixed=prefixed,
        files=files,
        missing=tuple(missing),
        counts={
            "renamed": len(renames),
            "kept": len(kept),
            "prefixed": len(prefixed),
            "files": len(files),
        },
    )


def descriptive(name: str) -> str:
    """One name through :data:`SYNONYMS`, word by word, each word keeping its own case.

    A name no word of which the table holds — and a name the table maps to itself — gets the prefix
    `sv_`, which is honest and weak on purpose: it still carries the original, and `Plan.prefixed`
    says so. The fix is a table entry, not a cleverer fall-back.
    """
    words = name.split("_")
    out: list[str] = []
    hit = False
    for word in words:
        found = _synonym(word)
        out.append(word if found is None else found)
        hit = hit or found is not None
    new = "_".join(out)
    return f"sv_{name}" if (not hit or new == name) else new


def _synonym(word: str) -> str | None:
    """*word* through the table, whole first and then as a stem with a digit tail; `None` if neither."""
    if not word:
        return None
    found = SYNONYMS.get(word.lower())
    if found is not None:
        return _cased(word, found)
    stem = _STEM.fullmatch(word)
    if stem is None:
        return None
    found = SYNONYMS.get(stem.group(1).lower())
    if found is None:
        return None
    return _cased(stem.group(1), found) + stem.group(2)


def _cased(sample: str, replacement: str) -> str:
    """*replacement* in *sample*'s case: `PS` → `F32LANE`, `Ps` → `F32lane`, `ps` → `f32lane`."""
    if sample.isupper():
        return replacement.upper()
    if sample[:1].isupper():
        return replacement.capitalize()
    return replacement


def _opaque(symbols: list[dict]) -> dict[str, str]:
    """`fn_0001`, `MC_0001`, `ty_0001` — numbered per kind in the order of (path, line)."""
    counters: dict[str, int] = {}
    renames: dict[str, str] = {}
    for symbol in sorted(symbols, key=lambda s: (s["path"], s["line"], s["name"])):
        prefix = OPAQUE_PREFIX.get(symbol["kind"], "sy")
        counters[prefix] = counters.get(prefix, 0) + 1
        renames[symbol["name"]] = f"{prefix}_{counters[prefix]:04d}"
    return renames


def _symbols(graph: dict) -> list[dict]:
    """Every graph symbol under `src/` or `test/`, once per name, in the order of (path, line)."""
    paths = _module_paths(graph)
    found: dict[str, dict] = {}
    rows = []
    for symbol in graph.get("symbols") or ():
        path = paths.get(symbol.get("module")) or symbol.get("module") or ""
        if not (path.startswith("src/") or path.startswith("test/")):
            continue
        rows.append(
            {
                "name": symbol.get("name"),
                "kind": symbol.get("kind"),
                "path": path,
                "line": symbol.get("line") or 0,
            }
        )
    for row in sorted(rows, key=lambda r: (r["path"], r["line"], r["name"] or "")):
        if row["name"]:
            found.setdefault(row["name"], row)
    return list(found.values())


def _module_paths(graph: dict) -> dict[str, str]:
    """Each module node's repo-relative path; a module the nodes do not name keeps its own id."""
    paths = {}
    for node in graph.get("nodes") or ():
        if node.get("kind") == "module" and node.get("path"):
            paths[node["id"]] = node["path"]
    for symbol in graph.get("symbols") or ():
        module = symbol.get("module")
        if module and module not in paths:
            paths[module] = module if Path(module).suffix else f"{module}.c"
    return paths


def _external(graph: dict, missing: list[str]) -> list[str]:
    """The names `lane_agreement.external_vetoes` reports (ADR-111), and a note if it named only some.

    The report carries up to ten examples beside its count, so a target with more vetoed names than
    that gives this plan fewer names than it has. That is a gap in what was read, and it is said.
    """
    report = ((graph.get("lane_agreement") or {}).get("external_vetoes")) or {}
    examples = report.get("examples") or []
    names = sorted({row.get("name") for row in examples if row.get("name")})
    sites = report.get("sites") or 0
    if sites > len(examples):
        missing.append(
            f"external_vetoes: {sites} site(s), {len(examples)} example(s) — the rest are not named in the graph"
        )
    return names


def self_referential(text: str) -> set[str]:
    """The macros one file defines whose own replacement list writes their name.

    C11 6.10.3.4p2: the macro's name in its own replacement list is not expanded again, so
    `#define _mm512_abs_ps(x) _mm512_abs_ps(x)` is a *pass-through to whatever else declares that
    name* — here clang's AVX-512 header. Every arm of an `#if` is read, because one self-referential
    arm is enough for the rename to break the build on some box.
    """
    found: set[str] = set()
    for line in _logical_lines(text):
        define = _DEFINE.match(line.lstrip())
        if define is None:
            continue
        name = define.group(1)
        if re.search(rf"\b{re.escape(name)}\b", line[define.end() :]):
            found.add(name)
    return found


def _logical_lines(text: str):
    """The file's lines with every trailing-backslash continuation joined to the line it continues."""
    joined: list[str] = []
    carry = ""
    for line in text.splitlines():
        stripped = line.rstrip("\r")
        if stripped.endswith("\\"):
            carry += stripped[:-1] + " "
            continue
        joined.append(carry + stripped)
        carry = ""
    if carry:
        joined.append(carry)
    return joined


def _self_referential_in(root: Path) -> set[str]:
    """:func:`self_referential` over the files a rename would touch."""
    found: set[str] = set()
    for file in _files(root):
        found |= self_referential((root / file).read_text(encoding="utf-8", errors="replace"))
    return found


def declared_outside(root: Path | str) -> set[str]:
    """Every identifier the tree's C files *outside* the renamed set write in code or `#define`.

    Comments and literals do not count (a word in `sqlite3.h`'s prose is not a declaration). Preprocessor
    lines are read only for the names they `#define`, since :func:`scan.mask` blanks them. A graph symbol
    in this set is one the rename must not touch: some other part of the build owns the name too.
    """
    from .scan import mask

    root = Path(root)
    renamed = set(_files(root))
    found: set[str] = set()
    for pattern in ("**/*.c", "**/*.h"):
        for path in sorted(root.glob(pattern)):
            rel = path.relative_to(root)
            if not path.is_file() or str(rel) in renamed or _NOT_COPIED & set(rel.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            found |= {m.group(0) for m in _IDENT.finditer(mask(text))}
            found |= {d.group(1) for line in _logical_lines(text) if (d := _DEFINE.match(line.lstrip()))}
    return found


def _files(root: Path) -> list[str]:
    """The repo-relative files a rename is applied to, in a fixed order."""
    found: list[str] = []
    for pattern in RENAMED:
        found += sorted(str(path.relative_to(root)) for path in root.glob(pattern) if path.is_file())
    return found


def _check(renames: dict[str, str], tokens: set[str]) -> None:
    """Refuse unless the map is a bijection and no new name is already a token something else owns."""
    taken: dict[str, str] = {}
    for old, new in renames.items():
        clash = taken.get(new)
        if clash is not None:
            raise Collision(f"{clash!r} and {old!r} would both become {new!r}")
        taken[new] = old
    for old, new in renames.items():
        if new in tokens and new not in renames:
            raise Collision(f"{old!r} would become {new!r}, which the tree already writes")


def _kept(
    root: Path, symbols: list[dict], held: set[str], external: list[str], tokens: set[str], outside: list[str] = ()
) -> tuple[dict, ...]:
    """Every in-repo identifier the plan leaves unchanged, with the reason it did.

    The graph's own held-back names come first, then the declarations and enum constants the scanner
    finds under `src/` and `test/` that the graph does not name — one row per name, the first reason
    that applies.
    """
    named = {symbol["name"] for symbol in symbols}
    rows: dict[str, dict] = {}

    def add(name: str, reason: str) -> None:
        if name in tokens:
            rows.setdefault(name, {"name": name, "reason": reason})

    for name in external:
        add(name, "external")
    for name in ENTRY_POINTS:
        add(name, "entry-point")
    for name in outside:
        add(name, "declared-outside")
    for declared in _declared_in_tree(root):
        if declared in held or declared in named:
            continue
        add(declared, "not-a-graph-symbol")
    return tuple(rows[name] for name in sorted(rows))


def _declared_in_tree(root: Path) -> list[str]:
    """Every top-level declaration under the renamed files, in the order the files are read."""
    found: list[str] = []
    for file in _files(root):
        found += declarations((root / file).read_text(encoding="utf-8", errors="replace"))
    return found


# MARK: - the scanner over what the graph does not name -


def declarations(text: str) -> tuple[str, ...]:
    """Every name one C file declares at its top level: declarators, enum constants, `#define`s.

    A *declaration* is read off the chunk between two top-level `;`s: the identifier before the
    parameter list of a prototype or a definition, the identifier before a `=` or an array dimension
    otherwise. Enum constants are the leading identifiers of a top-level `enum { … }`. `#define` names
    come from :func:`scan.scan`.

    **What it reads wrongly rather than refuses**, like the rest of this package's hand scanning: a
    declarator with two names (`int a, b;`) gives only the last; a K&R definition and a macro-generated
    declaration are invisible to the scanner behind it; a text that does not scan at all answers with
    its `#define`s alone. It is used to *list* what a shadow leaves behind, never to decide what to
    rename — that set is the graph's.
    """
    defines = [found.group(1) for line in _logical_lines(text) if (found := _DEFINE.match(line.lstrip()))]
    try:
        scanned = scan(text)
    except ScanError:
        return tuple(dict.fromkeys(defines))
    names: list[str] = list(defines)
    masked = scanned.masked
    chunk = 0
    i, n = 0, len(masked)
    while i < n:
        char = masked[i]
        if char == ";":
            names += _declared(masked[chunk:i])
            chunk = i + 1
        elif char == "{":
            close = _closing(masked, i)
            if close is None:
                break
            head = masked[chunk:i]
            if _ENUM.search(head) and not head.rstrip().endswith(")"):
                names += _constants(masked[i + 1 : close])
            elif head.rstrip().endswith(")"):
                names += _declared(head)
                chunk = close + 1
            i = close
        i += 1
    return tuple(dict.fromkeys(name for name in names if name and name not in _KEYWORDS))


def _declared(chunk: str) -> list[str]:
    """The name a top-level declaration introduces, or nothing when the chunk declares none."""
    head = _before_initialiser(chunk).strip()
    while head.endswith(")"):
        opened = _opening(head)
        if opened is None:
            return []
        # `typedef float (*distance_function_t)(…)`: a parenthesised declarator holds the name itself,
        # and a parameter list does not — `(const void *v1, int n)` would otherwise answer `n`.
        inner = head[opened + 1 : -1].strip()
        if inner.startswith("*"):
            found = _TRAILING_IDENT.search(inner.lstrip("* \t"))
            if found is not None and found.group(0) not in _KEYWORDS:
                return [found.group(0)]
        before = head[:opened].rstrip()
        found = _TRAILING_IDENT.search(before)
        if found is not None and found.group(0) not in _KEYWORDS:
            return [found.group(0)]
        head = before
    head = _ARRAY.sub("", head).rstrip()
    found = _TRAILING_IDENT.search(head)
    return [found.group(0)] if found is not None else []


def _before_initialiser(chunk: str) -> str:
    """The chunk up to its first `=` outside any bracket — the declarator, without its initialiser."""
    depth = 0
    for i, char in enumerate(chunk):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "=" and depth == 0:
            return chunk[:i]
    return chunk


def _constants(body: str) -> list[str]:
    """A top-level enum body's constants: the leading identifier of each comma-separated element."""
    names: list[str] = []
    depth = 0
    start = 0
    for i, char in enumerate(body + ","):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            found = _LEADING_IDENT.match(body[start:i])
            if found is not None:
                names.append(found.group(1))
            start = i + 1
    return names


def _opening(head: str) -> int | None:
    """The index of the `(` that the head's trailing `)` closes."""
    depth = 0
    for i in range(len(head) - 1, -1, -1):
        if head[i] == ")":
            depth += 1
        elif head[i] == "(":
            depth -= 1
            if depth == 0:
                return i
    return None


def _closing(masked: str, opened: int) -> int | None:
    depth = 0
    for i in range(opened, len(masked)):
        if masked[i] == "{":
            depth += 1
        elif masked[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return None


# MARK: - applying a plan -


def identifiers(root: Path | str) -> set[str]:
    """Every identifier token the tree writes outside a string or character literal.

    The whole tree, not only the renamed files: a new name that collides with something `libs/` writes
    is still a collision, because `src/` compiles against it.
    """
    root = Path(root)
    found: set[str] = set()
    for pattern in ("**/*.c", "**/*.h"):
        for path in sorted(root.glob(pattern)):
            if not path.is_file() or _NOT_COPIED & set(path.relative_to(root).parts):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            literal = _literals(text)
            found |= {m.group(0) for m in _IDENT.finditer(text) if not literal[m.start()]}
    return found


def apply(plan: Plan | dict, text: str) -> str:
    """*text* with every renamed identifier token rewritten, whole words, outside literals only.

    Comments are rewritten with the code: a comment that still names `float32_distance_dot_avx2` hands
    the model back the name the shadow removed. String and character literals are not: the SQL-visible
    names live there and the tests call through them. *plan* may be a :class:`Plan` or a bare
    original-to-new mapping, because the driver's C is renamed by the same rule and has no plan.
    """
    renames = plan.renames if isinstance(plan, Plan) else dict(plan)
    if not renames:
        return text
    literal = _literals(text)
    out: list[str] = []
    last = 0
    for found in _IDENT.finditer(text):
        new = renames.get(found.group(0))
        if new is None or literal[found.start()]:
            continue
        out.append(text[last : found.start()])
        out.append(new)
        last = found.end()
    out.append(text[last:])
    return "".join(out)


def _literals(text: str) -> bytearray:
    """One flag per character: 1 inside a string or character literal, 0 in code and in comments.

    Comments are walked rather than skipped so that an apostrophe in one — the target writes
    `don't` in `distance-cpu.h` — does not open a character literal that swallows the rest of the file.
    """
    n = len(text)
    flags = bytearray(n)
    i = 0
    while i < n:
        pair = text[i : i + 2]
        if pair == "//":
            stop = text.find("\n", i)
            i = n if stop == -1 else stop
        elif pair == "/*":
            stop = text.find("*/", i + 2)
            i = n if stop == -1 else stop + 2
        elif text[i] in "\"'":
            i = _literal(text, flags, i)
        else:
            i += 1
    return flags


def _literal(text: str, flags: bytearray, i: int) -> int:
    """Flag one string or character literal, escapes included; an unterminated one ends at the line."""
    quote = text[i]
    n = len(text)
    flags[i] = 1
    i += 1
    while i < n and text[i] != quote:
        if text[i] == "\n":
            return i
        flags[i] = 1
        if text[i] == "\\" and i + 1 < n and text[i + 1] != "\n":
            flags[i + 1] = 1
            i += 2
            continue
        i += 1
    if i < n:
        flags[i] = 1
        i += 1
    return i


# MARK: - writing a shadow -


def write(plan: Plan, dest: Path | str) -> Path:
    """Write the shadow under *dest*: the renamed files, everything else verbatim, and the map.

    The whole of the target's root is copied — `libs/`, the `Makefile`, the tests, whatever else it
    holds — because the acceptance of a shadow is that it *builds and passes the target's own tests*
    unchanged. What is left out is :data:`_NOT_COPIED`: a history, a build tree, and an ingest, each
    of which belongs to the tree it came from and none of which a shadow's build needs.
    `shadow-map.json` goes at the root with the style, the map, `kept`, the counts, and
    :func:`leaks` — the copied files that still write an original name.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for entry in sorted(plan.root.iterdir()):
        if entry.name in _NOT_COPIED:
            continue
        into = dest / entry.name
        if entry.is_dir():
            shutil.copytree(entry, into, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, into)
    for file in plan.files:
        path = dest / file
        path.write_text(apply(plan, path.read_text(encoding="utf-8")), encoding="utf-8")
    payload = {**plan.as_map(), "leaks": leaks(plan, dest)}
    (dest / "shadow-map.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return dest


def leaks(plan: Plan, dest: Path | str) -> list[dict]:
    """The copied-but-not-renamed files of a written shadow that still write an original name.

    `README.md` and `API.md` name the functions they document, and a rename touches C only — so a
    shadow's prose can hand back exactly the names its code removed. That is a real limit on E2 (L3
    reads `API.md`), so it is measured and written into `shadow-map.json` rather than left for someone
    to notice. A file too large to read is listed with `"unread": true` instead of a name list.
    """
    dest = Path(dest)
    renamed = {dest / file for file in plan.files}
    pattern = re.compile(r"\b(" + "|".join(sorted(map(re.escape, plan.renames), key=len, reverse=True)) + r")\b")
    found: list[dict] = []
    for path in sorted(dest.rglob("*")):
        if not path.is_file() or path in renamed or path.name == "shadow-map.json":
            continue
        file = str(path.relative_to(dest))
        try:
            if path.stat().st_size > _LEAK_LIMIT:
                found.append({"file": file, "unread": True})
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        names = sorted({match.group(1) for match in pattern.finditer(text)})
        if names:
            found.append({"file": file, "names": names})
    return found


def read_map(where: Path | str) -> dict:
    """A written `shadow-map.json`, whole: the style, the map, `kept`, `prefixed`, the counts, the leaks."""
    return json.loads(Path(where).read_text(encoding="utf-8"))


def load(where: Path | str) -> dict[str, str]:
    """The new-to-original map from a `shadow-map.json` — what `--rename` hands the other verbs."""
    return {new: old for old, new in (read_map(where).get("renames") or {}).items()}


# MARK: - what identifies a shadow -


def map_digest(where: Path | str) -> str:
    """The SHA-256 of a `shadow-map.json`'s own bytes: which rename a run was planned through.

    The file's bytes and not the map's contents, because that is what a reader can check by hand
    against the shadow on disk.
    """
    return hashlib.sha256(Path(where).read_bytes()).hexdigest()


def tree_digest(root: Path | str) -> str:
    """One SHA-256 over the renamed files of a shadow: what `_same_target` checks in place of a SHA.

    A written shadow is not a checkout, so `e1`'s `target_sha` is `None` there and the plan would have
    nothing to hold a run to. The digest covers :data:`RENAMED`'s globs in :func:`_files`' fixed order,
    each file's repo-relative path and then its bytes, so a renamed file that changed — the one thing
    that would make the run's prompts another tree's bytes — moves it.
    """
    root = Path(root)
    digest = hashlib.sha256()
    for file in _files(root):
        digest.update(file.encode("utf-8"))
        digest.update(b"\0")
        digest.update((root / file).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@contextmanager
def grading(rename: dict[str, str]):
    """Let the existing graders read a shadow for as long as the block runs, then put them back.

    *rename* is the new-to-original map (`Plan.reverse`, or :func:`load`). Two names move:
    `grade.build_lattice`, so the grid is read through the reverse map, and `diff.driver_source`, so
    the generated driver calls `setup_dist_fns_x86v2` rather than `init_distance_functions_avx2` and
    declares the table as `dist_fn_t`. Everything else the graders do is already name-blind — the
    table itself, the `VECTOR_*` constants and the headers' paths are not renamed.

    This is a **seam, not a design**: `grade.py` and `diff.py` should take a rename of their own, and
    when they do this function is the one thing to delete. It is here rather than in a test so that
    `lattice grade --rename` really works and so that there is one place to find.
    """
    from . import diff, grade
    from .cells import build as build_lattice

    back = dict(rename)
    forward = {old: new for new, old in back.items()}
    lattice_of, driver_of = grade.build_lattice, diff.driver_source
    grade.build_lattice = lambda target: build_lattice(target, rename=back)
    diff.driver_source = lambda: apply(forward, driver_of())
    try:
        yield
    finally:
        grade.build_lattice, diff.driver_source = lattice_of, driver_of
