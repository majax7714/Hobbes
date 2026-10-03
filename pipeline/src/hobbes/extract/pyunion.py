"""Which Python method calls sit on a union-typed receiver (ADR-168, C-184).

scip-python answers ``x.m()`` on a receiver whose declared type is a union
with the *first* member that declares ``m``, and the join drew that answer
at ``semantic`` certainty: icalendar's ``VPROPERTY = vAdr | vBoolean | …``
made ``component['TZOFFSETFROM'].to_ical()`` an edge to ``vAdr.to_ical``.
Any one member is one possible dispatch presented as the resolved one, so
the site is ``union-member``: the join vetoes lane B and draws nothing, as
ADR-104 does for TypeScript.

Grammar-free (I-4): it reads :class:`~hobbes.extract.pysource.TypeFacts`,
which :mod:`pysource` collected. Everything is by name across the repo, and
every read fails toward *no* decision: a class name defined twice, an
annotation lane A cannot read, or two reads of one name that disagree leave
the site as it was, lane B's answer standing.
"""

from __future__ import annotations

from collections import defaultdict

from hobbes.extract.pysource import UNREAD_TYPE, ParsedFile


class _Repo:
    def __init__(self, facts: list) -> None:
        self.classes: dict[str, list[tuple[tuple[str, ...], tuple[str, ...]]]] = defaultdict(list)
        self.aliases: dict[str, list[object]] = defaultdict(list)
        self.attributes: dict[str, list[object]] = defaultdict(list)
        self.returns: dict[str, list[object]] = defaultdict(list)
        self.getitems: list[object] = []
        for tf in facts:
            for name, methods, bases in tf.classes:
                self.classes[name].append((methods, bases))
            for name, value in tf.aliases:
                self.aliases[name].append(value)
            for name, value in tf.attributes:
                self.attributes[name].append(value)
            for name, value in tf.returns:
                self.returns[name].append(value)
            self.getitems.extend(tf.getitems)

    def members(self, typ: object, seen: tuple[str, ...] = ()) -> list[str] | None:
        """The in-repo classes *typ* reads as, or None when any part is not one."""
        if typ == UNREAD_TYPE:
            return None
        if isinstance(typ, str):
            if typ == "None":
                return []
            if typ in self.aliases and typ not in seen:
                values = self.aliases[typ]
                return self.members(values[0], (*seen, typ)) if len(values) == 1 else None
            return [typ] if len(self.classes.get(typ, ())) == 1 else None
        if isinstance(typ, tuple) and len(typ) == 2 and typ[0] == "|":
            out: list[str] = []
            for part in typ[1]:
                found = self.members(part, seen)
                if found is None:
                    return None
                out += found
            return out
        return None

    def union(self, reads: list[object]) -> tuple[str, ...] | None:
        """The union every read agrees on, of two or more in-repo classes."""
        found = [self.members(r) for r in reads]
        if not found or any(f is None for f in found):
            return None
        distinct = {tuple(sorted(set(f))) for f in found}
        if len(distinct) != 1:
            return None
        members = next(iter(distinct))
        return members if len(members) >= 2 else None

    def holder(self, cls: str, method: str, seen: tuple[str, ...] = ()) -> str | None:
        """The class whose own def of *method* an instance of *cls* runs."""
        defs = self.classes.get(cls, ())
        if len(defs) != 1:
            return None
        methods, bases = defs[0]
        if method in methods:
            return cls
        for base in bases:
            if base not in seen:
                found = self.holder(base, method, (*seen, cls))
                if found is not None:
                    return found
        return None

    def receiver_union(self, how: str, key: object) -> tuple[str, ...] | None:
        if how == "param":
            return self.union([key])
        if how in ("local", "result"):
            return self.union(self.returns[key]) if key in self.returns else None
        if how == "attribute":
            return self.union(self.attributes[key]) if key in self.attributes else None
        if how == "subscript":
            # Lane A cannot tell which class is subscripted: every union an
            # in-repo `__getitem__` returns is a candidate.
            found = {m for r in self.getitems if (u := self.union([r])) for m in u}
            return tuple(sorted(found)) if len(found) >= 2 else None
        return None


def union_member_sites(modules, parsed: dict[str, ParsedFile]) -> set[tuple[str, int, int]]:
    """``(path, line, col)`` of each method call whose receiver reads as a
    union of in-repo classes two or more of which declare the method with
    distinct defs. ``line``/``col`` are the method name's, the call site's."""
    repo = _Repo([parsed[m.id].type_facts for m in modules])
    out: set[tuple[str, int, int]] = set()
    for module in modules:
        for read in parsed[module.id].type_facts.receivers:
            members = repo.receiver_union(read.how, read.key)
            if members is None:
                continue
            holders = {repo.holder(c, read.method) for c in members} - {None}
            if len(holders) >= 2:
                out.add((module.path, read.line, read.col))
    return out
