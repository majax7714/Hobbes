"""The coordinator's and the workers' tools as a stdio MCP server, relayed to the driver (DEC-022).

The harness starts this for the coordinator's session as
``python -I -S lead_mcp.py SOCKET`` (MCP server ``hobbes-lead``). It serves
four tools, ``propose_plan``, ``dispatch``, ``wait`` and ``finish``, and hands each
call to the ``hobbes job`` driver over the Unix socket in ``argv[1]``, as
``hook_client.py`` does for hooks (DEC-010): the driver asks the user and
runs the workers, so a plan question reaches the user's terminal and not
the harness's. With ``argv[2]`` ``hobbes-worker`` it is a worker's server
instead, serving one tool, ``report``, to the dispatch driver; with
``hobbes-mapper``, the mapper's (DEC-023), serving ``save_mapping``. Standard library only. One JSON request per connection,
``{"tool", "arguments"}``; the reply is ``{"text", "error"}``. No timeout:
a dispatch runs a whole worker. MCP's stdio transport is one JSON-RPC
message per line.
"""

import json
import socket
import sys

SERVER = "hobbes-lead"
VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2025-06-18"

TOOLS = [
    {
        "name": "propose_plan",
        "description": (
            "Show the user your plan for the job and ask for approval. Call this before any "
            "dispatch. The reply says whether the user approved, with any comment; if not "
            "approved, revise the plan and propose again."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"plan": {"type": "string", "description": "the plan: the units of work, each with its role"}},
            "required": ["plan"],
        },
    },
    {
        "name": "dispatch",
        "description": (
            "Hand one unit of work to a worker in a role. Returns at once with its ticket: the "
            "worker starts, or waits in a queue while the most workers allowed are running. It "
            "works on its own branch; the driver commits its work, merges the main branch in, runs "
            "the repo's tests and merges it when they pass, one worker at a time. Call wait for "
            "the handoffs. Only after an approved plan, and before you edit any files."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "role": {"type": "string", "description": "a worker role from the repo's roles"},
                "brief": {"type": "string", "description": "what the worker is to do, self-contained"},
            },
            "required": ["role", "brief"],
        },
    },
    {
        "name": "wait",
        "description": (
            "Wait until every dispatched worker is done. Returns their handoffs not returned "
            "before, as a JSON list: each with its ticket, outcome (merged; stopped, with the "
            "reason; or review, kept on its branch for the user), the worker's report, the files "
            "and the test result."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "finish",
        "description": ("End the job once wait has returned every handoff and the docs are updated, "
                        "with a short summary."),
        "inputSchema": {
            "type": "object",
            "properties": {"summary": {"type": "string", "description": "what was done and what is left"}},
            "required": ["summary"],
        },
    },
]

WORKER_TOOLS = [
    {
        "name": "report",
        "description": (
            "Hand back your work when you are done, as your last step. The outcome is done (ready "
            "to merge), blocked (you could not finish; nothing merges) or review (ready, but the "
            "user should review it before a merge). The driver commits your work and tests it "
            "before any merge, whatever you report."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "outcome": {"type": "string", "enum": ["done", "blocked", "review"]},
                "report": {"type": "string",
                           "description": "what you changed and why, what you checked, and anything left or failing"},
            },
            "required": ["outcome", "report"],
        },
    },
]

MAPPER_TOOLS = [
    {
        "name": "save_mapping",
        "description": (
            "Save the repo's whole agent mapping. It is checked first (it loads, every agent is "
            "installed, every role's prompt is given or already there) and written only when it "
            "passes; otherwise the reply lists what to fix."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "roles_toml": {"type": "string", "description": "the full text of .hobbes/roles.toml"},
                "prompts": {
                    "type": "object", "additionalProperties": {"type": "string"},
                    "description": "each role's prompt path under .hobbes/ (as its prompt key names it) to its text",
                },
            },
            "required": ["roles_toml", "prompts"],
        },
    },
]

SERVERS = {SERVER: TOOLS, "hobbes-worker": WORKER_TOOLS, "hobbes-mapper": MAPPER_TOOLS}


def relay(path: str, tool: str, arguments: dict) -> tuple[str, bool]:
    """Hand one call to the driver; its reply text and whether it is an error."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.connect(path)
            conn.sendall(json.dumps({"tool": tool, "arguments": arguments}).encode())
            conn.shutdown(socket.SHUT_WR)
            chunks = []
            while chunk := conn.recv(65536):
                chunks.append(chunk)
        reply = json.loads(b"".join(chunks) or b"{}")
        return str(reply.get("text", "")), bool(reply.get("error"))
    except (OSError, ValueError) as exc:
        return f"the hobbes job driver is not reachable: {exc}", True


def handle(path: str, message: dict, server: str = SERVER) -> dict | None:
    """The response to one JSON-RPC message to *server*, or None for a notification."""
    tools = SERVERS[server]
    method, ident = message.get("method"), message.get("id")
    if ident is None:
        return None
    params = message.get("params") or {}
    if method == "initialize":
        result = {
            "protocolVersion": params.get("protocolVersion") or DEFAULT_PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": server, "version": VERSION},
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": tools}
    elif method == "tools/call":
        name = params.get("name")
        if name not in {tool["name"] for tool in tools}:
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": f"unknown tool {name!r}"}}
        text, error = relay(path, name, params.get("arguments") or {})
        result = {"content": [{"type": "text", "text": text}], "isError": error}
    else:
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": f"no method {method!r}"}}
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def main(argv: list[str]) -> int:
    path = argv[1] if len(argv) > 1 else ""
    server = argv[2] if len(argv) > 2 and argv[2] in SERVERS else SERVER
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            response = handle(path, message, server) if isinstance(message, dict) else None
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
