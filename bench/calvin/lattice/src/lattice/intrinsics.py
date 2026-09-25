"""The intrinsic inventory, read off clang's own headers: every `_mm…` and `_cvt…` signature.

Why an inventory is an instrument. Atlas-0 measured the standard block *inventing from sand* — an
absent name built of known stems gets a confident answer — and the intrinsic namespace is exactly that
sand (`calvin-experiments.md` §2). ADR-151's rule is that the model may hold the language and never the
target's facts, so the names and the types of the intrinsics a body may call are **given**, from the
headers of the compiler that will build the body, at the version that will build it. Nothing here is
remembered and nothing is guessed.

**The two forms this reads**, which are the two clang writes:

    static __inline__ __m256 __DEFAULT_FN_ATTRS256
    _mm256_fmadd_ps(__m256 __A, __m256 __B, __m256 __C)
    {

    static __inline__ __m128d __DEFAULT_FN_ATTRS _mm_add_sd(__m128d __a, __m128d __b)
    {

    #define _mm256_extractf128_pd(V, M) \\

A function's signature is normalised to one line, `__m256 _mm256_fmadd_ps(__m256 __A, __m256 __B,
__m256 __C)`: the storage and inline keywords and the attribute macros (`__DEFAULT_FN_ATTRS256` and
anything else spelled `__ALL_CAPS`, plus a written-out `__attribute__((…))`) are dropped, because they
say how the header declares the intrinsic and not what it takes or returns. A macro has no type, so its
signature is its `#define` line with the line continuation removed — the honest thing to hand a model
about a name whose expansion is text.

**What it reads wrongly rather than refuses.** This is a line scanner, not a preprocessor: it reads
every arm of an `#if`, it does not expand `__DEFAULT_FN_ATTRS`, and a declaration whose parameter list
runs past four lines is dropped. A name defined in two headers keeps the first header's entry, in the
order `index` was given them. Nothing here is specific to sqlite-vector.
"""

from __future__ import annotations

import re
from pathlib import Path

__all__ = ["index", "load"]

#: the namespaces this keeps: the SIMD intrinsics and the scalar conversions beside them.
_KEPT = re.compile(r"\A_(?:mm|cvt)")

_MACRO = re.compile(r"#\s*define\s+(_\w+)\(")
_ATTRIBUTE = re.compile(r"\b__attribute__\s*\(")

#: dropped from a return type: it says how the header declares the intrinsic, not what it returns.
_STORAGE = frozenset({"static", "extern", "inline", "__inline", "__inline__", "__extension__", "__forceinline"})
_ATTR_MACRO = re.compile(r"\A__[A-Z0-9_]+\Z")

#: how many lines of one declaration this will join before giving up on it.
_MAX_LINES = 4


def index(texts: dict[str, str]) -> dict[str, dict]:
    """Every intrinsic the given header texts define, by name.

    *texts* maps a header's name to its text; each entry is `{"name", "signature", "header", "macro"}`.
    The first header to define a name owns it.
    """
    found: dict[str, dict] = {}
    for header, text in texts.items():
        for entry in _read(header, text):
            found.setdefault(entry["name"], entry)
    return found


def load(include_dir: Path | str) -> dict[str, dict]:
    """`index` over every `.h` under *include_dir* — clang's `-print-file-name=include`.

    Header names are relative to *include_dir*, so an index carries no absolute path. Text is decoded
    with `errors="replace"`: a header is read for its declarations, not for its bytes.
    """
    root = Path(include_dir)
    paths = sorted(root.rglob("*.h"))
    texts = {
        str(path.relative_to(root)): path.read_text(encoding="utf-8", errors="replace") for path in paths
    }
    return index(texts)


# MARK: - reading one header -


def _read(header: str, text: str):
    """Every entry one header's text yields, in the order it is written."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        macro = _MACRO.match(stripped)
        if macro is not None:
            if _KEPT.match(macro.group(1)):
                yield {
                    "name": macro.group(1),
                    "signature": _one_line(stripped),
                    "header": header,
                    "macro": True,
                }
            i += 1
            continue
        if _starts_a_declaration(stripped):
            head, i = _head(lines, i)
            entry = _function(head, header)
            if entry is not None:
                yield entry
            continue
        i += 1


def _starts_a_declaration(stripped: str) -> bool:
    """The first line of clang's declaration form: `static` and an `inline` spelling."""
    if not stripped.startswith("static"):
        return False
    return "inline" in stripped


def _head(lines: list[str], i: int) -> tuple[str, int]:
    """The declaration starting at *lines[i]*, joined to one string, and the line after it."""
    parts = [lines[i].strip()]
    j = i
    while j + 1 < len(lines) and not _complete(" ".join(parts)):
        nxt = lines[j + 1].strip()
        if not nxt or nxt.startswith("{") or nxt.startswith("#"):
            break
        j += 1
        parts.append(nxt)
        if len(parts) >= _MAX_LINES:
            break
    return " ".join(parts), j + 1


def _complete(head: str) -> bool:
    """True when the head holds a closed parameter list — the declarator is all there."""
    text = _strip_attributes(head)
    depth = 0
    seen = False
    for char in text:
        if char == "(":
            depth += 1
            seen = True
        elif char == ")":
            depth -= 1
    return seen and depth == 0


def _function(head: str, header: str) -> dict | None:
    """One entry from a joined declaration, or `None` when it is not a kept intrinsic."""
    text = _strip_attributes(head)
    at = text.find("(")
    if at == -1:
        return None
    close = _match_paren(text, at)
    if close is None:
        return None
    tokens = text[:at].split()
    if not tokens:
        return None
    stars, name = _split_stars(tokens[-1])
    if not _KEPT.match(name):
        return None
    returns = _return_type(tokens[:-1] + ([stars] if stars else []))
    if not returns:
        return None
    params = " ".join(text[at : close + 1].split())
    return {"name": name, "signature": f"{returns} {name}{params}", "header": header, "macro": False}


def _return_type(tokens: list[str]) -> str:
    """The declaration's tokens with the storage keywords and the attribute macros dropped."""
    kept: list[str] = []
    for token in tokens:
        stars, bare = _split_stars(token)
        if bare in _STORAGE or _ATTR_MACRO.match(bare) is not None:
            if stars:
                kept.append(stars)
            continue
        kept.append(token)
    return " ".join(kept).strip()


def _split_stars(token: str) -> tuple[str, str]:
    """A token's leading `*`s and the rest: `*__DEFAULT_FN_ATTRS` is a pointer and an attribute."""
    bare = token.lstrip("*")
    return token[: len(token) - len(bare)], bare


def _strip_attributes(text: str) -> str:
    """The text with every written-out `__attribute__((…))` removed, parens matched."""
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
    for i in range(open_at, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


def _one_line(text: str) -> str:
    """A `#define` line as one line: the continuation backslash gone, the runs of spaces collapsed."""
    return " ".join(text.rstrip().rstrip("\\").split())
