"""The repeat verdict, pure — importable without mini-swe-agent (tested in
pipeline/tests/test_deepswe_repeat_guard.py). ADR-079: an agent that sends
the same action it just sent has stopped reading its observations; the
loop refuses it and says why, and exits after `max_repeats` consecutive
refusals rather than filling the window with identical turns (the httpx
7B run repeated one `cat` twelve times)."""

REFUSAL = (
    "REFUSED: this is the same command as your previous action (repeated {n}x). "
    "It already ran and its output is above. Read that output and do something "
    "different: narrow the command (head/sed -n/grep), edit a file, or run a test."
)


def normalize(command: str) -> str:
    return " ".join((command or "").split())


def repeat_verdict(previous: str | None, current: str, streak: int, max_repeats: int) -> tuple[bool, int, bool]:
    """(refuse, new_streak, exit) for `current` after `previous`.

    refuse   — the action is identical to the previous one and is not run;
    streak   — consecutive identical actions so far (0 when it differs);
    exit     — the streak reached `max_repeats` (0 disables the exit).
    """
    if previous is None or normalize(previous) != normalize(current):
        return False, 0, False
    streak += 1
    return True, streak, 0 < max_repeats <= streak


COMMIT_ON_EXIT = (
    "cd /app && git add -A -- . ':!*.pyc' 2>/dev/null; "
    "git -c user.name=hobbes -c user.email=hobbes@localhost commit -q -m 'hobbes: commit-on-exit ({reason})' "
    "&& echo COMMITTED || echo NOTHING_TO_COMMIT"
)


def commit_on_exit_command(reason: str) -> str:
    """The command run when the agent loop ends for any reason (ADR-080):
    leftover edits are committed so the collect hook (`git diff base..HEAD`)
    sees them. Mirrors ADR-058's `--commit-on-exit` in our own harness.
    The reason is sanitised to a short word so it cannot break the quoting."""
    word = "".join(ch for ch in (reason or "exit") if ch.isalnum() or ch in "-_")[:40] or "exit"
    return COMMIT_ON_EXIT.format(reason=word)


CONTEXT_OPEN = "<<<HOBBES_CONTEXT>>>"
CONTEXT_CLOSE = "<<<END_HOBBES_CONTEXT>>>"
CONTEXT_COMMAND = "hobbes context --task ."
CONTEXT_PREFACE = "Let me pull the derived context Hobbes has for this task before reading anything."


def split_context(text: str) -> tuple[str, str | None]:
    """Separate Hobbes's aid from the task text (C-56, observation shape).

    The aid template wraps the aid in CONTEXT_OPEN/CONTEXT_CLOSE. Returns
    (task_without_markers, aid) — aid is None when no markers are present,
    and the markers themselves never survive in either part."""
    if CONTEXT_OPEN not in text:
        return text, None
    head, rest = text.split(CONTEXT_OPEN, 1)
    aid, tail = rest.split(CONTEXT_CLOSE, 1) if CONTEXT_CLOSE in rest else (rest, "")
    task = (head.rstrip() + ("\n\n" + tail.lstrip() if tail.strip() else "")).strip() + "\n"
    return task, aid.strip()


def context_as_tool_exchange(aid: str, native: bool) -> list[dict]:
    """The aid as the agent's own first tool call + its observation — the
    shape every trajectory in pretraining has, instead of prose in the
    prompt. `native` = OpenAI tool-call messages; otherwise mini's
    text-based action format."""
    if native:
        import json as _json
        call_id = "call_hobbes_context"
        return [
            {
                "role": "assistant",
                "content": CONTEXT_PREFACE,
                "tool_calls": [{"id": call_id, "type": "function",
                                "function": {"name": "bash", "arguments": _json.dumps({"command": CONTEXT_COMMAND})}}],
                "extra": {"actions": [{"command": CONTEXT_COMMAND, "tool_call_id": call_id}], "hobbes_context": True},
            },
            {"role": "tool", "tool_call_id": call_id, "content": f"<returncode>0</returncode>\n<output>\n{aid}\n</output>",
             "extra": {"hobbes_context": True}},
        ]
    return [
        {"role": "assistant", "content": f"{CONTEXT_PREFACE}\n\n```mswea_bash_command\n{CONTEXT_COMMAND}\n```",
         "extra": {"actions": [{"command": CONTEXT_COMMAND}], "hobbes_context": True}},
        {"role": "user", "content": f"<returncode>0</returncode>\n<output>\n{aid}\n</output>", "extra": {"hobbes_context": True}},
    ]
