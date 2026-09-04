"""The local harness — Calvin M0 §2.4, step 5 of §8. Component X: exec, policy and testmap for arms T and O.

Two things, both model-free.

**`verify`** — the behaviour verifier for a candidate diff at a SHA
(§4.5 "tests pass?"). A fresh worktree at the SHA, the diff applied,
and the tests the **testmap** names as reaching the edited code — a
test whose ``reaches`` holds a symbol whose span the diff touches
(symbol grain), a test reaching an edited module where the diff
falls outside every span (module grain), and every test in a test
file the diff itself touches (the whole file, so a test the change
adds is run too) — executed **in the sandbox image, offline**, under
:mod:`hobbes.extract.containment`'s planner with the ``verify``
profile: a target's tests execute the target's code, so they run
where lane B runs (ADR-092) and refuse without the image. The same
tests run once more at the SHA *without* the diff, so every outcome
is classed against its baseline — ``P2P``, ``F2P``, ``P2F`` (a
regression), ``F2F``, ``new-pass`` / ``new-fail`` (a test the diff
adds) — the SWE-bench reading, made from the repo's own history.

**The environment binding** (ADR-100, ADR-058's precedent): no image
carries a target's *dependencies*, so the harness links the dependency
trees a **source checkout** of the same repo holds — a ``.venv`` beside
a ``pyproject.toml``, a ``node_modules`` beside a ``package.json``, the
interpreter a venv links to, the Go module cache lane B's fetches
filled — into the worktree and mounts each **read-only at its own
host path**, so the links resolve inside the container. Regenerable
trees only, never authored source (ADR-032's rule). The trees are the
source's, i.e. the dependency set at *its* commit, not the SHA's
lockfile — registered as C-92.

**Arm O** — the orchestrator alone with the derived manifest
(§3.2), on the same harness with exec: ``hobbes plan`` at the SHA from
the task text alone (lexical seeds, C-36 — the same input arm T's
anchor pass gets; a refusal is recorded, not seeded from gold), the
units' manifests rendered into an ADR-077-shaped brief, a session
through ``hobbes-session`` with the proxy's policy-checked ``exec``
(the box policy `calvin.box.policy` plus an agent policy allowing the
guards), the knowledge tools **withheld** (``--mcp-tools exec``: the
manifest is the only Hobbes in O, as the template is the only Hobbes
in T), and the session's patch grounded by the same grounder T uses
(`ground_patch`: the raw-diff route of charter §4.1) so HSR reads off
lane-A call sites in both arms (the cell's D-3/D-4) before `verify`
runs it.

Computes and records; interprets nothing. Every record carries the
containment stamp of what ran where.
"""
from __future__ import annotations

import collections
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from hobbes.derive import ground as G
from hobbes.derive import template as T
from hobbes.extract import containment, staging

HARNESS_VERSION = 1  # 1: the `removed` class; the verdict reads only what the diff did (P2F, new-fail, error, not-run); F2F rows are faults
LOOP_PATH = Path(__file__).resolve().parents[1] / "agent" / "loop.py"
#: The box policy an arm-O session runs under: the benchmark floor
#: (ADR-057) plus the test runners this repo's guards need in the image.
CALVIN_BOX = Path(__file__).resolve().parent / "calvin.box.policy"
#: A dependency tree the harness may link, by the manifest beside it.
#: Regenerable from a lockfile, never authored — the ADR-032 rule.
DEP_DIRS = {"pyproject.toml": ".venv", "package.json": "node_modules"}
_SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__"}
MANIFEST_CAP = 24_000
OUTCOMES = ("pass", "fail", "skip", "error", "not-run", "uncollected", "unsupported")


# --------------------------------------------------------------- environment

@dataclass
class Environment:
    """What binds a worktree to the dependencies its tests need — host trees, read-only, at their own paths."""

    source: str
    #: ``(worktree-relative path, host path)`` — the symlinks the worktree gets.
    links: list[tuple[str, str]] = field(default_factory=list)
    #: Host paths mounted read-only at the same path in the container.
    ro: list[str] = field(default_factory=list)
    #: ``KEY=VALUE`` for every command.
    env: list[str] = field(default_factory=list)
    #: pyproject dir (worktree-relative) → its interpreter (relative to that dir).
    python: dict[str, str] = field(default_factory=dict)
    #: What a session's brief says about the binding — the runners' quirks a read-only tree causes (host-authored, ADR-058's "environment notice").
    notes: list[str] = field(default_factory=list)

    def record(self) -> dict:
        return {"source": self.source, "links": [list(l) for l in self.links], "ro": list(self.ro), "env": list(self.env), "python": dict(self.python), "notes": list(self.notes)}


def environment(source: Path, worktree: Path, *, container_root: str | None = None, gocache: str | None = None) -> Environment:
    """The binding for *worktree* from *source*'s trees: every manifest in the worktree whose source-side dependency tree exists is linked; the venvs' interpreters ride along (hop by hop, as lane B mounts them); the tool caches are the Hobbes cache root's. *container_root* is the worktree's path inside the container when it differs from the host's (a session's ``/work``)."""
    source = Path(source).resolve()
    worktree = Path(worktree)
    root = container_root or str(worktree)
    env = Environment(source=str(source))
    targets: list[Path] = []
    pyroots: list[str] = []
    for dirpath, dirnames, filenames in os.walk(worktree):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        rel = os.path.relpath(dirpath, worktree)
        rel = "" if rel == "." else rel
        for manifest, dep in DEP_DIRS.items():
            if manifest not in filenames:
                continue
            host = source / rel / dep
            if not host.is_dir():
                continue
            env.links.append((os.path.join(rel, dep), str(host)))
            targets.append(host)
            if manifest == "pyproject.toml":
                pyroots.append(rel)
                env.python[rel] = os.path.join(dep, "bin", "python3")
                targets += [Path(p) for p in containment.interpreter_mounts(host / "bin" / "python3")]
    env.ro = list(containment.mount_roots(targets))
    cache = staging.cache_root()
    env.env = [kv for kv in containment._cache_env(cache) if not (gocache and kv.startswith("GOCACHE="))]
    if gocache:
        env.env.append(f"GOCACHE={gocache}")
    env.env += [kv for kv in ("GOFLAGS=-mod=mod", "GOPROXY=off", "PYTHONDONTWRITEBYTECODE=1", "CI=1",
                              # a test that commits needs an identity, and the container has no git config (the 2026-09-04 calibration: seven F2F on `exit status 128`)
                              "GIT_AUTHOR_NAME=hobbes-verify", "GIT_AUTHOR_EMAIL=verify@hobbes.local", "GIT_COMMITTER_NAME=hobbes-verify", "GIT_COMMITTER_EMAIL=verify@hobbes.local")
                if kv not in env.env]
    pp = []
    for rel in pyroots:
        if (worktree / rel / "src").is_dir():
            pp.append(os.path.join(root, rel, "src") if rel else os.path.join(root, "src"))
        pp.append(os.path.join(root, rel) if rel else root)
    if pp:
        env.env.append("PYTHONPATH=" + ":".join(pp))
    if env.links:
        env.notes.append("The dependency trees (" + ", ".join(rel for rel, _ in env.links) + ") are mounted read-only; nothing installs, and a tool that writes into them fails with EROFS.")
        if any(rel.endswith("node_modules") for rel, _ in env.links):
            env.notes.append("vitest writes its cache into node_modules: run it as `npx vitest run --no-cache <files>` or it exits 1 (EROFS) after the tests pass.")
        if any(rel.endswith(".venv") for rel, _ in env.links):
            env.notes.append("There is no `uv` here: run pytest as `python -m pytest` (the venv's python is first on PATH).")
    return env


def link_deps(env: Environment, worktree: Path) -> None:
    """Create the symlinks on the host side (a link is a path, not a copy; the target is only readable inside)."""
    for rel, host in env.links:
        dst = Path(worktree) / rel
        if dst.is_symlink() or dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(host, dst)


def pre_command(env: Environment, container_root: str = "/work") -> str:
    """The same links as one shell command for a session's ``--pre`` (the worktree is a fresh clone the launcher made). The links are excluded from git first, so the session's commit-on-exit never carries the harness's own binding as the session's work (the first scripted run's patch did)."""
    if not env.links:
        return "true"
    exclude = "printf '%s\\n' " + " ".join(rel for rel, _ in env.links) + f" >> {container_root}/.git/info/exclude"
    return " && ".join([exclude] + [f"ln -sfn {host} {container_root}/{rel}" for rel, host in env.links])


# ---------------------------------------------------------------- selection

_DIFF_HEAD = re.compile(r"^diff --git a/(.*?) b/(.*?)$", re.M)
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.M)
_TEST_FILE = re.compile(r"(^|/)(test_[^/]*\.py|[^/]*_test\.(py|go)|[^/]*\.(test|spec)\.(m?js|tsx?))$")


def split_patch(diff: str) -> list[tuple[str, str]]:
    """``(path, per-file diff)`` for every file a unified diff touches — the shape `ground.fills_from_diff` takes."""
    heads = list(_DIFF_HEAD.finditer(diff))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(diff)
        text = diff[m.start():end]
        path = m.group(2) if "+++ /dev/null" not in text else m.group(1)
        out.append((path, text))
    return out


def pre_ranges(diff: str) -> tuple[dict[str, list[tuple[int, int]]], set[str]]:
    """Per file, the pre-image line ranges the diff **changes** — deleted lines, and for an insertion the two lines it lands between — with context lines left out; and the set of files it creates."""
    ranges: dict[str, list[tuple[int, int]]] = {}
    created: set[str] = set()
    for path, text in split_patch(diff):
        if "+++ /dev/null" in text:
            ranges.setdefault(path, [])
            continue
        if "--- /dev/null" in text:
            created.add(path)
            ranges[path] = []
            continue
        marks: set[int] = set()
        old = None
        replacing = False  # a `+` right after a `-` run replaces those lines; it inserts nothing new
        for line in text.splitlines():
            m = _HUNK.match(line)
            if m:
                old = int(m.group(1)) + (1 if m.group(2) == "0" else 0)  # an empty old side names the line *before* the insertion
                replacing = False
                continue
            if old is None or not line:
                continue
            if line.startswith("-"):
                marks.add(old)
                old += 1
                replacing = True
            elif line.startswith("+"):
                if not replacing:
                    marks.update((max(old - 1, 1), old))
            elif line.startswith(" "):
                old += 1
                replacing = False
        rs: list[tuple[int, int]] = []
        for n in sorted(marks):
            if rs and n <= rs[-1][1] + 1:
                rs[-1] = (rs[-1][0], n)
            else:
                rs.append((n, n))
        ranges.setdefault(path, []).extend(rs)
    return ranges, created


def is_test_path(path: str) -> bool:
    return _TEST_FILE.search(path) is not None


@dataclass
class Selection:
    """The tests a diff's edits reach, by the testmap at the SHA."""

    edited_files: list[str]
    created_files: list[str]
    edited_symbols: list[str]
    edited_modules: list[str]
    #: ``{id, file, framework, origin: guard|touched, grain: symbol|module|file}``
    tests: list[dict]
    touched_test_files: list[str]

    def ids(self) -> list[str]:
        return [t["id"] for t in self.tests]

    def record(self) -> dict:
        return {"edited_files": self.edited_files, "created_files": self.created_files, "edited_symbols": self.edited_symbols,
                "edited_modules": self.edited_modules, "touched_test_files": self.touched_test_files,
                "tests": len(self.tests), "by_origin": dict(collections.Counter(t["origin"] for t in self.tests)),
                "by_grain": dict(collections.Counter(t["grain"] for t in self.tests)),
                "by_framework": dict(collections.Counter(t["framework"] for t in self.tests))}


def select_tests(L: T.Ledger, diff: str) -> Selection:
    ranges, created = pre_ranges(diff)
    symbols: set[str] = set()
    modules: set[str] = set()
    for path, rs in ranges.items():
        mod = L.path_mod.get(path)
        if mod is None:
            continue
        for a, b in rs:
            hit = [s["id"] for s in L.by_module.get(mod, []) if s["line"] <= b and a <= s["end_line"]]
            if hit:
                symbols.update(hit)
            else:
                modules.add(mod)
    test_files = {t["file"] for t in L.tests}
    touched = sorted(p for p in ranges if p in test_files or is_test_path(p))
    tests: list[dict] = []
    seen: set[str] = set()
    for t in L.tests:
        grain = None
        if t["file"] in touched:
            grain, origin = "file", "touched"
        elif set(t.get("reaches", [])) & symbols:
            grain, origin = "symbol", "guard"
        elif set(t.get("reaches_modules", [])) & modules:
            grain, origin = "module", "guard"
        if grain and t["id"] not in seen:
            seen.add(t["id"])
            tests.append({"id": t["id"], "file": t["file"], "framework": t["framework"], "origin": origin, "grain": grain})
    return Selection(sorted(ranges), sorted(created), sorted(symbols), sorted(modules), tests, touched)


# ----------------------------------------------------------------- commands

@dataclass
class Command:
    """One contained test run: a framework, a root to run from, the argv, and the ids it answers for."""

    framework: str
    cwd: str
    argv: list[str]
    files: list[str]
    ids: list[str]
    report: str | None = None

    def record(self) -> dict:
        return {"framework": self.framework, "cwd": self.cwd, "argv": list(self.argv), "files": list(self.files), "ids": len(self.ids)}


def nearest(worktree: Path, path: str, names: tuple[str, ...]) -> str:
    """The closest ancestor directory of *path* (worktree-relative, ``""`` for the root) holding one of *names*."""
    cur = Path(path).parent
    while True:
        if any((worktree / cur / n).exists() for n in names):
            return "" if str(cur) == "." else str(cur)
        if str(cur) in (".", ""):
            return ""
        cur = cur.parent


def _rel(path: str, root: str) -> str:
    return os.path.relpath(path, root) if root else path


def commands(sel: Selection, worktree: Path, env: Environment, reports: Path) -> list[Command]:
    """The commands that run the selection, grouped by framework and root. Go packages, node files and vitest files run whole (fast, and a test the diff adds is caught); pytest runs the ids and the touched files."""
    reports = Path(reports)
    groups: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for t in sel.tests:
        if t["framework"] == "pytest":
            root = nearest(worktree, t["file"], ("pyproject.toml", "setup.cfg", "pytest.ini", "tox.ini", "setup.py"))
        elif t["framework"] == "go-test":
            root = nearest(worktree, t["file"], ("go.mod",))
        elif t["framework"] in ("node:test", "vitest"):
            root = nearest(worktree, t["file"], ("package.json",))
        else:
            root = ""
        groups[(t["framework"], root)].append(t)
    # a touched test file with no test the parent testmap knows (a new file) still runs
    for f in sel.touched_test_files:
        if any(t["file"] == f for t in sel.tests):
            continue
        fw = "pytest" if f.endswith(".py") else "go-test" if f.endswith(".go") else "vitest" if re.search(r"\.(test|spec)\.tsx?$", f) else "node:test"
        root = nearest(worktree, f, ("pyproject.toml",) if fw == "pytest" else ("go.mod",) if fw == "go-test" else ("package.json",))
        groups[(fw, root)].append({"id": f + "::*", "file": f, "framework": fw, "origin": "touched", "grain": "file"})
    out: list[Command] = []
    n = 0
    for (fw, root), rows in sorted(groups.items()):
        n += 1
        # a file the diff creates is absent on the baseline tree: a runner asked for it refuses the whole command (pytest's
        # "file or directory not found", rc 4, nothing run — the first calibration read 552 F2P off exactly that), so a
        # command names only files its worktree has; a test in a missing file is simply not-run there
        rows = [r for r in rows if (worktree / r["file"]).exists()]
        if not rows:
            continue
        files = sorted({r["file"] for r in rows})
        ids = [r["id"] for r in rows if not r["id"].endswith("::*")]
        touched = sorted({r["file"] for r in rows if r["origin"] == "touched"})
        if fw == "pytest":
            python = env.python.get(root, "python3")
            targets = [_rel(f, root) for f in touched] + sorted({_rel(r["file"], root) + "::" + r["id"].split("::", 1)[1] for r in rows if r["origin"] != "touched"})
            rep = reports / f"pytest-{n}.xml"
            out.append(Command(fw, root, [python, "-m", "pytest", "-p", "no:cacheprovider", "-q", f"--junit-xml={rep}", *targets], files, ids, str(rep)))
        elif fw == "go-test":
            for pkg in sorted({os.path.dirname(f) for f in files}):
                pkg_rel = _rel(pkg, root) or "."
                out.append(Command(fw, root, ["go", "test", "-json", "-count=1", "./" + pkg_rel.rstrip("/") + "/"], [f for f in files if os.path.dirname(f) == pkg], [i for i in ids if os.path.dirname(i.split("::")[0]) == pkg]))
        elif fw == "node:test":
            for f in files:
                out.append(Command(fw, root, ["node", "--test", "--test-reporter=tap", _rel(f, root)], [f], [i for i in ids if i.split("::")[0] == f]))
        elif fw == "vitest":
            rep = reports / f"vitest-{n}.json"
            # vitest's cache lives in node_modules, which is read-only here: without --no-cache it exits 1 after passing (EROFS)
            out.append(Command(fw, root, ["./node_modules/.bin/vitest", "run", "--no-cache", "--reporter=json", f"--outputFile={rep}", *[_rel(f, root) for f in files]], files, ids, str(rep)))
        else:
            out.append(Command(fw, root, [], files, ids))
    return out


# ------------------------------------------------------------------ parsers

def parse_junit(text: str, worktree: Path, root: str) -> dict[str, str]:
    """pytest's JUnit XML → ``{test id: outcome}``; the id is rebuilt from the classname (module path, then classes) and the name."""
    out: dict[str, str] = {}
    try:
        tree = ET.fromstring(text)
    except ET.ParseError:
        return out
    for case in tree.iter("testcase"):
        parts = (case.get("classname") or "").split(".")
        file, classes = None, parts
        for i in range(len(parts), 0, -1):
            cand = "/".join(parts[:i]) + ".py"
            if (worktree / root / cand).exists():
                file, classes = cand, parts[i:]
                break
        if file is None:
            continue
        name = (case.get("name") or "").split("[", 1)[0]  # a parametrized case folds into its test: the testmap's id has no bracket
        tid = (os.path.join(root, file) if root else file) + "::" + "::".join(classes + [name])
        tags = {c.tag for c in case}
        oc = "error" if "error" in tags else "fail" if "failure" in tags else "skip" if "skipped" in tags else "pass"
        out[tid] = _worse(out.get(tid), oc)
    return out


_RANK = {"error": 3, "fail": 2, "pass": 1, "skip": 0}


def _worse(a: str | None, b: str) -> str:
    """The outcome a folded set of cases reports: any error or failure wins over a pass, a pass over a skip."""
    return b if a is None or _RANK[b] > _RANK[a] else a


def go_test_files(worktree: Path, pkg: str) -> dict[str, str]:
    """``TestName → file`` for every top-level test function in a package's ``_test.go`` files (a test the diff adds has no testmap row)."""
    out: dict[str, str] = {}
    d = worktree / pkg
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*_test.go")):
        for m in re.finditer(r"(?m)^func (Test\w+)\(", f.read_text(errors="replace")):
            out[m.group(1)] = os.path.join(pkg, f.name) if pkg else f.name
    return out


def parse_go_json(text: str, worktree: Path, root: str, pkg: str) -> dict[str, str]:
    """``go test -json`` → ``{test id: outcome}`` for the top-level tests (subtests fold into their parent)."""
    files = go_test_files(worktree, pkg)
    out: dict[str, str] = {}
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        name = row.get("Test")
        if not name or "/" in name or row.get("Action") not in ("pass", "fail", "skip"):
            continue
        file = files.get(name, os.path.join(pkg, "?"))
        out[file + "::" + name] = row["Action"]
    if not out and re.search(r"(?m)^(FAIL|# |.*\[build failed\])", text):
        out["__build__"] = "error"
    return out


_TAP = re.compile(r"^(not )?ok \d+ - (.*?)(?: # (SKIP|TODO).*)?$")


def parse_tap(text: str, file: str) -> dict[str, str]:
    """node's TAP reporter → ``{test id: outcome}`` for the file's top-level tests."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = _TAP.match(line)
        if not m:
            continue
        out[file + "::" + m.group(2).strip()] = "skip" if m.group(3) else ("fail" if m.group(1) else "pass")
    return out


def parse_vitest_json(text: str, worktree: Path) -> dict[str, str]:
    """vitest's JSON reporter → ``{test id: outcome}`` (``file::describe > title``, the testmap's shape)."""
    out: dict[str, str] = {}
    try:
        doc = json.loads(text)
    except ValueError:
        return out
    for tr in doc.get("testResults", []):
        name = tr.get("name", "")
        try:
            file = os.path.relpath(name, worktree)
        except ValueError:
            file = name
        for a in tr.get("assertionResults", []):
            tid = file + "::" + " > ".join([*a.get("ancestorTitles", []), a.get("title", "")])
            st = a.get("status")
            out[tid] = "pass" if st == "passed" else "fail" if st == "failed" else "skip"
    return out


# ---------------------------------------------------------------------- run

def run_commands(worktree: Path, cmds: list[Command], env: Environment, *, timeout: int = 900) -> tuple[dict[str, dict], list[dict], list[dict]]:
    """Run every command contained; returns ``(results by id, command records, containment ledger)``. A refusal (no image) propagates — a test never runs on the host (P10)."""
    containment.reset_ledger()
    results: dict[str, dict] = {}
    records: list[dict] = []
    for c in cmds:
        if not c.argv:
            for i in c.ids:
                results[i] = {"outcome": "unsupported", "framework": c.framework}
            records.append({**c.record(), "rc": None, "wall_s": 0.0, "note": "no runner for this framework"})
            continue
        rep = Path(c.report) if c.report else None
        if rep:
            rep.parent.mkdir(parents=True, exist_ok=True)
            rep.unlink(missing_ok=True)
        cwd = Path(worktree) / c.cwd if c.cwd else Path(worktree)
        t0 = time.monotonic()
        argv = list(c.argv)
        dropped: list[str] = []
        try:
            o = containment.run(containment.plan("verify", argv, cwd=cwd, ro=env.ro, env=env.env), timeout=timeout)
            missing = _pytest_not_found(o.proc) if c.framework == "pytest" else []
            if missing:
                # One id pytest cannot collect (a fixture the testmap took for a test) aborts the whole
                # command (rc 4, nothing run): drop what it names and run once more; the dropped ids are
                # `not-run` with the reason, never a failure of the diff.
                gone = [a for a in argv if any(m.endswith("/" + a) or m == a for m in missing)]
                dropped = [i for i in c.ids if _rel(i.split("::")[0], c.cwd) + "::" + i.split("::", 1)[1] in gone]
                argv = [a for a in argv if a not in gone]
                o = containment.run(containment.plan("verify", argv, cwd=cwd, ro=env.ro, env=env.env), timeout=timeout)
        except containment.ContainmentError as exc:
            for i in c.ids:
                results[i] = {"outcome": "error", "framework": c.framework, "note": str(exc)[:300]}
            records.append({**c.record(), "rc": None, "wall_s": round(time.monotonic() - t0, 1), "error": str(exc)[:300]})
            continue
        wall = round(time.monotonic() - t0, 1)
        proc = o.proc
        if c.framework == "pytest":
            parsed = parse_junit(rep.read_text() if rep and rep.exists() else "", Path(worktree), c.cwd)
        elif c.framework == "go-test":
            parsed = parse_go_json(proc.stdout, Path(worktree), c.cwd, os.path.dirname(c.files[0]) if c.files else c.cwd)
        elif c.framework == "node:test":
            parsed = parse_tap(proc.stdout, c.files[0])
        else:
            parsed = parse_vitest_json(rep.read_text() if rep and rep.exists() else "", Path(worktree))
        build_error = parsed.pop("__build__", None)
        for i in c.ids:
            if i in dropped:
                results[i] = {"outcome": "uncollected", "framework": c.framework, "note": "pytest could not collect this id at the SHA (the testmap lists a name pytest does not — a fixture?)"}
                continue
            results[i] = {"outcome": parsed.get(i, "error" if (build_error or (proc.returncode and not parsed)) else "not-run"), "framework": c.framework}
        for i, oc in parsed.items():
            if i not in results:
                results[i] = {"outcome": oc, "framework": c.framework, "extra": True}
        records.append({**c.record(), "rc": proc.returncode, "wall_s": wall, "contained": o.contained, "dropped": dropped,
                        "stderr_tail": (proc.stderr or "")[-600:] if proc.returncode else "", "parsed": len(parsed)})
    return results, records, list(containment.LEDGER)


_NOT_FOUND = re.compile(r"^ERROR: (?:not found|file or directory not found): (\S+)$", re.M)


def _pytest_not_found(proc: subprocess.CompletedProcess) -> list[str]:
    """The ids pytest refused to collect (its rc 4 "not found" report), as they were passed — relative to the command's cwd."""
    if proc.returncode != 4:
        return []
    return [m.group(1) for m in _NOT_FOUND.finditer((proc.stderr or "") + (proc.stdout or ""))]


def checkout(clone: Path, sha: str, dest: Path) -> Path:
    """A fresh worktree of *clone* at *sha* (a shared clone: no copy of the objects)."""
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(clone), str(dest)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "-q", sha], check=True, capture_output=True, text=True)
    return dest


CLASSES = ("P2P", "F2P", "P2F", "F2F", "new-pass", "new-fail", "removed", "skip", "error", "not-run", "uncollected", "unsupported")
#: The classes that fail a verdict: what the diff itself did. An `F2F` fails on both trees (an environment fault, C-92 — listed
#: under `faults`); a `removed` test is one the diff renamed or deleted (the 2026-09-04 calibration: seven tests three commits renamed).
FAILING = ("P2F", "new-fail", "error", "not-run")


def classify(candidate: str, baseline: str | None) -> str:
    """A test's class from its outcome with the diff and without it."""
    if candidate == "not-run" and baseline not in (None, "not-run"):
        return "removed"  # the test existed without the diff and does not with it: renamed or deleted by the diff
    if candidate in ("error", "unsupported", "not-run", "uncollected"):
        return candidate
    if candidate == "skip":
        return "skip"
    if baseline in (None, "not-run"):
        return "new-pass" if candidate == "pass" else "new-fail"
    if candidate == "pass":
        return "P2P" if baseline == "pass" else "F2P"
    return "P2F" if baseline == "pass" else "F2F"


def verify(clone: Path, sha: str, diff: str, L: T.Ledger, source: Path, *, out: Path | None = None, baseline: bool = True, timeout: int = 900, keep: bool = False) -> dict:
    """The verdict record for *diff* at *sha*: applies?, the selection, every test's outcome with and without the diff and its class, the verdict, the commands and where they ran."""
    t0 = time.monotonic()
    key = hashlib.sha256(diff.encode("utf-8", "surrogateescape")).hexdigest()[:12]
    scratch = staging.cache_root() / "verify" / f"{sha[:12]}-{key}"
    rec: dict = {"harness_version": HARNESS_VERSION, "sha": sha, "diff_hash": key, "applies": False}
    if L.sha != sha:
        raise ValueError(f"the ledger is at {L.sha[:12]}, the verify at {sha[:12]}")
    if not split_patch(diff):
        # arm T leaves an empty diff when the orchestrator changed nothing (three of step 4's five): a verdict of its own, not a failed apply
        rec.update({"applies": True, "verdict": "empty-diff", "tests": [], "summary": {}, "wall_s": round(time.monotonic() - t0, 1)})
        if out:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            Path(out).write_text(json.dumps(rec, indent=1))
        return rec
    wt = checkout(clone, sha, scratch / "work")
    try:
        chk = subprocess.run(["git", "apply", "--check", "-"], cwd=wt, input=diff, capture_output=True, text=True)
        if chk.returncode:
            rec.update({"apply_error": chk.stderr.strip()[-400:], "verdict": "not-applied", "tests": [], "summary": {}, "wall_s": round(time.monotonic() - t0, 1)})
            return rec
        subprocess.run(["git", "apply", "-"], cwd=wt, input=diff, check=True, capture_output=True, text=True)
        rec["applies"] = True
        sel = select_tests(L, diff)
        rec["selection"] = sel.record()
        env = environment(source, wt)
        link_deps(env, wt)
        rec["environment"] = env.record()
        cmds = commands(sel, wt, env, scratch / "reports" / "work")
        res, cmd_recs, ledger = run_commands(wt, cmds, env, timeout=timeout)
        rec["commands"] = cmd_recs
        base_res: dict[str, dict] = {}
        if baseline and cmds:
            bwt = checkout(clone, sha, scratch / "base")
            benv = environment(source, bwt)
            link_deps(benv, bwt)
            bcmds = commands(sel, bwt, benv, scratch / "reports" / "base")
            base_res, base_recs, base_ledger = run_commands(bwt, bcmds, benv, timeout=timeout)
            rec["baseline_commands"] = base_recs
            ledger += base_ledger
        meta = {t["id"]: t for t in sel.tests}
        rows = []
        for tid in sorted(set(res) | set(base_res)):
            cand = res.get(tid, {}).get("outcome", "not-run")
            base = base_res.get(tid, {}).get("outcome") if baseline else None
            m = meta.get(tid, {"file": tid.split("::")[0], "framework": (res.get(tid) or base_res.get(tid) or {}).get("framework"), "origin": "touched", "grain": "file"})
            rows.append({"id": tid, "file": m["file"], "framework": m["framework"], "origin": m["origin"], "grain": m["grain"],
                         "candidate": cand, "baseline": base, **({"note": res[tid]["note"]} if res.get(tid, {}).get("note") else {})})
        rec["tests"] = rows
        rec["baseline"] = baseline
        score(rec)
        rec["containment"] = {"steps": ledger, "all_contained": all(s.get("contained") for s in ledger) if ledger else None}
        rec["wall_s"] = round(time.monotonic() - t0, 1)
        return rec
    finally:
        if out:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            Path(out).write_text(json.dumps(rec, indent=1))
        if not keep:
            shutil.rmtree(scratch, ignore_errors=True)


def score(rec: dict) -> dict:
    """Class every test row of a verify record and read the verdict off the classes — the one place the reading is made, so a record can be rescored into a new file when the classes change (never in place)."""
    rows = rec.get("tests", [])
    baseline = rec.get("baseline", True)
    for r in rows:
        r["class"] = classify(r["candidate"], r["baseline"]) if baseline else r["candidate"]
    rec["harness_version"] = HARNESS_VERSION
    rec["summary"] = dict(collections.Counter(r["class"] for r in rows))
    if rec.get("verdict") in ("not-applied", "empty-diff"):
        return rec
    if not rows:
        rec["verdict"] = "no-tests"
    else:
        rec["verdict"] = "fail" if any(r["class"] in FAILING for r in rows) else "pass"
    rec["regressions"] = [r["id"] for r in rows if r["class"] == "P2F"]
    rec["faults"] = [r["id"] for r in rows if r["class"] == "F2F"]
    return rec


# -------------------------------------------------------------------- arm O

O_HEAD = ("You are working in a checkout of the {repo} repository at commit {sha12}. Implement the task below by changing "
          "files in this working tree. You have the exec tool for shell commands (the session policy decides; a "
          "refused command is reported, never run) and the file tools. Run the guarding tests after you edit. Do "
          "not create branches or commit — the harness records what you leave in the tree. When the task is done, "
          "reply with a short summary of what you changed and what you could not verify.")


def o_plan(root: Path, task: str, max_units: int | None = None) -> tuple[dict | None, str | None]:
    """``hobbes plan`` at the SHA whose derived artifacts *root* holds, from the task text alone; ``(spec, None)`` or ``(None, the refusal)``."""
    from hobbes.derive.changespec import derive_plan, spec_to_dict
    try:
        return spec_to_dict(derive_plan(Path(root), task, seeds=None, max_units=max_units)), None
    except Exception as exc:  # noqa: BLE001 — the planner's refusal is the record (the cell's precedent)
        return None, f"{type(exc).__name__}: {exc}"


def o_brief(task: str, spec: dict | None, refusal: str | None, repo: str, sha: str, cap: int = MANIFEST_CAP, env: Environment | None = None) -> str:
    """The ADR-077-shaped brief: the task, the environment's notes, then every unit's manifest as an aid, not a boundary; the cut stated."""
    from hobbes.run.agents import render_context
    parts = [O_HEAD.format(repo=repo, sha12=sha[:12]), "", "## Task", task.strip(), ""]
    if env and env.notes:
        parts += ["## Environment (the harness's, not the task's)", *[f"- {n}" for n in env.notes], ""]
    parts.append(f"## Derived context (Hobbes, graph @ {sha[:12]}; an aid, not a boundary — edit whatever the task needs)")
    if spec is None:
        parts.append(f"Hobbes resolved nothing specific from the task text ({refusal}); work from the task and the repo.")
        return "\n".join(parts)
    body = []
    for u in spec.get("units", []):
        if u.get("deferred"):
            continue
        body.append(render_context(spec, u["name"]).strip())
    text = "\n\n".join(body)
    if len(text) > cap:
        text = text[:cap] + f"\n\n(derived context cut by {len(text) - cap:,} characters to fit — C-45)"
    parts.append(text or "the plan derived no unit; work from the task and the repo.")
    return "\n".join(parts)


def o_agent_dir(spec: dict | None, L: T.Ledger, dest: Path) -> Path:
    """The derived agent dir for an arm-O session (ADR-054's shape): one policy allowing every unit's guards under the guarantees, one manifest that is the union of the units' interiors."""
    import yaml
    from hobbes.run.agents import GUARANTEE_RULES, build_context_json, build_policy
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    rules = [dict(r) for r in GUARANTEE_RULES]
    ctx = {"unit": "O", "interior": [], "boundary": [], "neighborhood": [], "paths": []}
    if spec is not None:
        test_files = {t["id"]: t["file"] for t in L.tests}
        seen = {r["pattern"] for r in rules}
        for u in spec.get("units", []):
            if u.get("deferred"):
                continue
            for r in build_policy(spec, u["name"], test_files, human_first="spawn")["rules"]:
                if r["pattern"] not in seen:
                    seen.add(r["pattern"])
                    rules.append(r)
            c = build_context_json(spec, u["name"])
            for k in ("interior", "boundary", "neighborhood", "paths"):
                ctx[k] += [x for x in c[k] if x not in ctx[k]]
    (dest / "policy.yaml").write_text(yaml.safe_dump({"version": 1, "scope": "agent", "default": "escalate", "rules": rules}, sort_keys=False))
    (dest / "context.json").write_text(json.dumps(ctx, indent=1))
    return dest


def session_command(session_bin: str, clone: Path, sha: str, brief: Path, agent_dir: Path, env: Environment, *, base_url: str, model: str,
                    session_id: str, sessions_root: Path, max_turns: int = 40, max_tokens: int = 4096, loop_args: list[str] | None = None,
                    runtime: Path = LOOP_PATH, box: Path = CALVIN_BOX, network: str = "pasta", knowledge: bool = False, timeout: str = "5s") -> list[str]:
    """The ``hobbes-session start`` argv for one arm-O session: the owned loop with exec through the proxy, the box and agent policies, the environment binding as read-only host mounts, the knowledge tools withheld unless *knowledge*."""
    cmd = [session_bin, "start", "--repo", str(clone), "--ref", sha, "--role", "implementer", "--session", session_id, "--sessions", str(sessions_root),
           "--runtime", str(runtime), "--runtime-python", "/usr/bin/python3", "--llm-base-url", base_url, "--model", model, "--task-file", str(brief),
           "--box", str(box), "--agent-dir", str(agent_dir), "--network", network, "--escalation-timeout", timeout, "--commit-on-exit",
           "--max-turns", str(max_turns), "--max-tokens", str(max_tokens),
           "--path", "/work/pipeline/.venv/bin:" + containment.CONTAINER_PATH, "--pre", pre_command(env)]
    for kv in env.env:
        cmd += ["--env", kv]
    for p in env.ro:
        cmd += ["--mount", p]
    gomod = str(staging.cache_root() / "go" / "mod")
    if os.path.isdir(gomod) and gomod not in env.ro:
        cmd += ["--mount", gomod]
    if not knowledge:
        cmd.append("--loop-arg=--mcp-tools=exec")
    for a in loop_args or []:
        cmd.append(f"--loop-arg={a}")
    return cmd


def session_patch(clone: Path, sha: str, session_id: str, env: Environment | None = None) -> str:
    """What the session left: the harvested branch against the SHA, ``.hobbes/`` excluded (the bench's candidate-patch rule) and the harness's own links dropped should one have been committed anyway."""
    from hobbes.bench.workspace import candidate_patch
    branch = f"hobbes/{session_id}"
    has = subprocess.run(["git", "-C", str(clone), "rev-parse", "--verify", "-q", branch], capture_output=True)
    if has.returncode:
        return ""
    patch = candidate_patch(Path(clone), sha, branch)
    links = {rel for rel, _ in (env.links if env else [])}
    return "".join(text for path, text in split_patch(patch) if path not in links) if links else patch


def ground_patch(template: dict, patch: str, L: T.Ledger, repo_root: Path) -> dict:
    """A session's patch through the grounder (charter §4.1's raw-diff route): the same HSR instrument arm T gets, over lane-A call sites."""
    t = copy.deepcopy(template)
    doc, counts = G.fills_from_diff(t, split_patch(patch), repo_root)
    g = G.ground(copy.deepcopy(template), doc, L, repo_root)
    g["fills_attribution"] = {k: v for k, v in counts.items() if k != "in_closed_at"}
    return g


def run_o(clone: Path, sha: str, task: str, L: T.Ledger, source: Path, graphs: tuple[Path, Path], *, session_bin: str, base_url: str, model: str,
          session_id: str, sessions_root: Path, out_dir: Path, template: dict | None = None, timeout: float = 3600.0, verify_after: bool = True,
          dry_run: bool = False, **session_kw) -> dict:
    """Arm O for one unit: the derived artifacts placed at the SHA, the plan and brief, the agent dir, the session, its patch grounded and verified. Returns the record (the session's argv and nothing run under *dry_run*)."""
    clone = Path(clone)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(clone), "checkout", "-q", "--force", sha], check=True, capture_output=True, text=True)
    derived = clone / ".hobbes" / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(graphs[0], derived / "graph.json")
    shutil.copyfile(graphs[1], derived / "tests.json")
    spec, refusal = o_plan(clone, task)
    env = environment(source, clone, container_root="/work", gocache=f"/sessions/{session_id}/go-build")
    brief = o_brief(task, spec, refusal, "Hobbes" if (clone / "docs" / "hobbes-architecture.md").exists() else clone.name, sha, env=env)
    brief_path = out_dir / f"{session_id}.brief.md"
    brief_path.write_text(brief)
    agent_dir = o_agent_dir(spec, L, out_dir / f"{session_id}.agent")
    cmd = session_command(session_bin, clone, sha, brief_path, agent_dir, env, base_url=base_url, model=model, session_id=session_id, sessions_root=sessions_root, **session_kw)
    rec: dict = {"arm": "O", "sha": sha, "session": session_id, "model": model, "plan": {"refusal": refusal, "units": [u["name"] for u in (spec or {}).get("units", []) if not u.get("deferred")],
                 "paths": sorted({p for c in (spec or {}).get("contexts", []) for p in [m.get("path") for m in c.get("modules", [])] if p})},
                 "brief_chars": len(brief), "command": cmd, "environment": env.record()}
    if dry_run:
        return rec
    t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        rec["session_rc"] = proc.returncode
        rec["session_stderr_tail"] = proc.stderr[-1500:]
        (out_dir / f"{session_id}.session.log").write_text(proc.stdout + proc.stderr)
    except subprocess.TimeoutExpired:
        rec["session_rc"] = None
        rec["error"] = f"session timed out after {timeout:.0f}s"
    rec["wall_s"] = round(time.monotonic() - t0, 1)
    sdir = Path(sessions_root) / session_id
    rec["transcript"] = str(sdir / "transcript.jsonl") if (sdir / "transcript.jsonl").exists() else None
    rec["flight_log"] = str(sdir / "flight.jsonl") if (sdir / "flight.jsonl").exists() else None
    patch = session_patch(clone, sha, session_id, env)
    rec["patch_files"] = [p for p, _ in split_patch(patch)]
    (out_dir / f"{session_id}.o.diff").write_text(patch)
    if template is not None and patch:
        g = ground_patch(template, patch, L, clone)
        rec["ground"] = {k: g[k] for k in ("references", "null_by_class", "hsr", "output_hash")}
        rec["null"] = g["null"]
        (out_dir / f"{session_id}.ground.json").write_text(json.dumps(g, indent=1))
    if verify_after and patch:
        rec["verify"] = verify(clone, sha, patch, L, source, out=out_dir / f"{session_id}.verify.json")
    (out_dir / f"{session_id}.o.json").write_text(json.dumps(rec, indent=1))
    return rec
