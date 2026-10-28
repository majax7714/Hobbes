"""Architecture views of a repo, from the graph alone (DEC-020).

``build`` turns the level model's inputs (``hobbes.watterson.levels``, DEC-014) into
a small document of **architecture views** for the review page's
Architecture tab, beside the folder-by-folder code map:

- the **system view**: the repo's top-level parts (the code map's repo view
  folders), the entry points above them (commands, routes) and the outside
  systems they reach below them (processes, network, storage, files,
  environment, infrastructure), classed by ``OUTSIDE``, a fixed table of
  external names;
- a **component view** per part, and per component big enough to split:
  folders, splitting the biggest while the view stays within
  ``MAX_COMPONENTS`` boxes (``MAX_SPLIT`` when it would show fewer than
  ``FEW``); a folder's own files are one box; widely used modules with few
  dependencies of their own go in one **shared** box (``_shared``).

- a **pipeline view** per entry point (``_Pipelines``): the components its
  flow reaches, numbered in the order a depth-first walk of its calls, in
  call-site order, first enters them, and the calls between them. A
  function that references DISPATCH_MIN or more functions without calling
  them (a handler table, ``set_defaults(func=...)``) is a **dispatcher**:
  each referenced function gets its own pipeline, reached by reference.
  Fewer references are followed like calls, marked so.

Every box gets roles by fixed rules (``_roles``, explained on the page), a
summary in the code's own words (``Summaries``: a folder's ``__init__.py``
docstring, README or Go package comment, or a lone module's docstring, read
from the working tree since the graph drops them), its tests and what it
touches outside the repo. Edges, cycles and stubs are rolled up as the
code map rolls them (``levels._Builder._finish``); levels skip the light
links that close cycles, which are marked against the layers
(``_against``). Outside systems are linked from the parts that import
them; the page draws those links on focus. Nothing is guessed:
what the graph does not record (files passed between parts, links between
languages) is said in the view's notes.

Reads Hobbes's outputs and the repo's own files only. Glue outside
``hobbes.extract``.
"""

from __future__ import annotations

import ast
import posixpath
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from hobbes.watterson import levels

ROOT = "arch:"  # the system view; a component view is ROOT + its folder
MAX_COMPONENTS = 9
MAX_SPLIT = levels.MAX_BOXES
FEW = 4
SHARED_PERCENTILE = 0.95
SHARED_MAX_OUT = 2
SHARED_MIN_USERS = 3
ADAPTER_SHARE = 1 / 2
MIN_PREFIX = 3
DISPATCH_MIN = 3
DRILL = 2  # pipeline levels below an entry's own
SUMMARY_CHARS = 220
ABOUT_CHARS = 700

# Outside systems, by external name: Python's top-level package, Go's import
# path (a prefix matches below it), a TS/JS specifier. Order is display order.
OUTSIDE: dict[str, tuple[str, frozenset[str]]] = {
    "process": ("Processes", frozenset({
        "subprocess", "multiprocessing", "pty", "pexpect", "sh", "plumbum", "docker", "podman",
        "os/exec", "syscall", "child_process", "node:child_process", "execa", "cross-spawn"})),
    "network": ("Network", frozenset({
        "socket", "http", "urllib", "urllib3", "requests", "httpx", "aiohttp", "websockets", "websocket", "ssl",
        "smtplib", "ftplib", "grpc", "fastapi", "flask", "starlette", "uvicorn", "django", "anthropic", "openai",
        "boto3", "net", "net/http", "net/url", "net/rpc", "google.golang.org/grpc", "github.com/gorilla/websocket",
        "node:http", "node:https", "node:net", "https", "axios", "node-fetch", "undici", "ws", "express"})),
    "storage": ("Storage", frozenset({
        "sqlite3", "dbm", "shelve", "sqlalchemy", "psycopg", "psycopg2", "pymongo", "redis", "duckdb",
        "database/sql", "github.com/mattn/go-sqlite3", "modernc.org/sqlite", "github.com/lib/pq",
        "go.etcd.io/bbolt", "pg", "mysql", "mysql2", "better-sqlite3", "@prisma/client", "mongodb"})),
    "files": ("Files", frozenset({
        "pathlib", "shutil", "tempfile", "glob", "fnmatch", "io", "os", "zipfile", "tarfile",
        "io/fs", "io/ioutil", "path/filepath", "embed", "fs", "node:fs", "fs/promises", "node:fs/promises",
        "fs-extra"})),
}
ENV, INFRA = "env", "infra"
OUTSIDE_LABELS = {**{k: v[0] for k, v in OUTSIDE.items()}, ENV: "Environment", INFRA: "Infrastructure"}
TALKS = frozenset({"process", "network", "storage"})  # what makes a component an adapter
_NODE_BUILTINS = frozenset({"assert", "buffer", "crypto", "events", "os", "path", "stream", "url", "util", "zlib",
                            "readline", "process", "child_process", "fs", "http", "https", "net", "worker_threads"})

PARTS_NOTE = ("No links between these parts are recorded: extraction does not follow calls between "
              "languages, processes, HTTP or files they share (gaps 2 and 6). Arrows here are imports "
              "and calls only.")
OUTSIDE_NOTE = ("Outside systems are classed by the names a part imports (subprocess, http, sqlite3…), "
                "not by what it runs or which files it reads.")
SHARED_NOTE = ("Shared holds modules used from {users}+ components that depend on little themselves "
               "(fan-in in the top 5%, fan-out at most {out}); they are drawn once, not as links from everywhere.")
STALE_NOTE = "Summaries are read from the working tree at {head}, not from the graph's commit {sha}."
PIPELINE_NOTE = ("Steps are the components this entry point's flow reaches, numbered in the order a walk of its "
                 "calls (in call-site order) first enters them; arrows are the calls between them. Calls the graph "
                 "does not record (dynamic dispatch, other languages, subprocesses) are not followed.")
DISPATCH_NOTE = ("{fn} references {n} functions without calling them (a handler table or set_defaults): each is "
                 "taken as a handler, with its own pipeline. Which one runs is decided at run time.")
CUT_NOTE = "This entry point's code is not in the graph: {cut}."


# -- summaries ----------------------------------------------------------------


def _paragraph(text: str) -> str:
    """The first paragraph of *text*, on one line, without markup."""
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln.strip() for ln in block.splitlines()]
        lines = [ln for ln in lines if ln and not re.match(r"^(#|!\[|<|```|---|===|\[!\[)", ln)]
        if lines:
            out = " ".join(lines)
            out = re.sub(r"`{1,2}([^`]+)`{1,2}", r"\1", out)
            out = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", out)
            out = re.sub(r"\*\*([^*]+)\*\*", r"\1", out)
            return re.sub(r"\s+", " ", out).strip()
    return ""


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("; "))
    return cut[:end + 1] if end > limit // 2 else cut.rsplit(" ", 1)[0] + "…"


def _python_doc(text: str) -> str | None:
    try:
        return ast.get_docstring(ast.parse(text))
    except (SyntaxError, ValueError):
        return None


def _leading_comment(text: str, go: bool) -> str | None:
    """A file's leading comment block: Go's package comment (the comment right
    above ``package``), or a TS/JS file's first ``/** */`` or ``//`` block."""
    lines = text.splitlines()
    if go:
        for i, line in enumerate(lines):
            if line.startswith("package "):
                block = []
                j = i - 1
                while j >= 0 and lines[j].startswith("//"):
                    block.insert(0, lines[j][2:].strip())
                    j -= 1
                return "\n".join(block) or None
        return None
    head = text.lstrip()
    if head.startswith("#!"):
        head = head.split("\n", 1)[-1].lstrip()
    if head.startswith("/*"):
        body = head[2:head.find("*/")] if "*/" in head else ""
        return "\n".join(ln.strip().lstrip("*").strip() for ln in body.splitlines()).strip() or None
    block = []
    for line in head.splitlines():
        if not line.startswith("//"):
            break
        block.append(line[2:].strip())
    return "\n".join(block) or None


class Summaries:
    """Summaries read from the repo's files, each with where it came from."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self._cache: dict[str, str | None] = {}

    def _read(self, path: str) -> str | None:
        if path not in self._cache:
            try:
                self._cache[path] = (self.repo / path).read_text(errors="replace")
            except (OSError, ValueError):
                self._cache[path] = None
        return self._cache[path]

    def of_file(self, path: str) -> str | None:
        text = self._read(path)
        if text is None:
            return None
        suffix = posixpath.splitext(path)[1]
        if suffix in (".py", ".pyi"):
            doc = _python_doc(text)
        elif suffix == ".go":
            doc = _leading_comment(text, go=True)
        elif suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"):
            doc = _leading_comment(text, go=False)
        else:
            doc = None
        return _paragraph(doc) if doc else None

    def of_folder(self, folder: str, files: list[str]) -> tuple[str, str] | None:
        """(text, source path) for *folder*, whose own files are *files*."""
        prefix = folder + "/" if folder else ""
        candidates = [prefix + "__init__.py"]
        candidates += [prefix + name for name in ("README.md", "README.rst", "README.txt", "README")]
        candidates += [prefix + "doc.go"] + sorted(f for f in files if f.endswith(".go"))
        for path in candidates:
            if posixpath.basename(path).startswith("README"):
                text = self._read(path)
                found = _paragraph(text) if text else None
            else:
                found = self.of_file(path) if self._read(path) is not None else None
            if found:
                return found, path
        return None


# -- outside systems ----------------------------------------------------------


def outside_class(name: str) -> str | None:
    for key, (_, names) in OUTSIDE.items():
        if name in names or any(name.startswith(n + "/") for n in names if "/" in n or "." in n):
            return key
    return None


def is_library(name: str) -> bool:
    """A third-party package rather than the language's standard library
    (best effort: the graph does not say, gap 6)."""
    if name in sys.stdlib_module_names or name.startswith("node:") or name in _NODE_BUILTINS:
        return False
    if "/" in name and not name.startswith("@"):
        return "." in name.split("/", 1)[0]  # Go: a domain first means not the standard library
    return not name.startswith(".")


# -- the document ---------------------------------------------------------------


class _Arch:
    def __init__(self, builder: levels._Builder, code_views: set[str]) -> None:
        self.b = builder
        self.tree = builder.tree
        self.code_views = code_views
        self.summaries = Summaries(builder.repo)
        self.views: dict[str, dict[str, Any]] = {}
        kept = set(self.tree.paths)
        self.ext: dict[str, set[str]] = defaultdict(set)
        self.env: dict[str, set[str]] = defaultdict(set)
        for edge in builder.graph.get("module_edges", ()):
            a, to = edge["from"], str(edge["to"])
            if a not in kept:
                continue
            if edge.get("type") == "imports" and to.startswith("ext:"):
                self.ext[a].add(to[4:])
            elif edge.get("type") in ("env-read", "env-set"):
                self.env[a].add(to.removeprefix("env:"))
        self.entry_modules: dict[str, list[dict]] = defaultdict(list)
        by_path = {p: m for m, p in self.tree.paths.items()}
        for entry in builder.entries:
            module = builder.owner.get(entry.get("symbol", ""))
            if module is None:
                source = (entry.get("source") or "").rsplit(":", 1)[0]
                module = by_path.get(entry.get("target") or "") or by_path.get(source)
            if module is not None:
                self.entry_modules[module].append(entry)
        self.infra = [n["id"] for n in builder.graph["nodes"] if n.get("kind") in ("resource", "data", "tf-module")
                      and not any(p in levels.FIXTURE_DIRS for p in re.split(r"[/:]", n["id"]))]

    # -- grouping --------------------------------------------------------

    def _children(self, folder: str) -> list[tuple[str, str, list[str]]]:
        """(kind, id, members) entries directly under *folder*: its sub-folders
        (single-folder chains followed) and one box for its own files."""
        entries = [("folder", child, self.tree.members(child)) for child in
                   sorted(self.tree.collapse(d, self.b.is_root) for d in self.tree.dirs.get(folder, ()))]
        own = sorted(self.tree.files.get(folder, ()))
        if len(own) == 1:
            entries.append(("module", own[0], own))
        elif own:
            entries.append(("files", f"{folder}/*" if folder else "*", own))
        return entries

    def _split(self, folder: str) -> list[tuple[str, str, list[str]]]:
        """Folders under *folder*, splitting the biggest while the view stays
        within MAX_COMPONENTS boxes (MAX_SPLIT while it holds fewer than FEW)."""
        entries = self._children(folder)
        tried: set[str] = set()
        while True:
            folders = sorted((e for e in entries if e[0] == "folder" and e[1] not in tried),
                             key=lambda e: (-len(e[2]), e[1]))
            if not folders:
                return self._spread(entries)
            kind, fid, members = folders[0]
            inner = self._children(fid)
            grown = len(entries) - 1 + len(inner)
            limit = MAX_SPLIT if len(entries) < FEW else MAX_COMPONENTS
            if len(inner) < 2 or grown > limit:
                tried.add(fid)
                continue
            entries = [e for e in entries if e[1] != fid] + inner

    def _spread(self, entries: list[tuple]) -> list[tuple]:
        """With fewer than FEW boxes, a big box of a folder's own files is
        broken into its files (``_break_files``)."""
        files = [e for e in entries if e[0] == "files" and len(e[2]) > MAX_COMPONENTS - len(entries)]
        if len(entries) >= FEW or not files:
            return entries
        kind, fid, members = files[0]
        rest = [e for e in entries if e[1] != fid]
        return rest + self._break_files(fid[:-2] if fid.endswith("/*") else "", members,
                                        MAX_COMPONENTS - len(rest))

    def _break_files(self, folder: str, members: list[str], room: int, view_id: str | None = None) -> list[tuple]:
        """A folder's own files as boxes: filename groups (``*source``) of
        MIN_PREFIX or more, then single modules by how many modules they link
        to, then "+N more"."""
        stems = {m: levels._stem(self.tree.paths[m]) for m in members}
        groups = [(a, ids) for a, ids in levels.affix_groups(stems, room) if len(ids) >= MIN_PREFIX]
        grouped = {m for _, ids in groups for m in ids}
        entries: list[tuple] = [("prefix", f"{folder}/{a}" if folder else a, ids) for a, ids in groups]
        degree: Counter = Counter()
        for (a, b) in self.b.edges.pairs:
            degree[a] += 1
            degree[b] += 1
        single = sorted((m for m in members if m not in grouped), key=lambda m: (-degree[m], self.tree.paths[m]))
        entries += [("module", m, [m]) for m in single]
        return self._fold(view_id or ROOT + folder + "/*", entries, room)

    def _fold(self, view_id: str, entries: list[tuple], limit: int) -> list[tuple]:
        """At most *limit* entries: the biggest kept (ties in the given order),
        the rest in one "+N more"."""
        if len(entries) <= limit:
            return entries
        entries = sorted(entries, key=lambda e: -len(e[2]))
        keep, rest = entries[:limit - 1], entries[limit - 1:]
        return keep + [("more", f"{view_id}/+more", sorted(m for e in rest for m in e[2]),
                        [e[1] for e in rest])]

    def _shared(self, entries: list[tuple]) -> tuple[list[tuple], tuple | None]:
        """Pull modules many components use, and which use little, into one box."""
        box_of = {m: e[1] for e in entries for m in e[2]}
        fan_in: Counter = Counter()
        fan_out: Counter = Counter()
        users: dict[str, set[str]] = defaultdict(set)
        for (a, b) in self.b.edges.pairs:
            if a in box_of and b in box_of:
                fan_in[b] += 1
                fan_out[a] += 1
                if box_of[a] != box_of[b]:
                    users[b].add(box_of[a])
        if len(box_of) < 20 or not fan_in:
            return entries, None
        ranked = sorted(fan_in.values())
        cut = ranked[min(len(ranked) - 1, int(len(ranked) * SHARED_PERCENTILE))]
        shared = sorted(m for m in box_of if fan_in[m] >= max(cut, SHARED_MIN_USERS)
                        and fan_out[m] <= SHARED_MAX_OUT and len(users[m]) >= SHARED_MIN_USERS)
        if not shared:
            return entries, None
        gone = set(shared)
        kept = [(e[0], e[1], [m for m in e[2] if m not in gone], *e[3:]) for e in entries]
        return [e for e in kept if e[2]], ("shared", None, shared)

    # -- boxes -----------------------------------------------------------

    def _touches(self, members: list[str]) -> dict[str, list[str]]:
        found: dict[str, set[str]] = defaultdict(set)
        for m in members:
            for name in self.ext.get(m, ()):
                key = outside_class(name)
                if key:
                    found[key].add(name)
            if self.env.get(m):
                found[ENV] |= self.env[m]
        order = list(OUTSIDE) + [ENV]
        return {k: sorted(found[k]) for k in order if found.get(k)}

    def _box(self, kind: str, box_id: str, members: list[str], view_id: str, folded: list[str] | None = None) -> dict:
        b, paths = self.b, self.tree.paths
        box: dict[str, Any] = {"id": box_id, "kind": kind, "members": members, "modules": len(members),
                               "tests": sum(b.tests_on[m] for m in members)}
        parent = view_id[len(ROOT):]
        if kind == "folder":
            box.update(label=posixpath.basename(box_id) + "/", path=box_id)
            if b.is_root(box_id):
                box["root"] = True
            found = self.summaries.of_folder(box_id, [paths[m] for m in self.tree.files.get(box_id, ())])
            if found is None and len(members) == 1:
                text = self.summaries.of_file(paths[members[0]])
                found = (text, paths[members[0]]) if text else None
            if box_id in self.code_views:
                box["code"] = box_id
        elif kind == "module":
            path = paths[members[0]]
            box.update(label=posixpath.basename(path), path=path)
            text = self.summaries.of_file(path)
            found = (text, path) if text else None
            box["code"] = path if path in self.code_views else posixpath.dirname(path)
        elif kind == "files":
            folder = box_id[:-2] if box_id.endswith("/*") else ""
            names = sorted(posixpath.basename(paths[m]) for m in members)
            box.update(label=f"{posixpath.basename(folder) or '(repo)'}/ files", path=folder,
                       files=names)
            found = None
            if folder in self.code_views:
                box["code"] = folder
        elif kind == "prefix":
            box.update(label=box_id.rsplit("/", 1)[-1], files=sorted(posixpath.basename(paths[m]) for m in members))
            found = None
            if box_id in self.code_views:
                box["code"] = box_id
        elif kind == "shared":
            box.update(id=f"{view_id}/shared", label="shared", files=sorted(paths[m] for m in members))
            found = None
        else:  # more
            box.update(label=f"+{len(members)} more", folded=folded or [])
            found = None
        if found:
            text, source = found
            box.update(summary=_clip(text, SUMMARY_CHARS), about=_clip(text, ABOUT_CHARS), source=source)
        touches = self._touches(members)
        if touches:
            box["touches"] = touches
        talking = sum(1 for m in members if any(outside_class(n) in TALKS for n in self.ext.get(m, ())))
        box["adapter"] = bool(members) and kind != "shared" and talking / len(members) >= ADAPTER_SHARE
        libs = sorted({n for m in members for n in self.ext.get(m, ()) if is_library(n)})
        if libs:
            box["libraries"] = libs
        entries = [e for m in members for e in self.entry_modules.get(m, ())]
        if entries:
            box["entries"] = sorted({e["label"] for e in entries})
        return box

    # -- views -----------------------------------------------------------

    def _finish(self, view_id: str, title: str, parent: str | None, level: int, kind: str,
                boxes: list[dict], stub_folder: str) -> dict[str, Any]:
        self.b._finish(view_id, title, parent, level, boxes, self.b.edges.pairs, self.b.edges.samples,
                       lambda module: self.b._stub(stub_folder, module), kind=kind)
        view = self.b.views.pop(view_id)
        _layers(view)
        _roles(view)
        _unique_labels(view)
        self.views[view_id] = view
        return view

    def system_view(self, top: str) -> None:
        view_id = ROOT
        entries = self._fold(view_id, self._children(top), levels.MAX_BOXES)
        boxes = [self._box(e[0], e[1], e[2], ROOT + top, e[3] if len(e) > 3 else None) for e in entries]
        view = self._finish(view_id, "System", None, 0, "system", boxes, top)
        notes = [OUTSIDE_NOTE]
        if sum(1 for b in boxes if b.get("root")) > 1:
            notes.insert(0, PARTS_NOTE)
        view["notes"] = notes
        self._doors(view)
        self._outside(view)
        for box in boxes:
            self._open(box, view_id, 1)

    def component_view(self, folder: str, parent: str, level: int) -> None:
        view_id = ROOT + folder
        entries, shared = self._shared(self._split(folder))
        entries = self._fold(view_id, entries, MAX_SPLIT)
        boxes = [self._box(e[0], e[1], e[2], view_id, e[3] if len(e) > 3 else None) for e in entries]
        if shared:
            boxes.append(self._box("shared", "", shared[2], view_id))
        title = posixpath.basename(folder) or "(repo)"
        view = self._finish(view_id, title, parent, level, "components", boxes, folder)
        view["path"] = folder
        if folder in self.code_views:
            view["code"] = folder
        found = self.summaries.of_folder(folder, [self.tree.paths[m] for m in self.tree.files.get(folder, ())])
        if found:
            view["summary"], view["source"] = _clip(found[0], ABOUT_CHARS), found[1]
        notes = []
        if shared:
            notes.append(SHARED_NOTE.format(users=SHARED_MIN_USERS, out=SHARED_MAX_OUT))
        view["notes"] = notes
        for box in boxes:
            self._open(box, view_id, level + 1)

    def _open(self, box: dict, view_id: str, level: int) -> None:
        """Give a folder box its own component view when it splits into two
        or more, and a box of FEW or more files a view of them."""
        if box["kind"] == "files" and box["modules"] >= FEW and ROOT + box["id"] not in self.views:
            box["view"] = ROOT + box["id"]
            self.files_view(box, box["path"], box["view"], view_id, level)
            return
        if box["kind"] == "more" and box["modules"] >= 2 and box["id"] not in self.views:
            box["view"] = box["id"]
            self.files_view(box, self.views[view_id].get("path", ""), box["view"], view_id, level)
            return
        if box["kind"] != "folder" or ROOT + box["id"] in self.views:
            return
        if box["modules"] > 1 and len(self._split(box["id"])) >= 2:
            box["view"] = ROOT + box["id"]
            self.component_view(box["id"], view_id, level)

    def files_view(self, box: dict, folder: str, view_id: str, parent: str, level: int) -> None:
        """A view of a files or "+N more" box's modules, by ``_break_files``."""
        entries = self._break_files(folder, box["members"], MAX_COMPONENTS, view_id)
        boxes = [self._box(e[0], e[1], e[2], view_id, e[3] if len(e) > 3 else None) for e in entries]
        title = box["label"] if box["kind"] == "files" else f"{posixpath.basename(folder) or '(repo)'}: {box['label']}"
        view = self._finish(view_id, title, parent, level, "components", boxes, folder)
        view["path"] = folder
        if folder in self.code_views:
            view["code"] = folder
        view["notes"] = []
        for inner in boxes:
            self._open(inner, view_id, level + 1)

    def _doors(self, view: dict) -> None:
        """An entry-point box above each part with commands or routes."""
        for box in list(view["boxes"]):
            if not box.get("entries"):
                continue
            entries = [e for m in box["members"] for e in self.entry_modules.get(m, ())]
            cli = sorted({e["label"] for e in entries if e["entry"] == "cli"})
            routes = sorted({e["label"] for e in entries if e["entry"] == "route"})
            parts = []
            if cli:
                parts.append(", ".join(cli) if len(cli) <= 2 else f"{len(cli)} commands")
            if routes:
                parts.append(f"{len(routes)} route" + ("" if len(routes) == 1 else "s"))
            door = {"id": f"door:{box['id']}", "kind": "door", "label": " · ".join(parts), "members": [],
                    "commands": cli, "routes": routes, "level": box["level"] + 1}
            view["boxes"].append(door)
            view["edges"].append({"from": door["id"], "to": box["id"], "starts": len(entries)})

    def _outside(self, view: dict) -> None:
        """A box per outside system the parts touch, below them."""
        reach: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for box in view["boxes"]:
            if box["kind"] == "door":
                continue
            for key, names in box.get("touches", {}).items():
                reach[key][box["id"]] |= set(names)
        if self.infra:
            reach[INFRA]["(repo)"] = set(self.infra)
        for key in [k for k in OUTSIDE_LABELS if k in reach]:
            names = sorted(set().union(*reach[key].values()))
            out = {"id": f"outside:{key}", "kind": "outside", "label": OUTSIDE_LABELS[key], "class": key,
                   "names": names, "members": [], "level": -1}
            view["boxes"].append(out)
            for part, used in sorted(reach[key].items()):
                if part != "(repo)":
                    view["edges"].append({"from": part, "to": out["id"], "touches": len(used),
                                          "names": sorted(used)})


def _unique_labels(view: dict) -> None:
    """Folder labels are names; two boxes with one name show their paths."""
    seen = Counter(b["label"] for b in view["boxes"])
    for box in view["boxes"]:
        if seen[box["label"]] > 1 and box.get("path"):
            box["label"] = box["path"] + ("/" if box["kind"] == "folder" else "")


def _weight(edge: dict) -> int:
    return sum(edge.get(k, 0) for k in ("imports", "calls", "uses"))


def _against(nodes: list[str], edges: list[dict]) -> set[tuple[str, str]]:
    """Links to set against the layers so the rest is acyclic: a weighted
    greedy feedback arc set (Eades, Lin and Smyth), deterministic. Sinks go
    last and sources first; otherwise the node with the most outgoing weight
    over incoming goes first. A link from later to earlier is against."""
    out: dict[str, dict[str, int]] = defaultdict(dict)
    inc: dict[str, dict[str, int]] = defaultdict(dict)
    for e in edges:
        out[e["from"]][e["to"]] = _weight(e)
        inc[e["to"]][e["from"]] = _weight(e)
    left = set(nodes)
    first: list[str] = []
    last: list[str] = []
    while left:
        changed = True
        while changed:
            changed = False
            for n in sorted(left):
                if not any(m in left for m in out[n]):
                    last.insert(0, n)
                    left.discard(n)
                    changed = True
                elif not any(m in left for m in inc[n]):
                    first.append(n)
                    left.discard(n)
                    changed = True
        if left:
            def gain(n: str) -> int:
                return sum(w for m, w in out[n].items() if m in left) - sum(w for m, w in inc[n].items() if m in left)
            pick = min(left, key=lambda n: (-gain(n), n))
            first.append(pick)
            left.discard(pick)
    rank = {n: i for i, n in enumerate(first + last)}
    return {(e["from"], e["to"]) for e in edges if rank[e["from"]] > rank[e["to"]]}


def _layers(view: dict) -> None:
    """Levels on the links that are not against the layers (see ``_against``),
    so a cycle shows as a few marked links, not one flat layer."""
    ids = [b["id"] for b in view["boxes"]]
    inside = [e for e in view["edges"] if e.get("cycle")]
    against = _against(sorted({e["from"] for e in inside} | {e["to"] for e in inside}), inside)
    down: dict[str, set[str]] = defaultdict(set)
    for e in view["edges"]:
        if (e["from"], e["to"]) in against:
            e["against"] = True
        else:
            down[e["from"]].add(e["to"])
    of = {n: i for i, n in enumerate(ids)}
    level = levels._levels(ids, down, of)
    for box in view["boxes"]:
        box["level"] = level[box["id"]]


def _roles(view: dict) -> None:
    """Tag the view's boxes by fixed rules on the view's links: ``entry``
    holds an entry point's code; ``adapter`` has ADAPTER_SHARE or more of its
    modules importing process, network or storage libraries; ``foundation``
    is used by 2 or more boxes and Martin's instability (uses / (uses +
    users)) is at most 1/3; ``coordinator`` uses 2 or more and instability
    is at least 2/3; ``standalone`` has no links in a view that has some."""
    ids = {b["id"] for b in view["boxes"]}
    linked = any(e["from"] in ids and e["to"] in ids for e in view["edges"])
    uses: dict[str, set[str]] = defaultdict(set)
    users: dict[str, set[str]] = defaultdict(set)
    for e in view["edges"]:
        if e["from"] in ids and e["to"] in ids:
            uses[e["from"]].add(e["to"])
            users[e["to"]].add(e["from"])
    for box in view["boxes"]:
        roles = []
        if box.get("entries"):
            roles.append("entry")
        if box.pop("adapter", False):
            roles.append("adapter")
        ce, ca = len(uses[box["id"]]), len(users[box["id"]])
        if box["kind"] == "shared":
            roles.append("shared")
        elif ce + ca == 0:
            if linked:  # with no links at all, the gap is extraction's, not the box's
                roles.append("standalone")
        elif ca >= 2 and ce / (ce + ca) <= 1 / 3:
            roles.append("foundation")
        elif ce >= 2 and ce / (ce + ca) >= 2 / 3:
            roles.append("coordinator")
        box["roles"] = roles
        box["uses"], box["users"] = ce, ca


class _Pipelines:
    """Pipeline views (see the module docstring), built once the component
    views exist: a step is a box of the entry's part's component view."""

    def __init__(self, arch: _Arch) -> None:
        self.arch, self.b = arch, arch.b
        # references to plain functions only: a method or property named on an
        # object is an attribute use, not a handler handed on
        functions = {sid for sid, sym in self.b.symbol.items() if sym.get("kind") == "function"}
        refs: dict[str, dict[str, int]] = defaultdict(dict)
        for edge in self.b.graph.get("symbol_edges", ()):
            a, t = edge["from"], edge["to"]
            if (edge.get("type") != "uses" or a == t or t not in functions or a not in self.b.owner
                    or t not in self.b.owner or any(ev.get("via") for ev in edge.get("evidence", ()))):
                continue
            line = min((ev.get("line", 0) for ev in edge.get("evidence", ())), default=0)
            refs[a][t] = min(line, refs[a].get(t, line))
        self.refs = {a: sorted(ts.items(), key=lambda i: (i[1], i[0])) for a, ts in refs.items()}
        system = arch.views[ROOT]
        self.parts = [b for b in system["boxes"] if b["kind"] in ("folder", "module", "files", "more")]
        self.part_of = {m: part["id"] for part in self.parts for m in part["members"]}
        self.step_of: dict[str, dict[str, dict]] = {}  # part -> module -> box of its component view
        for part in self.parts:
            view = arch.views.get(part.get("view") or "")
            boxes = [b for b in view["boxes"] if b.get("members")] if view else [part]
            self.step_of[part["id"]] = {m: box for box in boxes for m in box["members"]}

    def _label(self, sid: str) -> str:
        return levels._label(self.b.symbol[sid])

    def _site(self, sid: str, line: int) -> str:
        return f"{self.b.tree.paths[self.b.owner[sid]]}:{line}"

    def walk(self, start: str) -> dict[str, Any]:
        """Depth-first from *start*, calls and references in line order."""
        seen: set[str] = set()
        order: list[str] = []
        via: dict[str, tuple[str, str, int]] = {}
        pairs: dict[tuple[str, str], str] = {}
        dispatch: list[tuple[str, list[tuple[str, int]]]] = []
        stack: list[tuple[str, str | None, int]] = [(start, None, 0)]
        while stack:
            sid, caller, line = stack.pop()
            if caller is not None:
                pairs.setdefault((caller, sid), "ref" if sid in dict(self.refs.get(caller, ())) and
                                 sid not in {c for c, _, _ in self.b.calls.get(caller, ())} else "call")
            if sid in seen:
                continue
            seen.add(sid)
            order.append(sid)
            if caller is not None:
                via[sid] = (caller, sid, line)
            nexts = [(c, ln) for c, ln, _ in self.b.calls.get(sid, ())]
            refs = [(t, ln) for t, ln in self.refs.get(sid, ()) if t not in {c for c, _ in nexts}]
            if len(refs) >= DISPATCH_MIN:
                dispatch.append((sid, refs))
            else:
                nexts += refs
            for nxt, ln in sorted(nexts, key=lambda i: (i[1], i[0]), reverse=True):
                stack.append((nxt, sid, ln))
        return {"order": order, "via": via, "pairs": pairs, "dispatch": dispatch}

    def view(self, view_id: str, title: str, parent: str, level: int, entry: dict, start: str) -> None:
        """An entry point's pipeline over its part's components, with its
        dispatchers' handler lists."""
        a = self.arch
        walked = self.walk(start)

        def home(module: str) -> dict | None:
            return self.step_of.get(self.part_of.get(module, ""), {}).get(module)

        view = self._steps(view_id, title, parent, level, entry, start, walked, home, 0)
        part = self.part_of.get(self.b.owner[start])
        if part:
            view["part"] = part
        box_of = view.pop("_box_of")
        for sid, handlers in walked["dispatch"]:
            list_id = f"{ROOT}dispatch:{sid}"
            box = {"id": f"dispatch:{sid}", "kind": "dispatch", "label": f"{self._label(sid)} dispatches to {len(handlers)}",
                   "members": [], "level": 0, "view": list_id, "handlers": [self._label(h) for h, _ in handlers]}
            view["boxes"].append(box)
            owner = box_of.get(sid)
            if owner:
                view["edges"].append({"from": owner, "to": box["id"], "starts": len(handlers)})
            view["notes"].append(DISPATCH_NOTE.format(fn=self._label(sid), n=len(handlers)))
            items = [{"entry": "handler", "id": h, "label": self._label(h), "symbol": h,
                      "target": self.b.tree.paths[self.b.owner[h]], "source": self._site(sid, ln)} for h, ln in handlers]
            if list_id not in a.views:
                self.list_view(list_id, f"{self._label(sid)} handlers", view_id, level + 1, items)

    def _steps(self, view_id: str, title: str, parent: str, level: int, entry: dict, start: str,
               walked: dict, home, depth: int, inside: str | None = None) -> dict:
        """A pipeline view of *walked* over the boxes *home* maps modules to;
        a step with a component view of its own opens the same walk inside
        it (down to DRILL levels)."""
        a = self.arch
        steps: dict[str, dict] = {}
        box_of: dict[str, str] = {}
        for sid in walked["order"]:
            module = self.b.owner.get(sid)
            box = home(module) if module else None
            if box is None:
                continue
            box_of[sid] = box["id"]
            step = steps.get(box["id"])
            if step is None:
                keep = {k: box[k] for k in ("label", "kind", "summary", "about", "source", "touches", "path", "code",
                                            "root", "files", "modules", "tests") if k in box}
                step = steps[box["id"]] = {**keep, "id": box["id"], "order": len(steps) + 1, "functions": [],
                                           "reached": 0, "members": [], "roles": [], "_modules": Counter()}
                if box.get("view") in a.views:
                    step["component"] = box["view"]
                if sid in walked["via"]:
                    caller, _, line = walked["via"][sid]
                    step["via"] = {"from": self._label(caller), "to": self._label(sid), "at": self._site(caller, line)}
            step["reached"] += 1
            step["_modules"][module] += 1
            if len(step["functions"]) < 15:
                step["functions"].append({"label": self._label(sid), "path": self.b.tree.paths[module],
                                          "line": self.b.symbol[sid].get("line", 0)})
        boxes = list(steps.values())
        for box in boxes:
            box["level"] = len(boxes) - box["order"] + 1
        links: dict[tuple[str, str], Counter] = defaultdict(Counter)
        for (x, y), kind in walked["pairs"].items():
            bx, by = box_of.get(x), box_of.get(y)
            if bx and by and bx != by:
                links[(bx, by)]["refs" if kind == "ref" else "calls"] += 1
        rank = {b["id"]: b["order"] for b in boxes}
        edges = [{"from": x, "to": y, "calls": c["calls"] + c["refs"], **({"refs": c["refs"]} if c["refs"] else {}),
                  **({"against": True} if rank[x] > rank[y] else {})} for (x, y), c in sorted(links.items())]
        door = {"id": f"door:{view_id}", "kind": "door", "label": title, "members": [], "level": len(boxes) + 1,
                "commands": [entry["label"]] if entry.get("entry") == "cli" else [],
                "routes": [entry["label"]] if entry.get("entry") == "route" else []}
        first = next((box_of[sid] for sid in walked["order"] if sid in box_of), None)
        if first:
            edges.insert(0, {"from": door["id"], "to": first, "starts": 1})
        notes = [PIPELINE_NOTE]
        if depth == 0 and entry.get("note") and not walked["dispatch"]:
            notes.append(entry["note"])
        if depth == 0 and entry.get("resolved"):
            notes.append(f"Entry resolved: {entry['resolved']}.")
        view = {"id": view_id, "kind": "pipeline", "title": title, "parent": parent, "level": level,
                "boxes": [door] + boxes, "edges": edges, "cycles": [], "stubs": [], "notes": notes,
                "entry": {k: entry[k] for k in ("label", "target", "source", "entry") if k in entry},
                "start": {"label": self._label(start), "path": self.b.tree.paths[self.b.owner[start]],
                          "line": self.b.symbol[start].get("line", 0)}, "_box_of": box_of}
        if inside:
            view["inside"] = inside
        a.views[view_id] = view
        for box in boxes:
            modules = box.pop("_modules")
            if box["kind"] == "more":  # count what this flow reaches, not the folded box's size
                box["label"] = f"{len(modules)} more module" + ("" if len(modules) == 1 else "s")
            inner = a.views.get(box.get("component", ""))
            if depth >= DRILL or inner is None:
                continue
            inner_home = {m: b for b in inner["boxes"] if b.get("members") for m in b["members"]}
            used = {inner_home[m]["id"] for m in modules if m in inner_home}
            for more in [b for b in inner["boxes"] if b["kind"] == "more" and b["id"] in used]:
                # show the modules the flow reaches most in "+N more", as many as fit
                hidden = sorted((m for m in modules if m in more["members"]), key=lambda m: (-modules[m], m))
                room = MAX_SPLIT - len(used)
                shown = hidden if len(hidden) <= room + 1 else hidden[:room]
                if len(shown) == len(hidden):
                    used.discard(more["id"])
                used |= set(shown)
                for m in shown:
                    inner_home[m] = a._box("module", m, [m], inner["id"])
                    inner_home[m].pop("adapter", None)
            if len(used) < 2:
                continue
            sub = f"{view_id}@{box['id']}"
            box["view"] = sub
            self._steps(sub, f"{title} in {box['label']}", view_id, level + 1, entry, start, walked,
                        inner_home.get, depth + 1, inside=box["label"]).pop("_box_of")
        return view

    def list_view(self, view_id: str, title: str, parent: str, level: int, entries: list[dict]) -> None:
        """A numbered list of entry points (or handlers), each opening its pipeline."""
        boxes = []
        for order, e in enumerate(entries, 1):
            box = {"id": e["id"], "kind": "entry", "label": e["label"], "target": e.get("target") or "",
                   "source": e.get("source") or "", "order": order, "members": [], "tests": 0, "level": 0}
            for key in ("resolved", "cut", "note"):
                if key in e:
                    box[key] = e[key]
            boxes.append(box)
        self.arch.views[view_id] = {"id": view_id, "kind": "entries", "title": title, "parent": parent,
                                    "level": level, "boxes": boxes, "edges": [], "cycles": [], "stubs": [],
                                    "notes": []}
        for e, box in zip(entries, boxes, strict=True):
            if "symbol" in e:
                run = ROOT + "run:" + e["symbol"]
                box["view"] = run
                if run not in self.arch.views:
                    self.view(run, e["label"], view_id, level + 1, e, e["symbol"])

    def build(self) -> None:
        """A pipeline list per part with entry points, opened from its door."""
        system = self.arch.views[ROOT]
        doors = {b["id"][len("door:"):]: b for b in system["boxes"] if b["kind"] == "door"}
        by_part: dict[str, list[dict]] = defaultdict(list)
        for module, entries in self.arch.entry_modules.items():
            if module in self.part_of:
                by_part[self.part_of[module]] += entries
        for part, entries in sorted(by_part.items()):
            entries = sorted({e["id"]: e for e in entries}.values(), key=lambda e: (e["entry"], e["label"], e["id"]))
            label = next((p["label"] for p in self.parts if p["id"] == part), part)
            list_id = ROOT + "runs:" + part
            self.list_view(list_id, f"{label} entry points", ROOT, 1, entries)
            if part in doors:
                doors[part]["view"] = list_id


def build(builder: levels._Builder, top: str, code_views: set[str]) -> dict[str, Any]:
    """The architecture document: its root view id, notes and views."""
    arch = _Arch(builder, code_views)
    arch.system_view(top)
    _Pipelines(arch).build()
    notes = []
    head = _head(builder.repo)
    sha = builder.graph.get("sha")
    if head and sha and head != sha:
        notes.append(STALE_NOTE.format(head=head[:7], sha=sha[:7]))
    return {"root": ROOT, "notes": notes, "views": dict(sorted(arch.views.items()))}


def _head(repo: Path) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                             timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None
