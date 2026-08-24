"""ADR-079: the repeat verdict that RepeatGuardAgent applies inside Pier's
mini-swe-agent container. Tested as the pure function it is, so the test
needs no mini-swe-agent install."""
import importlib.util
from pathlib import Path

_GUARD = Path(__file__).resolve().parents[1] / "scripts" / "deepswe" / "hobbesmini" / "hobbesmini" / "guard.py"
_spec = importlib.util.spec_from_file_location("hobbesmini_guard", _GUARD)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def test_first_action_is_never_refused():
    assert guard.repeat_verdict(None, "ls", 0, 3) == (False, 0, False)


def test_different_action_resets_the_streak():
    assert guard.repeat_verdict("cat a.py", "sed -n 1,40p a.py", 2, 3) == (False, 0, False)


def test_identical_action_is_refused_and_counted():
    refuse, streak, stop = guard.repeat_verdict("cat a.py", "cat a.py", 0, 3)
    assert (refuse, streak, stop) == (True, 1, False)


def test_whitespace_differences_do_not_evade_the_guard():
    assert guard.repeat_verdict("cat  a.py\n", "cat a.py", 0, 3)[0] is True


def test_exit_at_max_repeats():
    assert guard.repeat_verdict("x", "x", 2, 3) == (True, 3, True)


def test_zero_max_repeats_refuses_but_never_exits():
    assert guard.repeat_verdict("x", "x", 40, 0) == (True, 41, False)


def test_refusal_text_names_the_count_and_the_way_out():
    text = guard.REFUSAL.format(n=2)
    assert "2x" in text and "different" in text


def test_commit_on_exit_command_commits_in_app_and_names_the_reason():
    cmd = guard.commit_on_exit_command("ContextWindowExceededError")
    assert cmd.startswith("cd /app && git add -A") and "commit-on-exit (ContextWindowExceededError)" in cmd
    assert "COMMITTED" in cmd and "NOTHING_TO_COMMIT" in cmd


def test_commit_on_exit_reason_is_sanitised():
    cmd = guard.commit_on_exit_command("bad'; rm -rf / #")
    assert "'" not in cmd.split("commit-on-exit (")[1].split(")")[0]
    assert guard.commit_on_exit_command("") .count("commit-on-exit (exit)") == 1


def test_split_context_strips_markers_and_returns_aid():
    task, aid = guard.split_context("Do the thing.\n\n<<<HOBBES_CONTEXT>>>\n## What Hobbes can see\nx\n<<<END_HOBBES_CONTEXT>>>\n")
    assert task == "Do the thing.\n" and aid == "## What Hobbes can see\nx"
    assert "<<<" not in task and "<<<" not in aid


def test_split_context_without_markers_is_identity():
    assert guard.split_context("plain task") == ("plain task", None)


def test_context_as_tool_exchange_native_is_a_call_and_its_tool_result():
    a, t = guard.context_as_tool_exchange("AID", native=True)
    assert a["role"] == "assistant" and a["tool_calls"][0]["id"] == t["tool_call_id"] and t["role"] == "tool"
    assert "AID" in t["content"] and a["extra"]["hobbes_context"] and t["extra"]["hobbes_context"]


def test_context_as_tool_exchange_textbased_uses_minis_action_format():
    a, u = guard.context_as_tool_exchange("AID", native=False)
    assert "```mswea_bash_command" in a["content"] and u["role"] == "user" and "AID" in u["content"]
