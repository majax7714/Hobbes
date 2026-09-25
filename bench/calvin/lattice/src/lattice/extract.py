"""**E1-c's parse:** the body a completion offers, or the reason there is none.

A model answering E1's prompt writes prose, then a fenced block, then more prose, and the runner needs
one thing out of it: the definition of the cell's own name, braces included, exactly as the model wrote
it. This module is that read, and it is deliberately narrow.

**The first fenced block, whatever its tag.** Instruct models write ```` ```c ````, ```` ```C ````,
```` ```cpp ```` and a bare ```` ``` ````, so the tag is not read; and the rule is *the first* block even
when a later one would parse, because "take whichever block works" is a rule that quietly rewards a model
for a second attempt inside one completion and makes the arms incomparable. A block with no closing
fence — the shape a completion truncated at `max_tokens` has — runs to the end of the text.

**The definition is found by `scan`,** the same scanner the lattice reads the target with, so a helper
the model wrote above the target is skipped by name rather than by position, and the body returned is the
file's own bytes from `{` to its matching `}`.

**The parameter names it wrote come back with the body.** A model writes its own whole definition, and
it renames the target's parameters as it goes — `v1, v2` where the target writes `va, vb`, or `a_vec`,
`x`, `s1`. The grafted body then fails on names that are its own (E1-g's record, limit 1), so the runner
needs to know which names those were: `params` is the definition's parameter names in order, and
:func:`params` reads them off any signature, the target's included. It is `None` when there is no body,
because a completion with no definition has no parameters either.

**Every failure says which one it is.** No block, no definition of that name in the first block, a text
the scanner refuses, a body `holes` would not write: four reasons, one per case, and `body` is `None` for
all four. The caller files them as class `no-body` (E1-c), which is reported beside `compile` and never
folded into it — a model that wrote nothing usable and a model that wrote something that will not build
are two different results. Nothing here classifies, and nothing here keeps or discards the model's text:
that is the runner's, and it keeps the text whole.
"""

from __future__ import annotations

import re

from . import holes
from .scan import ScanError, scan

__all__ = ["NO_BLOCK", "extract", "first_block", "params"]

#: The reason there was nothing to read at all.
NO_BLOCK = "no fenced code block"

_FENCE = "```"

_IDENTIFIER = re.compile(r"[A-Za-z_]\w*")


def extract(completion: str, name: str) -> dict:
    """The definition of *name* in *completion*'s first fenced block.

    Returns `{"body", "reason", "block", "params"}`: the body from `{` to its matching `}`, `reason`
    `None` and the definition's own parameter names in order, or `body` `None`, `params` `None` and the
    reason it could not be read. `block` is the 1-based index of the fenced block that was read — always
    the first, so always 1 — and `None` when the completion had no fence at all.
    """
    block = first_block(completion)
    if block is None:
        return {"body": None, "reason": NO_BLOCK, "block": None, "params": None}

    try:
        scanned = scan(block)
    except ScanError as refusal:
        return {"body": None, "reason": f"the first fenced block does not scan: {refusal}", "block": 1, "params": None}

    found = next((fn for fn in scanned.functions if fn.name == name), None)
    if found is None:
        return {"body": None, "reason": f"the first fenced block defines no {name}", "block": 1, "params": None}

    body = block[found.body_span.start : found.body_span.end]
    refused = _refused(body)
    if refused is not None:
        return {
            "body": None,
            "reason": f"the body of {name} would not be written: {refused}",
            "block": 1,
            "params": None,
        }
    return {"body": body, "reason": None, "block": 1, "params": params(found.signature)}


def params(signature: str) -> list[str]:
    """The parameter names of a C signature, in order. `(void)` and `()` give `[]`.

    The name is the **last identifier of each comma-separated parameter**, which is where C puts it
    however the declarator is written: `const float *a`, `const float* a` and `int a[]` all give `a`.
    Commas inside a nested parameter list do not split, so a function-pointer parameter stays one
    parameter — though **its** name is then read wrongly, the last identifier being inside the pointer's
    own list (`int (*cmp)(const void *, const void *)` reads as `void`). An unnamed parameter
    (`const void *`) reads as the last word of its type in the same way. Both cost nothing here: the one
    use of these names is to compare them with identifiers a compiler said resolve nowhere, and no
    kernel signature in the lattice takes a function pointer or leaves a parameter unnamed.

    A signature that does not end in a parameter list gives `[]` — there is nothing to read, and
    guessing would be worse than saying nothing.
    """
    head = signature.strip()
    if not head.endswith(")"):
        return []
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
        return []

    inside = head[i + 1 : -1]
    if inside.strip() == "void":
        return []
    names = []
    for part in _split(inside):
        found = _IDENTIFIER.findall(part)
        if found:
            names.append(found[-1])
    return names


def _split(parameters: str) -> list[str]:
    """One string per parameter: split on the commas that are not inside brackets of their own."""
    parts, depth, start = [], 0, 0
    for at, char in enumerate(parameters):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(parameters[start:at])
            start = at + 1
    parts.append(parameters[start:])
    return [part for part in parts if part.strip()]


def first_block(completion: str) -> str | None:
    """The text inside the first fenced block, tag dropped, or `None` if the completion opens none.

    An unclosed fence runs to the end of the text, which is what a completion cut off at `max_tokens`
    looks like.
    """
    lines = completion.splitlines()
    opened = None
    for at, line in enumerate(lines):
        if line.strip().startswith(_FENCE):
            opened = at
            break
    if opened is None:
        return None
    for at in range(opened + 1, len(lines)):
        if lines[at].strip().startswith(_FENCE):
            return "\n".join(lines[opened + 1 : at])
    return "\n".join(lines[opened + 1 :])


def _refused(body: str) -> str | None:
    """The reason `holes` would refuse this body, or `None`.

    `holes.fill` is that refusal's one public form, and the hole is the smallest punched text there is:
    the point is to ask `holes` the question rather than to re-implement its answer here, since it is the
    module that will be handed this body.
    """
    try:
        holes.fill(holes.HOLE, body)
    except holes.UnbalancedBody as refusal:
        return str(refusal)
    return None
