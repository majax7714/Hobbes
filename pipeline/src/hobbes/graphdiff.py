"""Graph diff: the architecture delta between two extractions (ADR-009).

Node identity is ``id``; edge identity is ``(from, to, type)``. Evidence
changes (an import moving lines) are deliberately not deltas — this is the
concept-level review artifact, not a line diff. :func:`extract_at_ref`
produces a graph for any committed ref by unpacking ``git archive`` output
into a scratch directory and running the pure extractor over it; the user's
checkout is never touched.
"""

from __future__ import annotations

import io
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
    with tempfile.TemporaryDirectory(prefix="hobbes-diff-") as scratch:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(scratch, filter="data")
        return extract_repo(Path(scratch))


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

    added = len(delta["symbol_edges_added"])
    removed = len(delta["symbol_edges_removed"])
    if added or removed:
        lines.append(f"  symbol layer: +{added} / -{removed} call edges")
    return "\n".join(lines) + "\n"


def _edge_key(edge: dict) -> tuple:
    return (edge["from"], edge["to"], edge["type"])


def _site(edge: dict) -> str:
    evidence = edge.get("evidence")
    if not evidence:
        return ""
    return f"   [{evidence[0]['path']}:{evidence[0]['line']}]"
