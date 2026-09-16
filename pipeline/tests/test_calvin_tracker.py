"""Tests for `scripts/calvin_tracker.py`: parsing the harness's session logs, the pinned rows from the real logs, totals over synthetic logs, and the render/check drift gate."""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("calvin_tracker", Path(__file__).resolve().parents[1] / "scripts" / "calvin_tracker.py")
ct = importlib.util.module_from_spec(spec)
sys.modules["calvin_tracker"] = ct
spec.loader.exec_module(ct)

SESSIONS_DIR = Path(__file__).resolve().parents[2] / "docs" / "calvin" / "sessions"


def _record(suffix: str) -> dict:
    path = next(p for p in SESSIONS_DIR.glob("S-*.md") if p.stem.endswith(suffix))
    return ct.parse_session(path)


def test_check_passes_over_the_repo():
    """`check`'s drift test: the README's tracker block is not stale against a fresh render of the real logs."""
    records = ct.load_sessions(SESSIONS_DIR)
    fresh = ct.render_table(records)
    current = ct.current_block((SESSIONS_DIR / "README.md").read_text())
    assert current == fresh, "the tracker block is stale — run `pipeline/scripts/calvin_tracker.py render`"


def test_9cad_the_usual_shape():
    """The usual-shape log (D-r's fix): turns, cost and wall parsed as numbers, area from its Branch line, review and outcome from the review block."""
    r = _record("9cad")
    assert r["turns"] == "15/80"
    assert r["cost"] == pytest.approx(0.2914)
    assert r["wall"] == pytest.approx(60.4)
    assert r["area"] == "harness and sandbox"
    assert r["review_gate"] == "right-clear"
    assert r["outcome"] == "merged"


def test_96df_a_rejected_token_no_branch():
    """A rejected token left no diff: turns 1/40, a reported cost of exactly $0.00, an `empty` verify, no mapped area, `n/a` review."""
    r = _record("96df")
    assert r["turns"] == "1/40"
    assert r["cost"] == pytest.approx(0.0)
    assert r["verify"] == "empty"
    assert r["area"] == "—"
    assert r["review_gate"] == "n/a"
    assert r["outcome"] == "discarded"


def test_b126_stopped_no_result():
    """A session the developer stopped mid-run: no reported cost at all and no turns numerator (`— of 200`), discarded."""
    r = _record("b126")
    assert r["cost"] is None
    assert r["turns"] == "—"
    assert r["outcome"] == "discarded"


def test_3c45_area_is_knowledge_tools():
    """A Branch line under `go/internal/knowledge/` reads as the `knowledge tools` area."""
    assert _record("3c45")["area"] == "knowledge tools"


def test_417f_the_knowledge_tools_schemas_in_the_proxy_are_knowledge_tools():
    """`go/internal/proxy/knowledge.go` holds the knowledge tools' MCP schemas, so the `path` alias (417f) reads as `knowledge tools`, not the harness."""
    assert _record("417f")["area"] == "knowledge tools"


def test_a323_area_is_extraction():
    """A Branch line under `pipeline/src/hobbes/extract/` reads as the `extraction` area."""
    assert _record("a323")["area"] == "extraction"


def test_5d5f_area_is_oracle_lane():
    """A Branch line under `bench/oracle/` reads as the `oracle lane` area."""
    assert _record("5d5f")["area"] == "oracle lane"


SESSION_TEMPLATE = """# Harness session `{id}`

- **Task:** Do a thing. (brief `/x/brief.md`, task sha256 `abc123`)
- **Parent:** `deadbeef` of `hobbes_public`
- **Doer:** {doer}
- **Egress:** allow api.anthropic.com:443; opened `api.anthropic.com:443`×3; refused {refused}
- **Policy:** {policy}
- **Branch:** {branch}
- **Gate:** **clear** at `deadbeef` (gate v2, grounder v3, record `cafef00d`); unknown 0; map over 2 file(s), 0.0% of their lines uncaptured; partition checked
- **Verify:** {verify}

## Review

- gate: {gate}
- outcome: {outcome}
- notes: none
"""


def _write_session(tmp_path: Path, sid: str, **overrides: str) -> None:
    """Write one synthetic session log named *sid* under *tmp_path*, from `SESSION_TEMPLATE` with *overrides* applied over the usual-shape defaults."""
    defaults = dict(
        doer="1.0.0 (Claude Code); model the default; turns 10 of 40; result `success`; "
             "reported cost $1.5000 (the envelope's figure, on the subscription); wall 30.0 s; session exit 0",
        refused="none",
        policy="1 exec decision(s) — `allow`×1",
        branch=f"`hobbes/{sid}`, 1 commit(s); files: `pipeline/src/hobbes/extract/x.py`",
        verify="pass; tests 1, regressions 0; {'P2P': 1}",
        gate="right-clear",
        outcome="merged",
    )
    defaults.update(overrides)
    (tmp_path / f"{sid}.md").write_text(SESSION_TEMPLATE.format(id=sid, **defaults))


def test_totals_over_synthetic_logs(tmp_path):
    """Totals over three minimal logs: the session count, the cost sum over only the sessions that report one, the union of areas, one false-block and one missed counted, and egress refusals summed."""
    _write_session(
        tmp_path, "S-20260101T000000Z-aaaa",
        branch="`hobbes/a`, 1 commit(s); files: `pipeline/src/hobbes/extract/x.py`",
        gate="false-block", outcome="reworked",
    )
    _write_session(
        tmp_path, "S-20260102T000000Z-bbbb",
        branch="`hobbes/b`, 1 commit(s); files: `go/internal/knowledge/knowledge.go`",
        refused="`llm`×2",
        doer="1.0.0 (Claude Code); model the default; turns — of 40; result `—`; wall 5.0 s; session exit 143",
        gate="missed", outcome="merged",
    )
    _write_session(
        tmp_path, "S-20260103T000000Z-cccc",
        branch="`hobbes/c`, 1 commit(s); files: `bench/oracle/internal/x.go`",
    )

    records = ct.load_sessions(tmp_path)
    table = ct.render_table(records)

    assert "3 of 40 sessions" in table
    assert "extraction, knowledge tools, oracle lane (3; at least 3)" in table
    assert "false blocks 1" in table
    assert "missed 1" in table
    assert "egress 2" in table
    assert "reported cost $3.00 over 2 of 3 sessions" in table


def test_unparseable_doer_line_raises(tmp_path):
    """A Doer line matching none of the harness's known shapes raises `ValueError`, naming the file."""
    sid = "S-20260101T000000Z-dead"
    _write_session(tmp_path, sid, doer="not a real doer line at all")
    path = tmp_path / f"{sid}.md"
    with pytest.raises(ValueError, match=re.escape(str(path))):
        ct.parse_session(path)


def test_a_doer_line_naming_its_model_parses(tmp_path):
    """A Doer line naming the model (`model claude-opus-5`, ADR-107's 2026-09-14 amendment) parses as `model the default` does; the turns and cost still count."""
    sid = "S-20260101T000000Z-cd8e"
    _write_session(tmp_path, sid, doer="2.1.270 (Claude Code); model claude-opus-5; turns 22 of 60; result `success`; "
                                       "reported cost $1.1112 (the envelope's figure, on the subscription); wall 75.6 s; session exit 0")
    rec = ct.parse_session(tmp_path / f"{sid}.md")
    assert (rec["turns_num"], rec["turns_den"], rec["cost"]) == (22, 60, 1.1112)


def test_a_blocked_gate_line_naming_its_classes_parses(tmp_path):
    """A Gate line the gate blocked (`**blocked** … — blocking: near-miss; …`, the shape `f3c1` first wrote) parses, with its verdict; the row it names on the next line does not break the parse."""
    sid = "S-20260101T000000Z-f3c1"
    _write_session(tmp_path, sid)
    path = tmp_path / f"{sid}.md"
    clear = ("- **Gate:** **clear** at `deadbeef` (gate v2, grounder v3, record `cafef00d`); unknown 0; "
             "map over 2 file(s), 0.0% of their lines uncaptured; partition checked")
    blocked = ("- **Gate:** **blocked** at `deadbeef` (gate v2, grounder v3, record `cafef00d`) — blocking: near-miss; "
               "unknown 0; map over 2 file(s), 0.0% of their lines uncaptured; partition checked\n"
               "  - `near-miss` scip/index.mjs:264 `check`")
    path.write_text(path.read_text().replace(clear, blocked))
    assert ct.parse_session(path)["gate"] == "blocked"


def test_a_gate_line_at_newer_rule_versions_parses(tmp_path):
    """The gate's and the grounder's versions are read, not pinned, and a non-zero uncaptured percentage parses.

    Found by use on 2026-09-16: `GATE_RE` held `gate v2, grounder v3` as
    literals, so the first session run at grounder v4 (0.2.28-beta's C-91
    fix) could not be parsed and `calvin_tracker.py render` refused the
    harness's own output. Every fixture here carried the same literals,
    which is why the drift test could not catch it — so this case moves
    both numbers and the percentage away from the fixture's values.
    """
    sid = "S-20260101T000000Z-4a44"
    _write_session(tmp_path, sid)
    path = tmp_path / f"{sid}.md"
    pinned = ("- **Gate:** **clear** at `deadbeef` (gate v2, grounder v3, record `cafef00d`); unknown 0; "
              "map over 2 file(s), 0.0% of their lines uncaptured; partition checked")
    moved = ("- **Gate:** **clear** at `deadbeef` (gate v3, grounder v4, record `cafef00d`); unknown 0; "
             "map over 9 file(s), 7.0% of their lines uncaptured; partition checked")
    path.write_text(path.read_text().replace(pinned, moved))
    assert ct.parse_session(path)["gate"] == "clear"


def test_policy_line_with_the_stream_bracket_parses(tmp_path):
    """A Policy line carrying the sink's bracket (`; records: stream opened→closed`, ADR-112) parses, with and without an escalation clause before it; the kinds still count."""
    sid = "S-20260101T000000Z-beef"
    _write_session(tmp_path, sid, policy="3 exec decision(s) — `allow`×3; records: stream opened→closed")
    rec = ct.parse_session(tmp_path / f"{sid}.md")
    assert (rec["policy_escalate"], rec["policy_deny"]) == (0, 0)
    sid2 = "S-20260101T000001Z-cafe"
    _write_session(
        tmp_path, sid2,
        policy="5 exec decision(s) — `allow`×4, `escalate`×1; escalated: `/bin/sh -c git rm x`; records: WARNING never listened",
    )
    rec2 = ct.parse_session(tmp_path / f"{sid2}.md")
    assert rec2["policy_escalate"] == 1
