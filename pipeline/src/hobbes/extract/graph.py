"""Graph assembly: resolve per-file facts into typed nodes and edges.

Module-level edges (``imports``, ``env-read``) depend only on import
resolution, are near-exact, and stay lane A's on purpose (§3.1) — they
reach ``ext:`` and ``env:`` nodes lane B cannot see, and they are what the
lane-agreement report compares.

**This module no longer produces symbol edges (ADR-031).** ADR-007's call
resolution rules 1–4 survive as :func:`resolve_call_sites`, whose output is
the *fallback* the range join consults where the semantic provider resolved
nothing — labelled ``syntactic`` when it is used. There is one resolver of
record and it is lane B; what lives here is a labelled floor beneath it, so
that a repo whose language has no indexer, or a box without one installed,
still has a call graph (P6). It is deliberately under-approximated: a
resolution is offered only when the callee resolves statically, because
false edges are worse than missing ones.

The output shape is ADR-006's graph.json body minus the symbol layer:
``nodes``, ``symbols``, ``module_edges``. The join supplies
``symbol_edges``, and the stamp is added at emission.
"""

from __future__ import annotations

from collections import defaultdict

from hobbes.extract.discover import ModuleInfo
from hobbes.extract.pysource import EXPR_RECEIVER, FromImport, ParsedFile, PlainImport
from hobbes.extract.schema import tiered_edge

_SELF_NAMES = ("self", "cls")


def build_graph(modules: list[ModuleInfo], parsed: dict[str, ParsedFile]) -> dict:
    """Assemble the typed graph from discovered modules and per-file facts.

    Nodes, symbols and module edges only — the symbol layer comes from the
    range join now (ADR-031). Call *sites* are still detected here, by
    :mod:`hobbes.extract.pysource`; what moved is resolution.
    """
    index = _Index(modules)
    nodes = {m.id: {"id": m.id, "kind": m.kind, "path": m.path} for m in modules}
    symbols = _symbol_records(modules, parsed)
    module_edges: dict[tuple, list] = defaultdict(list)

    for module in modules:
        facts = parsed[module.id]
        env = _NameEnv(module, facts, index)

        for imp, target in env.resolved_imports:
            if target.id != module.id:
                module_edges[(module.id, target.id, "imports")].append(
                    {"path": module.path, "line": imp.line}
                )
        for imp, top_level in env.external_imports:
            # Stdlib and third-party alike (ADR-038): `subprocess` is exactly
            # the import a reviewer wants flagged, and Go's layer already
            # shows its stdlib — a split answer misleads worse than either.
            ext_id = f"ext:{top_level}"
            nodes.setdefault(ext_id, {"id": ext_id, "kind": "external", "name": top_level})
            module_edges[(module.id, ext_id, "imports")].append(
                {"path": module.path, "line": imp.line}
            )

        for read in facts.env_reads:
            env_id = f"env:{read.var}"
            nodes.setdefault(env_id, {"id": env_id, "kind": "env", "name": read.var})
            module_edges[(module.id, env_id, "env-read")].append(
                {"path": module.path, "line": read.line}
            )

    return {
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "symbols": symbols,
        "module_edges": _edge_list(module_edges),
    }


def resolve_call_sites(
    modules: list[ModuleInfo], parsed: dict[str, ParsedFile]
) -> dict[tuple[str, int, str], tuple[str, int]]:
    """Lane A's own call resolutions, keyed by call site (ADR-031).

    ``(file, line, terminal name) -> (definition file, definition line)``,
    which is the shape the range join's *fallback* takes. Deliberately not
    edges: the join decides whether any of this reaches the graph, and
    stamps what it uses ``syntactic``.

    Implements ADR-007 rules 1–4 exactly as before. Keeping the rules while
    demoting their output is the whole of ADR-031 — without them a repo
    with no working indexer has no call graph at all, which P6 forbids and
    P7 would make permanent for every unwired language.
    """
    index = _Index(modules)
    table = _SymbolTable(parsed)
    where: dict[str, tuple[str, int]] = {}
    for module in modules:
        for symbol in parsed[module.id].symbols:
            where.setdefault(
                f"{module.id}.{symbol.qualname}", (module.path, symbol.line)
            )

    fallback: dict[tuple[str, int, str], tuple[str, int]] = {}
    for module in modules:
        facts = parsed[module.id]
        env = _NameEnv(module, facts, index)
        for call in facts.calls:
            target_id = _resolve_call(module, call, env, index, table)
            if target_id is None:
                continue
            target = where.get(target_id)
            if target is None:
                continue
            if "." not in call.callee and _shadowed(module.path, call.line, call.callee, target, facts.local_bindings):
                continue
            fallback[(module.path, call.line, call.callee.split(".")[-1])] = target
    return fallback


def _shadowed(path: str, line: int, name: str, target: tuple[str, int], bindings) -> bool:
    """A bare name bound in a scope that spans the call (a parameter, an
    assignment, a nested ``def`` — ADR-046's bindings) is *that* binding,
    not a module-level declaration of the same name; the fallback may
    only bind it to a declaration inside the same extent (the nested
    ``def`` itself). The oracle lane's first Python triage (O6,
    2026-08-25): six executed syntactic edges, all a pytest fixture
    *parameter* name-matched to the fixture function, all wrong."""
    for b in bindings:
        if b.name != name or not (b.start <= line <= b.end):
            continue
        if target[0] == path and b.start <= target[1] <= b.end:
            return False  # the binding is the nested declaration itself
        return True
    return False


def _symbol_records(modules: list[ModuleInfo], parsed: dict[str, ParsedFile]) -> list[dict]:
    records: dict[str, dict] = {}
    for module in modules:
        for symbol in parsed[module.id].symbols:
            symbol_id = f"{module.id}.{symbol.qualname}"
            # Duplicate qualnames (if/else definitions) keep the first record.
            records.setdefault(
                symbol_id,
                {
                    "id": symbol_id,
                    "module": module.id,
                    "name": symbol.name,
                    "qualname": symbol.qualname,
                    "kind": symbol.kind,
                    "line": symbol.line,
                    "end_line": symbol.end_line,
                },
            )
    return sorted(records.values(), key=lambda s: s["id"])


def _edge_list(edges: dict[tuple, list]) -> list[dict]:
    return [
        tiered_edge(
            from_id,
            to_id,
            edge_type,
            sorted(evidence, key=lambda e: (e["path"], e["line"])),
        )
        for (from_id, to_id, edge_type), evidence in sorted(edges.items())
    ]


class _Index:
    """Lookup tables over the discovered modules and their symbols."""

    def __init__(self, modules: list[ModuleInfo]):
        self.by_name_global: dict[str, ModuleInfo] = {}
        self.by_root: dict[str, dict[str, ModuleInfo]] = defaultdict(dict)
        for m in modules:
            self.by_name_global.setdefault(m.import_name, m)
            self.by_root[m.root][m.import_name] = m

    def lookup(self, importer: ModuleInfo, dotted: str) -> ModuleInfo | None:
        """Exact import-name lookup, preferring the importer's own root."""
        return self.by_root[importer.root].get(dotted) or self.by_name_global.get(dotted)

    def resolve_prefix(self, importer: ModuleInfo, dotted: str) -> ModuleInfo | None:
        """Longest repo-module prefix of *dotted* (ADR-007), or None."""
        parts = dotted.split(".")
        for i in range(len(parts), 0, -1):
            found = self.lookup(importer, ".".join(parts[:i]))
            if found is not None:
                return found
        return None


class _SymbolTable:
    """Per-module qualname sets, built lazily for call resolution."""

    def __init__(self, parsed: dict[str, ParsedFile]):
        self._parsed = parsed
        self._quals: dict[str, dict[str, str]] = {}

    def quals(self, module_id: str) -> dict[str, str]:
        """qualname → kind for every symbol in *module_id*."""
        if module_id not in self._quals:
            self._quals[module_id] = {
                s.qualname: s.kind for s in self._parsed[module_id].symbols
            }
        return self._quals[module_id]


class _NameEnv:
    """One module's import bindings, resolved (ADR-007 rules 2 and 3)."""

    def __init__(self, module: ModuleInfo, facts: ParsedFile, index: _Index):
        self.module = module
        #: bound name → ("module", ModuleInfo) | ("symbol", ModuleInfo, name)
        self.bindings: dict[str, tuple] = {}
        self.resolved_imports: list[tuple] = []  # (import record, ModuleInfo)
        self.external_imports: list[tuple] = []  # (import record, top-level name)

        for imp in facts.imports:
            if isinstance(imp, PlainImport):
                self._plain(imp, index)
            elif isinstance(imp, FromImport):
                self._from(imp, index)

    def _plain(self, imp: PlainImport, index: _Index) -> None:
        resolved = index.resolve_prefix(self.module, imp.module)
        if resolved is None:
            self.external_imports.append((imp, imp.module.split(".")[0]))
            return
        self.resolved_imports.append((imp, resolved))
        if imp.alias:
            # `import a.b as c` binds c to the module a.b (or its best prefix).
            self.bindings[imp.alias] = ("module", resolved)
        # `import a.b` binds only `a`; dotted callees like a.b.f() are
        # resolved by full-path lookup in _resolve_call, no binding needed.

    def _from(self, imp: FromImport, index: _Index) -> None:
        base = self._absolute_base(imp)
        if base is None:
            return
        base_resolved = index.resolve_prefix(self.module, base) if base else None
        if base and base_resolved is None and imp.level == 0:
            self.external_imports.append((imp, base.split(".")[0]))
            return
        for name, bound in imp.names:
            if name == "*":
                if base_resolved is not None:
                    self.resolved_imports.append((imp, base_resolved))
                continue
            submodule = index.lookup(self.module, f"{base}.{name}" if base else name)
            if submodule is not None:
                self.resolved_imports.append((imp, submodule))
                self.bindings[bound] = ("module", submodule)
            elif base_resolved is not None:
                self.resolved_imports.append((imp, base_resolved))
                self.bindings[bound] = ("symbol", base_resolved, name)

    def _absolute_base(self, imp: FromImport) -> str | None:
        """Absolute dotted base of a from-import; None if it escapes the tree."""
        if imp.level == 0:
            return imp.module
        package_parts = self.module.import_name.split(".")
        if self.module.kind == "module":
            package_parts = package_parts[:-1]
        cut = len(package_parts) - (imp.level - 1)
        if cut < 0:
            return None
        parts = package_parts[:cut]
        if imp.module:
            parts += imp.module.split(".")
        return ".".join(parts)


def _resolve_call(
    module: ModuleInfo, call, env: _NameEnv, index: _Index, table: _SymbolTable
) -> str | None:
    """Resolve a call site to a symbol id, or None (ADR-007 rules 1–4)."""
    parts = call.callee.split(".")
    head = parts[0]

    if head == EXPR_RECEIVER:
        # C-80: the receiver is a call, a subscript or `super()` — a value
        # only a type checker can name. The site exists for the join;
        # the fallback has no rule for it and says nothing.
        return None

    # Rule 4: self.method() / cls.method() within the enclosing class.
    if head in _SELF_NAMES and len(parts) == 2 and call.scope:
        quals = table.quals(module.id)
        scope_parts = call.scope.split(".")
        for depth in range(len(scope_parts), 0, -1):
            prefix = ".".join(scope_parts[:depth])
            if quals.get(prefix) == "class" and f"{prefix}.{parts[1]}" in quals:
                return f"{module.id}.{prefix}.{parts[1]}"
        return None

    # Rule 1 and 2: bare name — local top-level symbol, or from-imported.
    if len(parts) == 1:
        quals = table.quals(module.id)
        if head in quals:
            return f"{module.id}.{head}"
        binding = env.bindings.get(head)
        if binding is not None and binding[0] == "symbol":
            _, target_module, name = binding
            if name in table.quals(target_module.id):
                return f"{target_module.id}.{name}"
        return None

    # Rule 3: dotted path through a repo module. Expand a module-bound head
    # (import alias or from-imported submodule), then split the dotted text
    # into (module import name, symbol qualname) at every point.
    binding = env.bindings.get(head)
    if binding is not None and binding[0] == "module":
        parts = binding[1].import_name.split(".") + parts[1:]
    for i in range(len(parts) - 1, 0, -1):
        target_module = index.lookup(module, ".".join(parts[:i]))
        if target_module is None:
            continue
        qualname = ".".join(parts[i:])
        if qualname in table.quals(target_module.id):
            return f"{target_module.id}.{qualname}"
    return None
