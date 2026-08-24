"""Read-volume metric for a Pier/mini-swe-agent trial (benchmark-hypotheses.md,
2026-08-22): where a trial's context went, per arm. Hobbes's aid is supposed
to make reads *smaller*; this is the number that should separate the arms by
design, so it is computed, never interpreted.

    uv run scripts/deepswe_read_volume.py <trial-dir> [<trial-dir> ...]

Prints, per trial: calls, final prompt tokens, completion tokens, observation
chars by command kind, the model's own heredoc bodies kept in context, and
the largest observations with their commands.
"""
import json
import re
import sys
from pathlib import Path

KINDS = ("read", "diff", "pytest", "edit", "other")


def kind_of(command: str) -> str:
    if "EOF" in command:
        return "edit"
    if "git diff" in command:
        return "diff"
    if "pytest" in command:
        return "pytest"
    if re.search(r"\b(nl -ba|sed -n|cat |head |tail |grep)", command):
        return "read"
    return "other"


def read_volume(trial_dir: Path) -> dict:
    t = json.loads((trial_dir / "agent" / "mini-swe-agent.trajectory.json").read_text())
    m = t["messages"]
    calls = [x for x in m if x["role"] == "assistant"]
    usages = [(x.get("extra", {}).get("response", {}) or {}).get("usage", {}) or {} for x in calls]
    cmds = {}
    for x in calls:
        for tc in x.get("tool_calls") or []:
            try:
                cmds[tc["id"]] = json.loads(tc["function"]["arguments"]).get("command", "")
            except (json.JSONDecodeError, KeyError, TypeError):
                cmds[tc["id"]] = str(tc["function"].get("arguments", ""))
    obs = [x for x in m if x["role"] in ("tool", "user")][1:]
    by_kind = {k: [0, 0] for k in KINDS}
    biggest = []
    for x in obs:
        c = cmds.get(x.get("tool_call_id"), "")
        n = len(str(x.get("content")))
        k = kind_of(c)
        by_kind[k][0] += 1
        by_kind[k][1] += n
        biggest.append((n, c))
    heredoc = sum(
        len(tc["function"]["arguments"]) for x in calls for tc in x.get("tool_calls") or [] if "EOF" in tc["function"]["arguments"]
    )
    return {
        "trial": str(trial_dir),
        "exit": t["info"].get("exit_status"),
        "calls": len(calls),
        "final_prompt_tokens": usages[-1].get("prompt_tokens") if usages else None,
        "completion_tokens": sum(u.get("completion_tokens", 0) for u in usages),
        "observation_chars_by_kind": {k: {"n": v[0], "chars": v[1]} for k, v in by_kind.items()},
        "heredoc_chars_in_assistant_turns": heredoc,
        "largest_observations": [{"chars": n, "command": c[:160]} for n, c in sorted(biggest, reverse=True)[:8]],
    }


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    for arg in argv:
        r = read_volume(Path(arg))
        print(f"== {r['trial']}")
        print(f"  exit {r['exit']} | calls {r['calls']} | final prompt {r['final_prompt_tokens']} tok | completion {r['completion_tokens']} tok")
        print("  observations:", ", ".join(f"{k} {v['n']}x/{v['chars']}ch" for k, v in r["observation_chars_by_kind"].items()))
        print(f"  model's own heredoc bodies kept in context: {r['heredoc_chars_in_assistant_turns']} ch")
        for o in r["largest_observations"]:
            print(f"   {o['chars']:7d}  $ {o['command']}".replace("\n", " | "))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
