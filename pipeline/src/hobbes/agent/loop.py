#!/usr/bin/env python3
"""A minimal agent loop over an OpenAI-compatible chat endpoint (ADR-056).

**Stdlib only, one file.** ``hobbes-session`` copies this file into the
session dir and runs it inside the sandbox with the image's ``python3``;
the pure benchmark arm runs it on the host. Either way it is the same
loop:

1. send the system prompt, the task, and the tool schemas;
2. execute every tool call the model returns — MCP tools through the
   hobbes-proxy over stdio (the sandbox's policy-checked ``exec`` and
   the knowledge tools), native ``bash`` only when no MCP config is
   given (the pure arm), and confined file tools either way;
3. feed the results back; stop when the model answers without tool
   calls or the turn budget runs out.

It prints one **result envelope** on stdout in Claude Code's shape
(``type: result``, ``usage``, ``duration_ms``, ``num_turns``,
``is_error``), so the benchmark's meter reads both runtimes with one
reader. Everything else goes to stderr.

Usage::

    loop.py --base-url URL --model NAME [--api-key-env VAR]
            (--prompt TEXT | --prompt-file FILE)
            [--mcp-config FILE] [--role ROLE] [--workdir DIR]
            [--max-turns N] [--max-tokens N] [--timeout SEC]

The API key is read from the environment variable named by
``--api-key-env`` (default ``HOBBES_LLM_API_KEY``); an unset variable
sends no ``Authorization`` header, which is what a private endpoint
wants.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Callable

SYSTEM_PROMPT = """\
You are a software engineer working in a git checkout at {workdir}.
Use the tools to read code, change it, and run commands; do the task
in the prompt and nothing else. Work in small verified steps: read
before you edit, run the relevant tests after you edit. When the task
is done, reply with a short plain-text summary of what you changed
and what you could not verify, and stop calling tools. Call tools
through the tool-calling interface, never by writing JSON in your
message.
"""

#: Roles whose worktree is read-only and whose *job is a handoff*: they
#: do their work through reflect, never through an edit (harness
#: restructure, phase 1). Mirrors go/internal/sandbox ReadOnlyRoles.
READ_ONLY_ROLES = {"reviewer", "verifier", "planner"}

#: Any fence tag (the 7B writes ```python and ```sh around JSON too), a
#: fence the model never closed (ADR-067), or a <tool_call> block.
_FENCED = re.compile(r"```[\w+-]*[ \t]*\n?\s*(\{.*?\})\s*(?:```|\Z)|<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


_FUNCTION_CALLS = re.compile(r"<function_calls>(.*?)</function_calls>", re.S)
_CALL_HEAD = re.compile(r"\s*([A-Za-z_][\w.]*)\s*\(", re.S)
_ARG_HEAD = re.compile(r"\s*([A-Za-z_]\w*)\s*=\s*", re.S)


def _python_call(line: str) -> dict | None:
    """``name(key='value', flag=True)`` as a Python expression — the
    quoting a model falls into when it is not copying the template's
    JSON; every value must be a literal, or the call is not read."""
    import ast
    try:
        node = ast.parse(line.strip(), mode="eval").body
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.args:
            return None
        args = {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords if kw.arg}
    except (SyntaxError, ValueError, TypeError):
        return None
    return {"name": node.func.id, "arguments": args}


def call_syntax_calls(block: str) -> list[dict]:
    """Calls written as ``name(key=<json>, key2=<json>)`` — the shape
    Olmo 3's chat template renders and its model writes inside
    ``<function_calls>`` (one call per line). Values are JSON, or —
    when a call does not decode as JSON — Python literals on one line
    (``path='a.py'``); a call that reads neither way is skipped, not
    guessed at."""
    out, pos, decoder = [], 0, json.JSONDecoder()
    taken: list[tuple[int, int]] = []
    while True:
        head = _CALL_HEAD.match(block, pos)
        if not head:
            break
        name, pos, args, ok = head.group(1), head.end(), {}, True
        while True:
            if block[pos:pos + 1] == ")" or not block[pos:].strip():
                pos += 1 if block[pos:pos + 1] == ")" else 0
                break
            arg = _ARG_HEAD.match(block, pos)
            if not arg:
                ok = False
                break
            try:
                value, end = decoder.raw_decode(block, arg.end())
            except json.JSONDecodeError:
                ok = False
                break
            args[arg.group(1)], pos = value, end
            while block[pos:pos + 1] in (",", " ", "\n", "\t") and block[pos:pos + 1]:
                pos += 1
        if not ok:
            close = block.find(")", pos)
            pos = len(block) if close < 0 else close + 1
            continue
        taken.append((head.start(), pos))
        out.append({"id": f"text_{len(out)}", "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args)}})
    if not out:
        for line in block.splitlines():
            call = _python_call(line)
            if call:
                out.append({"id": f"text_{len(out)}", "type": "function",
                            "function": {"name": call["name"], "arguments": json.dumps(call["arguments"])}})
    return out


def text_tool_calls(content: str) -> list[dict]:
    """Tool calls a model wrote *as text* — a fenced JSON object, a
    ``<tool_call>`` block with ``name`` and ``arguments``, or a
    ``<function_calls>`` block in call syntax (Olmo 3's own template) —
    in the shape of structured ones. Small models do this; refusing
    them would measure the chat template, not the model. The loop counts
    how often it happened (``text_tool_calls`` in the envelope) so the
    accommodation is visible in every record."""
    out = []
    for block in _FUNCTION_CALLS.findall(content or ""):
        for call in call_syntax_calls(block):
            call["id"] = f"text_{len(out)}"
            out.append(call)
    if out:
        return out
    for n, match in enumerate(_FENCED.finditer(content or "")):
        raw = match.group(1) or match.group(2)
        try:
            # strict=False: a model writes real newlines inside the
            # "text" of a handoff; refusing those measures the JSON
            # encoder, not the model (ADR-067).
            doc = json.loads(raw, strict=False)
        except json.JSONDecodeError:
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get("name"), str):
            continue
        args = doc.get("arguments", doc.get("parameters", {}))
        if not isinstance(args, dict):
            continue
        out.append({"id": f"text_{n}", "type": "function",
                    "function": {"name": doc["name"], "arguments": json.dumps(args)}})
    return out


# --------------------------------------------------------------------------
# MCP over stdio (newline-delimited JSON-RPC, the go-sdk's stdio transport)

class MCPClient:
    """The one MCP server a session has: the hobbes-proxy from the
    wrapper's ``mcp.json``. Tools are listed from it, never assumed."""

    def __init__(self, config_path: str):
        cfg = json.load(open(config_path))["mcpServers"]
        name, server = next(iter(cfg.items()))
        self.proc = subprocess.Popen(
            [server["command"], *server.get("args", [])],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, text=True,
        )
        self.n = 0
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "hobbes-agent-loop", "version": "0"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, msg: dict) -> None:
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def _rpc(self, method: str, params: dict) -> dict:
        self.n += 1
        self._send({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params})
        assert self.proc.stdout
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server closed the connection")
            msg = json.loads(line)
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"MCP {method}: {msg['error']}")
                return msg.get("result", {})

    def tools(self) -> list[dict]:
        """MCP tool descriptors as OpenAI function tools."""
        out = []
        for tool in self._rpc("tools/list", {}).get("tools", []):
            out.append({"type": "function", "function": {
                "name": tool["name"], "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema") or {"type": "object", "properties": {}},
            }})
        return out

    def call(self, name: str, args: dict) -> tuple[str, bool]:
        result = self._rpc("tools/call", {"name": name, "arguments": args})
        text = "".join(c.get("text", "") for c in result.get("content", []) if isinstance(c, dict))
        return text, bool(result.get("isError"))

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.wait(timeout=15)
        except Exception:  # noqa: BLE001 — shutting down
            self.proc.kill()


# --------------------------------------------------------------------------
# Native tools: confined file access, and bash only for the pure arm

def _confine(workdir: str, path: str) -> str:
    full = os.path.realpath(os.path.join(workdir, path))
    root = os.path.realpath(workdir)
    if full != root and not full.startswith(root + os.sep):
        raise ValueError(f"{path!r} is outside the working tree")
    return full


FILE_TOOLS = [
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a file in the working tree (path relative to it). Returns the text with line numbers.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "start_line": {"type": "integer", "description": "1-based first line (default 1)"},
            "end_line": {"type": "integer", "description": "1-based last line (default: end)"},
        }, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "list_files", "description": "List files under a directory of the working tree (default: its root), recursively, up to 500 entries.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "search_file",
        "description": "Find lines matching a regular expression in one file (or every file under a directory) of the "
                       "working tree. Returns path:line: text for each match — use it to locate a definition in a "
                       "large file, then read_file that line range and copy old_text from what you see.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "file or directory, relative to the working tree"},
            "pattern": {"type": "string", "description": "Python regular expression, e.g. 'def integrate\\('"},
            "max_results": {"type": "integer", "description": "default 50"},
        }, "required": ["path", "pattern"]}}},
]

WRITE_TOOLS = [
    {"type": "function", "function": {
        "name": "write_file", "description": "Create or overwrite a file in the working tree with the given content.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "edit_file", "description": "Replace one exact occurrence of old_text with new_text in a file. Fails if old_text is absent or ambiguous — include enough context to be unique.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}},
            "required": ["path", "old_text", "new_text"]}}},
]

BASH_TOOL = {"type": "function", "function": {
    "name": "bash", "description": "Run a shell command in the working tree and return its output (stdout+stderr, exit code).",
    "parameters": {"type": "object", "properties": {
        "command": {"type": "string"}, "timeout": {"type": "integer", "description": "seconds (default 300)"}},
        "required": ["command"]}}}


def native_call(name: str, args: dict, workdir: str, allow_bash: bool, allow_write: bool,
                read_paths: set[str] | None = None) -> tuple[str, bool]:
    """Execute a native tool; returns (text, is_error). *read_paths*
    accumulates the paths the session has read, so an overwrite of an
    existing file it never looked at can be refused (ADR-064)."""
    try:
        if name == "read_file":
            full = _confine(workdir, args["path"])
            if read_paths is not None:
                read_paths.add(os.path.normpath(args["path"]))
            lines = open(full, encoding="utf-8", errors="replace").read().splitlines()
            start = max(int(args.get("start_line") or 1), 1)
            end = min(int(args.get("end_line") or len(lines)), len(lines))
            body = "\n".join(f"{n:6d}\t{lines[n - 1]}" for n in range(start, end + 1))
            return (body or "(empty file)"), False
        if name == "search_file":
            # ADR-070: a 7,000-line file reads as its first 12k chars
            # (C-46's clip) and the model never narrowed a range on its
            # own — 15 of 18 anchor-missing sessions had a clipped read.
            # The search is how it finds the line to read.
            full = _confine(workdir, args.get("path") or ".")
            if not os.path.exists(full):
                # A missing path is an answer, not an empty result: two
                # pure arms of the ADR-070 run searched a hallucinated
                # file, read "(no matches)", and kept editing it.
                return (f"no such file or directory: {args.get('path')} — list_files its parent "
                        "directory, or search_file the directory instead"), True
            try:
                rx = re.compile(str(args["pattern"]))
            except re.error as exc:
                return f"pattern is not a valid regular expression: {exc}", True
            limit = max(1, int(args.get("max_results") or 50))
            hits: list[str] = []
            files = [full] if os.path.isfile(full) else []
            if not files:
                for root, dirs, names in os.walk(full):
                    dirs[:] = sorted(d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".hobbes"))
                    files += [os.path.join(root, f) for f in sorted(names)]
            scanned = 0
            for path in files:
                scanned += 1
                try:
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        for n, line in enumerate(fh, 1):
                            if rx.search(line):
                                hits.append(f"{os.path.relpath(path, workdir)}:{n}: {line.rstrip()[:200]}")
                                if len(hits) >= limit:
                                    return "\n".join(hits) + f"\n… stopped at {limit} matches; narrow the pattern", False
                except OSError:
                    continue
                if scanned >= 2000:
                    hits.append("… stopped after 2000 files; give a narrower directory")
                    break
            return "\n".join(hits) or "(no matches)", False
        if name == "list_files":
            full = _confine(workdir, args.get("path") or ".")
            out = []
            for root, dirs, files in os.walk(full):
                dirs[:] = sorted(d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".hobbes"))
                for f in sorted(files):
                    out.append(os.path.relpath(os.path.join(root, f), workdir))
                    if len(out) >= 500:
                        return "\n".join(out) + "\n… truncated at 500", False
            return "\n".join(out) or "(no files)", False
        if name in ("write_file", "edit_file"):
            if not allow_write:
                return f"{name} is not available to this role", True
            full = _confine(workdir, args["path"])
            if name == "write_file":
                # Read before you overwrite (ADR-064): a whole-file write
                # onto an existing file the session never read is how the
                # 7B silently replaced a 308-line module with a stub. A
                # new file is fine; so is a write after a read of the same
                # path — edit_file, which must see the file, is the tool
                # for a change to existing content.
                if read_paths is not None and os.path.exists(full) \
                        and os.path.normpath(args["path"]) not in read_paths:
                    return (f"{args['path']} already exists and this session has not read it. "
                            "read_file it first, then use edit_file to change part of it, or "
                            "write_file only to replace a file you have read in full."), True
                os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
                with open(full, "w", encoding="utf-8") as fh:
                    fh.write(args["content"])
                return f"wrote {args['path']} ({len(args['content'])} bytes)", False
            # Read before you edit (ADR-067, the same rule as the write
            # guard above): an anchor guessed from memory is how the 7B
            # spent whole sessions on "old_text occurs 0 times" — xarray-
            # 3993's U2 sent nine identical pairs against a signature
            # that does not exist and never read the file.
            if read_paths is not None and os.path.normpath(args["path"]) not in read_paths:
                return (f"this session has not read {args['path']}. search_file for the name you are "
                        "changing, read_file that line range, then edit_file — old_text must be copied "
                        "from the file as it is, not recalled."), True
            text = open(full, encoding="utf-8").read()
            count = text.count(args["old_text"])
            if count != 1:
                return (f"old_text occurs {count} times in {args['path']}; it must occur exactly once"), True
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(text.replace(args["old_text"], args["new_text"], 1))
            return f"edited {args['path']}", False
        if name == "bash":
            if not allow_bash:
                return "bash is not available in this session; use the exec tool", True
            timeout = int(args.get("timeout") or 300)
            proc = subprocess.run(args["command"], shell=True, cwd=workdir, capture_output=True,
                                  text=True, timeout=timeout)
            out = (proc.stdout + proc.stderr)[-20000:]
            return f"{out}\n[exit {proc.returncode}]", proc.returncode != 0
        return f"unknown tool {name}", True
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        return f"{type(exc).__name__}: {exc}", True


# --------------------------------------------------------------------------
# The endpoint

#: What a context-length refusal looks like (vLLM's wording, also
#: OpenAI's): the window and the request's input, both in tokens.
CONTEXT_LENGTH_RE = re.compile(r"maximum context length is (\d+) tokens.*?(\d+) input tokens", re.S)
#: Below this many completion tokens a fitted call is not worth making;
#: the loop elides old tool results instead.
MIN_COMPLETION = 256
ELIDED = "[tool result elided to fit the model's context window]"
#: Tool names that mutate the tree — an edit is what a patch is made of.
#: `write_file`/`edit_file` are the loop's; `mcp__hobbes__exec` is the
#: sandbox's shell (used to apply changes or run tests). A model that
#: stops before calling one of these has described a fix, not made one.
MUTATING_TOOLS = {"write_file", "edit_file"}
#: The nudge sent when a small model returns a prose plan before editing
#: (ADR-058, the fifth finding): the 7B reads "summarize when done" and
#: jumps to the summary on turn 1. Bounded so a model that simply cannot
#: act still terminates.
NUDGE = (
    "You have not changed any files yet — you only described what to do. "
    "A description is not a fix. Make the change now by calling the "
    "write_file or edit_file tool (and run the guarding tests with the "
    "exec tool). Do not reply with a summary until the files are edited."
)
#: The same nudge for a read-only role: its deliverable is a reflect
#: handoff, and a prose reply that never reaches the orchestrator is the
#: same failure as a prose plan that never edits.
NUDGE_READ_ONLY = (
    "You have not sent your result yet — you only described it. A reply "
    "the orchestrator never receives is not a result. Call the reflect "
    "tool now with kind \"handoff\" and your complete answer as the text. "
    "Do not reply with a summary until reflect has been called."
)
#: Returned in place of re-running a tool the model already called with
#: the exact same arguments (ADR-058, sixth finding — a 7B unit called
#: one read-only tool 55 times). The pipeline refuses the repeat rather
#: than pay for it; the model must do something new.
REPEAT_REFUSAL = (
    "You already called this tool with these exact arguments and the "
    "result has not changed. Stop repeating it. Read something new, edit "
    "a file with write_file/edit_file, or finish — do not call it again."
)
EXEC_REPEAT_REFUSAL = (
    "That exact command already ran and nothing has been edited since, "
    "so its result would be the same. Edit something first, or run a "
    "different command."
)
EDIT_REPEAT_REFUSAL = (
    "You already made this exact edit. Applying it again does not change "
    "the file the way you intend — an edit whose new text still contains "
    "its own anchor stacks a duplicate. Read the file to see its current "
    "state, then make a different edit."
)


ANCHOR_STACK_REFUSAL = (
    "You already edited this file at this exact old_text, and your new_text "
    "still contains it — applying another edit at the same anchor stacks a "
    "second copy instead of replacing the first. read_file the region to see "
    "what the file holds now, then anchor the edit on the current text."
)
#: The read ticket was hollowed out by the window fit (ADR-091, D3):
#: eliding a read_file result invalidates the path's read-before-edit
#: ticket, so the guarantee's premise — the model has the file in front
#: of it — holds at the moment of the write, not only in the past.
ELIDED_READ_REFUSAL = (
    "your read of {path} was elided from the context window to fit the "
    "model, so its contents are no longer in front of you. read_file the "
    "range you are changing again, then edit — old_text must be copied "
    "from a read you can still see."
)
#: A read and an edit of the same path in one turn (ADR-091, D4): the
#: edit's anchor was authored before the read's result existed, so it
#: was recalled, not copied — sphinx-8548's U1 anchored on a line that
#: occurs nowhere in the file.
SAME_TURN_REFUSAL = (
    "the read of {path} landed this turn — you wrote this edit before you "
    "could see its result, so old_text was recalled, not copied. Copy your "
    "anchor from the read's result and edit on the next turn."
)
#: The implementer's handoff nudge (ADR-091, D8): an implementer that
#: edited and then ended in prose (sphinx-8548's U1: "let's reflect…",
#: never calling reflect) hands nothing to the orchestrator. One bounded
#: nudge, the same shape as NUDGE_READ_ONLY; only sent when a reflect
#: tool is on offer.
NUDGE_HANDOFF = (
    "You have edited files but not sent your handoff — a summary in prose "
    "never reaches the orchestrator. Call the reflect tool now with kind "
    "\"handoff\" and what you changed, what you ran, and what is left, as "
    "the text. Then stop."
)
#: A completion the endpoint cut at max_tokens (finish_reason "length")
#: is retried once with this much more room (ADR-067); the window fit
#: still bounds it. A cut completion is never what the model meant —
#: the sphinx-8548 planner lost a correct-shaped handoff three times.
CUT_RETRY_FACTOR = 2


def is_exec_tool(name: str) -> bool:
    """Is *name* the shell — the proxy's ``exec`` (its MCP name is plain
    ``exec``; a client that prefixes server names yields ``…__exec``) or
    the pure arm's ``bash``? ADR-071: the check used to accept only the
    prefixed form, so in every harness run the shell was treated as a
    read-only tool — a test re-run after an edit was refused as a
    repeat, which is how most harness sessions ended."""
    return name == "exec" or name.endswith("__exec") or name == "bash"


def sampling_fields(temperature: float = 0.0, top_p: float | None = None,
                    reasoning_effort: str | None = None, thinking: str = "server", sampling: str = "greedy") -> dict:
    """The request fields that shape a completion (ADR-074). Greedy
    (``temperature`` 0) is the ladder's default and what every 7B run
    used; a thinking model's card warns greedy decoding loops its
    reasoning, so the bench passes the model's own sampling for that
    rung. ``reasoning_effort`` goes through as the OpenAI field vLLM
    maps onto the chat template; ``thinking`` is ``server`` (the
    template's default), ``on`` or ``off`` via ``chat_template_kwargs``
    — a field a non-thinking template ignores. ``sampling="model-default"``
    sends no ``temperature`` at all — an endpoint that rejects the field
    (Anthropic's OpenAI-compatible surface for Sonnet 5, Calvin M0 step
    4) decodes with its own default, and the record says so."""
    fields: dict = {"temperature": temperature} if sampling == "greedy" else {}
    if top_p is not None:
        fields["top_p"] = top_p
    if reasoning_effort:
        fields["reasoning_effort"] = reasoning_effort
    if thinking != "server":
        fields["chat_template_kwargs"] = {"enable_thinking": thinking == "on"}
    return fields


def reasoning_tokens(usage: dict) -> int:
    """Reasoning tokens the endpoint reports inside ``completion_tokens``
    (OpenAI's ``completion_tokens_details.reasoning_tokens``; vLLM's
    reasoning parser fills it) — 0 when the field is absent, so the
    count is observed, never inferred."""
    details = usage.get("completion_tokens_details") or {}
    try:
        return int(details.get("reasoning_tokens") or 0)
    except (TypeError, ValueError):
        return 0


class ContextOverflow(RuntimeError):
    """The endpoint refused the request for length; carries the window
    and input sizes it reported."""

    def __init__(self, message: str, window: int, inputs: int):
        super().__init__(message)
        self.window, self.inputs = window, inputs


class Endpoint:
    def __init__(self, base_url: str, model: str, api_key: str | None, timeout: float, max_tokens: int,
                 sampling: dict | None = None):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model, self.api_key, self.timeout, self.max_tokens = model, api_key, timeout, max_tokens
        #: Request fields beyond the message list (ADR-074): temperature
        #: (0 unless told otherwise — the 7B ladder ran greedy), top_p,
        #: and for a thinking model ``reasoning_effort`` and the
        #: ``chat_template_kwargs`` that switch thinking off. Built by
        #: :func:`sampling_fields`; the envelope repeats it.
        self.sampling = sampling if sampling is not None else {"temperature": 0}
        #: ``auto`` sends the schemas as tools and asks the server to
        #: parse the model's calls (vLLM needs a --tool-call-parser for
        #: that, and defaults to auto whenever tools are sent). ``none``
        #: sends no tool field at all: the schemas ride the system prompt
        #: as a ``<functions>`` JSON block — the tag Olmo 3's own template
        #: uses — and the loop reads the calls out of the text
        #: (:func:`text_tool_calls`).
        self.tool_choice = "auto"
        #: How often the window had to be fitted or trimmed — the
        #: envelope reports both, so a run can see the window bind.
        self.fitted, self.elided = 0, 0
        #: The last call as it actually went — max_tokens finally sent,
        #: overflow events on the way, wall time — so the loop can log
        #: every call, not just the ones that errored (ADR-068).
        self.last: dict = {}
        #: Called with each tool message the window fit elides (ADR-091,
        #: D3) so the loop can revoke what that result had earned.
        self.on_elide: Callable[[dict], None] | None = None

    def chat(self, messages: list[dict], tools: list[dict], max_tokens: int | None = None) -> dict:
        """One completion, fitted to the model's window: a length
        refusal retries with ``max_tokens`` shrunk to what is left, and
        when that would leave fewer than :data:`MIN_COMPLETION` tokens
        the oldest tool results are elided (in place, stated) until the
        request fits or nothing is left to elide. *max_tokens* overrides
        the session's cap for this one call (the cut-completion retry).

        One fit per elide cycle (ADR-091, D1): the input count an
        endpoint reports is treated as a lower bound, not the prompt's
        size. vLLM's overflow message says "at least N" where N is
        ``window − max_tokens + 1``, so refitting from it shrinks the
        room by 17 tokens a try — one sklearn call absorbed 450 400s that
        way. If the fitted retry overflows again, the next step is an
        elision, not another fit."""
        max_tokens = max_tokens or self.max_tokens
        self.last = {"max_tokens_sent": max_tokens, "fitted": 0, "elided": 0, "window": None}
        started = time.monotonic()
        fitted_this_cycle = False
        while True:
            try:
                reply = self._post(messages, tools, max_tokens)
                u = reply.get("usage") or {}
                self.last.update(max_tokens_sent=max_tokens, prompt_tokens=u.get("prompt_tokens"),
                                 completion_tokens=u.get("completion_tokens"),
                                 finish_reason=(reply.get("choices") or [{}])[0].get("finish_reason"),
                                 wall_ms=int((time.monotonic() - started) * 1000))
                return reply
            except ContextOverflow as exc:
                self.last["window"] = exc.window
                room = exc.window - exc.inputs - 16
                if not fitted_this_cycle and room >= MIN_COMPLETION and room < max_tokens:
                    max_tokens = room
                    fitted_this_cycle = True
                    self.fitted += 1
                    self.last["fitted"] += 1
                    continue
                elided = elide_oldest_tool_result(messages)
                if elided is None:
                    raise
                if self.on_elide is not None:
                    self.on_elide(elided)
                self.elided += 1
                self.last["elided"] += 1
                max_tokens = self.max_tokens
                fitted_this_cycle = False

    def _post(self, messages: list[dict], tools: list[dict], max_tokens: int) -> dict:
        body = {"model": self.model, "messages": messages, "max_tokens": max_tokens, **self.sampling}
        if tools and self.tool_choice != "none":
            body["tools"] = tools
            body["tool_choice"] = self.tool_choice
        data = json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        last = None
        for attempt in range(4):
            req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")[:500]
                last = RuntimeError(f"HTTP {exc.code} from {self.url}: {detail}")
                if exc.code == 400 and (m := CONTEXT_LENGTH_RE.search(detail)):
                    raise ContextOverflow(str(last), int(m.group(1)), int(m.group(2)))
                if exc.code < 500 and exc.code != 429:
                    raise last
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last = RuntimeError(f"{type(exc).__name__}: {exc}")
            time.sleep(2 ** attempt)
        raise last  # type: ignore[misc]


def calls_path(transcript: str) -> str:
    """Where the per-call log goes: ``calls.jsonl`` beside the transcript."""
    return os.path.join(os.path.dirname(os.path.abspath(transcript)), "calls.jsonl")


#: A tool result shorter than this many characters is never elided
#: (ADR-091, D2): the placeholder is nearly as long, so eliding it saves
#: nothing and deletes the record of what was tried. sklearn-25102's U1
#: lost its four failed-edit errors (89–112 chars) this way and then
#: repeated the four edits.
ELIDE_FLOOR = 2 * len(ELIDED)


def elide_oldest_tool_result(messages: list[dict]) -> dict | None:
    """Replace the content of the oldest not-yet-elided tool result with
    a stated placeholder and return that message. Returns None when
    there is none left — the brief itself is then what does not fit,
    and that is an error.

    Never elided (ADR-091, D2): the result of a mutating tool — an edit's
    outcome is the session's action memory, and a model that cannot see
    a failed edit repeats it — and any result shorter than
    :data:`ELIDE_FLOOR`, which the placeholder would not shorten."""
    for message in messages:
        if message.get("role") != "tool" or message.get("content") == ELIDED:
            continue
        if message.get("name") in MUTATING_TOOLS:
            continue
        if len(message.get("content") or "") < ELIDE_FLOOR:
            continue
        message["content"] = ELIDED
        return message
    return None


def clip(text: str, limit: int) -> str:
    """A tool result cut to *limit* characters, head kept (a file's top
    carries its imports and signatures), the cut stated."""
    if len(text) <= limit:
        return text
    return text[:limit] + (f"\n… [truncated: {len(text) - limit:,} more characters not shown. This is NOT the "
                           "whole file: search_file for the name you need, then read_file that line range]")


# --------------------------------------------------------------------------
# The loop

def run(args: argparse.Namespace) -> dict:
    started = time.monotonic()
    workdir = os.path.abspath(args.workdir)
    prompt = args.prompt if args.prompt is not None else open(args.prompt_file, encoding="utf-8").read()
    read_only = args.role in READ_ONLY_ROLES
    mcp = MCPClient(args.mcp_config) if args.mcp_config else None
    tools = list(FILE_TOOLS)
    if not read_only:
        tools += WRITE_TOOLS
    mcp_names: set[str] = set()
    if mcp:
        offered = mcp.tools()
        if args.mcp_tools:
            # An arm that gets the proxy's exec and nothing else of Hobbes
            # (Calvin M0's arm O, design §3.2): the server still serves
            # every tool — only what the model is *offered* narrows, and a
            # call to a withheld tool never reaches it.
            keep = {n.strip() for n in args.mcp_tools.split(",") if n.strip()}
            offered = [t for t in offered if t["function"]["name"] in keep or t["function"]["name"].rsplit("__", 1)[-1] in keep]
        tools += offered
        mcp_names = {t["function"]["name"] for t in offered}
    elif not args.no_bash:
        tools.append(BASH_TOOL)
    endpoint = Endpoint(args.base_url, args.model, os.environ.get(args.api_key_env) or None,
                        args.timeout, args.max_tokens,
                        sampling_fields(args.temperature, args.top_p, args.reasoning_effort, args.thinking, args.sampling))
    endpoint.tool_choice = args.tool_choice
    system = SYSTEM_PROMPT.format(workdir=workdir)
    if args.tool_choice == "none":
        system += ("\nYou are provided with function signatures within <functions></functions> XML tags. "
                   "Call one or more of them by writing the calls within <function_calls></function_calls> "
                   "XML tags, one per line, as name(key=<json value>, ...).\n<functions>"
                   + json.dumps(tools) + "</functions>")
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": prompt}]
    usage = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
    turns, tool_calls_made, text_calls, final, error = 0, 0, 0, "", ""
    edited, nudges_left, nudges = False, args.max_nudges, 0
    reflected = False
    nudge_text = NUDGE_READ_ONLY if read_only else NUDGE
    seen_calls: set[tuple[str, str]] = set()
    applied_edits: set[tuple[str, str]] = set()
    applied_anchors: set[tuple[str, str]] = set()
    read_paths: set[str] = set()
    #: Which tool message holds which path's read (by message identity),
    #: the turn each path's ticket was earned on, and the paths whose
    #: ticket the window fit revoked (ADR-091, D3/D4).
    read_results: dict[int, str] = {}
    result_sigs: dict[int, tuple[str, str]] = {}
    read_turn: dict[str, int] = {}
    stale_reads: set[str] = set()
    has_reflect = any(n.endswith("reflect") for n in mcp_names)
    handoff_nudged = False
    cut_retried = 0
    calls_log: list[dict] = []
    prompt_max = 0
    repeats, dry_turns, refused_run = 0, 0, 0
    edited_since_exec = True  # the first run of any command is always fresh

    def revoke_on_elide(message: dict) -> None:
        # An elided result may be asked for again: the repeat guard
        # refuses a call whose answer is already in the window, and this
        # one no longer is.
        seen_calls.discard(result_sigs.get(id(message), ("", "")))
        # D3: a read the model can no longer see earns no edit. The ticket
        # survives only while another un-elided read of the same path is
        # still in the window.
        path = read_results.get(id(message))
        if path is None:
            return
        still = any(p == path and m.get("content") != ELIDED
                    for m in messages if m.get("role") == "tool"
                    for p in [read_results.get(id(m))])
        if not still:
            read_paths.discard(path)
            stale_reads.add(path)

    endpoint.on_elide = revoke_on_elide
    try:
        while turns < args.max_turns:
            turns += 1
            reply = endpoint.chat(messages, tools)
            u = reply.get("usage") or {}
            usage["input_tokens"] += int(u.get("prompt_tokens") or 0)
            usage["output_tokens"] += int(u.get("completion_tokens") or 0)
            usage["reasoning_tokens"] += reasoning_tokens(u)
            calls_log.append({"turn": turns, "reasoning_tokens": reasoning_tokens(u), **endpoint.last})
            prompt_max = max(prompt_max, int(u.get("prompt_tokens") or 0))
            choice = (reply.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            if choice.get("finish_reason") == "length" and not message.get("tool_calls"):
                # Cut at max_tokens with no structured call: whatever the
                # model was writing (a fenced tool call, a handoff) is
                # incomplete, and treating it as prose nudges the model
                # to write it again and be cut again. One retry with
                # more room (ADR-067); if that is cut too, it stands.
                cut_retried += 1
                reply = endpoint.chat(messages, tools, max_tokens=endpoint.max_tokens * CUT_RETRY_FACTOR)
                u = reply.get("usage") or {}
                usage["input_tokens"] += int(u.get("prompt_tokens") or 0)
                usage["output_tokens"] += int(u.get("completion_tokens") or 0)
                usage["reasoning_tokens"] += reasoning_tokens(u)
                calls_log.append({"turn": turns, "cut_retry": True, "reasoning_tokens": reasoning_tokens(u),
                                  **endpoint.last})
                prompt_max = max(prompt_max, int(u.get("prompt_tokens") or 0))
                choice = (reply.get("choices") or [{}])[0]
                message = choice.get("message") or {}
            calls = message.get("tool_calls") or []
            if not calls:
                calls = text_tool_calls(message.get("content") or "")
                text_calls += len(calls)
                if calls and _FUNCTION_CALLS.search(message.get("content") or ""):
                    # The template renders tool_calls as its own
                    # <function_calls> block; leaving the model's text
                    # copy in content would show it twice.
                    message["content"] = _FUNCTION_CALLS.sub("", message["content"]).strip()
            # A thinking model's reasoning comes back beside the content
            # (the server's reasoning parser splits it, ADR-074). It goes
            # on the message as received: the chat template of such a
            # model keeps earlier turns' reasoning in context
            # (preserve_thinking), and the transcript then shows why the
            # model did what it did, not only what. A template without
            # the field ignores it.
            reasoning = message.get("reasoning_content") or message.get("reasoning")
            messages.append({"role": "assistant", "content": message.get("content") or "",
                             **({"reasoning_content": reasoning} if reasoning else {}),
                             **({"tool_calls": calls} if calls else {})})
            productive = False
            refused_turn = False
            for call in calls:
                fn = call.get("function") or {}
                name = fn.get("name", "")
                raw = fn.get("arguments") or "{}"
                try:
                    targs = json.loads(raw)
                except json.JSONDecodeError as exc:
                    text, is_err = f"arguments were not valid JSON: {exc}", True
                else:
                    sig = (name, json.dumps(targs, sort_keys=True))
                    is_exec = is_exec_tool(name)
                    mutating = name in MUTATING_TOOLS or is_exec
                    if sig in seen_calls and not mutating:
                        # A repeated read-only call: refuse, do not re-run it.
                        text, is_err = REPEAT_REFUSAL, True
                        repeats += 1
                        refused_turn = True
                    elif is_exec and sig in seen_calls and not edited_since_exec:
                        # The same command again with no edit in between
                        # returns the same result: U4 of the first
                        # full-stage probe ran one failing pytest 8x until
                        # the window overflowed. A re-run after an edit is
                        # legitimate and still allowed.
                        text, is_err = EXEC_REPEAT_REFUSAL, True
                        repeats += 1
                        refused_turn = True
                    elif name in MUTATING_TOOLS and sig in applied_edits:
                        # The same edit, already applied. edit_file's
                        # new_text re-includes its anchor, so a repeat
                        # stacks a duplicate rather than being a no-op —
                        # django-11400's U4 stacked one broken block four
                        # times this way. Refuse the identical repeat; a
                        # genuinely different edit is still allowed.
                        text, is_err = EDIT_REPEAT_REFUSAL, True
                        repeats += 1
                        refused_turn = True
                    elif name == "edit_file" and (str(targs.get("old_text")) in str(targs.get("new_text"))) \
                            and (os.path.normpath(str(targs.get("path"))), str(targs.get("old_text"))) in applied_anchors:
                        # The reworded repeat ADR-066 does not cover: the
                        # same anchor on the same path, already applied,
                        # new_text again containing the anchor — django-
                        # 11400's U4 applied three *different* wordings
                        # of one block at one anchor and stacked all
                        # three (ADR-067).
                        text, is_err = ANCHOR_STACK_REFUSAL, True
                        repeats += 1
                        refused_turn = True
                    elif name in MUTATING_TOOLS and (tpath := os.path.normpath(str(targs.get("path")))) \
                            in stale_reads and tpath not in read_paths:
                        # D3: the read was elided; the ticket went with it.
                        text, is_err = ELIDED_READ_REFUSAL.format(path=targs.get("path")), True
                    elif name in MUTATING_TOOLS and read_turn.get(tpath) == turns:
                        # D4: read and edit batched in one turn — the
                        # anchor predates the read's result.
                        text, is_err = SAME_TURN_REFUSAL.format(path=targs.get("path")), True
                    else:
                        seen_calls.add(sig)
                        if name == "read_file":
                            rpath = os.path.normpath(str(targs.get("path")))
                            if rpath not in read_paths:
                                read_turn[rpath] = turns
                            stale_reads.discard(rpath)
                        if is_exec:
                            edited_since_exec = False
                        if mcp and name in mcp_names:
                            text, is_err = mcp.call(name, targs)
                        else:
                            text, is_err = native_call(name, targs, workdir, allow_bash=mcp is None and not args.no_bash,
                                                       allow_write=not read_only, read_paths=read_paths)
                        if not is_err and mutating:
                            edited = True
                            productive = True
                            if not is_exec:
                                edited_since_exec = True
                                applied_edits.add(sig)
                                if name == "edit_file":
                                    applied_anchors.add((os.path.normpath(str(targs.get("path"))),
                                                         str(targs.get("old_text"))))
                        if not is_err and name.endswith("reflect") and targs.get("kind") == "handoff":
                            # A read-only role's deliverable (planner, verifier):
                            # the handoff is its edit.
                            reflected = True
                            productive = True
                tool_calls_made += 1
                print(f"[turn {turns}] {name}({json.dumps(targs)[:160]}) → {'error' if is_err else 'ok'}",
                      file=sys.stderr, flush=True)
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "name": name,
                                 "content": clip(("ERROR: " if is_err else "") + text, args.max_result_chars)})
                if not is_err and isinstance(targs, dict):
                    result_sigs[id(messages[-1])] = (name, json.dumps(targs, sort_keys=True))
                    if name == "read_file":
                        read_results[id(messages[-1])] = os.path.normpath(str(targs.get("path")))
            # Pipeline discipline (ADR-058): a turn that changed nothing is
            # "dry". Nudge toward acting; once nudges are spent, a run of
            # dry turns is a stall, not progress — stop with a reason
            # rather than burn the turn budget (the 55-identical-calls loop).
            # For a read-only role the deliverable is a handoff reflection,
            # so "acted" means reflected, not edited.
            acted = reflected if read_only else edited
            # A run of turns that only re-issue refused calls is a stall
            # whether or not the session edited earlier: the first
            # full-stage probe's U6 had committed, then spent 57 of 60
            # turns on refused repeats (1.5M tokens) because "acted" held.
            refused_run = refused_run + 1 if (refused_turn and not productive) else 0
            if refused_run >= args.stall_after:
                error = f"no progress: {refused_run} turns of refused repeated calls ({repeats} refused in all)"
                break
            if productive:
                dry_turns = 0
            else:
                dry_turns += 1
                if not acted and nudges_left > 0 and (not calls or dry_turns >= args.nudge_after):
                    nudges_left -= 1
                    nudges += 1
                    dry_turns = 0
                    messages.append({"role": "user", "content": nudge_text})
                    continue
                if not calls:
                    if edited and not read_only and has_reflect and not reflected and not handoff_nudged:
                        # D8: edits made, prose given, no handoff sent.
                        handoff_nudged = True
                        nudges += 1
                        messages.append({"role": "user", "content": NUDGE_HANDOFF})
                        continue
                    final = message.get("content") or ""
                    break
                if not acted and dry_turns >= args.stall_after:
                    what = "a handoff" if read_only else "an edit"
                    error = f"no progress: {dry_turns} turns without {what} after {nudges} nudge(s)"
                    break
        else:
            error = f"turn budget ({args.max_turns}) exhausted"
    except Exception as exc:  # noqa: BLE001 — the envelope carries it
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if mcp:
            mcp.close()
        if getattr(args, "transcript", None):
            # The whole message list, so a trace does not stop at the
            # tool-call line (ADR-064). Written once at the end; the
            # finally runs on the crash path too.
            try:
                os.makedirs(os.path.dirname(os.path.abspath(args.transcript)), exist_ok=True)
                with open(args.transcript, "w", encoding="utf-8") as fh:
                    for m in messages:
                        fh.write(json.dumps(m, ensure_ascii=False) + "\n")
                # Every call as it went — prompt size, completion size,
                # max_tokens actually sent, finish_reason, overflow
                # events, wall — beside the transcript (ADR-068). A
                # saturated window that never errors is visible here,
                # not only the 400s the fit absorbed.
                with open(calls_path(args.transcript), "w", encoding="utf-8") as fh:
                    for c in calls_log:
                        fh.write(json.dumps(c) + "\n")
            except OSError as exc:
                print(f"transcript: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    duration = int((time.monotonic() - started) * 1000)
    return {
        "type": "result", "subtype": "success" if not error else "error",
        "is_error": bool(error), "duration_ms": duration, "num_turns": turns,
        "tool_calls": tool_calls_made, "text_tool_calls": text_calls,
        "context_fitted": endpoint.fitted, "context_elided": endpoint.elided,
        "cut_retried": cut_retried, "nudges": nudges,
        # The window as it was actually used: the largest prompt any call
        # carried, and the calls that needed a fit or an elision to go
        # through at all (ADR-068).
        "prompt_tokens_max": prompt_max,
        "calls_saturated": sum(1 for c in calls_log if c.get("fitted") or c.get("elided")),
        "calls": len(calls_log), "edited": edited, "reflected": reflected, "repeats_refused": repeats,
        "handoff_nudged": handoff_nudged,
        "role": args.role,
        "result": final or error, "model": args.model,
        "runtime": "hobbes-agent-loop", "usage": usage,
        # How the completions were asked for (ADR-074): the bench
        # records it per run, so a rung's sampling is on the record.
        "sampling": endpoint.sampling,
    }


def parse(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-url", required=True, help="OpenAI-compatible API root, e.g. https://host/v1")
    p.add_argument("--model", required=True)
    p.add_argument("--api-key-env", default="HOBBES_LLM_API_KEY")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt")
    g.add_argument("--prompt-file")
    p.add_argument("--mcp-config", help="the session's mcp.json; tools come from its server, bash is withheld")
    p.add_argument("--role", default="implementer",
                   help="the session role; a read-only role (planner, reviewer, verifier) gets no write "
                        "tools and is disciplined toward a reflect handoff instead of an edit")
    p.add_argument("--workdir", default=".")
    p.add_argument("--tool-choice", choices=("auto", "none"), default="auto",
                   help="auto: the schemas go as tools and the server parses the calls; none: no tool field is "
                        "sent, the schemas ride the system prompt as a <functions> JSON block and the loop reads "
                        "the calls from the text (a model whose call syntax the server cannot parse — Olmo 3)")
    p.add_argument("--mcp-tools", default=None,
                   help="offer only these MCP tools (comma-separated names, e.g. `exec`); the rest are withheld "
                        "from the model and refused if called (Calvin M0 arm O)")
    p.add_argument("--no-bash", action="store_true",
                   help="withhold the native bash tool: file tools only, no exec at all (the TTT cell's arms, "
                        "ADR-099 review item 9 — repo code never runs, and policy is the same for every arm)")
    p.add_argument("--max-turns", type=int, default=60)
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--max-result-chars", type=int, default=12_000,
                   help="a tool result is clipped to this many characters, the cut stated (default 12000)")
    p.add_argument("--max-nudges", type=int, default=2,
                   help="how many times to nudge a model that stops at a prose plan before editing (default 2)")
    p.add_argument("--nudge-after", type=int, default=3,
                   help="dry (no-edit) turns before a mid-stream nudge (default 3)")
    p.add_argument("--stall-after", type=int, default=6,
                   help="dry (no-edit) turns before stopping a stalled session with a reason (default 6)")
    p.add_argument("--transcript", help="write the full message list here as JSONL on exit (ADR-064)")
    p.add_argument("--temperature", type=float, default=0.0,
                   help="sampling temperature (default 0 = greedy; a thinking model wants its own, ADR-074)")
    p.add_argument("--sampling", choices=("greedy", "model-default"), default="greedy",
                   help="greedy sends --temperature; model-default sends no temperature field (an endpoint that rejects it)")
    p.add_argument("--top-p", type=float, default=None, help="nucleus sampling, sent only when given")
    p.add_argument("--reasoning-effort", default=None,
                   help="a thinking model's reasoning depth (low|medium|high|xhigh as the model defines them); "
                        "sent only when given")
    p.add_argument("--thinking", choices=("server", "on", "off"), default="server",
                   help="a thinking model's mode: the server's default, on, or off (chat_template_kwargs "
                        "enable_thinking); a model without the switch ignores it")
    p.add_argument("--timeout", type=float, default=600.0)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    envelope = run(parse(sys.argv[1:] if argv is None else argv))
    print(json.dumps(envelope), flush=True)
    return 1 if envelope["is_error"] else 0


if __name__ == "__main__":
    sys.exit(main())
