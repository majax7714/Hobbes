"""The decision ledger and the blocking readiness gate (ADR-026)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from hobbes import decisions
from hobbes.decisions import (
    APPROVED,
    DENIED,
    EDITED,
    confirm_intent,
    content_key,
    load,
    pending_invariants,
    readiness,
    record_verdict,
    save,
)


def write_inferred(repo: Path, records: list[dict]) -> None:
    path = repo / ".hobbes" / "derived" / "docs" / "invariants.inferred.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "kind": "inferred-invariants",
                "sha": "abc",
                "dirty": False,
                "invariants": records,
            },
            sort_keys=False,
        )
    )


def inferred(statement: str, scope: str = "src", ident: str = "INF-1") -> dict:
    return {
        "id": ident,
        "statement": statement,
        "scope": scope,
        "status": "inferred",
        "evidence": [{"path": "src/a.py", "line": 1}],
        "guarded_by": [],
    }


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


class TestContentKey:
    def test_the_same_text_is_the_same_decision(self):
        assert content_key("only core mints tokens", "src") == content_key(
            "only core mints tokens", "src"
        )

    def test_reflowing_whitespace_is_not_a_new_decision(self):
        # A regenerated payload that wraps differently must not re-ask.
        assert content_key("only core\n  mints   tokens", "src") == content_key(
            "only core mints tokens", "src"
        )

    def test_changed_words_are_a_new_decision(self):
        assert content_key("only core mints tokens", "src") != content_key(
            "only auth mints tokens", "src"
        )

    def test_changed_scope_is_a_new_decision(self):
        # Same claim over a wider blast radius is a different question.
        assert content_key("only core mints tokens", "src") != content_key(
            "only core mints tokens", "."
        )

    def test_the_id_is_not_part_of_identity(self):
        # INF-n is positional, so it says nothing about what was decided.
        a = inferred("x", "src", "INF-1")
        b = inferred("x", "src", "INF-9")
        assert content_key(a["statement"], a["scope"]) == content_key(
            b["statement"], b["scope"]
        )


class TestLedger:
    def test_an_absent_ledger_is_empty_not_an_error(self, repo):
        ledger = load(repo)
        assert not ledger.intent_confirmed
        assert ledger.decisions == {}

    def test_a_verdict_round_trips(self, repo):
        record_verdict(repo, "only core mints tokens", "src", APPROVED, record="I-1")
        ledger = load(repo)
        decision = ledger.verdict_for(content_key("only core mints tokens", "src"))
        assert decision.verdict == APPROVED
        assert decision.record == "I-1"
        assert decision.decided_at
        # The original wording is kept, so an edit stays inspectable.
        assert decision.source_statement == "only core mints tokens"

    def test_a_later_verdict_replaces_the_earlier_one(self, repo):
        record_verdict(repo, "s", "src", APPROVED, record="I-1")
        record_verdict(repo, "s", "src", DENIED)
        assert load(repo).verdict_for(content_key("s", "src")).verdict == DENIED

    def test_an_unknown_verdict_is_refused(self, repo):
        with pytest.raises(ValueError, match="verdict must be one of"):
            record_verdict(repo, "s", "src", "maybe")

    def test_a_mangled_row_is_dropped_not_trusted(self, repo):
        # An unreadable verdict must re-ask, never auto-approve.
        path = repo / ".hobbes" / "decisions.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "intent": {},
                    "invariants": [
                        {"key": "sha256:abc", "verdict": "sure-why-not"},
                        {"verdict": "approved"},
                        {"key": "sha256:def", "verdict": "approved"},
                    ],
                }
            )
        )
        ledger = load(repo)
        assert list(ledger.decisions) == ["sha256:def"]

    def test_the_file_is_yaml_a_human_can_read(self, repo):
        record_verdict(repo, "only core mints tokens", "src", APPROVED, record="I-1")
        text = (repo / ".hobbes" / "decisions.yaml").read_text()
        assert text.startswith("#")
        assert "only core mints tokens" in text
        assert yaml.safe_load(text)["invariants"][0]["verdict"] == APPROVED

    def test_the_ledger_is_not_derived_output(self, repo):
        # It is human judgement; it must not sit where a regeneration
        # would wipe it.
        path = save(repo, load(repo))
        assert ".hobbes/derived" not in str(path)
        assert path.name == "decisions.yaml"


class TestIntent:
    def test_intent_starts_unconfirmed(self, repo):
        assert not load(repo).intent_confirmed

    def test_confirming_records_when_and_against_what(self, repo):
        ledger = confirm_intent(repo, policy_blob="blob123")
        assert ledger.intent_confirmed
        assert ledger.intent_policy_blob == "blob123"
        assert load(repo).intent_confirmed_at == ledger.intent_confirmed_at

    def test_confirmation_survives_a_later_invariant_verdict(self, repo):
        confirm_intent(repo, policy_blob="blob123")
        record_verdict(repo, "s", "src", DENIED)
        assert load(repo).intent_confirmed


class TestPendingQueue:
    def test_no_narration_means_nothing_pending(self, repo):
        assert pending_invariants(repo) == []

    def test_undecided_records_are_pending(self, repo):
        write_inferred(repo, [inferred("a", "src", "INF-1"), inferred("b", "lib", "INF-2")])
        assert [p.statement for p in pending_invariants(repo)] == ["a", "b"]

    def test_a_decided_record_drops_out(self, repo):
        write_inferred(repo, [inferred("a"), inferred("b", "lib", "INF-2")])
        record_verdict(repo, "a", "src", APPROVED, record="I-1")
        assert [p.statement for p in pending_invariants(repo)] == ["b"]

    def test_a_denial_keeps_it_out(self, repo):
        # Re-narration re-infers what was rejected; a gate that asks the
        # same question forever teaches you to click through it.
        write_inferred(repo, [inferred("a")])
        record_verdict(repo, "a", "src", DENIED)
        assert pending_invariants(repo) == []
        write_inferred(repo, [inferred("a", "src", "INF-7")])
        assert pending_invariants(repo) == []

    def test_reworded_text_comes_back(self, repo):
        write_inferred(repo, [inferred("a")])
        record_verdict(repo, "a", "src", APPROVED, record="I-1")
        write_inferred(repo, [inferred("a, but only on Tuesdays")])
        assert len(pending_invariants(repo)) == 1

    def test_a_renumbered_record_does_not_come_back(self, repo):
        # The id moved, the text did not — the decision still stands.
        write_inferred(repo, [inferred("a", "src", "INF-1")])
        record_verdict(repo, "a", "src", APPROVED, record="I-1")
        write_inferred(repo, [inferred("a", "src", "INF-4")])
        assert pending_invariants(repo) == []

    def test_an_approval_does_not_bleed_onto_a_renumbered_neighbour(self, repo):
        # The trap this design exists to avoid: INF-2 is a different
        # statement next run, and must not inherit INF-2's old verdict.
        write_inferred(repo, [inferred("a", "src", "INF-1"), inferred("b", "src", "INF-2")])
        record_verdict(repo, "b", "src", APPROVED, record="I-1")
        write_inferred(repo, [inferred("b", "src", "INF-1"), inferred("c", "src", "INF-2")])
        assert [p.statement for p in pending_invariants(repo)] == ["c"]

    def test_pending_carries_evidence_for_the_reviewer(self, repo):
        write_inferred(repo, [inferred("a")])
        (item,) = pending_invariants(repo)
        assert item.evidence == [{"path": "src/a.py", "line": 1}]
        assert item.key.startswith("sha256:")


class TestReadiness:
    def test_a_fresh_repo_is_not_ready(self, repo):
        state = readiness(repo)
        assert not state.ready
        assert any("intent" in b for b in state.blockers())

    def test_intent_alone_is_enough_when_nothing_was_inferred(self, repo):
        confirm_intent(repo)
        assert readiness(repo).ready

    def test_pending_invariants_block(self, repo):
        confirm_intent(repo)
        write_inferred(repo, [inferred("a")])
        state = readiness(repo)
        assert not state.ready
        assert any("1 awaiting" in b for b in state.blockers())

    def test_deciding_everything_clears_the_gate(self, repo):
        confirm_intent(repo)
        write_inferred(repo, [inferred("a"), inferred("b", "lib", "INF-2")])
        record_verdict(repo, "a", "src", APPROVED, record="I-1")
        record_verdict(repo, "b", "lib", DENIED)
        state = readiness(repo)
        assert state.ready
        assert state.blockers() == []

    def test_an_edit_counts_as_decided(self, repo):
        confirm_intent(repo)
        write_inferred(repo, [inferred("a")])
        record_verdict(repo, "a", "src", EDITED, record="I-2")
        assert readiness(repo).ready

    def test_the_payload_is_serialisable_for_the_api(self, repo):
        write_inferred(repo, [inferred("a")])
        payload = readiness(repo).to_dict()
        assert payload["ready"] is False
        assert payload["pending_invariants"][0]["statement"] == "a"
        assert payload["blockers"]


def test_module_constants_are_where_the_go_side_expects(repo):
    # The web server reads the same paths; a rename here is a break there.
    assert decisions.LEDGER_PATH == ".hobbes/decisions.yaml"


class TestCrossLanguageContract:
    """The Go web server writes this ledger; `hobbes up` reads it.

    A disagreement about the content key would silently lose every
    decision rather than fail, so both sides assert the same vectors.
    """

    def _vectors(self):
        import json

        path = Path(__file__).parent / "fixtures" / "decision-keys.json"
        return json.loads(path.read_text())["vectors"]

    def test_every_vector_matches_this_implementation(self):
        for vector in self._vectors():
            assert content_key(vector["statement"], vector["scope"]) == vector["key"], (
                f"vector drifted: {vector['why']}"
            )

    def test_the_vectors_cover_the_cases_that_matter(self):
        whys = " ".join(v["why"] for v in self._vectors())
        for case in ("whitespace", "scope", "unicode"):
            assert case in whys, f"no vector covers {case}"

    def test_the_ledger_the_go_side_writes_is_readable_here(self, repo):
        # The exact shape internal/web/decisions.go marshals.
        (repo / ".hobbes").mkdir(parents=True)
        (repo / ".hobbes" / "decisions.yaml").write_text(
            "# header\n"
            "schema_version: 1\n"
            "intent:\n"
            "  confirmed_at: '2026-08-11T18:00:00Z'\n"
            "  policy_blob: deadbeef\n"
            "invariants:\n"
            "  - key: sha256:abc\n"
            "    verdict: approved\n"
            "    decided_at: '2026-08-11T18:00:00Z'\n"
            "    record: I-1\n"
            "    source_statement: only core mints tokens\n"
            "    source_scope: src\n"
        )
        ledger = load(repo)
        assert ledger.intent_confirmed
        assert ledger.intent_policy_blob == "deadbeef"
        assert ledger.verdict_for("sha256:abc").record == "I-1"
