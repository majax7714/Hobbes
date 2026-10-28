"""The dev environment (ADR-181), moved from watterson-environment@a65b6b1.

The ``watterson`` command (``hobbes.watterson.cli``) puts an agent harness
under Hobbes: the provider layer (``providers``, DEC-004), live sessions with
a fresh graph between turns (``freshness``, ``snapshot``, ``session_graph``,
``live_session``; DEC-005/006/009), permission routes and hooks
(``permissions``, ``hooks``; DEC-007/010), the knowledge tools
(``knowledge``, DEC-008), the TUI's server (``serve``, DEC-013), the level
views and the review page (``levels``, ``architecture``, ``repodocs``,
``review``; DEC-014/018/020/021), and agent roles with a coordinator
(``roles``, ``dispatch``, ``lead``, ``mapper``; DEC-022/023). Its decisions,
DEC-001…027, are in ``docs/watterson/decisions/``.

It reads the graph through ``hobbes.artifacts`` and ingests through
``hobbes.cli``; it never imports a parser (I-4).
"""
