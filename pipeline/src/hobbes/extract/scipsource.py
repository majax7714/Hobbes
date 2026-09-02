"""Lane B: SCIP-proven edges joined onto lane A's structure (§3.2, §3.4).

The helper in ``scip/`` runs an indexer over a staging tree and hands back
definitions and references with file:line coordinates. This module does the
**range join** §3.4 describes: SCIP occurrences carry ranges, lane A's
symbols carry ranges, so a reference at ``file:line`` is attributed to
whichever lane-A symbol encloses it, and pointed at whichever lane-A symbol
its definition starts.

Joining on ranges rather than on ids is what keeps V2.M2 from churning node
identity: the graph's ids stay lane A's, and what lane B contributes is
*confidence* — the same edge, at ``tier: semantic`` instead of
``syntactic``. ADR-028 reserved a ``scip:`` namespace for ids lane B would
have to invent; the range join means M2 barely needs it.

Since ADR-029 the join is not between two finished edge sets but between
two *providers*: tree-sitter's call sites and SCIP's resolutions meet in
the evidence IR (:mod:`hobbes.extract.evidence`) before any graph exists.
This module's job is to get SCIP's facts into that IR and to project the
result back onto lane A's module and symbol ids.
"""

from __future__ import annotations

import json
import os
import re
import shlex
from bisect import bisect_right
from pathlib import Path, PurePosixPath

from hobbes.extract import containment, staging
from hobbes.extract.evidence import SCIP as SCIP_LANE
from hobbes.extract.schema import LANE_SCIP, LANE_TREE_SITTER, tiered_edge

#: Shell-split command replacing ``node <repo>/scip/index.mjs``.
SCIP_CMD_ENV = "HOBBES_SCIP_CMD"

#: Set to "0" to skip lane B entirely — for boxes without the helper
#: installed, and for the lane-A-only tests.
SCIP_ENABLE_ENV = "HOBBES_SCIP"

#: Facts schema this join understands (helper HELPER_VERSION).
#: v2 (V2.M3, ADR-032): facts carry ``dependency_coverage`` on every run.
HELPER_VERSION = 3


class ScipError(RuntimeError):
    """The indexer helper could not run, or answered something unusable."""


#: What one indexing unit's failure may raise without taking the language
#: down. The same tuple the per-language catch uses — nothing broader, so
#: a failure class the language-level handler would not absorb is not
#: quietly absorbed one level deeper either (P10).
UNIT_ERRORS = (ScipError, staging.StagingError, OSError)


def _unit_failure(unit: str, stage: str, what: str, exc: Exception) -> dict:
    """A degradation record for one indexing unit that failed alone.

    Before this existed, one zone with a broken tsconfig cost every other
    zone its semantics: the per-unit error propagated to the per-language
    catch, which can only drop the whole lane. Measured on dagger
    (2026-08-18): one docs zone missing ``@docusaurus/tsconfig`` zeroed
    all 84 TypeScript zones. P6 wants the degradation at the granularity
    of what actually failed.
    """
    return {
        "path": unit or ".",
        "stage": stage,
        "message": (
            f"semantic indexing failed for this {what} alone; its call "
            f"edges fall to lane A's fallback (syntactic tier), other "
            f"{what}s are unaffected: {exc}"
        ),
    }


def find_venv(repo_root: Path) -> tuple[str, str] | None:
    """Pyright's ``(venvPath, venv)`` for the repo's virtual environment.

    Discovery is by convention, in a deterministic order: ``.venv`` then
    ``venv`` at the repo root, then beside each ``pyproject.toml`` in the
    pruned manifest walk — the same "not just the root" correction C-16
    needed, one layer down: this repo's own venv is ``pipeline/.venv``,
    and pointing Pyright at ``<root>/.venv`` quietly resolved none of the
    five declared packages (C-27). A candidate counts only if it holds a
    ``pyvenv.cfg``, the marker every venv/virtualenv writes — a directory
    merely *named* ``.venv`` must not be handed to the indexer as an
    environment. Returns None when nothing qualifies; conda and system
    environments have no on-disk marker here and are not searched for,
    which is C-27's honest residue.
    """
    from hobbes.extract.interfaces import iter_pyprojects

    repo_root = Path(repo_root).resolve()
    candidates = [repo_root / name for name in (".venv", "venv")]
    for pyproject in iter_pyprojects(repo_root):
        candidates.extend(pyproject.parent / name for name in (".venv", "venv"))
    for candidate in candidates:
        if (candidate / "pyvenv.cfg").is_file():
            return str(candidate.parent), candidate.name
    return None


#: Runs inside the *venv's* interpreter, never ours: the environment being
#: described is the one whose ``sys.path`` this python owns. stdlib only —
#: a uv venv has no pip, which is exactly why scip-python's own discovery
#: (the first ``pip3`` on PATH) described the wrong environment (C-27).
_ENV_LISTING_SNIPPET = (
    "import importlib.metadata, json, sys\n"
    "out = []\n"
    "for dist in importlib.metadata.distributions():\n"
    "    name = dist.metadata['Name'] if dist.metadata else None\n"
    "    if not name:\n"
    "        continue\n"
    "    out.append({'name': name, 'version': dist.version,\n"
    "                'files': [str(f) for f in (dist.files or [])]})\n"
    "json.dump(out, sys.stdout)\n"
)


def venv_environment(venv_path: str, venv_name: str) -> list[dict] | None:
    """The venv's installed distributions, in scip-python's
    ``--environment`` shape (``[{name, version, files}]``).

    Asked of the venv's own interpreter, because that is the only thing
    that knows what the venv holds: scip-python's fallback asks whichever
    ``pip3`` is first on PATH, and a uv-managed venv carries no pip, so
    the answer described the *system* environment and every third-party
    reference was attributed to the local project (C-27). Read-only, and
    None on any failure — the index still runs, resolution degrades, and
    ``dependency_coverage`` says so.
    """
    python = Path(venv_path) / venv_name / "bin" / "python"
    if not python.is_file():
        return None
    # The venv's python is a binary under the repo tree, so this step
    # executes repo-provided code: it runs in the ingest container
    # (ADR-092), with the venv and the install it links to mounted ro at
    # their host paths so the link resolves. A ContainmentRefusal
    # propagates — the caller records it; it is never run on the host.
    p = containment.plan(
        "python-env",
        [str(python), "-c", _ENV_LISTING_SNIPPET],
        cwd=str(python.parent.parent),
        # The venv itself, never its parent — that is the repo.
        ro=[str(python.parent.parent), *containment.interpreter_mounts(python)],
    )
    try:
        proc = containment.run(p, timeout=60).proc
    except (OSError, containment.ContainmentError):
        return None
    if proc.returncode != 0:
        return None
    try:
        listing = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return listing if isinstance(listing, list) else None


def declared_dependencies(repo_root: Path) -> list[str]:
    """Third-party packages the repo says it needs (every pyproject.toml).

    Fed to the helper so Decision 4's degradation check has something to
    compare against: an index that resolved *none* of a repo's declared
    dependencies is one whose environment is not installed, and its missing
    third-party edges are absent rather than nonexistent. Without this the
    check is inert — which it silently was until the private-repo-A ingest.

    Walks the whole repo (the pruned `iter_pyprojects` walk, same as the
    CLI pack), not just the root: a repo whose manifest lives in a
    subdirectory — this repo's own deps are in ``pipeline/pyproject.toml``
    — otherwise runs the check against an empty list, and an inert check
    that appears to run is worse than no check (C-16, lifted here).
    """
    from hobbes.extract.interfaces import iter_pyprojects

    names: set[str] = set()
    for pyproject in iter_pyprojects(Path(repo_root)):
        names.update(_declared_in(pyproject))
    return sorted(names)


def _declared_in(pyproject: Path) -> set[str]:
    """Bare package names one ``pyproject.toml`` declares."""
    try:
        import tomllib

        data = tomllib.loads(pyproject.read_text())
    except (OSError, ValueError):
        return set()
    project = data.get("project") or {}
    specs = list(project.get("dependencies") or [])
    for extra in (project.get("optional-dependencies") or {}).values():
        specs.extend(extra)
    names = set()
    for spec in specs:
        if not isinstance(spec, str):
            continue
        # "pkg[extra]>=1.2,<2" -> "pkg"; the index reports bare names.
        name = re.split(r"[<>=!~;\[ ]", spec.strip(), maxsplit=1)[0]
        if name:
            names.add(name)
    return names


def declared_npm_dependencies(package_json: Path) -> list[str]:
    """Third-party packages a ``package.json`` says it needs.

    The TypeScript half of Decision 4's degradation input. Without it the
    check has nothing to compare against — and with the old all-or-nothing
    threshold it had nothing useful to say either (ADR-032).
    """
    try:
        data = json.loads(package_json.read_text())
    except (OSError, ValueError):
        return []
    names = set()
    for field in ("dependencies", "devDependencies"):
        section = data.get(field)
        if isinstance(section, dict):
            names.update(k for k in section if isinstance(k, str))
    return sorted(names)


def enabled() -> bool:
    """Whether lane B should run at all."""
    return os.environ.get(SCIP_ENABLE_ENV, "1") not in ("0", "false", "no")


def _helper_cmd() -> list[str]:
    override = os.environ.get(SCIP_CMD_ENV)
    if override:
        return shlex.split(override)
    helper = Path(__file__).resolve().parents[4] / "scip" / "index.mjs"
    return ["node", str(helper)]


def run_helper(
    config: dict,
    timeout: int = 900,
    ro: list[str] | tuple[str, ...] = (),
    env: tuple[str, ...] | list[str] = (),
) -> dict:
    """Run the helper with *config* and return its parsed facts.

    The helper runs **inside the ingest container** (ADR-092): the
    stage, its config and output are under the cache root (mounted rw at
    its host path), the helper and its indexers come from the hobbes
    checkout's ``scip/`` (ro), and *ro* names the symlink targets this
    stage points at outside the cache — a repo's ``node_modules``, a
    venv — mounted ro at their host paths. Network: none. A step that ran
    on the host instead (no container runtime, non-executing provider;
    or the escape hatch) says so in the facts' ``degraded`` records.
    """
    stage = Path(config["stage"])
    config_path = stage.parent / f"{stage.name}.config.json"
    config_path.write_text(json.dumps(config))
    setup = (
        "the SCIP helper is unusable — install Node and run `npm install` in "
        f"the hobbes repo's scip/, or set ${SCIP_CMD_ENV} (ADR-027)"
    )
    plan = containment.plan(
        containment.INDEX_STEP[config["language"]],
        [*_helper_cmd(), "--config", str(config_path)],
        cwd=stage.parent,
        ro=ro,
        env=env,
    )
    try:
        outcome = containment.run(plan, timeout=timeout)
    except FileNotFoundError as exc:
        raise ScipError(f"{setup}: {exc}") from exc
    except containment.ContainmentError as exc:
        raise ScipError(str(exc)) from exc
    finally:
        config_path.unlink(missing_ok=True)
    proc = outcome.proc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()[-500:]
        raise ScipError(f"{setup}: helper exited {proc.returncode}: {detail}")
    try:
        facts = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ScipError(f"the SCIP helper emitted invalid JSON: {exc}") from exc
    if facts.get("helper_version") != HELPER_VERSION:
        raise ScipError(
            f"SCIP facts version {facts.get('helper_version')!r} unsupported "
            f"(want {HELPER_VERSION})"
        )
    record = containment.host_record(".", f"scip-{config['language']}", plan, outcome)
    if record is not None:
        facts.setdefault("degraded", []).append(record)
    return facts


def _fetch(
    step: str,
    command: list[str],
    cwd: Path,
    *,
    timeout: int | None = None,
    env: tuple[str, ...] = (),
) -> str | None:
    """Run a registry step (network on) and return why it failed, or None.
    A failed fetch is not a failed index: the index step still runs,
    offline, and resolution degrades where the registry was needed
    (C-30's shape, now per fetch). A :class:`containment.ContainmentRefusal`
    is not caught here — ``fetch-java`` executes repo build logic
    (ADR-097) and the guarantee outranks the degrade (P10)."""
    plan = containment.plan(step, command, cwd=cwd, env=env)
    try:
        outcome = containment.run(plan, timeout=timeout or _NPM_INSTALL_TIMEOUT)
    except FileNotFoundError as exc:
        return f"{command[0]} is not installed: {exc}"
    except containment.ContainmentError as exc:
        return str(exc)
    if outcome.proc.returncode != 0:
        tail = (outcome.proc.stderr or outcome.proc.stdout or "").strip().splitlines()[-3:]
        return f"{' '.join(command[:2])} failed: {' | '.join(tail)}"
    return None


class _SymbolIndex:
    """Lane A's symbols, queryable by file and line.

    Two questions, because a reference has two ends: which symbol *encloses*
    this line (the caller), and which symbol *starts* at it (the callee).
    """

    def __init__(self, nodes: list[dict], symbols: list[dict]):
        self._kinds = {s["id"]: s.get("kind") for s in symbols}
        self.module_of_path = {
            n["path"]: n["id"] for n in nodes if n.get("path")
        }
        self._by_module: dict[str, list[dict]] = {}
        for symbol in symbols:
            self._by_module.setdefault(symbol["module"], []).append(symbol)
        for rows in self._by_module.values():
            rows.sort(key=lambda s: (s["line"], -(s.get("end_line") or s["line"])))
        self._starts = {
            module: [s["line"] for s in rows]
            for module, rows in self._by_module.items()
        }

    def kind(self, symbol_id: str) -> str | None:
        """The declared kind of a symbol id, or None for a module id."""
        return self._kinds.get(symbol_id)

    def module(self, path: str) -> str | None:
        return self.module_of_path.get(path)

    def enclosing(self, module: str, line: int) -> str | None:
        """The innermost symbol whose range contains *line*."""
        rows = self._by_module.get(module)
        if not rows:
            return None
        cut = bisect_right(self._starts[module], line)
        best = None
        for symbol in rows[:cut]:
            end = symbol.get("end_line") or symbol["line"]
            if symbol["line"] <= line <= end:
                # Later starts are more deeply nested, so the last match wins.
                best = symbol["id"]
        return best

    def starting_at(self, module: str, line: int) -> str | None:
        """The symbol defined at *line*, innermost first."""
        rows = self._by_module.get(module)
        if not rows:
            return None
        matches = [s["id"] for s in rows if s["line"] == line]
        return matches[-1] if matches else None


def resolution_sites(facts: dict) -> list:
    """SCIP's references as evidence-IR resolution sites (ADR-029)."""
    from hobbes.extract.evidence import RESOLUTION, SCIP, Site

    return [
        Site(
            provider=SCIP,
            kind=RESOLUTION,
            file=ref["file"],
            line=ref["line"],
            name=ref.get("name", ""),
            col=ref.get("col", -1),
            def_file=ref["def_file"],
            def_line=ref["def_line"],
        )
        for ref in facts.get("references", [])
    ]


def project(resolved: list, nodes: list[dict], symbols: list[dict]) -> dict:
    """Project semantic-IR facts onto lane A's module and symbol ids.

    The IR speaks in files and lines because that is what both providers
    can agree on; the graph speaks in ids. This is the only place the two
    vocabularies meet, and it resolves ends the same way for every fact
    kind — the source is whatever symbol encloses the site, the target is
    whatever symbol the definition starts.
    """
    index = _SymbolIndex(nodes, symbols)
    module_evidence: dict[tuple, list] = {}
    symbol_evidence: dict[tuple, list] = {}
    # Call sites the semantic lane resolved to a declaration lane A keeps
    # no symbol for — an interface method, a closure, a nested function
    # below C-9's floor. The site counts as resolved and draws no edge
    # (C-58); returned so the tail view can name it `below-floor`.
    below_floor: list[tuple[str, int]] = []

    for fact in resolved:
        source_module = index.module(fact.source_file)
        target_module = index.module(fact.def_file)
        if source_module is None or target_module is None:
            continue  # a file lane A never discovered; not ours to name
        lane = LANE_SCIP if SCIP_LANE in fact.lanes else LANE_TREE_SITTER
        site = {"path": fact.source_file, "line": fact.line}

        if source_module != target_module:
            key = (source_module, target_module, "imports", fact.tier, lane)
            module_evidence.setdefault(key, []).append(site)

        caller = fact.scope or index.enclosing(source_module, fact.line) or source_module
        callee = index.starting_at(target_module, fact.def_line)
        if callee is None:
            if fact.kind == "calls" and SCIP_LANE in fact.lanes:
                below_floor.append((fact.source_file, fact.line))
            continue
        if caller == callee and fact.kind != "calls":
            continue  # a type naming itself is not an edge; a function calling itself is
        edge_type = fact.kind
        if edge_type == "calls" and fact.def_file.endswith((".go", ".rs")) and index.kind(callee) == "type":
            # Go writes a conversion exactly like a call. Lane A drops the
            # ones it can name (a type in the same or an imported repo
            # package); this is the guard for the rest — a nested module
            # whose import path does not mirror its directory, a
            # dot-import — because a type is never called (O4: 40 of 40
            # contradictions on dagger were `dagger.JSON("0")` as `calls`).
            # Rust writes a tuple-struct constructor the same way
            # (`FinderRev(Hash::new(..))`), and the compiler lowers it to
            # an aggregate, not a call: memchr (O7, 2026-08-27), 7 of 7
            # contradictions. Not Java: `new T()` with an implicit
            # constructor is a call javac places at the class line (the
            # O8 fixture cell: the guard cost that pair), and the one
            # shape that references a type at a `new` — `new T() {..}` —
            # is no lane A site at all (ADR-096). The edge to the type
            # stays, as `uses`.
            edge_type = "uses"
        key = (caller, callee, edge_type, fact.tier, lane)
        symbol_evidence.setdefault(key, []).append(site)

    return {
        "module_edges": _edges(module_evidence),
        "symbol_edges": _edges(symbol_evidence),
        "below_floor": below_floor,
    }


def _edges(evidence: dict[tuple, list]) -> list[dict]:
    """Collapse sightings into edges, keeping tier and lane distinct.

    Two facts with the same endpoints but different tiers are two different
    claims — one proven, one guessed — so they stay separable here, and the
    graph decides which survives rather than this function guessing.
    """
    out = []
    for (source, target, edge_type, tier, lane), sightings in sorted(evidence.items()):
        unique = sorted({(s["path"], s["line"]) for s in sightings})
        out.append(
            tiered_edge(
                source,
                target,
                edge_type,
                [{"path": path, "line": line} for path, line in unique],
                tier=tier,
                lane=lane,
            )
        )
    return out


#: Config filenames staged verbatim alongside a TypeScript zone's sources.
#: Copied rather than parsed: a ``tsconfig.json`` may carry comments and
#: may ``extends`` a sibling, and copying every one of them sidesteps both
#: without a JSON5 dependency. They are tiny.
_TS_CONFIG_NAMES = ("tsconfig.json", "jsconfig.json", "package.json")


def ts_zones(repo_root: Path, files: list[str]) -> dict[str, list[str]]:
    """Group TS/JS *files* by the directory of their nearest tsconfig.

    The M6 zoning lesson, now applied to lane B: per-package compiler
    options — path aliases above all — only resolve the way that package's
    own build does, so each zone is indexed on its own. This is ADR-027's
    "the config is derived, not authored" for TypeScript, and §3.7's
    root-discovery checklist item.

    Files under no tsconfig at all group under ``""`` and get a generated
    config in the stage, which is exactly what the staging tree is for.
    """
    zones: dict[str, list[str]] = {}
    cache: dict[str, str] = {}
    for rel in files:
        directory = str(PurePosixPath(rel).parent)
        if directory not in cache:
            cache[directory] = _nearest_config_dir(repo_root, directory)
        zones.setdefault(cache[directory], []).append(rel)
    return {zone: sorted(paths) for zone, paths in sorted(zones.items())}


def _nearest_config_dir(repo_root: Path, directory: str) -> str:
    """Directory of the nearest tsconfig at or above *directory*, or ""."""
    current = PurePosixPath(directory)
    while True:
        if (repo_root / current / "tsconfig.json").is_file():
            return "" if str(current) == "." else str(current)
        if str(current) == ".":
            return ""
        current = current.parent


def zone_dependency_links(
    repo_root: Path, zone_files: list[str]
) -> dict[str, str]:
    """Every ``node_modules`` tree a zone's files would resolve against
    in the repo, keyed by stage-relative path (ADR-050).

    TypeScript resolution walks up from the *importing file*, not from
    the zone root — so a zone that groups files from several package
    directories (this repo's tsconfig-less ``tsextract/`` and ``scip/``
    both land in the root zone) resolves each file against the
    ``node_modules`` beside it. Linking only the zone root's tree, as
    the first version did, left those files' dependencies behind in the
    stage while lane A — which reads the real repo — resolved them
    fine: a silent lane asymmetry measured on this repo's own 61.6%.
    """
    links: dict[str, str] = {}
    seen: set[str] = set()
    for rel in zone_files:
        directory = PurePosixPath(rel).parent
        while True:
            key = str(directory)
            if key in seen:
                break
            seen.add(key)
            candidate = (
                repo_root / directory / "node_modules"
                if key != "."
                else repo_root / "node_modules"
            )
            if candidate.is_dir():
                stage_rel = (
                    "node_modules" if key == "." else f"{key}/node_modules"
                )
                links[stage_rel] = str(candidate.resolve())
            if key == ".":
                break
            directory = directory.parent
    return links


#: Seconds a dependency install may take. Docusaurus-sized trees need
#: minutes; a hang needs an end.
_NPM_INSTALL_TIMEOUT = 600

#: The classic-yarn version corepack runs for v1 lockfiles. Pinned in
#: code for the same reason every indexer is (ADR-027 Decision 1): an
#: unpinned installer is a different environment on every box.
_YARN1_VERSION = "1.22.22"


def detect_installer(manifest_dir: Path) -> tuple[str, str] | tuple[None, str]:
    """``(installer, lockfile)`` for a package directory, or ``(None,
    why)``.

    Only lockfile-backed installs are offered — ``npm ci`` for
    ``package-lock.json``, classic yarn for a v1 ``yarn.lock`` — because
    a lockfile is what makes the provisioned tree the *repo's* pinned
    resolution rather than the registry's answer of the day (P1).
    pnpm and Yarn Berry are declined by name: Berry's PnP does not even
    produce the ``node_modules`` shape the indexer resolves against.
    """
    if (manifest_dir / "package-lock.json").is_file():
        return "npm", "package-lock.json"
    yarn_lock = manifest_dir / "yarn.lock"
    if yarn_lock.is_file():
        try:
            head = yarn_lock.read_text(errors="replace")[:2048]
        except OSError:
            return None, "yarn.lock unreadable"
        if "yarn lockfile v1" in head:
            return "yarn1", "yarn.lock"
        return None, "yarn.lock is Berry (v2+), which does not build node_modules"
    if (manifest_dir / "pnpm-lock.yaml").is_file():
        return None, "pnpm-lock.yaml (pnpm installs are not provisioned)"
    return None, "no lockfile (an unpinned install would drift — C-34)"


def _corepack() -> Path | None:
    """corepack, which ships beside the real node binary but rarely on
    PATH through symlink farms."""
    import shutil as _shutil

    node = _shutil.which("node")
    if node is None:
        return None
    candidate = Path(node).resolve().parent / "corepack"
    return candidate if candidate.is_file() else None


def provision_node_modules(
    repo_root: Path, manifest_dir_rel: str
) -> tuple[Path | None, str | None]:
    """A ``node_modules`` for *manifest_dir_rel*, installed into Hobbes's
    own cache — never the repo (ADR-050).

    Returns ``(path, None)`` on success or ``(None, why)``. The install
    is keyed by the content hash of ``package.json`` + the lockfile, so
    re-ingests reuse it; it runs with ``--ignore-scripts`` always — a
    dependency's lifecycle script is arbitrary code, and unlike C-29
    there is no analyzer requiring it — and it needs a fetchable npm
    registry (C-34, the npm sibling of C-30).
    """
    import hashlib
    import shutil as _shutil

    manifest_dir = repo_root / manifest_dir_rel if manifest_dir_rel else repo_root
    installer, lockfile = detect_installer(manifest_dir)
    if installer is None:
        return None, lockfile
    package_json = manifest_dir / "package.json"
    if not package_json.is_file():
        return None, "no package.json beside the lockfile"

    digest = hashlib.sha256(
        package_json.read_bytes() + (manifest_dir / lockfile).read_bytes()
    ).hexdigest()[:16]
    cache = staging.cache_root() / "npm" / digest
    tree = cache / "node_modules"
    if (cache / ".complete").is_file() and tree.is_dir():
        return tree, None

    cache.mkdir(parents=True, exist_ok=True)
    _shutil.copy2(package_json, cache / "package.json")
    _shutil.copy2(manifest_dir / lockfile, cache / lockfile)
    if installer == "npm":
        argv = ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"]
    else:
        corepack = _corepack()
        if corepack is None:
            return None, "yarn.lock v1 but corepack is not installed"
        argv = [
            str(corepack), f"yarn@{_YARN1_VERSION}", "install",
            "--ignore-scripts", "--frozen-lockfile", "--non-interactive",
        ]
    # The install is a fetch step (ADR-092): network on, no repo code —
    # `--ignore-scripts` keeps it that way — in its own container.
    failure = _fetch("fetch-npm", argv, cache)
    if failure is not None:
        return None, failure
    if not tree.is_dir():
        return None, "install succeeded but produced no node_modules"
    (cache / ".complete").write_text("")
    return tree, None


def _nearest_package_manifest(repo_root: Path, zone: str) -> str | None:
    """Repo-relative directory of the nearest ``package.json`` at or
    above *zone*, or None."""
    current = PurePosixPath(zone) if zone else PurePosixPath(".")
    while True:
        probe = repo_root / current / "package.json" if str(current) != "." else repo_root / "package.json"
        if probe.is_file():
            return "" if str(current) == "." else str(current)
        if str(current) == ".":
            return None
        current = current.parent


def _staged_ts_configs(repo_root: Path, files: list[str]) -> list[str]:
    """Every tsconfig/package.json at or above a staged TS file."""
    wanted: set[str] = set()
    for rel in files:
        current = PurePosixPath(rel).parent
        while True:
            for name in _TS_CONFIG_NAMES:
                candidate = current / name if str(current) != "." else PurePosixPath(name)
                if (repo_root / candidate).is_file():
                    wanted.add(str(candidate))
            if str(current) == ".":
                break
            current = current.parent
    return sorted(wanted)


def _generated_tsconfig(files: list[str], zone: str) -> dict:
    """A config for files the repo never gave one.

    Mirrors `tsextract`'s zone-less default project, so both lanes see the
    same language dialect. ``files`` is explicit rather than a glob: a
    root-level config with a default include would swallow every other
    zone's sources and index them under the wrong compiler options.
    """
    prefix = f"{zone}/" if zone else ""
    return {
        "compilerOptions": {
            "allowJs": True,
            "checkJs": False,
            "module": "ESNext",
            "moduleResolution": "Bundler",
            "target": "ES2022",
            "jsx": "preserve",
            "noEmit": True,
            "skipLibCheck": True,
        },
        "files": [
            rel[len(prefix):] if prefix and rel.startswith(prefix) else rel
            for rel in files
        ],
    }


def extract_scip_typescript(
    repo_root: Path, files: list[str], sha: str = ""
) -> dict | None:
    """Index every TypeScript zone and return one merged facts document.

    One indexer run per zone, because a zone is a separate TypeScript
    program (M6). Zones are merged rather than reconciled: they resolve
    independently, so a cross-zone import resolves in neither — which is
    C-12, unchanged by this milestone and now true of both lanes.
    """
    if not enabled() or not files:
        return None
    repo_root = Path(repo_root).resolve()
    merged: dict = {
        "definitions": [],
        "references": [],
        "external_refs": [],
        "packages": {},
        "degraded": [],
        "dependency_coverage": {"declared": 0, "resolved": 0, "missing": []},
    }
    for zone, zone_files in ts_zones(repo_root, files).items():
        try:
            facts = _index_ts_zone(repo_root, zone, zone_files, sha)
        except containment.ContainmentRefusal:
            raise  # P10: the guarantee outranks the per-unit degrade
        except UNIT_ERRORS as exc:
            merged["degraded"].append(
                _unit_failure(zone, "scip-typescript", "zone", exc)
            )
            continue
        if facts is None:
            continue
        for key in ("definitions", "references", "external_refs", "degraded"):
            merged[key].extend(facts.get(key, []))
        for name, count in (facts.get("packages") or {}).items():
            merged["packages"][name] = merged["packages"].get(name, 0) + count
        zone_coverage = facts.get("dependency_coverage") or {}
        merged["dependency_coverage"]["declared"] += zone_coverage.get("declared", 0)
        merged["dependency_coverage"]["resolved"] += zone_coverage.get("resolved", 0)
        merged["dependency_coverage"]["missing"].extend(
            zone_coverage.get("missing", [])
        )
    merged["dependency_coverage"]["missing"] = sorted(
        set(merged["dependency_coverage"]["missing"])
    )
    join_cross_unit(merged)
    return merged


def join_cross_unit(merged: dict) -> None:
    """Resolve external references against sibling units' definitions
    (ADR-049, lifting C-33).

    "External" in a decoded index means external to *that index* — but a
    language's units (Go modules, cargo roots, TS zones) are indexed
    separately and merged, so a reference into a sibling unit of the same
    repo sits in ``external_refs`` carrying the exact moniker the
    sibling's own index defines. Moniker equality is the join: exact,
    never heuristic — this is not C-12's rejected cross-zone
    *reconciliation*, because nothing here interprets another unit's
    compiler configuration; a moniker either matches or the reference
    stays external.

    A moniker defined by more than one unit (in different files) is
    dropped from the joinable set and the drop reported — C-28's rule
    applied across units: unattributed rather than guessed. Mutates
    *merged* in place, after every unit has been merged.
    """
    by_moniker: dict[str, dict] = {}
    ambiguous: set[str] = set()
    for definition in merged["definitions"]:
        moniker = definition.get("moniker")
        if not moniker:
            continue
        prior = by_moniker.setdefault(moniker, definition)
        if prior is not definition and prior["file"] != definition["file"]:
            ambiguous.add(moniker)
    still_external = []
    for ref in merged["external_refs"]:
        moniker = ref.get("moniker") or ""
        target = by_moniker.get(moniker)
        if target is None or moniker in ambiguous:
            still_external.append(ref)
            continue
        merged["references"].append(
            {
                "file": ref["file"],
                "line": ref["line"],
                "col": ref["col"],
                "name": ref["name"],
                "def_file": target["file"],
                "def_line": target["line"],
            }
        )
    merged["external_refs"] = still_external
    if ambiguous:
        sample = ", ".join(sorted(ambiguous)[:3])
        merged["degraded"].append(
            {
                "path": ".",
                "stage": "scip-merge",
                "message": (
                    f"{len(ambiguous)} symbol(s) are defined in more than "
                    f"one indexing unit (e.g. {sample}) — references to "
                    "them stay unattributed rather than guessed (C-28's "
                    "rule, across units)"
                ),
            }
        )


def go_modules(repo_root: Path, files: list[str]) -> dict[str, list[str]]:
    """Group Go *files* by the directory of their nearest ``go.mod``.

    The TS zoning lesson, a language later: a Go module is the unit the
    loader understands, and this repo is the worked example — its
    ``go.mod`` is at ``go/``, not the root, so indexing from the repo root
    would find no module at all. Files under no module group under ``""``
    and are skipped rather than guessed at, because a Go file outside a
    module cannot be type-checked and inventing a ``go.mod`` would invent
    its dependencies too.
    """
    modules: dict[str, list[str]] = {}
    cache: dict[str, str | None] = {}
    for rel in files:
        directory = str(PurePosixPath(rel).parent)
        if directory not in cache:
            cache[directory] = _nearest_go_module(repo_root, directory)
        root = cache[directory]
        if root is None:
            continue
        modules.setdefault(root, []).append(rel)
    return {root: sorted(paths) for root, paths in sorted(modules.items())}


def go_orphans(files: list[str], grouped: dict[str, list[str]]) -> dict[str, list[str]]:
    """Go files *grouped* left out, by directory — the C-26 denominator.

    Public and pure so the surfacing has a test that runs without an
    indexer installed: the skip itself lives in :func:`go_modules`, and a
    skip nobody can see is how a lane quietly stops covering (the
    lane-agreement lesson, applied to degradation).
    """
    covered = {path for paths in grouped.values() for path in paths}
    orphans: dict[str, list[str]] = {}
    for rel in files:
        if rel not in covered:
            orphans.setdefault(str(PurePosixPath(rel).parent), []).append(rel)
    return {directory: sorted(paths) for directory, paths in sorted(orphans.items())}


def _nearest_go_module(repo_root: Path, directory: str) -> str | None:
    """Directory of the nearest ``go.mod`` at or above *directory*."""
    current = PurePosixPath(directory)
    while True:
        if (repo_root / current / "go.mod").is_file():
            return "" if str(current) == "." else str(current)
        if str(current) == ".":
            return None
        current = current.parent


def extract_scip_go(
    repo_root: Path, files: list[str], sha: str = ""
) -> dict | None:
    """Index every Go module and return one merged facts document.

    One run per ``go.mod``, for the reason TS runs one per tsconfig: the
    module is what the loader resolves against. Paths come back relative to
    the module root and are re-rooted at the repo by :func:`_rebase`, the
    same correction that made or broke the TS lane at V2.M3.
    """
    if not enabled() or not files:
        return None
    repo_root = Path(repo_root).resolve()
    merged: dict = {
        "definitions": [],
        "references": [],
        "external_refs": [],
        "packages": {},
        "degraded": [],
        "dependency_coverage": {"declared": 0, "resolved": 0, "missing": []},
    }
    grouped = go_modules(repo_root, files)
    for directory, orphans in go_orphans(files, grouped).items():
        # C-26 (surfaced): the tier already says these files' edges are lane
        # A's; this record says *why* this file in particular got no
        # semantics, which the tier cannot.
        merged["degraded"].append(
            {
                "path": directory,
                "stage": "scip-go",
                "message": (
                    f"{len(orphans)} Go file(s) under {directory!r} sit below no "
                    "go.mod, so scip-go cannot type-check them; their call edges "
                    "fall to lane A's fallback (syntactic tier). Add a go.mod to "
                    "give them semantics."
                ),
            }
        )
    for module_root, module_files in grouped.items():
        try:
            facts = _index_go_module(
                repo_root, module_root, module_files, sha, grouped
            )
        except containment.ContainmentRefusal:
            raise  # P10: the guarantee outranks the per-unit degrade
        except UNIT_ERRORS as exc:
            merged["degraded"].append(
                _unit_failure(module_root, "scip-go", "module", exc)
            )
            continue
        if facts is None:
            continue
        for key in ("definitions", "references", "external_refs", "degraded"):
            merged[key].extend(facts.get(key, []))
        for name, count in (facts.get("packages") or {}).items():
            merged["packages"][name] = merged["packages"].get(name, 0) + count
    join_cross_unit(merged)
    return merged


#: A go.mod replace whose right side is a filesystem path — the spec says
#: a path replacement must start with ``./`` or ``../``, which is what
#: separates it from a module replacement (``X => Y v1.2.3``).
_GO_PATH_REPLACE = re.compile(
    r"^\s*(?:replace\s+)?\S+(?:\s+v\S+)?\s+=>\s+(\.\.?/\S*)\s*$"
)


def go_replace_targets(repo_root: Path, module_root: str) -> list[str]:
    """Module roots (repo-relative) a module's ``go.mod`` replaces into.

    Only path replacements that resolve **inside the repo** count — a
    replace escaping the repo names code Hobbes will not stage (the
    staging contract copies the repo, nothing else). Only the consumer's
    own ``go.mod`` is read, which is exactly Go's rule: replace
    directives apply in the main module only.
    """
    manifest = repo_root / (f"{module_root}/go.mod" if module_root else "go.mod")
    try:
        lines = manifest.read_text().splitlines()
    except OSError:
        return []
    targets = []
    for line in lines:
        match = _GO_PATH_REPLACE.match(line.split("//", 1)[0])
        if not match:
            continue
        resolved = (
            (repo_root / module_root / match.group(1)).resolve()
            if module_root
            else (repo_root / match.group(1)).resolve()
        )
        try:
            rel = resolved.relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            continue  # escapes the repo: not ours to stage
        targets.append("" if rel == "." else rel)
    return sorted(set(targets))


def cargo_crates(repo_root: Path, files: list[str]) -> dict[str, list[str]]:
    """Group Rust *files* by the manifest root that indexes them.

    The go.mod/tsconfig lesson, third spelling: the unit rust-analyzer's
    loader understands is a cargo package — or a **workspace**, whose root
    manifest carries the members' lock and patch tables — so files group
    by their nearest ``Cargo.toml`` and then collapse to the nearest
    ``[workspace]`` manifest above it, one index run per root. Files under
    no manifest group under nothing and are skipped rather than guessed
    at (the C-26 pattern): inventing a manifest would invent the
    dependency versions with it.
    """
    grouped: dict[str, list[str]] = {}
    cache: dict[str, str | None] = {}
    for rel in files:
        directory = str(PurePosixPath(rel).parent)
        if directory not in cache:
            crate = _nearest_manifest(repo_root, directory, "Cargo.toml")
            cache[directory] = _workspace_root(repo_root, crate) if crate is not None else None
        root = cache[directory]
        if root is None:
            continue
        grouped.setdefault(root, []).append(rel)
    return {root: sorted(paths) for root, paths in sorted(grouped.items())}


def _nearest_manifest(repo_root: Path, directory: str, name: str) -> str | None:
    """Directory of the nearest *name* at or above *directory*."""
    current = PurePosixPath(directory)
    while True:
        if (repo_root / current / name).is_file():
            return "" if str(current) == "." else str(current)
        if str(current) == ".":
            return None
        current = current.parent


def _workspace_root(repo_root: Path, crate_root: str) -> str:
    """The nearest ``[workspace]`` manifest at or above *crate_root*.

    A member crate's manifest can lean on the workspace root's
    (``version.workspace = true``), so indexing the member alone fails on
    a repo that builds fine. Detection reads the manifest rather than
    trusting directory shape; a parse error just means "not a workspace",
    which degrades to per-crate indexing, visibly if the load then fails.
    """
    import tomllib

    current = PurePosixPath(crate_root) if crate_root else PurePosixPath(".")
    found = crate_root
    while True:
        manifest = repo_root / current / "Cargo.toml"
        if manifest.is_file():
            try:
                if "workspace" in tomllib.loads(manifest.read_text()):
                    found = "" if str(current) == "." else str(current)
            except (OSError, ValueError):
                pass
        if str(current) == ".":
            return found
        current = current.parent


def declared_cargo_dependencies(manifest: Path) -> list[str]:
    """Third-party crates one ``Cargo.toml`` says it needs.

    The Rust arm of Decision 4's degradation input: an index that resolved
    none of these is describing a repo whose crate registry was never
    fetched (C-30), and its missing third-party edges are absent rather
    than nonexistent.
    """
    import tomllib

    try:
        data = tomllib.loads(manifest.read_text())
    except (OSError, ValueError):
        return []
    names: set[str] = set()
    sections = [
        data.get("dependencies"),
        data.get("dev-dependencies"),
        data.get("build-dependencies"),
        (data.get("workspace") or {}).get("dependencies"),
    ]
    for section in sections:
        if isinstance(section, dict):
            names.update(k for k in section if isinstance(k, str))
    return sorted(names)


def extract_scip_rust(
    repo_root: Path, files: list[str], sha: str = ""
) -> dict | None:
    """Index every cargo root and return one merged facts document.

    **Indexing Rust executes the repo's code** (C-29): rust-analyzer runs
    cargo's loader with build-script and proc-macro support, so a
    ``build.rs`` runs on this machine during ingest — no other lane B
    provider executes repo-authored code. The notice below is the
    surfacing; it prints every time, not only the first, because the
    posture fact does not wear off.
    """
    if not enabled() or not files:
        return None
    repo_root = Path(repo_root).resolve()
    merged: dict = {
        "definitions": [],
        "references": [],
        "external_refs": [],
        "packages": {},
        "degraded": [],
        "dependency_coverage": {"declared": 0, "resolved": 0, "missing": []},
    }
    grouped = cargo_crates(repo_root, files)
    for directory, orphans in go_orphans(files, grouped).items():
        # The C-26 pattern, one language over: the skip is visible where a
        # user meets it, with the fix named.
        merged["degraded"].append(
            {
                "path": directory,
                "stage": "scip-rust",
                "message": (
                    f"{len(orphans)} Rust file(s) under {directory!r} sit below no "
                    "Cargo.toml, so rust-analyzer cannot load them; their call "
                    "edges fall to lane A's fallback (syntactic tier). Add a "
                    "Cargo.toml to give them semantics."
                ),
            }
        )
    if grouped:
        import sys

        print(
            "NOTE: rust semantics: rust-analyzer executes the repo's build "
            "scripts and proc macros during indexing, inside the ingest "
            "container (C-29, ADR-092)",
            file=sys.stderr,
        )
    for root, root_files in grouped.items():
        try:
            facts = _index_cargo_root(repo_root, root, root_files, sha)
        except containment.ContainmentRefusal:
            raise  # P10: the guarantee outranks the per-unit degrade
        except UNIT_ERRORS as exc:
            merged["degraded"].append(
                _unit_failure(root, "scip-rust", "cargo root", exc)
            )
            continue
        if facts is None:
            continue
        for key in ("definitions", "references", "external_refs", "degraded"):
            merged[key].extend(facts.get(key, []))
        for name, count in (facts.get("packages") or {}).items():
            merged["packages"][name] = merged["packages"].get(name, 0) + count
        coverage = facts.get("dependency_coverage") or {}
        merged["dependency_coverage"]["declared"] += coverage.get("declared", 0)
        merged["dependency_coverage"]["resolved"] += coverage.get("resolved", 0)
        merged["dependency_coverage"]["missing"].extend(coverage.get("missing", []))
    merged["dependency_coverage"]["missing"] = sorted(
        set(merged["dependency_coverage"]["missing"])
    )
    join_cross_unit(merged)
    return merged


def _index_cargo_root(
    repo_root: Path, root: str, root_files: list[str], sha: str
) -> dict | None:
    """Stage and index one cargo package or workspace.

    Staged beside the sources: every manifest on a staged file's path (a
    member leans on the workspace root's), ``Cargo.lock`` so resolution
    matches the repo's, and ``.cargo/config.toml`` when present. The
    dependency tree needs no symlink — cargo's registry is user-global,
    which is where ADR-032's problem dissolves for Rust and C-30 begins.
    """
    staged = set(root_files)
    manifests: set[str] = set()
    for rel in root_files:
        nearest = _nearest_manifest(repo_root, str(PurePosixPath(rel).parent), "Cargo.toml")
        if nearest is not None:
            manifests.add(f"{nearest}/Cargo.toml" if nearest else "Cargo.toml")
    manifests.add(f"{root}/Cargo.toml" if root else "Cargo.toml")
    staged |= {m for m in manifests if (repo_root / m).is_file()}
    for extra in ("Cargo.lock", ".cargo/config.toml"):
        candidate = f"{root}/{extra}" if root else extra
        if (repo_root / candidate).is_file():
            staged.add(candidate)

    declared: set[str] = set()
    for manifest in manifests:
        if (repo_root / manifest).is_file():
            declared.update(declared_cargo_dependencies(repo_root / manifest))

    stage = staging.build_stage(repo_root, sorted(staged), sha=sha)
    crate_root = stage / root if root else stage
    try:
        # Registry first, in the container that has a network and runs
        # nothing; then the index, in the one that runs build scripts and
        # has none (ADR-092's split of C-30's "fetchable registry").
        fetch_failure = _fetch(
            "fetch-rust",
            containment.rust_fetch_command(str(crate_root / "Cargo.toml")),
            crate_root,
        )
        facts = run_helper(
            {
                "stage": str(crate_root),
                "language": "rust",
                "projectName": repo_root.name,
                # Unused by the rust argv — the moniker version is the
                # crate's own (ADR-040) — carried for config uniformity.
                "projectVersion": "0",
                "output": str(stage.parent / f"{stage.name}.scip"),
                "declaredDeps": sorted(declared),
            }
        )
    finally:
        staging.remove_stage(stage)
    if fetch_failure is not None:
        facts.setdefault("degraded", []).append(
            {
                "path": ".",
                "stage": "scip-rust",
                "message": (
                    f"crate registry fetch failed ({fetch_failure}); third-party "
                    "resolution degrades, in-repo edges survive (C-30)"
                ),
            }
        )
    return _rebase(facts, root)


#: The image's JDKs, for Gradle's toolchain resolution (ADR-096): a
#: `languageVersion` pin refuses any other major and cannot download one
#: offline (the J.M0 spike), so the three LTS majors the image carries
#: are named in the derived `gradle.properties` under GRADLE_USER_HOME.
JAVA_INSTALLATIONS = ("/usr/local/java-17", "/usr/local/java-21", "/usr/local/java-25")

_GRADLE_BUILD = ("build.gradle", "build.gradle.kts")
_GRADLE_SETTINGS = ("settings.gradle", "settings.gradle.kts")
#: Files a Java build reads besides the sources, by name or directory.
_JAVA_BUILD_NAMES = {"pom.xml", *_GRADLE_BUILD, *_GRADLE_SETTINGS, "gradle.properties",
                     "gradlew", "mvnw", "lombok.config"}
_JAVA_BUILD_DIRS = {"gradle", ".mvn", "buildSrc"}


def java_units(repo_root: Path, files: list[str]) -> dict[str, tuple[str, list[str]]]:
    """Group Java *files* by the build root that indexes them:
    ``{root: (tool, files)}``, *tool* ``maven`` or ``gradle``.

    The go.mod/tsconfig/Cargo lesson, fourth spelling: scip-java drives
    the build, so the unit is what the build tool roots at — a Maven
    reactor (the highest ``pom.xml`` above the file) or a Gradle build
    (the nearest ``settings.gradle[.kts]``, else the build file's own
    directory). A directory holding both (spring-petclinic) is indexed
    with Maven: its resolution is declarative, the pom is data. Files
    under no build file group under nothing and are skipped, reported
    (the C-26 pattern): inventing a build would invent its dependencies.
    """
    grouped: dict[str, tuple[str, list[str]]] = {}
    cache: dict[str, tuple[str, str] | None] = {}
    for rel in files:
        directory = str(PurePosixPath(rel).parent)
        if directory not in cache:
            cache[directory] = _java_build_root(repo_root, directory)
        unit = cache[directory]
        if unit is None:
            continue
        tool, root = unit
        grouped.setdefault(root, (tool, []))[1].append(rel)
    return {root: (tool, sorted(paths)) for root, (tool, paths) in sorted(grouped.items())}


def _java_build_root(repo_root: Path, directory: str) -> tuple[str, str] | None:
    current = PurePosixPath(directory)
    nearest: tuple[str, PurePosixPath] | None = None
    while True:
        here = repo_root / current
        if (here / "pom.xml").is_file():
            nearest = ("maven", current)
            break
        if any((here / name).is_file() for name in (*_GRADLE_BUILD, *_GRADLE_SETTINGS)):
            nearest = ("gradle", current)
            break
        if str(current) == ".":
            return None
        current = current.parent
    tool, at = nearest
    if tool == "maven":
        # The highest pom above: a reactor's modules lean on its root.
        top = at
        probe = at
        while True:
            if str(probe) == ".":
                break
            probe = probe.parent
            if (repo_root / probe / "pom.xml").is_file():
                top = probe
        root = top
    else:
        root = at
        probe = at
        while True:
            if any((repo_root / probe / name).is_file() for name in _GRADLE_SETTINGS):
                root = probe
                break
            if str(probe) == ".":
                break
            probe = probe.parent
    return tool, ("" if str(root) == "." else str(root))


def java_build_files(repo_root: Path, root: str) -> list[str]:
    """Every file under *root* the build could read that is not a
    source: the poms and Gradle scripts at every level, the wrappers and
    their ``gradle/`` / ``.mvn/`` trees, a ``buildSrc/``, resources, a
    checkstyle config a pom binds to ``validate`` (spring-petclinic's
    ``src/checkstyle/nohttp-checkstyle.xml`` — the first real repo failed
    on exactly that when only the build files were staged). The build
    sees the tree it was written for; the stage is a copy, so the cost
    is bytes, not trust. Walked with lane A's pruning so ``target/`` and
    ``build/`` never enter the stage, and dot-directories are kept only
    for the two build tools' own (``.mvn``)."""
    from hobbes.extract.javasource import _JAVA_SKIPPED

    base = repo_root / root if root else repo_root
    out: list[str] = []
    stack = [base]
    while stack:
        directory = stack.pop()
        try:
            children = sorted(directory.iterdir())
        except OSError:
            continue
        for child in children:
            rel = child.relative_to(repo_root).as_posix()
            if child.is_symlink():
                continue
            if child.is_dir():
                if child.name in _JAVA_BUILD_DIRS:
                    out.extend(
                        p.relative_to(repo_root).as_posix()
                        for p in sorted(child.rglob("*")) if p.is_file() and not p.is_symlink()
                    )
                elif child.name not in _JAVA_SKIPPED and not child.name.startswith("."):
                    stack.append(child)
            elif child.suffix != ".java":
                out.append(rel)
    return sorted(set(out))


def declared_java_dependencies(repo_root: Path, build_files: list[str]) -> list[str]:
    """Dependency *groups* a build declares — ``maven/<groupId>`` — the
    Java arm of Decision 4's degradation input, matched at the group
    (``canonicalName`` in the helper).

    A pom's ``<dependencies>`` are parsed as XML — ``runtime``-scoped
    entries and ``pom``-typed imports left out, since nothing in source
    references them; ``${project.groupId}`` is the pom's own group, other
    properties are left unresolved and skipped. Gradle declares in code, which is not read: a version
    catalog (``gradle/libs.versions.toml``) is parsed as TOML, and a
    ``"group:artifact:version"`` literal in a build script is taken as
    text — an observation of what the script spells, not of what it
    resolves.
    """
    import re
    import tomllib
    import xml.etree.ElementTree as ET

    groups: set[str] = set()
    for rel in build_files:
        path = repo_root / rel
        name = path.name
        try:
            if name == "pom.xml":
                tree = ET.parse(path)
                ns = {"m": "http://maven.apache.org/POM/4.0.0"}
                own = tree.find("m:groupId", ns)
                if own is None:
                    own = tree.find("m:parent/m:groupId", ns)
                own_group = (own.text or "").strip() if own is not None else ""
                for dep in tree.iterfind(".//m:dependencies/m:dependency", ns):
                    scope = dep.find("m:scope", ns)
                    kind = dep.find("m:type", ns)
                    # A runtime-only dependency (a JDBC driver) and a BOM
                    # import are never referenced from source, so their
                    # absence from the index says nothing about the
                    # environment (spring-petclinic: 9 of 13 "missing").
                    if scope is not None and (scope.text or "").strip() == "runtime":
                        continue
                    if kind is not None and (kind.text or "").strip() == "pom":
                        continue
                    group = dep.find("m:groupId", ns)
                    text = (group.text or "").strip() if group is not None else ""
                    if text == "${project.groupId}":
                        text = own_group
                    if text and "${" not in text and text != own_group:
                        groups.add(f"maven/{text}")
            elif name == "libs.versions.toml":
                data = tomllib.loads(path.read_text())
                for entry in (data.get("libraries") or {}).values():
                    if isinstance(entry, dict):
                        module = entry.get("module") or ""
                        group = entry.get("group") or module.split(":")[0]
                        if group:
                            groups.add(f"maven/{group}")
                    elif isinstance(entry, str) and ":" in entry:
                        groups.add(f"maven/{entry.split(':')[0]}")
            elif name in _GRADLE_BUILD:
                for line in path.read_text().splitlines():
                    if "runtimeOnly" in line or "platform(" in line:
                        continue  # the same rule, as text
                    for match in re.finditer(r"""["']([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+):[^"'\s]+["']""", line):
                        groups.add(f"maven/{match.group(1)}")
        except (OSError, ValueError, ET.ParseError):
            continue
    return sorted(groups)


def extract_scip_java(
    repo_root: Path, files: list[str], sha: str = ""
) -> dict | None:
    """Index every Java build root and return one merged facts document.

    **Indexing Java executes the repo's build** (C-29's Java face,
    ADR-096): scip-java is a javac plugin, and the only way to hand it a
    classpath is to run the build that resolves one — Maven or the
    repo's own Gradle wrapper, inside the ingest container. Two passes
    (ADR-097): the build's *resolution* runs first with a network on a
    stage that holds no sources, then the build runs again with
    scip-java attached, offline, on the full stage — the pass that can
    reach the network never sees a ``.java``. What the resolve pass still
    concedes is C-66; the notice below is its surfacing and prints every
    time.
    """
    if not enabled() or not files:
        return None
    repo_root = Path(repo_root).resolve()
    merged: dict = {
        "definitions": [],
        "references": [],
        "external_refs": [],
        "packages": {},
        "degraded": [],
        "dependency_coverage": {"declared": 0, "resolved": 0, "missing": []},
    }
    grouped = java_units(repo_root, files)
    for directory, orphans in go_orphans(files, {r: f for r, (_, f) in grouped.items()}).items():
        merged["degraded"].append(
            {
                "path": directory,
                "stage": "scip-java",
                "message": (
                    f"{len(orphans)} Java file(s) under {directory!r} sit below no "
                    "pom.xml or Gradle build, so scip-java cannot compile them; "
                    "their call edges fall to lane A's fallback (syntactic "
                    "tier). Add a build file to give them semantics."
                ),
            }
        )
    if grouped:
        import sys

        print(
            "NOTE: java semantics: scip-java runs the repo's own build (Maven "
            "or its Gradle wrapper) inside the ingest container — dependency "
            "resolution in a networked pass that holds no sources, then the "
            "index offline (C-29, C-66, ADR-097)",
            file=sys.stderr,
        )
    for root, (tool, root_files) in grouped.items():
        try:
            facts = _index_java_unit(repo_root, root, tool, root_files, sha)
        except containment.ContainmentRefusal:
            raise  # P10: the guarantee outranks the per-unit degrade
        except UNIT_ERRORS as exc:
            merged["degraded"].append(
                _unit_failure(root, "scip-java", f"{tool} build", exc)
            )
            continue
        if facts is None:
            continue
        for key in ("definitions", "references", "external_refs", "degraded"):
            merged[key].extend(facts.get(key, []))
        for name, count in (facts.get("packages") or {}).items():
            merged["packages"][name] = merged["packages"].get(name, 0) + count
        coverage = facts.get("dependency_coverage") or {}
        merged["dependency_coverage"]["declared"] += coverage.get("declared", 0)
        merged["dependency_coverage"]["resolved"] += coverage.get("resolved", 0)
        merged["dependency_coverage"]["missing"].extend(coverage.get("missing", []))
    merged["dependency_coverage"]["missing"] = sorted(
        set(merged["dependency_coverage"]["missing"])
    )
    join_cross_unit(merged)
    return merged


#: The image's JDK homes by major (sandbox/Containerfile).
JAVA_HOMES = {17: "/usr/local/java-17", 21: "/usr/local/java-21", 25: "/usr/local/java-25"}


def java_home_for(repo_root: Path, build_files: list[str]) -> str:
    """The JDK the build runs on: derived from the build files, never
    authored (ADR-027). A build that asks for a source/release level
    above the default 21 — Gradle's ``JavaVersion.VERSION_25``,
    ``languageVersion.of(25)``, ``sourceCompatibility = 25``; Maven's
    ``<release>25``, ``<maven.compiler.release>25``, ``<java.version>25``
    — gets the image's JDK 25 (Severed-Chains: "invalid source release:
    25" on the default). A level at or below 21 keeps the default: a
    newer javac compiles an older source level, and a Gradle toolchain
    pin resolves through ``org.gradle.java.installations.paths``
    regardless. This is a text observation of what the build spells."""
    import re

    pattern = re.compile(
        r"(?:VERSION_|JavaLanguageVersion\.of\(|languageVersion\s*=\s*|"
        r"sourceCompatibility\s*=\s*|targetCompatibility\s*=\s*|release\s*=\s*|"
        r"<release>|<maven\.compiler\.release>|<maven\.compiler\.source>|<java\.version>|<javaVersion>)"
        r"\s*['\"]?(\d{1,2})"
    )
    wanted = 0
    for rel in build_files:
        try:
            text = (repo_root / rel).read_text(errors="replace")
        except OSError:
            continue
        for match in pattern.finditer(text):
            wanted = max(wanted, int(match.group(1)))
    for major in sorted(JAVA_HOMES):
        if major >= wanted and major >= 21:
            return JAVA_HOMES[major]
    return JAVA_HOMES[max(JAVA_HOMES)]


def gradle_user_properties() -> str:
    """The derived ``gradle.properties`` under GRADLE_USER_HOME: the
    image's JDKs for toolchain resolution, no auto-download (there is
    nothing to download from that the pin would trust), no daemon (one
    build per container)."""
    return (
        f"org.gradle.java.installations.paths={','.join(JAVA_INSTALLATIONS)}\n"
        "org.gradle.java.installations.auto-download=false\n"
        "org.gradle.daemon=false\n"
    )


_JAVA_INDEX_TIMEOUT = 1800


def _index_java_unit(
    repo_root: Path, root: str, tool: str, root_files: list[str], sha: str
) -> dict | None:
    """Stage and index one Maven reactor or Gradle build, in two passes
    (ADR-097).

    **Resolve pass** (``fetch-java``, network on): the build files and
    every other non-source file under the root (:func:`java_build_files`)
    — never a ``.java`` — staged alone, and the build's own resolution
    run over them: Maven's ``test-compile`` (it resolves the mojo's scope
    before finding nothing to compile), or the Gradle wrapper with a
    Hobbes init script that resolves every configuration. **Index pass**
    (``index-java``, ``--network none``): the full stage, the same build
    with scip-java attached and the tool's offline flag, so a build that
    still wants the network fails visibly instead of reaching for it. A
    failed resolve is recorded and the index pass runs anyway — the
    caches persist across ingests, so a warm one may carry it — and if
    the build then fails, the unit degrades to lane A with both records.

    Staged beside the sources in the index pass: every other unpruned
    file under the root. The wrappers lose their mode in the copy and
    get it back, because scip-java runs ``./gradlew``. The dependency
    tree needs no symlink: both tools keep a user-level repository, which
    the cache root supplies (``MAVEN_OPTS``, ``GRADLE_USER_HOME``).
    """
    build_files = java_build_files(repo_root, root)
    staged = sorted(set(root_files) | set(build_files))
    declared = declared_java_dependencies(repo_root, build_files)
    java_home = java_home_for(repo_root, build_files)
    env = (f"JAVA_HOME={java_home}", f"PATH={java_home}/bin:{containment.CONTAINER_PATH}")

    gradle_home = staging.cache_root() / "gradle"
    gradle_home.mkdir(parents=True, exist_ok=True)
    (gradle_home / "gradle.properties").write_text(gradle_user_properties())
    init_script = gradle_home / "hobbes-resolve.gradle"
    init_script.write_text(containment.GRADLE_RESOLVE_SCRIPT)

    # Resolve pass: no sources on this stage, by construction.
    resolve_stage = _stage_java(repo_root, root, build_files, sha)
    try:
        resolve_failure = _fetch(
            "fetch-java",
            containment.java_resolve_command(tool, str(init_script)),
            resolve_stage[1],
            timeout=_JAVA_INDEX_TIMEOUT,
            env=env,
        )
    finally:
        staging.remove_stage(resolve_stage[0])

    # Index pass: the full stage, offline.
    stage, unit_root = _stage_java(repo_root, root, staged, sha)
    try:
        facts = run_helper(
            {
                "stage": str(unit_root),
                "language": "java",
                "buildTool": tool,
                "projectName": repo_root.name,
                # Unused by the java argv — the moniker version is the
                # artifact's own (ADR-096) — carried for config uniformity.
                "projectVersion": "0",
                "output": str(stage.parent / f"{stage.name}.scip"),
                "declaredDeps": declared,
            },
            timeout=_JAVA_INDEX_TIMEOUT,
            env=env,
        )
    except UNIT_ERRORS as exc:
        if resolve_failure is not None:
            raise ScipError(
                f"{exc} (the resolve pass had failed first: {resolve_failure})"
            ) from exc
        raise
    finally:
        staging.remove_stage(stage)
    if resolve_failure is not None:
        facts.setdefault("degraded", []).append(
            {
                "path": root or ".",
                "stage": "scip-java",
                "message": (
                    f"dependency resolution failed ({resolve_failure}); the "
                    "index ran offline on the cache as it stood, so "
                    "third-party resolution may degrade (C-67)"
                ),
            }
        )
    return _rebase(facts, root)


def _stage_java(repo_root: Path, root: str, files: list[str], sha: str) -> tuple[Path, Path]:
    """Copy *files* into a fresh stage and return ``(stage, unit_root)``,
    the wrappers made executable again (the copy drops their mode)."""
    stage = staging.build_stage(repo_root, files, sha=sha)
    unit_root = stage / root if root else stage
    for wrapper in ("gradlew", "mvnw"):
        script = unit_root / wrapper
        if script.is_file():
            script.chmod(script.stat().st_mode | 0o111)
    return stage, unit_root


def _index_go_module(
    repo_root: Path,
    module_root: str,
    module_files: list[str],
    sha: str,
    grouped: dict[str, list[str]] | None = None,
) -> dict | None:
    """Stage and index one Go module.

    ``go.mod`` and ``go.sum`` are staged with the source: without them the
    loader has no module to root at and no dependency versions to resolve,
    and scip-go fails loudly rather than producing a thin index — which is
    the degradation being visible rather than silent (P6).

    Modules this one ``replace``s to in-repo paths are staged beside it
    (ADR-049): without their sources the loader cannot type the import
    at all and mis-attributes every reference into it — half of what
    made C-33. Only the consumer's own go.mod is read (Go's rule:
    replaces apply in the main module only), and the sibling's files
    come from *grouped*, the same discovery that staged this module's.
    """
    manifest = f"{module_root}/go.mod" if module_root else "go.mod"
    sums = f"{module_root}/go.sum" if module_root else "go.sum"
    staged = set(module_files) | {manifest}
    if (repo_root / sums).is_file():
        staged.add(sums)
    for sibling in go_replace_targets(repo_root, module_root):
        if sibling == module_root:
            continue
        staged.update((grouped or {}).get(sibling, []))
        for extra in ("go.mod", "go.sum"):
            candidate = f"{sibling}/{extra}" if sibling else extra
            if (repo_root / candidate).is_file():
                staged.add(candidate)

    stage = staging.build_stage(repo_root, sorted(staged), sha=sha)
    mod_root = stage / module_root if module_root else stage
    try:
        fetch_failure = _fetch("fetch-go", containment.go_fetch_command(), mod_root)
        facts = run_helper(
            {
                "stage": str(mod_root),
                "language": "go",
                "projectName": repo_root.name,
                # Pinned for the third time, under a third flag name
                # (ADR-037): scip-go's --module-version defaults to the git
                # revision exactly as scip-python's --project-version does.
                "projectVersion": "0",
                "output": str(stage.parent / f"{stage.name}.scip"),
                "declaredDeps": [],
            }
        )
    finally:
        staging.remove_stage(stage)
    if fetch_failure is not None:
        facts.setdefault("degraded", []).append(
            {
                "path": ".",
                "stage": "scip-go",
                "message": (
                    f"module download failed ({fetch_failure}); third-party "
                    "resolution degrades, in-repo edges survive (C-26)"
                ),
            }
        )
    return _rebase(facts, module_root)


def _index_ts_zone(
    repo_root: Path, zone: str, zone_files: list[str], sha: str
) -> dict | None:
    """Stage and index one TypeScript zone.

    Dependencies enter the stage as symlinks and only as symlinks
    (ADR-032/050): every ``node_modules`` on a zone file's walk-up path
    in the repo, and — when the repo has none — a lockfile-pinned tree
    provisioned into Hobbes's own cache. The repo is never written.
    """
    staged = sorted(set(zone_files) | set(_staged_ts_configs(repo_root, zone_files)))
    provision_failure: str | None = None
    links = zone_dependency_links(repo_root, zone_files)
    if not links:
        manifest_dir = _nearest_package_manifest(repo_root, zone)
        if manifest_dir is not None:
            tree, provision_failure = provision_node_modules(
                repo_root, manifest_dir
            )
            if tree is not None:
                rel = (
                    "node_modules"
                    if not manifest_dir
                    else f"{manifest_dir}/node_modules"
                )
                links[rel] = str(tree)

    configs = {}
    zone_config = f"{zone}/tsconfig.json" if zone else "tsconfig.json"
    if not (repo_root / zone_config).is_file():
        configs[zone_config] = _generated_tsconfig(zone_files, zone)

    package_json = repo_root / (f"{zone}/package.json" if zone else "package.json")
    declared = (
        declared_npm_dependencies(package_json) if package_json.is_file() else []
    )

    stage = staging.build_stage(repo_root, staged, sha=sha, configs=configs, links=links)
    try:
        facts = run_helper(
            {
                "stage": str(stage / zone if zone else stage),
                "language": "typescript",
                "projectName": repo_root.name,
                "projectVersion": "0",
                "output": str(stage.parent / f"{stage.name}.scip"),
                "declaredDeps": declared,
            },
            # The trees the links point at, mounted ro where the links
            # expect them (ADR-092): the C-22 trust becomes a mount flag.
            ro=sorted(links.values()),
        )
    finally:
        staging.remove_stage(stage)
    # Rebase first: the helper's own degradation records name zone-
    # relative paths (the duplicate-symbol record, ADR-091 D7); the one
    # appended below is already repo-relative.
    facts = _rebase(facts, zone)
    if provision_failure is not None:
        # The zone indexed without its dependencies and this says why —
        # C-23's surfacing, at the moment the gap was created.
        facts.setdefault("degraded", []).append(
            {
                "path": zone or ".",
                "stage": "scip-typescript",
                "message": (
                    "dependencies not provisioned for this zone "
                    f"({provision_failure}); third-party resolution "
                    "degrades to lane A (C-23)"
                ),
            }
        )
    return facts


def _rebase(facts: dict, zone: str) -> dict:
    """Re-root a zone's file paths at the repo.

    A zone is indexed with ``--cwd`` at *its own* directory, so SCIP
    reports ``src/App.tsx`` where lane A says ``web/src/App.tsx``. The two
    providers must speak the same paths or the range join silently matches
    nothing — which is not an error, just a graph with no semantic TS
    edges and a coverage denominator full of holes. Python never hit this
    because its ``--cwd`` is the stage root, where the two already agree.
    """
    if not zone:
        return facts
    def at(path: str) -> str:
        return f"{zone}/{path}" if path else path

    for ref in facts.get("references", []):
        ref["file"] = at(ref["file"])
        ref["def_file"] = at(ref["def_file"])
    for definition in facts.get("definitions", []):
        definition["file"] = at(definition["file"])
    for ref in facts.get("external_refs", []):
        ref["file"] = at(ref["file"])
    for record in facts.get("degraded", []):
        # A record scoped to a directory inside the zone (ADR-091, D7);
        # a whole-index record stays at the repo root.
        if record.get("path") not in (None, "", "."):
            record["path"] = at(record["path"])
    return facts


def extract_scip(
    repo_root: Path,
    files: list[str],
    roots: list[str],
    project_name: str,
    sha: str,
    declared_deps: list[str] | None = None,
) -> dict | None:
    """Stage *files*, index them, and return joined facts — or None.

    Returns None when lane B is disabled. Every write lands in the staging
    tree (ADR-027): the repo is read and never touched.
    """
    if not enabled() or not files:
        return None
    config: dict = {"extraPaths": roots}
    venv = find_venv(repo_root)
    environment = None
    refused: str | None = None
    ro: list[str] = []
    if venv is not None:
        # Absolute, so third-party resolution survives staging — without
        # it every dependency edge silently vanishes (ADR-027 Decision 4).
        # Discovered, not assumed at the root: pointing at a venv that is
        # not there resolved 0 of this repo's 5 declared packages (C-27).
        config["venvPath"], config["venv"] = venv
        try:
            environment = venv_environment(*venv)
        except containment.ContainmentRefusal as exc:
            environment = None
            refused = str(exc)
    stage = staging.build_stage(repo_root, files, config=config, sha=sha)
    env_path = stage.parent / f"{stage.name}.env.json"
    helper_config = {
        "stage": str(stage),
        "language": "python",
        "projectName": project_name,
        # Pinned, never defaulted: the default is the git revision,
        # which would change every moniker on every commit.
        "projectVersion": "0",
        "output": str(stage.parent / f"{stage.name}.scip"),
        "declaredDeps": declared_deps or [],
    }
    if environment is not None:
        # C-27's second mechanism: venvPath gives Pyright *resolution*,
        # this gives scip-python *attribution*. Both land in the cache,
        # never the repo.
        env_path.write_text(json.dumps(environment))
        helper_config["environment"] = str(env_path)
    if venv is not None:
        venv_dir = Path(venv[0]) / venv[1]
        ro = [str(venv_dir), *containment.interpreter_mounts(venv_dir / "bin" / "python")]
    try:
        facts = run_helper(helper_config, ro=ro)
    finally:
        env_path.unlink(missing_ok=True)
        staging.remove_stage(stage)
    if refused is not None:
        facts.setdefault("degraded", []).append(
            {
                "path": ".",
                "stage": "scip-python",
                "message": (
                    f"environment listing not taken: {refused} — third-party "
                    "references attribute to the local project (C-27)"
                ),
            }
        )
    return facts
