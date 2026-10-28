"""Start the Hobbes server and our opencode TUI against it (DEC-013, DEC-025).

The server listens on loopback with a fresh password, and the TUI
(``tui/bin/opencode``, built from ``tui/opencode`` by ``tui/build.sh``) runs in this terminal with
``--server`` pointing at it; it never starts opencode's own service.
The TUI's files (prompt history, layout state) go under
``$HOBBES_CACHE_DIR/tui/xdg`` instead of the user's opencode dirs, and its
self-updater is off. Session logs (the transcripts) go to
``$HOBBES_CACHE_DIR/tui/sessions/``. The server logs to
``$HOBBES_CACHE_DIR/tui/server.log`` so nothing writes over the TUI's screen.
The TUI loads Hobbes's graph panel plugin (``tui/plugins/graph``, DEC-015)
by absolute path through ``OPENCODE_CLI_CONFIG_CONTENT``. ``serve_only`` runs
just the server and prints how to attach.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import TextIO

from hobbes.watterson.serve.http import Server
from hobbes.watterson.serve.opencode import HobbesServer

TUI_DIR = Path(__file__).resolve().parents[5] / "tui"
TUI_BIN = TUI_DIR / "bin" / ("opencode.exe" if sys.platform == "win32" else "opencode")
#: The graph panel plugin (DEC-015): a directory holding ``tui.tsx``.
PLUGIN_DIR = TUI_DIR / "plugins" / "graph"
TUI_INSTALL_HINT = "run `tui/build.sh` at the repo root (DEC-025)"


def cache_dir(env=os.environ) -> Path:
    return Path(env.get("HOBBES_CACHE_DIR") or "~/.watterson/cache").expanduser() / "tui"


def tui_env(url_password: str, base: Path, env=os.environ) -> dict[str, str]:
    """The TUI's environment: our password, no updater, our plugin, XDG dirs under *base*."""
    out = dict(env)
    out.update({
        "OPENCODE_PASSWORD": url_password,
        "OPENCODE_DISABLE_AUTOUPDATE": "1",
        "OPENCODE_CLI_CONFIG_CONTENT": json.dumps({"plugins": [str(PLUGIN_DIR)]}),
        **{f"XDG_{kind.upper()}_HOME": str(base / "xdg" / kind) for kind in ("data", "config", "state", "cache")},
    })
    out.pop("OPENCODE_SERVER_PASSWORD", None)
    return out


async def run(repo: Path, registry: dict, *, serve_only: bool = False, port: int = 0,
              out: TextIO = sys.stderr) -> int:
    base = cache_dir()
    base.mkdir(parents=True, exist_ok=True)
    log_file = (base / "server.log").open("a")

    def log(line: str) -> None:
        log_file.write(f"{time.strftime('%H:%M:%S')} {line}\n")
        log_file.flush()

    password = secrets.token_urlsafe(24)
    app = HobbesServer(repo, registry, log=log, store=base / "sessions")
    server = Server(app.router, password, log=log)
    await server.start(port=port)
    log(f"serving {repo} at {server.url}")
    try:
        if serve_only:
            print(f"hobbes: serving {repo} at {server.url}\n"
                  f"  attach: OPENCODE_PASSWORD={password} {TUI_BIN} --server {server.url} {repo}",
                  file=out, flush=True)
            await asyncio.Event().wait()
            return 0
        if not TUI_BIN.exists():
            print(f"hobbes: the TUI is not installed: {TUI_INSTALL_HINT}", file=out)
            return 2
        proc = await asyncio.create_subprocess_exec(
            str(TUI_BIN), "--server", server.url, str(repo), env=tui_env(password, base))
        return await proc.wait()
    finally:
        await app.close()
        await server.close()
        log_file.close()
