#!/usr/bin/env sh
# One command per cell (ADR-089, design §9): ingest the repo with lane B,
# export the Hobbes edges of one Go module, run the Go RTA oracle on it,
# grade, and leave hobbes.json / oracle.json / report.json / report.txt
# in the output directory.
#
#   bench/oracle/run-cell.sh <repo> <module-dir> <out-dir> [--no-ingest]
#
# <module-dir> is repo-relative ("." for a single-module repo). Pass
# --no-ingest to grade an existing .hobbes/derived/graph.json. Runtime is
# printed at the end so every cell's cost is on the record.
set -eu
repo=$(cd "$1" && pwd); module=$2; out=$3; shift 3
ingest=1; [ "${1:-}" = "--no-ingest" ] && ingest=0
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
mkdir -p "$out"; out=$(cd "$out" && pwd)
start=$(date +%s)
if [ "$ingest" = 1 ]; then
  (cd "$root/pipeline" && HOBBES_SCIP=1 uv run hobbes ingest --repo "$repo")
fi
(cd "$here" && go build -o "$out/oracle" ./cmd/oracle)
"$out/oracle" export --graph "$repo/.hobbes/derived/graph.json" --module "$module" --out "$out/hobbes.json"
"$out/oracle" go-rta --repo "$repo" --module "$module" --out "$out/oracle.json"
"$out/oracle" grade --hobbes "$out/hobbes.json" --oracle "$out/oracle.json" --json "$out/report.json" | tee "$out/report.txt"
echo "cell $module of $repo: $(( $(date +%s) - start ))s" | tee -a "$out/report.txt"
