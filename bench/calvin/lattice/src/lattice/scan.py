"""A hand scanner for C source text: enough of C to find where a function's body begins and ends.

It is not a parser and does not want to be one. It masks what cannot hold code — comments, string and
character literals, preprocessor lines — and then walks the top level for `… (…) {` followed by a
matching `}`. That is all the lattice needs: the kernel files it reads are hand-written definitions at
the top level, and a hole is punched by byte span, never by re-printing what was parsed.

**Offsets are character indices into the text given**, not byte offsets: the target's sources carry
non-ASCII comment characters (`8×bf16` in `distance-avx2.c`), so the two differ, and every consumer in
this package slices the same `str` these offsets came from.

**What it does not handle**, and will read wrongly rather than refuse:

- K&R definitions (`int f(a) int a; { … }`): the parameter declarations between `)` and `{` make the
  chunk before the brace end in `;`, so the definition is missed.
- A definition produced by a macro (`DEFINE_KERNEL(f32, l2)`): there is no `)`-then-`{` at the top
  level to see, and no preprocessor runs here.
- A declarator that returns a function pointer (`void (*f(int))(int)`): the name is not the identifier
  before the last parameter list, so the definition is missed.
- A block comment opened on a preprocessor line and closed on a later one; a `//` comment continued
  with a trailing backslash. Both are masked as if the line ended where it appears to.
- Trigraphs and digraphs.

One thing it does that a compiler does not, and that is deliberate: **every arm of an `#if`/`#else` is
read.** Masking the directives leaves both branches as text, so a name defined once per arm — as
`distance-cpu.c` defines `cpu_supports_neon` three times — is returned once per definition. No
preprocessor runs here and no build's `-D` flags are known, so choosing an arm would be a guess.

Nothing here is specific to sqlite-vector; the lattice's knowledge of the target lives in `cells`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["Span", "FunctionDef", "ScanResult", "ScanError", "mask", "scan"]

_DEFINE = re.compile(r"#\s*define\s+([A-Za-z_]\w*)")
_TRAILING_IDENT = re.compile(r"[A-Za-z_]\w*\Z")

# keywords that can end a parenthesised head; none of them can start a top-level definition, and
# refusing them keeps a stray `if (…) {` from being read as one.
_NOT_A_NAME = frozenset({"if", "for", "while", "switch", "do", "else", "return", "sizeof", "catch"})


class ScanError(Exception):
    """The text does not scan: a brace closes at the top level that nothing opened."""


@dataclass(frozen=True)
class Span:
    """A half-open range `[start, end)` of the text, with the 1-based lines it starts and ends on."""

    start: int
    end: int
    line: int
    end_line: int


@dataclass(frozen=True)
class FunctionDef:
    """One top-level function definition: where its signature is, where its body is, and how it is declared."""

    name: str
    signature: str
    signature_span: Span
    body_span: Span
    static: bool
    inline: bool


@dataclass(frozen=True)
class ScanResult:
    """Everything one pass over a file yields: its definitions, its `#define` names, its masked text."""

    functions: tuple[FunctionDef, ...]
    defines: tuple[str, ...]
    masked: str


def mask(text: str) -> str:
    """The text with comments, literals and preprocessor lines blanked to spaces, newlines kept.

    Same length as the input, so an offset into one is an offset into the other.
    """
    masked, _ = _mask(text)
    return masked


def scan(text: str) -> ScanResult:
    """Scan one C translation unit's text for its top-level function definitions and `#define` names."""
    masked, defines = _mask(text)
    functions: list[FunctionDef] = []
    chunk_start = 0
    i, n = 0, len(masked)
    while i < n:
        c = masked[i]
        if c == ";":
            chunk_start = i + 1
        elif c == "}":
            raise ScanError(f"unbalanced '}}' at offset {i} (line {_line_of(text, i)})")
        elif c == "{":
            close = _match_brace(masked, i)
            found = _definition_name(masked[chunk_start:i])
            if found is not None:
                name, name_offset = found
                sig_start = _signature_start(masked, chunk_start, i)
                functions.append(_definition(text, masked, name, chunk_start + name_offset, sig_start, i, close))
            chunk_start = close + 1
            i = close
        i += 1
    return ScanResult(tuple(functions), defines, masked)


# MARK: - masking -


def _mask(text: str) -> tuple[str, tuple[str, ...]]:
    out = list(text)
    defines: list[str] = []
    seen: set[str] = set()
    n = len(text)
    i = 0
    fresh = True  # nothing but whitespace seen on this line yet
    while i < n:
        c = text[i]
        if c == "\n":
            fresh = True
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        if fresh and c == "#":
            i, logical = _blank_logical_line(text, out, i)
            found = _DEFINE.match(logical.lstrip())
            if found is not None and found.group(1) not in seen:
                seen.add(found.group(1))
                defines.append(found.group(1))
            fresh = True
            continue
        fresh = False
        pair = text[i : i + 2]
        if pair == "//":
            while i < n and text[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if pair == "/*":
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
            for k in range(i, end):
                if text[k] != "\n":
                    out[k] = " "
            i = end
            continue
        if c in "\"'":
            i = _blank_literal(text, out, i)
            continue
        i += 1
    return "".join(out), tuple(defines)


def _blank_logical_line(text: str, out: list[str], i: int) -> tuple[int, str]:
    """Blank a preprocessor line and every line a trailing backslash joins to it. Returns (next index, its text)."""
    n = len(text)
    parts: list[str] = []
    while i < n:
        stop = text.find("\n", i)
        if stop == -1:
            stop = n
        for k in range(i, stop):
            out[k] = " "
        line = text[i:stop].rstrip("\r")
        joined = line.endswith("\\")
        parts.append(line[:-1] if joined else line)
        i = stop + 1 if stop < n else n
        if not joined:
            break
    return i, " ".join(parts)


def _blank_literal(text: str, out: list[str], i: int) -> int:
    """Blank a string or character literal, escapes included. An unterminated one stops at the newline."""
    quote = text[i]
    n = len(text)
    out[i] = " "
    i += 1
    while i < n and text[i] != quote:
        if text[i] == "\n":
            return i
        if text[i] == "\\" and i + 1 < n:
            out[i] = " "
            i += 1
            if text[i] != "\n":
                out[i] = " "
                i += 1
            continue
        out[i] = " "
        i += 1
    if i < n:
        out[i] = " "
        i += 1
    return i


# MARK: - definitions -


def _match_brace(masked: str, open_at: int) -> int:
    depth = 0
    for i in range(open_at, len(masked)):
        if masked[i] == "{":
            depth += 1
        elif masked[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ScanError(f"'{{' at offset {open_at} is never closed")


def _definition_name(chunk: str) -> tuple[str, int] | None:
    """The function name in the text before a top-level `{`, and its offset in that text.

    `None` when the chunk is not a definition's head: an initialiser (`… = {`), a struct body, a
    `do {`. The test is C's own — a definition's head ends in the parameter list's `)`.
    """
    head = chunk.rstrip()
    if not head.endswith(")"):
        return None
    depth = 0
    i = len(head) - 1
    while i >= 0:
        if head[i] == ")":
            depth += 1
        elif head[i] == "(":
            depth -= 1
            if depth == 0:
                break
        i -= 1
    if i < 0 or depth != 0:
        return None
    before = head[:i].rstrip()
    found = _TRAILING_IDENT.search(before)
    if found is None or found.group(0) in _NOT_A_NAME:
        return None
    return found.group(0), found.start()


def _signature_start(masked: str, chunk_start: int, brace: int) -> int:
    """Where the signature really begins: the run of non-blank lines ending at the `{`.

    Everything the mask blanked — the `#endif` above a definition, a `// MARK:` banner, the comment
    the author wrote about it — is a blank line by then, so this drops it and keeps the declaration.
    """
    line_start = masked.rfind("\n", 0, brace) + 1
    while True:
        previous_end = line_start - 1
        if previous_end < chunk_start:
            break
        previous_start = masked.rfind("\n", 0, previous_end) + 1
        if previous_start < chunk_start or not masked[previous_start:previous_end].strip():
            break
        line_start = previous_start
    i = max(line_start, chunk_start)
    while i < brace and masked[i] in " \t":
        i += 1
    return i


def _definition(
    text: str, masked: str, name: str, name_at: int, sig_start: int, brace: int, close: int
) -> FunctionDef:
    signature = text[sig_start:brace].rstrip()
    declared = masked[sig_start:name_at]
    return FunctionDef(
        name=name,
        signature=signature,
        signature_span=Span(
            start=sig_start,
            end=sig_start + len(signature),
            line=_line_of(text, sig_start),
            end_line=_line_of(text, sig_start + len(signature)),
        ),
        body_span=Span(
            start=brace,
            end=close + 1,
            line=_line_of(text, brace),
            end_line=_line_of(text, close),
        ),
        static=re.search(r"\bstatic\b", declared) is not None,
        inline=re.search(r"\binline\b", declared) is not None,
    )


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1
