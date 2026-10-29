"""Compare two ingests' artifacts (ADR-184's gate).

    compare.py <before-dir> <after-dir>

Each of graph.json, tests.json and interfaces.json must be the same
bytes but for the value of graph.json's `built_by` (the checkout's path,
version and dirty flag), which is masked in both. The same JSON in
different bytes (key order, number form) differs. A pass that run.sh
recorded as failed (a non-zero `exit`) differs whatever its directory
holds. Prints IDENTICAL, or what differs, with a few of a key's differing
rows, and exits 1.
"""

import json
import sys
from pathlib import Path


def rows(value):
    return {json.dumps(row, sort_keys=True) for row in value}


def masked(raw: str) -> str:
    """*raw* with the value of its top-level `built_by` cut out, if any."""
    at = raw.find('"built_by"')
    if at < 0:
        return raw
    start = raw.index(":", at) + 1
    while raw[start].isspace():
        start += 1
    _, end = json.JSONDecoder().raw_decode(raw, start)
    return raw[:start] + raw[end:]


def failed(arm: Path) -> str | None:
    code = (arm / "exit").read_text().strip() if (arm / "exit").is_file() else "0"
    return None if code == "0" else code


def main(before: Path, after: Path) -> int:
    differs = False
    for arm, label in ((before, "before"), (after, "after")):
        code = failed(arm)
        if code is not None:
            print(f"the {label} pass failed (exit {code}): nothing it left is compared")
            differs = True
    if differs:
        print("DIFFERS")
        return 1
    for name in ("graph.json", "tests.json", "interfaces.json"):
        a, b = before / name, after / name
        if not a.is_file() or not b.is_file():
            print(f"{name}: MISSING ({'before' if not a.is_file() else 'after'})")
            differs = True
            continue
        if a.read_bytes() == b.read_bytes():
            print(f"{name}: identical bytes")
            continue
        if name == "graph.json" and masked(a.read_text()) == masked(b.read_text()):
            print(f"{name}: identical bytes but for built_by")
            continue
        differs = True
        da, db = json.loads(a.read_text()), json.loads(b.read_text())
        if name == "graph.json":
            da.pop("built_by", None)
            db.pop("built_by", None)
        keys = sorted(k for k in set(da) | set(db) if da.get(k) != db.get(k))
        if not keys:
            print(f"{name}: the same JSON in different bytes (key order or number form)")
            continue
        for key in keys:
            va, vb = da.get(key), db.get(key)
            if isinstance(va, list) and isinstance(vb, list):
                ra, rb = rows(va), rows(vb)
                print(f"{name} {key}: -{len(ra - rb)} +{len(rb - ra)}")
                for row in sorted(ra - rb)[:3]:
                    print(f"  - {row[:240]}")
                for row in sorted(rb - ra)[:3]:
                    print(f"  + {row[:240]}")
            else:
                print(f"{name} {key}: {json.dumps(va)[:240]} -> {json.dumps(vb)[:240]}")
    print("DIFFERS" if differs else "IDENTICAL")
    return 1 if differs else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
