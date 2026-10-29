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
    parent, made = _scratch_parent(repo_root)
    try:
        with tempfile.TemporaryDirectory(prefix="hobbes-diff-", dir=parent) as scratch:
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                tar.extractall(scratch, filter="data")
            environments = link_environments(repo_root, Path(scratch))
            extraction = extract_repo(Path(scratch))
    finally:
        for path in reversed(made):
            try:
                path.unlink() if path.name == ".gitignore" else path.rmdir()
            except OSError:
                pass
    return dataclasses.replace(extraction, environments=tuple(environments))


def _scratch_parent(repo_root: Path) -> tuple[Path | None, list[Path]]:
    """Where to unpack a ref, and what was made for it (removed after).

    ``<repo>/.hobbes/tmp/``, on the checkout's filesystem so its files can
    be hardlinked in, and ignoring itself (a ``*`` .gitignore) so a killed
    run leaves nothing git would offer to commit, in any repo. A checkout
    that cannot be written to unpacks in the system's temp directory
    instead, where a link across filesystems fails and is said (C-198).
    """
    parent = repo_root / ".hobbes" / "tmp"
    ignore = parent / ".gitignore"
    made = [d for d in (parent.parent, parent) if not d.exists()]
    try:
        parent.mkdir(parents=True, exist_ok=True)
        if not ignore.exists():
            ignore.write_text("*\n")
            made.append(ignore)
    except OSError:
        return None, [d for d in made if d.exists()]
    return parent, made


#: Dependency trees an extraction reads that `git archive` leaves out (ADR-186).
NODE_MODULES = "node_modules"
VENV_NAMES = (".venv", "venv")


def link_environments(repo_root: Path, scratch: Path) -> list[dict]:
    """Hardlink the checkout's dependency trees into an unpacked ref (ADR-186).

    A ``node_modules``, and a ``.venv`` or ``venv`` holding ``pyvenv.cfg``,
    is linked where the ref's tree has its parent and not the tree itself:
    directories made, files hardlinked, symlinks copied, so a workspace
    package's relative link resolves inside *scratch*; an absolute link
    into the checkout is pointed at the same place in *scratch*, so it too
    reads the ref. A tree that is itself a symlink is linked from where it
    resolves, and its record says ``via``. Nothing is copied. A tree that
    cannot be linked is removed again and its record says why; that end
    reads the directory without it (C-198).
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
            source = Path(root) / name
            record = {"path": str(rel / name) if rel.parts else name, "kind": kind}
            if source.is_symlink():
                source = source.resolve()
                record["via"] = str(source)
            try:
                _link_tree(source, target, repo_root.resolve(), scratch)
            except OSError as exc:
                shutil.rmtree(target, ignore_errors=True)
                record["error"] = str(exc)
                if target.exists() or target.is_symlink():
                    record["error"] += "; and part of it could not be removed, so that end reads a partial tree"
            linked.append(record)
    return sorted(linked, key=lambda r: r["path"])


def _link_tree(source: Path, target: Path, repo_root: Path, scratch: Path) -> None:
    """*source* rebuilt at *target*: directories made, files hardlinked, symlinks copied."""
    target.mkdir()
    with os.scandir(source) as entries:
        for entry in entries:
            destination = target / entry.name
            if entry.is_symlink():
                link = os.readlink(entry.path)
                if os.path.isabs(link) and Path(link).is_relative_to(repo_root):
                    link = str(scratch / Path(link).relative_to(repo_root))
                os.symlink(link, destination)
            elif entry.is_dir(follow_symlinks=False):
                _link_tree(Path(entry.path), destination, repo_root, scratch)
            else:
                os.link(entry.path, destination)


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
        if "via" in e and "error" not in e:
            lines.append(f"a symlink, linked from where it resolves (C-198): {e['path']} -> {e['via']}")
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
