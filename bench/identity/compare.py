"""Compare two ingests' artifacts (ADR-184's gate).

    compare.py <before-dir> <after-dir>

Each of graph.json, tests.json and interfaces.json must be identical but
for graph.json's `built_by` (the checkout's path, version and dirty flag).
Prints IDENTICAL, or each top-level key that differs with a few of its
differing rows, and exits 1.
"""

import json
import sys
from pathlib import Path


def rows(value):
    return {json.dumps(row, sort_keys=True) for row in value}


def main(before: Path, after: Path) -> int:
    differs = False
    for name in ("graph.json", "tests.json", "interfaces.json"):
        a, b = before / name, after / name
        if not a.is_file() or not b.is_file():
            print(f"{name}: MISSING ({'before' if not a.is_file() else 'after'})")
            differs = True
            continue
        if a.read_bytes() == b.read_bytes():
            print(f"{name}: identical bytes")
            continue
        da, db = json.loads(a.read_text()), json.loads(b.read_text())
        if name == "graph.json":
            da.pop("built_by", None)
            db.pop("built_by", None)
        keys = sorted(k for k in set(da) | set(db) if da.get(k) != db.get(k))
        if not keys:
            print(f"{name}: identical but for built_by")
            continue
        differs = True
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
