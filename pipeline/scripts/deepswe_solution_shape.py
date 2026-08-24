"""Solution-shape diff (C-56): how alike are two arms' patches, and how alike
is either to a known library implementation? High similarity to a library
is a recall flag (the `0.19.0` string, generalised); two arms converging on
one shape says the shape is in the model, not in the context.

    uv run scripts/deepswe_solution_shape.py <patch-or-file> <patch-or-file> [...] [--ref path ...]

Every argument is a `.patch` (its added lines are taken) or a source file
(all lines). Prints the pairwise matrix of: difflib ratio on normalised
lines, and the fraction of A's distinct non-trivial lines that appear
verbatim in B. Computes; does not interpret.
"""
import argparse
import difflib
import re
import sys
from pathlib import Path

TRIVIAL = re.compile(r"^(\s*|[\[\]{}()]+|return|else:|try:|pass|continue|break|\"\"\"|#.*|import .*|from .* import .*)$")


def lines_of(p: Path) -> list[str]:
    text = p.read_text(errors="replace")
    if p.suffix == ".patch" or text.startswith("diff --git"):
        out = [ln[1:] for ln in text.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    else:
        out = text.splitlines()
    return [ln.strip() for ln in out]


def nontrivial(lines: list[str]) -> set[str]:
    return {ln for ln in lines if len(ln) >= 12 and not TRIVIAL.match(ln)}


def compare(a: list[str], b: list[str]) -> tuple[float, float]:
    ratio = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    na, nb = nontrivial(a), nontrivial(b)
    shared = len(na & nb) / max(1, len(na))
    return round(ratio, 3), round(shared, 3)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("items", nargs="+", type=Path); ap.add_argument("--ref", action="append", type=Path, default=[])
    a = ap.parse_args(argv)
    names = [p.name if p.suffix == ".patch" else p.name for p in a.items] + [f"ref:{p.name}" for p in a.ref]
    bodies = [lines_of(p) for p in a.items] + [lines_of(p) for p in a.ref]
    for i, p in enumerate(names):
        print(f"[{i}] {p}: {len(bodies[i])} lines, {len(nontrivial(bodies[i]))} non-trivial")
    print("\npair            ratio  A-lines-in-B")
    for i in range(len(bodies)):
        for j in range(len(bodies)):
            if i != j:
                r, s = compare(bodies[i], bodies[j])
                print(f"[{i}]→[{j}]         {r:.3f}  {s:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
