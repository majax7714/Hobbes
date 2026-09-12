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

**Go** (`docs/calvin/calvin-m0-go.md` §2.3): a package's tests run with
``-run '^(TestA|TestB)$'`` at symbol grain, the whole package where an
edit falls outside every span of a Go file (package grain) or a test file
is touched; ``go test -list`` first, so an id the testmap names that the
package does not have is ``uncollected``. Before any test, every module
root the diff touches gets its **tree steps** on both trees: the repo's
own ``//go:generate`` directives regenerate what they write (a generated
file is produced from the tree the diff leaves, never taken from a diff —
gitleaks embeds the generated ``config/gitleaks.toml``), and a generation
whose package's import closure (``go list -deps``) holds an edited
directory guards the edit as a test row (a rule's own true/false-positive
validation runs there); then ``go build ./...`` and ``go vet ./...`` as
**build rows** — a diff that does not compile is ``build-fail``, its own
verdict, not a test failure. The module cache rides read-only (C-92).

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

HARNESS_VERSION = 2  # 1: the `removed` class; the verdict reads only what the diff did (P2F, new-fail, error, not-run); F2F rows are faults. 2: Go (calvin-m0-go §2.3) — `-run` at symbol grain, package grain, `go test -list` → uncollected, the tree steps (generate, build, vet), `build-fail`
LOOP_PATH = Path(__file__).resolve().parents[1] / "agent" / "loop.py"
#: Prompt tokens an arm-O session may spend in all before the loop stops it with a reason (step 6: three of four sessions
#: hit the 30-turn cap at 1.3–1.6M tokens; this endpoint fits no window, so the cap is the cost ceiling, stated per run).
O_TOKEN_BUDGET = 1_000_000
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
    #: Paths under the cache root laid read-only over its rw mount — the Go module cache lane B's fetches filled (C-92).
    ro_cache: list[str] = field(default_factory=list)

    def record(self) -> dict:
        return {"source": self.source, "links": [list(l) for l in self.links], "ro": list(self.ro), "ro_cache": list(self.ro_cache), "env": list(self.env),
                "python": dict(self.python), "notes": list(self.notes)}


def environment(source: Path, worktree: Path, *, container_root: str | None = None, gocache: str | None = None) -> Environment:
    """The binding for *worktree* from *source*'s trees: every manifest in the worktree whose source-side dependency tree exists is linked; the venvs' interpreters ride along (hop by hop, as lane B mounts them); the tool caches are the Hobbes cache root's. *container_root* is the worktree's path inside the container when it differs from the host's (a session's ``/work``)."""
    source = Path(source).resolve()
    worktree = Path(worktree)
    root = container_root or str(worktree)
    env = Environment(source=str(source))
    targets: list[Path] = []
    pyroots: list[str] = []
    gomod = False
    for dirpath, dirnames, filenames in os.walk(worktree):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        rel = os.path.relpath(dirpath, worktree)
        rel = "" if rel == "." else rel
        gomod = gomod or "go.mod" in filenames
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
    if gomod and (cache / "go" / "mod").is_dir():
        env.ro_cache.append(str(cache / "go" / "mod"))
    env.env = [kv for kv in containment._cache_env(cache) if not (gocache and kv.startswith("GOCACHE="))]
    if gocache:
        env.env.append(f"GOCACHE={gocache}")
    # -buildvcs=false: the worktree is a shared clone whose objects live in an alternate the container cannot see, so
    # `go build`'s VCS stamp fails with exit status 128 on every tree (calvin-m0-go WP-1: every gold read build-fail)
    env.env += [kv for kv in ("GOFLAGS=-mod=mod -buildvcs=false", "GOPROXY=off", "PYTHONDONTWRITEBYTECODE=1", "CI=1",
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
        if env.python:
            trees = python_trees(env)
            interp = {rel: os.path.join(root, rel, env.python[rel]) for rel in trees}
            if len(trees) == 1:
                env.notes.append(f"There is no `uv` here: run pytest as `python -m pytest` (the venv's python, `{interp[trees[0]]}`, "
                                 "is first on PATH).")
            else:
                where = lambda rel: f"in `{rel}/`" if rel else "at the repo root"
                env.notes.append("There is no `uv` here, and each Python tree has its own venv: run a tree's tests with its own "
                                 "interpreter — " + "; ".join(f"`{interp[rel]} -m pytest` {where(rel)}" for rel in trees)
                                 + f". A bare `python` is {where(trees[0]).replace('in ', '', 1)}'s, the first on PATH.")
    if env.ro_cache:
        env.notes.append("The Go module cache is mounted read-only and there is no network (GOPROXY=off): build with the modules go.sum already names; `go get` fails.")
    return env


def python_trees(env: Environment) -> list[str]:
    """The Python trees *env* binds, outermost first (by depth, then by name). This is the order their venvs take on a
    session's PATH, so a bare ``python`` is the outermost tree's, not whichever path sorts first as a string. Sorted as
    strings, ``bench/atlas0`` came before ``pipeline``, and a dispatched doer's ``python`` was Atlas-0's
    (S-20260912T174351Z-404f)."""
    return sorted(env.python, key=lambda rel: (rel.count("/") + 1 if rel else 0, rel))


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
#: Directories a test loads its own fixtures from, never a build target: Go's `testdata/` (the tool itself
#: excludes it — https://pkg.go.dev/cmd/go#hdr-Testing_flags) and its cross-language cousins. A production
#: hunk never legitimately falls under one of these names (WP-11a-1: gold's own test can need a fixture gold
#: adds beside it, e.g. `testdata/config/extend_rule_allowlist.toml`, that is not itself a `_test.go` file).
_TEST_SUPPORT_DIR = re.compile(r"(^|/)(testdata|__fixtures__|__snapshots__)(/|$)")


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


def is_test_support_path(path: str) -> bool:
    """A test file itself, or a path under a directory a test loads its own fixtures from (`_TEST_SUPPORT_DIR`) —
    never a production hunk (WP-11a-1)."""
    return is_test_path(path) or _TEST_SUPPORT_DIR.search(path) is not None


def gold_test_hunks(gold_diff: str) -> str:
    """The gold diff's own test-file hunks, reassembled as a patch, **with the test-support fixtures they need**
    (`is_test_support_path`) riding along — calvin-m0-go-r2 §2.3's "gold's own test changes": the diff Hobbes
    applies on top of an arm's diff to ask whether the gold's tests, not the harness's guard selection, read the
    arm's change as done. A test-support hunk travels only alongside an actual test-file hunk (WP-11a-1: a
    fixture with no test change beside it is not "gold's own test changes"); a production hunk never qualifies,
    since no production path is ever named `testdata/`, `__fixtures__/` or `__snapshots__/`."""
    hunks = [(path, text) for path, text in split_patch(gold_diff) if is_test_support_path(path)]
    if not any(is_test_path(p) for p, _ in hunks):
        return ""
    return "".join(text for _, text in hunks)


def gold_non_test_hunks(gold_diff: str) -> str:
    """The exact complement of `gold_test_hunks`: whatever hunks it did *not* take, so
    ``gold_non_test_hunks(d) + gold_test_hunks(d)`` reassembles *d* file-for-file. WP-11a-1's control feeds this
    to `gold_tests_verdict` as the "arm" — a perfect arm's diff stands in for exactly this — to ask whether the
    instrument itself reads `pass` before any real arm is judged by it."""
    taken = {path for path, _ in split_patch(gold_test_hunks(gold_diff))}
    return "".join(text for path, text in split_patch(gold_diff) if path not in taken)


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
    edited_modules = {L.path_mod[p] for p in ranges if p in L.path_mod}
    # Go's package grain (calvin-m0-go §2.3): a non-test Go file edited outside every span, created, deleted or unknown to
    # the graph shares its package's namespace with every test file beside it — the package's tests guard it
    go_packages = {os.path.dirname(p) for p, rs in ranges.items() if p.endswith(".go") and not is_test_path(p)
                   and (not rs or L.path_mod.get(p) is None or L.path_mod[p] in modules)}
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
        elif L.imports_of.get(L.path_mod.get(t["file"], ""), set()) & edited_modules:
            grain, origin = "import", "guard"  # step 6: the test's module imports an edited module (a value read by name, no call the testmap maps)
        elif t["framework"] == "go-test" and os.path.dirname(t["file"]) in go_packages:
            grain, origin = "package", "guard"
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
    #: Go: ``go test -list`` with the same pattern, run first — an id it does not return is ``uncollected``.
    list_argv: list[str] | None = None
    #: The grain a result the command returns beyond its ids gets (a whole Go package: ``package``; a whole file: ``file``).
    grain: str = "file"

    def record(self) -> dict:
        return {"framework": self.framework, "cwd": self.cwd, "argv": list(self.argv), "files": list(self.files), "ids": len(self.ids),
                **({"list_argv": list(self.list_argv)} if self.list_argv else {})}


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


def _go_target(pkg: str, root: str) -> str:
    """The ``go`` package argument for *pkg* (worktree-relative) from the module root *root*."""
    rel = os.path.relpath(pkg or ".", root or ".")
    return "." if rel == "." else "./" + rel + "/"


def commands(sel: Selection, worktree: Path, env: Environment, reports: Path) -> list[Command]:
    """The commands that run the selection, grouped by framework and root. A Go package runs its selected tests by name
    (``-run '^(A|B)$'``) and whole where a row is at package or file grain, each after ``go test -list``; node files and
    vitest files run whole (fast, and a test the diff adds is caught); pytest runs the ids and the touched files."""
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
        fw = "pytest" if f.endswith(".py") else "go-test" if f.endswith(".go") else "vitest" if re.search(r"\.(test|spec)\.[cm]?tsx?$", f) else "node:test"
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
            by_pkg: dict[str, list[dict]] = collections.defaultdict(list)
            for r in rows:
                by_pkg[os.path.dirname(r["file"])].append(r)
            for pkg, prow in sorted(by_pkg.items()):
                pids = [r["id"] for r in prow if not r["id"].endswith("::*")]
                names = sorted({i.split("::", 1)[1] for i in pids})
                whole = not names or any(r["grain"] in ("package", "file") for r in prow)
                pattern = "." if whole else "^(" + "|".join(names) + ")$"
                target = _go_target(pkg, root)
                out.append(Command(fw, root, ["go", "test", "-json", "-count=1", *([] if whole else ["-run", pattern]), target],
                                   sorted({r["file"] for r in prow}), pids, list_argv=["go", "test", "-list", pattern, target],
                                   grain="package" if whole else "symbol"))
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
        listed: set[str] | None = None
        try:
            if c.list_argv:
                lo = containment.run(containment.plan("verify", c.list_argv, cwd=cwd, ro=env.ro, env=env.env, ro_cache=env.ro_cache), timeout=timeout)
                if lo.proc.returncode == 0:  # a package that does not compile lists nothing: the test run reports it
                    listed = set(re.findall(r"(?m)^(\w+)$", lo.proc.stdout or ""))
            o = containment.run(containment.plan("verify", argv, cwd=cwd, ro=env.ro, env=env.env, ro_cache=env.ro_cache), timeout=timeout)
            missing = _pytest_not_found(o.proc) if c.framework == "pytest" else []
            if missing:
                # One id pytest cannot collect (a fixture the testmap took for a test) aborts the whole
                # command (rc 4, nothing run): drop what it names and run once more; the dropped ids are
                # `not-run` with the reason, never a failure of the diff.
                gone = [a for a in argv if any(m.endswith("/" + a) or m == a for m in missing)]
                dropped = [i for i in c.ids if _rel(i.split("::")[0], c.cwd) + "::" + i.split("::", 1)[1] in gone]
                argv = [a for a in argv if a not in gone]
                o = containment.run(containment.plan("verify", argv, cwd=cwd, ro=env.ro, env=env.env, ro_cache=env.ro_cache), timeout=timeout)
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
            if listed is not None and i.split("::", 1)[1] not in listed:
                results[i] = {"outcome": "uncollected", "framework": c.framework, "note": "`go test -list` does not return this id on the tree (the testmap names a test the package does not have)"}
                continue
            results[i] = {"outcome": parsed.get(i, "error" if (build_error or (proc.returncode and not parsed)) else "not-run"), "framework": c.framework}
        for i, oc in parsed.items():
            if i not in results:
                results[i] = {"outcome": oc, "framework": c.framework, "extra": True, "grain": c.grain}
        records.append({**c.record(), "rc": proc.returncode, "wall_s": wall, "contained": o.contained, "dropped": dropped,
                        **({"listed": len(listed)} if listed is not None else {}),
                        "stderr_tail": (proc.stderr or "")[-600:] if proc.returncode else "", "parsed": len(parsed)})
    return results, records, list(containment.LEDGER)


_NOT_FOUND = re.compile(r"^ERROR: (?:not found|file or directory not found): (\S+)$", re.M)


def _pytest_not_found(proc: subprocess.CompletedProcess) -> list[str]:
    """The ids pytest refused to collect (its rc 4 "not found" report), as they were passed — relative to the command's cwd."""
    if proc.returncode != 4:
        return []
    return [m.group(1) for m in _NOT_FOUND.finditer((proc.stderr or "") + (proc.stdout or ""))]


# --------------------------------------------------------------- Go tree steps

_GO_GENERATE = re.compile(r"(?m)^//go:generate\s")
#: What `./...` never walks: the go tool skips vendor/, testdata/ and names starting with `.` or `_`; a nested go.mod is another module.
_GO_SKIP = {"vendor", "testdata", "node_modules", ".git"}
#: The generated diff a record keeps, in characters (gitleaks' largest is a few hundred lines).
GENERATED_CAP = 200_000
#: Runs a *failing* generation gets. A generator may validate on random samples — gitleaks' rules draw their true positives
#: from reggen, seeded by the clock — so one failure can be the draw's, not the tree's (calvin-m0-go WP-1: two of forty
#: generations failed on rules no diff touched). A failure on every attempt is the tree's; a pass after a failure is `flaky`.
GENERATE_ATTEMPTS = 3


def go_directives(worktree: Path, root: str) -> dict[str, str]:
    """``{package dir: the first file in it holding a //go:generate directive}`` (worktree-relative) in the module at *root*, walked as ``./...`` walks it."""
    worktree = Path(worktree)
    base = worktree / root if root else worktree
    out: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in _GO_SKIP and not d.startswith((".", "_")) and not (Path(dirpath) / d / "go.mod").exists())
        rel = os.path.relpath(dirpath, worktree)
        rel = "" if rel == "." else rel
        for f in sorted(filenames):
            if not f.endswith(".go") or rel in out:
                continue
            try:
                text = (Path(dirpath) / f).read_text(errors="replace")
            except OSError:
                continue
            if _GO_GENERATE.search(text):
                out[rel] = os.path.join(rel, f) if rel else f
    return out


def _go_step(argv: list[str], cwd: Path, env: Environment, timeout: int) -> dict:
    """One contained Go tree step → ``{argv, outcome: pass|fail|error, rc, wall_s, stdout, stderr_tail}``. A refusal propagates (P10)."""
    t0 = time.monotonic()
    try:
        o = containment.run(containment.plan("verify", argv, cwd=cwd, ro=env.ro, env=env.env, ro_cache=env.ro_cache), timeout=timeout)
    except containment.ContainmentError as exc:
        return {"argv": argv, "outcome": "error", "rc": None, "wall_s": round(time.monotonic() - t0, 1), "stdout": "", "stderr_tail": str(exc)[-600:]}
    p = o.proc
    return {"argv": argv, "outcome": "pass" if p.returncode == 0 else "fail", "rc": p.returncode, "wall_s": round(time.monotonic() - t0, 1),
            "stdout": p.stdout or "", "stderr_tail": (p.stderr or "")[-600:] if p.returncode else "", "contained": o.contained}


def go_roots(worktree: Path, paths: list[str]) -> list[str]:
    """The Go module roots (worktree-relative, ``""`` for the top) holding any of *paths* that can move the Go build: a
    ``.go`` file, a module file, or any file in a directory that holds Go files (an embedded file, a template a generator
    reads). A Python file under a Go module's root moves nothing the go tool reads."""
    roots = set()
    for p in paths:
        d = Path(worktree) / os.path.dirname(p)
        if not (p.endswith(".go") or os.path.basename(p) in ("go.mod", "go.sum", "go.work") or (d.is_dir() and any(d.glob("*.go")))):
            continue
        r = nearest(Path(worktree), p, ("go.mod",))
        if (Path(worktree) / r / "go.mod").exists():
            roots.add(r)
    return sorted(roots)


def go_tree(worktree: Path, sel: Selection, env: Environment, *, timeout: int = 900) -> dict:
    """The Go tree steps (calvin-m0-go §2.3) on one tree, before any test: for every module root the diff touches, each
    ``//go:generate`` directive package is regenerated (``go generate``; what it writes read back as a ``git diff`` against
    the tree as it stood) and its import closure listed (``go list -deps``), then ``go build ./...`` and ``go vet ./...``.
    Returns the steps by row id, the generation records and the containment ledger of these steps."""
    worktree = Path(worktree)
    start = len(containment.LEDGER)
    steps: dict[str, dict] = {}
    generated: list[dict] = []
    roots = go_roots(worktree, sel.edited_files)
    for root in roots:
        cwd = worktree / root if root else worktree
        for pkg, f in sorted(go_directives(worktree, root).items()):
            target = _go_target(pkg, root)
            subprocess.run(["git", "add", "-A"], cwd=worktree, capture_output=True)  # the tree as it stands: what generation writes is the diff after it
            attempts: list[str] = []
            failures: list[str] = []
            for _ in range(GENERATE_ATTEMPTS):
                s = _go_step(["go", "generate", target], cwd, env, timeout)
                attempts.append(s["outcome"])
                if s["outcome"] != "fail":
                    break  # a pass is the tree's answer; a container error is not retried
                failures.append(s["stderr_tail"][-300:])
            changed = subprocess.run(["git", "diff", "--name-only"], cwd=worktree, capture_output=True, text=True).stdout.split()
            text = subprocess.run(["git", "diff", "--no-color"], cwd=worktree, capture_output=True, text=True, errors="surrogateescape").stdout
            lo = _go_step(["go", "list", "-deps", "-f", "{{.Dir}}", target], cwd, env, timeout)
            deps = sorted({os.path.relpath(d, worktree) if os.path.relpath(d, worktree) != "." else "" for d in lo["stdout"].split()
                           if containment._under(Path(d), worktree)})
            rid = f + "::go:generate"
            flaky = "fail" in attempts and "pass" in attempts
            steps[rid] = {"kind": "generate", "root": root, "file": f, **{k: v for k, v in s.items() if k != "stdout"},
                          "attempts": attempts, "flaky": flaky, **({"failures": failures} if failures else {})}
            generated.append({"id": rid, "dir": pkg, "outcome": s["outcome"], "attempts": attempts, "flaky": flaky, "changed": changed, "diff": text[:GENERATED_CAP],
                              "diff_sha256": hashlib.sha256(text.encode("utf-8", "surrogateescape")).hexdigest(), "truncated": len(text) > GENERATED_CAP,
                              "deps": deps, "deps_listed": lo["outcome"] == "pass"})
        for kind, argv in (("build", ["go", "build", "./..."]), ("vet", ["go", "vet", "./..."])):
            s = _go_step(argv, cwd, env, timeout)
            steps[f"{root or '.'}::{' '.join(argv)}"] = {"kind": kind, "root": root, **{k: v for k, v in s.items() if k != "stdout"}}
    return {"roots": roots, "steps": steps, "generated": generated, "ledger": list(containment.LEDGER[start:])}


def go_rows(sel: Selection, cand: dict, base: dict | None) -> tuple[list[dict], list[dict]]:
    """``(build rows, generation test rows)`` from the two trees' steps. A generation whose import closure (on either tree)
    holds an edited path's directory, or that rewrites a file the diff touches, guards the edit — a test row; any other
    generation is a build row beside ``go build`` and ``go vet``."""
    edited = set(sel.edited_files)
    reach: dict[str, bool] = {}
    for g in cand["generated"] + (base["generated"] if base else []):
        hit = any(os.path.dirname(p) in set(g["deps"]) for p in edited) or bool(edited & set(g["changed"]))
        reach[g["id"]] = reach.get(g["id"], False) or hit
    build, gen = [], []
    for rid in sorted(set(cand["steps"]) | set(base["steps"] if base else ())):
        s = cand["steps"].get(rid) or base["steps"][rid]
        row = {"id": rid, "kind": s["kind"], "root": s["root"], "candidate": cand["steps"].get(rid, {}).get("outcome", "not-run"),
               "baseline": (base["steps"].get(rid, {}).get("outcome", "not-run") if base else None)}
        if s["kind"] == "generate" and reach.get(rid):
            gen.append({"id": rid, "file": s["file"], "framework": "go-generate", "origin": "generate", "grain": "deps",
                        "candidate": row["candidate"], "baseline": row["baseline"]})
        else:
            build.append(row)
    return build, gen


def checkout(clone: Path, sha: str, dest: Path) -> Path:
    """A fresh worktree of *clone* at *sha* (a shared clone: no copy of the objects)."""
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(clone), str(dest)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "-q", sha], check=True, capture_output=True, text=True)
    return dest


#: A build/vet error line's own file:line:col prefix — ``{name}`` is *filename*, escaped, at call time.
_BUILD_ERROR_LINE = r"^\S*{name}:\d+:\d+:"


def trim_build_error(stderr_tail: str, filename: str) -> str:
    """calvin-m0-go-r2 §2.4: a Go build/vet step's stderr, trimmed to the lines naming *filename* (its basename — a build error
    names the file it fell in, not the whole module) plus their unindented continuation lines (the ``have``/``want`` blocks an
    arity error prints, each starting with a tab) — dropping every other file's lines and the tool's own trailer. ``""`` when
    *filename* names nothing in *stderr_tail* (the failure is elsewhere in the diff, not this declaration's to repair)."""
    pat = re.compile(_BUILD_ERROR_LINE.format(name=re.escape(filename)))
    lines = stderr_tail.rstrip("\n").split("\n")
    kept: list[str] = []
    keeping = False
    for ln in lines:
        if pat.match(ln):
            kept.append(ln)
            keeping = True
        elif keeping and ln.startswith("\t"):
            kept.append(ln)
        else:
            keeping = False
    return "\n".join(kept)


def build_row(clone: Path, sha: str, diff: str, L: T.Ledger, source: Path, *, timeout: int = 900) -> dict:
    """calvin-m0-go-r2 §2.4: the build row alone on *diff* applied at *sha* — no baseline tree, no test selection, just the tree
    steps (`go_tree`: ``go generate``, ``go build ./...``, ``go vet ./...``) — what the declaration repair (`adapter.
    declaration_build_errors`) reads before asking anything back. Contained (ADR-092), the same environment binding `verify`
    uses. Returns ``{"applies", "apply_error"?, "roots", "steps", "wall_s"}``; a diff with no hunk (T asked nothing, or asked and
    got nothing back) applies trivially and runs no step — there is nothing yet to build."""
    t0 = time.monotonic()
    if not split_patch(diff):
        return {"applies": True, "roots": [], "steps": {}, "wall_s": 0.0}
    key = hashlib.sha256(diff.encode("utf-8", "surrogateescape")).hexdigest()[:12]
    scratch = staging.cache_root() / "verify" / f"{sha[:12]}-build-{key}"
    try:
        wt = checkout(clone, sha, scratch / "work")
        chk = subprocess.run(["git", "apply", "--check", "-"], cwd=wt, input=diff, capture_output=True, text=True)
        if chk.returncode:
            return {"applies": False, "apply_error": chk.stderr.strip()[-400:], "roots": [], "steps": {}, "wall_s": round(time.monotonic() - t0, 1)}
        subprocess.run(["git", "apply", "-"], cwd=wt, input=diff, check=True, capture_output=True, text=True)
        sel = select_tests(L, diff)
        env = environment(source, wt)
        link_deps(env, wt)
        gt = go_tree(wt, sel, env, timeout=timeout)
        return {"applies": True, "roots": gt["roots"], "steps": gt["steps"], "wall_s": round(time.monotonic() - t0, 1)}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


CLASSES = ("P2P", "F2P", "P2F", "F2F", "new-pass", "new-fail", "removed", "skip", "error", "not-run", "uncollected", "unsupported")
#: The classes that fail a verdict: what the diff itself did. An `F2F` fails on both trees (an environment fault, C-92 — listed
#: under `faults`); a `removed` test is one the diff renamed or deleted (the 2026-09-04 calibration: seven tests three commits
#: renamed). D-p (calvin-m0-go-r2, WP-14, found by WP-13 on `d22371873bd8`): `not-run` is **not** here — `classify` returns it
#: only when neither tree ever executed the id (both `not-run`/`uncollected`, or the row was never baselined at all — a
#: candidate-only `not-run` against a baseline that *did* run something reads `removed`, and against no baseline at all reads
#: `new-fail`/`new-pass`, both already covered above). A row nothing ever ran says nothing about this diff — a `Benchmark*`
#: function the testmap names as a guard but that plain ``go test`` never runs is the case that found it: `not-run`/`not-run`
#: on both trees, previously enough to fail the whole verdict before `vacuous`/`gold_tests` were ever read. It still never
#: counts as *executed* (`EXECUTED`, unchanged) — a `not-run`/`not-run` row now decides nothing either way.
FAILING = ("P2F", "new-fail", "error")
#: The build-row classes that make the verdict `build-fail` (a tree the diff leaves that does not build or vet); `fail` is an unbaselined row's.
BUILD_FAILING = ("P2F", "new-fail", "fail", "error")


def classify(candidate: str, baseline: str | None) -> str:
    """A test's class from its outcome with the diff and without it."""
    if candidate in ("not-run", "uncollected") and baseline not in (None, "not-run", "uncollected"):
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
        gt = go_tree(wt, sel, env, timeout=timeout)  # generation first: the tests read what it writes
        cmds = commands(sel, wt, env, scratch / "reports" / "work")
        res, cmd_recs, ledger = run_commands(wt, cmds, env, timeout=timeout)
        ledger = gt["ledger"] + ledger
        rec["commands"] = cmd_recs
        base_res: dict[str, dict] = {}
        bgt = None
        if baseline and (cmds or gt["steps"]):
            bwt = checkout(clone, sha, scratch / "base")
            benv = environment(source, bwt)
            link_deps(benv, bwt)
            bgt = go_tree(bwt, sel, benv, timeout=timeout)
            bcmds = commands(sel, bwt, benv, scratch / "reports" / "base")
            base_res, base_recs, base_ledger = run_commands(bwt, bcmds, benv, timeout=timeout)
            rec["baseline_commands"] = base_recs
            ledger += bgt["ledger"] + base_ledger
        meta = {t["id"]: t for t in sel.tests}
        rows = []
        for tid in sorted(set(res) | set(base_res)):
            cand = res.get(tid, {}).get("outcome", "not-run")
            base = base_res.get(tid, {}).get("outcome") if baseline else None
            got = res.get(tid) or base_res.get(tid) or {}
            g = got.get("grain", "file")
            m = meta.get(tid, {"file": tid.split("::")[0], "framework": got.get("framework"), "origin": "touched" if g == "file" else "guard", "grain": g})
            note = res.get(tid, {}).get("note") or base_res.get(tid, {}).get("note")
            rows.append({"id": tid, "file": m["file"], "framework": m["framework"], "origin": m["origin"], "grain": m["grain"],
                         "candidate": cand, "baseline": base, **({"note": note} if note else {})})
        if gt["steps"]:
            build, gen = go_rows(sel, gt, bgt)
            rows = sorted(rows + gen, key=lambda r: r["id"])
            rec["build"] = build
            rec["go"] = {"roots": gt["roots"], "steps": {"candidate": gt["steps"], "baseline": bgt["steps"] if bgt else None},
                         "generated": {"candidate": gt["generated"], "baseline": bgt["generated"] if bgt else None}}
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


#: A test row's `candidate` outcomes that mean the test actually ran and reported, as against the testmap merely
#: naming it (`uncollected` — `go test -list`/pytest's collection never returned it) or it never starting
#: (`not-run`). `skip`, `error` and `unsupported` are seen but are not a guard executing: skip decides nothing,
#: error and unsupported report no verdict on the change (calvin-m0-go-r2 §2.3's reading, stated in the report).
EXECUTED = ("pass", "fail")


def guarding_tests_executed(rec: dict) -> dict:
    """From a scored verify record, the tests that guard the diff — `origin` `"guard"` (the testmap's own reach)
    or `"touched"` (a test file the diff itself touches, whole, per `verify`'s docstring) — that executed on the
    candidate tree, as against a tree-step row (`origin == "generate"`, a build guard, not a test): `{"count",
    "ids"}` (calvin-m0-go-r2 §2.3)."""
    ids = [r["id"] for r in rec.get("tests", []) if r.get("origin") in ("guard", "touched") and r.get("candidate") in EXECUTED]
    return {"count": len(ids), "ids": ids}


def score(rec: dict, *, gold_tests: dict | None = None) -> dict:
    """Class every test row of a verify record and read the verdict off the classes — the one place the reading is
    made, so a record can be rescored into a new file when the classes change (never in place). calvin-m0-go-r2
    §2.3 hardens `pass`: a row whose build is clean but that reaches no executed guarding test is `vacuous`, its
    own class, unless *gold_tests* — the verdict of the gold's own test-file hunks applied on top of this diff
    (`gold_tests_verdict`), passed in by the caller because it takes its own `verify` run — itself reads `pass`."""
    rows = rec.get("tests", [])
    builds = rec.get("build", [])
    baseline = rec.get("baseline", True)
    for r in rows + builds:
        r["class"] = classify(r["candidate"], r["baseline"]) if baseline else r["candidate"]
    rec["harness_version"] = HARNESS_VERSION
    rec["summary"] = dict(collections.Counter(r["class"] for r in rows))
    if builds:
        rec["build_summary"] = dict(collections.Counter(r["class"] for r in builds))
    if gold_tests is not None:
        rec["gold_tests"] = gold_tests
    if rec.get("verdict") in ("not-applied", "empty-diff"):
        return rec
    executed = guarding_tests_executed(rec)
    rec["guarding_tests_executed"] = executed
    broken = [b["id"] for b in builds if b["class"] in BUILD_FAILING]
    if broken:
        rec["verdict"] = "build-fail"  # a diff that does not compile is its own class, not a test failure (calvin-m0-go §2.3)
    elif not rows:
        rec["verdict"] = "no-tests"
    elif any(r["class"] in FAILING for r in rows):
        rec["verdict"] = "fail"
    elif executed["count"] == 0 and (rec.get("gold_tests") or {}).get("verdict") != "pass":
        rec["verdict"] = "vacuous"  # build-clean, but no guarding test executed and gold_tests did not carry it (calvin-m0-go-r2 §2.3)
    else:
        rec["verdict"] = "pass"
    if builds:
        rec["build_failures"] = broken
    rec["regressions"] = [r["id"] for r in rows if r["class"] == "P2F"]
    rec["faults"] = [r["id"] for r in rows + builds if r["class"] == "F2F"]
    return rec


#: Go's own wording for a name nothing declares (`undefined: X`) — read off a failing build step's `stderr_tail`
#: to say, of a `gold_tests` `build-fail`, how many are gold's test naming a symbol the arm named differently
#: or never created at all (WP-11a §3).
_UNDEFINED = re.compile(r"undefined: (\S+)")


def gold_tests_verdict(clone: Path, sha: str, arm_diff: str, gold_diff: str, L: T.Ledger, source: Path, *,
                        out: Path | None = None, timeout: int = 900) -> dict:
    """calvin-m0-go-r2 §2.3's second door into ``pass``: the gold's own test-file hunks (`gold_test_hunks`, with
    the test-support fixtures they need) applied on top of *arm_diff*, verified. ``{"verdict", "ids", ...}``,
    verdict one of five, WP-11a §3's split so WP-12 can tell them apart:

    - ``"n/a"`` — the gold diff touches no test file, so this row cannot pass this way (§2.3: "then only
      executed guarding tests can make a pass").
    - ``"conflict"`` — the combined diff does not apply (the arm's diff and the gold's own test hunk collide,
      most often because the arm already rewrote the same test file): its own value, never read as ``fail``,
      because it says nothing about whether the arm's change is right.
    - ``"build-fail"`` — the combined tree does not compile: the gold's tests cannot even run against what the
      arm shipped. Carries ``undefined_symbols`` — names Go's compiler read as ``undefined: X`` in the failing
      build's own stderr — the count of builds failing because gold's test names a symbol the arm named
      differently or never created at all, as against some other compile error.
    - ``"pass"`` / ``"fail"`` — read off exactly the rows belonging to the gold's own touched test files (not
      the whole combined `verify`, which also carries whatever the arm's diff alone reaches): a test that ran
      and failed, or one the testmap named that nothing collected (``ids: []``, noted).
    """
    hunks = gold_test_hunks(gold_diff)
    if not hunks.strip():
        return {"verdict": "n/a", "ids": []}
    combined = (arm_diff if arm_diff.endswith("\n") else arm_diff + "\n") + hunks
    rec = verify(clone, sha, combined, L, source, out=out, baseline=True, timeout=timeout)
    if rec.get("verdict") in ("not-applied", "empty-diff"):
        return {"verdict": "conflict", "ids": [], "apply_error": rec.get("apply_error")}
    if rec.get("verdict") == "build-fail":
        candidate_steps = (rec.get("go") or {}).get("steps", {}).get("candidate") or {}
        undefined = sorted({m for step in candidate_steps.values() for m in _UNDEFINED.findall(step.get("stderr_tail", "") or "")})
        return {"verdict": "build-fail", "ids": [], "build_failures": rec.get("build_failures", []), "undefined_symbols": undefined}
    gold_files = {path for path, _ in split_patch(hunks)}
    rows = [r for r in rec.get("tests", []) if r.get("file") in gold_files]
    if not rows:
        return {"verdict": "fail", "ids": [], "note": "gold's test file named no collected id"}
    failing = [r["id"] for r in rows if r["class"] in FAILING]
    return {"verdict": "fail" if failing else "pass", "ids": [r["id"] for r in rows], "failing": failing}


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


def o_brief(task: str, spec: dict | None, refusal: str | None, repo: str, sha: str, cap: int = MANIFEST_CAP, env: Environment | None = None,
            withheld: bool = False) -> str:
    """The ADR-077-shaped brief: the task, the environment's notes, then every unit's manifest as an aid, not a boundary; the cut stated.
    *withheld* (calvin-m0-gate §0b's A0 check): the task and the notes alone, no derived context at all."""
    from hobbes.run.agents import render_context
    parts = [O_HEAD.format(repo=repo, sha12=sha[:12]), "", "## Task", task.strip(), ""]
    if env and env.notes:
        parts += ["## Environment (the harness's, not the task's)", *[f"- {n}" for n in env.notes], ""]
    if withheld:
        return "\n".join(parts).rstrip() + "\n"
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
                    runtime: Path = LOOP_PATH, box: Path = CALVIN_BOX, network: str = "pasta", knowledge: bool = False, timeout: str = "5s",
                    token_budget: int = O_TOKEN_BUDGET) -> list[str]:
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
    if token_budget:
        cmd.append(f"--loop-arg=--token-budget={token_budget}")
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


#: calvin-m0-gate D-x: what the repo an arm-O session (or its repair turn) is launched from may hold. WP-21's key 1 ran
#: `git show <its own key>` in a session repo cloned from the owned clone's full history; rounds 1–2 carried the same exposure.
SESSION_REPO_RULE = ("An arm-O session starts from a repo cut from the owned clone at the session's base commit (the key's parent; for the "
                     "repair turn, O's harvested commit): a branch at the base, then `git clone --no-local --single-branch --no-tags` (only "
                     "objects reachable from the base cross), `origin` removed, reflogs dropped — checked to hold no commit object that is "
                     "not the base or its ancestor, no remote, no alternates file, and no text under .git naming the owned clone. The "
                     "session's branch is fetched back into the owned clone after it and the cut repo removed; the gate, verify, gold_tests "
                     "and recall read the owned clone, host side, where gold is.")


def session_repo_errors(repo: Path, base: str, owned: Path | None = None) -> list[str]:
    """Every way *repo* breaks `SESSION_REPO_RULE` for *base*, read at the object level (a stash, a reflog's commit, a packed
    unreachable object and a tag are all commit objects in the store); an empty list is a repo an arm-O session may start from."""
    repo = Path(repo)

    def git(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)

    ancestors = set(git("rev-list", base).stdout.split())
    if not ancestors:
        return [f"the base {base[:12]} is not in {repo}"]
    errs: list[str] = []
    objs = git("cat-file", "--batch-all-objects", "--batch-check=%(objecttype) %(objectname)").stdout.splitlines()
    extra = sorted({line.split()[1] for line in objs if line.startswith("commit ")} - ancestors)
    if extra:
        errs.append(f"{len(extra)} commit object(s) neither the base nor its ancestor, e.g. {extra[0][:12]}")
    if git("remote").stdout.strip():
        errs.append("a remote: " + " ".join(git("remote").stdout.split()))
    if (repo / ".git" / "objects" / "info" / "alternates").exists():
        errs.append("an alternates file")
    if owned is not None:
        needle = str(Path(owned).resolve())
        for p in sorted((repo / ".git").rglob("*")):
            if p.is_file() and p.relative_to(repo / ".git").parts[0] != "objects" and needle in p.read_text(errors="replace"):
                errs.append(f".git/{p.relative_to(repo / '.git')} names the owned clone")
                break
    return errs


def session_repo(owned: Path, base: str, dest: Path, name: str) -> Path:
    """calvin-m0-gate D-x: cut the repo an arm-O session (or its repair turn) is launched from, per `SESSION_REPO_RULE` — *base* and its
    ancestors from the *owned* clone, into *dest* (outside the sessions root: never mounted into the container). Raises RuntimeError when
    the cut fails its check (`session_repo_errors`)."""
    owned, dest = Path(owned), Path(dest)
    branch = f"calvin-base/{name}"

    def run(*a: str) -> None:
        subprocess.run(list(a), capture_output=True, text=True, check=True)

    run("git", "-C", str(owned), "branch", "-f", branch, base)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    run("git", "clone", "-q", "--no-local", "--single-branch", "--no-tags", "--branch", branch, str(owned), str(dest))
    run("git", "-C", str(dest), "remote", "remove", "origin")
    run("git", "-C", str(dest), "reflog", "expire", "--expire=now", "--all")
    shutil.rmtree(dest / ".git" / "logs", ignore_errors=True)
    errs = session_repo_errors(dest, base, owned)
    if errs:
        raise RuntimeError(f"the session repo at {dest} breaks the rule: " + "; ".join(errs))
    return dest


def session_repo_record(repo: Path, base: str) -> dict:
    """What the record says of a cut session repo: its base, how many commits it holds, and the rule it was checked against."""
    n = subprocess.run(["git", "-C", str(repo), "rev-list", "--count", base], capture_output=True, text=True).stdout.strip()
    return {"base": base, "commits": int(n) if n.isdigit() else None, "errors": session_repo_errors(repo, base), "rule": "harness.SESSION_REPO_RULE"}


def harvest_back(repo: Path, owned: Path, session_id: str) -> bool:
    """The session's branch — harvested by hobbes-session into the cut *repo* — fetched into the *owned* clone, where `session_patch`, the
    gate and the verifier read it; False when the session left no branch there."""
    branch = f"refs/heads/hobbes/{session_id}"
    if subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "-q", branch], capture_output=True).returncode:
        return False
    subprocess.run(["git", "-C", str(owned), "fetch", "-q", str(repo), f"+{branch}:{branch}"], capture_output=True, text=True, check=True)
    return True


def run_o(clone: Path, sha: str, task: str, L: T.Ledger, source: Path, graphs: tuple[Path, Path], *, session_bin: str, base_url: str, model: str,
          session_id: str, sessions_root: Path, out_dir: Path, template: dict | None = None, timeout: float = 3600.0, verify_after: bool = True,
          dry_run: bool = False, manifest: bool = True, **session_kw) -> dict:
    """Arm O for one unit: the derived artifacts placed at the SHA, the plan and brief, the agent dir, the session, its patch grounded and verified. Returns the record (the session's argv and nothing run under *dry_run*).
    *manifest* False (calvin-m0-gate §0b): no plan is derived, the brief carries the task alone and the agent dir no manifest."""
    clone = Path(clone)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(clone), "checkout", "-q", "--force", sha], check=True, capture_output=True, text=True)
    derived = clone / ".hobbes" / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(graphs[0], derived / "graph.json")
    shutil.copyfile(graphs[1], derived / "tests.json")
    spec, refusal = o_plan(clone, task) if manifest else (None, None)
    env = environment(source, clone, container_root="/work", gocache=f"/sessions/{session_id}/go-build")
    brief = o_brief(task, spec, refusal, "Hobbes" if (clone / "docs" / "hobbes-architecture.md").exists() else clone.name, sha, env=env, withheld=not manifest)
    brief_path = out_dir / f"{session_id}.brief.md"
    brief_path.write_text(brief)
    agent_dir = o_agent_dir(spec, L, out_dir / f"{session_id}.agent")
    # calvin-m0-gate D-x: the session starts from a repo cut at the parent — never the owned clone, whose history holds the key's gold
    repo = session_repo(clone, sha, out_dir / f"{session_id}.repo", session_id)
    (repo / ".hobbes" / "derived").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(graphs[0], repo / ".hobbes" / "derived" / "graph.json")
    shutil.copyfile(graphs[1], repo / ".hobbes" / "derived" / "tests.json")
    cmd = session_command(session_bin, repo, sha, brief_path, agent_dir, env, base_url=base_url, model=model, session_id=session_id, sessions_root=sessions_root, **session_kw)
    rec: dict = {"arm": "O", "sha": sha, "session": session_id, "model": model, "plan": {"refusal": refusal, "withheld": not manifest, "units": [u["name"] for u in (spec or {}).get("units", []) if not u.get("deferred")],
                 "paths": sorted({p for c in (spec or {}).get("contexts", []) for p in [m.get("path") for m in c.get("modules", [])] if p})},
                 "brief_chars": len(brief), "command": cmd, "environment": env.record(), "session_repo": session_repo_record(repo, sha)}
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
    rec["harvested"] = harvest_back(repo, clone, session_id)  # D-x: the session's branch comes back to the owned clone; the cut goes
    shutil.rmtree(repo, ignore_errors=True)
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
