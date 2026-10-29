#!/usr/bin/env bash
# ADR-184's gate: a speed change leaves every artifact byte-identical.
#
#   run.sh <out> <before-checkout> <after-checkout> <cells.txt> [extra env, e.g. HOBBES_TS_JOBS=1]
#
# Each cell (one path per line of cells.txt; `#` comments) is ingested by
# the before checkout and then the after one, one pass at a time, with the
# index cache off in both: a fresh index is what a version bump sees. The
# three artifacts are cleared before each pass and copied out after it,
# and compare.py compares their bytes with `built_by`'s value masked. A
# pass that exits non-zero is recorded as failed (`exit` beside its
# artifacts), and the comparison fails with it. Each pass's wall time and
# peak RSS (GNU time) and its timings summary are kept beside them.
# CONTROL=1 ingests the before checkout a second time (`control`) and
# compares it with the first: a difference the control shows too is the
# run's (a registered nondeterminism, C-149), not the change's.
# A checkout needs its scip/ and tsextract/ node_modules *copied*, not
# linked (a linked node_modules breaks lane B in the container).
set -u
OUT=${1:?out dir}; BEFORE=${2:?before checkout}; AFTER=${3:?after checkout}; CELLS=${4:?cells.txt}
shift 4
mkdir -p "$OUT"; OUT=$(cd "$OUT" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
SUM=$OUT/summary.tsv
printf 'cell\tarm\texit\twall_s\tpeak_rss_mb\n' > "$SUM"
while IFS= read -r cell; do
  case "$cell" in ''|'#'*) continue;; esac
  cell=${cell/#\~/$HOME}
  name=$(basename "$cell")
  arms="before after"; [ "${CONTROL:-0}" = 1 ] && arms="before control after"
  for arm in $arms; do
    root=$BEFORE; [ "$arm" = after ] && root=$AFTER
    dir=$OUT/$name/$arm; mkdir -p "$dir"
    # A pass that writes nothing must not be compared as the last pass's
    # output.
    rm -f "$cell"/.hobbes/derived/{graph,tests,interfaces}.json "$dir"/{graph,tests,interfaces}.json
    (cd "$root/pipeline" && env HOBBES_INDEX_CACHE=0 "$@" /usr/bin/time -v -o "$dir/time.txt" \
      uv run hobbes ingest --repo "$cell") > "$dir/ingest.log" 2>&1
    code=$?
    echo "$code" > "$dir/exit"
    for f in graph tests interfaces; do cp "$cell/.hobbes/derived/$f.json" "$dir/" 2>/dev/null; done
    wall=$(awk -F': ' '/Elapsed \(wall clock\)/{print $2}' "$dir/time.txt" | awk -F: '{ if (NF==3) print $1*3600+$2*60+$3; else print $1*60+$2 }')
    rss=$(awk -F': ' '/Maximum resident/{printf "%d", $2/1024}' "$dir/time.txt")
    printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$arm" "$code" "$wall" "$rss" >> "$SUM"
    echo "$name $arm exit=$code ${wall}s ${rss}MB"
  done
  python3 -I "$HERE/compare.py" "$OUT/$name/before" "$OUT/$name/after" | tee "$OUT/$name/compare.txt"
  if [ "${CONTROL:-0}" = 1 ]; then
    echo "-- control (before against before):"
    python3 -I "$HERE/compare.py" "$OUT/$name/before" "$OUT/$name/control" | tee "$OUT/$name/control.txt"
  fi
done < "$CELLS"
echo ALL-DONE
