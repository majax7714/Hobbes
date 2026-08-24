"""Narrative pass (M5, architecture §3.2): cartographer-generated module
docs, test-behavior indexes, and inferred invariants, every claim pinned
``file:line @ SHA``.

This module is the orchestrator behind ``hobbes narrate`` (ADR-020): it
plans work units from the derived skeleton, decides which are due
(missing or stale, ADR-019), drives the runner one unit at a time with
one corrective retry, and files only validated artifacts. ``schema``
defines the artifacts, ``stale`` the badge computation, ``prompts`` the
cartographer prompts, ``runner`` the headless Claude Code call.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable, Iterable

import yaml

from hobbes.extract.emit import repo_stamp
from hobbes.narrate import prompts, schema
from hobbes.narrate.runner import RunnerError, parse_json_response
from hobbes.narrate.stale import changed_sources

#: The repo-wide invariants unit has no subject module; this is its id.
INVARIANTS_UNIT_ID = "invariants"


class NarrateError(RuntimeError):
    """The pass could not start (derived skeleton missing or unreadable)."""


@dataclass(frozen=True)
class Unit:
    """One cartographer call: a module doc, a test file's behavior
    index, or the repo-wide invariants inference."""

    kind: str  # "module" | "tests" | "invariants"
    id: str
    path: str | None = None
    tests: tuple = ()  # for kind == "tests": that file's tests.json rows


def _load_derived(repo_root: Path) -> tuple[dict, dict, dict]:
    derived = Path(repo_root) / ".hobbes" / "derived"
    loaded = []
    for name in ("graph.json", "tests.json", "interfaces.json"):
        file = derived / name
        if not file.is_file():
            raise NarrateError(f"{file} not found — run `hobbes ingest` first")
        try:
            loaded.append(json.loads(file.read_text()))
        except json.JSONDecodeError as exc:
            raise NarrateError(f"{file} is not valid JSON ({exc})") from exc
    return tuple(loaded)


def _fallback_id(path: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._:/-]", "_", path)
    return sanitized if schema._SAFE_ID.match(sanitized) else f"f_{sanitized}"


def plan_units(graph: dict, tests: dict, *, invariants: bool = True) -> list[Unit]:
    """Every potential work unit, in execution order.

    Module docs first, then behavior indexes, invariants last — the
    invariants prompt reads the freshly written module purposes. Any
    source-backed module *or package* node gets a doc (a package's
    ``__init__.py`` can carry real code — hobbes.narrate's orchestrator
    does); a node that *is* a test file gets a behavior index instead.
    """
    by_file: dict[str, list[dict]] = {}
    for test in tests["tests"]:
        by_file.setdefault(test["file"], []).append(test)
    modules = [
        n
        for n in graph["nodes"]
        if n.get("kind") in ("module", "package") and n.get("path")
    ]
    path_to_id = {n["path"]: n["id"] for n in modules}
    units = [
        Unit("module", node["id"], node["path"])
        for node in sorted(modules, key=lambda n: n["id"])
        if node["path"] not in by_file
    ]
    units += [
        Unit(
            "tests",
            path_to_id.get(file, _fallback_id(file)),
            file,
            tuple(sorted(file_tests, key=lambda t: t["line"])),
        )
        for file, file_tests in sorted(by_file.items())
    ]
    if invariants:
        units.append(Unit("invariants", INVARIANTS_UNIT_ID))
    return units


def substantive_units(repo_root: Path, units: Iterable[Unit]) -> list[Unit]:
    """Drop units whose subject file has nothing to pin.

    An empty ``__init__.py`` can't yield a valid doc — every claim
    needs a pin — so planning it out beats burning two failed calls.
    """
    kept = []
    for unit in units:
        if unit.path is not None:
            try:
                text = (Path(repo_root) / unit.path).read_text(errors="replace")
            except OSError:
                continue
            if not any(line.strip() for line in text.splitlines()):
                continue
        kept.append(unit)
    return kept


def select_units(
    units: Iterable[Unit], only: Iterable[str] = (), exclude: Iterable[str] = ()
) -> list[Unit]:
    """Filter by fnmatch pattern against unit id or path; exclude wins."""

    def matches(unit: Unit, patterns: Iterable[str]) -> bool:
        return any(
            fnmatch(unit.id, p) or (unit.path and fnmatch(unit.path, p))
            for p in patterns
        )

    only, exclude = list(only), list(exclude)
    return [
        u
        for u in units
        if not matches(u, exclude) and (not only or matches(u, only))
    ]


def _artifact_path(repo_root: Path, unit: Unit) -> Path:
    if unit.kind == "module":
        return schema.module_doc_path(repo_root, unit.id)
    if unit.kind == "tests":
        return schema.behavior_index_path(repo_root, unit.id)
    return schema.invariants_path(repo_root)


def _load_artifact(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        if path.suffix == ".yaml":
            loaded = yaml.safe_load(path.read_text())
        else:
            loaded = json.loads(path.read_text())
        return loaded if isinstance(loaded, dict) else None
    except (OSError, json.JSONDecodeError, yaml.YAMLError):
        return None


def unit_status(repo_root: Path, unit: Unit) -> tuple[bool, str]:
    """(due, reason) for one unit against what's on disk (ADR-019)."""
    artifact = _load_artifact(_artifact_path(repo_root, unit))
    if artifact is None:
        return True, "missing"
    if artifact.get("schema_version") != schema.SCHEMA_VERSION:
        return True, "artifact schema changed"
    changed = changed_sources(repo_root, artifact.get("sources", []))
    if changed:
        listed = ", ".join(changed[:3]) + ("…" if len(changed) > 3 else "")
        return True, f"stale: {listed}"
    return False, "fresh"


def plan_status(
    repo_root: Path,
    *,
    only: Iterable[str] = (),
    exclude: Iterable[str] = (),
    invariants: bool = True,
    force_all: bool = False,
) -> list[tuple[Unit, bool, str]]:
    """The dry-run view: every selected unit with its due/fresh verdict."""
    graph, tests, _ = _load_derived(repo_root)
    units = select_units(
        substantive_units(repo_root, plan_units(graph, tests, invariants=invariants)),
        only,
        exclude,
    )
    return [
        (unit, *((True, "forced") if force_all else unit_status(repo_root, unit)))
        for unit in units
    ]


def _module_purposes(repo_root: Path) -> list[tuple[str, str]]:
    return [
        (a["id"], a["purpose"]["text"])
        for a in schema.load_artifacts(repo_root)
        if a.get("kind") == "module-doc"
    ]


def _generate(
    repo_root: Path,
    unit: Unit,
    runner: Callable[[str], str],
    graph: dict,
    tests: dict,
    interfaces: dict,
    stamp: dict,
) -> Path:
    """One unit: prompt → runner → parse → validate → write.

    A validation or JSON failure gets one corrective retry carrying the
    problem list (ADR-020); a runner failure gets one plain retry.
    Raises the last error when both attempts fail.
    """
    if unit.kind == "module":
        prompt = prompts.module_doc_prompt(repo_root, unit, graph, tests, interfaces)

        def write(payload: dict) -> Path:
            return schema.write_module_doc(
                repo_root, unit.id, unit.path, payload, stamp
            )

    elif unit.kind == "tests":
        prompt = prompts.test_doc_prompt(repo_root, unit)
        expected = [t["id"] for t in unit.tests]

        def write(payload: dict) -> Path:
            return schema.write_test_doc(
                repo_root, unit.id, unit.path, payload, expected, stamp
            )

    else:
        prompt = prompts.invariants_prompt(
            repo_root, graph, tests, interfaces, _module_purposes(repo_root)
        )

        def write(payload: dict) -> Path:
            return schema.write_inferred_invariants(repo_root, payload, stamp)

    attempt_prompt = prompt
    last_error: Exception = RunnerError("runner was never called")
    for _ in range(2):
        try:
            return write(parse_json_response(runner(attempt_prompt)))
        except (ValueError, schema.ValidationError) as exc:
            last_error = exc
            problems = getattr(exc, "problems", None) or [str(exc)]
            attempt_prompt = (
                f"{prompt}\n\nYour previous response failed validation:\n"
                + "\n".join(f"- {p}" for p in problems)
                + "\nReturn the corrected JSON object only."
            )
        except RunnerError as exc:
            last_error = exc
    raise last_error


def run_pass(
    repo_root: Path,
    runner: Callable[[str], str],
    *,
    only: Iterable[str] = (),
    exclude: Iterable[str] = (),
    invariants: bool = True,
    force_all: bool = False,
    out: Callable[[str], None] = print,
) -> dict:
    """Run the narrative pass; returns
    ``{"generated": [...], "skipped": [...], "failed": {id: problems}}``.

    Failures don't stop the run — every due unit gets its two attempts,
    and the caller decides what a non-empty ``failed`` means.
    """
    repo_root = Path(repo_root)
    graph, tests, interfaces = _load_derived(repo_root)
    units = select_units(
        substantive_units(repo_root, plan_units(graph, tests, invariants=invariants)),
        only,
        exclude,
    )
    stamp = repo_stamp(repo_root)
    summary: dict = {"generated": [], "skipped": [], "failed": {}}
    for unit in units:
        due, reason = (True, "forced") if force_all else unit_status(repo_root, unit)
        if not due:
            summary["skipped"].append(unit.id)
            out(f"  skip {unit.id} (fresh)")
            continue
        try:
            path = _generate(repo_root, unit, runner, graph, tests, interfaces, stamp)
        except (RunnerError, ValueError, schema.ValidationError) as exc:
            problems = getattr(exc, "problems", None) or [str(exc)]
            summary["failed"][unit.id] = problems
            more = f" (+{len(problems) - 1} more)" if len(problems) > 1 else ""
            out(f"  FAIL {unit.id}: {problems[0]}{more}")
            continue
        summary["generated"].append(unit.id)
        out(f"  ok   {unit.id} ({reason}) → {path.relative_to(repo_root)}")
    out(
        f"narrate: {len(summary['generated'])} generated, "
        f"{len(summary['skipped'])} fresh, {len(summary['failed'])} failed"
    )
    return summary


def artifact_status(repo_root: Path) -> list[dict]:
    """Stale-badge rows for every narrative artifact on disk (§3.3)."""
    rows = []
    for artifact in schema.load_artifacts(repo_root):
        if artifact.get("kind") == "unreadable":
            rows.append(
                {
                    "kind": "unreadable",
                    "id": artifact.get("id", "?"),
                    "status": "broken",
                    "changed": [],
                    "error": artifact.get("error", ""),
                }
            )
            continue
        changed = changed_sources(repo_root, artifact.get("sources", []))
        rows.append(
            {
                "kind": artifact.get("kind", "?"),
                "id": artifact.get("id", INVARIANTS_UNIT_ID),
                "sha": artifact.get("sha", ""),
                "status": "stale" if changed else "fresh",
                "changed": changed,
            }
        )
    return rows
