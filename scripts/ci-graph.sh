#!/usr/bin/env bash
# scripts/ci-graph.sh — the README's CI shape, as one script CI and a
# developer run the same way (ADR-095):
#
#   hobbes ingest && hobbes lanes && hobbes invariants compile (+ run the
#   compiled checkers) && hobbes review $BASE..HEAD
#
# then the lane_b-marked pytest cases, which only run with the image.
#
# Needs: podman, uv, node, Go ≥ 1.26 — the same as a developer box
# (CLAUDE.md "Build & test"). Builds the static proxy and the sandbox
# image itself, because lane B runs *only* in the image (ADR-092, C-64):
# an ingest without it is not the graph this repo verifies.
#
# Usage: scripts/ci-graph.sh <base-ref>     (e.g. origin/main, HEAD~1)
set -euo pipefail

BASE="${1:?usage: scripts/ci-graph.sh <base-ref>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

step() { printf '\n==> %s\n' "$*"; }

step "static proxy (mounted into the image)"
(cd go && CGO_ENABLED=0 go build -o ../sandbox/hobbes-proxy ./cmd/hobbes-proxy)

step "sandbox image hobbes-session:local (sessions and lane B ingest, ADR-092)"
(cd sandbox && podman build -q -t hobbes-session:local -f Containerfile .)

step "hobbes ingest (lane B contained; refuses on the host, C-64)"
(cd pipeline && uv run hobbes ingest)

# The artifact must say it was contained; a host run here is the ADR-094
# incident shape (a stale tree, a missing image) and fails loudly.
step "containment stamp"
python3 - <<'EOF'
import json, sys
g = json.load(open(".hobbes/derived/graph.json"))
c = g.get("containment")
if not c:
    sys.exit("graph.json carries no containment stamp — a pre-ADR-092 tree ran this ingest")
print(f"{len(c['steps'])} lane B steps; all_contained={c['all_contained']} escape_hatch={c['escape_hatch']}")
if not c["all_contained"] or c["escape_hatch"]:
    sys.exit("graph.json: lane B did not run contained — see C-64")
EOF

step "hobbes lanes (exit 1 on disagreement)"
(cd pipeline && uv run hobbes lanes)

step "hobbes invariants compile, then run every compiled checker (C-19)"
(cd pipeline && uv run hobbes invariants compile --json) > .hobbes/derived/compiled/manifest.ci.json
python3 - <<'EOF'
import json, shlex, subprocess, sys
m = json.load(open(".hobbes/derived/compiled/manifest.ci.json"))
for out in m["outputs"]:
    cmd = out["run"]
    # The emitter names the tool; the repo's dev environment supplies it.
    # semgrep is a pipeline dev dependency (uv run); the others are on PATH
    # or the step fails — a config nobody can execute is the C-19 debt.
    if cmd.startswith("semgrep "):
        cmd = "cd pipeline && uv run " + cmd.replace(".hobbes/", "../.hobbes/") + " .."
    print(f"--> {out['invariants']}: {cmd}", flush=True)
    subprocess.run(cmd, shell=True, check=True)
if not m["outputs"]:
    print("nothing compiled — every confirmed record is soft or graph-checked")
EOF

step "hobbes review $BASE..HEAD (exit 1 if it needs attention)"
(cd pipeline && uv run hobbes review "$BASE..HEAD")

step "lane_b pytest (the image-dependent cases)"
# No deselection since 2026-09-05: the venv-listing case builds a real
# venv (its python links to the base install, which the container
# mounts hop by hop) instead of a fake one whose `home = /usr` made the
# image's own python the base — the one permanent exclusion is gone.
(cd pipeline && uv run pytest -q -m lane_b)

step "graph checks passed"
