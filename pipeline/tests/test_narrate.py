"""Narrative artifact schema and filing (ADR-019): hobbes.narrate.schema."""

import json

import pytest
import yaml

from hobbes.narrate.schema import (
    ValidationError,
    invariants_path,
    load_artifacts,
    module_doc_path,
    behavior_index_path,
    validate_invariants_payload,
    validate_module_payload,
    validate_test_payload,
    write_inferred_invariants,
    write_module_doc,
    write_test_doc,
)

STAMP = {"sha": "a" * 40, "dirty": False}


def claim(text="greets by name", path="app.py", line=5):
    return {"text": text, "pins": [{"path": path, "line": line}]}


def module_payload(**overrides):
    payload = {
        "purpose": claim("a tiny app module", line=1),
        "responsibilities": [claim()],
        "gotchas": [],
    }
    payload.update(overrides)
    return payload


class TestValidateModulePayload:
    def test_happy_payload_is_clean(self, git_repo):
        assert validate_module_payload(git_repo, module_payload()) == []

    def test_non_dict_payload(self, git_repo):
        assert validate_module_payload(git_repo, ["nope"]) == [
            "payload must be an object, got list"
        ]

    def test_missing_purpose_and_empty_responsibilities(self, git_repo):
        problems = validate_module_payload(
            git_repo, {"purpose": None, "responsibilities": [], "gotchas": []}
        )
        assert any("purpose" in p for p in problems)
        assert any("responsibilities" in p for p in problems)

    def test_empty_gotchas_allowed(self, git_repo):
        assert validate_module_payload(git_repo, module_payload(gotchas=[])) == []

    @pytest.mark.parametrize(
        "pin, fragment",
        [
            ({"path": "../etc/passwd", "line": 1}, "repo-relative"),
            ({"path": "/etc/passwd", "line": 1}, "repo-relative"),
            ({"path": "gone.py", "line": 1}, "does not exist"),
            ({"path": "app.py", "line": 0}, "positive integer"),
            ({"path": "app.py", "line": True}, "positive integer"),
            ({"path": "app.py", "line": 999}, "past the end"),
            ({"path": "", "line": 1}, "string 'path'"),
            ("app.py:1", "must be an object"),
        ],
    )
    def test_bad_pins(self, git_repo, pin, fragment):
        payload = module_payload(
            responsibilities=[{"text": "x", "pins": [pin]}]
        )
        problems = validate_module_payload(git_repo, payload)
        assert any(fragment in p for p in problems), problems

    def test_claim_without_pins(self, git_repo):
        payload = module_payload(responsibilities=[{"text": "x", "pins": []}])
        assert any(
            "at least one pin" in p
            for p in validate_module_payload(git_repo, payload)
        )

    def test_empty_text(self, git_repo):
        payload = module_payload(responsibilities=[{"text": "  ", "pins": [{"path": "app.py", "line": 1}]}])
        assert any(
            "non-empty 'text'" in p
            for p in validate_module_payload(git_repo, payload)
        )


class TestWriteModuleDoc:
    def test_writes_stamped_doc(self, git_repo):
        path = write_module_doc(git_repo, "app", "app.py", module_payload(), STAMP)
        assert path == module_doc_path(git_repo, "app")
        doc = json.loads(path.read_text())
        assert doc["kind"] == "module-doc"
        assert doc["id"] == "app"
        assert doc["sha"] == STAMP["sha"]
        assert [s["path"] for s in doc["sources"]] == ["app.py"]
        assert doc["purpose"]["pins"] == [{"path": "app.py", "line": 1}]

    def test_sources_union_module_and_pins(self, git_repo):
        (git_repo / "other.py").write_text("x = 1\n")
        payload = module_payload(gotchas=[claim("see other", path="other.py", line=1)])
        doc = json.loads(
            write_module_doc(git_repo, "app", "app.py", payload, STAMP).read_text()
        )
        assert [s["path"] for s in doc["sources"]] == ["app.py", "other.py"]

    def test_invalid_payload_writes_nothing(self, git_repo):
        with pytest.raises(ValidationError) as err:
            write_module_doc(
                git_repo, "app", "app.py", module_payload(purpose=None), STAMP
            )
        assert err.value.problems
        assert not module_doc_path(git_repo, "app").exists()

    def test_unsafe_id_refused(self, git_repo):
        with pytest.raises(ValueError, match="unsafe artifact id"):
            write_module_doc(
                git_repo, "../evil", "app.py", module_payload(), STAMP
            )


def behavior(test_id, text="pins greeting format", line=6):
    return {"test": test_id, "text": text, "pins": [{"path": "app.py", "line": line}]}


class TestValidateTestPayload:
    EXPECTED = ["t.py::test_a", "t.py::test_b"]

    def test_happy_payload_is_clean(self, git_repo):
        payload = {"behaviors": [behavior("t.py::test_a"), behavior("t.py::test_b")]}
        assert validate_test_payload(git_repo, payload, self.EXPECTED) == []

    def test_missing_and_unknown_tests(self, git_repo):
        payload = {"behaviors": [behavior("t.py::test_a"), behavior("t.py::test_x")]}
        problems = validate_test_payload(git_repo, payload, self.EXPECTED)
        assert any("missing test t.py::test_b" in p for p in problems)
        assert any("unknown test t.py::test_x" in p for p in problems)

    def test_duplicate_test(self, git_repo):
        payload = {"behaviors": [behavior("t.py::test_a")] * 2 + [behavior("t.py::test_b")]}
        assert any(
            "exactly once" in p
            for p in validate_test_payload(git_repo, payload, self.EXPECTED)
        )

    def test_multiline_text_refused(self, git_repo):
        payload = {
            "behaviors": [
                behavior("t.py::test_a", text="two\nlines"),
                behavior("t.py::test_b"),
            ]
        }
        assert any(
            "single line" in p
            for p in validate_test_payload(git_repo, payload, self.EXPECTED)
        )


class TestWriteTestDoc:
    def test_behaviors_sorted_by_test_id(self, git_repo):
        payload = {"behaviors": [behavior("t.py::b"), behavior("t.py::a")]}
        path = write_test_doc(
            git_repo, "tests.t", "app.py", payload, ["t.py::a", "t.py::b"], STAMP
        )
        assert path == behavior_index_path(git_repo, "tests.t")
        doc = json.loads(path.read_text())
        assert [b["test"] for b in doc["behaviors"]] == ["t.py::a", "t.py::b"]
        assert doc["kind"] == "test-doc"


def invariant(statement="only app greets", scope="app.py", line=5):
    return {
        "statement": statement,
        "scope": scope,
        "evidence": [{"path": "app.py", "line": line}],
    }


class TestInvariants:
    def test_happy_payload_is_clean(self, git_repo):
        assert (
            validate_invariants_payload(git_repo, {"invariants": [invariant()]}) == []
        )

    def test_empty_list_refused(self, git_repo):
        assert validate_invariants_payload(git_repo, {"invariants": []}) == [
            "invariants: must be a non-empty list"
        ]

    def test_missing_fields_and_evidence(self, git_repo):
        problems = validate_invariants_payload(
            git_repo,
            {"invariants": [{"statement": "", "scope": None, "evidence": []}]},
        )
        assert any("'statement'" in p for p in problems)
        assert any("'scope'" in p for p in problems)
        assert any("evidence pin" in p for p in problems)

    def test_guarded_by_must_be_string_list(self, git_repo):
        record = invariant() | {"guarded_by": "test_x"}
        assert any(
            "guarded_by" in p
            for p in validate_invariants_payload(git_repo, {"invariants": [record]})
        )

    def test_write_assigns_ids_and_status(self, git_repo):
        path = write_inferred_invariants(
            git_repo,
            {"invariants": [invariant("first"), invariant("second")]},
            STAMP,
        )
        assert path == invariants_path(git_repo)
        doc = yaml.safe_load(path.read_text())
        assert [(r["id"], r["status"]) for r in doc["invariants"]] == [
            ("INF-1", "inferred"),
            ("INF-2", "inferred"),
        ]
        assert doc["kind"] == "inferred-invariants"
        assert [s["path"] for s in doc["sources"]] == ["app.py"]

    def test_model_supplied_status_is_overridden(self, git_repo):
        record = invariant() | {"status": "confirmed", "id": "I-99"}
        doc = yaml.safe_load(
            write_inferred_invariants(
                git_repo, {"invariants": [record]}, STAMP
            ).read_text()
        )
        assert doc["invariants"][0]["id"] == "INF-1"
        assert doc["invariants"][0]["status"] == "inferred"


class TestLoadArtifacts:
    def test_lists_all_kinds_sorted(self, git_repo):
        write_module_doc(git_repo, "app", "app.py", module_payload(), STAMP)
        write_test_doc(
            git_repo, "tests.t", "app.py",
            {"behaviors": [behavior("t.py::a")]}, ["t.py::a"], STAMP,
        )
        write_inferred_invariants(git_repo, {"invariants": [invariant()]}, STAMP)
        kinds = [a["kind"] for a in load_artifacts(git_repo)]
        assert kinds == ["inferred-invariants", "module-doc", "test-doc"]

    def test_no_docs_dir_is_empty(self, git_repo):
        assert load_artifacts(git_repo) == []

    def test_unreadable_artifact_is_listed_not_fatal(self, git_repo):
        write_module_doc(git_repo, "app", "app.py", module_payload(), STAMP)
        broken = module_doc_path(git_repo, "broken")
        broken.write_text("{not json")
        entries = load_artifacts(git_repo)
        assert {a["kind"] for a in entries} == {"module-doc", "unreadable"}


class TestSlashIds:
    """TS/JS module ids are paths (ADR-021): artifacts nest under docs/."""

    def test_nested_id_writes_nested_file(self, git_repo):
        path = write_module_doc(git_repo, "src/app", "app.py", module_payload(), STAMP)
        assert path == module_doc_path(git_repo, "src/app")
        assert path.parent.name == "src"
        assert json.loads(path.read_text())["id"] == "src/app"

    def test_nested_artifacts_are_loaded(self, git_repo):
        write_module_doc(git_repo, "src/app", "app.py", module_payload(), STAMP)
        (entry,) = load_artifacts(git_repo)
        assert entry["id"] == "src/app"

    @pytest.mark.parametrize("bad", ["../evil", "a/../b", "a//b", "a/./b", "/abs"])
    def test_traversal_ids_still_refused(self, git_repo, bad):
        with pytest.raises(ValueError, match="unsafe artifact id"):
            write_module_doc(git_repo, bad, "app.py", module_payload(), STAMP)
