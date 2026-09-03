"""Does a trained prior override the text in the prompt? (review item 8, 2026-09-03)

    uv run scripts/ttt_override_probe.py <repo> <corpus-dir> <nav-run.json> [--family tests] [--heavy 0.5]

For the run's has-truth items of a family, joins every zero-score reply
that names nothing to the symbol's module and to how often that module's
training answers in the family were "none recorded" — the ∅ shape.
Prints the counts (`hobbes.ttt.report.override_probe`); the reading is
preregistered in `benchmark-hypotheses.md` § Follow-ups, item 8.
Computes; does not interpret.
"""
import argparse
import json
import sys
from pathlib import Path

from hobbes import artifacts
from hobbes.ttt.report import none_density, override_probe


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", type=Path); ap.add_argument("corpus", type=Path); ap.add_argument("run", type=Path)
    ap.add_argument("--family", default="tests"); ap.add_argument("--heavy", type=float, default=0.5)
    a = ap.parse_args(argv)
    graph = artifacts.load_graph(a.repo)
    module_of = {s["id"]: s.get("module", "") for s in graph.get("symbols", [])}
    train = [json.loads(ln) for ln in (a.corpus / "train.jsonl").read_text().splitlines() if ln.strip()]
    density = none_density(train, a.family, module_of)
    out = override_probe(json.loads(a.run.read_text()), a.family, density, module_of, a.heavy)
    out["modules"] = len(density)
    out["training_none_share"] = round(sum(x for x, _ in density.values()) / max(1, sum(y for _, y in density.values())), 4)
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
