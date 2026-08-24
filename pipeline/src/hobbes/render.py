"""Module-level Mermaid export of graph.json (ADR-008).

:func:`to_mermaid` maps the module layer of a graph document onto a
``flowchart LR``: internal modules clustered by top-level package, external
dependencies and environment variables shape-styled, edges styled by type.
Deterministic — the same document always yields the same text. The symbol
layer is never rendered here (architecture §10: render module-level).
"""

from __future__ import annotations

import posixpath

#: Edge types with dedicated arrow styles; anything new renders labeled so
#: it is visible before it earns bespoke styling (ADR-008).
_EDGE_ARROWS = {"imports": "-->", "env-read": "-.->", "env-set": "-.->"}


def to_mermaid(graph: dict) -> str:
    """Render a graph.json document as a Mermaid flowchart."""
    nodes = sorted(graph["nodes"], key=lambda n: n["id"])
    tokens = {node["id"]: f"n{i}" for i, node in enumerate(nodes)}

    lines = ["flowchart LR"]
    lines += _node_lines(nodes, tokens)
    lines += _edge_lines(graph["module_edges"], tokens)
    return "\n".join(lines) + "\n"


#: Kinds clustered into subgraphs: app modules by top-level package, infra
#: blocks by the directory of their defining .tf file.
_GROUPED_KINDS = {"module", "package", "resource", "data", "tf-module"}


def _declaration(node: dict, token: str) -> str:
    label = node["id"].replace('"', "'")
    kind = node["kind"]
    if kind == "external":
        return f'{token}[["{label}"]]'
    if kind == "env":
        return f'{token}(["{label}"])'
    if kind == "resource":
        return f'{token}{{{{"{label}"}}}}'
    if kind == "data":
        return f'{token}[("{label}")]'
    if kind == "tf-module":
        return f'{token}[/"{label}"/]'
    return f'{token}["{label}"]'


def _group_key(node: dict) -> str:
    """Cluster key: app modules use the top-level package of their id
    (root-disambiguated ids like ``pipeline:tests.test_cli`` keep their
    prefix, so the two ``tests`` packages cluster separately); infra nodes
    use their .tf file's directory."""
    if node["kind"] in ("module", "package"):
        return node["id"].split(".", 1)[0]
    return posixpath.dirname(node.get("path", "")) or "infra"


def _node_lines(nodes: list[dict], tokens: dict[str, str]) -> list[str]:
    internal = [n for n in nodes if n["kind"] in _GROUPED_KINDS]
    other = [n for n in nodes if n["kind"] not in _GROUPED_KINDS]

    groups: dict[str, list[dict]] = {}
    for node in internal:
        groups.setdefault(_group_key(node), []).append(node)

    lines = []
    for i, (key, members) in enumerate(sorted(groups.items())):
        if len(members) == 1:  # one-node boxes are noise (ADR-008)
            lines.append(f"  {_declaration(members[0], tokens[members[0]['id']])}")
            continue
        lines.append(f'  subgraph sg{i}["{key}"]')
        lines += [
            f"    {_declaration(m, tokens[m['id']])}" for m in members
        ]
        lines.append("  end")
    lines += [f"  {_declaration(n, tokens[n['id']])}" for n in other]
    return lines


def _edge_lines(module_edges: list[dict], tokens: dict[str, str]) -> list[str]:
    lines = []
    for edge in sorted(
        module_edges, key=lambda e: (e["from"], e["to"], e["type"])
    ):
        arrow = _EDGE_ARROWS.get(edge["type"], f'--"{edge["type"]}"-->')
        lines.append(f"  {tokens[edge['from']]} {arrow} {tokens[edge['to']]}")
    return lines
