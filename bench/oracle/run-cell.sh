#!/usr/bin/env sh
# One command per cell (ADR-089, design §9): ingest the repo with lane B,
# export the Hobbes edges of one Go module, run the Go RTA oracle on it,
# grade, and leave hobbes.json / oracle.json / report.json / report.txt
# in the output directory.
#
#   bench/oracle/run-cell.sh <repo> <module-dir> <out-dir> [--lang go|ts|py|rust|java] [--no-ingest]
#       [--exclude a,b] [--python "<cmd>"] [--runs N] [--sys-path a,b] [-- <pytest args>]
#
# --exclude a,b drops nested module directories from a root cell.
# <module-dir> is repo-relative ("." for a single-module repo): a Go
# module directory for --lang go (default), a directory holding a
# tsconfig.json for --lang ts, the directory whose pytest suite is the
# trace's root for --lang py (design §6: --python is the interpreter
# that can import the target and pytest, run from <module-dir>; default
# "uv run --project <repo>/<module-dir> python"; --runs unions N suite
# runs; everything after -- goes to pytest), the cargo package directory
# for --lang rust (the MIR driver under bench/oracle/rust is built with
# the pinned nightly first; --features passes cargo features), the Maven
# reactor or Gradle build root for --lang java (the HobbesOracle javac
# plugin is built in the image once per cell dir; --tool forces the build
# tool). Pass --no-ingest to grade an existing
# .hobbes/derived/graph.json. Runtime is
# printed at the end so every cell's cost is on the record. O6 and O7
# run inside the sandbox image (ADR-092 phase 2): build it first
# (sandbox/README.md); HOBBES_UNCONTAINED=1 runs them on the host,
# recorded in the cell's export and report.
set -eu
repo=$(cd "$1" && pwd); module=$2; out=$3; shift 3
ingest=1; lang=go; exclude=; python=; runs=1; syspath=; features=; tool=
while [ $# -gt 0 ]; do
  case "$1" in
    --no-ingest) ingest=0 ;;
    --lang) lang=$2; shift ;;
    --exclude) exclude=$2; shift ;;
    --python) python=$2; shift ;;
    --runs) runs=$2; shift ;;
    --sys-path) syspath=$2; shift ;;
    --features) features=$2; shift ;;
    --tool) tool=$2; shift ;;
    --) shift; break ;;
    *) echo "unknown argument $1" >&2; exit 2 ;;
  esac
  shift
done
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
mkdir -p "$out"; out=$(cd "$out" && pwd)
start=$(date +%s)
if [ "$ingest" = 1 ]; then
  (cd "$root/pipeline" && HOBBES_SCIP=1 uv run hobbes ingest --repo "$repo")
fi
(cd "$here" && go build -o "$out/oracle" ./cmd/oracle)
"$out/oracle" export --graph "$repo/.hobbes/derived/graph.json" --module "$module" --lang "$lang" --exclude "$exclude" --out "$out/hobbes.json"
case "$lang" in
  go) "$out/oracle" go-rta --repo "$repo" --module "$module" --exclude "$exclude" --out "$out/oracle.json" ;;
  ts) node "$here/ts/tsc-oracle.mjs" --repo "$repo" --zone "$module" --out "$out/oracle.json" ;;
  py) # The trace runs in the sandbox image (ADR-092): the interpreter is
      # a path — the cell's own venv python — not `uv run`, which the
      # image does not carry (and which resolves to that path anyway).
      [ -n "$python" ] || python="$repo/$module/.venv/bin/python"
      "$out/oracle" py-trace --repo "$repo" --module "$module" --python "$python" --runs "$runs" --sys-path "$syspath" --label "$python -m pytest $*" --out "$out/oracle.json" -- "$@" ;;
  rust) (cd "$here/rust" && LD_LIBRARY_PATH="$(rustc +nightly --print sysroot)/lib" cargo +nightly build --release --quiet)
        "$out/oracle" rust-mir --repo "$repo" --module "$module" --driver "$here/rust/target/release/mir-oracle" --out-dir "$out" --features "$features" --out "$out/oracle.json" ;;
  java) "$out/oracle" java-javac --repo "$repo" --module "$module" --plugin "$here/java" --out-dir "$out" --tool "$tool" --out "$out/oracle.json" ;;
  *) echo "unknown lang $lang" >&2; exit 2 ;;
esac
"$out/oracle" grade --hobbes "$out/hobbes.json" --oracle "$out/oracle.json" --json "$out/report.json" --poison | tee "$out/report.txt"
echo "cell $module of $repo: $(( $(date +%s) - start ))s" | tee -a "$out/report.txt"
