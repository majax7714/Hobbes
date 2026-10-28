"""Tests for the ``watterson`` CLI's ingest path (ADR-181).

Moved from watterson-environment@a65b6b1 ``pipeline/tests/test_cli.py``: the
classes that run ``ingest`` through ``watterson``'s own ``main`` (its parser
and its cache default), plus ``--version`` and the cache default itself. The
summary-printer classes it carried were copies of ``test_cli.py``'s; they
test ``hobbes.watterson.cli``'s printers, which ``watterson`` imports, and run there.
"""

import io
import json
import os
import pathlib
import shutil
import subprocess
from pathlib import Path

import pytest

from hobbes.watterson import cli

FIXTURE = Path(__file__).parent / "fixtures" / "miniapp"


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
        # Registered, not deleted: `--uncontained` sets the variable in this
        # process, and a `delenv` of an unset variable records nothing to
        # undo. The escape hatch then leaked into every later test; the C
        # lane-B test ran `index-c` on the host in a full run. "0" is off.
        monkeypatch.setenv("HOBBES_UNCONTAINED", "0")
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
        # ADR-103: the stamp and the line carry the Hobbes version too.
        from hobbes import __version__
        assert stamp["version"] == __version__
        assert f"built by hobbes {__version__} @ {stamp['sha'][:12]}" in out and stamp["checkout"] in out

    def test_non_git_repo_is_a_clear_error(self, tmp_path, capsys):
        assert cli.main(["ingest", "--repo", str(tmp_path)]) == 1
        assert "git repo" in capsys.readouterr().err

    def test_a_second_ingest_of_one_repo_is_refused(self, git_fixture, capsys):
        # ADR-127: refused, not queued — and before anything is staged or
        # written, so the running ingest's artifacts are its own.
        from tests.test_ingestlock import held_by_subprocess

        with held_by_subprocess(git_fixture):
            assert cli.main(["ingest", "--repo", str(git_fixture)]) == 1
        err = capsys.readouterr().err
        assert "hobbes ingest: another hobbes ingest of" in err
        assert not (git_fixture / ".hobbes" / "derived" / "graph.json").exists()

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
            n["id"] == "tf:infra:aws_cloudwatch_log_group.worker" for n in doc["nodes"]
        )

    def test_tfstate_plan_refused(self, git_fixture, tmp_path, capsys):
        lookalike = tmp_path / "prod.tfstate"
        lookalike.write_text("{}")
        code = cli.main(
            ["ingest", "--repo", str(git_fixture), "--tf-plan", str(lookalike)]
        )
        assert code == 1
        assert "state" in capsys.readouterr().err


class TestLaneACppCache:
    """ADR-128 §4: the ingest says what lane A's C++ walk was — a read of
    a stored parse, or a walk — and the line is where C-160 is met."""

    @pytest.fixture
    def cpp_fixture(self, tmp_path, monkeypatch):
        """The minicpp fixture as a git repo, with the store under
        tmp_path: a test never writes the developer's own cache."""
        monkeypatch.setenv("HOBBES_CACHE_DIR", str(tmp_path / "cache"))
        repo = tmp_path / "minicpp"
        shutil.copytree(Path(__file__).parent / "fixtures" / "minicpp", repo)
        (repo / ".gitignore").write_text(".hobbes/\n")
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git[:3], "init", "-q"], check=True)
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-qm", "fixture"], check=True)
        return repo

    @pytest.mark.lanea_cache
    def test_a_cpp_ingest_prints_the_line_and_the_second_one_is_all_hits(
        self, cpp_fixture, capsys
    ):
        assert cli.main(["ingest", "--repo", str(cpp_fixture)]) == 0
        out = capsys.readouterr().out
        assert "lane A C++ file cache: 0 hit," in out
        assert "C-160" in out and "HOBBES_LANEA_CACHE=0 to parse afresh" in out

        assert cli.main(["ingest", "--repo", str(cpp_fixture)]) == 0
        warm = capsys.readouterr().out
        assert "lane A C++ file cache: " in warm and " hit, 0 miss (" in warm

    def test_a_python_only_ingest_prints_nothing(self, git_fixture, capsys):
        # No C++ in the repo is no lookup, and no lookup is no line.
        assert cli.main(["ingest", "--repo", str(git_fixture)]) == 0
        assert "lane A C++ file cache" not in capsys.readouterr().out


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
        impls = sum(1 for e in graph["symbol_edges"] if e["type"] == "implements")
        assert calls + uses + impls == len(graph["symbol_edges"])
        assert f"{calls} call edges, {uses} uses edges, {impls} implements edges" in out
        assert f"{len(graph['symbol_edges'])} call edges" not in out or calls == len(
            graph["symbol_edges"]
        )


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0


class TestProgressIsNotBuffered:
    """`ingest` prints while it works, so a redirected run has to show
    those lines as they happen rather than at exit.

    Moved from hobbes-public, where these ran `init`; that command did not
    move, so they run `ingest` on the miniapp fixture instead (same check
    on `main`'s stdout handling)."""

    def test_main_line_buffers_a_redirected_stdout(self, git_fixture, tmp_path, monkeypatch):
        log = tmp_path / "out.log"
        with open(log, "w") as handle:
            # A real file object, as a redirect gives — block-buffered by
            # default, which is the papercut.
            assert handle.line_buffering is False
            monkeypatch.setattr("sys.stdout", handle)
            assert cli.main(["ingest", "--repo", str(git_fixture)]) == 0
            assert handle.line_buffering is True
            # Already on disk, with the command still running.
            assert log.read_text() != ""

    def test_a_captured_stdout_without_reconfigure_still_works(
        self, git_fixture, monkeypatch
    ):
        # pytest's capsys and a plain StringIO have no reconfigure; buffering
        # is not their problem, and main must not assume the attribute.
        buffer = io.StringIO()
        assert not hasattr(buffer, "reconfigure")
        monkeypatch.setattr("sys.stdout", buffer)
        assert cli.main(["ingest", "--repo", str(git_fixture)]) == 0
        assert buffer.getvalue() != ""


class TestDefaultCacheDir:
    def test_sets_repo_cache_when_unset(self, monkeypatch):
        monkeypatch.delenv("HOBBES_CACHE_DIR", raising=False)
        cli._default_cache_dir()
        assert os.environ["HOBBES_CACHE_DIR"] == cli.DEFAULT_CACHE_DIR

    def test_respects_explicit_override(self, monkeypatch):
        monkeypatch.setenv("HOBBES_CACHE_DIR", "/elsewhere")
        cli._default_cache_dir()
        assert os.environ["HOBBES_CACHE_DIR"] == "/elsewhere"
