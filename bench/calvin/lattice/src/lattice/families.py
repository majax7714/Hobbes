"""E3's draw rules, as they ran — the port `lattice e3 corpus` draws its members with.

**Source: `bench/calvin/e3-draw/`, the draw's scripts as they ran (copied there unchanged on
2026-09-26; the rule they were committed under is that directory's `DRAW-RULE.md`).** The figures the
pool is priced on were read by those scripts — 33,902 union tasks over the 40 taken repos, **24,222
unique** (`docs/calvin/calvin-experiments.md` §6, "E3's pool — the C lattice draw's record") — so the
corpus must select the *same* members, and that means the rules live here once, ported line for line,
rather than being restated.

What comes from where:

- **`count.py`** — `C_EXT`, `TEST_PARTS`, `VENDOR_PARTS`, `BODY_RATIO`, `BODY_CAP`, `tokens`,
  `classify_path`, `strip_comments`, `Repo` (the member set off `graph.json` and `tests.json`, each
  member's comment-stripped body, and the thin filter), `loose_groups` and `body_tokens`.
- **`measure.py`** — `isa_families`, `body_families` with its `PAIR_CAP` skip (a pair in which either
  body is over the cap is not computed, and the member is counted rather than sampled), `SCALAR` and
  `scalar_ref`.
- **`gate.py`** — `ISA`, `norm` and the tokeniser the ISA rule is written in, here `isa_tokens`: `_` and
  camelCase boundaries only, so `avx512vnni`, `adler32` and `sse41` each stay one token. It is **not**
  `tokens`, which splits a digit run off (`count.py`'s); both are ported because the draw used both.
- **`dedupe.py`** — `body_hash`, the sha1 of a whitespace-normalised body, which is the key a second
  copy of one body is found by, across repos in the taken order and inside one repo.

**Two deliberate differences, neither of which decides anything.** The drivers' paths and their output
are gone — no CLI, no `HERE`, nothing printed to stderr — and `count.py`'s census helpers (`canon`,
`strict_families`, `summarise`, `sample`, `run`, `calibrate_cells`) and `measure.py`'s reading helpers
(`two_axis`, `pair_reading`) are not ported: the corpus reads the union, not the count. Every rule that
decides whether a symbol is a member, whether its body is thin, and whether two members are one family
is here unchanged, and `tests/test_families.py` holds this module against those scripts on the same
synthetic clones.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

__all__ = [
    "BODY_CAP",
    "BODY_RATIO",
    "C_EXT",
    "ISA",
    "PAIR_CAP",
    "SCALAR",
    "TEST_PARTS",
    "VENDOR_PARTS",
    "Repo",
    "body_families",
    "body_hash",
    "body_tokens",
    "classify_path",
    "isa_families",
    "isa_tokens",
    "loose_groups",
    "norm",
    "scalar_ref",
    "strip_comments",
    "tokens",
]

#: count.py: a member is defined in a file with one of these extensions.
C_EXT = {".c", ".h", ".cc", ".cpp", ".cxx", ".c++", ".hpp", ".hh", ".hxx", ".h++", ".inl", ".ipp", ".tpp", ".inc"}
#: count.py: a path part (or a file stem) that makes the file a test's, and one that makes it vendored.
TEST_PARTS = {"test", "tests", "testing", "unittest", "unittests", "gtest", "gmock", "googletest", "googlemock",
              "fuzz", "fuzzing", "fuzzer", "benchmark", "benchmarks", "bench", "examples", "example"}
VENDOR_PARTS = {"third_party", "thirdparty", "third-party", "vendor", "vendored", "external", "extern", "deps",
                "libs", "3rdparty", "contrib", "unity"}
#: count.py: the body-shape rule's similarity bar, and the group size above which no pair is compared.
BODY_RATIO = 0.6
BODY_CAP = 64
#: measure.py: body tokens; a pair in which either side is over this is not computed (cost only).
PAIR_CAP = 20_000
#: measure.py: the words a scalar reference sibling is spelled with.
SCALAR = {"c", "scalar", "generic", "ref", "reference", "serial", "portable", "plain", "fallback", "cpu", "naive"}
#: gate.py: the ISA tokens the lattice rule is fixed on.
ISA = set("sse sse2 sse3 ssse3 sse41 sse42 avx avx2 avx512 avx512f avx512bw avx512vl avx512dq avx512vnni "
          "avx512fp16 avx512bf16 avxvnni neon asimd sve sve2 rvv altivec vsx vmx power8 power9 wasm simd128 "
          "lsx lasx msa".split())

_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+[0-9]*|[A-Z]+[0-9]*|[0-9]+[a-z0-9]*")
_CTOK = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|[0-9][0-9A-Za-z_.]*|\S")
# gate.py's: `_` and camelCase boundaries only (the rule's wording), so a digit-to-letter run is not split
_ISA_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z0-9]+")


def tokens(name: str) -> tuple[str, ...]:
    """count.py's tokeniser: `_` and camelCase, lowercased, a digit run split off its letters."""
    out: list[str] = []
    for part in name.split("_"):
        if not part:
            continue
        out.extend(m.group(0).lower() for m in _CAMEL.finditer(part))
    return tuple(out)


def norm(name: str) -> str:
    """gate.py: `sse4_1` and `avx512_vnni` written as the one token the ISA list spells."""
    name = re.sub(r"(?i)sse4_([12])", lambda m: "sse4" + m.group(1), name)
    name = re.sub(r"(?i)avx512_([A-Za-z0-9]+)", lambda m: "avx512" + m.group(1), name)
    return name


def isa_tokens(name: str) -> tuple[str, ...]:
    """gate.py's tokeniser, the one the ISA rule is written in: no digit-to-letter split."""
    out: list[str] = []
    for part in norm(name).split("_"):
        if part:
            out.extend(m.group(0).lower() for m in _ISA_CAMEL.finditer(part))
    return tuple(out)


def classify_path(path: str) -> str | None:
    """`test`, `vendor` or None, from the path's directory parts and its file name."""
    parts = [p.lower() for p in Path(path).parts]
    stem = Path(path).stem.lower()
    if any(p in VENDOR_PARTS for p in parts[:-1]):
        return "vendor"
    if any(p in TEST_PARTS for p in parts[:-1]) or stem.startswith("test_") or stem.endswith("_test") \
            or stem.endswith("_unittest") or stem.startswith("test"):
        return "test"
    return None


def strip_comments(text: str) -> str:
    """Comments out, string literals emptied — the text a body is tokenised and hashed from."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    return text


def body_hash(body: str | None) -> str:
    """dedupe.py's key: the sha1 of the whitespace-normalised body."""
    return hashlib.sha1(" ".join((body or "").split()).encode()).hexdigest()


class Repo:
    """count.py's member set for one ingested clone: the symbols, their bodies and the thin filter.

    `graph.json` (schema v4) and `tests.json` under `<root>/.hobbes/derived/`. A member is a symbol of
    kind function or method, defined in a C or C++ file by extension, outside a test or vendored path,
    whose name has at least two tokens. Each member carries `body` (the text between its braces,
    comments stripped), `toks`, `path`, `line`, `end_line`, `calls` (callee names, `sem` and `all`) and
    `thin`.
    """

    def __init__(self, name: str, root: Path):
        self.name, self.root = name, root
        derived = root / ".hobbes" / "derived"
        g = json.loads((derived / "graph.json").read_text(encoding="utf-8"))
        self.sha = g.get("sha")
        self.version = (g.get("built_by") or {}).get("version")
        self.languages = g.get("languages")
        mod_path = {n["id"]: n.get("path") for n in g["nodes"] if n.get("kind") == "module" and n.get("path")}
        test_files: set[str] = set()
        tj = derived / "tests.json"
        reached: set[str] = set()
        if tj.exists():
            t = json.loads(tj.read_text(encoding="utf-8"))
            for row in t.get("tests") or []:
                if row.get("file"):
                    test_files.add(row["file"])
                reached.update(row.get("reaches") or [])
        self.reached = reached
        self.excluded = Counter()
        self.members: dict[str, dict] = {}
        name_of = {s["id"]: s["name"] for s in g["symbols"]}
        for s in g["symbols"]:
            if s.get("kind") not in ("function", "method"):
                continue
            path = mod_path.get(s.get("module"))
            if not path or Path(path).suffix.lower() not in C_EXT:
                self.excluded["not-c-file"] += 1
                continue
            cls = "test" if path in test_files else classify_path(path)
            if cls:
                self.excluded[cls] += 1
                continue
            toks = tokens(s["name"])
            if len(toks) < 2:
                self.excluded["one-token-name"] += 1
                continue
            self.members[s["id"]] = {"id": s["id"], "name": s["name"], "qualname": s.get("qualname"),
                                     "path": path, "line": s.get("line"), "end_line": s.get("end_line"),
                                     "toks": toks, "calls": {"sem": [], "all": []}}
        for e in g["symbol_edges"]:
            if e.get("type") != "calls":
                continue
            m = self.members.get(e["from"])
            if m is None:
                continue
            callee = name_of.get(e["to"], e["to"].split(".")[-1])
            m["calls"]["all"].append(callee)
            if e.get("tier") == "semantic":
                m["calls"]["sem"].append(callee)
        del g
        self._files: dict[str, list[str]] = {}
        for m in self.members.values():
            m["body"] = self._body(m)
            m["thin"] = self._thin(m)

    def _lines(self, path: str) -> list[str]:
        if path not in self._files:
            try:
                self._files[path] = (self.root / path).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                self._files[path] = []
        return self._files[path]

    def _body(self, m: dict) -> str | None:
        lines = self._lines(m["path"])
        if not lines or not m["line"] or not m["end_line"]:
            return None
        text = strip_comments("\n".join(lines[m["line"] - 1: m["end_line"]]))
        a, b = text.find("{"), text.rfind("}")
        if a < 0 or b <= a:
            return None
        return text[a + 1: b]

    def _thin(self, m: dict) -> bool:
        body = m["body"]
        if body is None:
            return True
        nonblank = [l for l in body.splitlines() if l.strip()]
        if len(nonblank) <= 2:
            return True
        if body.count(";") <= 1 and len(m["calls"]["all"]) <= 1:
            return True
        return False


def loose_groups(members: list[dict]) -> dict[tuple, list[dict]]:
    """count.py: names of the same token count differing at exactly one position, that position wildcarded.

    A group is kept only where at least two distinct values appear at the varying position.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for m in members:
        t = m["toks"]
        for i in range(len(t)):
            groups[(len(t), i, t[:i] + ("*",) + t[i + 1:])].append(m)
    return {k: v for k, v in groups.items() if len({m["toks"][k[1]] for m in v}) >= 2}


def body_tokens(m: dict, vary: str) -> list[str]:
    """count.py: the body's C tokens, the member's varying token masked — also inside identifiers."""
    out = []
    for t in _CTOK.findall(m["body"] or ""):
        if vary and len(vary) > 1 and vary in t.lower():
            t = re.sub(re.escape(vary), "*", t, flags=re.I)
        out.append(t)
    return out


def isa_families(members: list[dict]) -> list[dict]:
    """measure.py: names differing at one position which holds an ISA token, over the given members."""
    groups = defaultdict(list)
    for m in members:
        t = isa_tokens(m["name"])
        for i, tok in enumerate(t):
            if tok in ISA:
                groups[(len(t), i, t[:i] + ("*",) + t[i + 1:])].append(m)
    return [{"key": k, "members": ms} for k, ms in groups.items()
            if len({isa_tokens(m["name"])[k[1]] for m in ms}) >= 2]


def body_families(groups):
    """measure.py: `count.body_families` line for line, plus the PAIR_CAP skip (`skipped_size`).

    Single linkage over a loose group: two members are linked where their body token sequences, the
    varying token masked, have a `SequenceMatcher` ratio at or above `BODY_RATIO`, with both exact
    upper-bound prefilters first. A group over `BODY_CAP` members is not compared at all.
    """
    fams, skipped, skipped_size = [], 0, {}
    for key, ms in groups.items():
        if len(ms) > BODY_CAP:
            skipped += 1
            continue
        i = key[1]
        toks = [body_tokens(m, m["toks"][i]) for m in ms]
        parent = list(range(len(ms)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for a in range(len(ms)):
            if ms[a]["body"] is None:
                continue
            for b in range(a + 1, len(ms)):
                if ms[b]["body"] is None or ms[a]["toks"][i] == ms[b]["toks"][i]:
                    continue
                sm = difflib.SequenceMatcher(None, toks[a], toks[b], autojunk=False)
                if sm.real_quick_ratio() < BODY_RATIO or sm.quick_ratio() < BODY_RATIO:
                    continue
                if len(toks[a]) > PAIR_CAP or len(toks[b]) > PAIR_CAP:
                    for x in (a, b):
                        if len(toks[x]) > PAIR_CAP:
                            skipped_size[ms[x]["id"]] = len(toks[x])
                    continue
                if sm.ratio() >= BODY_RATIO:
                    parent[find(a)] = find(b)
        comp = defaultdict(list)
        for x in range(len(ms)):
            comp[find(x)].append(ms[x])
        for sub in comp.values():
            if len({m["toks"][i] for m in sub}) >= 2:
                fams.append({"key": key, "members": sub, "empty": False})
    return fams, skipped, skipped_size


def scalar_ref(m: dict, pos: int, all_names: set) -> bool:
    """measure.py: whether the member has a sibling with its ISA token dropped, or a scalar word there."""
    t = isa_tokens(m["name"])
    rest = t[:pos] + t[pos + 1:]
    if rest in all_names:
        return True
    return any(t[:pos] + (s,) + t[pos + 1:] in all_names for s in SCALAR)
