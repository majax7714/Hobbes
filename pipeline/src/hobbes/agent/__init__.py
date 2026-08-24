"""The owned agent runtime (ADR-056).

A minimal tool loop against any OpenAI-compatible chat endpoint — the
runtime both benchmark arms run on when the model is not Claude
(ADR-055's small-model ladder served from the owner's compute). It
replaces Claude Code *as the loop*, not as anything else: the harness
arm's tools are exactly the hobbes-proxy's MCP tools plus confined file
tools, the pure arm's are bash plus the same file tools, and neither
arm carries a hidden system prompt sized for a frontier model.

:mod:`hobbes.agent.loop` is deliberately **stdlib-only and one file**:
``hobbes-session`` copies it into the session dir and runs it with the
sandbox image's ``python3`` — the image gains no dependency, and the
runtime a session runs is the one the host tested. It prints the same
result envelope Claude Code does, so :mod:`hobbes.bench.accounting`
meters both runtimes with one reader.
"""
