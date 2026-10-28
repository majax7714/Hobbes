"""Tiered graph views of a repo, grouped by folder (DEC-014).

``build`` turns ``graph.json`` (plus ``tests.json`` and ``interfaces.json``
when present) into a document of **views**. A view is one folder's chart:
at most ``MAX_BOXES`` boxes (its sub-folders and files) and the rolled-up
edges between them. Selecting a folder box opens that folder's view, from
the repo (level 0) down to modules; selecting a module opens its **module
view** (level 3): its top-level symbols. An "entry points" box on the repo
view opens the **flows** (level 4): from each CLI entry point and route,
the calls a function makes, in call-site order; each step opens its own.

Rules, all deterministic:

- modules are grouped by ``path``, never by id; test fixtures
  (``FIXTURE_DIRS``) are dropped, with the entry points and routes they
  define;
- test modules stay out of the boxes; each test counts on the box holding
  the module it reaches most;
- a folder that only wraps one folder is merged with it (``src/hobbes``),
  unless it is a language root;
- folders holding a build manifest are marked as language roots;
  extraction records no links between languages, so roots show
  unconnected (a note says so);
- a folder with too many entries groups its files by filename prefix,
  then folds the smallest boxes into "+N more";
- edges count imports and calls/uses separately with sample ``path:line``s;
  edges inside a cycle are marked; each box gets a level (one more than the
  highest box it depends on); edges leaving a view become stubs named by
  the sibling folder they reach;
- a module view's boxes are its top-level symbols, a class with its
  methods; they are grouped and folded like files (name affixes, then
  "+N more"); edges are calls and uses between them; stubs are the other
  modules they call or are called from, plus the module's imports; each
  box counts the tests guarding it: tests that reach one of its symbols
  from a file that imports the module or sits in its folder (all tests
  that reach it, often most of the suite, are ``reached_by``);
- a flow view's boxes are the calls one function makes, ordered by their
  first call site, at most ``MAX_BOXES`` with the rest in "+N more" views;
  a step opens the callee's flow, or is marked where the flow ends (no
  calls recorded) or leaves kept code; entry targets the graph does not
  link are resolved and tagged so (a Go or Rust file's ``main``, a route
  handler by its name in the registering folder: gaps 4 and 5) or shown
  as cut; a Python CLI that imports argparse is noted (gap 3).

Reads Hobbes's outputs only. Glue outside ``hobbes.extract``.
"""

from __future__ import annotations

import posixpath
import re
from collections import Counter, defaultdict, deque
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = 5  # 2: module views (level 3); 3: flow views (level 4); 4: paths and definition lines for links;
# 5: the architecture views (DEC-020)
MAX_BOXES = 12
SAMPLES = 3
FIXTURE_DIRS = frozenset({"fixtures", "testdata", "__fixtures__"})
TEST_DIRS = frozenset({"tests", "test", "__tests__", "spec", "specs"})
_TEST_FILE = re.compile(r"(^test_.*|.*_test|.*\.test|.*\.spec|conftest)\.[A-Za-z]+$")
MANIFESTS = ("pyproject.toml", "setup.py", "package.json", "go.mod", "Cargo.toml",
             "pom.xml", "build.gradle", "build.gradle.kts", "CMakeLists.txt")
IMPORT_TYPES = frozenset({"imports", "references"})
ROOTS_NOTE = ("Language roots show no edges between them: extraction does not record links "
              "between languages (subprocesses, HTTP, files). A map file to declare them is planned.")
FLOWS = "flow:"  # the entry points' view; a function's flow view is FLOWS + its symbol id
ENTRY_KINDS = {"cli": "CLI entry points", "route": "routes"}
FLOW_NOTE = ("Steps are calls in call-site order. A step that ends has no calls recorded: the flow ends "
             "there, or goes on through dispatch the graph does not record (extraction gap 8).")
ARGPARSE_NOTE = ("This CLI imports argparse: dispatch through set_defaults(func=...) is not extracted, "
                 "so the flow may stop early (extraction gap 3).")
NO_CALLS_NOTE = "No calls recorded from here."
ORDERED = frozenset({"flow", "entries"})  # views whose boxes keep their given order


def is_fixture(path: str) -> bool:
    return any(part in FIXTURE_DIRS for part in path.split("/")[:-1])


def is_test(path: str, test_files: frozenset[str]) -> bool:
    parts = path.split("/")
    return path in test_files or any(p in TEST_DIRS for p in parts[:-1]) or bool(_TEST_FILE.match(parts[-1]))


def _module_paths(graph: dict) -> dict[str, str]:
    return {n["id"]: n["path"] for n in graph["nodes"]
            if n.get("kind") in ("module", "package") and isinstance(n.get("path"), str)}


class _Tree:
    """Folders of the kept modules: ``dirs[folder]`` sub-folders, ``files[folder]`` module ids."""

    def __init__(self, paths: dict[str, str]) -> None:
        self.paths = paths
        self.dirs: dict[str, set[str]] = defaultdict(set)
        self.files: dict[str, list[str]] = defaultdict(list)
        for mid, path in paths.items():
            folder = posixpath.dirname(path)
            self.files[folder].append(mid)
            while folder:
                parent = posixpath.dirname(folder)
                self.dirs[parent].add(folder)
                folder = parent

    def collapse(self, folder: str, keep=lambda folder: False) -> str:
        """Follow folders that hold no files and exactly one folder, stopping
        at one *keep* says to show (a language root)."""
        while not keep(folder) and not self.files.get(folder) and len(self.dirs.get(folder, ())) == 1:
            folder = next(iter(self.dirs[folder]))
        return folder

    def members(self, folder: str) -> list[str]:
        prefix = folder + "/" if folder else ""
        return sorted(m for m, p in self.paths.items() if p.startswith(prefix))


MIN_AFFIX = 4
MIN_GROUP = 2


def _stem(module_path: str) -> str:
    return posixpath.basename(module_path).split(".")[0]


def _qualname(symbol: dict) -> str:
    return symbol.get("qualname") or symbol.get("name") or symbol["id"].rsplit(".", 1)[-1]


def _top(symbol: dict) -> str:
    """A symbol's top-level name: a method's class, a nested function's outer one."""
    return _qualname(symbol).split(".")[0]


def _label(symbol: dict) -> str:
    return _qualname(symbol) + ("()" if symbol.get("kind") in ("function", "method") else "")


def _count_box(box_id: str, label: str, kind: str, count: int, noun: str) -> dict[str, Any]:
    """A box that opens a list (entry points, a kind of them, "+N more")."""
    return {"id": box_id, "label": label, "kind": kind, "members": [], "count": count, "noun": noun,
            "tests": 0, "level": 0, "view": box_id}


_WORD_CUT = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?=_)|(?<=_)")


def _cuts(stem: str, words: bool) -> list[int]:
    """Where *stem* may be cut: anywhere, or (*words*) only at ``_`` and
    camelCase boundaries."""
    if not words:
        return list(range(1, len(stem)))
    return sorted({m.start() for m in _WORD_CUT.finditer(stem)} - {0, len(stem)})


def _is_affix_group(view_id: str) -> bool:
    """Whether *view_id* names a filename or name group: its last part
    (after ``/`` or ``#``) is a prefix (``cli*``) or a suffix (``*source``)."""
    last = view_id.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    return last.startswith("*") or last.endswith("*")


def affix_groups(stems: dict[str, str], room: int, words: bool = False) -> list[tuple[str, list[str]]]:
    """Group ids by the name start or ending most of them share.

    Greedy and deterministic: repeatedly take the affix (``cli*`` or
    ``*source``, at least ``MIN_AFFIX`` chars) shared by the most ungrouped
    names, until the boxes fit in *room* or no affix covers ``MIN_GROUP``
    names. Ties go to the longer affix, then alphabetically. With *words*,
    affixes end at word boundaries (``_collect_*``, ``*_chain``)."""
    left = dict(stems)
    groups: list[tuple[str, list[str]]] = []
    while len(left) + len(groups) > room:
        counts: dict[str, set[str]] = defaultdict(set)
        for fid, stem in left.items():
            for k in _cuts(stem, words):
                if k >= MIN_AFFIX:
                    counts[stem[:k] + "*"].add(fid)
                if len(stem) - k >= MIN_AFFIX:
                    counts["*" + stem[k:]].add(fid)
        best = min(counts.items(), key=lambda kv: (-len(kv[1]), -len(kv[0]), kv[0]), default=None)
        if best is None or len(best[1]) < MIN_GROUP:
            break
        groups.append((best[0], sorted(best[1])))
        for fid in best[1]:
            del left[fid]
    return groups


class _Edges:
    """Module-pair counts with samples, from module and symbol edges."""

    def __init__(self, graph: dict, kept: set[str]) -> None:
        self.pairs: dict[tuple[str, str], Counter] = defaultdict(Counter)
        self.samples: dict[tuple[str, str], list[str]] = defaultdict(list)
        owner = {s["id"]: s["module"] for s in graph.get("symbols", ())}
        for edge in graph.get("module_edges", ()):
            if edge.get("type") in IMPORT_TYPES:
                self._add(edge["from"], edge["to"], "imports", edge, kept)
        for edge in graph.get("symbol_edges", ()):
            a, b = owner.get(edge["from"]), owner.get(edge["to"])
            if a and b and edge.get("type") in ("calls", "uses"):
                self._add(a, b, edge["type"], edge, kept)

    def _add(self, a: str, b: str, kind: str, edge: dict, kept: set[str]) -> None:
        if a == b or a not in kept or b not in kept:
            return
        self.pairs[(a, b)][kind] += 1
        samples = self.samples[(a, b)]
        for ev in edge.get("evidence", ())[:1]:
            if len(samples) < SAMPLES and "path" in ev:
                samples.append(f"{ev['path']}:{ev.get('line', 0)}")


def _sccs(nodes: list[str], out: dict[str, set[str]]) -> list[list[str]]:
    """Tarjan's strongly connected components, iteratively, in sorted order."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on: set[str] = set()
    found: list[list[str]] = []
    for start in nodes:
        if start in index:
            continue
        work = [(start, iter(sorted(out.get(start, ()))))]
        index[start] = low[start] = len(index)
        stack.append(start)
        on.add(start)
        while work:
            node, children = work[-1]
            for child in children:
                if child not in index:
                    index[child] = low[child] = len(index)
                    stack.append(child)
                    on.add(child)
                    work.append((child, iter(sorted(out.get(child, ())))))
                    break
                if child in on:
                    low[node] = min(low[node], index[child])
            else:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[node])
                if low[node] == index[node]:
                    component = []
                    while True:
                        item = stack.pop()
                        on.discard(item)
                        component.append(item)
                        if item == node:
                            break
                    found.append(sorted(component))
    return found


def _levels(nodes: list[str], out: dict[str, set[str]], component_of: dict[str, int]) -> dict[str, int]:
    """Lakos levels on the condensation: 0 for boxes that depend on nothing here."""
    memo: dict[int, int] = {}
    members: dict[int, list[str]] = defaultdict(list)
    for node in nodes:
        members[component_of[node]].append(node)

    def level(comp: int) -> int:
        if comp not in memo:
            memo[comp] = 0  # guards re-entry; the condensation is acyclic
            deps = {component_of[d] for n in members[comp] for d in out.get(n, ())} - {comp}
            memo[comp] = 1 + max((level(d) for d in deps), default=-1)
        return memo[comp]

    return {node: level(component_of[node]) for node in nodes}


class _Builder:
    def __init__(self, graph: dict, repo: Path, tests: dict | None, interfaces: dict | None) -> None:
        self.graph, self.repo = graph, repo
        test_files = frozenset(t.get("file") for t in (tests or {}).get("tests", ()) if t.get("file"))
        paths = _module_paths(graph)
        self.fixtures = {m for m, p in paths.items() if is_fixture(p)}
        self.test_modules = {m for m, p in paths.items() if m not in self.fixtures and is_test(p, test_files)}
        kept = {m: p for m, p in paths.items() if m not in self.fixtures and m not in self.test_modules}
        self.tree = _Tree(kept)
        self.edges = _Edges(graph, set(kept))
        self.tests_on = self._attach_tests(tests, set(kept))
        self._index_symbols(tests)
        self._index_calls()
        self.interfaces = interfaces or {}
        self.entries = self._entries()
        self.views: dict[str, dict[str, Any]] = {}
        self._manifest: dict[str, bool] = {}

    def _attach_tests(self, tests: dict | None, kept: set[str]) -> Counter:
        on: Counter = Counter()
        for test in (tests or {}).get("tests", ()):
            if is_fixture(test.get("file") or ""):
                continue
            reached = Counter(m for m in test.get("reaches_modules", ()) if m in kept)
            if reached:
                top = max(reached.values())
                on[min(m for m, c in reached.items() if c == top)] += 1
        return on

    def is_root(self, folder: str) -> bool:
        if folder not in self._manifest:
            self._manifest[folder] = any((self.repo / folder / m).is_file() for m in MANIFESTS)
        return self._manifest[folder]

    # -- boxes ---------------------------------------------------------

    def _box(self, box_id: str, label: str, kind: str, members: list[str], view: str | None) -> dict[str, Any]:
        box = {"id": box_id, "label": label, "kind": kind, "members": members, "modules": len(members),
               "tests": sum(self.tests_on[m] for m in members)}
        if view is not None:
            box["view"] = view
        if kind == "folder" and self.is_root(box_id):
            box["root"] = True
        return box

    def _boxes(self, folder: str, entries: list[tuple[str, str, list[str]]],
               regroup: bool = True, limit: int = MAX_BOXES) -> tuple[list[dict], list[tuple]]:
        """Fit (kind, id, members) entries into at most *limit* boxes; the
        second result lists the virtual views (prefix groups, overflow) to
        build, each as (id, title, its entries)."""
        virtual: list[tuple] = []
        if regroup and len(entries) > limit:
            files = {e[1]: e for e in entries if e[0] == "module"}
            room = limit - (len(entries) - len(files))
            for affix, ids in affix_groups({m: _stem(self.tree.paths[m]) for m in files}, room):
                gid = f"{folder}/{affix}" if folder else affix
                group = [files.pop(m) for m in ids]
                virtual.append((gid, affix, group))
                entries = [e for e in entries if e[1] not in ids]
                entries.append(("prefix", gid, sorted(ids)))
        if len(entries) > limit:
            entries.sort(key=lambda e: (-len(e[2]), e[1]))
            keep, rest = entries[:limit - 1], entries[limit - 1:]
            members = sorted(m for _, _, ms in rest for m in ms)
            gid = f"{folder}/+more" if folder else "+more"
            entries = keep + [("more", gid, members)]
            virtual.append((gid, f"+{len(rest)} more", rest))
        boxes = []
        for kind, eid, members in sorted(entries, key=lambda e: e[1]):
            if kind == "folder":
                label = posixpath.relpath(eid, folder) if folder else eid
                boxes.append(self._box(eid, label + "/", "folder", members, eid))
            elif kind == "module":
                boxes.append(self._box(eid, posixpath.basename(self.tree.paths[eid]), "module", members, None))
                boxes[-1]["path"] = self.tree.paths[eid]
            else:
                label = eid.rsplit("/", 1)[-1] if kind == "prefix" else f"+{len(members)} modules"
                boxes.append(self._box(eid, label, kind, members, eid))
        boxes.sort(key=lambda b: (b["label"], b["id"]))
        return boxes, virtual

    # -- views ---------------------------------------------------------

    def folder_view(self, folder: str, parent: str | None, level: int, limit: int = MAX_BOXES) -> None:
        entries = [("folder", child, self.tree.members(child))
                   for child in sorted(self.tree.collapse(d, self.is_root) for d in self.tree.dirs.get(folder, ()))]
        entries += [("module", m, [m]) for m in sorted(self.tree.files.get(folder, ()))]
        title = folder or "(repo)"
        boxes, virtual = self._boxes(folder, entries, limit=limit)
        self._finish_folder(folder, title, parent, level, folder, boxes)
        for gid, label, group in virtual:
            self.virtual_view(gid, label, group, folder, folder, level + 1)
        for box in boxes:
            if box["kind"] == "folder":
                self.folder_view(box["id"], folder, level + 1)

    def virtual_view(self, view_id: str, title: str, entries: list[tuple], parent: str, folder: str,
                     level: int) -> None:
        """A filename group's or an overflow's own view. A filename group is
        never regrouped (its files share the affix already)."""
        boxes, virtual = self._boxes(view_id, list(entries), regroup=not _is_affix_group(view_id))
        self._finish_folder(view_id, title, parent, level, folder, boxes)
        for gid, label, group in virtual:
            self.virtual_view(gid, label, group, view_id, folder, level + 1)
        for box in boxes:
            if box["kind"] == "folder" and box["id"] not in self.views:
                self.folder_view(box["id"], view_id, level + 1)

    def _stub(self, folder: str, module: str) -> str:
        """The sibling folder (or file) of *folder* that holds *module*."""
        parts = self.tree.paths[module].split("/")
        mine = folder.split("/") if folder else []
        k = 0
        while k < len(mine) and k < len(parts) - 1 and parts[k] == mine[k]:
            k += 1
        return "/".join(parts[:k + 1])

    def _finish_folder(self, view_id: str, title: str, parent: str | None, level: int, folder: str,
                       boxes: list[dict]) -> None:
        self._finish(view_id, title, parent, level, boxes, self.edges.pairs, self.edges.samples,
                     lambda module: self._stub(folder, module), kind="folder")

    def _finish(self, view_id: str, title: str, parent: str | None, level: int, boxes: list[dict],
                pairs: dict[tuple[str, str], Counter], pair_samples: dict[tuple[str, str], list[str]],
                stub, kind: str, stubs: dict[str, dict[str, Counter]] | None = None) -> None:
        """Roll *pairs* (member to member) up to edges between *boxes*; a pair
        with one end outside the view counts on the stub *stub* names."""
        box_of = {m: b["id"] for b in boxes for m in b["members"]}
        counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
        samples: dict[tuple[str, str], list[str]] = defaultdict(list)
        if stubs is None:
            stubs = defaultdict(lambda: {"out": Counter(), "in": Counter()})
        for (a, b), pair in pairs.items():
            ba, bb = box_of.get(a), box_of.get(b)
            if ba and bb and ba != bb:
                counts[(ba, bb)].update(pair)
                kept = samples[(ba, bb)]
                kept.extend(s for s in pair_samples[(a, b)] if len(kept) < SAMPLES)
            elif ba and not bb:
                stubs[stub(b)]["out"].update(pair)
            elif bb and not ba:
                stubs[stub(a)]["in"].update(pair)
        out: dict[str, set[str]] = defaultdict(set)
        for a, b in counts:
            out[a].add(b)
        ids = [b["id"] for b in boxes]
        components = _sccs(ids, out)
        component_of = {n: i for i, comp in enumerate(components) for n in comp}
        levels = _levels(ids, out, component_of)
        for box in boxes:
            box["level"] = levels[box["id"]]
        edges = [{"from": a, "to": b, **dict(sorted(c.items())), "samples": samples[(a, b)],
                  **({"cycle": True} if component_of[a] == component_of[b] else {})}
                 for (a, b), c in sorted(counts.items())]
        self.views[view_id] = {
            "id": view_id, "kind": kind, "title": title, "parent": parent, "level": level,
            "boxes": boxes, "edges": edges,
            "cycles": [c for c in components if len(c) > 1],
            "stubs": [{"id": s, "out": dict(sorted(v["out"].items())), "in": dict(sorted(v["in"].items()))}
                      for s, v in sorted(stubs.items())],
        }

    # -- level 3: a module's symbols --------------------------------------

    def _index_symbols(self, tests: dict | None) -> None:
        """Kept modules' symbols, symbol pairs by the modules they touch, and
        the tests reaching each symbol."""
        kept = self.tree.paths
        self.symbols_of: dict[str, list[dict]] = defaultdict(list)
        self.owner: dict[str, str] = {}
        self.top_name: dict[str, str] = {}
        for symbol in self.graph.get("symbols", ()):
            if symbol.get("module") in kept:
                self.symbols_of[symbol["module"]].append(symbol)
                self.owner[symbol["id"]] = symbol["module"]
                self.top_name[symbol["id"]] = _top(symbol)
        self.symbol_pairs: dict[str, dict[tuple[str, str], Counter]] = defaultdict(lambda: defaultdict(Counter))
        self.symbol_samples: dict[str, dict[tuple[str, str], list[str]]] = defaultdict(lambda: defaultdict(list))
        for edge in self.graph.get("symbol_edges", ()):
            a, b = edge["from"], edge["to"]
            ma, mb = self.owner.get(a), self.owner.get(b)
            if not ma or not mb or a == b or edge.get("type") not in ("calls", "uses"):
                continue
            for module in {ma, mb}:
                self.symbol_pairs[module][(a, b)][edge["type"]] += 1
                samples = self.symbol_samples[module][(a, b)]
                for ev in edge.get("evidence", ())[:1]:
                    if len(samples) < SAMPLES and "path" in ev:
                        samples.append(f"{ev['path']}:{ev.get('line', 0)}")
        # A test guards a symbol it reaches when its file imports the symbol's
        # module or sits in the module's folder; ``reaches`` alone is
        # transitive, so it counts as ``reached_by`` only.
        module_of = {s["id"]: s.get("module") for s in self.graph.get("symbols", ())}
        all_paths = _module_paths(self.graph)
        self.imports: dict[str, set[str]] = defaultdict(set)
        imports = self.imports
        for edge in self.graph.get("module_edges", ()):
            if edge.get("type") in IMPORT_TYPES:
                imports[edge["from"]].add(edge["to"])
        self.tested_by: dict[str, set[str]] = defaultdict(set)
        self.reached_by: dict[str, set[str]] = defaultdict(set)
        for test in (tests or {}).get("tests", ()):
            if is_fixture(test.get("file") or "") or not test.get("id"):
                continue
            test_module = module_of.get(test.get("symbol"))
            test_folder = posixpath.dirname(test.get("file") or "")
            for symbol in test.get("reaches", ()):
                module = self.owner.get(symbol)
                if module is None:
                    continue
                self.reached_by[symbol].add(test["id"])
                if module in imports.get(test_module, ()) or posixpath.dirname(all_paths[module]) == test_folder:
                    self.tested_by[symbol].add(test["id"])

    def module_views(self) -> None:
        """Give each module box with symbols its module view (level 3)."""
        for view in list(self.views.values()):
            for box in view["boxes"]:
                if box["kind"] == "module" and self.symbols_of.get(box["id"]):
                    box["view"] = self.tree.paths[box["id"]]
                    self.module_view(box["id"], view["id"], view["level"] + 1)

    def module_view(self, module: str, parent: str, level: int) -> None:
        path = self.tree.paths[module]
        tops: dict[str, list[dict]] = defaultdict(list)
        for symbol in self.symbols_of[module]:
            tops[_top(symbol)].append(symbol)
        entries = []
        for top, members in sorted(tops.items()):
            head = next((s for s in members if _qualname(s) == top), None)
            entries.append(("symbol", f"{path}#{top}", top, head, sorted(s["id"] for s in members)))
        stubs: dict[str, dict[str, Counter]] = defaultdict(lambda: {"out": Counter(), "in": Counter()})
        for (a, b), pair in self.edges.pairs.items():
            if pair["imports"] and module in (a, b):
                other, way = (b, "out") if a == module else (a, "in")
                stubs[self.tree.paths[other]][way]["imports"] += pair["imports"]
        self.symbol_view(path, posixpath.basename(path), parent, level, module, entries, stubs)

    def symbol_view(self, view_id: str, title: str, parent: str, level: int, module: str,
                    entries: list[tuple], stubs: dict | None = None) -> None:
        """A module view, or one of its name groups or overflow views."""
        boxes, virtual = self._symbol_boxes(view_id, entries, regroup=not _is_affix_group(view_id))
        path = self.tree.paths[module]
        for box in boxes:
            box["path"] = path

        def stub(symbol: str) -> str:
            owner = self.owner[symbol]
            return f"{path}#{self.top_name[symbol]}" if owner == module else self.tree.paths[owner]

        self._finish(view_id, title, parent, level, boxes, self.symbol_pairs[module],
                     self.symbol_samples[module], stub, kind="module", stubs=stubs)
        for gid, label, group in virtual:
            self.symbol_view(gid, label, view_id, level + 1, module, group)

    def _symbol_boxes(self, view_id: str, entries: list[tuple], regroup: bool) -> tuple[list[dict], list[tuple]]:
        """Fit (kind, id, name, head, members) entries into MAX_BOXES boxes,
        as ``_boxes`` does for files."""
        virtual: list[tuple] = []
        if regroup and len(entries) > MAX_BOXES:
            singles = {e[1]: e for e in entries if e[0] == "symbol"}
            for affix, ids in affix_groups({i: e[2] for i, e in singles.items()}, MAX_BOXES, words=True):
                gid = f"{view_id}#{affix}" if "#" not in view_id else f"{view_id}/{affix}"
                group = [singles.pop(i) for i in ids]
                virtual.append((gid, affix, group))
                entries = [e for e in entries if e[1] not in ids]
                entries.append(("prefix", gid, affix, None, sorted(m for g in group for m in g[4])))
        if len(entries) > MAX_BOXES:
            entries.sort(key=lambda e: (-len(e[4]), e[1]))
            keep, rest = entries[:MAX_BOXES - 1], entries[MAX_BOXES - 1:]
            gid = f"{view_id}#+more" if "#" not in view_id else f"{view_id}/+more"
            members = sorted(m for e in rest for m in e[4])
            entries = keep + [("more", gid, f"+{len(rest)} more", None, members)]
            virtual.append((gid, f"+{len(rest)} more", rest))
        boxes = []
        for kind, eid, name, head, members in entries:
            tests = sorted({t for m in members for t in self.tested_by.get(m, ())})
            reached = {t for m in members for t in self.reached_by.get(m, ())}
            box: dict[str, Any] = {"id": eid, "members": members, "symbols": len(members), "tests": len(tests),
                                   "reached_by": len(reached)}
            if kind == "symbol":
                box["kind"] = (head or {}).get("kind") or "symbol"
                box["label"] = name + ("()" if box["kind"] in ("function", "method") else "")
                if head and head.get("line") and head.get("end_line"):
                    box["lines"] = head["end_line"] - head["line"] + 1
                    box["line"] = head["line"]
                box["test_samples"] = tests[:SAMPLES]
            else:
                box.update(kind=kind, label=name, view=eid)
            boxes.append(box)
        boxes.sort(key=lambda b: (b["label"], b["id"]))
        return boxes, virtual

    # -- level 4: flows from entry points ---------------------------------

    def _index_calls(self) -> None:
        """Each symbol's calls in call-site order, as (callee, first line, sites)."""
        self.symbol = {s["id"]: s for s in self.graph.get("symbols", ())}
        all_paths = _module_paths(self.graph)
        lines: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
        for edge in self.graph.get("symbol_edges", ()):
            a, b = edge["from"], edge["to"]
            if edge.get("type") != "calls" or a == b or a not in self.symbol or b not in self.symbol:
                continue
            path = all_paths.get(self.symbol[a].get("module"))
            sites = {ev.get("line", 0) for ev in edge.get("evidence", ()) if ev.get("path") == path}
            lines[a][b] |= sites or {self.symbol[a].get("line", 0)}
        self.calls: dict[str, list[tuple[str, int, int]]] = {
            a: sorted(((b, min(ls), len(ls)) for b, ls in callees.items()), key=lambda c: (c[1], c[0]))
            for a, callees in lines.items()}

    def _entries(self) -> list[dict[str, Any]]:
        """Entry points outside fixtures, each with the symbol its flow starts
        at (and how it was resolved) or why it is cut."""
        by_name: dict[tuple[str, str], list[str]] = defaultdict(list)
        for sid, module in self.owner.items():
            by_name[(posixpath.dirname(self.tree.paths[module]), self.symbol[sid].get("name"))].append(sid)
        found = []
        for e in self.interfaces.get("cli_entry_points", ()):
            source, target = e.get("source") or "", e.get("target") or ""
            if not is_fixture(source):
                found.append({"entry": "cli", "id": f"cli:{e.get('name')}@{source}", "label": str(e.get("name")),
                              "target": target, "source": source, **self._resolve_cli(target)})
        for r in self.interfaces.get("routes", ()):
            file, handler = r.get("file") or "", r.get("handler") or ""
            if not is_fixture(file):
                name = f"{r.get('method', '')} {r.get('path', '')}".strip()
                found.append({"entry": "route", "id": f"route:{name}@{file}:{r.get('line')}", "label": name,
                              "target": handler, "source": f"{file}:{r.get('line')}",
                              **self._resolve_route(handler, posixpath.dirname(file), by_name)})
        return sorted(found, key=lambda e: (e["entry"], e["label"], e["id"]))

    def _resolve_cli(self, target: str) -> dict[str, Any]:
        """``mod:func`` names a symbol; a Go or Rust target is a file, whose
        ``main`` is taken (gap 5)."""
        if ":" in target:
            module, _, name = target.partition(":")
            wanted = f"{module}.{name}"
            if wanted in self.owner:
                found: dict[str, Any] = {"symbol": wanted}
            else:
                matches = sorted(s for s in self.owner if s.endswith("." + wanted))
                if len(matches) != 1:
                    return {"cut": "target not in the graph"}
                found = {"symbol": matches[0], "resolved": "matched by name"}
            if "ext:argparse" in self.imports.get(self.owner[found["symbol"]], ()):
                found["note"] = ARGPARSE_NOTE
            return found
        mains = sorted(s for s, m in self.owner.items()
                       if self.tree.paths[m] == target and _qualname(self.symbol[s]) == "main")
        if len(mains) == 1:
            return {"symbol": mains[0], "resolved": "main() of the file (gap 5)"}
        return {"cut": f"no single main() in {target} (gap 5)"}

    def _resolve_route(self, handler: str, folder: str, by_name: dict[tuple[str, str], list[str]]) -> dict[str, Any]:
        """A handler id that is no symbol is matched by its name among the
        symbols in the registering file's folder, when one alone has it (gap 4)."""
        if not handler:
            return {"cut": "handler not recorded (gap 4)"}
        if handler in self.owner:
            return {"symbol": handler}
        matches = by_name.get((folder, handler.rsplit(".", 1)[-1]), [])
        if len(matches) == 1:
            return {"symbol": matches[0], "resolved": "matched by name (gap 4)"}
        if matches:
            return {"cut": f"handler name shared by {len(matches)} symbols (gap 4)"}
        return {"cut": "handler not found (gap 4)"}

    def flow_views(self, root_view: str) -> None:
        """An "entry points" box on the repo view, its view, and a flow view
        for each function reachable from an entry by calls (level 4)."""
        if not self.entries:
            return
        root = self.views[root_view]
        root["boxes"].append(_count_box(FLOWS, "entry points", "entries", len(self.entries), "entry point"))
        root["boxes"].sort(key=lambda b: (b["label"], b["id"]))
        boxes = []
        for e in self.entries:
            box = {**e, "kind": "entry", "members": [], "tests": 0, "level": 0}
            if "symbol" in e:
                box["view"] = FLOWS + e["symbol"]
            boxes.append(box)
        level = root["level"] + 1
        kinds = sorted({b["entry"] for b in boxes})
        if len(boxes) > MAX_BOXES and len(kinds) > 1:
            groups = [_count_box(FLOWS + k, ENTRY_KINDS[k], "group", sum(b["entry"] == k for b in boxes), "entry point")
                      for k in kinds]
            self._list_view(FLOWS, "entry points", root_view, level, groups, "entries", [FLOW_NOTE])
            placed = [p for k in kinds for p in self._list_view(
                FLOWS + k, ENTRY_KINDS[k], FLOWS, level + 1, [b for b in boxes if b["entry"] == k], "entries")]
        else:
            placed = self._list_view(FLOWS, "entry points", root_view, level, boxes, "entries", [FLOW_NOTE])
        notes = {b["symbol"]: b["note"] for _, b in placed if "note" in b}
        queue = deque((b["symbol"], view, self.views[view]["level"] + 1) for view, b in placed if "symbol" in b)
        while queue:
            symbol, parent, level = queue.popleft()
            if FLOWS + symbol in self.views:
                continue
            steps = [self._step(symbol, callee, order, line, sites)
                     for order, (callee, line, sites) in enumerate(self.calls.get(symbol, ()), 1)]
            head = self.symbol[symbol]
            title = f"{_label(head)} in {self.tree.paths[self.owner[symbol]]}"
            view_notes = [notes[symbol]] if symbol in notes else []
            if not steps:
                view_notes.append(NO_CALLS_NOTE)
            placed = self._list_view(FLOWS + symbol, title, parent, level, steps, "flow", view_notes,
                                     {"symbol": symbol, "module": self.tree.paths[self.owner[symbol]]})
            queue.extend((b["id"], view, self.views[view]["level"] + 1) for view, b in placed if "view" in b)

    def _step(self, caller: str, callee: str, order: int, line: int, sites: int) -> dict[str, Any]:
        """One call of *caller*: the callee, where it is called, and whether
        the flow goes on from it."""
        symbol = self.symbol[callee]
        box: dict[str, Any] = {"id": callee, "label": _label(symbol), "kind": "step",
                               "symbol_kind": symbol.get("kind") or "symbol", "order": order, "line": line,
                               "sites": sites, "members": [callee], "tests": 0, "level": 0}
        module = self.owner.get(callee)
        if module is None:
            box["outside"] = "test or fixture code"
            return box
        tests = sorted(self.tested_by.get(callee, ()))
        if symbol.get("line"):
            box["def_line"] = symbol["line"]
        box.update(module=self.tree.paths[module], local=module == self.owner.get(caller),
                   tests=len(tests), test_samples=tests[:SAMPLES])
        if self.calls.get(callee):
            box["view"] = FLOWS + callee
        else:
            box["end"] = "no calls recorded"
        return box

    def _list_view(self, view_id: str, title: str, parent: str, level: int, boxes: list[dict], kind: str,
                   notes: Iterable[str] = (), extra: dict | None = None) -> list[tuple[str, dict]]:
        """*boxes*, in order, as a view; past MAX_BOXES the rest go to a
        "+N more" view, and so on. Returns (view id, box) for each box placed."""
        placed: list[tuple[str, dict]] = []
        start, vid = 0, view_id
        while True:
            rest = boxes[start:]
            shown = rest if len(rest) <= MAX_BOXES else rest[:MAX_BOXES - 1]
            more = None
            if len(rest) > MAX_BOXES:
                more = _count_box(f"{view_id}@{start + len(shown) + 1}", f"+{len(rest) - len(shown)} more", "more",
                                  len(rest) - len(shown), "step" if kind == "flow" else "entry point")
            ids = {b["id"] for b in shown}
            edges = [{"from": b["id"], "to": c, "calls": sites, "samples": []}
                     for b in shown for c, _, sites in self.calls.get(b["id"], ()) if c in ids]
            self.views[vid] = {
                "id": vid, "kind": kind, "title": title if not start else f"{title} (from {start + 1})",
                "parent": parent, "level": level, **(extra or {}),
                "boxes": shown + ([more] if more else []), "edges": edges, "cycles": [], "stubs": [],
                "notes": list(notes) if not start else [],
            }
            placed += [(vid, b) for b in shown]
            if more is None:
                return placed
            parent, vid, level, start = vid, more["view"], level + 1, start + len(shown)

    # -- the system view's context ---------------------------------------

    def context(self) -> dict[str, Any]:
        nodes = self.graph["nodes"]
        uses: Counter = Counter()
        readers: Counter = Counter()
        kept = set(self.tree.paths)
        for edge in self.graph.get("module_edges", ()):
            if edge["from"] not in kept:
                continue
            if edge.get("type") == "imports" and str(edge["to"]).startswith("ext:"):
                uses[edge["to"]] += 1
            elif edge.get("type") in ("env-read", "env-set"):
                readers[edge["to"]] += 1
        entries = [{"kind": "cli", "name": e.get("name"), "target": e.get("target"), "source": e.get("source")}
                   for e in self.interfaces.get("cli_entry_points", ()) if not is_fixture(e.get("source") or "")]
        entries += [{"kind": "route", "name": f"{r.get('method', '')} {r.get('path', '')}".strip(),
                     "target": r.get("handler"), "source": f"{r.get('file')}:{r.get('line')}"}
                    for r in self.interfaces.get("routes", ()) if not is_fixture(r.get("file") or "")]
        return {
            "entries": sorted(entries, key=lambda e: (e["kind"], str(e["name"]))),
            "externals": [{"id": x, "modules": n} for x, n in sorted(uses.items(), key=lambda i: (-i[1], i[0]))],
            "env": [{"id": e, "modules": n} for e, n in sorted(readers.items())],
            "infra": sorted(n["id"] for n in nodes if n.get("kind") in ("resource", "data", "tf-module")
                            and not any(part in FIXTURE_DIRS for part in re.split(r"[/:]", n["id"]))),
        }


def build(graph: dict, repo: str | Path, tests: dict | None = None, interfaces: dict | None = None) -> dict:
    """The level-model document for one ingested repo, with its
    architecture views (``hobbes.watterson.architecture``, DEC-020)."""
    from hobbes.watterson import architecture

    builder = _Builder(graph, Path(repo), tests, interfaces)
    top = builder.tree.collapse("")
    builder.folder_view(top, None, 0, MAX_BOXES - 1 if builder.entries else MAX_BOXES)
    builder.module_views()
    builder.flow_views(top)
    roots = [b["id"] for b in builder.views[top]["boxes"] if b.get("root")]
    notes = [ROOTS_NOTE] if len(roots) > 1 else []
    return {
        "schema": SCHEMA, "sha": graph.get("sha"), "dirty": graph.get("dirty"),
        "grouping": "folders", "root_view": top, "notes": notes,
        "omitted": {"fixture_modules": len(builder.fixtures), "test_modules": len(builder.test_modules)},
        "context": builder.context(),
        "views": dict(sorted(builder.views.items())),
        "architecture": architecture.build(builder, top, set(builder.views)),
    }


# -- outputs ---------------------------------------------------------------


def _many(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


def describe(box: dict) -> str:
    """What a box holds, in words: its modules, a symbol's kind and size, an
    entry point's target, or where a flow step is called; then its tests."""
    if "count" in box:
        parts = [_many(box["count"], box["noun"])]
    elif box["kind"] == "entry":
        parts = [box["target"] or "(no target)"]
        if "resolved" in box:
            parts.append(box["resolved"])
        if "cut" in box:
            parts.append(f"cut: {box['cut']}")
        if "note" in box:
            parts.append("dispatch not extracted (gap 3)")
    elif box["kind"] == "step":
        parts = [f"called at line {box['line']}" + (f" ({box['sites']} sites)" if box["sites"] > 1 else "")]
        if not box.get("local", True) and "module" in box:
            parts.append(f"in {box['module']}")
        for key in ("end", "outside"):
            if key in box:
                parts.append(f"ends: {box[key]}" if key == "end" else f"leaves: {box[key]}")
    elif "modules" in box:
        parts = [_many(box["modules"], "module")]
    elif box["kind"] in ("prefix", "more"):
        parts = [_many(box["symbols"], "symbol")]
    else:
        parts = [box["kind"]]
        if box["symbols"] > 1:
            parts.append(_many(box["symbols"] - 1, "member"))
        if box.get("lines"):
            parts.append(_many(box["lines"], "line"))
    if box["tests"]:
        parts.append(_many(box["tests"], "test"))
    return ", ".join(parts)


def _counts(edge: dict) -> str:
    parts = [f"{edge[k]} {k}" for k in ("imports", "calls", "uses") if edge.get(k)]
    return ", ".join(parts)


def to_text(doc: dict, view_id: str | None = None) -> str:
    view_id = doc["root_view"] if view_id is None else view_id
    view = doc["views"][view_id]
    lines = [f"{view['title']}  (level {view['level']}, {len(view['boxes'])} boxes"
             + (f", parent {view['parent'] or '(repo)'})" if view["parent"] is not None else ")")]
    if view_id == doc["root_view"]:
        lines += [f"note: {n}" for n in doc["notes"]]
    lines += [f"note: {n}" for n in view.get("notes", ())]
    if view.get("kind") in ORDERED:
        lines.append("steps (in call order):" if view["kind"] == "flow" else "entry points:")
        for box in view["boxes"]:
            number = f"{box['order']}. " if "order" in box else ""
            opens = f"  -> {box['view']}" if "view" in box else ""
            lines.append(f"  {number}{box['label']}  {describe(box)}{opens}")
    else:
        lines.append("boxes (level: depends on boxes of lower levels):")
    for box in sorted(view["boxes"], key=lambda b: (-b["level"], b["id"])) if view.get("kind") not in ORDERED else ():
        tags = " root" if box.get("root") else ""
        opens = f"  -> {box['view'] or '(repo)'}" if box.get("view") is not None else ""
        size = f"{box['modules']} modules, {box['tests']} tests" if "modules" in box else describe(box)
        lines.append(f"  [{box['level']}] {box['label']}{tags}  {size}{opens}")
    labels = {b["id"]: b["label"] for b in view["boxes"]}
    if view["edges"]:
        lines.append("edges:")
        for edge in view["edges"]:
            mark = "  (cycle)" if edge.get("cycle") else ""
            lines.append(f"  {labels[edge['from']]} -> {labels[edge['to']]}  {_counts(edge)}{mark}")
    for cycle in view["cycles"]:
        lines.append("cycle: " + " <-> ".join(labels[c] for c in cycle))
    if view["stubs"]:
        lines.append("outside this view:")
        for stub in view["stubs"]:
            arrows = [f"out {_counts(stub['out'])}" if stub["out"] else "", f"in {_counts(stub['in'])}" if stub["in"] else ""]
            lines.append(f"  {stub['id']}  " + "; ".join(a for a in arrows if a))
    return "\n".join(lines) + "\n"


def to_mermaid(doc: dict, view_id: str | None = None) -> str:
    """A flowchart of the view's boxes, or a sequence diagram of a flow."""
    view = doc["views"][doc["root_view"] if view_id is None else view_id]
    if view.get("kind") == "flow":
        return _sequence(doc, view)
    token = {b["id"]: f"b{i}" for i, b in enumerate(view["boxes"])}
    lines = ["flowchart LR"]
    for box in view["boxes"]:
        size = box.get("modules", box.get("symbols", box.get("count")))
        label = (box["label"] + (f" ({size})" if size is not None else "")).replace('"', "'")
        shape = f'[["{label}"]]' if box["kind"] in ("prefix", "more") else f'["{label}"]'
        lines.append(f"  {token[box['id']]}{shape}")
    for edge in view["edges"]:
        arrow = "-.->" if edge.get("cycle") else "-->"
        lines.append(f'  {token[edge["from"]]} {arrow}|"{_counts(edge)}"| {token[edge["to"]]}')
    return "\n".join(lines) + "\n"


def _sequence(doc: dict, view: dict) -> str:
    """A flow as a sequence diagram: modules are the participants; each step
    is a message, followed by the first calls of its own flow."""
    names: dict[str, str] = {}
    messages: list[str] = []

    def who(box: dict) -> str:
        return names.setdefault(box.get("module") or "(tests)", f"p{len(names)}")

    def text(label: str) -> str:
        return label.replace(";", ",").replace("#", "")

    me = names.setdefault(view["module"], "p0")
    for step in view["boxes"]:
        if step["kind"] == "more":
            messages.append(f"  Note over {me}: {step['label']} steps")
            continue
        callee = who(step)
        messages.append(f"  {me}->>{callee}: {text(step['label'])}")
        inner = doc["views"][step["view"]]["boxes"] if "view" in step else []
        for sub in [b for b in inner if b["kind"] == "step"][:SAMPLES]:
            messages.append(f"  {callee}->>{who(sub)}: {text(sub['label'])}")
        total = sum(b.get("count", 1) for b in inner)
        if total > SAMPLES:
            messages.append(f"  Note over {callee}: +{total - SAMPLES} more")
    short = Counter(posixpath.basename(path) for path in names)
    lines = ["sequenceDiagram"]
    for path, token in names.items():
        base = posixpath.basename(path)
        lines.append(f"  participant {token} as {text(base if short[base] == 1 else path)}")
    return "\n".join(lines + messages) + "\n"


def view_ids(doc: dict) -> Iterable[str]:
    return doc["views"].keys()
