"""Headless Claude Code invocation (ADR-020).

One ``claude -p --output-format json --tools ""`` subprocess per work
unit, prompt on stdin. ``--tools ""`` disables every built-in tool, so
the cartographer has no I/O surface: it sees the prompt, returns text,
and the pipeline is the only writer. The binary comes from
``HOBBES_CLAUDE_BIN`` when set (the ``HOBBES_POLICY_BIN`` precedent).
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass

#: Environment variable naming the Claude Code binary to run.
CLAUDE_BIN_ENV = "HOBBES_CLAUDE_BIN"


class RunnerError(RuntimeError):
    """The claude invocation itself failed (exit code, timeout, or an
    unusable result envelope) — distinct from the *content* failing
    ADR-019 validation, which the orchestrator handles via retry."""


@dataclass
class ClaudeRunner:
    """Callable prompt → result text. Swapped for a fake in tests."""

    model: str | None = None
    timeout: float = 600.0

    def __call__(self, prompt: str) -> str:
        bin_ = os.environ.get(CLAUDE_BIN_ENV, "claude")
        cmd = [bin_, "-p", "--output-format", "json", "--tools", ""]
        if self.model:
            cmd += ["--model", self.model]
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise RunnerError(
                f"claude binary not found ({bin_!r}); install Claude Code or "
                f"set {CLAUDE_BIN_ENV}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RunnerError(f"claude timed out after {self.timeout:.0f}s") from exc
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()[-500:]
            raise RunnerError(f"claude exited {proc.returncode}: {detail}")
        try:
            envelope = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RunnerError(f"claude emitted unparseable envelope: {exc}") from exc
        if not isinstance(envelope, dict) or envelope.get("is_error"):
            raise RunnerError(f"claude reported an error: {str(envelope)[:500]}")
        result = envelope.get("result")
        if not isinstance(result, str) or not result.strip():
            raise RunnerError("claude envelope carried no result text")
        return result


def parse_json_response(text: str) -> object:
    """The model's JSON payload, tolerating a markdown fence around it.

    Raises ValueError (with a message fit for retry feedback) when the
    text is not JSON.
    """
    body = text.strip()
    if body.startswith("```"):
        lines = body.splitlines()
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        body = "\n".join(lines[1:]).strip()
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"response was not valid JSON ({exc}); respond with only the JSON object"
        ) from exc
