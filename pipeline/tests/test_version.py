"""ADR-103: the Hobbes layer has one version, and every place that states
it agrees with the root ``VERSION`` file — the Python package, its
pyproject, the Go ``version`` package, and the three Node helpers'
package.json (and lockfiles). A bump is one edit per file, and this test
is what makes forgetting one a red suite rather than a wrong stamp."""
from __future__ import annotations

import json
import pathlib
import re
import tomllib

import hobbes

ROOT = pathlib.Path(__file__).resolve().parents[2]

# semver pre-release → PEP 440, the one place the two spellings meet:
# 0.1.3-beta is 0.1.3b0 to pip and uv (ADR-103 §5).
PEP440 = {"alpha": "a0", "beta": "b0", "preview": "rc0", "rc": "rc0"}


def pep440(version: str) -> str:
    base, _, pre = version.partition("-")
    return base + (PEP440[pre] if pre else "")


def test_root_version_file_is_the_one_version():
    version = (ROOT / "VERSION").read_text().strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+(-(alpha|beta|preview|rc))?", version), version
    assert hobbes.__version__ == version
    assert tomllib.loads((ROOT / "pipeline" / "pyproject.toml").read_text())["project"]["version"] == pep440(version)
    go = (ROOT / "go" / "internal" / "version" / "version.go").read_text()
    assert re.search(r'const Version = "([^"]+)"', go).group(1) == version
    for helper in ("tsextract", "scip", "web"):
        assert json.loads((ROOT / helper / "package.json").read_text())["version"] == version, helper
        lock = json.loads((ROOT / helper / "package-lock.json").read_text())
        assert lock["version"] == version and lock["packages"][""]["version"] == version, helper
