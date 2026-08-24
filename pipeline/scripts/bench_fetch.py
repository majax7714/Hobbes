# /// script
# requires-python = ">=3.12"
# dependencies = ["datasets>=3"]
# ///
"""Export a Hugging Face SWE-bench-style dataset split to JSONL for
``hobbes bench`` (ADR-055).

    uv run pipeline/scripts/bench_fetch.py princeton-nlp/SWE-bench_Verified test out.jsonl

Kept out of the pipeline's dependencies on purpose: the harness reads
a local file, and the only thing that needs the ``datasets`` library is
this one-off export. Every row is written as-is; the instance protocol
(``hobbes bench select``) does the filtering, with the drops counted.
"""

import json
import sys

from datasets import load_dataset


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    name, split, out = argv[1:]
    rows = load_dataset(name, split=split)
    with open(out, "w") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row)) + "\n")
    print(f"wrote {len(rows)} instances from {name}:{split} to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
