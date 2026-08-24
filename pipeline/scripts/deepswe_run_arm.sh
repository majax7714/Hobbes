#!/bin/bash
# ADR-078/079/082. usage: deepswe_run_arm.sh <baseline|aided> <task-id> [model]   (aided = model + prompt; NOT a Hobbes arm)
#   MODE=textbased (default; the 7B) | native (tool calls; the 27B)
#   SUFFIX=-x appends to the job name.
# Expects ~/.hobbes/deepswe: venv (datacurve-pier + mini-swe-agent), deep-swe/ clone, pier.env, aid/<task>.j2
# Hobbes's repeat guard (hobbesmini, ADR-079) is installed into the agent's venv at IMAGE BUILD time, so
# it must be reachable by URL: `uv build --wheel -o ~/.hobbes/deepswe/wheels pipeline/scripts/deepswe/hobbesmini`
# then `python3 -m http.server 8765 --bind 172.17.0.1 --directory ~/.hobbes/deepswe/wheels` (docker0 only;
# WHEEL_URL overrides). Both arms get it.
set -u
ARM=$1; TASK=$2
# P12 (ADR-082): this runner drives ONE agent on the whole task. That is
# "model + prompt", never a Hobbes arm — the name `hobbes` is refused until a
# planner → units → per-unit-window shape exists on Pier. Use `aided`.
if [ "$ARM" = hobbes ]; then echo "refused: one agent on the whole task is not a Hobbes arm (P12, ADR-082); use 'aided'" >&2; exit 2; fi
[ "$ARM" = aided ] && AIDED=1 || AIDED=0
 MODEL=${3:-openai/Qwen/Qwen2.5-Coder-7B-Instruct}; MODE=${MODE:-textbased}
HERE="$(cd "$(dirname "$0")/deepswe" && pwd)"
cd "$HOME/.hobbes/deepswe" && source venv/bin/activate
EXTRA=""
[ "$AIDED" = 1 ] && EXTRA="--ak prompt_template_path=$HOME/.hobbes/deepswe/aid/${TASK#*-}.j2"
if [ "$MODE" = native ]; then MC=litellm; CFG=$HERE/mini_hobbes_native.yaml; else MC=litellm_textbased; CFG=$HERE/mini_hobbes_textbased.yaml; fi
NAME="$ARM-$(echo "$MODEL" | tr '/' '_' | tr 'A-Z' 'a-z')-$TASK${SUFFIX:-}"
exec pier run -p deep-swe/tasks/$TASK --agent mini-swe-agent -m "$MODEL" \
  --ak model_class=$MC --ak config_file=$CFG \
  --ak "extra_python_packages=[\"${WHEEL_URL:-http://172.17.0.1:8765/hobbesmini-0.3.0-py3-none-any.whl}\"]" \
  --agent-timeout-multiplier "${TIMEOUT_MULT:-2}" \
  $EXTRA --env-file pier.env -o jobs --job-name "$NAME" -n 1 -y --debug \
  > jobs/$NAME.log 2>&1
