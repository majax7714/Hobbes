"""The Hobbes server the opencode v2 TUI talks to (DEC-013).

The TUI (``tui/``, run unmodified with ``--server``) speaks opencode's HTTP
and event-stream API. This package serves the slice of it the TUI needs,
backed by ``hobbes.watterson.providers`` sessions and ``hobbes.watterson.permissions``:

- ``http``: a small asyncio HTTP/1.1 server with an event stream;
- ``ids``: opencode's id format;
- ``turns``: one prompt turn, provider events to opencode events;
- ``opencode``: the routes, the catalogs and the session store.

Written against opencode v2.0.29 (tag ``042d083``). Glue outside
``hobbes.extract`` and ``hobbes.watterson.providers``.
"""
