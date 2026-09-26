"""E3's draw, gates 1-4 and 6 (DRAW-RULE.md), per repo, resumable: gates/<owner>__<name>.json.

Run under the lattice project: uv run --project <repo>/bench/calvin/lattice python gate.py [workers]
"""
import json, os, re, shutil, subprocess, sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from lattice.scan import scan, ScanError

HERE = Path(__file__).resolve().parent
REPOS = HERE / "repos"
GATES = HERE / "gates"
MAX_FILE = 2_000_000  # a file above 2 MB is not scanned (generated tables); counted per repo

EXCL_TEST = {"test", "tests", "bench", "benchmark", "benchmarks", "example", "examples"}
EXCL_VENDOR = {"third_party", "thirdparty", "3rdparty", "vendor", "deps", "external", "extern", "contrib"}
ISA = set("sse sse2 sse3 ssse3 sse41 sse42 avx avx2 avx512 avx512f avx512bw avx512vl avx512dq avx512vnni "
          "avx512fp16 avx512bf16 avxvnni neon asimd sve sve2 rvv altivec vsx vmx power8 power9 wasm simd128 "
          "lsx lasx msa".split())
# `_` and camelCase boundaries only (the rule's wording): a digit-to-letter run is not split, so
# `avx512vnni`, `adler32` and `sse41` stay one token.
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z0-9]+")
CPP = {".cc", ".cpp", ".cxx", ".hpp"}
CEXT = {".c", ".h"}


def norm(name: str) -> str:
    name = re.sub(r"(?i)sse4_([12])", lambda m: "sse4" + m.group(1), name)
    name = re.sub(r"(?i)avx512_([A-Za-z0-9]+)", lambda m: "avx512" + m.group(1), name)
    return name


def tokens(name: str) -> tuple:
    out = []
    for part in norm(name).split("_"):
        if part:
            out.extend(m.group(0).lower() for m in _CAMEL.finditer(part))
    return tuple(out)


def excluded(rel: Path) -> bool:
    parts = [p.lower() for p in rel.parts[:-1]]
    return any(p in EXCL_TEST or p in EXCL_VENDOR for p in parts)


def isa_families(names: set) -> dict:
    groups = defaultdict(set)
    for n in names:
        t = tokens(n)
        for i, tok in enumerate(t):
            if tok in ISA:
                groups[(len(t), i, t[:i] + ("*",) + t[i + 1:])].add(n)
    fams = {}
    for k, ms in groups.items():
        isas = {tokens(n)[k[1]] for n in ms}
        if len(isas) >= 2:
            fams[" ".join(k[2])] = sorted(ms)
    return fams


LIC_TESTS = {
    "MIT": lambda t: "permission is hereby granted, free of charge" in t,
    "Apache-2.0": lambda t: "apache license" in t and "version 2.0" in t,
    "BSD-3-Clause": lambda t: "redistribution and use" in t and ("neither the name" in t or "endorse or promote" in t),
    "BSD-2-Clause": lambda t: "redistribution and use" in t and "neither the name" not in t and "endorse or promote" not in t,
    "Unlicense": lambda t: "free and unencumbered software released into the public domain" in t,
    "Zlib": lambda t: "provided 'as-is'" in t.replace("‘", "'").replace("’", "'") and "plainly marked" in t,
    "CC0-1.0": lambda t: "cc0" in t or "creative commons zero" in t or "commons legal code" in t,
    "ISC": lambda t: "permission to use, copy, modify, and/or distribute this software" in t and "provided that the above copyright notice" in t,
    "BSL-1.0": lambda t: "boost software license" in t,
    "0BSD": lambda t: "permission to use, copy, modify, and/or distribute this software" in t and "provided that" not in t,
}


def licence_ok(root: Path, spdx: str, sources: list) -> tuple:
    test = LIC_TESTS.get(spdx)
    if test is None:
        return False, f"spdx {spdx!r} not in the rule's list"
    files = [p for p in root.iterdir() if p.is_file() and re.match(r"(?i)(licen[cs]e|copying)", p.name)]
    for f in files:
        t = " ".join(f.read_text(errors="replace").lower().split())
        if test(t):
            return True, f"file {f.name}"
    tagged = 0
    for s in sources:
        try:
            head = s.read_text(errors="replace")[:4000]
        except OSError:
            continue
        m = re.search(r"SPDX-License-Identifier:\s*([^\n*]+)", head)
        if m and spdx.lower() in m.group(1).lower():
            tagged += 1
    if sources and tagged * 2 > len(sources):
        return True, f"spdx headers {tagged}/{len(sources)}"
    return False, f"no licence text agreeing with {spdx} ({[f.name for f in files] or 'no licence file'}; spdx headers {tagged}/{len(sources)})"


def gate(repo: dict) -> dict:
    name = repo["full_name"]
    out = {"full_name": name, "spdx": repo["spdx"], "stars": repo["stars"]}
    if repo["fork"] or repo["archived"]:
        return {**out, "passed": False, "gate": 1, "reason": "fork" if repo["fork"] else "archived"}
    if repo["owner"].lower() == "sqliteai" or "sqlite-vector" in name.lower():
        return {**out, "passed": False, "gate": 2, "reason": "sqlite-vector / sqliteai"}
    dest = REPOS / name.replace("/", "__")
    if not dest.exists():
        r = subprocess.run(["git", "clone", "-q", "--depth", "1", "--single-branch",
                            f"https://github.com/{name}.git", str(dest)],
                           capture_output=True, text=True, timeout=1800,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        if r.returncode != 0:
            shutil.rmtree(dest, ignore_errors=True)
            return {**out, "passed": False, "gate": 0, "reason": f"clone failed: {r.stderr.strip()[-200:]}"}
    try:
        sha = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        out["sha"] = sha
        files = [p for p in dest.rglob("*") if p.is_file() and ".git" not in p.relative_to(dest).parts]
        # gate 2: the target's text
        for p in files:
            if p.suffix.lower() in CEXT | CPP | {".md", ".txt", ".py", ".json", ".cmake", ".mk", ""} or p.name == "Makefile":
                try:
                    t = p.read_text(errors="ignore")
                except OSError:
                    continue
                if "sqlite-vector" in t or ("distance_function_t" in t and "dispatch_distance_table" in t):
                    return _drop(dest, {**out, "passed": False, "gate": 2, "reason": f"target text in {p.relative_to(dest)}"})
        # gate 6: C++ by majority
        ncpp = sum(1 for p in files if p.suffix.lower() in CPP)
        nc = sum(1 for p in files if p.suffix.lower() in CEXT)
        out["files"] = {"c_h": nc, "cpp": ncpp}
        if ncpp > nc:
            return _drop(dest, {**out, "passed": False, "gate": 6, "reason": f"C++ by majority ({ncpp} C++ against {nc} C)"})
        sources = [p for p in files if p.suffix.lower() in CEXT]
        # gate 3: licence
        ok, why = licence_ok(dest, repo["spdx"], sources)
        out["licence"] = why
        if not ok:
            return _drop(dest, {**out, "passed": False, "gate": 3, "reason": why})
        # gate 4: the ISA lattice
        names, big, errors = set(), 0, 0
        for p in sources:
            rel = p.relative_to(dest)
            if excluded(rel):
                continue
            if p.stat().st_size > MAX_FILE:
                big += 1
                continue
            try:
                res = scan(p.read_text(encoding="utf-8", errors="replace"))
            except (ScanError, RecursionError, ValueError):
                errors += 1
                continue
            names.update(f.name for f in res.functions)
        fams = isa_families(names)
        members = {n for ms in fams.values() for n in ms}
        out.update({"definitions": len(names), "isa_families": len(fams), "isa_members": len(members),
                    "skipped_big": big, "scan_errors": errors})
        if len(fams) < 3 or len(members) < 8:
            return _drop(dest, {**out, "passed": False, "gate": 4,
                                "reason": f"ISA lattice too small ({len(fams)} families, {len(members)} members)"})
        out["families"] = fams
        return {**out, "passed": True, "gate": None, "reason": "passes 1-4, 6"}
    except Exception as e:  # a repo the gate cannot read is passed over, with its error
        return _drop(dest, {**out, "passed": False, "gate": 0, "reason": f"gate error: {type(e).__name__}: {e}"[:300]})


def _drop(dest: Path, result: dict) -> dict:
    shutil.rmtree(dest, ignore_errors=True)
    return result


def main():
    GATES.mkdir(exist_ok=True)
    REPOS.mkdir(exist_ok=True)
    pool = json.load(open(HERE / "pool.json"))
    todo = [r for r in pool["repos"] if not (GATES / (r["full_name"].replace("/", "__") + ".json")).exists()]
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(gate, r): r for r in todo}
        for i, f in enumerate(as_completed(futs)):
            r = futs[f]
            try:
                res = f.result()
            except Exception as e:
                res = {"full_name": r["full_name"], "passed": False, "gate": 0, "reason": f"worker error: {e}"[:300]}
            (GATES / (r["full_name"].replace("/", "__") + ".json")).write_text(json.dumps(res, indent=1))
            print(f"{i+1}/{len(todo)} {r['full_name']}: {res['reason'][:100]}", flush=True)


if __name__ == "__main__":
    main()
