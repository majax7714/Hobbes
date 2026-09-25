"""**C-1, the facts arm** (`calvin-experiments.md` §5.3): the callees of a cell, from the ledger.

ADR-151's rule is that the model may learn the language and never the target's facts; the facts come
from the ledger at the SHA, every time. This module is that ledger's reader for one field — what a
kernel body calls — and it reads **two** instruments, because neither alone answers:

| instrument | what it has | what it does not |
|---|---|---|
| Hobbes' graph (`derived/graph.json`) | every in-repo callee, resolved, with a tier and `file:line` evidence | **no edge to an intrinsic**: `_mm256_fmadd_ps` is not defined in the repo |
| the clang key (`derived/oracle.json`) | every callee the compiler saw, intrinsics included, and the `mode` a macro was reached through | no tier, no in-repo notion — a `caller` is a bare name |

So the graph is asked first and the key fills what the graph cannot see. **Every row names where it came
from**: `provenance` is `hobbes:<tier>` or `clang-key:<mode>`, and a callee both instruments name keeps
the graph's row with `"also": "clang-key"` beside it — the graph's answer is the one with a tier, and
the key agreeing with it is worth recording, not worth overwriting with.

**The order is first use.** The graph's rows come first, in the order of their first evidence line in
the cell's file; then the key's, in the order of their first site. A **macro-mode** site is ordered
after every direct one: the name is not written in the body at all (`_mm256_fmadd_ps` is reached
through `MM256_FMA_PS`, which already stands in the body's own order), so the line it is reported at is
the expansion's, not a use's.

**Matching a site to a cell.** The key's `caller` is a bare name and a `static` name can repeat across
files, so a site is this cell's only when its `pos.path` is the cell's file *and* its line falls inside
the cell's body span. Nothing is matched by name alone.

**A header macro is named as the source wrote it** (session `189e`'s review). A key site in mode `macro`
names what the macro *expands to*, and that is two different facts wearing one shape. Where the macro is
the repo's own, the expansion is the real intrinsic and it is the answer: `MM256_FMA_PS` expands to
`_mm256_fmadd_ps`, which is what the body does. Where the macro is one of clang's, the expansion is
compiler internals no one writes — `_mm256_extracti128_si256` reports as `__builtin_ia32_extract128i256`,
and `INFINITY` as `__builtin_inff`. Handing those to a model as "what this cell calls" is handing it
names it must not use. So, per macro-mode site:

- the **written token** at the site's own line and column decides. Its target is kept when that token is
  an in-repo macro — one the graph names, or one the cell's own file `#define`s — or when the target is
  itself a function in the intrinsic index (`_mm256_undefined_ps` is a real intrinsic a macro reaches);
- every other macro-mode target is dropped into `Callees.dropped` with the reason, never silently;
- the header macros the body *does* write are then added from its own identifier tokens that the index
  marks `macro: true`, with `provenance` `clang-headers:macro` and the index's `#define` line, in the
  body's own order beside the direct sites — because unlike an expansion, they *are* written there;
- with no index, none of that is added and `missing` says the index was not there to ask.

`static`-mode targets are untouched: a libm call and a `__builtin_popcount` written out in the source
are names the body really writes.

**What is missing is said.** With no graph, or no key, or no intrinsic index, `callees` returns the rows
it can and lists what was not there to ask (`Callees.missing`). It never fills a gap by inference: a
callee this module did not read is a callee it does not name.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import re

from .cells import Cell, Lattice
from .scan import scan

__all__ = ["Callees", "Facts", "callees", "module_paths", "symbol_for", "load"]

_IDENT = re.compile(r"[A-Za-z_]\w*")

#: What a dropped macro-mode target is dropped for. One reason, because there is one rule.
DROPPED = "a header macro's expansion, not a name the source wrote"


class Callees(list):
    """The callee rows, and the two honesty fields beside them.

    A plain `list` of rows, so it dumps as a JSON array. `missing` names the instruments that were not
    there to ask, and an empty `missing` is the claim that every instrument answered. `dropped` names
    the key's macro-mode targets this module refused to call callees, with the reason.
    """

    def __init__(self, rows=(), missing=(), dropped=()):
        super().__init__(rows)
        self.missing: list[str] = list(missing)
        self.dropped: list[dict] = list(dropped)


@dataclass(frozen=True)
class Facts:
    """The ledger a task record is filled from: the graph, the clang key, the intrinsic index.

    Any of the three may be `None` — the arms of §5.3 differ in what they carry, and a missing one is
    reported rather than worked around.
    """

    graph: dict | None = None
    key: dict | None = None
    intrinsics: dict | None = None

    def callees(self, lattice: Lattice, cell: Cell) -> Callees:
        """This cell's callees, from whichever of the three this ledger holds."""
        return callees(lattice, cell, self.graph, self.key, self.intrinsics)

    def source(self) -> dict:
        """Where the facts came from: the graph's SHA and the Hobbes that built it, the key's oracle."""
        built_by = (self.graph or {}).get("built_by") or {}
        return {
            "graph": None if self.graph is None else {"sha": self.graph.get("sha"), "version": built_by.get("version")},
            "key": None if self.key is None else {"oracle": self.key.get("oracle")},
            "intrinsics": None if self.intrinsics is None else {"names": len(self.intrinsics)},
        }


def load(graph: Path | str | None = None, key: Path | str | None = None, intrinsics: Path | str | None = None) -> Facts:
    """A `Facts` from the JSON on disk: `derived/graph.json`, `derived/oracle.json`, an index file."""
    return Facts(graph=_read(graph), key=_read(key), intrinsics=_read(intrinsics))


def callees(
    lattice: Lattice, cell: Cell, graph: dict | None, key: dict | None, intrinsics: dict | None = None
) -> Callees:
    """One row per distinct callee of *cell*, in first-use order, each naming where it came from."""
    paths = module_paths(graph) if graph is not None else {}
    files = _Files(lattice, paths)
    rows: list[dict] = []
    at: dict[str, int] = {}
    missing: list[str] = []
    dropped: list[dict] = []

    if graph is None:
        missing.append("graph")
    else:
        symbol = symbol_for(graph, cell, paths)
        if symbol is None:
            missing.append(f"graph: no symbol for {cell.name} in {cell.file}")
        else:
            for row in _graph_rows(graph, symbol, cell, files):
                at.setdefault(row["name"], len(rows))
                rows.append(row)

    if key is None:
        missing.append("clang-key")
    else:
        if cell.file not in set(key.get("files") or ()):
            missing.append(f"clang-key: {cell.file} is not one of the key's files")
        written = _written_macros(lattice, cell, intrinsics)
        for order, row in sorted(
            list(_key_rows(key, cell, intrinsics, graph, lattice, dropped)) + written, key=lambda pair: pair[0]
        ):
            seen = at.get(row["name"])
            if seen is not None:
                # a callee both instruments name keeps the graph's row, with the agreement beside it;
                # the same name on a second site of its own is simply the same callee again
                if rows[seen]["provenance"].startswith("hobbes:"):
                    rows[seen]["also"] = "clang-key"
                continue
            at[row["name"]] = len(rows)
            rows.append(row)
        if intrinsics is None:
            missing.append("intrinsics")

    # one row per distinct expansion, not per site: four uses of `_mm256_extracti128_si256` are one fact
    seen_drops: dict[tuple, dict] = {}
    for row in dropped:
        seen_drops.setdefault((row["name"], row["wrote"]), row)
    return Callees(rows, missing, list(seen_drops.values()))


# MARK: - the graph -


def symbol_for(graph: dict, cell: Cell, paths: dict[str, str] | None = None) -> dict | None:
    """The graph symbol that is this cell: its name, defined in its file.

    Public because G-graph asks the same question of two graphs (`graphgrade`), and asking it twice in
    two modules is how the two would drift.
    """
    paths = module_paths(graph) if paths is None else paths
    found = [
        symbol
        for symbol in graph.get("symbols") or ()
        if symbol.get("name") == cell.name and paths.get(symbol.get("module")) == cell.file
    ]
    if not found:
        return None
    on_the_line = [symbol for symbol in found if symbol.get("line") == cell.signature_span.line]
    return (on_the_line or found)[0]


def module_paths(graph: dict) -> dict[str, str]:
    """Each module node's repo-relative path: `src/distance-avx2` is `src/distance-avx2.c`."""
    paths = {}
    for node in graph.get("nodes") or ():
        if node.get("kind") == "module" and node.get("path"):
            paths[node["id"]] = node["path"]
    for symbol in graph.get("symbols") or ():
        module = symbol.get("module")
        if module and module not in paths:
            paths[module] = module if Path(module).suffix else f"{module}.c"
    return paths


def _graph_rows(graph: dict, symbol: dict, cell: Cell, files: _Files):
    """The `calls` edges out of *symbol*, in the order of their first evidence line in the cell's file."""
    symbols = {entry.get("id"): entry for entry in graph.get("symbols") or ()}
    edges = [
        edge
        for edge in graph.get("symbol_edges") or ()
        if edge.get("from") == symbol.get("id") and edge.get("type") == "calls"
    ]
    for edge in sorted(edges, key=lambda edge: _first_evidence(edge, cell.file)):
        target = symbols.get(edge.get("to")) or {}
        name = target.get("name") or str(edge.get("to"))
        yield {
            "name": name,
            "kind": target.get("kind"),
            "signature": _defined_signature(target, files),
            "provenance": f"hobbes:{edge.get('tier')}",
        }


def _first_evidence(edge: dict, file: str) -> int:
    """The edge's first evidence line in *file*, or its first anywhere, or last of all with none."""
    lines = [row.get("line") for row in edge.get("evidence") or () if row.get("path") == file]
    if not lines:
        lines = [row.get("line") for row in edge.get("evidence") or ()]
    lines = [line for line in lines if isinstance(line, int)]
    return min(lines) if lines else 1 << 30


def _defined_signature(symbol: dict, files: _Files) -> str | None:
    """A callee's signature from the file that defines it: a function's head, a macro's `#define` line."""
    text = files.text(symbol.get("module"))
    if text is None:
        return None
    line = symbol.get("line")
    if symbol.get("kind") == "macro":
        return _define_line(text, line)
    definitions = [fn for fn in files.scanned(symbol["module"]).functions if fn.name == symbol.get("name")]
    if not definitions:
        return None
    on_the_line = [fn for fn in definitions if fn.signature_span.line == line]
    return (on_the_line or definitions)[0].signature


def _define_line(text: str, line: int | None) -> str | None:
    """The `#define` at that 1-based line, the continuation backslash dropped, otherwise verbatim."""
    if not isinstance(line, int):
        return None
    lines = text.splitlines()
    if not 1 <= line <= len(lines):
        return None
    return lines[line - 1].rstrip().rstrip("\\").rstrip()


class _Files:
    """The files a signature may come from, read and scanned once each: the lattice's, then the tree's.

    *paths* is the graph's own module-to-path map, so the file a symbol is looked for in is the file the
    graph says it is in; a module the map does not name falls back to the `.c` the graph's ids imply.
    """

    def __init__(self, lattice: Lattice, paths: dict[str, str]):
        self.lattice = lattice
        self.paths = paths
        self._by_file = {source.file: source for source in lattice.sources.values()}
        self._texts: dict[str, str | None] = {}
        self._scans: dict[str, object] = {}

    def path(self, module: str | None) -> str | None:
        if not module:
            return None
        return self.paths.get(module) or (module if Path(module).suffix else f"{module}.c")

    def text(self, module: str | None) -> str | None:
        file = self.path(module)
        if file is None:
            return None
        if file not in self._texts:
            source = self._by_file.get(file)
            if source is not None:
                self._texts[file] = source.text
            else:
                whole = self.lattice.root / file
                try:
                    self._texts[file] = whole.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    self._texts[file] = None
        return self._texts[file]

    def scanned(self, module: str):
        file = self.path(module)
        if file not in self._scans:
            source = self._by_file.get(file)
            text = self.text(module)
            self._scans[file] = source.scanned if source is not None else scan(text or "")
        return self._scans[file]


# MARK: - the clang key -


def _key_rows(
    key: dict, cell: Cell, intrinsics: dict | None, graph: dict | None, lattice: Lattice, dropped: list[dict]
):
    """`(order, row)` for each target of the key's sites inside this cell's body.

    A macro-mode target survives only under the rule in the module docstring; the rest go to *dropped*.
    """
    in_repo = _in_repo_macros(graph, lattice, cell)
    text = lattice.sources[cell.isa].text
    for site in [site for site in key.get("sites") or () if _is_the_cells(site, cell)]:
        mode = site.get("mode")
        wrote = _token_at(text, (site.get("pos") or {}).get("line"), site.get("col"))
        for target in site.get("targets") or ():
            name = target.get("name")
            if not name:
                continue
            entry = (intrinsics or {}).get(name) or {}
            if mode == "macro" and wrote not in in_repo and not (entry and not entry.get("macro")):
                dropped.append({"name": name, "wrote": wrote, "mode": mode, "reason": DROPPED})
                continue
            yield _site_order(site), {
                "name": name,
                "kind": target.get("kind"),
                "mode": mode,
                "signature": entry.get("signature"),
                "provenance": f"clang-key:{mode}",
            }


def _written_macros(lattice: Lattice, cell: Cell, intrinsics: dict | None) -> list[tuple]:
    """`(order, row)` for each of clang's own macros the body writes, at the token that writes it.

    Read off the body's identifier tokens — masked, so a name in a comment or a string is not one — and
    kept only where the index says that name is a `#define`. Without an index there is nothing to say
    a token is a header macro, and nothing is added.
    """
    if not intrinsics:
        return []
    source = lattice.sources[cell.isa]
    masked = source.scanned.masked[cell.body_span.start : cell.body_span.end]
    base = cell.body_span.start
    found: list[tuple] = []
    seen: set[str] = set()
    for token in _IDENT.finditer(masked):
        name = token.group(0)
        entry = intrinsics.get(name)
        if name in seen or not entry or not entry.get("macro"):
            continue
        seen.add(name)
        at = base + token.start()
        line = source.text.count("\n", 0, at) + 1
        col = at - (source.text.rfind("\n", 0, at) + 1) + 1
        found.append(
            (
                (0, line, col),
                {
                    "name": name,
                    "kind": "macro",
                    "mode": "macro",
                    "signature": entry.get("signature"),
                    "provenance": "clang-headers:macro",
                },
            )
        )
    return found


def _in_repo_macros(graph: dict | None, lattice: Lattice, cell: Cell) -> frozenset[str]:
    """The macro names the repo defines: the graph's, and the cell's own file's `#define`s.

    Two readings of one fact, and both are reads rather than inferences — the graph knows the whole
    tree, and the scanner knows this file even when no graph was given.
    """
    named = {
        symbol.get("name")
        for symbol in (graph or {}).get("symbols") or ()
        if symbol.get("kind") == "macro" and symbol.get("name")
    }
    return frozenset(named | set(lattice.sources[cell.isa].scanned.defines))


def _token_at(text: str, line: int | None, col: int | None) -> str | None:
    """The identifier token covering the 1-based (*line*, *col*) of *text*, or `None` if none does."""
    if not isinstance(line, int) or not isinstance(col, int):
        return None
    lines = text.splitlines()
    if not 1 <= line <= len(lines):
        return None
    row = lines[line - 1]
    at = col - 1
    if not 0 <= at < len(row) or not (row[at].isalnum() or row[at] == "_"):
        return None
    start = at
    while start > 0 and (row[start - 1].isalnum() or row[start - 1] == "_"):
        start -= 1
    found = _IDENT.match(row[start:])
    return found.group(0) if found is not None else None


def _is_the_cells(site: dict, cell: Cell) -> bool:
    """A site is this cell's when the caller's name, its file and its line all say so."""
    if site.get("caller") != cell.name:
        return False
    pos = site.get("pos") or {}
    if pos.get("path") != cell.file:
        return False
    line = pos.get("line")
    return isinstance(line, int) and cell.body_span.line <= line <= cell.body_span.end_line


def _site_order(site: dict) -> tuple[int, int, int]:
    """Direct sites in their line and column order, then the macro-reached ones in theirs."""
    pos = site.get("pos") or {}
    return (1 if site.get("mode") == "macro" else 0, pos.get("line") or 0, site.get("col") or 0)


def _read(where: Path | str | None) -> dict | None:
    if where is None:
        return None
    return json.loads(Path(where).read_text(encoding="utf-8"))
