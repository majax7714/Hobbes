"""The tail view: classify unresolved call sites by observation (ADR-045).

Resolution coverage (ADR-029, C-2) counts how many detected call sites
have no known destination. This module says what the uncounted remainder
*is* — by observation only, never by inference. Every class states a
checkable fact about the site:

- ``fallback-resolved`` — lane A's resolver produced a (syntactic) edge
  for this site; only the semantic provider came up empty.
- ``local-binding`` — the callee is a binding **below the modelled
  vocabulary in the same file** (C-9): a destructured setter, a handler
  ``const``, a nested function, a fixture parameter, a closure-typed
  ``:=`` target. Seen and deliberately not modelled — not unknown. Two
  proof grades, both observations (ADR-046): for TS/JS the checker
  resolved the declaration; for Python and Go, lane A's own parse
  recorded the binding *with its enclosing function's extent*, and the
  site matches only when that extent spans the call's line — scope
  containment, not a file-wide name coincidence.
- ``nested-decl`` — same, but the declaration lives in another repo file.
- ``external-origin`` — every declaration the checker found lives outside
  the repo: a dependency or an ambient lib. Known origin, unresolved call.
- ``import-binding`` — a bare call whose name an import statement **in
  the same file** binds (``from x import y as z`` binds ``z``). The
  binding is lane A's own parse, not a guess; what stays open is only
  where the imported thing's call would land — often a dependency the
  environment is missing (C-23/C-27/C-30), which is exactly when this
  class carries the tail. Added after the private-repo-A/qwen run: their
  ``unclassified`` was almost entirely this (``PG_UUID``,
  ``load_dataset``, ``LLM`` — imports of the very packages
  ``dependency_coverage`` reported missing).
- ``builtin-name`` — a bare call whose name matches the language's pinned
  builtin list. The class says "matches": a local shadowing ``len`` would
  match too, and the name is honest about that. An import binding
  outranks a builtin match — ``from rich import print`` makes the
  import the truer observation about ``print(...)``.
- ``attr-call`` — an attribute call (``x.foo()``): a receiver no static
  provider could type. The genuine static-analysis limit, C-2's core.
- ``path-call`` — a ``::``-qualified call (Rust) the index left dark.
- ``unclassified`` — none of the above observations applies. This is the
  residue that stays honestly unknown.

The classes roll up into the two statements the ingest summary prints
(architecture §3.4): *seen and not modelled by design* (local-binding,
nested-decl, builtin-name) versus *cannot resolve* (everything else but
fallback-resolved, which has an edge and merely lacks proof).

Checker-origin classes are **TypeScript/JavaScript only** in this
version — the tsextract helper's checker knows declarations; the other
syntax providers do not resolve. The asymmetry, the pinned (not
runtime) builtin lists, and the text-based shape read are the
classifier's own boundaries, registered as C-32 — and the asymmetry is
*stated* per language by :data:`CLASSES_AVAILABLE`, which
``graph.json`` carries as ``tail_classes_available`` so a reader can
tell "no external-origin sites" from "no provider that reports them".
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path, PurePosixPath

#: Classes, in the order they are decided. First observation wins.
FALLBACK = "fallback-resolved"
LOCAL = "local-binding"
NESTED = "nested-decl"
EXTERNAL_ORIGIN = "external-origin"
IMPORT_BINDING = "import-binding"
BUILTIN = "builtin-name"
ATTR = "attr-call"
PATH_CALL = "path-call"
UNCLASSIFIED = "unclassified"

#: Rollup: sites the graph sees and deliberately does not model. The
#: complement (minus FALLBACK) is what it cannot resolve — the register's
#: "concentrated need" (ADR-045).
NOT_MODELLED = frozenset({LOCAL, NESTED, BUILTIN})

_LANG_BY_EXT = {
    ".py": "python",
    ".ts": "ts/js",
    ".tsx": "ts/js",
    ".js": "ts/js",
    ".jsx": "ts/js",
    ".mjs": "ts/js",
    ".cjs": "ts/js",
    ".go": "go",
    ".rs": "rust",
}

#: Pinned, not read from the running interpreter (determinism across
#: boxes; the C-3 lift documented what a runtime-bound list costs).
#: Python 3.13 ``builtins``, underscored names dropped.
PY_BUILTINS = frozenset({
    "ArithmeticError", "AssertionError", "AttributeError", "BaseException",
    "BaseExceptionGroup", "BlockingIOError", "BrokenPipeError",
    "BufferError", "BytesWarning", "ChildProcessError",
    "ConnectionAbortedError", "ConnectionError", "ConnectionRefusedError",
    "ConnectionResetError", "DeprecationWarning", "EOFError", "Ellipsis",
    "EncodingWarning", "EnvironmentError", "Exception", "ExceptionGroup",
    "False", "FileExistsError", "FileNotFoundError", "FloatingPointError",
    "FutureWarning", "GeneratorExit", "IOError", "ImportError",
    "ImportWarning", "IndentationError", "IndexError", "InterruptedError",
    "IsADirectoryError", "KeyError", "KeyboardInterrupt", "LookupError",
    "MemoryError", "ModuleNotFoundError", "NameError", "None",
    "NotADirectoryError", "NotImplemented", "NotImplementedError",
    "OSError", "OverflowError", "PendingDeprecationWarning",
    "PermissionError", "ProcessLookupError", "PythonFinalizationError",
    "RecursionError", "ReferenceError", "ResourceWarning", "RuntimeError",
    "RuntimeWarning", "StopAsyncIteration", "StopIteration", "SyntaxError",
    "SyntaxWarning", "SystemError", "SystemExit", "TabError",
    "TimeoutError", "True", "TypeError", "UnboundLocalError",
    "UnicodeDecodeError", "UnicodeEncodeError", "UnicodeError",
    "UnicodeTranslateError", "UnicodeWarning", "UserWarning", "ValueError",
    "Warning", "ZeroDivisionError", "abs", "aiter", "all", "anext", "any",
    "ascii", "bin", "bool", "breakpoint", "bytearray", "bytes", "callable",
    "chr", "classmethod", "compile", "complex", "copyright", "credits",
    "delattr", "dict", "dir", "divmod", "enumerate", "eval", "exec",
    "exit", "filter", "float", "format", "frozenset", "getattr",
    "globals", "hasattr", "hash", "help", "hex", "id", "input", "int",
    "isinstance", "issubclass", "iter", "len", "license", "list",
    "locals", "map", "max", "memoryview", "min", "next", "object", "oct",
    "open", "ord", "pow", "print", "property", "quit", "range", "repr",
    "reversed", "round", "set", "setattr", "slice", "sorted",
    "staticmethod", "str", "sum", "super", "tuple", "type", "vars", "zip",
})

#: The Go spec's predeclared functions and convertible predeclared types
#: — both are spelled exactly like calls at a call site (ADR-037).
GO_BUILTINS = frozenset({
    "append", "cap", "clear", "close", "complex", "copy", "delete",
    "imag", "len", "make", "max", "min", "new", "panic", "print",
    "println", "real", "recover",
    "bool", "byte", "complex64", "complex128", "error", "float32",
    "float64", "int", "int8", "int16", "int32", "int64", "rune",
    "string", "uint", "uint8", "uint16", "uint32", "uint64", "uintptr",
})

_BUILTINS = {"python": PY_BUILTINS, "go": GO_BUILTINS}

#: Which classes each language's providers can actually produce (C-32's
#: candidate fix, applied). A class absent from a language's set is one
#: that language *could not have reported* — so a Python tail with no
#: ``external-origin`` is not "no external origins", it is "no checker
#: that reports origins". Pinned beside the mechanisms that decide it:
#: checker origins come from tsextract alone; builtin lists exist for
#: Python and Go; ``import-binding`` is lane A's Python parse; the
#: ``local-binding`` collectors are Python/Go (ADR-046) and TS (checker);
#: ``path-call`` needs ``::``, which only Rust's grammar spells. The
#: test suite pins this table against :func:`classify`'s decision tree,
#: so a provider that learns a new class must widen its row here too.
CLASSES_AVAILABLE: dict[str, frozenset[str]] = {
    "python": frozenset({FALLBACK, LOCAL, IMPORT_BINDING, BUILTIN, ATTR,
                         UNCLASSIFIED}),
    "ts/js": frozenset({FALLBACK, LOCAL, NESTED, EXTERNAL_ORIGIN, ATTR,
                        UNCLASSIFIED}),
    "go": frozenset({FALLBACK, LOCAL, BUILTIN, ATTR, UNCLASSIFIED}),
    "rust": frozenset({FALLBACK, ATTR, PATH_CALL, UNCLASSIFIED}),
}

#: Every class, in decision order — the vocabulary the table draws from.
ALL_CLASSES = (FALLBACK, LOCAL, NESTED, EXTERNAL_ORIGIN, IMPORT_BINDING,
               BUILTIN, ATTR, PATH_CALL, UNCLASSIFIED)


def classes_available(coverage_rows: list[dict]) -> dict[str, list[str]]:
    """Per-language ``classes_available`` for the languages that have
    detected call sites in *coverage_rows* — the artifact form of C-32's
    note, keyed by the tail-view language bucket and listed in decision
    order. Emitted into ``graph.json`` so every consumer (the ingest
    summary, ``list_blind_spots``) states what a language's tail *could*
    have said next to what it did say, rather than holding a second copy
    of this table."""
    present = {language_of(row["file"]) for row in coverage_rows}
    return {
        lang: [c for c in ALL_CLASSES if c in CLASSES_AVAILABLE[lang]]
        for lang in sorted(present - {None})
        if lang in CLASSES_AVAILABLE
    }

#: Checker origin (tsextract v4) -> tail class.
_ORIGIN_CLASS = {"local": LOCAL, "nested": NESTED, "external": EXTERNAL_ORIGIN}


def language_of(file: str) -> str | None:
    """The tail-view language bucket for *file*, or None (e.g. ``.tf``)."""
    return _LANG_BY_EXT.get(PurePosixPath(file).suffix)


#: Languages whose grammar forbids a statement from ending in ``.`` — so
#: a previous line ending there can only be a wrapped chain, and reading
#: it is an observation. Python is excluded: its chains wrap with the dot
#: *leading* the next line (already read same-line), and a trailing dot
#: inside parentheses, while legal, is a shape this classifier abstains on.
_TRAILING_CHAIN_LANGS = frozenset({"go", "rust", "ts/js"})

#: Line openers that make the previous line prose, not code.
_COMMENT_OPENERS = ("//", "/*", "*", "#")


def _continuation(prev_text: str) -> str | None:
    """``attr``/``path`` when *prev_text* ends mid-chain, else None.

    gofmt *mandates* the trailing dot for a wrapped method chain
    (semicolon insertion forbids a leading one), which is why dagger's
    fluent integration tests put thousands of call openers at line
    starts. A trailing ``//`` comment is cut first so prose ending in a
    period cannot fake a chain; a line that *is* a comment never
    continues anything.
    """
    stripped = prev_text.strip()
    if not stripped or stripped.startswith(_COMMENT_OPENERS):
        return None
    code = prev_text.split("//", 1)[0].rstrip()
    if code.endswith("::"):
        return "path"
    if code.endswith("."):
        return "attr"
    return None


def _shape(
    line_text: str, name: str, col: int, prev_text: str | None = None
) -> str | None:
    """What immediately precedes *name* on its line: ``attr``, ``path``,
    ``bare`` — or None when the name cannot be located (wrapped chains
    put the terminal on a line the recorded text may not contain). When
    the name opens its line, *prev_text* (the previous source line, only
    passed for the trailing-chain languages) answers instead."""
    hits, start = [], 0
    while (found := line_text.find(name, start)) != -1:
        hits.append(found)
        start = found + 1
    if not hits:
        return None
    at = min(hits, key=lambda h: abs(h - col)) if col >= 0 else hits[0]
    j = at - 1
    while j >= 0 and line_text[j] in " \t":
        j -= 1
    if j < 0:
        if prev_text is not None and (cont := _continuation(prev_text)):
            return cont
        return "bare"
    if line_text[j] == ":" and j >= 1 and line_text[j - 1] == ":":
        return "path"
    if line_text[j] in ".?!":
        return "attr"
    return "bare"


class _Lines:
    """Source lines per file, read once, repo-root-relative, read-only."""

    def __init__(self, repo_root: Path):
        self.root = Path(repo_root)
        self.cache: dict[str, list[str]] = {}

    def line(self, file: str, number: int) -> str | None:
        if file not in self.cache:
            try:
                text = (self.root / file).read_text(errors="replace")
            except OSError:
                text = ""
            self.cache[file] = text.splitlines()
        lines = self.cache[file]
        return lines[number - 1] if 0 < number <= len(lines) else None


def classify(
    unresolved: list,
    repo_root: Path,
    origins: dict[tuple[str, int, str], str] | None = None,
    fallback: dict[tuple[str, int, str], tuple] | None = None,
    import_bindings: dict[str, frozenset[str]] | None = None,
    local_bindings: dict[str, tuple] | None = None,
) -> dict[str, Counter]:
    """Per-file tail classes for the *unresolved* call sites.

    *origins* is the checker's verdict per site (tsextract v4), keyed
    like the fallback dict: ``(file, line, name)``. *import_bindings*
    maps a file to the names its import statements bind (lane A's own
    parse — Python's ``FromImport`` bound names today).
    *local_bindings* maps a file to ``(name, start, end)`` tuples — lane
    A's sub-module bindings with enclosing-function extents (ADR-046);
    a bare site matches only when an extent spans its line, and a
    scope-contained local outranks an import binding because a binding
    inside the enclosing function shadows a module-level import. Every
    input site lands in exactly one class, so per file the counts sum
    to the coverage row's ``unresolved`` — an invariant the tests pin.
    """
    origins = origins or {}
    fallback = fallback or {}
    import_bindings = import_bindings or {}
    local_bindings = local_bindings or {}
    lines = _Lines(repo_root)
    out: dict[str, Counter] = {}
    for site in unresolved:
        key = (site.file, site.line, site.name)
        lang = language_of(site.file)
        if key in fallback:
            cls = FALLBACK
        elif key in origins and origins[key] in _ORIGIN_CLASS:
            cls = _ORIGIN_CLASS[origins[key]]
        else:
            text = lines.line(site.file, site.line)
            prev = (
                lines.line(site.file, site.line - 1)
                if lang in _TRAILING_CHAIN_LANGS
                else None
            )
            shape = (
                _shape(text, site.name, site.col, prev)
                if text is not None
                else None
            )
            builtins_ = _BUILTINS.get(lang or "", frozenset())
            bound = import_bindings.get(site.file, frozenset())
            locals_ = local_bindings.get(site.file, ())
            if shape == "bare" and any(
                name == site.name and start <= site.line <= end
                for (name, start, end) in locals_
            ):
                cls = LOCAL
            elif shape == "bare" and site.name in bound:
                cls = IMPORT_BINDING
            elif shape == "bare" and site.name in builtins_:
                cls = BUILTIN
            elif shape == "attr":
                cls = ATTR
            elif shape == "path":
                cls = PATH_CALL
            else:
                cls = UNCLASSIFIED
        out.setdefault(site.file, Counter())[cls] += 1
    return out


def rollup(coverage_rows: list[dict]) -> dict[str, dict]:
    """Per-language tail totals from ``resolution_coverage`` rows.

    Pure read over the artifact — the CLI summary and any other consumer
    derive the rollup rather than storing it twice.
    """
    langs: dict[str, dict] = {}
    for row in coverage_rows:
        lang = language_of(row["file"])
        if lang is None:
            continue
        agg = langs.setdefault(
            lang, {"sites": 0, "unresolved": 0, "tail": Counter()}
        )
        agg["sites"] += row["sites"]
        agg["unresolved"] += row["unresolved"]
        for cls, count in (row.get("tail") or {}).items():
            agg["tail"][cls] += count
    return langs


def directory_of(file: str, depth: int = 2) -> str:
    """The directory bucket for *file*: the first *depth* segments of its
    containing directory, or ``"."`` for a root-level file. Depth 2 is
    the summary's grain — deep enough to split a heterogeneous top-level
    directory (``sdk/python`` vs ``sdk/typescript``), shallow enough to
    stay a summary; the per-file rows remain the full-resolution record.
    """
    parts = PurePosixPath(file).parts[:-1][:depth]
    return "/".join(parts) if parts else "."


def rollup_directories(
    coverage_rows: list[dict], depth: int = 2
) -> dict[tuple[str, str], dict]:
    """Per-(directory, language) tail totals from ``resolution_coverage``
    rows, keyed ``(directory, language)`` with the same aggregate shape
    as :func:`rollup`.

    Language stays a key inside the directory because the capture
    statement is per-language by construction (each denominator is that
    language's detected call sites) — collapsing ``sdk/python`` and a
    stray shell of TS in the same directory into one number would blur
    whose sites went unresolved. Like :func:`rollup`, a pure read over
    the artifact: nothing here is stored twice.
    """
    dirs: dict[tuple[str, str], dict] = {}
    for row in coverage_rows:
        lang = language_of(row["file"])
        if lang is None:
            continue
        key = (directory_of(row["file"], depth), lang)
        agg = dirs.setdefault(
            key, {"sites": 0, "unresolved": 0, "tail": Counter()}
        )
        agg["sites"] += row["sites"]
        agg["unresolved"] += row["unresolved"]
        for cls, count in (row.get("tail") or {}).items():
            agg["tail"][cls] += count
    return dirs
