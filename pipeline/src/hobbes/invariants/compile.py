"""Compile invariant records into CI configs (ADR-024).

One emitter per target. Emitting a config is text generation, so none of
this needs import-linter, dependency-cruiser, semgrep, or conftest
installed — the tools run in CI, against the files written here.

Output lands in ``.hobbes/derived/compiled/``: derived, gitignored, and
regenerated per run, exactly like ``graph.json``. A manifest records
which invariant produced which file and the command that runs it, so the
CI step is copy-pasteable rather than folklore.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from hobbes.invariants.schema import COMPILED_DIR, Invariant, scope_matches

#: Filename per target, plus the command CI runs against it.
OUTPUTS = {
    "import-linter": ("importlinter.ini", "lint-imports --config {path}"),
    "dep-cruiser": ("dependency-cruiser.json", "depcruise --config {path} src"),
    "semgrep": ("semgrep.yml", "semgrep --config {path} --error"),
    "rego": ("terraform.rego", "conftest test --policy {path} plan.json"),
}


def compile_all(repo_root: Path, invariants: list[Invariant], graph: dict) -> dict:
    """Compile every confirmed, non-soft record; write and return a manifest.

    *graph* supplies the module ids a rule's wildcards expand over —
    ``importers: ["*"]`` means everything in the record's scope, which
    only the graph knows.
    """
    repo_root = Path(repo_root)
    out_dir = repo_root / COMPILED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    by_target: dict[str, list[Invariant]] = {}
    skipped: list[dict] = []
    for inv in invariants:
        if not inv.confirmed:
            skipped.append({"id": inv.id, "why": f"status is {inv.status}"})
        elif inv.check == "soft":
            skipped.append({"id": inv.id, "why": "check: soft — a reviewer session judges it"})
        elif inv.check == "graph":
            skipped.append(
                {"id": inv.id, "why": "check: graph — the unified checker judges it in-process"}
            )
        else:
            by_target.setdefault(inv.target, []).append(inv)

    emitters = {
        "import-linter": _emit_import_linter,
        "dep-cruiser": _emit_dep_cruiser,
        "semgrep": _emit_semgrep,
        "rego": _emit_rego,
    }

    written: list[dict] = []
    for target, records in sorted(by_target.items()):
        filename, command = OUTPUTS[target]
        path = out_dir / filename
        path.write_text(emitters[target](records, graph))
        written.append(
            {
                "target": target,
                "path": f"{COMPILED_DIR}/{filename}",
                "invariants": [r.id for r in records],
                "run": command.format(path=f"{COMPILED_DIR}/{filename}"),
            }
        )

    # A target with no records must not leave last run's file behind
    # claiming to be current.
    for target, (filename, _) in OUTPUTS.items():
        if target not in by_target:
            (out_dir / filename).unlink(missing_ok=True)

    manifest = {
        "schema_version": 1,
        "sha": graph.get("sha", ""),
        "dirty": graph.get("dirty", False),
        "outputs": written,
        "skipped": sorted(skipped, key=lambda s: s["id"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


# --- helpers ----------------------------------------------------------------


def _external_name(node_id: str) -> str:
    """``ext:tree_sitter`` is the graph's name for the package tree_sitter."""
    return node_id.split(":", 1)[1] if node_id.startswith("ext:") else node_id


def _scoped_modules(invariant: Invariant, graph: dict) -> list[str]:
    """Internal module ids inside the record's scope, sorted."""
    return sorted(
        node["id"]
        for node in graph.get("nodes", [])
        if node.get("kind") in ("module", "package")
        and scope_matches(invariant.scope, node.get("path"))
    )


def _root_packages(module_ids: list[str]) -> list[str]:
    """Top-level Python packages among dotted module ids."""
    roots = {mid.split(".", 1)[0] for mid in module_ids if "/" not in mid}
    return sorted(r for r in roots if ":" not in r)


def _summary(invariant: Invariant, limit: int = 90) -> str:
    """The statement on one line, for a config comment."""
    text = " ".join(invariant.statement.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# --- emitters ---------------------------------------------------------------


def _emit_import_linter(records: list[Invariant], graph: dict) -> str:
    """import-linter INI: one `forbidden` contract per record."""
    all_roots: list[str] = []
    contracts: list[str] = []

    for inv in records:
        modules = _scoped_modules(inv, graph)
        roots = _root_packages(modules)
        all_roots.extend(roots)

        rule = inv.rule
        forbidden = [_external_name(m) for m in rule.get("imported") or []]
        importers = rule.get("importers") or []
        # `*` becomes the scope's root packages; explicit ids pass through.
        sources = roots if "*" in importers else [
            _external_name(i).rstrip(".*").rstrip("/*") for i in importers
        ]

        # import-linter has no "except" on a forbidden contract; the
        # exemptions are expressed as ignored edges.
        ignored = [
            f"{_external_name(allowed)} -> {imported}"
            for allowed in (rule.get("except") or [])
            for imported in forbidden
        ]

        block = [
            f"[importlinter:contract:{inv.id}]",
            f"name = {inv.id}: {_summary(inv)}",
            "type = forbidden",
            "source_modules =",
            *(f"    {s}" for s in sources),
            "forbidden_modules =",
            *(f"    {f}" for f in forbidden),
        ]
        if ignored:
            # `except` means "this importer may import any of the forbidden",
            # so the pairs are a cross-product and most never occur as real
            # imports. import-linter treats an unmatched ignore as an ERROR
            # by default, which failed a clean repo the first time the
            # generated config was actually executed (V2.M6) — the exact
            # class of bug the shape-only tests could not see.
            block += [
                "ignore_imports =",
                *(f"    {i}" for i in ignored),
                "unmatched_ignore_imports_alerting = warn",
            ]
        contracts.append("\n".join(block))

    header = [
        "; Generated by `hobbes invariants compile` — do not edit.",
        "; Source of truth: .hobbes/invariants/*.yaml (ADR-024).",
        "",
        "[importlinter]",
        "root_packages =",
        *(f"    {r}" for r in sorted(set(all_roots))),
        "include_external_packages = True",
    ]
    return "\n".join(header) + "\n\n" + "\n\n".join(contracts) + "\n"


def _path_regex(node_id: str) -> str:
    """A dependency-cruiser path regex for a TS/JS module id.

    Ids are repo-relative paths without an extension (ADR-021), so the
    regex anchors the path and leaves the extension open.
    """
    return "^" + re.escape(node_id) + r"($|\.[cm]?[jt]sx?$)"


def _emit_dep_cruiser(records: list[Invariant], graph: dict) -> str:
    """dependency-cruiser config: one `forbidden` rule per record."""
    rules = []
    for inv in records:
        rule = inv.rule
        importers = rule.get("importers") or []
        exempt = rule.get("except") or []

        from_spec: dict = {}
        if "*" in importers:
            scope = inv.scope.rstrip("/")
            if scope not in (".", ""):
                from_spec["path"] = "^" + re.escape(scope) + "/"
        else:
            from_spec["path"] = "|".join(_path_regex(i) for i in importers)
        if exempt:
            from_spec["pathNot"] = "|".join(_path_regex(e) for e in exempt)

        to_spec = {
            "path": "|".join(
                _path_regex(t) for t in rule.get("imported") or [] if not t.startswith("ext:")
            ),
            "dependencyTypes": ["local"],
        }
        externals = [_external_name(t) for t in rule.get("imported") or [] if t.startswith("ext:")]
        if externals:
            # An external is a package name, not a path.
            to_spec = {"dependencyTypes": ["npm", "npm-dev", "npm-peer"]}
            to_spec["path"] = "|".join("^" + re.escape(e) for e in externals)
        elif not to_spec["path"]:
            to_spec.pop("path")

        rules.append(
            {
                "name": inv.id,
                "comment": _summary(inv),
                "severity": "error",
                "from": from_spec,
                "to": to_spec,
            }
        )

    config = {
        "$comment": "Generated by `hobbes invariants compile` — do not edit. "
        "Source of truth: .hobbes/invariants/*.yaml (ADR-024).",
        "forbidden": rules,
        "options": {"doNotFollow": {"path": "node_modules"}},
    }
    return json.dumps(config, indent=2, sort_keys=False) + "\n"


def _emit_semgrep(records: list[Invariant], graph: dict) -> str:
    """semgrep rules: a match is the violation."""
    rules = []
    for inv in records:
        rule = inv.rule
        entry: dict = {
            "id": inv.id,
            "message": _summary(inv, limit=200),
            "severity": "ERROR",
            "languages": list(rule.get("languages") or []),
        }
        patterns = list(rule.get("patterns") or [])
        if len(patterns) == 1:
            entry["pattern"] = patterns[0]
        else:
            entry["pattern-either"] = [{"pattern": p} for p in patterns]

        paths: dict = {}
        if rule.get("paths"):
            paths["include"] = list(rule["paths"])
        if rule.get("exclude"):
            paths["exclude"] = list(rule["exclude"])
        if paths:
            entry["paths"] = paths
        rules.append(entry)

    header = (
        "# Generated by `hobbes invariants compile` — do not edit.\n"
        "# Source of truth: .hobbes/invariants/*.yaml (ADR-024).\n"
    )
    return header + yaml.safe_dump(
        {"rules": rules}, sort_keys=False, width=100, allow_unicode=True
    )


def _rego_ident(invariant_id: str) -> str:
    """`I-4` is not a Rego identifier; `I_4` is."""
    return re.sub(r"[^A-Za-z0-9_]", "_", invariant_id)


def _emit_rego(records: list[Invariant], graph: dict) -> str:
    """Rego for conftest against `terraform plan -json`."""
    blocks = []
    for inv in records:
        rule = inv.rule
        resource_type = rule.get("resource_type", "")
        checks = []
        for attribute, expected in (rule.get("require") or {}).items():
            checks.append(
                f"\tnot _has(resource.change.after, {json.dumps(attribute)}, "
                f"{json.dumps(expected)})"
            )
        for attribute, banned in (rule.get("forbid") or {}).items():
            checks.append(
                f"\t_has(resource.change.after, {json.dumps(attribute)}, "
                f"{json.dumps(banned)})"
            )
        body = "\n".join(checks) if checks else "\ttrue"
        blocks.append(
            f"# {inv.id}: {_summary(inv)}\n"
            f"deny contains msg if {{\n"
            f"\tsome resource in input.resource_changes\n"
            f"\tresource.type == {json.dumps(resource_type)}\n"
            f"{body}\n"
            f'\tmsg := sprintf("%s violates {inv.id}: %s", '
            f"[resource.address, {json.dumps(_summary(inv, limit=200))}])\n"
            f"}}"
        )

    header = (
        "# Generated by `hobbes invariants compile` — do not edit.\n"
        "# Source of truth: .hobbes/invariants/*.yaml (ADR-024).\n"
        "package main\n\n"
        "import rego.v1\n\n"
        "# _has is true when the attribute is present and equal to want.\n"
        "# A null or absent attribute is never a match, so `require` fails\n"
        "# on an unset value rather than passing it.\n"
        "_has(obj, key, want) if {\n"
        "\tobj[key] == want\n"
        "}\n"
    )
    return header + "\n" + "\n\n".join(blocks) + "\n"
