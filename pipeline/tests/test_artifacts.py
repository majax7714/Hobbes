"""The version gate ADR-006 promised and ADR-028 finally built.

The point of these cases is not that the happy path works — it is that a
version this build does not know is *refused* rather than half-read. A
partially-decoded graph produces confident wrong answers (an invariant
verdict over edges whose tier it could not see), which is worse than an
error.
"""

import json

import pytest

from hobbes import artifacts
from hobbes.extract import SCHEMA_VERSION


def write(repo, name, document):
    derived = repo / ".hobbes" / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    (derived / name).write_text(json.dumps(document))
    return derived / name


class TestVersionGate:
    def test_accepts_the_version_the_pipeline_emits(self, tmp_path):
        write(tmp_path, "graph.json", {"schema_version": SCHEMA_VERSION, "nodes": []})
        assert artifacts.load_graph(tmp_path)["nodes"] == []

    def test_v3_reader_accepts_v3_and_v4(self, tmp_path):
        for version in artifacts.V3_COMPATIBLE:
            write(tmp_path, "graph.json", {"schema_version": version, "nodes": []})
            assert artifacts.load_graph(tmp_path)["schema_version"] == version

    def test_a_v4_only_reader_refuses_v3(self, tmp_path):
        write(tmp_path, "graph.json", {"schema_version": 3, "nodes": []})
        with pytest.raises(artifacts.ArtifactError) as exc:
            artifacts.load_graph(tmp_path, accepts=artifacts.V4_ONLY)
        assert "schema v3" in str(exc.value)
        assert "hobbes ingest" in str(exc.value)  # names its own fix

    def test_an_older_version_is_refused_not_half_read(self, tmp_path):
        write(tmp_path, "graph.json", {"schema_version": 2, "nodes": [{"id": "a"}]})
        with pytest.raises(artifacts.ArtifactError):
            artifacts.load_graph(tmp_path)

    def test_a_newer_version_says_to_upgrade_hobbes(self, tmp_path):
        write(tmp_path, "graph.json", {"schema_version": SCHEMA_VERSION + 1})
        with pytest.raises(artifacts.ArtifactError) as exc:
            artifacts.load_graph(tmp_path)
        assert "upgrade Hobbes" in str(exc.value)

    def test_a_missing_version_field_is_refused(self, tmp_path):
        write(tmp_path, "graph.json", {"nodes": []})
        with pytest.raises(artifacts.ArtifactError) as exc:
            artifacts.load_graph(tmp_path)
        assert "no schema_version" in str(exc.value)

    def test_a_missing_artifact_names_the_command(self, tmp_path):
        with pytest.raises(artifacts.ArtifactError) as exc:
            artifacts.load_graph(tmp_path)
        assert "hobbes ingest" in str(exc.value)

    def test_unreadable_json_is_an_error_not_a_crash(self, tmp_path):
        derived = tmp_path / ".hobbes" / "derived"
        derived.mkdir(parents=True)
        (derived / "graph.json").write_text("{not json")
        with pytest.raises(artifacts.ArtifactError):
            artifacts.load_graph(tmp_path)


class TestNotIngestedIsNotAVersionError:
    def test_absent_graph_reads_as_none(self, tmp_path):
        assert artifacts.graph_if_ingested(tmp_path) is None

    def test_but_a_wrong_version_still_raises(self, tmp_path):
        # The distinction matters: "never ingested" is a state the CLI
        # reports, "wrong version" is a mismatch it must not swallow.
        write(tmp_path, "graph.json", {"schema_version": 1})
        with pytest.raises(artifacts.ArtifactError):
            artifacts.graph_if_ingested(tmp_path)
