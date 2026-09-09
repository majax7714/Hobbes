#!/usr/bin/env sh
# Grade a third-party tool's call graph against one of the oracle lane's
# answer keys (ADR-101). One command, the same matcher, the same poison
# check as a Hobbes cell — the oracle does not care who produced the edges.
#
#   bench/oracle/grade-foreign.sh <edges.json> <oracle.json> <out-dir> [--module .] [--lang go|ts|py|rust|java] [--exclude a,b]
#
# <edges.json> is the tool's graph converted to the minimal shape
# (README § Grading a graph Hobbes did not build): {repo, sha, tool,
# version, converter, edges:[{site:"file:line", callee:"file:line",
# caller?, kind?, label?}]}. <oracle.json> is an answer key produced by
# `oracle go-rta | rust-mir | java-javac | py-trace` or ts/tsc-oracle.mjs
# on the same repo at the same commit — every cell record names the
# command that regenerates its key. Leaves hobbes.json (the converted
# graph), report.json and report.txt in <out-dir>; the last line of the
# report is the poison check, and a cell without one is not a cell.
set -eu
edgesf=$(cd "$(dirname "$1")" && pwd)/$(basename "$1"); oraclef=$(cd "$(dirname "$2")" && pwd)/$(basename "$2"); out=$3; shift 3
module=.; lang=go; exclude=
while [ $# -gt 0 ]; do
  case "$1" in
    --module) module=$2; shift ;;
    --lang) lang=$2; shift ;;
    --exclude) exclude=$2; shift ;;
    *) echo "unknown argument $1" >&2; exit 2 ;;
  esac
  shift
done
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$out"; out=$(cd "$out" && pwd)
start=$(date +%s)
(cd "$here" && go build -o "$out/oracle" ./cmd/oracle)
"$out/oracle" import --edges "$edgesf" --module "$module" --lang "$lang" --exclude "$exclude" --out "$out/hobbes.json"
"$out/oracle" grade --hobbes "$out/hobbes.json" --oracle "$oraclef" --json "$out/report.json" --poison | tee "$out/report.txt"
echo "foreign cell $module ($(basename "$edgesf")): $(( $(date +%s) - start ))s" | tee -a "$out/report.txt"
