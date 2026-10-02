"""A Python reference lane B names with another symbol's name through an
imported module, refused (ADR-161, C-178).

Where a package's ``__init__.py`` re-exports by ``from .core import *``,
scip-python 0.6.6 answers every later ``<pkg>.<name>`` with the first one
it resolved through the re-export: ``pp.Word``, ``pp.Forward`` and
``pp.alphas`` all named ``CaselessLiteral#`` on pyparsing, across files.
The join would draw each as a ``semantic`` ``uses`` row of a class the
source never names there.

This module reads each Python reference against its file's text and lane
A's plain imports, and refuses one when both hold:

- the identifier at its line and column — the column read as scip-python
  writes it, in UTF-16 code units — is not the name the index gave it;
- that identifier is the member of a dotted chain ``root(.x)*.token``
  whose ``root`` the file binds by a plain ``import`` (``import a.b``
  binds ``a``; ``import a.b as c`` binds ``c``).

A module attribute that is what it says always names a symbol with the
token's name, so only an answer naming something else through a module
is refused. A mismatch through a *value* receiver (``self._link`` named
``Style``) is the index naming the receiver's class at an attribute it
has no symbol for, a true ``uses``, and is kept; so is a receiver bound
by ``from x import y``, which is not a module binding this rule can read.

A refused reference reaches neither the join nor anything that reads
resolutions; nothing is repaired and no replacement target is guessed.
The refusals are counted in one degradation record per ingest. Without
lane B for Python there is nothing to refuse and nothing is recorded (P6).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence

from hobbes.extract.evidence import RESOLUTION, Site
from hobbes.extract.pysource import ParsedFile, PlainImport

#: The stage a refusal is recorded under: the provider whose answer it is.
STAGE = "scip-python"

#: How many refused references the record names, at most.
EXAMPLES = 3

_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_IDENTIFIER = re.compile(r"[^\W\d]\w*")
#: A dotted chain of identifiers ending at the end of the text it is
#: searched in: ``root(.x)*``.
_CHAIN = re.compile(r"[^\W\d]\w*(?:\.[^\W\d]\w*)*\Z")


def module_names(parsed_file: ParsedFile) -> frozenset[str]:
    """The names *parsed_file* binds by a plain ``import`` statement: each
    one's alias, or its module's first dotted component."""
    return frozenset(
        item.alias or item.module.split(".", 1)[0]
        for item in parsed_file.imports
        if isinstance(item, PlainImport)
    )


def source_lines(text: str) -> list[str]:
    """*text* split into lines as the index counts them: at ``\\r\\n``,
    ``\\r`` or ``\\n`` only. ``str.splitlines`` also breaks at a form feed
    and the other separators Python does not end a line at, which would
    move every later line off the index's numbering."""
    return _LINE_BREAK.split(text)


def token_at(text_line: str, col16: int) -> str:
    """The identifier starting at UTF-16 column *col16* of *text_line*, or
    ``""`` where none starts there.

    A character above U+FFFF is two code units, so the string index trails
    the column by one for each such character before it. A column that
    falls inside one, or past the line, reads nothing.
    """
    index = _string_index(text_line, col16)
    if index is None:
        return ""
    match = _IDENTIFIER.match(text_line, index)
    return match.group() if match else ""


def refused(site: Site, text_line: str, names: frozenset[str]) -> bool:
    """Whether ADR-161 step 2 refuses *site*, a site on *text_line* in a
    file that binds *names* by a plain ``import``."""
    if site.kind != RESOLUTION:
        return False
    index = _string_index(text_line, site.col)
    if index is None:
        return False
    match = _IDENTIFIER.match(text_line, index)
    if match is None or match.group() == site.name:
        return False
    if index == 0 or text_line[index - 1] != ".":
        return False
    head = text_line[: index - 1]
    chain = _CHAIN.search(head)
    if chain is None:
        return False
    start = chain.start()
    # A chain hanging off something else — `f().os.x`, `a .os.x` — has no
    # root this rule can read.
    if start > 0 and head[start - 1] == ".":
        return False
    return chain.group().split(".", 1)[0] in names


def refuse(
    resolutions: Iterable[Site],
    python_files: Mapping[str, tuple[Sequence[str], frozenset[str]]],
) -> tuple[list[Site], list[tuple[str, int, str, str]]]:
    """Split *resolutions* into the kept sites and the refused references.

    *python_files* maps a repo-relative path to ``(lines, names)``: the
    file's text split into lines and :func:`module_names`. Only a site
    whose file is a key is read; every other one — another language's, an
    ``implements`` row, a file with no text — is kept untouched, and every
    kept site stays in its order.

    Returns ``(kept, refused_rows)``, a refused row being ``(path, line,
    token, name)``.
    """
    kept: list[Site] = []
    refused_rows: list[tuple[str, int, str, str]] = []
    for site in resolutions:
        entry = python_files.get(site.file)
        if entry is None or site.kind != RESOLUTION:
            kept.append(site)
            continue
        lines, names = entry
        if not 1 <= site.line <= len(lines):
            kept.append(site)
            continue
        text_line = lines[site.line - 1]
        if refused(site, text_line, names):
            refused_rows.append(
                (site.file, site.line, token_at(text_line, site.col), site.name)
            )
        else:
            kept.append(site)
    return kept, refused_rows


def record(refused_rows: Sequence[tuple[str, int, str, str]]) -> dict | None:
    """The degradation record for *refused_rows* (ADR-161 step 4), or
    ``None`` when nothing was refused."""
    if not refused_rows:
        return None
    examples = ", ".join(
        f"{path}:{line} `{token}` named `{name}`"
        for path, line, token, name in sorted(refused_rows)[:EXAMPLES]
    )
    count = len(refused_rows)
    noun = "reference" if count == 1 else "references"
    return {
        "path": ".",
        "stage": STAGE,
        "message": (
            f"{count} Python {noun} lane B named through an imported module with "
            "another symbol's name (scip-python's reading of a `from … import *` "
            "re-export, C-178) refused, so no edge is drawn there; "
            f"e.g. {examples}"
        ),
    }


def _string_index(text_line: str, col16: int) -> int | None:
    """The string index of UTF-16 column *col16* in *text_line*, or ``None``
    where the column is negative, inside a surrogate pair, or past the
    line's last character."""
    if col16 < 0:
        return None
    units = 0
    for index, char in enumerate(text_line):
        if units == col16:
            return index
        if units > col16:
            return None
        units += 2 if ord(char) > 0xFFFF else 1
    return None
