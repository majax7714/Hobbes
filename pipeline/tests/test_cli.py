"""Tests for the hobbes CLI: init/ingest/render/diff behavior, passthrough."""

import io
import json
import pathlib
import shutil
import subprocess
from pathlib import Path

import pytest

from hobbes import cli
from hobbes.extract import SCHEMA_VERSION
from tests.conftest import FAKE_RESOLUTION

FIXTURE = Path(__file__).parent / "fixtures" / "miniapp"


class TestInit:
    def test_scaffolds_layout(self, tmp_path, capsys):
        assert cli.main(["init", "--repo", str(tmp_path)]) == 0
        assert (tmp_path / ".hobbes" / "policies" / "repo.policy").is_file()
        assert (tmp_path / ".hobbes" / "invariants").is_dir()
        gitignore = (tmp_path / ".gitignore").read_text()
        assert ".hobbes/" in gitignore.splitlines()  # ADR-012: the whole dir
        assert "*.tfstate" in gitignore

    def test_idempotent_and_preserves_existing(self, tmp_path, capsys):
        (tmp_path / ".gitignore").write_text("node_modules/\n")
        assert cli.main(["init", "--repo", str(tmp_path)]) == 0
        marker = "# custom policy"
        policy_path = tmp_path / ".hobbes" / "policies" / "repo.policy"
        policy_path.write_text(marker)
        capsys.readouterr()

        assert cli.main(["init", "--repo", str(tmp_path)]) == 0
        assert "nothing to do" in capsys.readouterr().out
        assert policy_path.read_text() == marker
        gitignore = (tmp_path / ".gitignore").read_text()
        assert gitignore.startswith("node_modules/\n")
        assert gitignore.count(".hobbes/") == 1


@pytest.fixture
def git_fixture(tmp_path):
    """The miniapp fixture as a real git repo with one commit."""
    repo = tmp_path / "miniapp"
    shutil.copytree(FIXTURE, repo)
    (repo / ".gitignore").write_text(".hobbes/\n")
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git[:3], "init", "-q"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "fixture"], check=True)
    return repo


class TestIngest:
    def test_ingests_and_summarizes(self, git_fixture, capsys):
        assert cli.main(["ingest", "--repo", str(git_fixture)]) == 0
        out = capsys.readouterr().out
        assert "graph.json" in out and "module edges" in out
        assert (git_fixture / ".hobbes" / "derived" / "graph.json").is_file()

    def test_uncontained_is_disclosed_and_stamped(self, git_fixture, capsys, monkeypatch):
        # ADR-092 phase 3: the escape hatch is said before it happens and
        # recorded in the artifact after; a default ingest stamps that
        # every step was contained and prints nothing about it.
        monkeypatch.delenv("HOBBES_UNCONTAINED", raising=False)
        assert cli.main(["ingest", "--repo", str(git_fixture)]) == 0
        assert "containment" not in capsys.readouterr().err
        graph = json.loads((git_fixture / ".hobbes" / "derived" / "graph.json").read_text())
        assert graph["containment"] == {"steps": [], "all_contained": True, "escape_hatch": False}
        assert cli.main(["ingest", "--repo", str(git_fixture), "--uncontained"]) == 0
        err = capsys.readouterr().err
        assert "UNCONTAINED: lane B runs on this host" in err and "C-64" in err
        graph = json.loads((git_fixture / ".hobbes" / "derived" / "graph.json").read_text())
        assert graph["containment"]["escape_hatch"] is True

    def test_the_artifact_says_which_hobbes_built_it(self, git_fixture, capsys):
        # ADR-094: a stale install on PATH once ingested with
        # pre-containment code and nothing said so. The stamp names the
        # checkout and commit the pipeline code came from.
        from hobbes.extract import built_by
        assert cli.main(["ingest", "--repo", str(git_fixture)]) == 0
        out = capsys.readouterr().out
        graph = json.loads((git_fixture / ".hobbes" / "derived" / "graph.json").read_text())
        stamp = graph["built_by"]
        assert stamp == built_by()
        assert pathlib.Path(stamp["checkout"], "pipeline", "src", "hobbes").is_dir()
        assert len(stamp["sha"]) == 40
        assert f"built by hobbes @ {stamp['sha'][:12]}" in out and stamp["checkout"] in out

    def test_non_git_repo_is_a_clear_error(self, tmp_path, capsys):
        assert cli.main(["ingest", "--repo", str(tmp_path)]) == 1
        assert "git repo" in capsys.readouterr().err

    def test_summary_breaks_capture_down_by_directory(self, git_fixture, capsys):
        # Lane B is off in the suite, so sites go unresolved and the
        # per-directory view must give those misses an address.
        assert cli.main(["ingest", "--repo", str(git_fixture)]) == 0
        out = capsys.readouterr().out
        assert "by directory" in out

    def test_tf_plan_enriches_graph(self, git_fixture, capsys):
        plan = Path(__file__).parent / "fixtures" / "plans" / "miniapp-plan.json"
        code = cli.main(
            ["ingest", "--repo", str(git_fixture), "--tf-plan", str(plan)]
        )
        assert code == 0
        doc = json.loads(
            (git_fixture / ".hobbes" / "derived" / "graph.json").read_text()
        )
        assert any(
            n["id"] == "tf:aws_cloudwatch_log_group.worker" for n in doc["nodes"]
        )

    def test_tfstate_plan_refused(self, git_fixture, tmp_path, capsys):
        lookalike = tmp_path / "prod.tfstate"
        lookalike.write_text("{}")
        code = cli.main(
            ["ingest", "--repo", str(git_fixture), "--tf-plan", str(lookalike)]
        )
        assert code == 1
        assert "state" in capsys.readouterr().err


class TestDirectoryView:
    @staticmethod
    def row(file, sites, unresolved, tail=None):
        return {
            "file": file, "sites": sites, "unresolved": unresolved,
            **({"tail": tail} if tail else {}),
        }

    def test_worst_directory_prints_first_with_its_classes(self, capsys):
        cli._print_directory_view([
            self.row("a/b/x.py", 10, 1, {"attr-call": 1}),
            self.row("c/d/y.py", 10, 7, {"attr-call": 5, "unclassified": 2}),
        ])
        out = capsys.readouterr().out.splitlines()
        assert "c/d [python]" in out[1] and "a/b [python]" in out[2]
        assert "attr-call 5" in out[1] and "unclassified 2" in out[1]

    def test_directories_without_unresolvable_sites_are_counted_not_listed(
        self, capsys
    ):
        # Both the fully-resolved directory and the all-by-design one land
        # in the "without" count: neither holds a site the view should
        # point at.
        cli._print_directory_view([
            self.row("a/b/x.py", 10, 0),
            self.row("e/f/z.py", 10, 3, {"builtin-name": 3}),
            self.row("c/d/y.py", 10, 2, {"attr-call": 2}),
        ])
        out = capsys.readouterr().out
        assert "2 without" in out
        assert "a/b" not in out and "e/f" not in out

    def test_ranked_by_cannot_resolve_not_total_unresolved(self, capsys):
        # a/b has more unresolved sites, but they are by-design builtins;
        # c/d's real misses must outrank them.
        cli._print_directory_view([
            self.row("a/b/x.py", 20, 9, {"builtin-name": 8, "attr-call": 1}),
            self.row("c/d/y.py", 10, 5, {"unclassified": 5}),
        ])
        out = capsys.readouterr().out.splitlines()
        assert "c/d [python]" in out[1] and "a/b [python]" in out[2]
        assert "8 by design" in out[2]

    def test_the_cut_is_stated_never_silent(self, capsys):
        rows = [
            self.row(f"d{i}/s/x.py", 10, i + 1, {"attr-call": i + 1})
            for i in range(cli._DIR_ROWS_SHOWN + 3)
        ]
        cli._print_directory_view(rows)
        out = capsys.readouterr().out
        held = 1 + 2 + 3  # the three smallest tails are the ones held back
        assert f"… and 3 more directories ({held} unresolvable)" in out

    def test_silent_when_every_site_resolved(self, capsys):
        cli._print_directory_view([self.row("a/b/x.py", 10, 0)])
        assert capsys.readouterr().out == ""


class TestRender:
    def test_renders_after_ingest(self, git_fixture, capsys):
        assert cli.main(["ingest", "--repo", str(git_fixture)]) == 0
        capsys.readouterr()
        assert cli.main(["render", "--repo", str(git_fixture)]) == 0
        out = capsys.readouterr().out
        assert out.startswith("flowchart LR")
        assert '"miniapp.core"' in out

    def test_missing_artifact_says_run_ingest(self, git_fixture, capsys):
        assert cli.main(["render", "--repo", str(git_fixture)]) == 1
        assert "hobbes ingest" in capsys.readouterr().err


class TestIngestSummaryCounts:
    """The first numbers a user reads must not read larger than the truth."""

    def test_calls_and_uses_are_counted_apart(self, git_fixture, capsys):
        """C-76: the summary once printed every symbol edge as a call edge
        (serde: 4,361 for 1,557 calls)."""
        assert cli.main(["ingest", "--repo", str(git_fixture)]) == 0
        out = capsys.readouterr().out
        graph = json.loads(
            (git_fixture / ".hobbes" / "derived" / "graph.json").read_text()
        )
        calls = sum(1 for e in graph["symbol_edges"] if e["type"] == "calls")
        uses = sum(1 for e in graph["symbol_edges"] if e["type"] == "uses")
        assert calls + uses == len(graph["symbol_edges"])
        assert f"{calls} call edges, {uses} uses edges" in out
        assert f"{len(graph['symbol_edges'])} call edges" not in out or calls == len(
            graph["symbol_edges"]
        )


class TestLanes:
    """`hobbes lanes` — §3.4's self-test as a command, not only a CI file."""

    def test_clean_report_exits_zero(self, git_fixture, capsys):
        assert cli.main(["ingest", "--repo", str(git_fixture)]) == 0
        capsys.readouterr()
        assert cli.main(["lanes", "--repo", str(git_fixture)]) == 0
        out = capsys.readouterr().out
        assert "lane agreement @" in out
        assert "the lanes agree wherever both can answer" in out

    def test_a_site_disagreement_exits_one(self, git_fixture, capsys):
        assert cli.main(["ingest", "--repo", str(git_fixture)]) == 0
        graph_path = git_fixture / ".hobbes" / "derived" / "graph.json"
        graph = json.loads(graph_path.read_text())
        graph["lane_agreement"]["site_disagreements"].append(
            {
                "file": "src/miniapp/core.py",
                "line": 16,
                "name": "normalize",
                "syntactic": "src/miniapp/util.py:6",
                "semantic": "src/miniapp/other.py:2",
            }
        )
        graph_path.write_text(json.dumps(graph))
        capsys.readouterr()

        assert cli.main(["lanes", "--repo", str(git_fixture)]) == 1
        out = capsys.readouterr().out
        assert "1 disagree" in out
        assert "src/miniapp/core.py:16 normalize()" in out
        assert "syntactic -> src/miniapp/util.py:6" in out
        assert "semantic  -> src/miniapp/other.py:2" in out

    def test_module_edge_differences_alone_do_not_fail(self, git_fixture, capsys):
        """Lane B following a re-export past the package is not a bug.

        ADR-027 measured exactly this and it favours lane B, so it is
        reported and does not fail the check.
        """
        assert cli.main(["ingest", "--repo", str(git_fixture)]) == 0
        graph_path = git_fixture / ".hobbes" / "derived" / "graph.json"
        graph = json.loads(graph_path.read_text())
        graph["lane_agreement"]["module_edges_lane_b_only"].append(
            {"from": "miniapp.cli", "to": "miniapp.core"}
        )
        graph_path.write_text(json.dumps(graph))
        capsys.readouterr()

        assert cli.main(["lanes", "--repo", str(git_fixture)]) == 0
        assert "lane B only: miniapp.cli -> miniapp.core" in capsys.readouterr().out

    def test_lane_b_share_is_printed_beside_the_comparison(self, git_fixture, capsys):
        """C-75: the compared count is a union of both lanes; with lane B
        off (the suite's default) the report must say lane B produced
        nothing rather than reading lane A's fallback as agreement."""
        assert cli.main(["ingest", "--repo", str(git_fixture)]) == 0
        graph = json.loads(
            (git_fixture / ".hobbes" / "derived" / "graph.json").read_text()
        )
        report = graph["lane_agreement"]
        assert report["module_edges_lane_b_produced"] == 0
        assert report["module_edges_compared"] == 0
        assert report["module_edges_lane_b_only"] == []
        capsys.readouterr()
        assert cli.main(["lanes", "--repo", str(git_fixture)]) == 0
        out = capsys.readouterr().out
        assert "module edges compared: 0 (lane B produced 0)" in out
        assert "lane B produced no module edges; the module comparison did not run" in out

    def test_a_graph_without_the_report_says_so(self, git_fixture, capsys):
        assert cli.main(["ingest", "--repo", str(git_fixture)]) == 0
        graph_path = git_fixture / ".hobbes" / "derived" / "graph.json"
        graph = json.loads(graph_path.read_text())
        del graph["lane_agreement"]
        graph_path.write_text(json.dumps(graph))
        capsys.readouterr()

        assert cli.main(["lanes", "--repo", str(git_fixture)]) == 2
        assert "re-run `hobbes ingest`" in capsys.readouterr().err


class TestDiff:
    @pytest.fixture
    def two_commit_fixture(self, git_fixture):
        git = ["git", "-C", str(git_fixture), "-c", "user.name=t", "-c", "user.email=t@t"]
        (git_fixture / "src" / "miniapp" / "extra.py").write_text(
            "from miniapp import util\n"
        )
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-qm", "add extra"], check=True)
        return git_fixture

    def test_delta_prints_and_exits_one(self, two_commit_fixture, capsys):
        code = cli.main(["diff", "HEAD~1..HEAD", "--repo", str(two_commit_fixture)])
        assert code == 1
        out = capsys.readouterr().out
        assert "+ module miniapp.extra" in out
        assert "+ imports miniapp.extra -> miniapp.util" in out

    def test_bare_base_means_head(self, two_commit_fixture, capsys):
        assert cli.main(["diff", "HEAD~1", "--repo", str(two_commit_fixture)]) == 1
        assert "miniapp.extra" in capsys.readouterr().out

    def test_no_delta_exits_zero(self, two_commit_fixture, capsys):
        code = cli.main(["diff", "HEAD..HEAD", "--repo", str(two_commit_fixture)])
        assert code == 0
        assert "no architectural changes" in capsys.readouterr().out

    def test_json_output(self, two_commit_fixture, capsys):
        code = cli.main(
            ["diff", "HEAD~1..HEAD", "--json", "--repo", str(two_commit_fixture)]
        )
        assert code == 1
        delta = json.loads(capsys.readouterr().out)
        assert [n["id"] for n in delta["nodes_added"]] == ["miniapp.extra"]

    def test_bad_ref_exits_two(self, git_fixture, capsys):
        assert cli.main(["diff", "nope..HEAD", "--repo", str(git_fixture)]) == 2
        assert "nope" in capsys.readouterr().err

    def test_three_dot_range_rejected(self, git_fixture):
        with pytest.raises(SystemExit, match="three-dot"):
            cli.main(["diff", "a...b", "--repo", str(git_fixture)])


class TestPolicyResolve:
    def test_propagates_decision_exit_and_prints_json(
        self, fake_policy_bin, monkeypatch, capsys
    ):
        payload = dict(FAKE_RESOLUTION, decision="deny")
        monkeypatch.setenv("HOBBES_POLICY_BIN", fake_policy_bin(10, payload))
        code = cli.main(["policy", "resolve", "git push --force origin main"])
        assert code == 10
        printed = json.loads(capsys.readouterr().out)
        assert printed["decision"] == "deny"
        assert printed["rule"]["pattern"] == "git push --force*"

    def test_allow_exits_zero(self, fake_policy_bin, monkeypatch):
        payload = dict(FAKE_RESOLUTION, decision="allow")
        monkeypatch.setenv("HOBBES_POLICY_BIN", fake_policy_bin(0, payload))
        assert cli.main(["policy", "resolve", "git status"]) == 0

    def test_missing_binary_is_a_clear_error(self, no_real_binary, capsys):
        assert cli.main(["policy", "resolve", "git status"]) == 1
        assert "go build" in capsys.readouterr().err

    def test_binary_runtime_error_reported(
        self, fake_policy_bin, monkeypatch, capsys
    ):
        monkeypatch.setenv("HOBBES_POLICY_BIN", fake_policy_bin(1))
        assert cli.main(["policy", "resolve", "git status"]) == 1
        assert "exited 1" in capsys.readouterr().err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0


class TestInvariantsCommand:
    """`hobbes invariants list | check | compile` (ADR-024)."""

    def _repo(self, tmp_path, record):
        import yaml

        directory = tmp_path / ".hobbes" / "invariants"
        directory.mkdir(parents=True)
        (directory / "I-1-x.yaml").write_text(yaml.safe_dump(record, sort_keys=False))
        return tmp_path

    def _record(self, **overrides):
        record = {
            "id": "I-1",
            "statement": "Only the parser parses.",
            "scope": "src",
            "status": "confirmed",
            "check": "emit",
            "rule": {
                "kind": "forbidden-import",
                "importers": ["*"],
                "imported": ["ext:tree_sitter"],
            },
            "compile": {"target": "import-linter"},
            "guarded_by": [],
        }
        record.update(overrides)
        return record

    def test_check_passes_on_valid_records(self, tmp_path, capsys):
        repo = self._repo(tmp_path, self._record())
        assert cli.main(["invariants", "check", "--repo", str(repo)]) == 0
        assert "1 record(s) valid" in capsys.readouterr().out

    def test_check_exits_one_and_names_every_problem(self, tmp_path, capsys):
        repo = self._repo(
            tmp_path,
            {"id": "I-1", "check": "emit", "compile": {"target": "nope"}},
        )
        assert cli.main(["invariants", "check", "--repo", str(repo)]) == 1
        err = capsys.readouterr().err
        assert "problem(s)" in err
        assert "rule block is required" in err

    def test_list_hides_unconfirmed_unless_asked(self, tmp_path, capsys):
        repo = self._repo(tmp_path, self._record(status="retired"))
        cli.main(["invariants", "list", "--repo", str(repo)])
        assert "no confirmed invariants" in capsys.readouterr().out
        cli.main(["invariants", "list", "--repo", str(repo), "--all"])
        assert "I-1" in capsys.readouterr().out

    def test_compile_without_ingest_says_so(self, tmp_path, capsys):
        repo = self._repo(tmp_path, self._record())
        assert cli.main(["invariants", "compile", "--repo", str(repo)]) == 1
        assert "hobbes ingest" in capsys.readouterr().err

    def test_compile_writes_configs_and_a_manifest(self, tmp_path, capsys):
        repo = self._repo(tmp_path, self._record())
        derived = repo / ".hobbes" / "derived"
        derived.mkdir(parents=True, exist_ok=True)
        (derived / "graph.json").write_text(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "sha": "abc",
                    "dirty": False,
                    "nodes": [{"id": "app.core", "kind": "module", "path": "src/core.py"}],
                    "module_edges": [],
                }
            )
        )
        assert cli.main(["invariants", "compile", "--repo", str(repo)]) == 0
        assert "importlinter.ini" in capsys.readouterr().out
        manifest = json.loads((derived / "compiled" / "manifest.json").read_text())
        assert manifest["outputs"][0]["invariants"] == ["I-1"]


class TestProgressIsNotBuffered:
    """`up` and `narrate` print while they work, so a redirected run has to
    show those lines as they happen rather than at exit."""

    def test_main_line_buffers_a_redirected_stdout(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        repo.mkdir()
        log = tmp_path / "out.log"
        with open(log, "w") as handle:
            # A real file object, as a redirect gives — block-buffered by
            # default, which is the papercut.
            assert handle.line_buffering is False
            monkeypatch.setattr("sys.stdout", handle)
            assert cli.main(["init", "--repo", str(repo)]) == 0
            assert handle.line_buffering is True
            # Already on disk, with the command still running.
            assert log.read_text() != ""

    def test_a_captured_stdout_without_reconfigure_still_works(
        self, tmp_path, monkeypatch
    ):
        # pytest's capsys and a plain StringIO have no reconfigure; buffering
        # is not their problem, and main must not assume the attribute.
        buffer = io.StringIO()
        assert not hasattr(buffer, "reconfigure")
        repo = tmp_path / "repo"
        repo.mkdir()
        monkeypatch.setattr("sys.stdout", buffer)
        assert cli.main(["init", "--repo", str(repo)]) == 0
        assert buffer.getvalue() != ""
