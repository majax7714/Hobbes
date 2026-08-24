"""Observe brief sizes per unit from a stored change-spec, and measure the
P12 levers (2026-08-23) without re-deriving or spending a model.

    uv run scripts/brief_sizes.py <change-spec.yaml> [<change-spec.yaml> ...]

For each unit it renders the standing context (`agents.render_context`, the
metered thing) and reports total chars and the per-section breakdown, so the
brief's mass is visible. The contract-collapse and neighborhood-bound levers
live in `render_context`, so running this before/after a code change shows
the reduction directly. `--section` limits the breakdown to matching headers.
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hobbes.run import agents  # noqa: E402


def sections(text: str) -> list[tuple[str, int]]:
    out = []
    for m in re.finditer(r"(?ms)^(##+ [^\n]+)\n(.*?)(?=^##+ |\Z)", text):
        out.append((m.group(1).strip(), len(m.group(0))))
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("specs", nargs="+", type=Path)
    ap.add_argument("--section", default=None, help="only show sections whose header contains this")
    ap.add_argument("--top", type=int, default=4, help="largest N sections per unit")
    a = ap.parse_args(argv)
    grand = 0
    for path in a.specs:
        spec = yaml.safe_load(path.read_text())
        name = spec.get("task", path.parent.name)
        print(f"== {name}  ({len(spec.get('units', []))} units, {len(spec.get('contracts', []))} contracts)")
        for ctx in spec.get("contexts", []):
            unit = ctx["unit"]
            text = agents.render_context(spec, unit)
            total = len(text)
            grand += total
            secs = sections(text)
            if a.section:
                secs = [s for s in secs if a.section.lower() in s[0].lower()]
            top = sorted(secs, key=lambda s: -s[1])[: a.top]
            interior = len(ctx.get("modules", []))
            hood = len(ctx.get("neighborhood", []))
            bnd = len([c for c in spec.get("contracts", []) if unit in (c["from_unit"], c["to_unit"])])
            head = f"  {unit:4} {total:7,d} ch  interior={interior} boundary={bnd} hood_entries={hood}"
            print(head)
            for h, n in top:
                print(f"        {n:7,d}  {h[:60]}")
    print(f"total rendered context across all units/specs: {grand:,} chars")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
