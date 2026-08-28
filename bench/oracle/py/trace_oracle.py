"""The Python runtime-trace oracle (ADR-089, design §6; D-O5).

Runs a repository's own pytest suite under ``sys.monitoring`` (PEP 669,
CPython 3.12+) and records every call the interpreter actually made from
code inside the cell, at **site grain**: (caller file, line of the call
instruction) → (callee declaration file, line of the identifier). The
interpreter is the authority; it is asymmetric (design §3.1): an observed
edge is a fact, an unobserved edge is not a falsehood. The output is the
lane's ``OracleExport`` shape with ``kind: "trace"``.

    python trace_oracle.py --repo <repo> --module <dir> --out oracle.json \
        [--runs N] [--sys-path <dir>]... [--label <text>] -- <pytest args>

Each run is its own subprocess (``pytest.main`` twice in one interpreter
is not supported by pytest); the parent unions the runs and states N.

Conventions (the harness README, D-O4), as the tracer meets them:

- **Site line** is the start line of the ``CALL`` instruction's position
  (``co_positions``), which is the line the callee expression starts on
  — the callee name's line in every ordinary shape. Columns are kept for
  triage only.
- **Declaration line** is the identifier's line (``def``/``class``
  keyword line), never a decorator's. ``co_firstlineno`` of a decorated
  function *is* the first decorator's line, so the tracer maps it back
  through an ``ast`` index of the file (``firstlineno → def line``).
- **Wrappers.** A callee that is a wrapper around a Python function
  (``functools.wraps``, ``__wrapped__``) is reported as the wrapped
  declaration, ``via: "wrapped"``; ``functools.partial`` unwinds to its
  function; a bound method to its function; a callable *instance* to its
  class's ``__call__``, ``via: "__call__"``.
- **Classes.** A call of a class is an edge to the class declaration
  (Hobbes draws ``Foo(...)`` to the ``class`` symbol); the ``__init__``
  the interpreter then runs from C has no site of its own and is not an
  edge.
- **Module bodies are in the graded set**: a call made at import time is
  a call the interpreter made; its caller is ``<module>``.
- **C callees** (builtins, extension functions, ``str.strip``) have no
  Python declaration; they are counted per site as ``c_callees`` and
  *not* listed as targets. Python callees outside the repo are listed
  ``external: true`` (out of the in-repo recall denominator, D-O3).
- **Callers outside the cell** — pytest itself, site-packages, the
  interpreter's import machinery — are disabled at the first event from
  each of their call sites, which is also what keeps the overhead low.

Coverage line (mandatory for a trace cell): ``files_loaded`` of
``files_in_module`` (module bodies that ran), ``functions_started`` of
``functions_declared`` (Python declarations under the module that ran at
least once), and the C-callee count. Subprocesses the suite spawns are
not traced; the cell says so.
"""

from __future__ import annotations

import argparse
import ast
import functools
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

SKIP_DIRS = {".venv", "venv", "site-packages", "node_modules", "__pycache__", ".hobbes", ".git"}


# ---------------------------------------------------------------- ast index


def _is_overload(decorator: ast.expr) -> bool:
    """``@overload``, ``@typing.overload``, ``@t.overload``."""
    if isinstance(decorator, ast.Call):
        decorator = decorator.func
    if isinstance(decorator, ast.Name):
        return decorator.id == "overload"
    return isinstance(decorator, ast.Attribute) and decorator.attr == "overload"


class DeclIndex:
    """Declarations of one repo, by file: ``firstlineno`` (as the compiler
    reports it, decorator line included) → identifier line, and qualname →
    (line, kind). Built lazily per file the trace touches; the full module
    index is built once at the end for the coverage denominator."""

    def __init__(self, repo: Path):
        self.repo = repo
        self.files: dict[str, dict] = {}

    def file(self, rel: str) -> dict:
        idx = self.files.get(rel)
        if idx is not None:
            return idx
        idx = {"first_to_def": {}, "qual": {}, "lambda_lines": set(), "declared": 0}
        self.files[rel] = idx
        # `@overload` stubs and the implementation are one declaration
        # (D-O4, 2026-08-28): the graph's symbol sits on the first stub's
        # def line, the interpreter runs the implementation. The
        # implementation's first line maps to the anchor. click (O6,
        # 2026-08-27): 47 of 85 suspects were this grain.
        overload_anchor: dict[str, int] = {}
        try:
            tree = ast.parse((self.repo / rel).read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, OSError, UnicodeDecodeError):
            return idx

        def walk(node, prefix):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    first = child.decorator_list[0].lineno if child.decorator_list else child.lineno
                    qual = prefix + child.name
                    kind = "class" if isinstance(child, ast.ClassDef) else "function"
                    if qual in overload_anchor:
                        idx["first_to_def"][first] = overload_anchor[qual]
                    else:
                        idx["first_to_def"][first] = child.lineno
                        if kind == "function" and any(
                            _is_overload(d) for d in child.decorator_list
                        ):
                            overload_anchor[qual] = child.lineno
                    idx["qual"].setdefault(qual, (idx["first_to_def"][first], kind))
                    idx["declared"] += 1
                    walk(child, qual + ("." if kind == "class" else ".<locals>."))
                elif isinstance(child, ast.Lambda):
                    idx["lambda_lines"].add(child.lineno)
                    walk(child, prefix)
                else:
                    walk(child, prefix)

        walk(tree, "")
        return idx


# ---------------------------------------------------------------- one run


def _rel(repo: Path, filename: str) -> str | None:
    """Repo-relative path of a code object's file, or None when it is not
    a real file under the repo (frozen modules, ``<string>``, site-packages
    inside a venv under the repo)."""
    if not filename or filename[0] == "<":
        return None
    try:
        p = Path(filename)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        rel = p.relative_to(repo)
    except ValueError:
        return None
    if any(part in SKIP_DIRS for part in rel.parts):
        return None
    return rel.as_posix()


def run_once(repo: Path, module: str, pytest_args: list[str], raw_out: Path, extra_paths: list[str]) -> int:
    import sys as _sys

    mon = _sys.monitoring
    TOOL = mon.PROFILER_ID
    mon.use_tool_id(TOOL, "hobbes-oracle-trace")

    index = DeclIndex(repo)
    module_prefix = module.rstrip("/") + "/" if module not in ("", ".") else ""
    # (site key) -> {"targets": {target key: target dict}, "c": count, "caller": str, "col": int}
    sites: dict[tuple[str, int], dict] = {}
    started: set[tuple[str, str]] = set()
    loaded: set[str] = set()
    code_rel: dict = {}
    positions: dict = {}
    guard = [False]

    def rel_of(code):
        try:
            return code_rel[code]
        except KeyError:
            r = _rel(repo, code.co_filename)
            if r is not None and not r.endswith(".py"):
                r = None
            if r is not None and module_prefix and not r.startswith(module_prefix):
                r = None
            code_rel[code] = r
            return r

    def site_line(code, offset):
        pos = positions.get(code)
        if pos is None:
            pos = list(code.co_positions())
            positions[code] = pos
        i = offset // 2
        if 0 <= i < len(pos):
            line, _end, col, _ecol = pos[i]
            if line:
                return line, (col or 0) + 1
        return code.co_firstlineno, 0

    def decl_of_code(fcode):
        """(rel, line, name, kind, external) for a Python code object."""
        r = _rel(repo, fcode.co_filename)
        first = fcode.co_firstlineno
        qual = fcode.co_qualname
        if r is None:
            return None, first, qual, "function", True
        idx = index.file(r)
        line = idx["first_to_def"].get(first, first)
        kind = "function"
        if qual.endswith("<lambda>"):
            kind = "lambda"
        elif "<locals>" in qual:
            kind = "closure"
        elif "." in qual:
            kind = "method"
        return r, line, qual, kind, False

    def resolve(callable_obj):
        """Return (target dict or None, via) — None means a C callee."""
        via = None
        obj = callable_obj
        for _ in range(8):
            if isinstance(obj, functools.partial):
                obj = obj.func
                via = via or "partial"
                continue
            if isinstance(obj, (staticmethod, classmethod)):
                obj = obj.__func__
                continue
            f = getattr(obj, "__func__", None)  # bound method
            if f is not None and not isinstance(obj, type):
                obj = f
                continue
            w = getattr(obj, "__wrapped__", None)
            if w is not None and w is not obj and not isinstance(obj, type):
                obj = w
                via = via or "wrapped"
                continue
            break
        if isinstance(obj, type):
            mod = _sys.modules.get(obj.__module__)
            filename = getattr(mod, "__file__", None)
            r = _rel(repo, filename) if filename else None
            if r is None:
                return {"name": obj.__qualname__, "kind": "class", "external": True}, via
            idx = index.file(r)
            hit = idx["qual"].get(obj.__qualname__)
            if hit is None:
                return {"name": obj.__qualname__, "kind": "class", "external": True, "via": "unindexed"}, via
            return {"pos": {"path": r, "line": hit[0]}, "name": obj.__qualname__, "kind": "class"}, via
        fcode = getattr(obj, "__code__", None)
        if fcode is None:
            call = getattr(type(obj), "__call__", None)
            fcode = getattr(call, "__code__", None)
            if fcode is None:
                return None, via  # a C callee
            via = via or "__call__"
        r, line, name, kind, external = decl_of_code(fcode)
        if external:
            return {"name": name, "kind": kind, "external": True}, via
        t = {"pos": {"path": r, "line": line}, "name": name, "kind": kind}
        if kind in ("closure", "lambda"):
            t["closure"] = True
        return t, via

    def on_call(code, offset, callable_obj, arg0):
        if guard[0]:
            return None
        r = rel_of(code)
        if r is None:
            return mon.DISABLE
        guard[0] = True
        try:
            line, col = site_line(code, offset)
            key = (r, line)
            site = sites.get(key)
            if site is None:
                site = {"targets": {}, "c": 0, "caller": code.co_qualname, "col": col, "hits": 0}
                sites[key] = site
            site["hits"] += 1
            target, via = resolve(callable_obj)
            if target is None:
                site["c"] += 1
                return None
            if via:
                target["via"] = via
            tkey = json.dumps(target, sort_keys=True)
            site["targets"].setdefault(tkey, target)
        finally:
            guard[0] = False
        return None

    def on_start(code, offset):
        r = rel_of(code)
        if r is None:
            return mon.DISABLE
        if code.co_name == "<module>":
            loaded.add(r)
        else:
            started.add((r, code.co_qualname))
        return mon.DISABLE  # one event per code object is enough

    mon.register_callback(TOOL, mon.events.CALL, on_call)
    mon.register_callback(TOOL, mon.events.PY_START, on_start)
    mon.set_events(TOOL, mon.events.CALL | mon.events.PY_START)

    for p in extra_paths:
        _sys.path.insert(0, str((repo / p).resolve()))
    import pytest

    rc = pytest.main(pytest_args)

    mon.set_events(TOOL, 0)
    mon.free_tool_id(TOOL)

    out_sites = []
    for (path, line), s in sorted(sites.items()):
        out_sites.append({
            "pos": {"path": path, "line": line}, "col": s["col"], "caller": s["caller"],
            "mode": "observed", "hits": s["hits"], "c_callees": s["c"],
            "targets": list(s["targets"].values()),
        })
    raw_out.write_text(json.dumps({
        "exit": int(rc), "sites": out_sites, "loaded": sorted(loaded),
        "started": sorted(f"{r}::{q}" for r, q in started),
    }))
    return int(rc)


# ---------------------------------------------------------------- the union


def module_files(repo: Path, module: str) -> list[str]:
    base = repo / module if module not in ("", ".") else repo
    out = []
    for p in base.rglob("*.py"):
        rel = p.relative_to(repo)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        out.append(rel.as_posix())
    return sorted(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--module", default=".")
    ap.add_argument("--out", required=True)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--sys-path", action="append", default=[], help="repo-relative dir to prepend to sys.path")
    ap.add_argument("--label", default="", help="how the suite was invoked, for the record")
    ap.add_argument("--one-run", help=argparse.SUPPRESS)
    ap.add_argument("pytest_args", nargs="*")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()
    module = os.path.normpath(args.module)
    if module == ".":
        module = ""

    if args.one_run:
        return run_once(repo, module, args.pytest_args, Path(args.one_run), args.sys_path)

    if sys.version_info < (3, 12):
        print("trace_oracle: sys.monitoring needs CPython 3.12+", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    union: dict[tuple[str, int], dict] = {}
    loaded: set[str] = set()
    started: set[str] = set()
    exits = []
    for i in range(args.runs):
        raw = out.with_suffix(f".run{i + 1}.json")
        cmd = [sys.executable, os.path.abspath(__file__), "--repo", str(repo), "--module", module or ".",
               "--out", str(out), "--one-run", str(raw)]
        for p in args.sys_path:
            cmd += ["--sys-path", p]
        cmd += ["--"] + args.pytest_args
        rc = subprocess.call(cmd)
        exits.append(rc)
        data = json.loads(raw.read_text())
        loaded.update(data["loaded"])
        started.update(data["started"])
        for s in data["sites"]:
            key = (s["pos"]["path"], s["pos"]["line"])
            u = union.get(key)
            if u is None:
                union[key] = s
                continue
            u["hits"] += s["hits"]
            u["c_callees"] += s["c_callees"]
            seen = {json.dumps(t, sort_keys=True) for t in u["targets"]}
            for t in s["targets"]:
                if json.dumps(t, sort_keys=True) not in seen:
                    u["targets"].append(t)

    files = module_files(repo, module)
    index = DeclIndex(repo)
    declared = sum(index.file(f)["declared"] for f in files)
    # Started declarations are counted against the same index: a class
    # body or a lambda starts too, but is not a declared function.
    started = {
        s for s in started
        if index.file(s.split("::", 1)[0])["qual"].get(s.split("::", 1)[1], (0, ""))[1] == "function"
    }
    c_total = sum(s["c_callees"] for s in union.values())
    ext = sum(1 for s in union.values() for t in s["targets"] if t.get("external"))
    export = {
        "oracle": f"py-trace {sys.version.split()[0]} sys.monitoring",
        "kind": "trace",
        "module": module,
        "roots": [args.label or ("pytest " + " ".join(args.pytest_args)).strip()],
        "tags": [],
        "runs": args.runs,
        "suite_exit_codes": exits,
        "files": sorted(loaded),
        "coverage": {
            "files_loaded": len(loaded),
            "files_in_module": len(files),
            "functions_started": len(started),
            "functions_declared": declared,
            "c_callee_calls": c_total,
            "external_python_targets": ext,
            "subprocesses_traced": 0,
        },
        "sites": [union[k] for k in sorted(union)],
    }
    out.write_text(json.dumps(export, indent=1) + "\n")
    print(f"trace: {len(export['sites'])} sites, {sum(len(s['targets']) for s in export['sites'])} targets, "
          f"{len(loaded)}/{len(files)} module files loaded, {len(started)}/{declared} declarations started, "
          f"runs {args.runs}, suite exits {exits}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
