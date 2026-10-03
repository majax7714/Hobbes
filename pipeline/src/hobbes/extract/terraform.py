"""Terraform/HCL extractor: infra nodes, references, cross-layer joins (ADR-010).

Static tree-sitter-hcl parse of every ``.tf`` file plus optional
``terraform show -json`` plan enrichment. Produces nodes (``tf:`` prefixed)
and module-level edges in graph.json's shape:

- ``references`` — traversal chains (``aws_iam_role.x.arn``) resolving to a
  *declared* block; undeclared addresses produce nothing.
- ``env-set`` — literal environment-variable keys (Lambda-style
  ``environment { variables = {…} }`` and container-style ``env { name = … }``
  blocks), landing on the same ``env:VAR`` nodes the Python extractor uses
  for ``env-read`` — the §4.1 cross-layer join is id equality.
- ``packages`` — string literals (after ``${path.module}`` substitution)
  resolving to a repo file the Python extractor discovered: the
  infra-packages-app-code edge.

A node's id is ``tf:<dir>:<address>``, the directory being the module's
scope in Terraform's terms (``.`` for the repo root), and a reference
resolves in its own directory: an address declared only in another
directory draws nothing (ADR-173 and its amendment). What the layer does
not read is registered (C-188 to C-193) and named per ingest in one
``hcl-layer`` record, and per damaged file in ``hcl-parse``.

Never reads ``.tfstate`` — state carries secrets (engineering rule; the
policy engine's builtin floor, ADR-011, enforces the same for agents).
"""

from __future__ import annotations

import json
import posixpath
from pathlib import Path

import tree_sitter_hcl
from tree_sitter import Language, Node, Parser

from hobbes.extract.discover import ModuleInfo, SKIPPED_DIR_NAMES, is_linked_copy
from hobbes.extract.graph import _edge_list

_PARSER = Parser(Language(tree_sitter_hcl.language()))

#: Top-level block types that become graph nodes, → node kind.
_BLOCK_KINDS = {"resource": "resource", "data": "data", "module": "tf-module"}

#: Top-level block types the layer does not make nodes of, counted in the
#: ``hcl-layer`` record (C-188).
_INDIRECT_BLOCKS = ("locals", "variable", "output")

#: Terraform files in a syntax the layer does not parse (C-192).
_UNREAD_SUFFIXES = (".tf.json", ".tofu")

#: Chain heads that can never be a declared-block reference.
_NON_ADDRESS_HEADS = {"var", "local", "path", "each", "count", "terraform", "self"}


class PlanError(RuntimeError):
    """A terraform plan JSON could not be used."""


def extract_terraform(
    repo_root: Path, modules: list[ModuleInfo], tf_plan: Path | None = None
) -> dict:
    """Extract the infra layer: ``{"nodes", "module_edges", "tf_file_count",
    "errors"}``.

    *modules* is the Python discovery result, used for the ``packages``
    join. *tf_plan* optionally names a ``terraform show -json`` file.
    """
    repo_root = Path(repo_root).resolve()
    tf_files = discover_tf(repo_root)
    module_by_path = {m.path: m.id for m in modules}

    parsed: list[tuple[str, Node, str, str]] = []  # (file, block, addr, kind)
    declared_dirs: dict[str, set[str]] = {}  # address → directories declaring it
    indirect = dict.fromkeys(_INDIRECT_BLOCKS, 0)
    module_sources = {"local": 0, "remote": 0}
    errors: list[dict] = []
    for rel in tf_files:
        root = _PARSER.parse((repo_root / rel).read_bytes()).root_node
        if root.has_error:
            errors.append(_parse_record(rel))
        for block_type, block in _top_level(root):
            if block_type in indirect:
                indirect[block_type] += 1
        for block, addr, kind in _top_blocks(root):
            declared_dirs.setdefault(addr, set()).add(_tf_dir(rel))
            parsed.append((rel, block, addr, kind))
            if kind == "tf-module":
                module_sources[_module_source_kind(block)] += 1

    nodes: dict[str, dict] = {}
    edges: dict[tuple, list] = {}
    cross_directory = 0
    for rel, block, addr, kind in parsed:
        tf_dir = _tf_dir(rel)
        source_id = _node_id(tf_dir, addr)
        nodes.setdefault(source_id, {"id": source_id, "kind": kind, "path": rel})

        for chain, line in _traversals(block):
            target_addr = _addr_from_chain(chain)
            if target_addr in declared_dirs and target_addr != addr:
                if tf_dir not in declared_dirs[target_addr]:
                    cross_directory += 1  # Terraform never resolves it (ADR-173)
                    continue
                _add_edge(
                    edges, source_id, _node_id(tf_dir, target_addr), "references", rel, line
                )

        for key, line in _env_keys(block):
            env_id = f"env:{key}"
            nodes.setdefault(env_id, {"id": env_id, "kind": "env", "name": key})
            _add_edge(edges, source_id, env_id, "env-set", rel, line)

        for literal, line in _string_values(block):
            target_module = _resolve_repo_path(
                repo_root, posixpath.dirname(rel), literal, module_by_path
            )
            if target_module is not None:
                _add_edge(edges, source_id, target_module, "packages", rel, line)

    if tf_plan is not None:
        _consume_plan(repo_root, tf_plan, declared_dirs, nodes, edges, errors)

    if tf_files:
        errors.insert(0, _layer_record(
            len(tf_files), indirect, module_sources,
            _walk_files(repo_root, _UNREAD_SUFFIXES), cross_directory,
        ))
    return {
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "module_edges": _edge_list(edges),
        "tf_file_count": len(tf_files),
        "errors": errors,
    }


def discover_tf(repo_root: Path) -> list[str]:
    """Repo-relative .tf paths, pruned like Python discovery (.terraform/
    is a dot-directory and already excluded).

    Public because the Terraform pack's detection needs the same pruned
    walk: a plain ``glob("**/*.tf")`` would descend into ``node_modules``.
    """
    return _walk_files(repo_root, (".tf",))


def _walk_files(repo_root: Path, suffixes: tuple[str, ...]) -> list[str]:
    """Repo-relative paths whose name ends in one of *suffixes*, under
    discovery's pruning. A name is matched whole (``x.tf.json`` is not
    ``.tf``)."""
    found = []
    stack = [repo_root]
    while stack:
        directory = stack.pop()
        for child in sorted(directory.iterdir()):
            if child.is_dir():
                if (
                    child.name not in SKIPPED_DIR_NAMES
                    and not child.name.startswith(".")
                    and not is_linked_copy(child, repo_root)
                ):
                    stack.append(child)
            elif child.name.endswith(suffixes):
                found.append(child.relative_to(repo_root).as_posix())
    return sorted(found)


def _tf_dir(rel: str) -> str:
    """The directory a ``.tf`` file declares into: its module's scope."""
    return posixpath.dirname(rel) or "."


def _node_id(tf_dir: str, addr: str) -> str:
    """``tf:<dir>:<address>`` — an address is unique only in its directory
    (ADR-173's amendment; C-187 lifted)."""
    return f"tf:{tf_dir}:{addr}"


def _parse_record(rel: str) -> dict:
    """The ``hcl-parse`` record for a ``.tf`` file tree-sitter-hcl parsed
    with errors (C-192): its recovery can swallow every block after an
    unclosed brace."""
    return {
        "path": rel,
        "stage": "hcl-parse",
        "message": (
            f"{rel} parsed with syntax errors (tree-sitter ERROR nodes); a block inside a "
            "region the parse could not read is not a node and its references are not "
            "drawn — an unclosed brace can take the rest of the file (C-192)"
        ),
    }


def _layer_record(
    tf_count: int,
    indirect: dict[str, int],
    module_sources: dict[str, int],
    unread: list[str],
    cross_directory: int,
) -> dict:
    """The one ``hcl-layer`` record per ingest that names what the Terraform
    layer does not read, with this repo's counts (ADR-173, C-188 to C-193)."""
    parts = [
        f"the Terraform layer read {tf_count} .tf file(s), syntactic. It draws `references` "
        "only where a block names another block in its own directory",
        f"{indirect['locals']} `locals`, {indirect['variable']} `variable` and "
        f"{indirect['output']} `output` block(s) are not nodes, and a reference through one "
        "is not drawn (C-188)",
        f"{module_sources['local'] + module_sources['remote']} module call(s) "
        f"({module_sources['local']} local, {module_sources['remote']} registry or remote) are "
        "one node each, not followed into their source (C-189)",
        "`env-set` reads only literal keys of `environment { variables = {…} }` and "
        "`env { name = … }`: a Python env-read with no env-set does not mean nothing sets "
        "it (C-190)",
        "`packages` joins only a literal or `${path.module}` path to a Python file (C-191)",
    ]
    if unread:
        parts.append(
            f"{len(unread)} .tf.json or .tofu file(s) not read: "
            + ", ".join(unread[:3]) + (" …" if len(unread) > 3 else "") + " (C-192)"
        )
    if cross_directory:
        parts.append(
            f"{cross_directory} reference(s) to an address declared only in another "
            "directory refused, since Terraform never resolves one (ADR-173, C-187's residual)"
        )
    return {"path": ".", "stage": "hcl-layer", "message": "; ".join(parts)}


def _text(node: Node) -> str:
    return (node.text or b"").decode("utf-8", "replace")


def _top_level(root: Node):
    """Yield (block type, block node) for every top-level block."""
    body = next((c for c in root.children if c.type == "body"), None)
    for block in body.children if body else []:
        if block.type != "block":
            continue
        block_type = next(
            (_text(c) for c in block.children if c.type == "identifier"), None
        )
        yield block_type, block


def _module_source_kind(block: Node) -> str:
    """``local`` for a module block whose ``source`` is a ``./`` or ``../``
    path, ``remote`` for anything else (a registry address, git, a URL)."""
    body = next((c for c in block.children if c.type == "body"), None)
    for attribute in body.children if body else []:
        if attribute.type == "attribute" and _text(attribute.children[0]) == "source":
            source = _pure_string(attribute.children[-1]) or ""
            return "local" if source.startswith(("./", "../")) else "remote"
    return "remote"


def _top_blocks(root: Node):
    """Yield (block node, address, kind) for node-worthy top-level blocks."""
    for block_type, block in _top_level(root):
        labels = [
            _string_label(child) for child in block.children if child.type == "string_lit"
        ]
        kind = _BLOCK_KINDS.get(block_type)
        if kind is None:
            continue
        if block_type == "resource" and len(labels) >= 2:
            yield block, f"{labels[0]}.{labels[1]}", kind
        elif block_type == "data" and len(labels) >= 2:
            yield block, f"data.{labels[0]}.{labels[1]}", kind
        elif block_type == "module" and len(labels) >= 1:
            yield block, f"module.{labels[0]}", kind


def _string_label(string_lit: Node) -> str:
    return "".join(
        _text(c) for c in string_lit.children if c.type == "template_literal"
    )


def _walk(node: Node):
    """*node* and everything under it in pre-order — the node, then its
    children left to right, depth first. An explicit stack, as
    ``csource._walk``: a recursive generator overflowed Python's stack on
    a 537-call builder chain and ended the whole ingest (moonlab's
    ``build.rs``, the E3 draw, 2026-09-26)."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def _traversals(block: Node):
    """Every identifier traversal chain in the block's expressions:
    ``aws_iam_role.worker.arn`` → (["aws_iam_role", "worker", "arn"], line).
    Includes chains inside string interpolations."""
    for node in _walk(block):
        if node.type != "variable_expr" or node.parent is None:
            continue
        chain = [_text(node)]
        siblings = node.parent.children
        for sibling in siblings[siblings.index(node) + 1 :]:
            if sibling.type != "get_attr":
                break
            chain.append(
                "".join(_text(c) for c in sibling.children if c.type == "identifier")
            )
        yield chain, node.start_point.row + 1


def _addr_from_chain(chain: list[str]) -> str | None:
    if not chain or chain[0] in _NON_ADDRESS_HEADS:
        return None
    if chain[0] == "data":
        return f"data.{chain[1]}.{chain[2]}" if len(chain) >= 3 else None
    if chain[0] == "module":
        return f"module.{chain[1]}" if len(chain) >= 2 else None
    return f"{chain[0]}.{chain[1]}" if len(chain) >= 2 else None


def _env_keys(block: Node):
    """Literal env-var keys from ``environment { variables = {…} }`` and
    ``env { name = "…" }`` patterns (ADR-010)."""
    for node in _walk(block):
        if node.type != "block":
            continue
        name = next(
            (_text(c) for c in node.children if c.type == "identifier"), None
        )
        if name == "environment":
            yield from _environment_variables_keys(node)
        elif name == "env":
            yield from _env_block_name(node)


def _environment_variables_keys(environment_block: Node):
    for node in _walk(environment_block):
        if node.type != "attribute":
            continue
        if _text(node.children[0]) != "variables":
            continue
        for elem in _walk(node):
            if elem.type == "object_elem" and elem.named_children:
                key = _key_text(elem.named_children[0])
                if key is not None:
                    yield key, elem.start_point.row + 1


def _env_block_name(env_block: Node):
    body = next((c for c in env_block.children if c.type == "body"), None)
    for attribute in body.children if body else []:
        if attribute.type != "attribute":
            continue
        if _text(attribute.children[0]) != "name":
            continue
        literal = _pure_string(attribute.children[-1])
        if literal is not None:
            yield literal, attribute.start_point.row + 1


def _key_text(expression: Node) -> str | None:
    """An object key: bare identifier or plain string literal."""
    for node in _walk(expression):
        if node.type == "variable_expr":
            return _text(node)
        if node.type in ("quoted_template", "string_lit"):
            return _quoted_literal(node)
    return None


def _string_values(block: Node):
    """String attribute values usable for the packages join: pure literals
    (``string_lit`` in this grammar) and ``${path.module}<literal>``
    templates (``quoted_template``, yielding the literal remainder — the
    caller anchors both at the .tf file's directory)."""
    for node in _walk(block):
        if node.type == "string_lit":
            # Skip the block's own labels (resource "type" "name").
            if node.parent is not None and node.parent.type == "block":
                continue
            literal = _quoted_literal(node)
            if literal:
                yield literal, node.start_point.row + 1
            continue
        if node.type != "quoted_template":
            continue
        parts = [
            c
            for c in node.children
            if c.type in ("template_literal", "template_interpolation")
        ]
        line = node.start_point.row + 1
        if all(p.type == "template_literal" for p in parts):
            if parts:
                yield "".join(_text(p) for p in parts), line
        elif (
            len(parts) == 2
            and parts[0].type == "template_interpolation"
            and parts[1].type == "template_literal"
            and _interpolation_chain(parts[0]) == ["path", "module"]
        ):
            yield "." + _text(parts[1]), line


def _interpolation_chain(interpolation: Node) -> list[str] | None:
    chains = [chain for chain, _ in _traversals(interpolation)]
    return chains[0] if len(chains) == 1 else None


def _pure_string(node: Node) -> str | None:
    for candidate in _walk(node):
        if candidate.type in ("quoted_template", "string_lit"):
            return _quoted_literal(candidate)
    return None


def _quoted_literal(string_node: Node) -> str | None:
    """The literal content of a string_lit/quoted_template; None if it
    contains interpolation."""
    parts = [
        c
        for c in string_node.children
        if c.type in ("template_literal", "template_interpolation")
    ]
    if any(p.type == "template_interpolation" for p in parts):
        return None
    return "".join(_text(p) for p in parts)


def _resolve_repo_path(
    repo_root: Path, tf_dir: str, literal: str, module_by_path: dict[str, str]
) -> str | None:
    """Resolve a string against the .tf file's directory (Terraform's rule
    for relative paths); return the module id it names, if any."""
    if literal.startswith("/") or not literal:
        return None  # absolute paths point outside the repo's terms
    candidate = posixpath.normpath(posixpath.join(tf_dir, literal))
    if candidate.startswith(".."):
        return None
    return module_by_path.get(candidate)


def _add_edge(
    edges: dict, from_id: str, to_id: str, edge_type: str, path: str, line: int
) -> None:
    edges.setdefault((from_id, to_id, edge_type), []).append(
        {"path": path, "line": line}
    )


def _consume_plan(
    repo_root: Path,
    tf_plan: Path,
    declared_dirs: dict[str, set[str]],
    nodes: dict[str, dict],
    edges: dict,
    errors: list[dict],
) -> None:
    """Enrich with a ``terraform show -json`` document (ADR-010): declared
    addresses and the resolved reference lists from ``configuration``.
    Evidence is file-granular — plans carry no source lines. A plan names no
    directory, so its root module is the one directory that declares every
    address it shares with the ``.tf`` files, or the repo's only Terraform
    directory; otherwise it adds nothing and says so (ADR-173's amendment)."""
    tf_plan = Path(tf_plan)
    if "tfstate" in tf_plan.name.lower():
        raise PlanError(
            f"{tf_plan}: refusing anything that looks like Terraform state "
            "(state carries secrets; use `terraform show -json <planfile>`)"
        )
    try:
        plan = json.loads(tf_plan.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanError(f"{tf_plan}: not a readable plan JSON ({exc})") from exc

    try:
        plan_rel = str(tf_plan.resolve().relative_to(repo_root))
    except ValueError:
        plan_rel = tf_plan.name

    resources = [
        r
        for r in plan.get("configuration", {}).get("root_module", {}).get("resources", [])
        if r.get("address")
    ]
    tf_dir = _plan_directory([r["address"] for r in resources], declared_dirs)
    if tf_dir is None:
        if resources:
            errors.append({
                "path": plan_rel,
                "stage": "hcl-plan",
                "message": (
                    f"{plan_rel} names no directory, and its {len(resources)} root-module "
                    "resource(s) are not declared by exactly one Terraform directory, so the "
                    "plan adds nothing (ADR-173, C-193)"
                ),
            })
        return
    in_plan = {r["address"] for r in resources}
    for addr in in_plan:
        kind = "data" if addr.startswith("data.") else "resource"
        node_id = _node_id(tf_dir, addr)
        nodes.setdefault(node_id, {"id": node_id, "kind": kind, "path": plan_rel})
    for resource in resources:
        addr = resource["address"]
        for reference in _plan_references(resource.get("expressions", {})):
            target_addr = _addr_from_chain(reference.split("."))
            if target_addr != addr and (
                target_addr in in_plan or tf_dir in declared_dirs.get(target_addr, ())
            ):
                _add_edge(
                    edges, _node_id(tf_dir, addr), _node_id(tf_dir, target_addr),
                    "references", plan_rel, 1,
                )


def _plan_directory(addresses: list[str], declared_dirs: dict[str, set[str]]) -> str | None:
    """The directory a plan's root module is: the one that declares every
    address the plan shares with the ``.tf`` files, or, where it shares none,
    the repo's only Terraform directory. None where neither settles it."""
    shared = [declared_dirs[a] for a in addresses if a in declared_dirs]
    if shared:
        candidates = set.intersection(*shared)
    else:
        candidates = set().union(*declared_dirs.values()) if declared_dirs else set()
    return next(iter(candidates)) if len(candidates) == 1 else None


def _plan_references(value):
    """Every string in any ``references`` list nested under *value*."""
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "references" and isinstance(nested, list):
                yield from (r for r in nested if isinstance(r, str))
            else:
                yield from _plan_references(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _plan_references(nested)
