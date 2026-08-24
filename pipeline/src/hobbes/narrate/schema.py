"""Narrative artifact schema: validation and filing (ADR-019).

Artifacts are plain dicts, like the extractor's (ADR-006), written
under ``.hobbes/derived/docs/``. The writers here are the only path to
disk: a claim whose pins don't validate never becomes an artifact. A
**claim** is ``{"text": …, "pins": [{"path": …, "line": …}, …]}`` with
at least one pin citing a 1-based line in an existing repo file.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import yaml

from hobbes.narrate.stale import stamp_sources

DOCS_DIR = ".hobbes/derived/docs"
MODULE_DOCS_DIR = f"{DOCS_DIR}/modules"
TEST_DOCS_DIR = f"{DOCS_DIR}/tests"
INVARIANTS_FILE = f"{DOCS_DIR}/invariants.inferred.yaml"
SCHEMA_VERSION = 1

#: Artifact filenames come from graph node ids; anything else is refused.
#: TS/JS module ids are repo-relative paths (ADR-021), so ``/`` is legal
#: and artifacts nest under docs/ mirroring the repo tree — traversal is
#: blocked by the segment check in :func:`_safe_id`.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._:/-]*$")


class ValidationError(ValueError):
    """Cartographer output violated the artifact contract.

    Carries every problem found so one retry can fix them all
    (ADR-020's feedback loop).
    """

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("; ".join(problems) or "invalid payload")


def module_doc_path(repo_root: Path, module_id: str) -> Path:
    return Path(repo_root) / MODULE_DOCS_DIR / f"{_safe_id(module_id)}.json"


def behavior_index_path(repo_root: Path, module_id: str) -> Path:
    return Path(repo_root) / TEST_DOCS_DIR / f"{_safe_id(module_id)}.json"


def invariants_path(repo_root: Path) -> Path:
    return Path(repo_root) / INVARIANTS_FILE


def _safe_id(module_id: str) -> str:
    if not _SAFE_ID.match(module_id) or any(
        part in (".", "..", "") for part in module_id.split("/")
    ):
        raise ValueError(f"unsafe artifact id: {module_id!r}")
    return module_id


# --- validation ------------------------------------------------------------


class _PinChecker:
    """Validates pins against the working tree, caching file line counts."""

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root)
        self._line_counts: dict[str, int | None] = {}

    def _line_count(self, path: str) -> int | None:
        if path not in self._line_counts:
            file = self.repo_root / path
            self._line_counts[path] = (
                len(file.read_text(errors="replace").splitlines())
                if file.is_file()
                else None
            )
        return self._line_counts[path]

    def check(self, pin: object, where: str, problems: list[str]) -> None:
        if not isinstance(pin, dict):
            problems.append(f"{where}: pin must be an object, got {pin!r}")
            return
        path, line = pin.get("path"), pin.get("line")
        if not isinstance(path, str) or not path:
            problems.append(f"{where}: pin needs a string 'path'")
            return
        pure = Path(path)
        if pure.is_absolute() or ".." in pure.parts or "\\" in path:
            problems.append(f"{where}: pin path must be repo-relative: {path!r}")
            return
        count = self._line_count(path)
        if count is None:
            problems.append(f"{where}: pinned file does not exist: {path}")
            return
        if not isinstance(line, int) or isinstance(line, bool) or line < 1:
            problems.append(f"{where}: pin 'line' must be a positive integer")
        elif line > count:
            problems.append(
                f"{where}: pin {path}:{line} is past the end of the file "
                f"({count} lines)"
            )

    def check_claim(
        self, claim: object, where: str, problems: list[str], one_line: bool = False
    ) -> None:
        if not isinstance(claim, dict):
            problems.append(f"{where}: claim must be an object, got {claim!r}")
            return
        text = claim.get("text")
        if not isinstance(text, str) or not text.strip():
            problems.append(f"{where}: claim needs non-empty 'text'")
        elif one_line and "\n" in text.strip():
            problems.append(f"{where}: text must be a single line")
        pins = claim.get("pins")
        if not isinstance(pins, list) or not pins:
            problems.append(f"{where}: claim needs at least one pin (P3)")
            return
        for i, pin in enumerate(pins):
            self.check(pin, f"{where}.pins[{i}]", problems)


def validate_module_payload(repo_root: Path, payload: object) -> list[str]:
    """Problems with a cartographer module-doc payload; empty means valid.

    Expected shape: ``{"purpose": claim, "responsibilities": [claim, …],
    "gotchas": [claim, …]}`` (gotchas may be empty).
    """
    if not isinstance(payload, dict):
        return [f"payload must be an object, got {type(payload).__name__}"]
    problems: list[str] = []
    checker = _PinChecker(repo_root)
    checker.check_claim(payload.get("purpose"), "purpose", problems)
    for field, may_be_empty in (("responsibilities", False), ("gotchas", True)):
        claims = payload.get(field)
        if not isinstance(claims, list) or (not claims and not may_be_empty):
            problems.append(f"{field}: must be a non-empty list of claims")
            continue
        for i, claim in enumerate(claims):
            checker.check_claim(claim, f"{field}[{i}]", problems)
    return problems


def validate_test_payload(
    repo_root: Path, payload: object, expected_test_ids: list[str]
) -> list[str]:
    """Problems with a test-doc payload; empty means valid.

    Expected shape: ``{"behaviors": [{"test": id, "text": one line,
    "pins": […]}, …]}`` covering each expected test id exactly once.
    """
    if not isinstance(payload, dict):
        return [f"payload must be an object, got {type(payload).__name__}"]
    behaviors = payload.get("behaviors")
    if not isinstance(behaviors, list):
        return ["behaviors: must be a list"]
    problems: list[str] = []
    checker = _PinChecker(repo_root)
    seen: list[str] = []
    for i, entry in enumerate(behaviors):
        where = f"behaviors[{i}]"
        if not isinstance(entry, dict):
            problems.append(f"{where}: must be an object")
            continue
        seen.append(entry.get("test"))
        checker.check_claim(entry, where, problems, one_line=True)
    expected = set(expected_test_ids)
    for missing in sorted(expected - set(seen)):
        problems.append(f"behaviors: missing test {missing}")
    for extra in sorted(set(seen) - expected - {None}):
        problems.append(f"behaviors: unknown test {extra}")
    if len(seen) != len(set(seen)):
        problems.append("behaviors: each test must appear exactly once")
    return problems


def validate_invariants_payload(repo_root: Path, payload: object) -> list[str]:
    """Problems with an inferred-invariants payload; empty means valid.

    Expected shape: ``{"invariants": [{"statement": …, "scope": …,
    "evidence": [pins], "guarded_by": [test ids]?}, …]}``. Ids and
    ``status: inferred`` are assigned at write time, not by the model.
    """
    if not isinstance(payload, dict):
        return [f"payload must be an object, got {type(payload).__name__}"]
    invariants = payload.get("invariants")
    if not isinstance(invariants, list) or not invariants:
        return ["invariants: must be a non-empty list"]
    problems: list[str] = []
    checker = _PinChecker(repo_root)
    for i, record in enumerate(invariants):
        where = f"invariants[{i}]"
        if not isinstance(record, dict):
            problems.append(f"{where}: must be an object")
            continue
        for field in ("statement", "scope"):
            value = record.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{where}: needs non-empty '{field}'")
        evidence = record.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            problems.append(f"{where}: needs at least one evidence pin (P3)")
        else:
            for j, pin in enumerate(evidence):
                checker.check(pin, f"{where}.evidence[{j}]", problems)
        guarded = record.get("guarded_by", [])
        if not (
            isinstance(guarded, list) and all(isinstance(g, str) for g in guarded)
        ):
            problems.append(f"{where}: 'guarded_by' must be a list of test ids")
    return problems


# --- filing ----------------------------------------------------------------


def _pin_paths(claims: list[dict]) -> list[str]:
    return [pin["path"] for claim in claims for pin in claim["pins"]]


def _write_atomic(path: Path, text: str) -> Path:
    """Write via tmp+rename so a concurrent reader (the proxy's
    ``get_module_doc``) never sees a torn artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise
    return path


def _write_json(path: Path, doc: dict) -> Path:
    return _write_atomic(path, json.dumps(doc, indent=2, sort_keys=True) + "\n")


def write_module_doc(
    repo_root: Path, module_id: str, module_path: str, payload: dict, stamp: dict
) -> Path:
    """Validate *payload* and file it as ``modules/<id>.json``.

    Raises :class:`ValidationError` rather than writing anything wrong.
    """
    problems = validate_module_payload(repo_root, payload)
    if problems:
        raise ValidationError(problems)
    claims = [payload["purpose"], *payload["responsibilities"], *payload["gotchas"]]
    doc = {
        "schema_version": SCHEMA_VERSION,
        "kind": "module-doc",
        "id": module_id,
        "path": module_path,
        "sha": stamp["sha"],
        "dirty": stamp["dirty"],
        "sources": stamp_sources(repo_root, [module_path, *_pin_paths(claims)]),
        "purpose": payload["purpose"],
        "responsibilities": payload["responsibilities"],
        "gotchas": payload["gotchas"],
    }
    return _write_json(module_doc_path(repo_root, module_id), doc)


def write_test_doc(
    repo_root: Path,
    module_id: str,
    file_path: str,
    payload: dict,
    expected_test_ids: list[str],
    stamp: dict,
) -> Path:
    """Validate *payload* and file it as ``tests/<id>.json``."""
    problems = validate_test_payload(repo_root, payload, expected_test_ids)
    if problems:
        raise ValidationError(problems)
    behaviors = sorted(payload["behaviors"], key=lambda b: b["test"])
    doc = {
        "schema_version": SCHEMA_VERSION,
        "kind": "test-doc",
        "id": module_id,
        "path": file_path,
        "sha": stamp["sha"],
        "dirty": stamp["dirty"],
        "sources": stamp_sources(repo_root, [file_path, *_pin_paths(behaviors)]),
        "behaviors": behaviors,
    }
    return _write_json(behavior_index_path(repo_root, module_id), doc)


def write_inferred_invariants(repo_root: Path, payload: dict, stamp: dict) -> Path:
    """Validate *payload* and file it as ``invariants.inferred.yaml``.

    Records get sequential ``INF-n`` ids and ``status: inferred`` here —
    never from the model. Confirmation is a human moving a record into
    the versioned ``.hobbes/invariants/`` (ADR-019); this writer only
    ever touches ``derived/``.
    """
    problems = validate_invariants_payload(repo_root, payload)
    if problems:
        raise ValidationError(problems)
    records = [
        {
            "id": f"INF-{i}",
            "statement": record["statement"].strip(),
            "scope": record["scope"].strip(),
            "status": "inferred",
            "evidence": record["evidence"],
            "guarded_by": record.get("guarded_by", []),
        }
        for i, record in enumerate(payload["invariants"], start=1)
    ]
    doc = {
        "schema_version": SCHEMA_VERSION,
        "kind": "inferred-invariants",
        "sha": stamp["sha"],
        "dirty": stamp["dirty"],
        "sources": stamp_sources(
            repo_root, [pin["path"] for r in records for pin in r["evidence"]]
        ),
        "invariants": records,
    }
    text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
    return _write_atomic(invariants_path(repo_root), text)


def load_artifacts(repo_root: Path) -> list[dict]:
    """Every narrative artifact on disk, sorted by (kind, id).

    Unreadable files surface as ``{"kind": "unreadable", …}`` entries
    rather than crashing ``docs status`` — a broken artifact is a fact
    worth listing, not a fatal error.
    """
    repo_root = Path(repo_root)
    artifacts: list[dict] = []
    for directory in (MODULE_DOCS_DIR, TEST_DOCS_DIR):
        for file in sorted((repo_root / directory).rglob("*.json")):
            try:
                artifacts.append(json.loads(file.read_text()))
            except (OSError, json.JSONDecodeError) as exc:
                artifacts.append(
                    {"kind": "unreadable", "id": file.name, "error": str(exc)}
                )
    inv = invariants_path(repo_root)
    if inv.is_file():
        try:
            artifacts.append(yaml.safe_load(inv.read_text()))
        except (OSError, yaml.YAMLError) as exc:
            artifacts.append({"kind": "unreadable", "id": inv.name, "error": str(exc)})
    return sorted(
        artifacts, key=lambda a: (a.get("kind", ""), a.get("id", ""))
    )
