"""Every wall-clock cap is in one table and says where it bites (ADR-183, C-196)."""

from __future__ import annotations

import stat
import subprocess

import pytest

from hobbes.extract import caps, containment, scipsource, tssource


class TestTable:
    def test_scale_one_is_the_table(self, monkeypatch):
        monkeypatch.delenv(caps.SCALE_ENV, raising=False)
        assert caps.seconds("tsextract") == 300
        assert caps.seconds("lane-b-unit") == 900
        assert caps.seconds("lane-b-java") == 1800
        assert caps.seconds("clang-unit") == 300, "scip-clang's own default, so scale 1 moves nothing"

    def test_the_scale_multiplies_every_cap(self, monkeypatch):
        monkeypatch.setenv(caps.SCALE_ENV, "2.5")
        assert {name: caps.seconds(name) for name in caps.CAPS} == {
            name: round(base * 2.5) for name, base in caps.CAPS.items()
        }

    @pytest.mark.parametrize("raw", ["0", "-1", "fast", "nan", "inf"])
    def test_a_scale_that_is_not_a_positive_number_is_refused(self, monkeypatch, raw):
        # A cap the user thinks they raised and did not would fire unexplained.
        monkeypatch.setenv(caps.SCALE_ENV, raw)
        with pytest.raises(ValueError, match="not a positive number"):
            caps.seconds("tsextract")

    def test_the_step_cap_sits_under_its_unit(self):
        assert caps.step_seconds(900) == 870
        assert caps.step_seconds(10) == 1

    def test_every_timeout_says_the_cap_the_entry_and_the_knob(self):
        assert caps.timed_out("scip-go", 870) == (
            "scip-go did not finish within its 870 s cap (C-196; HOBBES_TIMEOUT_SCALE raises every cap)"
        )


class TestWhereTheyBite:
    def test_the_ts_helper_names_its_cap_and_stops_the_ingest(self, tmp_path, monkeypatch):
        script = tmp_path / "helper.sh"
        script.write_text("#!/bin/sh\nsleep 5\n")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        monkeypatch.setenv("HOBBES_TSEXTRACT_CMD", str(script))
        monkeypatch.setitem(caps.CAPS, "tsextract", 1)
        with pytest.raises(tssource.TsExtractError) as info:
            tssource.run_helper(tmp_path)
        said = str(info.value)
        assert "did not finish within its 1 s cap (C-196; HOBBES_TIMEOUT_SCALE" in said
        assert "the ingest stops rather than drawing the repo without its TS/JS" in said

    def test_a_contained_step_names_its_cap(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOBBES_CACHE_DIR", str(tmp_path / "cache"))
        monkeypatch.setattr(containment, "unavailable_reason", lambda: None)

        def slow(argv, **kw):
            raise subprocess.TimeoutExpired(argv, kw["timeout"])

        monkeypatch.setattr(containment.subprocess, "run", slow)
        plan = containment.plan("index-go", ["node", "helper"], cwd=tmp_path)
        with pytest.raises(containment.ContainmentError) as info:
            containment.run(plan, timeout=900)
        assert str(info.value) == (
            "index-go, in its container, did not finish within its 900 s cap "
            "(C-196; HOBBES_TIMEOUT_SCALE raises every cap)"
        )

    def test_the_zone_map_names_its_cap(self, tmp_path, monkeypatch):
        script = tmp_path / "helper.sh"
        script.write_text("#!/bin/sh\nsleep 5\n")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        monkeypatch.setenv("HOBBES_TSEXTRACT_CMD", str(script))
        monkeypatch.setitem(caps.CAPS, "tsextract-zones", 1)
        with pytest.raises(scipsource.ScipError, match=r"zone map did not finish within its 1 s cap \(C-196"):
            scipsource.ts_zone_map(tmp_path)


class TestTheUnitConfigCarriesTheCaps:
    """The helper reads its step cap and scip-clang's wait from the unit's
    config, so the one table governs inside the container too."""

    def _capture(self, tmp_path, monkeypatch):
        seen: dict = {}

        def fake(config, config_path, facts_path, timeout, ro, env, root, key=None):
            seen["config"] = dict(config)
            seen["timeout"] = timeout
            return {}

        monkeypatch.setattr(scipsource, "_run_helper", fake)
        monkeypatch.setattr(scipsource, "_cache_key", lambda *a: None)
        return seen

    def test_a_unit_at_the_default_cap(self, tmp_path, monkeypatch):
        monkeypatch.delenv(caps.SCALE_ENV, raising=False)
        seen = self._capture(tmp_path, monkeypatch)
        scipsource.run_helper({"stage": str(tmp_path / "s"), "language": "go"})
        assert seen["timeout"] == 900
        assert seen["config"]["stepTimeoutSeconds"] == 870
        assert "clangUnitTimeoutSeconds" not in seen["config"]

    def test_a_c_unit_carries_scip_clangs_wait(self, tmp_path, monkeypatch):
        monkeypatch.setenv(caps.SCALE_ENV, "2")
        seen = self._capture(tmp_path, monkeypatch)
        scipsource.run_helper({"stage": str(tmp_path / "s"), "language": "cpp"})
        assert seen["timeout"] == 1800
        assert seen["config"]["stepTimeoutSeconds"] == 1770
        assert seen["config"]["clangUnitTimeoutSeconds"] == 600

    def test_a_named_timeout_sets_the_step_under_it(self, tmp_path, monkeypatch):
        monkeypatch.delenv(caps.SCALE_ENV, raising=False)
        seen = self._capture(tmp_path, monkeypatch)
        scipsource.run_helper({"stage": str(tmp_path / "s"), "language": "java"}, timeout=caps.seconds("lane-b-java"))
        assert seen["config"]["stepTimeoutSeconds"] == 1770


class TestTheVenvListing:
    def test_a_listing_past_its_cap_says_so_rather_than_returning_nothing(self, tmp_path, monkeypatch):
        # Other failures return None and show only as dependency coverage;
        # a cap that fired is raised, so the caller's record names it.
        python = tmp_path / "venv" / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.write_text("")
        monkeypatch.setattr(containment, "interpreter_mounts", lambda p: [])

        def slow(plan, timeout):
            raise containment.ContainmentTimeout(caps.timed_out("python-env, in its container,", timeout))

        monkeypatch.setattr(containment, "run", slow)
        with pytest.raises(containment.ContainmentTimeout, match=r"within its 60 s cap \(C-196"):
            scipsource.venv_environment(str(tmp_path / "venv"), ".venv")

    def test_a_timeout_is_still_a_containment_error(self):
        # Every catch that degrades on a ContainmentError still does.
        assert issubclass(containment.ContainmentTimeout, containment.ContainmentError)
