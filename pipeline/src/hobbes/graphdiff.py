"""Graph diff: the architecture delta between two extractions (ADR-009).

Node identity is ``id``; edge identity is ``(from, to, type)``. Evidence
changes (an import moving lines) are deliberately not deltas — this is the
concept-level review artifact, not a line diff. :func:`extract_at_ref`
produces a graph for any committed ref by unpacking ``git archive`` output
into a scratch directory and running the pure extractor over it; the user's
checkout is never changed. An archive holds no dependency trees, so the
checkout's are hardlinked in (ADR-186): both ends read today's install (C-198).
"""

from __future__ import annotations

import dataclasses
import io
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from hobbes.extract import extract_repo


class RefError(RuntimeError):
    """A git ref could not be resolved or archived."""


def extract_at_ref(repo_root: Path, ref: str) -> dict:
    """The graph document for *ref*'s tree (module + symbol layers)."""
    return extract_all_at_ref(repo_root, ref).graph


def extract_all_at_ref(repo_root: Path, ref: str):
    """The whole extraction for *ref*'s tree — graph, tests, interfaces.

    `hobbes review` needs the test inventory as well as the graph to
    compute a behavioral-coverage delta (ADR-025), and unpacking the
    archive twice to get them would double the cost of every review.
    """
    repo_root = Path(repo_root)
    try:
        archive = subprocess.run(
            ["git", "-C", str(repo_root), "archive", "--format=tar", ref],
            capture_output=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise RefError(
            f"cannot archive {ref!r}: {exc.stderr.decode(errors='replace').strip()}"
        ) from exc
    # On the checkout's filesystem, so its files can be hardlinked in.
    parent = repo_root / ".hobbes" / "tmp"
    made = [d for d in (parent.parent, parent) if not d.exists()]
    parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="hobbes-diff-", dir=parent) as scratch:
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                tar.extractall(scratch, filter="data")
            environments = link_environments(repo_root, Path(scratch))
            extraction = extract_repo(Path(scratch))
    finally:
        for directory in reversed(made):
            try:
                directory.rmdir()
            except OSError:
                pass
    return dataclasses.replace(extraction, environments=tuple(environments))


#: Dependency trees an extraction reads that `git archive` leaves out (ADR-186).
NODE_MODULES = "node_modules"
VENV_NAMES = (".venv", "venv")


def link_environments(repo_root: Path, scratch: Path) -> list[dict]:
    """Hardlink the checkout's dependency trees into an unpacked ref (ADR-186).

    A ``node_modules``, and a ``.venv`` or ``venv`` holding ``pyvenv.cfg``,
    is linked where the ref's tree has its parent and not the tree itself:
    directories made, files hardlinked, symlinks copied as they are, so a
    workspace package's relative link resolves inside *scratch*. Nothing
    is copied. A tree that cannot be linked is removed again and its
    record says why; that end reads the directory without it (C-198).
    """
    linked = []
    for root, dirs, _ in os.walk(repo_root):
        rel = Path(root).relative_to(repo_root)
        if rel.parts[:1] in ((".git",), (".hobbes",)) or not (scratch / rel).is_dir():
            dirs[:] = []
            continue
        found = [(NODE_MODULES, "node_modules")] if NODE_MODULES in dirs else []
        found += [(name, "venv") for name in VENV_NAMES if name in dirs and (Path(root) / name / "pyvenv.cfg").is_file()]
        for name, kind in found:
            dirs.remove(name)
            target = scratch / rel / name
            if target.exists() or target.is_symlink():
                continue
            record = {"path": str(rel / name) if rel.parts else name, "kind": kind}
            try:
                shutil.copytree(Path(root) / name, target, symlinks=True, copy_function=os.link)
            except (OSError, shutil.Error) as exc:
                shutil.rmtree(target, ignore_errors=True)
                record["error"] = _link_error(exc)
            linked.append(record)
    return sorted(linked, key=lambda r: r["path"])


def _link_error(exc: Exception) -> str:
    """The first cause of a failed link, short enough for one review line."""
    if isinstance(exc, shutil.Error) and exc.args and exc.args[0]:
        first = exc.args[0][0]
        return str(first[2]) if len(first) > 2 else str(first)
    return str(exc)


def format_environments(environments) -> list[str]:
    """What a ref's extraction was given, for the review and the diff (C-198)."""
    if not environments:
        return []
    ok = [e for e in environments if "error" not in e]
    kinds = {}
    for e in ok:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    lines = []
    if ok:
        counted = ", ".join(f"{n} {kind}" for kind, n in sorted(kinds.items()))
        lines.append(
            f"dependency trees: {len(ok)} hardlinked from the checkout into each end ({counted});"
            " both ends read today's install, not each ref's (C-198)"
        )
    for e in environments:
        if "error" in e:
            lines.append(f"not linked, read without its dependency tree (C-198): {e['path']} — {e['error']}")
    return lines


def diff_graphs(base: dict, head: dict) -> dict:
    """The typed delta between two graph documents (ADR-009).

    Added edges carry head's evidence, removed edges carry base's; nodes
    are reported bare (id + kind from the side they exist on).
    """
    base_nodes = {n["id"]: n for n in base["nodes"]}
    head_nodes = {n["id"]: n for n in head["nodes"]}
    delta = {
        "nodes_added": [
            head_nodes[i] for i in sorted(head_nodes.keys() - base_nodes.keys())
        ],
        "nodes_removed": [
            base_nodes[i] for i in sorted(base_nodes.keys() - head_nodes.keys())
        ],
    }
    for layer in ("module_edges", "symbol_edges"):
        base_edges = {_edge_key(e): e for e in base[layer]}
        head_edges = {_edge_key(e): e for e in head[layer]}
        delta[f"{layer}_added"] = [
            head_edges[k] for k in sorted(head_edges.keys() - base_edges.keys())
        ]
        delta[f"{layer}_removed"] = [
            base_edges[k] for k in sorted(base_edges.keys() - head_edges.keys())
        ]
    return delta


def has_changes(delta: dict) -> bool:
    """Whether the delta contains anything at all (drives exit codes)."""
    return any(delta[key] for key in delta)


def format_delta(delta: dict, base_label: str, head_label: str) -> str:
    """Human-readable delta: module level line by line, symbol layer as
    counts (module-level is the review altitude — ADR-009)."""
    lines = [f"architecture delta {base_label}..{head_label}"]
    if not has_changes(delta):
        lines.append("  no architectural changes")
        return "\n".join(lines) + "\n"

    for node in delta["nodes_added"]:
        lines.append(f"  + {node['kind']} {node['id']}")
    for node in delta["nodes_removed"]:
        lines.append(f"  - {node['kind']} {node['id']}")
    for edge in delta["module_edges_added"]:
        lines.append(f"  + {edge['type']} {edge['from']} -> {edge['to']}{_site(edge)}")
    for edge in delta["module_edges_removed"]:
        lines.append(f"  - {edge['type']} {edge['from']} -> {edge['to']}")

    # C-76: `calls` and `uses` counted apart, as the ingest summary does;
    # `implements` (ADR-120) beside them.
    for edge_type in ("calls", "uses", "implements"):
        added = sum(1 for e in delta["symbol_edges_added"] if e["type"] == edge_type)
        removed = sum(1 for e in delta["symbol_edges_removed"] if e["type"] == edge_type)
        if added or removed:
            lines.append(f"  symbol layer: +{added} / -{removed} {edge_type} edges")
    return "\n".join(lines) + "\n"


def _edge_key(edge: dict) -> tuple:
    return (edge["from"], edge["to"], edge["type"])


def _site(edge: dict) -> str:
    evidence = edge.get("evidence")
    if not evidence:
        return ""
    return f"   [{evidence[0]['path']}:{evidence[0]['line']}]"
